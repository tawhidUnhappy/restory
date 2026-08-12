"""restory.subtitles — Whisper ASR subtitle generator (.ass & .srt formats)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from restory import __product_name__
from restory.layout import project_dir, project_subtitles_dir, tool_dir


def generate_subtitles_whisper(media_file: Path, out_ass: Path, out_srt: Path) -> tuple[Path, Path]:
    w_dir = tool_dir("whisper-turbo")
    out_ass.parent.mkdir(parents=True, exist_ok=True)

    worker_script = w_dir / "_whisper_worker.py"
    if not worker_script.is_file():
        code = """import sys
from pathlib import Path
from faster_whisper import WhisperModel

media = Path(sys.argv[1])
out_ass = Path(sys.argv[2])
out_srt = Path(sys.argv[3])

model = WhisperModel("deepdml/faster-whisper-large-v3-turbo-ct2", device="cuda", compute_type="float16")
segments, _ = model.transcribe(str(media), beam_size=5)

ass_lines = [
    "[Script Info]\\nScriptType: v4.00+\\nPlayResX: 1920\\nPlayResY: 1080\\n\\n",
    "[V4+ Styles]\\nFormat: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\\n",
    "Style: Default,Arial,48,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,30,30,50,1\\n\\n",
    "[Events]\\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\\n"
]
srt_lines = []

def fmt_ass(s):
    h, r = divmod(int(s), 3600); m, sec = divmod(r, 60); cs = int(round((s % 1) * 100))
    return f"{h}:{m:02d}:{sec:02d}.{min(cs, 99):02d}"

def fmt_srt(s):
    h, r = divmod(int(s), 3600); m, sec = divmod(r, 60); ms = int(round((s % 1) * 1000))
    return f"{h:02d}:{m:02d}:{sec:02d},{min(ms, 999):03d}"

for idx, seg in enumerate(segments, 1):
    txt = seg.text.strip()
    if txt:
        ass_lines.append(f"Dialogue: 0,{fmt_ass(seg.start)},{fmt_ass(seg.end)},Default,,0,0,0,,{txt}")
        srt_lines.append(f"{idx}\\n{fmt_srt(seg.start)} --> {fmt_srt(seg.end)}\\n{txt}\\n")

out_ass.write_text("\\n".join(ass_lines) + "\\n", encoding="utf-8")
out_srt.write_text("\\n".join(srt_lines) + "\\n", encoding="utf-8")
"""
        worker_script.write_text(code, encoding="utf-8")

    venv_py = w_dir / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / ("python.exe" if sys.platform == "win32" else "python")
    python_bin = str(venv_py) if venv_py.is_file() else sys.executable

    cmd = [python_bin, str(worker_script), str(media_file), str(out_ass), str(out_srt)]
    print(f"--> Running Whisper Subtitle Generator on {media_file.name}...")
    res = subprocess.run(cmd, cwd=str(w_dir), capture_output=True, text=True)

    if res.returncode != 0:
        raise RuntimeError(f"Whisper subtitle generation failed: {res.stderr}")

    return out_ass, out_srt


def subtitles_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"{__product_name__} video-subtitles")
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args(argv)

    root = args.project_root.resolve()
    manga_name = root.name

    output_dir = project_dir(manga_name) / "output"
    media_files = list(output_dir.glob("*_full*.mp4"))

    if not media_files:
        print(f"[ERROR] No full recap MP4s found in {output_dir}", file=sys.stderr)
        return 1

    latest_media = max(media_files, key=lambda f: f.stat().st_mtime)
    sub_dir = project_subtitles_dir(manga_name)

    out_ass = sub_dir / f"{latest_media.stem}.ass"
    out_srt = sub_dir / f"{latest_media.stem}.srt"

    try:
        generate_subtitles_whisper(latest_media, out_ass, out_srt)
        print(f"[OK] Generated Subtitles:\n  .ass -> {out_ass}\n  .srt -> {out_srt}")
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1