from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_marker_and_version():
    assert (ROOT / "VERSION").read_text().strip() in {"4.12.8", "4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3", "4.13.4", "4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13", "4.14.14", "4.14.15", "4.14.16", "4.14.17", "4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23"}
    ui = (ROOT / "core/ui.py").read_text()
    assert "4128-RESPONSIVE-ENTERPRISE-UI-REPORT-HUB" in ui


def test_workspace_uses_real_columns_and_no_fixed_overlay():
    app = (ROOT / "streamlit_app.py").read_text()
    ui = (ROOT / "core/ui.py").read_text()
    assert 'key="qcms_workspace"' in app
    assert 'rail_col, content_col = st.columns([1.22, 8.78]' in app
    assert 'with rail_col:' in app and 'with content_col:' in app
    assert "position:fixed!important" not in ui
    assert "pointer-events:auto!important" in ui


def test_header_navigation_and_contrast_contract():
    ui = (ROOT / "core/ui.py").read_text()
    assert "qcms_header_nav_active_" in ui
    assert "cursor:pointer!important" in ui
    assert ".fsi-page-title" in ui and "color:#2F3438!important" in ui
    assert ".fsi-section-bar" in ui and "background:#fff!important" in ui


def test_cards_fields_grids_match_enterprise_preview_contract():
    ui = (ROOT / "core/ui.py").read_text()
    for token in (
        ".fsi-kpi-grid,.fsi-status-grid",
        "grid-template-columns:repeat(4,minmax(0,1fr))",
        '[data-baseweb="input"],[data-baseweb="select"]>div,textarea',
        'div[data-testid="stDataFrame"] [role="columnheader"]',
        'div[data-testid="stDataFrame"] [role="gridcell"]',
    ):
        assert token in ui


def test_report_hub_registers_supply_chain_and_other_modules():
    app = (ROOT / "streamlit_app.py").read_text()
    reports = (ROOT / "app_pages/reports.py").read_text()
    for path in (
        "supply-chain-report", "rmtc-report", "inward-report",
        "dimensional-report", "metlab-report", "complaints-report",
        "traceability-report", "npd-report", "apqp-report", "qc-report",
        "inspection-layout-report", "standards-report",
    ):
        assert path in app
        assert path in reports
    assert "Supply Chain Order / Dispatch MIS" in reports


def test_v4128_has_no_database_migration():
    assert not list((ROOT / "supabase/migrations").glob("*v4128*.sql"))
