#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo " restory — Interactive Recap Production Pipeline"
echo "============================================================"

read -p "Enter Manga Project Name (e.g. my_manga): " MANGA_NAME
if [ -z "$MANGA_NAME" ]; then
    MANGA_NAME="my_manga"
fi

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
    echo "12) Full Setup (Install All AI Tools at Once)"
    echo "13) Setup Light (Bootstrap Environment Only)"
    echo " 0) Exit"
    echo "---------------------------------------"
    read -p "Select option [0-13]: " CHOICE

    case "$CHOICE" in
        1)
            ./run.sh doctor
            ;;
        2)
            read -p "Enter MangaDex URL or UUID: " MANGADEX_URL
            read -p "Enter Chapter Range (e.g. 1-5 or 'all'): " CH_RANGE
            if [ -z "$CH_RANGE" ]; then CH_RANGE="all"; fi
            ./run.sh download "$MANGADEX_URL" "$CH_RANGE" --name "$MANGA_NAME"
            ;;
        3)
            ./run.sh style-detect --project-root "data/library/$MANGA_NAME"
            ;;
        4)
            echo ""
            echo "Select Crop Engine / Format Mode:"
            echo " 1) Paged Manga — CV Heuristic (Fast)"
            echo " 2) Paged Manga — MAGI v3 (AI Transformer)"
            echo " 3) Paged Manga — Hybrid (AI + CV Snapping)"
            echo " 4) Webtoon Strip — Vertical Density Cuts"
            read -p "Choice [1-4] (default: 1): " CROP_ENGINE_CHOICE
            read -p "Enter Chapter Range/Items (e.g. 1-5 or leave empty for all): " CH_ITEMS
            
            ITEMS_ARG=""
            if [ -n "$CH_ITEMS" ]; then
                ITEMS_ARG="--items $CH_ITEMS"
            fi

            case "$CROP_ENGINE_CHOICE" in
                2)
                    ./run.sh page-split --project-root "data/library/$MANGA_NAME" --engine magi $ITEMS_ARG
                    ;;
                3)
                    ./run.sh page-split --project-root "data/library/$MANGA_NAME" --engine hybrid $ITEMS_ARG
                    ;;
                4)
                    ./run.sh webtoon-split --project-root "data/library/$MANGA_NAME" $ITEMS_ARG
                    ;;
                *)
                    ./run.sh page-split --project-root "data/library/$MANGA_NAME" --engine heuristic $ITEMS_ARG
                    ;;
            esac
            ;;
        5)
            echo ""
            echo "Select Crop Editor Mode:"
            echo " 1) Paged Manga Crop Editor (WebUI)"
            echo " 2) Webtoon Strip Editor (WebUI)"
            read -p "Choice [1-2] (default: 1): " EDITOR_MODE_CHOICE
            read -p "Enter Chapter Number (default 01): " CH_NUM
            if [ -z "$CH_NUM" ]; then CH_NUM="01"; fi

            case "$EDITOR_MODE_CHOICE" in
                2)
                    ./run.sh webtoon-editor --project-root "data/library/$MANGA_NAME" --item "$CH_NUM"
                    ;;
                *)
                    ./run.sh crop-editor --project-root "data/library/$MANGA_NAME" --item "$CH_NUM"
                    ;;
            esac
            ;;
        6)
            read -p "Enter Chapter Range/Items (e.g. 1-5 or leave empty for all): " CH_ITEMS
            ITEMS_ARG=""
            if [ -n "$CH_ITEMS" ]; then ITEMS_ARG="--items $CH_ITEMS"; fi
            ./run.sh panel-reading-sheets --project-root "data/library/$MANGA_NAME" $ITEMS_ARG
            ./run.sh sheets-pack --project-root "data/library/$MANGA_NAME"
            ;;
        7)
            read -p "Enter Chapter Number (default 01): " CH_NUM
            if [ -z "$CH_NUM" ]; then CH_NUM="01"; fi
            ./run.sh narration-editor --project-root "data/library/$MANGA_NAME" --item "$CH_NUM"
            ;;
        8)
            read -p "Enter Chapter Range/Items (leave empty for all): " CH_ITEMS
            ITEMS_ARG=""
            if [ -n "$CH_ITEMS" ]; then ITEMS_ARG="--items $CH_ITEMS"; fi
            ./run.sh narration-check --project-root "data/library/$MANGA_NAME" $ITEMS_ARG
            ;;
        9)
            read -p "Enter Chapter Range/Items (leave empty for all): " CH_ITEMS
            ITEMS_ARG=""
            if [ -n "$CH_ITEMS" ]; then ITEMS_ARG="--items $CH_ITEMS"; fi
            ./run.sh video-audio --project-root "data/library/$MANGA_NAME" $ITEMS_ARG --tts auto
            ;;
        10)
            read -p "Enter Chapter Range/Items (leave empty for all): " CH_ITEMS
            ITEMS_ARG=""
            if [ -n "$CH_ITEMS" ]; then ITEMS_ARG="--items $CH_ITEMS"; fi
            ./run.sh video --project-root "data/library/$MANGA_NAME" $ITEMS_ARG --build-long-video --normalize-audio
            ;;
        11)
            ./run.sh video-subtitles --project-root "data/library/$MANGA_NAME"
            ./run.sh video-quality --project-root "data/library/$MANGA_NAME"
            ;;
        12)
            echo "--> Running Full Setup & Installing All AI Tools..."
            ./bootstrap.sh
            ./run.sh install-all-tools
            ;;
        13)
            echo "--> Running Setup Light (Core Environment Only)..."
            ./bootstrap.sh
            ;;
        0)
            echo "Exiting pipeline. Goodbye!"
            exit 0
            ;;
        *)
            echo "[ERROR] Invalid option. Please enter a number between 0 and 13."
            ;;
    esac
done