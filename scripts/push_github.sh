#!/usr/bin/env bash
set -euo pipefail

PROJECT="/Users/dhokaleraj/QSMS"
REMOTE="https://github.com/dhokaleraj-cpu/QSMS.git"
cd "$PROJECT"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || git init
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE"
else
  git remote add origin "$REMOTE"
fi

git branch -M main
git add \
  .gitignore VERSION requirements.txt streamlit_app.py \
  app_pages core docs scripts supabase tests

if ! git diff --cached --quiet; then
  git commit -m "QSMS live release 4.9.2 $(date '+%Y-%m-%d %H:%M:%S')"
fi

if git ls-remote --exit-code --heads origin main >/dev/null 2>&1; then
  git pull --rebase origin main
fi

git push -u origin main
printf '\nQSMS 4.9.2 pushed to GitHub. Streamlit Cloud will redeploy automatically.\n'
