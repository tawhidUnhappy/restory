"""restory.detectors.magi — ViT MAGI v3 AI manga panel detector wrapper (Batch CUDA GPU accelerated)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from PIL import Image

from restory.isolation import get_install_root, tool_subprocess_env
from restory.layout import tool_dir
from restory.detectors.heuristic import detect_heuristic


def detect_magi_batch(img_paths: list[Path]) -> dict[Path, list[dict]]:
    """Detect panel boxes for a list of chapter page images in a single GPU pass."""
    if not img_paths:
        return {}

    t_dir = tool_dir("magi-v3")
    ready_file = t_dir / "READY.json"

    # Fallback to heuristic if tool is uninstalled
    if not ready_file.is_file():
        print("[WARN] MAGI v3 AI tool environment not provisioned. Falling back to classic CV detector.", file=sys.stderr)
        out = {}
        for p in img_paths:
            with Image.open(p) as im:
                out[p] = detect_heuristic(im)
        return out

    worker_script = t_dir / "_magi_predict_batch.py"
    code = """import sys, json
from pathlib import Path
from PIL import Image
import torch

input_json = Path(sys.argv[1])
out_json = Path(sys.argv[2])

try:
    paths = [Path(p) for p in json.loads(input_json.read_text(encoding="utf-8"))]
    from transformers import AutoModel
    model = AutoModel.from_pretrained("ragavsachdeva/magi", trust_remote_code=True)
    if torch.cuda.is_available():
        model = model.cuda()
    model.eval()

    results_map = {}
    for p in paths:
        if not p.is_file():
            continue
        with Image.open(p) as img:
            res = model.predict_panels([img])
            boxes = []
            if res and len(res) > 0:
                raw_boxes = res[0]
                for idx, b in enumerate(raw_boxes):
                    boxes.append({
                        "x1": int(b[0]), "y1": int(b[1]), "x2": int(b[2]), "y2": int(b[3]),
                        "z_index": idx, "type": "rectangle", "locked": False, "visible": True, "label": "ai_magi"
                    })
            results_map[str(p.resolve())] = boxes

    out_json.write_text(json.dumps(results_map), encoding="utf-8")
except Exception as exc:
    print(f"MAGI Error: {exc}", file=sys.stderr)
    sys.exit(1)
"""
    worker_script.write_text(code, encoding="utf-8")

    venv_py = t_dir / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / ("python.exe" if sys.platform == "win32" else "python")
    python_bin = str(venv_py) if venv_py.is_file() else sys.executable

    batch_dir = img_paths[0].parent
    in_file = batch_dir / "_magi_batch_in.json"
    out_file = batch_dir / "_magi_batch_out.json"

    in_file.write_text(json.dumps([str(p.resolve()) for p in img_paths]), encoding="utf-8")

    cmd = [python_bin, str(worker_script), str(in_file), str(out_file)]
    env = tool_subprocess_env()

    try:
        res = subprocess.run(cmd, cwd=str(t_dir), env=env, capture_output=True, text=True, timeout=180)
        if res.returncode == 0 and out_file.is_file():
            raw_res = json.loads(out_file.read_text(encoding="utf-8"))
            in_file.unlink(missing_ok=True)
            out_file.unlink(missing_ok=True)

            out = {}
            for p in img_paths:
                key = str(p.resolve())
                out[p] = raw_res.get(key, [])
            return out
    except Exception as exc:
        print(f"[WARN] MAGI v3 batch prediction failed ({exc}). Falling back to CV detector.", file=sys.stderr)

    in_file.unlink(missing_ok=True)
    out_file.unlink(missing_ok=True)

    out = {}
    for p in img_paths:
        with Image.open(p) as im:
            out[p] = detect_heuristic(im)
    return out


def detect_magi(img_path: Path) -> list[dict]:
    """Single image wrapper around detect_magi_batch."""
    res = detect_magi_batch([img_path])
    return res.get(img_path, [])