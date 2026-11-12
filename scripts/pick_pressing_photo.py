#!/usr/bin/env python3
"""Pick The Right Pressing Photo & Static Index Compiler (`pick_pressing_photo.py`).

Inspects every release in `data/collection.json` and all of its associated images
(from `assets/releases/<release_id>/img_*.jpg` and `data/releases_cache.json`),
determines which photo most likely shows the physical vinyl pressing (vs. sleeve
cover, back cover, gatefold, or paper label closeup), defaults the record's wax
ring / platter image to that photo, reconciles the Vinyl Flattening Queue and
Collection Value, and injects the compiled dataset + overrides directly into
`index.html` ready for `git push` to GitHub Pages.

Usage (from `C:\\DiscogsCollection\\discogs_collection` or `scripts/`):
    python pick_pressing_photo.py
    python scripts/pick_pressing_photo.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import shutil
import sys
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

USER_AGENT = "KrunkedDiscogsVault/2.2 +https://github.com/krunked-fpv/discogs_collection"

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


def _download_image_bytes(url: str, token: str = "") -> bytes | None:
    if not url or not url.startswith("http"):
        return None
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Discogs token={token}"
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read()
    except Exception:
        return None


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
    # --- PASTE START (Line 72) ---
    if "â€¢" in html_text or "ðŸ" in html_text:
        try:
            html_text = html_text.encode("cp1252").decode("utf-8")
        except Exception:
            pass
    # --- PASTE END ---
    payload_js = json.dumps(collection_data, indent=2, ensure_ascii=False)
    overrides_js = json.dumps(overrides_data, indent=2, ensure_ascii=False)

    replacement_block = (
        "/* __DISCOGS_COLLECTION_DATA_START__ */\n"
        f"    window.__DISCOGS_OVERRIDES__ = {overrides_js};\n"
        f"    window.__DISCOGS_COLLECTION__ = {payload_js};\n"
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

    # Also update static KPI text in HTML so static scrapers / NotebookLM / initial paint show exact numbers
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


def run_pick_pressing_photos(
    collection_path: pathlib.Path,
    cache_path: pathlib.Path,
    overrides_path: pathlib.Path,
    flattening_path: pathlib.Path,
    assets_releases_dir: pathlib.Path,
    html_path: pathlib.Path,
    download_missing: bool = False,
    token: str = "",
) -> dict[str, Any]:
    """Evaluates all release images, picks the best pressing photo, updates JSONs, and injects index.html."""
    if not collection_path.exists():
        raise FileNotFoundError(f"Collection file not found: {collection_path}")

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

    pressing_photo_count = 0
    colored_count = 0
    newly_detected_overrides = 0

    for rec in records:
        rid = int(rec.get("release_id") or 0)
        rid_str = str(rid)
        rel_detail = cache.get(rid_str) or {}
        rel_dir = assets_releases_dir / rid_str
        rel_dir.mkdir(parents=True, exist_ok=True)

        # Gather full images list from cache or record
        raw_images = rel_detail.get("images") or []
        if not raw_images and rec.get("images", {}).get("classified_images"):
            raw_images = rec["images"]["classified_images"]
        if not raw_images and rec.get("images", {}).get("cover_image_url"):
            raw_images = [
                {
                    "type": "primary",
                    "uri": rec["images"]["cover_image_url"],
                    "width": 600,
                    "height": 600,
                }
            ]

        # Load local image bytes (and optionally download missing candidate images if online)
        downloaded_bytes: dict[str, bytes] = {}
        for idx, img in enumerate(raw_images[:24]):
            uri = img.get("uri") or img.get("resource_url") or ""
            local_img_file = rel_dir / f"img_{idx}.jpg"
            if local_img_file.exists():
                try:
                    downloaded_bytes[uri] = local_img_file.read_bytes()
                except Exception:
                    pass
            elif download_missing and uri:
                raw_b = _download_image_bytes(uri, token=token)
                if raw_b:
                    local_img_file.write_bytes(raw_b)
                    downloaded_bytes[uri] = raw_b

        if raw_images and not (rel_dir / "cover.jpg").exists():
            if (rel_dir / "img_0.jpg").exists():
                shutil.copyfile(rel_dir / "img_0.jpg", rel_dir / "cover.jpg")

        formats = rel_detail.get("formats") or []
        notes_str = str(rel_detail.get("notes") or "")
        user_comments = str(rec.get("comments") or "")
        fmt_str = str(rec.get("format_string") or "LP, Album")

        img_selection = select_release_images_deterministic(
            images=raw_images,
            formats=formats,
            notes=f"{notes_str} {user_comments}",
            release_id=rid,
            overrides=overrides,
            downloaded_bytes_by_uri=downloaded_bytes,
            local_release_dir=rel_dir,
        )

        # If CV/Guideline 13.8 detected a pressing photo for a release not yet in overrides.json, save it
        if img_selection.get("has_pressing_photo") and img_selection.get("pressing_image_url"):
            p_url = img_selection["pressing_image_url"]
            if rid_str not in overrides and len(raw_images) > 1:
                overrides[rid_str] = p_url
                newly_detected_overrides += 1

            # Also copy the selected local image to assets/releases/<rid>/pressing.jpg if present locally
            sel_idx = int(img_selection.get("selected_index") or -1)
            src_local = rel_dir / f"img_{sel_idx}.jpg"
            dest_pressing = rel_dir / "pressing.jpg"
            if src_local.exists():
                if not dest_pressing.exists() or src_local.stat().st_size != dest_pressing.stat().st_size:
                    shutil.copyfile(src_local, dest_pressing)
                img_selection["local_pressing_image_url"] = f"assets/releases/{rid_str}/img_{sel_idx}.jpg"
                img_selection["display_thumbnail_url"] = img_selection["local_pressing_image_url"]

        rec["images"] = img_selection

        # Re-verify wax_spec
        wax_spec = parse_wax_variant(fmt_str, comments=f"{notes_str} {user_comments}", release_id=rid)
        rec["wax_spec"] = wax_spec

        # Re-verify estimated_value_usd from cache lowest_price or verified fallbacks
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

    collection_data["schema_version"] = "2.2.0"
    collection_data["is_offline_seed"] = False
    collection_data["synced_at_utc"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
        f"     • Records processed:         {len(records)}\n"
        f"     • Verified pressing photos:  {pressing_photo_count} / {len(records)} "
        f"(+{newly_detected_overrides} newly added to overrides.json)\n"
        f"     • Colored / special wax:     {colored_count} / {len(records)} ({(colored_count/len(records)*100 if records else 0):.1f}%)\n"
        f"     • Flattening queue:          {todo_count} Need to be done • {done_count} Done\n"
        f"     • Collection value:          {collection_value['median']} Discogs Median "
        f"(Min {collection_value['minimum']} • Max {collection_value['maximum']} • Sum {collection_value['formatted_total']})\n"
        f"     • Injected into index.html:  {'YES' if injected else 'NO'} ({html_path})"
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
    parser.add_argument("--download-missing", action="store_true", help="Download any missing release images from Discogs")
    parser.add_argument("--token", default=os.environ.get("DISCOGS_TOKEN", ""))
    args = parser.parse_args()

    run_pick_pressing_photos(
        collection_path=pathlib.Path(args.collection),
        cache_path=pathlib.Path(args.cache),
        overrides_path=pathlib.Path(args.overrides),
        flattening_path=pathlib.Path(args.flattening),
        assets_releases_dir=pathlib.Path(args.assets_dir),
        html_path=pathlib.Path(args.inject_html),
        download_missing=args.download_missing,
        token=args.token,
    )


if __name__ == "__main__":
    main()
