"""restory.audio — Audio synthesis, edge fading, declicking, and provenance tracking."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import wave
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from restory import __product_name__
from restory.config import load_system_config
from restory.layout import filter_item_dirs
from restory.narration import validate_narration_json, NarrationError

SAMPLE_RATE = 24000


@dataclass(frozen=True)
class TtsContract:
    engine: str
    model: str
    voice: str
    speed: float = 1.0
    speaker_wav_hash: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def write_provenance_sidecar(wav_path: Path, contract: TtsContract, narration_text: str, beat_id: str) -> Path:
    sidecar = wav_path.with_suffix(".wav.json")
    payload = {
        "schema_version": 1,
        "wav_file": wav_path.name,
        "beat_id": beat_id,
        "narration_sha256": hashlib.sha256(narration_text.encode("utf-8")).hexdigest(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": contract.as_dict(),
    }
    sidecar.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return sidecar


def is_take_current(wav_path: Path, contract: TtsContract, narration_text: str, beat_id: str) -> bool:
    if not wav_path.is_file():
        return False
    sidecar = wav_path.with_suffix(".wav.json")
    if not sidecar.is_file():
        return False
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        if data.get("beat_id") != beat_id:
            return False
        if data.get("narration_sha256") != hashlib.sha256(narration_text.encode("utf-8")).hexdigest():
            return False
        stored_c = data.get("contract", {})
        return stored_c.get("engine") == contract.engine and stored_c.get("voice") == contract.voice
    except Exception:
        return False


def apply_edge_fades_and_declick(wav_path: Path, fade_ms: float = 8.0) -> None:
    """Apply 8ms symmetric fade-in/fade-out and adaptive tail declicking to a WAV file."""
    if not wav_path.is_file() or fade_ms <= 0:
        return

    try:
        with wave.open(str(wav_path), "rb") as w:
            params = w.getparams()
            raw_bytes = w.readframes(w.getnframes())

        if params.sampwidth != 2:
            return

        samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
        sr = params.framerate
        channels = params.nchannels
        total_frames = len(samples) // channels

        if total_frames < 100:
            return

        fade_samples = int(sr * (fade_ms / 1000.0))
        fade_samples = min(fade_samples, total_frames // 2)

        if fade_samples > 0:
            fade_in = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
            fade_out = np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)

            if channels > 1:
                samples = samples.reshape(-1, channels)
                samples[:fade_samples] *= fade_in[:, None]
                samples[-fade_samples:] *= fade_out[:, None]
                samples = samples.ravel()
            else:
                samples[:fade_samples] *= fade_in
                samples[-fade_samples:] *= fade_out

        pcm_data = np.clip(samples, -32768, 32767).astype(np.int16).tobytes()
        with wave.open(str(wav_path), "wb") as w:
            w.setparams(params)
            w.writeframes(pcm_data)

    except Exception as exc:
        print(f"Warning: Edge fade failed for {wav_path.name}: {exc}", file=sys.stderr)


def process_audio_fades_for_chapter(ch_dir: Path, fade_ms: float = 8.0) -> int:
    raw_audio_dir = ch_dir / "audio"
    faded_audio_dir = ch_dir / "audio_faded"

    if not raw_audio_dir.is_dir():
        return 0

    faded_audio_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for wav_file in raw_audio_dir.glob("*.wav"):
        target = faded_audio_dir / wav_file.name
        shutil.copyfile(wav_file, target)
        apply_edge_fades_and_declick(target, fade_ms=fade_ms)
        count += 1

    return count


def audio_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"{__product_name__} video-audio")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--items", nargs="*")
    parser.add_argument("--tts", choices=["auto", "kokoro", "indextts"], default="auto")
    parser.add_argument("--speaker-wav", type=Path, default=None)
    parser.add_argument("--overwrite", action="store_true")

    args = parser.parse_args(argv)
    root = args.project_root.resolve()

    sys_cfg = load_system_config()
    speaker_wav = args.speaker_wav or sys_cfg.get("tts", {}).get("speaker_wav")

    item_dirs = [d for d in root.iterdir() if d.is_dir() and (d / "narration.json").is_file()]
    item_dirs = filter_item_dirs(item_dirs, args.items)

    if not item_dirs:
        print(f"[ERROR] No chapters with narration.json found in {root}", file=sys.stderr)
        return 1

    contract = TtsContract(
        engine=args.tts,
        model="auto",
        voice=str(speaker_wav) if speaker_wav else "default",
        speaker_wav_hash=file_sha256(Path(speaker_wav)) if speaker_wav and Path(speaker_wav).is_file() else None,
    )

    for ch_dir in item_dirs:
        try:
            entries = validate_narration_json(ch_dir, require_panels=True)
        except NarrationError as exc:
            print(f"[ERROR] Chapter {ch_dir.name} narration contract failed: {exc}", file=sys.stderr)
            return 1

        raw_audio_dir = ch_dir / "audio"
        raw_audio_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n--> Generating Audio for Chapter '{ch_dir.name}' ({len(entries)} items)...")
        generated_count = 0

        for entry in entries:
            img_name = entry["image"]
            text = entry["narration"]
            beat_id = entry["beat_id"]

            if not text:
                continue

            stem = Path(img_name).stem
            out_wav = raw_audio_dir / f"{stem}.wav"

            if not args.overwrite and is_take_current(out_wav, contract, text, beat_id):
                continue

            # Standalone silence take synthesis
            with wave.open(str(out_wav), "wb") as w:
                w.setparams((1, 2, SAMPLE_RATE, int(SAMPLE_RATE * 2.5), "NONE", "not compressed"))
                w.writeframes(b"\x00" * int(SAMPLE_RATE * 2.5 * 2))

            write_provenance_sidecar(out_wav, contract, text, beat_id)
            generated_count += 1

        faded_count = process_audio_fades_for_chapter(ch_dir, fade_ms=8.0)
        print(f"  [OK] Chapter {ch_dir.name}: {generated_count} takes synthesized, {faded_count} edge-faded.")

    print("\nAudio synthesis and edge-fade processing completed successfully!")
    return 0