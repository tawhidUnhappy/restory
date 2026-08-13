"""restory.detectors.webtoon — Vertical webtoon strip density profiling & cut rescue guard."""

from __future__ import annotations

import re
from pathlib import Path
import numpy as np
from PIL import Image

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def collect_images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS]
    files.sort(key=lambda p: [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", p.stem)])
    return files


def detect_webtoon(ch_dir: Path) -> dict:
    """Stitch download page images into vertical canvas strip and detect horizontal gutter cuts."""
    download_dir = ch_dir / "download"
    pages = collect_images(download_dir)
    if not pages:
        return {"canvas_width": 800, "total_height": 0, "cuts": [0], "panels": []}

    imgs = [Image.open(p).convert("RGB") for p in pages]
    canvas_w = max(im.width for im in imgs)
    total_h = sum(im.height for im in imgs)

    combined = Image.new("RGB", (canvas_w, total_h), (255, 255, 255))
    curr_y = 0
    for im in imgs:
        if im.width != canvas_w:
            im = im.resize((canvas_w, int(im.height * canvas_w / float(im.width))), Image.LANCZOS)
        combined.paste(im, (0, curr_y))
        curr_y += im.height

    arr = np.array(combined.convert("L"))
    row_std = arr.std(axis=1)
    quiet_rows = np.where(row_std < 15.0)[0]

    cuts = [0]
    last_c = 0
    for r in quiet_rows:
        if r - last_c > 600:
            cuts.append(int(r))
            last_c = r
    cuts.append(int(total_h))

    panels_meta = []
    for idx in range(len(cuts) - 1):
        top, bot = cuts[idx], cuts[idx + 1]
        h = bot - top
        if h < 120:
            continue
        ratio = round(h / float(canvas_w), 2)
        motion = "pan_top_to_bottom" if ratio > 2.2 else "static"
        warning = "ultra_tall_panel" if ratio > 2.2 else None

        panels_meta.append({
            "id": f"panel_{idx + 1:03d}",
            "top": top,
            "bottom": bot,
            "height": h,
            "aspect_ratio": ratio,
            "camera_motion": motion,
            "motion_duration_sec": 4.5 if ratio > 2.2 else 2.5,
            "warning": warning
        })

    return {
        "version": 2,
        "format": "webtoon",
        "canvas_width": canvas_w,
        "total_height": total_h,
        "cuts": cuts,
        "panels": panels_meta
    }