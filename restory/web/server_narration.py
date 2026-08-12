"""restory.web.server_narration — HTTP server and REST API for Side-by-Side Narration Script Editor."""

from __future__ import annotations

import http.server
import json
import mimetypes
import sys
import threading
import wave
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from restory.isolation import get_install_root
from restory.layout import project_memory_json
from restory.narration import validate_narration_json, NarrationError
from restory.detectors.heuristic import collect_images
from restory.audio import apply_edge_fades_and_declick, SAMPLE_RATE


class NarrationEditorHandler(http.server.BaseHTTPRequestHandler):
    project_root: Path = Path(".")
    active_item: str = "01"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        templates_dir = get_install_root() / "restory" / "web" / "templates"
        static_dir = get_install_root() / "restory" / "web" / "static"

        if path in ("/", "/index.html"):
            html_file = templates_dir / "narration_editor.html"
            if html_file.is_file():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_file.read_bytes())
                return

        if path.startswith("/static/"):
            rel_path = path[len("/static/"):]
            asset_path = static_dir / rel_path
            if asset_path.is_file():
                mime, _ = mimetypes.guess_type(asset_path)
                self.send_response(200)
                self.send_header("Content-Type", mime or "application/octet-stream")
                self.end_headers()
                self.wfile.write(asset_path.read_bytes())
                return

        if path == "/api/chapters":
            item_dirs = [d.name for d in self.project_root.iterdir() if d.is_dir() and (d / "panels").is_dir()]
            item_dirs.sort()
            active = self.active_item if self.active_item in item_dirs else (item_dirs[0] if item_dirs else "01")

            self._send_json({"chapters": item_dirs, "active": active})
            return

        if path == "/api/narration-data":
            ch = query.get("chapter", [self.active_item])[0]
            ch_dir = self.project_root / ch
            narration_file = ch_dir / "narration.json"
            panels_dir = ch_dir / "panels"

            entries = []
            if narration_file.is_file():
                try:
                    entries = json.loads(narration_file.read_text(encoding="utf-8-sig"))
                except Exception:
                    pass

            if not entries and panels_dir.is_dir():
                panels = collect_images(panels_dir)
                for p in panels:
                    entries.append({
                        "image": p.name,
                        "narration": "",
                        "beat_id": f"ch{ch}_{p.stem}",
                        "pause_after_ms": 0
                    })
                narration_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

            memory_file = project_memory_json(self.project_root.name)
            cast_list = []
            if memory_file.is_file():
                try:
                    m_data = json.loads(memory_file.read_text(encoding="utf-8"))
                    cast_list = list(m_data.get("characters", {}).keys())
                except Exception:
                    pass

            self._send_json({"chapter": ch, "entries": entries, "cast": cast_list})
            return

        if path.startswith("/image/panels/"):
            parts = path.strip("/").split("/")
            if len(parts) >= 4:
                ch, filename = parts[2], parts[3]
                img_path = self.project_root / ch / "panels" / filename
                if img_path.is_file():
                    mime, _ = mimetypes.guess_type(img_path)
                    self.send_response(200)
                    self.send_header("Content-Type", mime or "image/jpeg")
                    self.end_headers()
                    self.wfile.write(img_path.read_bytes())
                    return

        if path.startswith("/audio/preview/"):
            parts = path.strip("/").split("/")
            if len(parts) >= 4:
                ch, stem = parts[2], parts[3]
                wav_path = self.project_root / ch / "audio_faded" / f"{stem}.wav"
                if not wav_path.is_file():
                    wav_path = self.project_root / ch / "audio" / f"{stem}.wav"

                if wav_path.is_file():
                    self.send_response(200)
                    self.send_header("Content-Type", "audio/wav")
                    self.end_headers()
                    self.wfile.write(wav_path.read_bytes())
                    return

        self.send_error(404, "File Not Found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8")
        data = json.loads(raw_body) if raw_body else {}

        if path == "/api/save-narration":
            ch = data.get("chapter", self.active_item)
            entries = data.get("entries", [])
            ch_dir = self.project_root / ch
            narration_file = ch_dir / "narration.json"

            narration_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            self._send_json({"status": "ok", "chapter": ch})
            return

        if path == "/api/preview-tts":
            ch = data.get("chapter", self.active_item)
            stem = data.get("stem", "preview")

            ch_dir = self.project_root / ch
            audio_dir = ch_dir / "audio"
            faded_dir = ch_dir / "audio_faded"
            audio_dir.mkdir(parents=True, exist_ok=True)
            faded_dir.mkdir(parents=True, exist_ok=True)

            out_wav = audio_dir / f"{stem}.wav"
            faded_wav = faded_dir / f"{stem}.wav"

            with wave.open(str(out_wav), "wb") as w:
                w.setparams((1, 2, SAMPLE_RATE, int(SAMPLE_RATE * 2.0), "NONE", "not compressed"))
                w.writeframes(b"\x00" * int(SAMPLE_RATE * 2.0 * 2))

            faded_wav.write_bytes(out_wav.read_bytes())
            apply_edge_fades_and_declick(faded_wav, fade_ms=8.0)

            self._send_json({"status": "ok", "audio_url": f"/audio/preview/{ch}/{stem}"})
            return

        if path == "/api/narration-check":
            ch = data.get("chapter", self.active_item)
            ch_dir = self.project_root / ch
            try:
                validate_narration_json(ch_dir, require_panels=True)
                self._send_json({"ok": True})
            except NarrationError as exc:
                self._send_json({"ok": False, "error": str(exc)})
            return

        if path == "/api/shutdown":
            self._send_json({"status": "stopping"})
            threading.Thread(target=self.server.shutdown).start()
            return

        self.send_error(400, "Bad Request")

    def _send_json(self, data: dict) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def run_narration_server(project_root: Path, item: str = "01", port: int = 8001, open_browser: bool = True) -> int:
    NarrationEditorHandler.project_root = project_root
    NarrationEditorHandler.active_item = item

    server_address = ("", port)
    httpd = http.server.HTTPServer(server_address, NarrationEditorHandler)
    url = f"http://localhost:{port}"

    print(f"\n============================================================")
    print(f" restory Side-by-Side Narration Editor running at: {url}")
    print(f" Press 'Done & Continue Pipeline' in browser to finish.")
    print(f"============================================================\n")

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nNarration server stopped.")
    return 0