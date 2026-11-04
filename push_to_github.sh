#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/kairo192/mux-Luxury-.git"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo " Mus Luxury (LUXE) — GitHub Push Utility (mux-Luxury-)"
echo "============================================================"

# Verify .env is ignored and not staged
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo "[!] Removing .env from git index to protect secrets..."
  git rm --cached .env
fi

# Ensure remote origin points to kairo192/mux-Luxury-
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REPO_URL"
else
  git remote add origin "$REPO_URL"
fi

echo "[*] Remote configured: $(git remote get-url origin)"
echo "[*] Current branch   : $(git branch --show-current)"
echo "[*] Latest commit    : $(git log -1 --oneline)"
echo "[*] Pushing main branch to GitHub..."

git branch -M main
git push -u origin main --force

echo "============================================================"
echo " [OK] Successfully pushed to $REPO_URL (branch: main)"
echo "============================================================"
