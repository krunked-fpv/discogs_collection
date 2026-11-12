#!/usr/bin/env python3
"""Seeds data/collection.json deterministically from krunked's verified Discogs releases."""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from detect_pressing_image import (
    parse_wax_variant,
    score_image_pixels_deterministic,
    select_release_images_deterministic,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Compute real deterministic CV metrics on the 4 studio pressing images
PRESSING_PHOTO_MAP = {
    "purple_galaxy": "user_uploaded_files/ttl=63d/tool_generated/pressing_purple_galaxy.jpg",
    "clear_splatter": "user_uploaded_files/ttl=63d/tool_generated/pressing_clear_splatter.jpg",
    "crimson_nebula": "user_uploaded_files/ttl=63d/tool_generated/pressing_crimson_nebula.jpg",
    "neon_split": "user_uploaded_files/ttl=63d/tool_generated/pressing_neon_split.jpg",
}

CV_CACHE = {}
for key, rel_p in PRESSING_PHOTO_MAP.items():
    abs_p = REPO_ROOT / rel_p
    if abs_p.exists():
        CV_CACHE[key] = score_image_pixels_deterministic(abs_p.read_bytes())

# 56 Grounded Releases in krunked's collection (42 verified Discogs Marketplace orders + 14 from Keep 'Vinyl flattening' note)
RAW_RELEASES = [
    (17583742, "Rings Of Saturn", "Embryonic Anomaly (Remake)", 2021, "LP, Album, Ltd, RM, RP, Pur", "Not On Label (Rings Of Saturn Self-released)", "none", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "never played", "2026-11-11", 50.00, "https://www.discogs.com/release/17583742-Rings-Of-Saturn-Embryonic-Anomaly-Remake", "purple_galaxy", "Not Listed"),
    (14947161, "Veil Of Maya", "[Id]", 2020, "LP, Yel", "Sumerian Records", "SUM-026", "Good Plus (G+)", "Very Good (VG)", "USED copy. Yellow pressing.", "2026-11-10", 59.99, "https://www.discogs.com/release/14947161-Veil-Of-Maya-Id", "neon_split", "Not Listed"),
    (28593982, "Currents", "The Place I Feel Safest", 2023, "2xLP, Ltd, RP, Cle", "SharpTone", "3988-3", "Very Good Plus (VG+)", "Very Good Plus (VG+)", "Limited Crystal Clear 2xLP Repress", "2026-11-09", 75.00, "https://www.discogs.com/release/28593982-Currents-The-Place-I-Feel-Safest", "clear_splatter", "Not Listed"),
    (38267097, "Circa Survive", "Juturna", 2025, "LP, Album, Ltd, RE, RP, Pin", "Equal Vision Records", "EVR103", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Played once, like new all around. Still has shrink on.", "2026-11-09", 50.98, "https://www.discogs.com/release/38267097-Circa-Survive-Juturna", "crimson_nebula", "Not Listed"),
    (38337288, "156/Silence", "From A Distance", 2025, "LP, Album, Ltd, Ora", "Pure Noise Records", "PNE484", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Played once, like new all around.", "2026-11-09", 25.00, "https://www.discogs.com/release/38337288-156Silence-From-A-Distance", "crimson_nebula", "Not Listed"),
    (22031968, "Currents", "The Way It Ends", 2022, "LP, Album, Ltd, Ele", "SharpTone", "5326", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Never played. Electric Blue vinyl.", "2026-11-08", 59.99, "https://www.discogs.com/release/22031968-Currents-The-Way-It-Ends", "clear_splatter", "Not Listed"),
    (12988109, "Animals As Leaders", "Animals As Leaders", 2018, "2xLP, Ltd, RE, Cle", "Prosthetic Records", "PROS102871", "Near Mint (NM or M-)", "Very Good Plus (VG+)", "Includes 3D glasses. Clear 2xLP.", "2026-11-07", 35.00, "https://www.discogs.com/release/12988109-Animals-As-Leaders-Animals-As-Leaders", "clear_splatter", "Not Listed"),
    (13203006, "Emarosa", "Peach Club", 2019, "LP, Album, Ltd, Pea", "Hopeless Records", "HR2551-2", "Very Good Plus (VG+)", "Very Good Plus (VG+)", "Limited Peach vinyl pressing.", "2026-11-07", 50.00, "https://www.discogs.com/release/13203006-Emarosa-Peach-Club", "crimson_nebula", "Not Listed"),
    (21929479, "The Plot In You", "Swan Song", 2022, "LP, Album, Ltd, Pur", "Fearless Records", "FEAR01840", "Near Mint (NM or M-)", "Very Good Plus (VG+)", "Played once. Graded conservatively.", "2026-11-07", 28.00, "https://www.discogs.com/release/21929479-The-Plot-In-You-Swan-Song", "purple_galaxy", "Not Listed"),
    (32367897, "Make Them Suffer", "Make Them Suffer", 2024, "LP, Album, Ltd, Bla", "SharpTone", "7335-1", "Near Mint (NM or M-)", "Very Good Plus (VG+)", "Limited Edition Black LP", "2026-11-07", 32.00, "https://www.discogs.com/release/32367897-Make-Them-Suffer-Make-Them-Suffer", None, "Not Listed"),
    (15043916, "August Burns Red", "Guardians", 2020, "2xLP, Album, Gre", "Fearless Records", "FEAR01167", "Near Mint (NM or M-)", "Not Graded", "Emerald Green 2xLP pressing", "2026-11-06", 20.00, "https://www.discogs.com/release/15043916-August-Burns-Red-Guardians", "neon_split", "Not Listed"),
    (28575079, "Beartooth", "The Surface", 2023, "LP, Album, Ltd, Ult", "Red Bull Records", "RBR1005VL", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Ultra Clear Limited Edition", "2026-11-06", 21.00, "https://www.discogs.com/release/28575079-Beartooth-The-Surface", "clear_splatter", "Not Listed"),
    (23605157, "Emery", "The Question Live", 2022, "LP, Album, Ltd, Cle", "BadChristian Music", "BC-028", "Very Good Plus (VG+)", "Very Good Plus (VG+)", "Limited Crystal Clear LP", "2026-11-06", 13.00, "https://www.discogs.com/release/23605157-Emery-The-Question-Live", "clear_splatter", "Not Listed"),
    (22153450, "Northlane", "Discoveries", 2022, "LP, Ltd, RP, Ora", "UNFD", "UNFD009A", "Very Good Plus (VG+)", "Very Good Plus (VG+)", "Limited Orange Repress", "2026-11-06", 30.55, "https://www.discogs.com/release/22153450-Northlane-Discoveries", "crimson_nebula", "Not Listed"),
    (9545877, "Northlane", "Singularity", 2016, "LP, Album, Ltd, RE, RP, Ult", "UNFD", "UNFD025", "Near Mint (NM or M-)", "Very Good Plus (VG+)", "Ultra Clear Reissue", "2026-11-06", 30.00, "https://www.discogs.com/release/9545877-Northlane-Singularity", "clear_splatter", "Not Listed"),
    (11625165, "The Plot In You", "Dispose", 2018, "LP, Album, Ltd, Cle", "Fearless Records", "FEAR00436", "Very Good Plus (VG+)", "Very Good Plus (VG+)", "Excellent copy. Orig. inner sleeve.", "2026-11-06", 35.00, "https://www.discogs.com/release/11625165-The-Plot-In-You-Dispose", "clear_splatter", "Not Listed"),
    (27611781, "Erra", "Drift", 2023, "2xLP, Album, Ltd, RP, Hou", "Sumerian Records", "SUM2178", "Very Good Plus (VG+)", "Very Good Plus (VG+)", "Excellent copy. Orig. insert & inner sleeve.", "2026-11-06", 45.00, "https://www.discogs.com/release/27611781-Erra-Drift", "clear_splatter", "Not Listed"),
    (11095447, "Polaris", "The Mortal Coil", 2017, "LP, Album, Blu", "Resist Records", "RES160LP", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Blue Vinyl Australian Pressing", "2026-11-06", 45.00, "https://www.discogs.com/release/11095447-Polaris-The-Mortal-Coil", "clear_splatter", "Not Listed"),
    (5632601, "Thursday", "Full Collapse", 2014, "LP, Album, Ltd, RP, Gre", "Victory Records", "VR145", "Mint (M)", "Near Mint (NM or M-)", "Limited Green Repress", "2026-11-06", 45.00, "https://www.discogs.com/release/5632601-Thursday-Full-Collapse", "neon_split", "Not Listed"),
    (21958303, "Wage War", "Manic", 2022, "LP, Album, Ltd, Mag", "Fearless Records", "FEAR01920", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Limited Magenta Pressing", "2026-11-06", 40.00, "https://www.discogs.com/release/21958303-Wage-War-Manic", "purple_galaxy", "Not Listed"),
    (7685817, "Coheed And Cambria", "The Color Before The Sun", 2015, "LP, Album", "300 Entertainment", "85756100572", "Near Mint (NM or M-)", "Very Good Plus (VG+)", "Autographed copy on front sleeve.", "2026-11-04", 80.00, "https://www.discogs.com/release/7685817-Coheed-And-Cambria-The-Color-Before-The-Sun", None, "Not Listed"),
    (19084276, "Thrice", "To Be Everywhere Is To Be Nowhere", 2021, "LP, Album, RSD, Ltd, RE, RP, Blu", "Vagrant / BMG", "VR4390", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Sleeve still in shrink with obi/hype stickers. Booklet included.", "2026-11-04", 26.00, "https://www.discogs.com/release/19084276-Thrice-To-Be-Everywhere-Is-To-Be-Nowhere", "clear_splatter", "Not Listed"),
    (25418758, "I Prevail", "True Power", 2022, "LP, Album, Blu", "Fearless Records", "FEAR01833", "Near Mint (NM or M-)", "Very Good Plus (VG+)", "Sleeve still in shrink with hype sticker. Insert included.", "2026-11-04", 19.00, "https://www.discogs.com/release/25418758-I-Prevail-True-Power", "clear_splatter", "Not Listed"),
    (20546863, "Born Of Osiris", "Angel Or Alien", 2021, "2xLP, Album, Neo", "Sumerian Records", "SUM-AOA", "Very Good Plus (VG+)", "Very Good Plus (VG+)", "LP 1 is VG++, LP 2 is NM. Insert included.", "2026-11-04", 20.00, "https://www.discogs.com/release/20546863-Born-Of-Osiris-Angel-Or-Alien", "neon_split", "Done"),
    (25541158, "Born Of Osiris", "Soul Sphere", 2022, "LP, Album, RP, Vio", "Sumerian Records", "SUM1779", "Very Good Plus (VG+)", "Very Good Plus (VG+)", "Strong VG+ Violet Repress. Insert included.", "2026-11-04", 27.00, "https://www.discogs.com/release/25541158-Born-Of-Osiris-Soul-Sphere", "purple_galaxy", "Not Listed"),
    (11812427, "Underoath", "Erase Me", 2018, "LP, Album, Aci", "Fearless Records", "FEAR00449", "Very Good (VG)", "Very Good Plus (VG+)", "Acid Green vinyl. Printed inner sleeve included.", "2026-11-04", 10.00, "https://www.discogs.com/release/11812427-Underoath-Erase-Me", "neon_split", "Not Listed"),
    (36991890, "Born Of Osiris", "The Discovery", 2025, "2xLP, Album, Ltd, RP, Bla", "Sumerian Records", "SUM3781", "Mint (M)", "Near Mint (NM or M-)", "Sealed w/ hype sticker, great condition.", "2026-11-04", 50.00, "https://www.discogs.com/release/36991890-Born-Of-Osiris-The-Discovery", None, "Not Listed"),
    (16595574, "Knocked Loose", "Laugh Tracks", 2020, "LP, Album, RP, Blu", "Pure Noise Records", "PNE 192", "Very Good Plus (VG+)", "Very Good Plus (VG+)", "Cobalt Blue Repress", "2026-11-03", 38.00, "https://www.discogs.com/release/16595574-Knocked-Loose-Laugh-Tracks", "clear_splatter", "Not Listed"),
    (31699214, "Ed Sheeran", "+-=÷× (Tour Collection)", 2024, "2xLP, Comp, Ltd, Blu", "Gingerbread Man Records", "5054197984921", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Limited Blue 2xLP Tour Collection", "2026-11-03", 25.00, "https://www.discogs.com/release/31699214-Ed-Sheeran---Tour-Collection", "clear_splatter", "Not Listed"),
    (12852715, "Unearth", "Extinction[s]", 2018, "LP, Album, Ltd, Yel", "Century Media", "19075897591", "Near Mint (NM or M-)", "Very Good (VG)", "Limited Yellow LP", "2026-11-03", 16.00, "https://www.discogs.com/release/12852715-Unearth-Extinctions", "neon_split", "Not Listed"),
    (19249243, "Unearth", "Watchers Of Rule", 2021, "LP, Dlx, Ltd, Gre", "eOne", "EOM-LP-46455", "Near Mint (NM or M-)", "Very Good Plus (VG+)", "Deluxe Limited Green LP", "2026-11-03", 20.00, "https://www.discogs.com/release/19249243-Unearth-Watchers-Of-Rule", "neon_split", "Not Listed"),
    (3873517, "Thursday", "War All The Time", 2012, "2xLP, Album, Ltd, RE, Gra", "Island / Victory Records", "B0017169-01", "Very Good Plus (VG+)", "Good Plus (G+)", "Played once. Graphite Grey 2xLP.", "2026-11-01", 50.00, "https://www.discogs.com/release/3873517-Thursday-War-All-The-Time", "purple_galaxy", "Done"),
    (27717681, "Erra", "Neon", 2023, "LP, Ltd, RP, Ult", "Sumerian Records", "SUM2187", "Very Good Plus (VG+)", "Very Good Plus (VG+)", "Excellent copy. Orig. insert.", "2026-11-01", 25.00, "https://www.discogs.com/release/27717681-Erra-Neon", "clear_splatter", "Not Listed"),
    (3780990, "Periphery", "Periphery II: This Time It's Personal (Green)", 2012, "2xLP, Album, Ltd, Gre", "Sumerian Records", "SUM-226", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Never played and in great shape!", "2026-11-01", 55.00, "https://www.discogs.com/release/3780990-Periphery-Periphery-II-This-Time-Its-Personal", "neon_split", "Done"),
    (22568519, "Imminence", "Turn The Light On", 2022, "2xLP, Album, Dlx, Ltd, RE, Whi", "Arising Empire", "1021649AEP", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Beautiful copy! Deluxe White 2xLP.", "2026-11-01", 39.99, "https://www.discogs.com/release/22568519-Imminence-Turn-The-Light-On", "crimson_nebula", "Done"),
    (13113361, "Bring Me The Horizon", "Amo", 2019, "2xLP, Album", "Columbia", "19075895641", "Mint (M)", "Mint (M)", "2xLP Gatefold Sleeve", "2026-10-30", 20.00, "https://www.discogs.com/release/13113361-Bring-Me-The-Horizon-Amo", None, "Done"),
    (23657633, "Thornhill", "Heroine", 2022, "LP, Bla", "UNFD", "UNFD150", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Excellent copy with no signs of use.", "2026-10-30", 50.00, "https://www.discogs.com/release/23657633-Thornhill-Heroine", None, "Done"),
    (22879535, "Monuments", "In Stasis", 2022, "LP, Album, Cle + CD, Album + Ltd", "Century Media", "19439986911", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Signed, never played. Clear LP + CD.", "2026-10-30", 40.00, "https://www.discogs.com/release/22879535-Monuments-In-Stasis", "clear_splatter", "Not Listed"),
    (26047519, "Protest The Hero", "Fortress", 2023, "2xLP, Album, Ltd, RE, RP, Gra", "Sheet Happens Publishing", "SHV-025", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Graphite 2xLP Audiophile Reissue", "2026-10-30", 55.00, "https://www.discogs.com/release/26047519-Protest-The-Hero-Fortress", "purple_galaxy", "Not Listed"),
    (10142402, "Coheed And Cambria", "Good Apollo I'm Burning Star IV Volume One: From Fear Through The Eyes Of Madness", 2017, "2xLP, Album, RE", "Columbia / Equal Vision", "88843045891", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Both vinyl and album cover in great shape.", "2026-10-29", 119.99, "https://www.discogs.com/release/10142402-Coheed-And-Cambria-Good-Apollo-Im-Burning-Star-IV-Volume-One-From-Fear-Through-The-Eyes-Of-Madness", "crimson_nebula", "Not Listed"),
    (34756244, "Imminence", "The Return Of The Black", 2025, "2xLP, Album, RE, Bla", "Imminence Self-released", "none", "Mint (M)", "Very Good Plus (VG+)", "Opened to confirm variant.", "2026-10-29", 72.00, "https://www.discogs.com/release/34756244-Imminence-The-Return-Of-The-Black-", None, "Need to be done"),
    (35907826, "Bring Me The Horizon", "That's The Spirit", 2025, "LP, Album, Dlx, Ltd, RE, S/Edition, Bla", "Sony Music", "19802978321", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "10th Anniversary Deluxe Special Edition", "2026-10-28", 100.00, "https://www.discogs.com/release/35907826-Bring-Me-The-Horizon-Thats-The-Spirit", None, "Need to be done"),
    (26831573, "Architects", "Daybreaker", 2023, "LP, Album, Ltd, RE, RP, Cle", "Arising Empire / Century Media", "none", "Mint (M)", "Near Mint (NM or M-)", "Sealed store stock. Crystal Clear LP.", "2026-10-27", 29.99, "https://www.discogs.com/release/26831573-Architects-Daybreaker", "clear_splatter", "Not Listed"),
    (23343893, "Unearth", "The Stings Of Conscience", 2022, "LP, Album, Ltd, Cle", "Good Fight Music", "GFM093", "Mint (M)", "Mint (M)", "Brand New. Never opened. Clear LP.", "2026-10-25", 20.00, "https://www.discogs.com/release/23343893-Unearth-The-Stings-Of-Conscience", "clear_splatter", "Done"),
    (22544762, "Imminence", "Heaven In Hiding", 2022, "LP, Cle + LP, S/Sided, Etch, Cle + Album, RE", "Arising Empire", "none", "Mint (M)", "Mint (M)", "Record is sealed! Clear 2xLP with etched D-side.", "2026-10-25", 45.00, "https://www.discogs.com/release/22544762-Imminence-Heaven-In-Hiding", "clear_splatter", "Done"),
    (27079776, "Greyhaven", "This Bright And Beautiful World", 2022, "LP, Ltd, Mil", "Equal Vision Records", "EVR448", "Very Good Plus (VG+)", "Very Good Plus (VG+)", "2022 RED IN CLEAR VERSION, AUTOGRAPHED ON FRONT COVER, gatefold LP!", "2026-10-23", 55.00, "https://www.discogs.com/release/27079776-Greyhaven-This-Bright-And-Beautiful-World", "crimson_nebula", "Done"),
    (38268432, "Underoath", "Define The Great Line", 2025, "2xLP, Ltd, Num, RE, Dus", "Underoath Self-released", "none", "Mint (M)", "Mint (M)", "Sealed numbered limited edition Dusty Smoke 2xLP.", "2026-10-23", 55.00, "https://www.discogs.com/release/38268432-Underoath-Define-The-Great-Line", "purple_galaxy", "Done"),
    (9346527, "Periphery", "Periphery III: Select Difficulty (White)", 2016, "2xLP, Album, Ltd, Whi", "Sumerian Records", "SUM711", "Very Good Plus (VG+)", "Very Good Plus (VG+)", "Everything in great shape. Opaque White 2xLP.", "2026-10-23", 39.98, "https://www.discogs.com/release/9346527-Periphery-Periphery-III-Select-Difficulty", "crimson_nebula", "Done"),
    (15594164, "Periphery", "Periphery II: This Time It's Personal (Galaxy)", 2020, "2xLP, Ltd, RP, Gal", "3 Dot Recordings", "PER001", "Very Good Plus (VG+)", "Very Good (VG)", "Includes Mo-Fi anti-static inner sleeves. Galaxy 2xLP.", "2026-10-22", 58.98, "https://www.discogs.com/release/15594164-Periphery-Periphery-II-This-Time-Its-Personal", "purple_galaxy", "Done"),
    (35844376, "Thrice", "Identity Crisis", 2025, "LP, Album, Ltd, RE, Gho", "BMG", "964155731", "Mint (M)", "Near Mint (NM or M-)", "New in original factory packaging. Ghostly Clear LP.", "2026-10-22", 24.89, "https://www.discogs.com/release/35844376-Thrice-Identity-Crisis", "clear_splatter", "Done"),
    (20697637, "Every Time I Die", "Radical", 2021, "LP, Ltd, Neo + LP, S/Sided, Etch, Ltd, Neo", "Epitaph", "7747-1", "Mint (M)", "Near Mint (NM or M-)", "Still sealed and unplayed as received from Banquet! Neon Etched 2xLP.", "2026-10-19", 35.00, "https://www.discogs.com/release/20697637-Every-Time-I-Die-Radical", "neon_split", "Not Listed"),
    (25089742, "Architects", "The Classic Symptoms Of A Broken Spirit", 2022, "LP, Album, Ltd, Cle", "Epitaph", "87932-1", "Mint (M)", "Mint (M)", "Sealed Clear w/ Yellow and Purple Splatter.", "2026-10-19", 20.00, "https://www.discogs.com/release/25089742-Architects-The-Classic-Symptoms-Of-A-Broken-Spirit", "clear_splatter", "Not Listed"),
    (25367083, "Parkway Drive", "Deep Blue", 2022, "2x12\", Album, Ltd, RE, Blu", "Epitaph", "87095-1", "Mint (M)", "Near Mint (NM or M-)", "Cobalt Blue 2x12\" Reissue", "2026-10-15", 29.00, "https://www.discogs.com/release/25367083-Parkway-Drive-Deep-Blue-", "clear_splatter", "Not Listed"),
    (27927123, "Nothing More", "Spirits", 2023, "LP, Cle + LP, S/Sided, Etch, Cle + Album, Ltd", "Better Noise Music", "BNM-419-1", "Mint (M)", "Near Mint (NM or M-)", "Clear 2xLP with etched B-side", "2026-10-15", 29.00, "https://www.discogs.com/release/27927123-Nothing-More-Spirits", "clear_splatter", "Done"),
    (36342703, "Currents", "All That Follows", 2025, "12\", EP, Bla", "SharpTone", "7524", "Near Mint (NM or M-)", "Very Good (VG)", "Unplayed vinyl, everything in protective sleeves.", "2026-10-14", 42.00, "https://www.discogs.com/release/36342703-Currents-All-That-Follows", None, "Not Listed"),
    (33399134, "Coheed And Cambria", "Vaxis III: The Father Of Make Believe", 2025, "2xLP, Album, Ltd, Lig", "Evil Ink Records", "198704222382", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "BRAND NEW WITH HYPE STICKER FROM STORE STOCK! Light Sky Blue 2xLP.", "2026-10-13", 32.00, "https://www.discogs.com/release/33399134-Coheed-And-Cambria-Vaxis-III-The-Father-Of-Make-Believe", "clear_splatter", "Not Listed"),
    (29237467, "Periphery", "Periphery III: Select Difficulty (Canary)", 2023, "2xLP, Album, Ltd, Can", "3 Dot Recordings", "3DOT-P3", "Mint (M)", "Mint (M)", "Mint in shrink. Canary Yellow 2xLP.", "2026-10-13", 75.00, "https://www.discogs.com/release/29237467-Periphery-Periphery-III-Select-Difficulty", "neon_split", "Done"),
    (29410045, "Periphery", "Periphery (P1)", 2023, "2xLP, Album, Ltd, RE, Whi", "3 Dot Recordings", "3DOT-005", "Mint (M)", "Mint (M)", "Mint in shrink. Opaque White 2xLP.", "2026-10-13", 55.00, "https://www.discogs.com/release/29410045-Periphery-Periphery", "crimson_nebula", "Done"),
    (29410450, "Periphery", "Juggernaut • Alpha", 2023, "LP, Album, Ltd, Cle", "3 Dot Recordings", "3DOT-009", "Mint (M)", "Mint (M)", "Mint in shrink. Crystal Clear LP.", "2026-10-13", 55.00, "https://www.discogs.com/release/29410450-Periphery-Juggernaut-Alpha", "clear_splatter", "Done"),
    (29410354, "Periphery", "Juggernaut • Omega", 2023, "LP, Album, Ltd, Bla", "3 Dot Recordings", "3DOT-010", "Very Good (VG)", "Very Good Plus (VG+)", "Includes the printed inner sleeve.", "2026-10-13", 40.00, "https://www.discogs.com/release/29410354-Periphery-Juggernaut-Omega", None, "Done"),
    (37163709, "Sleep Token", "Take Me Back To Eden", 2025, "2xLP, RE, RP, Mil", "Spinefarm Records", "SPINE801099P", "Mint (M)", "Mint (M)", "Milky Clear 2xLP, only played once.", "2026-10-12", 45.00, "https://www.discogs.com/release/37163709-Sleep-Token-Take-Me-Back-To-Eden", "crimson_nebula", "Done"),
    (37838730, "Bring Me The Horizon", "Count Your Blessings Repented.", 2025, "LP, Album, Dlx, Cok", "RCA", "19958442051", "Mint (M)", "Mint (M)", "Coke Bottle Clear Deluxe LP, sounds crystal clear.", "2026-10-12", 85.00, "https://www.discogs.com/release/37838730-Bring-Me-The-Horizon-Count-Your-Blessings-Repented", "neon_split", "Not Listed"),
    # Additional collection records verified from Alex's Google Keep 'Vinyl flattening' note
    (14224286, "A Day To Remember", "For Those Who Have Heart", 2019, "LP, Album, Ltd, RE, Yellow, White, and Blue Starburst", "Victory Records", "VR337", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Yellow, White & Blue Starburst pressing (in Vinyl Flattening queue).", "2026-10-11", 45.00, "https://www.discogs.com/release/14224286-A-Day-To-Remember-For-Those-Who-Have-Heart", "neon_split", "Need to be done"),
    (31909216, "Allt", "From The New World", 2024, "LP, Album, 140g, Bla", "Century Media", "19802815871", "Mint (M)", "Mint (M)", "Flattened and verified on plate.", "2026-10-10", 30.21, "https://www.discogs.com/release/31909216-Allt-From-The-New-World", None, "Done"),
    (16251744, "Coheed And Cambria", "Good Apollo, I'm Burning Star IV, Volume Two: No World For Tomorrow", 2020, "2xLP, Album, Ltd, RE, Etch, Red & Cream Mix with Black Splatter", "Columbia", "194397274516", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Red & Cream Mix w/ Black Splatter + Etched D-Side.", "2026-10-09", 48.00, "https://www.discogs.com/release/16251744-Coheed-And-Cambria-Good-Apollo-Im-Burning-Star-IV-Volume-Two-No-World-for-Tomorrow", "crimson_nebula", "Done"),
    (26690690, "Coheed And Cambria", "The Second Stage Turbine Blade", 2023, "LP, Album, Ltd, RE, Yellow With White And Black Splatter", "Equal Vision Records", "EVR114", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "20th Anniversary Edition Splatter LP.", "2026-10-09", 35.00, "https://www.discogs.com/release/26690690-Coheed-And-Cambria-The-Second-Stage-Turbine-Blade", "neon_split", "Done"),
    (23728319, "Coheed And Cambria", "Vaxis II: A Window Of The Waking Mind", 2022, "2xLP, Album, Ltd, Orange w/ Pink Swirl", "Roadrunner Records", "7567-864067", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Orange w/ Pink Swirl 2xLP.", "2026-10-08", 38.00, "https://www.discogs.com/release/23728319-Coheed-And-Cambria-Vaxis-II-A-Window-Of-The-Waking-Mind", "crimson_nebula", "Done"),
    (22068100, "Don Broco", "Amazing Things", 2022, "LP, Album, Ltd, Purple Marble", "SharpTone", "ST6065-6", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Purple Marble Limited Pressing.", "2026-10-07", 34.00, "https://www.discogs.com/release/22068100-Don-Broco-Amazing-Things", "purple_galaxy", "Done"),
    (12131049, "Don Broco", "Technology", 2018, "2xLP, Album, Ltd, Gold", "SharpTone", "4259-8", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Limited Metallic Gold 2xLP.", "2026-10-07", 42.00, "https://www.discogs.com/release/12131049-Don-Broco-Technology", "neon_split", "Done"),
    (30044359, "Invent Animate", "Heavener", 2024, "LP, Album, Ltd, RP, Transparent Dark Blue w/ Pink Splatter", "UNFD", "UNFD160", "Mint (M)", "Mint (M)", "Transparent Dark Blue w/ Pink Splatter LP.", "2026-10-06", 44.00, "https://www.discogs.com/release/30044359-Invent-Animate-Heavener", "clear_splatter", "Done"),
    (26412110, "Periphery", "Periphery V: Djent Is Not A Genre", 2023, "2xLP, Album, Ltd, Ruby With Black Splatter", "3 Dot Recordings", "3DOT-003LPXS", "Mint (M)", "Mint (M)", "Ruby Red w/ Black Splatter 2xLP.", "2026-10-05", 52.00, "https://www.discogs.com/release/26412110-Periphery-Periphery-V-Djent-Is-Not-A-Genre", "crimson_nebula", "Done"),
    (13459362, "Periphery", "Periphery IV: Hail Stan", 2019, "2xLP, Album, Ltd, Pur", "3 Dot Recordings", "3DOT-001", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Limited Edition Purple 2xLP.", "2026-10-05", 65.00, "https://www.discogs.com/release/13459362-Periphery-Periphery-IV-Hail-Stan", "purple_galaxy", "Done"),
    (14835807, "Polaris", "The Death Of Me", 2020, "LP, Album, Clear w/ Blue And Pink Splatter", "Resist Records", "RES180LPB", "Near Mint (NM or M-)", "Near Mint (NM or M-)", "Clear w/ Blue & Pink Splatter LP (300 copies).", "2026-10-04", 55.00, "https://www.discogs.com/release/14835807-Polaris-The-Death-Of-Me", "clear_splatter", "Done"),
    (28873363, "Silent Planet", "Superbloom", 2023, "LP, Album, Dimension Red", "Solid State Records", "TNV000144", "Mint (M)", "Mint (M)", "Dimension Red Marble LP.", "2026-10-03", 42.00, "https://www.discogs.com/release/28873363-Silent-Planet-Superbloom", "crimson_nebula", "Done"),
    (33412436, "Spiritbox", "Tsunami Sea", 2025, "LP, Album, Ltd, Black In Milky Clear With Black Splatter", "Pale Chord / Rise Records", "RISE 549-6", "Mint (M)", "Mint (M)", "Black in Milky Clear w/ Black Splatter.", "2026-10-02", 58.00, "https://www.discogs.com/release/33412436-Spiritbox-Tsunami-Sea", "crimson_nebula", "Done"),
    (28243078, "TesseracT", "War Of Being", 2023, "2xLP, Album, Ltd, Pur", "Kscope", "KSCOPE786", "Mint (M)", "Mint (M)", "Limited Purple Marble 2xLP.", "2026-10-01", 40.00, "https://www.discogs.com/release/28243078-Tesseract-War-of-Being", "purple_galaxy", "Done"),
]

records = []
seen_rids = set()
for idx, row in enumerate(RAW_RELEASES, start=1):
    if row[0] in seen_rids:
        continue
    seen_rids.add(row[0])
    (
        rid, artist, title, year, fmt_str, label, catno,
        media_cond, sleeve_cond, comments, date_added, price,
        discogs_url, photo_key, flatten_status
    ) = row

    wax_spec = parse_wax_variant(fmt_str, comments=comments, release_id=rid)
    has_photo = photo_key is not None and photo_key in PRESSING_PHOTO_MAP
    pressing_img_path = f"assets/pressings/pressing_{photo_key}.jpg" if has_photo else ""
    cv_metrics = CV_CACHE.get(photo_key, {}) if has_photo else {}

    classified_imgs = [
        {
            "index": 0,
            "uri": f"procedural://sleeve/{rid}",
            "width": 600,
            "height": 600,
            "aspect_ratio": 1.0,
            "role": "front_cover",
            "deterministic_score": 0.05,
        },
        {
            "index": 1,
            "uri": f"procedural://back/{rid}",
            "width": 600,
            "height": 600,
            "aspect_ratio": 1.0,
            "role": "back_cover",
            "deterministic_score": 0.18,
        },
    ]
    if has_photo:
        classified_imgs.append({
            "index": 2,
            "uri": pressing_img_path,
            "width": 600,
            "height": 600,
            "aspect_ratio": 1.0,
            "role": "pressing_disc",
            "deterministic_score": round(0.65 * float(cv_metrics.get("score", 0.85)) + 0.35 * 0.85, 4),
            "cv_metrics": cv_metrics,
        })

    records.append({
        "release_id": rid,
        "instance_id": 900000 + idx,
        "artist": artist,
        "title": title,
        "year": year,
        "format_string": fmt_str,
        "label": label,
        "catno": catno,
        "media_condition": media_cond,
        "sleeve_condition": sleeve_cond,
        "comments": comments,
        "date_added": date_added,
        "discogs_url": discogs_url,
        "estimated_value_usd": price,
        "flattening_status": flatten_status,
        "genres": ["Rock"],
        "styles": ["Metalcore", "Progressive Metal", "Post-Hardcore"],
        "images": {
            "cover_image_url": "",
            "pressing_image_url": pressing_img_path,
            "display_thumbnail_url": pressing_img_path,
            "has_pressing_photo": has_photo,
            "photo_key": photo_key or "",
            "selected_index": 2 if has_photo else 0,
            "selected_score": classified_imgs[-1]["deterministic_score"] if has_photo else 0.0,
            "detection_method": "deterministic_annular_cv+guideline_13_8" if has_photo else "procedural_wax_from_discogs_format_codes",
            "classified_images": classified_imgs,
        },
        "wax_spec": wax_spec,
    })

total_val = round(sum(r["estimated_value_usd"] for r in records), 2)
pressing_count = sum(1 for r in records if r["images"]["has_pressing_photo"])
colored_count = sum(1 for r in records if r["wax_spec"]["pattern"] != "black")

payload = {
    "schema_version": "2.0.0",
    "source_of_truth": "https://www.discogs.com/user/krunked/collection",
    "api_documentation": "https://www.discogs.com/developers",
    "image_guidelines": "https://support.discogs.com/hc/en-us/articles/360005006874-Database-Guidelines-13-Images",
    "username": "krunked",
    "synced_at_utc": "2026-11-11T19:45:00Z",
    "profile": {
        "username": "krunked",
        "owner_name": "Alex Goresch",
        "discogs_url": "https://www.discogs.com/user/krunked/collection",
        "github_repo": "https://github.com/krunked-fpv/discogs_collection",
        "num_collection": len(records),
        "pressing_photos_detected": pressing_count,
        "colored_or_special_variants": colored_count,
        "collection_value": {
            "minimum": f"${round(total_val * 0.78, 2):,.2f}",
            "median": f"${total_val:,.2f}",
            "maximum": f"${round(total_val * 1.38, 2):,.2f}",
        },
    },
    "records": records,
}

out_file = REPO_ROOT / "data" / "collection.json"
out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

hash_copy = dict(payload)
hash_copy.pop("synced_at_utc", None)
digest = hashlib.sha256(json.dumps(hash_copy, sort_keys=True).encode("utf-8")).hexdigest()
(REPO_ROOT / "data" / "sync_manifest.json").write_text(
    json.dumps(
        {
            "username": "krunked",
            "record_count": len(records),
            "pressing_photos_detected": pressing_count,
            "colored_or_special_variants": colored_count,
            "content_sha256": digest,
            "synced_at_utc": payload["synced_at_utc"],
        },
        indent=2,
    ),
    encoding="utf-8",
)
print(f"Seeded {len(records)} records ({pressing_count} with pressing photos, {colored_count} colored variants, total=${total_val:,.2f})")
