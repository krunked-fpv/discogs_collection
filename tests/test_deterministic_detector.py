#!/usr/bin/env python3
"""Unit tests for the deterministic pressing image detector & wax variant parser."""

from __future__ import annotations

import hashlib
import io
import json
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
from PIL import Image

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_html
from detect_pressing_image import (
    parse_wax_variant,
    score_image_pixels_deterministic,
    select_release_images_deterministic,
)
import pick_pressing_photo
import setup_discogs_token


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

    def test_wax_variant_explicit_format_overrides_multi_pressing_notes(self) -> None:
        spec = parse_wax_variant(
            "2xLP, Album, Ltd, Green Neon",
            "Red/Black Swirl or Neon Green (this)",
            release_id=3780990,
        )
        self.assertNotEqual(spec["pattern"], "marble")
        self.assertEqual(spec["pattern"], "split")
        self.assertEqual(spec["color_name"], "Emerald Green")
        self.assertTrue(spec["is_double_lp"])

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

    def test_setup_discogs_token_hash_scrubber_and_no_plaintext_secret(self) -> None:
        self.assertFalse(setup_discogs_token.is_old_exposed_token(""))
        self.assertFalse(setup_discogs_token.is_old_exposed_token("short"))
        self.assertFalse(setup_discogs_token.is_old_exposed_token("A" * 40))

        # Verify no tracked script, src/*, or index.html embeds the revoked legacy token
        tracked_files = [
            REPO_ROOT / "index.html",
            *sorted(p for p in (REPO_ROOT / "src").iterdir() if p.is_file()),
            *sorted((REPO_ROOT / "scripts").glob("*.py")),
        ]
        for rel in tracked_files:
            raw = rel.read_text(encoding="utf-8")
            for m in setup_discogs_token._CANDIDATE_TOKEN_RE.finditer(raw):
                self.assertFalse(
                    setup_discogs_token.is_old_exposed_token(m.group(0)),
                    f"Revoked legacy token found in {rel}",
                )

        # Verify hash-based scrubber strips matching 40-char tokens in a temp repo
        fake_leaked = "TestFakeDiscogsToken0123456789abcdefghij"
        self.assertEqual(len(fake_leaked), setup_discogs_token.OLD_EXPOSED_TOKEN_LEN)
        fake_hash = hashlib.sha256(fake_leaked.encode("utf-8")).hexdigest()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = pathlib.Path(tmpdir)
            (tmp_root / "scripts").mkdir()
            (tmp_root / "src").mkdir()
            (tmp_root / "index.html").write_text(f'<input value="{fake_leaked}">', encoding="utf-8")
            (tmp_root / "src" / "app.js").write_text(f'const t = "{fake_leaked}";\n', encoding="utf-8")
            (tmp_root / "scripts" / "sample.py").write_text(f'DEFAULT_TOKEN = "{fake_leaked}"\n', encoding="utf-8")

            with mock.patch.object(setup_discogs_token, "OLD_EXPOSED_TOKEN_SHA256", fake_hash):
                scrubbed = setup_discogs_token.scrub_exposed_token_from_repo(tmp_root)

            self.assertEqual(len(scrubbed), 3)
            self.assertNotIn(fake_leaked, (tmp_root / "index.html").read_text(encoding="utf-8"))
            self.assertNotIn(fake_leaked, (tmp_root / "src" / "app.js").read_text(encoding="utf-8"))
            self.assertIn('DEFAULT_TOKEN = ""', (tmp_root / "scripts" / "sample.py").read_text(encoding="utf-8"))

    def test_inject_into_index_html_preserves_markers_and_updates_kpis(self) -> None:
        src_html = REPO_ROOT / "index.html"
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_html = pathlib.Path(tmpdir) / "index.html"
            shutil.copy2(src_html, tmp_html)

            synthetic_collection = {
                "schema_version": "5.0.0",
                "username": "krunked",
                "synced_at_utc": "2026-11-18T20:00:00Z",
                "profile": {
                    "username": "krunked",
                    "num_collection": 2,
                    "pressing_photos_detected": 1,
                    "colored_or_special_variants": 2,
                    "collection_value": {
                        "minimum": "$10.00",
                        "median": "$25.00",
                        "maximum": "$50.00",
                        "formatted_total": "$25.00",
                    },
                },
                "records": [
                    {"release_id": 1001, "artist": "Band A", "title": "Album A", "flattening_status": "Need to be done"},
                    {"release_id": 1002, "artist": "Band B", "title": "Album B", "flattening_status": "Done"},
                ],
                "flattening_queue": {
                    "schema_version": "5.0.0",
                    "protocol": "Test protocol",
                    "need_to_be_done_release_ids": [1001],
                    "done_release_ids": [1002],
                    "unlisted_release_ids": [],
                },
            }

            ok = pick_pressing_photo.inject_into_index_html(
                html_path=tmp_html,
                collection_data=synthetic_collection,
                overrides_data={"1001": "assets/releases/1001/pressing.jpg"},
            )
            self.assertTrue(ok)

            out = tmp_html.read_text(encoding="utf-8")
            self.assertIn("<!-- BEGIN KRUNKED_COOKIE_VAULT_V1 -->", out)
            self.assertIn("<!-- END KRUNKED_COOKIE_VAULT_V1 -->", out)
            self.assertIn('<div id="kpi-total-records" class="text-lg sm:text-xl font-black text-white mt-0.5">2 LPs</div>', out)
            self.assertIn('id="kpi-flattening" class="text-lg sm:text-xl font-black text-cyan-300 mt-0.5">1 Queued / 1 Done</div>', out)
            self.assertIn('id="flatten-hidden-todo-ids" name="need_to_be_done_release_ids" value="1001"', out)
            self.assertIn('id="flatten-hidden-done-ids" name="done_release_ids" value="1002"', out)

    def test_modular_src_template_compiler_and_build_html(self) -> None:
        self.assertTrue(build_html.build_index_html(check_only=True))
        rendered_shell = pick_pressing_photo.render_template_from_src()
        self.assertIn("<!-- BEGIN KRUNKED_COOKIE_VAULT_V1 -->", rendered_shell)
        self.assertIn("/* __DISCOGS_COLLECTION_DATA_START__ */", rendered_shell)
        self.assertIn("const VERIFIED_YTM_RELEASE_MAP =", rendered_shell)
        self.assertIn("window.addEventListener('DOMContentLoaded', initApp);", rendered_shell)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = pathlib.Path(tmpdir)
            tmp_src = tmp_root / "src"
            shutil.copytree(REPO_ROOT / "src", tmp_src)

            # Edit modular CSS and JS in tmp_src and verify changes compile into a fresh index.html
            (tmp_src / "styles.css").write_text(
                (tmp_src / "styles.css").read_text(encoding="utf-8") + "\n.modular-test-selector { color: #00ffff; }\n",
                encoding="utf-8",
            )
            (tmp_src / "app.js").write_text(
                (tmp_src / "app.js").read_text(encoding="utf-8") + "\nwindow.__MODULAR_COMPILER_TEST__ = true;\n",
                encoding="utf-8",
            )

            tmp_data = tmp_root / "data"
            tmp_data.mkdir()
            col_path = tmp_data / "collection.json"
            ovr_path = tmp_data / "overrides.json"
            flat_path = tmp_data / "flattening_queue.json"
            out_html = tmp_root / "index.html"

            synthetic_collection = {
                "schema_version": "5.0.0",
                "username": "krunked",
                "synced_at_utc": "2026-11-18T21:00:00Z",
                "profile": {
                    "username": "krunked",
                    "num_collection": 1,
                    "pressing_photos_detected": 1,
                    "colored_or_special_variants": 1,
                    "collection_value": {
                        "minimum": "$20.00",
                        "median": "$40.00",
                        "maximum": "$80.00",
                        "formatted_total": "$40.00",
                    },
                },
                "records": [
                    {"release_id": 2001, "artist": "Periphery", "title": "Hail Stan", "flattening_status": "Done"},
                ],
            }
            col_path.write_text(json.dumps(synthetic_collection), encoding="utf-8")
            ovr_path.write_text(json.dumps({"2001": "assets/releases/2001/pressing.jpg"}), encoding="utf-8")
            flat_path.write_text(
                json.dumps(
                    {
                        "schema_version": "5.0.0",
                        "updated_at_utc": "2026-11-18T21:00:00Z",
                        "need_to_be_done_release_ids": [],
                        "done_release_ids": [2001],
                        "unlisted_release_ids": [],
                    }
                ),
                encoding="utf-8",
            )

            ok = build_html.build_index_html(
                src_dir=tmp_src,
                collection_path=col_path,
                overrides_path=ovr_path,
                flattening_path=flat_path,
                html_path=out_html,
            )
            self.assertTrue(ok)
            compiled = out_html.read_text(encoding="utf-8")
            self.assertIn(".modular-test-selector { color: #00ffff; }", compiled)
            self.assertIn("window.__MODULAR_COMPILER_TEST__ = true;", compiled)
            self.assertIn('<div id="kpi-total-records" class="text-lg sm:text-xl font-black text-white mt-0.5">1 LPs</div>', compiled)
            self.assertIn('id="flatten-hidden-done-ids" name="done_release_ids" value="2001"', compiled)


if __name__ == "__main__":
    unittest.main()
