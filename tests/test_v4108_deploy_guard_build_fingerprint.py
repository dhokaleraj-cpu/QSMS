from pathlib import Path


def test_build_fingerprint_visible():
    auth=Path("core/auth.py").read_text()
    ui=Path("core/ui.py").read_text()
    complaints=Path("app_pages/complaints.py").read_text()
    assert "BUILD 4108-RCA-DEPLOY-GUARD" in auth
    assert "BUILD 4108-RCA-DEPLOY-GUARD" in ui
    assert "Detailed RCA/CAPA workflow" in complaints

def test_version_4108():
    assert Path("VERSION").read_text().strip()=="4.10.8"
