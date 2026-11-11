#!/usr/bin/env python3
"""Unit tests for the deterministic pressing image detector & wax variant parser."""

from __future__ import annotations

import io
import pathlib
import sys
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

from detect_pressing_image import (
    parse_wax_variant,
    score_image_pixels_deterministic,
    select_release_images_deterministic,
)


def _make_synthetic_vinyl_pressing_png() -> bytes:
    yy, xx = np.mgrid[0:256, 0:256]
    dy = (yy - 127.5) / 120.0
    dx = (xx - 127.5) / 120.0
    r = np.hypot(dx, dy)
    theta = np.arctan2(dy, dx)

    img = np.zeros((256, 256, 3), dtype=np.uint8)
    img[r > 1.0] = [18, 18, 22]

    wax_mask = (r > 0.33) & (r <= 1.0)
    groove_mod = (np.sin(r * 160.0) * 18.0 + np.cos(theta * 12.0) * 22.0).astype(np.int16)
    img[wax_mask, 0] = np.clip(145 + groove_mod[wax_mask], 0, 255).astype(np.uint8)
    img[wax_mask, 1] = np.clip(45 + groove_mod[wax_mask], 0, 255).astype(np.uint8)
    img[wax_mask, 2] = np.clip(235 + groove_mod[wax_mask], 0, 255).astype(np.uint8)

    label_mask = (r > 0.04) & (r <= 0.33)
    img[label_mask] = [32, 32, 38]
    img[r <= 0.04] = [235, 235, 240]

    buf = io.BytesIO()
    Image.fromarray(img, mode="RGB").save(buf, format="PNG")
    return buf.getvalue()


def _make_synthetic_sleeve_cover_png() -> bytes:
    rng = np.random.default_rng(42)
    img = rng.integers(20, 230, size=(256, 256, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(img, mode="RGB").save(buf, format="PNG")
    return buf.getvalue()


class TestDeterministicDetector(unittest.TestCase):
    def test_wax_variant_parser(self) -> None:
        spec = parse_wax_variant("LP, Album, Ltd, RM, RP, Pur", "never played", release_id=17583742)
        self.assertEqual(spec["primary_color"], "#8b2cf5")
        self.assertEqual(spec["color_name"], "Purple")
        self.assertTrue(spec["is_limited"])

        splatter_spec = parse_wax_variant(
            "LP, Album, Ltd, Cle",
            "Sealed Clear w/ Yellow and Purple Splatter",
            release_id=25089742,
        )
        self.assertEqual(splatter_spec["pattern"], "splatter")
        self.assertTrue(splatter_spec["translucent"])

    def test_annular_cv_distinguishes_pressing_from_sleeve(self) -> None:
        vinyl_bytes = _make_synthetic_vinyl_pressing_png()
        sleeve_bytes = _make_synthetic_sleeve_cover_png()

        vinyl_res = score_image_pixels_deterministic(vinyl_bytes)
        sleeve_res = score_image_pixels_deterministic(sleeve_bytes)

        self.assertTrue(vinyl_res["is_pressing"], f"Expected vinyl pressing to pass CV: {vinyl_res}")
        self.assertFalse(sleeve_res["is_pressing"], f"Expected busy sleeve cover to fail CV: {sleeve_res}")
        self.assertGreater(vinyl_res["score"], sleeve_res["score"])

    def test_guideline_13_8_selection(self) -> None:
        images = [
            {"type": "primary", "uri": "https://img.discogs.com/front.jpg", "width": 600, "height": 600},
            {"type": "secondary", "uri": "https://img.discogs.com/back.jpg", "width": 600, "height": 600},
            {"type": "secondary", "uri": "https://img.discogs.com/pressing.jpg", "width": 600, "height": 600},
        ]
        res = select_release_images_deterministic(
            images=images,
            formats=[{"name": "Vinyl", "qty": "1", "descriptions": ["LP", "Album", "Ltd", "Pur"]}],
            release_id=17583742,
        )
        self.assertTrue(res["has_pressing_photo"])
        self.assertEqual(res["selected_index"], 2)
        self.assertEqual(res["display_thumbnail_url"], "https://img.discogs.com/pressing.jpg")


if __name__ == "__main__":
    unittest.main()
