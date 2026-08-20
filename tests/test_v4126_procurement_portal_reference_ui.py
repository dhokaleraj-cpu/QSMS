from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_and_reference_ui_build_marker():
    assert tuple(map(int, (ROOT / "VERSION").read_text().strip().split("."))) >= (4, 12, 8)
    ui = (ROOT / "core/ui.py").read_text()
    auth = (ROOT / "core/auth.py").read_text()
    assert "4126-PROCUREMENT-PORTAL-REFERENCE-UI" in ui
    assert "4126-PROCUREMENT-PORTAL-REFERENCE-UI" in auth


def test_v4128_supersedes_layered_css_with_single_reference_style():
    ui = (ROOT / "core/ui.py").read_text()
    for token in (
        "def apply_global_style",
        "--qcms-red:#C60035",
        "--qcms-bg:#F5F6F7",
        '--qcms-font:Arial,Helvetica,"Segoe UI",sans-serif',
        "border-radius:2px!important",
        "background:linear-gradient(90deg,var(--qcms-red-dark),var(--qcms-red))",
    ):
        assert token in ui


def test_stage_titles_and_field_borders_match_reference_contract():
    ui = (ROOT / "core/ui.py").read_text()
    assert '[class*="st-key-fsi_stage_"] details[data-testid="stExpander"] summary' in ui
    assert '[data-baseweb="input"],[data-baseweb="select"]>div,textarea' in ui
    assert 'border:1px solid var(--qcms-line-dark)!important' in ui
    assert 'div[data-testid="stDataFrame"] [role="columnheader"]' in ui


def test_login_uses_same_reference_visual_language():
    auth = (ROOT / "core/auth.py").read_text()
    for token in ("#B20738", "#EFEFEF", 'Arial,"Helvetica Neue",Helvetica,sans-serif', "border-radius:2px!important", "#2E86C1"):
        assert token in auth


def test_v4126_requires_no_database_migration():
    assert list((ROOT / "supabase/migrations").glob("*v4126*.sql")) == []
