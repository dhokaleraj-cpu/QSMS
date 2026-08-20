from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v4127_visual_intent_is_preserved_by_v4128_shell():
    assert tuple(map(int, (ROOT / "VERSION").read_text().strip().split("."))) >= (4, 12, 8)
    ui = (ROOT / "core/ui.py").read_text()
    app = (ROOT / "streamlit_app.py").read_text()
    assert "4127-EXACT-PREVIEW-ENTERPRISE-UI" in ui
    assert "QCMS v4.12.8 — responsive enterprise navigation contract" in app


def test_preview_shell_is_structurally_rebuilt_without_fixed_overlap():
    ui = (ROOT / "core/ui.py").read_text()
    app = (ROOT / "streamlit_app.py").read_text()
    for token in (
        "def render_left_navigation",
        "--qcms-red:#C60035",
        "--qcms-charcoal:#242424",
        "qcms_workspace",
        "fsi-user-avatar",
        "fsi-page-chevron",
    ):
        assert token in (ui + app)
    assert "position:fixed!important" not in ui
    assert "rail_col, content_col = st.columns" in app


def test_preview_forms_tables_sections_and_cards_contract():
    ui = (ROOT / "core/ui.py").read_text()
    for token in (
        "border:1px solid var(--qcms-line-dark)!important",
        'div[data-testid="stDataFrame"] [role="columnheader"]',
        'div[data-testid="stDataFrame"] [role="gridcell"]',
        ".fsi-section-bar:after",
        ".fsi-kpi:before,.fsi-status-card:before",
        ".supply-order-card",
    ):
        assert token in ui


def test_v4128_is_ui_report_routing_only_and_preserves_database_schema():
    assert not list((ROOT / "supabase/migrations").glob("*v4128*.sql"))
