from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v4133_release_and_login_isolation():
    assert (ROOT / "VERSION").read_text().strip() in {"4.13.3", "4.13.4", "4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13", "4.14.14"}
    ui = (ROOT / "core/ui.py").read_text()
    auth = (ROOT / "core/auth.py").read_text()
    assert "4133-LOGIN-NO-MENU-STAWN-FOOTER-PORTAL-POLISH" in ui
    assert "4133-LOGIN-NO-MENU-STAWN-FOOTER-PORTAL-POLISH" in auth
    assert 'div.st-key-fsi_shell' in auth
    assert 'st-key-qcms_workspace' in auth
    assert 'st-key-fsi_left_rail' in auth
    assert 'display:none!important' in auth
    assert 'qcms_login_image_card' in auth
    assert 'app_footer()' in auth

def test_v4133_footer_and_header_contract():
    ui = (ROOT / "core/ui.py").read_text()
    reporting = (ROOT / "core/reporting.py").read_text()
    reports = (ROOT / "app_pages/reports.py").read_text()
    assert 'Developed by Rajesh Dhokale' in ui
    assert 'dhokaleraj@icloud.com' in ui
    assert 'Copyrights by <strong>STAWN</strong>' in ui
    assert 'Copyrights by STAWN' in reporting
    assert 'Copyrights by STAWN' in reports
    assert 'header[data-testid="stHeader"]' in ui
    assert 'div[data-testid="stDataFrame"]' in ui
