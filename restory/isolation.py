"""restory.isolation — Process-level cache pinning and environment protection."""

from __future__ import annotations

import os
import sys
from pathlib import Path

CACHE_ENV_VARS = (
    "UV_CACHE_DIR",
    "UV_PYTHON_INSTALL_DIR",
    "HF_HOME",
    "HF_HUB_CACHE",
    "TRANSFORMERS_CACHE",
    "TORCH_HOME",
    "TORCH_EXTENSIONS_DIR",
    "TORCHINDUCTOR_CACHE_DIR",
    "TRITON_CACHE_DIR",
    "XDG_CACHE_HOME",
)

TARGET_ENV_VARS = (
    "VIRTUAL_ENV",
    "UV_PROJECT_ENVIRONMENT",
    "PYTHONHOME",
    "PYTHONPATH",
)


def get_install_root() -> Path:
    """Return the absolute path of the restory installation root."""
    if "RESTORY_INSTALL_ROOT" in os.environ:
        return Path(os.environ["RESTORY_INSTALL_ROOT"]).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def get_cache_root() -> Path:
    """Return the pinned cache directory inside runtime/cache."""
    return get_install_root() / "runtime" / "cache"


def cache_paths() -> dict[str, Path]:
    """Map cache environment variable names to their in-repo directories."""
    base = get_cache_root()
    return {
        "UV_CACHE_DIR": base / "uv",
        "UV_PYTHON_INSTALL_DIR": base / "uv_python",
        "HF_HOME": base / "hf",
        "HF_HUB_CACHE": base / "hf" / "hub",
        "TRANSFORMERS_CACHE": base / "hf" / "hub",
        "TORCH_HOME": base / "torch",
        "TORCH_EXTENSIONS_DIR": base / "torch_extensions",
        "TORCHINDUCTOR_CACHE_DIR": base / "torchinductor",
        "TRITON_CACHE_DIR": base / "triton",
        "XDG_CACHE_HOME": base / "xdg",
    }


def apply_isolation() -> None:
    """Force-set all cache environment variables to point inside restory/runtime/cache/."""
    paths = cache_paths()
    for var, path in paths.items():
        os.environ[var] = str(path)
        path.mkdir(parents=True, exist_ok=True)

    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["UV_PROJECT_ENVIRONMENT"] = str(get_install_root() / ".venv")


def tool_subprocess_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Build an environment for running an isolated tool, stripping main-venv target variables."""
    env = dict(base_env if base_env is not None else os.environ)
    paths = cache_paths()
    for var, path in paths.items():
        env[var] = str(path)

    for var in TARGET_ENV_VARS:
        env.pop(var, None)

    vendor_bin = get_install_root() / "runtime" / "tools" / "_vendor"
    extra_paths = [
        str(vendor_bin / "uv" / "bin"),
        str(vendor_bin / "ffmpeg" / "bin"),
        str(vendor_bin / "git-lfs" / "bin"),
    ]
    current_path = env.get("PATH", "")
    env["PATH"] = os.pathsep.join([p for p in extra_paths if Path(p).is_dir()] + [current_path])
    return env


def check_isolation() -> dict[str, str | bool]:
    """Audit whether any cache variable escapes the restory root."""
    root = get_install_root()
    escaping = {}
    for var, path in cache_paths().items():
        current = os.environ.get(var)
        if current:
            curr_path = Path(current).resolve()
            if not curr_path.is_relative_to(root):
                escaping[var] = current

    return {
        "isolated": len(escaping) == 0,
        "install_root": str(root),
        "cache_root": str(get_cache_root()),
        "escaping": escaping,
    }