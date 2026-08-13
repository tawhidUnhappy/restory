"""restory.detectors.heuristic — Advanced Japanese paged manga panel detection engine.

Features:
- Otsu adaptive thresholding for grey scans and screentones
- OpenCV contour-based frame border extraction
- Speech bubble tail & noise tolerance in 1D gutter projection cuts
- Content boundary snapping with padding guard
- Non-maximum suppression (NMS) for overlapping/nested sub-boxes
- Topological Japanese reading order sorting (RTL, Top-to-Bottom)
"""

from __future__ import annotations

import re
from pathlib import Path
import numpy as np
from PIL import Image

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def collect_images(folder: Path) -> list[Path]:
    """Collect and naturally sort images in a folder."""
    if not folder.is_dir():
        return []
    files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS]
    files.sort(key=lambda p: [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", p.stem)])
    return files


def clamp_box(raw: list | dict, w: int, h: int) -> dict | None:
    """Ensure box coordinates stay strictly within image bounds [0, 0, w, h]."""
    try:
        if isinstance(raw, dict):
            x1, y1, x2, y2 = raw["x1"], raw["y1"], raw["x2"], raw["y2"]
        else:
            x1, y1, x2, y2 = int(raw[0]), int(raw[1]), int(raw[2]), int(raw[3])
    except (TypeError, IndexError, ValueError, KeyError):
        return None

    x1, y1 = max(0, min(int(x1), w)), max(0, min(int(y1), h))
    x2, y2 = max(0, min(int(x2), w)), max(0, min(int(y2), h))
    if x2 <= x1 or y2 <= y1:
        return None

    return {
        "x1": int(x1),
        "y1": int(y1),
        "x2": int(x2),
        "y2": int(y2),
        "z_index": raw.get("z_index", 0) if isinstance(raw, dict) else 0,
        "type": raw.get("type", "rectangle") if isinstance(raw, dict) else "rectangle",
        "locked": raw.get("locked", False) if isinstance(raw, dict) else False,
        "visible": raw.get("visible", True) if isinstance(raw, dict) else True,
        "label": raw.get("label", "") if isinstance(raw, dict) else "",
    }


def is_blank_or_sliver(img_crop: Image.Image, min_dim: int = 80, max_ratio: float = 10.0) -> bool:
    """Return True if image crop is a sliver or solid blank color."""
    w, h = img_crop.size
    if w < min_dim or h < min_dim:
        return True

    ratio = max(w / float(h), h / float(w))
    if ratio > max_ratio:
        return True

    gray = np.array(img_crop.convert("L"))
    if float(gray.std()) < 5.0:
        return True

    return False


def sort_reading_order(boxes: list[dict], rtl: bool = True) -> list[dict]:
    """Sort panel bounding boxes in topological Japanese reading order (RTL, Top-to-Bottom)."""
    if len(boxes) <= 1:
        return list(boxes)

    def cy(b): return (b["y1"] + b["y2"]) / 2.0
    def cx(b): return (b["x1"] + b["x2"]) / 2.0

    n = len(boxes)
    adj = {i: [] for i in range(n)}
    in_deg = {i: 0 for i in range(n)}

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            A, B = boxes[i], boxes[j]
            overlap_y = max(0, min(A["y2"], B["y2"]) - max(A["y1"], B["y1"]))
            min_h = min(A["y2"] - A["y1"], B["y2"] - B["y1"])

            if min_h > 0 and overlap_y > 0.3 * min_h:
                is_before = (cx(A) > cx(B)) if rtl else (cx(A) < cx(B))
            else:
                is_before = cy(A) < cy(B)

            if is_before:
                adj[i].append(j)
                in_deg[j] += 1

    result = []
    visited = set()
    while len(result) < n:
        cands = [i for i in range(n) if i not in visited and in_deg[i] == 0]
        if not cands:
            unvisited = [i for i in range(n) if i not in visited]
            min_deg = min(in_deg[i] for i in unvisited)
            cands = [i for i in unvisited if in_deg[i] == min_deg]
        cands.sort(key=lambda idx: (int(cy(boxes[idx]) // 12), -cx(boxes[idx]) if rtl else cx(boxes[idx])))
        best = cands[0]
        visited.add(best)
        result.append(boxes[best])
        for nxt in adj[best]:
            in_deg[nxt] -= 1

    for idx, b in enumerate(result):
        b["z_index"] = idx

    return result


def otsu_threshold(gray: np.ndarray) -> int:
    """Compute Otsu's binarization threshold for a 2D uint8 grayscale array."""
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    total = gray.size
    current_max, threshold = 0.0, 128
    sum_total = float(np.dot(np.arange(256), hist))
    sum_b, weight_b = 0.0, 0

    for i in range(256):
        weight_b += hist[i]
        if weight_b == 0:
            continue
        weight_f = total - weight_b
        if weight_f == 0:
            break
        sum_b += i * hist[i]
        mean_b = sum_b / float(weight_b)
        mean_f = (sum_total - sum_b) / float(weight_f)
        var_between = float(weight_b) * float(weight_f) * ((mean_b - mean_f) ** 2)
        if var_between > current_max:
            current_max = var_between
            threshold = i

    return threshold


def snap_box_to_content(b: dict, gray: np.ndarray, is_white_bg: bool, pad: int = 4) -> dict:
    """Snap candidate box boundaries to tight content stroke boundaries inside box."""
    h_img, w_img = gray.shape
    x1, y1, x2, y2 = b["x1"], b["y1"], b["x2"], b["y2"]
    crop = gray[y1:y2, x1:x2]
    if crop.size == 0:
        return b

    thresh = (crop < 220) if is_white_bg else (crop > 35)
    row_sums = thresh.sum(axis=1)
    col_sums = thresh.sum(axis=0)

    nz_rows = np.where(row_sums > 2)[0]
    nz_cols = np.where(col_sums > 2)[0]

    if len(nz_rows) > 0 and len(nz_cols) > 0:
        new_y1 = max(0, y1 + nz_rows[0] - pad)
        new_y2 = min(h_img, y1 + nz_rows[-1] + 1 + pad)
        new_x1 = max(0, x1 + nz_cols[0] - pad)
        new_x2 = min(w_img, x1 + nz_cols[-1] + 1 + pad)

        if (new_x2 - new_x1) >= 60 and (new_y2 - new_y1) >= 60:
            b["x1"], b["y1"], b["x2"], b["y2"] = int(new_x1), int(new_y1), int(new_x2), int(new_y2)

    return b


def _suppress_overlapping_boxes(boxes: list[dict], w: int, h: int) -> list[dict]:
    """Remove redundant duplicate or heavily nested sub-boxes."""
    if len(boxes) <= 1:
        return boxes

    boxes_sorted = sorted(boxes, key=lambda b: (b["x2"] - b["x1"]) * (b["y2"] - b["y1"]), reverse=True)
    kept = []

    for b in boxes_sorted:
        bw, bh = b["x2"] - b["x1"], b["y2"] - b["y1"]
        area_b = bw * bh
        if area_b <= 0:
            continue

        duplicate = False
        for k in kept:
            kw, kh = k["x2"] - k["x1"], k["y2"] - k["y1"]
            area_k = kw * kh

            ix1 = max(b["x1"], k["x1"])
            iy1 = max(b["y1"], k["y1"])
            ix2 = min(b["x2"], k["x2"])
            iy2 = min(b["y2"], k["y2"])

            if ix2 > ix1 and iy2 > iy1:
                i_area = (ix2 - ix1) * (iy2 - iy1)
                iou = i_area / float(area_b + area_k - i_area)
                containment_b = i_area / float(area_b)

                if iou > 0.70 or containment_b > 0.88:
                    duplicate = True
                    break

        if not duplicate:
            kept.append(b)

    return kept


def _detect_contours_cv2(img: Image.Image) -> list[dict]:
    """Detect panel boxes using OpenCV contour finding if cv2 is available."""
    if not HAS_CV2:
        return []

    w, h = img.size
    page_area = w * h
    gray = np.array(img.convert("L"))

    top_margin = int(h * 0.02)
    bot_margin = int(h * 0.98)
    left_margin = int(w * 0.02)
    right_margin = int(w * 0.98)

    border_pixels = np.concatenate([
        gray[top_margin:bot_margin, left_margin],
        gray[top_margin:bot_margin, right_margin - 1]
    ])
    is_white_bg = float(np.median(border_pixels)) > 128.0

    thresh_type = cv2.THRESH_BINARY_INV if is_white_bg else cv2.THRESH_BINARY
    _, thresh = cv2.threshold(gray, 0, 255, thresh_type + cv2.THRESH_OTSU)

    thresh[:top_margin, :] = 0
    thresh[bot_margin:, :] = 0
    thresh[:, :left_margin] = 0
    thresh[:, right_margin:] = 0

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, hierarchy = cv2.findContours(closed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []

    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        box_area = bw * bh

        if (box_area < page_area * 0.015) or (box_area > page_area * 0.96):
            continue
        if bw < 70 or bh < 70:
            continue
        if bw > w * 0.98 and bh > h * 0.98:
            continue

        cnt_area = cv2.contourArea(cnt)
        solidity = cnt_area / float(box_area) if box_area > 0 else 0
        if solidity < 0.25:
            continue

        boxes.append({
            "x1": int(x),
            "y1": int(y),
            "x2": int(x + bw),
            "y2": int(y + bh),
            "z_index": 0,
            "type": "rectangle",
            "locked": False,
            "visible": True,
            "label": "japanese_paged_cv2",
        })

    return boxes


def detect_japanese_paged(img: Image.Image) -> list[dict]:
    """Extract manga panel boxes using adaptive Otsu thresholding, contours, and noise-tolerant gutter projection."""
    w, h = img.size
    if w < 100 or h < 100:
        return [{"x1": 0, "y1": 0, "x2": int(w), "y2": int(h), "z_index": 0, "type": "rectangle", "locked": False, "visible": True, "label": "japanese_paged"}]

    # 1. Try OpenCV Contour-based detection if available
    cv_boxes = _detect_contours_cv2(img)
    if len(cv_boxes) >= 2:
        cv_boxes = _suppress_overlapping_boxes(cv_boxes, w, h)
        if len(cv_boxes) >= 1:
            return sort_reading_order(cv_boxes, rtl=True)

    # 2. Enhanced Morphological Gutter Profiling Fallback
    gray = np.array(img.convert("L"))

    top_margin = int(h * 0.02)
    bot_margin = int(h * 0.98)
    left_margin = int(w * 0.02)
    right_margin = int(w * 0.98)

    border_pixels = np.concatenate([gray[top_margin:bot_margin, left_margin], gray[top_margin:bot_margin, right_margin - 1]])
    is_white_bg = float(np.median(border_pixels)) > 128.0

    otsu_t = otsu_threshold(gray)
    t_val = otsu_t if 30 < otsu_t < 235 else (210 if is_white_bg else 45)

    binary = (gray < t_val).astype(np.uint8) if is_white_bg else (gray > t_val).astype(np.uint8)
    binary[:top_margin, :] = 0
    binary[bot_margin:, :] = 0
    binary[:, :left_margin] = 0
    binary[:, right_margin:] = 0

    def recursive_gutter_split(x1: int, y1: int, x2: int, y2: int, depth: int = 0) -> list[dict]:
        rw, rh = x2 - x1, y2 - y1
        if depth > 7 or rw < 75 or rh < 75:
            return [{"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2), "z_index": 0, "type": "rectangle", "locked": False, "visible": True, "label": "japanese_paged"}]

        region = binary[y1:y2, x1:x2]
        row_sums = region.sum(axis=1)
        col_sums = region.sum(axis=0)

        # Allow small noise / speech bubble tail tolerance in gutters (up to 3% of row width)
        row_thresh = max(3, int(rw * 0.03))
        empty_rows = row_sums <= row_thresh
        min_gutter_h = max(3, int(rh * 0.007))

        h_cuts = []
        in_g = False
        g_start = 0
        for r in range(rh):
            if empty_rows[r]:
                if not in_g:
                    in_g = True
                    g_start = r
            else:
                if in_g:
                    in_g = False
                    if (r - g_start) >= min_gutter_h:
                        cut_y = y1 + (g_start + r) // 2
                        if cut_y - y1 > 50 and y2 - cut_y > 50:
                            h_cuts.append(int(cut_y))

        if h_cuts:
            results = []
            last_y = y1
            for cy in h_cuts:
                results.extend(recursive_gutter_split(x1, last_y, x2, cy, depth + 1))
                last_y = cy
            results.extend(recursive_gutter_split(x1, last_y, x2, y2, depth + 1))
            return results

        col_thresh = max(3, int(rh * 0.03))
        empty_cols = col_sums <= col_thresh
        min_gutter_w = max(3, int(rw * 0.007))

        v_cuts = []
        in_g = False
        g_start = 0
        for c in range(rw):
            if empty_cols[c]:
                if not in_g:
                    in_g = True
                    g_start = c
            else:
                if in_g:
                    in_g = False
                    if (c - g_start) >= min_gutter_w:
                        cut_x = x1 + (g_start + c) // 2
                        if cut_x - x1 > 50 and x2 - cut_x > 50:
                            v_cuts.append(int(cut_x))

        if v_cuts:
            results = []
            last_x = x1
            for cx in v_cuts:
                results.extend(recursive_gutter_split(last_x, y1, cx, y2, depth + 1))
                last_x = cx
            results.extend(recursive_gutter_split(last_x, y1, x2, y2, depth + 1))
            return results

        c_rows = np.where(row_sums > 0)[0]
        c_cols = np.where(col_sums > 0)[0]
        if len(c_rows) > 0 and len(c_cols) > 0:
            tx1, ty1 = x1 + int(c_cols[0]), y1 + int(c_rows[0])
            tx2, ty2 = x1 + int(c_cols[-1]) + 1, y1 + int(c_rows[-1]) + 1
            pad = 4
            tx1, ty1 = max(0, tx1 - pad), max(0, ty1 - pad)
            tx2, ty2 = min(w, tx2 + pad), min(h, ty2 + pad)
            if (tx2 - tx1) >= 60 and (ty2 - ty1) >= 60:
                return [{"x1": int(tx1), "y1": int(ty1), "x2": int(tx2), "y2": int(ty2), "z_index": 0, "type": "rectangle", "locked": False, "visible": True, "label": "japanese_paged"}]

        return [{"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2), "z_index": 0, "type": "rectangle", "locked": False, "visible": True, "label": "japanese_paged"}]

    raw_boxes = recursive_gutter_split(0, 0, w, h)
    valid_boxes = []

    for b in raw_boxes:
        bw, bh = b["x2"] - b["x1"], b["y2"] - b["y1"]
        if (bw * bh) >= (w * h) * 0.015 and bw >= 60 and bh >= 60:
            b_snapped = snap_box_to_content(b, gray, is_white_bg, pad=4)
            crop = img.crop((b_snapped["x1"], b_snapped["y1"], b_snapped["x2"], b_snapped["y2"]))
            if not is_blank_or_sliver(crop):
                valid_boxes.append(b_snapped)

    valid_boxes = _suppress_overlapping_boxes(valid_boxes, w, h)

    if not valid_boxes:
        return [{"x1": 0, "y1": 0, "x2": int(w), "y2": int(h), "z_index": 0, "type": "rectangle", "locked": False, "visible": True, "label": "japanese_paged"}]

    return sort_reading_order(valid_boxes, rtl=True)


# Alias for backwards compatibility
detect_heuristic = detect_japanese_paged