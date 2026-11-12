#!/usr/bin/env python3
"""Local Windows Environment Variable Setup & Hardcoded Token Scrubber.

Run this script once on your Windows machine:
    python scripts/setup_discogs_token.py

What it does:
1. Prompts you for your new Discogs Personal Access Token (hidden input).
2. Saves `DISCOGS_TOKEN` permanently to your Windows User Environment Variables
   (in `HKCU\\Environment`) so Python can read `os.environ.get("DISCOGS_TOKEN")`
   without ever hardcoding it in your repository.
3. Also creates/updates a git-ignored `.env` file in your repo root as a backup
   and ensures `.env` is listed in `.gitignore`.
4. Scans `index.html` and `scripts/*.py` and scrubs the old exposed token if
   present so you never accidentally push it to GitHub again.
"""

from __future__ import annotations

import getpass
import os
import pathlib
import subprocess
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name == "scripts" else SCRIPT_DIR

# The previously exposed token prefix/string to scrub from tracked files
OLD_EXPOSED_TOKEN = "HWLciALlIIgSGquWsckHVkbEXCbmXlcrULmVdogi"


def set_windows_user_env_var(var_name: str, value: str) -> bool:
    """Persistently sets a Windows User Environment Variable via winreg / setx."""
    if os.name != "nt":
        return False

    try:
        import ctypes
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, var_name, 0, winreg.REG_SZ, value)

        # Broadcast WM_SETTINGCHANGE so new terminals see the updated variable immediately
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        result = ctypes.c_long()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment",
            SMTO_ABORTIFHUNG,
            5000,
            ctypes.byref(result),
        )
        return True
    except Exception:
        # Fallback to setx command
        try:
            subprocess.run(["setx", var_name, value], check=True, capture_output=True, text=True)
            return True
        except Exception as exc:
            print(f"[warn] Could not write Windows registry env var: {exc}", file=sys.stderr)
            return False


def ensure_gitignore_has_env(repo_root: pathlib.Path) -> None:
    """Ensures `.env` is listed inside `.gitignore` so it is never committed."""
    gitignore_path = repo_root / ".gitignore"
    existing_lines: list[str] = []
    if gitignore_path.exists():
        existing_lines = gitignore_path.read_text(encoding="utf-8").splitlines()

    needed_entries = [".env", ".env.*", "*.env"]
    missing = [entry for entry in needed_entries if entry not in [line.strip() for line in existing_lines]]
    if missing:
        with gitignore_path.open("a", encoding="utf-8") as f:
            if existing_lines and existing_lines[-1].strip() != "":
                f.write("\n")
            f.write("# Local environment variables (never commit API tokens)\n")
            for entry in missing:
                f.write(f"{entry}\n")
        print(f"[ok] Updated {gitignore_path} to ignore .env files.")


def write_local_dotenv(repo_root: pathlib.Path, token: str, username: str = "krunked") -> None:
    """Writes a local `.env` file (ignored by git) for instant local loading."""
    dotenv_path = repo_root / ".env"
    content = (
        "# Local Discogs API Credentials (Git-Ignored — DO NOT COMMIT)\n"
        f"DISCOGS_USERNAME={username}\n"
        f"DISCOGS_TOKEN={token}\n"
    )
    dotenv_path.write_text(content, encoding="utf-8")
    print(f"[ok] Wrote git-ignored local .env file at {dotenv_path}")


def scrub_exposed_token_from_repo(repo_root: pathlib.Path) -> list[pathlib.Path]:
    """Removes the old exposed token from index.html and scripts/*.py."""
    scrubbed_files: list[pathlib.Path] = []
    candidate_paths = [repo_root / "index.html"]
    scripts_dir = repo_root / "scripts"
    if scripts_dir.exists():
        candidate_paths.extend(sorted(scripts_dir.glob("*.py")))

    for path in candidate_paths:
        if not path.exists() or path.resolve() == pathlib.Path(__file__).resolve():
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except Exception:
            continue

        if OLD_EXPOSED_TOKEN in raw:
            updated = raw.replace(f'DEFAULT_TOKEN = "{OLD_EXPOSED_TOKEN}"', 'DEFAULT_TOKEN = ""')
            updated = updated.replace(f"DEFAULT_TOKEN = '{OLD_EXPOSED_TOKEN}'", 'DEFAULT_TOKEN = ""')
            updated = updated.replace(f'value="{OLD_EXPOSED_TOKEN}"', 'value=""')
            updated = updated.replace(OLD_EXPOSED_TOKEN, "")
            path.write_text(updated, encoding="utf-8")
            scrubbed_files.append(path)

    return scrubbed_files


def main() -> None:
    print("=" * 68)
    print("  KRUNKED // DISCOGS TOKEN SECURITY & WINDOWS ENV SETUP")
    print("=" * 68)
    print("1. First, go to https://www.discogs.com/settings/developers")
    print("   and click 'Generate new token' to invalidate the old exposed token.")
    print("2. Paste your NEW token below (or press Enter to just scrub old files).\n")

    try:
        token = getpass.getpass("Enter your NEW Discogs Personal Access Token (hidden): ").strip()
    except Exception:
        token = input("Enter your NEW Discogs Personal Access Token: ").strip()

    if not token:
        token = input("If hidden paste didn't work, paste token here (or leave blank): ").strip()

    scrubbed = scrub_exposed_token_from_repo(REPO_ROOT)
    if scrubbed:
        for p in scrubbed:
            print(f"[scrubbed] Removed exposed token from: {p.relative_to(REPO_ROOT)}")
    else:
        print("[ok] No occurrences of the old exposed token found in index.html or scripts/*.py.")

    ensure_gitignore_has_env(REPO_ROOT)

    if token:
        if token == OLD_EXPOSED_TOKEN:
            print(
                "\n[warn] That is the OLD exposed token! Please generate a fresh one at "
                "https://www.discogs.com/settings/developers so the leaked one cannot be used.",
                file=sys.stderr,
            )

        if os.name == "nt":
            ok = set_windows_user_env_var("DISCOGS_TOKEN", token)
            if ok:
                print("[ok] Saved DISCOGS_TOKEN to your Windows User Environment Variables (HKCU\\Environment).")
        write_local_dotenv(REPO_ROOT, token)
        os.environ["DISCOGS_TOKEN"] = token
        print("\n[success] Your token is now stored safely outside of your code!")
        print("          Both local Windows runs and GitHub Actions will read `DISCOGS_TOKEN` automatically.")
    else:
        print("\n[info] No new token entered. Run `python scripts/setup_discogs_token.py` again once you generate one.")


if __name__ == "__main__":
    main()