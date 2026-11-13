#!/usr/bin/env python3
"""Pick The Right Pressing Photo & Static Index Compiler (`pick_pressing_photo.py`).

Inspects every release in `data/collection.json` AND every release folder in
`assets/releases/<release_id>/`, discovers all local `img_*.jpg` files even when
`data/releases_cache.json` is incomplete, re-evaluates all candidate images with
the Calibrated Multi-Scale Concentric Dual-Circle CV + Guideline 13.8 classifier
(automatically upgrading any stale/wrong past auto-picks in `overrides.json` and
`pressing.jpg`, and deleting false-positive `pressing.jpg` files when a release
should display its deterministic wax seed), reconciles the Vinyl Flattening Queue
and Collection Value, and injects the compiled payload into `index.html`.

Usage (from `C:\\DiscogsCollection\\discogs_collection` or `scripts/`):
    python pick_pressing_photo.py
    python scripts/pick_pressing_photo.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import os
import pathlib
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from typing import Any

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else SCRIPT_DIR
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from detect_pressing_image import (
    parse_wax_variant,
    resolve_flattening_status,
    select_release_images_deterministic,
)

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

DISCOGS_API_BASE = "https://api.discogs.com"
USER_AGENT = "KrunkedDiscogsVault/2.3 +https://github.com/krunked-fpv/discogs_collection"
DEFAULT_TOKEN = ""

# Verified marketplace purchase prices for releases with 0 active copies currently listed on Discogs
VERIFIED_PRICE_FALLBACKS: dict[int, float] = {
    22031968: 59.99,  # Currents - The Way It Ends (Electric Blue)
    12988109: 35.00,  # Animals As Leaders - Animals As Leaders (Clear 2xLP)
    27611781: 45.00,  # Erra - Drift (Blue/Cyan Swirl 2xLP)
    27717681: 25.00,  # Erra - Neon (Ultra Clear)
    38854575: 45.00,  # Periphery - A Pale White Dot (Black in Green)
    26047519: 55.00,  # Protest The Hero - Fortress (Purple/Red Splatter 2xLP)
    27079776: 55.00,  # Greyhaven - This Bright And Beautiful World (Red in Clear)
    9346527: 39.98,   # Periphery - Periphery III: Select Difficulty (White 2xLP)
    27927123: 29.00,  # Nothing More - Spirits (Clear w/ Black Smoke)
}


def sanitize_token(raw_token: str | None) -> str:
    """Strips control chars (e.g. \\x16 from Ctrl+V in Windows getpass), quotes, and prefixes."""
    if not raw_token:
        return ""
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]+", "", str(raw_token)).strip().strip("\"'` ")
    for prefix in ("DISCOGS_TOKEN=", "Discogs token=", "token=", "Bearer "):
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip().strip("\"'` ")
    return re.sub(r"[^A-Za-z0-9._\-]", "", cleaned)


def resolve_discogs_token(cli_token: str | None = None, repo_root: pathlib.Path = REPO_ROOT) -> str:
    """Resolves a clean Discogs token from CLI, environment, .env, or Windows HKCU Registry."""
    raw_token = cli_token if cli_token is not None else os.environ.get("DISCOGS_TOKEN", "")
    dotenv_path = repo_root / ".env"
    if not sanitize_token(raw_token) and dotenv_path.exists():
        try:
            for line in dotenv_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line_s = line.strip()
                if line_s.startswith("DISCOGS_TOKEN="):
                    raw_token = line_s.split("=", 1)[1].strip()
                    break
        except Exception:
            pass
    if os.name == "nt" and not sanitize_token(raw_token):
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ) as key:
                reg_val, _ = winreg.QueryValueEx(key, "DISCOGS_TOKEN")
                if reg_val:
                    raw_token = str(reg_val)
        except Exception:
            pass
    return sanitize_token(raw_token) or sanitize_token(DEFAULT_TOKEN)


def _download_image_bytes(url: str, token: str = "") -> bytes | None:
    if not url or not url.startswith("http"):
        return None
    clean_tok = sanitize_token(token)
    for use_token in ([clean_tok, ""] if clean_tok else [""]):
        headers = {"User-Agent": USER_AGENT}
        if use_token:
            headers["Authorization"] = f"Discogs token={use_token}"
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 401, 403) and use_token:
                continue
            return None
        except Exception:
            return None
    return None


def _fetch_release_detail_from_discogs(release_id: int, token: str = "") -> dict[str, Any]:
    """Fetches /releases/{release_id} from Discogs API with automatic 400/401/403 token fallback."""
    if release_id <= 0:
        return {}
    url = f"{DISCOGS_API_BASE}/releases/{release_id}?curr_abbr=USD"
    clean_tok = sanitize_token(token)
    for use_token in ([clean_tok, ""] if clean_tok else [""]):
        headers = {
            "Accept": "application/vnd.discogs.v2.discogs+json",
            "User-Agent": USER_AGENT,
        }
        if use_token:
            headers["Authorization"] = f"Discogs token={use_token}"
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=25) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                    data = json.loads(raw)
                    if isinstance(data, dict) and data.get("id"):
                        return data
            except urllib.error.HTTPError as exc:
                if exc.code in (400, 401, 403) and use_token:
                    break
                if exc.code == 429:
                    time.sleep(10 * (attempt + 1))
                    continue
                return {}
            except Exception:
                return {}
    return {}


def _probe_image_dimensions(img_bytes: bytes) -> tuple[int, int]:
    """Returns (width, height) from image bytes using PIL or fallback JPEG SOF header parsing."""
    if HAS_PIL:
        try:
            with Image.open(io.BytesIO(img_bytes)) as im:
                return im.size
        except Exception:
            pass
    try:
        data = io.BytesIO(img_bytes)
        if data.read(2) == b"\xff\xd8":
            while True:
                marker = data.read(2)
                if len(marker) < 2:
                    break
                while marker[1] == 0xFF:
                    b = data.read(1)
                    if not b:
                        break
                    marker = bytes([0xFF, b[0]])
                m_type = marker[1]
                if m_type in (0xD8, 0xD9) or 0xD0 <= m_type <= 0xD7:
                    continue
                length_bytes = data.read(2)
                if len(length_bytes) < 2:
                    break
                seg_len = int.from_bytes(length_bytes, "big")
                if m_type in (0xC0, 0xC1, 0xC2, 0xC3):
                    sof = data.read(5)
                    if len(sof) == 5:
                        h = int.from_bytes(sof[1:3], "big")
                        w = int.from_bytes(sof[3:5], "big")
                        if w > 0 and h > 0:
                            return (w, h)
                    break
                data.seek(seg_len - 2, io.SEEK_CUR)
    except Exception:
        pass
    return (600, 600)


def _discover_local_release_images(rel_dir: pathlib.Path, rid_str: str) -> list[tuple[int, pathlib.Path]]:
    """Returns sorted `(idx, path)` pairs for all `img_<idx>.jpg` files in `rel_dir`."""
    found: list[tuple[int, pathlib.Path]] = []
    if not rel_dir.exists():
        return found
    for p in rel_dir.iterdir():
        if not p.is_file():
            continue
        m = re.match(r"^img_(\d+)\.(?:jpg|jpeg|png|webp)$", p.name, flags=re.IGNORECASE)
        if m:
            found.append((int(m.group(1)), p))
    found.sort(key=lambda x: x[0])
    return found


def inject_into_index_html(
    html_path: pathlib.Path,
    collection_data: dict[str, Any],
    overrides_data: dict[str, Any],
) -> bool:
    """Injects window.__DISCOGS_COLLECTION__, window.__DISCOGS_OVERRIDES__, and static KPI values into index.html."""
    if not html_path.exists():
        print(f"[warn] HTML file not found at {html_path}", file=sys.stderr)
        return False

    html_text = html_path.read_text(encoding="utf-8")
    if "â" in html_text or "Ã" in html_text:
        try:
            html_text = html_text.encode("cp1252").decode("utf-8")
        except Exception:
            pass

    payload_js = json.dumps(collection_data, indent=2, ensure_ascii=False)
    overrides_js = json.dumps(overrides_data, indent=2, ensure_ascii=False)

    sync_stamp = str(collection_data.get("synced_at_utc") or "")
    replacement_block = (
        "/* __DISCOGS_COLLECTION_DATA_START__ */\n"
        f"    window.__DISCOGS_OVERRIDES__ = {overrides_js};\n"
        f"    window.__DISCOGS_COLLECTION__ = {payload_js};\n"
        "    try {\n"
        f"      var __pySyncStamp = {json.dumps(sync_stamp)};\n"
        "      if (typeof localStorage !== 'undefined' && localStorage.getItem('__discogs_py_sync_stamp__') !== __pySyncStamp) {\n"
        "        Object.keys(localStorage).forEach(function(k) {\n"
        "          if (k.toLowerCase().indexOf('token') === -1) {\n"
        "            localStorage.removeItem(k);\n"
        "          }\n"
        "        });\n"
        "        localStorage.setItem('__discogs_py_sync_stamp__', __pySyncStamp);\n"
        "      }\n"
        "    } catch (e) {}\n"
        "    /* __DISCOGS_COLLECTION_DATA_END__ */"
    )

    pattern = re.compile(
        r"/\*\s*__DISCOGS_COLLECTION_DATA_START__\s*\*/.*?/\*\s*__DISCOGS_COLLECTION_DATA_END__\s*\*/",
        re.DOTALL,
    )
    if pattern.search(html_text):
        html_text = pattern.sub(lambda _: replacement_block, html_text)
    else:
        print("[warn] Could not find __DISCOGS_COLLECTION_DATA_START__ marker in index.html", file=sys.stderr)
        return False

    prof = collection_data.get("profile") or {}
    records = collection_data.get("records") or []
    total_lps = len(records)
    pressing_count = int(prof.get("pressing_photos_detected") or 0)
    colored_count = int(prof.get("colored_or_special_variants") or 0)
    colored_pct = f"{(colored_count / total_lps * 100.0):.1f}%" if total_lps else "0.0%"

    col_val = prof.get("collection_value") or {}
    median_str = str(col_val.get("median") or col_val.get("formatted_total") or "$6,011.87")
    range_str = f"Min {col_val.get('minimum', '$3,721.74')} • Max {col_val.get('maximum', '$10,437.49')}"

    todo_count = sum(1 for r in records if r.get("flattening_status") == "Need to be done")
    done_count = sum(1 for r in records if r.get("flattening_status") == "Done")

    kpi_replacements = [
        (r'(<div id="kpi-total-records"[^>]*>)(.*?)(</div>)', f"\\g<1>{total_lps} LPs\\g<3>"),
        (r'(<div id="kpi-pressing-photos"[^>]*>)(.*?)(</div>)', f"\\g<1>{pressing_count} / {total_lps}\\g<3>"),
        (r'(<div id="kpi-colored-wax"[^>]*>)(.*?)(</div>)', f"\\g<1>{colored_pct}\\g<3>"),
        (r'(<div id="kpi-vault-value"[^>]*>)(.*?)(</div>)', f"\\g<1>{median_str}\\g<3>"),
        (r'(<div id="kpi-vault-range"[^>]*>)(.*?)(</div>)', f"\\g<1>{range_str}\\g<3>"),
        (r'(<div id="kpi-flattening"[^>]*>)(.*?)(</div>)', f"\\g<1>{todo_count} Queued / {done_count} Done\\g<3>"),
        (r'(<span id="flatten-todo-count"[^>]*>)(.*?)(</span>)', f"\\g<1>{todo_count} Records\\g<3>"),
        (r'(<span id="flatten-done-count"[^>]*>)(.*?)(</span>)', f"\\g<1>{done_count} Records\\g<3>"),
        (
            r'(<div id="grid-status-label"[^>]*>\s*)(.*?)(\s*</div>)',
            f"\\g<1>Showing {total_lps} of {total_lps} releases in krunked's collection\\g<3>",
        ),
    ]
    for pat_str, rep_str in kpi_replacements:
        html_text = re.sub(pat_str, rep_str, html_text, flags=re.DOTALL)

    html_path.write_text(html_text, encoding="utf-8")
    return True


def _write_pressing_and_cover_files(
    rel_dir: pathlib.Path,
    rid_str: str,
    img_selection: dict[str, Any],
    local_files: list[tuple[int, pathlib.Path]],
) -> tuple[bool, bool]:
    """Ensures `cover.jpg` and `pressing.jpg` are physically synced in `assets/releases/<rid>/`.

    Returns `(updated_pressing, removed_stale_pressing)`.
    When `has_pressing_photo` is False, any stale `pressing.jpg` in `rel_dir` is deleted so
    the release cleanly displays its deterministic procedural wax seed.
    """
    if not (rel_dir / "cover.jpg").exists():
        if (rel_dir / "img_0.jpg").exists():
            shutil.copyfile(rel_dir / "img_0.jpg", rel_dir / "cover.jpg")
        elif local_files:
            shutil.copyfile(local_files[0][1], rel_dir / "cover.jpg")

    dest_pressing = rel_dir / "pressing.jpg"

    if not img_selection.get("has_pressing_photo"):
        removed_stale = False
        if dest_pressing.exists():
            try:
                dest_pressing.unlink()
                removed_stale = True
            except Exception:
                pass
        img_selection["pressing_image_url"] = ""
        img_selection.pop("local_pressing_image_url", None)
        if (rel_dir / "cover.jpg").exists():
            img_selection["display_thumbnail_url"] = f"assets/releases/{rid_str}/cover.jpg"
        return (False, removed_stale)

    raw_sel = img_selection.get("selected_index")
    sel_idx = int(raw_sel) if raw_sel is not None else -1

    src_local: pathlib.Path | None = None
    if sel_idx >= 0 and (rel_dir / f"img_{sel_idx}.jpg").exists():
        src_local = rel_dir / f"img_{sel_idx}.jpg"
    else:
        p_url = str(img_selection.get("pressing_image_url") or "")
        m = re.search(r"img_(\d+)\.jpg", p_url)
        if m and (rel_dir / f"img_{m.group(1)}.jpg").exists():
            sel_idx = int(m.group(1))
            src_local = rel_dir / f"img_{sel_idx}.jpg"

    updated = False
    if src_local and src_local.exists():
        src_bytes = src_local.read_bytes()
        img_hash = hashlib.sha256(src_bytes).hexdigest()[:8]
        if not dest_pressing.exists() or dest_pressing.read_bytes() != src_bytes:
            try:
                if dest_pressing.exists():
                    dest_pressing.unlink()
            except Exception:
                pass
            dest_pressing.write_bytes(src_bytes)
            updated = True
        cache_busted_url = f"assets/releases/{rid_str}/pressing.jpg?v={sel_idx}_{img_hash}"
        img_selection["local_pressing_image_url"] = cache_busted_url
        img_selection["display_thumbnail_url"] = cache_busted_url
        if not str(img_selection.get("pressing_image_url") or "").startswith("http"):
            img_selection["pressing_image_url"] = cache_busted_url
    return (updated, False)


def run_pick_pressing_photos(
    collection_path: pathlib.Path,
    cache_path: pathlib.Path,
    overrides_path: pathlib.Path,
    flattening_path: pathlib.Path,
    assets_releases_dir: pathlib.Path,
    html_path: pathlib.Path,
    download_missing: bool = True,
    token: str = "",
) -> dict[str, Any]:
    """Evaluates all release images, picks the best pressing photo, updates JSONs, and injects index.html."""
    if not collection_path.exists():
        raise FileNotFoundError(f"Collection file not found: {collection_path}")

    clean_token = resolve_discogs_token(cli_token=token, repo_root=REPO_ROOT)

    collection_data = json.loads(collection_path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = collection_data.get("records") or []

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

    flattening_queue: dict[str, Any] = {}
    if flattening_path.exists():
        try:
            flattening_queue = json.loads(flattening_path.read_text(encoding="utf-8"))
        except Exception:
            flattening_queue = {}

    assets_releases_dir.mkdir(parents=True, exist_ok=True)

    # 1. Discover any newly added folders in assets/releases/<rid>/ that aren't in collection.json yet
    known_rids: set[int] = {int(r.get("release_id") or 0) for r in records if int(r.get("release_id") or 0) > 0}
    cache_dirty = False

    for child_dir in sorted(assets_releases_dir.iterdir()):
        if not child_dir.is_dir() or not child_dir.name.isdigit():
            continue
        folder_rid = int(child_dir.name)
        folder_rid_str = child_dir.name
        if folder_rid in known_rids:
            continue

        rel_detail = cache.get(folder_rid_str) or {}
        if not rel_detail.get("id") and download_missing:
            rel_detail = _fetch_release_detail_from_discogs(folder_rid, token=clean_token)
            if rel_detail:
                cache[folder_rid_str] = rel_detail
                cache_dirty = True
                time.sleep(0.4)

        artists = rel_detail.get("artists") or []
        artist_name = ", ".join(
            re.sub(r"\s+\(\d+\)$", "", str(a.get("name") or ""))
            for a in artists
            if a.get("name")
        ) or "Unknown Artist"
        title_str = str(rel_detail.get("title") or f"Release #{folder_rid}")
        labels = rel_detail.get("labels") or []
        label_name = re.sub(r"\s+\(\d+\)$", "", str(labels[0].get("name") or "")) if labels else "Independent"
        catno = str(labels[0].get("catno") or "none") if labels else "none"
        formats = rel_detail.get("formats") or []
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

        records.append({
            "release_id": folder_rid,
            "instance_id": folder_rid,
            "artist": artist_name,
            "title": title_str,
            "year": int(rel_detail.get("year") or 0),
            "format_string": format_str,
            "label": label_name,
            "catno": catno,
            "media_condition": "Near Mint (NM or M-)",
            "sleeve_condition": "Near Mint (NM or M-)",
            "comments": "",
            "date_added": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"),
            "discogs_url": str(rel_detail.get("uri") or f"https://www.discogs.com/release/{folder_rid}"),
            "estimated_value_usd": float(rel_detail.get("lowest_price") or VERIFIED_PRICE_FALLBACKS.get(folder_rid, 35.0)),
            "flattening_status": "Not Listed",
            "genres": rel_detail.get("genres") or ["Rock"],
            "styles": rel_detail.get("styles") or ["Metalcore", "Progressive Metal"],
            "images": {},
            "wax_spec": {},
        })
        known_rids.add(folder_rid)

    pressing_photo_count = 0
    colored_count = 0
    newly_detected_overrides = 0
    upgraded_pressing_files = 0
    removed_false_pressing_files = 0

    for rec in records:
        rid = int(rec.get("release_id") or 0)
        rid_str = str(rid)
        rel_detail = cache.get(rid_str) or {}
        rel_dir = assets_releases_dir / rid_str
        rel_dir.mkdir(parents=True, exist_ok=True)

        local_files = _discover_local_release_images(rel_dir, rid_str)
        cached_imgs_initial = list(rel_detail.get("images") or [])
        has_empty_cached_uris = any(not (im.get("uri") or im.get("resource_url")) for im in cached_imgs_initial)

        # If cache has <= 1 image, or was truncated at 6 images in an older build, or has empty URIs, enrich from Discogs API
        if (
            (len(cached_imgs_initial) <= 1 and len(local_files) <= 1)
            or (len(cached_imgs_initial) == 6 and len(local_files) <= 6)
            or has_empty_cached_uris
        ) and download_missing and rid > 0:
            fetched_detail = _fetch_release_detail_from_discogs(rid, token=clean_token)
            if fetched_detail.get("images"):
                rel_detail = fetched_detail
                cache[rid_str] = rel_detail
                cache_dirty = True
                time.sleep(0.4)

        # Gather full images list from cache, record, and ALL local img_*.jpg files in assets/releases/<rid>/
        cached_imgs = list(rel_detail.get("images") or [])
        rec_classified = [
            img for img in (rec.get("images", {}).get("classified_images") or [])
            if not str(img.get("uri") or "").startswith("procedural://")
        ]
        raw_images: list[dict[str, Any]] = cached_imgs if len(cached_imgs) >= len(rec_classified) else rec_classified
        if not raw_images and rec.get("images", {}).get("cover_image_url"):
            raw_images = [
                {
                    "type": "primary",
                    "uri": rec["images"]["cover_image_url"],
                    "width": 600,
                    "height": 600,
                }
            ]

        # Download any missing images from raw_images into assets/releases/<rid>/img_<idx>.jpg
        downloaded_bytes: dict[str, bytes] = {}
        for idx, img in enumerate(raw_images[:40]):
            uri = img.get("uri") or img.get("resource_url") or f"assets/releases/{rid_str}/img_{idx}.jpg"
            local_img_file = rel_dir / f"img_{idx}.jpg"
            if local_img_file.exists():
                try:
                    b = local_img_file.read_bytes()
                    downloaded_bytes[uri] = b
                    downloaded_bytes[f"idx:{idx}"] = b
                except Exception:
                    pass
            elif download_missing and uri.startswith("http"):
                raw_b = _download_image_bytes(uri, token=clean_token)
                if raw_b:
                    local_img_file.write_bytes(raw_b)
                    downloaded_bytes[uri] = raw_b
                    downloaded_bytes[f"idx:{idx}"] = raw_b

        # Re-scan local files so any img_0.jpg .. img_N.jpg on disk are ALWAYS included with true dimensions
        local_files = _discover_local_release_images(rel_dir, rid_str)
        existing_indices = set(range(len(raw_images)))
        for disk_idx, disk_path in local_files:
            try:
                b = disk_path.read_bytes()
            except Exception:
                continue
            w, h = _probe_image_dimensions(b)
            local_uri = f"assets/releases/{rid_str}/{disk_path.name}"
            downloaded_bytes[local_uri] = b
            downloaded_bytes[f"idx:{disk_idx}"] = b

            if disk_idx < len(raw_images):
                entry_uri = raw_images[disk_idx].get("uri") or raw_images[disk_idx].get("resource_url") or ""
                if not entry_uri:
                    raw_images[disk_idx]["uri"] = local_uri
                else:
                    downloaded_bytes[entry_uri] = b
                if w > 0 and h > 0:
                    raw_images[disk_idx]["width"] = w
                    raw_images[disk_idx]["height"] = h
            elif disk_idx not in existing_indices:
                while len(raw_images) < disk_idx:
                    pad_i = len(raw_images)
                    raw_images.append({
                        "type": "primary" if pad_i == 0 else "secondary",
                        "uri": f"assets/releases/{rid_str}/img_{pad_i}.jpg",
                        "width": 600,
                        "height": 600,
                    })
                raw_images.append({
                    "type": "primary" if disk_idx == 0 else "secondary",
                    "uri": local_uri,
                    "width": w,
                    "height": h,
                })
                existing_indices.add(disk_idx)

        formats = rel_detail.get("formats") or []
        if not formats and rec.get("format_string"):
            formats = [{"descriptions": [str(rec["format_string"])]}]
        notes_str = str(rel_detail.get("notes") or "")
        user_comments = str(rec.get("comments") or "")
        fmt_str = str(rec.get("format_string") or "LP, Album")

        img_selection = select_release_images_deterministic(
            images=raw_images,
            formats=formats,
            notes=f"{notes_str}\n{user_comments}",
            release_id=rid,
            overrides=overrides,
            downloaded_bytes_by_uri=downloaded_bytes,
            local_release_dir=rel_dir,
        )

        updated_file, removed_stale_file = _write_pressing_and_cover_files(
            rel_dir, rid_str, img_selection, local_files
        )
        if updated_file:
            upgraded_pressing_files += 1
            sel_i = img_selection.get("selected_index")
            print(f"[updated] Release #{rid_str} ({rec.get('artist')} - {rec.get('title')}): pressing.jpg -> img_{sel_i}.jpg")
        elif removed_stale_file:
            removed_false_pressing_files += 1
            print(f"[cleaned] Release #{rid_str} ({rec.get('artist')} - {rec.get('title')}): removed non-pressing pressing.jpg -> using deterministic seed")

        # Update overrides.json with cache-busted local path when CV verified a pressing photo,
        # and purge any stale override when no pressing photo exists
        prev_ov = overrides.get(rid_str)
        if img_selection.get("has_pressing_photo") and len(raw_images) > 1:
            preferred_url = (
                img_selection.get("local_pressing_image_url")
                or img_selection.get("pressing_image_url")
                or ""
            )
            det_method = str(img_selection.get("detection_method") or "")
            if preferred_url and det_method.startswith("deterministic_annular_cv"):
                if rid_str not in overrides or (isinstance(prev_ov, str) and prev_ov != preferred_url):
                    overrides[rid_str] = preferred_url
                    newly_detected_overrides += 1
            elif preferred_url and isinstance(prev_ov, str) and prev_ov != preferred_url:
                overrides[rid_str] = preferred_url
                newly_detected_overrides += 1
        elif not img_selection.get("has_pressing_photo"):
            if rid_str in overrides and isinstance(prev_ov, str):
                overrides.pop(rid_str, None)
                newly_detected_overrides += 1

        rec["images"] = img_selection

        # Re-verify wax_spec
        wax_spec = parse_wax_variant(fmt_str, comments=f"{notes_str}\n{user_comments}", release_id=rid)
        rec["wax_spec"] = wax_spec

        # Re-verify estimated_value_usd
        lowest_price = rel_detail.get("lowest_price")
        if isinstance(lowest_price, (int, float)) and float(lowest_price) > 0:
            rec["estimated_value_usd"] = round(float(lowest_price), 2)
        elif rid in VERIFIED_PRICE_FALLBACKS:
            rec["estimated_value_usd"] = VERIFIED_PRICE_FALLBACKS[rid]
        elif not isinstance(rec.get("estimated_value_usd"), (int, float)) or float(rec.get("estimated_value_usd") or 0) <= 0:
            rec["estimated_value_usd"] = 35.0
        else:
            rec["estimated_value_usd"] = round(float(rec["estimated_value_usd"]), 2)

        # Re-verify flattening_status from Google Keep flattening queue
        if flattening_queue:
            rec["flattening_status"] = resolve_flattening_status(
                artist=str(rec.get("artist") or ""),
                title=str(rec.get("title") or ""),
                release_id=rid,
                queue_data=flattening_queue,
            )

        if img_selection.get("has_pressing_photo"):
            pressing_photo_count += 1
        if wax_spec.get("pattern") != "black":
            colored_count += 1

    if cache_dirty:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")

    # Save sorted overrides.json
    overrides_sorted = {
        k: overrides[k]
        for k in sorted(overrides.keys(), key=lambda x: int(x) if str(x).isdigit() else str(x))
    }
    overrides_path.parent.mkdir(parents=True, exist_ok=True)
    overrides_path.write_text(json.dumps(overrides_sorted, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Compute total and range collection values
    total_est_val = round(sum(float(r.get("estimated_value_usd") or 0.0) for r in records), 2)
    existing_val = (collection_data.get("profile") or {}).get("collection_value") or {}
    collection_value = {
        "minimum": existing_val.get("minimum") or "$3,721.74",
        "median": existing_val.get("median") or "$6,011.87",
        "maximum": existing_val.get("maximum") or "$10,437.49",
        "total_estimated_usd": total_est_val,
        "formatted_total": f"${total_est_val:,.2f}",
    }

    todo_count = sum(1 for r in records if r.get("flattening_status") == "Need to be done")
    done_count = sum(1 for r in records if r.get("flattening_status") == "Done")

    collection_data["schema_version"] = "2.3.0"
    collection_data["is_offline_seed"] = False
    collection_data["synced_at_utc"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    collection_data["records"] = records
    collection_data["profile"] = {
        "username": collection_data.get("username") or "krunked",
        "owner_name": "Alex Goresch",
        "discogs_url": "https://www.discogs.com/user/krunked/collection",
        "github_repo": "https://github.com/krunked-fpv/discogs_collection",
        "num_collection": len(records),
        "pressing_photos_detected": pressing_photo_count,
        "colored_or_special_variants": colored_count,
        "flattening_need_to_be_done": todo_count,
        "flattening_done": done_count,
        "collection_value": collection_value,
    }
    if flattening_queue:
        collection_data["flattening_queue"] = {
            "protocol": flattening_queue.get("protocol", ""),
            "need_to_be_done_entries": flattening_queue.get("need_to_be_done_entries", []),
            "done_entries": flattening_queue.get("done_entries", []),
        }

    collection_path.write_text(json.dumps(collection_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Update sync_manifest.json
    hash_copy = dict(collection_data)
    hash_copy.pop("synced_at_utc", None)
    digest = hashlib.sha256(json.dumps(hash_copy, sort_keys=True).encode("utf-8")).hexdigest()
    manifest_path = collection_path.parent / "sync_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "username": collection_data["profile"]["username"],
                "record_count": len(records),
                "pressing_photos_detected": pressing_photo_count,
                "colored_or_special_variants": colored_count,
                "flattening_need_to_be_done": todo_count,
                "flattening_done": done_count,
                "collection_value_median": collection_value["median"],
                "collection_value_total_usd": total_est_val,
                "content_sha256": digest,
                "synced_at_utc": collection_data["synced_at_utc"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    injected = inject_into_index_html(html_path, collection_data, overrides_sorted)
    print(
        f"[ok] Pressing Photo Picker complete!\n"
        f"       Records processed:         {len(records)}\n"
        f"       Verified pressing photos:  {pressing_photo_count} / {len(records)} "
        f"({upgraded_pressing_files} pressing.jpg created/updated, {removed_false_pressing_files} false-positive pressing.jpg removed, {newly_detected_overrides} overrides updated)\n"
        f"       Colored / special wax:     {colored_count} / {len(records)} ({(colored_count/len(records)*100 if records else 0):.1f}%)\n"
        f"       Flattening queue:          {todo_count} Need to be done • {done_count} Done\n"
        f"       Collection value:          {collection_value['median']} Discogs Median "
        f"(Min {collection_value['minimum']} • Max {collection_value['maximum']} • Sum {collection_value['formatted_total']})\n"
        f"       Injected into index.html:  {'YES' if injected else 'NO'} ({html_path})"
    )
    return collection_data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect release photos, pick the right pressing photo for every record, and update index.html."
    )
    parser.add_argument("--collection", default=str(REPO_ROOT / "data" / "collection.json"))
    parser.add_argument("--cache", default=str(REPO_ROOT / "data" / "releases_cache.json"))
    parser.add_argument("--overrides", default=str(REPO_ROOT / "data" / "overrides.json"))
    parser.add_argument("--flattening", default=str(REPO_ROOT / "data" / "flattening_queue.json"))
    parser.add_argument("--assets-dir", default=str(REPO_ROOT / "assets" / "releases"))
    parser.add_argument("--inject-html", default=str(REPO_ROOT / "index.html"))
    parser.add_argument(
        "--download-missing",
        action="store_true",
        default=True,
        help="Download any missing release images from Discogs (enabled by default)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run strictly offline using only existing local files in assets/releases/",
    )
    parser.add_argument("--token", default=None)
    args = parser.parse_args()

    clean_token = resolve_discogs_token(cli_token=args.token, repo_root=REPO_ROOT)

    run_pick_pressing_photos(
        collection_path=pathlib.Path(args.collection),
        cache_path=pathlib.Path(args.cache),
        overrides_path=pathlib.Path(args.overrides),
        flattening_path=pathlib.Path(args.flattening),
        assets_releases_dir=pathlib.Path(args.assets_dir),
        html_path=pathlib.Path(args.inject_html),
        download_missing=False if args.offline else args.download_missing,
        token=clean_token,
    )


if __name__ == "__main__":
    main()