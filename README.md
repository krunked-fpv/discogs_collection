# KRUNKED // DISCOGS VINYL VAULT (v3.0)

A visually rich, **Sleeve + Disc** static web application and deterministic synchronization pipeline for [discogs.com/user/krunked/collection](https://www.discogs.com/user/krunked/collection), powered by the [Discogs REST API v2.0](https://www.discogs.com/developers), local computer-vision asset compilation, and GitHub Actions.

*Vibe coding a Discogs collection page to not look like trash.*

---

## What's New in v3.0

* **Zero Hardcoded Secrets (`DISCOGS_TOKEN` Architecture):** Eliminated all hardcoded API tokens from `scripts/*.py` and `index.html`. Credentials now resolve seamlessly across local Windows User Environment Variables (`HKCU\Environment`), a git-ignored `.env` fallback (`scripts/setup_discogs_token.py`), and encrypted GitHub Actions Repository Secrets (`secrets.DISCOGS_TOKEN`).
* **Default `Sleeve + Disc` Split Showcase:** The UI now defaults to the **Sleeve + Disc** (`split`) view mode on both desktop and mobile, displaying the authentic front album jacket alongside the physical vinyl pressing photo (or procedural wax variant shader).
* **Dedicated Per-Release Local Asset Pipeline (`assets/releases/<release_id>/`):** `sync_discogs.py` and `pick_pressing_photo.py` download release galleries (`img_0.jpg .. img_N.jpg`), generate a canonical `cover.jpg` and verified `pressing.jpg` inside every release folder, and self-heal incomplete cache entries automatically.
* **Concentric Dual-Circle & 4-Quadrant Diagonal CV (`detect_pressing_image.py`):** Upgraded the pixel classifier to support both `1:1` square and `4:3` / `3:4` camera photos, scan diagonal quadrants ($|\sin(2\theta)| > 0.55$) to reject square $12\text{"} \times 12\text{"}$ lyric inserts, and verify the $1/3$ center-label boundary ($R_{\text{label}} \approx R_{\text{disc}} / 3.0$) to reject zoomed-in $4\text{"}$ paper center-label scans.
* **Full Multi-Page Collection Pagination (150+ LPs):** Paginates deterministically through all pages of `/users/krunked/collection/folders/0/releases?per_page=100`, enriches release metadata via an incremental cache (`data/releases_cache.json`), and reconciles live collection valuation.
* **Vinyl Flattening Queue & Thermal Protocol Tracker:** Built-in tracker and cross-reference view (`data/flattening_queue.json`) for monitoring records in the flattening queue vs. completed discs following the thermal plate protocol ($\text{Bag on } 6 \rightarrow 130^\circ\text{F} \rightarrow \text{Drop to } 4 \text{ for } 2.5\text{ hours}$).

---

## Why Deterministic Instead of Probabilistic?

When fetching a release from the [Discogs Database Release endpoint (`GET /releases/{release_id}`)](https://www.discogs.com/developers/#page:database,header:database-release), the `images[]` array only tags images as `"type": "primary"` (typically the front sleeve cover) or `"type": "secondary"` (back cover, inner gatefold spread, lyric insert, paper center labels, or the physical vinyl pressing itself).

Instead of relying on an LLM or vision model to guess which image shows the physical vinyl pressing, this repository uses a **4-tier deterministic pipeline** across `scripts/detect_pressing_image.py` and `scripts/pick_pressing_photo.py`:

1. **Tier 1 — Deterministic Override Pinning (`data/overrides.json`):**
   * Locks a specific `pressing_image_index` or custom image path per `release_id` with zero ambiguity (can also be pinned visually in the browser UI and exported).
2. **Tier 2 — Discogs Database Guideline 13.8 Canonical Positional Classifier:**
   * Inspects `formats[].descriptions` and `formats[].text` (`Gatefold`, `Single Sided`, `Etched`, `No Cover`) and applies Discogs' mandatory image ordering rules:
     * **Standard Sleeve LP ($\text{len}(\text{images}) \ge 3$):** `[0]` = Front Cover (`primary`), `[1]` = Back Cover (`secondary`), `[2..3]` = Media / Physical Vinyl Pressing (`secondary`).
     * **Gatefold LP (`"Gatefold"` in format/notes, $\text{len}(\text{images}) \ge 4$):** `[0]` = Front Cover, `[1]` = Gatefold Spread, `[2]` = Back Cover, `[3..5]` = Vinyl Pressing Disc.
3. **Tier 3 — Radial / Annular Geometry & 4-Quadrant Pixel Computer Vision (`score_image_pixels_deterministic`):**
   * Evaluates candidate secondary images using pure `numpy` + `Pillow` math in polar coordinates $(r, \theta)$ after center-cropping to the inscribed square:
     * **Aspect Ratio Gate ($0.65 \le W/H \le 1.52$):** Accepts both `1:1` and `4:3` / `3:4` camera photos while rejecting wide panoramic gatefold spreads.
     * **4-Quadrant Diagonal Rim Detection ($|\sin(2\theta)| > 0.55$):** Isolates curved circular disc rims along the 4 diagonal quadrants so square $12\text{"} \times 12\text{"}$ lyric sheets or inner sleeves cannot masquerade as vinyl discs.
     * **Concentric $12\text{"}$ Disc vs. $4\text{"}$ Center Label Verification:** Verifies radial step energy ($\partial I / \partial r$) at the outer disc rim ($r \approx 0.70 .. 0.98$), the $4\text{-inch}$ center label border ($r \approx R_{\text{disc}} / 3.0$), and the center spindle hole ($r < 0.045$), while comparing outer corner backdrop uniformity ($r > 1.04$) against the wax annulus ($0.40 R_{\text{disc}} \le r \le 0.92 R_{\text{disc}}$) to reject close-up paper label scans.
4. **Tier 4 — Deterministic Wax Variant Code Parser (`parse_wax_variant`):**
   * Parses Discogs format codes and variant notes (`Pur`, `Cle`, `Ult`, `Blu`, `Ele`, `Gre`, `Aci`, `Ora`, `Pea`, `Yel`, `Can`, `Pin`, `Vio`, `Mag`, `Mil`, `Gho`, `Cok`, `Gal`, `Neo`, `Gra`, `Dus`, `Hou`, `Whi`, `Bla`, `Splatter`, `Swirl`, `Marble`, `Split`, `Color-in-Color`, `Etched`) into a deterministic `wax_spec` that drives an in-browser procedural vinyl renderer whenever a release only has sleeve artwork on Discogs.

---

## UI Features & Crate Controls

* **3 View Modes (Defaults to `Sleeve + Disc`):** Switch seamlessly between **Sleeve + Disc** (`split`), **Pressing First** (`pressing`), and **Sleeve First** (`sleeve`) layouts.
* **Interactive Direct-Drive Pressing Stage:** Features a quartz-locked $33\frac{1}{3}\text{ RPM}$ interactive turntable platter, live Discogs release image gallery selector (click any thumbnail to pin it as the pressing photo), random LP selector, and collection value telemetry.
* **Smart Variant Filtering:** Filter the crate by *All Releases*, *Verified Pressing Photo*, *Splatter & Color-in-Color*, *Galaxy, Marble & Split*, *Clear / Milky / Translucent*, *2xLP Double Sets*, or *180g Black Wax*.
* **Sorting & Instant Search:** Search across artists, album titles, labels, and catalog numbers, with sorting by *Date Added (Newest First)*, *Artist (A $\rightarrow$ Z)*, *Album Title (A $\rightarrow$ Z)*, *Est. Value (High $\rightarrow$ Low)*, and *Release Year (Newest)*.

---

## Repository Structure

```text
discogs_collection/
├── .github/
│   └── workflows/
│       └── static.yml                     # Syncs via DISCOGS_TOKEN secret & deploys to GitHub Pages
├── assets/
│   └── releases/
│       └── <release_id>/                  # Per-release cached gallery (img_0..N.jpg, cover.jpg, pressing.jpg)
├── data/
│   ├── collection.json                    # Compiled deterministic collection dataset for user `krunked`
│   ├── releases_cache.json                # Incremental Discogs release detail & image gallery cache
│   ├── overrides.json                     # Per-release deterministic image overrides
│   └── flattening_queue.json              # Vinyl flattening queue & completed thermal protocol records
├── scripts/
│   ├── setup_discogs_token.py             # One-time Windows User Env Var setup & hardcoded token scrubber
│   ├── sync_discogs.py                    # Multi-page Discogs REST API v2.0 sync engine & HTML injector
│   ├── pick_pressing_photo.py             # Standalone & integrated local pressing.jpg selector & compiler
│   ├── detect_pressing_image.py           # 4-quadrant annular CV + Guideline 13.8 classifier + wax parser
│   └── validate_collection.py             # Strict schema & asset integrity validator
├── tests/
│   └── test_deterministic_detector.py     # Unit tests for annular CV, Guideline 13.8, and wax code parsing
├── index.html                             # Self-contained v3.0 Sleeve + Disc Turntable Stage & Crate UI
├── requirements.txt                       # Python dependencies (Pillow, numpy)
└── README.md                              # Project documentation
```

---

## Token Security & Local Windows Setup

This project never stores API tokens in source code. Both local Windows builds and GitHub Actions read the **`DISCOGS_TOKEN`** environment variable.

### 1. Install Python Dependencies
```powershell
pip install -r requirements.txt
```

### 2. Configure `DISCOGS_TOKEN` Locally on Windows (One-Time Setup)
1. Go to **[Discogs Developer Settings](https://www.discogs.com/settings/developers)** and click **Generate new token**.
2. From `C:\DiscogsCollection\discogs_collection`, run the setup utility:
   ```powershell
   python scripts/setup_discogs_token.py
   ```
3. Paste your token when prompted. This script:
   * Saves `DISCOGS_TOKEN` permanently to your **Windows User Environment Variables** (`HKCU\Environment`).
   * Writes a local git-ignored `.env` file (`DISCOGS_TOKEN=...`) and ensures `.env` is in `.gitignore`.
   * Scrubs any legacy hardcoded tokens from tracked files.

---

## Running Locally (Windows PowerShell)

Once `DISCOGS_TOKEN` is saved via `setup_discogs_token.py`, you can run a full collection sync or re-evaluate pressing photos anytime without passing tokens on the command line:

### Full Discogs API Sync + Image Download + Pressing Selection + HTML Injection
```powershell
python scripts/sync_discogs.py
```

### Re-Evaluate Local Release Folders & Regenerate `pressing.jpg` Only
```powershell
python scripts/pick_pressing_photo.py
```

### Run Unit Tests & Schema Validation
```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/validate_collection.py data/collection.json
```

---

## GitHub Actions & GitHub Pages Deployment

1. **Add Repository Secret:**
   * In `krunked-fpv/discogs_collection` on GitHub, go to **Settings $\rightarrow$ Secrets and variables $\rightarrow$ Actions**.
   * Click **New repository secret**, set the Name to **`DISCOGS_TOKEN`**, and paste your Discogs Personal Access Token.
2. **Enable GitHub Pages:**
   * Go to **Settings $\rightarrow$ Pages** and set **Build and deployment $\rightarrow$ Source** to **GitHub Actions**.
3. **Automated & Manual Runs:**
   * The workflow in `.github/workflows/static.yml` runs automatically on every push to `main`, every 6 hours on a schedule (`0 */6 * * *`), or on demand via **Actions $\rightarrow$ Run workflow**, injecting the latest synced collection and deploying directly to GitHub Pages.