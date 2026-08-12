"""restory.detectors.magi — ViT MAGI v3 AI manga panel detector wrapper."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from PIL import Image

from restory.isolation import get_install_root, tool_subprocess_env
from restory.layout import tool_dir
from restory.detectors.heuristic import detect_heuristic


def detect_magi(img_path: Path) -> list[dict]:
    """Detect panel boxes using MAGI v3 AI tool environment (falls back to heuristic if uninstalled)."""
    t_dir = tool_dir("magi-v3")
    ready_file = t_dir / "READY.json"

    if not ready_file.is_file():
        print("[WARN] MAGI v3 AI tool environment not provisioned. Falling back to classic CV detector.", file=sys.stderr)
        with Image.open(img_path) as im:
            return detect_heuristic(im)

    worker_script = t_dir / "_magi_predict.py"
    if not worker_script.is_file():
        code = """import sys, json
from pathlib import Path
from PIL import Image
import torch

img_path = Path(sys.argv[1])
out_json = Path(sys.argv[2])

try:
    from transformers import AutoModel
    model = AutoModel.from_pretrained("ragavsachdeva/magi", trust_remote_code=True)
    if torch.cuda.is_available():
        model = model.cuda()
    model.eval()

    with Image.open(img_path) as img:
        results = model.predict_panels([img])
        boxes = []
        if results and len(results) > 0:
            raw_boxes = results[0]
            for idx, b in enumerate(raw_boxes):
                boxes.append({
                    "x1": int(b[0]), "y1": int(b[1]), "x2": int(b[2]), "y2": int(b[3]),
                    "z_index": idx, "type": "rectangle", "locked": False, "visible": True, "label": "ai_magi"
                })
    out_json.write_text(json.dumps(boxes), encoding="utf-8")
except Exception as exc:
    sys.exit(1)
"""
        worker_script.write_text(code, encoding="utf-8")

    venv_py = t_dir / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / ("python.exe" if sys.platform == "win32" else "python")
    python_bin = str(venv_py) if venv_py.is_file() else sys.executable

    tmp_out = img_path.parent / f"_magi_out_{img_path.stem}.json"
    cmd = [python_bin, str(worker_script), str(img_path), str(tmp_out)]
    env = tool_subprocess_env()

    try:
        res = subprocess.run(cmd, cwd=str(t_dir), env=env, capture_output=True, text=True, timeout=30)
        if res.returncode == 0 and tmp_out.is_file():
            boxes = json.loads(tmp_out.read_text(encoding="utf-8"))
            tmp_out.unlink(missing_ok=True)
            return boxes
    except Exception as exc:
        print(f"[WARN] MAGI v3 prediction failed ({exc}). Falling back to classic CV detector.", file=sys.stderr)

    tmp_out.unlink(missing_ok=True)
    with Image.open(img_path) as im:
        return detect_heuristic(im)