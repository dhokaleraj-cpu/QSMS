from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v4149_release_markers_and_pdf_test_dependency():
    assert (ROOT / "VERSION").read_text().strip() == "4.14.9"
    app = (ROOT / "streamlit_app.py").read_text()
    assert "4149-DEPENDENCY-BOOTSTRAP-REMOTE-DEPLOY" in app
    req = (ROOT / "requirements.txt").read_text().lower()
    assert "pypdf" in req
    assert "pytest" in req
