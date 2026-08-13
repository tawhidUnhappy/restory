#!/usr/bin/env bash
# ==============================================================================
# restory — Modern Interactive CLI Pipeline Runner & Project Selector
# Streamlined 3-Option Panel Cropping Engine (Japanese, MAGI v3, Webtoon)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RUN_SH="./run.sh"
if [ ! -f "$RUN_SH" ]; then
    echo -e "\033[0;31merror:\033[0m ./run.sh launcher not found in $SCRIPT_DIR" >&2
    exit 1
fi

# Modern Slate Color Palette (uv / cargo style)
BOLD='\033[1m'
DIM='\033[2m'
WHITE='\033[1;37m'
SLATE='\033[38;5;245m'
DARK_GRAY='\033[38;5;239m'
GREEN='\033[38;5;78m'
CYAN='\033[38;5;111m'
YELLOW='\033[38;5;221m'
RED='\033[38;5;203m'
NC='\033[0m' # No Color

# Helper to read format and official title from data/library/<manga>/manga.json
get_manga_info() {
    local p_name="$1"
    local ledger="data/library/$p_name/manga.json"
    if [ -f "$ledger" ]; then
        python3 -c "
import json
try:
    d = json.load(open('$ledger'))
    fmt = str(d.get('format', 'paged')).lower()
    title = str(d.get('official_title', '$p_name'))
    print(f'{fmt}|{title}')
except Exception:
    print('paged|$p_name')
" 2>/devnull || echo "paged|$p_name"
    else
        echo "paged|$p_name"
    fi
}

get_manga_format() {
    local info
    info=$(get_manga_info "$1")
    echo "$info" | cut -d'|' -f1
}

get_manga_title() {
    local info
    info=$(get_manga_info "$1")
    echo "$info" | cut -d'|' -f2
}

