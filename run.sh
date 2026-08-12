#!/usr/bin/env bash
# ==============================================================================
# restory Environment Isolation Wrapper Launcher
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export RESTORY_INSTALL_ROOT="$SCRIPT_DIR"

VENDOR_BIN="$SCRIPT_DIR/runtime/tools/_vendor"
export PATH="$VENDOR_BIN/uv/bin:$VENDOR_BIN/ffmpeg/bin:$VENDOR_BIN/git-lfs/bin:$PATH"

PYTHON_EXEC="$SCRIPT_DIR/.venv/bin/python"
if [ ! -f "$PYTHON_EXEC" ]; then
  PYTHON_EXEC="$SCRIPT_DIR/.venv/Scripts/python.exe"
fi

if [ ! -f "$PYTHON_EXEC" ]; then
  echo "[ERROR] Virtual environment not found. Please run ./bootstrap.sh first." >&2
  exit 1
fi

exec "$PYTHON_EXEC" -m restory.cli "$@"