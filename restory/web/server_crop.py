"""restory.web.server_crop — HTTP server & API with Background Batch Cropping & Live Progress Polling."""

from __future__ import annotations

import http.server
import json
import mimetypes
import sys
import threading
import time
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
    detect_magi_batch,
    detect_webtoon,
    sort_reading_order,
)
from restory.panels import (
    load_chapter_boxes,
    recrop_chapter_from_boxes,
    save_chapter_boxes,
)

# Global progress state for live modal progress tracking
crop_progress_lock = threading.Lock()
crop_progress_state = {
    "running": False,
    "current": 0,
    "total": 0,
    "message": "Idle",
    "error": None,
    "active_chapter": "",
}


def update_progress(current: int, total: int, msg: str, running: bool = True, error: str | None = None, ch: str = ""):
    with crop_progress_lock:
        crop_progress_state["running"] = running
        crop_progress_state["current"] = current
        crop_progress_state["total"] = total
        crop_progress_state["message"] = msg
        crop_progress_state["error"] = error
        if ch:
            crop_progress_state["active_chapter"] = ch


def execute_batch_crop_thread(project_root: Path, chapter: str, scope: str, engine: str, rtl: bool):
    try:
        item_dirs = [d for d in project_root.iterdir() if d.is_dir() and (d / "download").is_dir()]
        item_dirs.sort(key=lambda d: d.name)

        if scope == "chapter":
            target_dirs = [d for d in item_dirs if d.name == normalize_chapter_name(chapter) or d.name == chapter]
            if not target_dirs:
                target_dirs = [item_dirs[0]] if item_dirs else []
        elif scope == "all":
            target_dirs = item_dirs
        else:
            target_dirs = [d for d in item_dirs if d.name == normalize_chapter_name(chapter) or d.name == chapter]

        total_pages = sum(len(collect_images(d / "download")) for d in target_dirs)
        if total_pages == 0:
            update_progress(0, 0, "No pages found to crop.", running=False, error="No page images found.")
            return

        update_progress(0, total_pages, f"Starting batch crop ({scope}) using '{engine}' engine...", running=True)
        processed_pages = 0

        for ch_dir in target_dirs:
            pages = collect_images(ch_dir / "download")
            if not pages:
                continue

            update_progress(processed_pages, total_pages, f"Detecting Chapter {ch_dir.name} ({len(pages)} pages)...", running=True, ch=ch_dir.name)

            boxes_dict = {"version": 2, "pages": {}}

            if engine == "magi":
                # CUDA GPU Batch Prediction
                batch_res = detect_magi_batch(pages)
                for p in pages:
                    boxes_dict["pages"][p.stem] = batch_res.get(p, [])
                    processed_pages += 1
                    update_progress(processed_pages, total_pages, f"MAGI AI: Processed {p.name} in Ch {ch_dir.name}", running=True, ch=ch_dir.name)
            elif engine == "webtoon":
                webtoon_meta = detect_webtoon(ch_dir)
                save_chapter_boxes(ch_dir, webtoon_meta)
                processed_pages += len(pages)
                update_progress(processed_pages, total_pages, f"Webtoon Strip: Processed Ch {ch_dir.name}", running=True, ch=ch_dir.name)
                continue
            else:
                # Japanese Paged Manga Python CV logic
                for p in pages:
                    with Image.open(p) as im:
                        boxes_dict["pages"][p.stem] = detect_japanese_paged(im)
                    processed_pages += 1
                    update_progress(processed_pages, total_pages, f"Japanese CV: Processed {p.name} in Ch {ch_dir.name}", running=True, ch=ch_dir.name)

            recrop_chapter_from_boxes(ch_dir, boxes_dict, rtl=rtl)

        update_progress(total_pages, total_pages, "Batch crop & physical render completed successfully!", running=False)
    except Exception as exc:
        update_progress(0, 0, f"Error: {exc}", running=False, error=str(exc))


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

        if path == "/api/crop-progress":
            with crop_progress_lock:
                state_copy = dict(crop_progress_state)
            self._send_json(state_copy)
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

        if path == "/api/start-batch-crop":
            with crop_progress_lock:
                if crop_progress_state["running"]:
                    self._send_json({"status": "error", "message": "Batch crop already in progress."})
                    return

            ch = data.get("chapter", self.active_item)
            scope = data.get("scope", "chapter") # 'page', 'chapter', 'all'
            engine = data.get("engine", "japanese")
            rtl = bool(data.get("rtl", True))

            t = threading.Thread(
                target=execute_batch_crop_thread,
                args=(self.project_root, ch, scope, engine, rtl),
                daemon=True
            )
            t.start()
            self._send_json({"status": "started", "scope": scope, "engine": engine})
            return

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
                raw_boxes = detect_magi_batch([img_path]).get(img_path, [])
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
    print(f" restory Crop Editor running at: {url}")
    print(f" Press 'Done & Continue Pipeline' in browser to finish.")
    print(f"============================================================\n")

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nCrop server stopped.")
    return 0