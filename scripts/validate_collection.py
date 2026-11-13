#!/usr/bin/env python3
"""Deterministic schema & integrity validator for data/collection.json."""

from __future__ import annotations

import json
import pathlib
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else SCRIPT_DIR
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from detect_pressing_image import VaultTerminalUI
except Exception:
    VaultTerminalUI = None  # type: ignore

REQUIRED_RECORD_KEYS = {
    "release_id",
    "artist",
    "title",
    "format_string",
    "label",
    "catno",
    "media_condition",
    "sleeve_condition",
    "discogs_url",
    "estimated_value_usd",
    "flattening_status",
    "images",
    "wax_spec",
}


def validate_collection(path: pathlib.Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing collection file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("username") == "krunked", "Expected username 'krunked'"
    assert data.get("source_of_truth") == "https://www.discogs.com/user/krunked/collection"
    records = data.get("records")
    assert isinstance(records, list) and len(records) > 0, "Expected non-empty records list"

    prof = data.get("profile") or {}
    col_val = prof.get("collection_value") or {}
    assert col_val.get("median"), "Missing profile.collection_value.median"

    delta_sig_count = 0
    for idx, rec in enumerate(records):
        missing = REQUIRED_RECORD_KEYS - set(rec.keys())
        if missing:
            raise ValueError(f"Record #{idx} ({rec.get('title')}) missing keys: {sorted(missing)}")
        url = str(rec.get("discogs_url") or "")
        if not url.startswith("https://www.discogs.com/release/"):
            raise ValueError(f"Record #{idx} has invalid discogs_url: {url}")
        wax = rec.get("wax_spec") or {}
        if not wax.get("primary_color") or not wax.get("pattern"):
            raise ValueError(f"Record #{idx} has incomplete wax_spec: {wax}")
        if (rec.get("images") or {}).get("delta_sig"):
            delta_sig_count += 1

    pressing_count = sum(1 for r in records if r["images"].get("has_pressing_photo"))
    todo_count = sum(1 for r in records if r.get("flattening_status") == "Need to be done")
    done_count = sum(1 for r in records if r.get("flattening_status") == "Done")
    msg = (
        f"{path}: {len(records)} records verified against schema v{data.get('schema_version')} "
        f"({pressing_count} pressing photos, {delta_sig_count}/{len(records)} delta-cached, "
        f"{todo_count} flattening todo, {done_count} flattening done, "
        f"median value {col_val.get('median')})."
    )
    if VaultTerminalUI is not None:
        ui = VaultTerminalUI()
        ui.log("ok", f"[valid] {msg}")
    else:
        print(f"[valid] {msg}")


if __name__ == "__main__":
    default_target = REPO_ROOT / "data" / "collection.json"
    target = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else default_target
    validate_collection(target)
