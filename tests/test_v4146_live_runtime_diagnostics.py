from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v4146_version_build_and_global_strip():
    assert (ROOT / "VERSION").read_text().strip() in {"4.14.6", "4.14.7", "4.14.8", "4.14.9"}
    app = text("streamlit_app.py")
    assert any(token in app for token in ("4146-LIVE-RUNTIME-DIAGNOSTICS-FORCE-REDEPLOY", "4147-NEXT-STAGE-EMAIL-TEMPLATES-AUTO-OVERDUE-DEPLOY-TARGET", "4148-AUTO-SAFETY-SNAPSHOT-DIRTY-WORKTREE-DEPLOY", "4149-DEPENDENCY-BOOTSTRAP-REMOTE-DEPLOY"))
    assert "LIVE BUILD · QCMS" in app


def test_deployment_diagnostics_page_is_registered():
    app = text("streamlit_app.py")
    diag = text("app_pages/deployment_diagnostics.py")
    assert "deployment-diagnostics" in app
    assert "Deployment Diagnostics" in app
    assert "Git HEAD" in diag
    assert "REQUESTED FEATURE PROOF" in diag
    assert "All requested feature markers" in diag


def test_report_edit_controls_are_always_visible():
    met = text("app_pages/metlab_report.py")
    dim = text("app_pages/dimensional_report.py")
    assert "DIRECT METLAB EDIT SELECTOR v4.14.6 — always visible" in met
    assert "DIRECT DIMENSIONAL EDIT SELECTOR v4.14.6 — always visible" in dim
    assert 'section_bar("NEW / EDIT EXISTING METLAB REPORT")' in met
    assert 'section_bar("NEW / EDIT EXISTING DIMENSIONAL REPORT")' in dim
    assert "if report_rows:" not in met[met.index("DIRECT METLAB EDIT SELECTOR v4.14.6"):met.index("existing_record = service.get_metlab")]
    assert "if report_rows:" not in dim[dim.index("DIRECT DIMENSIONAL EDIT SELECTOR v4.14.6"):dim.index("existing_record = service.get_dimensional")]


def test_opening_stock_has_supply_home_quick_action():
    supply = text("app_pages/supply_chain.py")
    assert "OPENING STOCK & IMPORT" in supply
    assert "Open Opening Stock & Import" in supply
    assert '"supply-opening-stock"' in supply


def test_manifest_declares_forced_redeploy_and_diagnostics():
    manifest = text("DEPLOYMENT_MANIFEST.json")
    assert any(token in manifest for token in ('"version": "4.14.6"', '"version": "4.14.7"', '"version": "4.14.8"', '"version": "4.14.9"'))
    assert '"live_runtime_diagnostics"' in manifest
    assert '"forced_streamlit_redeploy_commit"' in manifest
