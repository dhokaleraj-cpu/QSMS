#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/dhokaleraj/QSMS"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install -q -r requirements.txt
exec python -m streamlit run streamlit_app.py --server.port 8510
