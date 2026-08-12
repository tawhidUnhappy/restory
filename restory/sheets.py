"""restory.sheets — Reading sheets, sheet ZIP packing, and AI context panel packaging."""

from __future__ import annotations

import argparse
import math
import re
import sys
import zipfile
from pathlib import Path
from PIL import Image, ImageDraw

from restory import __product_name__
from restory.layout import project_zips_dir, filter_item_dirs

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def collect_panels(panels_dir: Path) -> list[Path]:
    if not panels_dir.is_dir():
        return []
    files = [p for p in panels_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
    files.sort(key=lambda p: [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", p.stem)])
    return files


def render_reading_sheets(ch_dir: Path, per_sheet: int = 6) -> list[Path]:
    panels_dir = ch_dir / "panels"
    sheets_dir = ch_dir / "review"
    sheets_dir.mkdir(parents=True, exist_ok=True)

    panels = collect_panels(panels_dir)
    if not panels:
        return []

    cols = 2 if per_sheet <= 6 else 3
    rows = math.ceil(per_sheet / cols)
    cell_w, cell_h, pad, head_h = 600, 750, 16, 40

    created = []
    sheet_count = 0
    for start in range(0, len(panels), per_sheet):
        chunk = panels[start:start + per_sheet]
        sheet_w = cols * cell_w + (cols + 1) * pad
        sheet_h = rows * cell_h + (rows + 1) * pad
        sheet = Image.new("RGB", (sheet_w, sheet_h), (20, 20, 20))
        draw = ImageDraw.Draw(sheet)

        for idx, img_path in enumerate(chunk):
            r, c = divmod(idx, cols)
            x = pad + c * (cell_w + pad)
            y = pad + r * (cell_h + pad)
            draw.rectangle([x, y, x + cell_w, y + cell_h], fill=(35, 35, 35), outline=(80, 80, 80), width=2)
            draw.text((x + 12, y + 8), f"Panel {start + idx + 1}: {img_path.name}", fill=(255, 230, 0))

            with Image.open(img_path) as im:
                thumb = im.convert("RGB")
                thumb.thumbnail((cell_w - 24, cell_h - head_h - 24), Image.LANCZOS)
                sheet.paste(thumb, (x + (cell_w - thumb.width) // 2, y + head_h + (cell_h - head_h - thumb.height) // 2))

        sheet_count += 1
        out_path = sheets_dir / f"reading_sheet_{sheet_count:02d}.jpg"
        sheet.save(out_path, quality=92)
        created.append(out_path)

    return created


def reading_sheets_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"{__product_name__} panel-reading-sheets")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--items", nargs="*")
    parser.add_argument("--per-sheet", type=int, default=6)
    args = parser.parse_args(argv)

    root = args.project_root.resolve()
    item_dirs = [d for d in root.iterdir() if d.is_dir() and (d / "panels").is_dir()]
    item_dirs = filter_item_dirs(item_dirs, args.items)

    total_sheets = 0
    for ch_dir in item_dirs:
        sheets = render_reading_sheets(ch_dir, per_sheet=args.per_sheet)
        total_sheets += len(sheets)
        print(f"--> [OK] Chapter {ch_dir.name}: Rendered {len(sheets)} reading sheet(s) in {ch_dir / 'review'}")

    print(f"\nRendered {total_sheets} reading sheet(s) across {len(item_dirs)} chapter(s).")
    return 0


def sheets_pack_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"{__product_name__} sheets-pack")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--max-size-mb", type=int, default=1000)
    args = parser.parse_args(argv)

    root = args.project_root.resolve()
    manga_name = root.name
    zips_dir = project_zips_dir(manga_name)
    zips_dir.mkdir(parents=True, exist_ok=True)

    sheets = sorted(list(root.rglob("review/*.jpg")) + list(root.rglob("review/*.png")))
    if not sheets:
        print(f"[ERROR] No review/reading sheets found under {root}", file=sys.stderr)
        return 1

    max_bytes = args.max_size_mb * 1024 * 1024
    vol, curr_bytes = 1, 0
    zip_path = zips_dir / f"{manga_name}_sheets_part_{vol:02d}.zip"
    zf = zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED)

    for sheet in sheets:
        sz = sheet.stat().st_size
        if curr_bytes + sz > max_bytes and curr_bytes > 0:
            zf.close()
            vol += 1
            curr_bytes = 0
            zip_path = zips_dir / f"{manga_name}_sheets_part_{vol:02d}.zip"
            zf = zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED)

        arcname = f"{sheet.parent.parent.name}/{sheet.parent.name}/{sheet.name}"
        zf.write(sheet, arcname=arcname)
        curr_bytes += sz

    zf.close()
    print(f"[OK] Packed {len(sheets)} sheet(s) into {vol} ZIP archive(s) under {zips_dir}")
    return 0