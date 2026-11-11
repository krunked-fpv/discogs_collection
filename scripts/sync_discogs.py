#!/usr/bin/env python3
"""Deterministic Discogs Collection Sync & Static Site Builder.

Synchronizes `https://www.discogs.com/user/krunked/collection` via the official
Discogs REST API v2.0 (`https://api.discogs.com`), enriches release metadata and
secondary images using an incremental cache, runs deterministic pressing-image
detection (`detect_pressing_image.py`), writes `data/collection.json`, and
injects the static payload into `index.html`.

Discogs API Reference: https://www.discogs.com/developers
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from detect_pressing_image import (
    parse_wax_variant,
    select_release_images_deterministic,
)

DISCOGS_API_BASE = "https://api.discogs.com"
USER_AGENT = "KrunkedDiscogsVault/2.0 +https://github.com/krunked-fpv/discogs_collection"


class DiscogsClient:
    """Deterministic, rate-limit-aware Discogs REST API v2.0 client."""

    def __init__(self, token: str | None = None, user_agent: str = USER_AGENT) -> None:
        self.token = (token or "").strip()
        self.user_agent = user_agent
        self.ratelimit_remaining = 60

    def get_json(self, path_or_url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if path_or_url.startswith("http"):
            url = path_or_url
        else:
            url = f"{DISCOGS_API_BASE}/{path_or_url.lstrip('/')}"
        if params:
            qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{qs}"

        headers = {
            "Accept": "application/vnd.discogs.v2.discogs+json",
            "User-Agent": self.user_agent,
        }
        if self.token:
            headers["Authorization"] = f"Discogs token={self.token}"

        for attempt in range(4):
            if self.ratelimit_remaining <= 3:
                time.sleep(1.5)
            req = urllib.request.Request(url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    rem = resp.headers.get("X-Discogs-Ratelimit-Remaining")
                    if rem and rem.isdigit():
                        self.ratelimit_remaining = int(rem)
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw)
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    wait_s = 15 * (attempt + 1)
                    print(f"[rate-limit] HTTP 429 on {url}; sleeping {wait_s}s...", file=sys.stderr)
                    time.sleep(wait_s)
                    continue
                raise
        raise RuntimeError(f"Exhausted retries fetching {url}")

    def download_bytes(self, url: str) -> bytes | None:
        if not url:
            return None
        headers = {"User-Agent": self.user_agent}
        if self.token:
            headers["Authorization"] = f"Discogs token={self.token}"
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.read()
        except Exception as exc:
            print(f"[warn] Could not download image {url}: {exc}", file=sys.stderr)
            return None


def fetch_full_collection(
    client: DiscogsClient,
    username: str,
    cache_path: pathlib.Path,
    overrides_path: pathlib.Path,
    analyze_pixels: bool = False,
    download_dir: pathlib.Path | None = None,
) -> dict[str, Any]:
    """Fetches all pages of Folder 0 ('All') and enriches each release deterministically."""
    cache: dict[str, Any] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    overrides: dict[str, Any] = {}
    if overrides_path.exists():
        try:
            overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
        except Exception:
            overrides = {}

    profile = client.get_json(f"/users/{username}")
    collection_value = {}
    if client.token:
        try:
            collection_value = client.get_json(f"/users/{username}/collection/value")
        except Exception:
            collection_value = {}

    raw_items: list[dict[str, Any]] = []
    page = 1
    while True:
        payload = client.get_json(
            f"/users/{username}/collection/folders/0/releases",
            params={"per_page": 100, "page": page, "sort": "added", "sort_order": "desc"},
        )
        releases_page = payload.get("releases") or []
        raw_items.extend(releases_page)
        pagination = payload.get("pagination") or {}
        if page >= int(pagination.get("pages") or 1):
            break
        page += 1

    compiled_records: list[dict[str, Any]] = []
    for item in raw_items:
        basic = item.get("basic_information") or {}
        release_id = int(basic.get("id") or item.get("id") or 0)
        rid_str = str(release_id)

        if rid_str not in cache:
            try:
                rel_detail = client.get_json(f"/releases/{release_id}", params={"curr_abbr": "USD"})
                cache[rid_str] = rel_detail
                time.sleep(0.6)
            except Exception as exc:
                print(f"[warn] Could not enrich release {release_id}: {exc}", file=sys.stderr)
                cache[rid_str] = {}

        rel_detail = cache.get(rid_str) or {}
        images = rel_detail.get("images") or []
        if not images and basic.get("cover_image"):
            images = [{"type": "primary", "uri": basic["cover_image"], "width": 600, "height": 600}]

        formats = basic.get("formats") or rel_detail.get("formats") or []
        notes_str = str(rel_detail.get("notes") or "")

        media_cond = "Near Mint (NM or M-)"
        sleeve_cond = "Near Mint (NM or M-)"
        user_comments = ""
        for note_obj in item.get("notes") or []:
            fid = int(note_obj.get("field_id") or 0)
            val = str(note_obj.get("value") or "").strip()
            if fid == 1 and val:
                media_cond = val
            elif fid == 2 and val:
                sleeve_cond = val
            elif val:
                user_comments = val

        downloaded_bytes: dict[str, bytes] = {}
        if analyze_pixels and len(images) > 1:
            for img in images[1:5]:
                uri = img.get("uri") or ""
                raw_b = client.download_bytes(uri)
                if raw_b:
                    downloaded_bytes[uri] = raw_b

        img_selection = select_release_images_deterministic(
            images=images,
            formats=formats,
            notes=f"{notes_str} {user_comments}",
            release_id=release_id,
            overrides=overrides,
            downloaded_bytes_by_uri=downloaded_bytes,
        )

        if download_dir and release_id:
            rel_asset_dir = download_dir / rid_str
            rel_asset_dir.mkdir(parents=True, exist_ok=True)
            for key, fname in (("pressing_image_url", "pressing.jpg"), ("cover_image_url", "cover.jpg")):
                src_url = img_selection.get(key) or ""
                if src_url.startswith("http"):
                    dest_file = rel_asset_dir / fname
                    if not dest_file.exists():
                        b = downloaded_bytes.get(src_url) or client.download_bytes(src_url)
                        if b:
                            dest_file.write_bytes(b)
                    if dest_file.exists():
                        img_selection[f"local_{key}"] = f"assets/releases/{rid_str}/{fname}"

        fmt_parts: list[str] = []
        for f in formats:
            qty = str(f.get("qty") or "1")
            name = str(f.get("name") or "Vinyl")
            descs = list(f.get("descriptions") or [])
            if f.get("text"):
                descs.append(str(f["text"]))
            prefix = f"{qty}x{name}" if qty != "1" else name
            fmt_parts.append(f"{prefix}, {', '.join(descs)}" if descs else prefix)
        format_str = " + ".join(fmt_parts) if fmt_parts else "LP, Album"

        wax_spec = parse_wax_variant(format_str, comments=f"{notes_str} {user_comments}", release_id=release_id)

        artists = basic.get("artists") or rel_detail.get("artists") or []
        artist_name = ", ".join(
            re.sub(r"\s+\(\d+\)$", "", str(a.get("name") or ""))
            for a in artists
            if a.get("name")
        ) or "Unknown Artist"

        labels = basic.get("labels") or rel_detail.get("labels") or []
        label_name = re.sub(r"\s+\(\d+\)$", "", str(labels[0].get("name") or "")) if labels else "Independent"
        catno = str(labels[0].get("catno") or "none") if labels else "none"

        discogs_uri = str(rel_detail.get("uri") or f"https://www.discogs.com/release/{release_id}")
        lowest_price = rel_detail.get("lowest_price")

        compiled_records.append({
            "release_id": release_id,
            "instance_id": item.get("instance_id") or release_id,
            "artist": artist_name,
            "title": str(basic.get("title") or rel_detail.get("title") or ""),
            "year": int(basic.get("year") or rel_detail.get("year") or 0),
            "format_string": format_str,
            "label": label_name,
            "catno": catno,
            "media_condition": media_cond,
            "sleeve_condition": sleeve_cond,
            "comments": user_comments,
            "date_added": str(item.get("date_added") or ""),
            "discogs_url": discogs_uri,
            "estimated_value_usd": float(lowest_price) if isinstance(lowest_price, (int, float)) else 35.0,
            "genres": basic.get("genres") or rel_detail.get("genres") or ["Rock"],
            "styles": basic.get("styles") or rel_detail.get("styles") or ["Metalcore", "Progressive Metal"],
            "images": img_selection,
            "wax_spec": wax_spec,
        })

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")

    compiled_records.sort(key=lambda r: (r.get("date_added") or "", r["artist"], r["title"]), reverse=True)

    pressing_photo_count = sum(1 for r in compiled_records if r["images"].get("has_pressing_photo"))
    colored_count = sum(1 for r in compiled_records if r["wax_spec"]["pattern"] != "black")

    return {
        "schema_version": "2.0.0",
        "source_of_truth": f"https://www.discogs.com/user/{username}/collection",
        "api_documentation": "https://www.discogs.com/developers",
        "username": username,
        "synced_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profile": {
            "username": username,
            "discogs_url": f"https://www.discogs.com/user/{username}/collection",
            "num_collection": len(compiled_records),
            "pressing_photos_detected": pressing_photo_count,
            "colored_or_special_variants": colored_count,
            "collection_value": collection_value,
        },
        "records": compiled_records,
    }


def inject_collection_into_html(html_path: pathlib.Path, collection_data: dict[str, Any]) -> None:
    if not html_path.exists():
        return
    html_text = html_path.read_text(encoding="utf-8")
    payload_js = json.dumps(collection_data, indent=2, ensure_ascii=False)
    pattern = re.compile(
        r"(/\* __DISCOGS_COLLECTION_DATA_START__ \*/)(.*?)(/\* __DISCOGS_COLLECTION_DATA_END__ \*/)",
        re.DOTALL,
    )
    if pattern.search(html_text):
        updated = pattern.sub(
            lambda m: f"{m.group(1)}\nwindow.__DISCOGS_COLLECTION__ = {payload_js};\n{m.group(3)}",
            html_text,
        )
        html_path.write_text(updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic Discogs Collection Sync")
    parser.add_argument("--username", default=os.environ.get("DISCOGS_USERNAME", "krunked"))
    parser.add_argument("--token", default=os.environ.get("DISCOGS_TOKEN", ""))
    parser.add_argument("--output", default="data/collection.json")
    parser.add_argument("--cache", default="data/releases_cache.json")
    parser.add_argument("--overrides", default="data/overrides.json")
    parser.add_argument("--inject-html", default="index.html")
    parser.add_argument("--analyze-pixels", action="store_true")
    parser.add_argument("--download-images", action="store_true")
    args = parser.parse_args()

    out_path = pathlib.Path(args.output)
    cache_path = pathlib.Path(args.cache)
    overrides_path = pathlib.Path(args.overrides)
    download_dir = pathlib.Path("assets/releases") if args.download_images else None

    client = DiscogsClient(token=args.token)
    data = fetch_full_collection(
        client=client,
        username=args.username,
        cache_path=cache_path,
        overrides_path=overrides_path,
        analyze_pixels=args.analyze_pixels,
        download_dir=download_dir,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    hash_copy = dict(data)
    hash_copy.pop("synced_at_utc", None)
    digest = hashlib.sha256(json.dumps(hash_copy, sort_keys=True).encode("utf-8")).hexdigest()
    manifest_path = out_path.parent / "sync_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "username": args.username,
                "record_count": len(data["records"]),
                "pressing_photos_detected": data["profile"]["pressing_photos_detected"],
                "content_sha256": digest,
                "synced_at_utc": data["synced_at_utc"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if args.inject_html:
        inject_collection_into_html(pathlib.Path(args.inject_html), data)

    print(
        f"[ok] Synced {len(data['records'])} records for '{args.username}' "
        f"({data['profile']['pressing_photos_detected']} pressing photos, sha256={digest[:12]})"
    )


if __name__ == "__main__":
    main()
