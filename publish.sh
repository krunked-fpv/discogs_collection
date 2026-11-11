#!/usr/bin/env bash
# Deterministic 1-step GitHub push & GitHub Pages publisher for krunked-fpv/discogs_collection
set -euo pipefail

REPO_SLUG="krunked-fpv/discogs_collection"
REMOTE_URL="https://github.com/${REPO_SLUG}.git"

if [ ! -d ".git" ]; then
  git init
  git branch -M main
  git remote add origin "$REMOTE_URL" 2>/dev/null || git remote set-url origin "$REMOTE_URL"
  git fetch origin main || true
  git reset --soft origin/main || true
fi

git add README.md requirements.txt index.html .github/ scripts/ data/ tests/ assets/ publish.sh
if ! git diff --cached --quiet; then
  git commit -m "feat: pressing-first Discogs collection vault & deterministic sync pipeline"
fi

git push -u origin main

# If GitHub CLI (gh) is installed and authenticated, configure Pages & trigger workflow automatically
if command -v gh >/dev/null 2>&1; then
  echo "[gh] Configuring GitHub Pages to deploy from GitHub Actions..."
  gh api -X POST "repos/${REPO_SLUG}/pages" -f build_type="workflow" 2>/dev/null || \
    gh api -X PUT "repos/${REPO_SLUG}/pages" -f build_type="workflow" 2>/dev/null || true

  if [ -n "${DISCOGS_TOKEN:-}" ]; then
    echo "[gh] Setting DISCOGS_TOKEN repository secret..."
    printf "%s" "$DISCOGS_TOKEN" | gh secret set DISCOGS_TOKEN --repo "$REPO_SLUG"
  fi

  echo "[gh] Triggering Sync Discogs Collection & Deploy to GitHub Pages workflow..."
  gh workflow run "sync-and-deploy.yml" --repo "$REPO_SLUG" || true
  echo "[ok] Published! Live URL: https://krunked-fpv.github.io/discogs_collection/"
else
  echo "[ok] Pushed to main! Enable GitHub Pages (Source: GitHub Actions) at:"
  echo "     https://github.com/${REPO_SLUG}/settings/pages"
fi
