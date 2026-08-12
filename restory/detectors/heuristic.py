"""restory.detectors.heuristic — Classic OpenCV and NumPy panel detection algorithms."""

from __future__ import annotations

import re
from pathlib import Path
import numpy as np
from PIL import Image

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def collect_images(folder: Path) -> list[Path]:
    """Collect and naturally sort images in a folder."""
    if not folder.is_dir():
        return []
    files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS]
    files.sort(key=lambda p: [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", p.stem)])
    return files


def clamp_box(raw: list | dict, w: int, h: int) -> dict | None:
    """Ensure coordinates stay strictly within image dimensions [0, 0, w, h]."""
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


def is_blank_or_sliver(img_crop: Image.Image, min_dim: int = 120, max_ratio: float = 8.0) -> bool:
    """Return True if an image crop is a sliver, extreme aspect ratio, or solid color."""
    w, h = img_crop.size
    if w < min_dim or h < min_dim:
        return True

    ratio = max(w / float(h), h / float(w))
    if ratio > max_ratio:
        return True

    gray = np.array(img_crop.convert("L"))
    std_dev = float(gray.std())
    if std_dev < 8.0:
        return True

    return False


def sort_reading_order(boxes: list[dict], rtl: bool = True) -> list[dict]:
    """Sort bounding boxes topologically according to reading direction (RTL or LTR)."""
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
        cands.sort(key=lambda idx: (int(cy(boxes[idx]) // 10), -cx(boxes[idx]) if rtl else cx(boxes[idx])))
        best = cands[0]
        visited.add(best)
        result.append(boxes[best])
        for nxt in adj[best]:
            in_deg[nxt] -= 1

    for idx, b in enumerate(result):
        b["z_index"] = idx

    return result


def detect_heuristic(img: Image.Image) -> list[dict]:
    """Detect panel bounding boxes using recursive XY-cut projection profiling."""
    w, h = img.size
    if w < 100 or h < 100:
        return [{"x1": 0, "y1": 0, "x2": int(w), "y2": int(h), "z_index": 0, "type": "rectangle", "locked": False, "visible": True, "label": ""}]

    top_margin = int(h * 0.03)
    bot_margin = int(h * 0.96)
    left_margin = int(w * 0.02)
    right_margin = int(w * 0.98)

    gray = np.array(img.convert("L"))
    border_pixels = np.concatenate([gray[top_margin:bot_margin, left_margin], gray[top_margin:bot_margin, right_margin - 1]])
    is_white_bg = float(np.median(border_pixels)) > 128.0

    binary = (gray < 225).astype(np.uint8) if is_white_bg else (gray > 30).astype(np.uint8)
    binary[:top_margin, :] = 0
    binary[bot_margin:, :] = 0
    binary[:, :left_margin] = 0
    binary[:, right_margin:] = 0

    def xy_cut(x1: int, y1: int, x2: int, y2: int, depth: int = 0) -> list[dict]:
        rw, rh = x2 - x1, y2 - y1
        if depth > 8 or rw < 120 or rh < 120:
            return [{"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2), "z_index": 0, "type": "rectangle", "locked": False, "visible": True, "label": ""}]

        region = binary[y1:y2, x1:x2]
        row_sums = region.sum(axis=1)
        col_sums = region.sum(axis=0)

        row_thresh = max(4, int(rw * 0.035))
        empty_rows = row_sums <= row_thresh
        min_gutter_h = max(6, int(rh * 0.012))

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
                        if cut_y - y1 > 100 and y2 - cut_y > 100:
                            h_cuts.append(int(cut_y))

        if h_cuts:
            results = []
            last_y = y1
            for cy in h_cuts:
                results.extend(xy_cut(x1, last_y, x2, cy, depth + 1))
                last_y = cy
            results.extend(xy_cut(x1, last_y, x2, y2, depth + 1))
            return results

        col_thresh = max(4, int(rh * 0.035))
        empty_cols = col_sums <= col_thresh
        min_gutter_w = max(6, int(rw * 0.012))

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
                        if cut_x - x1 > 100 and x2 - cut_x > 100:
                            v_cuts.append(int(cut_x))

        if v_cuts:
            results = []
            last_x = x1
            for cx in v_cuts:
                results.extend(xy_cut(last_x, y1, cx, y2, depth + 1))
                last_x = cx
            results.extend(xy_cut(last_x, y1, x2, y2, depth + 1))
            return results

        c_rows = np.where(row_sums > 0)[0]
        c_cols = np.where(col_sums > 0)[0]
        if len(c_rows) > 0 and len(c_cols) > 0:
            tx1, ty1 = x1 + int(c_cols[0]), y1 + int(c_rows[0])
            tx2, ty2 = x1 + int(c_cols[-1]) + 1, y1 + int(c_rows[-1]) + 1
            pad = 6
            tx1, ty1 = max(0, tx1 - pad), max(0, ty1 - pad)
            tx2, ty2 = min(w, tx2 + pad), min(h, ty2 + pad)
            if (tx2 - tx1) >= 120 and (ty2 - ty1) >= 120:
                return [{"x1": int(tx1), "y1": int(ty1), "x2": int(tx2), "y2": int(ty2), "z_index": 0, "type": "rectangle", "locked": False, "visible": True, "label": ""}]

        return [{"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2), "z_index": 0, "type": "rectangle", "locked": False, "visible": True, "label": ""}]

    raw_boxes = xy_cut(0, 0, w, h)
    page_area = w * h
    valid_boxes = []

    for b in raw_boxes:
        bw, bh = b["x2"] - b["x1"], b["y2"] - b["y1"]
        box_area = bw * bh
        if box_area >= page_area * 0.03 and bw >= 120 and bh >= 120:
            crop = img.crop((b["x1"], b["y1"], b["x2"], b["y2"]))
            if not is_blank_or_sliver(crop):
                valid_boxes.append(b)

    if not valid_boxes:
        return [{"x1": 0, "y1": 0, "x2": int(w), "y2": int(h), "z_index": 0, "type": "rectangle", "locked": False, "visible": True, "label": ""}]

    return valid_boxes