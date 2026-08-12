# AI Agent Operating Guide for `restory`

This document serves as the primary operating manual for AI assistants (Claude, Gemini, GPT, Roo Code, Cursor) interacting with and running `restory`.

---

## 1. Agent Entry Point & Orientation

Before executing any project actions, always orient yourself and verify the active environment paths:

```bash
./run.sh doctor --json
```

- **Execution Wrapper**: Always run CLI commands through `./run.sh` (or `python -m restory.cli`) to ensure process environment isolation.
- **Workspace Isolation**: Everything `restory` downloads or generates goes under `data/library/<manga_name>/`. Never write production files outside `data/`.

---

## 2. Operating Principles & Invariants

1. **Deterministic Code vs. LLM Judgment**:
   - Let code handle deterministic chores (fetching feed, verifying page counts, cropping, audio fading, normalization).
   - Reserve LLM attention for story understanding, narration writing, and quality inspection.

2. **Page Count Verification (`manga.json`)**:
   - `download` records official MangaDex metadata in `data/library/<manga_name>/manga.json`.
   - Never assume downloads are complete without checking `pages_downloaded == pages_expected`. If pages are missing or corrupted, re-run `download` to fetch missing files.

3. **Strict Panel Coverage & Blank Narration Option**:
   - Every cropped panel in `panels/` MUST have an entry in `narration.json` in reading order.
   - For covers, credits, or decorative end-pages, set `"narration": ""`.
   - All story-carrying panels MUST have non-empty narration text.

4. **1-to-1 Panel Synchronization**:
   - The line for panel `N` MUST describe ONLY panel `N`. Never reveal future events from panel `N+1` or lag behind.
   - Describe emotions in prose ("he laughed", "she gasped"). NEVER write phonetic sound effects (`"hahaha"`, `"ghaha"`, `"aaaargh"`).
   - Unspeakable lines (pure punctuation like `"?!"`) are strictly forbidden.

5. **Story Memory Protocol (`MEMORY.json`)**:
   - Maintain `data/library/<manga_name>/MEMORY.json` across chapters to preserve character names, plot beats, and tone.
   - Keep the `brief` block <= 40 lines.

---

## 3. Recommended Agent Workflow

### Phase 1: Acquisition & Verification
```bash
./run.sh download "https://mangadex.org/title/<UUID>" "01-05" --name "my_manga"
```
Verify page completeness in `data/library/my_manga/manga.json`.

### Phase 2: Format Detection & Cropping (Deferred Metadata Engine)
```bash
./run.sh style-detect --project-root data/library/my_manga
# If paged:
./run.sh page-split --project-root data/library/my_manga --engine hybrid --items 01-05
./run.sh crop-editor --project-root data/library/my_manga --item 01

# If webtoon:
./run.sh webtoon-split --project-root data/library/my_manga --items 01-05
./run.sh webtoon-editor --project-root data/library/my_manga --item 01
```

### Phase 3: Reading Sheets & Scriptwriting
```bash
./run.sh panel-reading-sheets --project-root data/library/my_manga --items 01-05
./run.sh sheets-pack --project-root data/library/my_manga
./run.sh narration-editor --project-root data/library/my_manga --item 01
```

### Phase 4: Script Validation & Audio Synthesis
```bash
./run.sh narration-check --project-root data/library/my_manga --items 01-05
./run.sh video-audio --project-root data/library/my_manga --items 01-05 --tts auto
```

### Phase 5: Subtitles & Video Rendering
```bash
./run.sh video --project-root data/library/my_manga --items 01-05 --build-long-video --normalize-audio
./run.sh video-subtitles --project-root data/library/my_manga
./run.sh video-quality --project-root data/library/my_manga
```