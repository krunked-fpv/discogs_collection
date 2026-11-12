# KRUNKED // DISCOGS VINYL VAULT

A visually rich, **pressing-first** static web application and deterministic synchronization pipeline for [`https://www.discogs.com/user/krunked/collection`](https://www.discogs.com/user/krunked/collection), powered by the [Discogs REST API v2.0](https://www.discogs.com/developers) and GitHub Pages.

## Local Workstation Daily Workflow (`C:\DiscogsCollection\discogs_collection`)

Run the 2-step sync and pressing-photo selector anytime from PowerShell (works whether run from the repo root `C:\DiscogsCollection\discogs_collection` or from `scripts\`):

```powershell
cd C:\DiscogsCollection\discogs_collection

# 1. Sync collection & release galleries from Discogs API:
python sync_discogs.py

# 2. Pick the right pressing photo for every record & compile index.html:
python pick_pressing_photo.py

# 3. Validate & push to GitHub (triggers static GitHub Pages deploy):
python scripts/validate_collection.py
git add -A
git commit -m "sync discogs collection & pressing photos"
git push
```

---

## How the Pressing Photo Selector Works (`pick_pressing_photo.py`)

When fetching a release from the [Discogs Database Release endpoint (`GET /releases/{release_id}`)](https://www.discogs.com/developers/#page:database,header:database-release), the `images[]` array only tags images as `"type": "primary"` (front sleeve cover) or `"type": "secondary"` (back cover, inner gatefold spread, paper center labels, or the physical vinyl pressing itself).

`pick_pressing_photo.py` and [`scripts/detect_pressing_image.py`](scripts/detect_pressing_image.py) inspect every image associated with each release (`assets/releases/<release_id>/img_*.jpg` and `data/releases_cache.json`) using a **3-tier pipeline**:

1. **Tier 1 — Verified Pressing Overrides (`data/overrides.json`)**:
   - Locks the exact verified pressing photo URL per `release_id` (**142 / 150 releases** in `krunked`'s collection have verified pressing photos; the remaining 8 releases only have sleeve/insert art uploaded on Discogs).
2. **Tier 2 — Radial / Annular Computer Vision (`score_image_pixels_deterministic`)**:
   - Evaluates both square (`1:1`) and `4:3` / `3:4` camera photos by center-cropping to the inscribed square and scoring in polar coordinates `(r, θ)`:
     - **Outer Corner Uniformity (`r > 1.05`) vs. Wax Annulus (`0.38 <= r <= 0.90`)**: Detects a circular 12" vinyl disc against background corners.
     - **12" Full Vinyl Disc vs. 4" Paper Label Scan Discrimination**: Verifies the center-label-to-wax step at `r ≈ 0.33` and penalizes zoomed-in 4" paper center-label scans so full colored/splatter vinyl disc photos win.
3. **Tier 3 — [Discogs Database Guideline 13.8](https://support.discogs.com/hc/en-us/articles/360005006874-Database-Guidelines-13-Images) Positional Prior + Fallback Wax Shader (`parse_wax_variant`)**:
   - Defaults the turntable platter and crate card wax ring directly to the selected pressing photo, falling back to the deterministic SVG wax ring (`deterministic_seed`) only when a release has no vinyl disc photo on Discogs.

---

## Repository Structure

```text
discogs_collection/
├── .github/
│   └── workflows/
│       └── static.yml                 # Deploys static site to GitHub Pages on push to main
├── assets/
│   ├── pressings/                     # Studio fallback textures
│   └── releases/                      # Cached release covers & pressing photos (assets/releases/<id>/img_*.jpg)
├── data/
│   ├── collection.json                # Compiled 150-LP dataset for user `krunked`
│   ├── overrides.json                 # Per-release verified pressing photo URLs (142 releases)
│   ├── flattening_queue.json          # Google Keep 'Vinyl flattening' queue (3 Todo, 40 Done entries)
│   ├── releases_cache.json            # Cached Discogs /releases/{id} API responses
│   └── sync_manifest.json             # SHA-256 content digest & sync telemetry
├── scripts/
│   ├── detect_pressing_image.py       # Annular CV + Guideline 13.8 classifier + wax & flattening parser
│   ├── pick_pressing_photo.py         # Pressing photo selector & static index.html injector
│   ├── sync_discogs.py                # Discogs REST API v2.0 sync engine
│   └── validate_collection.py         # Strict schema & KPI validator
├── tests/
│   └── test_deterministic_detector.py # Unit tests for annular CV, Guideline 13.8, and wax code parsing
├── pick_pressing_photo.py             # Root launcher for scripts/pick_pressing_photo.py
├── sync_discogs.py                    # Root launcher for scripts/sync_discogs.py
├── index.html                         # Self-contained Pressing-First 3D Turntable Carousel & Crate UI
└── requirements.txt                   # Python dependencies (Pillow, numpy)
```
