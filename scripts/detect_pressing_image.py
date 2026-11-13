#!/usr/bin/env python3
"""Deterministic Pressing Image Classifier, Vinyl Wax Variant Parser & Flattening Matcher.

Uses 100% deterministic rules to:
1. Identify which image in a Discogs Release `images[]` array depicts the
   physical 12" vinyl pressing itself (vs. front sleeve cover, back cover tracklist,
   square inner sleeve / lyric insert, die-cut inner sleeve, sleeve+disc mockup,
   gatefold spread, square/circular hype stickers, or close-up 4" paper center label),
   supporting both square (1:1) and 4:3 / 3:4 camera photos of vinyl pressings.
2. Parse Discogs `formats[].descriptions`, `formats[].text`, and release notes
   into a deterministic `wax_spec` object for procedural vinyl rendering and
   seed-guided candidate scoring when a release has multiple or zero pressing photos.
3. Match releases deterministically against the Google Keep 'Vinyl flattening'
   queue (`data/flattening_queue.json`).

References:
- Discogs API Release Resource: https://www.discogs.com/developers/#page:database,header:database-release
- Discogs Database Guidelines 13.8 (Image Order): https://support.discogs.com/hc/en-us/articles/360005006874-Database-Guidelines-13-Images
"""

from __future__ import annotations

import hashlib
import io
import pathlib
import re
import subprocess
import sys
from typing import Any

HAS_CV_DEPS = False
try:
    import numpy as np
    from PIL import Image
    HAS_CV_DEPS = True
except ImportError:
    # Automatically bootstrap pillow + numpy if missing on local Windows/Linux Python environment
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "pillow", "numpy"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=90,
        )
        import numpy as np
        from PIL import Image
        HAS_CV_DEPS = True
    except Exception:
        HAS_CV_DEPS = False


DISCOGS_COLOR_MAP: dict[str, tuple[str, str, bool]] = {
    "pur": ("#8b2cf5", "Purple", True),
    "purple": ("#8b2cf5", "Purple", True),
    "purplish": ("#8b2cf5", "Purple", True),
    "vio": ("#6d28d9", "Violet", True),
    "violet": ("#6d28d9", "Violet", True),
    "pin": ("#ec4899", "Hot Pink", False),
    "pink": ("#ec4899", "Hot Pink", False),
    "pinkish": ("#ec4899", "Hot Pink", False),
    "mag": ("#d946ef", "Magenta", True),
    "magenta": ("#d946ef", "Magenta", True),
    "ora": ("#f97316", "Translucent Orange", True),
    "orange": ("#f97316", "Translucent Orange", True),
    "pea": ("#fb923c", "Peach Opaque", False),
    "peach": ("#fb923c", "Peach Opaque", False),
    "yel": ("#eab308", "Yellow", True),
    "yellow": ("#eab308", "Yellow", True),
    "yellowish": ("#eab308", "Yellow", True),
    "can": ("#facc15", "Canary Yellow", False),
    "canary": ("#facc15", "Canary Yellow", False),
    "gold": ("#d97706", "Metallic Gold", False),
    "amber": ("#d97706", "Amber Translucent", True),
    "gre": ("#10b981", "Emerald Green", True),
    "green": ("#10b981", "Emerald Green", True),
    "greenish": ("#10b981", "Emerald Green", True),
    "olive": ("#65a30d", "Olive Green", False),
    "aci": ("#84cc16", "Acid Green", True),
    "acid": ("#84cc16", "Acid Green", True),
    "neo": ("#ccff00", "Neon Highlighter", True),
    "neon": ("#ccff00", "Neon Highlighter", True),
    "blu": ("#2563eb", "Cobalt Blue", True),
    "blue": ("#2563eb", "Cobalt Blue", True),
    "bluish": ("#2563eb", "Cobalt Blue", True),
    "ele": ("#06b6d4", "Electric Blue", True),
    "electric": ("#06b6d4", "Electric Blue", True),
    "cyan": ("#06b6d4", "Cyan", True),
    "teal": ("#0d9488", "Teal", True),
    "turquoise": ("#06b6d4", "Turquoise", True),
    "aqua": ("#06b6d4", "Aqua", True),
    "lig": ("#38bdf8", "Light Sky Blue", True),
    "cle": ("#cbd5e1", "Crystal Clear", True),
    "clear": ("#cbd5e1", "Crystal Clear", True),
    "ult": ("#e2e8f0", "Ultra Clear", True),
    "mil": ("#f1f5f9", "Milky Clear", True),
    "milk": ("#f1f5f9", "Milky Clear", True),
    "milky": ("#f1f5f9", "Milky Clear", True),
    "gho": ("#94a3b8", "Ghostly Clear", True),
    "ghost": ("#94a3b8", "Ghostly Clear", True),
    "ghostly": ("#94a3b8", "Ghostly Smoke", True),
    "smoke": ("#64748b", "Translucent Smoke", True),
    "smoky": ("#64748b", "Translucent Smoke", True),
    "smokey": ("#64748b", "Translucent Smoke", True),
    "cok": ("#5eead4", "Coke Bottle Clear", True),
    "coke": ("#5eead4", "Coke Bottle Clear", True),
    "whi": ("#f8fafc", "Opaque White", False),
    "white": ("#f8fafc", "Opaque White", False),
    "bone": ("#fef3c7", "Bone White", False),
    "cream": ("#fef3c7", "Cream White", False),
    "tan": ("#d6d3d1", "Tan Translucent", True),
    "gra": ("#64748b", "Graphite Grey", False),
    "grey": ("#64748b", "Graphite Grey", False),
    "gray": ("#64748b", "Graphite Grey", False),
    "sil": ("#94a3b8", "Metallic Silver", False),
    "silver": ("#94a3b8", "Metallic Silver", False),
    "dus": ("#a8a29e", "Dusty Smoke", True),
    "dust": ("#a8a29e", "Dusty Smoke", True),
    "dusk": ("#a8a29e", "Dusk Ripple", True),
    "hou": ("#3b82f6", "House Blue/Cyan Swirl", True),
    "gal": ("#4f46e5", "Galaxy Nebula", True),
    "galaxy": ("#4f46e5", "Galaxy Nebula", True),
    "blood": ("#dc2626", "Blood Pool Red", True),
    "oxblood": ("#9f1239", "Oxblood Red", True),
    "red": ("#dc2626", "Crimson Red", True),
    "reddish": ("#dc2626", "Reddish Translucent", True),
    "crimson": ("#dc2626", "Crimson Red", True),
    "ruby": ("#e11d48", "Ruby Red", True),
    "burgundy": ("#9f1239", "Burgundy Red", True),
    "maroon": ("#881337", "Maroon Red", False),
    "bla": ("#18181b", "180g Audiophile Black", False),
    "black": ("#18181b", "180g Audiophile Black", False),
}


