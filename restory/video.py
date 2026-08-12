"""restory.video — Item rendering, video joining, BGM auto-ducking, and EBU R128 loudness normalization."""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

from restory import __product_name__
from restory.config import load_system_config
from restory.layout import project_output_dir, filter_item_dirs
from restory.narration import validate_narration_json

VIDEO_WIDTH, VIDEO_HEIGHT = 1920, 1080
VIDEO_FPS = 30


def probe_duration(path: Path) -> float:
    """Return stream duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(res.stdout.strip())
    except (ValueError, AttributeError):
        return 1.0


def blur_background_filter(width: int = VIDEO_WIDTH, height: int = VIDEO_HEIGHT) -> str:
    small_w, small_h = max(16, width // 4), max(16, height // 4)
    return (
        f"[0:v]format=rgba,split=2[bgsrc][fgsrc];"
        f"[bgsrc]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,scale={small_w}:{small_h},"
        f"gblur=sigma=7.0:steps=1,scale={width}:{height},"
        f"eq=brightness=-0.06:saturation=1.08[bg];"
        f"[fgsrc]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"setsar=1,format=rgba[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=rgb24,setsar=1[v]"
    )


def render_chapter_item(ch_dir: Path, output_dir: Path, fps: int = VIDEO_FPS) -> Path | None:
    narration_file = ch_dir / "narration.json"
    if not narration_file.is_file():
        return None

    try:
        entries = validate_narration_json(ch_dir, require_panels=True)
    except Exception as exc:
        print(f"Error reading narration in {ch_dir}: {exc}", file=sys.stderr)
        return None

    panels_dir = ch_dir / "panels"
    audio_dir = ch_dir / "audio_faded"
    if not audio_dir.is_dir():
        audio_dir = ch_dir / "audio"

    output_dir.mkdir(parents=True, exist_ok=True)
    final_mp4 = output_dir / f"item_{ch_dir.name}.mp4"
    print(f"\n--> Rendering Video for Chapter '{ch_dir.name}' ({len(entries)} entries)...")

    work_dir = ch_dir / "work" / "segments"
    work_dir.mkdir(parents=True, exist_ok=True)

    segment_mp4s = []
    vf_filter = blur_background_filter()

    for idx, entry in enumerate(entries, start=1):
        img_name = entry["image"]
        img_path = panels_dir / img_name
        stem = Path(img_name).stem
        audio_path = audio_dir / f"{stem}.wav"

        if not img_path.is_file() or not audio_path.is_file():
            continue

        audio_dur = probe_duration(audio_path)
        pause_ms = entry.get("pause_after_ms", 0)
        total_dur = audio_dur + (pause_ms / 1000.0)
        frames = max(1, math.ceil(total_dur * fps))

        seg_mp4 = work_dir / f"seg_{idx:04d}_{stem}.mp4"

        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-framerate", str(fps),
            "-i", str(img_path), "-i", str(audio_path),
            "-vf", vf_filter,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-frames:v", str(frames),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(seg_mp4)
        ]
        res = subprocess.run(cmd)
        if res.returncode == 0 and seg_mp4.is_file():
            segment_mp4s.append(seg_mp4)

    if not segment_mp4s:
        return None

    concat_txt = work_dir / "concat.txt"
    with open(concat_txt, "w", encoding="utf-8") as f:
        f.write("ffconcat version 1.0\n")
        for seg in segment_mp4s:
            f.write(f"file '{seg.resolve().as_posix()}'\n")

    concat_cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_txt),
        "-c", "copy", "-movflags", "+faststart",
        str(final_mp4)
    ]
    subprocess.run(concat_cmd)
    shutil.rmtree(work_dir, ignore_errors=True)

    return final_mp4 if final_mp4.is_file() else None


def join_item_videos(item_mp4s: list[Path], output_mp4: Path) -> Path:
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_mp4.parent / "temp_join"
    temp_dir.mkdir(parents=True, exist_ok=True)
    concat_txt = temp_dir / "full_concat.txt"

    with open(concat_txt, "w", encoding="utf-8") as f:
        f.write("ffconcat version 1.0\n")
        for mp4 in item_mp4s:
            f.write(f"file '{mp4.resolve().as_posix()}'\n")

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_txt),
        "-c", "copy", "-movflags", "+faststart",
        str(output_mp4)
    ]
    subprocess.run(cmd, check=True)
    shutil.rmtree(temp_dir, ignore_errors=True)
    return output_mp4


def add_background_music(video_in: Path, video_out: Path, bgm_file: Path, bgm_db: float = -28.0) -> Path:
    filter_complex = (
        f"[0:a]volume=1.2,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[narr];"
        f"[1:a]volume={bgm_db}dB,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[music];"
        f"[narr][music]amix=inputs=2:duration=first:dropout_transition=3:normalize=0,alimiter=level=disabled:limit=0.95[a]"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video_in),
        "-stream_loop", "-1", "-i", str(bgm_file.resolve()),
        "-filter_complex", filter_complex,
        "-map", "0:v:0", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", str(video_out)
    ]
    subprocess.run(cmd, check=True)
    return video_out


def normalize_audio(input_mp4: Path, output_mp4: Path, target_i: float = -14.0, target_tp: float = -1.5) -> Path:
    """Two-pass EBU R128 loudness normalization."""
    first_pass_cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(input_mp4),
        "-map", "0:a:0",
        "-af", f"loudnorm=I={target_i}:TP={target_tp}:LRA=11:print_format=json",
        "-f", "null", "-"
    ]
    res = subprocess.run(first_pass_cmd, capture_output=True, text=True)
    matches = re.findall(r"\{\s*\"input_i\".*?\}", res.stderr or "", flags=re.DOTALL)
    if not matches:
        return input_mp4

    data = json.loads(matches[-1])
    filter_str = (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA=11:"
        f"measured_I={data['input_i']}:measured_TP={data['input_tp']}:"
        f"measured_LRA={data['input_lra']}:measured_thresh={data['input_thresh']}:"
        f"offset={data['target_offset']}:linear=true:print_format=summary,"
        "aresample=48000:async=1:first_pts=0"
    )

    second_pass_cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(input_mp4),
        "-map", "0:v:0", "-map", "0:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-af", filter_str,
        "-movflags", "+faststart",
        str(output_mp4)
    ]
    subprocess.run(second_pass_cmd, check=True)
    return output_mp4


def video_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"{__product_name__} video")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--items", nargs="*")
    parser.add_argument("--build-long-video", action="store_true")
    parser.add_argument("--normalize-audio", action="store_true")

    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    manga_name = root.name

    sys_cfg = load_system_config()
    bgm_file = sys_cfg.get("bgm", {}).get("file")
    bgm_db = float(sys_cfg.get("bgm", {}).get("volume_db", -28.0))

    item_dirs = [d for d in root.iterdir() if d.is_dir() and (d / "narration.json").is_file()]
    item_dirs = filter_item_dirs(item_dirs, args.items)

    output_dir = project_output_dir(manga_name) / "items"
    output_dir.mkdir(parents=True, exist_ok=True)

    rendered_mp4s = []
    for ch_dir in item_dirs:
        item_mp4 = render_chapter_item(ch_dir, output_dir)
        if item_mp4 and item_mp4.is_file():
            rendered_mp4s.append(item_mp4)

    if not rendered_mp4s:
        print("[ERROR] No item videos could be rendered.", file=sys.stderr)
        return 1

    if args.build_long_video:
        full_recap_mp4 = project_output_dir(manga_name) / f"{manga_name}_full_recap.mp4"
        print(f"\n--> Joining item videos into full recap: {full_recap_mp4.name}...")
        join_item_videos(rendered_mp4s, full_recap_mp4)

        if bgm_file and Path(bgm_file).is_file():
            print(f"--> Mixing background music ({Path(bgm_file).name} @ {bgm_db} dB)...")
            mixed_mp4 = project_output_dir(manga_name) / f"{manga_name}_full_recap_bgm.mp4"
            add_background_music(full_recap_mp4, mixed_mp4, Path(bgm_file), bgm_db=bgm_db)
            full_recap_mp4 = mixed_mp4

        if args.normalize_audio:
            print(f"--> Running EBU R128 audio normalization (-14 LUFS / -1.5 dBTP)...")
            norm_mp4 = project_output_dir(manga_name) / f"{manga_name}_full_recap_normalized.mp4"
            normalize_audio(full_recap_mp4, norm_mp4)
            full_recap_mp4 = norm_mp4

    return 0