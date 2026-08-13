#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

mkdir -p data/library
LAST_PROJECT_FILE="data/.last_project"

select_manga_project() {
    local default_name="my_manga"
    if [ -f "$LAST_PROJECT_FILE" ]; then
        local saved_name="$(cat "$LAST_PROJECT_FILE" | tr -d '\r\n')"
        if [ -n "$saved_name" ]; then
            default_name="$saved_name"
        fi
    fi

    # Discover existing manga projects in data/library/
    local projects=()
    while IFS= read -r dir; do
        if [ -n "$dir" ]; then
            projects+=("$dir")
        fi
    done < <(find data/library -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | sort)

    echo ""
    echo "============================================================"
    echo " restory — Interactive Recap Production Pipeline"
    echo "============================================================"

    if [ ${#projects[@]} -gt 0 ]; then
        echo "Discovered Manga Projects in data/library/:"
        local default_idx=1
        local idx=1
        for p in "${projects[@]}"; do
            if [ "$p" = "$default_name" ]; then
                default_idx=$idx
                echo "  $idx) $p (Last Used)"
            else
                echo "  $idx) $p"
            fi
            ((idx++))
        done
        local new_option_idx=$idx
        echo "  $new_option_idx) [Create / Enter New Manga Project Name]"
        echo ""

        read -e -p "Select project [1-$new_option_idx] (default: $default_idx): " PROJ_CHOICE
        if [ -z "$PROJ_CHOICE" ]; then
            PROJ_CHOICE=$default_idx
        fi

        if [ "$PROJ_CHOICE" -ge 1 ] && [ "$PROJ_CHOICE" -lt "$new_option_idx" ] 2>/dev/null; then
            MANGA_NAME="${projects[$((PROJ_CHOICE - 1))]}"
        else
            read -e -p "Enter New Manga Project Name: " MANGA_NAME
            if [ -z "$MANGA_NAME" ]; then
                MANGA_NAME="my_manga"
            fi
        fi
    else
        read -e -p "Enter Manga Project Name (default: $default_name): " MANGA_NAME
        if [ -z "$MANGA_NAME" ]; then
            MANGA_NAME="$default_name"
        fi
    fi

    echo "$MANGA_NAME" > "$LAST_PROJECT_FILE"
    echo "--> Active Project set to: '$MANGA_NAME'"
}

# Initial manga selection on startup
select_manga_project

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
    echo "14) Switch Active Manga Project"
    echo " 0) Exit"
    echo "---------------------------------------"
    read -e -p "Select option [0-14]: " CHOICE

    case "$CHOICE" in
        1)
            ./run.sh doctor
            ;;
        2)
            read -e -p "Enter MangaDex URL or UUID: " MANGADEX_URL
            read -e -p "Enter Chapter Range (e.g. 1-5 or 'all'): " CH_RANGE
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
            read -e -p "Choice [1-4] (default: 1): " CROP_ENGINE_CHOICE
            read -e -p "Enter Chapter Range/Items (e.g. 1-5 or leave empty for all): " CH_ITEMS
            
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
            read -e -p "Choice [1-2] (default: 1): " EDITOR_MODE_CHOICE
            read -e -p "Enter Chapter Number (default 01): " CH_NUM
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
            read -e -p "Enter Chapter Range/Items (e.g. 1-5 or leave empty for all): " CH_ITEMS
            ITEMS_ARG=""
            if [ -n "$CH_ITEMS" ]; then ITEMS_ARG="--items $CH_ITEMS"; fi
            ./run.sh panel-reading-sheets --project-root "data/library/$MANGA_NAME" $ITEMS_ARG
            ./run.sh sheets-pack --project-root "data/library/$MANGA_NAME"
            ;;
        7)
            read -e -p "Enter Chapter Number (default 01): " CH_NUM
            if [ -z "$CH_NUM" ]; then CH_NUM="01"; fi
            ./run.sh narration-editor --project-root "data/library/$MANGA_NAME" --item "$CH_NUM"
            ;;
        8)
            read -e -p "Enter Chapter Range/Items (leave empty for all): " CH_ITEMS
            ITEMS_ARG=""
            if [ -n "$CH_ITEMS" ]; then ITEMS_ARG="--items $CH_ITEMS"; fi
            ./run.sh narration-check --project-root "data/library/$MANGA_NAME" $ITEMS_ARG
            ;;
        9)
            read -e -p "Enter Chapter Range/Items (leave empty for all): " CH_ITEMS
            ITEMS_ARG=""
            if [ -n "$CH_ITEMS" ]; then ITEMS_ARG="--items $CH_ITEMS"; fi
            ./run.sh video-audio --project-root "data/library/$MANGA_NAME" $ITEMS_ARG --tts auto
            ;;
        10)
            read -e -p "Enter Chapter Range/Items (leave empty for all): " CH_ITEMS
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
        14)
            select_manga_project
            ;;
        0)
            echo "Exiting pipeline. Goodbye!"
            exit 0
            ;;
        *)
            echo "[ERROR] Invalid option. Please enter a number between 0 and 14."
            ;;
    esac
done