"""restory.web.server_crop — HTTP server and REST API for Paged Manga Crop Editor with Live Engine Switching."""

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
from restory.detectors import (
    collect_images,
    detect_japanese_paged,
    detect_magi,
    detect_webtoon,
    sort_reading_order,
)
from restory.panels import load_chapter_boxes, recrop_chapter_from_boxes, save_chapter_boxes


class CropEditorHandler(http.server.BaseHTTPRequestHandler):
    project_root: Path = Path(".")
    active_item: str = "01"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        templates_dir = get_install_root() / "restory" / "web" / "templates"
        static_dir = get_install_root() / "restory" / "web" / "static"

        if path in ("/", "/index.html"):
            html_file = templates_dir / "crop_editor.html"
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
            self._send_json({"product": "restory", "gpu": gpu, "active_engine": "japanese"})
            return

        if path == "/api/chapter-data":
            item_dirs = [d.name for d in self.project_root.iterdir() if d.is_dir() and (d / "download").is_dir()]
            item_dirs.sort()
            active = self.active_item if self.active_item in item_dirs else (item_dirs[0] if item_dirs else "01")

            manga_json = self.project_root / "manga.json"
            orig_lang = "ja"
            if manga_json.is_file():
                try:
                    data = json.loads(manga_json.read_text(encoding="utf-8"))
                    orig_lang = data.get("original_language", "ja")
                except Exception:
                    pass

            self._send_json({"chapters": item_dirs, "active_chapter": active, "rtl": orig_lang in ("ja", "zh-hk")})
            return

        if path == "/api/page-data":
            ch = query.get("chapter", [self.active_item])[0]
            ch_norm = normalize_chapter_name(ch)
            ch_dir = self.project_root / ch_norm
            if not ch_dir.is_dir():
                ch_dir = self.project_root / ch

            download_dir = ch_dir / "download"

            pages = collect_images(download_dir)
            pages_list = [{"filename": p.name, "stem": p.stem} for p in pages]
            boxes_data = load_chapter_boxes(ch_dir)

            self._send_json({"chapter": ch_dir.name, "pages": pages_list, "boxes": boxes_data})
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

        if path == "/api/redetect":
            ch = data.get("chapter", self.active_item)
            filename = data.get("filename")
            engine = data.get("engine", "japanese")

            ch_norm = normalize_chapter_name(ch)
            img_path = self.project_root / ch_norm / "download" / filename
            if not img_path.is_file():
                img_path = self.project_root / ch / "download" / filename

            if not img_path.is_file():
                self.send_error(404, "Image file not found")
                return

            if engine == "magi":
                raw_boxes = detect_magi(img_path)
            elif engine == "webtoon":
                ch_dir = img_path.parent.parent
                w_meta = detect_webtoon(ch_dir)
                raw_boxes = []
                with Image.open(img_path) as im:
                    w, h = im.size
                cuts = w_meta.get("cuts", [])
                for idx in range(len(cuts) - 1):
                    raw_boxes.append({
                        "x1": 0, "y1": cuts[idx], "x2": w, "y2": cuts[idx + 1],
                        "z_index": idx, "type": "rectangle", "locked": False, "visible": True, "label": "webtoon_strip"
                    })
            else:
                # Japanese Paged Manga Python Logic
                with Image.open(img_path) as im:
                    raw_boxes = detect_japanese_paged(im)

            self._send_json({"status": "ok", "boxes": raw_boxes, "engine": engine})
            return

        if path == "/api/sort-boxes":
            boxes = data.get("boxes", [])
            rtl = bool(data.get("rtl", True))
            sorted_boxes = sort_reading_order(boxes, rtl=rtl)
            self._send_json({"sorted_boxes": sorted_boxes})
            return

        if path == "/api/save-boxes":
            ch = data.get("chapter", self.active_item)
            boxes = data.get("boxes", {})
            rtl = bool(data.get("rtl", True))

            ch_norm = normalize_chapter_name(ch)
            ch_dir = self.project_root / ch_norm
            if not ch_dir.is_dir():
                ch_dir = self.project_root / ch

            recrop_chapter_from_boxes(ch_dir, boxes, rtl=rtl)
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


def run_crop_server(project_root: Path, item: str = "01", port: int = 8000, open_browser: bool = True) -> int:
    CropEditorHandler.project_root = project_root
    CropEditorHandler.active_item = normalize_chapter_name(item)

    server_address = ("", port)
    httpd = http.server.HTTPServer(server_address, CropEditorHandler)
    url = f"http://localhost:{port}"

    print(f"\n============================================================")
    print(f" restory Crop & Layer Editor running at: {url}")
    print(f" Press 'Done & Continue Pipeline' in browser to finish.")
    print(f"============================================================\n")

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nCrop server stopped.")
    return 0