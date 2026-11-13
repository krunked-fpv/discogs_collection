#!/usr/bin/env python3
"""Deterministic Discogs Collection Sync & Static Site Builder (`sync_discogs.py`).

Synchronizes `https://www.discogs.com/user/krunked/collection` via the official
Discogs REST API v2.0 (`https://api.discogs.com`) using the v2.4 Incremental
Delta Engine:
- Compares incoming Discogs collection items against the local baseline in
  `data/collection.json`, `data/releases_cache.json`, `data/overrides.json`,
  and `assets/releases/<release_id>/`.
- Fast-paths `UNCHANGED` releases in microseconds without redundant API calls,
  image downloads, or 4-pass NumPy CV passes.
- Executes full metadata enrichment, concurrent image downloading, and the
  4-pass Concentric Dual-Circle CV pressing picker ONLY on `NEW` or `RESYNCED`
  releases (or all releases when `--full` is passed).
- Reconciles the Vinyl Flattening Queue (`data/flattening_queue.json`) and
  Collection Value, writes `data/collection.json`, updates `index.html`, and
  prints a comprehensive Delta Sync Report & Changelog.

Can be run from either `C:\\DiscogsCollection\\discogs_collection` or `scripts/`:
    python scripts/sync_discogs.py
    python scripts/sync_discogs.py --full
    python scripts/sync_discogs.py --resync 35668090,16610055
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
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
    VaultTerminalUI,
    compute_release_delta_signature,
    evaluate_release_delta_status,
    parse_wax_variant,
    resolve_flattening_status,
    select_release_images_deterministic,
)
from pick_pressing_photo import (
    VERIFIED_PRICE_FALLBACKS,
    run_pick_pressing_photos,
)

DISCOGS_API_BASE = "https://api.discogs.com"
USER_AGENT = "KrunkedDiscogsVault/2.4 +https://github.com/krunked-fpv/discogs_collection"
DEFAULT_TOKEN = ""


def sanitize_token(raw_token: str | None) -> str:
    """Strips control chars (e.g. \\x16 from Ctrl+V in Windows getpass), quotes, and prefixes."""
    if not raw_token:
        return ""
    cleaned = str(raw_token)
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]+", "", cleaned).strip().strip("\"'` ")
    for prefix in ("DISCOGS_TOKEN=", "Discogs token=", "token=", "Bearer "):
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip().strip("\"'` ")
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
    ui: VaultTerminalUI | None = None,
) -> tuple[str, str]:
    """Resolves (username, token) from CLI, environment, local .env, or Windows HKCU Registry."""
    raw_user = cli_username or os.environ.get("DISCOGS_USERNAME") or ""
    raw_token = cli_token if cli_token is not None else os.environ.get("DISCOGS_TOKEN", "")

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
        msg = "Stripped hidden control/formatting characters from DISCOGS_TOKEN."
        if ui:
            ui.log("info", msg, stream=sys.stderr)
        else:
            print(f"[info] {msg}", file=sys.stderr)
    username = sanitize_username(raw_user, default="krunked")
    return username, token


class DiscogsClient:
    """Deterministic, rate-limit-aware Discogs REST API v2.0 client with full HTTP error recovery."""

    def __init__(
        self,
        token: str | None = None,
        user_agent: str = USER_AGENT,
        ui: VaultTerminalUI | None = None,
    ) -> None:
        self.token = sanitize_token(token)
        self.user_agent = user_agent
        self.ratelimit_remaining = 60
        self.ui = ui

    def _log(self, tag: str, msg: str, stream: Any = sys.stderr) -> None:
        if self.ui:
            self.ui.log(tag, msg, stream=stream)
        else:
            print(f"[{tag}] {msg}", file=stream)

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
                            if self.ui:
                                self.ui.update_throbber(api_remaining=self.ratelimit_remaining)
                        raw = resp.read().decode("utf-8", errors="replace")
                        return json.loads(raw)
                except urllib.error.HTTPError as exc:
                    last_error = exc
                    err_body = ""
                    try:
                        err_body = exc.read().decode("utf-8", errors="replace").strip()
                    except Exception:
                        pass

                    if exc.code in (400, 401, 403) and use_token:
                        detail = f" ({err_body[:140]})" if err_body else ""
                        self._log(
                            "warn",
                            f"Discogs rejected authenticated request (HTTP {exc.code}) on {url}{detail}; "
                            "disabling bad token and retrying unauthenticated...",
                        )
                        self.token = ""
                        break

                    if exc.code == 429:
                        wait_s = 15 * (attempt + 1)
                        self._log("rate-limit", f"HTTP 429 on {url}; sleeping {wait_s}s...")
                        time.sleep(wait_s)
                        continue

                    if exc.code in (500, 502, 503, 504):
                        wait_s = 5 * (attempt + 1)
                        self._log(
                            "warn",
                            f"Transient Discogs server error (HTTP {exc.code}) on {url}; retrying in {wait_s}s...",
                        )
                        time.sleep(wait_s)
                        continue

                    detail = f" — {err_body[:200]}" if err_body else ""
                    raise RuntimeError(f"HTTP Error {exc.code}: {exc.reason} on {url}{detail}") from exc
                except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                    last_error = exc
                    wait_s = 4 * (attempt + 1)
                    self._log(
                        "warn",
                        f"Network error on {url} ({exc}); retrying in {wait_s}s ({attempt + 1}/4)...",
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
                self._log("warn", f"Could not download image {url}: {exc}")
                return None
            except Exception as exc:
                self._log("warn", f"Could not download image {url}: {exc}")
                return None
        return None


def _parse_resync_arg(raw_arg: str | None) -> set[int]:
    if not raw_arg:
        return set()
    out: set[int] = set()
    for part in re.split(r"[,;\s]+", str(raw_arg).strip()):
        if part.isdigit() and int(part) > 0:
            out.add(int(part))
    return out


def fetch_full_collection(
    client: DiscogsClient,
    username: str,
    cache_path: pathlib.Path,
    overrides_path: pathlib.Path,
    flattening_path: pathlib.Path,
    download_dir: pathlib.Path,
    analyze_pixels: bool = True,
    existing_collection_path: pathlib.Path | None = None,
    force_full: bool = False,
    force_rids: set[int] | None = None,
    ui: VaultTerminalUI | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fetches Folder 0 ('All') and enriches releases using the v2.4 Delta Fast-Path Engine."""
    force_rids = force_rids or set()

    # Load previous collection baseline for delta detection
    pre_sync_records_by_id: dict[int, dict[str, Any]] = {}
    if existing_collection_path and existing_collection_path.exists():
        try:
            prev_col = json.loads(existing_collection_path.read_text(encoding="utf-8"))
            for r in prev_col.get("records") or []:
                rid_val = int(r.get("release_id") or 0)
                if rid_val > 0:
                    pre_sync_records_by_id[rid_val] = r
        except Exception:
            pre_sync_records_by_id = {}

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

    if ui:
        ui.log(
            "info",
            f"Loaded local vault baseline: {len(pre_sync_records_by_id)} indexed LPs, "
            f"{len(cache)} cached releases, {len(overrides)} overrides.",
        )
        ui.update_throbber(phase=f"Fetching @{username} profile & valuation...")

    safe_user = urllib.parse.quote(username.strip(), safe="")
    profile: dict[str, Any] = {}
    try:
        profile = client.get_json(f"/users/{safe_user}")
    except Exception as exc:
        client._log("warn", f"Could not fetch user profile for '{username}' ({exc}); continuing with collection sync...")
        profile = {}

    collection_value: dict[str, Any] = {}
    if client.token:
        try:
            collection_value = client.get_json(f"/users/{safe_user}/collection/value")
            if ui and collection_value.get("median"):
                ui.log(
                    "api",
                    f"Discogs Valuation synced: Median {collection_value.get('median')} "
                    f"(Min {collection_value.get('minimum')} • Max {collection_value.get('maximum')})",
                )
        except Exception as exc:
            client._log("warn", f"Could not fetch collection value endpoint ({exc}); using calculated fallback.")
            collection_value = {}

    raw_items: list[dict[str, Any]] = []
    page = 1
    while True:
        if ui:
            ui.update_throbber(phase=f"Fetching Discogs Folder 0 (Page {page})...")
        try:
            payload = client.get_json(
                f"/users/{safe_user}/collection/folders/0/releases",
                params={"per_page": 100, "page": page, "sort": "added", "sort_order": "desc"},
            )
        except Exception as exc:
            client._log("error", f"Failed fetching collection page {page} for '{username}': {exc}")
            break
        releases_page = payload.get("releases") or []
        raw_items.extend(releases_page)
        pagination = payload.get("pagination") or {}
        total_pages = int(pagination.get("pages") or 1)
        if ui:
            ui.log("api", f"Fetched Folder 0 page {page}/{total_pages} ({len(releases_page)} releases)")
        if page >= total_pages:
            break
        page += 1

    # Deduplicate raw_items by release_id (preserving most recent instance) while tracking all seen release_ids
    seen_api_rids: set[int] = set()
    deduped_items: list[dict[str, Any]] = []
    for item in raw_items:
        basic = item.get("basic_information") or {}
        rid = int(basic.get("id") or item.get("id") or 0)
        if rid > 0 and rid not in seen_api_rids:
            seen_api_rids.add(rid)
            deduped_items.append(item)

    removed_records: list[dict[str, Any]] = [
        r for rid, r in pre_sync_records_by_id.items()
        if rid not in seen_api_rids and not (download_dir / str(rid)).exists()
    ]

    compiled_records: list[dict[str, Any]] = []
    evaluated_rids: set[int] = set()
    new_records: list[dict[str, Any]] = []
    resynced_records: list[dict[str, Any]] = []
    unchanged_count = 0
    upgraded_pressing_files = 0
    removed_false_pressing_files = 0
    cache_dirty = False

    total_items = len(deduped_items)
    if ui:
        ui.update_throbber(phase="Running Delta Analysis...", total=total_items, done=0)

    for idx_item, item in enumerate(deduped_items, start=1):
        basic = item.get("basic_information") or {}
        release_id = int(basic.get("id") or item.get("id") or 0)
        rid_str = str(release_id)
        existing_rec = pre_sync_records_by_id.get(release_id)

        cached_entry = cache.get(rid_str)
        cached_imgs = (cached_entry.get("images") or []) if isinstance(cached_entry, dict) else []
        needs_enrich = (
            not isinstance(cached_entry, dict)
            or not cached_imgs
            or any(not (im.get("uri") or im.get("resource_url")) for im in cached_imgs)
        )
        cache_was_enriched = False
        if needs_enrich:
            if ui:
                ui.log("api", f"Enriching release metadata from Discogs API for #{release_id}...")
                ui.update_throbber(current_item=f"🌐 API Enrich #{release_id}")
            try:
                rel_detail_fetched = client.get_json(f"/releases/{release_id}", params={"curr_abbr": "USD"})
                if isinstance(rel_detail_fetched, dict) and rel_detail_fetched.get("id"):
                    rel_detail_fetched["_full_images_fetched"] = True
                    cache[rid_str] = rel_detail_fetched
                    cache_dirty = True
                    cache_was_enriched = True
                time.sleep(0.45)
            except Exception as exc:
                client._log("warn", f"Could not enrich release {release_id}: {exc}")

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

        rel_asset_dir = download_dir / rid_str
        rel_asset_dir.mkdir(parents=True, exist_ok=True)
        combined_notes = f"{notes_str}\n{user_comments}"

        # Evaluate Delta Status
        delta_status, delta_reason, current_sig = evaluate_release_delta_status(
            release_id=release_id,
            existing_record=existing_rec,
            rel_dir=rel_asset_dir,
            cached_images=images,
            overrides=overrides,
            format_str=format_str,
            notes=combined_notes,
            force_full=force_full,
            force_rids=force_rids,
        )
        if delta_status == "unchanged" and cache_was_enriched:
            delta_status = "resynced"
            delta_reason = "release cache newly enriched from Discogs API"

        if delta_status == "unchanged":
            # FAST-PATH: Reuse verified image selection & CV classification without reading JPEGs or running NumPy CV
            unchanged_count += 1
            img_selection = dict((existing_rec or {}).get("images") or {})
            img_selection["delta_sig"] = current_sig
            if ui:
                ui.update_throbber(
                    done=idx_item,
                    total=total_items,
                    new_count=len(new_records),
                    resync_count=len(resynced_records),
                    cached_count=unchanged_count,
                    current_item=f"⚡ Cached #{rid_str} ({artist_name})",
                )
        else:
            # ACTIVE SUITE: Run full image download + 4-Pass Concentric Dual-Circle CV
            if ui:
                tag = "new" if delta_status == "new" else "resync"
                ui.log(tag, f"#{rid_str} {artist_name} — {title_str} [{delta_reason}]")
                ui.update_throbber(
                    done=idx_item,
                    total=total_items,
                    new_count=len(new_records),
                    resync_count=len(resynced_records),
                    cached_count=unchanged_count,
                    current_item=f"🔍 Full Suite #{rid_str} {artist_name}...",
                )

            downloaded_bytes: dict[str, bytes] = {}
            missing_downloads: list[tuple[int, str, pathlib.Path]] = []

            for idx_img, img in enumerate(images[:40]):
                uri = img.get("uri") or img.get("resource_url") or ""
                img_file = rel_asset_dir / f"img_{idx_img}.jpg"
                if img_file.exists():
                    try:
                        b = img_file.read_bytes()
                        if uri:
                            downloaded_bytes[uri] = b
                        downloaded_bytes[f"idx:{idx_img}"] = b
                    except Exception:
                        pass
                elif analyze_pixels and uri:
                    missing_downloads.append((idx_img, uri, img_file))

            if missing_downloads:
                if ui:
                    ui.log("api", f"Downloading {len(missing_downloads)} release image(s) for #{rid_str}...")

                def _dl_one(t_arg: tuple[int, str, pathlib.Path]) -> tuple[int, str, pathlib.Path, bytes | None]:
                    i_idx, u_str, p_file = t_arg
                    return (i_idx, u_str, p_file, client.download_bytes(u_str))

                with ThreadPoolExecutor(max_workers=4) as pool:
                    for i_idx, u_str, p_file, raw_b in pool.map(_dl_one, missing_downloads):
                        if raw_b:
                            p_file.write_bytes(raw_b)
                            downloaded_bytes[u_str] = raw_b
                            downloaded_bytes[f"idx:{i_idx}"] = raw_b

            if (rel_asset_dir / "img_0.jpg").exists() and not (rel_asset_dir / "cover.jpg").exists():
                shutil.copyfile(rel_asset_dir / "img_0.jpg", rel_asset_dir / "cover.jpg")

            img_selection = select_release_images_deterministic(
                images=images,
                formats=formats,
                notes=combined_notes,
                release_id=release_id,
                overrides=overrides,
                downloaded_bytes_by_uri=downloaded_bytes,
                local_release_dir=rel_asset_dir,
            )

            dest_pressing = rel_asset_dir / "pressing.jpg"
            action_desc = ""
            if img_selection.get("has_pressing_photo"):
                raw_sel = img_selection.get("selected_index")
                sel_idx = int(raw_sel) if raw_sel is not None else -1
                sc_val = float(img_selection.get("selected_score") or 0.0)
                if sel_idx >= 0 and (rel_asset_dir / f"img_{sel_idx}.jpg").exists():
                    src_local = rel_asset_dir / f"img_{sel_idx}.jpg"
                    src_bytes = src_local.read_bytes()
                    img_hash = hashlib.sha256(src_bytes).hexdigest()[:8]
                    if not dest_pressing.exists() or dest_pressing.read_bytes() != src_bytes:
                        try:
                            if dest_pressing.exists():
                                dest_pressing.unlink()
                        except Exception:
                            pass
                        dest_pressing.write_bytes(src_bytes)
                        upgraded_pressing_files += 1
                        action_desc = f"pressing.jpg -> img_{sel_idx}.jpg (CV {sc_val:.3f})"
                        if ui:
                            ui.log("cv-pick", f"#{rid_str} {artist_name} — {title_str}: {action_desc}")
                    else:
                        action_desc = f"verified img_{sel_idx}.jpg (CV {sc_val:.3f})"
                    cache_busted_url = f"assets/releases/{rid_str}/pressing.jpg?v={sel_idx}_{img_hash}"
                    prev_p_url = str(img_selection.get("pressing_image_url") or "")
                    if prev_p_url.startswith("http"):
                        img_selection["remote_pressing_image_url"] = prev_p_url
                    img_selection["local_pressing_image_url"] = cache_busted_url
                    img_selection["display_thumbnail_url"] = cache_busted_url
                    img_selection["pressing_image_url"] = cache_busted_url
            else:
                if dest_pressing.exists():
                    try:
                        dest_pressing.unlink()
                        removed_false_pressing_files += 1
                        action_desc = "removed non-pressing pressing.jpg -> procedural seed"
                        if ui:
                            ui.log("cleaned", f"#{rid_str} {artist_name} — {title_str}: {action_desc}")
                    except Exception:
                        pass
                else:
                    action_desc = "procedural wax seed"
                    if ui:
                        ui.log("wax-seed", f"#{rid_str} {artist_name} — {title_str}: using procedural wax seed")
                img_selection["pressing_image_url"] = ""
                img_selection.pop("local_pressing_image_url", None)

            img_selection["delta_sig"] = compute_release_delta_signature(
                release_id=release_id,
                rel_dir=rel_asset_dir,
                format_str=format_str,
                notes=combined_notes,
                override_val=overrides.get(rid_str),
            )

        wax_spec = parse_wax_variant(format_str, comments=combined_notes, release_id=release_id)

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

        record_obj = {
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
        }
        compiled_records.append(record_obj)
        evaluated_rids.add(release_id)

        if delta_status == "new":
            new_records.append(record_obj)
        elif delta_status == "resynced":
            resynced_records.append({
                "record": record_obj,
                "reason": delta_reason,
                "action": action_desc,
            })

    if cache_dirty or not cache_path.exists():
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

    collection_payload = {
        "schema_version": "2.4.0",
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

    delta_summary = {
        "evaluated_rids": evaluated_rids,
        "new_records": new_records,
        "resynced_records": resynced_records,
        "removed_records": removed_records,
        "unchanged_count": unchanged_count,
        "upgraded_pressing_files": upgraded_pressing_files,
        "removed_false_pressing_files": removed_false_pressing_files,
    }
    return collection_payload, delta_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic Discogs Collection Delta Sync & Pressing Photo Compiler")
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
    parser.add_argument(
        "--full",
        "-f",
        action="store_true",
        help="Force full CV re-evaluation on every release (bypassing delta fast-path)",
    )
    parser.add_argument(
        "--resync",
        default=None,
        help="Comma-separated list of specific release_ids to force re-evaluate (e.g. 35668090,16610055)",
    )
    args = parser.parse_args()

    force_rids = _parse_resync_arg(args.resync)
    mode_str = "FULL REBUILD (--full)" if args.full else (
        f"TARGETED RESYNC ({sorted(force_rids)})" if force_rids else "INCREMENTAL DELTA SYNC"
    )
    ui = VaultTerminalUI(
        title="KRUNKED // VINYL VAULT",
        subtitle="DISCOGS DELTA SYNC ENGINE v2.4",
    )
    ui.print_banner(mode_label=mode_str)
    ui.start_throbber(phase="Resolving credentials...")

    username, token = load_discogs_credentials(
        cli_token=args.token,
        cli_username=args.username,
        repo_root=REPO_ROOT,
        ui=ui,
    )
    masked_tok = f"{token[:4]}••••{token[-4:]}" if len(token) >= 8 else ("set" if token else "unauthenticated")
    ui.log("auth", f"Authenticated as @{username} (Token: {masked_tok})")

    out_path = pathlib.Path(args.output)
    cache_path = pathlib.Path(args.cache)
    overrides_path = pathlib.Path(args.overrides)
    flattening_path = pathlib.Path(args.flattening)
    download_dir = pathlib.Path(args.assets_dir)
    html_path = pathlib.Path(args.inject_html)

    client = DiscogsClient(token=token, ui=ui)
    data, delta_summary = fetch_full_collection(
        client=client,
        username=username,
        cache_path=cache_path,
        overrides_path=overrides_path,
        flattening_path=flattening_path,
        download_dir=download_dir,
        analyze_pixels=args.analyze_pixels,
        existing_collection_path=out_path,
        force_full=args.full,
        force_rids=force_rids,
        ui=ui,
    )

    if data.get("records"):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        pre_sync_arg: dict[str, Any] | None = delta_summary
    elif not out_path.exists():
        ui.stop_throbber()
        raise RuntimeError(
            "Discogs API returned 0 records and no local data/collection.json exists to fall back on."
        )
    else:
        ui.log(
            "warn",
            f"Discogs API returned 0 records; preserving existing {out_path} and running local delta picker...",
            stream=sys.stderr,
        )
        pre_sync_arg = None

    run_pick_pressing_photos(
        collection_path=out_path,
        cache_path=cache_path,
        overrides_path=overrides_path,
        flattening_path=flattening_path,
        assets_releases_dir=download_dir,
        html_path=html_path,
        download_missing=args.download_images,
        token=client.token,
        force_full=args.full,
        force_rids=force_rids,
        pre_sync_delta=pre_sync_arg,
        ui=ui,
    )


if __name__ == "__main__":
    main()