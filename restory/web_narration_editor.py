"""restory.web_narration_editor — Launcher for Side-by-Side Narration WebUI Editor."""

from __future__ import annotations

import argparse
from pathlib import Path

from restory import __product_name__
from restory.web.server_narration import run_narration_server


def narration_editor_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"{__product_name__} narration-editor")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--item", default="01")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--no-browser", action="store_true")

    args = parser.parse_args(argv)
    root = args.project_root.resolve()

    return run_narration_server(
        project_root=root,
        item=args.item,
        port=args.port,
        open_browser=not args.no_browser,
    )