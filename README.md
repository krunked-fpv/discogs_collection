# KRUNKED // DISCOGS VINYL VAULT (v2.2)

> *"vibe coding a discogs collection page to not look like trash"*

A **pressing-first** interactive vinyl collection showcase, direct-drive turntable stage, and deterministic Discogs synchronization pipeline for [**discogs.com/user/krunked/collection**](https://www.discogs.com/user/krunked/collection).

* **Live Site:** [**krunked-fpv.github.io/discogs_collection**](https://krunked-fpv.github.io/discogs_collection/)
* **Source of Truth:** [**Discogs Collection (`krunked` • Folder 0)**](https://www.discogs.com/user/krunked/collection)
* **Repository:** [**github.com/krunked-fpv/discogs_collection**](https://github.com/krunked-fpv/discogs_collection)

---

## ⚡ Daily Workflow (Local Windows Workstation)

When you add new records to your Discogs collection, you only need to run **one command** before pushing to GitHub. `sync_discogs.py` automatically fetches your new releases, downloads their Discogs image galleries, runs `pick_pressing_photo.py` to select the physical vinyl pressing photo, reconciles your Vinyl Flattening queue and collection value, and injects the compiled dataset straight into `index.html`:

```powershell
cd C:\DiscogsCollection\discogs_collection
python sync_discogs.py
git add -A
git commit -m "sync discogs collection & pressing photos"
git push
```

*(Note: Both root wrapper scripts `sync_discogs.py` and `pick_pressing_photo.py` automatically anchor all file paths to the repository root, whether you invoke them from `C:\DiscogsCollection\discogs_collection` or `scripts\`.)*

### When to run `python pick_pressing_photo.py` by itself:
`sync_discogs.py` already calls `pick_pressing_photo.py` at the end of every sync. You only need to run `python pick_pressing_photo.py` standalone if you manually edited `data/overrides.json` or `data/flattening_queue.json` and want to re-compile `index.html` instantly offline without hitting the Discogs API.

---

## 🎯 What's Inside (v2.2 Architecture)

### 1. Pressing-First Turntable & Crate UI (`index.html`)
* **Direct-Drive Strobe Turntable Stage:** Interactive 33⅓ & 45 RPM quartz-locked platter with S-shaped tonearm, Web Audio API vinyl crackle generator, and instant record switching.
* **Real Pressing Photos by Default (142 / 150 LPs):** Every record's spinning platter and crate card defaults directly to its physical vinyl pressing photo from Discogs.
* **Procedural SVG Wax Shader Fallback:** For the few releases on Discogs that only have front/back sleeve cover scans uploaded, the UI falls back to a deterministic SVG/Canvas vinyl renderer driven by the release's parsed Discogs format string (`Splatter`, `Galaxy`, `Color-in-Color`, `Marble Swirl`, `Split`, `Translucent`, `Etched`, or `180g Black`).
* **Interactive Release Image Strip:** Displays all images (`[0..N]`) from each release's Discogs gallery. Clicking any thumbnail pins that photo as the record's pressing image and saves it to `overrides.json` / `localStorage`.
* **3 Thumbnail Modes:** Switch the crate grid on the fly between **Pressing First**, **Sleeve + Disc**, and **Sleeve First**.
* **Instant Static + Live Valuation:** Pre-compiles both the official Discogs Collection Value (`Min $3,721.74 • Median $6,011.87 • Max $10,437.49`) and the sum of individual release values directly into `index.html` so telemetry loads immediately with zero "Syncing..." delay.

### 2. Deterministic Pressing Photo Detector (`scripts/detect_pressing_image.py`)
When fetching a release from the Discogs Database API (`GET /releases/{release_id}`), the `images[]` array only tags photos as `"primary"` or `"secondary"` (which mixes back covers, inner gatefold spreads, lyric inserts, paper center-label scans, and the vinyl disc itself).

Instead of guessing with an LLM, `detect_pressing_image.py` uses a **4-tier deterministic pipeline**:
1. **Tier 1 — Verified Override Pinning (`data/overrides.json`):** Locks a specific Discogs image URL or index per `release_id`. Newly detected pressing photos are automatically persisted here so future syncs stay 100% consistent.
2. **Tier 2 — Discogs Database Guideline 13.8 Positional Classifier:** Inspects `formats[].descriptions` and `formats[].text` (`Gatefold`, `Single Sided`, `Etched`, `No Cover`) and applies Discogs' canonical image ordering rules (`[0]` = Front Cover, `[1]` = Back Cover / Gatefold Inner, `[2+]` = Physical Vinyl Disc).
3. **Tier 3 — Polar `(r, θ)` Annular Computer Vision (`score_image_pixels_deterministic`):**
   * Supports both square (`1:1`) and camera (`4:3` / `3:4`, `0.65 <= W/H <= 1.52`) photos by center-cropping to the inscribed square before polar analysis, while rejecting wide panoramic gatefold spreads (`W/H > 1.52`).
   * Measures **outer corner background uniformity** (`r > 1.05`) vs. the **wax playing surface annulus** (`0.38 <= r <= 0.90`).
   * Compares concentric groove tangential continuity (`∂I/∂θ`) against radial edge steps (`∂I/∂r`) at the outer rim (`r ≈ 0.94`), the 4-inch center label border (`r ≈ 0.33`), and the center spindle hole (`r <= 0.045`).
   * **Rejects Zoomed 4" Center Label Scans:** Detects and penalizes close-up paper label scans that lack a radial step at `r ≈ 0.33`.
4. **Tier 4 — Auto-Pick Candidate Fallback:** If a newly added release has secondary images on a busy background that score just below the strict `0.50` CV threshold (`>= 0.34`), the detector automatically selects the highest-scoring non-panoramic candidate photo rather than falling back to the front cover.

### 3. Thermal Vinyl Flattening Queue (`data/flattening_queue.json`)
* Cross-references the collection against the Google Keep **Vinyl flattening** note (`Bag on 6 until it hits 130°F then drop to 4 — 2.5 hours once at 130°F on the plate`).
* Tracks **🔥 Need to be done** (Queue) and **✓ Flattened & Verified** (Done) statuses both in the dedicated **Flattening Queue** tab and via badges on the crate cards.

---

## 📁 Repository Structure

```text
discogs_collection/
├── .github/
│   └── workflows/
│       └── static.yml                     # Deploys static repository to GitHub Pages on push to `main`
├── assets/
│   ├── pressings/                         # Fallback procedural/reference pressing textures
│   └── releases/                          # Local cached Discogs images (`<release_id>/cover.jpg`, `img_0.jpg`, `pressing.jpg`)
├── data/
│   ├── collection.json                    # Compiled 150-LP dataset + wax specs + image classifications
│   ├── overrides.json                     # Auto-populated & user-pinned pressing photo URLs by release_id
│   ├── flattening_queue.json              # Synced Google Keep thermal plate queue & completed list
│   ├── releases_cache.json                # Incremental local Discogs `/releases/{id}` cache (speeds up syncs)
│   └── sync_manifest.json                 # SHA-256 content digest & collection telemetry summary
├── scripts/
│   ├── sync_discogs.py                    # Multi-page Discogs API v2.0 sync engine
│   ├── pick_pressing_photo.py             # Pressing photo selector, Keep reconciler & `index.html` injector
│   ├── detect_pressing_image.py           # Polar (r, θ) annular CV classifier & Discogs format parser
│   ├── seed_collection.py                 # Offline deterministic collection builder
│   └── validate_collection.py             # Strict schema & URL integrity validator
├── tests/
│   └── test_deterministic_detector.py     # Unit tests for annular CV, Guideline 13.8 & wax variant parsing
├── sync_discogs.py                        # Root convenience wrapper -> runs `scripts/sync_discogs.py`
├── pick_pressing_photo.py                 # Root convenience wrapper -> runs `scripts/pick_pressing_photo.py`
├── index.html                             # Self-contained single-file Turntable & Crate web application
├── publish.sh                             # Optional bash helper for syncing, testing & pushing
└── requirements.txt                       # Python dependencies (`Pillow`, `numpy`)
```

---

## 🛠️ Setup & Installation

### Prerequisites
* **Python 3.10+**
* `Pillow` and `numpy` (for polar pixel analysis of newly added release images):

```powershell
pip install -r requirements.txt
```

### Running Unit Tests & Schema Validation
```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/validate_collection.py data/collection.json
```

### Customizing or Pinning a Different Pressing Photo
1. **In the Browser:** Click any record in the crate grid, look at the **"Discogs Release Images (Click to Pin Pressing Photo)"** strip on the right, and click the thumbnail you want. Click **Sync / Export JSON → Download overrides.json** to save it back to `data/overrides.json`.
2. **Or directly in `data/overrides.json`:** Map any `"release_id"` to its desired Discogs image URL or image index (`0`, `1`, `2`, ...) and run `python pick_pressing_photo.py`.