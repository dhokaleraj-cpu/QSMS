from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_4104():
    assert (ROOT / "VERSION").read_text().strip() == "4.10.4"


def test_rmtc_heat_balance_number_input_is_float_safe():
    text = (ROOT / "app_pages" / "rmtc_pages.py").read_text()
    assert "heat_remaining=float(max(global_heat_steel-projected_commitment,0.0))" in text
    assert "max(current_heat_commitment-current_existing_remaining,0.0)" in text
    assert "max(projected_commitment-heat_inward_steel,0.0)" in text


def test_premium_login_workspace_is_present():
    auth = (ROOT / "core" / "auth.py").read_text()
    ui = (ROOT / "core" / "ui.py").read_text()
    assert "qcms_login_shell" in auth
    assert "qcms_login_panel" in auth
    assert "Welcome back" in auth
    assert "Sign in to QCMS" in auth
    assert "QUALITY CONTROL<br>MONITORING SYSTEM" in auth
    assert "QCMS 4.10.4 — premium authentication workspace" in ui
    assert "qcms-login-hero" in ui
    assert "qcms-login-security" in ui
