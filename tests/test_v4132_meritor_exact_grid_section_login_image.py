from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v4132_release_and_visual_contract():
    assert (ROOT / "VERSION").read_text().strip() in {"4.13.2", "4.13.3", "4.13.4", "4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0", "4.14.1"}
    ui = (ROOT / "core" / "ui.py").read_text()
    auth = (ROOT / "core" / "auth.py").read_text()
    assert "4132-MERITOR-EXACT-GRID-SECTION-LOGIN-IMAGE" in ui
    assert "--qcms-portal-maroon:#B20738" in ui
    assert "--qcms-portal-field:#FFFDF0" in ui
    assert "Exact enterprise table/grid contract" in ui
    assert "details[data-testid=\"stExpander\"] summary p" in ui
    assert "login_factory.jpeg" in auth
    assert "qcms_login_image_card" in auth
    assert 'st.columns([1.85, 1.0]' in auth
    assert (ROOT / "assets" / "login_factory.jpeg").exists()
