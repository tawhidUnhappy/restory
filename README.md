# restory

> Standalone, fully isolated CLI toolkit and WebUI suite for manga, manhwa, and webtoon recap video production.

[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)

`restory` is a production-oriented, standalone toolkit that allows human operators and AI assistants to acquire manga chapters, detect and crop panel bounding boxes, generate reading sheets, edit narration scripts side-by-side, synthesize voiceover audio with edge fading, render 1080p recap videos, and generate subtitles.

---

## Key Features

- **100% Isolated Installation (`./bootstrap.sh`)**: Downloads portable `uv`, Python 3.12, `ffmpeg`/`ffprobe`, and `git-lfs` into `./runtime/tools/_vendor/`. Pinned caches prevent writing to system folders (`~/.cache` or `/usr/local`).
- **Clean Data/Runtime Split**:
  - `data/`: Deletable production state (`data/library/<manga_name>/`). Deleting `data/` gives a fresh slate without losing installed models or tools.
  - `runtime/`: Surviving machinery (isolated virtual environments, HuggingFace/PyTorch caches, portable binaries).
- **Deferred Metadata Cropping Paradigm**:
  - Auto-detection algorithms generate and save bounding box coordinate metadata (`boxes.json`) without physically cropping files.
  - Users inspect and fine-tune bounding box layers in interactive WebUI tools before executing a single-pass physical crop render.
- **Multi-Engine Detection Suite**:
  - **Classic OpenCV/NumPy**: Fast recursive XY-cut projection profiling and Canny contour detection.
  - **MAGI v3 (AI)**: Vision Transformer (ViT) panel detection for complex, borderless, or overlapping manga frames.
  - **Hybrid AI + CV Snapping**: Uses MAGI v3 candidate proposals refined with OpenCV local whitespace gradient snapping.
  - **Webtoon Density Profiling**: Vertical variance profiling with rescue guard algorithms to protect speech bubbles.
- **Interactive WebUI Editors**:
  - **Paged Crop Editor (`crop-editor`)**: HTML5 Canvas box editor with layer stacking, lock/visibility toggles, full-page preset (`F`), and GPU telemetry.
  - **Webtoon Strip Editor (`webtoon-editor`)**: Virtualized infinite scroll viewer with draggable horizontal cut lines and camera motion keyframing.
  - **Side-by-Side Narration Editor (`narration-editor`)**: Scriptwriting interface with instant draft TTS audio preview and contract validation radar.
- **Audio Engine with Edge Fading**:
  - Automatic 8ms symmetric edge fades and adaptive tail declicking to eliminate audio clicks.
  - Content-hashed `.wav.json` sidecar provenance tracking.
- **Video Engine & Quality Gate**:
  - 1080p MP4 rendering with blurred background framing or Ken Burns camera motion.
  - Two-pass EBU R128 audio normalization (-14 LUFS / -1.5 dBTP) and sidechain music ducking.
  - YouTube chapter timestamps (`video-quality`) and Whisper ASR subtitles (`video-subtitles`).

---

## Directory Structure

```text
restory/
├── bootstrap.sh                  # Portable zero-prerequisite setup
├── run.sh                        # Environment-isolated execution launcher
├── pipeline.sh                   # Master interactive CLI pipeline runner
├── pyproject.toml                # Build & dependency configuration
├── config.system.example.json    # System-wide configuration template
├── data/                         # DELETABLE production output
│   └── library/
│       └── <manga_name>/
│           ├── manga.json        # MangaDex metadata ledger
│           ├── MEMORY.json       # Story memory (brief, cast, beats)
│           └── <ch>/             # Chapter folder (01, 02, etc.)
│               ├── download/     # Source page images
│               ├── panels/       # Cropped panel images
│               ├── review/       # Visual review overlays & reading sheets
│               ├── work/         # boxes.json metadata ledger
│               ├── narration.json# Script entries
│               ├── audio/        # Raw TTS takes
│               └── audio_faded/  # 8ms edge-faded render derivatives
└── restory/                      # Source Code
    ├── detectors/                # Multi-engine cropping detectors
    ├── web/                      # Decoupled WebUI servers, templates, CSS/JS
    └── ...                       # Core pipeline modules
```

---

## Quickstart

### 1. Setup Environment
```bash
chmod +x bootstrap.sh run.sh pipeline.sh
./bootstrap.sh
```

### 2. Verify Readiness
```bash
./run.sh doctor
```

### 3. Run Interactive Pipeline
```bash
./pipeline.sh
```

---

## Command Reference

Run commands using the `./run.sh` launcher to inherit environment isolation:

| Command | Category | Description |
|---|---|---|
| `./run.sh doctor` | System | Check executables, GPU acceleration, and tool readiness. |
| `./run.sh install-tool <name>` | System | Install isolated AI tools (`index-tts`, `magi-v3`, `deepseek-ocr2`, `kokoro-82m`, `whisper-turbo`). |
| `./run.sh download <url> <chapters>` | Acquire | Download chapters from MangaDex with page verification. |
| `./run.sh style-detect --project-root <path>` | Cropping | Detect webtoon vs paged manga format. |
| `./run.sh page-split --project-root <path>` | Cropping | Detect paged manga panel boxes metadata. |
| `./run.sh webtoon-split --project-root <path>` | Cropping | Detect webtoon strip panel cuts metadata. |
| `./run.sh crop-editor --project-root <path>` | WebUI | Launch Paged Manga Crop & Layer Editor. |
| `./run.sh webtoon-editor --project-root <path>` | WebUI | Launch Webtoon Strip & Motion Editor. |
| `./run.sh panel-reading-sheets --project-root <path>` | Sheets | Render multi-panel reading sheets. |
| `./run.sh sheets-pack --project-root <path>` | Packaging | Pack reading sheets into split ZIPs (<= 1 GB each). |
| `./run.sh narration-editor --project-root <path>` | WebUI | Launch Side-by-Side Narration Script Editor. |
| `./run.sh narration-check --project-root <path>` | Scripting | Validate `narration.json` contract rules. |
| `./run.sh video-audio --project-root <path>` | Audio | Synthesize narration audio with edge fading and provenance. |
| `./run.sh video-subtitles --project-root <path>` | Subtitles | Generate `.ass` and `.srt` subtitles using Whisper. |
| `./run.sh video --project-root <path> --build-long-video --normalize-audio` | Video | Render items, join into full recap, and normalize audio. |
| `./run.sh video-quality --project-root <path>` | Quality | Run video stream and quality gate checks. |

---

## License

This project is licensed under the [MIT License](LICENSE).