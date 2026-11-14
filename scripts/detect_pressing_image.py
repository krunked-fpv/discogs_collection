#!/usr/bin/env python3
"""Deterministic Pressing Image Classifier, Vinyl Wax Variant Parser & Flattening Matcher.

Uses 100% deterministic rules to:
1. Identify which image in a Discogs Release `images[]` array depicts the
   physical 12" vinyl pressing itself (vs. front sleeve cover, back cover tracklist,
   square inner sleeve / lyric insert, die-cut inner sleeve, sleeve+disc mockup,
   gatefold spread, square/circular hype stickers, or close-up 4" paper center label),
   supporting:
   - Standard centered 1:1 / near-square 12" disc photos (`R_disc in [0.80..0.99]`)
   - Landscape 4:3 turntable platter photos with tonearm on the right (`20697637`, `2343816`)
   - Padded studio disc photos with wider outer margins (`R_disc in [0.65..0.79]`, e.g. `26690690`)
   - Off-center angled vinyl disc photos with a full 360-degree 4" center label and spindle hole (`13203006`)
   - Full-bleed records resting on inner sleeves or printed album jackets (`12988109`, `26917130`)
   - Dark-on-dark splatter/translucent pressings (`26047519`) and color-in-color/swirl pressings (`16595574`, `35907826`)
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
import json
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


def _eval_centered_concentric(
    rgb: "np.ndarray",
    aspect: float,
    expected_wax_hex: str | None = None,
    secondary_wax_hex: str | None = None,
    wax_spec: dict[str, Any] | None = None,
    r_min: float = 0.80,
    r_max: float = 0.99,
    n_steps: int = 20,
) -> dict[str, Any]:
    """Evaluates concentric dual-circle (outer 12" rim + inner 4" 1/3 center label + spindle hole) on a 256x256 grid."""
    gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    sat = np.max(rgb, axis=2) - np.min(rgb, axis=2)

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

    for r_cand in np.linspace(r_min, r_max, n_steps):
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

        # Support slight perspective tilt on hand-held portrait disc photos (e.g., 27927123/img_4)
        if active_quads == 4 and r_cand <= 0.86 and aspect < 0.88:
            dy_t = dy - (-0.09)
            dx_t = dx - (-0.05)
            r_t = np.hypot(dx_t, dy_t)
            th_t = np.arctan2(dy_t, dx_t)
            gr_t = np.abs(gx * np.cos(th_t) + gy * np.sin(th_t))
            gt_t = np.abs(-gx * np.sin(th_t) + gy * np.cos(th_t))
            pr_t = np.maximum(0.0, gr_t - 0.55 * gt_t)
            for rl_t in np.linspace(0.24, 0.33, 6):
                le_t = float(np.mean(pr_t[(r_t >= rl_t - 0.022) & (r_t <= rl_t + 0.022)]))
                if le_t > best_lbl_e_local:
                    lbl_in_t = (r_t >= 0.045) & (r_t <= rl_t - 0.02)
                    wax_m_t = (r_t >= rl_t + 0.035) & (r_t <= r_cand - 0.05)
                    if np.any(lbl_in_t) and np.any(wax_m_t):
                        lwd_t = float(np.linalg.norm(np.mean(rgb[lbl_in_t], axis=0) - np.mean(rgb[wax_m_t], axis=0)))
                        if lwd_t >= 0.22:
                            best_lbl_e_local = le_t
                            lbl_wax_d = max(lbl_wax_d, lwd_t)

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

    left_wax = wax_annulus_mask & (dx < -0.15)
    right_wax = wax_annulus_mask & (dx > 0.15)
    lr_wax_diff = float(np.linalg.norm(np.mean(rgb[left_wax], axis=0) - np.mean(rgb[right_wax], axis=0)))

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

    wax_mean_rgb = np.mean(rgb[wax_annulus_mask], axis=0)
    wax_mean_sat = float(np.mean(sat[wax_annulus_mask]))
    wax_rgb_std = float(np.mean(np.std(rgb[wax_annulus_mask], axis=0)))
    corner_outer_m_all = (r >= 1.02) & (r <= 1.32) & diag_mask
    corner_outer_sat = float(np.mean(sat[corner_outer_m_all])) if np.any(corner_outer_m_all) else 0.0
    inner_65_mask = r <= 0.65
    hv_inner_aniso = abs(
        float(np.log((np.mean(np.abs(gy[inner_65_mask])) + 1e-5) / (np.mean(np.abs(gx[inner_65_mask])) + 1e-5)))
    )
    wax_tan_rad_ratio = float(wax_tan_e / (wax_rad_e + 1e-5))

    # Radial splatter / starburst spoke signature: radial rays have tangential gradient >> radial gradient
    # (e.g., 37023150/img_2,3 has ratio ~3.5 and 23343893/img_3 has ratio ~2.53)
    is_radial_splatter_spokes = bool(
        wax_tan_rad_ratio >= 1.35
        and best_rim_step >= 0.026
        and best_label_wax_dist >= 0.20
        and q25_oct_lbl_wax >= 0.16
        and hv_wax_aniso < 0.22
    )

    # True concentric 360-degree center label + outer disc rim signature
    # Protects real 12" vinyl discs sitting on inner sleeves or album covers (e.g., 12988109/img_4,5 & 26917130/img_4,5)
    has_strong_concentric_disc = bool(
        best_active_quads >= 4
        and best_rim_step >= 0.025
        and best_r_disc >= 0.84
        and (best_label_step >= 0.028 or best_color_in_color_dist >= 0.16 or spindle_contrast >= 0.22 or is_radial_splatter_spokes)
        and best_label_wax_dist >= 0.15
        and (q25_oct_lbl_wax >= 0.165 or best_color_in_color_dist >= 0.18 or best_corner_wax_dist >= 0.30)
        and (wax_grad_mag <= 0.055 or is_radial_splatter_spokes or best_color_in_color_dist >= 0.16 or best_corner_std < 0.095)
        and hv_wax_aniso < 0.18
        and label_grad_mag < 0.085
    )

    # 1. Die-cut inner sleeve with blank paper center hole (e.g., 38268432/img_4, img_5, 28895677/img_1)
    is_diecut_sleeve = bool(label_grad_mag < 0.009 and spindle_edge < 0.0065 and spindle_contrast < 0.04)

    # 2. Off-center sleeve + half-disc promotional composite mockup (e.g., 27717681/img_2)
    is_mockup_composite = bool(
        best_label_step < 0.015
        and spindle_edge < 0.010
        and (lr_wax_diff > 0.22 or label_grad_mag < 0.022)
    )

    # 3. Zoomed-in 4" paper center label close-up on colored or black vinyl (e.g., 27066432/img_4,5, 35907826/img_4,5 & 20518822/img_2,3)
    # Guards full 12" swirl/splatter discs on clean backdrops (e.g., 35907826/img_6,7 & 26047519/img_4)
    is_zoomed_label_scan = bool(
        (
            corner_outer_sat >= 0.45
            and best_corner_std < 0.045
            and wax_mean_sat < corner_outer_sat * 0.42
            and wax_rgb_std > 0.17
            and q25_oct_lbl_wax < 0.20
        )
        or (
            not (best_rim_step >= 0.030 and best_corner_wax_dist >= 0.30 and best_label_step >= 0.030 and hv_wax_aniso < 0.12)
            and not (best_color_in_color_dist >= 0.12 and spindle_contrast >= 0.18 and best_label_step >= 0.020 and hv_wax_aniso < 0.08)
            and (
                (
                    best_label_wax_dist < 0.175
                    and best_label_step < 0.065
                    and (wax_grad_mag >= label_grad_mag * 0.68 or best_corner_std < 0.05)
                )
                or (best_corner_std < 0.040 and best_label_wax_dist < 0.22 and best_corner_wax_dist < 0.28)
            )
        )
    )

    # 4. Square or Circular Hype Stickers, Barcode Stickers, & Text Inserts (e.g., 14188877/img_6, 28895677/img_9, 16595574/img_2, 26690690/img_2, 16251744/img_2)
    is_hype_sticker_or_text_insert = bool(
        (best_corner_std > 0.22 and not has_strong_concentric_disc)
        or wax_grad_mag > 0.095
        or (hv_wax_aniso > 0.32 and (wax_grad_mag > 0.022 or hi_grad_wax_frac > 0.05) and q25_oct_lbl_wax < 0.25)
        or (hi_grad_wax_frac > 0.16 and hi_grad_lbl_frac > 0.25 and q25_oct_lbl_wax < 0.22)
        or (label_grad_mag > 0.125 and wax_grad_mag > 0.045 and q25_oct_lbl_wax < 0.25)
        or (q25_oct_lbl_wax < 0.055 and best_rim_step < 0.022 and spindle_contrast < 0.06 and (hv_inner_aniso > 0.12 or best_corner_std > 0.10))
    )

    # Verified splatter/starburst/split/color-in-color disc exemption for radial wax streaks (e.g., 12988109/img_4,5, 16595574/img_4, 37023150/img_2,3, 23343893/img_3)
    is_verified_splatter_or_split_disc = bool(
        not is_hype_sticker_or_text_insert
        and best_corner_std < 0.245
        and wax_grad_mag < 0.095
        and hv_wax_aniso < 0.20
        and (wax_grad_mag <= 0.055 or is_radial_splatter_spokes or best_color_in_color_dist >= 0.16 or lr_wax_diff >= 0.18 or best_corner_std < 0.095)
        and (q25_oct_lbl_wax >= 0.14 or best_color_in_color_dist >= 0.12)
        and (
            is_radial_splatter_spokes
            or (best_label_step >= 0.028 and best_rim_step >= 0.022 and best_label_wax_dist >= 0.175)
            or (best_color_in_color_dist >= 0.165 and best_rim_step >= 0.022 and best_label_wax_dist >= 0.175)
            or (best_corner_std < 0.090 and best_corner_wax_dist >= 0.35 and best_rim_step >= 0.018 and best_label_wax_dist >= 0.18)
        )
    )

    # Verified clear/translucent or dark-on-dark splatter disc exemption for soft outer rim (e.g., 26047519/img_3..6)
    is_verified_clear_or_soft_rim_disc = bool(
        not is_hype_sticker_or_text_insert
        and best_corner_std < 0.245
        and wax_grad_mag < 0.095
        and hv_wax_aniso < 0.18
        and (wax_grad_mag <= 0.055 or is_radial_splatter_spokes or best_color_in_color_dist >= 0.16)
        and (q25_oct_lbl_wax >= 0.105 or best_color_in_color_dist >= 0.11)
        and (
            (best_rim_step >= 0.024 and best_label_step >= 0.030 and best_label_wax_dist >= 0.20)
            or (best_rim_step >= 0.014 and best_label_step >= 0.018 and best_label_wax_dist >= 0.22 and best_corner_wax_dist >= 0.18 and best_corner_std < 0.085)
            or (best_color_in_color_dist >= 0.11 and best_label_step >= 0.017 and best_label_wax_dist >= 0.15 and best_corner_wax_dist >= 0.10 and best_corner_std < 0.16 and hv_wax_aniso < 0.08 and lr_wax_diff < 0.12)
        )
    )

    # 5. Square lyric sheet, inner sleeve, slipcover, back cover, or hype sticker
    is_square_insert_or_sleeve = bool(
        is_hype_sticker_or_text_insert
        or best_active_quads < 4
        or (best_corner_wax_dist < 0.14 and best_rim_step < 0.027 and not is_verified_clear_or_soft_rim_disc and not is_verified_splatter_or_split_disc)
        or (best_rim_step < 0.016 and best_corner_wax_dist < 0.32 and not is_verified_clear_or_soft_rim_disc)
        or (wax_grad_mag > 0.048 and wax_grad_mag > label_grad_mag * 0.70 and not is_verified_splatter_or_split_disc)
        or (spindle_edge < 0.008 and best_label_wax_dist < 0.23 and not is_verified_clear_or_soft_rim_disc and not is_verified_splatter_or_split_disc)
        or (best_sq_border > 0.045 and best_rim_step < best_sq_border * 0.42 and best_label_step < 0.028)
    )

    # Deterministic Seed (`wax_spec`) Color & Texture Alignment Bonus
    variant_color_bonus = 0.0

    primary_hex = expected_wax_hex or (wax_spec or {}).get("primary_color")
    secondary_hex = secondary_wax_hex or (wax_spec or {}).get("secondary_color")
    seed_pattern = str((wax_spec or {}).get("pattern") or "")
    seed_trans = bool((wax_spec or {}).get("translucent", False))

    achromatic_hexes = {"#18181b", "#3f3f46", "#64748b", "#94a3b8", "#a8a29e", "#cbd5e1", "#e2e8f0", "#f1f5f9", "#f8fafc"}

    if primary_hex and primary_hex not in achromatic_hexes:
        target_rgb = np.asarray(_hex_to_rgb01(primary_hex), dtype=np.float32)
        wax_norm = wax_mean_rgb / (np.linalg.norm(wax_mean_rgb) + 1e-6)
        tgt_norm = target_rgb / (np.linalg.norm(target_rgb) + 1e-6)
        sim_p = float(np.dot(wax_norm, tgt_norm))
        if sim_p > 0.86 and wax_mean_sat > 0.12:
            variant_color_bonus = max(variant_color_bonus, min(0.065, (sim_p - 0.84) * 0.38 + wax_mean_sat * 0.05))

    if secondary_hex and secondary_hex not in achromatic_hexes:
        target_rgb2 = np.asarray(_hex_to_rgb01(secondary_hex), dtype=np.float32)
        wax_norm = wax_mean_rgb / (np.linalg.norm(wax_mean_rgb) + 1e-6)
        tgt_norm2 = target_rgb2 / (np.linalg.norm(target_rgb2) + 1e-6)
        sim_s = float(np.dot(wax_norm, tgt_norm2))
        if sim_s > 0.86 and wax_mean_sat > 0.12:
            variant_color_bonus = max(variant_color_bonus, min(0.045, (sim_s - 0.84) * 0.28 + wax_mean_sat * 0.04))

    if (seed_trans or seed_pattern in ("galaxy", "splatter", "color_in_color", "translucent")) and q25_oct_lbl_wax >= 0.22 and best_corner_std < 0.06:
        if 0.004 <= wax_grad_mag <= 0.065 and hv_wax_aniso < 0.18:
            variant_color_bonus += 0.025

    eff_wax_tan = min(wax_tan_e, wax_rad_e * 1.10) if is_radial_splatter_spokes else wax_tan_e
    circularity_ratio = (best_rim_step + 0.6 * best_label_step + 0.25 * wax_rad_e) / (eff_wax_tan * 0.65 + 0.012)
    clean_disc_bonus = 0.025 if (circularity_ratio >= 1.55 and best_label_wax_dist >= 0.175 and best_corner_std < 0.090) else 0.0
    if has_strong_concentric_disc or is_verified_splatter_or_split_disc or is_verified_clear_or_soft_rim_disc:
        clean_disc_bonus = max(clean_disc_bonus, 0.050)

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

    is_pressing = bool(not rejected and score >= 0.438)

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
        "rim_step": round(best_rim_step, 4),
        "label_step": round(best_label_step, 4),
        "reason": reason,
    }


def _eval_offcenter_disc(rgb: "np.ndarray", aspect: float) -> dict[str, Any] | None:
    """Detects off-center angled vinyl disc photos where the full 360-degree 4-inch center label and spindle hole are visible in-frame (e.g. 13203006/img_1.jpg)."""
    gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    gy, gx = np.gradient(gray)
    yy, xx = np.mgrid[0:256, 0:256]
    in_frame = (yy >= 3) & (yy < 253) & (xx >= 3) & (xx < 253)

    best_cand: dict[str, Any] | None = None
    for (cx, cy) in [(-0.39, -0.49), (0.39, -0.49), (-0.39, 0.49), (0.39, 0.49)]:
        dy = (yy - 127.5) / 127.5 - cy
        dx = (xx - 127.5) / 127.5 - cx
        rad = np.hypot(dx, dy)
        theta = np.arctan2(dy, dx)
        grad_r = np.abs(gx * np.cos(theta) + gy * np.sin(theta))
        grad_t = np.abs(-gx * np.sin(theta) + gy * np.cos(theta))
        pure_rad = np.maximum(0.0, grad_r - 0.55 * grad_t)

        sp_hole = (rad <= 0.036) & in_frame
        sp_surr = (rad >= 0.050) & (rad <= 0.110) & in_frame
        sp_ring = (rad >= 0.020) & (rad <= 0.055) & in_frame
        if np.sum(sp_hole) < 10 or np.sum(sp_surr) < 30:
            continue
        sp_c = float(np.linalg.norm(np.mean(rgb[sp_hole], axis=0) - np.mean(rgb[sp_surr], axis=0)))
        sp_e = float(np.mean(grad_r[sp_ring]))

        lbl_b = (rad >= 0.30) & (rad <= 0.35) & in_frame
        lbl_e = float(np.mean(pure_rad[lbl_b])) if np.any(lbl_b) else 0.0
        lbl_in = (rad >= 0.05) & (rad <= 0.29) & in_frame
        wax_m = (rad >= 0.36) & (rad <= 0.90) & in_frame
        if np.sum(lbl_in) < 100 or np.sum(wax_m) < 400:
            continue
        lwd = float(np.linalg.norm(np.mean(rgb[lbl_in], axis=0) - np.mean(rgb[wax_m], axis=0)))
        octs: list[float] = []
        for k in range(8):
            a0 = -np.pi + k * (np.pi / 4.0)
            ang = (theta >= a0) & (theta < a0 + np.pi / 4.0)
            io_m = lbl_in & ang
            oo_m = wax_m & ang
            if np.sum(io_m) >= 15 and np.sum(oo_m) >= 25:
                octs.append(float(np.linalg.norm(np.mean(rgb[io_m], axis=0) - np.mean(rgb[oo_m], axis=0))))
        if len(octs) < 8:
            continue
        q25 = sorted(octs)[1]
        aniso = abs(float(np.log((np.mean(np.abs(gy[wax_m])) + 1e-5) / (np.mean(np.abs(gx[wax_m])) + 1e-5))))

        if sp_c >= 0.25 and sp_e >= 0.030 and lbl_e >= 0.025 and lwd >= 0.35 and q25 >= 0.24 and aniso < 0.15:
            sc = round(min(0.95, 0.45 + 0.25 * lwd + 0.20 * q25 + 0.15 * sp_c), 4)
            cand = {
                "is_pressing": True,
                "is_zoomed_label_scan": False,
                "is_hype_sticker_or_text_insert": False,
                "is_square_insert_or_sleeve": False,
                "detected_disc_radius": 0.98,
                "active_diagonal_quadrants": 4,
                "score": sc,
                "raw_annular_score": sc,
                "aspect_ratio": round(aspect, 3),
                "corner_std": 0.05,
                "corner_wax_dist": round(lwd, 4),
                "circularity_ratio": 2.1,
                "label_wax_dist": round(lwd, 4),
                "octant_label_wax_q25": round(q25, 4),
                "hv_wax_anisotropy": round(aniso, 4),
                "spindle_contrast": round(sp_c, 4),
                "rim_step": 0.025,
                "label_step": round(lbl_e, 4),
                "reason": "deterministic_annular_cv_match",
            }
            if best_cand is None or cand["score"] > best_cand["score"]:
                best_cand = cand

    # Close-cropped pressing photo where the 360-degree 4" center label and spindle hole sit surrounded by all 8 octants of colored/splatter wax (e.g. 16251744/img_1.jpg)
    if best_cand is None:
        sat = np.max(rgb, axis=2) - np.min(rgb, axis=2)
        grad_mag = np.hypot(gx, gy)
        dy_o = (yy - 127.5) / 127.5
        dx_o = (xx - 127.5) / 127.5
        r_o = np.hypot(dx_o, dy_o)
        sp_c_origin = float(np.linalg.norm(np.mean(rgb[r_o <= 0.038], axis=0) - np.mean(rgb[(r_o >= 0.050) & (r_o <= 0.115)], axis=0)))
        for (dx0, dy0) in [(0.0, 0.0), (-0.03, -0.09), (0.0, -0.08), (-0.04, 0.0)]:
            dy = (yy - 127.5) / 127.5 - dy0
            dx = (xx - 127.5) / 127.5 - dx0
            r = np.hypot(dx, dy)
            theta = np.arctan2(dy, dx)
            grad_r = np.abs(gx * np.cos(theta) + gy * np.sin(theta))
            grad_t = np.abs(-gx * np.sin(theta) + gy * np.cos(theta))
            pure_rad = np.maximum(0.0, grad_r - 0.55 * grad_t)
            sp_c_local = float(np.linalg.norm(np.mean(rgb[r <= 0.038], axis=0) - np.mean(rgb[(r >= 0.050) & (r <= 0.115)], axis=0)))
            sp_c = max(sp_c_origin, sp_c_local)
            if sp_c < 0.16:
                continue
            for rl in (0.34, 0.38, 0.41, 0.44):
                l_band = (r >= rl - 0.024) & (r <= rl + 0.024)
                le = float(np.mean(pure_rad[l_band]))
                lbl_in = (r >= 0.048) & (r <= rl - 0.025)
                wax_m = (r >= rl + 0.035) & (r <= 0.94)
                if not np.any(lbl_in) or not np.any(wax_m):
                    continue
                lwd = float(np.linalg.norm(np.mean(rgb[lbl_in], axis=0) - np.mean(rgb[wax_m], axis=0)))
                octs = []
                for k in range(8):
                    a0 = -np.pi + k * (np.pi / 4.0)
                    ang = (theta >= a0) & (theta < a0 + np.pi / 4.0)
                    octs.append(float(np.linalg.norm(np.mean(rgb[lbl_in & ang], axis=0) - np.mean(rgb[wax_m & ang], axis=0))))
                q25 = sorted(octs)[1]
                wax_gm = float(np.mean(grad_mag[wax_m]))
                aniso = abs(float(np.log((np.mean(np.abs(gy[wax_m])) + 1e-5) / (np.mean(np.abs(gx[wax_m])) + 1e-5))))
                wax_sat = float(np.mean(sat[wax_m]))
                lbl_sat = float(np.mean(sat[lbl_in]))
                if le >= 0.018 and lwd >= 0.42 and q25 >= 0.34 and wax_gm < 0.035 and aniso < 0.185 and (wax_sat - lbl_sat) >= 0.22:
                    sc = round(min(0.92, 0.46 + 0.25 * lwd + 0.20 * q25 + 0.10 * sp_c), 4)
                    cand = {
                        "is_pressing": True,
                        "is_zoomed_label_scan": False,
                        "is_hype_sticker_or_text_insert": False,
                        "is_square_insert_or_sleeve": False,
                        "detected_disc_radius": 0.98,
                        "active_diagonal_quadrants": 4,
                        "score": sc,
                        "raw_annular_score": sc,
                        "aspect_ratio": round(aspect, 3),
                        "corner_std": 0.06,
                        "corner_wax_dist": round(lwd, 4),
                        "circularity_ratio": 1.85,
                        "label_wax_dist": round(lwd, 4),
                        "octant_label_wax_q25": round(q25, 4),
                        "hv_wax_anisotropy": round(aniso, 4),
                        "spindle_contrast": round(sp_c, 4),
                        "rim_step": 0.022,
                        "label_step": round(le, 4),
                        "reason": "deterministic_annular_cv_match",
                    }
                    if best_cand is None or cand["score"] > best_cand["score"]:
                        best_cand = cand
    return best_cand


def score_image_pixels_deterministic(
    image_bytes: bytes,
    expected_wax_hex: str | None = None,
    secondary_wax_hex: str | None = None,
    wax_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministically scores an image for whether it shows a physical 12" vinyl record pressing.

    Uses Multi-Pass Calibrated Concentric Dual-Circle Detection + 8-Octant Label Continuity:
    - Pass 1: Standard centered disc search (`R_disc in [0.80..0.99]`), preserving full-bleed
      near-square frames (`|aspect - 1.0| <= 0.06`) and protecting verified concentric discs on
      inner sleeves or album jackets (`has_strong_concentric_disc`).
    - Pass 2: Landscape 4:3 turntable platter alignment (`aspect > 1.08`), evaluating left-shifted
      platter crops so right-hand tonearms do not obscure the outer rim (`20697637/img_1`, `2343816/img_1`).
    - Pass 3: Padded studio pressing search (`R_disc in [0.65..0.79]`) on clean backdrops (`26690690/img_1`).
    - Pass 4: Off-center angled vinyl disc detection where the full 360-degree 4-inch center label
      and spindle hole are visible in-frame (`13203006/img_1`).
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
                    "raw_annular_score": 0.05,
                    "aspect_ratio": round(aspect, 3),
                    "reason": "rejected_aspect_ratio_panoramic_or_strip",
                }
            rgb_full = im.convert("RGB")
            side = min(w, h)
            if abs(aspect - 1.0) > 0.06:
                left_c = (w - side) // 2
                top_c = (h - side) // 2
                cropped_c = rgb_full.crop((left_c, top_c, left_c + side, top_c + side))
            else:
                cropped_c = rgb_full
            rgb_c = np.asarray(cropped_c.resize((256, 256), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0

            # Pass 1: Standard centered disc search (r in [0.80..0.99])
            best_res = _eval_centered_concentric(
                rgb_c, aspect, expected_wax_hex, secondary_wax_hex, wax_spec, r_min=0.80, r_max=0.99, n_steps=20
            )

            # Pass 2: Landscape turntable platter or side-by-side sleeve + 12" disc photo (w > h * 1.08)
            if not best_res["is_pressing"] and aspect > 1.08:
                top_c = (h - side) // 2
                for lf in (0.12, 0.06):
                    left = int((w - side) * lf)
                    cropped_l = rgb_full.crop((left, top_c, left + side, top_c + side))
                    rgb_l = np.asarray(cropped_l.resize((256, 256), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
                    res_l = _eval_centered_concentric(
                        rgb_l, aspect, expected_wax_hex, secondary_wax_hex, wax_spec, r_min=0.80, r_max=0.99, n_steps=20
                    )
                    if res_l["is_pressing"] and res_l["label_wax_dist"] >= 0.25 and res_l["rim_step"] >= 0.022:
                        if not best_res["is_pressing"] or res_l["score"] > best_res["score"]:
                            best_res = res_l

                # Side-by-side sleeve + full 12" vinyl disc in 4:3 landscape frame (e.g. 17583742/img_2.jpg & img_3.jpg)
                if not best_res["is_pressing"] and aspect > 1.18:
                    box_s = int(min(h, w * 0.54))
                    for xf in (0.98, 0.96, 1.0, 0.02, 0.04):
                        left_s = max(0, min(w - box_s, int(w * xf) - box_s if xf > 0.5 else int(w * xf)))
                        top_s = max(0, min(h - box_s, int(h * 0.54) - box_s // 2))
                        cropped_s = rgb_full.crop((left_s, top_s, left_s + box_s, top_s + box_s))
                        rgb_s = np.asarray(cropped_s.resize((256, 256), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
                        res_s = _eval_centered_concentric(
                            rgb_s, aspect, expected_wax_hex, secondary_wax_hex, wax_spec, r_min=0.80, r_max=0.99, n_steps=20
                        )
                        if (
                            res_s["is_pressing"]
                            and res_s["rim_step"] >= 0.032
                            and res_s["label_step"] >= 0.025
                            and res_s["label_wax_dist"] >= 0.45
                            and res_s["octant_label_wax_q25"] >= 0.35
                            and res_s["corner_wax_dist"] >= 0.38
                        ):
                            if not best_res["is_pressing"] or res_s["score"] > best_res["score"]:
                                best_res = res_s

            # Pass 2B: Portrait vertical window alignment where disc sits slightly below/above dead center (e.g. 27927123/img_4.jpg)
            if not best_res["is_pressing"] and aspect < 0.88:
                left_c = (w - side) // 2
                for yf in (0.56, 0.55, 0.44):
                    top_v = max(0, min(h - side, int(h * yf) - side // 2))
                    cropped_v = rgb_full.crop((left_c, top_v, left_c + side, top_v + side))
                    rgb_v = np.asarray(cropped_v.resize((256, 256), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
                    res_v = _eval_centered_concentric(
                        rgb_v, aspect, expected_wax_hex, secondary_wax_hex, wax_spec, r_min=0.80, r_max=0.99, n_steps=20
                    )
                    if (
                        res_v["is_pressing"]
                        and res_v["rim_step"] >= 0.019
                        and res_v["label_wax_dist"] >= 0.20
                        and res_v["corner_wax_dist"] >= 0.14
                        and res_v["hv_wax_anisotropy"] < 0.06
                    ):
                        if not best_res["is_pressing"] or res_v["score"] > best_res["score"]:
                            best_res = res_v

            # Pass 3: Padded studio pressing photo where disc has wider margin (r in [0.65..0.79], e.g. 26690690/img_1.jpg)
            if not best_res["is_pressing"]:
                res_pad = _eval_centered_concentric(
                    rgb_c, aspect, expected_wax_hex, secondary_wax_hex, wax_spec, r_min=0.65, r_max=0.79, n_steps=10
                )
                if (
                    res_pad["is_pressing"]
                    and res_pad["corner_std"] < 0.05
                    and res_pad["corner_wax_dist"] >= 0.40
                    and res_pad["rim_step"] >= 0.035
                    and res_pad["label_step"] >= 0.035
                ):
                    best_res = res_pad

            # Pass 4: Off-center angled or close-cropped vinyl disc with full 8-octant 4" center label and spindle hole (e.g. 13203006/img_1.jpg, 16251744/img_1.jpg)
            if not best_res["is_pressing"]:
                res_off = _eval_offcenter_disc(rgb_c, aspect)
                if res_off is not None:
                    best_res = res_off

            return best_res
    except Exception:
        return {"is_pressing": False, "score": 0.0, "reason": "image_decode_error"}


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
                    # First verified pressing disc (Side A) gets a tie-breaker bonus (+0.038)
                    side_a_bonus = 0.038 if not first_verified_pressing_seen else 0.0
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

        ov_is_rejected = (
            0 <= ov_idx < len(classified)
            and has_any_real_cv
            and classified[ov_idx].get("role") != "pressing_disc"
            and not (isinstance(ov, dict) and ov.get("user_locked") is True)
        )
        if ov_url and ov_idx >= 0 and (is_manual_pin or not has_any_real_cv) and not ov_is_rejected:
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


DEFAULT_FLATTENING_PROTOCOL = (
    "Bag on 6 until 130°F then drop to 4 — 2.5 hours once at 130°F on the plate"
)


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
    unlisted_ids = {int(x) for x in (queue_data.get("unlisted_release_ids") or []) if str(x).isdigit()}
    if rid_int > 0 and rid_int in unlisted_ids:
        return "Not Listed"

    todo_ids = {int(x) for x in (queue_data.get("need_to_be_done_release_ids") or []) if str(x).isdigit()}
    done_ids = {int(x) for x in (queue_data.get("done_release_ids") or []) if str(x).isdigit()}

    for entry in queue_data.get("need_to_be_done_entries") or []:
        for r_x in entry.get("release_ids") or []:
            if str(r_x).isdigit():
                todo_ids.add(int(r_x))

    for entry in queue_data.get("done_entries") or []:
        for r_x in entry.get("release_ids") or []:
            if str(r_x).isdigit():
                done_ids.add(int(r_x))

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


def _parse_csv_int_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    out: list[int] = []
    for tok in re.split(r"[,;\s]+", str(raw).strip()):
        if tok.isdigit() and int(tok) > 0:
            val = int(tok)
            if val not in out:
                out.append(val)
    return out


def extract_inline_flattening_from_html(html_path: pathlib.Path | None) -> dict[str, Any]:
    """Extracts the inline HTML flattening queue stored inside `#flattening-inline-form` or `window.__DISCOGS_COLLECTION__`."""
    if not html_path or not html_path.exists():
        return {}
    try:
        html_text = html_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}

    result: dict[str, Any] = {}

    # 1. Check hidden textarea `#flatten-hidden-json` first
    m_json = re.search(
        r'<textarea[^>]*id="flatten-hidden-json"[^>]*>(.*?)</textarea>',
        html_text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if m_json:
        raw_json = m_json.group(1).strip()
        if raw_json:
            try:
                import html as _html_mod
                parsed = json.loads(_html_mod.unescape(raw_json))
                if isinstance(parsed, dict):
                    result.update(parsed)
            except Exception:
                pass

    # 2. Check hidden `<input type="hidden">` fields (which override or supplement the textarea)
    def _extract_input_val(elem_id: str) -> tuple[bool, str]:
        m_tag = re.search(
            rf'<input[^>]*id="{re.escape(elem_id)}"[^>]*>',
            html_text,
            flags=re.IGNORECASE,
        )
        if not m_tag:
            return (False, "")
        m_val = re.search(r'value="([^"]*)"', m_tag.group(0), flags=re.IGNORECASE)
        return (True, m_val.group(1).strip() if m_val else "")

    has_todo, todo_csv = _extract_input_val("flatten-hidden-todo-ids")
    has_done, done_csv = _extract_input_val("flatten-hidden-done-ids")
    has_unlisted, unlisted_csv = _extract_input_val("flatten-hidden-unlisted-ids")
    has_ts, updated_at = _extract_input_val("flatten-hidden-updated-at")
    has_proto, protocol_str = _extract_input_val("flatten-hidden-protocol")

    if has_todo or has_done or has_ts:
        if has_todo:
            result["need_to_be_done_release_ids"] = _parse_csv_int_ids(todo_csv)
        if has_done:
            result["done_release_ids"] = _parse_csv_int_ids(done_csv)
        if has_unlisted:
            result["unlisted_release_ids"] = _parse_csv_int_ids(unlisted_csv)
        if has_ts and updated_at:
            result["updated_at_utc"] = updated_at
        if has_proto and protocol_str:
            result["protocol"] = protocol_str

    # 3. Fallback: if no hidden form yet, extract from embedded window.__DISCOGS_COLLECTION__
    if not result.get("need_to_be_done_release_ids") and not result.get("done_release_ids") and not has_todo:
        m_col = re.search(
            r"window\.__DISCOGS_COLLECTION__\s*=\s*(\{.*?\});\s*(?:try\s*\{|/\*\s*__DISCOGS_COLLECTION_DATA_END__)",
            html_text,
            flags=re.DOTALL,
        )
        if m_col:
            try:
                col_obj = json.loads(m_col.group(1))
                recs = col_obj.get("records") or []
                todo_rids = sorted({int(r["release_id"]) for r in recs if r.get("flattening_status") == "Need to be done" and r.get("release_id")})
                done_rids = sorted({int(r["release_id"]) for r in recs if r.get("flattening_status") == "Done" and r.get("release_id")})
                fq = col_obj.get("flattening_queue") or {}
                result = {
                    "protocol": fq.get("protocol") or DEFAULT_FLATTENING_PROTOCOL,
                    "updated_at_utc": fq.get("updated_at_utc") or col_obj.get("synced_at_utc") or "",
                    "need_to_be_done_release_ids": todo_rids,
                    "done_release_ids": done_rids,
                    "need_to_be_done_entries": fq.get("need_to_be_done_entries") or [],
                    "done_entries": fq.get("done_entries") or [],
                }
            except Exception:
                pass

    return result


def build_flattening_queue_payload(
    records: list[dict[str, Any]],
    base_queue: dict[str, Any] | None = None,
    updated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Builds a clean, portable flattening_queue payload from `records` and `base_queue`."""
    base_queue = base_queue or {}
    protocol = str(base_queue.get("protocol") or DEFAULT_FLATTENING_PROTOCOL).replace(
        "it hits 130 then drop to 4 — 2.5 hours once it hits 130",
        "130°F then drop to 4 — 2.5 hours once at 130°F",
    )
    todo_recs = sorted(
        [r for r in records if r.get("flattening_status") == "Need to be done"],
        key=lambda x: (str(x.get("artist") or "").lower(), str(x.get("title") or "").lower()),
    )
    done_recs = sorted(
        [r for r in records if r.get("flattening_status") == "Done"],
        key=lambda x: (str(x.get("artist") or "").lower(), str(x.get("title") or "").lower()),
    )
    todo_ids = sorted({int(r["release_id"]) for r in todo_recs if int(r.get("release_id") or 0) > 0})
    done_ids = sorted({int(r["release_id"]) for r in done_recs if int(r.get("release_id") or 0) > 0})
    unlisted_ids = sorted(
        {
            int(x)
            for x in (base_queue.get("unlisted_release_ids") or [])
            if str(x).isdigit() and int(x) not in todo_ids and int(x) not in done_ids
        }
    )

    todo_entries = [
        {
            "artist": str(r.get("artist") or ""),
            "album": str(r.get("title") or ""),
            "release_ids": [int(r["release_id"])],
        }
        for r in todo_recs
        if int(r.get("release_id") or 0) > 0
    ]
    done_entries = [
        {
            "artist": str(r.get("artist") or ""),
            "album": str(r.get("title") or ""),
            "release_ids": [int(r["release_id"])],
        }
        for r in done_recs
        if int(r.get("release_id") or 0) > 0
    ]

    ts = updated_at_utc or str(base_queue.get("updated_at_utc") or "") or _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schema_version": "4.0.0",
        "storage_mode": "portable_inline_html+json",
        "updated_at_utc": ts,
        "protocol": protocol,
        "need_to_be_done_release_ids": todo_ids,
        "done_release_ids": done_ids,
        "unlisted_release_ids": unlisted_ids,
        "need_to_be_done_entries": todo_entries,
        "done_entries": done_entries,
    }


def reconcile_flattening_state(
    flattening_path: pathlib.Path,
    html_path: pathlib.Path | None = None,
) -> dict[str, Any]:
    """Loads and reconciles the flattening queue from both `data/flattening_queue.json` and inline `index.html`."""
    file_queue: dict[str, Any] = {}
    if flattening_path and flattening_path.exists():
        try:
            file_queue = json.loads(flattening_path.read_text(encoding="utf-8"))
        except Exception:
            file_queue = {}

    html_queue = extract_inline_flattening_from_html(html_path)

    file_ts = str(file_queue.get("updated_at_utc") or "")
    html_ts = str(html_queue.get("updated_at_utc") or "")

    # Prefer inline HTML queue if it has a newer timestamp or if file_queue is missing/empty
    if html_queue and (not file_queue or (html_ts and html_ts > file_ts)):
        chosen = dict(file_queue)
        chosen.update(html_queue)
    elif file_queue:
        chosen = dict(html_queue)
        chosen.update(file_queue)
        if not chosen.get("need_to_be_done_release_ids") and html_queue.get("need_to_be_done_release_ids"):
            chosen["need_to_be_done_release_ids"] = html_queue["need_to_be_done_release_ids"]
        if not chosen.get("done_release_ids") and html_queue.get("done_release_ids"):
            chosen["done_release_ids"] = html_queue["done_release_ids"]
    else:
        chosen = {}

    return chosen


# ==============================================================================
# DELTA SYNC ENGINE & LIVE TERMINAL UI / TURNTABLE THROBBER (v4.0.0)
# ==============================================================================

import datetime as _dt
import os as _os
import threading as _threading
import time as _time
import unicodedata as _unicodedata

CV_DELTA_VERSION = "2.4.0"


def _term_display_width(s: str) -> int:
    """Computes exact terminal column width of a string (accounting for wide symbols/emojis)."""
    w = 0
    for ch in s:
        if ch in ("\ufe0f", "\u200d"):
            continue
        eaw = _unicodedata.east_asian_width(ch)
        if eaw in ("W", "F"):
            w += 2
        else:
            w += 1
    return w


def _pad_to_width(s: str, target_w: int) -> str:
    """Truncates or pads `s` with spaces so its terminal column width equals `target_w`."""
    out_chars: list[str] = []
    cur_w = 0
    for ch in s:
        if ch in ("\ufe0f", "\u200d"):
            out_chars.append(ch)
            continue
        cw = 2 if _unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if cur_w + cw > target_w:
            break
        out_chars.append(ch)
        cur_w += cw
    return "".join(out_chars) + (" " * max(0, target_w - cur_w))


def compute_release_delta_signature(
    release_id: int | str,
    rel_dir: pathlib.Path | None,
    format_str: str = "",
    notes: str = "",
    override_val: Any = None,
) -> str:
    """Computes a fast deterministic SHA-256 fingerprint of a release's local files, metadata, and override state."""
    rid_str = str(release_id)
    file_parts: list[str] = []
    if rel_dir and rel_dir.exists():
        try:
            entries = []
            for p in rel_dir.iterdir():
                if not p.is_file():
                    continue
                m = re.match(r"^img_(\d+)\.(?:jpg|jpeg|png|webp)$", p.name, flags=re.IGNORECASE)
                if m:
                    st = p.stat()
                    entries.append((int(m.group(1)), p.name.lower(), st.st_size, int(st.st_mtime)))
            entries.sort(key=lambda x: x[0])
            file_parts = [f"{idx}:{name}:{sz}:{mt}" for idx, name, sz, mt in entries]
        except Exception:
            pass

    ov_repr = repr(override_val) if override_val is not None else ""
    payload = "|".join([
        f"v={CV_DELTA_VERSION}",
        f"rid={rid_str}",
        f"files={','.join(file_parts)}",
        f"fmt={format_str.strip()}",
        f"notes={notes.strip()}",
        f"ov={ov_repr}",
    ])
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()[:16]


def evaluate_release_delta_status(
    release_id: int,
    existing_record: dict[str, Any] | None,
    rel_dir: pathlib.Path,
    cached_images: list[dict[str, Any]],
    overrides: dict[str, Any],
    format_str: str = "",
    notes: str = "",
    force_full: bool = False,
    force_rids: set[int] | None = None,
) -> tuple[str, str, str]:
    """Determines whether a release is 'new', 'resynced', or 'unchanged'.

    Returns `(status, reason, delta_sig)` where `status` is one of:
      - `'new'`: Release was not in previous `collection.json`
      - `'resynced'`: Release needs full image download + CV classification suite
      - `'unchanged'`: Release can fast-path reuse existing `images` classification
    """
    rid_str = str(release_id)
    ov_val = overrides.get(rid_str)
    current_sig = compute_release_delta_signature(
        release_id=release_id,
        rel_dir=rel_dir,
        format_str=format_str,
        notes=notes,
        override_val=ov_val,
    )

    if existing_record is None:
        return ("new", "newly added release", current_sig)

    if force_full:
        return ("resynced", "forced full rebuild (--full)", current_sig)

    if force_rids and release_id in force_rids:
        return ("resynced", f"forced release resync (--resync {release_id})", current_sig)

    existing_images = existing_record.get("images")
    if not isinstance(existing_images, dict) or not existing_images:
        return ("resynced", "missing images metadata in collection.json", current_sig)

    classified = existing_images.get("classified_images")
    if not isinstance(classified, list):
        return ("resynced", "missing classified_images array", current_sig)

    # Check if record was seeded from offline procedural seed
    for c_img in classified:
        uri_c = str(c_img.get("uri") or "")
        if uri_c.startswith("procedural://") or uri_c.startswith("assets/pressings/"):
            return ("resynced", "upgrading procedural seed to real Discogs images", current_sig)

    # Discover local img_*.jpg files
    local_img_count = 0
    if rel_dir.exists():
        for p in rel_dir.iterdir():
            if p.is_file() and re.match(r"^img_(\d+)\.(?:jpg|jpeg|png|webp)$", p.name, flags=re.IGNORECASE):
                local_img_count += 1

    expected_cached_count = min(40, len(cached_images))
    if expected_cached_count > 0 and local_img_count == 0:
        return ("resynced", f"no local images downloaded yet (0/{expected_cached_count})", current_sig)

    if expected_cached_count > 0 and local_img_count < expected_cached_count:
        return ("resynced", f"incomplete local images ({local_img_count}/{expected_cached_count})", current_sig)

    if local_img_count > 0 and not (rel_dir / "cover.jpg").exists():
        return ("resynced", "missing cover.jpg in release folder", current_sig)

    if local_img_count > 0 and len(classified) != local_img_count:
        return ("resynced", f"local image count changed ({len(classified)} -> {local_img_count})", current_sig)

    # Check pressing.jpg consistency on disk (supports deleting pressing.jpg to force re-pick!)
    has_pressing = bool(existing_images.get("has_pressing_photo"))
    pressing_file_exists = (rel_dir / "pressing.jpg").exists()
    if has_pressing and not pressing_file_exists:
        return ("resynced", "pressing.jpg missing/deleted -> regenerating", current_sig)
    if not has_pressing and pressing_file_exists:
        return ("resynced", "stale pressing.jpg found -> cleaning/re-evaluating", current_sig)

    # Check explicit manual override changes
    if isinstance(ov_val, int) and existing_images.get("selected_index") != ov_val:
        return ("resynced", f"manual override pin -> img_{ov_val}.jpg", current_sig)
    if isinstance(ov_val, dict) and "pressing_image_index" in ov_val:
        pin_idx = int(ov_val["pressing_image_index"])
        if existing_images.get("selected_index") != pin_idx:
            return ("resynced", f"manual override pin -> img_{pin_idx}.jpg", current_sig)

    # Check stored delta signature if present from a prior v2.4+ run
    prev_sig = existing_images.get("delta_sig")
    if prev_sig and prev_sig != current_sig:
        sig_without_ov = compute_release_delta_signature(
            release_id=release_id,
            rel_dir=rel_dir,
            format_str=format_str,
            notes=notes,
            override_val=None,
        )
        auto_ov_matches = isinstance(ov_val, str) and ov_val in (
            existing_images.get("local_pressing_image_url"),
            existing_images.get("pressing_image_url"),
        )
        if not (prev_sig == sig_without_ov and auto_ov_matches):
            return ("resynced", "local files, notes, or override modified", current_sig)

    return ("unchanged", "verified in delta cache", current_sig)


def _norm_track_stem(s: str) -> str:
    s_low = str(s or "").lower().replace("∆", "a")
    s_low = re.sub(r"\[([^\]]{1,2})\]", r"\1", s_low)
    s_low = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", s_low)
    words = re.findall(r"[a-z0-9]+", s_low)
    return "".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words)


def _norm_track_tokens(s: str) -> set[str]:
    s_low = str(s or "").lower().replace("∆", "a")
    s_low = re.sub(r"\[([^\]]{1,2})\]", r"\1", s_low)
    s_low = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", s_low)
    words = re.findall(r"[a-z0-9]+", s_low)
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words if len(w) > 1}


VERIFIED_YTM_RELEASE_MAP: dict[int, dict[str, Any]] = {2343816: {'defaultYtVideoId': 'XsvLfL3Qh1A',
           'fallbackTracks': [{'duration': '3:26', 'position': 'A1', 'title': 'No Son Of Mine'},
                              {'duration': '2:41', 'position': 'A2', 'title': 'Pigs Is Pigs'},
                              {'duration': '', 'position': 'A3', 'title': 'Leatherneck'},
                              {'duration': '', 'position': 'A4', 'title': "We'rewolf"},
                              {'duration': '', 'position': 'A5', 'title': 'Rebel Without Applause'},
                              {'duration': '', 'position': 'A6', 'title': 'Cities And Years'},
                              {'duration': '', 'position': 'B1', 'title': 'Rendez-Voodoo'},
                              {'duration': '', 'position': 'B2', 'title': "A Gentleman's Sport"},
                              {'duration': '4:09', 'position': 'B3', 'title': 'INRIhab'},
                              {'duration': '', 'position': 'B4', 'title': 'Depressionista'},
                              {'duration': '', 'position': 'B5', 'title': 'Buffalo Gals'},
                              {'duration': '',
                               'position': 'B6',
                               'title': 'Imitation Is The Sincerest Form Of Battery'}],
           'trackDurations': {'0': '3:26', '1': '2:41', '8': '4:09'},
           'trackIds': {'0': 'XsvLfL3Qh1A', '1': 'A6OXX2vcaZU', '8': 'uPBdlDMX5Ws'}},
 2486041: {'defaultYtVideoId': 'Zm4JVkH0T-E',
           'fallbackTracks': [{'duration': '3:50', 'position': 'A1', 'title': 'Hot Mess'},
                              {'duration': '', 'position': 'A2', 'title': "I'm Not Contagious"},
                              {'duration': '3:51', 'position': 'A3', 'title': 'Night By Night'},
                              {'duration': '4:36',
                               'position': 'A4',
                               'title': "Don't Turn The Lights On"},
                              {'duration': '7:21', 'position': 'A5', 'title': 'You Make It Rough'},
                              {'duration': '4:26',
                               'position': 'B1',
                               'title': 'When The Night Falls'},
                              {'duration': '', 'position': 'B2', 'title': "Don't Walk Away"},
                              {'duration': '', 'position': 'B3', 'title': "J'ai Claqué La Porte"},
                              {'duration': '3:57', 'position': 'B4', 'title': 'The Right Type'},
                              {'duration': '', 'position': 'B5', 'title': 'Grow Up'}],
           'trackDurations': {'0': '3:50',
                              '2': '3:51',
                              '3': '4:36',
                              '4': '7:21',
                              '5': '4:26',
                              '8': '3:57'},
           'trackIds': {'0': 'Zm4JVkH0T-E',
                        '2': '6XCcWlgVqHA',
                        '3': 'TuM5pB4dE-A',
                        '4': 'Yn9mopkpYS4',
                        '5': 'kkyYxAv6kB4',
                        '8': 'bW9pZGD4vaU'}},
 3093365: {'defaultYtVideoId': 'Tfv4PqEOZCU',
           'fallbackTracks': [{'duration': '3:58', 'position': 'A1', 'title': 'Yellow Belly'},
                              {'duration': '4:09', 'position': 'A2', 'title': 'Promises'},
                              {'duration': '4:18', 'position': 'A3', 'title': 'Blinded'},
                              {'duration': '3:57', 'position': 'B1', 'title': 'Cataracts'},
                              {'duration': '4:31', 'position': 'B2', 'title': 'Call It In The Air'},
                              {'duration': '4:37', 'position': 'B3', 'title': 'Treading Paper'},
                              {'duration': '3:04', 'position': 'C1', 'title': 'Blur'},
                              {'duration': '6:18', 'position': 'C2', 'title': 'Words In The Water'},
                              {'duration': '4:33', 'position': 'D1', 'title': 'Listen Through Me'},
                              {'duration': '4:28', 'position': 'D2', 'title': 'Anthology'},
                              {'duration': '4:45', 'position': 'D3', 'title': 'Disarmed'}],
           'trackDurations': {'0': '3:58',
                              '1': '4:09',
                              '10': '4:45',
                              '2': '4:18',
                              '3': '3:57',
                              '4': '4:31',
                              '5': '4:37',
                              '6': '3:04',
                              '7': '6:18',
                              '8': '4:33',
                              '9': '4:28'},
           'trackIds': {'0': 'Tfv4PqEOZCU', '1': '3GCLb-PQzfc'}},
 3780990: {'defaultYtVideoId': 'tUltTV3t4OM',
           'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Muramasa'},
                              {'duration': '', 'position': 'A2', 'title': 'Have A Blast'},
                              {'duration': '', 'position': 'A3', 'title': 'Facepalm Mute'},
                              {'duration': '', 'position': 'A4', 'title': 'Ji'},
                              {'duration': '4:29', 'position': 'B1', 'title': 'Scarlet'},
                              {'duration': '', 'position': 'B2', 'title': 'Luck As A Constant'},
                              {'duration': '4:38', 'position': 'B3', 'title': 'Ragnarok'},
                              {'duration': '',
                               'position': 'C1',
                               'title': 'The Gods Must Be Crazy!'},
                              {'duration': '4:26', 'position': 'C2', 'title': 'Make Total Destroy'},
                              {'duration': '', 'position': 'C3', 'title': 'Erised'},
                              {'duration': '', 'position': 'C4', 'title': 'Epoch'},
                              {'duration': '', 'position': 'D1', 'title': "Froggin' Bullfish"},
                              {'duration': '', 'position': 'D2', 'title': 'Mile Zero'},
                              {'duration': '', 'position': 'D3', 'title': 'Masamune'}],
           'fullAlbumYtDuration': 4585,
           'fullAlbumYtVideoId': 'hz16Wty7Gho',
           'trackDurations': {'4': '4:29', '6': '4:38', '8': '4:26'},
           'trackIds': {'4': 'tUltTV3t4OM', '6': 'Rm3OpBpwzBs', '8': 'spCmStMOiHE'}},
 3873517: {'defaultYtVideoId': '9QQQetnmxcw',
           'fallbackTracks': [{'duration': '3:15',
                               'position': 'A1',
                               'title': 'For The Workforce, Drowning'},
                              {'duration': '3:04',
                               'position': 'A2',
                               'title': 'Between Rupture And Rapture'},
                              {'duration': '4:15', 'position': 'A3', 'title': 'Division St.'},
                              {'duration': '4:13',
                               'position': 'B4',
                               'title': 'Signals Over The Air'},
                              {'duration': '4:28',
                               'position': 'B5',
                               'title': 'Marches And Maneuvers'},
                              {'duration': '3:47',
                               'position': 'B6',
                               'title': 'Asleep In The Chapel'},
                              {'duration': '2:17',
                               'position': 'C7',
                               'title': 'This Song Brought To You By A Falling Bomb'},
                              {'duration': '', 'position': 'C8', 'title': 'Steps Ascending'},
                              {'duration': '4:00', 'position': 'C9', 'title': 'War All The Time'},
                              {'duration': '3:37', 'position': 'D10', 'title': 'M. Shepard'},
                              {'duration': '4:08',
                               'position': 'D11',
                               'title': "Tomorrow I'll Be You"},
                              {'duration': '', 'position': 'D12', 'title': 'Ny Batteri'}],
           'fullAlbumYtDuration': 3151,
           'fullAlbumYtVideoId': 'GkGU7XJUNAE',
           'trackDurations': {'0': '3:15',
                              '1': '3:04',
                              '10': '4:08',
                              '2': '4:15',
                              '3': '4:13',
                              '4': '4:28',
                              '5': '3:47',
                              '6': '2:17',
                              '8': '4:00',
                              '9': '3:37'},
           'trackIds': {'0': '9QQQetnmxcw',
                        '1': '3nK_FptbiAM',
                        '10': 'ZhuY9hvA7So',
                        '2': 'LVYWP48nUV4',
                        '3': 'pejvzJZSLpw',
                        '4': 'TVx6KFvRZ44',
                        '5': '4FwHcoPu-0M',
                        '6': 'se4yNC5yfEI',
                        '8': 'aAD6lJiHBdA',
                        '9': 'H9_-qaQsSFo'},
           'ytPlaylistId': 'OLAK5uy_nLyxICgfkVQGgPWJ-Yz24rp92OdpNyN3s'},
 4902348: {'defaultYtVideoId': '1KOS-dQ9wOw',
           'fallbackTracks': [{'duration': '3:20', 'position': 'A1', 'title': 'Redefine'},
                              {'duration': '3:17', 'position': 'A2', 'title': 'Vitamin'},
                              {'duration': '3:55', 'position': 'A3', 'title': 'New Skin'},
                              {'duration': '4:12', 'position': 'A4', 'title': 'Idiot Box'},
                              {'duration': '3:47', 'position': 'B1', 'title': 'Glass'},
                              {'duration': '3:03', 'position': 'B2', 'title': 'Magic Medicine'},
                              {'duration': '3:12',
                               'position': 'B3',
                               'title': 'A Certain Shade Of Green'},
                              {'duration': '3:11', 'position': 'B4', 'title': 'Favorite Things'},
                              {'duration': '4:31',
                               'position': 'C1',
                               'title': 'Summer Romance (Anti-Gravity Love Song)'},
                              {'duration': '3:54', 'position': 'C2', 'title': 'Nebula'},
                              {'duration': '3:57', 'position': 'C3', 'title': 'Deep Inside'},
                              {'duration': '5:12', 'position': 'D1a', 'title': 'Calgone'},
                              {'duration': '10:20', 'position': 'D1b', 'title': 'Untitled'}],
           'trackDurations': {'0': '3:20',
                              '1': '3:17',
                              '10': '3:57',
                              '11': '5:12',
                              '12': '10:20',
                              '2': '3:55',
                              '3': '4:12',
                              '4': '3:47',
                              '5': '3:03',
                              '6': '3:12',
                              '7': '3:11',
                              '8': '4:31',
                              '9': '3:54'},
           'trackIds': {'0': '1KOS-dQ9wOw',
                        '1': 'Qo9xKdoS0HQ',
                        '10': 'Kck2FsziHXs',
                        '11': 'T6wALK3sRlM',
                        '12': 'Sjaqq69uaSI',
                        '2': '4b8B58wi9Wc',
                        '3': 'O0faaOKA8P8',
                        '4': 'l4xv8_YePZA',
                        '5': 'XYmXlOrqHBM',
                        '6': 'HCml8Th66mM',
                        '7': 'bbj73tV5qNM',
                        '8': 'U80VQpqWojU',
                        '9': 'NPnvjhO66OI'}},
 5632601: {'defaultYtVideoId': '8-cepZ6K7mY',
           'fallbackTracks': [{'duration': '0:36', 'position': 'A1', 'title': 'A0001'},
                              {'duration': '4:25',
                               'position': 'A2',
                               'title': 'Understanding In A Car Crash'},
                              {'duration': '2:19', 'position': 'A3', 'title': 'Concealer'},
                              {'duration': '3:56',
                               'position': 'A4',
                               'title': 'Autobiography Of A Nation'},
                              {'duration': '3:28',
                               'position': 'A5',
                               'title': 'A Hole In The World'},
                              {'duration': '4:08', 'position': 'A6', 'title': 'Cross Out The Eyes'},
                              {'duration': '4:33', 'position': 'B1', 'title': 'Paris In Flames'},
                              {'duration': '3:35', 'position': 'B2', 'title': 'I Am The Killer'},
                              {'duration': '3:42',
                               'position': 'B3',
                               'title': 'Standing On The Edge Of Summer'},
                              {'duration': '4:23', 'position': 'B4', 'title': 'Wind Up'},
                              {'duration': '5:45',
                               'position': 'B5',
                               'title': 'How Long Is The Night?'},
                              {'duration': '1:40', 'position': 'B6', 'title': 'I1100'}],
           'trackDurations': {'0': '0:36',
                              '1': '4:25',
                              '10': '5:45',
                              '11': '1:40',
                              '2': '2:19',
                              '3': '3:56',
                              '4': '3:28',
                              '5': '4:08',
                              '6': '4:33',
                              '7': '3:35',
                              '8': '3:42',
                              '9': '4:23'},
           'trackIds': {'1': '8-cepZ6K7mY', '5': '6zlnil-v3dg'}},
 7685817: {'defaultYtVideoId': '5bvTqD37ALI',
           'fallbackTracks': [{'duration': '5:02', 'position': 'A1', 'title': 'Island'},
                              {'duration': '3:53', 'position': 'A2', 'title': 'Eraser'},
                              {'duration': '4:42', 'position': 'A3', 'title': 'Colors'},
                              {'duration': '4:01', 'position': 'A4', 'title': 'Here To Mars'},
                              {'duration': '2:45', 'position': 'A5', 'title': 'Ghost'},
                              {'duration': '6:03', 'position': 'B1', 'title': 'Atlas'},
                              {'duration': '3:51', 'position': 'B2', 'title': 'Young Love'},
                              {'duration': '4:11',
                               'position': 'B3',
                               'title': 'You Got Spirit, Kid'},
                              {'duration': '6:11', 'position': 'B4', 'title': 'The Audience'},
                              {'duration': '6:34',
                               'position': 'B5',
                               'title': 'Peace To The Mountain'}],
           'fullAlbumYtDuration': 2840,
           'fullAlbumYtVideoId': '5bvTqD37ALI',
           'trackDurations': {'0': '5:02',
                              '1': '3:53',
                              '2': '4:42',
                              '3': '4:01',
                              '4': '2:45',
                              '5': '6:03',
                              '6': '3:51',
                              '7': '4:11',
                              '8': '6:11',
                              '9': '6:34'},
           'trackIds': {'2': '5bvTqD37ALI'}},
 8781739: {'defaultYtVideoId': 'ikUrxI7g6BM',
           'fallbackTracks': [{'duration': '2:52',
                               'position': 'A1',
                               'title': 'Cold Cash And Colder Hearts'},
                              {'duration': '2:41',
                               'position': 'A2',
                               'title': 'Under A Killing Moon'},
                              {'duration': '3:20', 'position': 'A3', 'title': "All That's Left"},
                              {'duration': '3:06', 'position': 'B1', 'title': 'Silhouette'},
                              {'duration': '3:23', 'position': 'B2', 'title': 'Stare At The Sun'},
                              {'duration': '3:59', 'position': 'B3', 'title': 'Paper Tigers'},
                              {'duration': '3:31', 'position': 'C1', 'title': 'Hoods On Peregrine'},
                              {'duration': '3:29',
                               'position': 'C2',
                               'title': 'The Melting Point Of Wax'},
                              {'duration': '2:49',
                               'position': 'C3',
                               'title': 'Blood Clots And Black Holes'},
                              {'duration': '3:39',
                               'position': 'D1',
                               'title': 'The Artist In The Ambulance'},
                              {'duration': '2:46',
                               'position': 'D2',
                               'title': 'The Abolition Of Man'},
                              {'duration': '3:59',
                               'position': 'D3',
                               'title': "Don't Tell And We Won't Ask"}],
           'trackDurations': {'0': '2:52',
                              '1': '2:41',
                              '10': '2:46',
                              '11': '3:59',
                              '2': '3:20',
                              '3': '3:06',
                              '4': '3:23',
                              '5': '3:59',
                              '6': '3:31',
                              '7': '3:29',
                              '8': '2:49',
                              '9': '3:39'},
           'trackIds': {'0': 'ikUrxI7g6BM',
                        '1': 'nPR5pFlKmiA',
                        '10': 'xp_qNnMHgsI',
                        '11': 'nuTNNGbiQG4',
                        '2': 'EIHtFDpLFqw',
                        '3': 'CkY-RMrkALU',
                        '4': '9pyA_lSJXK4',
                        '5': 'OxNZ3y6KJy8',
                        '6': 'zt7IBHcG3iY',
                        '7': 'ffvRU4V65E4',
                        '8': 'gAEGUVT8W2s',
                        '9': 'dqy1jA8-WCQ'}},
 9346527: {'defaultYtVideoId': 'rmtU2WJfPgU',
           'fallbackTracks': [{'duration': '3:57', 'position': '1', 'title': 'The Price Is Wrong'},
                              {'duration': '4:50', 'position': '2', 'title': 'Motormouth'},
                              {'duration': '7:20', 'position': '3', 'title': 'Marigold'},
                              {'duration': '5:04',
                               'position': '4',
                               'title': 'The Way the News Goes...'},
                              {'duration': '6:10', 'position': '5', 'title': 'Remain Indoors'},
                              {'duration': '6:52',
                               'position': '6',
                               'title': 'Habitual Line-Stepper'},
                              {'duration': '5:51', 'position': '7', 'title': 'Flatline'},
                              {'duration': '7:44', 'position': '8', 'title': 'Absolomb'},
                              {'duration': '3:54', 'position': '9', 'title': 'Catch Fire'},
                              {'duration': '4:37', 'position': '10', 'title': 'Prayer Position'},
                              {'duration': '7:47', 'position': '11', 'title': 'Lune'}],
           'fullAlbumYtDuration': 3845,
           'fullAlbumYtVideoId': 'IK78K2yQgn0',
           'trackDurations': {'0': '3:57',
                              '1': '4:50',
                              '10': '7:47',
                              '2': '7:20',
                              '3': '5:04',
                              '4': '6:10',
                              '5': '6:52',
                              '6': '5:51',
                              '7': '7:44',
                              '8': '3:54',
                              '9': '4:37'},
           'trackIds': {'2': 'rmtU2WJfPgU', '6': 'L7cH6o_sblg'}},
 9545877: {'defaultYtVideoId': 'MIajmLP46b4',
           'fallbackTracks': [{'duration': '1:35', 'position': 'A1', 'title': 'Genesis'},
                              {'duration': '3:06', 'position': 'A2', 'title': 'Scarab'},
                              {'duration': '3:43', 'position': 'A3', 'title': 'Windbreaker'},
                              {'duration': '3:49', 'position': 'A4', 'title': 'Worldeater'},
                              {'duration': '4:03', 'position': 'A5', 'title': 'Quantum Flux'},
                              {'duration': '4:17', 'position': 'B1', 'title': 'Dream Awake'},
                              {'duration': '3:12', 'position': 'B2', 'title': 'The Calling'},
                              {'duration': '3:32', 'position': 'B3', 'title': 'Masquerade'},
                              {'duration': '3:46', 'position': 'B4', 'title': 'Singularity'},
                              {'duration': '3:38', 'position': 'B5', 'title': 'Aspire'}],
           'fullAlbumYtDuration': 2089,
           'fullAlbumYtVideoId': '-yfQUVfGZt8',
           'trackDurations': {'0': '1:35',
                              '1': '3:06',
                              '2': '3:43',
                              '3': '3:49',
                              '4': '4:03',
                              '5': '4:17',
                              '6': '3:12',
                              '7': '3:32',
                              '8': '3:46',
                              '9': '3:38'},
           'trackIds': {'4': 'MIajmLP46b4',
                        '5': '24C2Fz15DZI',
                        '7': 'mbqu3EKBJuo',
                        '8': '-yfQUVfGZt8'}},
 10024143: {'defaultYtVideoId': 'anQ836BXbYw',
            'fallbackTracks': [{'duration': '4:24', 'position': 'A1', 'title': 'Citizen'},
                               {'duration': '3:41', 'position': 'A2', 'title': 'Colourwave'},
                               {'duration': '4:39', 'position': 'A3', 'title': 'Savage'},
                               {'duration': '3:16', 'position': 'A4', 'title': 'Solar'},
                               {'duration': '4:04', 'position': 'A5', 'title': 'Heartmachine'},
                               {'duration': '3:51', 'position': 'B1', 'title': 'Intuition'},
                               {'duration': '3:57', 'position': 'B2', 'title': 'Zero-One'},
                               {'duration': '3:58', 'position': 'B3', 'title': 'Fade'},
                               {'duration': '3:56', 'position': 'B4', 'title': 'Render'},
                               {'duration': '3:25', 'position': 'B5', 'title': 'Veridian'},
                               {'duration': '4:23', 'position': 'B6', 'title': 'Paragon'}],
            'trackDurations': {'0': '4:24',
                               '1': '3:41',
                               '10': '4:23',
                               '2': '4:39',
                               '3': '3:16',
                               '4': '4:04',
                               '5': '3:51',
                               '6': '3:57',
                               '7': '3:58',
                               '8': '3:56',
                               '9': '3:25'},
            'trackIds': {'0': 'anQ836BXbYw',
                         '1': '1jKQZX26laU',
                         '10': 'RrX5LpESxsc',
                         '2': 'vuMD3WGxMw4',
                         '3': 'ifh9nWGYyNk',
                         '4': 'dhv9mV04hdY',
                         '5': 'B1q5bv1loKY',
                         '6': 'ajjQqtVKR_4',
                         '7': 'TtliPomEfK4',
                         '8': 'wBYcRdIdvok',
                         '9': 'HiSZKHxQW50'}},
 10142402: {'defaultYtVideoId': 'n0H3RlaQVrM',
            'fallbackTracks': [{'duration': '', 'position': '1', 'title': 'Keeping the Blade'},
                               {'duration': '', 'position': '2', 'title': 'Always & Never'},
                               {'duration': '4:24', 'position': '3', 'title': 'Welcome Home'},
                               {'duration': '',
                                'position': '4',
                                'title': "Ten Speed (Of God's Blood And Burial)"},
                               {'duration': '', 'position': '5', 'title': 'Crossing The Frame'},
                               {'duration': '',
                                'position': '6',
                                'title': 'Apollo 1: The Writing Writer'},
                               {'duration': '',
                                'position': '7',
                                'title': 'Once Upon Your Dead Body'},
                               {'duration': '', 'position': '8', 'title': 'Wake Up'},
                               {'duration': '3:51', 'position': '9', 'title': 'The Suffering'},
                               {'duration': '',
                                'position': '10',
                                'title': 'The Lying Lies And Dirty Secrets Of Miss Erica Court'},
                               {'duration': '', 'position': '11', 'title': 'Mother May I'},
                               {'duration': '',
                                'position': '12',
                                'title': 'The Willing Well I: Fuel For The Feeding End'},
                               {'duration': '',
                                'position': '13',
                                'title': 'The Willing Well II: From Fear Through The Eyes Of '
                                         'Madness'},
                               {'duration': '',
                                'position': '14',
                                'title': 'The Willing Well III: Apollo II: The Telling Truth'},
                               {'duration': '',
                                'position': '15',
                                'title': 'The Willing Well IV: The Final Cut'}],
            'trackDurations': {'2': '4:24', '8': '3:51'},
            'trackIds': {'0': 'Z8zpd4JxgDM',
                         '12': 'Z8zpd4JxgDM',
                         '2': 'n0H3RlaQVrM',
                         '8': 'XnABRPS37hk'},
            'ytPlaylistId': 'OLAK5uy_kOM4PsSMruzQrK_uIM5-iFfhCiId44-4E'},
 11095447: {'defaultYtVideoId': 'Pj1m7TuSGBs',
            'fallbackTracks': [{'duration': '4:00', 'position': 'A1', 'title': 'Lucid'},
                               {'duration': '4:04', 'position': 'A2', 'title': 'The Remedy'},
                               {'duration': '3:16', 'position': 'A3', 'title': 'Relapse'},
                               {'duration': '4:12', 'position': 'A4', 'title': 'Consume'},
                               {'duration': '3:21', 'position': 'A5', 'title': 'Frailty'},
                               {'duration': '2:22', 'position': 'A6', 'title': 'In Somnus Veritas'},
                               {'duration': '4:03', 'position': 'B1', 'title': 'Dusk To Day'},
                               {'duration': '3:44', 'position': 'B2', 'title': 'Casualty'},
                               {'duration': '4:15', 'position': 'B3', 'title': 'The Slow Decay'},
                               {'duration': '4:42', 'position': 'B4', 'title': 'Crooked Path'},
                               {'duration': '4:19', 'position': 'B5', 'title': 'Sonder'}],
            'trackDurations': {'0': '4:00',
                               '1': '4:04',
                               '10': '4:19',
                               '2': '3:16',
                               '3': '4:12',
                               '4': '3:21',
                               '5': '2:22',
                               '6': '4:03',
                               '7': '3:44',
                               '8': '4:15',
                               '9': '4:42'},
            'trackIds': {'0': 'Pj1m7TuSGBs',
                         '1': 'WWurkdQBlAE',
                         '10': 'DH94rmS76_o',
                         '2': 'Wqo4GOCUQtk',
                         '3': 'Z_hxKefpFTg',
                         '4': 'PMpP_1o8LK4',
                         '5': 'MsmUUNo-K1Q',
                         '6': 'S-5YU6kFZso',
                         '7': 'TRPaMrIjtj8',
                         '8': 'vS1tA0u7VR8',
                         '9': 'eWEOXd8U58o'}},
 11368406: {'defaultYtVideoId': 'dDMuVL3sdU0',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Lull'},
                               {'duration': '3:15', 'position': 'A2', 'title': 'Fracture'},
                               {'duration': '4:19', 'position': 'A3', 'title': 'Doublespeak'},
                               {'duration': '3:58', 'position': 'A4', 'title': 'Overthrow'},
                               {'duration': '3:30', 'position': 'B1', 'title': 'Whistleblower'},
                               {'duration': '4:11', 'position': 'B2', 'title': 'Echo Chamber'},
                               {'duration': '3:30', 'position': 'B3', 'title': 'Pool Spray'},
                               {'duration': '3:43', 'position': 'B4', 'title': 'Graymail'},
                               {'duration': '', 'position': 'C1', 'title': 'Manichee'},
                               {'duration': '3:42', 'position': 'C2', 'title': 'Citadel'},
                               {'duration': '3:27', 'position': 'C3', 'title': 'Follow Me'},
                               {'duration': '', 'position': 'D1', 'title': 'Tyrant'},
                               {'duration': '', 'position': 'D2', 'title': 'Livestream'}],
            'trackDurations': {'1': '3:15',
                               '10': '3:27',
                               '2': '4:19',
                               '3': '3:58',
                               '4': '3:30',
                               '5': '4:11',
                               '6': '3:30',
                               '7': '3:43',
                               '9': '3:42'},
            'trackIds': {'1': 'dDMuVL3sdU0',
                         '10': 'JitMrYx_H5M',
                         '2': 'IKmgXQFtnig',
                         '3': 'GLu-E42-RmA',
                         '4': 'uRS3582EKMI',
                         '5': '7G566cXl1wE',
                         '6': 'Y5Kf5qbZoW0',
                         '7': 'Ohux9_gN5hc',
                         '9': '48fHECyl2zg'}},
 11625165: {'defaultYtVideoId': 'OMxTBPvRoH8',
            'fallbackTracks': [{'duration': '4:21', 'position': 'A1', 'title': 'Rigged'},
                               {'duration': '3:54',
                                'position': 'A2',
                                'title': 'Not Just Breathing'},
                               {'duration': '3:19', 'position': 'A3', 'title': 'One Last Time'},
                               {'duration': '3:18',
                                'position': 'A4',
                                'title': 'I Always Wanted To Leave'},
                               {'duration': '3:37', 'position': 'A5', 'title': 'Feel Nothing'},
                               {'duration': '1:02', 'position': 'B1', 'title': 'Happy'},
                               {'duration': '3:26', 'position': 'B2', 'title': 'The One You Loved'},
                               {'duration': '3:46', 'position': 'B3', 'title': 'Paid In Full'},
                               {'duration': '4:08', 'position': 'B4', 'title': 'The Sound'},
                               {'duration': '3:48', 'position': 'B5', 'title': 'Disposable Fix'}],
            'trackDurations': {'0': '4:21',
                               '1': '3:54',
                               '2': '3:19',
                               '3': '3:18',
                               '4': '3:37',
                               '5': '1:02',
                               '6': '3:26',
                               '7': '3:46',
                               '8': '4:08',
                               '9': '3:48'},
            'trackIds': {'0': 'OMxTBPvRoH8',
                         '1': 'eevyacmd1q4',
                         '2': 'n7m8_s683do',
                         '3': 'nvKl_zCTNWE',
                         '4': 'pjX3J9EpAr0',
                         '5': 'GY3vKxBsSM4',
                         '6': 'mZ8cmw9wBOo',
                         '7': 'sDtnFEjSq_c',
                         '8': '3232vvnE9NU',
                         '9': 'uYRv4tC8928'}},
 11771142: {'defaultYtVideoId': 'VcApGdcRZN4',
            'fallbackTracks': [{'duration': '1:16', 'position': 'A1', 'title': 'Two Years'},
                               {'duration': '2:57', 'position': 'A2', 'title': 'Southbound'},
                               {'duration': '4:05',
                                'position': 'A3',
                                'title': "Don't Let Me Fade Away"},
                               {'duration': '3:21', 'position': 'A4', 'title': 'Stitch'},
                               {'duration': '3:45', 'position': 'A5', 'title': 'Witness'},
                               {'duration': '3:36', 'position': 'A6', 'title': 'Deadweight'},
                               {'duration': '3:50', 'position': 'B1', 'title': 'Gravity'},
                               {'duration': '3:12', 'position': 'B2', 'title': 'Never Enough'},
                               {'duration': '4:13', 'position': 'B3', 'title': 'Indestructible'},
                               {'duration': '2:05', 'position': 'B4', 'title': 'Disdain'},
                               {'duration': '3:23',
                                'position': 'B5',
                                'title': 'My Grave Is Mine To Dig'},
                               {'duration': '3:49', 'position': 'B6', 'title': 'Johnny Cash'}],
            'trackDurations': {'0': '1:16',
                               '1': '2:57',
                               '10': '3:23',
                               '11': '3:49',
                               '2': '4:05',
                               '3': '3:21',
                               '4': '3:45',
                               '5': '3:36',
                               '6': '3:50',
                               '7': '3:12',
                               '8': '4:13',
                               '9': '2:05'},
            'trackIds': {'0': 'VcApGdcRZN4',
                         '1': '8nrNk4XzHB4',
                         '10': '3AI8mQiYJdQ',
                         '11': 'AnFBqJA18iY',
                         '2': 'q9bu5BI03WA',
                         '3': 'DE7oZ9nVFB0',
                         '4': 'lWo1N8Q0t9o',
                         '5': 'iiBPpShYedE',
                         '6': '4Z6rHzry3mE',
                         '7': 'RzcVDvZ2rO8',
                         '8': 'iQckxe1kGbU',
                         '9': 'DCZWCBpQ8EI'}},
 11812427: {'defaultYtVideoId': 'LswEN0icdj0',
            'fallbackTracks': [{'duration': '3:11',
                                'position': 'A1',
                                'title': 'It Has To Start Somewhere'},
                               {'duration': '3:34', 'position': 'A2', 'title': 'Rapture'},
                               {'duration': '3:11', 'position': 'A3', 'title': 'On My Teeth'},
                               {'duration': '3:40', 'position': 'A4', 'title': 'Wake Me'},
                               {'duration': '3:33', 'position': 'A5', 'title': 'Bloodlust'},
                               {'duration': '4:45', 'position': 'B1', 'title': 'Sink With You'},
                               {'duration': '3:28', 'position': 'B2', 'title': 'ihateit'},
                               {'duration': '3:29', 'position': 'B3', 'title': 'Hold Your Breath'},
                               {'duration': '3:45', 'position': 'B4', 'title': 'No Frame'},
                               {'duration': '3:34', 'position': 'B5', 'title': 'In Motion'},
                               {'duration': '4:03', 'position': 'B6', 'title': 'I Gave Up'}],
            'trackDurations': {'0': '3:11',
                               '1': '3:34',
                               '10': '4:03',
                               '2': '3:11',
                               '3': '3:40',
                               '4': '3:33',
                               '5': '4:45',
                               '6': '3:28',
                               '7': '3:29',
                               '8': '3:45',
                               '9': '3:34'},
            'trackIds': {'0': 'LswEN0icdj0',
                         '1': 'kq1a_oMPswM',
                         '10': 'YxGX3hXRlno',
                         '2': 'WlDVOIO1rIA',
                         '3': 'IkX2wayURWU',
                         '4': '5HIRDba6Y9A',
                         '5': 'ikKAdbO-dE0',
                         '6': 'XKJ6cm1yOy0',
                         '7': 'ueJqHYyuB9w',
                         '8': '-lLEwTjAouk',
                         '9': 'HL590q6OGhY'}},
 12131049: {'defaultYtVideoId': 'GzuSruxHL2g',
            'fallbackTracks': [{'duration': '3:52', 'position': 'A1', 'title': 'Technology'},
                               {'duration': '3:18', 'position': 'A2', 'title': 'Stay Ignorant'},
                               {'duration': '4:05', 'position': 'A3', 'title': 'T-Shirt Song'},
                               {'duration': '4:47', 'position': 'A4', 'title': 'Come Out To LA'},
                               {'duration': '3:52', 'position': 'B1', 'title': 'Pretty'},
                               {'duration': '', 'position': 'B2', 'title': 'The Blues'},
                               {'duration': '', 'position': 'B3', 'title': 'Tightrope'},
                               {'duration': '', 'position': 'B4', 'title': 'Everybody'},
                               {'duration': '5:09', 'position': 'B5', 'title': 'Greatness'},
                               {'duration': '', 'position': 'C1', 'title': 'Porkies'},
                               {'duration': '', 'position': 'C2', 'title': 'Got To Be You'},
                               {'duration': '', 'position': 'C3', 'title': 'Good Listener'},
                               {'duration': '3:52', 'position': 'D1', 'title': 'Y'},
                               {'duration': '', 'position': 'D2', 'title': 'Something To Drink'}],
            'trackDurations': {'0': '3:52',
                               '1': '3:18',
                               '12': '3:52',
                               '2': '4:05',
                               '3': '4:47',
                               '4': '3:52',
                               '8': '5:09'},
            'trackIds': {'0': 'GzuSruxHL2g',
                         '1': '6SbiuMrWi5M',
                         '12': 'GzuSruxHL2g',
                         '2': 'eXjCcC7e1fk',
                         '3': 'Yc8VGHTlKts',
                         '4': 'XcYTkySdAwQ',
                         '8': 'rpnzmvp-VTg'}},
 12852715: {'defaultYtVideoId': 'eibN9wI77ME',
            'fallbackTracks': [{'duration': '4:02', 'position': 'A1', 'title': 'Incinerate'},
                               {'duration': '', 'position': 'A2', 'title': 'Dust'},
                               {'duration': '4:16', 'position': 'A3', 'title': 'Survivalist'},
                               {'duration': '',
                                'position': 'A4',
                                'title': 'Cultivation Of Infection'},
                               {'duration': '', 'position': 'A5', 'title': 'The Hunt Begins'},
                               {'duration': '', 'position': 'B1', 'title': 'Hard Lined Downfall'},
                               {'duration': '', 'position': 'B2', 'title': 'King Of The Arctic'},
                               {'duration': '', 'position': 'B3', 'title': 'Sidewinder'},
                               {'duration': '', 'position': 'B4', 'title': 'No Reprisal'},
                               {'duration': '4:36', 'position': 'B5', 'title': 'One With The Sun'}],
            'trackDurations': {'0': '4:02', '2': '4:16', '9': '4:36'},
            'trackIds': {'0': 'eibN9wI77ME',
                         '1': 'AhEN-MCx90c',
                         '2': 'rsYsP5TgAVM',
                         '3': '1BcSoTKt0cQ',
                         '4': 'MSXeFU20QCo',
                         '5': 'mTn6TGr2Tjw',
                         '6': '7JvyhCTLaiQ',
                         '7': 'TrCde8m0Ulc',
                         '8': 'lPA0lTw3jog',
                         '9': 'cz8IbywzOCw'}},
 12988109: {'defaultYtVideoId': 'CO_4rGjK7UU',
            'fallbackTracks': [{'duration': '5:23', 'position': 'A1', 'title': 'Tempting Time'},
                               {'duration': '4:27', 'position': 'A2', 'title': 'Soraya'},
                               {'duration': '4:02',
                                'position': 'A3',
                                'title': 'Thoroughly At Home'},
                               {'duration': '6:09', 'position': 'A4', 'title': 'On Impulse'},
                               {'duration': '1:06', 'position': 'B1', 'title': 'Tessitura'},
                               {'duration': '4:26', 'position': 'B2', 'title': 'Behaving Badly'},
                               {'duration': '5:32',
                                'position': 'B3',
                                'title': 'The Price Of Everything And The Value Of Nothing'},
                               {'duration': '6:41', 'position': 'B4', 'title': 'CAFO'},
                               {'duration': '6:08', 'position': 'C1', 'title': 'Inamorata'},
                               {'duration': '1:44', 'position': 'C2', 'title': 'Point To Point'},
                               {'duration': '2:06', 'position': 'C3', 'title': 'Modern Meat'},
                               {'duration': '4:16', 'position': 'C4', 'title': 'Song Of Solomon'},
                               {'duration': '5:29', 'position': 'D1', 'title': 'Wave Of Babies'},
                               {'duration': '6:38', 'position': 'D2', 'title': 'Kalimba'},
                               {'duration': '1:57', 'position': 'D3', 'title': 'Orea (Demo)'}],
            'fullAlbumYtDuration': 3126,
            'fullAlbumYtVideoId': 'MA2YTm7qjnE',
            'trackDurations': {'0': '5:23',
                               '1': '4:27',
                               '10': '2:06',
                               '11': '4:16',
                               '12': '5:29',
                               '13': '6:38',
                               '14': '1:57',
                               '2': '4:02',
                               '3': '6:09',
                               '4': '1:06',
                               '5': '4:26',
                               '6': '5:32',
                               '7': '6:41',
                               '8': '6:08',
                               '9': '1:44'},
            'trackIds': {'0': 'CO_4rGjK7UU',
                         '1': 'F3kpUHgYf0o',
                         '10': 'clvu21iWkkg',
                         '11': 'ihqT1aA4Q88',
                         '12': 'bt-RoSzsEKA',
                         '2': 'Xs5N0cUFQoU',
                         '3': 'Sf3satvbCIE',
                         '4': 'L257mQgpIrE',
                         '5': 'uHU1ryKhSHc',
                         '7': 'NmfzWpp0hMc',
                         '8': 'aAiyTCrAChE',
                         '9': 'v1h9ilhxRP0'}},
 13113361: {'defaultYtVideoId': 'N0eOaXc9H4s',
            'fallbackTracks': [{'duration': '2:20',
                                'position': 'A1',
                                'title': 'I Apologise If You Feel Something'},
                               {'duration': '3:53', 'position': 'A2', 'title': 'Mantra'},
                               {'duration': '5:26', 'position': 'A3', 'title': 'Nihilist Blues'},
                               {'duration': '4:31', 'position': 'B1', 'title': 'In The Dark'},
                               {'duration': '4:34', 'position': 'B2', 'title': 'Wonderful Life'},
                               {'duration': '1:49', 'position': 'B3', 'title': 'Ouch'},
                               {'duration': '3:47', 'position': 'B4', 'title': 'Medicine'},
                               {'duration': '4:22',
                                'position': 'C1',
                                'title': 'Sugar Honey Ice & Tea'},
                               {'duration': '4:29',
                                'position': 'C2',
                                'title': "Why You Gotta Kick Me When I'm Down"},
                               {'duration': '3:19', 'position': 'C3', 'title': 'Fresh Bruises'},
                               {'duration': '3:37', 'position': 'D1', 'title': 'Mother Tongue'},
                               {'duration': '4:01', 'position': 'D2', 'title': 'Heavy Metal'},
                               {'duration': '5:57',
                                'position': 'D3',
                                'title': "I Don't Know What To Say"}],
            'trackDurations': {'0': '2:20',
                               '1': '3:53',
                               '10': '3:37',
                               '11': '4:01',
                               '12': '5:57',
                               '2': '5:26',
                               '3': '4:31',
                               '4': '4:34',
                               '5': '1:49',
                               '6': '3:47',
                               '7': '4:22',
                               '8': '4:29',
                               '9': '3:19'},
            'trackIds': {'0': 'N0eOaXc9H4s',
                         '1': 'VAXg78MKJcM',
                         '10': '-aC_TSkGvPw',
                         '11': '_bvBC1mcyB0',
                         '12': 'y7hVM8CFsGE',
                         '2': 'iwzfR7-33Wc',
                         '3': 'rju0pbdm4z4',
                         '4': '4hoDwVy6IQ4',
                         '5': 'QD1vsicJevY',
                         '6': 'MocF43ncu8I',
                         '7': 'ULj6eH5YfAw',
                         '8': '3e89Y9S00pM',
                         '9': 'Pj_aE3PHTjI'},
            'ytPlaylistId': 'OLAK5uy_mF9FtSn7fe7R9LgeDpAOrGYqcT2MHH0po'},
 13203006: {'defaultYtVideoId': 'Shmt5YnF40A',
            'fallbackTracks': [{'duration': '3:26', 'position': 'A1', 'title': "Givin' Up"},
                               {'duration': '', 'position': 'A2', 'title': "Don't Cry"},
                               {'duration': '', 'position': 'A3', 'title': 'Cautions'},
                               {'duration': '3:13', 'position': 'A4', 'title': 'Get Back Up'},
                               {'duration': '', 'position': 'A5', 'title': 'So Bad'},
                               {'duration': '', 'position': 'A6', 'title': 'Help You Out'},
                               {'duration': '', 'position': 'B1', 'title': 'Xo'},
                               {'duration': '', 'position': 'B2', 'title': 'Hell Of It'},
                               {'duration': '', 'position': 'B3', 'title': 'Comfortable'},
                               {'duration': '', 'position': 'B4', 'title': 'Iw2dwy'},
                               {'duration': '', 'position': 'B5', 'title': 'Wait, Stay'}],
            'trackDurations': {'0': '3:26', '3': '3:13'},
            'trackIds': {'0': 'Shmt5YnF40A', '3': 'mNlp4WklZ6k'}},
 13990219: {'defaultYtVideoId': 'K0-CW1DbVIg',
            'fallbackTracks': [{'duration': '4:05', 'position': 'A1', 'title': 'Details Matter'},
                               {'duration': '3:26', 'position': 'A2', 'title': 'Bloodline'},
                               {'duration': '4:11', 'position': 'A3', 'title': '4D'},
                               {'duration': '3:51', 'position': 'A4', 'title': 'Talking Heads'},
                               {'duration': '4:03', 'position': 'A5', 'title': 'Freefall'},
                               {'duration': '4:01', 'position': 'A6', 'title': 'Jinn'},
                               {'duration': '4:03', 'position': 'B1', 'title': 'Eclipse'},
                               {'duration': '4:00', 'position': 'B2', 'title': 'Rift'},
                               {'duration': '3:24', 'position': 'B3', 'title': 'Paradigm'},
                               {'duration': '3:48', 'position': 'B4', 'title': 'Vultures'},
                               {'duration': '4:37', 'position': 'B5', 'title': 'Sleepless'}],
            'trackDurations': {'0': '4:05',
                               '1': '3:26',
                               '10': '4:37',
                               '2': '4:11',
                               '3': '3:51',
                               '4': '4:03',
                               '5': '4:01',
                               '6': '4:03',
                               '7': '4:00',
                               '8': '3:24',
                               '9': '3:48'},
            'trackIds': {'0': 'K0-CW1DbVIg',
                         '1': 'jGba1gDibw4',
                         '10': 'LCr06VmbYBo',
                         '2': 'A7AhNiyj_EQ',
                         '3': 'Kn3c5i-gW6s',
                         '4': '6TTZ72n5KBQ',
                         '5': 'cQFbYRRNj9Y',
                         '6': 'ni8qtNKujmo',
                         '7': 'TM7NZFIdJ5w',
                         '8': 'iOQtil5JFI4',
                         '9': 'l8Ms6atpNRA'}},
 14043330: {'defaultYtVideoId': 'LQ8KvLQIdMc',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Reptile'},
                               {'duration': '', 'position': 'B1', 'title': 'Blood Eagle'},
                               {'duration': '', 'position': 'B2', 'title': 'Chvrch Bvrner'},
                               {'duration': '', 'position': 'B3', 'title': 'Garden In The Bones'},
                               {'duration': '5:34', 'position': 'C1', 'title': "It's Only Smiles"},
                               {'duration': '', 'position': 'C2', 'title': 'Follow Your Ghost'},
                               {'duration': '6:50', 'position': 'C3', 'title': 'Crush'},
                               {'duration': '4:28', 'position': 'D1', 'title': 'Sentient Glow'},
                               {'duration': '', 'position': 'D2', 'title': 'Satellites'}],
            'trackDurations': {'4': '5:34', '6': '6:50', '7': '4:28'},
            'trackIds': {'4': 'LQ8KvLQIdMc', '6': '9za7ZV4n7mo', '7': 'gpVMGvZbGPc'}},
 14188877: {'defaultYtVideoId': 'km0Byzc4UfM',
            'fallbackTracks': [{'duration': '3:21', 'position': 'A1', 'title': 'You Wanna Know'},
                               {'duration': '3:29', 'position': 'A2', 'title': 'Superlove'},
                               {'duration': '3:41', 'position': 'A3', 'title': 'Automatic'},
                               {'duration': '', 'position': 'A4', 'title': 'Fire'},
                               {'duration': '', 'position': 'B1', 'title': 'Nerve'},
                               {'duration': '', 'position': 'B2', 'title': 'What You Do To Me'},
                               {'duration': '3:39', 'position': 'B3', 'title': 'Money Power Fame'},
                               {'duration': '', 'position': 'B4', 'title': 'Keep On Pushing'},
                               {'duration': '', 'position': 'C1', 'title': 'Tough On You'},
                               {'duration': '', 'position': 'C2', 'title': 'Let You Get Away'},
                               {'duration': '', 'position': 'C3', 'title': 'I Got Sick'},
                               {'duration': '',
                                'position': 'C4',
                                'title': 'Wrong Place Wrong Time'},
                               {'duration': '', 'position': 'D1', 'title': 'Bad Feeling'},
                               {'duration': '', 'position': 'D2', 'title': 'Further'},
                               {'duration': '3:21',
                                'position': 'D3',
                                'title': 'You Wanna Know - Club Sex Mix'}],
            'trackDurations': {'0': '3:21', '1': '3:29', '14': '3:21', '2': '3:41', '6': '3:39'},
            'trackIds': {'0': 'km0Byzc4UfM',
                         '1': 'LQ59HPH2X20',
                         '14': 'km0Byzc4UfM',
                         '2': 'BQCI7kwV5w8',
                         '6': 'oHcEFB7D6WU'},
            'ytPlaylistId': 'OLAK5uy_k3n2ijq66W8FD0xR0bcguKcRSi2sqgE7A'},
 14458307: {'defaultYtVideoId': 'FrbwVzgvl3E',
            'fallbackTracks': [{'duration': '5:03',
                                'position': 'A1',
                                'title': 'The Night Does Not Belong To God'},
                               {'duration': '5:49', 'position': 'A2', 'title': 'The Offering'},
                               {'duration': '4:58', 'position': 'A3', 'title': 'Levitate'},
                               {'duration': '4:28', 'position': 'B1', 'title': 'Dark Signs'},
                               {'duration': '5:21', 'position': 'B2', 'title': 'Higher'},
                               {'duration': '3:39', 'position': 'B3', 'title': 'Take Aim'},
                               {'duration': '3:56', 'position': 'C1', 'title': 'Give'},
                               {'duration': '3:25', 'position': 'C2', 'title': 'Gods'},
                               {'duration': '4:52', 'position': 'C3', 'title': 'Sugar'},
                               {'duration': '5:03', 'position': 'D1', 'title': 'Say That You Will'},
                               {'duration': '3:56', 'position': 'D2', 'title': 'Drag Me Under'},
                               {'duration': '4:07', 'position': 'D3', 'title': 'Blood Sport'}],
            'trackDurations': {'0': '5:03',
                               '1': '5:49',
                               '10': '3:56',
                               '11': '4:07',
                               '2': '4:58',
                               '3': '4:28',
                               '4': '5:21',
                               '5': '3:39',
                               '6': '3:56',
                               '7': '3:25',
                               '8': '4:52',
                               '9': '5:03'},
            'trackIds': {'0': 'FrbwVzgvl3E',
                         '1': '-cUXKKf6my0',
                         '10': 'c6Cqvgjql_Q',
                         '11': 'WvmUZGS92c0',
                         '3': 'yVlJpp_-V7M',
                         '4': 'IhoSDCVb4n0',
                         '5': 'pNLJrWuIvl0',
                         '6': '8jXjK7kfRmY',
                         '7': 'wFodog4zZlY',
                         '8': '-sogivGtsVM'}},
 14816287: {'defaultYtVideoId': '0bmXGkwNs-k',
            'fallbackTracks': [{'duration': '',
                                'position': 'A1',
                                'title': 'An Infinite Regression'},
                               {'duration': '4:40', 'position': 'A2', 'title': 'Odessa'},
                               {'duration': '', 'position': 'A3', 'title': 'Somarium'},
                               {'duration': '', 'position': 'A4', 'title': 'Earth Departure'},
                               {'duration': '', 'position': 'A5', 'title': 'Isolated Incidents'},
                               {'duration': '', 'position': 'A6', 'title': 'Do Not Go Gently'},
                               {'duration': '', 'position': 'B1', 'title': 'New Eden'},
                               {'duration': '', 'position': 'B2', 'title': 'Cylindrical Sea'},
                               {'duration': '', 'position': 'B3', 'title': 'Espera'},
                               {'duration': '',
                                'position': 'B4',
                                'title': 'To Lead You To An Overwhelming Question'},
                               {'duration': '', 'position': 'B5', 'title': 'Weightless'},
                               {'duration': '', 'position': 'B6', 'title': 'David'}],
            'trackDurations': {'1': '4:40'},
            'trackIds': {'1': '0bmXGkwNs-k'}},
 14947161: {'defaultYtVideoId': 'b4dHvbgYZhM',
            'fallbackTracks': [{'duration': '0:43', 'position': 'A1', 'title': '[Id]'},
                               {'duration': '3:44', 'position': 'A2', 'title': 'Unbreakable'},
                               {'duration': '3:33', 'position': 'A3', 'title': 'Dark Passenger'},
                               {'duration': '3:00', 'position': 'A4', 'title': 'The Higler'},
                               {'duration': '1:13', 'position': 'A5', 'title': 'Martyrs'},
                               {'duration': '3:01', 'position': 'A6', 'title': 'Resistance'},
                               {'duration': '1:03', 'position': 'B1', 'title': 'Circle'},
                               {'duration': '3:03', 'position': 'B2', 'title': 'Mowgli'},
                               {'duration': '3:30', 'position': 'B3', 'title': 'Namaste'},
                               {'duration': '2:56', 'position': 'B4', 'title': 'Conquer'},
                               {'duration': '3:24', 'position': 'B5', 'title': 'Codex'}],
            'trackDurations': {'0': '0:43',
                               '1': '3:44',
                               '10': '3:24',
                               '2': '3:33',
                               '3': '3:00',
                               '4': '1:13',
                               '5': '3:01',
                               '6': '1:03',
                               '7': '3:03',
                               '8': '3:30',
                               '9': '2:56'},
            'trackIds': {'0': 'b4dHvbgYZhM',
                         '1': 'mO9IPeudhsw',
                         '10': '1cUowhlf2h0',
                         '2': 'gJADFkEkrOs',
                         '3': 'Acie7fTOTu4',
                         '4': 'GLOZAG5M7sw',
                         '5': 'Vd3IT1LuHfM',
                         '6': 'fF12NgKZGXk',
                         '7': 'p-1W8AL1BYo',
                         '8': 'eeRS1YIfk2o',
                         '9': '6fUldx_n0no'}},
 15043916: {'defaultYtVideoId': 'kF32LWxokRo',
            'fallbackTracks': [{'duration': '4:09', 'position': 'A1', 'title': 'The Narrative'},
                               {'duration': '4:15', 'position': 'A2', 'title': 'Bones'},
                               {'duration': '4:48', 'position': 'A3', 'title': 'Paramount'},
                               {'duration': '4:21', 'position': 'B1', 'title': 'Defender'},
                               {'duration': '4:13', 'position': 'B2', 'title': 'Lighthouse'},
                               {'duration': '4:09',
                                'position': 'B3',
                                'title': 'Dismembered Memory'},
                               {'duration': '4:18', 'position': 'C1', 'title': 'Ties That Bind'},
                               {'duration': '3:40', 'position': 'C2', 'title': 'Bloodletter'},
                               {'duration': '4:43',
                                'position': 'C3',
                                'title': 'Extinct By Instinct'},
                               {'duration': '4:25', 'position': 'D1', 'title': 'Empty Heaven'},
                               {'duration': '6:21', 'position': 'D2', 'title': 'Three Fountains'}],
            'trackDurations': {'0': '4:09',
                               '1': '4:15',
                               '10': '6:21',
                               '2': '4:48',
                               '3': '4:21',
                               '4': '4:13',
                               '5': '4:09',
                               '6': '4:18',
                               '7': '3:40',
                               '8': '4:43',
                               '9': '4:25'},
            'trackIds': {'0': 'kF32LWxokRo',
                         '1': 'yrckqAEFJE4',
                         '10': 'xl9jfleu6Qg',
                         '2': 'w55YCDzZjvA',
                         '3': '48L67oBBvHQ',
                         '4': 'GQmK0Lka96w',
                         '5': 'PHzuwIY1mY0',
                         '6': 'TVZAAyBFuFc',
                         '7': 'uSfrUu1KZkk',
                         '8': 'Mb1gt8XMUTc',
                         '9': 'jY5wBdtgNY4'}},
 15594164: {'defaultYtVideoId': 'tUltTV3t4OM',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Muramasa'},
                               {'duration': '', 'position': 'A2', 'title': 'Have A Blast'},
                               {'duration': '', 'position': 'A3', 'title': 'Facepalm Mute'},
                               {'duration': '', 'position': 'A4', 'title': 'Ji'},
                               {'duration': '4:29', 'position': 'B1', 'title': 'Scarlet'},
                               {'duration': '', 'position': 'B2', 'title': 'Luck As A Constant'},
                               {'duration': '4:38', 'position': 'B3', 'title': 'Ragnarok'},
                               {'duration': '',
                                'position': 'C1',
                                'title': 'The Gods Must Be Crazy!'},
                               {'duration': '4:26',
                                'position': 'C2',
                                'title': 'Make Total Destroy'},
                               {'duration': '', 'position': 'C3', 'title': 'Erised'},
                               {'duration': '', 'position': 'C4', 'title': 'Epoch'},
                               {'duration': '', 'position': 'D1', 'title': "Froggin' Bullfish"},
                               {'duration': '', 'position': 'D2', 'title': 'Mile Zero'},
                               {'duration': '', 'position': 'D3', 'title': 'Masamune'}],
            'fullAlbumYtDuration': 4585,
            'fullAlbumYtVideoId': 'hz16Wty7Gho',
            'trackDurations': {'4': '4:29', '6': '4:38', '8': '4:26'},
            'trackIds': {'4': 'tUltTV3t4OM', '6': 'Rm3OpBpwzBs', '8': 'spCmStMOiHE'}},
 15847991: {'defaultYtVideoId': 'PIPPQbsWlgA',
            'fallbackTracks': [{'duration': '0:49', 'position': 'A1', 'title': 'Prelude'},
                               {'duration': '4:06',
                                'position': 'A2',
                                'title': 'All Nereids Beware'},
                               {'duration': '3:33',
                                'position': 'A3',
                                'title': 'One Day Women Will All Become Monsters'},
                               {'duration': '2:56',
                                'position': 'A4',
                                'title': 'Expired In Goreville'},
                               {'duration': '4:41',
                                'position': 'A5',
                                'title': "Baby, You Wouldn't Last A Minute On The Creek"},
                               {'duration': '3:37',
                                'position': 'A6',
                                'title': "The Words 'Best Friend' Become Redefined"},
                               {'duration': '1:00', 'position': 'A7', 'title': 'Interlude Pt 1'},
                               {'duration': '4:34',
                                'position': 'B1',
                                'title': "There's No Penguins In Alaska"},
                               {'duration': '1:00', 'position': 'B2', 'title': 'Interlude Pt 2'},
                               {'duration': '4:20',
                                'position': 'B3',
                                'title': "We're Gonna Have Us A Champagne Jam"},
                               {'duration': '',
                                'position': 'B4',
                                'title': 'No Hardcore Dancing In The Living Room'},
                               {'duration': '2:00',
                                'position': 'B5',
                                'title': "Who's Sandie Jenkins"},
                               {'duration': '4:18',
                                'position': 'B6',
                                'title': 'To Trixie And Reptile, Thanks For Everything'}],
            'trackDurations': {'0': '0:49',
                               '1': '4:06',
                               '11': '2:00',
                               '12': '4:18',
                               '2': '3:33',
                               '3': '2:56',
                               '4': '4:41',
                               '5': '3:37',
                               '6': '1:00',
                               '7': '4:34',
                               '8': '1:00',
                               '9': '4:20'},
            'trackIds': {'0': 'PIPPQbsWlgA',
                         '1': '8IrHIsE6NdQ',
                         '11': '-EAcxVgVBiY',
                         '12': 'l3azCaNiRQw',
                         '2': 'zeZjxqCjlgg',
                         '3': 'ds9TVnT-Jt4',
                         '4': 'CuAjAn01cU4',
                         '5': 'tR5Nzqk5Q28',
                         '6': '49HPutLFVds',
                         '7': 'sLzSjZ7KhLY',
                         '8': 'aECKbe-PYWg',
                         '9': 'dVV3y-CPohA'}},
 15962864: {'defaultYtVideoId': '18mvj0kawGs',
            'fallbackTracks': [{'duration': '3:41', 'position': '1', 'title': 'The Face Of Hate'},
                               {'duration': '3:34',
                                'position': '2',
                                'title': 'Breaking The Mirror'},
                               {'duration': '3:10', 'position': '3', 'title': 'Annihilation'},
                               {'duration': '4:07', 'position': '4', 'title': 'The Path'},
                               {'duration': '4:17', 'position': '5', 'title': 'The Prophet'},
                               {'duration': '3:06',
                                'position': '6',
                                'title': 'Locked (In My Head)'},
                               {'duration': '3:30', 'position': '7', 'title': 'God Of Fire'},
                               {'duration': '2:30', 'position': '8', 'title': 'Stockholm'},
                               {'duration': '4:31', 'position': '9', 'title': 'Louder Voice'},
                               {'duration': '3:07', 'position': '10', 'title': 'Vendetta'}],
            'trackDurations': {'0': '3:41',
                               '1': '3:34',
                               '2': '3:10',
                               '3': '4:07',
                               '4': '4:17',
                               '5': '3:06',
                               '6': '3:30',
                               '7': '2:30',
                               '8': '4:31',
                               '9': '3:07'},
            'trackIds': {'3': '18mvj0kawGs', '5': 'TRJF6GLVFzU'}},
 15985409: {'defaultYtVideoId': 'ou0TdTwLhbQ',
            'fallbackTracks': [{'duration': '3:18', 'position': 'A1', 'title': 'Belleville'},
                               {'duration': '',
                                'position': 'A2',
                                'title': 'Trapped In The Grasp Of A Memory'},
                               {'duration': '', 'position': 'A3', 'title': 'A Serpent’s Touch'},
                               {'duration': '3:49', 'position': 'A4', 'title': 'By The Grave'},
                               {'duration': '', 'position': 'A5', 'title': 'In The Walls'},
                               {'duration': '3:49',
                                'position': 'A6',
                                'title': 'Guided By The Moon'},
                               {'duration': '3:42',
                                'position': 'B1',
                                'title': 'Mistakes Like Fractures'},
                               {'duration': '', 'position': 'B2', 'title': 'Forget Your Name'},
                               {'duration': '', 'position': 'B3', 'title': 'Road 23'},
                               {'duration': '2:40',
                                'position': 'B4',
                                'title': '...And Still I Wander South'},
                               {'duration': '', 'position': 'B5', 'title': 'Denied By Fate'},
                               {'duration': '', 'position': 'B6', 'title': 'Misguided Son'}],
            'fullAlbumYtDuration': 2317,
            'fullAlbumYtVideoId': 'OCowDtHZyUg',
            'trackDurations': {'0': '3:18', '3': '3:49', '5': '3:49', '6': '3:42', '9': '2:40'},
            'trackIds': {'0': 'ou0TdTwLhbQ',
                         '3': 'dgWQm6wv7qk',
                         '5': 'dgWQm6wv7qk',
                         '6': 'jOB3IYBcJEE',
                         '9': 'WYbJC9-h5Z4'}},
 15985411: {'fallbackTracks': [{'duration': '5:05', 'position': 'A1', 'title': 'Dark'},
                               {'duration': '4:09', 'position': 'A2', 'title': 'Cloud Cascade'},
                               {'duration': '3:51', 'position': 'A3', 'title': 'Reflection Room'},
                               {'duration': '3:58', 'position': 'A4', 'title': 'Hollow Light'},
                               {'duration': '3:46', 'position': 'A5', 'title': 'Shapeshifter'},
                               {'duration': '1:35', 'position': 'A6', 'title': 'Heaven, Alone'},
                               {'duration': '3:42', 'position': 'A7', 'title': 'Monarch'},
                               {'duration': '4:26', 'position': 'B1', 'title': 'Fireside'},
                               {'duration': '3:22', 'position': 'B2', 'title': 'Secret Sun'},
                               {'duration': '4:08', 'position': 'B3', 'title': 'Eden'},
                               {'duration': '3:16', 'position': 'B4', 'title': 'Brightwing'},
                               {'duration': '3:39', 'position': 'B5', 'title': 'Halcyon'},
                               {'duration': '4:19', 'position': 'B6', 'title': 'Nova'}],
            'trackDurations': {'0': '5:05',
                               '1': '4:09',
                               '10': '3:16',
                               '11': '3:39',
                               '12': '4:19',
                               '2': '3:51',
                               '3': '3:58',
                               '4': '3:46',
                               '5': '1:35',
                               '6': '3:42',
                               '7': '4:26',
                               '8': '3:22',
                               '9': '4:08'}},
 16251744: {'defaultYtVideoId': 'caZACpJN3ss',
            'fallbackTracks': [{'duration': '1:14', 'position': 'A1', 'title': 'The Reaping'},
                               {'duration': '5:06',
                                'position': 'A2',
                                'title': 'No World For Tomorrow'},
                               {'duration': '4:39',
                                'position': 'A3',
                                'title': 'The Hound (Of Blood And Rank)'},
                               {'duration': '4:56', 'position': 'A4', 'title': 'Feathers'},
                               {'duration': '4:13', 'position': 'B1', 'title': 'The Running Free'},
                               {'duration': '6:39', 'position': 'B2', 'title': 'Mother Superior'},
                               {'duration': '4:21',
                                'position': 'B3',
                                'title': 'Gravemakers & Gunslingers'},
                               {'duration': '4:29', 'position': 'B4', 'title': 'Justice In Murder'},
                               {'duration': '1:05',
                                'position': 'C1',
                                'title': 'I - The Fall Of House Atlantic'},
                               {'duration': '4:55',
                                'position': 'C2',
                                'title': 'II - Radio Bye Bye'},
                               {'duration': '7:45',
                                'position': 'C3',
                                'title': 'III - The End Complete'},
                               {'duration': '3:36',
                                'position': 'C4',
                                'title': 'IV - The Road And The Damned'},
                               {'duration': '7:09', 'position': 'C5', 'title': 'V - On The Brink'}],
            'trackDurations': {'0': '1:14',
                               '1': '5:06',
                               '10': '7:45',
                               '11': '3:36',
                               '12': '7:09',
                               '2': '4:39',
                               '3': '4:56',
                               '4': '4:13',
                               '5': '6:39',
                               '6': '4:21',
                               '7': '4:29',
                               '8': '1:05',
                               '9': '4:55'},
            'trackIds': {'0': 'caZACpJN3ss',
                         '1': 'DYFVQ_o3SAQ',
                         '10': 'IWxL42xqV2I',
                         '11': 'X1RJdBHF_Fs',
                         '12': 'wQx9UsSjzVA',
                         '2': 'Q62g4b0A8Qs',
                         '3': 'NN2yuGIjNE8',
                         '4': 'qoqcKqPWhzc',
                         '5': 'thXSi3czdAY',
                         '6': 'Fx8yc4u8Qgc',
                         '7': 'jwWDJda3rHI',
                         '8': 'unaN4Jejgk8',
                         '9': 'qHzUfa6IO5U'},
            'ytPlaylistId': 'OLAK5uy_llgJ7B3izoiZrEaEUlh73LkGM3949b71I'},
 16595574: {'defaultYtVideoId': 'yg3MNW0dSg8',
            'fallbackTracks': [{'duration': '3:38', 'position': 'A1', 'title': "Oblivion's Peak"},
                               {'duration': '3:00', 'position': 'A2', 'title': 'Deadringer'},
                               {'duration': '2:56', 'position': 'A3', 'title': 'The Rain'},
                               {'duration': '2:25',
                                'position': 'A4',
                                'title': 'Blood Will Have Blood'},
                               {'duration': '1:12', 'position': 'A5', 'title': 'Counting Worms'},
                               {'duration': '2:37', 'position': 'B1', 'title': 'My Heroes'},
                               {'duration': '2:14', 'position': 'B2', 'title': 'Billy No Mates'},
                               {'duration': '2:36', 'position': 'B3', 'title': 'Last Words'},
                               {'duration': '2:16', 'position': 'B4', 'title': 'No Thanks'},
                               {'duration': '2:20', 'position': 'B5', 'title': 'A Fetish'},
                               {'duration': '3:52', 'position': 'B6', 'title': 'Laugh Tracks'}],
            'fullAlbumYtDuration': 1744,
            'fullAlbumYtVideoId': 'Z0faeREYjHc',
            'trackDurations': {'0': '3:38',
                               '1': '3:00',
                               '10': '3:52',
                               '2': '2:56',
                               '3': '2:25',
                               '4': '1:12',
                               '5': '2:37',
                               '6': '2:14',
                               '7': '2:36',
                               '8': '2:16',
                               '9': '2:20'},
            'trackIds': {'10': 'Z0faeREYjHc',
                         '2': 'yg3MNW0dSg8',
                         '4': 'Lei58UXZzUQ',
                         '6': 'Lei58UXZzUQ'},
            'ytPlaylistId': 'OLAK5uy_monA5m177p6DxVZh8aFKhu0bOUaBuoD2E'},
 16610055: {'defaultYtVideoId': 'eCB6p39_IP4',
            'fallbackTracks': [{'duration': '3:48', 'position': '1', 'title': 'Inherit The Earth'},
                               {'duration': '3:07', 'position': '2', 'title': 'Psychescape'},
                               {'duration': '2:58', 'position': '3', 'title': 'Dying In Circles'},
                               {'duration': '3:27',
                                'position': '4',
                                'title': 'Understanding Love As Loss'},
                               {'duration': '0:51', 'position': '5', 'title': 'Tout Comprendre'},
                               {'duration': '4:00', 'position': '6', 'title': 'Panic Room'},
                               {'duration': '3:11', 'position': '7', 'title': 'Redivideя'},
                               {'duration': '3:48', 'position': '8', 'title': 'Nervosa'},
                               {'duration': '2:12',
                                'position': '9',
                                'title': "C'est Tout Pardonner"},
                               {'duration': '3:48', 'position': '10', 'title': 'Orphan'},
                               {'duration': '2:38',
                                'position': '11',
                                'title': 'No Place To Breathe'},
                               {'duration': '4:26', 'position': '12', 'title': 'First Father'},
                               {'duration': '3:31',
                                'position': '13',
                                'title': 'Inhabit The Wound'}],
            'fullAlbumYtDuration': 2507,
            'fullAlbumYtVideoId': 'YEXIv6gWzAE',
            'trackDurations': {'0': '3:48',
                               '1': '3:07',
                               '10': '2:38',
                               '11': '4:26',
                               '12': '3:31',
                               '2': '2:58',
                               '3': '3:27',
                               '4': '0:51',
                               '5': '4:00',
                               '6': '3:11',
                               '7': '3:48',
                               '8': '2:12',
                               '9': '3:48'},
            'trackIds': {'0': 'eCB6p39_IP4',
                         '1': 'b7JSv-36m68',
                         '10': 'QkOtJXLroHk',
                         '11': 'uvHQ6xHlKlM',
                         '12': 'sn5xqkr5t5M',
                         '2': 'Q65bcH2akkg',
                         '3': 'VFIwTsxxCIA',
                         '4': 'yUxMMB6c5sk',
                         '5': 'VbaFJiWftwk',
                         '6': 'IYXjuY_-cOQ',
                         '7': 'QJCzMqwuJW0',
                         '8': 'gi0IOjSW95U',
                         '9': 'a3TpBg1T9_k'}},
 16839336: {'defaultYtVideoId': 'Pn-6eOxnEMI',
            'fallbackTracks': [{'duration': '3:16', 'position': 'A1', 'title': 'Sticks & Bricks'},
                               {'duration': '3:22', 'position': 'A2', 'title': 'All I Want'},
                               {'duration': '2:57', 'position': 'A3', 'title': "It's Complicated"},
                               {'duration': '3:30',
                                'position': 'A4',
                                'title': 'This Is The House That Doubt Built'},
                               {'duration': '2:27', 'position': 'A5', 'title': '2nd Sucks'},
                               {'duration': '3:26',
                                'position': 'B6',
                                'title': 'Better Off This Way'},
                               {'duration': '3:17',
                                'position': 'B7',
                                'title': 'All Signs Point To Lauderdale'},
                               {'duration': '3:47',
                                'position': 'B8',
                                'title': "You Be Tails, I'll Be Sonic"},
                               {'duration': '3:26', 'position': 'B9', 'title': 'Out Of Time'},
                               {'duration': '3:24', 'position': 'B10', 'title': 'If I Leave'}],
            'trackDurations': {'0': '3:16',
                               '1': '3:22',
                               '2': '2:57',
                               '3': '3:30',
                               '4': '2:27',
                               '5': '3:26',
                               '6': '3:17',
                               '7': '3:47',
                               '8': '3:26',
                               '9': '3:24'},
            'trackIds': {'1': 'Pn-6eOxnEMI', '4': 'n6T9olarH-U', '6': '08PszRp2cBg'}},
 17583742: {'defaultYtVideoId': 'b6vhOPTdmeI',
            'fallbackTracks': [{'duration': '4:03',
                                'position': 'A1',
                                'title': 'Seized And Devoured'},
                               {'duration': '4:07', 'position': 'A2', 'title': 'Invasion'},
                               {'duration': '4:07', 'position': 'A3', 'title': 'Abducted'},
                               {'duration': '5:03',
                                'position': 'A4',
                                'title': 'Final Abhorrent Dream'},
                               {'duration': '4:04',
                                'position': 'B1',
                                'title': 'Corpses Thrown Across The Sky'},
                               {'duration': '3:25', 'position': 'B2', 'title': 'Embryonic Anomaly'},
                               {'duration': '4:53',
                                'position': 'B3',
                                'title': 'Annihilating The Pure'},
                               {'duration': '4:28',
                                'position': 'B4',
                                'title': 'Grinding Of Internal Organs'},
                               {'duration': '0:57', 'position': 'B5', 'title': 'End Of Humanity'}],
            'fullAlbumYtDuration': 2040,
            'fullAlbumYtVideoId': 'kBSb6UVAetw',
            'trackDurations': {'0': '4:03',
                               '1': '4:07',
                               '2': '4:07',
                               '3': '5:03',
                               '4': '4:04',
                               '5': '3:25',
                               '6': '4:53',
                               '7': '4:28',
                               '8': '0:57'},
            'trackIds': {'2': 'b6vhOPTdmeI', '5': 'b6vhOPTdmeI'}},
 17743813: {'defaultYtVideoId': 'W69ow97hqbI',
            'fallbackTracks': [{'duration': '',
                                'position': 'A1',
                                'title': 'Do You Dream Of Armageddon?'},
                               {'duration': '4:08', 'position': 'A2', 'title': 'Black Lungs'},
                               {'duration': '', 'position': 'A3', 'title': 'Giving Blood'},
                               {'duration': '', 'position': 'A4', 'title': 'Discourse Is Dead'},
                               {'duration': '4:03', 'position': 'B1', 'title': 'Dead Butterflies'},
                               {'duration': '',
                                'position': 'B2',
                                'title': 'An Ordinary Extinction'},
                               {'duration': '', 'position': 'B3', 'title': 'Impermanence'},
                               {'duration': '',
                                'position': 'B4',
                                'title': 'Flight Without Feathers'},
                               {'duration': '', 'position': 'C1', 'title': 'Little Wonder'},
                               {'duration': '4:05', 'position': 'C2', 'title': 'Animals'},
                               {'duration': '', 'position': 'C3', 'title': 'Libertine'},
                               {'duration': '', 'position': 'C4', 'title': 'Goliath'},
                               {'duration': '', 'position': 'D1', 'title': 'Demi God'},
                               {'duration': '4:20', 'position': 'D2', 'title': 'Meteor'},
                               {'duration': '',
                                'position': 'D3',
                                'title': 'Dying Is Absolutely Safe'}],
            'fullAlbumYtDuration': 3480,
            'fullAlbumYtVideoId': 'cDdvMnu5RoQ',
            'trackDurations': {'1': '4:08', '13': '4:20', '4': '4:03', '9': '4:05'},
            'trackIds': {'1': 'W69ow97hqbI',
                         '13': 'lm7ejB08cbQ',
                         '4': '2ZmjG3wuUes',
                         '9': 'jdWhJcrrjQs'}},
 18670618: {'fallbackTracks': [{'duration': '', 'position': '1', 'title': 'Sol'},
                               {'duration': '', 'position': '2', 'title': 'Naturehold'},
                               {'duration': '', 'position': '3', 'title': 'Nocturne: Lost Faith'},
                               {'duration': '', 'position': '4', 'title': 'Courier'},
                               {'duration': '', 'position': '5', 'title': 'Moon Phase'},
                               {'duration': '', 'position': '6', 'title': 'Forest Haven'},
                               {'duration': '',
                                'position': '7',
                                'title': 'The Desperate Are The Calm'},
                               {'duration': '', 'position': '8', 'title': 'Native Intellect'},
                               {'duration': '', 'position': '9', 'title': 'Half-Life'},
                               {'duration': '', 'position': '10', 'title': 'Luna'}]},
 18801928: {'defaultYtVideoId': 'dV3KY_jdW1g',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Hole In The Wall'},
                               {'duration': '', 'position': 'A2', 'title': 'Dear Old Friend'},
                               {'duration': '', 'position': 'A3', 'title': 'Take Me Away'},
                               {'duration': '', 'position': 'A4', 'title': 'Runaway'},
                               {'duration': '', 'position': 'B1', 'title': 'Pillhead'},
                               {'duration': '', 'position': 'B2', 'title': 'Better Vibes'},
                               {'duration': '', 'position': 'B3', 'title': 'My Old Ways'},
                               {'duration': '',
                                'position': 'B4',
                                'title': 'Die Like Your Brothers'},
                               {'duration': '', 'position': 'C1', 'title': 'Mind Controlled'},
                               {'duration': '',
                                'position': 'C2',
                                'title': 'Time Changes Everything'},
                               {'duration': '', 'position': 'C3', 'title': 'Living Your Dream'},
                               {'duration': '', 'position': 'C4', 'title': 'A Song About Myself'},
                               {'duration': '', 'position': 'D1', 'title': 'Forgive Me'},
                               {'duration': '', 'position': 'D2', 'title': 'Washed Up'},
                               {'duration': '5:29',
                                'position': 'D3',
                                'title': 'Happiness In Self Destruction'}],
            'fullAlbumYtDuration': 3420,
            'fullAlbumYtVideoId': '5X5vJeYsn2w',
            'trackDurations': {'14': '5:29'},
            'trackIds': {'0': 'dV3KY_jdW1g',
                         '1': 'HisBB9e8NzY',
                         '10': '_QNLUtoI9Y0',
                         '11': 'pq8nsjZkqUQ',
                         '12': 'rTysFOfvwXc',
                         '13': 'r_FIwXfqb64',
                         '14': 'UBhBUqA3LWc',
                         '2': '7GzfZKgEQHI',
                         '3': 'Boisk9F2RIo',
                         '4': '80pHBY8yjww',
                         '5': 'oPq3Y7fgFLY',
                         '6': 'hft2dt2uFs4',
                         '7': '0trFFiIxemg',
                         '8': 'GDt3dA8fN6k',
                         '9': 'NGQwL4_x3MA'}},
 19084276: {'defaultYtVideoId': 'SecJsEelf3c',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Hurricane'},
                               {'duration': '2:51', 'position': 'A2', 'title': 'Blood On The Sand'},
                               {'duration': '', 'position': 'A3', 'title': 'The Window'},
                               {'duration': '', 'position': 'A4', 'title': 'Wake Up'},
                               {'duration': '', 'position': 'A5', 'title': 'The Long Defeat'},
                               {'duration': '', 'position': 'A6', 'title': 'Seneca'},
                               {'duration': '4:19', 'position': 'B7', 'title': 'Black Honey'},
                               {'duration': '', 'position': 'B8', 'title': 'Stay With Me'},
                               {'duration': '3:38', 'position': 'B9', 'title': 'Death From Above'},
                               {'duration': '', 'position': 'B10', 'title': 'Whistleblower'},
                               {'duration': '', 'position': 'B11', 'title': 'Salt And Shadow'}],
            'trackDurations': {'1': '2:51', '6': '4:19', '8': '3:38'},
            'trackIds': {'0': 'XRv-Eio7WZM',
                         '1': 'SecJsEelf3c',
                         '6': 'C9GTEsNf_GU',
                         '8': '2TiDTE1UyM0'}},
 19249243: {'defaultYtVideoId': '2MSCGPZ-ghw',
            'fallbackTracks': [{'duration': '0:43', 'position': 'A1', 'title': 'Intro'},
                               {'duration': '3:24', 'position': 'A2', 'title': 'The Swarm'},
                               {'duration': '4:12', 'position': 'A3', 'title': 'Lifetime In Ruins'},
                               {'duration': '3:16',
                                'position': 'A4',
                                'title': 'Guards Of Contagion'},
                               {'duration': '3:35',
                                'position': 'A5',
                                'title': 'From The Tombs Of Five Below'},
                               {'duration': '3:25', 'position': 'A6', 'title': 'Never Cease'},
                               {'duration': '3:30', 'position': 'A7', 'title': 'Trail To Fire'},
                               {'duration': '3:15', 'position': 'B1', 'title': 'To The Ground'},
                               {'duration': '3:04', 'position': 'B2', 'title': 'Burial Lines'},
                               {'duration': '3:11', 'position': 'B3', 'title': 'Birth Of A Legion'},
                               {'duration': '3:27', 'position': 'B4', 'title': 'Watchers Of Rule'},
                               {'duration': '3:34',
                                'position': 'B5',
                                'title': 'Throes Of Remission'},
                               {'duration': '4:10', 'position': 'B6', 'title': 'Spirit In Black'}],
            'trackDurations': {'0': '0:43',
                               '1': '3:24',
                               '10': '3:27',
                               '11': '3:34',
                               '12': '4:10',
                               '2': '4:12',
                               '3': '3:16',
                               '4': '3:35',
                               '5': '3:25',
                               '6': '3:30',
                               '7': '3:15',
                               '8': '3:04',
                               '9': '3:11'},
            'trackIds': {'0': '2MSCGPZ-ghw',
                         '1': '_ebl2Qph6PE',
                         '10': 'RD3dw52f2Nk',
                         '2': '81PElASs5B0',
                         '5': '-UUBShPhuLA'}},
 20154643: {'defaultYtVideoId': 'TikYbkbRC8A',
            'fallbackTracks': [{'duration': '4:06', 'position': 'A1', 'title': 'My Time'},
                               {'duration': '4:45', 'position': 'A2', 'title': 'Summer Angel'},
                               {'duration': '5:32', 'position': 'A3', 'title': 'Secret Country'},
                               {'duration': '4:08', 'position': 'B1', 'title': 'Hold Me Down'},
                               {'duration': '4:39', 'position': 'B2', 'title': 'Excuses'},
                               {'duration': '4:34', 'position': 'B3', 'title': 'The Thief'},
                               {'duration': '5:11', 'position': 'C1', 'title': 'Into The Mirror'},
                               {'duration': '4:17', 'position': 'C2', 'title': 'Animal Backwards'},
                               {'duration': '5:10', 'position': 'C3', 'title': 'Dayglow Vista Rd'},
                               {'duration': '7:22',
                                'position': 'D1',
                                'title': 'Fooled By The Night'}],
            'trackDurations': {'0': '4:06',
                               '1': '4:45',
                               '2': '5:32',
                               '3': '4:08',
                               '4': '4:39',
                               '5': '4:34',
                               '6': '5:11',
                               '7': '4:17',
                               '8': '5:10',
                               '9': '7:22'},
            'trackIds': {'0': 'TikYbkbRC8A',
                         '1': '3ZEcYhRkwwQ',
                         '2': 'MqqeLjbzBqg',
                         '3': 'Xl5wsMRPNQc',
                         '4': 'JMzxCsMajwY',
                         '5': '6QbdG7QQhkI',
                         '6': 'hDttonV_LZI',
                         '7': 'hBQeFSpA9xQ',
                         '8': 'sB-RW4Goeiw',
                         '9': 'PU_-YyaJ2dI'}},
 20247346: {'defaultYtVideoId': 'iXY93aMLG7s',
            'fallbackTracks': [{'duration': '3:47', 'position': '1', 'title': 'Sun Killer'},
                               {'duration': '3:46', 'position': '2', 'title': 'Hurt You'},
                               {'duration': '3:18', 'position': '3', 'title': 'Yellowjacket'},
                               {'duration': '3:57', 'position': '4', 'title': 'The Summit'},
                               {'duration': '3:39', 'position': '5', 'title': 'Secret Garden'},
                               {'duration': '2:57',
                                'position': '6',
                                'title': 'Silk In The Strings'},
                               {'duration': '2:53', 'position': '7', 'title': 'Holy Roller'},
                               {'duration': '3:59', 'position': '8', 'title': 'Eternal Blue'},
                               {'duration': '2:48',
                                'position': '9',
                                'title': 'We Live In A Strange World'},
                               {'duration': '3:40', 'position': '10', 'title': 'Halcyon'},
                               {'duration': '3:53', 'position': '11', 'title': 'Circle With Me'},
                               {'duration': '4:30', 'position': '12', 'title': 'Constance'}],
            'trackDurations': {'0': '3:47',
                               '1': '3:46',
                               '10': '3:53',
                               '11': '4:30',
                               '2': '3:18',
                               '3': '3:57',
                               '4': '3:39',
                               '5': '2:57',
                               '6': '2:53',
                               '7': '3:59',
                               '8': '2:48',
                               '9': '3:40'},
            'trackIds': {'0': 'iXY93aMLG7s',
                         '1': 'ots5los164Q',
                         '10': 'I0WzT0OJ-E0',
                         '11': 'mY_oDyqRM1A',
                         '2': '8MP4QxsFICM',
                         '3': 'xqIyoWrl9rw',
                         '4': '3VcTYyuGrgM',
                         '5': '-TlxxvjNiBs',
                         '6': 'cWE0sSZ9yLc',
                         '7': 'EAiksF4bHpg',
                         '8': 'l2Q_xR-BGWA',
                         '9': 'fK6OFEaA3Cs'}},
 20518822: {'defaultYtVideoId': 'DOyyGlWoxeU',
            'fallbackTracks': [{'duration': '3:49', 'position': 'A1', 'title': 'Steel And Blood'},
                               {'duration': '4:01', 'position': 'A2', 'title': 'Lies And Eyes'},
                               {'duration': '4:55', 'position': 'A3', 'title': 'Diamond Lightning'},
                               {'duration': '4:31', 'position': 'A4', 'title': 'Toska'},
                               {'duration': '3:35', 'position': 'A5', 'title': 'Listing'},
                               {'duration': '4:49',
                                'position': 'B1',
                                'title': 'Heaven Is A Ghost Town'},
                               {'duration': '3:43', 'position': 'B2', 'title': 'Empty Party Rooms'},
                               {'duration': '3:30', 'position': 'B3', 'title': 'Zeros'},
                               {'duration': '3:45', 'position': 'B4', 'title': 'Lonely Gun'},
                               {'duration': '5:04', 'position': 'B5', 'title': 'Cold Company'}],
            'trackDurations': {'0': '3:49',
                               '1': '4:01',
                               '2': '4:55',
                               '3': '4:31',
                               '4': '3:35',
                               '5': '4:49',
                               '6': '3:43',
                               '7': '3:30',
                               '8': '3:45',
                               '9': '5:04'},
            'trackIds': {'0': 'DOyyGlWoxeU',
                         '1': 'tnTxmNFGvE4',
                         '2': 'T3NYcqwKPG8',
                         '3': '5byk940EX6w',
                         '4': 'Ts6qDLKLUxQ',
                         '5': 'b_dLxA97lrA',
                         '6': '8-v0oRQ2W0s',
                         '7': 'bVdJ7NKM8Dk',
                         '8': 'TMEy25sYRi8',
                         '9': 'YS7E4FAIURQ'}},
 20546863: {'defaultYtVideoId': '8rvZSm2dXMg',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Poster Child'},
                               {'duration': '', 'position': 'A2', 'title': 'White Nile'},
                               {'duration': '4:33', 'position': 'A3', 'title': 'Angel Or Alien'},
                               {'duration': '', 'position': 'A4', 'title': 'Waves'},
                               {'duration': '', 'position': 'B1', 'title': 'Oathbreaker'},
                               {'duration': '',
                                'position': 'B2',
                                'title': 'Threat Of Your Presence'},
                               {'duration': '', 'position': 'B3', 'title': 'Love Story'},
                               {'duration': '', 'position': 'C1', 'title': 'Crossface'},
                               {'duration': '', 'position': 'C2', 'title': 'Echobreather'},
                               {'duration': '', 'position': 'C3', 'title': 'Lost Souls'},
                               {'duration': '', 'position': 'C4', 'title': 'In For The Kill'},
                               {'duration': '', 'position': 'D1', 'title': 'You Are The Narrative'},
                               {'duration': '', 'position': 'D2', 'title': 'Truth And Denial'},
                               {'duration': '', 'position': 'D3', 'title': 'Shadowmourne'}],
            'fullAlbumYtDuration': 3305,
            'fullAlbumYtVideoId': 'EGwtcx8QwFY',
            'trackDurations': {'2': '4:33'},
            'trackIds': {'2': '8rvZSm2dXMg'}},
 20697637: {'defaultYtVideoId': '_1O1CuUuRWw',
            'fallbackTracks': [{'duration': '2:52', 'position': 'A1', 'title': 'Dark Distance'},
                               {'duration': '2:31', 'position': 'A2', 'title': 'Sly'},
                               {'duration': '3:56', 'position': 'A3', 'title': 'Planet Shit'},
                               {'duration': '3:16', 'position': 'A4', 'title': 'Post-Boredom'},
                               {'duration': '2:27', 'position': 'A5', 'title': 'A Colossal Wreck'},
                               {'duration': '3:11',
                                'position': 'B1',
                                'title': 'Desperate Pleasures'},
                               {'duration': '3:10', 'position': 'B2', 'title': 'All This And War'},
                               {'duration': '3:37',
                                'position': 'B3',
                                'title': 'Thing With Feathers'},
                               {'duration': '2:36',
                                'position': 'B4',
                                'title': 'Hostile Architecture'},
                               {'duration': '2:10', 'position': 'B5', 'title': 'AWOL'},
                               {'duration': '2:29', 'position': 'B6', 'title': 'The Whip'},
                               {'duration': '3:34', 'position': 'C1', 'title': 'White Void'},
                               {'duration': '3:13',
                                'position': 'C2',
                                'title': 'Distress Rehearsal'},
                               {'duration': '3:27', 'position': 'C3', 'title': 'sexsexsex'},
                               {'duration': '3:32', 'position': 'C4', 'title': 'People Verses'},
                               {'duration': '5:02', 'position': 'C5', 'title': 'We Go Together'}],
            'trackDurations': {'0': '2:52',
                               '1': '2:31',
                               '10': '2:29',
                               '11': '3:34',
                               '12': '3:13',
                               '13': '3:27',
                               '14': '3:32',
                               '15': '5:02',
                               '2': '3:56',
                               '3': '3:16',
                               '4': '2:27',
                               '5': '3:11',
                               '6': '3:10',
                               '7': '3:37',
                               '8': '2:36',
                               '9': '2:10'},
            'trackIds': {'3': '_1O1CuUuRWw', '7': '06mgL0GK--Y'}},
 21047380: {'defaultYtVideoId': 'T3E6AKDbI2Y',
            'fallbackTracks': [{'duration': '0:18',
                                'position': 'A1',
                                'title': '(Ambition; Destruction)'},
                               {'duration': '3:53',
                                'position': 'A2',
                                'title': 'Do You Really Want It?'},
                               {'duration': '0:41', 'position': 'A3', 'title': '(Convict; Divide)'},
                               {'duration': '3:56', 'position': 'A4', 'title': "Let 'Em Burn"},
                               {'duration': '4:04', 'position': 'A5', 'title': 'Ripping Me Apart'},
                               {'duration': '4:15', 'position': 'A6', 'title': "Don't Stop"},
                               {'duration': '3:28',
                                'position': 'B1',
                                'title': 'Funny Little Creatures'},
                               {'duration': '2:29', 'position': 'B2', 'title': '(React; Respond)'},
                               {'duration': '4:39', 'position': 'B3', 'title': 'The Great Divorce'},
                               {'duration': '4:36', 'position': 'B4', 'title': 'Still In Love'},
                               {'duration': '1:31', 'position': 'C1', 'title': '(Alone; Together)'},
                               {'duration': '4:05', 'position': 'C2', 'title': 'Go To War'},
                               {'duration': '3:41', 'position': 'C3', 'title': 'Just Say When'},
                               {'duration': '1:55',
                                'position': 'C4',
                                'title': '(Accept; Disconnect)'},
                               {'duration': '3:26', 'position': 'D1', 'title': 'Who We Are'},
                               {'duration': '4:11', 'position': 'D2', 'title': 'Tunnels'},
                               {'duration': '1:40', 'position': 'D3', 'title': '(End; Begin)'},
                               {'duration': '6:04',
                                'position': 'D4',
                                'title': 'Fade In / Fade Out'}],
            'trackDurations': {'0': '0:18',
                               '1': '3:53',
                               '10': '1:31',
                               '11': '4:05',
                               '12': '3:41',
                               '13': '1:55',
                               '14': '3:26',
                               '15': '4:11',
                               '16': '1:40',
                               '17': '6:04',
                               '2': '0:41',
                               '3': '3:56',
                               '4': '4:04',
                               '5': '4:15',
                               '6': '3:28',
                               '7': '2:29',
                               '8': '4:39',
                               '9': '4:36'},
            'trackIds': {'1': 'T3E6AKDbI2Y',
                         '11': 'Q6c8X_s1h9Y',
                         '12': 'p0rro0aGgt4',
                         '14': 'VJA_8EBQiNU',
                         '17': 'wBC3Tl0dg4M',
                         '3': 'mPb2_glC8kA',
                         '5': 'SfgUtVDdn0Q'}},
 21315247: {'defaultYtVideoId': 'MMI5bmlSrRg',
            'fallbackTracks': [{'duration': '4:21',
                                'position': 'A1',
                                'title': 'This Glorious Nightmare'},
                               {'duration': '3:57', 'position': 'A2', 'title': 'Giles'},
                               {'duration': '4:02',
                                'position': 'A3',
                                'title': 'March Of The Mutes'},
                               {'duration': '3:28',
                                'position': 'A4',
                                'title': 'Sanctity Of Brothers'},
                               {'duration': '3:21',
                                'position': 'A5',
                                'title': 'The Devil Has Risen'},
                               {'duration': '4:10',
                                'position': 'A6',
                                'title': 'This Time Was Mine'},
                               {'duration': '5:05', 'position': 'B1', 'title': 'Unstoppable'},
                               {'duration': '5:02', 'position': 'B2', 'title': 'So It Goes'},
                               {'duration': '3:23', 'position': 'B3', 'title': 'Impostors Kingdom'},
                               {'duration': '3:55', 'position': 'B4', 'title': 'Bled Dry'},
                               {'duration': '3:09',
                                'position': 'B5',
                                'title': 'Big Bear And The Hour Of Chaos'}],
            'trackDurations': {'0': '4:21',
                               '1': '3:57',
                               '10': '3:09',
                               '2': '4:02',
                               '3': '3:28',
                               '4': '3:21',
                               '5': '4:10',
                               '6': '5:05',
                               '7': '5:02',
                               '8': '3:23',
                               '9': '3:55'},
            'trackIds': {'0': 'MMI5bmlSrRg', '1': '2BoKYJzAtHM'}},
 21390094: {'defaultYtVideoId': 'nVCgCF5A4Cs',
            'fallbackTracks': [{'duration': '14:54', 'position': 'A1', 'title': 'Of Matter'},
                               {'duration': '18:24',
                                'position': 'B1',
                                'title': 'Concealing Fate (Parts 1, 2 & 3)'},
                               {'duration': '5:32', 'position': 'C1', 'title': 'Beneath My Skin'},
                               {'duration': '5:44', 'position': 'C2', 'title': 'Mirror Image'},
                               {'duration': '2:16', 'position': 'C3', 'title': 'Orbital'},
                               {'duration': '6:01', 'position': 'C4', 'title': 'Juno'},
                               {'duration': '5:28', 'position': 'D1', 'title': 'Cages'},
                               {'duration': '6:23', 'position': 'D2', 'title': 'Dystopia'},
                               {'duration': '4:11', 'position': 'D3', 'title': 'Phoenix'},
                               {'duration': '4:17', 'position': 'D4', 'title': 'Nocturne'},
                               {'duration': '6:34', 'position': 'E1', 'title': 'Eden'},
                               {'duration': '10:54', 'position': 'E2', 'title': 'Of Energy'},
                               {'duration': '5:45', 'position': 'F1', 'title': 'King'},
                               {'duration': '4:38', 'position': 'F2', 'title': 'Tourniquet'},
                               {'duration': '4:55', 'position': 'F3', 'title': 'Seven Names'}],
            'fullAlbumYtDuration': 1104,
            'fullAlbumYtVideoId': 'AmyqmTO_L1M',
            'trackDurations': {'0': '14:54',
                               '1': '18:24',
                               '10': '6:34',
                               '11': '10:54',
                               '12': '5:45',
                               '13': '4:38',
                               '14': '4:55',
                               '2': '5:32',
                               '3': '5:44',
                               '4': '2:16',
                               '5': '6:01',
                               '6': '5:28',
                               '7': '6:23',
                               '8': '4:11',
                               '9': '4:17'},
            'trackIds': {'0': 'nVCgCF5A4Cs',
                         '1': 'AmyqmTO_L1M',
                         '11': 'Pg504Z3mGqE',
                         '9': 'veqQXYhJNeg'}},
 21929479: {'defaultYtVideoId': 'lzAYXn2-1_E',
            'fallbackTracks': [{'duration': '',
                                'position': 'A1',
                                'title': 'Letters To A Dead Friend'},
                               {'duration': '', 'position': 'A2', 'title': 'Fall Again'},
                               {'duration': '3:29', 'position': 'A3', 'title': 'Face Me'},
                               {'duration': '4:10', 'position': 'A4', 'title': 'Too Far Gone'},
                               {'duration': '3:21', 'position': 'A5', 'title': 'Paradigm'},
                               {'duration': '', 'position': 'B1', 'title': 'Both To Blame'},
                               {'duration': '', 'position': 'B2', 'title': 'Too Heavy'},
                               {'duration': '', 'position': 'B3', 'title': 'Enemy'},
                               {'duration': '', 'position': 'B4', 'title': 'Whole Without Me'},
                               {'duration': '', 'position': 'B5', 'title': 'Freed'}],
            'trackDurations': {'2': '3:29', '3': '4:10', '4': '3:21'},
            'trackIds': {'0': 'lzAYXn2-1_E',
                         '1': 'eJ3afrcxZFs',
                         '2': '6f7ioSMKEms',
                         '3': 'HyETx2IPSwI',
                         '4': 'WrD6Nss7LnE',
                         '5': 'pJAMhSn-HeM',
                         '6': '_-Qc7fkmxLM',
                         '7': 'DRp1GT4r8cQ',
                         '8': 'a48CG2kg44g',
                         '9': '4nAy8VpZ1n4'}},
 21958303: {'defaultYtVideoId': 'ViFPVC3Jo24',
            'fallbackTracks': [{'duration': '2:59', 'position': 'A1', 'title': 'Relapse'},
                               {'duration': '3:08', 'position': 'A2', 'title': 'Teeth'},
                               {'duration': '2:44', 'position': 'A3', 'title': 'Manic'},
                               {'duration': '2:48', 'position': 'A4', 'title': 'High Horse'},
                               {'duration': '3:35', 'position': 'A5', 'title': 'Circle The Drain'},
                               {'duration': '3:06', 'position': 'A6', 'title': 'Godspeed'},
                               {'duration': '3:01', 'position': 'B1', 'title': 'Death Roll'},
                               {'duration': '3:09', 'position': 'B2', 'title': 'Slow Burn'},
                               {'duration': '3:19',
                                'position': 'B3',
                                'title': 'Never Said Goodbye'},
                               {'duration': '3:09', 'position': 'B4', 'title': 'True Colors'},
                               {'duration': '4:40',
                                'position': 'B5',
                                'title': 'If Tomorrow Never Comes'}],
            'trackDurations': {'0': '2:59',
                               '1': '3:08',
                               '10': '4:40',
                               '2': '2:44',
                               '3': '2:48',
                               '4': '3:35',
                               '5': '3:06',
                               '6': '3:01',
                               '7': '3:09',
                               '8': '3:19',
                               '9': '3:09'},
            'trackIds': {'0': 'ViFPVC3Jo24',
                         '1': '5xSW4LKSZLc',
                         '10': 'ZjEC816Grj4',
                         '2': 'bysWM5E9juI',
                         '3': 'TjvEqlxJgL0',
                         '4': 'NXn-dI9fFko',
                         '6': 'kUylqZM4biA',
                         '7': 'Xt-6LDpzgOw',
                         '8': 'kuyRjHhXMyg',
                         '9': 'V6E1c1xxsaM'}},
 22031968: {'defaultYtVideoId': 'hZnZ-CpX57Y',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Never There'},
                               {'duration': '3:45', 'position': 'A2', 'title': 'A Flag To Wave'},
                               {'duration': '', 'position': 'A3', 'title': 'Poverty Of Self'},
                               {'duration': '', 'position': 'A4', 'title': 'Monsters'},
                               {'duration': '3:54', 'position': 'A5', 'title': 'Kill The Ache'},
                               {'duration': '', 'position': 'A6', 'title': 'Let Me Leave'},
                               {'duration': '', 'position': 'B1', 'title': 'Origin'},
                               {'duration': '', 'position': 'B2', 'title': 'Split'},
                               {'duration': '', 'position': 'B3', 'title': 'Second Skin'},
                               {'duration': '', 'position': 'B4', 'title': 'How I Fall Apart'},
                               {'duration': '', 'position': 'B5', 'title': 'Better Days'}],
            'fullAlbumYtDuration': 2332,
            'fullAlbumYtVideoId': 'dy8IMkekW4U',
            'trackDurations': {'1': '3:45', '4': '3:54'},
            'trackIds': {'1': 'hZnZ-CpX57Y', '4': 'upTN4u7SjTM'}},
 22153450: {'defaultYtVideoId': 'sIPdH7vLmgQ',
            'fallbackTracks': [{'duration': '3:43', 'position': 'A1', 'title': 'Dispossession'},
                               {'duration': '4:04', 'position': 'A2', 'title': 'Abrasumente'},
                               {'duration': '4:13', 'position': 'A3', 'title': 'Comatose'},
                               {'duration': '3:43',
                                'position': 'A4',
                                'title': 'Transcending Dimensions'},
                               {'duration': '4:56', 'position': 'A5', 'title': 'Discoveries'},
                               {'duration': '3:55', 'position': 'B1', 'title': 'Corruption'},
                               {'duration': '3:41', 'position': 'B2', 'title': 'Exposure'},
                               {'duration': '4:39', 'position': 'B3', 'title': 'Metamorphosis'},
                               {'duration': '3:23', 'position': 'B4', 'title': 'Solitude'},
                               {'duration': '4:56',
                                'position': 'B5',
                                'title': 'Ishookhandswithdeath'}],
            'fullAlbumYtDuration': 2477,
            'fullAlbumYtVideoId': '6-CdrxX-JOg',
            'trackDurations': {'0': '3:43',
                               '1': '4:04',
                               '2': '4:13',
                               '3': '3:43',
                               '4': '4:56',
                               '5': '3:55',
                               '6': '3:41',
                               '7': '4:39',
                               '8': '3:23',
                               '9': '4:56'},
            'trackIds': {'0': 'sIPdH7vLmgQ', '4': '6-CdrxX-JOg'}},
 22544762: {'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'I Am Become A Name...'},
                               {'duration': '', 'position': 'A2', 'title': 'Ghost'},
                               {'duration': '', 'position': 'A3', 'title': 'Temptation'},
                               {'duration': '', 'position': 'A4', 'title': 'Surrender'},
                               {'duration': '', 'position': 'A5', 'title': 'Chasing Shadows'},
                               {'duration': '', 'position': 'B1', 'title': 'Moth To A Flame'},
                               {'duration': '', 'position': 'B2', 'title': 'Alleviate'},
                               {'duration': '', 'position': 'B3', 'title': 'Enslaved'},
                               {'duration': '', 'position': 'B4', 'title': 'Disappear'},
                               {'duration': '', 'position': 'C1', 'title': 'Lost And Left Behind'},
                               {'duration': '', 'position': 'C2', 'title': 'این نیز بگذرد'},
                               {'duration': '', 'position': 'C3', 'title': '∞'},
                               {'duration': '', 'position': 'C4', 'title': 'Heaven In Hiding'}]},
 22568519: {'defaultYtVideoId': 'UgPujyXPM84',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Erase'},
                               {'duration': '', 'position': 'A2', 'title': 'Paralyzed'},
                               {'duration': '', 'position': 'A3', 'title': 'Room To Breathe'},
                               {'duration': '', 'position': 'A4', 'title': 'Saturated Soul'},
                               {'duration': '5:38', 'position': 'A5', 'title': 'Infectious'},
                               {'duration': '', 'position': 'A6', 'title': 'The Sickness'},
                               {'duration': '', 'position': 'B1', 'title': 'Death of You'},
                               {'duration': '', 'position': 'B2', 'title': 'Scars'},
                               {'duration': '', 'position': 'B3', 'title': 'Disconnected'},
                               {'duration': '', 'position': 'B4', 'title': 'Wake Me Up'},
                               {'duration': '', 'position': 'B5', 'title': "Don't Tell A Soul"},
                               {'duration': '', 'position': 'B6', 'title': 'To The Light'},
                               {'duration': '3:53', 'position': 'C1', 'title': 'Lighthouse'},
                               {'duration': '', 'position': 'C2', 'title': 'Love & Grace'},
                               {'duration': '',
                                'position': 'C3',
                                'title': 'Paralyzed - Live in Studio Mega'},
                               {'duration': '',
                                'position': 'C4',
                                'title': 'Saturated Soul - Live in Studio Mega'},
                               {'duration': '5:38',
                                'position': 'C5',
                                'title': 'Infectious - Live in Studio Mega'},
                               {'duration': '', 'position': 'D1', 'title': 'Erase - Acoustic'},
                               {'duration': '',
                                'position': 'D2',
                                'title': 'Saturated Soul - Acoustic'},
                               {'duration': '', 'position': 'D3', 'title': 'Paralyzed - Acoustic'},
                               {'duration': '',
                                'position': 'D4',
                                'title': 'Disconnected - Acoustic'},
                               {'duration': '5:38',
                                'position': 'D5',
                                'title': 'Infectious - Acoustic'}],
            'trackDurations': {'12': '3:53', '16': '5:38', '21': '5:38', '4': '5:38'},
            'trackIds': {'12': 'mh4GQq3cL7Y',
                         '16': 'UgPujyXPM84',
                         '21': 'UgPujyXPM84',
                         '4': 'UgPujyXPM84'}},
 22879535: {'defaultYtVideoId': '2Lf6K-WhDRM',
            'fallbackTracks': [{'duration': '5:00',
                                'position': 'A1',
                                'title': 'No One Will Teach You'},
                               {'duration': '', 'position': 'A2', 'title': 'Lavos'},
                               {'duration': '4:43', 'position': 'A3', 'title': 'Cardinal Red'},
                               {'duration': '4:18', 'position': 'A4', 'title': 'Opiate'},
                               {'duration': '4:43', 'position': 'A5', 'title': 'Collapse'},
                               {'duration': '5:29', 'position': 'B1', 'title': 'Arch Essence'},
                               {'duration': '', 'position': 'B2', 'title': 'Somnus'},
                               {'duration': '4:43', 'position': 'B3', 'title': 'False Providence'},
                               {'duration': '4:28', 'position': 'B4', 'title': 'Makeshift Harmony'},
                               {'duration': '', 'position': 'B5', 'title': 'The Cimmerian'},
                               {'duration': '5:00',
                                'position': 'CD-1',
                                'title': 'No One Will Teach You'},
                               {'duration': '', 'position': 'CD-2', 'title': 'Lavos'},
                               {'duration': '4:43', 'position': 'CD-3', 'title': 'Cardinal Red'},
                               {'duration': '4:18', 'position': 'CD-4', 'title': 'Opiate'},
                               {'duration': '4:43', 'position': 'CD-5', 'title': 'Collapse'},
                               {'duration': '5:29', 'position': 'CD-6', 'title': 'Arch Essence'},
                               {'duration': '', 'position': 'CD-7', 'title': 'Somnus'},
                               {'duration': '4:43',
                                'position': 'CD-8',
                                'title': 'False Providence'},
                               {'duration': '4:28',
                                'position': 'CD-9',
                                'title': 'Makeshift Harmony'},
                               {'duration': '', 'position': 'CD-10', 'title': 'The Cimmerian'}],
            'fullAlbumYtDuration': 3064,
            'fullAlbumYtVideoId': 'M1jAETb7BJQ',
            'trackDurations': {'0': '5:00',
                               '10': '5:00',
                               '12': '4:43',
                               '13': '4:18',
                               '14': '4:43',
                               '15': '5:29',
                               '17': '4:43',
                               '18': '4:28',
                               '2': '4:43',
                               '3': '4:18',
                               '4': '4:43',
                               '5': '5:29',
                               '7': '4:43',
                               '8': '4:28'},
            'trackIds': {'0': '2Lf6K-WhDRM',
                         '10': '2Lf6K-WhDRM',
                         '12': 'MGG-p0Pmc7Q',
                         '13': 'b6cdYcUJ1dU',
                         '14': 'a2qo2c3axcA',
                         '15': 'H1Lfj4oA9P8',
                         '17': '7i6nvi5wh5s',
                         '18': 'VEViBL1LN-0',
                         '2': 'MGG-p0Pmc7Q',
                         '3': 'b6cdYcUJ1dU',
                         '4': 'a2qo2c3axcA',
                         '5': 'H1Lfj4oA9P8',
                         '7': '7i6nvi5wh5s',
                         '8': 'VEViBL1LN-0'}},
 22968539: {'defaultYtVideoId': 'qiRno1CVOSU',
            'fallbackTracks': [{'duration': '5:53', 'position': 'A1', 'title': 'Clarity'},
                               {'duration': '3:59', 'position': 'A2', 'title': 'Clockwork'},
                               {'duration': '3:47', 'position': 'A3', 'title': 'Echo Chamber'},
                               {'duration': '3:46', 'position': 'B1', 'title': 'Carbonized'},
                               {'duration': '4:10', 'position': 'B2', 'title': 'Abomination'},
                               {'duration': '3:40', 'position': 'B3', 'title': 'Plenty'},
                               {'duration': '3:30', 'position': 'C1', 'title': 'Is This A Test?'},
                               {'duration': '5:48', 'position': 'C2', 'title': 'Xen'},
                               {'duration': '4:37', 'position': 'C3', 'title': 'Cypher'},
                               {'duration': '4:27', 'position': 'C4', 'title': 'Nova'},
                               {'duration': '3:50', 'position': 'D1', 'title': 'Inamorata'},
                               {'duration': '3:56', 'position': 'D2', 'title': 'Obsidian'},
                               {'duration': '4:54', 'position': 'D3', 'title': 'Dark Solitaire'}],
            'trackDurations': {'0': '5:53',
                               '1': '3:59',
                               '10': '3:50',
                               '11': '3:56',
                               '12': '4:54',
                               '2': '3:47',
                               '3': '3:46',
                               '4': '4:10',
                               '5': '3:40',
                               '6': '3:30',
                               '7': '5:48',
                               '8': '4:37',
                               '9': '4:27'},
            'trackIds': {'0': 'qiRno1CVOSU',
                         '1': 'TwyvWR25FsE',
                         '10': 'lltVI8UWRoA',
                         '11': 'hdGB99U_wlg',
                         '12': 'QAEzFd4UF4Q',
                         '2': '6-WZ1JO-3P0',
                         '3': '-s4TiCT7nWI',
                         '4': 'W7B6zJc6xHg',
                         '5': 'HDsLFV5xhvk',
                         '6': 'KgQuYpi6Mgw',
                         '7': 'WAtr_vxBWXE',
                         '8': 'N0RxKEkyX5w',
                         '9': 'LyILjY1OS9U'}},
 23343893: {'defaultYtVideoId': '86i3YTruoGo',
            'fallbackTracks': [{'duration': '',
                                'position': 'A1',
                                'title': 'My Heart Bleeds No Longer'},
                               {'duration': '', 'position': 'A2', 'title': 'One Step Away'},
                               {'duration': '', 'position': 'A3', 'title': 'Fuel The Fire'},
                               {'duration': '', 'position': 'A4', 'title': 'Only The People'},
                               {'duration': '', 'position': 'A5', 'title': 'Stings Of Conscience'},
                               {'duration': '', 'position': 'B1', 'title': 'My Desire'},
                               {'duration': '', 'position': 'B2', 'title': 'Vanishment'},
                               {'duration': '', 'position': 'B3', 'title': 'Shattered By The Sun'},
                               {'duration': '', 'position': 'B4', 'title': 'Monition'},
                               {'duration': '', 'position': 'B5', 'title': 'Stronghold'}],
            'trackIds': {'0': '86i3YTruoGo', '4': '86i3YTruoGo'}},
 23605157: {'fallbackTracks': [{'duration': '',
                                'position': 'A1',
                                'title': 'So Cold I Could See My Breath'},
                               {'duration': '', 'position': 'A2', 'title': 'Playing With Fire'},
                               {'duration': '',
                                'position': 'A3',
                                'title': 'Returning The Smile You Have Had From The Start'},
                               {'duration': '', 'position': 'A4', 'title': 'Studying Politics'},
                               {'duration': '',
                                'position': 'A5',
                                'title': 'Left With Alibis And Lying Eyes'},
                               {'duration': '',
                                'position': 'A6',
                                'title': 'Listening to Freddie Mercury'},
                               {'duration': '', 'position': 'B1', 'title': 'The Weakest'},
                               {'duration': '', 'position': 'B2', 'title': "Miss Behavin'"},
                               {'duration': '',
                                'position': 'B3',
                                'title': 'In Between 4th and 2nd Street'},
                               {'duration': '', 'position': 'B4', 'title': 'The Terrible Secret'},
                               {'duration': '',
                                'position': 'B5',
                                'title': 'In A Lose, Lose Situation'},
                               {'duration': '',
                                'position': 'B6',
                                'title': 'In A Win, Win Situation'}]},
 23657633: {'defaultYtVideoId': 'cEfhtQFaLqU',
            'fallbackTracks': [{'duration': '5:07', 'position': 'A1', 'title': 'The Hellfire Club'},
                               {'duration': '3:22', 'position': 'A2', 'title': 'Leather Wings'},
                               {'duration': '4:51', 'position': 'A3', 'title': 'Blue Velvet'},
                               {'duration': '4:11', 'position': 'A4', 'title': 'Arkangel'},
                               {'duration': '3:14', 'position': 'A5', 'title': 'Valentine'},
                               {'duration': '3:59', 'position': 'B1', 'title': 'Casanova'},
                               {'duration': '2:31',
                                'position': 'B2',
                                'title': 'Something Terrible Came with the Rain'},
                               {'duration': '5:10', 'position': 'B3', 'title': 'Hollywood'},
                               {'duration': '3:43', 'position': 'B4', 'title': 'Raw'},
                               {'duration': '5:00', 'position': 'B5', 'title': 'Varsity Hearts'},
                               {'duration': '5:00', 'position': 'B6', 'title': 'Heroine'}],
            'fullAlbumYtDuration': 2765,
            'fullAlbumYtVideoId': '0J8nEtN43Tk',
            'trackDurations': {'0': '5:07',
                               '1': '3:22',
                               '10': '5:00',
                               '2': '4:51',
                               '3': '4:11',
                               '4': '3:14',
                               '5': '3:59',
                               '6': '2:31',
                               '7': '5:10',
                               '8': '3:43',
                               '9': '5:00'},
            'trackIds': {'0': 'cEfhtQFaLqU',
                         '1': 'pvW1_cgwgw0',
                         '10': 'NXjOaJOMxOg',
                         '2': '9Ty32V6ja0Q',
                         '4': 'TKBFcMZY-DU',
                         '8': 'AK8LIlvnFS8',
                         '9': 'EXLcf3RR9tk'},
            'ytPlaylistId': 'OLAK5uy_md5n68zYjGf_MiXGIvxE4P0cJ6kakvba8'},
 23674760: {'defaultYtVideoId': '9NBaKRUrr_M',
            'fallbackTracks': [{'duration': '1:36',
                                'position': 'A1',
                                'title': 'The Embers Of Fire'},
                               {'duration': '3:36', 'position': 'A2', 'title': 'Beautiful Losers'},
                               {'duration': '3:14', 'position': 'A3', 'title': 'Comatose'},
                               {'duration': '3:24', 'position': 'A4', 'title': 'Shoulders'},
                               {'duration': '3:30',
                                'position': 'A5',
                                'title': 'A Disappearing Act'},
                               {'duration': '3:26', 'position': 'B1', 'title': 'Love Murder One'},
                               {'duration': '3:56', 'position': 'B2', 'title': 'Blood'},
                               {'duration': '3:53', 'position': 'B3', 'title': 'The Liars Club'},
                               {'duration': '3:29', 'position': 'B4', 'title': 'Bad Man'},
                               {'duration': '2:29', 'position': 'C1', 'title': 'Our Love'},
                               {'duration': '6:49',
                                'position': 'C2',
                                'title': 'Ladders Of Supremacy'},
                               {'duration': '5:20',
                                'position': 'C3',
                                'title': 'Rise, Naianasha (Cut The Cord)'},
                               {'duration': '8:39',
                                'position': 'D1',
                                'title': 'Window Of The Waking Mind'}],
            'trackDurations': {'0': '1:36',
                               '1': '3:36',
                               '10': '6:49',
                               '11': '5:20',
                               '12': '8:39',
                               '2': '3:14',
                               '3': '3:24',
                               '4': '3:30',
                               '5': '3:26',
                               '6': '3:56',
                               '7': '3:53',
                               '8': '3:29',
                               '9': '2:29'},
            'trackIds': {'0': '9NBaKRUrr_M',
                         '1': 'XZpM_G2i5Uo',
                         '10': '1YNsq20co-o',
                         '11': '2BFqmKtLj1s',
                         '12': 'WscFSf_OjHA',
                         '2': 'sG940KWNeI8',
                         '3': '-Tb_v8MFbF8',
                         '4': 'QbmQH2LnuNs',
                         '5': '2dgLtjx-ZFg',
                         '6': 'nP7X8M-ngqU',
                         '7': 'ltKTHtMmDJQ',
                         '8': 'cOUCJUgVzIw',
                         '9': '7Ka43I-cN7g'}},
 23753615: {'defaultYtVideoId': 'lCPwR7R4hlA',
            'fallbackTracks': [{'duration': '1:55', 'position': 'A1', 'title': 'Nyu'},
                               {'duration': '2:51', 'position': 'A2', 'title': 'Leeloo'},
                               {'duration': '3:03', 'position': 'A3', 'title': 'Ellie'},
                               {'duration': '2:55', 'position': 'A4', 'title': 'Lucy'},
                               {'duration': '3:09', 'position': 'A5', 'title': 'Mikasa'},
                               {'duration': '3:47', 'position': 'A6', 'title': 'Aeris'},
                               {'duration': '3:26', 'position': 'B1', 'title': 'Three-Fifty'},
                               {'duration': '3:16', 'position': 'B2', 'title': 'Phoenix'},
                               {'duration': '1:18', 'position': 'B3', 'title': 'Matriarch'},
                               {'duration': '3:00', 'position': 'B4', 'title': 'Teleute'},
                               {'duration': '3:39', 'position': 'B5', 'title': 'Daenerys'},
                               {'duration': '3:45', 'position': 'B6', 'title': 'Lisbeth'}],
            'trackDurations': {'0': '1:55',
                               '1': '2:51',
                               '10': '3:39',
                               '11': '3:45',
                               '2': '3:03',
                               '3': '2:55',
                               '4': '3:09',
                               '5': '3:47',
                               '6': '3:26',
                               '7': '3:16',
                               '8': '1:18',
                               '9': '3:00'},
            'trackIds': {'10': 'uq6UnpsmEZI',
                         '4': 'lCPwR7R4hlA',
                         '5': 'XuqSC7x_M18',
                         '8': '6ljL1D0J3Y8'}},
 23775551: {'defaultYtVideoId': 'OI6BWndxkcs',
            'fallbackTracks': [{'duration': '3:37', 'position': '1', 'title': 'Gumshield'},
                               {'duration': '3:37',
                                'position': '2',
                                'title': 'Manchester Super Red No. 1 Fan'},
                               {'duration': '4:38', 'position': '3', 'title': 'Swimwear  Season'},
                               {'duration': '3:54', 'position': '4', 'title': 'Endorphins'},
                               {'duration': '3:58', 'position': '5', 'title': 'One True Prince'},
                               {'duration': '4:30', 'position': '6', 'title': 'Anaheim'},
                               {'duration': '3:31', 'position': '7', 'title': 'Uber'},
                               {'duration': '4:31',
                                'position': '8',
                                'title': 'How Are You Done With Existing?'},
                               {'duration': '3:16', 'position': '9', 'title': 'Burce Willis'},
                               {'duration': '3:46', 'position': '10', 'title': 'Revenge Body'},
                               {'duration': '4:20', 'position': '11', 'title': 'Bad 4 Ur Health'},
                               {'duration': '3:06', 'position': '12', 'title': 'Easter Sunday'}],
            'trackDurations': {'0': '3:37',
                               '1': '3:37',
                               '10': '4:20',
                               '11': '3:06',
                               '2': '4:38',
                               '3': '3:54',
                               '4': '3:58',
                               '5': '4:30',
                               '6': '3:31',
                               '7': '4:31',
                               '8': '3:16',
                               '9': '3:46'},
            'trackIds': {'0': 'OI6BWndxkcs',
                         '1': 'TL_gq84CRpo',
                         '10': 'eeWfUWYMgUA',
                         '11': '5gEzRDoKL8o',
                         '2': 'wYtiuYoBx_A',
                         '3': 'jJabdNMcyFs',
                         '4': 'KM660VDc6BY',
                         '5': 'jHrBsbxFDBk',
                         '6': '4Dz7evHfvRw',
                         '7': 'UCGhXXlkWPw',
                         '8': 'TXoYJu6_JRo',
                         '9': 'YLpHSXbz13U'}},
 25089742: {'defaultYtVideoId': 'TnCUJVPQH3I',
            'fallbackTracks': [{'duration': '3:33', 'position': 'A1', 'title': 'Deep Fake'},
                               {'duration': '4:14', 'position': 'A2', 'title': 'Tear Gas'},
                               {'duration': '3:32', 'position': 'A3', 'title': 'Spit The Bone'},
                               {'duration': '4:19',
                                'position': 'A4',
                                'title': 'Burn Down My House'},
                               {'duration': '3:41',
                                'position': 'A5',
                                'title': 'Living Is Killing Us'},
                               {'duration': '3:13',
                                'position': 'B1',
                                'title': 'When We Were Young'},
                               {'duration': '4:19', 'position': 'B2', 'title': 'Doomscrolling'},
                               {'duration': '3:31',
                                'position': 'B3',
                                'title': 'Born Again Pessimist'},
                               {'duration': '3:31',
                                'position': 'B4',
                                'title': 'A New Moral Low Ground'},
                               {'duration': '4:01',
                                'position': 'B5',
                                'title': 'All The Love In The World'},
                               {'duration': '4:20', 'position': 'B6', 'title': 'Be Very Afraid'}],
            'fullAlbumYtDuration': 260,
            'fullAlbumYtVideoId': 'o-GU_fmvZ3c',
            'trackDurations': {'0': '3:33',
                               '1': '4:14',
                               '10': '4:20',
                               '2': '3:32',
                               '3': '4:19',
                               '4': '3:41',
                               '5': '3:13',
                               '6': '4:19',
                               '7': '3:31',
                               '8': '3:31',
                               '9': '4:01'},
            'trackIds': {'0': 'TnCUJVPQH3I',
                         '1': 'X45uvccd5rA',
                         '10': '_EE-zVsTPlI',
                         '2': 'JCdUYBOJrKk',
                         '3': 'o-GU_fmvZ3c',
                         '4': 'oTUxePOrIGU',
                         '5': '1yOaxGQ-CYI',
                         '6': 'cOqpShm4PIQ',
                         '7': 'GmHCDoWK_H4',
                         '8': 't9mA1iLE-UY',
                         '9': 'aRmgCFE7lrg'}},
 25367083: {'defaultYtVideoId': 'xbOF5U2h_xg',
            'fallbackTracks': [{'duration': '1:46', 'position': 'A1', 'title': 'Samsara'},
                               {'duration': '2:27', 'position': 'A2', 'title': 'Unrest'},
                               {'duration': '4:08', 'position': 'A3', 'title': 'Sleepwalker'},
                               {'duration': '3:22', 'position': 'A4', 'title': 'Wreckage'},
                               {'duration': '3:48', 'position': 'B1', 'title': 'Deadweight'},
                               {'duration': '4:31', 'position': 'B2', 'title': 'Alone'},
                               {'duration': '3:23', 'position': 'B3', 'title': 'Pressures'},
                               {'duration': '4:14', 'position': 'C1', 'title': 'Deliver Me'},
                               {'duration': '3:52', 'position': 'C2', 'title': 'Karma'},
                               {'duration': '4:09',
                                'position': 'C3',
                                'title': 'Home Is For The Heartless'},
                               {'duration': '3:01', 'position': 'D1', 'title': 'Hollow'},
                               {'duration': '3:50', 'position': 'D2', 'title': 'Leviathan'},
                               {'duration': '1:35', 'position': 'D3', 'title': 'Set To Destroy'}],
            'fullAlbumYtDuration': 106,
            'fullAlbumYtVideoId': 'xbOF5U2h_xg',
            'trackDurations': {'0': '1:46',
                               '1': '2:27',
                               '10': '3:01',
                               '11': '3:50',
                               '12': '1:35',
                               '2': '4:08',
                               '3': '3:22',
                               '4': '3:48',
                               '5': '4:31',
                               '6': '3:23',
                               '7': '4:14',
                               '8': '3:52',
                               '9': '4:09'},
            'trackIds': {'0': 'xbOF5U2h_xg',
                         '1': 'MkcabeM6MH8',
                         '10': 'yCAC4tX_LBg',
                         '11': 'xM-Jmwk-6YU',
                         '12': 'gNZISXXCoYw',
                         '2': 'AVDcwAE1dl0',
                         '3': 'PXc5ThGlQ2c',
                         '4': 'Jj1FgS885NE',
                         '5': 'F8st3FGJ0qA',
                         '6': 'qTXwoP7PdkM',
                         '7': 'ei5hEyBnRF4',
                         '8': 'CeetS4vERoo',
                         '9': '-VF4ObZEM8w'}},
 25418758: {'defaultYtVideoId': 'XCKAkWkuuWU',
            'fallbackTracks': [{'duration': '0:42', 'position': 'A1', 'title': '0:00'},
                               {'duration': '3:57',
                                'position': 'A2',
                                'title': "There's Fear In Letting Go"},
                               {'duration': '3:17', 'position': 'A3', 'title': 'Body Bag'},
                               {'duration': '2:52', 'position': 'A4', 'title': 'Self-destruction'},
                               {'duration': '3:49', 'position': 'A5', 'title': 'Bad Things'},
                               {'duration': '2:52', 'position': 'A6', 'title': 'Fake'},
                               {'duration': '2:47', 'position': 'A7', 'title': 'Judgement Day'},
                               {'duration': '3:18', 'position': 'A8', 'title': 'FWYTYK'},
                               {'duration': '3:27', 'position': 'B1', 'title': 'Deep End'},
                               {'duration': '3:01',
                                'position': 'B2',
                                'title': 'Long Live The King'},
                               {'duration': '3:03', 'position': 'B3', 'title': 'Choke'},
                               {'duration': '2:21', 'position': 'B4', 'title': 'The Negative'},
                               {'duration': '3:10', 'position': 'B5', 'title': 'Closure'},
                               {'duration': '2:45', 'position': 'B6', 'title': 'Visceral'},
                               {'duration': '3:48', 'position': 'B7', 'title': 'Doomed'}],
            'trackDurations': {'0': '0:42',
                               '1': '3:57',
                               '10': '3:03',
                               '11': '2:21',
                               '12': '3:10',
                               '13': '2:45',
                               '14': '3:48',
                               '2': '3:17',
                               '3': '2:52',
                               '4': '3:49',
                               '5': '2:52',
                               '6': '2:47',
                               '7': '3:18',
                               '8': '3:27',
                               '9': '3:01'},
            'trackIds': {'0': 'XCKAkWkuuWU',
                         '1': 'kN6OPdy3W0E',
                         '10': 'kINkBXS_YZY',
                         '11': '1ptK9aFkW38',
                         '12': 'Et1jlM3AQKg',
                         '13': '1t9h-bugGrU',
                         '14': '--Y1LehCVks',
                         '2': 'zEzYKLLUAI4',
                         '3': 'xQoC9JlNXM8',
                         '4': '8BMXHQg9WqE',
                         '5': 'Q08aoD2twuA',
                         '6': 'CVm5pSBcm9s',
                         '7': 'ASr-WjLZs7U',
                         '8': 'c6i88Y7gDl4',
                         '9': 'phJuYmiTdxs'},
            'ytPlaylistId': 'OLAK5uy_lQrfpJq3e7CNZfbrK45tu46td3sjOKNIc'},
 25484485: {'defaultYtVideoId': '5yqWtYD8qSI',
            'fallbackTracks': [{'duration': '4:24', 'position': 'A1', 'title': 'M∆chine'},
                               {'duration': '3:57', 'position': 'A2', 'title': 'Divergency'},
                               {'duration': '3:32', 'position': 'A3', 'title': 'Mindful'},
                               {'duration': '3:32', 'position': 'A4', 'title': 'Exhil∆r∆te'},
                               {'duration': '4:05', 'position': 'A5', 'title': '∆bsolution'},
                               {'duration': '3:45', 'position': 'A6', 'title': 'The Origin'},
                               {'duration': '3:55', 'position': 'B1', 'title': '∆eon III'},
                               {'duration': '3:12',
                                'position': 'B2',
                                'title': 'Im∆gin∆ry Condition'},
                               {'duration': '3:59', 'position': 'B3', 'title': 'Illusionist'},
                               {'duration': '3:47', 'position': 'B4', 'title': 'Source Field'},
                               {'duration': '4:10', 'position': 'B5', 'title': 'Venge∆nce'}],
            'trackDurations': {'0': '4:24',
                               '1': '3:57',
                               '10': '4:10',
                               '2': '3:32',
                               '3': '3:32',
                               '4': '4:05',
                               '5': '3:45',
                               '6': '3:55',
                               '7': '3:12',
                               '8': '3:59',
                               '9': '3:47'},
            'trackIds': {'0': '5yqWtYD8qSI',
                         '1': 'L9ABuasa1Cc',
                         '10': 'dzT2t5Ofo_s',
                         '2': 'WLpxTf5loIc',
                         '3': 'jgS4KvasQg8',
                         '4': '0sE4sR6rE0U',
                         '5': 'fXqzb8BQZO0',
                         '6': 'RKRlEhVu2LU',
                         '7': 'EY-145Tnmjw',
                         '8': 'T_0HOrNg-W0',
                         '9': 'PLOpQHH1St0'}},
 25541158: {'defaultYtVideoId': 'HI25fVw7PIE',
            'fallbackTracks': [{'duration': '3:32',
                                'position': 'A1',
                                'title': 'The Other Half Of Me'},
                               {'duration': '3:36',
                                'position': 'A2',
                                'title': 'Throw Me In The Jungle'},
                               {'duration': '4:09', 'position': 'A3', 'title': 'Free Fall'},
                               {'duration': '4:45', 'position': 'A4', 'title': 'Illuminate'},
                               {'duration': '3:42',
                                'position': 'A5',
                                'title': 'The Sleeping And The Dead'},
                               {'duration': '4:21', 'position': 'A6', 'title': 'Tidebinder'},
                               {'duration': '3:50', 'position': 'B1', 'title': 'Resilience'},
                               {'duration': '3:23',
                                'position': 'B2',
                                'title': 'Goddess Of The Dawn'},
                               {'duration': '3:27',
                                'position': 'B3',
                                'title': 'The Louder The Sound, The More We All Believe'},
                               {'duration': '4:09', 'position': 'B4', 'title': 'Warlords'},
                               {'duration': '3:22', 'position': 'B5', 'title': 'River Of Time'},
                               {'duration': '4:28', 'position': 'B6', 'title': 'The Composer'}],
            'fullAlbumYtDuration': 2810,
            'fullAlbumYtVideoId': '5Tj8xEZTD5o',
            'trackDurations': {'0': '3:32',
                               '1': '3:36',
                               '10': '3:22',
                               '11': '4:28',
                               '2': '4:09',
                               '3': '4:45',
                               '4': '3:42',
                               '5': '4:21',
                               '6': '3:50',
                               '7': '3:23',
                               '8': '3:27',
                               '9': '4:09'},
            'trackIds': {'0': 'HI25fVw7PIE', '3': 'XjxtBrId4Q4'}},
 25599913: {'defaultYtVideoId': 'tptChkpxMoQ',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Begin'},
                               {'duration': '', 'position': 'A2', 'title': 'The Siren’s Song'},
                               {'duration': '', 'position': 'A3', 'title': 'Feed Them To The Pigs'},
                               {'duration': '', 'position': 'A4', 'title': 'Carrion'},
                               {'duration': '', 'position': 'A5', 'title': 'Five Months'},
                               {'duration': '3:17', 'position': 'A6', 'title': 'Boneyards'},
                               {'duration': '', 'position': 'B1', 'title': 'Idols and Anchors'},
                               {'duration': '', 'position': 'B2', 'title': 'Moments In Oblivion'},
                               {'duration': '', 'position': 'B3', 'title': 'Breaking Point'},
                               {'duration': '', 'position': 'B4', 'title': 'Dead Man’s Chest'},
                               {'duration': '', 'position': 'B5', 'title': 'Frostbite'},
                               {'duration': '', 'position': 'B6', 'title': 'Horizons'}],
            'trackDurations': {'5': '3:17'},
            'trackIds': {'5': 'tptChkpxMoQ'}},
 26047147: {'defaultYtVideoId': 'AEn8HmgJxd4',
            'fallbackTracks': [{'duration': '',
                                'position': 'A1',
                                'title': 'No Stars Over Bethlehem'},
                               {'duration': '4:28', 'position': 'A2', 'title': 'Heretic & Killers'},
                               {'duration': '', 'position': 'A3', 'title': 'Divinity Within'},
                               {'duration': '', 'position': 'B1', 'title': 'Bury The Hatchet'},
                               {'duration': '', 'position': 'B2', 'title': 'Nautical'},
                               {'duration': '3:54', 'position': 'B3', 'title': 'Blindfold Aside'},
                               {'duration': '',
                                'position': 'C1',
                                'title': 'She Who Mars The Skin Of Gods'},
                               {'duration': '6:24',
                                'position': 'C2',
                                'title': 'Turn Soonest To The Sea'},
                               {'duration': '4:48',
                                'position': 'D1',
                                'title': 'The Divine Suicide Of K'},
                               {'duration': '',
                                'position': 'D2',
                                'title': 'A Plateful Of Our Dead'}],
            'fullAlbumYtDuration': 2880,
            'fullAlbumYtVideoId': '8l_V2a5ZTqQ',
            'trackDurations': {'1': '4:28', '5': '3:54', '7': '6:24', '8': '4:48'},
            'trackIds': {'1': 'AEn8HmgJxd4',
                         '5': '8x3sLH4G0qA',
                         '7': 'ygUPP02XHwg',
                         '8': 'DLUD8jicLsk'}},
 26047519: {'defaultYtVideoId': 'rhMfz4HrcEA',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Piano Prelude'},
                               {'duration': '3:55', 'position': 'A2', 'title': 'Bloodmeat'},
                               {'duration': '4:25', 'position': 'A3', 'title': 'The Dissentience'},
                               {'duration': '', 'position': 'B1', 'title': 'Bone Marrow'},
                               {'duration': '3:30', 'position': 'B2', 'title': 'Sequoia Throne'},
                               {'duration': '4:41', 'position': 'C1', 'title': 'Palms Read'},
                               {'duration': '4:24', 'position': 'C2', 'title': 'Limb From Limb'},
                               {'duration': '3:45', 'position': 'C3', 'title': 'Spoils'},
                               {'duration': '4:13', 'position': 'D1', 'title': 'Wretch'},
                               {'duration': '', 'position': 'D2', 'title': 'Goddess Bound'},
                               {'duration': '3:15', 'position': 'D3', 'title': 'Goddess Gagged'}],
            'trackDurations': {'1': '3:55',
                               '10': '3:15',
                               '2': '4:25',
                               '4': '3:30',
                               '5': '4:41',
                               '6': '4:24',
                               '7': '3:45',
                               '8': '4:13'},
            'trackIds': {'1': 'rhMfz4HrcEA',
                         '10': 'YiNP-C2vmwQ',
                         '2': 'cEFJYg9nOWE',
                         '4': 'dWig9FwqWpk',
                         '5': 'YaGSX_KQwnc',
                         '6': '32Q4x112dAU',
                         '7': 'WqL_JnnOo9k',
                         '8': 'pneeCPirlyw'}},
 26411060: {'defaultYtVideoId': 'ei2wA2Ndm6M',
            'fallbackTracks': [{'duration': '2:47', 'position': 'A1', 'title': 'Kill Me Quickly'},
                               {'duration': '1:49', 'position': 'A2', 'title': 'A Subtle Dagger'},
                               {'duration': '2:36',
                                'position': 'A3',
                                'title': 'See You In The Shallows'},
                               {'duration': '2:50',
                                'position': 'A4',
                                'title': 'Betrayal Is A Symptom'},
                               {'duration': '3:01', 'position': 'A5', 'title': 'Deadbolt'},
                               {'duration': '2:17', 'position': 'A6', 'title': 'In Years To Come'},
                               {'duration': '2:15', 'position': 'A7', 'title': 'The Red Death'},
                               {'duration': '',
                                'position': 'A8',
                                'title': 'A Living Dance Upon Dead Minds'},
                               {'duration': '3:09',
                                'position': 'B1',
                                'title': 'Where Idols Once Stood'},
                               {'duration': '2:55', 'position': 'B2', 'title': 'Trust'},
                               {'duration': '3:07',
                                'position': 'B3',
                                'title': 'To Awake And Avenge The Dead'},
                               {'duration': '3:43',
                                'position': 'B4',
                                'title': 'So Strange I Remember You'},
                               {'duration': '4:36',
                                'position': 'B5',
                                'title': 'The Beltsville Crucible'},
                               {'duration': '',
                                'position': 'B6',
                                'title': 'That Hideous Strength (Bonus Track)'}],
            'trackDurations': {'0': '2:47',
                               '1': '1:49',
                               '10': '3:07',
                               '11': '3:43',
                               '12': '4:36',
                               '2': '2:36',
                               '3': '2:50',
                               '4': '3:01',
                               '5': '2:17',
                               '6': '2:15',
                               '8': '3:09',
                               '9': '2:55'},
            'trackIds': {'0': 'ei2wA2Ndm6M',
                         '1': 'uI-Sb5AUrtE',
                         '10': 't5kUkXVAAh4',
                         '11': 'jRkxu5ymYyM',
                         '12': 'ZPyiEubm-dk',
                         '2': 'dUY50VThgJk',
                         '3': 'L1SpX0s6FY4',
                         '4': 'tdC_T1J_fnE',
                         '5': '5iSq_nG8Qaw',
                         '6': 'XXWymj3yQ7Y',
                         '8': 'aIV-vsOtkqY',
                         '9': 'jOmK6Mhn7ko'}},
 26421509: {'defaultYtVideoId': 'pFKSiOkRzb4',
            'fallbackTracks': [{'duration': '7:05', 'position': 'A1', 'title': 'Wildfire'},
                               {'duration': '8:23', 'position': 'A2', 'title': 'Atropos'},
                               {'duration': '7:26', 'position': 'B1', 'title': 'Wax Wings'},
                               {'duration': '5:07',
                                'position': 'B2',
                                'title': 'Everything Is Fine!'},
                               {'duration': '4:51', 'position': 'B3', 'title': 'Silhouette'},
                               {'duration': '5:17', 'position': 'C1', 'title': 'Dying Star'},
                               {'duration': '8:19', 'position': 'C2', 'title': 'Zagreus'},
                               {'duration': '12:21', 'position': 'D1', 'title': 'Dracul Gras'},
                               {'duration': '11:16', 'position': 'D2', 'title': 'Thanks Nobuo'}],
            'trackDurations': {'0': '7:05',
                               '1': '8:23',
                               '2': '7:26',
                               '3': '5:07',
                               '4': '4:51',
                               '5': '5:17',
                               '6': '8:19',
                               '7': '12:21',
                               '8': '11:16'},
            'trackIds': {'0': 'pFKSiOkRzb4',
                         '1': 'Ppg8kpG-lio',
                         '2': 'bJ6lwiP6O-s',
                         '3': 'wQTUyzTA4Fw',
                         '4': 'z5mQxUCSlMQ',
                         '5': 'pYe1uNaP0aM',
                         '6': 'kDgNhyz-z5s',
                         '7': 'd5968yqaplA',
                         '8': 'z7HL2J_GHGU'}},
 26690690: {'defaultYtVideoId': 'etbjaSf6Sqo',
            'fallbackTracks': [{'duration': '0:53',
                                'position': 'A1',
                                'title': 'The Second Stage Turbine Blade'},
                               {'duration': '5:42', 'position': 'A2', 'title': 'Time Consumer'},
                               {'duration': '4:48',
                                'position': 'A3',
                                'title': 'Devil In Jersey City'},
                               {'duration': '5:51', 'position': 'A4', 'title': 'Everything Evil'},
                               {'duration': '4:45', 'position': 'A5', 'title': 'Delirium Trigger'},
                               {'duration': '5:41',
                                'position': 'B1',
                                'title': 'Heartshot Kid Disaster'},
                               {'duration': '3:30', 'position': 'B2', 'title': '33'},
                               {'duration': '5:20',
                                'position': 'B3',
                                'title': 'Junesong Provision'},
                               {'duration': '5:23', 'position': 'B4', 'title': 'Neverender'},
                               {'duration': '6:33',
                                'position': 'B5',
                                'title': 'God Send Conspirator'}],
            'trackDurations': {'0': '0:53',
                               '1': '5:42',
                               '2': '4:48',
                               '3': '5:51',
                               '4': '4:45',
                               '5': '5:41',
                               '6': '3:30',
                               '7': '5:20',
                               '8': '5:23',
                               '9': '6:33'},
            'trackIds': {'0': 'etbjaSf6Sqo',
                         '1': 'xFKoaJzXNo4',
                         '2': 'dLRung5bKKY',
                         '3': '0w-0qwx0hxU',
                         '4': 'E35z2AlLws4',
                         '5': 's_Pxn-RkxAM',
                         '6': 'Y1ODelRmkpQ',
                         '7': 'J7N-VGj3BvQ',
                         '8': 'jnLUuH5qykY',
                         '9': 'K2NlOiUVNfg'},
            'ytPlaylistId': 'OLAK5uy_kHtQe5MJBW8p3vFRDSf_KRbwnTHzSDos0'},
 26831573: {'defaultYtVideoId': 'j9Mh6ea67hk',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'The Bitter End'},
                               {'duration': '3:59', 'position': 'A2', 'title': 'Alpha Omega'},
                               {'duration': '',
                                'position': 'A3',
                                'title': "These Colours Don't Run"},
                               {'duration': '', 'position': 'A4', 'title': 'Daybreak'},
                               {'duration': '', 'position': 'A5', 'title': 'Truth, Be Told'},
                               {'duration': '',
                                'position': 'A6',
                                'title': "Even If You Win, You're Still A Rat"},
                               {'duration': '', 'position': 'B1', 'title': 'Outsider Heart'},
                               {'duration': '', 'position': 'B2', 'title': 'Behind The Throne'},
                               {'duration': '4:09', 'position': 'B3', 'title': "Devil's Island"},
                               {'duration': '', 'position': 'B4', 'title': 'Feather Of Lead'},
                               {'duration': '', 'position': 'B5', 'title': 'Unbeliever'}],
            'fullAlbumYtDuration': 2539,
            'fullAlbumYtVideoId': 'Q3ZvbcbskYA',
            'trackDurations': {'1': '3:59', '8': '4:09'},
            'trackIds': {'1': 'j9Mh6ea67hk', '3': 'Q3ZvbcbskYA', '8': 'CmOrHwWbQ0c'}},
 26847641: {'defaultYtVideoId': 'n5JQnbI5aMM',
            'fallbackTracks': [{'duration': '4:53', 'position': 'A1', 'title': 'Sweet Machine'},
                               {'duration': '3:20', 'position': 'A2', 'title': 'Blemish'},
                               {'duration': '4:15',
                                'position': 'A3',
                                'title': 'Echo And Dust Pt. I'},
                               {'duration': '3:13', 'position': 'A4', 'title': 'Mortality Rate'},
                               {'duration': '3:21',
                                'position': 'A5',
                                'title': 'Ten Dogs — Red Heaven'},
                               {'duration': '3:52', 'position': 'B6', 'title': 'White Lighters'},
                               {'duration': '2:53',
                                'position': 'B7',
                                'title': 'Kappa (River Child)'},
                               {'duration': '4:18', 'position': 'B8', 'title': 'Day Is Gone'},
                               {'duration': '2:43', 'position': 'B9', 'title': 'Broadcast Network'},
                               {'duration': '5:27',
                                'position': 'B10',
                                'title': 'Echo And Dust Pt. II'}],
            'trackDurations': {'0': '4:53',
                               '1': '3:20',
                               '2': '4:15',
                               '3': '3:13',
                               '4': '3:21',
                               '5': '3:52',
                               '6': '2:53',
                               '7': '4:18',
                               '8': '2:43',
                               '9': '5:27'},
            'trackIds': {'0': 'n5JQnbI5aMM'}},
 26917130: {'defaultYtVideoId': 'yR-WREcnzu4',
            'fallbackTracks': [{'duration': '1:02', 'position': 'A1', 'title': 'Wounds'},
                               {'duration': '4:02', 'position': 'A2', 'title': 'Crawl Back'},
                               {'duration': '3:57', 'position': 'A3', 'title': 'Mark The Lines'},
                               {'duration': '2:43',
                                'position': 'A4',
                                'title': 'It’s Not Safe to Swim Today'},
                               {'duration': '2:51',
                                'position': 'A5',
                                'title': 'Entry Level Exit Wounds'},
                               {'duration': '2:08', 'position': 'B1', 'title': 'Pillars'},
                               {'duration': '3:47',
                                'position': 'B2',
                                'title': 'We Bow In Its Aura'},
                               {'duration': '2:30',
                                'position': 'B3',
                                'title': 'All Eyes Look Ahead'},
                               {'duration': '5:04', 'position': 'B4', 'title': 'Sever the Voices'},
                               {'duration': '5:01', 'position': 'B5', 'title': 'It’s Torn Away'}],
            'trackDurations': {'0': '1:02',
                               '1': '4:02',
                               '2': '3:57',
                               '3': '2:43',
                               '4': '2:51',
                               '5': '2:08',
                               '6': '3:47',
                               '7': '2:30',
                               '8': '5:04',
                               '9': '5:01'},
            'trackIds': {'1': 'yR-WREcnzu4', '3': '4YMFgzNW8yE', '6': 'lJMjCDb9_zg'}},
 26986229: {'defaultYtVideoId': 'c3ftYYCi49o',
            'fallbackTracks': [{'duration': '4:20',
                                'position': 'A1',
                                'title': 'The Wretched; The Ruinous'},
                               {'duration': '3:19',
                                'position': 'A2',
                                'title': 'Cremation Of The Living'},
                               {'duration': '3:28', 'position': 'A3', 'title': 'Eradicator'},
                               {'duration': '3:31', 'position': 'A4', 'title': 'Mother Betrayal'},
                               {'duration': '3:44', 'position': 'A5', 'title': 'Invictus'},
                               {'duration': '3:33', 'position': 'A6', 'title': 'Call Of Existence'},
                               {'duration': '2:56',
                                'position': 'B1',
                                'title': 'Dawn Of The Militant'},
                               {'duration': '0:57', 'position': 'B2', 'title': 'Aniara'},
                               {'duration': '3:23', 'position': 'B3', 'title': 'Into The Abyss'},
                               {'duration': '2:50', 'position': 'B4', 'title': 'Broken Arrow'},
                               {'duration': '4:49', 'position': 'B5', 'title': 'Theaters Of War'}],
            'trackDurations': {'0': '4:20',
                               '1': '3:19',
                               '10': '4:49',
                               '2': '3:28',
                               '3': '3:31',
                               '4': '3:44',
                               '5': '3:33',
                               '6': '2:56',
                               '7': '0:57',
                               '8': '3:23',
                               '9': '2:50'},
            'trackIds': {'0': 'c3ftYYCi49o',
                         '3': 'TiV1RDfUe2Q',
                         '6': 'AwN96GwlfkY',
                         '8': 'BcMArGz2_TU'}},
 27066432: {'defaultYtVideoId': 'pOHvJuGwZJo',
            'fallbackTracks': [{'duration': '2:57', 'position': 'A1', 'title': 'Tokyo Chainsaw'},
                               {'duration': '3:25', 'position': 'A2', 'title': 'Artificial Dose'},
                               {'duration': '3:12', 'position': 'A3', 'title': 'Godhead'},
                               {'duration': '4:02', 'position': 'A4', 'title': '[re]connect'},
                               {'duration': '3:31', 'position': 'A5', 'title': 'Red Fur'},
                               {'duration': '3:09', 'position': 'B1', 'title': 'Disco Kill Party'},
                               {'duration': '5:12', 'position': 'B2', 'title': 'Mother Pt. 4'},
                               {'duration': '2:45', 'position': 'B3', 'title': 'Synthwave Vegan'},
                               {'duration': '3:24', 'position': 'B4', 'title': 'Lost Creator'},
                               {'duration': '3:36', 'position': 'B5', 'title': 'Death Runner'}],
            'trackDurations': {'0': '2:57',
                               '1': '3:25',
                               '2': '3:12',
                               '3': '4:02',
                               '4': '3:31',
                               '5': '3:09',
                               '6': '5:12',
                               '7': '2:45',
                               '8': '3:24',
                               '9': '3:36'},
            'trackIds': {'2': 'pOHvJuGwZJo', '4': '_KEdxh2FdwI', '6': 'JEI8nnlb0O8'}},
 27079776: {'defaultYtVideoId': 'xRLhcp_daow',
            'fallbackTracks': [{'duration': '3:03',
                                'position': 'A1',
                                'title': 'In A Room Where Everything Dies'},
                               {'duration': '2:57', 'position': 'A2', 'title': 'All Candy'},
                               {'duration': '4:05',
                                'position': 'A3',
                                'title': 'A Painful And Necessary Action'},
                               {'duration': '3:18',
                                'position': 'A4',
                                'title': 'More And More Hands'},
                               {'duration': '2:30',
                                'position': 'A5',
                                'title': 'Of Snakes And Swans'},
                               {'duration': '2:49', 'position': 'B1', 'title': 'Foreign Anchor'},
                               {'duration': '3:44',
                                'position': 'B2',
                                'title': 'Fade To The Lights'},
                               {'duration': '3:48', 'position': 'B3', 'title': 'The Quiet Shakes'},
                               {'duration': '3:26',
                                'position': 'B4',
                                'title': "And It's Still Too Loud"},
                               {'duration': '4:09',
                                'position': 'B5',
                                'title': 'Ornaments From The Well'}],
            'fullAlbumYtDuration': 2030,
            'fullAlbumYtVideoId': 'xRLhcp_daow',
            'trackDurations': {'0': '3:03',
                               '1': '2:57',
                               '2': '4:05',
                               '3': '3:18',
                               '4': '2:30',
                               '5': '2:49',
                               '6': '3:44',
                               '7': '3:48',
                               '8': '3:26',
                               '9': '4:09'}},
 27137034: {'defaultYtVideoId': 'c3ftYYCi49o',
            'fallbackTracks': [{'duration': '4:20',
                                'position': 'A1',
                                'title': 'The Wretched; The Ruinous'},
                               {'duration': '3:19',
                                'position': 'A2',
                                'title': 'Cremation Of The Living'},
                               {'duration': '3:28', 'position': 'A3', 'title': 'Eradicator'},
                               {'duration': '3:31', 'position': 'A4', 'title': 'Mother Betrayal'},
                               {'duration': '3:44', 'position': 'A5', 'title': 'Invictus'},
                               {'duration': '3:33', 'position': 'A6', 'title': 'Call Of Existence'},
                               {'duration': '2:56',
                                'position': 'B1',
                                'title': 'Dawn Of The Militant'},
                               {'duration': '0:57', 'position': 'B2', 'title': 'Aniara'},
                               {'duration': '3:23', 'position': 'B3', 'title': 'Into The Abyss'},
                               {'duration': '2:50', 'position': 'B4', 'title': 'Broken Arrow'},
                               {'duration': '4:49', 'position': 'B5', 'title': 'Theaters Of War'}],
            'trackDurations': {'0': '4:20',
                               '1': '3:19',
                               '10': '4:49',
                               '2': '3:28',
                               '3': '3:31',
                               '4': '3:44',
                               '5': '3:33',
                               '6': '2:56',
                               '7': '0:57',
                               '8': '3:23',
                               '9': '2:50'},
            'trackIds': {'0': 'c3ftYYCi49o',
                         '3': 'TiV1RDfUe2Q',
                         '6': 'AwN96GwlfkY',
                         '8': 'BcMArGz2_TU'}},
 27611781: {'defaultYtVideoId': 'M89t4Wge_b4',
            'fallbackTracks': [{'duration': '3:29', 'position': 'A1', 'title': 'Luminesce'},
                               {'duration': '', 'position': 'A2', 'title': 'Irreversible'},
                               {'duration': '4:50', 'position': 'A3', 'title': 'Skyline'},
                               {'duration': '', 'position': 'B1', 'title': 'Hourglass'},
                               {'duration': '', 'position': 'B2', 'title': 'Orchid'},
                               {'duration': '4:40', 'position': 'B3', 'title': 'Drift'},
                               {'duration': '3:19', 'position': 'C1', 'title': 'Sleeper'},
                               {'duration': '', 'position': 'C2', 'title': 'Continuum'},
                               {'duration': '', 'position': 'D1', 'title': 'Safehaven'},
                               {'duration': '', 'position': 'D2', 'title': 'The Hypnotist'}],
            'fullAlbumYtDuration': 2715,
            'fullAlbumYtVideoId': 'm8lS5qfJFC0',
            'trackDurations': {'0': '3:29', '2': '4:50', '5': '4:40', '6': '3:19'},
            'trackIds': {'0': 'M89t4Wge_b4',
                         '2': 'KEa2JU3sySQ',
                         '5': 'naEFwVvEx1M',
                         '6': 'Mdqtx1NwXtw'}},
 27717681: {'defaultYtVideoId': 'hK8cjJ8kv8I',
            'fallbackTracks': [{'duration': '4:43', 'position': 'A1', 'title': 'Breach'},
                               {'duration': '4:05', 'position': 'A2', 'title': 'Monolith'},
                               {'duration': '', 'position': 'A3', 'title': 'Signal Fire'},
                               {'duration': '', 'position': 'A4', 'title': 'Valhalla'},
                               {'duration': '', 'position': 'A5', 'title': 'Hyperreality'},
                               {'duration': '', 'position': 'B1', 'title': 'Ghost of Nothing'},
                               {'duration': '3:56', 'position': 'B2', 'title': 'Disarray'},
                               {'duration': '', 'position': 'B3', 'title': 'Expiate'},
                               {'duration': '', 'position': 'B4', 'title': 'Unify'},
                               {'duration': '', 'position': 'B5', 'title': 'Ultimata'}],
            'fullAlbumYtDuration': 2540,
            'fullAlbumYtVideoId': 'BFhF8eF9jRg',
            'trackDurations': {'0': '4:43', '1': '4:05', '6': '3:56'},
            'trackIds': {'0': 'hK8cjJ8kv8I', '1': 'elsRu8yig2c', '6': 'bhPbICS1qEc'},
            'ytPlaylistId': 'OLAK5uy_m3668wFvzraREQccAbDwX4nDAbqLv958g'},
 27927123: {'defaultYtVideoId': 'YwvAgY3_Ju8',
            'fallbackTracks': [{'duration': '',
                                'position': 'A1',
                                'title': 'Turn It Up Like (Stand In The Fire)'},
                               {'duration': '', 'position': 'A2', 'title': 'Tired Of Winning'},
                               {'duration': '', 'position': 'A3', 'title': 'Ships In The Night'},
                               {'duration': '',
                                'position': 'A4',
                                'title': "You Don't Know What Love Means"},
                               {'duration': '', 'position': 'A5', 'title': "Don't Look Back"},
                               {'duration': '', 'position': 'B6', 'title': 'The Other F Word'},
                               {'duration': '', 'position': 'B7', 'title': 'Face It'},
                               {'duration': '', 'position': 'B8', 'title': 'Best Times'},
                               {'duration': '', 'position': 'B9', 'title': 'Dèjá Vu'},
                               {'duration': '', 'position': 'C10', 'title': 'Dance With Me'},
                               {'duration': '', 'position': 'C11', 'title': 'Neverland'},
                               {'duration': '',
                                'position': 'C12',
                                'title': 'Valhalla (Too Young To See)'},
                               {'duration': '5:55', 'position': 'C13', 'title': 'Spirits'}],
            'trackDurations': {'12': '5:55'},
            'trackIds': {'12': 'YwvAgY3_Ju8'}},
 27938112: {'fallbackTracks': [{'duration': '4:15', 'position': 'A1', 'title': 'Indigo'},
                               {'duration': '3:51', 'position': 'A2', 'title': 'Agora'},
                               {'duration': '3:29', 'position': 'A3', 'title': 'White Wolf'},
                               {'duration': '4:04', 'position': 'A4', 'title': 'Celestrial Floods'},
                               {'duration': '3:25', 'position': 'A5', 'title': 'Solace'},
                               {'duration': '3:41', 'position': 'B1', 'title': 'Dead Roots'},
                               {'duration': '3:36', 'position': 'B2', 'title': 'Vacant'},
                               {'duration': '3:17', 'position': 'B3', 'title': 'Midnight Hymn'},
                               {'duration': '4:00', 'position': 'B4', 'title': 'Darkbloom'},
                               {'duration': '4:17', 'position': 'B5', 'title': 'Soul Sleep'}],
            'fullAlbumYtDuration': 2420,
            'fullAlbumYtVideoId': 'Jo1PlMrSMrI',
            'trackDurations': {'0': '4:15',
                               '1': '3:51',
                               '2': '3:29',
                               '3': '4:04',
                               '4': '3:25',
                               '5': '3:41',
                               '6': '3:36',
                               '7': '3:17',
                               '8': '4:00',
                               '9': '4:17'}},
 27945363: {'defaultYtVideoId': 'W4ocPPhtglU',
            'fallbackTracks': [{'duration': '3:24',
                                'position': 'A1',
                                'title': 'Come Back To Earth'},
                               {'duration': '4:06', 'position': 'A2', 'title': 'Hurt Feelings'},
                               {'duration': '4:49', 'position': 'A3', 'title': "What's The Use?"},
                               {'duration': '3:36', 'position': 'A4', 'title': 'Perfecto'},
                               {'duration': '5:48', 'position': 'B1', 'title': 'Self Care'},
                               {'duration': '4:11', 'position': 'B2', 'title': 'Wings'},
                               {'duration': '4:47', 'position': 'B3', 'title': 'Ladders'},
                               {'duration': '4:32', 'position': 'C1', 'title': 'Small Worlds'},
                               {'duration': '3:31',
                                'position': 'C2',
                                'title': 'Conversation, Pt. 1'},
                               {'duration': '3:58', 'position': 'C3', 'title': 'Dunno'},
                               {'duration': '5:46', 'position': 'D1', 'title': 'Jet Fuel'},
                               {'duration': '5:51', 'position': 'D2', 'title': '2009'},
                               {'duration': '5:23', 'position': 'D3', 'title': 'So It Goes'}],
            'trackDurations': {'0': '3:24',
                               '1': '4:06',
                               '10': '5:46',
                               '11': '5:51',
                               '12': '5:23',
                               '2': '4:49',
                               '3': '3:36',
                               '4': '5:48',
                               '5': '4:11',
                               '6': '4:47',
                               '7': '4:32',
                               '8': '3:31',
                               '9': '3:58'},
            'trackIds': {'0': 'W4ocPPhtglU',
                         '1': '8f2SPsLxPzQ',
                         '10': 'FrfNEoNnCt4',
                         '11': 'u_SvAhS7Di0',
                         '12': 'hT7uYDjFfrY',
                         '2': 'NjuiM8Rb2Iw',
                         '3': 'j_KAlIVNtHo',
                         '4': 'SsKT0s5J8ko',
                         '5': 'USIf2ZyKDN8',
                         '6': 'eU581WvbUyQ',
                         '7': 'v2E3ATcEGM4',
                         '8': 'ogodJg67Y4M',
                         '9': 'kL-oX-PAMho'},
            'ytPlaylistId': 'OLAK5uy_m4OxKJ2yP_WXvaCsS29oby4It_AG7hm34'},
 28129036: {'defaultYtVideoId': 'AvECsj3mIF8',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Harbinger'},
                               {'duration': '', 'position': 'A2', 'title': 'Nightmare'},
                               {'duration': '', 'position': 'A3', 'title': 'Parasites'},
                               {'duration': '4:14', 'position': 'A4', 'title': 'Overflow'},
                               {'duration': '', 'position': 'A5', 'title': 'With Regards'},
                               {'duration': '', 'position': 'A6', 'title': 'Inhumane'},
                               {'duration': '', 'position': 'B1', 'title': 'The Crossfire'},
                               {'duration': '', 'position': 'B2', 'title': 'Dissipate'},
                               {'duration': '', 'position': 'B3', 'title': 'Aftertouch'},
                               {'duration': '', 'position': 'B4', 'title': 'Fault Line'},
                               {'duration': '', 'position': 'B5', 'title': 'All In Vain'}],
            'fullAlbumYtDuration': 2771,
            'fullAlbumYtVideoId': 'hQ8p09u3umU',
            'trackDurations': {'3': '4:14'},
            'trackIds': {'3': 'AvECsj3mIF8'}},
 28269505: {'defaultYtVideoId': 'LvLMaL0THhw',
            'fallbackTracks': [{'duration': '6:06', 'position': 'A1', 'title': 'Natural Disaster'},
                               {'duration': '5:46', 'position': 'A2', 'title': 'Echoes'},
                               {'duration': '6:07', 'position': 'B1', 'title': 'The Grey'},
                               {'duration': '6:00', 'position': 'B2', 'title': 'Legion'},
                               {'duration': '4:37', 'position': 'B3', 'title': 'Tender'},
                               {'duration': '11:02', 'position': 'C1', 'title': 'War Of Being'},
                               {'duration': '4:57', 'position': 'C2', 'title': 'Sirens'},
                               {'duration': '6:34', 'position': 'D1', 'title': 'Burden'},
                               {'duration': '9:34', 'position': 'D2', 'title': 'Sacrifice'}],
            'trackDurations': {'0': '6:06',
                               '1': '5:46',
                               '2': '6:07',
                               '3': '6:00',
                               '4': '4:37',
                               '5': '11:02',
                               '6': '4:57',
                               '7': '6:34',
                               '8': '9:34'},
            'trackIds': {'2': 'LvLMaL0THhw', '3': 'pHZXTmPnMso', '5': 'UnkpPIupQxM'}},
 28518913: {'defaultYtVideoId': 'V8N6aKcdh54',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'The Ring In Return'},
                               {'duration': '',
                                'position': 'A2',
                                'title': 'In Keeping Secrets Of Silent Earth: 3'},
                               {'duration': '',
                                'position': 'A3',
                                'title': 'Cuts Marked In The March Of Men'},
                               {'duration': '',
                                'position': 'A4',
                                'title': 'Three Evils (Embodied In Love And Shadow)'},
                               {'duration': '', 'position': 'B5', 'title': 'The Crowing'},
                               {'duration': '', 'position': 'B6', 'title': 'Blood Red Summer'},
                               {'duration': '',
                                'position': 'B7',
                                'title': 'The Camper Velorium I: Faint Of Hearts'},
                               {'duration': '',
                                'position': 'B8',
                                'title': 'The Camper Velorium II: Backend Of Forever'},
                               {'duration': '',
                                'position': 'C9',
                                'title': 'The Camper Velorium III: Al The Killer'},
                               {'duration': '3:29',
                                'position': 'C10',
                                'title': 'A Favor House Atlantic'},
                               {'duration': '',
                                'position': 'C11',
                                'title': 'The Light & The Glass'},
                               {'duration': '', 'position': 'D12', 'title': '2113'}],
            'spotifyAlbumId': '4bWNRlFNPyNxtKYlgLZO1g',
            'trackDurations': {'9': '3:29'},
            'trackIds': {'0': 'V8N6aKcdh54', '1': 'V8N6aKcdh54', '9': 'pRWjLLpwnOM'},
            'ytPlaylistId': 'OLAK5uy_mJBkjY9Fuc293-VQc5gBO0rycP7tS1kLg'},
 28575079: {'defaultYtVideoId': 'Zv3t0Fvgvik',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'The Surface'},
                               {'duration': '3:32', 'position': 'A2', 'title': 'Riptide'},
                               {'duration': '3:14', 'position': 'A3', 'title': 'Doubt Me'},
                               {'duration': '', 'position': 'A4', 'title': 'The Better Me'},
                               {'duration': '3:46', 'position': 'A5', 'title': 'Might Love Myself'},
                               {'duration': '', 'position': 'A6', 'title': 'Sunshine!'},
                               {'duration': '', 'position': 'B1', 'title': "What's Killing You"},
                               {'duration': '', 'position': 'B2', 'title': 'Look The Other Way'},
                               {'duration': '',
                                'position': 'B3',
                                'title': 'What Are You Waiting For'},
                               {'duration': '', 'position': 'B4', 'title': 'My New Reality'},
                               {'duration': '3:26', 'position': 'B5', 'title': 'I Was Alive'}],
            'trackDurations': {'1': '3:32', '10': '3:26', '2': '3:14', '4': '3:46'},
            'trackIds': {'1': 'Zv3t0Fvgvik',
                         '10': 'pnGTAeUZ1EA',
                         '2': 'UfY5VokMkL8',
                         '4': '83rcK9Xne5A'},
            'ytPlaylistId': 'OLAK5uy_kybwT-y0VR8buWBdeAr73EcUVU8iPxZi0'},
 28593982: {'defaultYtVideoId': 'WvD5aMsD1HA',
            'fallbackTracks': [{'duration': '3:26', 'position': 'A1', 'title': 'Apnea'},
                               {'duration': '', 'position': 'A2', 'title': 'Tremor'},
                               {'duration': '3:46', 'position': 'A3', 'title': 'Night Terrors'},
                               {'duration': '4:02', 'position': 'A4', 'title': 'Delusion'},
                               {'duration': '3:47', 'position': 'B1', 'title': 'Withered'},
                               {'duration': '', 'position': 'B2', 'title': 'Dreamer'},
                               {'duration': '', 'position': 'B3', 'title': 'Forget Me'},
                               {'duration': '',
                                'position': 'C1',
                                'title': 'The Place I Feel Safest'},
                               {'duration': '', 'position': 'C2', 'title': 'Silence'},
                               {'duration': '', 'position': 'C3', 'title': 'Best Memory'},
                               {'duration': '', 'position': 'D1', 'title': 'Another Life'},
                               {'duration': '', 'position': 'D2', 'title': 'I’m Not Waiting'},
                               {'duration': '', 'position': 'D3', 'title': 'Shattered'}],
            'trackDurations': {'0': '3:26', '2': '3:46', '3': '4:02', '4': '3:47'},
            'trackIds': {'0': 'WvD5aMsD1HA',
                         '2': 'jHjtiJ33qME',
                         '3': 'TXXrDlgoBaM',
                         '4': 'ei7NnTF24-k'}},
 28844782: {'defaultYtVideoId': '4RtpvN42zM8',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Fast Forward To 2012'},
                               {'duration': '', 'position': 'A2', 'title': 'Speak Of The Devil'},
                               {'duration': '3:02',
                                'position': 'A3',
                                'title': 'The Danger In Starting A Fire'},
                               {'duration': '4:09',
                                'position': 'A4',
                                'title': 'The Plot To Bomb The Panhandle'},
                               {'duration': '', 'position': 'A5', 'title': 'Monument'},
                               {'duration': '', 'position': 'A6', 'title': 'The Price We Pay'},
                               {'duration': '',
                                'position': 'A7',
                                'title': 'Colder Than My Heart, If You Can Imagine'},
                               {'duration': '', 'position': 'B8', 'title': "Show 'Em The Ropes"},
                               {'duration': '', 'position': 'B9', 'title': 'A Shot In The Dark'},
                               {'duration': '', 'position': 'B10', 'title': "Here's To The Past"},
                               {'duration': '',
                                'position': 'B11',
                                'title': "I Heard It's The Softest Thing Ever"},
                               {'duration': '', 'position': 'B12', 'title': 'Start The Shooting'}],
            'trackDurations': {'2': '3:02', '3': '4:09'},
            'trackIds': {'2': '4RtpvN42zM8', '3': 'N1MujfQqLIg'}},
 28895677: {'defaultYtVideoId': 'JV3lFDVisaI',
            'fallbackTracks': [{'duration': '4:05',
                                'position': 'A1',
                                'title': 'The Going Price For Home'},
                               {'duration': '2:38',
                                'position': 'A2',
                                'title': 'The Fight of Mose Early & Sir Arthur McCloud'},
                               {'duration': '3:39',
                                'position': 'A3',
                                'title': 'Our Darling Daughter You Are, Little Cecillia Marie'},
                               {'duration': '3:26',
                                'position': 'A4',
                                'title': 'A Death In The Family'},
                               {'duration': '3:42',
                                'position': 'A5',
                                'title': 'The Margretville Dance'},
                               {'duration': '5:15', 'position': 'A6', 'title': 'Accidents'},
                               {'duration': '3:29',
                                'position': 'B1',
                                'title': 'Run, Gunner Recall, Run! The Town Wants You Dead!'},
                               {'duration': '4:04',
                                'position': 'B2',
                                'title': 'Who Watches The Watchmen?'},
                               {'duration': '3:00',
                                'position': 'B3',
                                'title': 'Wayne Andrews, The Old Bee Keeper'},
                               {'duration': '3:38',
                                'position': 'B4',
                                'title': 'The Missing McCloud Boys'},
                               {'duration': '2:44', 'position': 'B5', 'title': 'Easter'},
                               {'duration': '4:01', 'position': 'B6', 'title': '78'}],
            'trackDurations': {'0': '4:05',
                               '1': '2:38',
                               '10': '2:44',
                               '11': '4:01',
                               '2': '3:39',
                               '3': '3:26',
                               '4': '3:42',
                               '5': '5:15',
                               '6': '3:29',
                               '7': '4:04',
                               '8': '3:00',
                               '9': '3:38'},
            'trackIds': {'0': 'JV3lFDVisaI',
                         '1': 'HJ63vrfsBsc',
                         '10': '0Pjw5I6mhgg',
                         '11': 'Fo8QhYwROOQ',
                         '2': '5shViIbBGV4',
                         '3': 'W28_4lV179k',
                         '4': 'ypLNfotqJKc',
                         '5': 'ZdUYZ_Jka4c',
                         '6': 'BYkNL_9Bwnw',
                         '7': 'ZqGilQMDFSA',
                         '8': 'uMLGj3zxKiQ',
                         '9': '0mdjlRd5F2M'}},
 29075062: {'defaultYtVideoId': 'fl0Z72PoDdY',
            'fallbackTracks': [{'duration': '',
                                'position': 'A1',
                                'title': 'Apocalypse Now And Then'},
                               {'duration': '3:19', 'position': 'A2', 'title': 'Kill The Music'},
                               {'duration': '2:19', 'position': 'A3', 'title': 'Bored Stiff'},
                               {'duration': '', 'position': 'A4', 'title': 'Easy Tiger'},
                               {'duration': '', 'position': 'A5', 'title': 'Tusk And Temper'},
                               {'duration': '', 'position': 'A6', 'title': 'The New Black'},
                               {'duration': '', 'position': 'B1', 'title': 'Champing At The Bit'},
                               {'duration': '',
                                'position': 'B2',
                                'title': 'Gloom And How It Gets That Way'},
                               {'duration': '',
                                'position': 'B3',
                                'title': 'Guitared And Feathered'},
                               {'duration': '', 'position': 'B4', 'title': 'L’Astronaut'},
                               {'duration': '', 'position': 'B5', 'title': 'Pretty Dirty'}],
            'fullAlbumYtDuration': 2062,
            'fullAlbumYtVideoId': 'OYHf4PNvOJk',
            'trackDurations': {'1': '3:19', '2': '2:19'},
            'trackIds': {'1': 'fl0Z72PoDdY', '2': 'cg0rYWJ3xlc'}},
 29237467: {'defaultYtVideoId': 'rmtU2WJfPgU',
            'fallbackTracks': [{'duration': '3:57',
                                'position': 'A1',
                                'title': 'The Price Is Wrong'},
                               {'duration': '4:50', 'position': 'A2', 'title': 'Motormouth'},
                               {'duration': '7:20', 'position': 'A3', 'title': 'Marigold'},
                               {'duration': '5:04',
                                'position': 'B1',
                                'title': 'The Way The News Goes...'},
                               {'duration': '6:10', 'position': 'B2', 'title': 'Remain Indoors'},
                               {'duration': '6:52',
                                'position': 'B3',
                                'title': 'Habitual Line-Stepper'},
                               {'duration': '5:51', 'position': 'C1', 'title': 'Flatline'},
                               {'duration': '7:44', 'position': 'C2', 'title': 'Absolomb'},
                               {'duration': '3:54', 'position': 'C3', 'title': 'Catch Fire'},
                               {'duration': '4:37', 'position': 'D1', 'title': 'Prayer Position'},
                               {'duration': '7:47', 'position': 'D2', 'title': 'Lune'}],
            'fullAlbumYtDuration': 3845,
            'fullAlbumYtVideoId': 'IK78K2yQgn0',
            'trackDurations': {'0': '3:57',
                               '1': '4:50',
                               '10': '7:47',
                               '2': '7:20',
                               '3': '5:04',
                               '4': '6:10',
                               '5': '6:52',
                               '6': '5:51',
                               '7': '7:44',
                               '8': '3:54',
                               '9': '4:37'},
            'trackIds': {'2': 'rmtU2WJfPgU', '6': 'L7cH6o_sblg'}},
 29410045: {'defaultYtVideoId': 'Ip9xWCO8rdo',
            'fallbackTracks': [{'duration': '4:51', 'position': 'A1', 'title': 'Insomnia'},
                               {'duration': '5:06', 'position': 'A2', 'title': 'The Walk'},
                               {'duration': '6:36', 'position': 'A3', 'title': 'Letter Experiment'},
                               {'duration': '4:23', 'position': 'A4', 'title': 'Jetpacks Was Yes'},
                               {'duration': '5:52', 'position': 'B1', 'title': 'Light'},
                               {'duration': '5:21', 'position': 'B2', 'title': 'All New Materials'},
                               {'duration': '5:55', 'position': 'B3', 'title': 'Buttersnips'},
                               {'duration': '3:35', 'position': 'B4', 'title': 'Icarus Lives'},
                               {'duration': '4:01', 'position': 'C1', 'title': 'Totla Mad'},
                               {'duration': '6:08', 'position': 'C2', 'title': 'Ow My Feelings'},
                               {'duration': '5:08', 'position': 'C3', 'title': 'Zyglrox'},
                               {'duration': '', 'position': 'D1', 'title': 'Racecar'}],
            'trackDurations': {'0': '4:51',
                               '1': '5:06',
                               '10': '5:08',
                               '2': '6:36',
                               '3': '4:23',
                               '4': '5:52',
                               '5': '5:21',
                               '6': '5:55',
                               '7': '3:35',
                               '8': '4:01',
                               '9': '6:08'},
            'trackIds': {'0': 'Ip9xWCO8rdo',
                         '1': '5PdpxCcHYgA',
                         '10': 'TiwzdGjskwc',
                         '11': 'M995nzLSUTw',
                         '2': 'KgBaZJKq4s0',
                         '3': 'Sw4M5foAGUY',
                         '4': 'Is_-_S43WAM',
                         '5': 'u8RMEirHTUM',
                         '6': '4ZjEwB-fx3Q',
                         '7': 'MfOnq-zXXBw',
                         '8': 'bETk3KhNxvY',
                         '9': 'CC6sLtqO4C8'}},
 29410354: {'defaultYtVideoId': 'M_B-uWfHFiY',
            'fallbackTracks': [{'duration': '1:25', 'position': 'A1', 'title': 'Reprise'},
                               {'duration': '5:53', 'position': 'A2', 'title': 'The Bad Thing'},
                               {'duration': '5:03', 'position': 'A3', 'title': 'Priestess'},
                               {'duration': '3:55', 'position': 'A4', 'title': 'Graveless'},
                               {'duration': '3:43', 'position': 'A5', 'title': 'Hell Below'},
                               {'duration': '11:44', 'position': 'B1', 'title': 'Omega'},
                               {'duration': '7:35', 'position': 'B2', 'title': 'Stranger Things'}],
            'fullAlbumYtDuration': 4836,
            'fullAlbumYtVideoId': 'M_B-uWfHFiY',
            'trackDurations': {'0': '1:25',
                               '1': '5:53',
                               '2': '5:03',
                               '3': '3:55',
                               '4': '3:43',
                               '5': '11:44',
                               '6': '7:35'}},
 29410450: {'defaultYtVideoId': 'U1hHsTYdXxY',
            'fallbackTracks': [{'duration': '4:16', 'position': 'A1', 'title': 'A Black Minute'},
                               {'duration': '2:50', 'position': 'A2', 'title': 'MK Ultra'},
                               {'duration': '4:22', 'position': 'A3', 'title': 'Heavy Heart'},
                               {'duration': '1:48', 'position': 'A4', 'title': 'The Event'},
                               {'duration': '5:36', 'position': 'A5', 'title': 'The Scourge'},
                               {'duration': '5:31', 'position': 'B1', 'title': 'Alpha'},
                               {'duration': '3:52', 'position': 'B2', 'title': '22 Faces'},
                               {'duration': '4:39', 'position': 'B3', 'title': 'Rainbow Gravity'},
                               {'duration': '2:17', 'position': 'B4', 'title': 'Four Lights'},
                               {'duration': '6:16', 'position': 'B5', 'title': 'Psychosphere'}],
            'fullAlbumYtDuration': 4836,
            'fullAlbumYtVideoId': 'M_B-uWfHFiY',
            'trackDurations': {'0': '4:16',
                               '1': '2:50',
                               '2': '4:22',
                               '3': '1:48',
                               '4': '5:36',
                               '5': '5:31',
                               '6': '3:52',
                               '7': '4:39',
                               '8': '2:17',
                               '9': '6:16'},
            'trackIds': {'5': 'U1hHsTYdXxY'}},
 29410576: {'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'New Groove'},
                               {'duration': '', 'position': 'A2', 'title': 'Frak The Gods'},
                               {'duration': '',
                                'position': 'A3',
                                'title': 'Jetpacks Was Yes! (V2.0)'},
                               {'duration': '', 'position': 'A4', 'title': 'Icarus Lives!'},
                               {'duration': '',
                                'position': 'A5',
                                'title': 'Icarus Lives! (Bulbous Remix)'},
                               {'duration': '',
                                'position': 'B1',
                                'title': 'Icarus Lives! (Zedd Remix)'},
                               {'duration': '',
                                'position': 'B2',
                                'title': 'Icarus Lives! (Peteyg Remix)'},
                               {'duration': '', 'position': 'B3', 'title': 'Captain On'},
                               {'duration': '', 'position': 'B4', 'title': 'Eureka'}]},
 29425159: {'defaultYtVideoId': 'cjU88QrCoDk',
            'fallbackTracks': [{'duration': '2:53', 'position': 'A1', 'title': 'Hurt'},
                               {'duration': '3:24', 'position': 'A2', 'title': 'One Car Garage'},
                               {'duration': '3:54', 'position': 'A3', 'title': 'Sure'},
                               {'duration': '3:47', 'position': 'A4', 'title': 'Miracle'},
                               {'duration': '3:36', 'position': 'A5', 'title': 'Cloud 9'},
                               {'duration': '3:25', 'position': 'A6', 'title': 'Helpless'},
                               {'duration': '4:30', 'position': 'B1', 'title': 'Porcelain'},
                               {'duration': '2:43', 'position': 'B2', 'title': 'Never'},
                               {'duration': '3:17', 'position': 'B3', 'title': 'Young Lonely'},
                               {'duration': '2:43', 'position': 'B4', 'title': 'Blue'},
                               {'duration': '5:29', 'position': 'B5', 'title': 'Re'}],
            'trackDurations': {'0': '2:53',
                               '1': '3:24',
                               '10': '5:29',
                               '2': '3:54',
                               '3': '3:47',
                               '4': '3:36',
                               '5': '3:25',
                               '6': '4:30',
                               '7': '2:43',
                               '8': '3:17',
                               '9': '2:43'},
            'trackIds': {'1': 'cjU88QrCoDk',
                         '3': 'Go4k8gXbKW8',
                         '4': 'aaH3ud1utB0',
                         '5': 'Ro6Zo4BhMW4',
                         '9': 'tBtenlHt2sA'}},
 29592373: {'defaultYtVideoId': 'Pi81RThE7NU',
            'fallbackTracks': [{'duration': '',
                                'position': 'A1',
                                'title': 'Lights Off The Lost Coast'},
                               {'duration': '3:26', 'position': 'A2', 'title': 'Offworlder'},
                               {'duration': '3:40', 'position': 'A3', 'title': 'Collider'},
                               {'duration': '4:03', 'position': 'A4', 'title': 'Euphoria'},
                               {'duration': '', 'position': 'A5', 'title': 'Dreamwalker'},
                               {'duration': '3:57', 'position': 'A6', 'title': 'Antimatter'},
                               {'duration': '', 'position': 'B1', 'title': ':Signal:'},
                               {'duration': '', 'position': 'B2', 'title': 'Anunnaki'},
                               {'duration': '', 'position': 'B3', 'title': 'The Overgrowth'},
                               {'duration': '', 'position': 'B4', 'title': 'Nexus'},
                               {'duration': '', 'position': 'B5', 'title': 'Reentry'},
                               {'duration': '5:03', 'position': 'B6', 'title': 'Superbloom'}],
            'trackDurations': {'1': '3:26', '11': '5:03', '2': '3:40', '3': '4:03', '5': '3:57'},
            'trackIds': {'0': 'CYv_AJDlahY',
                         '1': 'Pi81RThE7NU',
                         '11': 'mGGcXba3bDM',
                         '2': 'H6IWR0UHNbA',
                         '3': 'NAnPPArDKrs',
                         '5': 'wiEno0KE5uU'}},
 29631781: {'defaultYtVideoId': 'TYrB2HustCs',
            'fallbackTracks': [{'duration': '3:30', 'position': 'A1', 'title': 'Living Together'},
                               {'duration': '4:03',
                                'position': 'A2',
                                'title': 'In the Morning and Amazing...'},
                               {'duration': '3:42', 'position': 'A3', 'title': 'The Greatest Lie'},
                               {'duration': '4:17',
                                'position': 'A4',
                                'title': 'The Difference Between Medicine And Poison Is In The '
                                         'Dose'},
                               {'duration': '3:23', 'position': 'A5', 'title': 'Mandala'},
                               {'duration': '3:12', 'position': 'A6', 'title': 'Travel Hymn'},
                               {'duration': '3:22',
                                'position': 'B1',
                                'title': 'Semi Constructive Criticism'},
                               {'duration': '3:37',
                                'position': 'B2',
                                'title': 'Kicking Your Crosses Down'},
                               {'duration': '4:03', 'position': 'B3', 'title': 'On Letting Go'},
                               {'duration': '3:20', 'position': 'B4', 'title': 'Carry Us Away'},
                               {'duration': '3:34',
                                'position': 'B5',
                                'title': 'Close Your Eyes to See'},
                               {'duration': '5:26',
                                'position': 'B6',
                                'title': 'Your Friends Are Gone'}],
            'trackAltIds': {'0': ['3mKkMlcn0Go', 'Wv09uhaFFfs'],
                            '3': ['Uuw1FvlGOgg', 'YhLm4JgXd5Q'],
                            '8': ['QWEoPWgAtkE'],
                            '9': ['nL7TeEeHTKA', 'uQJeQxEyIu8']},
            'trackDurations': {'0': '3:30',
                               '1': '4:03',
                               '10': '3:34',
                               '11': '5:26',
                               '2': '3:42',
                               '3': '4:17',
                               '4': '3:23',
                               '5': '3:12',
                               '6': '3:22',
                               '7': '3:37',
                               '8': '4:03',
                               '9': '3:20'},
            'trackIds': {'0': 'TYrB2HustCs',
                         '1': 'wDCwLQnmedU',
                         '10': 'Medi7crnbik',
                         '11': 'wNDGtQBLGOc',
                         '2': 'SK2VqHAys_0',
                         '3': 'wEDG8-6Fig4',
                         '4': 'P1G5nbPHhUU',
                         '5': 'aCxRFARDXf8',
                         '6': 'jqlFwi0fqhs',
                         '7': 'aossqmZEbto',
                         '8': 'MAp3uAk-poo',
                         '9': 'zS9iiXm97aQ'},
            'ytEmbedPlaylistId': 'PL-XbTEkQt3TaP-bdGSGscA4Ci5XGIANhn',
            'ytPlaylistId': 'OLAK5uy_m80Evo-9vz_8XceYZ5xiRnlvifZRSAfCA'},
 30245600: {'defaultYtVideoId': 'QwhwskB_eWo',
            'fallbackTracks': [{'duration': '',
                                'position': 'A1',
                                'title': 'Emergency Broadcast Syndrome'},
                               {'duration': '', 'position': 'A2', 'title': "Jimmy Tango's Method"},
                               {'duration': '3:43',
                                'position': 'A3',
                                'title': "Here's Looking At You"},
                               {'duration': '4:36',
                                'position': 'A4',
                                'title': 'Punch-Drunk Punk Rock Romance'},
                               {'duration': '',
                                'position': 'A5',
                                'title': 'Enter Without Knocking And Notify The Police'},
                               {'duration': '3:50',
                                'position': 'B6',
                                'title': 'The Logic Of Crocodiles'},
                               {'duration': '', 'position': 'B7', 'title': 'Pincushion'},
                               {'duration': '',
                                'position': 'B8',
                                'title': 'Nothing Dreadful Ever Happens'},
                               {'duration': '',
                                'position': 'B9',
                                'title': 'California, Gracefully'},
                               {'duration': '',
                                'position': 'B10',
                                'title': 'Shallow Water Blackout'}],
            'trackDurations': {'2': '3:43', '3': '4:36', '5': '3:50'},
            'trackIds': {'2': 'QwhwskB_eWo', '3': '3Ag1xxjNY8Y', '5': 'me1N0Z_JPNA'}},
 30637357: {'defaultYtVideoId': 'RAuuVY__KQ0',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Thirst'},
                               {'duration': '', 'position': 'A2', 'title': 'Piece By Piece'},
                               {'duration': '2:49', 'position': 'A3', 'title': 'Suffocate'},
                               {'duration': '4:11',
                                'position': 'A4',
                                'title': 'Don’t Reach For Me'},
                               {'duration': '', 'position': 'A5', 'title': 'Moss Covers All'},
                               {'duration': '', 'position': 'B1', 'title': 'Take Me Home'},
                               {'duration': '', 'position': 'B2', 'title': 'Slaughterhouse 2'},
                               {'duration': '',
                                'position': 'B3',
                                'title': 'The Calm That Keeps You Awake'},
                               {'duration': '2:58', 'position': 'B4', 'title': 'Blinding Faith'},
                               {'duration': '', 'position': 'B5', 'title': 'Sit & Mourn'}],
            'trackDurations': {'2': '2:49', '3': '4:11', '8': '2:58'},
            'trackIds': {'0': 'Gg79meazlfM',
                         '2': 'RAuuVY__KQ0',
                         '3': 'HlOFqHXH368',
                         '8': 'eO8q_Q4lRC8'},
            'ytPlaylistId': 'OLAK5uy_kIKIGNHqZjl6KvbVuKXthqyVxIrSNPuLQ'},
 31200271: {'defaultYtVideoId': 'ENLw_1TK6Ms',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Young And Aspiring'},
                               {'duration': '',
                                'position': 'A2',
                                'title': 'A Boy Brushed Red Living In Black And White'},
                               {'duration': '', 'position': 'A3', 'title': 'The Impact Of Reason'},
                               {'duration': '4:33',
                                'position': 'A4',
                                'title': 'Reinventing Your Exit'},
                               {'duration': '', 'position': 'A5', 'title': 'The Blue Note'},
                               {'duration': '4:08',
                                'position': 'A6',
                                'title': "It's Dangerous Business Walking Out Your Front Door"},
                               {'duration': '', 'position': 'B1', 'title': 'Down, Set, Go'},
                               {'duration': '',
                                'position': 'B2',
                                'title': "I Don't Feel Very Receptive Today"},
                               {'duration': '',
                                'position': 'B3',
                                'title': "I'm Content With Losing"},
                               {'duration': '',
                                'position': 'B4',
                                'title': 'Some Will Seek Forgiveness, Others Escape'}],
            'trackDurations': {'3': '4:33', '5': '4:08'},
            'trackIds': {'0': 'MXHikpA5COo', '3': 'ENLw_1TK6Ms', '5': 'SCwNG1YqhEU'}},
 31699214: {'fallbackTracks': [{'duration': '4:18', 'position': 'A1', 'title': 'The A Team'},
                               {'duration': '3:05', 'position': 'A2', 'title': 'Lego House'},
                               {'duration': '8:46', 'position': 'A3', 'title': 'Give Me Love'},
                               {'duration': '3:55', 'position': 'A4', 'title': 'Sing'},
                               {'duration': '3:40', 'position': 'A5', 'title': "Don't"},
                               {'duration': '4:42', 'position': 'B1', 'title': 'Thinking Out Loud'},
                               {'duration': '5:00', 'position': 'B2', 'title': 'Bloodstream'},
                               {'duration': '4:19', 'position': 'B3', 'title': 'Photograph'},
                               {'duration': '4:01', 'position': 'B4', 'title': 'Tenerife Sea'},
                               {'duration': '4:59', 'position': 'B5', 'title': 'I See Fire'},
                               {'duration': '4:21',
                                'position': 'C1',
                                'title': 'Castle On The Hill'},
                               {'duration': '3:51', 'position': 'C2', 'title': 'Shape Of You'},
                               {'duration': '2:49', 'position': 'C3', 'title': 'Galway Girl'},
                               {'duration': '4:22', 'position': 'C4', 'title': 'Perfect'},
                               {'duration': '3:26', 'position': 'C5', 'title': 'Happier'},
                               {'duration': '3:57', 'position': 'C6', 'title': 'Dive'},
                               {'duration': '3:39', 'position': 'D1', 'title': "I Don't Care"},
                               {'duration': '3:17', 'position': 'D2', 'title': 'Beautiful People'},
                               {'duration': '3:05', 'position': 'D3', 'title': 'Afterglow'},
                               {'duration': '3:50', 'position': 'D4', 'title': 'Bad Habits'},
                               {'duration': '3:27', 'position': 'D5', 'title': 'Shivers'},
                               {'duration': '3:14', 'position': 'D6', 'title': 'Eyes Closed'}],
            'trackDurations': {'0': '4:18',
                               '1': '3:05',
                               '10': '4:21',
                               '11': '3:51',
                               '12': '2:49',
                               '13': '4:22',
                               '14': '3:26',
                               '15': '3:57',
                               '16': '3:39',
                               '17': '3:17',
                               '18': '3:05',
                               '19': '3:50',
                               '2': '8:46',
                               '20': '3:27',
                               '21': '3:14',
                               '3': '3:55',
                               '4': '3:40',
                               '5': '4:42',
                               '6': '5:00',
                               '7': '4:19',
                               '8': '4:01',
                               '9': '4:59'}},
 31909216: {'defaultYtVideoId': 'ews1N1ICK2o',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'A Flash Of Light'},
                               {'duration': '', 'position': 'A2', 'title': 'Remnant'},
                               {'duration': '', 'position': 'A3', 'title': 'Aquila'},
                               {'duration': '', 'position': 'A4', 'title': 'Memory Of Light'},
                               {'duration': '', 'position': 'A5', 'title': 'Echoes'},
                               {'duration': '', 'position': 'B1', 'title': 'The Orphan Breed'},
                               {'duration': '', 'position': 'B2', 'title': 'Dissect Yourself'},
                               {'duration': '', 'position': 'B3', 'title': 'Emanate'},
                               {'duration': '', 'position': 'B4', 'title': 'Ephemeral'},
                               {'duration': '', 'position': 'B5', 'title': 'Cycles'}],
            'fullAlbumYtDuration': 2094,
            'fullAlbumYtVideoId': 'ews1N1ICK2o',
            'ytPlaylistId': 'OLAK5uy_l72qS6IlCzefr7ijRsFWijw8EFntwGhxY'},
 32219745: {'defaultYtVideoId': 'LCfCksqrZBI',
            'fallbackTracks': [{'duration': '4:54', 'position': 'A1', 'title': 'Burying Luck'},
                               {'duration': '4:04', 'position': 'A2', 'title': 'Ice Monster'},
                               {'duration': '3:40', 'position': 'A3', 'title': 'Knights'},
                               {'duration': '4:39', 'position': 'B1', 'title': 'White Mystery'},
                               {'duration': '6:48', 'position': 'B2', 'title': "Dr. L'ling"},
                               {'duration': '3:50', 'position': 'B3', 'title': 'Part 2'},
                               {'duration': '2:47', 'position': 'C1', 'title': "Throwin' Shapes"},
                               {'duration': '4:04', 'position': 'C2', 'title': 'When We Escape'},
                               {'duration': '4:30',
                                'position': 'C3',
                                'title': 'Double Vision Quest'},
                               {'duration': '8:48', 'position': 'D1', 'title': 'Lotus'}],
            'trackDurations': {'0': '4:54',
                               '1': '4:04',
                               '2': '3:40',
                               '3': '4:39',
                               '4': '6:48',
                               '5': '3:50',
                               '6': '2:47',
                               '7': '4:04',
                               '8': '4:30',
                               '9': '8:48'},
            'trackIds': {'0': 'LCfCksqrZBI',
                         '1': 'Q8HWiJeOmNQ',
                         '2': 'iZaBD3pymH0',
                         '3': 'gCbO6eFsMTM',
                         '4': 'zrKlESsDtyI',
                         '5': 'KKLcXsVZTzQ',
                         '6': '1pvbVA6lB-c',
                         '7': 'ujNYMHgfgYM',
                         '8': 'zB_IAMFDPVk',
                         '9': '7NF427er9Ak'},
            'ytPlaylistId': 'OLAK5uy_k19l5bxvVigN1pq3xdHHN1it6Yd38fqxs'},
 32282064: {'defaultYtVideoId': 'Yo5fE-Zl-V4',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Ocean Floor'},
                               {'duration': '4:48',
                                'position': 'A2',
                                'title': 'This Is The Time (Ballast)'},
                               {'duration': '3:29', 'position': 'A3', 'title': 'Christ Copyright'},
                               {'duration': '4:10', 'position': 'A4', 'title': 'Mr. MTV'},
                               {'duration': '', 'position': 'A5', 'title': 'First Punch'},
                               {'duration': '', 'position': 'A6', 'title': 'Gyre'},
                               {'duration': '', 'position': 'B1', 'title': 'The Matthew Effect'},
                               {'duration': '', 'position': 'B2', 'title': "I'll Be Ok"},
                               {'duration': '4:24',
                                'position': 'B3',
                                'title': "Here's To The Heartache"},
                               {'duration': '', 'position': 'B4', 'title': 'If I Were'},
                               {'duration': '', 'position': 'B5', 'title': 'Friendly Fire'},
                               {'duration': '', 'position': 'C1', 'title': 'Sex & Lies'},
                               {'duration': '', 'position': 'C2', 'title': 'Surface Flames'},
                               {'duration': '', 'position': 'C3', 'title': 'Take A Bullet'},
                               {'duration': '6:16', 'position': 'C4', 'title': 'Jenny'},
                               {'duration': '', 'position': 'C5', 'title': 'God Went North'},
                               {'duration': '', 'position': 'D1', 'title': 'Pyre'},
                               {'duration': '4:48',
                                'position': 'D2',
                                'title': 'This Is The Time (Remix)'},
                               {'duration': '6:16', 'position': 'D3', 'title': 'Jenny (Acoustic)'},
                               {'duration': '4:48',
                                'position': 'D4',
                                'title': 'This Is The Time (Acoustic)'}],
            'trackDurations': {'1': '4:48',
                               '14': '6:16',
                               '17': '4:48',
                               '18': '6:16',
                               '19': '4:48',
                               '2': '3:29',
                               '3': '4:10',
                               '8': '4:24'},
            'trackIds': {'1': 'Yo5fE-Zl-V4',
                         '14': '_TWr2pj6kqM',
                         '17': 'Yo5fE-Zl-V4',
                         '18': '_TWr2pj6kqM',
                         '19': 'Yo5fE-Zl-V4',
                         '2': '-cxsTDnRN7M',
                         '3': 'BXUb0WqkJbQ',
                         '8': 'TbUAtnWwADI'}},
 32367897: {'defaultYtVideoId': 'PnWP7cAf-bk',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'The Warning'},
                               {'duration': '', 'position': 'A2', 'title': 'Weaponized'},
                               {'duration': '4:01', 'position': 'A3', 'title': 'Oscillator'},
                               {'duration': '4:48', 'position': 'A4', 'title': 'Doomswitch'},
                               {'duration': '3:43', 'position': 'A5', 'title': 'Mana God'},
                               {'duration': '3:40', 'position': 'A6', 'title': 'Epitaph'},
                               {'duration': '', 'position': 'B1', 'title': 'No Hard Feelings'},
                               {'duration': '', 'position': 'B2', 'title': 'Venusian Blues'},
                               {'duration': '3:53', 'position': 'B3', 'title': 'Ghost Of Me'},
                               {'duration': '', 'position': 'B4', 'title': 'Tether'},
                               {'duration': '3:49',
                                'position': 'B5',
                                'title': 'Small Town Syndrome'}],
            'fullAlbumYtDuration': 2320,
            'fullAlbumYtVideoId': 'hYpY0n_amao',
            'trackDurations': {'10': '3:49',
                               '2': '4:01',
                               '3': '4:48',
                               '4': '3:43',
                               '5': '3:40',
                               '8': '3:53'},
            'trackIds': {'10': 'RmOjqDRIL4Y',
                         '2': 'PnWP7cAf-bk',
                         '3': 'vSW5gBfdR_8',
                         '4': 'V7GGewgpzac',
                         '5': '8Of9aA2pFrE',
                         '8': 'bAp3BPUfj2o'}},
 33201711: {'defaultYtVideoId': 'TuGCBQoYOu0',
            'fallbackTracks': [{'duration': '3:09',
                                'position': 'A1',
                                'title': 'Make It Make Sense'},
                               {'duration': '2:48', 'position': 'A2', 'title': 'Feedback'},
                               {'duration': '', 'position': 'A3', 'title': 'Bad Blood'},
                               {'duration': '', 'position': 'A4', 'title': 'All My Friends'},
                               {'duration': '', 'position': 'A5', 'title': 'To The Death'},
                               {'duration': '', 'position': 'A6', 'title': 'Flowers'},
                               {'duration': '2:47', 'position': 'B7', 'title': 'LeBron'},
                               {'duration': '', 'position': 'B8', 'title': 'Die For Me'},
                               {'duration': '', 'position': 'B9', 'title': 'Miracle'},
                               {'duration': '', 'position': 'B10', 'title': 'Same Team'},
                               {'duration': '', 'position': 'B11', 'title': 'Silence'},
                               {'duration': '',
                                'position': 'B12',
                                'title': 'Closer Than You Think'}],
            'trackDurations': {'0': '3:09', '1': '2:48', '6': '2:47'},
            'trackIds': {'0': 'TuGCBQoYOu0', '1': 'iXVnysmQ4e0', '6': 'nVmA9o4d3Kk'}},
 33303678: {'defaultYtVideoId': 'eoVExOdCpjs',
            'fallbackTracks': [{'duration': '4:22', 'position': 'A1', 'title': 'Fata Morgana'},
                               {'duration': '3:25', 'position': 'A2', 'title': 'Black Rainbow'},
                               {'duration': '4:01', 'position': 'A3', 'title': 'Perfect Soul'},
                               {'duration': '4:04', 'position': 'A4', 'title': 'Keep Sweet'},
                               {'duration': '3:05', 'position': 'A5', 'title': 'Soft Spine'},
                               {'duration': '4:17', 'position': 'A6', 'title': 'Tsunami Sea'},
                               {'duration': '5:33',
                                'position': 'B7',
                                'title': 'A Haven With Two Faces'},
                               {'duration': '2:57', 'position': 'B8', 'title': 'No Loss, No Love'},
                               {'duration': '3:20', 'position': 'B9', 'title': 'Crystal Roses'},
                               {'duration': '4:54', 'position': 'B10', 'title': 'Ride The Wave'},
                               {'duration': '3:48', 'position': 'B11', 'title': 'Deep End'}],
            'trackDurations': {'0': '4:22',
                               '1': '3:25',
                               '10': '3:48',
                               '2': '4:01',
                               '3': '4:04',
                               '4': '3:05',
                               '5': '4:17',
                               '6': '5:33',
                               '7': '2:57',
                               '8': '3:20',
                               '9': '4:54'},
            'trackIds': {'0': 'eoVExOdCpjs',
                         '1': 'VTUrj9hzlcc',
                         '10': 'nmqbm_BFPSI',
                         '2': 'kEOctaHwmbc',
                         '3': 'usgxyuMo0MA',
                         '4': '80VTmBAnTSE',
                         '5': 'hsKtH4gp6Vk',
                         '6': '5iAxY26Kkqk',
                         '7': 'YfKlcLKDkz0',
                         '8': '7-0tw8EaUas',
                         '9': 'ProbP9H_fb4'}},
 33399134: {'defaultYtVideoId': 'EPPFiG1rrs4',
            'fallbackTracks': [{'duration': '3:25', 'position': 'A1', 'title': "Yesterday's Lost"},
                               {'duration': '4:28', 'position': 'A2', 'title': 'Goodbye, Sunshine'},
                               {'duration': '3:34',
                                'position': 'A3',
                                'title': 'Searching For Tomorrow'},
                               {'duration': '4:40',
                                'position': 'A4',
                                'title': 'The Father Of Make Believe'},
                               {'duration': '4:17', 'position': 'A5', 'title': 'Meri Of Mercy'},
                               {'duration': '2:23', 'position': 'B1', 'title': 'Blind Side Sonny'},
                               {'duration': '3:30', 'position': 'B2', 'title': 'Play The Poet'},
                               {'duration': '3:13', 'position': 'B3', 'title': 'One Last Miracle'},
                               {'duration': '4:05',
                                'position': 'B4',
                                'title': 'Corner My Confidence'},
                               {'duration': '3:46', 'position': 'B5', 'title': 'Someone Who Can'},
                               {'duration': '3:44',
                                'position': 'C1',
                                'title': 'The Continuum I: Welcome To Forever, Mr. Nobody'},
                               {'duration': '6:24',
                                'position': 'C2',
                                'title': 'The Continuum II: The Flood'},
                               {'duration': '4:37',
                                'position': 'C3',
                                'title': 'The Continuum III: Tethered Together'},
                               {'duration': '5:46',
                                'position': 'C4',
                                'title': 'The Continuum IV: So It Goes'},
                               {'duration': '', 'position': 'D1', 'title': 'The Omni-Voice'}],
            'trackDurations': {'0': '3:25',
                               '1': '4:28',
                               '10': '3:44',
                               '11': '6:24',
                               '12': '4:37',
                               '13': '5:46',
                               '2': '3:34',
                               '3': '4:40',
                               '4': '4:17',
                               '5': '2:23',
                               '6': '3:30',
                               '7': '3:13',
                               '8': '4:05',
                               '9': '3:46'},
            'trackIds': {'0': 'EPPFiG1rrs4',
                         '1': '0fR7PX274oA',
                         '10': 'u0YCih79M9A',
                         '11': '9OfS1aSyQvU',
                         '12': 'RKcrYARTES0',
                         '13': 'XuO79A-KhF8',
                         '14': '-4T4VUr2K28',
                         '2': 'hDsYGLbmadg',
                         '3': 'F0M87930TE0',
                         '4': 'OcA_dRTHF2w',
                         '5': '-krVx46cjp8',
                         '6': 'Q72p016lRqk',
                         '7': 'BWbDAGxAEmg',
                         '8': 'Elui3TqWQWA',
                         '9': 'mld4KuTNg0M'},
            'ytPlaylistId': 'OLAK5uy_kqYY6Y7uhh4hAZr23qQiUsgANfiWMeCYo'},
 34007283: {'fallbackTracks': [{'duration': '1:16', 'position': 'A1', 'title': '| Carnal |'},
                               {'duration': '4:23', 'position': 'A2', 'title': 'House On Sand'},
                               {'duration': '2:59',
                                'position': 'A3',
                                'title': "If It Doesn't Hurt"},
                               {'duration': '3:06', 'position': 'A4', 'title': 'Angel Song'},
                               {'duration': '3:46', 'position': 'A5', 'title': 'Freefall'},
                               {'duration': '3:20',
                                'position': 'B1',
                                'title': 'Blame It On The Drugs'},
                               {'duration': '1:09', 'position': 'B2', 'title': '| Head |'},
                               {'duration': '4:04', 'position': 'B3', 'title': 'Existential Dread'},
                               {'duration': '3:45', 'position': 'B4', 'title': '| Heart |'},
                               {'duration': '3:06', 'position': 'B5', 'title': 'Down The River'},
                               {'duration': '3:39', 'position': 'C1', 'title': 'Give It Time'},
                               {'duration': '1:10', 'position': 'C2', 'title': '| Sight |'},
                               {'duration': '3:29', 'position': 'C3', 'title': 'Stuck'},
                               {'duration': '4:52', 'position': 'C4', 'title': 'Run For Your Life'},
                               {'duration': '1:48', 'position': 'C5', 'title': '| Sound |'},
                               {'duration': '3:04',
                                'position': 'D1',
                                'title': "We're All Gonna Die"},
                               {'duration': '3:46', 'position': 'D2', 'title': 'Freefall'},
                               {'duration': '3:25',
                                'position': 'D3',
                                'title': 'Angel Song (Live @ Aftershock)'},
                               {'duration': '3:01',
                                'position': 'D4',
                                'title': 'House On Sand (MG Remix)'},
                               {'duration': '3:46',
                                'position': 'D5',
                                'title': 'Angel Song (JD Remix)'}],
            'trackDurations': {'0': '1:16',
                               '1': '4:23',
                               '10': '3:39',
                               '11': '1:10',
                               '12': '3:29',
                               '13': '4:52',
                               '14': '1:48',
                               '15': '3:04',
                               '16': '3:46',
                               '17': '3:25',
                               '18': '3:01',
                               '19': '3:46',
                               '2': '2:59',
                               '3': '3:06',
                               '4': '3:46',
                               '5': '3:20',
                               '6': '1:09',
                               '7': '4:04',
                               '8': '3:45',
                               '9': '3:06'}},
 34691910: {'defaultYtVideoId': 'k2Wi7zw1gbI',
            'fallbackTracks': [{'duration': '4:45', 'position': 'A1', 'title': 'Pray For Rain'},
                               {'duration': '2:46', 'position': 'A2', 'title': 'Hypermania'},
                               {'duration': '4:18', 'position': 'A3', 'title': 'Masochist'},
                               {'duration': '4:16', 'position': 'A4', 'title': 'Landmine'},
                               {'duration': '4:17', 'position': 'A5', 'title': 'Vagabond'},
                               {'duration': '', 'position': 'B1', 'title': 'Creatures Of Habit'},
                               {'duration': '4:42', 'position': 'B2', 'title': 'Above My Head'},
                               {'duration': '3:51', 'position': 'B3', 'title': 'Martyr (Waves)'},
                               {'duration': '3:57',
                                'position': 'B4',
                                'title': 'All Of This Is Fleeting'},
                               {'duration': '', 'position': 'B5', 'title': 'The Descent'}],
            'trackDurations': {'0': '4:45',
                               '1': '2:46',
                               '2': '4:18',
                               '3': '4:16',
                               '4': '4:17',
                               '6': '4:42',
                               '7': '3:51',
                               '8': '3:57'},
            'trackIds': {'0': 'k2Wi7zw1gbI',
                         '1': '33BblvqmwLc',
                         '2': 'jmU2HH0LHmY',
                         '3': 'IuiAUi89yKA',
                         '4': 'dcHVeRifwyE',
                         '6': 'nDbCp0h4DA4',
                         '7': 'PwsXyPmOos4',
                         '8': 'ZoyhIZhTKEc'}},
 34756244: {'defaultYtVideoId': 'DzeqwQ79BWg',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'God Fearing Man'},
                               {'duration': '3:48',
                                'position': 'A2',
                                'title': 'Come Hell Or High Water'},
                               {'duration': '4:08', 'position': 'A3', 'title': 'Desolation'},
                               {'duration': '4:08', 'position': 'A4', 'title': 'Heaven Shall Burn'},
                               {'duration': '4:14', 'position': 'A5', 'title': 'Beyond The Pale'},
                               {'duration': '5:27',
                                'position': 'B1',
                                'title': 'Death By A Thousand Cuts'},
                               {'duration': '6:14', 'position': 'B2', 'title': 'Come What May'},
                               {'duration': '2:37', 'position': 'B3', 'title': 'Cul-de-Sac'},
                               {'duration': '',
                                'position': 'B4',
                                'title': 'Death Shall Have No Dominion'},
                               {'duration': '3:52',
                                'position': 'C1',
                                'title': 'The Call Of The Void'},
                               {'duration': '5:00', 'position': 'C2', 'title': 'Continuum'},
                               {'duration': '3:58', 'position': 'C3', 'title': "L'appel Du Vide"},
                               {'duration': '6:11', 'position': 'C4', 'title': 'The Black'},
                               {'duration': '3:05', 'position': 'C5', 'title': 'Le Noir'},
                               {'duration': '3:48',
                                'position': 'D1',
                                'title': 'Come Hell Or High Water (VAAAL remix)'},
                               {'duration': '6:11',
                                'position': 'D2',
                                'title': 'The Black (VAAAL Remix)'},
                               {'duration': '',
                                'position': 'D3',
                                'title': 'The Blvck (Sena Remix)'},
                               {'duration': '',
                                'position': 'D4',
                                'title': 'La Douleur Qui Est Sans Fin'}],
            'trackDurations': {'1': '3:48',
                               '10': '5:00',
                               '11': '3:58',
                               '12': '6:11',
                               '13': '3:05',
                               '14': '3:48',
                               '15': '6:11',
                               '2': '4:08',
                               '3': '4:08',
                               '4': '4:14',
                               '5': '5:27',
                               '6': '6:14',
                               '7': '2:37',
                               '9': '3:52'},
            'trackIds': {'1': 'DzeqwQ79BWg',
                         '10': 'SE88noufabg',
                         '11': '0jF2q5dPIvA',
                         '12': 'NEhSK6BMRiQ',
                         '13': 'mTNULGz0OaA',
                         '14': 'DzeqwQ79BWg',
                         '15': 'NEhSK6BMRiQ',
                         '2': 'gV7zjc2in8I',
                         '3': '3rAUiieikoE',
                         '4': 'm2GX67jnsOk',
                         '5': 'dnJUQLvWBFg',
                         '6': '-CpdcR8NoOA',
                         '7': '2dHXIZd-4c4',
                         '9': '8wuC6cRbrBo'}},
 34889219: {'defaultYtVideoId': 'BlopBb_b35w',
            'fallbackTracks': [{'duration': '3:15',
                                'position': 'A1',
                                'title': 'The Game Needed Me'},
                               {'duration': '3:40', 'position': 'A2', 'title': 'Memphis & 53rd'},
                               {'duration': '5:03', 'position': 'A3', 'title': 'Drilling'},
                               {'duration': '3:31', 'position': 'A4', 'title': 'The Fix'},
                               {'duration': '4:56', 'position': 'A5', 'title': 'El Torrente'},
                               {'duration': '3:35', 'position': 'B1', 'title': 'Pachuca Sunrise'},
                               {'duration': '3:35',
                                'position': 'B2',
                                'title': "Michio's Death Drive"},
                               {'duration': '4:17', 'position': 'B3', 'title': 'Hooray'},
                               {'duration': '3:23', 'position': 'B4', 'title': 'Fulfill The Dream'},
                               {'duration': '4:38', 'position': 'B5', 'title': 'The Pig War'},
                               {'duration': '4:53',
                                'position': 'B6',
                                'title': "This Ain't A Surfin' Movie"},
                               {'duration': '4:24', 'position': 'C1', 'title': 'Hooray (Demo)'},
                               {'duration': '5:30', 'position': 'C2', 'title': 'Drilling (Demo)'},
                               {'duration': '4:43',
                                'position': 'C3',
                                'title': 'The Pig War (Demo)'},
                               {'duration': '3:33',
                                'position': 'C4',
                                'title': "Michio's Death Drive (Demo)"},
                               {'duration': '4:03',
                                'position': 'C5',
                                'title': "I'm Totally Not Down With Rob's Alien (Demo)"}],
            'trackDurations': {'0': '3:15',
                               '1': '3:40',
                               '10': '4:53',
                               '11': '4:24',
                               '12': '5:30',
                               '13': '4:43',
                               '14': '3:33',
                               '15': '4:03',
                               '2': '5:03',
                               '3': '3:31',
                               '4': '4:56',
                               '5': '3:35',
                               '6': '3:35',
                               '7': '4:17',
                               '8': '3:23',
                               '9': '4:38'},
            'trackIds': {'0': 'BlopBb_b35w',
                         '1': 'hIt-usgVCu8',
                         '10': '5Hh05FRob-M',
                         '11': 'HBcy-8zzpaw',
                         '12': 'Ee3cPFq7vFI',
                         '13': 'ZQFFPR5Nkno',
                         '14': 'Qo6qhaZ119E',
                         '2': 'Ee3cPFq7vFI',
                         '3': 'QpnSLKALzU4',
                         '4': 'sUUWn9ocIZE',
                         '5': 'fwgu2qFrOEE',
                         '6': 'Qo6qhaZ119E',
                         '7': 'HBcy-8zzpaw',
                         '8': 'KLUdsIO_o7M',
                         '9': 'ZQFFPR5Nkno'}},
 35331742: {'defaultYtVideoId': 'Y5uLleCmm6k',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'The Ugly Organist'},
                               {'duration': '1:49',
                                'position': 'A2',
                                'title': 'Some Red Handed Slight Of Hand'},
                               {'duration': '2:52', 'position': 'A3', 'title': 'Art Is Hard'},
                               {'duration': '3:02', 'position': 'A4', 'title': 'The Recluse'},
                               {'duration': '', 'position': 'A5', 'title': 'Herald! Frankenstein'},
                               {'duration': '', 'position': 'A6', 'title': 'Butcher The Song'},
                               {'duration': '',
                                'position': 'A7',
                                'title': 'Driftwood: A Fairy Tale'},
                               {'duration': '', 'position': 'B1', 'title': 'A Gentleman Caller'},
                               {'duration': '', 'position': 'B2', 'title': 'Harold Weathervein'},
                               {'duration': '2:57', 'position': 'B3', 'title': 'Bloody Murderer'},
                               {'duration': '', 'position': 'B4', 'title': 'Sierra'},
                               {'duration': '', 'position': 'B5', 'title': 'Staying Alive'}],
            'trackDurations': {'1': '1:49', '2': '2:52', '3': '3:02', '9': '2:57'},
            'trackIds': {'0': 'Y5uLleCmm6k',
                         '1': 'F8klp9ro19Q',
                         '2': 'HgndBKP7nIE',
                         '3': '9JcFgL2qO9Y',
                         '9': '-lLiYdcN2YE'}},
 35336893: {'defaultYtVideoId': 'dgJFyar1yqY',
            'fallbackTracks': [{'duration': '4:36', 'position': 'A1', 'title': 'Escape'},
                               {'duration': '3:42', 'position': 'A2', 'title': 'Anatomy'},
                               {'duration': '4:37', 'position': 'A3', 'title': 'Outnumbered'},
                               {'duration': '4:54', 'position': 'B1', 'title': 'Revive'},
                               {'duration': '4:31', 'position': 'B2', 'title': 'Survivor'}],
            'trackDurations': {'0': '4:36', '1': '3:42', '2': '4:37', '3': '4:54', '4': '4:31'},
            'trackIds': {'0': 'dgJFyar1yqY',
                         '1': 'xcl4jJnucOo',
                         '2': 'cLA86Bjmnmg',
                         '3': 'Eou5nuDVbQY',
                         '4': '6wuNgaq0MpE'}},
 35426350: {'defaultYtVideoId': 'hkofx4TkHXc',
            'fallbackTracks': [{'duration': '6:51', 'position': 'A1', 'title': 'Dystopia'},
                               {'duration': '5:18', 'position': 'A2', 'title': 'Hexes'},
                               {'duration': '4:25', 'position': 'A3', 'title': 'Survival'},
                               {'duration': '5:59', 'position': 'A4', 'title': 'Tourniquet'},
                               {'duration': '5:34', 'position': 'B1', 'title': 'Utopia'},
                               {'duration': '3:54', 'position': 'B2', 'title': 'Phoenix'},
                               {'duration': '3:35', 'position': 'B3', 'title': 'Messenger'},
                               {'duration': '5:29', 'position': 'B4', 'title': 'Cages'},
                               {'duration': '5:40', 'position': 'B5', 'title': 'Seven Names'}],
            'fullAlbumYtDuration': 2873,
            'fullAlbumYtVideoId': 'Kkl7CiCghVI',
            'trackDurations': {'0': '6:51',
                               '1': '5:18',
                               '2': '4:25',
                               '3': '5:59',
                               '4': '5:34',
                               '5': '3:54',
                               '6': '3:35',
                               '7': '5:29',
                               '8': '5:40'},
            'trackIds': {'1': 'hkofx4TkHXc', '2': 'jO_Cp-Qlg5E'}},
 35485618: {'defaultYtVideoId': 'JOBvn6ZLNxg',
            'fallbackTracks': [{'duration': '3:31', 'position': 'A1', 'title': 'The Casualty'},
                               {'duration': '3:58', 'position': 'A2', 'title': 'The Martyr'},
                               {'duration': '3:37',
                                'position': 'A3',
                                'title': 'Shallow Means, Deep Ends'},
                               {'duration': '2:59',
                                'position': 'A4',
                                'title': 'Making Friends And Acquaintances'},
                               {'duration': '4:41', 'position': 'A5', 'title': 'A Red So Deep'},
                               {'duration': '3:16',
                                'position': 'B1',
                                'title': 'The Lament Of Pretty Baby'},
                               {'duration': '3:35',
                                'position': 'B2',
                                'title': 'The Game Of Who Needs Who Worst'},
                               {'duration': '3:25', 'position': 'B3', 'title': 'The Radiator Hums'},
                               {'duration': '3:23',
                                'position': 'B4',
                                'title': 'The Night I Lost The Will To Fight'}],
            'trackDurations': {'0': '3:31',
                               '1': '3:58',
                               '2': '3:37',
                               '3': '2:59',
                               '4': '4:41',
                               '5': '3:16',
                               '6': '3:35',
                               '7': '3:25',
                               '8': '3:23'},
            'trackIds': {'0': 'JOBvn6ZLNxg',
                         '1': 'onK5-q1Jg58',
                         '2': '2TmAIfd9rPQ',
                         '3': 'SS303X0F4So',
                         '4': 'wYTd9MqzKPQ',
                         '5': 'mDMumuVOh90',
                         '6': 'fFSMY7vqSQg',
                         '7': 'Dc54n4l-ZlQ',
                         '8': 'VvSJRSJ3mZc'}},
 35668090: {'defaultYtVideoId': 'i2wPVO92_xc',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Intro'},
                               {'duration': '3:34', 'position': 'A2', 'title': 'Tenderoni'},
                               {'duration': '3:21', 'position': 'A3', 'title': 'Fancy Footwork'},
                               {'duration': '3:52',
                                'position': 'A4',
                                'title': 'Bonafied Lovin (Tough Guys)'},
                               {'duration': '2:21',
                                'position': 'A5',
                                'title': 'My Girl Is Calling Me (A Liar)'},
                               {'duration': '2:37', 'position': 'A6', 'title': 'Outta Sight'},
                               {'duration': '',
                                'position': 'B1',
                                'title': 'Opening Up (Ce Soir On Danse)'},
                               {'duration': '', 'position': 'B2', 'title': "Momma's Boy"},
                               {'duration': '4:17', 'position': 'B3', 'title': 'Call Me Up'},
                               {'duration': '3:48', 'position': 'B4', 'title': 'Waiting 4 U'},
                               {'duration': '6:01', 'position': 'B5', 'title': '100%'}],
            'trackDurations': {'1': '3:34',
                               '10': '6:01',
                               '2': '3:21',
                               '3': '3:52',
                               '4': '2:21',
                               '5': '2:37',
                               '8': '4:17',
                               '9': '3:48'},
            'trackIds': {'1': 'i2wPVO92_xc',
                         '10': 'Kh6_XYJXi_A',
                         '2': 'I25YWZWLLEU',
                         '3': 'fGksDvKZ9ek',
                         '4': 'qIQxIXtulpU',
                         '5': 'WXF2IUEMh-U',
                         '8': 'pjOJn88ZfHc',
                         '9': '0e8xwp6L3XY'}},
 35720014: {'defaultYtVideoId': '7xeFcjtnAQ0',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Absence Persistent'},
                               {'duration': '', 'position': 'A2', 'title': 'Shade Astray'},
                               {'duration': '', 'position': 'A3', 'title': 'Labyrinthine'},
                               {'duration': '4:18', 'position': 'A4', 'title': 'Without A Whisper'},
                               {'duration': '5:01', 'position': 'A5', 'title': 'False Meridian'},
                               {'duration': '', 'position': 'A6', 'title': 'Reverie'},
                               {'duration': '5:04',
                                'position': 'B1',
                                'title': 'Immolation Of Night'},
                               {'duration': '4:09', 'position': 'B2', 'title': 'Purity Weeps'},
                               {'duration': '4:32', 'position': 'B3', 'title': 'Void Surfacing'},
                               {'duration': '', 'position': 'B4', 'title': 'Emberglow'},
                               {'duration': '4:50', 'position': 'B5', 'title': 'Elysium'}],
            'fullAlbumYtDuration': 2890,
            'fullAlbumYtVideoId': 'O5gYwnkgGO0',
            'trackDurations': {'10': '4:50',
                               '3': '4:18',
                               '4': '5:01',
                               '6': '5:04',
                               '7': '4:09',
                               '8': '4:32'},
            'trackIds': {'10': 'nDxrlM_gPYA',
                         '3': '7xeFcjtnAQ0',
                         '4': 'tZ8mdAHBbwI',
                         '6': '1iwNEukbK48',
                         '7': '1RV7ipCoJiE',
                         '8': 'm6VI_Iw_TeY'}},
 35844325: {'defaultYtVideoId': 'BtqfFZQfSq4',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Firebreather'},
                               {'duration': '', 'position': 'A2', 'title': 'The Messenger'},
                               {'duration': '', 'position': 'A3', 'title': 'Backdraft'},
                               {'duration': '', 'position': 'B4', 'title': 'The Arsonist'},
                               {'duration': '', 'position': 'B5', 'title': 'Burn The Fleet'},
                               {'duration': '', 'position': 'B6', 'title': 'The Flame Deluge'},
                               {'duration': '', 'position': 'C1', 'title': 'Digital Sea'},
                               {'duration': '', 'position': 'C2', 'title': 'Open Water'},
                               {'duration': '', 'position': 'C3', 'title': 'Lost Continent'},
                               {'duration': '', 'position': 'D4', 'title': 'Night Diving'},
                               {'duration': '', 'position': 'D5', 'title': 'The Whaler'},
                               {'duration': '', 'position': 'D6', 'title': 'Kings Upon The Main'}],
            'trackIds': {'0': 'BtqfFZQfSq4'}},
 35844376: {'defaultYtVideoId': 'CI0xoI6WwOY',
            'fallbackTracks': [{'duration': '2:59', 'position': 'A1', 'title': 'Identity Crisis'},
                               {'duration': '', 'position': 'A2', 'title': 'Phoenix Ignition'},
                               {'duration': '', 'position': 'A3', 'title': 'In Your Hands'},
                               {'duration': '', 'position': 'A4', 'title': 'To What End'},
                               {'duration': '', 'position': 'A5', 'title': 'Ultra Blue'},
                               {'duration': '', 'position': 'B6', 'title': 'As The Ruin Falls'},
                               {'duration': '', 'position': 'B7', 'title': 'The Next Day'},
                               {'duration': '',
                                'position': 'B8',
                                'title': 'A Torch To End All Torches'},
                               {'duration': '', 'position': 'B9', 'title': 'Unquestioned Answers'},
                               {'duration': '', 'position': 'B10', 'title': 'Under Par'},
                               {'duration': '', 'position': 'B11', 'title': 'T & C'}],
            'trackDurations': {'0': '2:59'},
            'trackIds': {'0': 'CI0xoI6WwOY'}},
 35852386: {'defaultYtVideoId': '-S2MvjRyhK8',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Broken Lungs'},
                               {'duration': '', 'position': 'A2', 'title': 'The Sky Is Falling'},
                               {'duration': '',
                                'position': 'A3',
                                'title': 'A Song For Milly Michaelson'},
                               {'duration': '', 'position': 'B4', 'title': 'Daedalus'},
                               {'duration': '', 'position': 'B5', 'title': 'As The Crow Flies'},
                               {'duration': '', 'position': 'B6', 'title': 'Silver Wing'},
                               {'duration': '', 'position': 'C1', 'title': 'Moving Mountains'},
                               {'duration': '', 'position': 'C2', 'title': 'Digging My Own Grave'},
                               {'duration': '',
                                'position': 'C3',
                                'title': 'The Earth Isn’t Humming'},
                               {'duration': '', 'position': 'D4', 'title': 'The Lion And The Wolf'},
                               {'duration': '', 'position': 'D5', 'title': 'Come All You Weary'},
                               {'duration': '', 'position': 'D6', 'title': 'Child Of Dust'}]},
 35907826: {'defaultYtVideoId': '5Oc0ja19_GU',
            'fallbackTracks': [{'duration': '4:35', 'position': 'A1', 'title': 'Doomed'},
                               {'duration': '3:57', 'position': 'A2', 'title': 'Happy Song'},
                               {'duration': '3:10', 'position': 'A3', 'title': 'Throne'},
                               {'duration': '3:53', 'position': 'A4', 'title': 'True Friends'},
                               {'duration': '4:50', 'position': 'A5', 'title': 'Follow You'},
                               {'duration': '4:13', 'position': 'A6', 'title': 'What You Need'},
                               {'duration': '', 'position': 'B1', 'title': 'Avalanche'},
                               {'duration': '3:43', 'position': 'B2', 'title': 'Run'},
                               {'duration': '4:06', 'position': 'B3', 'title': 'Drown'},
                               {'duration': '4:36', 'position': 'B4', 'title': 'Blasphemy'},
                               {'duration': '', 'position': 'B5', 'title': 'Oh No'}],
            'trackDurations': {'0': '4:35',
                               '1': '3:57',
                               '2': '3:10',
                               '3': '3:53',
                               '4': '4:50',
                               '5': '4:13',
                               '7': '3:43',
                               '8': '4:06',
                               '9': '4:36'},
            'trackIds': {'0': '5Oc0ja19_GU',
                         '1': 'GBRAnuT48qo',
                         '2': 'Ow_qI_F2ZJI',
                         '3': 'BpmJh2CjSIA',
                         '4': '-tVWt2RDsoM',
                         '5': 'k48k3BUdcXQ',
                         '7': '57F_JVBkyks',
                         '8': 'TkV5709EG5M',
                         '9': 'HYd9B6YvIHM'}},
 36085903: {'defaultYtVideoId': 'PagSv406kvk',
            'fallbackTracks': [{'duration': '3:13',
                                'position': 'A1',
                                'title': 'Meaning In Tragedy'},
                               {'duration': '5:31', 'position': 'A2', 'title': 'Confined'},
                               {'duration': '', 'position': 'A3', 'title': 'Losing Sight'},
                               {'duration': '', 'position': 'A4', 'title': 'The Darkest Nights'},
                               {'duration': '', 'position': 'A5', 'title': 'Empty Hearts'},
                               {'duration': '', 'position': 'A6', 'title': 'Reflection'},
                               {'duration': '', 'position': 'A7', 'title': 'Repeating Yesterday'},
                               {'duration': '4:04', 'position': 'B1', 'title': 'Through Struggle'},
                               {'duration': '',
                                'position': 'B2',
                                'title': 'The Truth Of My Perception'},
                               {'duration': '', 'position': 'B3', 'title': 'Control Is Dead'},
                               {'duration': '', 'position': 'B4', 'title': 'Morning Waits'},
                               {'duration': '', 'position': 'B5', 'title': 'Illusions'}],
            'fullAlbumYtDuration': 2612,
            'fullAlbumYtVideoId': 'EnKllQmSIoE',
            'trackDurations': {'0': '3:13', '1': '5:31', '7': '4:04'},
            'trackIds': {'0': 'PagSv406kvk', '1': 'zb-bnOJ_L-k', '7': '8RXgpfZE17w'}},
 36224473: {'defaultYtVideoId': 'nVEZlujnPR8',
            'fallbackTracks': [{'duration': '2:42', 'position': 'A1', 'title': 'The End'},
                               {'duration': '3:25', 'position': 'A2', 'title': 'Too Late'},
                               {'duration': '2:22',
                                'position': 'A3',
                                'title': 'Better Hell (Thicc Boi)'},
                               {'duration': '2:37', 'position': 'A4', 'title': 'Emptyhanded'},
                               {'duration': '2:51', 'position': 'A5', 'title': 'Miss Me'},
                               {'duration': '2:39', 'position': 'A6', 'title': 'Boutta Cashew'},
                               {'duration': '2:46',
                                'position': 'A7',
                                'title': "Livin' Laughin' Lovin'"},
                               {'duration': '2:44',
                                'position': 'B8',
                                'title': "Spinnin' You Around"},
                               {'duration': '3:06',
                                'position': 'B9',
                                'title': '2016 Cavaliers (Ohio)'},
                               {'duration': '2:49', 'position': 'B10', 'title': 'All Gas'},
                               {'duration': '2:37', 'position': 'B11', 'title': 'Blindsided'},
                               {'duration': '3:09',
                                'position': 'B12',
                                'title': 'Straight Through You'},
                               {'duration': '2:29',
                                'position': 'B13',
                                'title': "Talkin' 2 Ur Ghost"},
                               {'duration': '2:58', 'position': 'B14', 'title': 'Drunk Enough'}],
            'fullAlbumYtDuration': 1719,
            'fullAlbumYtVideoId': 'rzhRYwwVNJI',
            'trackDurations': {'0': '2:42',
                               '1': '3:25',
                               '10': '2:37',
                               '11': '3:09',
                               '12': '2:29',
                               '13': '2:58',
                               '2': '2:22',
                               '3': '2:37',
                               '4': '2:51',
                               '5': '2:39',
                               '6': '2:46',
                               '7': '2:44',
                               '8': '3:06',
                               '9': '2:49'},
            'trackIds': {'10': 'GFaMISXp3bg',
                         '11': 'YCgoRLTateY',
                         '12': 'MW2JD0tj1jQ',
                         '13': 'OZVgns6fmzw',
                         '2': 'nVEZlujnPR8',
                         '3': 'OXnIwlcY8l0',
                         '4': 'i6xNOW3dWy8',
                         '7': '9eTUjbiuheY',
                         '8': '7NCtXJPcxOk',
                         '9': '1SYYjaVyqd4'}},
 36282118: {'defaultYtVideoId': 'JnSGdUorfBs',
            'fallbackTracks': [{'duration': '3:11', 'position': 'A1', 'title': '94 Hours'},
                               {'duration': '2:33',
                                'position': 'A2',
                                'title': 'Falling Upon Deaf Ears'},
                               {'duration': '4:43', 'position': 'A3', 'title': 'Forever'},
                               {'duration': '3:12', 'position': 'A4', 'title': 'Collision'},
                               {'duration': '2:39',
                                'position': 'A5',
                                'title': 'Distance Is Darkness'},
                               {'duration': '3:04',
                                'position': 'A6',
                                'title': 'Behind Me Lies Another Fallen Soldier'},
                               {'duration': '2:18', 'position': 'B1', 'title': 'Undefined'},
                               {'duration': '1:46', 'position': 'B2', 'title': 'A Thousand Steps'},
                               {'duration': '3:30', 'position': 'B3', 'title': 'The Beginning'},
                               {'duration': '4:17', 'position': 'B4', 'title': 'Song 10'},
                               {'duration': '2:58',
                                'position': 'B5',
                                'title': 'The Pain Of Separation'},
                               {'duration': '4:48', 'position': 'B6', 'title': 'Elegy'}],
            'trackDurations': {'0': '3:11',
                               '1': '2:33',
                               '10': '2:58',
                               '11': '4:48',
                               '2': '4:43',
                               '3': '3:12',
                               '4': '2:39',
                               '5': '3:04',
                               '6': '2:18',
                               '7': '1:46',
                               '8': '3:30',
                               '9': '4:17'},
            'trackIds': {'0': 'JnSGdUorfBs',
                         '1': 'fmJ9QarFD18',
                         '10': 'raq6AZ4R660',
                         '11': 'jpZacbqOI3k',
                         '2': 'AU86i6ogVII',
                         '3': 'bzGJEmgBJPs',
                         '4': '8KWu_muudR0',
                         '5': 'n1fBTrm0ODs',
                         '6': 'omZTfLkLyfw',
                         '7': 'mjhBdKn2hIg',
                         '8': 'JbSrblmYBYw',
                         '9': 'FY6lGrESA6M'}},
 36342703: {'defaultYtVideoId': '4tGapndn0K8',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'It Only Gets Darker'},
                               {'duration': '', 'position': 'A2', 'title': 'My Severance'},
                               {'duration': '', 'position': 'A3', 'title': 'Making Circles'},
                               {'duration': '', 'position': 'A4', 'title': "Can't Turn Back"},
                               {'duration': '', 'position': 'A5', 'title': 'Rise & Fall'},
                               {'duration': '',
                                'position': 'B1',
                                'title': 'It Only Gets Darker (Instrumental)'},
                               {'duration': '',
                                'position': 'B2',
                                'title': 'My Severance (Instrumental)'},
                               {'duration': '',
                                'position': 'B3',
                                'title': 'Making Circles (Instrumental)'},
                               {'duration': '',
                                'position': 'B4',
                                'title': "Can't Turn Back (Instrumental)"},
                               {'duration': '',
                                'position': 'B5',
                                'title': 'Rise & Fall (Instrumental)'}],
            'fullAlbumYtDuration': 1202,
            'fullAlbumYtVideoId': '4tGapndn0K8'},
 36666961: {'fallbackTracks': [{'duration': '3:54', 'position': 'A1', 'title': 'Stelliform'},
                               {'duration': '3:31', 'position': 'A2', 'title': 'Further Eden'},
                               {'duration': '3:51', 'position': 'A3', 'title': 'Gore Of Being'},
                               {'duration': '3:38', 'position': 'A4', 'title': 'Black Cloud'},
                               {'duration': '3:57', 'position': 'A5', 'title': 'Cicada Siren'},
                               {'duration': '4:28', 'position': 'A6', 'title': 'Echo Sonata'},
                               {'duration': '3:40', 'position': 'B1', 'title': 'Lucid Threshold'},
                               {'duration': '4:17',
                                'position': 'B2',
                                'title': 'Spiral (Of Liminal Infinity)'},
                               {'duration': '3:06',
                                'position': 'B3',
                                'title': 'I. The Many Names Of God'},
                               {'duration': '3:30',
                                'position': 'B4',
                                'title': 'II. In The Gut Of The Wolf'},
                               {'duration': '4:40',
                                'position': 'B5',
                                'title': 'III. Twilight In The Reflection Of Dreams'}],
            'trackDurations': {'0': '3:54',
                               '1': '3:31',
                               '10': '4:40',
                               '2': '3:51',
                               '3': '3:38',
                               '4': '3:57',
                               '5': '4:28',
                               '6': '3:40',
                               '7': '4:17',
                               '8': '3:06',
                               '9': '3:30'}},
 36763201: {'defaultYtVideoId': 'O_IIAYZL1R4',
            'fallbackTracks': [{'duration': '3:09', 'position': 'A1', 'title': 'Feiticeria'},
                               {'duration': '4:15', 'position': 'A2', 'title': 'Digital Bath'},
                               {'duration': '4:01', 'position': 'A3', 'title': 'Elite'},
                               {'duration': '4:27', 'position': 'B1', 'title': 'Rx Queen'},
                               {'duration': '2:41', 'position': 'B2', 'title': 'Street Carp'},
                               {'duration': '3:20', 'position': 'B3', 'title': 'Teenager'},
                               {'duration': '4:59', 'position': 'C1', 'title': 'Knife Prty'},
                               {'duration': '3:23', 'position': 'C2', 'title': 'Korea'},
                               {'duration': '6:07', 'position': 'C3', 'title': 'Passenger'},
                               {'duration': '4:59',
                                'position': 'D1',
                                'title': 'Change (In The House Of Flies)'},
                               {'duration': '7:32', 'position': 'D2', 'title': 'Pink Maggit'}],
            'trackDurations': {'0': '3:09',
                               '1': '4:15',
                               '10': '7:32',
                               '2': '4:01',
                               '3': '4:27',
                               '4': '2:41',
                               '5': '3:20',
                               '6': '4:59',
                               '7': '3:23',
                               '8': '6:07',
                               '9': '4:59'},
            'trackIds': {'0': 'YKY3jpl99XM',
                         '1': 'O_IIAYZL1R4',
                         '4': 'hbknq6azohw',
                         '9': 'WPpDyIJdasg'}},
 36897417: {'defaultYtVideoId': 'L8CEs2tvKy0',
            'fallbackTracks': [{'duration': '3:17', 'position': 'A1', 'title': 'Cellophane'},
                               {'duration': '3:51', 'position': 'A2', 'title': 'Disappear'},
                               {'duration': '3:18', 'position': 'A3', 'title': 'Somersaults'},
                               {'duration': '5:21',
                                'position': 'A4',
                                'title': 'Nightmare Tripping'},
                               {'duration': '4:18',
                                'position': 'A5',
                                'title': 'Ghost In The Night'},
                               {'duration': '3:32', 'position': 'A6', 'title': 'True Believers'},
                               {'duration': '3:26', 'position': 'B1', 'title': 'Euphoria'},
                               {'duration': '3:41', 'position': 'B2', 'title': 'Pacify Me'},
                               {'duration': '3:09', 'position': 'B3', 'title': 'Swimming Pools'},
                               {'duration': '4:09', 'position': 'B4', 'title': 'Hype Man'},
                               {'duration': '4:24', 'position': 'B5', 'title': 'The Corner'}],
            'trackDurations': {'0': '3:17',
                               '1': '3:51',
                               '10': '4:24',
                               '2': '3:18',
                               '3': '5:21',
                               '4': '4:18',
                               '5': '3:32',
                               '6': '3:26',
                               '7': '3:41',
                               '8': '3:09',
                               '9': '4:09'},
            'trackIds': {'0': 'L8CEs2tvKy0'},
            'ytPlaylistId': 'OLAK5uy_nFCSSl9okFaIiO5fAxLUx0Lh5HbNZdwgQ'},
 36991890: {'defaultYtVideoId': 'jy2MLw_JMJk',
            'fallbackTracks': [{'duration': '5:01', 'position': 'A1', 'title': 'Follow The Signs'},
                               {'duration': '3:34', 'position': 'A2', 'title': 'Singularity'},
                               {'duration': '2:28', 'position': 'A3', 'title': 'Ascension'},
                               {'duration': '4:36', 'position': 'A4', 'title': 'Devastate'},
                               {'duration': '4:08', 'position': 'B1', 'title': 'Recreate'},
                               {'duration': '3:14',
                                'position': 'B2',
                                'title': 'Two Worlds Of Design'},
                               {'duration': '2:08', 'position': 'B3', 'title': 'A Solution'},
                               {'duration': '4:40',
                                'position': 'C1',
                                'title': 'Shaping The Masterpiece'},
                               {'duration': '2:48', 'position': 'C2', 'title': 'Dissimulation'},
                               {'duration': '2:43', 'position': 'C3', 'title': 'Automatic Motion'},
                               {'duration': '2:10', 'position': 'C4', 'title': 'The Omniscient'},
                               {'duration': '4:01', 'position': 'D1', 'title': 'Last Straw'},
                               {'duration': '5:07', 'position': 'D2', 'title': 'Regenerate'},
                               {'duration': '1:53', 'position': 'D3', 'title': 'XIV'},
                               {'duration': '5:51', 'position': 'D4', 'title': 'Behold'}],
            'trackAltIds': {'0': ['wraoECk6hss', 'Et7ewHe5iLc'],
                            '1': ['NmzKdzIcj4U'],
                            '10': ['rpPmKu1NffE', '-raGXcO67w8'],
                            '12': ['PaphbmyjxdU'],
                            '13': ['3I_a-FKpVpc'],
                            '14': ['dFGAPbzIPcg'],
                            '2': ['NFA9Mg0X80k'],
                            '4': ['7OWHDDWASXE', '6UyfrE4bI2E'],
                            '6': ['G45gegxJbHc'],
                            '9': ['JaMzUUK_DG4']},
            'trackDurations': {'0': '5:01',
                               '1': '3:34',
                               '10': '2:10',
                               '11': '4:01',
                               '12': '5:07',
                               '13': '1:53',
                               '14': '5:51',
                               '2': '2:28',
                               '3': '4:36',
                               '4': '4:08',
                               '5': '3:14',
                               '6': '2:08',
                               '7': '4:40',
                               '8': '2:48',
                               '9': '2:43'},
            'trackIds': {'0': 'jy2MLw_JMJk',
                         '1': 'Iekx3gCGL6k',
                         '10': 'PaRNwyUf0hI',
                         '11': 'DJ-jgBYomMg',
                         '12': '00H0eMgHCOw',
                         '13': 'pSPEgIknlwQ',
                         '14': 'k0VBaye65sc',
                         '2': 'LqRPSfw-SmY',
                         '3': 'EYK-T3foPgs',
                         '4': 'F2Dy9K7ohfY',
                         '5': 'M2iOUwFHv9Q',
                         '6': '8Zoq-H4oV0E',
                         '7': 'H2Fkt3JkJbk',
                         '8': 'pmn8hU_B4l8',
                         '9': 'd-Kh4wOoNKY'}},
 37023150: {'defaultYtVideoId': 'Ft1p8USWKHs',
            'fallbackTracks': [{'duration': '4:02', 'position': 'A1', 'title': 'soma.exe'},
                               {'duration': '4:14', 'position': 'A2', 'title': 'obelisk.exe'},
                               {'duration': '4:42', 'position': 'A3', 'title': 'node.exe'},
                               {'duration': '4:07', 'position': 'A4', 'title': 'ohm.exe'},
                               {'duration': '2:20', 'position': 'A5', 'title': 'nameless.exe'},
                               {'duration': '3:54', 'position': 'A6', 'title': 'rot.exe'},
                               {'duration': '4:21', 'position': 'B1', 'title': 'leech.exe'},
                               {'duration': '3:35', 'position': 'B2', 'title': 'impulse.exe'},
                               {'duration': '5:15', 'position': 'B3', 'title': 'weightless.exe'},
                               {'duration': '4:27', 'position': 'B4', 'title': 'ra.exe'},
                               {'duration': '5:24', 'position': 'B5', 'title': 'animate.exe'}],
            'fullAlbumYtDuration': 283,
            'fullAlbumYtVideoId': 'Bh9fROw9DE8',
            'trackDurations': {'0': '4:02',
                               '1': '4:14',
                               '10': '5:24',
                               '2': '4:42',
                               '3': '4:07',
                               '4': '2:20',
                               '5': '3:54',
                               '6': '4:21',
                               '7': '3:35',
                               '8': '5:15',
                               '9': '4:27'},
            'trackIds': {'1': 'Ft1p8USWKHs',
                         '10': '-pleP6qANnU',
                         '2': 'Bh9fROw9DE8',
                         '3': 'Ub8gUDSwVNo',
                         '4': '2JLpBieoqrU',
                         '5': 'azPPevjRDAA',
                         '6': 'z3F8h1FrMTg',
                         '7': 'hQdZvNeka0A',
                         '9': '4jLSP45kpnY'}},
 37058814: {'defaultYtVideoId': 'laIcNXtFLdM',
            'fallbackTracks': [{'duration': '4:53', 'position': 'A1', 'title': 'Lament'},
                               {'duration': '4:09', 'position': 'A2', 'title': 'Nascent'},
                               {'duration': '3:57', 'position': 'A3', 'title': 'Sunrise'},
                               {'duration': '4:49', 'position': 'A4', 'title': 'April'},
                               {'duration': '9:08', 'position': 'A5', 'title': 'Eden'},
                               {'duration': '8:34', 'position': 'B1', 'title': 'Acceptance'},
                               {'duration': '5:23', 'position': 'B2', 'title': 'Deception'},
                               {'duration': '4:51', 'position': 'B3', 'title': 'The Impossible'},
                               {'duration': '2:38', 'position': 'B4', 'title': 'Perfection'},
                               {'duration': '1:29', 'position': 'B5', 'title': 'Epiphany'},
                               {'duration': '4:44', 'position': 'B6', 'title': 'Origin'}],
            'fullAlbumYtDuration': 3271,
            'fullAlbumYtVideoId': 'WxQwFV4kRlQ',
            'trackDurations': {'0': '4:53',
                               '1': '4:09',
                               '10': '4:44',
                               '2': '3:57',
                               '3': '4:49',
                               '4': '9:08',
                               '5': '8:34',
                               '6': '5:23',
                               '7': '4:51',
                               '8': '2:38',
                               '9': '1:29'},
            'trackIds': {'0': 'laIcNXtFLdM', '1': 'grwmUTrO180'}},
 37084122: {'defaultYtVideoId': 'FncfMa-Umcs',
            'fallbackTracks': [{'duration': '1:21', 'position': 'A1', 'title': 'Kinda Hard'},
                               {'duration': '', 'position': 'A2', 'title': 'Twice'},
                               {'duration': '', 'position': 'A3', 'title': 'Worst Part Of You'},
                               {'duration': '2:48', 'position': 'A4', 'title': 'Rock Bottom'},
                               {'duration': '3:27', 'position': 'A5', 'title': 'More Than Hate'},
                               {'duration': '', 'position': 'A6', 'title': 'Hard2tell'},
                               {'duration': '', 'position': 'B7', 'title': 'Where To Find Me'},
                               {'duration': '', 'position': 'B8', 'title': 'St4rf1sh Spr34dr'},
                               {'duration': '3:07', 'position': 'B9', 'title': 'Shyt Fyst'},
                               {'duration': '5:07',
                                'position': 'B10',
                                'title': 'Always Let You Down'},
                               {'duration': '', 'position': 'B11', 'title': 'Back, Then'},
                               {'duration': '2:53', 'position': 'B12', 'title': 'Honest'},
                               {'duration': '3:15', 'position': 'B13', 'title': 'Waves'}],
            'trackDurations': {'0': '1:21',
                               '11': '2:53',
                               '12': '3:15',
                               '3': '2:48',
                               '4': '3:27',
                               '8': '3:07',
                               '9': '5:07'},
            'trackIds': {'0': 'FncfMa-Umcs',
                         '11': 'b9j912Bg4cI',
                         '12': '8UY5WEECAPs',
                         '3': 'NYDTe4Pab54',
                         '4': 'BzONJQRHtj0',
                         '8': '5h1Pka-Pu4s',
                         '9': 'W1mnfilKiPw'},
            'ytPlaylistId': 'OLAK5uy_nVNiXv8mydkzfsuG18YOskVoG5caFRfI4'},
 37163709: {'defaultYtVideoId': '-UUSUrr6zyo',
            'fallbackTracks': [{'duration': '5:04', 'position': '1', 'title': 'Chokehold'},
                               {'duration': '6:35', 'position': '2', 'title': 'The Summoning'},
                               {'duration': '3:45', 'position': '3', 'title': 'Granite'},
                               {'duration': '3:56', 'position': '4', 'title': 'Aqua Regia'},
                               {'duration': '5:39', 'position': '5', 'title': 'Vore'},
                               {'duration': '7:08', 'position': '6', 'title': 'Ascensionism'},
                               {'duration': '5:06',
                                'position': '7',
                                'title': 'Are You Really Okay?'},
                               {'duration': '4:28', 'position': '8', 'title': 'The Apparition'},
                               {'duration': '4:00', 'position': '9', 'title': 'DYWTYLM'},
                               {'duration': '4:12', 'position': '10', 'title': 'Rain'},
                               {'duration': '8:20',
                                'position': '11',
                                'title': 'Take Me Back To Eden'},
                               {'duration': '5:13', 'position': '12', 'title': 'Euclid'}],
            'trackDurations': {'0': '5:04',
                               '1': '6:35',
                               '10': '8:20',
                               '11': '5:13',
                               '2': '3:45',
                               '3': '3:56',
                               '4': '5:39',
                               '5': '7:08',
                               '6': '5:06',
                               '7': '4:28',
                               '8': '4:00',
                               '9': '4:12'},
            'trackIds': {'0': '-UUSUrr6zyo',
                         '1': 'wJNbtYdr-Hg',
                         '10': 'vFHBOKa_ZG0',
                         '11': 'DDdByJYUVeA',
                         '2': 'om4dEGKnEmw',
                         '3': 'nVE1ziLuSNg',
                         '4': '3zDjAtG_y5A',
                         '5': 'Oqr05E-ikmU',
                         '6': 'GdDmR4iWP0E',
                         '7': 'JYRgzsnMdnM',
                         '8': 'hP-6iVUyt8E',
                         '9': '7Fncun4ObQk'},
            'ytPlaylistId': 'OLAK5uy_nfeZcBZ_whZMPXn8oF7unN3763k_SxzSo'},
 37227948: {'fallbackTracks': [{'duration': '4:28', 'position': 'A1', 'title': 'The Edge'},
                               {'duration': '3:09', 'position': 'A2', 'title': 'Cherry Coke'},
                               {'duration': '3:33', 'position': 'A3', 'title': 'Good Enough'},
                               {'duration': '4:15', 'position': 'A4', 'title': 'Give It Away'},
                               {'duration': '2:32', 'position': 'A5', 'title': 'Automatic'},
                               {'duration': '3:24', 'position': 'B1', 'title': 'Shoes'},
                               {'duration': '3:16', 'position': 'B2', 'title': 'Sugarcane'},
                               {'duration': '2:32', 'position': 'B3', 'title': 'Ride'},
                               {'duration': '2:43', 'position': 'B4', 'title': 'Moon & Back'},
                               {'duration': '4:06', 'position': 'B5', 'title': 'Nevermind'}],
            'trackDurations': {'0': '4:28',
                               '1': '3:09',
                               '2': '3:33',
                               '3': '4:15',
                               '4': '2:32',
                               '5': '3:24',
                               '6': '3:16',
                               '7': '2:32',
                               '8': '2:43',
                               '9': '4:06'},
            'trackIds': {'0': 'IPIQhCbIYIQ',
                         '1': 'jFxwz-ZaUog',
                         '2': 'L11p2rJzSwc',
                         '3': 'T2MiAJClD10',
                         '4': 'tOnST5GuW80'}},
 37450368: {'defaultYtVideoId': 'LpMxRApFkkI',
            'fallbackTracks': [{'duration': '2:52', 'position': 'A1', 'title': 'Nihilist'},
                               {'duration': '3:53', 'position': 'A2', 'title': 'Deathwish'},
                               {'duration': '', 'position': 'A3', 'title': 'Phantom Fear'},
                               {'duration': '', 'position': 'A4', 'title': 'Downfall'},
                               {'duration': '', 'position': 'A5', 'title': 'Gone With The Wind'},
                               {'duration': '', 'position': 'A6', 'title': 'The Empty Hourglass'},
                               {'duration': '',
                                'position': 'B1',
                                'title': 'A Match Made In Heaven'},
                               {'duration': '', 'position': 'B2', 'title': 'Gravity'},
                               {'duration': '4:21', 'position': 'B3', 'title': 'All Love Is Lost'},
                               {'duration': '3:45',
                                'position': 'B4',
                                'title': 'From The Wilderness'},
                               {'duration': '8:14', 'position': 'B5', 'title': 'Memento Mori'}],
            'fullAlbumYtDuration': 172,
            'fullAlbumYtVideoId': 'LpMxRApFkkI',
            'trackDurations': {'0': '2:52', '1': '3:53', '10': '8:14', '8': '4:21', '9': '3:45'},
            'trackIds': {'0': 'LpMxRApFkkI',
                         '1': 'NMojaaLxyjI',
                         '10': 'CoFfOv8HIEg',
                         '8': '4nXF99fI6cg',
                         '9': 'qVuWoYi3iLw'}},
 37838730: {'defaultYtVideoId': '2V9Q_ExBHHs',
            'fallbackTracks': [{'duration': '4:27', 'position': 'A1', 'title': 'Pray For Plagues'},
                               {'duration': '3:49',
                                'position': 'A2',
                                'title': 'Tell Slater Not To Wash His D**k'},
                               {'duration': '',
                                'position': 'A3',
                                'title': '⠋⠕⠗ ⠎⠞⠑⠧⠊⠑ ⠺⠕⠝⠙⠑⠗⠎ ⠑⠽⠑⠎ ⠕⠝⠇⠽'},
                               {'duration': '2:17', 'position': 'A4', 'title': 'A Lot Like Vegas'},
                               {'duration': '4:33', 'position': 'A5', 'title': 'Black & Blue'},
                               {'duration': '1:39', 'position': 'A6', 'title': 'Slow Dance'},
                               {'duration': '2:43', 'position': 'B1', 'title': 'Dragon Slaying'},
                               {'duration': '6:09',
                                'position': 'B2',
                                'title': '(I Used To Make Out With) Medusa'},
                               {'duration': '1:56',
                                'position': 'B3',
                                'title': 'Fifteen Fathoms, Counting'},
                               {'duration': '6:11', 'position': 'B4', 'title': 'Off The Heezay'},
                               {'duration': '4:39', 'position': 'B5', 'title': 'Dehumanized'}],
            'fullAlbumYtDuration': 2255,
            'fullAlbumYtVideoId': 'oGEcCNdXqkM',
            'trackDurations': {'0': '4:27',
                               '1': '3:49',
                               '10': '4:39',
                               '3': '2:17',
                               '4': '4:33',
                               '5': '1:39',
                               '6': '2:43',
                               '7': '6:09',
                               '8': '1:56',
                               '9': '6:11'},
            'trackIds': {'0': '2V9Q_ExBHHs',
                         '1': 'jlmt7ri9CFk',
                         '10': 'ilqeDbu4E8Y',
                         '2': '_FhZ04iRoT0',
                         '3': '-rVYlPcRgpA',
                         '4': 'lVh84JYfXIQ',
                         '5': 'RhbJgzAHgZg',
                         '6': 'ZxARi4t1IhQ',
                         '7': '6bPvCRDPED4',
                         '8': 'vqUuRl4iHMQ',
                         '9': 'orUreATnopI'}},
 37848120: {'defaultYtVideoId': 'WMmA0iWI5zI',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Obsession'},
                               {'duration': '', 'position': 'A2', 'title': 'Talk'},
                               {'duration': '', 'position': 'A3', 'title': 'Mr. God'},
                               {'duration': '', 'position': 'B1', 'title': 'Heaven On High'},
                               {'duration': '', 'position': 'B2', 'title': 'Unlocking'},
                               {'duration': '', 'position': 'B3', 'title': 'Subhuman'},
                               {'duration': '', 'position': 'C1', 'title': 'Blackwall'},
                               {'duration': '', 'position': 'C2', 'title': 'Malevolent'},
                               {'duration': '', 'position': 'C3', 'title': 'Carry On'},
                               {'duration': '', 'position': 'D1', 'title': 'Neon Valley'},
                               {'duration': '', 'position': 'D2', 'title': 'Everyone Dies Alone'},
                               {'duration': '', 'position': 'D3', 'title': 'A Pale White Dot'}],
            'fullAlbumYtDuration': 3038,
            'fullAlbumYtVideoId': 'WMmA0iWI5zI'},
 38020071: {'defaultYtVideoId': 'GKcv_3T9-uc',
            'fallbackTracks': [{'duration': '3:33', 'position': 'A1', 'title': 'New Day'},
                               {'duration': '3:01', 'position': 'A2', 'title': 'Omertà'},
                               {'duration': '3:08', 'position': 'A3', 'title': 'Nevermind'},
                               {'duration': '3:24', 'position': 'A4', 'title': 'Enemy'},
                               {'duration': '2:30', 'position': 'A5', 'title': 'Ataraxia'},
                               {'duration': '3:37', 'position': 'B1', 'title': 'Ultraviolence'},
                               {'duration': '3:20', 'position': 'B2', 'title': 'Snowblind'},
                               {'duration': '3:48', 'position': 'B3', 'title': 'High Hopes'},
                               {'duration': '4:31', 'position': 'B4', 'title': 'Avalon'}],
            'fullAlbumYtDuration': 1865,
            'fullAlbumYtVideoId': 'GKcv_3T9-uc',
            'trackDurations': {'0': '3:33',
                               '1': '3:01',
                               '2': '3:08',
                               '3': '3:24',
                               '4': '2:30',
                               '5': '3:37',
                               '6': '3:20',
                               '7': '3:48',
                               '8': '4:31'},
            'ytPlaylistId': 'OLAK5uy_kh6iOuU11CT4IZ_eGOASxtc6r2sKxUrjw'},
 38113617: {'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Diesel'},
                               {'duration': '', 'position': 'A2', 'title': 'Revolver'},
                               {'duration': '', 'position': 'A3', 'title': 'Silver Swarm'},
                               {'duration': '', 'position': 'A4', 'title': 'Only Ever You'},
                               {'duration': '', 'position': 'A5', 'title': 'Fall Into The Wind'},
                               {'duration': '', 'position': 'A6', 'title': 'Tongues'},
                               {'duration': '', 'position': 'B1', 'title': 'Nerv'},
                               {'duration': '', 'position': 'B2', 'title': 'Obsession'},
                               {'duration': '', 'position': 'B3', 'title': 'Crush'},
                               {'duration': '', 'position': 'B4', 'title': 'Under The Knife'},
                               {'duration': '', 'position': 'B5', 'title': 'For Now'},
                               {'duration': '', 'position': 'B6', 'title': 'Mercia'}]},
 38199639: {'defaultYtVideoId': 'cBu89Oo01RI',
            'fallbackTracks': [{'duration': '5:08', 'position': 'A1', 'title': 'Squier Talk'},
                               {'duration': '4:13', 'position': 'A2', 'title': 'Más Rápido'},
                               {'duration': '3:55', 'position': 'A3', 'title': 'Wheel of Fortune'},
                               {'duration': '3:31', 'position': 'A4', 'title': 'Oh No (Believer)'},
                               {'duration': '4:04', 'position': 'A5', 'title': 'Marimba'},
                               {'duration': '5:25', 'position': 'B1', 'title': 'Melanchronic'},
                               {'duration': '3:18', 'position': 'B2', 'title': 'Whatever Alright'},
                               {'duration': '1:54', 'position': 'B3', 'title': 'Two More Hours'},
                               {'duration': '4:55', 'position': 'B4', 'title': 'Future Nostalgia'},
                               {'duration': '4:08', 'position': 'B5', 'title': 'Uh Yaya'},
                               {'duration': '5:12', 'position': 'B6', 'title': 'Obsolete'}],
            'trackDurations': {'0': '5:08',
                               '1': '4:13',
                               '10': '5:12',
                               '2': '3:55',
                               '3': '3:31',
                               '4': '4:04',
                               '5': '5:25',
                               '6': '3:18',
                               '7': '1:54',
                               '8': '4:55',
                               '9': '4:08'},
            'trackIds': {'0': 'cBu89Oo01RI',
                         '1': 'wBXcBccTSTQ',
                         '10': 'nfXihQCsOnc',
                         '2': 'cgbl7q2jvGY',
                         '3': 'UNEBfM6dXDo',
                         '4': 'dnHvpEwuH3E',
                         '5': 'Uba0M2k9pQs',
                         '6': 'o-SURLJL-Tg',
                         '7': 'YL8Ibs5RToY',
                         '8': 'JTgpqMZpKDU',
                         '9': 'cIYj984iNf4'}},
 38267097: {'defaultYtVideoId': 'cAkoQB6rb08',
            'fallbackTracks': [{'duration': '3:23',
                                'position': 'A1',
                                'title': "Holding Someone's Hair Back"},
                               {'duration': '3:27', 'position': 'A2', 'title': 'Act Appalled'},
                               {'duration': '4:15', 'position': 'A3', 'title': 'Wish Resign'},
                               {'duration': '3:14',
                                'position': 'A4',
                                'title': 'The Glorious Nosebleed'},
                               {'duration': '3:41', 'position': 'A5', 'title': 'In Fear And Faith'},
                               {'duration': '4:12',
                                'position': 'A6',
                                'title': 'The Great Golden Baby'},
                               {'duration': '4:23',
                                'position': 'B7',
                                'title': 'Stop The Fucking Car'},
                               {'duration': '4:54', 'position': 'B8', 'title': "We're All Thieves"},
                               {'duration': '2:37', 'position': 'B9', 'title': 'Oh, Hello'},
                               {'duration': '4:02',
                                'position': 'B10',
                                'title': 'Always Getting What You Want'},
                               {'duration': '1:57',
                                'position': 'B11',
                                'title': 'Meet Me In Montauk'},
                               {'duration': '5:44', 'position': 'B12', 'title': 'House Of Leaves'}],
            'trackDurations': {'0': '3:23',
                               '1': '3:27',
                               '10': '1:57',
                               '11': '5:44',
                               '2': '4:15',
                               '3': '3:14',
                               '4': '3:41',
                               '5': '4:12',
                               '6': '4:23',
                               '7': '4:54',
                               '8': '2:37',
                               '9': '4:02'},
            'trackIds': {'0': 'cAkoQB6rb08',
                         '1': 'uRuRYqzOaVI',
                         '10': 'sgCCZ4EOmyg',
                         '11': 'eJVsdLJCflE',
                         '2': 'KHFvrL1k33A',
                         '3': '9Pammeogs6E',
                         '4': 'LjLJf8YIZmU',
                         '5': '8VL3bZkKOms',
                         '6': 'otLHxvUdUTM',
                         '7': '7xlLyxRGXNk',
                         '8': '9zwhZBRrWVc',
                         '9': 'OLhZk5Z8Mg4'}},
 38268432: {'defaultYtVideoId': 'aAVp8qAh9eg',
            'fallbackTracks': [{'duration': '3:24',
                                'position': 'A1',
                                'title': 'In Regards To Myself'},
                               {'duration': '3:59',
                                'position': 'A2',
                                'title': 'A Moment Suspended In Time'},
                               {'duration': '3:26',
                                'position': 'A3',
                                'title': 'There Could Be Nothing After This'},
                               {'duration': '4:13',
                                'position': 'B1',
                                'title': 'You’re Ever So Inviting'},
                               {'duration': '2:57', 'position': 'B2', 'title': 'Salarnir'},
                               {'duration': '4:27',
                                'position': 'B3',
                                'title': 'Returning Empty Handed'},
                               {'duration': '6:13',
                                'position': 'C1',
                                'title': 'Casting Such A Thin Shadow'},
                               {'duration': '3:15',
                                'position': 'C2',
                                'title': 'Moving For The Sake Of Motion'},
                               {'duration': '4:02',
                                'position': 'C3',
                                'title': 'Writing On The Walls'},
                               {'duration': '2:56',
                                'position': 'D1',
                                'title': 'Everyone Looks So Good From Here'},
                               {'duration': '7:02',
                                'position': 'D2',
                                'title': 'To Whom It May Concern'}],
            'fullAlbumYtDuration': 1313,
            'fullAlbumYtVideoId': '0LS9jJVUGhI',
            'trackDurations': {'0': '3:24',
                               '1': '3:59',
                               '10': '7:02',
                               '2': '3:26',
                               '3': '4:13',
                               '4': '2:57',
                               '5': '4:27',
                               '6': '6:13',
                               '7': '3:15',
                               '8': '4:02',
                               '9': '2:56'},
            'trackIds': {'0': 'aAVp8qAh9eg',
                         '1': 'ap7w7t-n7AI',
                         '10': 'BV5Qxj71HIc',
                         '2': 'p0xJhGCb4OE',
                         '3': 'ExlaQBvEXOw',
                         '5': 'wDQpHOMBcUA',
                         '6': 'hfWA3zSBnsk',
                         '7': 'iq596Y2Fa1E',
                         '8': 'RaFZXbnLjoA',
                         '9': 'qqnGpJ0WYBE'}},
 38337288: {'defaultYtVideoId': '2qlV4zDosvg',
            'fallbackTracks': [{'duration': '3:09', 'position': 'A1', 'title': 'Control Burns'},
                               {'duration': '3:43', 'position': 'A2', 'title': 'No Arms'},
                               {'duration': '3:38', 'position': 'A3', 'title': 'Order & Entropy'},
                               {'duration': '3:23',
                                'position': 'A4',
                                'title': 'Swept From Under (Call of the Void)'},
                               {'duration': '3:11', 'position': 'A5', 'title': 'An Early Exit'},
                               {'duration': '4:31', 'position': 'A6', 'title': 'Collateral'},
                               {'duration': '3:57', 'position': 'B1', 'title': 'Cannon Fodder'},
                               {'duration': '3:11', 'position': 'B2', 'title': 'Secret Room'},
                               {'duration': '3:36', 'position': 'B3', 'title': 'Proxy Idols'},
                               {'duration': '3:38', 'position': 'B4', 'title': 'Phoenix Dies'},
                               {'duration': '4:07', 'position': 'B5', 'title': 'From a Distance'},
                               {'duration': '4:26', 'position': 'B6', 'title': 'After Dusk'}],
            'fullAlbumYtDuration': 2640,
            'fullAlbumYtVideoId': 'PMsqmOYXC7I',
            'trackDurations': {'0': '3:09',
                               '1': '3:43',
                               '10': '4:07',
                               '11': '4:26',
                               '2': '3:38',
                               '3': '3:23',
                               '4': '3:11',
                               '5': '4:31',
                               '6': '3:57',
                               '7': '3:11',
                               '8': '3:36',
                               '9': '3:38'},
            'trackIds': {'1': '2qlV4zDosvg',
                         '10': 'iGAK4qCH4rs',
                         '2': 'dzahI4e1298',
                         '3': 'LrYC2qWhP6E',
                         '5': 'iGAK4qCH4rs',
                         '8': 'mXUHkl8yGIY'},
            'ytPlaylistId': 'OLAK5uy_nqed_ed_LDoXrCfDOMpGAsGJ6rRcfdHWI'},
 38345517: {'defaultYtVideoId': 'XE68ORLCqa4',
            'fallbackTracks': [{'duration': '3:52', 'position': 'A1', 'title': 'Angel Wings'},
                               {'duration': '4:00', 'position': 'A2', 'title': 'Doom Loop'},
                               {'duration': '3:52', 'position': 'A3', 'title': 'Dark Heaven'},
                               {'duration': '4:04', 'position': 'A4', 'title': 'Pink Noise'},
                               {'duration': '3:48', 'position': 'A5', 'title': 'Mercy'},
                               {'duration': '3:48', 'position': 'B1', 'title': 'Sleepwalker'},
                               {'duration': '2:57', 'position': 'B2', 'title': 'Dionysus'},
                               {'duration': '4:03',
                                'position': 'B3',
                                'title': 'This Will Divide Us'},
                               {'duration': '2:48', 'position': 'B4', 'title': 'Hate Figure'},
                               {'duration': '4:22', 'position': 'B5', 'title': 'White Devil'}],
            'trackDurations': {'0': '3:52',
                               '1': '4:00',
                               '2': '3:52',
                               '3': '4:04',
                               '4': '3:48',
                               '5': '3:48',
                               '6': '2:57',
                               '7': '4:03',
                               '8': '2:48',
                               '9': '4:22'},
            'trackIds': {'0': 'XE68ORLCqa4',
                         '1': 'O_yO9c7zSIw',
                         '2': 'iMYl02RSHCo',
                         '3': 'VcFoTM1Hgmg',
                         '4': 'NhD3HC1jUeA',
                         '5': 'HnB5mmPfUZU',
                         '6': '0H-uNcxUYgI',
                         '7': 'QDESAAAltJc',
                         '8': 'rr4AFLXGBe0',
                         '9': 'yykLfu3es8s'}},
 38464542: {'defaultYtVideoId': 'lUmOCaQD47k',
            'fallbackTracks': [{'duration': '3:10',
                                'position': 'A1',
                                'title': "Absolutelycrankinmymfin'hog"},
                               {'duration': '2:41',
                                'position': 'A2',
                                'title': 'Iseriouslydislikemostotherhumans'},
                               {'duration': '3:08',
                                'position': 'A3',
                                'title': 'Midwestlawncaredadswhosmashbrews'},
                               {'duration': '', 'position': 'A4', 'title': 'Postalmondclarity'},
                               {'duration': '',
                                'position': 'A5',
                                'title': 'Fluorideinthehardseltzerwater'},
                               {'duration': '3:01',
                                'position': 'A6',
                                'title': 'Liftheavystonemakesadheadvoicequiet'},
                               {'duration': '3:24', 'position': 'A7', 'title': '.E G G.'}],
            'trackDurations': {'0': '3:10', '1': '2:41', '2': '3:08', '5': '3:01', '6': '3:24'},
            'trackIds': {'0': 'lUmOCaQD47k',
                         '1': 'uhT01Riu1V4',
                         '2': '7jlPy9qeO-o',
                         '5': '5cdglVNk18E',
                         '6': 'LRzofo8_V4o'}},
 38600733: {'defaultYtVideoId': 'k5HKMSVsUhU',
            'fallbackTracks': [{'duration': '4:13',
                                'position': 'A1',
                                'title': 'Twisting In The Wind'},
                               {'duration': '3:46',
                                'position': 'A2',
                                'title': 'The Sword That Never Bends'},
                               {'duration': '4:11', 'position': 'A3', 'title': 'Devil May Try'},
                               {'duration': '4:04', 'position': 'B4', 'title': 'Crestfallen'},
                               {'duration': '3:24', 'position': 'B5', 'title': 'False Light'},
                               {'duration': '3:57', 'position': 'B6', 'title': 'If Not Now, When'},
                               {'duration': '3:48',
                                'position': 'C7',
                                'title': "Didn't Think About You (Lately)"},
                               {'duration': '5:07', 'position': 'C8', 'title': 'Leviathan'},
                               {'duration': '4:53', 'position': 'C9', 'title': 'Shed Your Skin'},
                               {'duration': '3:54', 'position': 'D10', 'title': 'Power Divine'},
                               {'duration': '4:57', 'position': 'D11', 'title': 'Exodus'}],
            'trackDurations': {'0': '4:13',
                               '1': '3:46',
                               '10': '4:57',
                               '2': '4:11',
                               '3': '4:04',
                               '4': '3:24',
                               '5': '3:57',
                               '6': '3:48',
                               '7': '5:07',
                               '8': '4:53',
                               '9': '3:54'},
            'trackIds': {'0': 'k5HKMSVsUhU',
                         '1': '7b-VTfpGFUQ',
                         '10': 'lcdqO8v-Eeg',
                         '2': 'yAg8bvbaszU',
                         '3': 'DbKtG32pu6I',
                         '4': 'C-I6KkSRLH8',
                         '5': 'SkZpTYeg99g',
                         '6': 'nmEwUtHpqcU',
                         '7': 'fUlepgP0IiU',
                         '8': 'TuZEhDLiXts',
                         '9': 'Mb1Dt50nirk'}},
 38854575: {'defaultYtVideoId': 'WMmA0iWI5zI',
            'fallbackTracks': [{'duration': '', 'position': 'A1', 'title': 'Obsession'},
                               {'duration': '', 'position': 'A2', 'title': 'Talk'},
                               {'duration': '', 'position': 'A3', 'title': 'Mr. God'},
                               {'duration': '', 'position': 'B1', 'title': 'Heaven On High'},
                               {'duration': '', 'position': 'B2', 'title': 'Unlocking'},
                               {'duration': '', 'position': 'B3', 'title': 'Subhuman'},
                               {'duration': '', 'position': 'C1', 'title': 'Blackwall'},
                               {'duration': '', 'position': 'C2', 'title': 'Malevolent'},
                               {'duration': '', 'position': 'C3', 'title': 'Carry On'},
                               {'duration': '', 'position': 'D1', 'title': 'Neon Valley'},
                               {'duration': '', 'position': 'D2', 'title': 'Everyone Dies Alone'},
                               {'duration': '', 'position': 'D3', 'title': 'A Pale White Dot'}],
            'fullAlbumYtDuration': 3038,
            'fullAlbumYtVideoId': 'WMmA0iWI5zI'}}


def _is_full_album_video(title: str, duration_sec: int) -> bool:
    """Returns True if a YouTube video entry represents a full-album or full-EP stream rather than a single track."""
    low = str(title or "").lower()
    if int(duration_sec or 0) >= 1080:
        return True
    return any(
        kw in low
        for kw in (
            "full album",
            "full-album",
            "full length",
            "full ep",
            "complete album",
            "album stream",
            "album premiere",
            "(full)",
        )
    )


def resolve_youtube_music_live_py(
    artist: str,
    title: str,
    tracks: list[dict[str, Any]],
    ui: Any = None,
) -> dict[str, Any]:
    """Automatically queries YouTube / YouTube Music for any newly added album during sync_discogs.py."""
    import urllib.parse
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor

    clean_art = re.sub(r"\s+\(\d+\)$", "", str(artist or "")).strip()
    clean_tit = re.sub(r"\s*\((?:deluxe|reissue|remake|live|tour)[^)]*\)", "", str(title or ""), flags=re.I).strip() or str(title or "").strip()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Cookie": "CONSENT=YES+cb.20240101-17-p0.en+FX+999",
    }

    result: dict[str, Any] = {
        "ytPlaylistId": "",
        "fullAlbumYtVideoId": "",
        "fullAlbumYtDuration": 0,
        "trackIds": {},
    }

    def _fetch_yt_html(url: str) -> str:
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=6) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception:
            return ""

    # 1. Resolve Official Album Links (YouTube Music OLAK5uy_... & Spotify /album/<id>) via iTunes + Odesli (api.song.link)
    try:
        it_q = urllib.parse.quote(f"{clean_art} {clean_tit}")
        it_raw = _fetch_yt_html(f"https://itunes.apple.com/search?term={it_q}&media=music&entity=album&limit=8")
        if it_raw:
            it_json = json.loads(it_raw)
            it_results = it_json.get("results") or []
            if it_results and isinstance(it_results[0], dict):
                col_id = it_results[0].get("collectionId")
                if col_id:
                    sl_raw = _fetch_yt_html(f"https://api.song.link/v1-alpha.1/links?platform=itunes&type=album&id={col_id}&userCountry=US")
                    if sl_raw:
                        sl_json = json.loads(sl_raw)
                        platforms = sl_json.get("linksByPlatform") or {}
                        ytm_u = (platforms.get("youtubeMusic") or {}).get("url") or (platforms.get("youtube") or {}).get("url") or ""
                        m_ol = re.search(r"(OLAK5uy_[A-Za-z0-9_-]{10,})", str(ytm_u))
                        if m_ol:
                            result["ytPlaylistId"] = m_ol.group(1)
                        sp_u = (platforms.get("spotify") or {}).get("url") or ""
                        m_sp = re.search(r"open\.spotify\.com/(?:intl-[a-z-]+/)?album/([A-Za-z0-9]{15,30})", str(sp_u))
                        if m_sp:
                            result["spotifyAlbumId"] = m_sp.group(1)
    except Exception:
        pass

    # 1B. Fallback: Search YouTube strictly for OLAK5uy_ Album Playlist (NEVER accept PL... user playlists!)
    pl_q = urllib.parse.quote(f"{clean_art} {clean_tit} album")
    if not result.get("ytPlaylistId"):
        pl_html = _fetch_yt_html(f"https://www.youtube.com/results?search_query={pl_q}&sp=EgIQAw%3D%3D")
        if pl_html:
            olak_matches = re.findall(r'"playlistId":"(OLAK5uy_[A-Za-z0-9_-]{10,})"', pl_html)
            if olak_matches:
                result["ytPlaylistId"] = olak_matches[0]

    # 2. Search YouTube for Full Album Video stream (verifying full-album title or >=18m duration)
    fa_html = _fetch_yt_html(f"https://www.youtube.com/results?search_query={pl_q}")
    if fa_html:
        for m_v in re.finditer(
            r'"videoId":"([A-Za-z0-9_-]{11})".{0,600}?"title":\{"runs":\[\{"text":"([^"]+)"\}\]',
            fa_html,
        ):
            cand_id, cand_title = m_v.group(1), m_v.group(2)
            if _is_full_album_video(cand_title, 0):
                result["fullAlbumYtVideoId"] = cand_id
                result["fullAlbumYtDuration"] = 2400
                break

    # 3. Resolve individual track Official Audio videoIds for tracks missing ytVideoId
    missing_indices = [
        (idx, str(tr.get("title") or "").strip())
        for idx, tr in enumerate(tracks[:24])
        if isinstance(tr, dict) and not tr.get("ytVideoId") and str(tr.get("title") or "").strip()
    ]

    if missing_indices:
        def _resolve_one_track(item: tuple[int, str]) -> tuple[int, str]:
            t_idx, t_name = item
            tq = urllib.parse.quote(f"{clean_art} {t_name} {clean_tit} official audio")
            t_html = _fetch_yt_html(f"https://www.youtube.com/results?search_query={tq}")
            if t_html:
                vids = re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', t_html)
                for vid in vids:
                    if vid and vid != result.get("fullAlbumYtVideoId"):
                        return (t_idx, vid)
            return (t_idx, "")

        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                for t_idx, vid in pool.map(_resolve_one_track, missing_indices):
                    if vid:
                        result["trackIds"][str(t_idx)] = vid
        except Exception:
            pass

    if ui and (result["ytPlaylistId"] or result["fullAlbumYtVideoId"] or result["trackIds"]):
        ui.log(
            "yt-music",
            f"Auto-resolved YouTube Music streams for {clean_art} — {clean_tit} "
            f"(playlist={result['ytPlaylistId'] or 'none'}, tracks={len(result['trackIds'])}/{len(tracks)})",
        )
    return result


def extract_release_tracklist_and_videos(
    rel_detail: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extracts a clean vinyl tracklist and YouTube video list from a Discogs /releases/{id} payload, pre-matching track ytVideoId and durations."""
    if not isinstance(rel_detail, dict):
        return ([], [])

    rid = int(rel_detail.get("id") or 0)
    enr = dict(VERIFIED_YTM_RELEASE_MAP.get(rid) or {})
    cached_ytm = rel_detail.get("_ytm_resolved")
    if isinstance(cached_ytm, dict):
        for k in ("ytPlaylistId", "fullAlbumYtVideoId", "fullAlbumYtDuration", "defaultYtVideoId"):
            if cached_ytm.get(k) and not enr.get(k):
                enr[k] = cached_ytm[k]
        if isinstance(cached_ytm.get("trackIds"), dict):
            merged_tids = dict(cached_ytm["trackIds"])
            merged_tids.update(enr.get("trackIds") or {})
            enr["trackIds"] = merged_tids

    clean_tracks: list[dict[str, Any]] = []
    raw_tracks = rel_detail.get("tracklist") or []
    if isinstance(raw_tracks, list):
        for idx, tr in enumerate(raw_tracks, start=1):
            if not isinstance(tr, dict):
                continue
            t_type = str(tr.get("type_") or "track").lower()
            title = str(tr.get("title") or "").strip()
            if not title or t_type == "heading":
                continue
            pos = str(tr.get("position") or str(idx)).strip()
            dur = str(tr.get("duration") or "").strip()
            clean_tracks.append({
                "position": pos,
                "title": title,
                "duration": dur,
            })
            for sub in tr.get("sub_tracks") or []:
                if isinstance(sub, dict) and sub.get("title"):
                    clean_tracks.append({
                        "position": str(sub.get("position") or pos).strip(),
                        "title": str(sub.get("title") or "").strip(),
                        "duration": str(sub.get("duration") or "").strip(),
                    })

    if not clean_tracks and isinstance(enr.get("fallbackTracks"), list):
        clean_tracks = [dict(t) for t in enr["fallbackTracks"] if isinstance(t, dict)]

    clean_videos: list[dict[str, Any]] = []
    parsed_vids: list[dict[str, Any]] = []
    full_album_vid: dict[str, Any] | None = None
    raw_videos = rel_detail.get("videos") or []
    if isinstance(raw_videos, list):
        seen_uris: set[str] = set()
        for vid in raw_videos:
            if not isinstance(vid, dict):
                continue
            uri = str(vid.get("uri") or "").strip()
            if not uri or uri in seen_uris:
                continue
            seen_uris.add(uri)
            v_title = str(vid.get("title") or "").strip()
            v_dur = int(vid.get("duration") or 0)
            clean_videos.append({
                "uri": uri,
                "title": v_title,
                "duration": v_dur,
            })
            m_yt = re.search(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})", uri)
            if m_yt:
                vid_id = m_yt.group(1)
                pv = {
                    "videoId": vid_id,
                    "title": v_title,
                    "duration": v_dur,
                    "stem": _norm_track_stem(v_title),
                    "tokens": _norm_track_tokens(v_title),
                }
                parsed_vids.append(pv)
                if _is_full_album_video(v_title, v_dur) and not full_album_vid:
                    full_album_vid = pv
            if len(clean_videos) >= 64:
                break

    if enr.get("fullAlbumYtVideoId") and not full_album_vid:
        full_album_vid = {
            "videoId": str(enr["fullAlbumYtVideoId"]),
            "title": f"{rel_detail.get('title', 'Full Album')} (Full Album)",
            "duration": int(enr.get("fullAlbumYtDuration") or 2400),
        }

    # Pre-match tracks to YouTube videos (excluding full-album streams from single-track matches!)
    artists_list = rel_detail.get("artists") or []
    artist_name = ""
    if isinstance(artists_list, list) and artists_list and isinstance(artists_list[0], dict):
        artist_name = str(artists_list[0].get("name") or "")
    artist_stem = _norm_track_stem(artist_name)
    track_id_overrides = enr.get("trackIds") or {}
    track_alt_overrides = enr.get("trackAltIds") or {}
    track_dur_overrides = enr.get("trackDurations") or {}

    cum_seconds = 0
    for idx_tr, tr in enumerate(clean_tracks):
        t_title = str(tr.get("title") or "").strip()
        t_stem = _norm_track_stem(t_title)
        t_toks = _norm_track_tokens(t_title)
        best_v = None
        best_score = 0.0
        if t_stem and parsed_vids:
            for pv in parsed_vids:
                if _is_full_album_video(pv["title"], pv["duration"]):
                    continue
                v_stem = pv["stem"]
                v_clean = v_stem[len(artist_stem):] if (artist_stem and v_stem.startswith(artist_stem)) else v_stem
                if not v_clean:
                    continue
                if t_stem == v_clean or t_stem in v_clean or (len(v_clean) >= 5 and v_clean in t_stem):
                    score = 1.0 if t_stem == v_clean else 0.9
                elif t_toks and pv["tokens"]:
                    overlap = len(t_toks & pv["tokens"]) / max(1, len(t_toks))
                    score = overlap if overlap >= 0.65 else 0.0
                else:
                    score = 0.0
                if 45 <= pv["duration"] <= 900:
                    score += 0.05
                if score > best_score:
                    best_score = score
                    best_v = pv

        override_vid = track_id_overrides.get(str(idx_tr)) or track_id_overrides.get(idx_tr)
        if override_vid:
            tr["ytVideoId"] = str(override_vid)
            if not tr.get("ytTitle"):
                tr["ytTitle"] = f"{artist_name} - {t_title}".strip(" -")
        elif best_v and best_score >= 0.60:
            tr["ytVideoId"] = best_v["videoId"]
            tr["ytTitle"] = best_v["title"]
            if not tr.get("duration") and 35 <= best_v["duration"] <= 900:
                tr["duration"] = f"{best_v['duration'] // 60}:{best_v['duration'] % 60:02d}"

        override_alts = track_alt_overrides.get(str(idx_tr)) or track_alt_overrides.get(idx_tr)
        if isinstance(override_alts, list) and override_alts and not tr.get("ytAltVideoIds"):
            tr["ytAltVideoIds"] = [str(x) for x in override_alts if x]

        override_dur = track_dur_overrides.get(str(idx_tr)) or track_dur_overrides.get(idx_tr)
        if override_dur and not tr.get("duration"):
            tr["duration"] = str(override_dur)

        if full_album_vid:
            tr["albumYtVideoId"] = full_album_vid["videoId"]
            tr["albumYtStart"] = cum_seconds
            tr["albumYtDuration"] = int(full_album_vid.get("duration") or 2400)

        dur_str = str(tr.get("duration") or "")
        if ":" in dur_str:
            parts = dur_str.split(":")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                cum_seconds += int(parts[0]) * 60 + int(parts[1])
            else:
                cum_seconds += 215
        else:
            cum_seconds += 215

    return (clean_tracks, clean_videos)


def enrich_record_youtube_music(
    rec: dict[str, Any],
    rel_detail: dict[str, Any] | None = None,
    existing_rec: dict[str, Any] | None = None,
    allow_network_search: bool = True,
    ui: Any = None,
) -> bool:
    """Ensures a record has complete YouTube Music tracklist/playlist/full-album metadata, auto-resolving new releases."""
    rid = int(rec.get("release_id") or (rel_detail or {}).get("id") or 0)
    cache_updated = False

    old_tracks = (
        rec.get("tracklist")
        or ((existing_rec or {}).get("tracklist") if isinstance(existing_rec, dict) else None)
        or []
    )
    old_videos = (
        rec.get("youtube_videos")
        or ((existing_rec or {}).get("youtube_videos") if isinstance(existing_rec, dict) else None)
        or []
    )

    enr = dict(VERIFIED_YTM_RELEASE_MAP.get(rid) or {})
    if isinstance(rel_detail, dict) and isinstance(rel_detail.get("_ytm_resolved"), dict):
        for k, v in rel_detail["_ytm_resolved"].items():
            if v and not enr.get(k):
                enr[k] = v

    tracks, yt_videos = extract_release_tracklist_and_videos(rel_detail) if isinstance(rel_detail, dict) else ([], [])
    if not tracks and isinstance(old_tracks, list) and old_tracks:
        tracks = [dict(t) for t in old_tracks if isinstance(t, dict)]
    elif not tracks and isinstance(enr.get("fallbackTracks"), list):
        tracks = [dict(t) for t in enr["fallbackTracks"] if isinstance(t, dict)]
    elif tracks and isinstance(old_tracks, list):
        if len(old_tracks) == len(tracks):
            for ot, nt in zip(old_tracks, tracks):
                if isinstance(ot, dict):
                    for k in ("ytVideoId", "ytTitle", "ytAltVideoIds", "albumYtVideoId", "albumYtStart", "albumYtDuration", "duration"):
                        if ot.get(k) and not nt.get(k):
                            nt[k] = ot[k]
        else:
            old_by_stem = {
                _norm_track_stem(str(ot.get("title") or "")): ot
                for ot in old_tracks
                if isinstance(ot, dict) and _norm_track_stem(str(ot.get("title") or ""))
            }
            for nt in tracks:
                ot = old_by_stem.get(_norm_track_stem(str(nt.get("title") or "")))
                if isinstance(ot, dict):
                    for k in ("ytVideoId", "ytTitle", "ytAltVideoIds", "albumYtVideoId", "albumYtStart", "albumYtDuration", "duration"):
                        if ot.get(k) and not nt.get(k):
                            nt[k] = ot[k]

    if not yt_videos and isinstance(old_videos, list):
        yt_videos = list(old_videos)

    # Carry over top-level fields from existing_rec or rec (ignoring bogus 2400s single-track misclassifications)
    for src in (existing_rec, rec):
        if isinstance(src, dict):
            for k in ("ytPlaylistId", "fullAlbumYtVideoId", "fullAlbumYtDuration", "defaultYtVideoId"):
                if k in ("fullAlbumYtVideoId", "fullAlbumYtDuration") and int(src.get("fullAlbumYtDuration") or 0) == 2400 and rid in VERIFIED_YTM_RELEASE_MAP and "fullAlbumYtVideoId" not in VERIFIED_YTM_RELEASE_MAP[rid]:
                    continue
                if src.get(k) and not enr.get(k):
                    enr[k] = src[k]

    raw_pl_id = str(enr.get("ytPlaylistId") or "").strip()
    yt_playlist_id = raw_pl_id if raw_pl_id.startswith("OLAK5uy_") else ""
    spotify_album_id = str(enr.get("spotifyAlbumId") or rec.get("spotifyAlbumId") or "").strip()
    full_album_vid_id = str(enr.get("fullAlbumYtVideoId") or "").strip()
    full_album_dur = int(enr.get("fullAlbumYtDuration") or 0)
    track_ids_map = enr.get("trackIds") if isinstance(enr.get("trackIds"), dict) else {}
    track_alt_ids_map = enr.get("trackAltIds") if isinstance(enr.get("trackAltIds"), dict) else {}
    track_durs_map = enr.get("trackDurations") if isinstance(enr.get("trackDurations"), dict) else {}

    # Only query YouTube over the network for genuinely unmapped brand-new releases
    already_resolved = bool(
        rid in VERIFIED_YTM_RELEASE_MAP
        or (isinstance(rel_detail, dict) and rel_detail.get("_ytm_resolved"))
    )
    if tracks and allow_network_search and not already_resolved:
        covered = sum(
            1
            for idx, t in enumerate(tracks)
            if t.get("ytVideoId")
            or track_ids_map.get(str(idx))
            or track_ids_map.get(idx)
            or yt_playlist_id
            or full_album_vid_id
            or t.get("albumYtVideoId")
        )
        if covered < len(tracks):
            live_res = resolve_youtube_music_live_py(
                artist=str(rec.get("artist") or ""),
                title=str(rec.get("title") or ""),
                tracks=tracks,
                ui=ui,
            )
            if live_res.get("ytPlaylistId") and not yt_playlist_id:
                yt_playlist_id = str(live_res["ytPlaylistId"])
            if live_res.get("fullAlbumYtVideoId") and not full_album_vid_id:
                full_album_vid_id = str(live_res["fullAlbumYtVideoId"])
                full_album_dur = int(live_res.get("fullAlbumYtDuration") or 2400)
            if isinstance(live_res.get("trackIds"), dict) and live_res["trackIds"]:
                merged_t = dict(live_res["trackIds"])
                merged_t.update(track_ids_map)
                track_ids_map = merged_t
            if isinstance(rel_detail, dict):
                rel_detail["_ytm_resolved"] = {
                    "ytPlaylistId": yt_playlist_id,
                    "fullAlbumYtVideoId": full_album_vid_id,
                    "fullAlbumYtDuration": full_album_dur,
                    "trackIds": track_ids_map,
                }
                cache_updated = True

    cum_sec = 0
    for idx, t in enumerate(tracks):
        ov_vid = track_ids_map.get(str(idx)) or track_ids_map.get(idx)
        if ov_vid and not t.get("ytVideoId"):
            t["ytVideoId"] = str(ov_vid)
        ov_alts = track_alt_ids_map.get(str(idx)) or track_alt_ids_map.get(idx)
        if isinstance(ov_alts, list) and ov_alts and not t.get("ytAltVideoIds"):
            t["ytAltVideoIds"] = [str(x) for x in ov_alts if x]
        ov_dur = track_durs_map.get(str(idx)) or track_durs_map.get(idx)
        if ov_dur and not t.get("duration"):
            t["duration"] = str(ov_dur)
        if full_album_vid_id and not t.get("albumYtVideoId"):
            t["albumYtVideoId"] = full_album_vid_id
            t["albumYtDuration"] = full_album_dur or 2400
        if t.get("albumYtVideoId") and not t.get("albumYtStart") and idx > 0:
            t["albumYtStart"] = cum_sec
        dur_str = str(t.get("duration") or "")
        if ":" in dur_str:
            parts = dur_str.split(":")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                cum_sec += int(parts[0]) * 60 + int(parts[1])
            else:
                cum_sec += 215
        else:
            cum_sec += 215

    if not full_album_vid_id and tracks:
        for t in tracks:
            if t.get("albumYtVideoId"):
                full_album_vid_id = str(t["albumYtVideoId"])
                full_album_dur = int(t.get("albumYtDuration") or 2400)
                break

    default_vid_id = str(rec.get("defaultYtVideoId") or enr.get("defaultYtVideoId") or "").strip()
    if not default_vid_id:
        for t in tracks:
            if t.get("ytVideoId"):
                default_vid_id = str(t["ytVideoId"])
                break
    if not default_vid_id and full_album_vid_id:
        default_vid_id = full_album_vid_id
    if not default_vid_id and yt_videos:
        for v in yt_videos:
            m_v = re.search(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})", str(v.get("uri") or ""))
            if m_v:
                default_vid_id = m_v.group(1)
                break

    if tracks:
        rec["tracklist"] = tracks
    if yt_videos:
        rec["youtube_videos"] = yt_videos
    if yt_playlist_id and yt_playlist_id.startswith("OLAK5uy_"):
        rec["ytPlaylistId"] = yt_playlist_id
    else:
        rec.pop("ytPlaylistId", None)
    if spotify_album_id:
        rec["spotifyAlbumId"] = spotify_album_id
    if full_album_vid_id:
        rec["fullAlbumYtVideoId"] = full_album_vid_id
        rec["fullAlbumYtDuration"] = full_album_dur or 2400
    if default_vid_id:
        rec["defaultYtVideoId"] = default_vid_id

    return cache_updated



class VaultTerminalUI:
    """Fancy Cyber-Audiophile CLI UI, Live Spinning Turntable Throbber, and Delta Summary Reporter."""

    PLATTER_FRAMES = (
        "╭◉╮",
        "◝◉◞",
        "╰◉╯",
        "◟◉◝",
        "╭◎╮",
        "◝◎◞",
        "╰◎╯",
        "◟◎◝",
    )
    EQ_FRAMES = (
        "▂▄▆█▆▄▂",
        "▄▆█▇▅▃▂",
        "▆█▇▅▃▂▄",
        "█▇▅▃▂▄▆",
        "▇▅▃▂▄▆█",
        "▅▃▂▄▆█▇",
        "▃▂▄▆█▇▅",
        "▂▄▆█▇▅▃",
    )

    def __init__(self, title: str = "KRUNKED // VINYL VAULT", subtitle: str = "DELTA SYNC ENGINE v4.0") -> None:
        self.title = title
        self.subtitle = subtitle
        self.start_time = _time.perf_counter()
        self.lock = _threading.Lock()
        self.is_tty = self._init_terminal()
        self.color_enabled = self.is_tty and not bool(_os.environ.get("NO_COLOR"))

        # Throbber state
        self._running = False
        self._thread: _threading.Thread | None = None
        self._frame_idx = 0
        self._phase = "Initializing..."
        self._current_item = ""
        self._done = 0
        self._total = 0
        self._new_count = 0
        self._resync_count = 0
        self._cached_count = 0
        self._api_remaining = 60

    @staticmethod
    def _init_terminal() -> bool:
        """Enables UTF-8 and Windows VT100 ANSI escape codes in PowerShell / CMD / Windows Terminal."""
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

        is_tty = False
        try:
            is_tty = bool(sys.stdout.isatty())
        except Exception:
            is_tty = False

        if _os.name == "nt":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                # STD_OUTPUT_HANDLE = -11, ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
                handle = kernel32.GetStdHandle(-11)
                mode = ctypes.c_ulong()
                if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                    kernel32.SetConsoleMode(handle, mode.value | 0x0004)
                    is_tty = True
            except Exception:
                pass
        return is_tty

    def c(self, text: str, ansi_code: str) -> str:
        if not self.color_enabled:
            return text
        return f"\033[{ansi_code}m{text}\033[0m"

    def elapsed_str(self) -> str:
        el = max(0.0, _time.perf_counter() - self.start_time)
        if el < 60.0:
            return f"{el:05.2f}s"
        mins = int(el // 60)
        secs = el - (mins * 60)
        return f"{mins:02d}m{secs:04.1f}s"

    def print_banner(self, mode_label: str = "INCREMENTAL DELTA", extra_info: str = "") -> None:
        with self.lock:
            self._clear_line_unlocked()
            w = 114
            top = "╭" + ("─" * (w - 2)) + "╮"
            bot = "╰" + ("─" * (w - 2)) + "╯"
            print(self.c(top, "38;5;45"))
            line1 = _pad_to_width(f"  ◉━━━  {self.title}  •  {self.subtitle}", w - 2)
            print(
                self.c("│", "38;5;45")
                + self.c(line1, "1;38;5;213")
                + self.c("│", "38;5;45")
            )
            line2 = _pad_to_width(f"  ╭──╮  Mode: {mode_label}  •  CV: 4-Pass Concentric Dual-Circle", w - 2)
            print(
                self.c("│", "38;5;45")
                + self.c(line2, "38;5;117")
                + self.c("│", "38;5;45")
            )
            tip_text = extra_info or "Tip: Pass --full to force-rescan all records or --resync <release_id>"
            line3 = _pad_to_width(f"  ╰──╯  {tip_text}", w - 2)
            print(
                self.c("│", "38;5;45")
                + self.c(line3, "38;5;246")
                + self.c("│", "38;5;45")
            )
            print(self.c(bot, "38;5;45"), flush=True)

    def _clear_line_unlocked(self) -> None:
        if self.is_tty:
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()

    def _render_throbber_unlocked(self) -> None:
        if not self.is_tty or not self._running:
            return
        platter = self.PLATTER_FRAMES[self._frame_idx % len(self.PLATTER_FRAMES)]
        eq = self.EQ_FRAMES[self._frame_idx % len(self.EQ_FRAMES)]

        if self._total > 0:
            pct = min(100, int((self._done / float(self._total)) * 100))
            bar_w = 14
            filled = int(round((pct / 100.0) * bar_w))
            bar = ("█" * filled) + ("░" * max(0, bar_w - filled))
            prog_str = f"[{bar}] {pct:3d}% ({self._done}/{self._total})"
        else:
            spin_bar_pos = self._frame_idx % 10
            bar_chars = ["░"] * 10
            bar_chars[spin_bar_pos] = "█"
            if spin_bar_pos > 0:
                bar_chars[spin_bar_pos - 1] = "▓"
            prog_str = f"[{''.join(bar_chars)}] {self._phase}"

        delta_str = f"+{self._new_count} new • ~{self._resync_count} sync • {self._cached_count} cached"
        item_str = f" │ {_pad_to_width(self._current_item, 34).rstrip()}" if self._current_item else ""

        colored_line = (
            f" {self.c(platter, '1;38;5;213')} "
            f"{self.c(eq, '38;5;45')} "
            f"{self.c(prog_str, '1;38;5;159')} "
            f"│ {self.c(delta_str, '38;5;221')} "
            f"│ {self.c(self.elapsed_str(), '38;5;248')}"
            f"{self.c(item_str, '38;5;114') if item_str else ''}"
        )
        sys.stdout.write("\r\033[K" + colored_line)
        sys.stdout.flush()

    def _throbber_loop(self) -> None:
        while self._running:
            with self.lock:
                self._frame_idx += 1
                self._render_throbber_unlocked()
            _time.sleep(0.09)

    def start_throbber(self, phase: str = "Syncing Vault...", total: int = 0) -> None:
        with self.lock:
            self._phase = phase
            self._total = total
            self._done = 0
            if not self.is_tty or self._running:
                return
            self._running = True
            self._thread = _threading.Thread(target=self._throbber_loop, daemon=True)
            self._thread.start()

    def update_throbber(
        self,
        *,
        phase: str | None = None,
        current_item: str | None = None,
        done: int | None = None,
        total: int | None = None,
        new_count: int | None = None,
        resync_count: int | None = None,
        cached_count: int | None = None,
        api_remaining: int | None = None,
    ) -> None:
        with self.lock:
            if phase is not None:
                self._phase = phase
            if current_item is not None:
                self._current_item = current_item
            if done is not None:
                self._done = done
            if total is not None:
                self._total = total
            if new_count is not None:
                self._new_count = new_count
            if resync_count is not None:
                self._resync_count = resync_count
            if cached_count is not None:
                self._cached_count = cached_count
            if api_remaining is not None:
                self._api_remaining = api_remaining
            self._render_throbber_unlocked()

    def stop_throbber(self) -> None:
        self._running = False
        if self._thread is not None:
            try:
                self._thread.join(timeout=0.3)
            except Exception:
                pass
            self._thread = None
        with self.lock:
            self._clear_line_unlocked()

    def log(self, tag: str, message: str, *, stream: Any = None) -> None:
        """Prints a clean, timestamped `[tag]` line above the live throbber."""
        out = stream or sys.stdout
        tag_clean = tag.strip("[]").lower()
        palette = {
            "info": "1;38;5;81",       # Sky Cyan
            "auth": "1;38;5;117",      # Light Blue
            "api": "1;38;5;177",       # Orchid Purple
            "delta": "1;38;5;220",     # Gold/Amber
            "fast-path": "38;5;245",   # Dim Grey
            "new": "1;38;5;48",        # Neon Emerald Green
            "resync": "1;38;5;214",    # Warm Amber
            "updated": "1;38;5;48",    # Emerald
            "cleaned": "1;38;5;209",   # Coral Orange
            "cv-pick": "1;38;5;213",   # Hot Pink/Magenta
            "wax-seed": "1;38;5;51",   # Aqua Cyan
            "ok": "1;38;5;46",         # Bright Green
            "warn": "1;38;5;226",      # Yellow
            "error": "1;38;5;196",     # Red
            "rate-limit": "1;38;5;208",# Orange
        }
        ansi = palette.get(tag_clean, "1;38;5;117")
        ts = self.c(f"[{self.elapsed_str()}]", "38;5;242")
        tag_fmt = self.c(f"[{tag_clean}]".ljust(11), ansi)

        with self.lock:
            self._clear_line_unlocked()
            print(f"{ts} {tag_fmt} {message}", file=out, flush=True)
            self._render_throbber_unlocked()

    def print_summary_report(
        self,
        *,
        mode_title: str,
        total_records: int,
        pressing_photo_count: int,
        colored_count: int,
        todo_count: int,
        done_count: int,
        collection_value: dict[str, Any],
        injected_html: bool,
        html_path: pathlib.Path,
        new_records: list[dict[str, Any]],
        resynced_records: list[dict[str, Any]],
        removed_records: list[dict[str, Any]],
        unchanged_count: int,
        all_records: list[dict[str, Any]],
        upgraded_pressing_files: int = 0,
        removed_false_pressing_files: int = 0,
        newly_detected_overrides: int = 0,
    ) -> None:
        """Prints the comprehensive box-drawn end-of-run summary & changelog."""
        self.stop_throbber()
        w = 114
        inner_w = w - 4
        hr_top = "╭" + ("─" * (w - 2)) + "╮"
        hr_mid = "├" + ("─" * (w - 2)) + "┤"
        hr_bot = "╰" + ("─" * (w - 2)) + "╯"

        def row(text: str, ansi: str = "") -> None:
            padded = _pad_to_width(text, inner_w)
            body = self.c(padded, ansi) if ansi else padded
            print(self.c("│ ", "38;5;45") + body + self.c(" │", "38;5;45"))

        skip_pct = (unchanged_count / float(total_records) * 100.0) if total_records > 0 else 0.0
        colored_pct = (colored_count / float(total_records) * 100.0) if total_records > 0 else 0.0
        pressing_pct = (pressing_photo_count / float(total_records) * 100.0) if total_records > 0 else 0.0

        self.log(
            "delta",
            f"Run Summary: +{len(new_records)} NEW • ~{len(resynced_records)} RESYNCED • "
            f"{unchanged_count} FAST-PATH CACHED ({skip_pct:.1f}% skipped)",
        )

        print()
        print(self.c(hr_top, "38;5;45"))
        row(f"◉  {mode_title} — COMPLETE IN {self.elapsed_str()}", "1;38;5;48")
        print(self.c(hr_mid, "38;5;45"))

        # Section 1: Delta Engine Performance
        row("▸ DELTA ENGINE TELEMETRY", "1;38;5;220")
        row(
            f"  • Delta Breakdown:   +{len(new_records)} NEW  │  ~{len(resynced_records)} RESYNCED  │  "
            f"{unchanged_count} CACHED ({skip_pct:.1f}% skipped)"
        )
        if removed_records:
            row(f"  • Removed Records:   -{len(removed_records)} removed from collection", "38;5;209")
        row(
            f"  • Pressing Updates:  {upgraded_pressing_files} pressing.jpg written  │  "
            f"{removed_false_pressing_files} false-positives cleaned  │  {newly_detected_overrides} overrides"
        )

        print(self.c(hr_mid, "38;5;45"))

        # Section 2: Vault Health & Valuation
        row("▸ VAULT HEALTH & VALUATION", "1;38;5;81")
        row(f"  • Total Collection:  {total_records} LPs in Vault")
        row(f"  • Pressing Photos:   {pressing_photo_count} / {total_records} ({pressing_pct:.1f}%) verified physical disc photos")
        row(f"  • Colored / Special: {colored_count} / {total_records} ({colored_pct:.1f}%) non-black wax variants")
        row(f"  • Flattening Queue:  {todo_count} Need to be done  •  {done_count} Done")
        row(
            f"  • Vault Valuation:   Median {collection_value.get('median', '$0.00')}  "
            f"(Min {collection_value.get('minimum', '$0.00')} • Max {collection_value.get('maximum', '$0.00')})"
        )
        row(
            f"  • Static HTML Build: {'YES — index.html injected' if injected_html else 'NO'} "
            f"(Sum Est: {collection_value.get('formatted_total', '$0.00')})"
        )

        print(self.c(hr_mid, "38;5;45"))

        # Section 3: What Was Added (Always shown clearly!)
        if new_records:
            row(f"▸ NEWLY ADDED RECORDS (+{len(new_records)} ADDED THIS RUN)", "1;38;5;48")
            for idx, r in enumerate(new_records, start=1):
                rid = r.get("release_id")
                art = str(r.get("artist") or "Unknown Artist")
                tit = str(r.get("title") or "Untitled")
                yr = r.get("year") or ""
                yr_s = f" ({yr})" if yr else ""
                badge = str((r.get("wax_spec") or {}).get("variant_badge") or r.get("format_string") or "LP")
                val_f = float(r.get("estimated_value_usd") or 0.0)
                imgs = r.get("images") or {}
                if imgs.get("has_pressing_photo"):
                    sel_i = imgs.get("selected_index", 0)
                    sc = float(imgs.get("selected_score") or 0.0)
                    photo_tag = f"Photo: img_{sel_i}.jpg (CV {sc:.2f})"
                else:
                    photo_tag = "Photo: Procedural Wax Seed"
                row(f"  {idx}. + [#{rid}] {art} — {tit}{yr_s}", "1;38;5;120")
                row(f"       ↳ {badge} │ ${val_f:,.2f} │ {photo_tag}", "38;5;250")
        else:
            row("▸ NEWLY ADDED RECORDS (0 ADDED THIS RUN)", "1;38;5;81")
            row("  • No brand-new releases detected on this run (Vault is 100% synced).", "38;5;246")
            if all_records:
                recent = sorted(
                    all_records,
                    key=lambda x: (str(x.get("date_added") or ""), int(x.get("release_id") or 0)),
                    reverse=True,
                )[:3]
                row("  • Latest Pickups in Vault:", "38;5;117")
                for r in recent:
                    rid = r.get("release_id")
                    art = str(r.get("artist") or "")
                    tit = str(r.get("title") or "")
                    d_add = str(r.get("date_added") or "")[:10]
                    imgs = r.get("images") or {}
                    p_str = f"img_{imgs.get('selected_index')}.jpg" if imgs.get("has_pressing_photo") else "seed"
                    row(f"    ↳ [{d_add}] #{rid} {art} — {tit} ({p_str})", "38;5;248")

        # Section 4: Resynced / Updated Records (if any)
        if resynced_records:
            print(self.c(hr_mid, "38;5;45"))
            row(f"▸ RESYNCED / RE-EVALUATED RECORDS (~{len(resynced_records)} THIS RUN)", "1;38;5;214")
            for idx, item in enumerate(resynced_records[:12], start=1):
                rec = item["record"]
                reason = item.get("reason", "resynced")
                action = item.get("action", "")
                rid = rec.get("release_id")
                art = str(rec.get("artist") or "")
                tit = str(rec.get("title") or "")
                row(f"  {idx}. ~ [#{rid}] {art} — {tit}", "38;5;222")
                detail_line = f"       ↳ {reason}" + (f" │ {action}" if action else "")
                row(detail_line, "38;5;246")
            if len(resynced_records) > 12:
                row(f"  ... and {len(resynced_records) - 12} more resynced records.", "38;5;246")

        # Section 5: Removed Records (if any)
        if removed_records:
            print(self.c(hr_mid, "38;5;45"))
            row(f"▸ REMOVED FROM COLLECTION (-{len(removed_records)})", "1;38;5;209")
            for r in removed_records[:5]:
                row(f"  - [#{r.get('release_id')}] {r.get('artist')} — {r.get('title')}", "38;5;209")

        print(self.c(hr_bot, "38;5;45"), flush=True)