# Scan data/library/ for existing manga project folders
select_or_create_project() {
    local library_dir="data/library"
    local projects=()

    if [ -d "$library_dir" ]; then
        for dir in "$library_dir"/*/; do
            if [ -d "$dir" ]; then
                local bname
                bname=$(basename "$dir")
                if [[ "$bname" != "."* && "$bname" != "_"* ]]; then
                    projects+=("$bname")
                fi
            fi
        done
    fi

    echo -e "${BOLD}restory${NC} ${DIM}v0.3.0${NC} ${DARK_GRAY}›${NC} ${SLATE}Manga & Webtoon Recap Video Production Toolkit${NC}"
    echo -e "${DARK_GRAY}──────────────────────────────────────────────────────────────────────────────${NC}"

    if [ ${#projects[@]} -gt 0 ]; then
        echo -e "${WHITE}${BOLD}Select a project from library:${NC}"
        local idx=1
        for proj in "${projects[@]}"; do
            local fmt
            local title
            fmt=$(get_manga_format "$proj")
            title=$(get_manga_title "$proj")

            local disp_title="$title"
            if [ ${#disp_title} -gt 42 ]; then
                disp_title="${disp_title:0:39}..."
            fi

            printf "  ${DIM}%2d)${NC} ${BOLD}%-22s${NC} ${CYAN}%-7s${NC} ${DIM}%s${NC}\n" \
                "$idx" "$proj" "[$fmt]" "$disp_title"
            ((idx++))
        done
        echo ""
        read -p "$(echo -e "${CYAN}?${NC} ${BOLD}Select project number [1-${#projects[@]}] or enter new project name (1): ${NC}")" choice

        if [ -z "$choice" ]; then
            MANGA_NAME="${projects[0]}"
        elif [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#projects[@]}" ]; then
            MANGA_NAME="${projects[$((choice-1))]}"
        else
            MANGA_NAME="$choice"
        fi
    else
        echo -e "${DIM}No existing projects found in data/library/.${NC}"
        read -p "$(echo -e "${CYAN}?${NC} ${BOLD}Enter new manga project name (my_manga): ${NC}")" choice
        if [ -n "$choice" ]; then
            MANGA_NAME="$choice"
        else
            MANGA_NAME="my_manga"
        fi
    fi

    echo -e "${GREEN}✔${NC} Active project set to ${BOLD}'$MANGA_NAME'${NC}"
}

# Initial Project Selection
select_or_create_project

# Master Loop
while true; do
    FMT=$(get_manga_format "$MANGA_NAME")
    OFFICIAL_TITLE=$(get_manga_title "$MANGA_NAME")

    disp_title="$OFFICIAL_TITLE"
    if [ ${#disp_title} -gt 50 ]; then
        disp_title="${disp_title:0:47}..."
    fi

    echo ""
    echo -e "${BOLD}Project Details:${NC}"
    echo -e "  ${DIM}Name   :${NC} ${WHITE}${BOLD}$MANGA_NAME${NC}"
    echo -e "  ${DIM}Format :${NC} ${CYAN}$FMT${NC} ${DIM}($disp_title)${NC}"
    echo -e "  ${DIM}Path   :${NC} ${DIM}data/library/$MANGA_NAME${NC}"
    echo -e "${DARK_GRAY}──────────────────────────────────────────────────────────────────────────────${NC}"

    echo -e "${WHITE}${BOLD}1. Acquisition & Setup${NC}"
    echo -e "   ${DIM}1)${NC} Run Doctor & Hardware Audit"
    echo -e "   ${DIM}2)${NC} Download Chapters from MangaDex"
    echo -e "   ${DIM}3)${NC} Detect Manga Format (${DIM}Paged vs Webtoon${NC})"
    echo ""
    echo -e "${WHITE}${BOLD}2. Panel Segmentation & Editing${NC}"
    echo -e "   ${DIM}4)${NC} Auto Panel Crop (${GREEN}3 Engines: Japanese / MAGI v3 / Webtoon${NC})"
    echo -e "   ${DIM}5)${NC} Open Interactive Crop & Layer Editor (${YELLOW}WebUI${NC})"
    echo -e "   ${DIM}6)${NC} Render Panel Reading Sheets & Pack ZIPs"
    echo ""
    echo -e "${WHITE}${BOLD}3. Scriptwriting & Voice Synthesis${NC}"
    echo -e "   ${DIM}7)${NC} Open Side-by-Side Script Editor (${YELLOW}WebUI${NC})"
    echo -e "   ${DIM}8)${NC} Validate Narration Contract Rules"
    echo -e "   ${DIM}9)${NC} Synthesize Voiceover Audio (${DIM}8ms Edge Fading${NC})"
    echo ""
    echo -e "${WHITE}${BOLD}4. Rendering & Publishing${NC}"
    echo -e "  ${DIM}10)${NC} Render Video Items & Build Full Recap MP4"
    echo -e "  ${DIM}11)${NC} Generate Subtitles (${DIM}Whisper ASR${NC}) & Quality Gate"
    echo ""
    echo -e "${WHITE}${BOLD}5. Environment & Management${NC}"
    echo -e "  ${DIM}12)${NC} Install All AI Tool Environments"
    echo -e "  ${DIM}13)${NC} Bootstrap Environment Only"
    echo -e "  ${DIM}14)${NC} Switch Active Manga Project"
    echo -e "   ${DIM}0)${NC} Exit Pipeline"
    echo -e "${DARK_GRAY}──────────────────────────────────────────────────────────────────────────────${NC}"
    read -p "$(echo -e "${CYAN}?${NC} ${BOLD}Select action [0-14]: ${NC}")" opt

    case "$opt" in
        1)
            echo -e "\n${SLATE}› Running system doctor and GPU audit...${NC}"
            $RUN_SH doctor
            ;;
        2)
            echo -e "\n${SLATE}› Downloading chapters from MangaDex...${NC}"
            read -p "$(echo -e "${CYAN}?${NC} MangaDex URL or UUID: ")" url
            read -p "$(echo -e "${CYAN}?${NC} Chapter Range (e.g. 1-5 or 'all') [all]: ")" ch_range
            [ -z "$ch_range" ] && ch_range="all"
            $RUN_SH download "$url" "$ch_range" --name "$MANGA_NAME"
            ;;
        3)
            echo -e "\n${SLATE}› Detecting page aspect ratios...${NC}"
            $RUN_SH style-detect --project-root "data/library/$MANGA_NAME"
            ;;
        4)
            FMT=$(get_manga_format "$MANGA_NAME")
            echo -e "\n${SLATE}› Select Panel Cropping Engine for ${BOLD}$MANGA_NAME${NC}:"
            echo -e "  1) ${GREEN}Japanese Paged Manga (Python CV Gutter Logic)${NC} ${DIM}[Default]${NC}"
            echo -e "  2) ${CYAN}MAGI v3 (Vision Transformer AI Output)${NC}"
            echo -e "  3) ${YELLOW}Webtoon Strip Cut${NC}"
            read -p "$(echo -e "${CYAN}?${NC} Choice [1-3] (1): ")" eng_choice

            case "$eng_choice" in
                2) ENG="magi" ;;
                3) ENG="webtoon" ;;
                *) ENG="japanese" ;;
            esac

            read -p "$(echo -e "${CYAN}?${NC} Chapter Items (e.g. 1-5 or empty for all): ")" items_arg
            if [ "$ENG" = "webtoon" ]; then
                if [ -n "$items_arg" ]; then
                    $RUN_SH webtoon-split --project-root "data/library/$MANGA_NAME" --items $items_arg
                else
                    $RUN_SH webtoon-split --project-root "data/library/$MANGA_NAME"
                fi
            else
                if [ -n "$items_arg" ]; then
                    $RUN_SH page-split --project-root "data/library/$MANGA_NAME" --engine "$ENG" --items $items_arg --render
                else
                    $RUN_SH page-split --project-root "data/library/$MANGA_NAME" --engine "$ENG" --render
                fi
            fi
            ;;
        5)
            FMT=$(get_manga_format "$MANGA_NAME")
            read -p "$(echo -e "${CYAN}?${NC} Chapter Number [01]: ")" ch_num
            [ -z "$ch_num" ] && ch_num="01"
            if [ "$FMT" = "webtoon" ]; then
                $RUN_SH webtoon-editor --project-root "data/library/$MANGA_NAME" --item "$ch_num"
            else
                $RUN_SH crop-editor --project-root "data/library/$MANGA_NAME" --item "$ch_num"
            fi
            ;;
        6)
            echo -e "\n${SLATE}› Rendering panel reading sheets and packing ZIP archives...${NC}"
            $RUN_SH panel-reading-sheets --project-root "data/library/$MANGA_NAME"
            $RUN_SH sheets-pack --project-root "data/library/$MANGA_NAME"
            ;;
        7)
            read -p "$(echo -e "${CYAN}?${NC} Chapter Number [01]: ")" ch_num
            [ -z "$ch_num" ] && ch_num="01"
            $RUN_SH narration-editor --project-root "data/library/$MANGA_NAME" --item "$ch_num"
            ;;
        8)
            echo -e "\n${SLATE}› Validating narration script rules...${NC}"
            $RUN_SH narration-check --project-root "data/library/$MANGA_NAME"
            ;;
        9)
            echo -e "\n${SLATE}› Synthesizing voiceover audio takes...${NC}"
            $RUN_SH video-audio --project-root "data/library/$MANGA_NAME" --tts auto
            ;;
        10)
            echo -e "\n${SLATE}› Rendering video items and building full recap MP4...${NC}"
            $RUN_SH video --project-root "data/library/$MANGA_NAME" --build-long-video --normalize-audio
            ;;
        11)
            echo -e "\n${SLATE}› Generating Whisper subtitles and quality checks...${NC}"
            $RUN_SH video-subtitles --project-root "data/library/$MANGA_NAME"
            $RUN_SH video-quality --project-root "data/library/$MANGA_NAME"
            ;;
        12)
            echo -e "\n${SLATE}› Provisioning all AI tool virtual environments...${NC}"
            $RUN_SH install-all-tools
            ;;
        13)
            echo -e "\n${SLATE}› Bootstrapping core binaries...${NC}"
            ./bootstrap.sh
            ;;
        14)
            echo ""
            select_or_create_project
            ;;
        0)
            echo -e "\n${GREEN}✔${NC} Exiting restory pipeline."
            exit 0
            ;;
        *)
            echo -e "${RED}error:${NC} Invalid option '$opt'. Enter a number from 0 to 14."
            ;;
    esac
done