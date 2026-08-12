"""restory.detectors.hybrid — Combined MAGI v3 AI proposals with OpenCV gutter snapping."""

from __future__ import annotations

from pathlib import Path
import numpy as np
from PIL import Image

from restory.detectors.magi import detect_magi
from restory.detectors.heuristic import detect_heuristic, clamp_box


def detect_hybrid(img_path: Path) -> list[dict]:
    """MAGI v3 AI panel proposal refined with OpenCV local whitespace gradient snapping."""
    raw_boxes = detect_magi(img_path)

    with Image.open(img_path) as img:
        w, h = img.size
        gray = np.array(img.convert("L"))

    snapped_boxes = []
    for b in raw_boxes:
        x1, y1, x2, y2 = b["x1"], b["y1"], b["x2"], b["y2"]

        # Local whitespace snapping search window (+/- 15px)
        y1_win = gray[max(0, y1 - 15):min(h, y1 + 15), x1:x2]
        if y1_win.size > 0:
            y1 = max(0, y1 - 15) + int(np.argmax(y1_win.mean(axis=1)))

        y2_win = gray[max(0, y2 - 15):min(h, y2 + 15), x1:x2]
        if y2_win.size > 0:
            y2 = max(0, y2 - 15) + int(np.argmax(y2_win.mean(axis=1)))

        clamped = clamp_box({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "z_index": b.get("z_index", 0), "label": "hybrid_ai_cv"}, w, h)
        if clamped:
            snapped_boxes.append(clamped)

    return snapped_boxes if snapped_boxes else raw_boxes