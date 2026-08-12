"""restory.memory — MEMORY.json story memory manager and protocol implementation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from restory.layout import project_memory_json


class MemoryError(RuntimeError):
    """Raised when MEMORY.json is invalid or corrupted."""


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_memory(manga_name: str, agent: str = "human", force: bool = False) -> Path:
    """Initialize a fresh MEMORY.json for a project."""
    path = project_memory_json(manga_name)
    if path.is_file() and not force:
        raise MemoryError(f"MEMORY.json already exists at {path}.")

    data = {
        "version": 2,
        "project": manga_name,
        "updated_at": _iso_now(),
        "updated_by": agent,
        "brief": [
            "style: high-engagement YouTube recap; casual persona.",
            "batch: Project initialized."
        ],
        "characters": {},
        "beats": {},
        "decisions": [],
        "open_questions": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_memory(manga_name: str) -> dict[str, Any]:
    """Load and verify MEMORY.json for a project."""
    path = project_memory_json(manga_name)
    if not path.is_file():
        init_memory(manga_name, agent="system", force=True)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise MemoryError(f"Failed to parse {path}: {exc}") from exc

    return data


def save_memory(manga_name: str, data: dict[str, Any], agent: str = "system") -> Path:
    """Save updated memory and enforce brief block <= 40 lines."""
    path = project_memory_json(manga_name)
    data["updated_at"] = _iso_now()
    data["updated_by"] = agent

    brief = data.get("brief", [])
    if len(brief) > 40:
        data["brief"] = brief[:40]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def add_beat(manga_name: str, chapter: str, panel: str, beat_text: str, conf: str = "high") -> dict[str, Any]:
    """Record a story beat tied to a panel image."""
    data = load_memory(manga_name)
    beats = data.setdefault("beats", {}).setdefault(chapter, [])
    entry = {"panel": panel, "beat": beat_text, "conf": conf}
    beats.append(entry)
    save_memory(manga_name, data)
    return entry


def add_character(manga_name: str, name: str, role: str, appearance: str, speech_style: str = "normal") -> dict[str, Any]:
    """Register or update a character in story memory."""
    data = load_memory(manga_name)
    chars = data.setdefault("characters", {})
    entry = {"role": role, "appearance": appearance, "speech_style": speech_style, "conf": "high"}
    chars[name] = entry
    save_memory(manga_name, data)
    return entry