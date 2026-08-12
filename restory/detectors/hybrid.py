"""restory.detectors.hybrid — Combined MAGI v3 AI proposals with OpenCV gutter snapping."""

from __future__ import annotations

from pathlib import Path
import numpy as np
from PIL import Image

from restory.detectors.magi import detect_magi
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


def snap_box_edges(raw_box: dict, gray: np.ndarray, search_win: int = 20) -> dict:
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


def detect_hybrid(img_path: Path) -> list[dict]:
    """Clever Hybrid Panel Detector: Combines AI proposals (MAGI v3) with CV projection profiling.

    Logic:
    1. Obtains AI proposals (MAGI v3 or fallback).
    2. Runs OpenCV heuristic cuts on the source image.
    3. Snaps AI box edges to local whitespace/gutter boundaries.
    4. If an AI box is oversized and contains multiple CV panels, splits it along CV gutters.
    5. Rescues CV panels missed by AI if they are uncovered.
    6. Filters blanks/slivers and removes heavy duplicates via IoU.
    7. Clamps and sorts in reading order.
    """
    with Image.open(img_path) as img:
        img_rgb = img.convert("RGB")
        w, h = img_rgb.size
        gray = np.array(img_rgb.convert("L"))

    # 1. AI Proposals
    ai_boxes = detect_magi(img_path)

    # 2. CV Proposals
    cv_boxes = detect_heuristic(img_rgb)

    candidates: list[dict] = []

    # 3. Refine & Snap AI Boxes
    for b in ai_boxes:
        clamped = clamp_box(b, w, h)
        if not clamped:
            continue

        snapped = snap_box_edges(clamped, gray, search_win=18)
        snapped["label"] = "hybrid_ai_snapped"

        # Check if this AI box is a mega-container covering multiple CV boxes
        ai_area = _box_area(snapped)
        sub_cv = []
        for cb in cv_boxes:
            cb_clamped = clamp_box(cb, w, h)
            if not cb_clamped:
                continue
            x1 = max(snapped["x1"], cb_clamped["x1"])
            y1 = max(snapped["y1"], cb_clamped["y1"])
            x2 = min(snapped["x2"], cb_clamped["x2"])
            y2 = min(snapped["y2"], cb_clamped["y2"])
            inter = max(0, x2 - x1) * max(0, y2 - y1)
            if inter > 0.80 * _box_area(cb_clamped):
                sub_cv.append(cb_clamped)

        if len(sub_cv) >= 2 and ai_area > 0.35 * (w * h):
            # Split AI container into its CV constituent panels
            for scb in sub_cv:
                scb_snapped = snap_box_edges(scb, gray, search_win=12)
                scb_snapped["label"] = "hybrid_split"
                candidates.append(scb_snapped)
        else:
            candidates.append(snapped)

    # 4. Rescue Missed CV Panels
    for cb in cv_boxes:
        cb_clamped = clamp_box(cb, w, h)
        if not cb_clamped:
            continue

        # Check overlap with existing candidates
        max_overlap = max((_iou(cb_clamped, cand) for cand in candidates), default=0.0)
        if max_overlap < 0.25:
            # Uncovered panel detected by CV
            cb_snapped = snap_box_edges(cb_clamped, gray, search_win=12)
            cb_snapped["label"] = "hybrid_rescued_cv"
            candidates.append(cb_snapped)

    # 5. Filter out blanks/slivers and deduplicate via IoU
    valid_boxes: list[dict] = []
    for cand in candidates:
        crop = img_rgb.crop((cand["x1"], cand["y1"], cand["x2"], cand["y2"]))
        if is_blank_or_sliver(crop):
            continue

        # Non-Maximum Suppression (IoU > 0.60)
        duplicate = False
        for existing in valid_boxes:
            if _iou(cand, existing) > 0.60:
                duplicate = True
                break

        if not duplicate:
            valid_boxes.append(cand)

    # If no valid boxes survived, fallback to CV boxes
    if not valid_boxes:
        valid_boxes = [b for cb in cv_boxes if (b := clamp_box(cb, w, h))]

    return valid_boxes