from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v4131_version_and_build():
    assert (ROOT / "VERSION").read_text().strip() in {"4.13.1", "4.13.2", "4.13.3", "4.13.4", "4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13", "4.14.14", "4.14.15"}
    ui = (ROOT / "core/ui.py").read_text()
    assert "4131-MERITOR-FIELD-SECTION-LOGIN-REFRESH" in ui


def test_meritor_reference_field_contract_is_global():
    ui = (ROOT / "core/ui.py").read_text()
    for token in (
        "--qcms-maroon:#B20738",
        "--qcms-field-bg:#FFFDF2",
        "--qcms-field-border:#CFC79F",
        "border:1.2px solid var(--qcms-field-border)",
        'label[data-testid="stWidgetLabel"] p',
        "color:var(--qcms-heading)!important",
    ):
        assert token in ui


def test_login_is_minimal_identification_panel():
    auth = (ROOT / "core/auth.py").read_text()
    assert '<div class="qcms-login-form-title">IDENTIFICATION</div>' in auth
    assert 'st.text_input("Login *"' in auth
    assert 'st.text_input("Password *"' in auth
    assert 'st.form_submit_button("Login"' in auth
    active = auth[auth.index("def render_login() -> None:"):auth.index("def render_first_admin_claim() -> None:")]
    assert 'with st.expander("Forgot password")' not in active
    assert 'if settings.allow_preview:' not in active
    assert 'qcms-login-footer' not in active
