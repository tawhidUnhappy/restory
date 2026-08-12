"""restory.download — MangaDex downloader with page verification ledger."""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image

from restory import __version__, __product_name__
from restory.config import save_project_manga_json, load_project_manga_json
from restory.layout import chapter_dir, ensure_project_layout

API_BASE = "https://api.mangadex.org"
USER_AGENT = f"restory/{__version__} (+https://github.com/restory/restory)"
MIN_API_INTERVAL = 0.4
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

_last_api_call: float = 0.0


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def _api_get(sess: requests.Session, url: str, params: dict | None = None, retries: int = 5) -> requests.Response:
    global _last_api_call
    gap = MIN_API_INTERVAL - (time.monotonic() - _last_api_call)
    if gap > 0:
        time.sleep(gap)

    for attempt in range(retries):
        try:
            resp = sess.get(url, params=params, timeout=25)
            _last_api_call = time.monotonic()

            if resp.status_code == 429:
                wait = max(float(resp.headers.get("Retry-After", 30)), 15 * (2 ** attempt))
                time.sleep(wait)
                continue

            if resp.status_code >= 500:
                time.sleep(min(60, 5 * (2 ** attempt)))
                continue

            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            _last_api_call = time.monotonic()
            if attempt == retries - 1:
                raise exc
            time.sleep(min(30, 3 * (2 ** attempt)))
    raise RuntimeError(f"All {retries} API attempts failed for {url}")


def extract_manga_id(url_or_id: str) -> str:
    uuid_pattern = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    match = re.search(uuid_pattern, url_or_id.strip())
    if match:
        return match.group(0)
    raise ValueError(f"Could not extract MangaDex UUID from: {url_or_id}")


def fetch_manga_info(sess: requests.Session, manga_id: str) -> dict[str, str]:
    try:
        resp = _api_get(sess, f"{API_BASE}/manga/{manga_id}", retries=2)
        attrs = resp.json().get("data", {}).get("attributes", {}) or {}
        titles = attrs.get("title") or {}
        title = titles.get("en") or next(iter(titles.values()), "manga")
        clean_title = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_.")

        orig_lang = attrs.get("originalLanguage", "ja")
        format_type = "webtoon" if orig_lang in ("ko", "zh") else "paged"

        return {"title": title, "slug": clean_title or "manga", "original_language": orig_lang, "format": format_type}
    except Exception:
        return {"title": "manga", "slug": "manga", "original_language": "ja", "format": "paged"}


def fetch_chapter_feed(sess: requests.Session, manga_id: str, lang: str = "en") -> dict[str, dict]:
    offset, limit = 0, 100
    feed: dict[str, dict] = {}

    while True:
        resp = _api_get(
            sess,
            f"{API_BASE}/manga/{manga_id}/feed",
            params={"translatedLanguage[]": [lang], "order[chapter]": "asc", "limit": limit, "offset": offset},
        )
        data = resp.json()
        items = data.get("data", [])
        total = data.get("total", 0)

        for ch in items:
            attrs = ch.get("attributes", {})
            if attrs.get("externalUrl"):
                continue
            ch_num = str(attrs.get("chapter") or "")
            if not ch_num:
                continue
            candidate = {"id": ch["id"], "pages": int(attrs.get("pages") or 0), "title": attrs.get("title") or ""}
            if ch_num not in feed or candidate["pages"] > feed[ch_num]["pages"]:
                feed[ch_num] = candidate

        offset += len(items)
        if not items or offset >= total:
            break

    return feed


def verify_chapter_images(download_dir: Path, expected_pages: int) -> tuple[bool, list[int]]:
    if not download_dir.is_dir():
        return False, list(range(1, expected_pages + 1))

    files = [f for f in download_dir.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS]
    missing = []

    for idx in range(1, expected_pages + 1):
        matching = [f for f in files if f.stem == f"{idx:03d}"]
        if not matching or matching[0].stat().st_size == 0:
            missing.append(idx)
            continue
        try:
            with Image.open(matching[0]) as img:
                img.verify()
        except Exception:
            missing.append(idx)

    return len(missing) == 0 and len(files) >= expected_pages, missing


def download_chapter_pages(sess: requests.Session, chapter_id: str, download_dir: Path) -> int:
    download_dir.mkdir(parents=True, exist_ok=True)
    resp = _api_get(sess, f"{API_BASE}/at-home/server/{chapter_id}")
    data = resp.json()
    base_url = data.get("baseUrl")
    ch_hash = data.get("chapter", {}).get("hash")
    page_files = data.get("chapter", {}).get("data", [])

    total = len(page_files)
    for idx, filename in enumerate(page_files, start=1):
        ext = os.path.splitext(filename)[1] or ".jpg"
        dest = download_dir / f"{idx:03d}{ext}"

        if dest.is_file() and dest.stat().st_size > 0:
            try:
                with Image.open(dest) as img:
                    img.verify()
                continue
            except Exception:
                dest.unlink(missing_ok=True)

        url = f"{base_url}/data/{ch_hash}/{filename}"
        for attempt in range(3):
            try:
                img_resp = sess.get(url, timeout=30)
                img_resp.raise_for_status()
                dest.write_bytes(img_resp.content)
                break
            except Exception:
                dest.unlink(missing_ok=True)
                time.sleep(2 * (attempt + 1))

        time.sleep(0.3)

    return total


def download_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"{__product_name__} download")
    parser.add_argument("url", help="MangaDex title URL or UUID.")
    parser.add_argument("chapters", nargs="?", default="all")
    parser.add_argument("--name", help="Custom project folder name.")
    parser.add_argument("--lang", default="en")

    args = parser.parse_args(argv)
    manga_id = extract_manga_id(args.url)

    sess = _session()
    info = fetch_manga_info(sess, manga_id)
    manga_name = args.name or info["slug"]

    ensure_project_layout(manga_name)
    manga_ledger = load_project_manga_json(manga_name)
    manga_ledger.update({
        "manga_id": manga_id,
        "manga_name": manga_name,
        "official_title": info["title"],
        "original_language": info["original_language"],
        "format": info["format"],
    })

    feed = fetch_chapter_feed(sess, manga_id, lang=args.lang)
    if not feed:
        print(f"[ERROR] No chapters found for language '{args.lang}'.", file=sys.stderr)
        return 1

    target_chs = sorted(feed.keys()) if args.chapters in ("all", "*") else [args.chapters]
    ledger_chapters = manga_ledger.get("chapters", {})

    for ch_str in target_chs:
        if ch_str not in feed:
            continue
        ch_meta = feed[ch_str]
        ch_dir = chapter_dir(manga_name, ch_str)
        dl_dir = ch_dir / "download"

        is_complete, missing = verify_chapter_images(dl_dir, ch_meta["pages"])
        if is_complete:
            print(f"--> Chapter {ch_str}: Verified complete ({ch_meta['pages']} pages).")
            continue

        print(f"--> Downloading Chapter {ch_str}...")
        download_chapter_pages(sess, ch_meta["id"], dl_dir)

    save_project_manga_json(manga_name, manga_ledger)
    print("\nDownload & verification pass complete!")
    return 0