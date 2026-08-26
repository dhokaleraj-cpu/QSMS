from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v4148_release_markers():
    assert (ROOT / "VERSION").read_text().strip() in {"4.14.8", "4.14.9", "4.14.10"}
    app = (ROOT / "streamlit_app.py").read_text()
    assert any(token in app for token in ("4148-AUTO-SAFETY-SNAPSHOT-DIRTY-WORKTREE-DEPLOY", "4149-DEPENDENCY-BOOTSTRAP-REMOTE-DEPLOY", "41410-PO-SHIPTO-MASTER-LOGIN-REQUISITIONER"))

def test_v4147_features_retained():
    assert (ROOT / "core/notification_service.py").exists()
    assert "Opening Stock Excel Import" in (ROOT / "app_pages/supply_chain.py").read_text()
    assert (ROOT / "app_pages/deployment_diagnostics.py").exists()
