#!/usr/bin/env python3
"""Deterministic Pressing Image Classifier & Vinyl Wax Variant Parser.

Uses 100% deterministic rules (zero LLM / zero probabilistic guessing) to:
1. Identify which image in a Discogs Release `images[]` array depicts the
   physical vinyl pressing itself (vs. front sleeve cover, back cover tracklist,
   gatefold spread, or close-up paper center label).
2. Parse Discogs `formats[].descriptions`, `formats[].text`, and release notes
   into a deterministic `wax_spec` object for procedural vinyl rendering and
   filtering.

References:
- Discogs API Release Resource: https://www.discogs.com/developers/#page:database,header:database-release
- Discogs Database Guidelines 13.8 (Image Order): https://support.discogs.com/hc/en-us/articles/360005006874-Database-Guidelines-13-Images
"""

from __future__ import annotations

import hashlib
import io
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
    "vio": ("#6d28d9", "Violet", True),
    "violet": ("#6d28d9", "Violet", True),
    "pin": ("#ec4899", "Hot Pink", False),
    "pink": ("#ec4899", "Hot Pink", False),
    "mag": ("#d946ef", "Magenta", True),
    "magenta": ("#d946ef", "Magenta", True),
    "ora": ("#f97316", "Translucent Orange", True),
    "orange": ("#f97316", "Translucent Orange", True),
    "pea": ("#fb923c", "Peach Opaque", False),
    "peach": ("#fb923c", "Peach Opaque", False),
    "yel": ("#eab308", "Yellow", True),
    "yellow": ("#eab308", "Yellow", True),
    "can": ("#facc15", "Canary Yellow", False),
    "canary": ("#facc15", "Canary Yellow", False),
    "gold": ("#d97706", "Metallic Gold", False),
    "gre": ("#10b981", "Emerald Green", True),
    "green": ("#10b981", "Emerald Green", True),
    "aci": ("#84cc16", "Acid Green", True),
    "acid": ("#84cc16", "Acid Green", True),
    "neo": ("#ccff00", "Neon Highlighter", True),
    "neon": ("#ccff00", "Neon Highlighter", True),
    "blu": ("#2563eb", "Cobalt Blue", True),
    "blue": ("#2563eb", "Cobalt Blue", True),
    "ele": ("#06b6d4", "Electric Blue", True),
    "electric": ("#06b6d4", "Electric Blue", True),
    "lig": ("#38bdf8", "Light Sky Blue", True),
    "cle": ("#cbd5e1", "Crystal Clear", True),
    "clear": ("#cbd5e1", "Crystal Clear", True),
    "ult": ("#e2e8f0", "Ultra Clear", True),
    "mil": ("#f1f5f9", "Milky Clear", True),
    "milk": ("#f1f5f9", "Milky Clear", True),
    "gho": ("#94a3b8", "Ghostly Clear", True),
    "ghost": ("#94a3b8", "Ghostly Clear", True),
    "cok": ("#5eead4", "Coke Bottle Clear", True),
    "coke": ("#5eead4", "Coke Bottle Clear", True),
    "whi": ("#f8fafc", "Opaque White", False),
    "white": ("#f8fafc", "Opaque White", False),
    "bone": ("#fef3c7", "Bone White", False),
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
    "crimson": ("#dc2626", "Crimson Red", True),
    "ruby": ("#e11d48", "Ruby Red", True),
    "bla": ("#18181b", "180g Audiophile Black", False),
    "black": ("#18181b", "180g Audiophile Black", False),
}


def parse_wax_variant(
    format_str: str,
    comments: str = "",
    release_id: int | str = 0,
) -> dict[str, Any]:
    """Deterministically parses a Discogs format string + notes into a visual wax spec."""
    combined = f"{format_str} {comments}".strip()
    lower = combined.lower()

    tokens = [
        t.strip().lower()
        for t in re.split(r"[,()+/:\s-]+", format_str)
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
        ("red", "#dc2626", "Crimson Red", True),
        ("ruby", "#e11d48", "Ruby Red", True),
        ("purple", "#8b2cf5", "Purple", True),
        ("violet", "#6d28d9", "Violet", True),
        ("yellow", "#facc15", "Yellow", True),
        ("pink", "#ec4899", "Hot Pink", False),
        ("blue", "#2563eb", "Electric Blue", True),
        ("green", "#10b981", "Emerald Green", True),
        ("orange", "#f97316", "Translucent Orange", True),
        ("clear", "#cbd5e1", "Crystal Clear", True),
        ("white", "#f8fafc", "Opaque White", False),
        ("gold", "#eab308", "Metallic Gold", False),
        ("silver", "#94a3b8", "Silver", False),
        ("black", "#18181b", "180g Audiophile Black", False),
    ]
    for word, hex_c, label, trans in color_words:
        if re.search(rf"\b{word}\b", lower) and hex_c not in seen_hex:
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
    if re.search(r"splatter|starburst", lower):
        pattern = "splatter"
    elif re.search(r"in clear|color-in-color|bone in|pink in|black in|red in", lower):
        pattern = "color_in_color"
    elif re.search(r"\b(gal|galaxy|nebula|dus|dust|gho|ghost|smoke)\b", lower):
        pattern = "galaxy"
    elif re.search(r"\b(swirl|marb|marble|hou|aci|acid)\b", lower):
        pattern = "marble"
    elif re.search(r"\b(split|smash|twister|flip|neo|neon)\b", lower):
        pattern = "split"
    elif is_trans or re.search(r"\b(cle|ult|mil|cok|clear|translucent)\b", lower):
        pattern = "translucent"
    elif primary_hex == "#18181b":
        pattern = "black"
    else:
        pattern = "solid_color"

    is_2lp = "2xlp" in lower or "2x12" in lower or "+ lp" in lower
    is_ltd = "ltd" in lower or "limited" in lower
    is_repress = "rp" in lower or "re" in lower

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


