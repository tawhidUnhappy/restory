"""restory.layout — Central path resolver separating deletable data from surviving runtime."""

from __future__ import annotations

import json
import os
from pathlib import Path
from restory.isolation import get_install_root

DATA_DIRNAME = "data"
RUNTIME_DIRNAME = "runtime"


def workspace_root() -> Path:
    """Return the active workspace root."""
    if "RESTORY_PROJECT_ROOT" in os.environ:
        return Path(os.environ["RESTORY_PROJECT_ROOT"]).expanduser().resolve()
    return get_install_root()


def data_root() -> Path:
    """Return data/ — home for deletable production outputs."""
    return workspace_root() / DATA_DIRNAME


def runtime_root() -> Path:
    """Return runtime/ — home for surviving tools, caches, and state."""
    return get_install_root() / RUNTIME_DIRNAME


def library_root() -> Path:
    """Return data/library/ containing all manga project folders."""
    return data_root() / "library"


def project_dir(manga_name: str) -> Path:
    """Return the isolated root for a specific manga project."""
    clean_name = manga_name.strip("/\\ ")
    return library_root() / clean_name


def chapter_dir(manga_name: str, chapter: str) -> Path:
    """Return the folder for a specific chapter (e.g. data/library/manga/01)."""
    ch_str = f"{int(float(chapter)):02d}" if chapter.replace(".", "", 1).isdigit() else chapter
    return project_dir(manga_name) / ch_str


def project_manga_json(manga_name: str) -> Path:
    """Return path to project's manga.json metadata ledger."""
    return project_dir(manga_name) / "manga.json"


def project_memory_json(manga_name: str) -> Path:
    """Return path to project's MEMORY.json story memory."""
    return project_dir(manga_name) / "MEMORY.json"


def project_audio_dir(manga_name: str, chapter: str) -> Path:
    return chapter_dir(manga_name, chapter) / "audio"


def project_faded_audio_dir(manga_name: str, chapter: str) -> Path:
    return chapter_dir(manga_name, chapter) / "audio_faded"


def project_output_dir(manga_name: str) -> Path:
    return project_dir(manga_name) / "output"


def project_subtitles_dir(manga_name: str) -> Path:
    return project_dir(manga_name) / "subtitles"


def project_zips_dir(manga_name: str) -> Path:
    return project_dir(manga_name) / "zips"


def project_review_dir(manga_name: str) -> Path:
    return project_dir(manga_name) / "review"


def project_work_dir(manga_name: str) -> Path:
    return project_dir(manga_name) / "work"


def tools_root() -> Path:
    return runtime_root() / "tools"


def tool_dir(tool_name: str) -> Path:
    return tools_root() / tool_name


def ensure_project_layout(manga_name: str) -> Path:
    """Create all standard project subdirectories if they do not exist."""
    p_dir = project_dir(manga_name)
    p_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("output", "subtitles", "zips", "review", "work"):
        (p_dir / sub).mkdir(exist_ok=True)
    return p_dir


def normalize_chapter_name(chapter: str) -> str:
    """Normalize chapter identifier (e.g. '1' -> '01', '01' -> '01')."""
    raw = str(chapter).strip()
    if raw.replace(".", "", 1).isdigit():
        try:
            v = float(raw)
            if v.is_integer():
                return f"{int(v):02d}"
            return f"{v:g}"
        except ValueError:
            pass
    return raw


def filter_item_dirs(item_dirs: list[Path], items_spec: list[str] | None) -> list[Path]:
    """Filter chapter directories matching '1', '01', ranges ('1-5'), or 'all'."""
    if not items_spec:
        return item_dirs

    wanted = set()
    for item in items_spec:
        raw = str(item).strip().lower()
        if raw in ("all", "*"):
            return item_dirs

        wanted.add(raw)
        wanted.add(normalize_chapter_name(raw))

        if "-" in raw:
            parts = [p.strip() for p in raw.split("-", 1)]
            if parts[0].replace(".", "", 1).isdigit() and parts[1].replace(".", "", 1).isdigit():
                try:
                    start_v, end_v = float(parts[0]), float(parts[1])
                    start_v, end_v = min(start_v, end_v), max(start_v, end_v)
                    for d in item_dirs:
                        norm_d = normalize_chapter_name(d.name)
                        try:
                            v = float(norm_d)
                            if start_v <= v <= end_v:
                                wanted.add(d.name)
                                wanted.add(norm_d)
                        except ValueError:
                            pass
                except ValueError:
                    pass

    return [d for d in item_dirs if d.name in wanted or normalize_chapter_name(d.name) in wanted]