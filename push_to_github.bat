@echo off
setlocal
cd /d "%~dp0"

set REPO_URL=https://github.com/kairo192/mux-Luxury-.git

echo ============================================================
echo  Mus Luxury (LUXE) - GitHub Push Utility (mux-Luxury-)
echo ============================================================

git remote set-url origin %REPO_URL% 2>nul || git remote add origin %REPO_URL%
git branch -M main
echo [*] Pushing main branch to %REPO_URL% ...
git push -u origin main --force

echo ============================================================
echo  [OK] Push complete! Check GitHub Actions at:
echo  https://github.com/kairo192/mux-Luxury-/actions
echo ============================================================
pause
