#!/usr/bin/env python3
"""Deterministic Discogs Collection Sync & Static Site Builder.

Synchronizes `https://www.discogs.com/user/krunked/collection` via the official
Discogs REST API v2.0 (`https://api.discogs.com`), enriches release metadata and
secondary images using an incremental cache (`data/releases_cache.json`),
downloads release photography into `assets/releases/<release_id>/`, runs
`pick_pressing_photo.py` to select the physical pressing photo for every record,
reconciles the Vinyl Flattening Queue (`data/flattening_queue.json`) and
Collection Value, writes `data/collection.json`, and injects the static payload
into `index.html`.

Can be run from either `C:\\DiscogsCollection\\discogs_collection` or `scripts/`:
    python scripts/sync_discogs.py
    python pick_pressing_photo.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
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
from pick_pressing_photo import (
    VERIFIED_PRICE_FALLBACKS,
    run_pick_pressing_photos,
)

DISCOGS_API_BASE = "https://api.discogs.com"
USER_AGENT = "KrunkedDiscogsVault/2.2 +https://github.com/krunked-fpv/discogs_collection"
DEFAULT_TOKEN = ""


def sanitize_token(raw_token: str | None) -> str:
    """Strips control chars (e.g. \\x16 from Ctrl+V in Windows getpass), quotes, and prefixes."""
    if not raw_token:
        return ""
    cleaned = str(raw_token)
    # Remove ASCII & Unicode control characters (such as \x16 SYN from Ctrl+V in msvcrt.getwch)
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]+", "", cleaned).strip().strip("\"'` ")
    # Strip accidental key=value or header prefixes
    for prefix in ("DISCOGS_TOKEN=", "Discogs token=", "token=", "Bearer "):
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip().strip("\"'` ")
    # Keep only valid ASCII token characters
    cleaned = re.sub(r"[^A-Za-z0-9._\-]", "", cleaned)
    return cleaned


def sanitize_username(raw_username: str | None, default: str = "krunked") -> str:
    """Ensures username has no control characters, quotes, or whitespace."""
    if not raw_username:
        return default
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]+", "", str(raw_username)).strip().strip("\"'` ")
    return cleaned or default


def load_discogs_credentials(
    cli_token: str | None = None,
    cli_username: str | None = None,
    repo_root: pathlib.Path = REPO_ROOT,
) -> tuple[str, str]:
    """Resolves (username, token) from CLI, environment, local .env, or Windows HKCU Registry."""
    raw_user = cli_username or os.environ.get("DISCOGS_USERNAME") or ""
    raw_token = cli_token if cli_token is not None else os.environ.get("DISCOGS_TOKEN", "")

    # Check local .env file if token or username not yet populated
    dotenv_path = repo_root / ".env"
    if dotenv_path.exists():
        try:
            for line in dotenv_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line_s = line.strip()
                if not line_s or line_s.startswith("#") or "=" not in line_s:
                    continue
                k, v = line_s.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k == "DISCOGS_TOKEN" and not sanitize_token(raw_token):
                    raw_token = v
                elif k == "DISCOGS_USERNAME" and not sanitize_username(raw_user, ""):
                    raw_user = v
        except Exception:
            pass

    # Fallback to Windows User Registry (HKCU\Environment) if current PowerShell session is stale
    if os.name == "nt" and not sanitize_token(raw_token):
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ) as key:
                reg_val, _ = winreg.QueryValueEx(key, "DISCOGS_TOKEN")
                if reg_val:
                    raw_token = str(reg_val)
        except Exception:
            pass

    token = sanitize_token(raw_token) or sanitize_token(DEFAULT_TOKEN)
    if raw_token and token != str(raw_token).strip():
        print(
            "[info] Stripped hidden control/formatting characters from DISCOGS_TOKEN.",
            file=sys.stderr,
        )
    username = sanitize_username(raw_user, default="krunked")
    return username, token


class DiscogsClient:
    """Deterministic, rate-limit-aware Discogs REST API v2.0 client with full HTTP error recovery."""

    def __init__(self, token: str | None = None, user_agent: str = USER_AGENT) -> None:
        self.token = sanitize_token(token)
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

        token_candidates = [self.token, ""] if self.token else [""]
        last_error: Exception | None = None

        for use_token in token_candidates:
            headers = {
                "Accept": "application/vnd.discogs.v2.discogs+json",
                "User-Agent": self.user_agent,
            }
            if use_token:
                headers["Authorization"] = f"Discogs token={use_token}"

            for attempt in range(4):
                if self.ratelimit_remaining <= 3:
                    time.sleep(1.5)
                req = urllib.request.Request(url, headers=headers, method="GET")
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        rem = resp.headers.get("X-Discogs-Ratelimit-Remaining")
                        if rem and rem.isdigit():
                            self.ratelimit_remaining = int(rem)
                        raw = resp.read().decode("utf-8", errors="replace")
                        return json.loads(raw)
                except urllib.error.HTTPError as exc:
                    last_error = exc
                    err_body = ""
                    try:
                        err_body = exc.read().decode("utf-8", errors="replace").strip()
                    except Exception:
                        pass

                    # If token caused HTTP 400 (Bad Request), 401 (Unauthorized), or 403 (Forbidden),
                    # disable the rejected token and immediately retry unauthenticated.
                    if exc.code in (400, 401, 403) and use_token:
                        detail = f" ({err_body[:140]})" if err_body else ""
                        print(
                            f"[warn] Discogs rejected authenticated request (HTTP {exc.code}) on {url}{detail}; "
                            "disabling bad token and retrying unauthenticated...",
                            file=sys.stderr,
                        )
                        self.token = ""
                        break

                    if exc.code == 429:
                        wait_s = 15 * (attempt + 1)
                        print(f"[rate-limit] HTTP 429 on {url}; sleeping {wait_s}s...", file=sys.stderr)
                        time.sleep(wait_s)
                        continue

                    if exc.code in (500, 502, 503, 504):
                        wait_s = 5 * (attempt + 1)
                        print(
                            f"[warn] Transient Discogs server error (HTTP {exc.code}) on {url}; "
                            f"retrying in {wait_s}s...",
                            file=sys.stderr,
                        )
                        time.sleep(wait_s)
                        continue

                    detail = f" — {err_body[:200]}" if err_body else ""
                    raise RuntimeError(f"HTTP Error {exc.code}: {exc.reason} on {url}{detail}") from exc
                except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                    last_error = exc
                    wait_s = 4 * (attempt + 1)
                    print(
                        f"[warn] Network error on {url} ({exc}); retrying in {wait_s}s ({attempt + 1}/4)...",
                        file=sys.stderr,
                    )
                    time.sleep(wait_s)
                    continue

        raise RuntimeError(f"Exhausted retries fetching {url} (last error: {last_error})")

    def download_bytes(self, url: str) -> bytes | None:
        if not url:
            return None
        for use_token in ([self.token, ""] if self.token else [""]):
            headers = {"User-Agent": self.user_agent}
            if use_token:
                headers["Authorization"] = f"Discogs token={use_token}"
            try:
                req = urllib.request.Request(url, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=25) as resp:
                    return resp.read()
            except urllib.error.HTTPError as exc:
                if exc.code in (400, 401, 403) and use_token:
                    self.token = ""
                    continue
                print(f"[warn] Could not download image {url}: {exc}", file=sys.stderr)
                return None
            except Exception as exc:
                print(f"[warn] Could not download image {url}: {exc}", file=sys.stderr)
                return None
        return None


def fetch_full_collection(
    client: DiscogsClient,
    username: str,
    cache_path: pathlib.Path,
    overrides_path: pathlib.Path,
    flattening_path: pathlib.Path,
    download_dir: pathlib.Path,
    analyze_pixels: bool = True,
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

    flattening_queue: dict[str, Any] = {}
    if flattening_path.exists():
        try:
            flattening_queue = json.loads(flattening_path.read_text(encoding="utf-8"))
        except Exception:
            flattening_queue = {}

    safe_user = urllib.parse.quote(username.strip(), safe="")
    profile: dict[str, Any] = {}
    try:
        profile = client.get_json(f"/users/{safe_user}")
    except Exception as exc:
        print(f"[warn] Could not fetch user profile for '{username}' ({exc}); continuing with collection sync...", file=sys.stderr)
        profile = {}

    collection_value: dict[str, Any] = {}
    if client.token:
        try:
            collection_value = client.get_json(f"/users/{safe_user}/collection/value")
        except Exception as exc:
            print(f"[warn] Could not fetch collection value endpoint ({exc}); using calculated fallback.", file=sys.stderr)
            collection_value = {}

    raw_items: list[dict[str, Any]] = []
    page = 1
    while True:
        try:
            payload = client.get_json(
                f"/users/{safe_user}/collection/folders/0/releases",
                params={"per_page": 100, "page": page, "sort": "added", "sort_order": "desc"},
            )
        except Exception as exc:
            print(f"[error] Failed fetching collection page {page} for '{username}': {exc}", file=sys.stderr)
            break
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

        cached_entry = cache.get(rid_str)
        if not isinstance(cached_entry, dict) or not cached_entry.get("images"):
            try:
                rel_detail = client.get_json(f"/releases/{release_id}", params={"curr_abbr": "USD"})
                if isinstance(rel_detail, dict) and rel_detail.get("id"):
                    cache[rid_str] = rel_detail
                time.sleep(0.55)
            except Exception as exc:
                print(f"[warn] Could not enrich release {release_id}: {exc}", file=sys.stderr)

        rel_detail = cache.get(rid_str) or {}
        images = list(rel_detail.get("images") or [])
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

        rel_asset_dir = download_dir / rid_str
        rel_asset_dir.mkdir(parents=True, exist_ok=True)
        downloaded_bytes: dict[str, bytes] = {}

        for idx, img in enumerate(images[:40]):
            uri = img.get("uri") or img.get("resource_url") or ""
            img_file = rel_asset_dir / f"img_{idx}.jpg"
            if img_file.exists():
                try:
                    b = img_file.read_bytes()
                    if uri:
                        downloaded_bytes[uri] = b
                    downloaded_bytes[f"idx:{idx}"] = b
                except Exception:
                    pass
            elif analyze_pixels and uri:
                raw_b = client.download_bytes(uri)
                if raw_b:
                    img_file.write_bytes(raw_b)
                    downloaded_bytes[uri] = raw_b
                    downloaded_bytes[f"idx:{idx}"] = raw_b

        if (rel_asset_dir / "img_0.jpg").exists() and not (rel_asset_dir / "cover.jpg").exists():
            shutil.copyfile(rel_asset_dir / "img_0.jpg", rel_asset_dir / "cover.jpg")

        img_selection = select_release_images_deterministic(
            images=images,
            formats=formats,
            notes=f"{notes_str} {user_comments}",
            release_id=release_id,
            overrides=overrides,
            downloaded_bytes_by_uri=downloaded_bytes,
            local_release_dir=rel_asset_dir,
        )

        # Immediately write pressing.jpg during sync when a pressing photo is selected
        if img_selection.get("has_pressing_photo"):
            raw_sel = img_selection.get("selected_index")
            sel_idx = int(raw_sel) if raw_sel is not None else -1
            if sel_idx >= 0 and (rel_asset_dir / f"img_{sel_idx}.jpg").exists():
                src_local = rel_asset_dir / f"img_{sel_idx}.jpg"
                dest_pressing = rel_asset_dir / "pressing.jpg"
                src_bytes = src_local.read_bytes()
                if not dest_pressing.exists() or dest_pressing.read_bytes() != src_bytes:
                    dest_pressing.write_bytes(src_bytes)
                img_selection["local_pressing_image_url"] = f"assets/releases/{rid_str}/pressing.jpg"
                img_selection["display_thumbnail_url"] = img_selection["local_pressing_image_url"]

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
        title_str = str(basic.get("title") or rel_detail.get("title") or "")
        discogs_uri = str(rel_detail.get("uri") or f"https://www.discogs.com/release/{release_id}")

        lowest_price = rel_detail.get("lowest_price")
        if isinstance(lowest_price, (int, float)) and float(lowest_price) > 0:
            est_val = round(float(lowest_price), 2)
        elif release_id in VERIFIED_PRICE_FALLBACKS:
            est_val = VERIFIED_PRICE_FALLBACKS[release_id]
        else:
            est_val = 35.0

        flatten_status = resolve_flattening_status(
            artist=artist_name,
            title=title_str,
            release_id=release_id,
            queue_data=flattening_queue,
        )

        compiled_records.append({
            "release_id": release_id,
            "instance_id": item.get("instance_id") or release_id,
            "artist": artist_name,
            "title": title_str,
            "year": int(basic.get("year") or rel_detail.get("year") or 0),
            "format_string": format_str,
            "label": label_name,
            "catno": catno,
            "media_condition": media_cond,
            "sleeve_condition": sleeve_cond,
            "comments": user_comments,
            "date_added": str(item.get("date_added") or ""),
            "discogs_url": discogs_uri,
            "estimated_value_usd": est_val,
            "flattening_status": flatten_status,
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
    total_est = round(sum(float(r["estimated_value_usd"]) for r in compiled_records), 2)

    val_obj = {
        "minimum": collection_value.get("minimum") or f"${round(total_est * 0.52, 2):,.2f}",
        "median": collection_value.get("median") or f"${round(total_est * 0.83, 2):,.2f}",
        "maximum": collection_value.get("maximum") or f"${round(total_est * 1.44, 2):,.2f}",
        "total_estimated_usd": total_est,
        "formatted_total": f"${total_est:,.2f}",
    }

    return {
        "schema_version": "2.2.0",
        "is_offline_seed": False,
        "source_of_truth": f"https://www.discogs.com/user/{username}/collection",
        "api_documentation": "https://www.discogs.com/developers",
        "username": username,
        "synced_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profile": {
            "username": username,
            "owner_name": "Alex Goresch",
            "discogs_url": f"https://www.discogs.com/user/{username}/collection",
            "github_repo": "https://github.com/krunked-fpv/discogs_collection",
            "num_collection": int(profile.get("num_collection") or len(compiled_records)),
            "pressing_photos_detected": pressing_photo_count,
            "colored_or_special_variants": colored_count,
            "collection_value": val_obj,
        },
        "records": compiled_records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic Discogs Collection Sync & Pressing Photo Compiler")
    parser.add_argument("--username", default=None)
    parser.add_argument("--token", default=None)
    parser.add_argument("--output", default=str(REPO_ROOT / "data" / "collection.json"))
    parser.add_argument("--cache", default=str(REPO_ROOT / "data" / "releases_cache.json"))
    parser.add_argument("--overrides", default=str(REPO_ROOT / "data" / "overrides.json"))
    parser.add_argument("--flattening", default=str(REPO_ROOT / "data" / "flattening_queue.json"))
    parser.add_argument("--assets-dir", default=str(REPO_ROOT / "assets" / "releases"))
    parser.add_argument("--inject-html", default=str(REPO_ROOT / "index.html"))
    parser.add_argument("--analyze-pixels", action="store_true", default=True)
    parser.add_argument("--download-images", action="store_true", default=True)
    args = parser.parse_args()

    username, token = load_discogs_credentials(
        cli_token=args.token,
        cli_username=args.username,
        repo_root=REPO_ROOT,
    )

    out_path = pathlib.Path(args.output)
    cache_path = pathlib.Path(args.cache)
    overrides_path = pathlib.Path(args.overrides)
    flattening_path = pathlib.Path(args.flattening)
    download_dir = pathlib.Path(args.assets_dir)
    html_path = pathlib.Path(args.inject_html)

    client = DiscogsClient(token=token)
    data = fetch_full_collection(
        client=client,
        username=username,
        cache_path=cache_path,
        overrides_path=overrides_path,
        flattening_path=flattening_path,
        download_dir=download_dir,
        analyze_pixels=args.analyze_pixels,
    )

    if data.get("records"):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    elif not out_path.exists():
        raise RuntimeError(
            "Discogs API returned 0 records and no local data/collection.json exists to fall back on."
        )
    else:
        print(
            f"[warn] Discogs API returned 0 records; preserving existing {out_path} and running local photo picker...",
            file=sys.stderr,
        )

    run_pick_pressing_photos(
        collection_path=out_path,
        cache_path=cache_path,
        overrides_path=overrides_path,
        flattening_path=flattening_path,
        assets_releases_dir=download_dir,
        html_path=html_path,
        download_missing=args.download_images,
        token=client.token,
    )


if __name__ == "__main__":
    main()