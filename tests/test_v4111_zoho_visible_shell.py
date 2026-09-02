from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_visible_shell_contract():
    assert (ROOT / "VERSION").read_text().strip() in {"4.11.1", "4.11.2", "4.11.3", "4.11.4", "4.11.5", "4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4", "4.12.5", "4.12.6", "4.12.7", "4.12.8", "4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3", "4.13.4", "4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13", "4.14.14", "4.14.15", "4.14.16", "4.14.17", "4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23", "4.14.24"}
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
