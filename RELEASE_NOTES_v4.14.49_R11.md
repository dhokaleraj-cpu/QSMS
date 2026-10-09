# QCMS 4.14.49 R11 — 9 October 2026

Includes R10 (Forging PO source gate) and all earlier fixes.

## Part Master
- **Exact duplicate block:** Part Number / FSI Part Number identical to any existing Part Number or FSI Part Number, ignoring case, spaces, dashes, dots and slashes (`40-256 626` = `40256626`), cannot be saved.
- **4-digit similarity check:** if 4 or more consecutive digits match an existing Part Number / FSI Part Number (e.g. 40256626 vs 40257237 → `4025`), QCMS lists the similar Parts and requires ticking **Not a duplicate** before Save.
- **Save popup:** a modal "Part Master Saved" window (Part Number, FSI Part Number, Description) stays until OK is clicked.
- **Delete Part (Administrator only):** available on Part Master Entry and Part Master Records, with password confirmation. Shows where the Part is used (orders, POs, RMTC, inward, reports, complaints…). The database still refuses deletion while transactions reference the Part — reverse those first or set the Part INACTIVE.

## Global Search → AI Assistant
- New **AI Assistant** tab (Keyword Search kept as second tab).
- Ask in plain English for information, analysis or reports; results can be shown as tables and bar/line/pie charts with **Excel / CSV download**.
- Read-only, uses only the modules the user may View, tenant/RLS-scoped. Only the rows needed for the answer are sent to the Claude API.
- Configure `ANTHROPIC_API_KEY` (optional `QCMS_AI_MODEL`, default `claude-sonnet-5-5`) in `.streamlit/secrets.toml` and Streamlit Cloud secrets.

## Design
- `QCMS_10_Design_Concepts.html` preview (10 concepts). Pick one; it will be applied app-wide in the next release.

No SQL migration.
