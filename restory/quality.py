"""restory.quality — Stream audit quality gate and YouTube chapter timestamp generator."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from restory import __product_name__
from restory.layout import project_output_dir
from restory.video import probe_duration


def probe_streams(path: Path) -> dict[str, Any]:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_name,codec_type,width,height,sample_rate,channels",
        "-of", "json", str(path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(res.stdout or "{}")
    except Exception:
        return {}


def format_timestamp(seconds: float) -> str:
    whole = math.floor(seconds)
    hours, rem = divmod(whole, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def generate_chapter_timestamps(manga_name: str) -> list[dict[str, Any]]:
    items_dir = project_output_dir(manga_name) / "items"
    if not items_dir.is_dir():
        return []

    item_files = sorted(
        [f for f in items_dir.glob("item_*.mp4")],
        key=lambda f: float(re.search(r"\d+(?:\.\d+)?", f.stem).group(0)) if re.search(r"\d+(?:\.\d+)?", f.stem) else 999.0
    )

    timestamps = []
    elapsed = 0.0

    for item_file in item_files:
        ch_num = re.search(r"\d+(?:\.\d+)?", item_file.stem).group(0) if re.search(r"\d+(?:\.\d+)?", item_file.stem) else "01"
        dur = probe_duration(item_file)
        timestamps.append({
            "chapter": ch_num,
            "timestamp": format_timestamp(elapsed),
            "start_seconds": round(elapsed, 2),
            "duration_seconds": round(dur, 2),
            "file": item_file.name,
        })
        elapsed += dur

    return timestamps


def quality_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"{__product_name__} video-quality")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--json", action="store_true", dest="as_json")

    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    manga_name = root.name

    items_dir = project_output_dir(manga_name) / "items"
    item_files = list(items_dir.glob("item_*.mp4")) if items_dir.is_dir() else []

    if not item_files:
        print(f"[ERROR] No rendered item videos found in {items_dir}", file=sys.stderr)
        return 1

    errors = []
    for video in item_files:
        info = probe_streams(video)
        streams = info.get("streams", [])
        has_video = any(s.get("codec_type") == "video" for s in streams)
        has_audio = any(s.get("codec_type") == "audio" for s in streams)

        if not has_video:
            errors.append(f"{video.name}: Missing video stream.")
        if not has_audio:
            errors.append(f"{video.name}: Missing audio stream.")

    timestamps = generate_chapter_timestamps(manga_name)

    report = {
        "manga_name": manga_name,
        "items_checked": len(item_files),
        "errors": errors,
        "ok": len(errors) == 0,
        "timestamps": timestamps,
    }

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(f"============================================================")
        print(f" Quality Gate Report for '{manga_name}'")
        print(f"============================================================")
        print(f" Items Verified : {len(item_files)}")
        print(f" Errors Found   : {len(errors)}")
        if timestamps:
            print(f"\n YouTube Chapter Timestamps:")
            for ts in timestamps:
                print(f"   {ts['timestamp']} Chapter {ts['chapter']}")
        print(f"============================================================")

    return 0 if len(errors) == 0 else 1