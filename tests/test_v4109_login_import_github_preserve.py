from pathlib import Path


def test_login_helpers_are_imported():
    auth = Path("core/auth.py").read_text()
    assert "from core.ui import logo_data_uri, render_public_brand, safe" in auth
    assert "uri = logo_data_uri()" in auth
    assert "safe(settings.version)" in auth


def test_login_build_fingerprint():
    auth = Path("core/auth.py").read_text()
    ui = Path("core/ui.py").read_text()
    assert "4109-LOGIN-IMPORT-GUARD" in auth or "4110-MINIMAL-RECORDS-UX" in auth or "4111-ZOHO-VISIBLE-SHELL" in auth
    assert "4109-LOGIN-IMPORT-GUARD" in ui or "4110-MINIMAL-RECORDS-UX" in ui or "4111-ZOHO-VISIBLE-SHELL" in ui


def test_release_version():
    assert Path("VERSION").read_text().strip() in {"4.10.9", "4.11.0", "4.11.1", "4.11.2", "4.11.3", "4.11.4", "4.11.5", "4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4", "4.12.5", "4.12.6", "4.12.7", "4.12.8", "4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3", "4.13.4", "4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0"}

