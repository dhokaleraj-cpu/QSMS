#!/bin/bash
# QCMS R12 · Set up the Claude API key for Global Search → AI Assistant.
# Usage (from Terminal):  bash /Users/dhokaleraj/QSMS/scripts/set_ai_key.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SECRETS="$ROOT/.streamlit/secrets.toml"
MODEL_DEFAULT="claude-sonnet-5-5"

echo ""
echo "=== QCMS AI Assistant · Claude API key setup ==="
echo "Project : $ROOT"
echo "File    : $SECRETS"
echo ""
echo "Paste your Claude API key (starts with sk-ant-). Nothing is shown while you paste; press Enter after pasting."
read -r -s -p "API key: " KEY
echo ""
KEY="$(printf '%s' "$KEY" | tr -d '[:space:]')"
case "$KEY" in
  sk-ant-*) ;;
  *) echo "ERROR: that does not look like a Claude API key (it must start with sk-ant-). Nothing was changed."; exit 1 ;;
esac

echo "Checking the key with Anthropic..."
if [ "${QCMS_SKIP_KEY_CHECK:-0}" = "1" ]; then CODE="skipped"; else CODE="$(curl -s -o /tmp/qcms_ai_key_check.json -w '%{http_code}' https://api.anthropic.com/v1/models -H "x-api-key: $KEY" -H "anthropic-version: 2023-06-01" || echo 000)"; fi
if [ "$CODE" = "200" ]; then
  echo "Key is valid."
elif [ "$CODE" = "401" ]; then
  echo "ERROR: Anthropic rejected this key (401). Create a new key at console.anthropic.com → API Keys. Nothing was changed."; rm -f /tmp/qcms_ai_key_check.json; exit 1
else
  echo "WARNING: could not verify the key (HTTP $CODE, maybe no internet). Saving it anyway."
fi
rm -f /tmp/qcms_ai_key_check.json

mkdir -p "$ROOT/.streamlit"
touch "$SECRETS"
cp -p "$SECRETS" "$SECRETS.bak_$(date +%Y%m%d_%H%M%S)"
# Remove any old AI lines, then put the new ones at the TOP of the file
# (top-level keys must come before any [section] in TOML).
TMP="$(mktemp)"
grep -v -E '^[[:space:]]*(ANTHROPIC_API_KEY|QCMS_AI_MODEL)[[:space:]]*=' "$SECRETS" > "$TMP" || true
{ printf 'ANTHROPIC_API_KEY = "%s"\nQCMS_AI_MODEL = "%s"\n\n' "$KEY" "$MODEL_DEFAULT"; cat "$TMP"; } > "$SECRETS"
rm -f "$TMP"
chmod 600 "$SECRETS"

echo ""
echo "Saved. .streamlit/secrets.toml now starts with:"
echo "  ANTHROPIC_API_KEY = \"sk-ant-…${KEY: -4}\""
echo "  QCMS_AI_MODEL = \"$MODEL_DEFAULT\""
echo ""
echo "This file is NOT uploaded to GitHub (.gitignore protects it)."
echo "Next: restart QCMS, open Global Search → AI Assistant."
echo "For the online (Streamlit Cloud) app, also paste the same two lines in: App → Settings → Secrets."
