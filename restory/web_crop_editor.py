"""restory.web_crop_editor — Launcher for Paged Manga Crop & Layer WebUI Editor."""

from __future__ import annotations

import argparse
from pathlib import Path

from restory import __product_name__
from restory.web.server_crop import run_crop_server


def crop_editor_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"{__product_name__} crop-editor")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--item", default="01")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")

    args = parser.parse_args(argv)
    root = args.project_root.resolve()

    return run_crop_server(
        project_root=root,
        item=args.item,
        port=args.port,
        open_browser=not args.no_browser,
    )