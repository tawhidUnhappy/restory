"""restory.config — Configuration loader for system and project settings."""

from __future__ import annotations

import json
from pathlib import Path
from restory.isolation import get_install_root
from restory.layout import workspace_root, project_manga_json

SYSTEM_CONFIG_FILE = "config.system.json"
SYSTEM_CONFIG_EXAMPLE = "config.system.example.json"


class ConfigError(RuntimeError):
    """Raised when configuration is missing or unparseable."""


def load_system_config() -> dict:
    """Load system-wide configuration from config.system.json (or example fallback)."""
    root = get_install_root()
    primary = root / SYSTEM_CONFIG_FILE
    example = root / SYSTEM_CONFIG_EXAMPLE

    target = primary if primary.is_file() else example
    if not target.is_file():
        return {}

    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ConfigError(f"Invalid JSON in {target}: {exc}") from exc


def load_project_manga_json(manga_name: str) -> dict:
    """Load the project's source ledger (data/library/<manga_name>/manga.json)."""
    path = project_manga_json(manga_name)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc


def save_project_manga_json(manga_name: str, data: dict) -> Path:
    """Save or update data/library/<manga_name>/manga.json."""
    path = project_manga_json(manga_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path