def score_image_pixels_deterministic(image_bytes: bytes) -> dict[str, Any]:
    """Deterministically scores an image for whether it shows a physical vinyl record pressing."""
    if not HAS_CV_DEPS:
        return {"is_pressing": False, "score": 0.0, "reason": "cv_deps_unavailable"}

    with Image.open(io.BytesIO(image_bytes)) as im:
        w, h = im.size
        aspect = w / float(h) if h else 0.0
        if aspect < 0.86 or aspect > 1.16:
            return {
                "is_pressing": False,
                "score": 0.05,
                "aspect_ratio": round(aspect, 3),
                "reason": "rejected_aspect_ratio_non_square",
            }
        rgb = np.asarray(im.convert("RGB").resize((256, 256), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0

    gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]

    yy, xx = np.mgrid[0:256, 0:256]
    dy = (yy - 127.5) / 120.0
    dx = (xx - 127.5) / 120.0
    r = np.hypot(dx, dy)

    spindle_mask = r <= 0.045
    label_mask = (r > 0.06) & (r <= 0.31)
    label_boundary_mask = (r > 0.29) & (r <= 0.37)
    wax_annulus_mask = (r > 0.38) & (r <= 0.92)
    outer_rim_mask = (r > 0.92) & (r <= 1.00)
    corner_bg_mask = r > 1.06

    corner_std = float(np.mean(np.std(rgb[corner_bg_mask], axis=0)))
    corner_mean = np.mean(rgb[corner_bg_mask], axis=0)
    wax_mean = np.mean(rgb[wax_annulus_mask], axis=0)
    corner_wax_dist = float(np.linalg.norm(corner_mean - wax_mean))

    gy, gx = np.gradient(gray)
    theta = np.arctan2(dy, dx)
    grad_r = np.abs(gx * np.cos(theta) + gy * np.sin(theta))
    grad_t = np.abs(-gx * np.sin(theta) + gy * np.cos(theta))

    rim_radial_energy = float(np.mean(grad_r[outer_rim_mask]))
    label_step_energy = float(np.mean(grad_r[label_boundary_mask]))
    wax_radial_energy = float(np.mean(grad_r[wax_annulus_mask]))
    wax_tangential_energy = float(np.mean(grad_t[wax_annulus_mask])) + 1e-6

    circularity_ratio = (rim_radial_energy + 0.5 * wax_radial_energy) / (wax_tangential_energy + 0.01)

    label_mean = np.mean(rgb[label_mask], axis=0)
    label_wax_dist = float(np.linalg.norm(label_mean - wax_mean))
    spindle_contrast = float(abs(np.mean(gray[spindle_mask]) - np.mean(gray[label_mask])))

    score = 0.0
    score += max(0.0, min(0.25, (0.18 - corner_std) * 1.6))
    score += min(0.25, corner_wax_dist * 0.45)
    score += min(0.25, circularity_ratio * 0.18)
    score += min(0.15, (label_wax_dist * 0.25) + (label_step_energy * 1.2))
    score += min(0.10, spindle_contrast * 0.35)

    score = round(min(1.0, max(0.0, score)), 4)
    is_pressing = bool(score >= 0.48 and corner_std < 0.22 and (label_wax_dist > 0.06 or label_step_energy > 0.018))

    return {
        "is_pressing": is_pressing,
        "score": score,
        "aspect_ratio": round(aspect, 3),
        "corner_std": round(corner_std, 4),
        "corner_wax_dist": round(corner_wax_dist, 4),
        "circularity_ratio": round(circularity_ratio, 4),
        "label_wax_dist": round(label_wax_dist, 4),
        "spindle_contrast": round(spindle_contrast, 4),
        "reason": "deterministic_annular_cv_match" if is_pressing else "below_annular_threshold",
    }


def select_release_images_deterministic(
    images: list[dict[str, Any]],
    formats: list[dict[str, Any]] | None = None,
    notes: str = "",
    release_id: int | str = 0,
    overrides: dict[str, Any] | None = None,
    downloaded_bytes_by_uri: dict[str, bytes] | None = None,
) -> dict[str, Any]:
    """Deterministically classifies a Discogs release's `images[]` array and selects the pressing image."""
    overrides = overrides or {}
    formats = formats or []
    downloaded_bytes_by_uri = downloaded_bytes_by_uri or {}

    if not images:
        return {
            "cover_image_url": "",
            "pressing_image_url": "",
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
    fmt_joined = " ".join(fmt_tokens + [notes]).lower()
    is_gatefold = "gatefold" in fmt_joined
    is_no_cover = "no cover" in fmt_joined or "generic" in fmt_joined

    primary_idx = next((i for i, img in enumerate(images) if img.get("type") == "primary"), 0)
    cover_url = images[primary_idx].get("uri") or images[primary_idx].get("resource_url") or ""

    rid_key = str(release_id)
    if rid_key in overrides:
        ov = overrides[rid_key]
        if isinstance(ov, dict) and "pressing_image_index" in ov:
            idx = int(ov["pressing_image_index"])
            if 0 <= idx < len(images):
                p_url = images[idx].get("uri") or images[idx].get("resource_url") or ""
                return {
                    "cover_image_url": cover_url,
                    "pressing_image_url": p_url,
                    "display_thumbnail_url": p_url or cover_url,
                    "has_pressing_photo": bool(p_url),
                    "selected_index": idx,
                    "selected_score": 1.0,
                    "detection_method": "override_index",
                    "classified_images": images,
                }
        elif isinstance(ov, str) and ov:
            return {
                "cover_image_url": cover_url,
                "pressing_image_url": ov,
                "display_thumbnail_url": ov,
                "has_pressing_photo": True,
                "selected_index": -1,
                "selected_score": 1.0,
                "detection_method": "override_url",
                "classified_images": images,
            }

    classified: list[dict[str, Any]] = []
    best_pressing_idx = -1
    best_pressing_score = -1.0
    best_method = "cover_fallback"

    for idx, img in enumerate(images):
        uri = img.get("uri") or img.get("resource_url") or ""
        w = int(img.get("width") or 600)
        h = int(img.get("height") or 600)
        aspect = w / float(h) if h else 1.0
        is_square = 0.88 <= aspect <= 1.12

        role = "secondary"
        pos_score = 0.0
        cv_details: dict[str, Any] = {}

        if idx == primary_idx and not is_no_cover:
            role = "front_cover"
            pos_score = 0.05
        elif not is_square and aspect > 1.25:
            role = "gatefold_spread"
            pos_score = 0.0
        else:
            if is_no_cover and idx == 0:
                role = "pressing_or_label"
                pos_score = 0.80
            elif is_gatefold:
                if idx == 1:
                    role = "gatefold_inner"
                    pos_score = 0.15
                elif idx == 2 and len(images) >= 4:
                    role = "back_cover"
                    pos_score = 0.20
                elif idx >= 3:
                    role = "pressing_disc"
                    pos_score = 0.82 if idx in (3, 4) else 0.65
            else:
                if idx == 1 and len(images) >= 3:
                    role = "back_cover"
                    pos_score = 0.18
                elif idx == 1 and len(images) == 2:
                    has_color_code = any(
                        tok.lower() in DISCOGS_COLOR_MAP
                        for tok in re.split(r"[,()+/:\s-]+", fmt_joined)
                        if tok.lower() not in ("bla", "black")
                    )
                    role = "pressing_candidate" if has_color_code else "back_cover"
                    pos_score = 0.62 if (has_color_code and is_square) else 0.22
                elif idx >= 2:
                    role = "pressing_disc"
                    pos_score = 0.85 if idx in (2, 3) else 0.70

        if uri in downloaded_bytes_by_uri and idx != primary_idx:
            cv_details = score_image_pixels_deterministic(downloaded_bytes_by_uri[uri])
            if cv_details.get("is_pressing"):
                combined_score = 0.65 * float(cv_details["score"]) + 0.35 * pos_score
                method = "deterministic_annular_cv+guideline_13_8"
            else:
                combined_score = 0.40 * float(cv_details.get("score", 0.0)) + 0.30 * pos_score
                method = "guideline_13_8_positional"
        else:
            combined_score = pos_score
            method = "guideline_13_8_positional"

        entry = {
            "index": idx,
            "uri": uri,
            "width": w,
            "height": h,
            "aspect_ratio": round(aspect, 3),
            "role": role,
            "deterministic_score": round(combined_score, 4),
            "cv_metrics": cv_details,
        }
        classified.append(entry)

        if idx != primary_idx and combined_score >= 0.55 and combined_score > best_pressing_score:
            best_pressing_score = combined_score
            best_pressing_idx = idx
            best_method = method

    pressing_url = classified[best_pressing_idx]["uri"] if best_pressing_idx >= 0 else ""

    return {
        "cover_image_url": cover_url,
        "pressing_image_url": pressing_url,
        "display_thumbnail_url": pressing_url if pressing_url else cover_url,
        "has_pressing_photo": bool(pressing_url),
        "selected_index": best_pressing_idx,
        "selected_score": round(best_pressing_score, 4) if best_pressing_idx >= 0 else 0.0,
        "detection_method": best_method,
        "classified_images": classified,
    }