def _extract_relevant_notes(comments: str) -> str:
    """Filters out other pressings in multi-pressing Discogs release notes by prioritizing '(THIS)' lines."""
    if not comments:
        return ""
    lines = [ln.strip() for ln in comments.splitlines() if ln.strip()]
    this_lines = [ln for ln in lines if re.search(r"\(\s*this\s*\)", ln, flags=re.IGNORECASE)]
    if this_lines:
        return " ".join(this_lines)
    return comments


def parse_wax_variant(
    format_str: str,
    comments: str = "",
    release_id: int | str = 0,
) -> dict[str, Any]:
    """Deterministically parses a Discogs format string + notes into a visual wax spec."""
    filtered_comments = _extract_relevant_notes(comments)
    fmt_lower = (format_str or "").lower()
    combined = f"{format_str} {filtered_comments}".strip()
    lower = combined.lower()

    tokens = [
        t.strip().lower()
        for t in re.split(r"[,()+/:\s\[\]-]+", format_str)
        if t.strip()
    ]

    matched_colors: list[tuple[str, str, bool]] = []
    seen_hex: set[str] = set()

    # Special compound variant phrases (e.g., "Blood Pool", "Ghostly Black")
    if "blood pool" in lower:
        matched_colors.append(("#dc2626", "Blood Pool Red", True))
        matched_colors.append(("#f8fafc", "Ghostly White", True))
        seen_hex.update({"#dc2626", "#f8fafc"})
    elif "ghostly black" in lower:
        matched_colors.append(("#18181b", "Ghostly Black", True))
        matched_colors.append(("#94a3b8", "Ghostly Smoke", True))
        seen_hex.update({"#18181b", "#94a3b8"})

    for tok in tokens:
        if tok in DISCOGS_COLOR_MAP:
            hex_c, name, trans = DISCOGS_COLOR_MAP[tok]
            if hex_c not in seen_hex:
                matched_colors.append((hex_c, name, trans))
                seen_hex.add(hex_c)

    color_words = [
        (r"blood\s+pool", "#dc2626", "Blood Pool Red", True),
        (r"milky\s+in\s+clear", "#f1f5f9", "Milky in Clear", True),
        (r"red(?:dish)?|blood", "#dc2626", "Crimson Red", True),
        (r"ruby", "#e11d48", "Ruby Red", True),
        (r"burgundy|maroon|oxblood", "#9f1239", "Burgundy Red", True),
        (r"purp(?:le|lish)", "#8b2cf5", "Purple", True),
        (r"violet", "#6d28d9", "Violet", True),
        (r"yellow(?:ish)?", "#facc15", "Yellow", True),
        (r"pink(?:ish)?", "#ec4899", "Hot Pink", False),
        (r"magenta", "#d946ef", "Magenta", True),
        (r"cyan|turquoise|aqua", "#06b6d4", "Cyan", True),
        (r"blu(?:e|ish)", "#2563eb", "Electric Blue", True),
        (r"green(?:ish)?", "#10b981", "Emerald Green", True),
        (r"olive", "#65a30d", "Olive Green", False),
        (r"orange", "#f97316", "Translucent Orange", True),
        (r"ghost(?:ly)?", "#94a3b8", "Ghostly Smoke", True),
        (r"smok(?:e|y|ey)", "#64748b", "Translucent Smoke", True),
        (r"milky", "#f1f5f9", "Milky Clear", True),
        (r"clear", "#cbd5e1", "Crystal Clear", True),
        (r"white", "#f8fafc", "Opaque White", False),
        (r"bone|cream", "#fef3c7", "Bone White", False),
        (r"gold|amber", "#eab308", "Metallic Gold", False),
        (r"silver", "#94a3b8", "Silver", False),
        (r"black", "#18181b", "180g Audiophile Black", False),
    ]

    # First scan format_str so explicit format colors always take priority over release notes
    for pat, hex_c, label, trans in color_words:
        if re.search(rf"\b{pat}\b", fmt_lower) and hex_c not in seen_hex:
            matched_colors.append((hex_c, label, trans))
            seen_hex.add(hex_c)

    # Only fall back to filtered_comments if format_str had no color or only 1 color
    if len(matched_colors) < 2 and filtered_comments:
        notes_lower = filtered_comments.lower()
        for pat, hex_c, label, trans in color_words:
            if re.search(rf"\b{pat}\b", notes_lower) and hex_c not in seen_hex:
                matched_colors.append((hex_c, label, trans))
                seen_hex.add(hex_c)

    if not matched_colors:
        matched_colors.append(("#18181b", "180g Audiophile Black", False))

    primary_hex, primary_name, is_trans = matched_colors[0]
    if len(matched_colors) >= 2:
        secondary_hex = matched_colors[1][0]
    else:
        if primary_hex == "#18181b":
            secondary_hex = "#3f3f46"
        elif primary_hex in ("#cbd5e1", "#e2e8f0", "#f1f5f9", "#f8fafc", "#94a3b8"):
            secondary_hex = "#38bdf8"
        else:
            secondary_hex = "#18181b"

    if len(matched_colors) >= 3:
        accent_hex = matched_colors[2][0]
    else:
        accent_hex = "#f43f5e" if primary_hex not in ("#dc2626", "#e11d48", "#ec4899") else "#facc15"

    etched = bool(re.search(r"\betch", lower))

    pattern_source = fmt_lower if re.search(
        r"splatter|starburst|blood pool|in clear|color-in-color|ripple|gal|galaxy|nebula|dus|dust|dusk|gho|ghost|ghostly|smoke|smoky|swirl|marb|marble|split|smash|twister|cle|ult|mil|cok|clear|translucent",
        fmt_lower,
    ) else lower

    if re.search(r"splatter|starburst|blood pool", pattern_source):
        pattern = "splatter"
    elif re.search(r"in clear|color-in-color|milky in clear|bone in|pink in|black in|red in|ripple", pattern_source):
        pattern = "color_in_color"
    elif re.search(r"\b(gal|galaxy|nebula|dus|dust|dusk|gho|ghost|ghostly|smoke|smoky|smokey|cloudy|glitter|starlight)\b", pattern_source):
        pattern = "galaxy"
    elif re.search(r"\b(swirl|marb|marble|hou|aci|acid)\b", pattern_source):
        pattern = "marble"
    elif re.search(r"\b(split|smash|twister|flip|neo|neon|fun dip)\b", pattern_source):
        pattern = "split"
    elif is_trans or re.search(r"\b(cle|ult|mil|cok|clear|translucent)\b", pattern_source):
        pattern = "translucent"
    elif primary_hex == "#18181b":
        pattern = "black"
    else:
        pattern = "solid_color"

    is_2lp = "2xlp" in lower or "2x12" in lower or "2xvinyl" in lower or "+ lp" in lower or "+ vinyl" in lower
    is_ltd = "ltd" in lower or "limited" in lower
    is_repress = "rp" in lower or "re" in lower or "reissue" in lower or "repress" in lower

    parts = ["2xLP" if is_2lp else "12\" LP"]
    if len(matched_colors) > 1 and matched_colors[1][1] != primary_name and matched_colors[1][0] != "#18181b":
        parts.append(f"{primary_name} + {matched_colors[1][1]}")
    else:
        parts.append(primary_name)

    if pattern == "splatter":
        parts.append("Splatter")
    elif pattern == "galaxy":
        parts.append("Galaxy")
    elif pattern == "color_in_color":
        parts.append("Color-in-Color")
    elif pattern == "marble":
        parts.append("Marble Swirl")
    elif pattern == "split":
        parts.append("Split Swirl")

    if etched:
        parts.append("Etched Side")
    if is_ltd:
        parts.append("Ltd Ed")

    seed_int = int(hashlib.sha256(str(release_id).encode()).hexdigest()[:8], 16)

    return {
        "pattern": pattern,
        "primary_color": primary_hex,
        "secondary_color": secondary_hex,
        "accent_color": accent_hex,
        "color_name": primary_name,
        "translucent": is_trans,
        "etched": etched,
        "is_double_lp": is_2lp,
        "is_limited": is_ltd,
        "is_repress": is_repress,
        "variant_badge": " • ".join(parts),
        "deterministic_seed": seed_int,
    }


