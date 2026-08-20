from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v4127_release_marker_and_version():
    assert (ROOT / "VERSION").read_text().strip() == "4.12.7"
    ui = (ROOT / "core/ui.py").read_text()
    app = (ROOT / "streamlit_app.py").read_text()
    assert "4127-EXACT-PREVIEW-ENTERPRISE-UI" in ui
    assert "QCMS v4.12.7 — approved preview navigation contract" in app


def test_preview_shell_is_structurally_rebuilt_not_only_recolored():
    ui = (ROOT / "core/ui.py").read_text()
    app = (ROOT / "streamlit_app.py").read_text()
    for token in (
        "def _apply_v4127_exact_preview_style",
        "def render_left_navigation",
        "--preview-red:#C40035",
        "--preview-charcoal:#232323",
        "--preview-rail:154px",
        "position:fixed!important",
        "qcms-header-nav",
        "fsi-user-avatar",
        "qcms-rail-caption",
        "fsi-page-chevron",
    ):
        assert token in ui
    for token in ("HEADER_NAV = (", "RAIL_NAV = (", "render_left_navigation(current_module, RAIL_NAV)"):
        assert token in app
    assert "fsi_top_nav" not in app.split("nav = st.navigation", 1)[1]


def test_preview_forms_tables_sections_and_cards_contract():
    ui = (ROOT / "core/ui.py").read_text()
    for token in (
        'border:1px solid var(--preview-line-dark)!important',
        'div[data-testid="stDataFrame"] [role="columnheader"]',
        'div[data-testid="stDataFrame"] [role="gridcell"]',
        '.fsi-section-bar:after',
        '.fsi-kpi:before,.fsi-status-card:before',
        '.supply-order-card{border-radius:2px!important',
        'background:linear-gradient(180deg,#252525 0%,#1F1F1F 100%)!important',
    ):
        assert token in ui


def test_v4127_is_ui_only_and_preserves_database_schema():
    assert not list((ROOT / "supabase/migrations").glob("*v4127*.sql"))
