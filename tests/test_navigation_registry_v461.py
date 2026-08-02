from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_has_explicit_navigation_registry_key() -> None:
    text = (ROOT / "streamlit_app.py").read_text()
    assert '("dashboard", st.Page(dashboard.render' in text
    assert "PAGE_BY_PATH = dict(PAGE_ITEMS)" in text
    assert 'PAGE_BY_PATH.get(path)' in text
    assert 'st.session_state["_qsms_pages"] = PAGE_BY_PATH' in text


def test_navigation_does_not_index_session_registry_directly() -> None:
    text = (ROOT / "streamlit_app.py").read_text()
    assert 'st.session_state["_qsms_pages"][path]' not in text
