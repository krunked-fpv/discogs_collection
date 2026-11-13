# 🎵 KRUNKED // DISCOGS VINYL VAULT (v4.0)

[GitHub Repo](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection)
[Live Vault](https://www.google.com/search?q=https://krunked-fpv.github.io/discogs_collection/)
[](https://www.discogs.com/user/krunked/collection)
[](https://www.discogs.com/developers)

**KRUNKED // DISCOGS VINYL VAULT (v4.0)** is a pressing-first static web application and 100% deterministic Python synchronization pipeline built for [Alex Goresch's (`krunked`) Discogs Vinyl Collection](https://www.discogs.com/user/krunked/collection) and deployed to [GitHub Pages (krunked-fpv.github.io/discogs\_collection)](https://www.google.com/search?q=https://krunked-fpv.github.io/discogs_collection/) from [krunked-fpv/discogs\_collection](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection).

> *"Vibe coding a Discogs collection page to not look like trash."*

Unlike generic collection grids that only display square front-sleeve thumbnails, this project downloads every release's candidate gallery images from the [Discogs Database Release endpoint (GET /releases/{release\_id})](https://www.google.com/search?q=https://www.discogs.com/developers/%23page:database,header:database-release), runs a **4-Pass Calibrated Concentric Dual-Circle Computer Vision (CV) classifier** paired with [Discogs Database Guidelines 13.8 (Image Order)](https://support.discogs.com/hc/en-us/articles/360005006874-Database-Guidelines-13-Images) to isolate the physical 12" vinyl pressing photo (`pressing.jpg`), parses variant notes into a deterministic procedural wax shader when no physical disc photo exists, tracks the **Owner Vinyl Inspection & Thermal Flattening Regimen** inline inside the HTML, and compiles a zero-backend static payload directly into [index.html](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/index.html).

## ✨ What's New in Version 4.0

* **Unified Single-Command Delta Sync (`python scripts/sync_discogs.py`)**: Pressing photo evaluation, SHA-256 delta caching (`delta_sig`), local file cleaning, and HTML compilation are all baked directly into `sync_discogs.py`. Unchanged releases fast-path in sub-millisecond time while new or modified releases automatically download gallery images in parallel and run the 4-pass CV suite.
* **Portable Inline HTML Flattening Queue (`#flattening-inline-form`)**: Removed all legacy Google Keep dependencies. Your owner inspection & thermal plate regimen (`Need to be done`, `Done`, or `Not Listed`) is now stored portably inside hidden HTML form fields (`#flattening-inline-form`) right inside `index.html` alongside `data/flattening_queue.json`.
* **Owner Inspection Bench & 2.5-Hour Thermal Plate Session Timer**: Added an interactive **Owner Inspection Bench** inside the `Flattening Queue` tab (plus a 1-click `+ 🔥 Queue` / `✓ Mark Done` toggle on the main Turntable Stage) so any LP in the collection can be queued or marked flattened on arrival, paired with a persistent 2.5-hour (`150:00`) countdown timer for the 130°F thermal pouch hold.
* **1-Click Self-Contained `index.html` Baker & CLI Hub**: Replaced the legacy browser API sync modal with the **v4.0 Vault State Manager & Self-Contained Exporter**. Any pressing photo pins or flattening queue changes made in the browser can be baked directly into a downloadable `index.html` (which `sync_discogs.py` automatically reads and reconciles on its next run) or exported to `data/overrides.json` and `data/flattening_queue.json`.
* **100% Live Telemetry Across All Tabs**: Eliminated all static record counts in headers, buttons, search placeholders, and the `Deterministic CV & Local Sync` tab—every counter dynamically reflects the live compiled collection.

## 🧠 4-Tier Deterministic Pressing Selection Pipeline

When querying a release from the [Discogs Database Release endpoint (GET /releases/{release\_id})](https://www.google.com/search?q=https://www.discogs.com/developers/%23page:database,header:database-release), the `images[]` array only classifies images as `"type": "primary"` (typically the front sleeve cover) or `"type": "secondary"` (back cover tracklist, inner gatefold spread, lyric insert, hype sticker, close-up 4" paper center label, or the 12" vinyl record itself).

Rather than relying on slow, non-reproducible LLM vision calls, [scripts/detect\_pressing\_image.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/detect_pressing_image.py) uses a **4-Tier Deterministic Pipeline**:

| Tier | Stage | Deterministic Mechanism |
| :--- | :--- | :--- |
| **Tier 1** | **Override Pinning (`data/overrides.json`)** | Locks a verified `assets/releases/<id>/pressing.jpg?v=...` path or manual `user_locked` `pressing_image_index` per `release_id`. Automatically purges stale auto-overrides if re-evaluated CV rejects a sticker or sleeve. |
| **Tier 2** | **4-Pass Concentric Dual-Circle CV (`score_image_pixels_deterministic`)** | Evaluates candidate images in polar coordinates $(r, 	heta)$ on a normalized $256 	imes 256$ grid across 4 framing passes to verify the outer 12" disc rim ($R_{	ext{disc}} \in [0.65, 0.99]$), the 4 diagonal background quadrants, the 4" center label step ($r_{	ext{label}} pprox R_{	ext{disc}} / 3$), 8-octant label-to-wax color distance (`q25_oct_lbl_wax`), and the center spindle hole ($r \le 0.035$). |
| **Tier 3** | **[Discogs Guideline 13.8](https://support.discogs.com/hc/en-us/articles/360005006874-Database-Guidelines-13-Images) Positional Prior & Side-A Tie-Breaker** | Applies canonical Discogs image ordering rules (`[0]` front cover, `[1]` back cover / gatefold inner, `[2..3]` labels or inserts, `[4..5]` Side A/B physical disc) as an offline fallback when pixel dependencies are unavailable, and grants a `+0.038` tie-breaker bonus to the first verified physical disc (Side A). |
| **Tier 4** | **Deterministic Wax Variant Parser (`parse_wax_variant`)** | Parses `formats[].descriptions`, `formats[].text`, and `(THIS)` release notes (`Pur`, `Cle`, `Ult`, `Mil`, `Gho`, `Cok`, `Ele`, `Blu`, `Gre`, `Aci`, `Neo`, `Ora`, `Pea`, `Yel`, `Can`, `Pin`, `Vio`, `Mag`, `Gal`, `Gra`, `Dus`, `Hou`, `Splatter`, `Swirl`, `Marble`, `Split`, `Color-in-Color`, `Etched`) into a `wax_spec` object with a SHA-256 `deterministic_seed`. Guides CV candidate scoring (`variant_color_bonus`) and renders the procedural vinyl disc when `has_pressing_photo` is `false`. |

### Multi-Pass CV Verification Benchmarks

| Release | Variant Format | Selected Image | CV Pass & Detection Signature |
| :--- | :--- | :--- | :--- |
| [Coheed and Cambria – *The Second Stage Turbine Blade* (`26690690`)](https://www.discogs.com/release/26690690-Coheed-And-Cambria-The-Second-Stage-Turbine-Blade) | Yellow w/ White & Black Splatter LP | `img_1.jpg` (`0.9532`) | **Pass 3 (Padded Studio Disc)**: Locks onto $R_{	ext{disc}} = 0.712$ (`rim_step = 0.060`, `corner_wax_dist = 1.225`) while rejecting hype sticker `img_2.jpg`. |
| [Rings Of Saturn – *Embryonic Anomaly (Remake)* (`17583742`)](https://www.discogs.com/release/17583742-Rings-Of-Saturn-Embryonic-Anomaly-Remake) | Purple / Green Splatter LP | `img_3.jpg` (`0.8126`) | **Pass 2 (Landscape Side-by-Side 4:3)**: Aligns square crop window over the right-hand 12" disc beside the jacket (`label_wax_dist = 0.54`). |
| [Every Time I Die – *The Big Dirty* (`2343816`)](https://www.discogs.com/release/2343816) & [*Radical* (`20697637`)](https://www.discogs.com/release/20697637-Every-Time-I-Die-Radical) | Turntable Platter Photos | `img_1.jpg` (`0.8112` / `0.6942`) | **Pass 2 (Left-Shifted Platter 4:3)**: Shifts crop window left (`lf = 0.12`) so the right-hand tonearm does not break outer rim continuity. |
| [Coheed and Cambria – *No World For Tomorrow* (`16251744`)](https://www.discogs.com/release/16251744-Coheed-And-Cambria-Good-Apollo-Im-Burning-Star-IV-Volume-Two-No-World-for-Tomorrow) | Red & Cream Mix w/ Black Splatter 2xLP | `img_1.jpg` (`0.7549`) | **Pass 4 (Close-Cropped 360° Label+Spindle)**: Detects full 8-octant label (`r_lbl = 0.44`, `q25 = 0.43`) and rejects rectangular hype sticker `img_2.jpg`. |
| [Emarosa – *Peach Club* (`13203006`)](https://www.discogs.com/release/13203006-Emarosa-Peach-Club) | Limited Peach Opaque LP | `img_1.jpg` (`0.7363`) | **Pass 4 (Off-Center Angled Disc)**: Locates off-center 360° coral center label and spindle hole (`spindle_contrast = 0.362`, `oct_q25 = 0.282`). |
| [Northlane – Node: Reloaded (37023150)](https://www.google.com/search?q=https://www.discogs.com/release/37023150) | Radial Splatter LP | `img_2.jpg` (`0.7046`) | **Pass 1 (Radial Splatter Spoke Exemption)**: Recognizes $
abla_	heta I / 
abla_r I = 3.53$ as radial splatter rays rather than square-insert text noise. |
| [Bring Me The Horizon – *That's The Spirit* (`35907826`)](https://www.discogs.com/release/35907826-Bring-Me-The-Horizon-Thats-The-Spirit) | 10th Anniv. Deluxe Swirl LP | `img_6.jpg` (`0.6988`) | **Pass 1 (Centered 12" Disc)**: Rejects zoomed 4" label scans (`img_4`–`img_5`), lyric booklet (`img_8`–`img_21`), and hype sticker (`img_22`). |
| [Animals As Leaders – *Animals As Leaders* (`12988109`)](https://www.discogs.com/release/12988109-Animals-As-Leaders-Animals-As-Leaders) | Clear 2xLP on Inner Sleeve | `img_4.jpg` (`0.6464`) | **Pass 1 (`has_strong_concentric_disc`)**: Protects full-bleed 12" discs photographed over white inner sleeves on wood tables. |
| [Nothing More – *Spirits* (`27927123`)](https://www.discogs.com/release/27927123-Nothing-More-Spirits) | Clear w/ Black Smoke Etched 2xLP | `img_4.jpg` (`0.5560`) | **Pass 2B (Portrait Vertical Window)**: Aligns vertical crop window (`yf = 0.56`) on 3:4 hand-held disc photo. |

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
│   ├── collection.json                # Compiled schema v4.0.0 dataset for user `krunked`
│   ├── releases_cache.json            # Incremental Discogs /releases/{id} metadata & image cache
│   ├── overrides.json                 # Per-release verified pressing paths & user-locked pins
│   ├── flattening_queue.json          # Portable Vinyl Flattening Queue (synced with inline HTML form)
│   └── sync_manifest.json             # SHA-256 content digest, record counts, & sync timestamp
├── scripts/
│   ├── sync_discogs.py                # Unified v4.0 Delta Sync, CV Photo Picker, & HTML Compiler
│   ├── pick_pressing_photo.py         # Local/Offline CV photo selector & HTML KPI/Form injector
│   ├── detect_pressing_image.py       # 4-Pass polar CV classifier, wax parser, & inline queue reconciler
│   ├── setup_discogs_token.py         # Windows HKCU Registry + .env token installer & repo scrubber
│   ├── seed_collection.py             # Offline deterministic collection seed builder
│   └── validate_collection.py         # Schema v4.0.0 & Discogs URL integrity validator
├── .env                               # Local git-ignored credentials (DISCOGS_USERNAME / DISCOGS_TOKEN)
├── index.html                         # Self-contained Turntable Stage, Inline Flattening Bench, & Crate UI
└── requirements.txt                   # Python dependencies (Pillow, numpy)
```

## 🚀 Local Workstation Setup & Daily Workflow (v4.0)

### 1. Prerequisites & One-Time Token Setup

```powershell
cd C:\DiscogsCollection\discogs_collection
pip install -r requirements.txt
python scripts/setup_discogs_token.py
```

### 2. Daily Incremental Sync & GitHub Pages Deploy

Whenever you add new records to your [Discogs collection](https://www.discogs.com/user/krunked/collection) or update your flattening queue in `index.html`, run the unified single-command pipeline:

```powershell
cd C:\DiscogsCollection\discogs_collection
python scripts/sync_discogs.py
git add -A; git commit -m "chore(vault): sync discogs collection (v4.0)"; git push
```

### 3. Targeted Release Resync or Full CV Rebuild

```powershell
# Force re-download & re-run 4-pass CV on specific release ID(s)
python scripts/sync_discogs.py --resync 35668090,16610055

# Bypass SHA-256 delta fast-path and re-evaluate all releases
python scripts/sync_discogs.py --full
```

## 🛠️ Script Reference & CLI Flags

| Script | Primary Role | Key CLI Arguments |
| :--- | :--- | :--- |
| [scripts/sync\_discogs.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/sync_discogs.py) | Unified v4.0 pipeline: paginates Folder 0, runs SHA-256 delta checks, downloads new gallery images, runs 4-pass CV selection, reconciles inline HTML flattening state, and compiles `index.html`. | `--full` (`-f`), `--resync <id1,id2>`, `--username`, `--token`, `--output`, `--cache`, `--overrides`, `--flattening`, `--assets-dir`, `--inject-html` |
| [scripts/pick\_pressing\_photo.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/pick_pressing_photo.py) | Standalone local/offline delta photo picker and HTML injector (called automatically at the end of `sync_discogs.py`, or runnable directly with `--offline`). | `--full` (`-f`), `--resync <id1,id2>`, `--offline`, `--collection`, `--cache`, `--overrides`, `--flattening`, `--assets-dir`, `--inject-html` |
| [scripts/detect\_pressing\_image.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/detect_pressing_image.py) | Core deterministic library containing `score_image_pixels_deterministic()`, `select_release_images_deterministic()`, `parse_wax_variant()`, `reconcile_flattening_state()`, and `VaultTerminalUI`. | Imported by `sync_discogs.py`, `pick_pressing_photo.py`, and `seed_collection.py` |
| [scripts/setup\_discogs\_token.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/setup_discogs_token.py) | Interactive credential installer that sanitizes pasted tokens, writes `.env` + `HKCU\Environment`, updates `.gitignore`, and scrubs exposed tokens from repo files. | `python scripts/setup_discogs_token.py` |
| [scripts/validate\_collection.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/validate_collection.py) | Verifies `REQUIRED_RECORD_KEYS`, `https://www.discogs.com/release/` URLs, `wax_spec` completeness, and `delta_sig` coverage. | `python scripts/validate_collection.py [path/to/collection.json]` |
