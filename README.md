# 🎵 KRUNKED // DISCOGS VINYL VAULT (v3.2)

[](https://github.com/krunked-fpv/discogs_collection)
[](https://krunked-fpv.github.io/discogs_collection/)
[](https://www.discogs.com/user/krunked/collection)
[](https://www.discogs.com/developers)
[](https://github.com/krunked-fpv/discogs_collection/tree/main/scripts)

**KRUNKED // DISCOGS VINYL VAULT** is a pressing-first static web application and 100% deterministic Python synchronization pipeline built for [Alex Goresch's (`krunked`) Discogs Vinyl Collection](https://www.discogs.com/user/krunked/collection) and deployed to [GitHub Pages (`krunked-fpv.github.io/discogs_collection`)](https://krunked-fpv.github.io/discogs_collection/) from [`krunked-fpv/discogs_collection`](https://github.com/krunked-fpv/discogs_collection).

> *"Vibe coding a Discogs collection page to not look like trash."*

Unlike generic collection grids that only display square front-sleeve thumbnails, this project downloads every release's candidate gallery images from the [Discogs Database Release endpoint (`GET /releases/{release_id}`)](https://www.discogs.com/developers/#page:database,header:database-release), runs a **Multi-Pass Calibrated Concentric Dual-Circle Computer Vision (CV) classifier** paired with [Discogs Database Guidelines 13.8 (Image Order)](https://support.discogs.com/hc/en-us/articles/360005006874-Database-Guidelines-13-Images) to isolate the physical 12" vinyl pressing photo (`pressing.jpg`), parses variant notes into a deterministic procedural wax shader when no physical disc photo exists, cross-references the **Vinyl Flattening Thermal Plate Queue**, and compiles a zero-backend static payload directly into [`index.html`](https://github.com/krunked-fpv/discogs_collection/blob/main/index.html).

## ✨ What's New in Version 3.2

* **Multi-Pass Calibrated Concentric Dual-Circle CV (`detect_pressing_image.py`)**: Upgraded the pixel classifier to evaluate four distinct physical framing passes—standard centered 12" discs (`R_disc in [0.80..0.99]`), landscape 4:3 turntable platter and side-by-side sleeve+disc shots (`aspect > 1.08`), portrait hand-held vertical shifts (`aspect < 0.88`), padded studio shots (`R_disc in [0.65..0.79]`), and off-center/close-cropped 360° 4" center-label compositions.
* **Radial Splatter Spoke & Color-in-Color Exemptions**: Recognizes tangential-to-radial gradient ratios ($\nabla_\theta I / \nabla_r I \ge 1.35$) on heavy radial starburst/splatter pressings (such as [Northlane – Node: Reloaded (37023150)](https://www.google.com/search?q=https://www.discogs.com/release/37023150) and [Unearth – *The Stings Of Conscience* (`23343893`)](https://www.discogs.com/release/23343893-Unearth-The-Stings-Of-Conscience)) and inner-vs-outer annulus color shifts (`color_in_color_dist`) on puddle/swirl variants (such as [Knocked Loose – *Laugh Tracks* (`16595574`)](https://www.discogs.com/release/16595574-Knocked-Loose-Laugh-Tracks) and [Protest The Hero – *Fortress* (`26047519`)](https://www.discogs.com/release/26047519-Protest-The-Hero-Fortress)).
* **Zero False-Positive Hype Stickers or Zoomed 4" Labels**: Rejects rectangular and circular hype stickers (e.g., [Don Broco – *Automatic* (`14188877`)](https://www.discogs.com/release/14188877-Don-Broco-Automatic) and [The Prize Fighter Inferno – *My Brother's Blood Machine* (`28895677`)](https://www.discogs.com/release/28895677-The-Prize-Fighter-Inferno-My-Brothers-Blood-Machine)), die-cut inner sleeves, lyric inserts, and zoomed-in 4" center-label scans on high-saturation colored wax by enforcing 8-octant label-to-wax continuity (`q25_oct_lbl_wax`) and horizontal/vertical text gradient anisotropy bounds (`hv_wax_aniso`).
* **Automatic False-Positive `pressing.jpg` Purging & Deterministic Seed Fallback**: When a release has zero verified photos of the physical vinyl record (e.g., [Chromeo – *Business Casual* (`2486041`)](https://www.discogs.com/release/2486041-Chromeo-Business-Casual) or [TesseracT – *War Of Being* (`28269505`)](https://www.discogs.com/release/28269505-Tesseract-War-of-Being)), `pick_pressing_photo.py` automatically unlinks any stale `pressing.jpg` on disk and purges unpinned entries from `data/overrides.json` so the UI cleanly renders the record's deterministic procedural wax ring.
* **SHA-256 Cache-Busted Local Assets & `localStorage` Sync Stamp**: Appends `?v=<selected_index>_<sha256_8>` to local `assets/releases/<release_id>/pressing.jpg` URLs and injects `__discogs_py_sync_stamp__` into [`index.html`](https://github.com/krunked-fpv/discogs_collection/blob/main/index.html) so browsers immediately evict stale cached thumbnails after every local rebuild.
* **Self-Healing Incremental Cache & Orphan Folder Discovery**: `sync_discogs.py` and `pick_pressing_photo.py` automatically discover newly added `assets/releases/<release_id>/` folders on disk, probe true JPEG SOF dimensions (`img_0.jpg` .. `img_N.jpg`), recover from empty or 6-image-truncated entries in `data/releases_cache.json`, and default the UI to **Sleeve + Disc** (`split`) view mode.
* **Hardened Token Security & Windows Registry Auto-Loader (`setup_discogs_token.py`)**: Scrubs exposed tokens from tracked files, strips hidden Windows console `Ctrl+V` control bytes (`\x16`), persists `DISCOGS_TOKEN` to both git-ignored `.env` and Windows User Environment Variables (`HKCU\Environment`), and automatically falls back on HTTP `400`/`401`/`403` or `429` rate limits.

## 🧠 Why Deterministic Instead of Probabilistic?

When querying a release from the [Discogs Database Release endpoint (`GET /releases/{release_id}`)](https://www.discogs.com/developers/#page:database,header:database-release), the `images[]` array only classifies images as `"type": "primary"` (typically the front sleeve cover) or `"type": "secondary"` (back cover tracklist, inner gatefold spread, lyric insert, hype sticker, close-up 4" paper center label, or the 12" vinyl record itself).

Rather than relying on slow, non-reproducible LLM vision calls, [scripts/detect\_pressing\_image.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/detect_pressing_image.py) uses a **4-Tier Deterministic Pipeline**:

| Tier | Stage | Deterministic Mechanism |
| :--- | :--- | :--- |
| **Tier 1** | **Override Pinning (`data/overrides.json`)** | Locks a verified `assets/releases/<id>/pressing.jpg?v=...` path or manual `pressing_image_index` per `release_id`. Automatically purges stale auto-overrides if re-evaluated CV rejects a sticker or sleeve. |
| **Tier 2** | **Multi-Pass Concentric Dual-Circle CV (`score_image_pixels_deterministic`)** | Evaluates candidate images in polar coordinates $(r, \theta)$ on a normalized $256 \times 256$ grid across 4 framing passes to verify the outer 12" disc rim ($R_{\text{disc}} \in [0.65, 0.99]$), the 4 diagonal background quadrants, the 4" center label step ($r_{\text{label}} \approx R_{\text{disc}} / 3$), 8-octant label-to-wax color distance (`q25_oct_lbl_wax`), and the center spindle hole ($r \le 0.035$). |
| **Tier 3** | **[Discogs Guideline 13.8](https://support.discogs.com/hc/en-us/articles/360005006874-Database-Guidelines-13-Images) Positional Prior & Side-A Tie-Breaker** | Applies canonical Discogs image ordering rules (`[0]` front cover, `[1]` back cover / gatefold inner, `[2..3]` labels or inserts, `[4..5]` Side A/B physical disc) as an offline fallback when pixel dependencies are unavailable, and grants a `+0.038` tie-breaker bonus to the first verified physical disc (Side A). |
| **Tier 4** | **Deterministic Wax Variant Parser (`parse_wax_variant`)** | Parses `formats[].descriptions`, `formats[].text`, and `(THIS)` release notes (`Pur`, `Cle`, `Ult`, `Mil`, `Gho`, `Cok`, `Ele`, `Blu`, `Gre`, `Aci`, `Neo`, `Ora`, `Pea`, `Yel`, `Can`, `Pin`, `Vio`, `Mag`, `Gal`, `Gra`, `Dus`, `Hou`, `Blood Pool`, `Splatter`, `Swirl`, `Marble`, `Split`, `Color-in-Color`, `Etched`) into a `wax_spec` object with a SHA-256 `deterministic_seed`. Both guides CV candidate scoring (`variant_color_bonus`) and renders the procedural vinyl disc when `has_pressing_photo` is `false`. |

### Multi-Pass CV Verification Benchmarks

| Release | Variant Format | Selected Image | CV Pass & Detection Signature |
| :--- | :--- | :--- | :--- |
| [Coheed and Cambria – *The Second Stage Turbine Blade* (`26690690`)](https://www.discogs.com/release/26690690-Coheed-And-Cambria-The-Second-Stage-Turbine-Blade) | Yellow w/ White & Black Splatter LP | `img_1.jpg` (`0.9532`) | **Pass 3 (Padded Studio Disc)**: Locks onto $R_{\text{disc}} = 0.712$ (`rim_step = 0.060`, `corner_wax_dist = 1.225`) while rejecting hype sticker `img_2.jpg`. |
| [Rings Of Saturn – *Embryonic Anomaly (Remake)* (`17583742`)](https://www.discogs.com/release/17583742-Rings-Of-Saturn-Embryonic-Anomaly-Remake) | Purple / Green Splatter LP | `img_3.jpg` (`0.8126`) | **Pass 2 (Landscape Side-by-Side 4:3)**: Aligns square crop window over the right-hand 12" disc beside the jacket (`label_wax_dist = 0.54`). |
| [Every Time I Die – *The Big Dirty* (`2343816`)](https://www.discogs.com/release/2343816) & [*Radical* (`20697637`)](https://www.discogs.com/release/20697637-Every-Time-I-Die-Radical) | Turntable Platter Photos | `img_1.jpg` (`0.8112` / `0.6942`) | **Pass 2 (Left-Shifted Platter 4:3)**: Shifts crop window left (`lf = 0.12`) so the right-hand tonearm does not break outer rim continuity. |
| [Coheed and Cambria – *No World For Tomorrow* (`16251744`)](https://www.discogs.com/release/16251744-Coheed-And-Cambria-Good-Apollo-Im-Burning-Star-IV-Volume-Two-No-World-for-Tomorrow) | Red & Cream Mix w/ Black Splatter 2xLP | `img_1.jpg` (`0.7549`) | **Pass 4 (Close-Cropped 360° Label+Spindle)**: Detects full 8-octant label (`r_lbl = 0.44`, `q25 = 0.43`) and rejects rectangular hype sticker `img_2.jpg`. |
| [Emarosa – *Peach Club* (`13203006`)](https://www.discogs.com/release/13203006-Emarosa-Peach-Club) | Limited Peach Opaque LP | `img_1.jpg` (`0.7363`) | **Pass 4 (Off-Center Angled Disc)**: Locates off-center 360° coral center label and spindle hole (`spindle_contrast = 0.362`, `oct_q25 = 0.282`). |
| [Northlane – Node: Reloaded (37023150)](https://www.google.com/search?q=https://www.discogs.com/release/37023150) | Radial Splatter LP | `img_2.jpg` (`0.7046`) | **Pass 1 (Radial Splatter Spoke Exemption)**: Recognizes $\nabla_\theta I / \nabla_r I = 3.53$ as radial splatter rays rather than square-insert text noise. |
| [Bring Me The Horizon – *That's The Spirit* (`35907826`)](https://www.discogs.com/release/35907826-Bring-Me-The-Horizon-Thats-The-Spirit) | 10th Anniv. Deluxe Swirl LP | `img_6.jpg` (`0.6988`) | **Pass 1 (Centered 12" Disc)**: Rejects zoomed 4" label scans (`img_4`–`img_5`), lyric booklet (`img_8`–`img_21`), and hype sticker (`img_22`). |
| [Animals As Leaders – *Animals As Leaders* (`12988109`)](https://www.discogs.com/release/12988109-Animals-As-Leaders-Animals-As-Leaders) | Clear 2xLP on Inner Sleeve | `img_4.jpg` (`0.6464`) | **Pass 1 (`has_strong_concentric_disc`)**: Protects full-bleed 12" discs photographed over white inner sleeves on wood tables. |
| [Nothing More – *Spirits* (`27927123`)](https://www.discogs.com/release/27927123-Nothing-More-Spirits) | Clear w/ Black Smoke Etched 2xLP | `img_4.jpg` (`0.5560`) | **Pass 2B (Portrait Vertical Window)**: Aligns vertical crop window (`yf = 0.56`) on 3:4 hand-held disc photo. |

## 🎛️ Vault UI & Collection Telemetry

The static web application ([`index.html`](https://github.com/krunked-fpv/discogs_collection/blob/main/index.html), live at [`krunked-fpv.github.io/discogs_collection`](https://krunked-fpv.github.io/discogs_collection/)) compiles all collection data and KPIs at build time so the page loads instantaneously with zero unauthenticated API spinner delays:

* **3 Crate Thumbnail Modes (Default: `Sleeve + Disc`)**: Toggle between **Sleeve + Disc** (`split` — displays the album jacket paired with the emerging vinyl pressing or deterministic wax ring), **Pressing First** (`pressing`), and **Sleeve Cover** (`sleeve`) across desktop and mobile viewports.
* **Interactive 33⅓ RPM Direct-Drive Turntable Stage**: Click any record in the crate to load it onto the quartz-locked turntable platter, inspect its Discogs release metadata (`release_id`, label, catalog number, media/sleeve grading, variant badge, and CV detection score), or click any gallery thumbnail to manually pin an override and export `overrides.json`.
* **Collection Valuation & Verified Price Fallbacks**: Pulls Min / Median / Max valuation telemetry from `GET /users/krunked/collection/value` and per-release `lowest_price` in USD, supplemented by `VERIFIED_PRICE_FALLBACKS` in `pick_pressing_photo.py` for scarce pressings with zero active Discogs Marketplace listings (such as [Currents – *The Way It Ends* (`22031968`)](https://www.discogs.com/release/22031968-Currents-The-Way-It-Ends) and [Periphery – *Periphery III: Select Difficulty* (`9346527`)](https://www.discogs.com/release/9346527-Periphery-Periphery-III-Select-Difficulty)).
* **Vinyl Flattening Queue & Thermal Plate Protocol**: Cross-references every collection release against `data/flattening_queue.json` (synced from Alex's Google Keep *Vinyl flattening* note) using exact `release_id` sets and normalized artist/album matching (`Need to be done`, `Done`, or `Not Listed`), complete with the thermal pouch protocol:
  $$\text{Bag on } 6 \longrightarrow 130^\circ\text{F} \longrightarrow \text{Drop to } 4 \text{ for } 2.5\text{ Hours}$$

## 📁 Repository Architecture

```text
discogs_collection/
├── .github/
│   └── workflows/
│       └── static.yml                 # GitHub Actions workflow deploying static build to GitHub Pages
├── assets/
│   ├── pressings/                     # Procedural fallback studio textures
│   └── releases/
│       └── <release_id>/              # Per-release cached Discogs gallery images
│           ├── cover.jpg              # Primary front sleeve artwork (copied from img_0.jpg)
│           ├── pressing.jpg           # Verified 12" vinyl pressing photo (or unlinked if seed-only)
│           └── img_0.jpg .. img_N.jpg # Raw candidate images from Discogs GET /releases/{id}
├── data/
│   ├── collection.json                # Compiled schema v2.3.0 dataset for user `krunked`
│   ├── releases_cache.json            # Incremental Discogs /releases/{id} metadata & image cache
│   ├── overrides.json                 # Per-release verified pressing paths & user-locked pins
│   ├── flattening_queue.json          # Google Keep 'Vinyl flattening' queue (Need to be done / Done)
│   └── sync_manifest.json             # SHA-256 content digest, record counts, & sync timestamp
├── scripts/
│   ├── sync_discogs.py                # Multi-page Folder 0 Discogs REST API v2.0 sync & HTML compiler
│   ├── pick_pressing_photo.py         # Standalone CV photo selector, file cleaner, & HTML KPI injector
│   ├── detect_pressing_image.py       # Multi-pass annular CV classifier, wax parser, & queue matcher
│   ├── setup_discogs_token.py         # Windows HKCU Registry + .env token installer & repo scrubber
│   ├── seed_collection.py             # Offline deterministic collection seed builder
│   └── validate_collection.py         # Schema v2.3.0 & Discogs URL integrity validator
├── tests/
│   └── test_deterministic_detector.py # Unit test suite for CV passes, Guideline 13.8, & wax parsing
├── .env                               # Local git-ignored credentials (DISCOGS_USERNAME / DISCOGS_TOKEN)
├── index.html                         # Self-contained Turntable Stage, Flattening Tracker, & Crate UI
├── publish.sh                         # Automated build, validation, and git push helper
└── requirements.txt                   # Python dependencies (Pillow, numpy)
```

## 🚀 Local Workstation Setup & Daily Workflow

The project is designed to run locally on Windows (`C:\DiscogsCollection\discogs_collection`) or Linux/macOS, compile all static assets and JSON payloads into [`index.html`](https://github.com/krunked-fpv/discogs_collection/blob/main/index.html), and publish directly to GitHub Pages via `git push`.

### 1. Prerequisites & Dependencies

Install **Python 3.10+** (tested on Python 3.12 on Windows 11) and the required image processing packages (`Pillow` and `numpy`—note that `detect_pressing_image.py` will also auto-bootstrap them if missing):

```powershell
cd C:\DiscogsCollection\discogs_collection
pip install -r requirements.txt
```

### 2. Configure & Scrub Your Discogs API Token (One-Time Setup)

1. Generate a Personal Access Token at [Discogs Developer Settings (`discogs.com/settings/developers`)](https://www.discogs.com/settings/developers).
2. Run [scripts/setup\_discogs\_token.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/setup_discogs_token.py) once in PowerShell:

```powershell
python scripts/setup_discogs_token.py
```

**What `setup_discogs_token.py` does automatically:**
* Prompts for your token and strips any hidden Windows console control characters (such as `\x16` from `Ctrl+V`) or `Bearer ` / `DISCOGS_TOKEN=` prefixes.
* Saves `DISCOGS_TOKEN` permanently to your Windows User Environment Variables (`HKCU\Environment`) and broadcasts `WM_SETTINGCHANGE`.
* Writes a local `.env` file (`DISCOGS_USERNAME=krunked` and `DISCOGS_TOKEN=<your_discogs_personal_access_token>`) and ensures `.env` is listed in `.gitignore` so you can run scripts immediately without restarting PowerShell.
* Scans `index.html` and `scripts/*.py` to scrub any historical hardcoded token strings before you commit.

### 3. Sync Collection & Rebuild `index.html`

Whenever you add new records to your [Discogs collection](https://www.discogs.com/user/krunked/collection), run the full synchronization pipeline from the repository root (`C:\DiscogsCollection\discogs_collection`):

```powershell
python scripts/sync_discogs.py
```

`sync_discogs.py` paginates through all pages of `GET /users/krunked/collection/folders/0/releases?per_page=100`, enriches uncached releases in `data/releases_cache.json`, downloads new `img_*.jpg` files into `assets/releases/<release_id>/`, and automatically invokes `run_pick_pressing_photos()` to update `pressing.jpg`, `data/overrides.json`, `data/collection.json`, `data/sync_manifest.json`, and `index.html`.

### 4. Re-Evaluate Pressing Photos Only (Fast Local Pass)

If you already have `img_*.jpg` files in `assets/releases/<release_id>/` or dropped a new release folder into `assets/releases/` and want to re-run the computer vision selector and re-inject `index.html` in seconds:

```powershell
# Standard run (uses local img_*.jpg files and fetches any missing metadata/images from Discogs)
python scripts/pick_pressing_photo.py

# Strictly offline run (evaluates only existing local files in assets/releases/ with zero network calls)
python scripts/pick_pressing_photo.py --offline
```

> 💡 **Clean Slate Pressing Regeneration**: To force a 100% fresh regeneration of every `pressing.jpg` without re-downloading `img_0.jpg .. img_N.jpg` from Discogs, delete only the `pressing.jpg` files and re-run the picker:
> ```powershell
> Get-ChildItem -Path "assets\releases" -Filter "pressing.jpg" -Recurse | Remove-Item -Force
> python scripts/pick_pressing_photo.py
> ```

### 5. Validate & Publish to GitHub Pages

Verify schema integrity against [scripts/validate\_collection.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/validate_collection.py) and push to [`krunked-fpv/discogs_collection`](https://github.com/krunked-fpv/discogs_collection):

```powershell
python scripts/validate_collection.py data/collection.json
git add index.html data/ assets/ scripts/ README.md
git commit -m "chore(vault): sync collection and pressing photos (v3.2)"
git push origin main
```

Once pushed to `main`, `.github/workflows/static.yml` automatically deploys the updated static bundle to [`https://krunked-fpv.github.io/discogs_collection/`](https://krunked-fpv.github.io/discogs_collection/).

## 🛠️ Script Reference & CLI Flags

| Script | Primary Role | Key CLI Arguments |
| :--- | :--- | :--- |
| [scripts/sync\_discogs.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/sync_discogs.py) | Paginates Folder 0 (`per_page=100`), updates `data/releases_cache.json`, downloads release images, and runs `pick_pressing_photo.py`. | `--username`, `--token`, `--output`, `--cache`, `--overrides`, `--flattening`, `--assets-dir`, `--inject-html`, `--analyze-pixels`, `--download-images` |
| [scripts/pick\_pressing\_photo.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/pick_pressing_photo.py) | Scans `data/collection.json` and `assets/releases/<id>/`, runs CV classification, writes/cleans `pressing.jpg`, updates `overrides.json` and `sync_manifest.json`, and injects `window.__DISCOGS_COLLECTION__` + KPIs into `index.html`. | `--collection`, `--cache`, `--overrides`, `--flattening`, `--assets-dir`, `--inject-html`, `--download-missing`, `--offline`, `--token` |
| [scripts/detect\_pressing\_image.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/detect_pressing_image.py) | Core deterministic library containing `score_image_pixels_deterministic()`, `select_release_images_deterministic()`, `parse_wax_variant()`, and `resolve_flattening_status()`. | Imported by `sync_discogs.py`, `pick_pressing_photo.py`, and `seed_collection.py` |
| [scripts/setup\_discogs\_token.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/setup_discogs_token.py) | Interactive credential installer that sanitizes pasted tokens, writes `.env` + `HKCU\Environment`, updates `.gitignore`, and scrubs exposed tokens from repo files. | Interactive CLI (`python scripts/setup_discogs_token.py`) |
| [scripts/validate\_collection.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/validate_collection.py) | Asserts `REQUIRED_RECORD_KEYS`, verifies `https://www.discogs.com/release/` URLs, checks `wax_spec` completeness, and prints collection telemetry. | `python scripts/validate_collection.py [path/to/collection.json]` |
| [scripts/seed\_collection.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/seed_collection.py) | Rebuilds an offline deterministic baseline dataset from verified Discogs Marketplace orders and Google Keep Vinyl Flattening records. | `python scripts/seed_collection.py` |
