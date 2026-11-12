#!/usr/bin/env python3
"""Deterministic Pressing Image Classifier, Vinyl Wax Variant Parser & Flattening Matcher.

Uses 100% deterministic rules to:
1. Identify which image in a Discogs Release `images[]` array depicts the
   physical 12" vinyl pressing itself (vs. front sleeve cover, back cover tracklist,
   square inner sleeve / lyric insert, gatefold spread, or close-up 4" paper center
   label), supporting both square (1:1) and 4:3 / 3:4 camera photos of vinyl pressings.
2. Parse Discogs `formats[].descriptions`, `formats[].text`, and release notes
   into a deterministic `wax_spec` object for procedural vinyl rendering and
   filtering when a release has no pressing photo on Discogs.
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
from typing import Any

try:
    import numpy as np
    from PIL import Image
    HAS_CV_DEPS = True
except ImportError:
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
    "hou": ("#3b82f6", "House Blue/Cyan Swirl", True),
    "gal": ("#4f46e5", "Galaxy Nebula", True),
    "galaxy": ("#4f46e5", "Galaxy Nebula", True),
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

    for tok in tokens:
        if tok in DISCOGS_COLOR_MAP:
            hex_c, name, trans = DISCOGS_COLOR_MAP[tok]
            if hex_c not in seen_hex:
                matched_colors.append((hex_c, name, trans))
                seen_hex.add(hex_c)

    color_words = [
        (r"milky\s+in\s+clear", "#f1f5f9", "Milky in Clear", True),
        (r"red(?:dish)?", "#dc2626", "Crimson Red", True),
        (r"ruby", "#e11d48", "Ruby Red", True),
        (r"burgundy|maroon", "#9f1239", "Burgundy Red", True),
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

    # Determine pattern prioritizing format_str first, then filtered_comments
    pattern_source = fmt_lower if re.search(
        r"splatter|starburst|in clear|color-in-color|gal|galaxy|nebula|dus|dust|gho|ghost|smoke|swirl|marb|marble|split|smash|twister|cle|ult|mil|cok|clear|translucent",
        fmt_lower,
    ) else lower

    if re.search(r"splatter|starburst", pattern_source):
        pattern = "splatter"
    elif re.search(r"in clear|color-in-color|milky in clear|bone in|pink in|black in|red in", pattern_source):
        pattern = "color_in_color"
    elif re.search(r"\b(gal|galaxy|nebula|dus|dust|gho|ghost|smoke|glitter|starlight)\b", pattern_source):
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
) -> dict[str, Any]:
    """Deterministically scores an image for whether it shows a physical 12" vinyl record pressing.

    Uses Multi-Scale Concentric Dual-Circle Detection:
    1. Scans candidate disc radii `R_disc in [0.68..0.98]` along the 4 diagonal quadrants
       (`|cos(theta)| >= 0.36 & |sin(theta)| >= 0.36`) where circular discs curve inside the
       square frame while square sleeves/lyric inserts extend into the corners.
    2. Verifies the mandatory 1/3 center-label-to-disc ratio (`R_label ≈ R_disc / 3.0`)
       separating the 4" paper center label from the 12" vinyl wax annulus.
    3. Explicitly detects and penalizes:
       - Zoomed-in 4" paper center label scans (`img_2`, `img_3` in Guideline 13.8), where
         the paper label fills `r < 0.75` and only the outer corners show vinyl runout.
       - Square 12x12" lyric sheets, inner sleeves, and back covers (`img_1`, `img_2`, `img_3`),
         where horizontal/vertical edges and dense text lines lack a 4-quadrant circular rim.
    """
    if not HAS_CV_DEPS:
        return {"is_pressing": False, "score": 0.0, "reason": "cv_deps_unavailable"}

    with Image.open(io.BytesIO(image_bytes)) as im:
        w, h = im.size
        aspect = w / float(h) if h else 0.0
        if aspect < 0.65 or aspect > 1.52:
            return {
                "is_pressing": False,
                "score": 0.05,
                "aspect_ratio": round(aspect, 3),
                "reason": "rejected_aspect_ratio_panoramic_or_strip",
            }
        rgb_full = im.convert("RGB")
        if abs(aspect - 1.0) > 0.08:
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            rgb_cropped = rgb_full.crop((left, top, left + side, top + side))
        else:
            rgb_cropped = rgb_full
        rgb = np.asarray(rgb_cropped.resize((256, 256), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0

    gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    sat = np.max(rgb, axis=2) - np.min(rgb, axis=2)

    yy, xx = np.mgrid[0:256, 0:256]
    dy = (yy - 127.5) / 120.0
    dx = (xx - 127.5) / 120.0
    r = np.hypot(dx, dy)
    theta = np.arctan2(dy, dx)

    gy, gx = np.gradient(gray)
    grad_r = np.abs(gx * np.cos(theta) + gy * np.sin(theta))
    grad_t = np.abs(-gx * np.sin(theta) + gy * np.cos(theta))
    grad_mag = np.hypot(gx, gy)

    # 4 Diagonal Quadrant Masks (avoiding 0/90/180/270 deg where square borders live)
    abs_cos = np.abs(np.cos(theta))
    abs_sin = np.abs(np.sin(theta))
    diag_mask = (abs_cos >= 0.36) & (abs_sin >= 0.36)
    q_masks = [
        diag_mask & (dx > 0) & (dy > 0),
        diag_mask & (dx < 0) & (dy > 0),
        diag_mask & (dx < 0) & (dy < 0),
        diag_mask & (dx > 0) & (dy < 0),
    ]
    cardinal_mask = (abs_cos >= 0.92) | (abs_sin >= 0.92)

    # Multi-scale search for optimal outer 12" disc radius R_disc in [0.68..0.98]
    best_r_disc = 0.92
    best_dual_circle_score = -1.0
    best_active_quads = 0
    best_rim_step = 0.0
    best_label_step = 0.0
    best_label_wax_dist = 0.0
    best_corner_wax_dist = 0.0
    best_corner_std = 1.0

    for r_cand in (0.70, 0.74, 0.78, 0.82, 0.86, 0.90, 0.94, 0.98):
        rim_diag_band = (r >= r_cand - 0.028) & (r <= r_cand + 0.028) & diag_mask
        rim_card_band = (r >= r_cand - 0.028) & (r <= r_cand + 0.028) & cardinal_mask

        # Pure radial edge energy along diagonal arcs
        diag_rad_e = float(np.mean(np.maximum(0.0, grad_r[rim_diag_band] - 0.55 * grad_t[rim_diag_band])))
        card_rad_e = float(np.mean(grad_r[rim_card_band])) + 1e-6

        # Evaluate how many of the 4 diagonal quadrants show a genuine disc-to-background transition
        active_quads = 0
        q_dists: list[float] = []
        q_stds_out: list[float] = []
        for qm in q_masks:
            in_q = (r >= r_cand - 0.15) & (r <= r_cand - 0.035) & qm
            out_q = (r >= r_cand + 0.04) & (r <= min(1.32, r_cand + 0.22)) & qm
            rim_q = (r >= r_cand - 0.028) & (r <= r_cand + 0.028) & qm
            if not np.any(in_q) or not np.any(out_q):
                continue
            mean_in = np.mean(rgb[in_q], axis=0)
            mean_out = np.mean(rgb[out_q], axis=0)
            dist_q = float(np.linalg.norm(mean_in - mean_out))
            std_out_q = float(np.mean(np.std(rgb[out_q], axis=0)))
            rim_e_q = float(np.mean(grad_r[rim_q])) if np.any(rim_q) else 0.0
            q_dists.append(dist_q)
            q_stds_out.append(std_out_q)
            # Quadrant is active if there is a color step OR a clear rim bevel edge (for clear/milky vinyl)
            if dist_q >= 0.048 or rim_e_q >= 0.017:
                active_quads += 1

        median_q_dist = float(np.median(q_dists)) if q_dists else 0.0
        median_q_std = float(np.median(q_stds_out)) if q_stds_out else 0.25

        # Concentric 4" center label at R_label ≈ r_cand / 3.0
        r_lbl = r_cand / 3.0
        lbl_band = (r >= r_lbl - 0.042) & (r <= r_lbl + 0.045)
        lbl_in = (r >= 0.06) & (r <= max(0.14, r_lbl - 0.03))
        wax_mid = (r >= r_lbl + 0.05) & (r <= r_cand - 0.06)

        lbl_step_e = float(np.mean(np.maximum(0.0, grad_r[lbl_band] - 0.45 * grad_t[lbl_band])))
        lbl_wax_d = float(np.linalg.norm(np.mean(rgb[lbl_in], axis=0) - np.mean(rgb[wax_mid], axis=0)))

        # Color-in-Color ("Milky in Clear") inner-wax to outer-wax radial transition bonus
        wax_inner_half = (r >= r_lbl + 0.04) & (r <= r_cand * 0.62)
        wax_outer_half = (r > r_cand * 0.62) & (r <= r_cand - 0.05)
        color_in_color_dist = float(
            np.linalg.norm(np.mean(rgb[wax_inner_half], axis=0) - np.mean(rgb[wax_outer_half], axis=0))
        )

        # Combine into dual-circle score for candidate radius r_cand
        quad_factor = 1.0 if active_quads >= 3 else (0.55 if active_quads == 2 else 0.15)
        cand_score = quad_factor * (
            min(0.28, diag_rad_e * 8.5)
            + min(0.24, median_q_dist * 0.55)
            + max(0.0, min(0.18, (0.22 - median_q_std) * 1.1))
            + min(0.22, lbl_step_e * 6.0 + lbl_wax_d * 0.38)
            + min(0.08, color_in_color_dist * 0.35)
        )

        if cand_score > best_dual_circle_score:
            best_dual_circle_score = cand_score
            best_r_disc = r_cand
            best_active_quads = active_quads
            best_rim_step = diag_rad_e
            best_label_step = lbl_step_e
            best_label_wax_dist = lbl_wax_d
            best_corner_wax_dist = median_q_dist
            best_corner_std = median_q_std

    # Evaluate canonical masks at the detected best_r_disc
    r_lbl_best = best_r_disc / 3.0
    spindle_mask = r <= 0.042
    oversized_spindle_ring = (r > 0.052) & (r <= 0.115)
    label_mask = (r > 0.06) & (r <= max(0.15, r_lbl_best - 0.02))
    wax_annulus_mask = (r > r_lbl_best + 0.04) & (r <= best_r_disc - 0.05)
    outer_rim_mask = (r > best_r_disc - 0.03) & (r <= best_r_disc + 0.03)
    corner_bg_mask = r > max(1.04, best_r_disc + 0.06)

    spindle_contrast = float(abs(np.mean(gray[spindle_mask]) - np.mean(gray[label_mask])))
    oversized_spindle_step = float(np.mean(grad_r[oversized_spindle_ring]))

    wax_radial_energy = float(np.mean(grad_r[wax_annulus_mask]))
    wax_tangential_energy = float(np.mean(grad_t[wax_annulus_mask])) + 1e-6
    rim_radial_energy = float(np.mean(grad_r[outer_rim_mask & diag_mask]))
    circularity_ratio = (rim_radial_energy + 0.5 * best_label_step + 0.35 * wax_radial_energy) / (
        wax_tangential_energy * 0.65 + 0.012
    )

    # Check for high-frequency text / graphic clutter inside the wax annulus (characteristic of
    # zoomed 4" center labels AND square 12x12" lyric inserts / tracklist back covers)
    wax_grad_mag = float(np.mean(grad_mag[wax_annulus_mask]))
    label_grad_mag = float(np.mean(grad_mag[label_mask]))
    wax_luma = float(np.mean(gray[wax_annulus_mask]))
    corner_luma = float(np.mean(gray[corner_bg_mask]))

    # Check if a strong circle exists at r in [0.55..0.88] with dark smooth vinyl in corners
    # (Classic signature of a zoomed-in 4" paper center label surrounded by black/dark vinyl)
    outer_label_circle_e = float(np.mean(grad_r[(r >= 0.56) & (r <= 0.88) & diag_mask]))
    is_zoomed_label_on_vinyl = bool(
        best_corner_std < 0.095
        and corner_luma < 0.28
        and wax_luma > corner_luma + 0.14
        and wax_grad_mag > 0.036
        and outer_label_circle_e > best_label_step * 1.15
    )

    # Also catch full-bleed zoomed label scans where text fills the annulus and spindle hole is large
    is_full_bleed_label_scan = bool(
        (best_label_wax_dist < 0.085 and best_label_step < 0.018 and wax_grad_mag > 0.038)
        or (oversized_spindle_step > 0.042 and best_label_wax_dist < 0.11 and wax_grad_mag > label_grad_mag * 0.85)
    )
    is_zoomed_label_scan = is_zoomed_label_on_vinyl or is_full_bleed_label_scan

    # Detect square lyric sheets / inner sleeves / back covers:
    # 1. Fewer than 3 diagonal quadrants show a circular rim step, OR
    # 2. High-frequency text/graphic edges in the wax annulus exceed the 4" label and lack a 1/3 label step
    diag_continuation_dist = float(
        np.linalg.norm(
            np.mean(rgb[(r >= 0.72) & (r <= 0.88) & diag_mask], axis=0)
            - np.mean(rgb[(r >= 1.04) & (r <= 1.24) & diag_mask], axis=0)
        )
    )
    is_square_insert_or_sleeve = bool(
        best_active_quads < 3
        or (
            diag_continuation_dist < 0.042
            and best_rim_step < 0.015
            and best_label_wax_dist < 0.12
        )
        or (
            wax_grad_mag > 0.052
            and wax_grad_mag >= label_grad_mag * 0.92
            and best_label_step < 0.022
            and best_corner_wax_dist < 0.14
        )
    )

    # Optional Variant Color Match Bonus when expected_wax_hex is a colored variant
    variant_color_bonus = 0.0
    wax_mean_rgb = np.mean(rgb[wax_annulus_mask], axis=0)
    wax_mean_sat = float(np.mean(sat[wax_annulus_mask]))
    if expected_wax_hex and expected_wax_hex not in ("#18181b", "#cbd5e1", "#e2e8f0", "#f1f5f9", "#f8fafc"):
        target_rgb = np.asarray(_hex_to_rgb01(expected_wax_hex), dtype=np.float32)
        # Normalize chroma direction to compare hue regardless of lighting brightness
        wax_norm = wax_mean_rgb / (np.linalg.norm(wax_mean_rgb) + 1e-6)
        tgt_norm = target_rgb / (np.linalg.norm(target_rgb) + 1e-6)
        chroma_sim = float(np.dot(wax_norm, tgt_norm))
        if chroma_sim > 0.88 and wax_mean_sat > 0.12:
            variant_color_bonus = min(0.12, (chroma_sim - 0.85) * 0.8 + wax_mean_sat * 0.15)

    score = (
        best_dual_circle_score
        + min(0.14, circularity_ratio * 0.12)
        + min(0.08, spindle_contrast * 0.28)
        + variant_color_bonus
    )

    if is_zoomed_label_scan:
        score *= 0.38
    elif is_square_insert_or_sleeve:
        score *= 0.45

    score = round(min(1.0, max(0.0, score)), 4)

    is_pressing = bool(
        score >= 0.46
        and best_active_quads >= 3
        and not is_zoomed_label_scan
        and not is_square_insert_or_sleeve
        and (best_label_wax_dist > 0.055 or best_label_step > 0.015 or best_rim_step > 0.018)
    )

    reason = "deterministic_annular_cv_match"
    if not is_pressing:
        if is_zoomed_label_scan:
            reason = "rejected_zoomed_center_label_scan"
        elif is_square_insert_or_sleeve:
            reason = "rejected_square_insert_or_sleeve"
        else:
            reason = "below_annular_threshold"

    return {
        "is_pressing": is_pressing,
        "is_zoomed_label_scan": is_zoomed_label_scan,
        "is_square_insert_or_sleeve": is_square_insert_or_sleeve,
        "detected_disc_radius": round(best_r_disc, 3),
        "active_diagonal_quadrants": best_active_quads,
        "score": score,
        "aspect_ratio": round(aspect, 3),
        "corner_std": round(best_corner_std, 4),
        "corner_wax_dist": round(best_corner_wax_dist, 4),
        "circularity_ratio": round(circularity_ratio, 4),
        "label_wax_dist": round(best_label_wax_dist, 4),
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
    best_method = "cover_fallback"
    num_imgs = len(images)

    for idx, img in enumerate(images):
        uri = img.get("uri") or img.get("resource_url") or ""
        uri150 = img.get("uri150") or uri
        w = int(img.get("width") or 600)
        h = int(img.get("height") or 600)
        aspect = w / float(h) if h else 1.0
        is_square_or_43 = 0.68 <= aspect <= 1.48
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

        # Guideline 13.8 Positional Prior:
        # In 5+ image releases (like 35668090 and 16610055), [0]=Front, [1]=Back,
        # [2,3]=Center Labels or Lyric Sheet/Inner Sleeve, and [4,5]=Full 12" Vinyl Pressing!
        if idx == primary_idx and not is_no_cover:
            role = "front_cover"
            pos_score = 0.05
        elif not is_square_or_43 and aspect > 1.52:
            role = "gatefold_spread"
            pos_score = 0.0
        else:
            if is_no_cover and idx == 0:
                role = "pressing_or_label"
                pos_score = 0.80
            elif num_imgs >= 5:
                if idx == 1:
                    role = "back_cover" if not is_gatefold else "gatefold_inner"
                    pos_score = 0.20
                elif idx in (2, 3):
                    role = "label_or_insert_candidate" if (is_gatefold or has_insert_or_sheet or num_imgs >= 6) else "pressing_candidate"
                    pos_score = 0.52 if idx == 2 else 0.56
                elif idx in (4, 5):
                    role = "pressing_disc"
                    pos_score = 0.88 if idx == 4 else 0.86
                else:
                    role = "pressing_candidate"
                    pos_score = 0.74
            elif is_gatefold:
                if idx == 1:
                    role = "gatefold_inner"
                    pos_score = 0.22
                elif idx == 2 and num_imgs == 4:
                    role = "back_cover"
                    pos_score = 0.30
                elif idx >= 3:
                    role = "pressing_disc"
                    pos_score = 0.86
                else:
                    role = "pressing_candidate"
                    pos_score = 0.60
            else:
                if idx == 1 and num_imgs >= 3:
                    role = "back_cover"
                    pos_score = 0.30
                elif idx == 1 and num_imgs == 2:
                    has_color_code = wax_preview.get("pattern") != "black"
                    role = "pressing_candidate" if (has_color_code or is_square_or_43) else "back_cover"
                    pos_score = 0.72 if is_near_square else 0.58
                elif idx == 2 and num_imgs == 4:
                    role = "pressing_candidate"
                    pos_score = 0.74
                elif idx == 3 and num_imgs == 4:
                    role = "pressing_disc"
                    pos_score = 0.86
                elif idx >= 2:
                    role = "pressing_disc"
                    pos_score = 0.84

        if img_bytes is not None and (idx != primary_idx or is_no_cover):
            cv_details = score_image_pixels_deterministic(img_bytes, expected_wax_hex=expected_wax_hex)
            if cv_details.get("reason") == "cv_deps_unavailable":
                combined_score = pos_score
                method = "guideline_13_8_positional"
            elif cv_details.get("is_pressing"):
                role = "pressing_disc"
                # Pixel CV carries 78% weight when it positively verifies a 12" vinyl disc
                combined_score = 0.78 * float(cv_details["score"]) + 0.22 * max(pos_score, 0.70)
                method = "deterministic_annular_cv+guideline_13_8"
            elif cv_details.get("is_zoomed_label_scan"):
                role = "center_label_closeup"
                combined_score = 0.30 * float(cv_details.get("score", 0.0)) + 0.15 * pos_score
                method = "rejected_zoomed_center_label_scan"
            elif cv_details.get("is_square_insert_or_sleeve"):
                if role == "pressing_disc":
                    role = "insert_or_sleeve"
                combined_score = 0.35 * float(cv_details.get("score", 0.0)) + 0.20 * pos_score
                method = "rejected_square_insert_or_sleeve"
            else:
                combined_score = 0.65 * float(cv_details.get("score", 0.0)) + 0.35 * pos_score
                method = "guideline_13_8_positional"
        else:
            combined_score = pos_score
            method = "guideline_13_8_positional"

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

        if (idx != primary_idx or is_no_cover) and combined_score >= 0.45 and combined_score > best_pressing_score:
            best_pressing_score = combined_score
            best_pressing_idx = idx
            best_method = method

    # Fallback: select the highest-scoring non-cover candidate image when len(classified) > 1
    if best_pressing_idx < 0 and len(classified) > 1:
        candidates = [
            c for c in classified
            if c["index"] != primary_idx
            and c.get("role") != "gatefold_spread"
            and not (c.get("cv_metrics") or {}).get("is_zoomed_label_scan", False)
            and float(c.get("deterministic_score") or 0.0) >= 0.20
        ]
        if not candidates:
            candidates = [c for c in classified if c["index"] != primary_idx]
        if candidates:
            best_cand = max(
                candidates,
                key=lambda c: (
                    1 if (c.get("cv_metrics") or {}).get("is_pressing") else 0,
                    0 if (c.get("cv_metrics") or {}).get("is_square_insert_or_sleeve") else 1,
                    1 if c.get("role") in ("pressing_disc", "pressing_candidate") else 0,
                    float(c.get("deterministic_score") or 0.0),
                    int(c.get("index") or 0),
                ),
            )
            best_pressing_idx = int(best_cand["index"])
            best_pressing_score = float(best_cand["deterministic_score"])
            best_method = "auto_best_candidate_fallback"

    # Tier 1: Check explicit override in data/overrides.json
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
                is_manual_pin = True
        elif isinstance(ov, int) and 0 <= ov < len(images):
            ov_idx = ov
            ov_url = images[ov_idx].get("uri") or images[ov_idx].get("resource_url") or ""
            is_manual_pin = True
        elif isinstance(ov, str) and ov:
            ov_url = ov
            ov_idx = next(
                (i for i, im in enumerate(images) if (im.get("uri") or im.get("resource_url")) == ov),
                -1,
            )
            if ov_idx < 0:
                m_idx = re.search(r"img_(\d+)\.jpg", ov)
                if m_idx and 0 <= int(m_idx.group(1)) < len(images):
                    ov_idx = int(m_idx.group(1))

        # If ov was an auto-saved URL string (not an explicit manual index pin),
        # allow a much higher-scoring CV-verified pressing image (like img_4/img_5) to supersede a bad old pick!
        if ov_url and ov_idx >= 0:
            ov_cv_score = float(classified[ov_idx].get("deterministic_score") or 0.0) if 0 <= ov_idx < len(classified) else 0.0
            if (
                not is_manual_pin
                and best_pressing_idx >= 0
                and best_pressing_idx != ov_idx
                and best_pressing_score >= ov_cv_score + 0.08
            ):
                # Supersede stale auto-override with the superior CV-detected pressing image
                pass
            else:
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

    res = {
        "cover_image_url": cover_url,
        "pressing_image_url": pressing_url,
        "center_label_image_url": center_label_url,
        "display_thumbnail_url": local_p_rel or pressing_url or local_cover_rel or cover_url,
        "has_pressing_photo": bool(pressing_url),
        "selected_index": best_pressing_idx,
        "selected_score": round(best_pressing_score, 4) if best_pressing_idx >= 0 else 0.0,
        "detection_method": best_method,
        "classified_images": classified,
    }
    if local_cover_rel:
        res["local_cover_image_url"] = local_cover_rel
    if local_p_rel:
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