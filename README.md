# 🎰 KRUNKED // DISCOGS VINYL VAULT (v5.0) — *"Vibe Coding a Discogs Collection Page to Not Look Like Trash"*

[GitHub Repo](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection)
[Live Vault](https://www.google.com/search?q=https://krunked-fpv.github.io/discogs_collection/)
[](https://www.discogs.com/user/krunked/collection)
[](#)

> ### *"Vibe coding a Discogs collection page to not look like trash."*
> — **The Core Tenet of KRUNKED // DISCOGS VINYL VAULT**

Standard collection trackers treat stunning splatter, galaxy, marble, and color-in-color vinyl pressings like boring spreadsheet rows or flat square JPEGs. **KRUNKED // DISCOGS VINYL VAULT (v5.0)** was built from the ground up around one guiding philosophy—**making a Discogs collection page that actually looks, sounds, and feels as wild as the physical wax in the crate**.

Built for [Alex Goresch's (`krunked`) Discogs Vinyl Collection](https://www.discogs.com/user/krunked/collection) (**Audio-Technica AT-LP70XBT** turntable + **AT-VMN95ML** Microlinear stylus + 18-speaker **"krunked homies"** setup) and deployed to [GitHub Pages (krunked-fpv.github.io/discogs\_collection)](https://www.google.com/search?q=https://krunked-fpv.github.io/discogs_collection/) from [krunked-fpv/discogs\_collection](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection), **v5.0** combines a **4-Pass Concentric Dual-Circle Computer Vision (CV) classifier** (`133 / 157` verified physical pressing photos) with a neon-soaked **Command Deck** featuring a unified **Kinetic Wax Roulette & Direct-Drive Pressing Stage**, **3 Smart Spin Modes**, a 4-LP **Variant Clash Arena** knockout bracket, default-on **UV Blacklight** reactive shaders, synthesized **Web Audio Analog SFX**, and a **3D Flip 30-Second Preview & Full-Album Streaming Deck** (`OLAK5uy_` YouTube Music + Spotify).

---

## 🚀 What's New in Version 5.0 (The Command Deck Fusion)

* **Unified Kinetic Wax Roulette & Direct-Drive Pressing Command Stage**:
  * **One Combined Stage**: Merges the **Spin-the-Crate Roulette Reel** directly into the **+25% Direct-Drive Turntable Stage** (`392×392px` cyan-bracketed plinth, `318×318px` spinning 12" vinyl platter, and animated S-shaped tonearm).
  * **`🎰 SPIN THE CRATE [SPACE]`**: Click the glowing magenta-to-cyan Roulette button (or tap `Spacebar` anywhere on the showcase) to fire a 26-step exponential-deceleration physics spin across your crate.
  * **3D Flanking Crate Wing Cards (`← Prev` / `Next →`)**: The adjacent records in your pool peek out from behind the left and right cyan-lit edges of the turntable plinth—displaying live wax color orbs, `Flat ✓` / `Warped ⚠️` / release-year badges, artist, title, and variant specs.
  * **🛡️ Automatic Stylus Guard**: Any record currently flagged under `Need to be done` in your thermal flattening queue is automatically locked out of Roulette and Arena spins so a warped disc never touches your `AT-VMN95ML` Microlinear stylus.

* **Three Smart Spin Modes (Directly Above the Platter)**:

| Smart Spin Mode | Badge | What It Does |
| :--- | :--- | :--- |
| **🎲 Full Vault Roulette** | `ALL SAFE (154)` | Spins across every stylus-safe (non-warped) pressing in your [Discogs Collection](https://www.discogs.com/user/krunked/collection). |
| **📺 Showroom Kiosk** | `AUTO 15s` | Hands-free living room / TV mode: keeps **UV Blacklight Mode** ignited and automatically spins a fresh pressing onto the platter every 15 seconds with a live countdown badge. |
| **🌈 Eye-Candy Variants** | `FLEX WAX` | Filters the roulette pool strictly to loud visual pressings—**Splatter, Galaxy, Marble Swirl, Split Wax, and Color-in-Color** discs only. |

* **⚔️ Variant Clash Arena (`#view-arena` — 4-LP Head-to-Head Knockout Bracket)**:
  * **3-Round Showdown**: Can't decide what to spin with Marisa or guests? Deals **4 stylus-safe pressings** into a head-to-head knockout bracket (**Semifinal 1 → Semifinal 2 → 🏆 Championship Final**).
  * **Custom Bracket Pools & In-Card Audio Auditions**: Filter contenders by **`🎲 All Safe`**, **`🌈 Eye-Candy Only`**, or **`✓ Flat Certified`**. Every contender card showcases its **real Discogs jacket cover + spinning pressing photo** side-by-side and includes an in-card **`🎧 Audition 30s`** button so you can preview studio audio before voting.
  * **Championship Lock-In**: Crowning tonight's champion triggers an 85-particle neon confetti explosion, plays a 5-voice analog synth fanfare, and loads the winner straight onto the main turntable platter.

* **🟣 UV Blacklight Mode (ON by Default • `Shortcut: U`) & Dynamic Ambient Glow**:
  * **Out-of-the-Box Ultraviolet Reactive Shader**: Boots directly into **UV Blacklight Mode** (`body.uv-blacklight`, `#030108` obsidian backdrop) with high-saturation neon drop-shadow shaders (`.uv-reactive`) across the spinning turntable platter, Arena contenders, and all 157 crate grid discs. Press `U` or click **`🟣 UV Blacklight: ON`** anytime to toggle standard studio lighting.
  * **Record-Matched Ambient Stage Backdrop**: Stepping through records or locking in a roulette winner smoothly transitions `--glow-primary`, `--glow-secondary`, and `--glow-accent` to match the active record's `wax_spec` colors.

* **🔊 Web Audio Analog SFX Synthesizer & 60-FPS Particle Burst Engine**:
  * **100% Native Web Audio Synthesis (Zero External MP3 Dependencies)**:
    * **Velocity-Scaled Crate Flip Ticks**: Triangle-wave mechanical sleeve clicks that decelerate in sync with the roulette wheel.
    * **Stylus Needle-Drop Thump**: Warm low-end analog cue thump (`98 Hz → 26 Hz`) when a winner locks onto the platter.
    * **Multi-Oscillator Win Chords & 60-FPS Particle Confetti**: Analog synth chords paired with a full-screen HTML5 Canvas particle burst (`#fx-particles-canvas`) in the winning record's exact wax palette.
    * **Continuous Warm Vinyl Crackle**: Bandpass-filtered (`1900 Hz`) analog surface noise via the platter's **`🔊 Vinyl Crackle`** button.

* **Official Discogs Collection Valuation (`Low $3,952.62 • Med $6,423.73 • High $11,091.69`)**:
  * Directly reflects and preserves your official [Discogs Collection Value API (`GET /users/krunked/collection/value`)](https://www.discogs.com/developers) historical sales valuation across the KPI telemetry strip and local sync pipeline without synthetic multiplier overrides.

---

## 🎵 3D Flip Streaming Deck & Core Vault Features (`Side A ⇄ Side B`)

* **Locked `516px` 3D Flip Card (`Shortcut: F`)**:
  * **Side A — Pressing Specs & Release Image Pinning (`#hero-face-front`)**: Displays full Discogs format strings, `Media / Sleeve` grading, individual release pricing, one-click flattening status cycling (`+ 🔥 Queue` → `✓ Mark Done`), and the interactive **Discogs Release Images Strip** where clicking any thumbnail pins it as that release's verified pressing photo.
  * **Side B — Clean 30-Second HTML5 Track Preview Player (`#hero-face-back`)**:
    * **Cross-Origin 30s Studio Previews (Zero YouTube Error 153 Boxes)**: Powered by native HTML5 `<audio>` (`#vault-preview-audio`) with iTunes Search API (`fetch` + JSONP fallback) and Deezer JSONP fallback, **strict zero autoplay on page load**, interactive track scrubbing, and continuous auto-advance (`🔁`).
    * **Side-by-Side Direct YouTube Music & Spotify Album Links (`157 / 157 Releases`)**: Every release resolves **`YT Music ↗`** directly to its official `OLAK5uy_...` album playlist on [YouTube Music](https://music.youtube.com/playlist?list=OLAK5uy_m80Evo-9vz_8XceYZ5xiRnlvifZRSAfCA) alongside a companion emerald **`Spotify ↗`** album button (`open.spotify.com/album/...`).

* **🔥 Portable Inline Vinyl Flattening Queue & 2.5-Hour Thermal Plate Timer**:
  * **100% Self-Contained State**: Stores your `Need to be done`, `Done`, and `Not Listed` records directly inside `#flattening-inline-form` hidden inputs in [index.html](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/index.html) and [data/flattening\_queue.json](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/data/flattening_queue.json).
  * **130°F Thermal Pouch Timer (`02:30:00`)**: Includes a **Stage 1 Ramp (`Setting 6 → 130°F`)** stopwatch, a **Stage 2 Hold (`Setting 4 • 2.5 Hours`)** countdown timer with Web Audio completion chime, and the **Owner Inspection Bench** for logging newly arrived LPs.

---

## 🧠 4-Tier Deterministic Pressing Selection Pipeline

When querying a release from the [Discogs Database Release endpoint (GET /releases/{release\_id})](https://www.google.com/search?q=https://www.discogs.com/developers/%23page:database,header:database-release), the `images[]` array only classifies images as `"type": "primary"` (front cover) or `"type": "secondary"` (back cover, gatefold inner, lyric insert, hype sticker, close-up 4" center label, or the 12" vinyl record itself).

To make sure the page never looks like a generic grid of square sleeves, [scripts/detect\_pressing\_image.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/detect_pressing_image.py) runs a **4-Tier Deterministic Pipeline**:

| Tier | Stage | Deterministic Mechanism |
| :--- | :--- | :--- |
| **Tier 1** | **Override Pinning (`data/overrides.json`)** | Locks a verified `assets/releases/<id>/pressing.jpg?v=...` path or manual `user_locked` `pressing_image_index` per `release_id`. Automatically purges stale auto-overrides if re-evaluated CV rejects a sticker or sleeve. |
| **Tier 2** | **4-Pass Concentric Dual-Circle CV (`score_image_pixels_deterministic`)** | Evaluates candidate images in polar coordinates $(r, \theta)$ on a normalized $256 \times 256$ grid across 4 framing passes to verify the outer 12" disc rim ($R_{\text{disc}} \in [0.65, 0.99]$), the 4 diagonal background quadrants, the 4" center label step ($r_{\text{label}} \approx R_{\text{disc}} / 3$), 8-octant label-to-wax color distance (`q25_oct_lbl_wax`), and the center spindle hole ($r \le 0.035$). |
| **Tier 3** | [**Discogs Guideline 13.8**](https://support.discogs.com/hc/en-us/articles/360005006874-Database-Guidelines-13-Images) **Positional Prior & Side-A Tie-Breaker** | Applies canonical Discogs image ordering rules (`[0]` front cover, `[1]` back cover / gatefold inner, `[2..3]` labels or inserts, `[4..5]` Side A/B physical disc) as an offline fallback when pixel dependencies are unavailable, and grants a `+0.038` tie-breaker bonus to the first verified physical disc (Side A). |
| **Tier 4** | **Deterministic Wax Variant Parser (`parse_wax_variant`)** | Parses `formats[].descriptions`, `formats[].text`, and `(THIS)` release notes (`Pur`, `Cle`, `Ult`, `Mil`, `Gho`, `Cok`, `Ele`, `Blu`, `Gre`, `Aci`, `Neo`, `Ora`, `Pea`, `Yel`, `Can`, `Pin`, `Vio`, `Mag`, `Gal`, `Gra`, `Dus`, `Hou`, `Splatter`, `Swirl`, `Marble`, `Split`, `Color-in-Color`, `Etched`) into a `wax_spec` object with a SHA-256 `deterministic_seed`. Guides CV candidate scoring (`variant_color_bonus`) and renders the procedural vinyl disc when `has_pressing_photo` is `false`. |

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

---

## ⌨️ Keyboard Shortcuts

| Key | Action |
| :---: | :--- |
| **`Space`** | Trigger **`🎰 SPIN THE CRATE`** kinetic roulette spin (when on the Showcase tab) |
| **`F`** | Flip the 3D Hero Card between **Side A (Pressing Specs)** and **Side B (Album Player & Tracklist)** |
| **`U`** | Toggle **🟣 UV Blacklight Mode** on/off across the entire vault |

---

## 📁 Repository Architecture

```text
discogs_collection/
├── .github/
│   └── workflows/
│       └── static.yml                 # GitHub Actions workflow deploying static build to GitHub Pages
├── assets/
│   ├── pressings/                     # Procedural fallback studio textures
│   └── releases/
│       └── <release_id>/              # Per-release cached Discogs gallery images (157 releases)
│           ├── cover.jpg              # Primary front sleeve artwork (copied from img_0.jpg)
│           ├── pressing.jpg           # Verified 12" vinyl pressing photo (133/157 releases)
│           └── img_0.jpg .. img_N.jpg # Raw candidate images from Discogs GET /releases/{id}
├── data/
│   ├── collection.json                # Compiled schema v5.0.0 dataset for user `krunked` (157 LPs)
│   ├── releases_cache.json            # Incremental Discogs /releases/{id} metadata & image cache
│   ├── overrides.json                 # Per-release verified pressing paths & user-locked pins
│   ├── flattening_queue.json          # Portable Vinyl Flattening Queue (synced with inline HTML form)
│   └── sync_manifest.json             # SHA-256 content digest, record counts, & sync timestamp
├── scripts/
│   ├── sync_discogs.py                # Unified v5.0 Delta Sync, CV Photo Picker, & HTML Compiler
│   ├── pick_pressing_photo.py         # Local/Offline CV photo selector & HTML KPI/Form injector
│   ├── detect_pressing_image.py       # 4-Pass polar CV classifier, wax parser, YTM playlist map, & queue reconciler
│   ├── setup_discogs_token.py         # Windows HKCU Registry + .env token installer & repo scrubber
│   ├── seed_collection.py             # Offline deterministic collection seed builder
│   └── validate_collection.py         # Schema v5.0.0 & Discogs URL integrity validator
├── .env                               # Local git-ignored credentials (DISCOGS_USERNAME / DISCOGS_TOKEN)
├── index.html                         # Self-contained v5.0 Kinetic Wax Roulette, Variant Clash Arena, UV Blacklight & 3D Flip Deck
└── requirements.txt                   # Python dependencies (Pillow, numpy)
```

---

## ⚡ Local Workstation Setup & Daily Workflow (v5.0)

### 1. Prerequisites & One-Time Token Setup

```powershell
cd C:\DiscogsCollection\discogs_collection
pip install -r requirements.txt
python scripts/setup_discogs_token.py
```

### 2. Daily Incremental Sync & GitHub Pages Deploy

Whenever you add new records to your [Discogs collection](https://www.discogs.com/user/krunked/collection) or update your flattening queue in [index.html](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/index.html), run the unified single-command pipeline:

```powershell
cd C:\DiscogsCollection\discogs_collection
python scripts/sync_discogs.py
git add -A; git commit -m "chore(vault): sync discogs collection (v5.0)"; git push
```

### 3. Targeted Release Resync or Full CV Rebuild

```powershell
# Force re-download & re-run 4-pass CV on specific release ID(s)
python scripts/sync_discogs.py --resync 35668090,16610055

# Bypass SHA-256 delta fast-path and re-evaluate all 157 releases
python scripts/sync_discogs.py --full
```

---

## 🛠️ Script Reference & CLI Flags

| Script | Primary Role | Key CLI Arguments |
| :--- | :--- | :--- |
| [scripts/sync\_discogs.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/sync_discogs.py) | Unified v5.0 pipeline: paginates Folder 0, syncs official Discogs Low/Med/High collection valuation, runs SHA-256 delta checks, downloads new gallery images, runs 4-pass CV selection, extracts tracklists & album links, reconciles inline HTML flattening state, and compiles `index.html`. | `--full` (`-f`), `--resync <id1,id2>`, `--username`, `--token`, `--output`, `--cache`, `--overrides`, `--flattening`, `--assets-dir`, `--inject-html` |
| [scripts/pick\_pressing\_photo.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/pick_pressing_photo.py) | Standalone local/offline delta photo picker and HTML injector (called automatically at the end of `sync_discogs.py`, or runnable directly with `--offline`). | `--full` (`-f`), `--resync <id1,id2>`, `--offline`, `--collection`, `--cache`, `--overrides`, `--flattening`, `--assets-dir`, `--inject-html` |
| [scripts/detect\_pressing\_image.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/detect_pressing_image.py) | Core deterministic library containing `score_image_pixels_deterministic()`, `select_release_images_deterministic()`, `parse_wax_variant()`, `VERIFIED_YTM_RELEASE_MAP` (157/157 album playlists), `extract_release_tracklist_and_videos()`, `reconcile_flattening_state()`, and `VaultTerminalUI`. | Imported by `sync_discogs.py`, `pick_pressing_photo.py`, and `seed_collection.py` |
| [scripts/setup\_discogs\_token.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/setup_discogs_token.py) | Interactive credential installer that sanitizes pasted tokens, writes `.env` + `HKCU\Environment`, updates `.gitignore`, and scrubs exposed tokens from repo files. | `python scripts/setup_discogs_token.py` |
| [scripts/validate\_collection.py](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection/blob/main/scripts/validate_collection.py) | Verifies `REQUIRED_RECORD_KEYS`, `https://www.discogs.com/release/` URLs, `wax_spec` completeness, and `delta_sig` coverage. | `python scripts/validate_collection.py [path/to/collection.json]` |