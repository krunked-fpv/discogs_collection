#!/usr/bin/env python3
"""
Krunked Discogs Vinyl Vault — Modular Frontend HTML Compiler (`build_html.py`)
==============================================================================
Compiles the modular frontend source files in `src/`:
  - `src/template.html`   (HTML shell, Tailwind config, DOM layout & modals)
  - `src/cookie_vault.js` (Shadow-Cookie Auto-Healer `KRUNKED_COOKIE_VAULT_V1`)
  - `src/styles.css`      (Custom dark-obsidian theme, turntable & 3D flip CSS)
  - `src/ytm_maps.js`     (Static curated tracklists & verified YouTube Music maps)
  - `src/app.js`          (Frontend application state, audio engine, arena & UI logic)
together with `data/collection.json`, `data/overrides.json`, and `data/flattening_queue.json`
into the single self-contained, zero-spinner `index.html` at the repository root.

Usage:
  python scripts/build_html.py
  python scripts/build_html.py --check
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else SCRIPT_DIR
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from detect_pressing_image import (
    build_flattening_queue_payload,
    reconcile_flattening_state,
    reconcile_overrides_state,
    resolve_flattening_status,
)
from pick_pressing_photo import (
    DEFAULT_SRC_DIR,
    inject_into_index_html,
    render_template_from_src,
)


def build_index_html(
    src_dir: pathlib.Path = DEFAULT_SRC_DIR,
    collection_path: pathlib.Path = REPO_ROOT / "data" / "collection.json",
    overrides_path: pathlib.Path = REPO_ROOT / "data" / "overrides.json",
    flattening_path: pathlib.Path = REPO_ROOT / "data" / "flattening_queue.json",
    html_path: pathlib.Path = REPO_ROOT / "index.html",
    check_only: bool = False,
) -> bool:
    """Compiles `src/*` and `data/*.json` into `index.html` (or validates template assembly when `check_only=True`)."""
    rendered_shell = render_template_from_src(src_dir)
    for leftover in (
        "/* __KRUNKED_COOKIE_VAULT_JS__ */",
        "/* __VAULT_STYLES_CSS__ */",
        "/* __VAULT_YTM_MAPS_JS__ */",
        "/* __VAULT_APP_JS__ */",
    ):
        if leftover in rendered_shell:
            raise ValueError(f"Unresolved template placeholder {leftover!r} in rendered template")

    if check_only:
        return True

    if not collection_path.exists():
        raise FileNotFoundError(f"Collection JSON not found at {collection_path}")

    collection_data: dict[str, Any] = json.loads(collection_path.read_text(encoding="utf-8"))
    existing_html = html_path if html_path.exists() else None
    overrides_data, overrides_merged = reconcile_overrides_state(
        overrides_path=overrides_path,
        html_path=existing_html,
    )
    if overrides_merged:
        overrides_sorted = {
            k: overrides_data[k]
            for k in sorted(overrides_data.keys(), key=lambda x: (0, int(x), "") if str(x).isdigit() else (1, 0, str(x)))
        }
        overrides_path.parent.mkdir(parents=True, exist_ok=True)
        overrides_path.write_text(
            json.dumps(overrides_sorted, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        overrides_data = overrides_sorted

    # Reconcile any newer inline #flattening-inline-form state from an existing index.html before overwriting it
    flattening_queue = reconcile_flattening_state(
        flattening_path=flattening_path,
        html_path=existing_html,
    )
    records = collection_data.get("records") or []
    collection_updated = False
    for rec in records:
        rid = int(rec.get("release_id") or 0)
        if rid > 0:
            new_status = resolve_flattening_status(
                str(rec.get("artist") or ""),
                str(rec.get("title") or ""),
                rid,
                flattening_queue,
            )
            if rec.get("flattening_status") != new_status:
                rec["flattening_status"] = new_status
                collection_updated = True

    canonical_fq = build_flattening_queue_payload(
        records=records,
        base_queue=flattening_queue,
        updated_at_utc=str(flattening_queue.get("updated_at_utc") or collection_data.get("synced_at_utc") or ""),
    )
    prof = collection_data.get("profile")
    if isinstance(prof, dict):
        new_todo = len(canonical_fq.get("need_to_be_done_release_ids") or [])
        new_done = len(canonical_fq.get("done_release_ids") or [])
        if prof.get("flattening_need_to_be_done") != new_todo or prof.get("flattening_done") != new_done:
            prof["flattening_need_to_be_done"] = new_todo
            prof["flattening_done"] = new_done
            collection_updated = True

    if collection_data.get("flattening_queue") != canonical_fq:
        collection_data["flattening_queue"] = canonical_fq
        collection_updated = True

    if collection_updated:
        collection_path.write_text(
            json.dumps(collection_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    existing_fq_disk: dict[str, Any] | None = None
    if flattening_path.exists():
        try:
            existing_fq_disk = json.loads(flattening_path.read_text(encoding="utf-8"))
        except Exception:
            existing_fq_disk = None
    if existing_fq_disk != canonical_fq:
        flattening_path.parent.mkdir(parents=True, exist_ok=True)
        flattening_path.write_text(
            json.dumps(canonical_fq, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return inject_into_index_html(
        html_path=html_path,
        collection_data=collection_data,
        overrides_data=overrides_data,
        src_dir=src_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile modular frontend files in src/ and data/*.json into index.html."
    )
    parser.add_argument(
        "--src-dir",
        default=str(DEFAULT_SRC_DIR),
        help="Path to modular frontend source directory (default: src/)",
    )
    parser.add_argument(
        "--collection",
        default=str(REPO_ROOT / "data" / "collection.json"),
        help="Path to data/collection.json",
    )
    parser.add_argument(
        "--overrides",
        default=str(REPO_ROOT / "data" / "overrides.json"),
        help="Path to data/overrides.json",
    )
    parser.add_argument(
        "--flattening",
        default=str(REPO_ROOT / "data" / "flattening_queue.json"),
        help="Path to data/flattening_queue.json",
    )
    parser.add_argument(
        "--html",
        default=str(REPO_ROOT / "index.html"),
        help="Output path for compiled index.html",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate that src/* templates assemble cleanly without modifying index.html",
    )
    args = parser.parse_args()

    src_dir = pathlib.Path(args.src_dir)
    html_path = pathlib.Path(args.html)
    ok = build_index_html(
        src_dir=src_dir,
        collection_path=pathlib.Path(args.collection),
        overrides_path=pathlib.Path(args.overrides),
        flattening_path=pathlib.Path(args.flattening),
        html_path=html_path,
        check_only=args.check,
    )
    if not ok:
        print("[error] Failed to compile index.html", file=sys.stderr)
        return 1

    if args.check:
        print(f"[ok] Validated modular frontend templates in {src_dir}")
    else:
        num_lines = len(html_path.read_text(encoding="utf-8").splitlines())
        print(f"[ok] Compiled {src_dir}/* + data/*.json -> {html_path} ({num_lines:,} lines, {html_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
