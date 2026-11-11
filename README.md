# KRUNKED // DISCOGS VINYL VAULT

A visually rich, **pressing-first** static web application and deterministic synchronization pipeline for [`https://www.discogs.com/user/krunked/collection`](https://www.discogs.com/user/krunked/collection), powered by the [Discogs REST API v2.0](https://www.discogs.com/developers) and GitHub Actions.

## Why Deterministic Instead of Probabilistic?

When fetching a release from the [Discogs Database Release endpoint (`GET /releases/{release_id}`)](https://www.discogs.com/developers/#page:database,header:database-release), the `images[]` array only tags images as `"type": "primary"` (typically the front sleeve cover) or `"type": "secondary"` (back cover, inner gatefold spread, paper center labels, or the physical vinyl pressing itself).

Instead of relying on an LLM or vision model to guess which image shows the physical vinyl pressing, this repository uses a **3-tier deterministic pipeline** in [`scripts/detect_pressing_image.py`](scripts/detect_pressing_image.py):

1. **Tier 1 — Deterministic Override Pinning (`data/overrides.json`)**:
   - Allows locking a specific `pressing_image_index` or custom image URL per `release_id` with zero ambiguity.
2. **Tier 2 — [Discogs Database Guideline 13.8](https://support.discogs.com/hc/en-us/articles/360005006874-Database-Guidelines-13-Images) Canonical Positional Classifier**:
   - Inspects `formats[].descriptions` and `formats[].text` (`Gatefold`, `Single Sided`, `Etched`, `No Cover`) and applies Discogs' mandatory image ordering rules:
     - **Standard Sleeve LP (`len(images) >= 3`)**: `[0]` = Front Cover (`primary`), `[1]` = Back Cover (`secondary`), `[2]` = Media / Side A Vinyl Pressing (`secondary`), `[3]` = Side B / Full Vinyl Pressing (`secondary`).
     - **Gatefold LP (`"Gatefold"` in format/notes, `len(images) >= 4`)**: `[0]` = Front Cover, `[1]` = Gatefold Spread, `[2]` = Back Cover, `[3..4]` = Vinyl Pressing Disc.
3. **Tier 3 — Radial / Annular Geometry & Pixel Computer Vision (`score_image_pixels_deterministic`)**:
   - Evaluates candidate secondary images using pure `numpy` + `Pillow` math in polar coordinates `(r, θ)` centered on the square frame:
     - **Aspect Ratio Gate (`0.88 <= W/H <= 1.12`)**: Rejects wide gatefold spreads (`W/H > 1.25`) and vertical inserts.
     - **Outer Corner Uniformity (`r > 1.06`) vs. Wax Annulus (`0.38 <= r <= 0.92`)**: A circular 12" vinyl disc inscribed in a square leaves 4 uniform background corners outside `r = 1.0` with high color distance from the wax playing surface.
     - **Tangential Groove Continuity vs. Radial Step Energy**: Compares tangential variance (`∂I/∂θ`) along concentric microgrooves against radial edge steps (`∂I/∂r`) at the outer rim (`r ≈ 0.96`), the 4-inch center label border (`r ≈ 0.333`), and the center spindle hole (`r < 0.045`).
4. **Tier 4 — Deterministic Wax Variant Code Parser (`parse_wax_variant`)**:
   - Parses Discogs format codes (`Pur`, `Cle`, `Ult`, `Blu`, `Ele`, `Gre`, `Aci`, `Ora`, `Pea`, `Yel`, `Can`, `Pin`, `Vio`, `Mag`, `Mil`, `Gho`, `Cok`, `Gal`, `Neo`, `Gra`, `Dus`, `Hou`, `Whi`, `Bla`, `Splatter`, `Swirl`, `Marble`, `Split`, `Etched`) into a deterministic `wax_spec` that drives an in-browser SVG/Canvas procedural vinyl renderer whenever a release only has front-cover art on Discogs.

---

## Repository Structure

```text
discogs_collection/
├── .github/
│   └── workflows/
│       └── sync-and-deploy.yml      # Runs every 6h, on push, or workflow_dispatch -> deploys to GitHub Pages
├── assets/
│   └── pressings/                   # Cached pressing photography & release assets
├── data/
│   ├── collection.json              # Compiled deterministic collection dataset for user `krunked`
│   ├── overrides.json               # Per-release deterministic image overrides
│   └── sync_manifest.json           # SHA-256 content digest & sync telemetry
├── scripts/
│   ├── detect_pressing_image.py     # Deterministic annular CV + Guideline 13.8 classifier + wax parser
│   ├── sync_discogs.py              # Discogs REST API v2.0 sync engine & static HTML injector
│   ├── seed_collection.py           # Offline deterministic collection builder
│   └── validate_collection.py       # Strict schema & URL integrity validator
├── tests/
│   └── test_deterministic_detector.py # Unit tests for annular CV, Guideline 13.8, and wax code parsing
├── index.html                       # Self-contained Pressing-First 3D Turntable Carousel & Crate UI
└── requirements.txt                 # Python dependencies (Pillow, numpy)
```

---

## Setup & GitHub Actions Deployment

1. **Generate a Discogs Personal Access Token**:
   - Go to [Discogs Developer Settings (`https://www.discogs.com/settings/developers`)](https://www.discogs.com/settings/developers) and click **Generate new token**.
2. **Add Repository Secret**:
   - In `krunked-fpv/discogs_collection`, navigate to **Settings → Secrets and variables → Actions** and create a repository secret named `DISCOGS_TOKEN`.
3. **Enable GitHub Pages**:
   - Go to **Settings → Pages** and set **Build and deployment → Source** to **GitHub Actions**.
4. **Run Manual or Scheduled Sync**:
   - The workflow (`.github/workflows/sync-and-deploy.yml`) runs automatically every 6 hours (`0 */6 * * *`) or immediately via **Actions → Sync Discogs Collection & Deploy to GitHub Pages → Run workflow**.

## Running Locally

```bash
pip install -r requirements.txt
python3 -m unittest discover -s tests -p "test_*.py" -v

# Sync live from Discogs API and inject into index.html:
DISCOGS_TOKEN="your_token_here" python3 scripts/sync_discogs.py \
  --username krunked \
  --output data/collection.json \
  --inject-html index.html \
  --download-images \
  --analyze-pixels

python3 scripts/validate_collection.py data/collection.json
```
