#!/usr/bin/env bash
# ==============================================================================
# restory Portable Zero-Prerequisite Bootstrapper
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo " Bootstrapping restory Isolated Runtime Environment..."
echo "============================================================"

# Environment Isolation Directories
RUNTIME_DIR="$SCRIPT_DIR/runtime"
CACHE_DIR="$RUNTIME_DIR/cache"
TOOLS_DIR="$RUNTIME_DIR/tools"
VENDOR_DIR="$TOOLS_DIR/_vendor"

mkdir -p "$CACHE_DIR/uv" "$CACHE_DIR/uv_python" "$CACHE_DIR/hf" "$CACHE_DIR/torch" "$CACHE_DIR/xdg"
mkdir -p "$VENDOR_DIR/uv/bin" "$VENDOR_DIR/ffmpeg/bin" "$VENDOR_DIR/git-lfs/bin"

export UV_CACHE_DIR="$CACHE_DIR/uv"
export UV_PYTHON_INSTALL_DIR="$CACHE_DIR/uv_python"
export XDG_CACHE_HOME="$CACHE_DIR/xdg"

# Detect Operating System & Architecture
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

case "$ARCH" in
  x86_64|amd64) ARCH_UV="x86_64" ;;
  aarch64|arm64) ARCH_UV="aarch64" ;;
  *) echo "[ERROR] Unsupported architecture: $ARCH"; exit 1 ;;
esac

# 1. Fetch Portable UV Binary
UV_BIN="$VENDOR_DIR/uv/bin/uv"
if [ ! -f "$UV_BIN" ]; then
  echo "--> Installing portable uv binary..."
  if [ "$OS" = "darwin" ]; then
    UV_URL="https://github.com/astral-sh/uv/releases/latest/download/uv-${ARCH_UV}-apple-darwin.tar.gz"
  elif [ "$OS" = "linux" ]; then
    UV_URL="https://github.com/astral-sh/uv/releases/latest/download/uv-${ARCH_UV}-unknown-linux-gnu.tar.gz"
  else
    echo "[ERROR] Unsupported OS for bootstrap: $OS"; exit 1
  fi

  curl -sSL "$UV_URL" | tar -xz -C "$VENDOR_DIR/uv/bin" --strip-components=1
  chmod +x "$UV_BIN"
fi

# 2. Synchronize Isolated Python 3.12 Virtual Environment
echo "--> Provisioning isolated Python 3.12 environment in .venv/..."
"$UV_BIN" sync --python 3.12

# 3. Fetch Portable FFmpeg / FFprobe if missing
FFMPEG_BIN="$VENDOR_DIR/ffmpeg/bin/ffmpeg"
if [ ! -f "$FFMPEG_BIN" ]; then
  echo "--> Checking system/portable FFmpeg..."
  if command -v ffmpeg &>/dev/null; then
    echo "  [OK] System FFmpeg found."
  else
    echo "--> Downloading portable FFmpeg static binaries..."
    if [ "$OS" = "linux" ] && [ "$ARCH_UV" = "x86_64" ]; then
      curl -sSL "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz" | tar -xJ -C "$VENDOR_DIR/ffmpeg/bin" --strip-components=1
      chmod +x "$VENDOR_DIR/ffmpeg/bin/"*
    else
      echo "  [WARN] Please install FFmpeg using your system package manager (e.g., brew install ffmpeg / apt install ffmpeg)."
    fi
  fi
fi

# 4. Fetch Portable Git LFS if missing
GITLFS_BIN="$VENDOR_DIR/git-lfs/bin/git-lfs"
if [ ! -f "$GITLFS_BIN" ]; then
  if command -v git-lfs &>/dev/null; then
    echo "  [OK] System git-lfs found."
  fi
fi

echo "============================================================"
echo " restory Bootstrap Complete!"
echo " Run './run.sh doctor' to verify system readiness."
echo "============================================================"