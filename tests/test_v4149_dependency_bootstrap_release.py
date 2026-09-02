from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v4149_release_markers_and_pdf_test_dependency():
    assert (ROOT / "VERSION").read_text().strip() in {"4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13", "4.14.14", "4.14.15", "4.14.16", "4.14.17", "4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23", "4.14.24", "4.14.25", "4.14.26"}
    app = (ROOT / "streamlit_app.py").read_text()
    assert any(token in app for token in ("4149-DEPENDENCY-BOOTSTRAP-REMOTE-DEPLOY", "41410-PO-SHIPTO-MASTER-LOGIN-REQUISITIONER", "41411-PO-MASTER-HSN-PRICE-FORM-EMAIL-CONFIRM-SERIES", "41412-RM-TYPE-PO-RM-DETAILS-FORGING-FILTER-DUPLICATE-GUARD", "41413-METLAB-CASE-DEPTH-RECORD-EMAIL-TEMPLATE-TEST-CONFIRM"))
    req = (ROOT / "requirements.txt").read_text().lower()
    assert "pypdf" in req
    assert "pytest" in req
