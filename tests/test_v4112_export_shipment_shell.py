from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_version():
    assert (ROOT / "VERSION").read_text().strip() == "4.11.2"


def test_export_shipment_header_shell_contract():
    ui = (ROOT / "core/ui.py").read_text()
    for token in (
        "QCMS 4.11.2 — Export Shipment-inspired navy header and module navigation shell.",
        "--qcms-export-navy:#073462",
        "--qcms-export-blue:#0A68AC",
        "linear-gradient(110deg,var(--qcms-export-navy)",
        "fsi-user-pills",
        "QUALITY CONTROL<br>MONITORING SYSTEM",
        "4112-EXPORT-SHELL",
    ):
        assert token in ui
    header = ui.split("def render_shell_header", 1)[1].split("def render_side_navigation", 1)[0]
    assert "render_app_launcher(app_registry())" not in header
    assert "Account" in header and "Exit" in header


def test_export_shipment_module_rail_contract():
    ui = (ROOT / "core/ui.py").read_text()
    assert ".fsi-top-menu-title{" in ui
    assert "background:#FFFFFF!important" in ui
    assert "linear-gradient(105deg,#084C84 0%,#0C7BC7 100%)" in ui
    assert "[data-testid=\"stIconMaterial\"]{display:none!important;}" in ui


def test_records_centralization_is_retained():
    app = (ROOT / "streamlit_app.py").read_text()
    assert "RECORD_ROUTES = {" in app
    assert '**{path: "Records" for path in RECORD_ROUTES}' in app


def test_login_uses_same_build_fingerprint():
    auth = (ROOT / "core/auth.py").read_text()
    assert "4112-EXPORT-SHELL" in auth
