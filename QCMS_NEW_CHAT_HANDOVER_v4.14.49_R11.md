# QCMS / QSMS cumulative handover — 4.14.49 R11

Release date: 9 October 2026. Supersedes R10 (R10 = Forging PO source gate; see R10 handover). Base 4.14.49, build 41449-ANDROID-SINGLE-NATIVE-DRAWER-V12 unchanged; manifest release_revision = R11. No SQL migration.

## Install
```bash
bash "$HOME/Downloads/QSMS_LIVE_DEPLOY_UPDATE_v4.14.49_R11.command"
```
Updater: requires /Users/dhokaleraj/QSMS on main at 4.14.49; backup to ~/QSMS_BACKUPS; safety stash (fixed in R10: ignored files are no longer named as stash exclusions); payload SHA-256; preserves .env, .streamlit/secrets.toml, uploads, logs; compile, readiness, phase verification, focused R4–R11 tests, full pytest; commit + push; local/remote SHA check.

AI key (after install, once):
```bash
cd /Users/dhokaleraj/QSMS && printf '\nANTHROPIC_API_KEY = "sk-ant-PASTE-KEY"\nQCMS_AI_MODEL = "claude-sonnet-5-5"\n' >> .streamlit/secrets.toml
```
Also add the same two lines in Streamlit Cloud → App → Settings → Secrets.

## R11 contracts
- core/part_identity.py: `normalize_part_identity`, `longest_common_digit_run`, `find_part_conflicts(part_number, fsi, rows, exclude_id)` → {exact, similar}. Exact compares PN and FSI against existing PN and FSI (separator/case-insensitive). Similar = ≥4 consecutive common digits.
- app_pages/part_master.py: "Not a duplicate" checkbox in the header form; exact → "Duplicate Part Number/FSI Part Number is not allowed."; similar without tick → listed + blocked. Save → `save_success_dialog`. `_admin_part_delete_panel` (is_admin) on Entry and Records, with `part_usage_counts`. Delete via existing `qsms_delete_master_row` RPC (FK violations reported).
- core/ui.py: `save_success_dialog(title, message)` queues `_qcms_pending_save_dialog`; `render_pending_popups` shows an `@st.dialog` modal.
- core/ai_assistant.py: `QCMSAIAssistant(repo, SEARCH_SOURCES, can_view, api_key, model)`; tools describe_dataset / query_records / aggregate_records only (no write tools); datasets = SEARCH_SOURCES filtered by View permission; FK id → `<col>_label`; 5000-row fetch cap, 60 rows back to model, 10 tool rounds; reports → table + plotly chart + Excel/CSV. Uses httpx to https://api.anthropic.com/v1/messages (anthropic-version 2023-06-01).
- app_pages/global_search.py: tabs AI Assistant + Keyword Search (`_render_keyword_search`, previous behaviour).
- tests/test_r11_part_identity_ai_search.py: 16 tests (no network).

## Acceptance (live)
1. Part Master: save `40-256 626` when 40256626 exists → blocked. Save 40257237 → similar list; tick Not a duplicate → saved + modal popup.
2. As non-admin: no delete. As admin: delete an unused test part → deleted; delete a used part → usage table + database refusal message.
3. Global Search → AI Assistant: without key shows setup note; with key ask "open purchase orders by supplier with total value as a chart" → answer + chart + Excel download. Check a restricted user cannot get data from modules they cannot view.
4. Choose a design concept (1–10) for R12.
