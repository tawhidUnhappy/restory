"""restory.panels — Deferred cropping metadata persistence ledger and single-pass crop executor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from restory.config import load_project_manga_json
from restory.layout import project_dir, filter_item_dirs
from restory.detectors import (
    detect_heuristic,
    detect_magi,
    detect_webtoon,
    detect_hybrid,
    sort_reading_order,
    clamp_box,
    collect_images,
)


def get_boxes_json_path(ch_dir: Path) -> Path:
    """Return path to chapter metadata ledger data/library/<manga>/<ch>/work/boxes.json."""
    work_dir = ch_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir / "boxes.json"


def load_chapter_boxes(ch_dir: Path) -> dict:
    """Load boxes.json metadata ledger for a chapter."""
    p = get_boxes_json_path(ch_dir)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _to_python_types(obj):
    """Convert NumPy types recursively to Python native types."""
    if isinstance(obj, dict):
        return {k: _to_python_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_to_python_types(v) for v in obj]
    return obj


def save_chapter_boxes(ch_dir: Path, boxes_data: dict) -> None:
    """Save boxes.json metadata ledger."""
    p = get_boxes_json_path(ch_dir)
    cleaned = _to_python_types(boxes_data)
    p.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def recrop_chapter_from_boxes(ch_dir: Path, boxes_data: dict, rtl: bool = True) -> int:
    """Execute physical image cropping pass into panels/ and review/ overlays strictly from boxes_data."""
    download_dir = ch_dir / "download"
    panels_dir = ch_dir / "panels"
    review_dir = ch_dir / "review"

    if panels_dir.is_dir():
        for old_file in panels_dir.glob("*.jpg"):
            old_file.unlink(missing_ok=True)

    panels_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)

    pages = collect_images(download_dir)
    if not pages:
        return 0

    total_cropped = 0
    pages_data = boxes_data.get("pages", {}) if isinstance(boxes_data, dict) and "pages" in boxes_data else boxes_data

    for page_no, page_path in enumerate(pages, start=1):
        img = Image.open(page_path).convert("RGB")
        w, h = img.size
        stem = page_path.stem

        raw_page_boxes = pages_data.get(stem) or pages_data.get(f"{page_no:03d}") or []
        clamped_boxes = [b for raw in raw_page_boxes if (b := clamp_box(raw, w, h))]

        # Sort reading order topologically
        boxes = sort_reading_order(clamped_boxes, rtl=rtl)

        overlay = img.copy()
        draw = ImageDraw.Draw(overlay)

        valid_panel_idx = 1
        for b in boxes:
            if not b.get("visible", True):
                continue

            crop = img.crop((b["x1"], b["y1"], b["x2"], b["y2"]))
            out_name = f"ch{ch_dir.name}_{page_no:03d}_{valid_panel_idx:02d}.jpg"
            crop.save(panels_dir / out_name, "JPEG", quality=95)

            draw.rectangle([b["x1"], b["y1"], b["x2"], b["y2"]], outline=(255, 40, 40), width=6)
            draw.text((b["x1"] + 10, b["y1"] + 10), str(valid_panel_idx), fill=(255, 40, 40))

            valid_panel_idx += 1
            total_cropped += 1

        overlay.save(review_dir / f"overlay_{page_no:03d}.jpg", "JPEG", quality=92)

    save_chapter_boxes(ch_dir, boxes_data)
    return total_cropped


def style_detect_main(argv: list[str] | None = None) -> int:
    """CLI tool to detect format type (paged vs webtoon)."""
    parser = argparse.ArgumentParser(prog="restory style-detect")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--items", nargs="*")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    root = args.project_root.resolve()
    manga_name = root.name
    item_dirs = [d for d in root.iterdir() if d.is_dir() and (d / "download").is_dir()]
    item_dirs = filter_item_dirs(item_dirs, args.items)

    if not item_dirs:
        print(f"[ERROR] No chapters with download/ folders found in {root}", file=sys.stderr)
        return 1

    ratios = []
    for item in item_dirs:
        for img_path in collect_images(item / "download"):
            try:
                with Image.open(img_path) as im:
                    w, h = im.size
                    if w > 0 and h > 0:
                        ratios.append(h / float(w))
            except Exception:
                pass

    if not ratios:
        print("[ERROR] No valid images found to measure.", file=sys.stderr)
        return 1

    median_ratio = float(np.median(ratios))
    verdict = "webtoon" if median_ratio >= 2.0 else "paged"

    res = {
        "manga_name": manga_name,
        "images_measured": len(ratios),
        "median_ratio": round(median_ratio, 2),
        "verdict": verdict,
        "recommended_command": "webtoon-split" if verdict == "webtoon" else "page-split",
    }

    if args.as_json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(f"Format Verdict for '{manga_name}': {verdict.upper()} (Median Ratio: {res['median_ratio']}:1)")
        print(f"Recommended Command: restory {res['recommended_command']}")
    return 0


def page_split_main(argv: list[str] | None = None) -> int:
    """Run detection engine on paged manga and save ONLY work/boxes.json metadata."""
    parser = argparse.ArgumentParser(prog="restory page-split")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--items", nargs="*")
    parser.add_argument("--engine", choices=["heuristic", "magi", "hybrid"], default="heuristic")
    parser.add_argument("--render", action="store_true", help="Execute physical panel cropping immediately.")
    args = parser.parse_args(argv)

    root = args.project_root.resolve()
    manga_name = root.name
    manga_ledger = load_project_manga_json(manga_name)
    rtl = manga_ledger.get("original_language", "ja") in ("ja", "zh-hk")

    item_dirs = [d for d in root.iterdir() if d.is_dir() and (d / "download").is_dir()]
    item_dirs = filter_item_dirs(item_dirs, args.items)

    for ch_dir in item_dirs:
        pages = collect_images(ch_dir / "download")
        if not pages:
            continue

        print(f"--> Page-Splitting Chapter '{ch_dir.name}' using engine '{args.engine}'...")
        boxes_dict = {"version": 2, "pages": {}}

        for page_no, page_path in enumerate(pages, start=1):
            stem = page_path.stem
            if args.engine == "magi":
                raw_boxes = detect_magi(page_path)
            elif args.engine == "hybrid":
                raw_boxes = detect_hybrid(page_path)
            else:
                with Image.open(page_path) as im:
                    raw_boxes = detect_heuristic(im)

            boxes_dict["pages"][stem] = raw_boxes

        save_chapter_boxes(ch_dir, boxes_dict)
        print(f"  [OK] Saved box metadata -> {get_boxes_json_path(ch_dir)}")

        if args.render:
            count = recrop_chapter_from_boxes(ch_dir, boxes_dict, rtl=rtl)
            print(f"  [OK] Physical render complete ({count} panels cropped).")

    print("\nDeferred page-splitting completed successfully!")
    return 0


def webtoon_split_main(argv: list[str] | None = None) -> int:
    """Run detection on webtoon strip and save metadata."""
    parser = argparse.ArgumentParser(prog="restory webtoon-split")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--items", nargs="*")
    args = parser.parse_args(argv)

    root = args.project_root.resolve()
    item_dirs = [d for d in root.iterdir() if d.is_dir() and (d / "download").is_dir()]
    item_dirs = filter_item_dirs(item_dirs, args.items)

    for ch_dir in item_dirs:
        print(f"--> Webtoon-Splitting Chapter '{ch_dir.name}'...")
        webtoon_meta = detect_webtoon(ch_dir)
        save_chapter_boxes(ch_dir, webtoon_meta)
        print(f"  [OK] Saved webtoon metadata -> {get_boxes_json_path(ch_dir)}")

    print("\nWebtoon metadata detection completed successfully!")
    return 0