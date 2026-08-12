"""restory.web.server_webtoon — HTTP server and REST API for Webtoon Strip Editor."""

from __future__ import annotations

import http.server
import json
import mimetypes
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image

from restory.isolation import get_install_root
from restory.layout import normalize_chapter_name
from restory.tools_manager import check_gpu
from restory.detectors.webtoon import detect_webtoon, collect_images
from restory.panels import load_chapter_boxes, save_chapter_boxes


class WebtoonEditorHandler(http.server.BaseHTTPRequestHandler):
    project_root: Path = Path(".")
    active_item: str = "01"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        templates_dir = get_install_root() / "restory" / "web" / "templates"
        static_dir = get_install_root() / "restory" / "web" / "static"

        if path in ("/", "/index.html"):
            html_file = templates_dir / "webtoon_editor.html"
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

        if path == "/api/telemetry":
            gpu = check_gpu()
            self._send_json({"product": "restory", "gpu": gpu, "active_engine": "webtoon-density"})
            return

        if path == "/api/webtoon-data":
            ch = query.get("chapter", [self.active_item])[0]
            ch_norm = normalize_chapter_name(ch)
            ch_dir = self.project_root / ch_norm
            if not ch_dir.is_dir():
                ch_dir = self.project_root / ch

            download_dir = ch_dir / "download"

            pages = collect_images(download_dir)
            pages_list = [{"filename": p.name, "stem": p.stem} for p in pages]

            boxes_data = load_chapter_boxes(ch_dir)
            if not boxes_data or boxes_data.get("format") != "webtoon":
                boxes_data = detect_webtoon(ch_dir)
                save_chapter_boxes(ch_dir, boxes_data)

            self._send_json({"chapter": ch_dir.name, "pages": pages_list, "webtoon_data": boxes_data})
            return

        if path.startswith("/image/download/"):
            parts = path.strip("/").split("/")
            if len(parts) >= 4:
                ch, filename = parts[2], parts[3]
                ch_norm = normalize_chapter_name(ch)
                img_path = self.project_root / ch_norm / "download" / filename
                if not img_path.is_file():
                    img_path = self.project_root / ch / "download" / filename

                if img_path.is_file():
                    mime, _ = mimetypes.guess_type(img_path)
                    self.send_response(200)
                    self.send_header("Content-Type", mime or "image/jpeg")
                    self.end_headers()
                    self.wfile.write(img_path.read_bytes())
                    return

        self.send_error(404, "File Not Found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8")
        data = json.loads(raw_body) if raw_body else {}

        if path == "/api/save-webtoon":
            ch = data.get("chapter", self.active_item)
            webtoon_data = data.get("webtoon_data", {})

            ch_norm = normalize_chapter_name(ch)
            ch_dir = self.project_root / ch_norm
            if not ch_dir.is_dir():
                ch_dir = self.project_root / ch

            save_chapter_boxes(ch_dir, webtoon_data)

            # Crop physical webtoon panels
            download_dir = ch_dir / "download"
            panels_dir = ch_dir / "panels"
            panels_dir.mkdir(parents=True, exist_ok=True)

            pages = collect_images(download_dir)
            if pages:
                imgs = [Image.open(p).convert("RGB") for p in pages]
                canvas_w = max(im.width for im in imgs)
                total_h = sum(im.height for im in imgs)

                combined = Image.new("RGB", (canvas_w, total_h), (255, 255, 255))
                curr_y = 0
                for im in imgs:
                    if im.width != canvas_w:
                        im = im.resize((canvas_w, int(im.height * canvas_w / float(im.width))), Image.LANCZOS)
                    combined.paste(im, (0, curr_y))
                    curr_y += im.height

                cuts = webtoon_data.get("cuts", [])
                valid_idx = 1
                for idx in range(len(cuts) - 1):
                    top, bot = cuts[idx], cuts[idx + 1]
                    if bot - top < 100:
                        continue
                    crop = combined.crop((0, top, canvas_w, bot))
                    crop.save(panels_dir / f"ch{ch_dir.name}_{valid_idx:03d}.jpg", "JPEG", quality=95)
                    valid_idx += 1

            self._send_json({"status": "ok", "chapter": ch_dir.name})
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


def run_webtoon_server(project_root: Path, item: str = "01", port: int = 8002, open_browser: bool = True) -> int:
    WebtoonEditorHandler.project_root = project_root
    WebtoonEditorHandler.active_item = normalize_chapter_name(item)

    server_address = ("", port)
    httpd = http.server.HTTPServer(server_address, WebtoonEditorHandler)
    url = f"http://localhost:{port}"

    print(f"\n============================================================")
    print(f" restory Webtoon Strip Editor running at: {url}")
    print(f" Press 'Done & Continue Pipeline' in browser to finish.")
    print(f"============================================================\n")

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nWebtoon server stopped.")
    return 0