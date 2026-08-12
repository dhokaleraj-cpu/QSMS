from pathlib import Path


def test_auth_login_layout_is_centered_and_shipment_style_inspired():
    auth = Path('core/auth.py').read_text()
    assert 'QUALITY CONTROL<br>MONITORING SYSTEM' in auth
    assert 'User Name' in auth
    assert 'Login' in auth
    assert 'Developed by Rajesh Dhokale' in auth
    assert 'Open controlled Phase 1 preview' in auth


def test_login_css_classes_present():
    ui = Path('core/ui.py').read_text()
    assert '.qcms-login-header-card' in ui
    assert '.qcms-login-footer' in ui
    assert 'st-key-qcms_login_shell' in ui


def test_rmtc_plan_balance_uses_consistent_float_inputs():
    page = Path('app_pages/rmtc_pages.py').read_text()
    assert 'value=float(heat_remaining or 0.0)' in page
    assert 'projected_commitment=round(float(max(float(current_heat_commitment or 0.0)-float(current_existing_remaining or 0.0),0.0))+projected_current_remaining,3)' in page
