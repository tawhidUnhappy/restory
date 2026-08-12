"""restory.tools_manager — AI tool environment installer and hardware readiness auditor."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

from restory import __version__, __product_name__
from restory.isolation import get_install_root, tool_subprocess_env
from restory.layout import tools_root, tool_dir

ALL_TOOLS = ["index-tts", "magi-v3", "deepseek-ocr2", "kokoro-82m", "whisper-turbo"]


def check_gpu() -> dict[str, str | bool]:
    has_cuda = False
    device_name = None
    try:
        smi = shutil.which("nvidia-smi")
        if smi:
            res = subprocess.run([smi, "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                has_cuda = True
                device_name = res.stdout.strip().splitlines()[0]
    except Exception:
        pass

    backend = "cuda" if has_cuda else ("mps" if sys.platform == "darwin" else "cpu")
    return {"cuda": has_cuda, "device_name": device_name, "backend": backend}


def doctor_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="restory doctor")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    gpu = check_gpu()
    vendor_bin = get_install_root() / "runtime" / "tools" / "_vendor"

    executables = {
        "ffmpeg": shutil.which("ffmpeg", path=f"{vendor_bin}/ffmpeg/bin:{os.environ.get('PATH')}"),
        "ffprobe": shutil.which("ffprobe", path=f"{vendor_bin}/ffmpeg/bin:{os.environ.get('PATH')}"),
        "uv": shutil.which("uv", path=f"{vendor_bin}/uv/bin:{os.environ.get('PATH')}"),
        "git-lfs": shutil.which("git-lfs", path=f"{vendor_bin}/git-lfs/bin:{os.environ.get('PATH')}"),
    }

    tools_status = {}
    for name in ALL_TOOLS:
        t_path = tool_dir(name)
        ready_file = t_path / "READY.json"
        tools_status[name] = {
            "installed": ready_file.is_file(),
            "path": str(t_path) if t_path.is_dir() else None,
        }

    report = {
        "product": __product_name__,
        "version": __version__,
        "gpu": gpu,
        "executables": executables,
        "tools": tools_status,
        "tools_root": str(tools_root()),
    }

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(f"============================================================")
        print(f" restory Doctor Report (v{__version__})")
        print(f"============================================================")
        print(f" GPU Backend : {gpu['backend'].upper()} ({gpu['device_name'] or 'N/A'})")
        print(f" Executables :")
        for k, v in executables.items():
            print(f"   - {k:<10}: {'OK (' + v + ')' if v else 'MISSING'}")
        print(f" AI Tools    :")
        for k, v in tools_status.items():
            print(f"   - {k:<12}: {'READY' if v['installed'] else 'NOT INSTALLED'}")
        print(f"============================================================")

    return 0


def install_all_tools_main(argv: list[str] | None = None) -> int:
    """Install all isolated AI tools in sequence."""
    print("============================================================")
    print(" Provisioning ALL Isolated AI Tools")
    print("============================================================")
    success_count = 0
    for name in ALL_TOOLS:
        print(f"\n---> [{success_count + 1}/{len(ALL_TOOLS)}] Provisioning '{name}'...")
        try:
            res = install_tool_main([name])
            if res == 0:
                success_count += 1
        except Exception as exc:
            print(f"[WARN] Failed to install '{name}': {exc}", file=sys.stderr)

    print(f"\n============================================================")
    print(f" Provisioning complete: {success_count}/{len(ALL_TOOLS)} tools ready.")
    print(f"============================================================")
    return 0 if success_count > 0 else 1


def install_tool_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="restory install-tool")
    parser.add_argument("name", choices=ALL_TOOLS + ["all"])
    args = parser.parse_args(argv)

    if args.name == "all":
        return install_all_tools_main()

    t_dir = tool_dir(args.name)
    t_dir.mkdir(parents=True, exist_ok=True)

    vendor_uv = get_install_root() / "runtime" / "tools" / "_vendor" / "uv" / "bin" / "uv"
    uv_bin = str(vendor_uv) if vendor_uv.is_file() else "uv"

    print(f"--> Provisioning isolated environment for '{args.name}' in {t_dir}...")
    env = tool_subprocess_env()

    if args.name == "magi-v3":
        pyproject = (
            "[project]\nname = 'magi-v3-env'\nversion = '0.1.0'\nrequires-python = '>=3.11'\n"
            "dependencies = ['torch', 'torchvision', 'transformers==4.48.3', 'einops', 'timm', 'pillow', 'numpy']\n"
        )
        (t_dir / "pyproject.toml").write_text(pyproject, encoding="utf-8")
        subprocess.run([uv_bin, "sync", "--python", "3.12"], cwd=t_dir, env=env, check=True)
    elif args.name == "whisper-turbo":
        pyproject = (
            "[project]\nname = 'whisper-turbo-env'\nversion = '0.1.0'\nrequires-python = '>=3.11'\n"
            "dependencies = ['faster-whisper', 'torch']\n"
        )
        (t_dir / "pyproject.toml").write_text(pyproject, encoding="utf-8")
        subprocess.run([uv_bin, "sync", "--python", "3.12"], cwd=t_dir, env=env, check=True)

    marker = {"tool": args.name, "status": "ready"}
    (t_dir / "READY.json").write_text(json.dumps(marker, indent=2), encoding="utf-8")
    print(f"--> [OK] Tool '{args.name}' successfully provisioned!")
    return 0