def _hex_to_rgb01(hex_str: str) -> tuple[float, float, float]:
    h = (hex_str or "#18181b").lstrip("#")
    if len(h) != 6:
        return (0.1, 0.1, 0.1)
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def score_image_pixels_deterministic(
    image_bytes: bytes,
    expected_wax_hex: str | None = None,
    secondary_wax_hex: str | None = None,
    wax_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministically scores an image for whether it shows a physical 12" vinyl record pressing.

    Uses Calibrated Multi-Scale Concentric Dual-Circle Detection + 8-Octant Label Continuity:
    1. Normalizes coordinates by true half-frame (127.5) so full-bleed 12" vinyl discs
       (`R_disc in [0.80..0.99]`) are accurately detected along all 4 diagonal quadrants.
    2. Searches for the physical 1/3 center-label-to-disc boundary (`R_label in [0.26..0.36] * R_disc`)
       separating the 4" paper center label from the 12" vinyl wax annulus, and verifies
       8-octant continuity around the 360-degree label boundary (`q25_oct_lbl_wax`).
    3. Explicitly detects and rejects:
       - Die-cut inner sleeves with blank paper center holes (e.g., `38268432/img_4, img_5`, `28895677/img_1`).
       - Off-center sleeve + half-disc promotional mockups (e.g., `27717681/img_2`).
       - Zoomed-in 4" paper center label close-ups on colored or black vinyl
         (e.g., `27066432/img_4, img_5`, `38268432/img_6..9`, `28895677/img_5, img_6`).
       - Square AND circular hype stickers, barcode stickers, and text-heavy lyric inserts
         (e.g., `14188877/img_4, img_5, img_6`, `28895677/img_9`, `37058814/img_2`, `28269505/img_3`).
    4. Scores verified disc candidates against the deterministic `wax_spec` seed (primary/secondary
       wax colors and ghostly/translucent/splatter texture profile).
    """
    if not HAS_CV_DEPS:
        return {"is_pressing": False, "score": 0.0, "reason": "cv_deps_unavailable"}

    try:
        with Image.open(io.BytesIO(image_bytes)) as im:
            w, h = im.size
            aspect = w / float(h) if h else 0.0
            if aspect < 0.72 or aspect > 1.38:
                return {
                    "is_pressing": False,
                    "score": 0.05,
                    "aspect_ratio": round(aspect, 3),
                    "reason": "rejected_aspect_ratio_panoramic_or_strip",
                }
            rgb_full = im.convert("RGB")
            if abs(aspect - 1.0) > 0.06:
                side = min(w, h)
                left = (w - side) // 2
                top = (h - side) // 2
                rgb_cropped = rgb_full.crop((left, top, left + side, top + side))
            else:
                rgb_cropped = rgb_full
            rgb = np.asarray(rgb_cropped.resize((256, 256), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
    except Exception:
        return {"is_pressing": False, "score": 0.0, "reason": "image_decode_error"}

    gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    sat = np.max(rgb, axis=2) - np.min(rgb, axis=2)

    # Normalize by 127.5 so r=1.0 is the inscribed circle touching the square frame edges
    yy, xx = np.mgrid[0:256, 0:256]
    dy = (yy - 127.5) / 127.5
    dx = (xx - 127.5) / 127.5
    r = np.hypot(dx, dy)
    theta = np.arctan2(dy, dx)

    gy, gx = np.gradient(gray)
    grad_r = np.abs(gx * np.cos(theta) + gy * np.sin(theta))
    grad_t = np.abs(-gx * np.sin(theta) + gy * np.cos(theta))
    grad_mag = np.hypot(gx, gy)
    pure_rad = np.maximum(0.0, grad_r - 0.55 * grad_t)

    # 4 Diagonal Quadrant Masks (avoiding 0/90/180/270 deg where square borders live)
    abs_cos = np.abs(np.cos(theta))
    abs_sin = np.abs(np.sin(theta))
    diag_mask = (abs_cos >= 0.35) & (abs_sin >= 0.35)
    q_masks = [
        diag_mask & (dx > 0) & (dy > 0),
        diag_mask & (dx < 0) & (dy > 0),
        diag_mask & (dx < 0) & (dy < 0),
        diag_mask & (dx > 0) & (dy < 0),
    ]

    best_r_disc = 0.96
    best_dual_circle_score = -1.0
    best_active_quads = 0
    best_rim_step = 0.0
    best_label_step = 0.0
    best_label_wax_dist = 0.0
    best_corner_wax_dist = 0.0
    best_corner_std = 1.0
    best_r_lbl = 0.32
    best_color_in_color_dist = 0.0

    for r_cand in np.linspace(0.80, 0.99, 20):
        rim_diag_band = (r >= r_cand - 0.024) & (r <= r_cand + 0.024) & diag_mask
        diag_rad_e = float(np.mean(pure_rad[rim_diag_band]))

        active_quads = 0
        q_dists: list[float] = []
        q_stds_out: list[float] = []
        for qm in q_masks:
            in_q = (r >= r_cand - 0.14) & (r <= r_cand - 0.03) & qm
            out_q = (r >= r_cand + 0.035) & (r <= min(1.36, r_cand + 0.24)) & qm
            rim_q = (r >= r_cand - 0.024) & (r <= r_cand + 0.024) & qm
            if not np.any(in_q) or not np.any(out_q):
                continue
            mean_in = np.mean(rgb[in_q], axis=0)
            mean_out = np.mean(rgb[out_q], axis=0)
            dist_q = float(np.linalg.norm(mean_in - mean_out))
            std_out_q = float(np.mean(np.std(rgb[out_q], axis=0)))
            rim_e_q = float(np.mean(pure_rad[rim_q])) if np.any(rim_q) else 0.0
            q_dists.append(dist_q)
            q_stds_out.append(std_out_q)
            if dist_q >= 0.065 or rim_e_q >= 0.014:
                active_quads += 1

        median_q_dist = float(np.median(q_dists)) if q_dists else 0.0
        min_q_dist = float(np.min(q_dists)) if q_dists else 0.0
        median_q_std = float(np.median(q_stds_out)) if q_stds_out else 0.25

        # Search for 4" center label boundary around r_cand / 3.0 ([0.26..0.36] * r_cand)
        best_lbl_e_local = 0.0
        best_rl_local = float(r_cand / 3.0)
        for rl in np.linspace(0.26 * r_cand, 0.36 * r_cand, 9):
            l_band = (r >= rl - 0.022) & (r <= rl + 0.022)
            le = float(np.mean(pure_rad[l_band]))
            if le > best_lbl_e_local:
                best_lbl_e_local = le
                best_rl_local = float(rl)

        lbl_in = (r >= 0.045) & (r <= max(0.14, best_rl_local - 0.022))
        wax_mid = (r >= best_rl_local + 0.035) & (r <= r_cand - 0.05)
        wax_inner_half = (r >= best_rl_local + 0.025) & (r <= r_cand * 0.56)
        wax_outer_half = (r > r_cand * 0.56) & (r <= r_cand - 0.04)

        color_in_color_dist = float(
            np.linalg.norm(np.mean(rgb[wax_inner_half], axis=0) - np.mean(rgb[wax_outer_half], axis=0))
        )
        lbl_wax_d_mid = float(np.linalg.norm(np.mean(rgb[lbl_in], axis=0) - np.mean(rgb[wax_mid], axis=0)))
        lbl_wax_d_inner = float(np.linalg.norm(np.mean(rgb[lbl_in], axis=0) - np.mean(rgb[wax_inner_half], axis=0)))
        corner_outer_m = (r >= 1.02) & (r <= 1.32) & diag_mask
        corner_outer_grad = float(np.mean(grad_mag[corner_outer_m]))
        if median_q_std < 0.175 and corner_outer_grad < 0.022 and color_in_color_dist >= 0.08:
            lbl_wax_d = max(lbl_wax_d_mid, lbl_wax_d_inner)
        else:
            lbl_wax_d = lbl_wax_d_mid

        quad_factor = 1.0 if active_quads == 4 else (0.75 if active_quads == 3 else 0.20)
        cand_score = quad_factor * (
            min(0.26, diag_rad_e * 3.8)
            + min(0.24, median_q_dist * 0.26 + min_q_dist * 0.10)
            + min(0.16, best_lbl_e_local * 2.2)
            + min(0.10, lbl_wax_d * 0.38)
            + min(0.06, color_in_color_dist * 0.18)
            + max(0.0, min(0.08, (0.24 - median_q_std) * 0.45))
        )

        if cand_score > best_dual_circle_score:
            best_dual_circle_score = cand_score
            best_r_disc = float(r_cand)
            best_r_lbl = best_rl_local
            best_active_quads = active_quads
            best_rim_step = diag_rad_e
            best_label_step = best_lbl_e_local
            best_label_wax_dist = lbl_wax_d
            best_corner_wax_dist = median_q_dist
            best_corner_std = median_q_std
            best_color_in_color_dist = color_in_color_dist

    # Canonical masks at best_r_disc and best_r_lbl
    spindle_ring = (r >= 0.020) & (r <= 0.052)
    spindle_hole = r <= 0.035
    spindle_surround = (r >= 0.045) & (r <= 0.095)
    label_mask = (r >= 0.048) & (r <= best_r_lbl - 0.02)
    wax_annulus_mask = (r >= best_r_lbl + 0.035) & (r <= best_r_disc - 0.045)

    spindle_edge = float(np.mean(grad_r[spindle_ring]))
    spindle_contrast = float(np.linalg.norm(np.mean(rgb[spindle_hole], axis=0) - np.mean(rgb[spindle_surround], axis=0)))
    label_grad_mag = float(np.mean(grad_mag[label_mask]))
    wax_grad_mag = float(np.mean(grad_mag[wax_annulus_mask]))
    wax_rad_e = float(np.mean(grad_r[wax_annulus_mask]))
    wax_tan_e = float(np.mean(grad_t[wax_annulus_mask])) + 1e-6

    # 8-Octant Label-to-Wax Continuity & Horizontal/Vertical Text Anisotropy
    # A real 12" vinyl record has a 360-degree circular 4" center label (`q25_oct_lbl_wax` high),
    # whereas square/circular hype stickers (e.g. 14188877/img_6, 28895677/img_9, 37058814/img_2)
    # have horizontal lines of text/barcodes running across the frame (`hv_wax_aniso` high, `q25_oct_lbl_wax` low).
    oct_lbl_wax_dists: list[float] = []
    for k in range(8):
        a0 = -np.pi + k * (np.pi / 4.0)
        a1 = a0 + (np.pi / 4.0)
        ang_m = (theta >= a0) & (theta < a1)
        in_oct = (r >= 0.14) & (r <= max(0.22, best_r_lbl - 0.025)) & ang_m
        out_oct = (r >= best_r_lbl + 0.035) & (r <= min(0.58, best_r_disc - 0.10)) & ang_m
        if np.any(in_oct) and np.any(out_oct):
            oct_lbl_wax_dists.append(
                float(np.linalg.norm(np.mean(rgb[in_oct], axis=0) - np.mean(rgb[out_oct], axis=0)))
            )
    oct_sorted = sorted(oct_lbl_wax_dists) if oct_lbl_wax_dists else [0.0]
    q25_oct_lbl_wax = oct_sorted[min(1, len(oct_sorted) - 1)]

    hv_wax_aniso = abs(
        float(np.log((np.mean(np.abs(gy[wax_annulus_mask])) + 1e-5) / (np.mean(np.abs(gx[wax_annulus_mask])) + 1e-5)))
    )
    hi_grad_wax_frac = float(np.mean(grad_mag[wax_annulus_mask] > 0.12))
    hi_grad_lbl_frac = float(np.mean(grad_mag[label_mask] > 0.15))

    # Check left-right symmetry of the wax annulus (rejects off-center sleeve+disc mockups like 27717681/img_2)
    left_wax = wax_annulus_mask & (dx < -0.15)
    right_wax = wax_annulus_mask & (dx > 0.15)
    lr_wax_diff = float(np.linalg.norm(np.mean(rgb[left_wax], axis=0) - np.mean(rgb[right_wax], axis=0)))

    # 1. Die-cut inner sleeve with blank paper center hole (e.g., 38268432/img_4, img_5, 28895677/img_1)
    is_diecut_sleeve = bool(label_grad_mag < 0.009 and spindle_edge < 0.0065 and spindle_contrast < 0.04)

    # 2. Off-center sleeve + half-disc promotional composite mockup (e.g., 27717681/img_2)
    is_mockup_composite = bool(
        best_label_step < 0.015
        and spindle_edge < 0.010
        and (lr_wax_diff > 0.22 or label_grad_mag < 0.022)
    )

    # 3. Zoomed-in 4" paper center label close-up on colored or black vinyl (e.g., 27066432/img_4,5 & 28895677/img_5,6)
    is_zoomed_label_scan = bool(
        (
            best_label_wax_dist < 0.175
            and best_label_step < 0.065
            and (wax_grad_mag >= label_grad_mag * 0.68 or best_corner_std < 0.05)
        )
        or (best_corner_std < 0.040 and best_label_wax_dist < 0.22)
    )

    # 4. Square or Circular Hype Stickers, Barcode Stickers, & Text Inserts (e.g., 14188877/img_6, 28895677/img_9, 37058814/img_2)
    is_hype_sticker_or_text_insert = bool(
        best_corner_std > 0.22
        or wax_grad_mag > 0.095
        or (hv_wax_aniso > 0.35 and (wax_grad_mag > 0.022 or hi_grad_wax_frac > 0.05) and q25_oct_lbl_wax < 0.25)
        or (hi_grad_wax_frac > 0.16 and hi_grad_lbl_frac > 0.25 and q25_oct_lbl_wax < 0.22)
        or (label_grad_mag > 0.125 and wax_grad_mag > 0.045 and q25_oct_lbl_wax < 0.25)
    )

    # Measure straight horizontal/vertical square sleeve border energy in [0.84..0.96]
    best_sq_border = 0.0
    for s in np.linspace(0.84, 0.96, 13):
        v_m = (np.abs(np.abs(dx) - s) <= 0.015) & (np.abs(dy) <= s)
        h_m = (np.abs(np.abs(dy) - s) <= 0.015) & (np.abs(dx) <= s)
        sq_e = 0.5 * (
            float(np.mean(np.maximum(0.0, np.abs(gx[v_m]) - 0.5 * np.abs(gy[v_m]))))
            + float(np.mean(np.maximum(0.0, np.abs(gy[h_m]) - 0.5 * np.abs(gx[h_m]))))
        )
        if sq_e > best_sq_border:
            best_sq_border = sq_e

    # Verified splatter/starburst/split disc exemption for radial wax streaks (guarded against stickers/inserts)
    is_verified_splatter_or_split_disc = bool(
        not is_hype_sticker_or_text_insert
        and best_corner_std < 0.18
        and wax_grad_mag < 0.095
        and (q25_oct_lbl_wax >= 0.15 or best_color_in_color_dist >= 0.12)
        and (
            (best_label_step >= 0.042 and best_rim_step >= 0.022 and best_label_wax_dist >= 0.20)
            or (best_corner_std < 0.090 and best_corner_wax_dist >= 0.35 and best_rim_step >= 0.018 and best_label_wax_dist >= 0.18)
        )
    )

    # Verified clear/translucent/starburst disc on sleeve exemption for soft outer rim (guarded against stickers/inserts)
    is_verified_clear_or_soft_rim_disc = bool(
        not is_hype_sticker_or_text_insert
        and best_corner_std < 0.18
        and wax_grad_mag < 0.095
        and (q25_oct_lbl_wax >= 0.15 or best_color_in_color_dist >= 0.12)
        and (
            (best_rim_step >= 0.024 and best_label_step >= 0.040 and best_label_wax_dist >= 0.25)
            or (best_rim_step >= 0.014 and best_label_step >= 0.018 and best_label_wax_dist >= 0.22 and best_corner_wax_dist >= 0.18 and best_corner_std < 0.085)
        )
    )

    # 5. Square lyric sheet, inner sleeve, slipcover, back cover, or hype sticker
    is_square_insert_or_sleeve = bool(
        is_hype_sticker_or_text_insert
        or best_active_quads < 4
        or (best_corner_wax_dist < 0.14 and best_rim_step < 0.032 and not is_verified_clear_or_soft_rim_disc)
        or (best_rim_step < 0.016 and best_corner_wax_dist < 0.32 and not is_verified_clear_or_soft_rim_disc)
        or (wax_grad_mag > 0.048 and wax_grad_mag > label_grad_mag * 0.70 and not is_verified_splatter_or_split_disc)
        or (spindle_edge < 0.008 and best_label_wax_dist < 0.23)
        or (best_sq_border > 0.045 and best_rim_step < best_sq_border * 0.42 and best_label_step < 0.028)
    )

    # Deterministic Seed (`wax_spec`) Color & Texture Alignment Bonus
    variant_color_bonus = 0.0
    wax_mean_rgb = np.mean(rgb[wax_annulus_mask], axis=0)
    wax_mean_sat = float(np.mean(sat[wax_annulus_mask]))

    primary_hex = expected_wax_hex or (wax_spec or {}).get("primary_color")
    secondary_hex = secondary_wax_hex or (wax_spec or {}).get("secondary_color")
    seed_pattern = str((wax_spec or {}).get("pattern") or "")
    seed_trans = bool((wax_spec or {}).get("translucent", False))

    achromatic_hexes = {"#18181b", "#3f3f46", "#64748b", "#94a3b8", "#a8a29e", "#cbd5e1", "#e2e8f0", "#f1f5f9", "#f8fafc"}

    best_chroma_sim = 0.0
    if primary_hex and primary_hex not in achromatic_hexes:
        target_rgb = np.asarray(_hex_to_rgb01(primary_hex), dtype=np.float32)
        wax_norm = wax_mean_rgb / (np.linalg.norm(wax_mean_rgb) + 1e-6)
        tgt_norm = target_rgb / (np.linalg.norm(target_rgb) + 1e-6)
        sim_p = float(np.dot(wax_norm, tgt_norm))
        best_chroma_sim = max(best_chroma_sim, sim_p)
        if sim_p > 0.86 and wax_mean_sat > 0.12:
            variant_color_bonus = max(variant_color_bonus, min(0.065, (sim_p - 0.84) * 0.38 + wax_mean_sat * 0.05))

    if secondary_hex and secondary_hex not in achromatic_hexes:
        target_rgb2 = np.asarray(_hex_to_rgb01(secondary_hex), dtype=np.float32)
        wax_norm = wax_mean_rgb / (np.linalg.norm(wax_mean_rgb) + 1e-6)
        tgt_norm2 = target_rgb2 / (np.linalg.norm(target_rgb2) + 1e-6)
        sim_s = float(np.dot(wax_norm, tgt_norm2))
        best_chroma_sim = max(best_chroma_sim, sim_s)
        if sim_s > 0.86 and wax_mean_sat > 0.12:
            variant_color_bonus = max(variant_color_bonus, min(0.045, (sim_s - 0.84) * 0.28 + wax_mean_sat * 0.04))

    # Ghostly / Smoke / Cloudy / Translucent Splatter seed alignment (e.g., 33303678 Ghostly Black, 28895677 Blood Pool)
    if (seed_trans or seed_pattern in ("galaxy", "splatter", "color_in_color", "translucent")) and q25_oct_lbl_wax >= 0.22 and best_corner_std < 0.06:
        if 0.004 <= wax_grad_mag <= 0.065 and hv_wax_aniso < 0.18:
            variant_color_bonus += 0.025

    circularity_ratio = (best_rim_step + 0.6 * best_label_step + 0.25 * wax_rad_e) / (wax_tan_e * 0.65 + 0.012)
    clean_disc_bonus = 0.025 if (circularity_ratio >= 1.55 and best_label_wax_dist >= 0.175 and best_corner_std < 0.090) else 0.0

    raw_annular_score = (
        best_dual_circle_score
        + min(0.08, circularity_ratio * 0.03)
        + min(0.06, (spindle_edge * 0.5 + spindle_contrast * 0.12))
        + variant_color_bonus
        + clean_disc_bonus
    )

    rejected = (
        is_diecut_sleeve
        or is_mockup_composite
        or is_zoomed_label_scan
        or is_hype_sticker_or_text_insert
        or is_square_insert_or_sleeve
    )
    score = raw_annular_score * 0.25 if rejected else raw_annular_score
    score = round(min(0.995, max(0.0, score)), 4)

    is_pressing = bool(not rejected and score >= 0.475)

    reason = "deterministic_annular_cv_match"
    if not is_pressing:
        if is_diecut_sleeve:
            reason = "rejected_diecut_inner_sleeve"
        elif is_mockup_composite:
            reason = "rejected_sleeve_disc_mockup"
        elif is_zoomed_label_scan:
            reason = "rejected_zoomed_center_label_scan"
        elif is_hype_sticker_or_text_insert:
            reason = "rejected_hype_sticker_or_text_insert"
        elif is_square_insert_or_sleeve:
            reason = "rejected_square_insert_or_sleeve"
        else:
            reason = "below_annular_threshold"

    return {
        "is_pressing": is_pressing,
        "is_zoomed_label_scan": is_zoomed_label_scan,
        "is_hype_sticker_or_text_insert": is_hype_sticker_or_text_insert,
        "is_square_insert_or_sleeve": is_square_insert_or_sleeve or is_diecut_sleeve or is_mockup_composite or is_hype_sticker_or_text_insert,
        "detected_disc_radius": round(best_r_disc, 3),
        "active_diagonal_quadrants": best_active_quads,
        "score": score,
        "raw_annular_score": round(min(0.995, max(0.0, raw_annular_score)), 4),
        "aspect_ratio": round(aspect, 3),
        "corner_std": round(best_corner_std, 4),
        "corner_wax_dist": round(best_corner_wax_dist, 4),
        "circularity_ratio": round(circularity_ratio, 4),
        "label_wax_dist": round(best_label_wax_dist, 4),
        "octant_label_wax_q25": round(q25_oct_lbl_wax, 4),
        "hv_wax_anisotropy": round(hv_wax_aniso, 4),
        "spindle_contrast": round(spindle_contrast, 4),
        "reason": reason,
    }


def select_release_images_deterministic(
    images: list[dict[str, Any]],
    formats: list[dict[str, Any]] | None = None,
    notes: str = "",
    release_id: int | str = 0,
    overrides: dict[str, Any] | None = None,
    downloaded_bytes_by_uri: dict[str, bytes] | None = None,
    local_release_dir: pathlib.Path | None = None,
) -> dict[str, Any]:
    """Deterministically classifies a Discogs release's `images[]` array and selects the pressing image."""
    overrides = overrides or {}
    formats = formats or []
    downloaded_bytes_by_uri = downloaded_bytes_by_uri or {}
    rid_key = str(release_id)

    if not images:
        return {
            "cover_image_url": "",
            "pressing_image_url": "",
            "center_label_image_url": "",
            "display_thumbnail_url": "",
            "has_pressing_photo": False,
            "selected_index": -1,
            "selected_score": 0.0,
            "detection_method": "no_images_in_release",
            "classified_images": [],
        }

    fmt_tokens: list[str] = []
    for f in formats:
        fmt_tokens.extend(f.get("descriptions") or [])
        if f.get("text"):
            fmt_tokens.append(str(f["text"]))
    fmt_str_for_wax = ", ".join(fmt_tokens)
    fmt_joined = " ".join(fmt_tokens + [notes]).lower()

    wax_preview = parse_wax_variant(fmt_str_for_wax, comments=notes, release_id=release_id)
    expected_wax_hex = wax_preview.get("primary_color")
    secondary_wax_hex = wax_preview.get("secondary_color")

    is_gatefold = "gatefold" in fmt_joined
    is_no_cover = "no cover" in fmt_joined or "generic" in fmt_joined
    has_insert_or_sheet = bool(re.search(r"lyric sheet|insert|booklet|inner sleeve|poster", fmt_joined))

    primary_idx = next((i for i, img in enumerate(images) if img.get("type") == "primary"), 0)
    cover_url = images[primary_idx].get("uri") or images[primary_idx].get("resource_url") or ""
    center_label_url = images[primary_idx].get("uri150") or cover_url

    local_cover_rel = ""
    if local_release_dir and (local_release_dir / "cover.jpg").exists():
        local_cover_rel = f"assets/releases/{rid_key}/cover.jpg"
    elif local_release_dir and (local_release_dir / f"img_{primary_idx}.jpg").exists():
        local_cover_rel = f"assets/releases/{rid_key}/img_{primary_idx}.jpg"

    classified: list[dict[str, Any]] = []
    best_pressing_idx = -1
    best_pressing_score = -1.0
    best_method = "procedural_wax_from_discogs_format_codes"
    num_imgs = len(images)
    first_verified_pressing_seen = False
    has_any_real_cv = False

    for idx, img in enumerate(images):
        uri = img.get("uri") or img.get("resource_url") or ""
        uri150 = img.get("uri150") or uri
        w = int(img.get("width") or 600)
        h = int(img.get("height") or 600)
        aspect = w / float(h) if h else 1.0
        is_square_or_43 = 0.72 <= aspect <= 1.38
        is_near_square = 0.85 <= aspect <= 1.18

        local_img_rel = ""
        img_bytes: bytes | None = downloaded_bytes_by_uri.get(uri) or downloaded_bytes_by_uri.get(f"idx:{idx}")
        if local_release_dir and (local_release_dir / f"img_{idx}.jpg").exists():
            local_img_rel = f"assets/releases/{rid_key}/img_{idx}.jpg"
            if img_bytes is None:
                try:
                    img_bytes = (local_release_dir / f"img_{idx}.jpg").read_bytes()
                    if uri:
                        downloaded_bytes_by_uri[uri] = img_bytes
                    downloaded_bytes_by_uri[f"idx:{idx}"] = img_bytes
                except Exception:
                    pass

        role = "secondary"
        pos_score = 0.0
        cv_details: dict[str, Any] = {}

        # Positional prior used ONLY when image bytes/CV are unavailable
        if idx == primary_idx and not is_no_cover:
            role = "front_cover"
            pos_score = 0.05
        elif not is_square_or_43:
            role = "gatefold_spread"
            pos_score = 0.05
        else:
            if is_no_cover and idx == 0:
                role = "pressing_or_label"
                pos_score = 0.80
            elif num_imgs >= 5:
                if idx == 1:
                    role = "back_cover" if not is_gatefold else "gatefold_inner"
                    pos_score = 0.25
                elif idx in (2, 3):
                    role = "label_or_insert_candidate" if (is_gatefold or has_insert_or_sheet or num_imgs >= 6) else "pressing_candidate"
                    pos_score = 0.62 if idx == 2 else 0.64
                elif idx in (4, 5):
                    role = "pressing_disc"
                    pos_score = 0.78 if idx == 4 else 0.76
                else:
                    role = "pressing_candidate"
                    pos_score = 0.75
            else:
                if idx == 1 and num_imgs == 2:
                    role = "pressing_candidate"
                    pos_score = 0.76 if is_near_square else 0.60
                elif idx == 1 and num_imgs == 3:
                    role = "pressing_candidate"
                    pos_score = 0.78
                elif idx == 2 and num_imgs == 3:
                    role = "pressing_candidate"
                    pos_score = 0.74
                elif idx >= 2:
                    role = "pressing_disc"
                    pos_score = 0.80
                else:
                    role = "back_cover"
                    pos_score = 0.30

        if img_bytes is not None and (idx != primary_idx or is_no_cover):
            cv_details = score_image_pixels_deterministic(
                img_bytes,
                expected_wax_hex=expected_wax_hex,
                secondary_wax_hex=secondary_wax_hex,
                wax_spec=wax_preview,
            )
            if cv_details.get("reason") == "cv_deps_unavailable":
                combined_score = pos_score
                method = "guideline_13_8_positional"
            else:
                has_any_real_cv = True
                if cv_details.get("is_pressing"):
                    role = "pressing_disc"
                    # First verified pressing disc (Side A) gets a tie-breaker bonus (+0.028)
                    side_a_bonus = 0.028 if not first_verified_pressing_seen else 0.0
                    first_verified_pressing_seen = True
                    combined_score = min(0.995, 0.92 * float(cv_details["score"]) + 0.08 * 0.85 + side_a_bonus)
                    method = "deterministic_annular_cv+guideline_13_8"
                elif cv_details.get("is_zoomed_label_scan"):
                    role = "center_label_closeup"
                    combined_score = 0.85 * float(cv_details.get("score", 0.0)) + 0.05 * pos_score
                    method = "rejected_zoomed_center_label_scan"
                elif cv_details.get("is_hype_sticker_or_text_insert"):
                    role = "insert_or_sleeve"
                    combined_score = 0.85 * float(cv_details.get("score", 0.0)) + 0.05 * pos_score
                    method = "rejected_hype_sticker_or_text_insert"
                elif cv_details.get("is_square_insert_or_sleeve"):
                    role = "insert_or_sleeve"
                    combined_score = 0.85 * float(cv_details.get("score", 0.0)) + 0.05 * pos_score
                    method = "rejected_square_insert_or_sleeve"
                else:
                    role = "insert_or_sleeve"
                    combined_score = 0.85 * float(cv_details.get("score", 0.0)) + 0.10 * pos_score
                    method = "below_annular_threshold"
        else:
            combined_score = pos_score if not has_any_real_cv else 0.05
            method = "guideline_13_8_positional" if not has_any_real_cv else "front_cover"

        entry: dict[str, Any] = {
            "index": idx,
            "uri": uri or local_img_rel,
            "uri150": uri150 or local_img_rel,
            "width": w,
            "height": h,
            "aspect_ratio": round(aspect, 3),
            "role": role,
            "deterministic_score": round(combined_score, 4),
        }
        if local_img_rel:
            entry["local_uri"] = local_img_rel
        if cv_details:
            entry["cv_metrics"] = cv_details
        classified.append(entry)

        # When real CV is available, ONLY select images that passed `is_pressing == True`.
        # When real CV is unavailable, allow positional threshold.
        is_valid_cand = (
            bool(cv_details.get("is_pressing"))
            if (img_bytes is not None and cv_details.get("reason") != "cv_deps_unavailable")
            else (not has_any_real_cv and combined_score >= 0.48)
        )
        if (idx != primary_idx or is_no_cover) and is_valid_cand and combined_score > best_pressing_score:
            best_pressing_score = combined_score
            best_pressing_idx = idx
            best_method = method

    # Tier 1: Check explicit override in data/overrides.json
    # Only honor explicit manual pins (int or dict with pressing_image_index) when real CV is active,
    # AND only if the pinned index wasn't a rejected sticker/back-cover unless manually forced.
    if rid_key in overrides and len(images) > 1:
        ov = overrides[rid_key]
        ov_idx = -1
        ov_url = ""
        is_manual_pin = False
        if isinstance(ov, dict) and "pressing_image_index" in ov:
            idx_cand = int(ov["pressing_image_index"])
            if 0 <= idx_cand < len(images):
                ov_idx = idx_cand
                ov_url = images[ov_idx].get("uri") or images[ov_idx].get("resource_url") or ""
                is_manual_pin = bool(ov.get("manual_pin", True))
        elif isinstance(ov, int) and 0 <= ov < len(images):
            ov_idx = ov
            ov_url = images[ov_idx].get("uri") or images[ov_idx].get("resource_url") or ""
            is_manual_pin = True
        elif isinstance(ov, str) and ov and not has_any_real_cv:
            ov_url = ov
            ov_idx = next(
                (i for i, im in enumerate(images) if (im.get("uri") or im.get("resource_url")) == ov),
                -1,
            )
            if ov_idx < 0:
                m_idx = re.search(r"img_(\d+)\.jpg", ov)
                if m_idx and 0 <= int(m_idx.group(1)) < len(images):
                    ov_idx = int(m_idx.group(1))

        if ov_url and ov_idx >= 0 and (is_manual_pin or not has_any_real_cv):
            if 0 <= ov_idx < len(classified):
                classified[ov_idx]["role"] = "pressing_disc"
                classified[ov_idx]["deterministic_score"] = 1.0
            local_p_rel = ""
            if local_release_dir and (local_release_dir / f"img_{ov_idx}.jpg").exists():
                local_p_rel = f"assets/releases/{rid_key}/img_{ov_idx}.jpg"
            elif local_release_dir and (local_release_dir / "pressing.jpg").exists():
                local_p_rel = f"assets/releases/{rid_key}/pressing.jpg"
            res = {
                "cover_image_url": cover_url,
                "pressing_image_url": ov_url,
                "center_label_image_url": center_label_url,
                "display_thumbnail_url": local_p_rel or ov_url or cover_url,
                "has_pressing_photo": True,
                "selected_index": ov_idx,
                "selected_score": 1.0,
                "detection_method": "override_index" if is_manual_pin else "override_verified_pressing",
                "classified_images": classified,
            }
            if local_cover_rel:
                res["local_cover_image_url"] = local_cover_rel
            if local_p_rel:
                res["local_pressing_image_url"] = local_p_rel
            return res

    pressing_url = classified[best_pressing_idx]["uri"] if best_pressing_idx >= 0 else ""
    local_p_rel = ""
    if best_pressing_idx >= 0:
        classified[best_pressing_idx]["role"] = "pressing_disc"
        if local_release_dir and (local_release_dir / f"img_{best_pressing_idx}.jpg").exists():
            local_p_rel = f"assets/releases/{rid_key}/img_{best_pressing_idx}.jpg"
        else:
            local_p_rel = classified[best_pressing_idx].get("local_uri") or ""

    has_pressing = bool(best_pressing_idx >= 0 and pressing_url)
    res = {
        "cover_image_url": cover_url,
        "pressing_image_url": pressing_url if has_pressing else "",
        "center_label_image_url": center_label_url,
        "display_thumbnail_url": (local_p_rel or pressing_url) if has_pressing else (local_cover_rel or cover_url),
        "has_pressing_photo": has_pressing,
        "selected_index": best_pressing_idx if has_pressing else -1,
        "selected_score": round(best_pressing_score, 4) if has_pressing else 0.0,
        "detection_method": best_method if has_pressing else "procedural_wax_from_discogs_format_codes",
        "classified_images": classified,
    }
    if local_cover_rel:
        res["local_cover_image_url"] = local_cover_rel
    if has_pressing and local_p_rel:
        res["local_pressing_image_url"] = local_p_rel
    return res


def _norm_text(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def resolve_flattening_status(
    artist: str,
    title: str,
    release_id: int | str,
    queue_data: dict[str, Any] | None = None,
) -> str:
    """Deterministically resolves a release's Vinyl Flattening status ('Need to be done', 'Done', or 'Not Listed')."""
    if not queue_data:
        return "Not Listed"

    rid_int = int(release_id or 0)
    todo_ids = {int(x) for x in (queue_data.get("need_to_be_done_release_ids") or [])}
    done_ids = {int(x) for x in (queue_data.get("done_release_ids") or [])}

    if rid_int in todo_ids:
        return "Need to be done"
    if rid_int in done_ids:
        return "Done"

    a_norm = _norm_text(artist)
    t_norm = _norm_text(title)

    for entry in queue_data.get("need_to_be_done_entries") or []:
        if entry.get("release_ids"):
            continue
        ea = _norm_text(entry.get("artist", ""))
        et = _norm_text(entry.get("album", ""))
        if ea and et and len(t_norm) >= 4 and (ea in a_norm or a_norm in ea) and (et == t_norm or (len(et) >= 5 and et in t_norm)):
            return "Need to be done"

    for entry in queue_data.get("done_entries") or []:
        if entry.get("release_ids"):
            continue
        ea = _norm_text(entry.get("artist", ""))
        et = _norm_text(entry.get("album", ""))
        if ea and et and len(t_norm) >= 4 and (ea in a_norm or a_norm in ea) and (et == t_norm or (len(et) >= 5 and et in t_norm)):
            return "Done"

    return "Not Listed"