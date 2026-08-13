"""restory.detectors.hybrid — Combined MAGI v3 AI proposals with OpenCV gutter snapping and container box disintegration."""

from __future__ import annotations

from pathlib import Path
import numpy as np
from PIL import Image

from restory.detectors.magi import detect_magi_batch
from restory.detectors.heuristic import (
    detect_heuristic,
    clamp_box,
    is_blank_or_sliver,
    sort_reading_order,
)


def _box_area(b: dict) -> int:
    return max(0, b["x2"] - b["x1"]) * max(0, b["y2"] - b["y1"])


def _iou(b1: dict, b2: dict) -> float:
    x1 = max(b1["x1"], b2["x1"])
    y1 = max(b1["y1"], b2["y1"])
    x2 = min(b1["x2"], b2["x2"])
    y2 = min(b1["y2"], b2["y2"])

    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter == 0:
        return 0.0

    a1 = _box_area(b1)
    a2 = _box_area(b2)
    union = a1 + a2 - inter
    return inter / float(union) if union > 0 else 0.0


def snap_box_edges(raw_box: dict, gray: np.ndarray, search_win: int = 18) -> dict:
    """Refine box coordinates by snapping to nearest whitespace / gutter gradient minimums."""
    h, w = gray.shape
    x1, y1, x2, y2 = raw_box["x1"], raw_box["y1"], raw_box["x2"], raw_box["y2"]

    # Snap top edge y1
    if y1 > 10 and y1 < h - 10 and x2 > x1:
        top_win = gray[max(0, y1 - search_win):min(h, y1 + search_win), max(0, x1):min(w, x2)]
        if top_win.size > 0:
            row_means = top_win.mean(axis=1)
            best_idx = int(np.argmax(row_means))
            y1 = max(0, y1 - search_win) + best_idx

    # Snap bottom edge y2
    if y2 > 10 and y2 < h - 10 and x2 > x1:
        bot_win = gray[max(0, y2 - search_win):min(h, y2 + search_win), max(0, x1):min(w, x2)]
        if bot_win.size > 0:
            row_means = bot_win.mean(axis=1)
            best_idx = int(np.argmax(row_means))
            y2 = max(0, y2 - search_win) + best_idx

    # Snap left edge x1
    if x1 > 10 and x1 < w - 10 and y2 > y1:
        left_win = gray[max(0, y1):min(h, y2), max(0, x1 - search_win):min(w, x1 + search_win)]
        if left_win.size > 0:
            col_means = left_win.mean(axis=0)
            best_idx = int(np.argmax(col_means))
            x1 = max(0, x1 - search_win) + best_idx

    # Snap right edge x2
    if x2 > 10 and x2 < w - 10 and y2 > y1:
        right_win = gray[max(0, y1):min(h, y2), max(0, x2 - search_win):min(w, x2 + search_win)]
        if right_win.size > 0:
            col_means = right_win.mean(axis=0)
            best_idx = int(np.argmax(col_means))
            x2 = max(0, x2 - search_win) + best_idx

    res = dict(raw_box)
    res.update({"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)})
    return res


def _disintegrate_mega_containers(boxes: list[dict], page_w: int, page_h: int) -> list[dict]:
    """Remove giant outer container boxes that enclose multiple smaller valid panel boxes."""
    if len(boxes) <= 1:
        return boxes

    filtered = []
    for i, outer in enumerate(boxes):
        outer_area = _box_area(outer)
        children = []

        for j, inner in enumerate(boxes):
            if i == j:
                continue
            inner_area = _box_area(inner)

            # Check if inner box is substantially inside outer box
            x1 = max(outer["x1"], inner["x1"])
            y1 = max(outer["y1"], inner["y1"])
            x2 = min(outer["x2"], inner["x2"])
            y2 = min(outer["y2"], inner["y2"])
            inter_area = max(0, x2 - x1) * max(0, y2 - y1)

            if inner_area > 0 and (inter_area / float(inner_area)) > 0.82 and inner_area < 0.85 * outer_area:
                children.append(inner)

        # If box contains 2+ child panel boxes, discard the giant container box
        if len(children) >= 2 and outer_area > 0.25 * (page_w * page_h):
            continue

        filtered.append(outer)

    return filtered if filtered else boxes


def detect_hybrid_batch(img_paths: list[Path]) -> dict[Path, list[dict]]:
    """Batch CUDA Hybrid Detector: Combines AI proposals with CV projection and container disintegration."""
    ai_batch_results = detect_magi_batch(img_paths)
    out = {}

    for img_path in img_paths:
        with Image.open(img_path) as img:
            img_rgb = img.convert("RGB")
            w, h = img_rgb.size
            gray = np.array(img_rgb.convert("L"))

        ai_boxes = ai_batch_results.get(img_path, [])
        cv_boxes = detect_heuristic(img_rgb)

        candidates: list[dict] = []

        for b in ai_boxes:
            clamped = clamp_box(b, w, h)
            if not clamped:
                continue
            snapped = snap_box_edges(clamped, gray, search_win=15)
            snapped["label"] = "hybrid_ai_snapped"
            candidates.append(snapped)

        # Rescue CV panels missed by AI
        for cb in cv_boxes:
            cb_clamped = clamp_box(cb, w, h)
            if not cb_clamped:
                continue
            max_overlap = max((_iou(cb_clamped, cand) for cand in candidates), default=0.0)
            if max_overlap < 0.25:
                cb_snapped = snap_box_edges(cb_clamped, gray, search_win=12)
                cb_snapped["label"] = "hybrid_rescued_cv"
                candidates.append(cb_snapped)

        # Disintegrate giant mega-containers
        disintegrated = _disintegrate_mega_containers(candidates, w, h)

        # Deduplicate & filter blanks
        valid_boxes: list[dict] = []
        for cand in disintegrated:
            crop = img_rgb.crop((cand["x1"], cand["y1"], cand["x2"], cand["y2"]))
            if is_blank_or_sliver(crop):
                continue

            duplicate = False
            for existing in valid_boxes:
                if _iou(cand, existing) > 0.55:
                    duplicate = True
                    break

            if not duplicate:
                valid_boxes.append(cand)

        if not valid_boxes:
            valid_boxes = [b for cb in cv_boxes if (b := clamp_box(cb, w, h))]

        out[img_path] = valid_boxes

    return out


def detect_hybrid(img_path: Path) -> list[dict]:
    """Single image wrapper around detect_hybrid_batch."""
    res = detect_hybrid_batch([img_path])
    return res.get(img_path, [])