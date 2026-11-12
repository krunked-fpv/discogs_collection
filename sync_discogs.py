#!/usr/bin/env python3
"""Root-level convenience launcher for `scripts/sync_discogs.py`.

Run from `C:\\DiscogsCollection\\discogs_collection`:
    python sync_discogs.py
"""

from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sync_discogs import main

if __name__ == "__main__":
    main()
