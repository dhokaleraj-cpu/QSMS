# QCMS 4.14.49 R12 — 9 October 2026

Includes R11 (Part duplicate control, save popup, admin Part delete, AI Global Search) and R10 (Forging PO gate).

## Design 07 · Teal Material (app-wide)
- Teal top bar, white rounded left menu with teal active pill, rounded cards, sections, fields and buttons, teal headings, KPI values and table headers. Login page uses the same teal colours.
- Streamlit theme (.streamlit/config.toml): primary #0F8B8D, background #F1F6F6, text #173233.

## Faster data entry (page refresh after each field)
Streamlit re-runs the page after every field change; R12 makes each re-run fast:
- Database reads are reused for 45 seconds inside your session (any save/delete clears them immediately, so you always see your own changes). Set `QCMS_READ_CACHE_SECONDS = 0` in secrets to switch off.
- Duplicate checks (Part Master, Supply Chain transactions) always read live data.
- Page/section activity logging runs in the background instead of waiting for the database.
- Employee-link lookup is reused for 30 seconds instead of two database calls on every re-run.
- PDF/Excel download files are built once per content and reused, not rebuilt on every keystroke.

## AI key setup made simple
- New `scripts/set_ai_key.sh`: paste the key once; it checks it with Anthropic, writes it correctly at the top of `.streamlit/secrets.toml` (backup kept) and prints the lines for Streamlit Cloud.

No SQL migration.
