"""restory.thumbnail — Thumbnail candidate scoring and composition."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def score_panel(path: Path) -> dict | None:
    try:
        with Image.open(path) as handle:
            handle.draft("L", (512, 512))
            grey = handle.convert("L")
            w, h = handle.size
            sample = np.asarray(grey.resize((160, 90)), dtype="float32") / 255.0
    except Exception:
        return None

    if w < 10 or h < 10:
        return None

    detail = float(sample.std())
    ink = float((sample < 0.5).mean())
    ratio = w / float(h)

    detail_score = min(1.0, detail / 0.30)
    ink_score = max(0.0, 1.0 - abs(ink - 0.28) / 0.45)
    shape_score = max(0.0, 1.0 - abs(ratio - (16/9)) / (16/9))
    size_score = min(1.0, (w * h) / (1280 * 720))

    score = (0.40 * detail_score + 0.25 * ink_score + 0.20 * shape_score + 0.15 * size_score)
    return {
        "file": path.name,
        "path": str(path),
        "item": path.parent.parent.name,
        "score": round(score, 3),
        "width": w,
        "height": h,
    }


def candidates_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"{__product_name__} thumbnail-candidates")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    root = args.project_root.resolve()
    manga_name = root.name

    panels = list(root.rglob("panels/*.jpg")) + list(root.rglob("panels/*.png"))
    if not panels:
        print(f"[ERROR] No panels found under {root}", file=sys.stderr)
        return 1

    scored = [s for p in panels if (s := score_panel(p)) is not None]
    scored.sort(key=lambda x: x["score"], reverse=True)
    shortlist = scored[:args.top]

    if args.as_json:
        print(json.dumps({"manga_name": manga_name, "candidates": shortlist}, ensure_ascii=False))
    else:
        print(f"Top {len(shortlist)} Thumbnail Candidates for '{manga_name}':")
        for idx, c in enumerate(shortlist, 1):
            print(f"  #{idx:02d} [{c['score']:.2f}] {c['item']}/{c['file']} ({c['width']}x{c['height']})")
    return 0


def compose_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"{__product_name__} thumbnail-compose")
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--text", default="RECAP")
    args = parser.parse_args(argv)

    base_path = args.base.resolve()
    out_path = args.output.resolve()

    if not base_path.is_file():
        print(f"[ERROR] Base image not found: {base_path}", file=sys.stderr)
        return 1

    img = Image.open(base_path).convert("RGB")
    canvas = Image.new("RGB", (1280, 720), (0, 0, 0))

    scale = max(1280 / float(img.width), 720 / float(img.height))
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left = (resized.width - 1280) // 2
    top = (resized.height - 720) // 2
    canvas.paste(resized.crop((left, top, left + 1280, top + 720)), (0, 0))

    draw = ImageDraw.Draw(canvas)
    draw.text((60, 60), args.text.upper(), fill=(255, 230, 0))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=95)
    print(f"[OK] Composed thumbnail -> {out_path}")
    return 0