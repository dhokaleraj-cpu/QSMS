# QCMS / QSMS cumulative handover — 4.14.49 R13

Release date: 9 October 2026. Supersedes R12/R11/R10. Base 4.14.49, build 41449-ANDROID-SINGLE-NATIVE-DRAWER-V12; manifest release_revision = R13. No SQL migration.

## Install / push / online
```bash
bash "$HOME/Downloads/QSMS_LIVE_DEPLOY_UPDATE_v4.14.49_R13.command"
```
Updater backs up, installs, runs gates and pushes to GitHub main; Streamlit Cloud redeploys automatically. Secrets online: Streamlit Cloud → app ⋮ → Settings → Secrets (paste local `.streamlit/secrets.toml`: `cat ~/QSMS/.streamlit/secrets.toml | pbcopy`).

## R13 contracts
- core/system_settings.py: AI_MODE_KEY `qcms.system.ai_assistant_mode` in master_value_catalog (one ACTIVE row; value ALL / ADMIN_ONLY / DISABLED); `get_ai_mode(repo)` → (mode, source) with secret override QCMS_AI_MODE; `ai_allowed(mode, profile)`; `set_ai_mode(repo, mode, profile)` admin-only (is_admin). Note: master_value_catalog RLS allows tenant users to write, so the admin-only rule is enforced in the app; the secret override is the hard switch.
- app_pages/system_settings.py route `system-settings` (Admin submenu, USER_ACCESS permission + is_admin check).
- app_pages/global_search.py: if not ai_allowed → keyword search only.
- core/kpi_service.py: 10 pure builders (DASHBOARDS list: key, title, module_key, tables, builder) returning Dashboard(tiles×4, charts, tables). Status thresholds inside each builder. Chart colours validated (teal #00968f first).
- app_pages/kpi_dashboards.py route `kpi-dashboards` (module "KPI Dashboards"): period filter, overview strip, pills selector, plotly charts, data tables, Excel download (deferred callable).
- streamlit_app.py: HEADER_NAV (Home, KPIs, Masters, Supply, Quality, Reports, Records, Admin); RAIL_NAV grouped with `(None, "<Group>", "", "")` heading rows rendered by core/ui.render_left_navigation as `.qcms-rail-head`; scripts/verify_phase1.py expects kpi-dashboards + system-settings pages.
- tests/test_r13_kpi_admin_ai_layout.py (15 tests incl. preview-mode AppTest render).

## Acceptance
1. Admin → System Settings: set Disabled → Search shows keyword only; Admins only → non-admin sees keyword only; Enabled → all.
2. KPIs page: overview strip + each of 10 dashboards with live data; Excel download.
3. Left menu groups and top menu as above on desktop; Android drawer unaffected.
