from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v4148_release_markers():
    assert (ROOT / "VERSION").read_text().strip() in {"4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13", "4.14.14", "4.14.15", "4.14.16", "4.14.17", "4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23", "4.14.24"}
    app = (ROOT / "streamlit_app.py").read_text()
    assert any(token in app for token in ("4148-AUTO-SAFETY-SNAPSHOT-DIRTY-WORKTREE-DEPLOY", "4149-DEPENDENCY-BOOTSTRAP-REMOTE-DEPLOY", "41410-PO-SHIPTO-MASTER-LOGIN-REQUISITIONER", "41411-PO-MASTER-HSN-PRICE-FORM-EMAIL-CONFIRM-SERIES", "41412-RM-TYPE-PO-RM-DETAILS-FORGING-FILTER-DUPLICATE-GUARD", "41413-METLAB-CASE-DEPTH-RECORD-EMAIL-TEMPLATE-TEST-CONFIRM"))

def test_v4147_features_retained():
    assert (ROOT / "core/notification_service.py").exists()
    assert "Opening Stock Excel Import" in (ROOT / "app_pages/supply_chain.py").read_text()
    assert (ROOT / "app_pages/deployment_diagnostics.py").exists()
