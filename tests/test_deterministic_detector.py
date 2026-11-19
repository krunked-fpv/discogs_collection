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
    DEFAULT_FLATTENING_STATUS,
    _eval_offcenter_disc,
    build_flattening_queue_payload,
    parse_wax_variant,
    reconcile_flattening_state,
    reconcile_overrides_state,
    resolve_flattening_status,
    score_image_pixels_deterministic,
    select_release_images_deterministic,
)
import pick_pressing_photo
import setup_discogs_token
import sync_discogs
import validate_collection


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

    def test_flattening_auto_queue_rule_for_new_albums(self) -> None:
        self.assertEqual(DEFAULT_FLATTENING_STATUS, "Need to be done")
        # Empty / missing queue always defaults new albums into the Flattening Queue
        self.assertEqual(resolve_flattening_status("Currents", "The Way It Ends", 31082741, None), "Need to be done")
        self.assertEqual(resolve_flattening_status("Currents", "The Way It Ends", 31082741, {}), "Need to be done")

        queue = {
            "need_to_be_done_release_ids": [1001],
            "done_release_ids": [1002],
            "unlisted_release_ids": [1003],
        }
        self.assertEqual(resolve_flattening_status("Band A", "Album A", 1001, queue), "Need to be done")
        self.assertEqual(resolve_flattening_status("Band B", "Album B", 1002, queue), "Done")
        self.assertEqual(resolve_flattening_status("Band C", "Album C", 1003, queue), "Not Listed")
        # Brand-new release not in Done or Unlisted auto-queues for arrival inspection
        self.assertEqual(resolve_flattening_status("Band D", "Brand New LP", 99999999, queue), "Need to be done")

        # Payload builder defaults missing flattening_status to Need to be done and keeps explicit Not Listed
        payload = build_flattening_queue_payload(
            records=[
                {"release_id": 1002, "artist": "Band B", "title": "Album B", "flattening_status": "Done"},
                {"release_id": 1003, "artist": "Band C", "title": "Album C", "flattening_status": "Not Listed"},
                {"release_id": 1004, "artist": "Band D", "title": "Arrival LP"},
            ],
            base_queue={},
            updated_at_utc="2026-11-19T21:00:00Z",
        )
        self.assertEqual(payload["need_to_be_done_release_ids"], [1004])
        self.assertEqual(payload["done_release_ids"], [1002])
        self.assertEqual(payload["unlisted_release_ids"], [1003])

    def test_reconcile_flattening_state_preserves_empty_queue_and_no_stale_entry_leak(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = pathlib.Path(tmpdir)
            fq_path = tmp_root / "flattening_queue.json"
            html_path = tmp_root / "index.html"

            # Case 1: Newer JSON cleared queue to [] — must NOT resurrect stale todo ID from older HTML
            fq_path.write_text(
                json.dumps(
                    {
                        "updated_at_utc": "2026-11-19T22:00:00Z",
                        "need_to_be_done_release_ids": [],
                        "done_release_ids": [1001, 1002],
                        "unlisted_release_ids": [],
                    }
                ),
                encoding="utf-8",
            )
            html_path.write_text(
                '<form id="flattening-inline-form">'
                '<input type="hidden" id="flatten-hidden-updated-at" value="2026-11-19T20:00:00Z">'
                '<input type="hidden" id="flatten-hidden-todo-ids" value="1001">'
                '<input type="hidden" id="flatten-hidden-done-ids" value="1002">'
                '<input type="hidden" id="flatten-hidden-unlisted-ids" value="">'
                "</form>",
                encoding="utf-8",
            )
            reconciled = reconcile_flattening_state(fq_path, html_path)
            self.assertEqual(reconciled["need_to_be_done_release_ids"], [])
            self.assertEqual(resolve_flattening_status("Band A", "Album A", 1001, reconciled), "Done")

            # Case 2: Newer HTML moved 1001 to Done — must NOT leak older JSON's need_to_be_done_entries
            fq_path.write_text(
                json.dumps(
                    {
                        "updated_at_utc": "2026-11-19T18:00:00Z",
                        "need_to_be_done_release_ids": [1001],
                        "done_release_ids": [1002],
                        "unlisted_release_ids": [],
                        "need_to_be_done_entries": [
                            {"artist": "Band A", "album": "Album A", "release_ids": [1001]}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            html_path.write_text(
                '<form id="flattening-inline-form">'
                '<input type="hidden" id="flatten-hidden-updated-at" value="2026-11-19T23:00:00Z">'
                '<input type="hidden" id="flatten-hidden-todo-ids" value="">'
                '<input type="hidden" id="flatten-hidden-done-ids" value="1001,1002">'
                '<input type="hidden" id="flatten-hidden-unlisted-ids" value="">'
                "</form>",
                encoding="utf-8",
            )
            reconciled2 = reconcile_flattening_state(fq_path, html_path)
            self.assertEqual(reconciled2["need_to_be_done_release_ids"], [])
            self.assertEqual(resolve_flattening_status("Band A", "Album A", 1001, reconciled2), "Done")
            self.assertEqual(resolve_flattening_status("Band New", "Fresh Arrival", 1003, reconciled2), "Need to be done")

    def test_build_index_html_auto_queues_new_album_and_preserves_user_locked_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = pathlib.Path(tmpdir)
            tmp_data = tmp_root / "data"
            tmp_data.mkdir()
            col_path = tmp_data / "collection.json"
            ovr_path = tmp_data / "overrides.json"
            flat_path = tmp_data / "flattening_queue.json"
            out_html = tmp_root / "index.html"

            synthetic_collection = {
                "schema_version": "5.0.0",
                "username": "krunked",
                "synced_at_utc": "2026-11-19T21:00:00Z",
                "profile": {
                    "username": "krunked",
                    "num_collection": 3,
                    "pressing_photos_detected": 1,
                    "colored_or_special_variants": 3,
                    "collection_value": {
                        "minimum": "$30.00",
                        "median": "$60.00",
                        "maximum": "$90.00",
                        "formatted_total": "$60.00",
                    },
                },
                "records": [
                    {"release_id": 2001, "artist": "Periphery", "title": "Hail Stan", "flattening_status": "Done"},
                    {"release_id": 2002, "artist": "Northlane", "title": "Alien", "flattening_status": "Not Listed"},
                    {"release_id": 2003, "artist": "Currents", "title": "The Way It Ends"},
                ],
            }
            col_path.write_text(json.dumps(synthetic_collection), encoding="utf-8")
            ovr_path.write_text(json.dumps({"2001": "assets/releases/2001/pressing.jpg"}), encoding="utf-8")
            flat_path.write_text(
                json.dumps(
                    {
                        "schema_version": "5.0.0",
                        "updated_at_utc": "2026-11-19T21:00:00Z",
                        "need_to_be_done_release_ids": [],
                        "done_release_ids": [2001],
                        "unlisted_release_ids": [2002],
                    }
                ),
                encoding="utf-8",
            )
            # Pre-seed an existing index.html carrying a user_locked pin
            out_html.write_text(
                'window.__DISCOGS_OVERRIDES__ = {"2001": {"uri": "assets/releases/2001/img_5.jpg", "pressing_image_index": 5, "user_locked": true}};\n'
                "window.__DISCOGS_COLLECTION__ = {};\n",
                encoding="utf-8",
            )

            ok = build_html.build_index_html(
                src_dir=REPO_ROOT / "src",
                collection_path=col_path,
                overrides_path=ovr_path,
                flattening_path=flat_path,
                html_path=out_html,
            )
            self.assertTrue(ok)

            # Brand-new LP 2003 was automatically queued into Need to be done
            updated_col = json.loads(col_path.read_text(encoding="utf-8"))
            by_id = {r["release_id"]: r["flattening_status"] for r in updated_col["records"]}
            self.assertEqual(by_id, {2001: "Done", 2002: "Not Listed", 2003: "Need to be done"})
            self.assertEqual(updated_col["profile"]["flattening_need_to_be_done"], 1)
            self.assertEqual(updated_col["profile"]["flattening_done"], 1)

            updated_fq = json.loads(flat_path.read_text(encoding="utf-8"))
            self.assertEqual(updated_fq["need_to_be_done_release_ids"], [2003])
            self.assertEqual(updated_fq["done_release_ids"], [2001])
            self.assertEqual(updated_fq["unlisted_release_ids"], [2002])

            updated_ov = json.loads(ovr_path.read_text(encoding="utf-8"))
            self.assertTrue(updated_ov["2001"]["user_locked"])
            self.assertEqual(updated_ov["2001"]["pressing_image_index"], 5)

            compiled = out_html.read_text(encoding="utf-8")
            self.assertIn("const DEFAULT_FLATTENING_STATUS = 'Need to be done';", compiled)
            self.assertIn('id="flatten-hidden-todo-ids" name="need_to_be_done_release_ids" value="2003"', compiled)
            self.assertIn('id="flatten-hidden-done-ids" name="done_release_ids" value="2001"', compiled)
            self.assertIn('id="flatten-hidden-unlisted-ids" name="unlisted_release_ids" value="2002"', compiled)
            self.assertIn('id="kpi-flattening" class="text-lg sm:text-xl font-black text-cyan-300 mt-0.5">1 Queued / 1 Done</div>', compiled)
            self.assertIn('id="spin-badge-all" class="text-[10px] font-mono-tech font-bold px-1.5 py-0.5 rounded bg-slate-950/80 text-cyan-300 border border-cyan-500/30">ALL LPS (3)</span>', compiled)
            self.assertNotIn("r.flattening_status !== 'Need to be done'", compiled)
            self.assertNotIn("Stylus Guard Linked", compiled)

    def test_inject_into_index_html_safe_script_escaping_and_scoped_storage_eviction(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_html = pathlib.Path(tmpdir) / "index.html"
            synthetic_collection = {
                "schema_version": "5.0.0",
                "username": r"user\1<img src=x>",
                "synced_at_utc": "2026-11-19T22:00:00Z",
                "profile": {
                    "username": r"user\1<img src=x>",
                    "num_collection": 1,
                    "pressing_photos_detected": 0,
                    "colored_or_special_variants": 1,
                    "collection_value": {
                        "minimum": "$10.00",
                        "median": "$20.00",
                        "maximum": "$30.00",
                        "formatted_total": "$20.00",
                    },
                },
                "records": [
                    {
                        "release_id": 5001,
                        "artist": "Test Artist",
                        "title": "Album </script><script>alert(1)</script> <!-- comment -->",
                        "flattening_status": "Need to be done",
                    }
                ],
            }

            ok = pick_pressing_photo.inject_into_index_html(
                html_path=tmp_html,
                collection_data=synthetic_collection,
                overrides_data={},
                src_dir=REPO_ROOT / "src",
            )
            self.assertTrue(ok)
            out = tmp_html.read_text(encoding="utf-8")
            self.assertNotIn("Album </script><script>alert(1)</script>", out)
            self.assertIn(r"Album <\/script><script>alert(1)<\/script> \u003c!-- comment -->", out)
            self.assertIn("Folder 0 • user\\1&lt;img src=x&gt;", out)
            self.assertNotIn("Object.keys(localStorage)", out)
            self.assertIn("krunked_pressing_overrides_v2_2", out)
            self.assertIn("__savedFq.updated_at_utc > __pySyncStamp", out)

    def test_sync_discogs_aborts_on_mid_pagination_failure_and_scopes_auth_header(self) -> None:
        import urllib.error

        # 1. DiscogsClient.download_bytes must never leak PAT to CDN hosts or wipe self.token on 403
        token = "SecretDiscogsPAT123456789012345678901234"
        client = sync_discogs.DiscogsClient(token=token)
        seen_headers: list[tuple[str, dict[str, str]]] = []

        def fake_urlopen_cdn(req, timeout=25):
            hdrs = {k.lower(): v for k, v in req.header_items()}
            seen_headers.append((req.full_url, hdrs))
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen_cdn):
            res = client.download_bytes("https://i.discogs.com/some/pressing.jpg")
        self.assertIsNone(res)
        self.assertEqual(len(seen_headers), 1)
        self.assertNotIn("authorization", seen_headers[0][1])
        self.assertEqual(client.token, token)

        # Also verify api.discogs.com sends auth once, retries without auth on 403, and keeps client.token intact
        api_seen: list[dict[str, str]] = []

        def fake_urlopen_api(req, timeout=25):
            hdrs = {k.lower(): v for k, v in req.header_items()}
            api_seen.append(hdrs)
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen_api):
            res_api = client.download_bytes("https://api.discogs.com/images/test.jpg")
        self.assertIsNone(res_api)
        self.assertEqual(len(api_seen), 2)
        self.assertEqual(api_seen[0].get("authorization"), f"Discogs token={token}")
        self.assertNotIn("authorization", api_seen[1])
        self.assertEqual(client.token, token)

        # 2. Mid-pagination failure must abort safely without pruning existing overrides/cache
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = pathlib.Path(tmpdir)
            cache_path = tmp_root / "releases_cache.json"
            overrides_path = tmp_root / "overrides.json"
            flattening_path = tmp_root / "flattening_queue.json"
            assets_dir = tmp_root / "assets"
            html_path = tmp_root / "index.html"

            cache_path.write_text(json.dumps({"999": {"id": 999, "title": "Preserved LP"}}), encoding="utf-8")
            overrides_path.write_text(json.dumps({"999": {"uri": "assets/releases/999/pressing.jpg", "user_locked": True}}), encoding="utf-8")

            pages_requested: list[int] = []

            def fake_get_json(url: str, params: dict | None = None):
                if "/collection/folders/0/releases" in url:
                    p = int((params or {}).get("page") or 1)
                    pages_requested.append(p)
                    if p == 1:
                        return {
                            "pagination": {"page": 1, "pages": 2, "items": 2},
                            "releases": [{"id": 999, "basic_information": {"id": 999, "title": "Preserved LP"}}],
                        }
                    raise RuntimeError("Simulated HTTP 502 on page 2")
                return {}

            col_path = tmp_root / "collection.json"
            col_path.write_text(json.dumps({"username": "krunked", "records": [{"release_id": 999}]}), encoding="utf-8")

            with mock.patch.object(client, "get_json", side_effect=fake_get_json):
                col_data, summary = sync_discogs.fetch_full_collection(
                    client=client,
                    username="krunked",
                    cache_path=cache_path,
                    overrides_path=overrides_path,
                    flattening_path=flattening_path,
                    download_dir=assets_dir,
                    analyze_pixels=False,
                    existing_collection_path=col_path,
                )

            self.assertEqual(pages_requested, [1, 2])
            self.assertEqual(col_data["records"], [])
            self.assertEqual(summary["removed_records"], [])
            self.assertIn("999", json.loads(overrides_path.read_text(encoding="utf-8")))
            self.assertIn("999", json.loads(cache_path.read_text(encoding="utf-8")))

    def test_mixed_override_keys_sort_and_validate_collection_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = pathlib.Path(tmpdir)
            col_path = tmp_root / "collection.json"
            ovr_path = tmp_root / "overrides.json"
            flat_path = tmp_root / "flattening_queue.json"
            out_html = tmp_root / "index.html"

            synthetic_collection = {
                "schema_version": "5.0.0",
                "username": "krunked",
                "synced_at_utc": "2026-11-19T22:00:00Z",
                "profile": {
                    "username": "krunked",
                    "num_collection": 1,
                    "pressing_photos_detected": 1,
                    "colored_or_special_variants": 1,
                    "collection_value": {
                        "minimum": "$10.00",
                        "median": "$20.00",
                        "maximum": "$30.00",
                        "formatted_total": "$20.00",
                    },
                },
                "records": [
                    {"release_id": 2001, "artist": "Periphery", "title": "Hail Stan", "flattening_status": "Done"},
                ],
            }
            col_path.write_text(json.dumps(synthetic_collection), encoding="utf-8")
            ovr_path.write_text(
                json.dumps({"_note": "metadata", "2001": "assets/releases/2001/pressing.jpg"}),
                encoding="utf-8",
            )
            flat_path.write_text(
                json.dumps(
                    {
                        "schema_version": "5.0.0",
                        "updated_at_utc": "2026-11-19T22:00:00Z",
                        "need_to_be_done_release_ids": [],
                        "done_release_ids": [2001],
                        "unlisted_release_ids": [],
                    }
                ),
                encoding="utf-8",
            )
            # Pre-seed index.html with a user_locked pin so build_index_html exercises overrides_merged sorting
            out_html.write_text(
                'window.__DISCOGS_OVERRIDES__ = {"2001": {"uri": "assets/releases/2001/img_2.jpg", "pressing_image_index": 2, "user_locked": true}};\n'
                "window.__DISCOGS_COLLECTION__ = {};\n",
                encoding="utf-8",
            )

            ok = build_html.build_index_html(
                src_dir=REPO_ROOT / "src",
                collection_path=col_path,
                overrides_path=ovr_path,
                flattening_path=flat_path,
                html_path=out_html,
            )
            self.assertTrue(ok)
            saved_ov_keys = list(json.loads(ovr_path.read_text(encoding="utf-8")).keys())
            self.assertEqual(saved_ov_keys, ["2001", "_note"])

            bad_col = tmp_root / "bad_collection.json"
            bad_col.write_text(
                json.dumps({"username": "krunked", "source_of_truth": "https://wrong.example", "records": []}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                validate_collection.validate_collection(bad_col)

    def test_bool_override_ignored_and_offcenter_empty_mask_safe(self) -> None:
        import warnings

        images = [
            {"type": "primary", "uri": "https://img.discogs.com/front.jpg", "width": 600, "height": 600},
            {"type": "secondary", "uri": "https://img.discogs.com/back.jpg", "width": 600, "height": 600},
            {"type": "secondary", "uri": "https://img.discogs.com/pressing.jpg", "width": 600, "height": 600},
        ]
        # bool is a subclass of int in Python; True must NOT be misinterpreted as image index 1
        res = select_release_images_deterministic(
            images=images,
            formats=[{"name": "Vinyl", "qty": "1", "descriptions": ["LP", "Album", "Ltd", "Pur"]}],
            release_id=17583742,
            overrides={"17583742": True},
        )
        self.assertEqual(res["selected_index"], 2)

        # Edge-heavy blank/wide-aspect image should never emit empty-slice RuntimeWarning or NaN
        blank_rgb = np.zeros((256, 256, 3), dtype=np.float32)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            off_res = _eval_offcenter_disc(blank_rgb, aspect=2.0)
        runtime_warns = [w for w in caught if issubclass(w.category, RuntimeWarning)]
        self.assertEqual(runtime_warns, [])
        self.assertIsNone(off_res)


if __name__ == "__main__":
    unittest.main()
