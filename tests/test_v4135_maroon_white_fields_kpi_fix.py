from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v4135_release_and_build_marker():
    assert (ROOT / "VERSION").read_text().strip() in {"4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13", "4.14.14", "4.14.15"}
    marker = "4135-MAROON-SECTIONS-WHITE-FIELDS-KPI-ICON-FIX"
    assert marker in text("core/ui.py")
    assert marker in text("core/auth.py")
    assert marker in text("streamlit_app.py")


def test_v4135_all_expanders_are_maroon_section_headings():
    ui = text("core/ui.py")
    assert 'details[data-testid="stExpander"] summary p' in ui
    assert 'details[data-testid="stExpander"] summary span' in ui
    assert '--qcms-v4135-maroon:#B20738' in ui
    assert 'color:var(--qcms-v4135-maroon)!important' in ui


def test_v4135_fields_use_white_list_pocket_surface_not_cream():
    ui = text("core/ui.py")
    assert '--qcms-v4135-field:#FFFFFF' in ui
    assert '--qcms-v4135-field-readonly:#F8F9FA' in ui
    assert 'background:var(--qcms-v4135-field)!important' in ui


def test_v4135_kpi_icon_has_reserved_column_and_cannot_overlap_value():
    ui = text("core/ui.py")
    assert 'padding:13px 14px 12px 62px!important' in ui
    assert 'transform:translateY(-50%)!important' in ui
    assert '.fsi-kpi-label,.fsi-kpi-value,.fsi-kpi-foot' in ui
