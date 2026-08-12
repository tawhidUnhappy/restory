#!/usr/bin/env bash
# ==============================================================================
# restory Interactive Master Pipeline Runner
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RUN="./run.sh"

echo "============================================================"
echo " restory — Interactive Recap Production Pipeline"
echo "============================================================"

read -rp "Enter Manga Project Name (e.g. my_manga): " MANGA_NAME
if [ -z "$MANGA_NAME" ]; then
  echo "[ERROR] Manga name cannot be empty."
  exit 1
fi

PROJECT_DIR="data/library/$MANGA_NAME"

while true; do
  echo ""
  echo "--- Pipeline Menu for '$MANGA_NAME' ---"
  echo " 1) Run System Doctor & Hardware Check"
  echo " 2) Download Chapters from MangaDex"
  echo " 3) Detect Manga Format (Paged vs Webtoon)"
  echo " 4) Auto Panel Crop (page-split / webtoon-split)"
  echo " 5) Launch Interactive Crop & Layer Editor (WebUI)"
  echo " 6) Render Panel Reading Sheets & Pack ZIPs"
  echo " 7) Launch Side-by-Side Narration Script Editor (WebUI)"
  echo " 8) Validate Narration Contract Rules"
  echo " 9) Synthesize Voiceover Audio with Edge Fading"
  echo "10) Render Video Items & Build Full Recap MP4"
  echo "11) Generate Subtitles (Whisper ASR) & Quality Gate"
  echo " 0) Exit"
  echo "---------------------------------------"
  read -rp "Select option [0-11]: " CHOICE

  case "$CHOICE" in
    1) $RUN doctor ;;
    2)
      read -rp "Enter MangaDex URL or UUID: " M_URL
      read -rp "Enter Chapter Range (e.g. 1-5 or 'all'): " CH_RANGE
      $RUN download "$M_URL" "${CH_RANGE:-all}" --name "$MANGA_NAME"
      ;;
    3) $RUN style-detect --project-root "$PROJECT_DIR" ;;
    4)
      read -rp "Split Mode [paged/webtoon]: " MODE
      read -rp "Enter Chapter Selection (e.g. 01 or leave blank for all): " ITEMS
      if [ "$MODE" = "webtoon" ]; then
        $RUN webtoon-split --project-root "$PROJECT_DIR" ${ITEMS:+"--items" "$ITEMS"}
      else
        $RUN page-split --project-root "$PROJECT_DIR" ${ITEMS:+"--items" "$ITEMS"}
      fi
      ;;
    5)
      read -rp "Editor Mode [paged/webtoon]: " EMODE
      read -rp "Enter Chapter Number (default 01): " ITEM
      if [ "$EMODE" = "webtoon" ]; then
        $RUN webtoon-editor --project-root "$PROJECT_DIR" --item "${ITEM:-01}"
      else
        $RUN crop-editor --project-root "$PROJECT_DIR" --item "${ITEM:-01}"
      fi
      ;;
    6)
      $RUN panel-reading-sheets --project-root "$PROJECT_DIR"
      $RUN sheets-pack --project-root "$PROJECT_DIR"
      ;;
    7)
      read -rp "Enter Chapter Number (default 01): " ITEM
      $RUN narration-editor --project-root "$PROJECT_DIR" --item "${ITEM:-01}"
      ;;
    8) $RUN narration-check --project-root "$PROJECT_DIR" ;;
    9) $RUN video-audio --project-root "$PROJECT_DIR" ;;
    10) $RUN video --project-root "$PROJECT_DIR" --build-long-video --normalize-audio ;;
    11)
      $RUN video-subtitles --project-root "$PROJECT_DIR"
      $RUN video-quality --project-root "$PROJECT_DIR"
      ;;
    0) echo "Exiting pipeline. Goodbye!"; exit 0 ;;
    *) echo "Invalid option." ;;
  esac
done