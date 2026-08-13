#!/usr/bin/env bash
# ==============================================================================
# restory — Master Interactive CLI Pipeline Runner
# Format-Aware Auto Routing & CUDA GPU Accelerated Pipeline
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure execution wrapper exists
RUN_SH="./run.sh"
if [ ! -f "$RUN_SH" ]; then
    echo "[ERROR] ./run.sh launcher not found in $SCRIPT_DIR" >&2
    exit 1
fi

MANGA_NAME="my_manga"

# Helper to read format from data/library/<manga>/manga.json
get_manga_format() {
    local ledger="data/library/$1/manga.json"
    if [ -f "$ledger" ]; then
        python3 -c "import json; data=json.load(open('$ledger')); print(data.get('format', 'paged'))" 2>/dev/null || echo "paged"
    else
        echo "paged"
    fi
}

echo "============================================================"
echo " restory — Interactive Recap Production Pipeline"
echo "============================================================"
read -p "Enter Manga Project Name (default: $MANGA_NAME): " input_name
if [ -n "$input_name" ]; then
    MANGA_NAME="$input_name"
fi
echo "--> Active Project set to: '$MANGA_NAME'"

while true; do
    FMT=$(get_manga_format "$MANGA_NAME")
    echo ""
    echo "--- Pipeline Menu for '$MANGA_NAME' (Detected Format: ${FMT^^}) ---"
    echo " 1) Run System Doctor & Hardware Check"
    echo " 2) Download Chapters from MangaDex"
    echo " 3) Detect Manga Format (Paged vs Webtoon)"
    echo " 4) Auto Panel Crop (Format-Aware Batch GPU)"
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
    read -p "Select option [0-14]: " opt

    case "$opt" in
        1)
            $RUN_SH doctor
            ;;
        2)
            read -p "Enter MangaDex URL or UUID: " url
            read -p "Enter Chapter Range (e.g. 1-5 or 'all'): " ch_range
            [ -z "$ch_range" ] && ch_range="all"
            $RUN_SH download "$url" "$ch_range" --name "$MANGA_NAME"
            ;;
        3)
            $RUN_SH style-detect --project-root "data/library/$MANGA_NAME"
            ;;
        4)
            FMT=$(get_manga_format "$MANGA_NAME")
            echo "Format recorded in manga.json is: ${FMT^^}"
            if [ "$FMT" = "webtoon" ]; then
                echo "--> Running Webtoon Strip Split..."
                $RUN_SH webtoon-split --project-root "data/library/$MANGA_NAME"
            else
                echo ""
                echo "Select Paged Crop Engine:"
                echo " 1) Hybrid (AI + CV Snapping) [Recommended]"
                echo " 2) MAGI v3 (AI Transformer)"
                echo " 3) CV Heuristic (Fast)"
                read -p "Choice [1-3] (default: 1): " eng_choice
                case "$eng_choice" in
                    2) ENG="magi" ;;
                    3) ENG="heuristic" ;;
                    *) ENG="hybrid" ;;
                esac
                read -p "Enter Chapter Range/Items (e.g. 1-5 or empty for all): " items_arg
                if [ -n "$items_arg" ]; then
                    $RUN_SH page-split --project-root "data/library/$MANGA_NAME" --engine "$ENG" --items $items_arg --render
                else
                    $RUN_SH page-split --project-root "data/library/$MANGA_NAME" --engine "$ENG" --render
                fi
            fi
            ;;
        5)
            FMT=$(get_manga_format "$MANGA_NAME")
            read -p "Enter Chapter Number (default 01): " ch_num
            [ -z "$ch_num" ] && ch_num="01"
            if [ "$FMT" = "webtoon" ]; then
                $RUN_SH webtoon-editor --project-root "data/library/$MANGA_NAME" --item "$ch_num"
            else
                $RUN_SH crop-editor --project-root "data/library/$MANGA_NAME" --item "$ch_num"
            fi
            ;;
        6)
            $RUN_SH panel-reading-sheets --project-root "data/library/$MANGA_NAME"
            $RUN_SH sheets-pack --project-root "data/library/$MANGA_NAME"
            ;;
        7)
            read -p "Enter Chapter Number (default 01): " ch_num
            [ -z "$ch_num" ] && ch_num="01"
            $RUN_SH narration-editor --project-root "data/library/$MANGA_NAME" --item "$ch_num"
            ;;
        8)
            $RUN_SH narration-check --project-root "data/library/$MANGA_NAME"
            ;;
        9)
            $RUN_SH video-audio --project-root "data/library/$MANGA_NAME" --tts auto
            ;;
        10)
            $RUN_SH video --project-root "data/library/$MANGA_NAME" --build-long-video --normalize-audio
            ;;
        11)
            $RUN_SH video-subtitles --project-root "data/library/$MANGA_NAME"
            $RUN_SH video-quality --project-root "data/library/$MANGA_NAME"
            ;;
        12)
            $RUN_SH install-all-tools
            ;;
        13)
            ./bootstrap.sh
            ;;
        14)
            read -p "Enter New Manga Project Name: " input_name
            if [ -n "$input_name" ]; then
                MANGA_NAME="$input_name"
                echo "--> Switched active project to '$MANGA_NAME'"
            fi
            ;;
        0)
            echo "Exiting pipeline. Goodbye!"
            exit 0
            ;;
        *)
            echo "Invalid option. Please enter a number between 0 and 14."
            ;;
    esac
done