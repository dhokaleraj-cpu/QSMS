#!/bin/bash
# QCMS R15 · Set up the AI Assistant key (Global Search → AI Assistant).
# Choose a FREE engine (Google Gemini or Groq) or a paid one (Claude / OpenAI).
# Usage (from Terminal):  bash /Users/dhokaleraj/QSMS/scripts/set_ai_key.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SECRETS="$ROOT/.streamlit/secrets.toml"

echo ""
echo "=== QCMS AI Assistant · key setup ==="
echo "Project : $ROOT"
echo "File    : $SECRETS"
echo ""
echo "Choose the AI engine:"
echo "  1) Google Gemini  - FREE  (key from aistudio.google.com → Get API key, starts with AIza)"
echo "  2) Groq           - FREE  (key from console.groq.com → API Keys, starts with gsk_)"
echo "  3) Claude         - paid  (key from console.anthropic.com, starts with sk-ant-)"
echo "  4) OpenAI/ChatGPT - paid  (key from platform.openai.com, starts with sk-)"
read -r -p "Enter 1, 2, 3 or 4 [1] (or paste the key directly): " CHOICE
CHOICE="$(printf '%s' "${CHOICE:-1}" | tr -d '[:space:]')"
KEY=""
# A pasted key is accepted directly and the engine is detected from its prefix.
case "$CHOICE" in
  AIza*) KEY="$CHOICE"; CHOICE=1 ;;
  gsk_*) KEY="$CHOICE"; CHOICE=2 ;;
  sk-ant-*) KEY="$CHOICE"; CHOICE=3 ;;
  sk-*) KEY="$CHOICE"; CHOICE=4 ;;
esac
case "$CHOICE" in
  1) PROVIDER="gemini"; KEYNAME="GEMINI_API_KEY"; PREFIX="AIza"; MODEL="gemini-flash-latest" ;;
  2) PROVIDER="groq"; KEYNAME="GROQ_API_KEY"; PREFIX="gsk_"; MODEL="openai/gpt-oss-120b" ;;
  3) PROVIDER="claude"; KEYNAME="ANTHROPIC_API_KEY"; PREFIX="sk-ant-"; MODEL="claude-sonnet-5-5" ;;
  4) PROVIDER="openai"; KEYNAME="OPENAI_API_KEY"; PREFIX="sk-"; MODEL="gpt-5-mini" ;;
  *) echo "ERROR: choose 1, 2, 3 or 4. Nothing was changed."; exit 1 ;;
esac

if [ -z "$KEY" ]; then
  echo ""
  echo "Paste your $PROVIDER API key. Nothing is shown while you paste; press Enter after pasting."
  read -r -s -p "API key: " KEY || true
  echo ""
fi
KEY="$(printf '%s' "$KEY" | tr -d '[:space:]')"
case "$KEY" in
  "$PREFIX"*) ;;
  *) echo "ERROR: that does not look like a $PROVIDER key (it must start with $PREFIX). Nothing was changed."; exit 1 ;;
esac

CODE="skipped"
if [ "${QCMS_SKIP_KEY_CHECK:-0}" != "1" ]; then
  echo "Checking the key..."
  case "$PROVIDER" in
    gemini) CODE="$(curl -s -o /dev/null -w '%{http_code}' "https://generativelanguage.googleapis.com/v1beta/models?key=$KEY" || echo 000)" ;;
    groq)   CODE="$(curl -s -o /dev/null -w '%{http_code}' https://api.groq.com/openai/v1/models -H "Authorization: Bearer $KEY" || echo 000)" ;;
    claude) CODE="$(curl -s -o /dev/null -w '%{http_code}' https://api.anthropic.com/v1/models -H "x-api-key: $KEY" -H "anthropic-version: 2023-06-01" || echo 000)" ;;
    openai) CODE="$(curl -s -o /dev/null -w '%{http_code}' https://api.openai.com/v1/models -H "Authorization: Bearer $KEY" || echo 000)" ;;
  esac
fi
if [ "$CODE" = "200" ]; then
  echo "Key is valid."
elif [ "$CODE" = "401" ] || [ "$CODE" = "400" ] || [ "$CODE" = "403" ]; then
  echo "ERROR: the provider rejected this key (HTTP $CODE). Create a new key and run again. Nothing was changed."; exit 1
else
  echo "WARNING: could not verify the key (HTTP $CODE, maybe no internet). Saving it anyway."
fi

mkdir -p "$ROOT/.streamlit"
touch "$SECRETS"
cp -p "$SECRETS" "$SECRETS.bak_$(date +%Y%m%d_%H%M%S)"
# Remove old AI engine lines, keep any other provider keys, then put the new lines at the TOP
# (top-level keys must come before any [section] in TOML).
TMP="$(mktemp)"
grep -v -E "^[[:space:]]*(QCMS_AI_PROVIDER|QCMS_AI_MODEL|$KEYNAME)[[:space:]]*=" "$SECRETS" > "$TMP" || true
{ printf 'QCMS_AI_PROVIDER = "%s"\n%s = "%s"\nQCMS_AI_MODEL = "%s"\n\n' "$PROVIDER" "$KEYNAME" "$KEY" "$MODEL"; cat "$TMP"; } > "$SECRETS"
rm -f "$TMP"
chmod 600 "$SECRETS"

echo ""
echo "Saved. .streamlit/secrets.toml now starts with:"
echo "  QCMS_AI_PROVIDER = \"$PROVIDER\""
echo "  $KEYNAME = \"…${KEY: -4}\""
echo "  QCMS_AI_MODEL = \"$MODEL\""
echo ""
echo "This file is NOT uploaded to GitHub (.gitignore protects it)."
echo "Next: restart QCMS, open Global Search → AI Assistant."
echo "For the online (Streamlit Cloud) app, paste the same three lines (with your full key) in: App → Settings → Secrets."
if [ "$PROVIDER" = "gemini" ] || [ "$PROVIDER" = "groq" ]; then
  echo "Note: free tiers are rate-limited and the provider may use free-tier prompts to improve its services."
fi
