# 🎰 KRUNKED // DISCOGS VINYL VAULT `v5.0`
### *Kinetic Wax Roulette • Variant Clash Arena • UV Blacklight Shader • 4-Pass Polar CV • Full-Album Streaming Deck*

[Live Vault Showcase](https://www.google.com/search?q=https://krunked-fpv.github.io/discogs_collection/)
[](https://www.discogs.com/user/krunked/collection)
[](#)
[](#)

Welcome to **v5.0** of the **[KRUNKED // DISCOGS VINYL VAULT](https://www.google.com/search?q=https://github.com/krunked-fpv/discogs_collection)**—where a deterministic Python computer-vision pipeline meets a neon-soaked audiophile command deck built for an **Audio-Technica AT-LP70XBT** turntable (`AT-VMN95ML` Microlinear stylus) and 18-speaker **"krunked homies"** whole-home playback.

Version 5.0 fuses the best of the **Wax Roulette Command Deck** directly into the production Vinyl Vault: a unified **Kinetic Wax Roulette & Direct-Drive Pressing Command Stage**, **3 Smart Spin Modes**, a 4-LP **Variant Clash Arena** knockout bracket, a reactive **UV Blacklight** shader, and a zero-dependency **Web Audio Analog SFX + 60-FPS Particle Burst Engine**—all while keeping the 3D Flip Music Player, Pressing Spec inspector, and single-command delta sync intact.

---

## 🚀 What's New in `v5.0` (The Mind-Blower Update)

### 1. 🎰 Unified Kinetic Wax Roulette & Direct-Drive Pressing Command Stage
No more jumping between separate stages—the **3D Crate Reel** and the **Direct-Drive Turntable Plinth** now live together on one unified centerpiece stage:
- **`🎰 SPIN THE CRATE [SPACE]`**: Smash the glowing magenta-to-cyan Roulette button (or tap `Spacebar` anywhere on the showcase) to launch a 26-step exponential-deceleration spin across your collection.
- **3D Flanking Crate Wing Cards**: The previous and next records in your active pool peek out from behind the left and right cyan-lit edges of the turntable plinth—complete with live wax color orbs, `Flat ✓` / `Warped ⚠️` / release-year badges, and variant specs. Click either wing card to step through the crate.
- **🛡️ Automatic Stylus Guard**: Any record currently flagged under `Need to be done` in your thermal flattening queue is automatically locked out of roulette spins so a warped disc never touches your Microlinear stylus.

### 2. 🧠 Three Smart Spin Modes (Directly Above the Platter)
Pick how the vault deals your next spin with one click right above the turntable:
| Smart Spin Mode | Badge | What It Does |
| :--- | :--- | :--- |
| **🎲 Full Vault Roulette** | `ALL SAFE` | Spins across every stylus-safe (non-warped) pressing in your [Discogs Collection](https://www.discogs.com/user/krunked/collection). |
| **📺 Showroom Kiosk** | `AUTO 15s` | Hands-free living room / TV mode: automatically ignites **UV Blacklight Mode** and spins a fresh variant onto the platter every 15 seconds with a live countdown badge. |
| **🌈 Eye-Candy Variants** | `FLEX WAX` | Filters the roulette pool strictly to loud visual pressings—**Splatter, Galaxy, Marble Swirl, Split Wax, and Color-in-Color** discs only. |

### 3. ⚔️ Variant Clash Arena (4-LP Head-to-Head Knockout Bracket)
Can't decide what to spin with Marisa or guests? Switch to the **`⚔️ Variant Clash Arena`** tab in the top Command Deck bar:
- Deals **4 stylus-safe pressings** into a 3-round knockout bracket (**Semifinal 1 → Semifinal 2 → 🏆 Championship Final**).
- Filter the bracket pool by **`🎲 All Safe`**, **`🌈 Eye-Candy Only`**, or **`✓ Flat Certified`**.
- Every contender card displays its **real Discogs jacket cover + spinning pressing photo** side-by-side AND includes an in-card **`🎧 Audition 30s`** button so you can preview studio audio before casting your vote.
- Crowning the champion fires an 85-particle neon confetti burst, plays a 5-voice synth fanfare, and lets you load the winner straight onto the main turntable stage.

### 4. 🟣 UV Blacklight Toggle (`Shortcut: U`) & Dynamic Ambient Backdrop
- **Dynamic Ambient Stage Glow**: As you step through records or lock in a roulette winner, the page's ambient radial backdrop (`--glow-primary`, `--glow-secondary`, `--glow-accent`) smoothly morphs to match the active record's exact `wax_spec` palette.
- **UV Blacklight Mode (`🟣 UV Blacklight: ON`)**: Flip the header toggle (or press `U`) to drop the room into deep `#030108` ultraviolet obsidian and apply a high-saturation neon drop-shadow shader (`.uv-reactive`) across the spinning platter, Arena contenders, and all 157 crate grid discs.

### 5. 🔊 Web Audio Analog SFX Synthesizer & 60-FPS Particle Engine
Zero external MP3 sound files required—every sound is synthesized in real time via the browser's native **Web Audio API** (and can be muted anytime via **`🔊 Analog SFX: On/Off`**):
- **Mechanical Crate Flip Ticks**: Velocity-scaled triangle-wave sleeve clicks that speed up and slow down in sync with the roulette physics wheel.
- **Stylus Needle-Drop Thump**: Warm low-end analog cue thump (`98 Hz → 26 Hz`) whenever a record locks onto the platter.
- **Roulette & Arena Synth Chords**: Multi-oscillator analog chords paired with a **60-FPS HTML5 Canvas Particle Burst** (`#fx-particles-canvas`) matched to the winning record's wax colors.
- **UV Tube Ignition Sweep**: Fluorescent starter sweep when toggling UV Blacklight mode.
- **Continuous Warm Vinyl Crackle**: Bandpass-filtered (`1900 Hz`) analog surface noise & micro-pops via the platter's **`🔊 Vinyl Crackle`** button.

---

## 🎵 Preserved Core Architecture (Untouched & Rock-Solid)

### Side A / Side B 3D Flip Deck (`Shortcut: F`)
- **Side A — Pressing Specs & Release Image Pinning**: Displays full Discogs format strings, `Media / Sleeve` grading, marketplace valuation, quick flattening status cycling (`+ 🔥 Queue` → `✓ Mark Done`), and the interactive **Discogs Release Images Strip** where clicking any thumbnail pins it as that record's verified pressing photo.
- **Side B — 30-Second Studio Preview Player & Official Album Links**:
  - **In-Page 30s Audio Previews**: Uses HTML5 `<audio>` backed by the iTunes Search API (`fetch` + JSONP fallback) and Deezer JSONP fallback with **zero autoplay**, interactive track scrubbing, and continuous auto-advance (`🔁`).
  - **Verified Full-Album Streaming Links**: Side-by-side **`YT Music ↗`** (locked to official `OLAK5uy_...` album playlists across all 157 releases) and **`Spotify ↗`** (`open.spotify.com/album/...`) deep links.

### 🔥 Portable Inline Vinyl Flattening Queue & 2.5-Hour Thermal Plate Timer
- **Zero Cloud Lock-In**: Your `Need to be done`, `Done`, and `Not Listed` inspection states live directly inside hidden HTML form inputs (`#flattening-inline-form`) in `index.html` and `data/flattening_queue.json`.
- **Thermal Pouch Regimen (`130°F • 2.5h`)**: Built-in **Stage 1 Ramp (`Setting 6 → 130°F`)** stopwatch and **Stage 2 Hold (`Setting 4 • 02:30:00`)** countdown timer with Web Audio completion chime.
- **Owner Inspection Bench**: Search uninspected LPs on arrival and queue warped pressings or log completed bakes in one click.

---

## ⚡ Daily Local Sync Workflow (`C:\DiscogsCollection\discogs_collection`)

The Python sync suite (`scripts/sync_discogs.py`) uses the **v5.0 Incremental Delta Engine** to compare your live [Discogs API](https://www.discogs.com/developers) Folder 0 collection against your local cache—skipping unchanged releases in microseconds (~70x faster) and running image downloads + **4-Pass Polar Computer Vision** (`detect_pressing_image.py`) only on new or resynced LPs.

### 1. Standard Daily Sync & GitHub Pages Deploy (PowerShell)
```powershell
cd C:\DiscogsCollection\discogs_collection
python scripts/sync_discogs.py
git add -A; git commit -m "chore(vault): sync discogs collection (v5.0)"; git push
```

### 2. Targeted Release Resync or Full Vault Rebuild
```powershell
# Force re-download & re-evaluate specific Discogs release ID(s):
python scripts/sync_discogs.py --resync 35668090,16610055

# Bypass the SHA-256 delta cache and re-run 4-Pass CV across all 157+ LPs:
python scripts/sync_discogs.py --full
```

### 3. Saving In-Browser Pressing Pins or Flattening Edits
Whenever you pin a new pressing photo from the gallery strip or update your Flattening Queue in the browser:
1. Click **`Sync & Export LP's`** in the top-right header (or **`💾 Save Updated index.html`** in the Flattening tab).
2. Drop the downloaded self-contained `index.html` into `C:\DiscogsCollection\discogs_collection\index.html`.
3. On your next `python scripts/sync_discogs.py` run, the Python engine automatically reads your updated inline form state and reconciles `data/flattening_queue.json` and `data/overrides.json`.

---

## ⌨️ Keyboard Shortcuts

| Key | Action |
| :---: | :--- |
| **`Space`** | Trigger **`🎰 SPIN THE CRATE`** kinetic roulette spin (when on the Showcase tab) |
| **`F`** | Flip the 3D Hero Card between **Side A (Pressing Specs)** and **Side B (Album Player & Tracklist)** |
| **`U`** | Toggle **🟣 UV Blacklight Mode** on/off across the entire vault |

---

## 🗂️ Repository Layout

```text
C:\DiscogsCollection\discogs_collection\
├── index.html                      # Self-contained v5.0 Command Deck & Vinyl Vault (157 LPs compiled inline)
├── README.md                       # v5.0 Architecture, Roulette, Arena & Sync documentation
├── assets/
│   └── releases/<release_id>/      # Local cached Discogs images (cover.jpg, pressing.jpg, img_0..N.jpg)
├── data/
│   ├── collection.json             # Compiled collection payload, valuation & wax_spec metadata
│   ├── overrides.json              # Verified & user-locked pressing photo overrides
│   ├── flattening_queue.json       # Portable thermal flattening queue state
│   ├── releases_cache.json         # Cached Discogs release API responses
│   └── sync_manifest.json          # SHA-256 sync telemetry & collection counters
└── scripts/
    ├── sync_discogs.py             # Single-command v5.0 Incremental Delta Sync & HTML compiler
    ├── pick_pressing_photo.py      # Pressing photo verifier, override manager & HTML injector
    ├── detect_pressing_image.py    # 4-Pass Polar CV engine, format parser & terminal turntable UI
    ├── setup_discogs_token.py      # Interactive token setup helper (.env / Windows HKCU Registry)
    ├── seed_collection.py          # Offline baseline seeder
    └── validate_collection.py      # Integrity checker for collection JSON & local assets
```
