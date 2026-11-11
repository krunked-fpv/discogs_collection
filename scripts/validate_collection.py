#!/usr/bin/env python3
"""Deterministic schema & integrity validator for data/collection.json."""

from __future__ import annotations

import json
import pathlib
import sys


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

    print(f"[valid] {path}: {len(records)} records verified against schema v{data.get('schema_version')}.")


if __name__ == "__main__":
    target = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data/collection.json")
    validate_collection(target)
