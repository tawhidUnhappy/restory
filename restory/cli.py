"""restory.cli — Master command-line dispatcher for restory."""

from __future__ import annotations

import difflib
import importlib
import sys

from restory import __version__, __product_name__
from restory.isolation import apply_isolation


def _force_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


_force_utf8_stdio()
apply_isolation()

COMMANDS: dict[str, tuple[str, str, str, str]] = {
    # System & Environment
    "doctor": ("restory.tools_manager", "doctor_main", "Setup", "Check environment, GPU, and tool readiness."),
    "install-tool": ("restory.tools_manager", "install_tool_main", "Setup", "Install or update an isolated AI tool."),

    # Acquisition & Cropping
    "download": ("restory.download", "download_main", "Acquire", "Download chapters from MangaDex with page verification."),
    "style-detect": ("restory.panels", "style_detect_main", "Cropping", "Detect webtoon vs paged manga format."),
    "page-split": ("restory.panels", "page_split_main", "Cropping", "Detect paged manga panel boxes metadata."),
    "webtoon-split": ("restory.panels", "webtoon_split_main", "Cropping", "Detect webtoon strip panel cuts metadata."),
    "crop-editor": ("restory.web_crop_editor", "crop_editor_main", "Cropping", "Launch WebUI for paged panel bounding box editing."),
    "webtoon-editor": ("restory.web_webtoon_editor", "webtoon_editor_main", "Cropping", "Launch WebUI for webtoon strip cut editing."),

    # Sheets & Packaging
    "panel-reading-sheets": ("restory.sheets", "reading_sheets_main", "Sheets", "Render multi-panel reading sheets."),
    "sheets-pack": ("restory.sheets", "sheets_pack_main", "Sheets", "Pack reading/review sheets into split ZIPs <= 1 GB."),

    # Narration & Scripting
    "narration-check": ("restory.narration", "narration_check_main", "Scripting", "Validate narration.json contract rules."),
    "narration-edit": ("restory.narration", "narration_edit_main", "Scripting", "Edit narration script entries via CLI."),
    "narration-editor": ("restory.web_narration_editor", "narration_editor_main", "Scripting", "Launch WebUI for side-by-side narration editing."),

    # Audio & Subtitles
    "video-audio": ("restory.audio", "audio_main", "Audio", "Synthesize audio with edge fading & provenance."),
    "video-subtitles": ("restory.subtitles", "subtitles_main", "Audio", "Generate .ass/.srt subtitles using Whisper."),

    # Video Pipeline & Quality
    "video": ("restory.video", "video_main", "Video", "Render, join, and normalize recap videos."),
    "video-quality": ("restory.quality", "quality_main", "Video", "Run video stream and quality gate checks."),

    # Publishing & Thumbnails
    "thumbnail-candidates": ("restory.thumbnail", "candidates_main", "Publishing", "Score panels for thumbnail selection."),
    "thumbnail-compose": ("restory.thumbnail", "compose_main", "Publishing", "Compose 1280x720 thumbnail with markup."),
}


def print_help() -> None:
    print(f"{__product_name__} v{__version__} — Standalone Manga & Webtoon Recap Video Production\n")
    print("Usage: restory <command> [args...]\n")
    print("Available Commands:")

    grouped: dict[str, list[tuple[str, str]]] = {}
    for cmd, (_, _, group, desc) in COMMANDS.items():
        grouped.setdefault(group, []).append((cmd, desc))

    for group, cmds in grouped.items():
        print(f"\n  [{group}]")
        for cmd, desc in cmds:
            print(f"    {cmd:<22} {desc}")
    print()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        print_help()
        return 0

    command, rest = args[0], args[1:]
    if command not in COMMANDS:
        print(f"[ERROR] Unknown command '{command}'", file=sys.stderr)
        matches = difflib.get_close_matches(command, list(COMMANDS.keys()), n=3)
        if matches:
            print(f"Did you mean: {', '.join(matches)}?", file=sys.stderr)
        return 2

    module_path, func_name, _, _ = COMMANDS[command]
    module = importlib.import_module(module_path)
    func = getattr(module, func_name)
    sys.argv = [f"{__product_name__} {command}", *rest]
    return func() or 0


if __name__ == "__main__":
    raise SystemExit(main())