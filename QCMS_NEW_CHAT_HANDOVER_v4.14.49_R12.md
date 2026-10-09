# QCMS / QSMS cumulative handover — 4.14.49 R12

Release date: 9 October 2026. Supersedes R11/R10. Base 4.14.49, build 41449-ANDROID-SINGLE-NATIVE-DRAWER-V12; manifest release_revision = R12. No SQL migration.

## Install
```bash
bash "$HOME/Downloads/QSMS_LIVE_DEPLOY_UPDATE_v4.14.49_R12.command"
```
AI key (once): `bash /Users/dhokaleraj/QSMS/scripts/set_ai_key.sh` (hidden paste, validated via GET https://api.anthropic.com/v1/models, writes ANTHROPIC_API_KEY + QCMS_AI_MODEL at TOP of .streamlit/secrets.toml, keeps backup secrets.toml.bak_*, chmod 600). Streamlit Cloud: App → ⋮ → Settings → Secrets → paste the two lines at the top → Save.

## R12 contracts
- Design 07 Teal Material: core/ui.py `TEAL_MATERIAL_THEME` + `apply_teal_material_theme()` called at the end of `apply_global_style()` (override layer; older CSS contracts left intact for regression tests). Streamlit 1.60 renders `data-testid="stExpander"` on the wrapper, so selectors use `[data-testid="stExpander"] details`. Never set font-family on generic spans (Material icon ligatures). Login override block in core/auth.py `render_login`. config.toml primary #0F8B8D, bg #F1F6F6, text #173233.
- Performance: core/repository.py `_fresh_cache_seconds()` (secret QCMS_READ_CACHE_SECONDS, default 45), `_fresh_cache()`, `invalidate_read_cache()` called before insert/update/delete/bulk_upsert/rpc; `require_live=True` bypasses (used by Part duplicate check and SupplyChainService._assert_transaction_duplicate). core/activity.py `_submit_background` (2-thread pool). core/auth.py `_qcms_employee_link_memo` 30 s. core/export_cache.py `session_memo_bytes` wraps report/PO PDF & Excel builders (session LRU 24; bypassed outside Streamlit).
- Global Search tabs: "✨ AI Assistant", "🔎 Keyword Search".
- tests/test_r12_teal_theme_performance.py (6 tests).

## Acceptance
1. Login and all pages show teal design; icons render (no "arrow_right" text).
2. Type in Part Master / Inward / PO fields: re-runs noticeably faster after the first page load. Save → change visible immediately.
3. Run set_ai_key.sh, restart, Global Search → AI Assistant answers.
4. Duplicate Part / Forging PO gates still enforced.

Next: if any specific screen is still slow, note the page and the field; that screen's inputs can be moved into a single form (no re-run until Save).
