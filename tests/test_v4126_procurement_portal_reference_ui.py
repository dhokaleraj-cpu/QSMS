from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_and_reference_ui_build_marker():
    assert (ROOT / "VERSION").read_text().strip() == "4.12.6"
    ui = (ROOT / "core/ui.py").read_text()
    auth = (ROOT / "core/auth.py").read_text()
    assert "4126-PROCUREMENT-PORTAL-REFERENCE-UI" in ui
    assert "4126-PROCUREMENT-PORTAL-REFERENCE-UI" in auth


def test_whole_app_reference_palette_and_typography_are_last_layer():
    ui = (ROOT / "core/ui.py").read_text()
    for token in (
        "def _apply_v4126_procurement_reference_style",
        "_apply_v4126_procurement_reference_style()",
        "--qcms-ref-red:#B20738",
        "--qcms-ref-bg:#EFEFEF",
        '--qcms-ref-font:Arial,"Helvetica Neue",Helvetica,sans-serif',
        "border-bottom:2px solid var(--qcms-ref-red)",
        "border-radius:2px!important",
        "background:var(--qcms-ref-red)!important",
        "background:var(--qcms-ref-blue)!important",
    ):
        assert token in ui


def test_stage_titles_and_field_borders_match_reference_contract():
    ui = (ROOT / "core/ui.py").read_text()
    assert '[class*="st-key-fsi_stage_"] div[data-testid="stExpander"] summary' in ui
    assert 'color:var(--qcms-ref-red)!important;font-family:var(--qcms-ref-font)!important;font-size:14px!important' in ui
    assert '[data-baseweb="input"],[data-baseweb="select"]>div,textarea' in ui
    assert 'border:1px solid #C9CED2!important' in ui
    assert 'div[data-testid="stDataFrame"] [role="columnheader"]' in ui


def test_login_uses_same_reference_visual_language():
    auth = (ROOT / "core/auth.py").read_text()
    for token in ("#B20738", "#EFEFEF", 'Arial,"Helvetica Neue",Helvetica,sans-serif', "border-radius:2px!important", "#2E86C1"):
        assert token in auth


def test_v4126_requires_no_database_migration():
    assert list((ROOT / "supabase/migrations").glob("*v4126*.sql")) == []
