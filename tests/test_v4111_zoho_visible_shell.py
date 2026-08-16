from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_visible_shell_contract():
    assert (ROOT / "VERSION").read_text().strip() in {"4.11.1", "4.11.2", "4.11.3", "4.11.4", "4.11.5"}
    ui = (ROOT / "core" / "ui.py").read_text()
    auth = (ROOT / "core" / "auth.py").read_text()
    required = [
        "QCMS 4.11.1 — Zoho-inspired clean white/blue enterprise shell visibility layer.",
        "--qcms-zoho-blue:#1884D8",
        "background:#FFFFFF!important",
        "color:#17202A!important",
        "color:#111827!important",
        "color:#202A33!important",
        "box-shadow:inset 0 -3px 0 #1784D8!important",
        "opacity:1!important;visibility:visible!important",
        "4111-ZOHO-VISIBLE-SHELL",
    ]
    for marker in required:
        assert marker in ui
    assert "4111-ZOHO-VISIBLE-SHELL" in auth


def test_records_centralization_remains_in_place():
    app = (ROOT / "streamlit_app.py").read_text()
    assert "RECORD_ROUTES = {" in app
    assert '**{path: "Records" for path in RECORD_ROUTES}' in app
    for route in (
        "part-records", "process-records", "grade-records", "reference-records",
        "employee-records", "standards-records", "rmtc-records", "inward-records",
        "osp-records", "complaint-records", "qc-calculation-records",
        "inspection-layout-records", "dimensional-records", "metlab-records",
    ):
        assert f'("{route}",' in app
