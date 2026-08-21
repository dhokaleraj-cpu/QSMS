from pathlib import Path


def test_build_fingerprint_visible():
    auth=Path("core/auth.py").read_text()
    ui=Path("core/ui.py").read_text()
    complaints=Path("app_pages/complaints.py").read_text()
    assert "BUILD 4109-LOGIN-IMPORT-GUARD" in auth or "BUILD 4110-MINIMAL-RECORDS-UX" in auth or "BUILD 4111-ZOHO-VISIBLE-SHELL" in auth
    assert "BUILD 4109-LOGIN-IMPORT-GUARD" in ui or "BUILD 4110-MINIMAL-RECORDS-UX" in ui or "BUILD 4111-ZOHO-VISIBLE-SHELL" in ui
    assert "Detailed RCA/CAPA workflow" in complaints

def test_version_4108():
    assert Path("VERSION").read_text().strip() in {"4.10.9", "4.11.0", "4.11.1", "4.11.2", "4.11.3", "4.11.4", "4.11.5", "4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4", "4.12.5", "4.12.6", "4.12.7", "4.12.8", "4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3"}
