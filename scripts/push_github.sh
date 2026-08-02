#!/usr/bin/env bash
set -euo pipefail
TARGET="/Users/dhokaleraj/QSMS"
cd "$TARGET"
[[ -d .git ]] || { echo "Git repository is not initialized. Run QSMS_GITHUB_STREAMLIT_LIVE_DEPLOY.command first."; exit 1; }
[[ -x .venv/bin/python ]] || { echo "QSMS virtual environment is missing."; exit 1; }
source .venv/bin/activate
python -m compileall -q .
python scripts/check_online_readiness.py
pytest -q
git add .
if git diff --cached --quiet; then
  echo "No source changes to push."
  exit 0
fi
VERSION="$(tr -d '\r\n' < VERSION 2>/dev/null || echo update)"
git commit -m "QSMS ${VERSION} production update $(date +%Y-%m-%d_%H-%M)"
git push origin main
echo "GitHub push completed. Streamlit Cloud will redeploy from main."
