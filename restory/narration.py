"""restory.narration — Narration contract validation, prompt loader, and script editing."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from restory import __version__, __product_name__
from restory.layout import filter_item_dirs

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_BEAT_ID_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")


class NarrationError(ValueError):
    """Raised when narration.json violates contract rules."""


def is_speakable(text: str) -> bool:
    """Return True if text contains alphanumeric characters that TTS can pronounce."""
    return any(ch.isalnum() for ch in text or "")


def validate_narration_json(ch_dir: Path, require_panels: bool = True) -> list[dict[str, Any]]:
    """Validate narration.json for a chapter folder according to restory contract rules.

    Rules:
    1. Every panel image in panels/ must be listed in narration.json in reading order.
    2. 'narration' can be empty ("") for covers, credits, or decorative panels.
    3. Duplicate images or duplicate audio stems (<stem>.wav) are forbidden.
    4. Text must be speakable if non-empty (no pure punctuation like "?!").
    """
    narration_file = ch_dir / "narration.json"
    if not narration_file.is_file():
        raise NarrationError(f"Missing narration.json in {ch_dir}")

    try:
        entries = json.loads(narration_file.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise NarrationError(f"Invalid JSON in {narration_file}: {exc}") from exc

    if not isinstance(entries, list):
        raise NarrationError(f"{narration_file} must contain a JSON array.")

    panels_dir = ch_dir / "panels"
    actual_panels = {}
    if panels_dir.is_dir():
        for p in panels_dir.iterdir():
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
                actual_panels[p.name] = p

    seen_images: set[str] = set()
    seen_stems: set[str] = set()
    validated: list[dict[str, Any]] = []

    for idx, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise NarrationError(f"Entry #{idx} in {narration_file} is not an object.")

        img_name = str(entry.get("image") or "").strip()
        if not img_name:
            raise NarrationError(f"Entry #{idx} in {narration_file} is missing 'image'.")

        if img_name in seen_images:
            raise NarrationError(f"Duplicate image '{img_name}' in {narration_file}.")
        seen_images.add(img_name)

        stem = Path(img_name).stem.casefold()
        if stem in seen_stems:
            raise NarrationError(f"Image stem collision '{stem}' in {narration_file} (audio is <stem>.wav).")
        seen_stems.add(stem)

        if require_panels and actual_panels and img_name not in actual_panels:
            raise NarrationError(f"Entry #{idx} references panel '{img_name}' which does not exist in {panels_dir}.")

        text = str(entry.get("narration") if entry.get("narration") is not None else "").strip()
        if text and not is_speakable(text):
            raise NarrationError(f"Entry '{img_name}' narration contains no speakable letters/digits: '{text}'")

        beat_id = entry.get("beat_id") or f"{ch_dir.name}-{stem}"
        if not _BEAT_ID_RE.fullmatch(beat_id):
            beat_id = f"{ch_dir.name}-{stem}"

        validated.append({
            "image": img_name,
            "narration": text,
            "beat_id": beat_id,
            "pause_after_ms": int(entry.get("pause_after_ms") or 0),
        })

    if require_panels and actual_panels:
        missing_from_script = set(actual_panels.keys()) - seen_images
        if missing_from_script:
            missing_sorted = sorted(list(missing_from_script))
            raise NarrationError(
                f"Chapter {ch_dir.name} has {len(missing_from_script)} panel(s) omitted from narration.json: "
                f"{', '.join(missing_sorted[:5])}. (For covers/credits, include entry with \"narration\": \"\")."
            )

    return validated


def generate_llm_prompt(manga_name: str, chapter: str) -> str:
    """Load system prompt from external template file and substitute manga details."""
    pkg_root = Path(__file__).resolve().parent
    prompt_file = pkg_root / "assets" / "prompts" / "narration_prompt.md"

    if prompt_file.is_file():
        template = prompt_file.read_text(encoding="utf-8")
        return template.replace("{manga_name}", manga_name).replace("{chapter}", chapter)

    return (
        f"You are an expert YouTube manga recap scriptwriter.\n"
        f"Please generate narration.json and MEMORY.json for '{manga_name}', Chapter {chapter}.\n"
        f"Ensure strict 1-to-1 panel synchronization."
    )


def narration_check_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"{__product_name__} narration-check")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--items", nargs="*")
    args = parser.parse_args(argv)

    root = args.project_root.resolve()
    item_dirs = [d for d in root.iterdir() if d.is_dir() and (d / "narration.json").is_file()]
    item_dirs = filter_item_dirs(item_dirs, args.items)

    if not item_dirs:
        print(f"[ERROR] No chapters with narration.json found in {root}", file=sys.stderr)
        return 1

    errors = []
    for ch_dir in item_dirs:
        try:
            validated = validate_narration_json(ch_dir, require_panels=True)
            non_empty = sum(1 for e in validated if e["narration"])
            print(f"--> [OK] Chapter {ch_dir.name}: {len(validated)} entries ({non_empty} narrated, {len(validated) - non_empty} blank).")
        except NarrationError as exc:
            print(f"--> [FAIL] Chapter {ch_dir.name}: {exc}", file=sys.stderr)
            errors.append(str(exc))

    if errors:
        return 1
    print("\nNarration contract validation passed successfully!")
    return 0


def narration_edit_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"{__product_name__} narration-edit")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--item", required=True)
    parser.add_argument("--set", nargs=2, action="append", metavar=("IMAGE", "TEXT"))
    parser.add_argument("--delete", action="append")
    parser.add_argument("--prune-audio", action="store_true")

    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    ch_dir = root / args.item
    narration_file = ch_dir / "narration.json"

    entries = []
    if narration_file.is_file():
        entries = json.loads(narration_file.read_text(encoding="utf-8-sig"))

    entries_map = {e["image"]: e for e in entries if isinstance(e, dict) and "image" in e}

    stale_stems = []
    if args.set:
        for img_name, text in args.set:
            stem = Path(img_name).stem
            stale_stems.append(stem)
            entries_map[img_name] = {"image": img_name, "narration": text}

    if args.delete:
        for img_name in args.delete:
            stem = Path(img_name).stem
            stale_stems.append(stem)
            entries_map.pop(img_name, None)

    updated_entries = list(entries_map.values())
    narration_file.write_text(json.dumps(updated_entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[OK] Updated {narration_file} ({len(updated_entries)} entries).")

    if args.prune_audio and stale_stems:
        audio_dir = ch_dir / "audio"
        for stem in stale_stems:
            wav = audio_dir / f"{stem}.wav"
            if wav.is_file():
                wav.unlink()
                print(f"  Pruned stale audio: {wav.name}")

    return 0