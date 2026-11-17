# 🎛️ KRUNKED // DISCOGS VINYL VAULT (v5.0)

> *"Vibe coding a Discogs collection page to not look like trash."*

[](https://krunked-fpv.github.io/discogs_collection/)
[](https://www.discogs.com/user/krunked/collection)
[](https://github.com/krunked-fpv/discogs_collection)
[](https://krunked-fpv.github.io/discogs_collection/)

**[🚀 LAUNCH THE LIVE DISCOGS VINYL VAULT (krunked-fpv.github.io/discogs_collection)](https://krunked-fpv.github.io/discogs_collection/)** • **[📦 GitHub Repository](https://github.com/krunked-fpv/discogs_collection)** • **[💿 Official Discogs Profile (`krunked`)](https://www.discogs.com/user/krunked/collection)**

## 🌟 Core Tenet & Project Philosophy

Standard [Discogs collection grids](https://www.discogs.com/user/krunked/collection) bury custom splatter, galaxy, marble, and color-in-color vinyl pressings behind tiny square cardboard sleeve thumbnails. **KRUNKED // DISCOGS VINYL VAULT** was built from a single founding rule—**"Vibe coding a Discogs collection page to not look like trash"**—turning a 157-LP collection into an interactive, pressing-first 33⅓ RPM direct-drive command stage powered by deterministic computer vision, official [Discogs REST API v2.0](https://www.discogs.com/developers) telemetry, and a 3-tier persistence architecture that never loses your custom pressing pins or thermal flattening queue.

## 🛡️ 3-Tier Persistence Architecture (`Local Sync` + `Shadow-Cookie Auto-Healer`)

The Vault combines deterministic CLI state baking, portable in-browser synchronization, and a zero-touch **Shadow-Cookie Auto-Healer (`<script id="krunked-cookie-vault-v1">`)** so in-browser edits survive browser refreshes, mobile/tablet `localStorage` eviction, and Python CLI re-syncs.

| Persistence Tier | Mechanism & Storage Target | What It Preserves & How It Works |
| :--- | :--- | :--- |
| **Tier 1: CLI Static HTML & JSON Injection** | `scripts/sync_discogs.py` + `data/*.json` + `index.html` | Compiles `data/collection.json`, `data/overrides.json`, and `data/flattening_queue.json`, and injects live collection counters and release payloads directly into `index.html` while preserving `<!-- BEGIN KRUNKED_COOKIE_VAULT_V1 -->` markers inside `<head>`. |
| **Tier 2: Portable In-Browser `💾 Local Sync`** | `localStorage` + `#flattening-inline-form` + JSON Export | Persists pinned pressing photo overrides, inline Vinyl Flattening Queue edits (`Need to be done` / `Done`), UV Blacklight toggle state, `split` (`Sleeve + Disc`) thumbnail mode, Smart Spin mode, and Variant Clash Arena stats with one-click JSON export/import. |
| **Tier 3: Shadow-Cookie Auto-Healer (`kv1_*`)** | `<script id="krunked-cookie-vault-v1">` in `<head>` (400-day `SameSite=Lax` cookies) | Transparently hooks `Storage.prototype.setItem`, `removeItem`, and `clear`. Smartly skips the 157-LP full API release array (`records`) to stay under the browser's 4 KB cookie cap, splits user overrides and preferences into 3.2 KB chunks (`Max-Age=34560000`), self-heals `localStorage` on page boot before the main Vault script runs, and updates the shared cross-app `krunked_family_pulse` (`Path=/`) root cookie across `krunked-fpv.github.io`. |

### Patching, Rollback & Console Diagnostics

* **Ad-Hoc CLI Patcher (`bolt_on_cookie_persistence.py`):** Injects or updates the `krunked-cookie-vault-v1` block in `<head>` with automatic `.cookie_bak` backups:
  ```bash
  # Patch Discogs Vinyl Vault alongside family GitHub Pages repos
  python bolt_on_cookie_persistence.py C:\DiscogsCollection\discogs_collection

  # Restore from automatic .cookie_bak backup if needed
  python bolt_on_cookie_persistence.py --rollback C:\DiscogsCollection\discogs_collection
  ```
* **Live Browser Console Telemetry:** Run `window.__KRUNKED_COOKIE_VAULT__.status()` in DevTools at any time to inspect active `kv1_*` shadow cookie chunks, byte utilization, and the shared `krunked_family_pulse` payload across [discogs_collection](https://krunked-fpv.github.io/discogs_collection/), [violets_homework](https://krunked-fpv.github.io/violets_homework/), and [ozias_laboratory](https://krunked-fpv.github.io/ozias_laboratory/).

## 🔥 Key Features in v5.0

* **Combined Kinetic Wax Roulette & Direct-Drive Pressing Command Stage:** Merges the `🎰 SPIN THE CRATE [SPACE]` kinetic physics reel, 3D flanking crate wing cards (`#stage-prev-card`, `#stage-next-card`), and cyan-bracketed quartz-locked 33⅓ RPM direct-drive turntable platter onto one unified command deck.
* **3 Smart Spin Modes (Stylus-Safe Filtering):**
  * `🎲 Full Vault Roulette` (`ALL SAFE`): Automatically excludes warped `"Need to be done"` LPs from random spins to protect the Audio-Technica AT-VMN95ML microlinear stylus.
  * `📺 Showroom Kiosk` (`AUTO 15s`): Hands-free showcase mode that automatically spins and drops a fresh pressing onto the platter every 15 seconds.
  * `🌈 Eye-Candy Variants` (`FLEX WAX`): Filters spins exclusively to high-contrast Splatter, Galaxy, Marble, Split, and Color-in-Color pressings.
* **Variant Clash Arena (`#view-arena`):** Launch a 4-LP head-to-head knockout tournament (`Semifinal 1 → Semifinal 2 → Championship Final`) with pool filters (`All Safe`, `Eye-Candy Only`, `Flat Certified`) and in-card `🎧 Audition 30s` studio preview buttons.
* **UV Blacklight Mode (`🟣 UV Blacklight: ON` by Default, Shortcut `U`):** Boots with `body.uv-blacklight` active on page load, applying a reactive neon shader (`.uv-reactive`) across the main platter, Variant Clash Arena contenders, and all 157 crate grid discs, paired with synthesized Web Audio analog SFX and 60-FPS canvas particle bursts.
* **Official Discogs Historical Sales Valuation (`GET /users/krunked/collection/value`):** Queries the authenticated [Discogs Collection Value endpoint](https://www.discogs.com/developers) to display exact historical completed-sales valuation (`Low $3,952.62` • `Med $6,423.73` • `High $11,091.69`) and automatically scrubs legacy synthetic Marketplace asking-price estimates.
* **3D Flip Deck (`#hero-flip-stage`):**
  * **Side A (Pressing Specs & Gallery Pinning Strip):** Inspect runout matrix codes, pressing plant telemetry, wax color shaders, and click any release gallery thumbnail to pin it as the canonical pressing photo (`overrides.json`).
  * **Side B (30s Studio Audio Previews & Streaming):** Zero-autoplay 30-second HTML5 `<audio id="vault-preview-audio">` track previews powered by the iTunes Search API with automatic Deezer JSONP fallback, plus side-by-side **YT Music ↗** (`OLAK5uy_...` official album playlists) and **Spotify ↗** (`open.spotify.com/album/...`) deep links.
* **Portable Thermal Vinyl Flattening Queue (`#flattening-inline-form`):** Track records in the `Need to be done` queue vs. `Done (Flat Certified)` following the thermal flattening protocol (`Bag on 6 → 130°F → Drop to 4 for 2.5 hours`), backed by `data/flattening_queue.json`, `localStorage`, and shadow cookies.

## 🧠 Deterministic 12" Vinyl vs. 4" Label Computer Vision (`detect_pressing_image.py`)

When fetching a release from the [Discogs Database Release endpoint (`GET /releases/{release_id}`)](https://www.discogs.com/developers/#page:database,header:database-release), Discogs only tags images as `"primary"` or `"secondary"`. `scripts/detect_pressing_image.py` deterministically isolates true 12-inch colored vinyl photography without probabilistic guessing:

| Inspection Stage | Mathematical / Heuristic Rule | What It Accepts vs. Rejects |
| :--- | :--- | :--- |
| **1. Manual Override Pinning** | `data/overrides.json` + Shadow-Cookie / `localStorage` pins | Always honors user-pinned Discogs gallery image URLs first across CLI and browser runs. |
| **2. 4-Corner Backdrop Uniformity** | Corner patches ($12\%$ width) vs. outer ring variance | Rejects square gatefold sleeves, lyric inserts, and full-bleed back covers. |
| **3. Annular 12" vs. 4" Radial Step ($r \approx 0.33$)** | Inner paper label ($r \in [0.08, 0.31]$) vs. wax groove ring ($r \in [0.36, 0.88]$) | Accepts full 12" vinyl discs showing both center label and wax ring; rejects zoomed-in 4" paper center-label scans. |
| **4. Deterministic Wax Shader Parser** | `parse_wax_variant()` over `formats[].descriptions` + notes | Renders an accurate procedural SVG/CSS wax ring around real Discogs center labels when no physical disc photo exists on Discogs. |

## 📂 Repository Structure

```text
discogs_collection/
├── .github/
│   └── workflows/
│       └── static.yml                     # Deploys static site to GitHub Pages
├── assets/
│   └── pressings/                         # Cached pressing photography & release assets
├── data/
│   ├── collection.json                    # Compiled 157-LP collection dataset & official Discogs valuation
│   ├── flattening_queue.json              # Portable thermal flattening queue ("Need to be done" / "Done")
│   ├── overrides.json                     # Per-release pinned pressing image overrides
│   └── sync_manifest.json                 # SHA-256 content digest & delta sync telemetry
├── scripts/
│   ├── sync_discogs.py                    # Single-command delta sync engine, valuation scrubber & HTML injector
│   ├── pick_pressing_photo.py             # Interactive local photo picker & override manager
│   ├── detect_pressing_image.py           # Deterministic 12" annular CV + Guideline 13.8 classifier + wax parser
│   ├── seed_collection.py                 # Offline deterministic collection builder
│   └── validate_collection.py             # Strict schema & URL integrity validator
├── tests/
│   └── test_deterministic_detector.py     # Unit tests for annular CV, Guideline 13.8, and wax code parsing
├── index.html                             # Self-contained v5.0 Command Stage + Shadow-Cookie Auto-Healer
├── publish.sh                             # Automated build, sync, and git publish helper script
└── requirements.txt                       # Python dependencies (Pillow, numpy, requests)
```

## 🚀 Running Locally & Syncing (`Windows 11` / `WSL` / `Linux`)

### 1. Single-Command Delta Sync (Recommended)
`scripts/sync_discogs.py` automatically discovers `DISCOGS_TOKEN` from your environment (or Windows/WSL environment variables), fetches only newly added or removed releases unless `--force` is passed, preserves your official Discogs Low/Med/High collection valuation, and keeps `<script id="krunked-cookie-vault-v1">` intact inside `index.html`:

```powershell
# Windows PowerShell (from C:\DiscogsCollection\discogs_collection)
$env:DISCOGS_TOKEN="your_discogs_personal_access_token"
python scripts/sync_discogs.py
```

```bash
# WSL / Linux / macOS
DISCOGS_TOKEN="your_discogs_personal_access_token" python3 scripts/sync_discogs.py
```

### 2. Full Re-Analysis & Interactive Photo Picker
```powershell
# Force full CV re-evaluation across all 157 releases
python scripts/sync_discogs.py --force --analyze-pixels

# Launch interactive local pressing photo selector
python scripts/pick_pressing_photo.py

# Run unit tests & schema validation
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/validate_collection.py data/collection.json
```

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Space` | Launch **SPIN THE CRATE** kinetic roulette reel in the active Smart Spin mode |
| `U` | Toggle **UV Blacklight Mode** (`🟣 UV Blacklight: ON` by default) |
| `F` | Flip the 3D Hero Turntable Deck between **Side A (Pressing Specs)** and **Side B (30s Studio Audio & Streaming)** |
| `←` / `→` | Step to the previous or next record in the flanking 3D crate wings |
| `/` | Focus the instant crate search and variant filter bar |
