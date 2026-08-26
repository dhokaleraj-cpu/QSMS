from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v4149_release_markers_and_pdf_test_dependency():
    assert (ROOT / "VERSION").read_text().strip() in {"4.14.9", "4.14.10"}
    app = (ROOT / "streamlit_app.py").read_text()
    assert any(token in app for token in ("4149-DEPENDENCY-BOOTSTRAP-REMOTE-DEPLOY", "41410-PO-SHIPTO-MASTER-LOGIN-REQUISITIONER"))
    req = (ROOT / "requirements.txt").read_text().lower()
    assert "pypdf" in req
    assert "pytest" in req
