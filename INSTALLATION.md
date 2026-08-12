# Installation & Setup Guide for `restory`

This guide explains how to set up `restory` on macOS or Linux using the zero-prerequisite bootstrapper (`./bootstrap.sh`), configure GPU acceleration, and provision isolated AI tool environments.

---

## 1. System Requirements

- **Operating System**: Linux (Ubuntu, Debian, Fedora, Arch, RHEL, CentOS, Alpine) or macOS (Apple Silicon M1/M2/M3/M4 or Intel).
- **Core Dependencies**: Only basic POSIX utilities (`bash`, `curl` or `wget`, `tar`). No system Python or system FFmpeg required!
- **Free Disk Space**:
  - Base Installation: ~2.5 GB.
  - Full AI Toolchain (IndexTTS 2, MAGI v3, DeepSeek-OCR 2, Whisper): ~25–30 GB.
- **GPU Acceleration (Optional)**:
  - **Linux / Windows**: NVIDIA GPU with CUDA 12.1+ drivers installed.
  - **macOS**: Apple Silicon (MPS acceleration is used automatically by PyTorch).

---

## 2. Zero-Prerequisite Setup (`./bootstrap.sh`)

`restory` includes a portable bootstrapper that fetches everything it needs into the repository directory.

### Step-by-Step Installation:

1. **Clone Repo**:
   ```bash
   git clone https://github.com/restory/restory.git
   cd restory
   ```

2. **Make Scripts Executable**:
   ```bash
   chmod +x bootstrap.sh run.sh pipeline.sh
   ```

3. **Run the Bootstrapper**:
   ```bash
   ./bootstrap.sh
   ```

   **What `./bootstrap.sh` does:**
   - Downloads a portable `uv` binary into `./runtime/tools/_vendor/uv/bin/`.
   - Downloads a private, isolated Python 3.12 interpreter into `./runtime/cache/uv_python/`.
   - Synchronizes `restory` core dependencies inside `./.venv/`.
   - Downloads portable `ffmpeg` and `ffprobe` into `./runtime/tools/_vendor/ffmpeg/bin/`.
   - Pins all PyTorch, HuggingFace, and UV caches inside `./runtime/cache/`.

---

## 3. Verifying Installation & GPU (`./run.sh doctor`)

Verify that all core executables and GPU acceleration are detected properly:

```bash
./run.sh doctor
```

Example Output:
```text
============================================================
 restory Doctor Report (v0.3.0)
============================================================
 GPU Backend : CUDA (NVIDIA GeForce RTX 4090)
 Executables :
   - ffmpeg    : OK (/path/to/restory/runtime/tools/_vendor/ffmpeg/bin/ffmpeg)
   - ffprobe   : OK (/path/to/restory/runtime/tools/_vendor/ffmpeg/bin/ffprobe)
   - uv        : OK (/path/to/restory/runtime/tools/_vendor/uv/bin/uv)
   - git-lfs   : OK (/path/to/restory/runtime/tools/_vendor/git-lfs/bin/git-lfs)
 AI Tools    :
   - index-tts   : NOT INSTALLED
   - magi-v3     : NOT INSTALLED
   - deepseek-ocr2: NOT INSTALLED
   - kokoro-82m  : NOT INSTALLED
   - whisper-turbo: NOT INSTALLED
============================================================
```

---

## 4. Provisioning Isolated AI Tools

`restory` uses isolated virtual environments for heavy AI models inside `./runtime/tools/`. Each tool gets its own independent Python environment so dependency versions never conflict.

### Install Individual Tools:

- **MAGI v3 (Paged Manga Panel Detector)**:
  ```bash
  ./run.sh install-tool magi-v3
  ```

- **Whisper large-v3-turbo (Subtitle Generator)**:
  ```bash
  ./run.sh install-tool whisper-turbo
  ```

---

## 5. Environment Isolation & Cache Management

All cache locations are strictly forced into `./runtime/cache/` by `restory/isolation.py`:

- `UV_CACHE_DIR` -> `./runtime/cache/uv/`
- `UV_PYTHON_INSTALL_DIR` -> `./runtime/cache/uv_python/`
- `HF_HOME` -> `./runtime/cache/hf/`
- `TORCH_HOME` -> `./runtime/cache/torch/`
- `TRITON_CACHE_DIR` -> `./runtime/cache/triton/`
- `XDG_CACHE_HOME` -> `./runtime/cache/xdg/`

### How to Clean Up:
Delete `data/` or reset the workspace output directory:
```bash
rm -rf data/library/*
```
*(This deletes `data/library/` production outputs while preserving installed AI tools, portable binaries, and model caches).*