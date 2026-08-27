from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_v4145_version_and_live_banner():
    assert tuple(map(int, (ROOT / "VERSION").read_text().strip().split("."))) >= (4, 14, 5)
    assert any(token in text("app_pages/dashboard.py") for token in ("4145-DEPLOY-VERIFY-DIRECT-REPORT-EDIT-SMTP-TENANT-GUIDE", "4146-LIVE-RUNTIME-DIAGNOSTICS-FORCE-REDEPLOY", "4147-NEXT-STAGE-EMAIL-TEMPLATES-AUTO-OVERDUE-DEPLOY-TARGET", "4148-AUTO-SAFETY-SNAPSHOT-DIRTY-WORKTREE-DEPLOY", "4149-DEPENDENCY-BOOTSTRAP-REMOTE-DEPLOY", "41410-PO-SHIPTO-MASTER-LOGIN-REQUISITIONER", "41411-PO-MASTER-HSN-PRICE-FORM-EMAIL-CONFIRM-SERIES", "41412-RM-TYPE-PO-RM-DETAILS-FORGING-FILTER-DUPLICATE-GUARD", "41413-METLAB-CASE-DEPTH-RECORD-EMAIL-TEMPLATE-TEST-CONFIRM", "41414-LAYOUT-CASE-DEPTH-RM-PRICE-COMPANY-BRANCH", "41415-DIRECT-PRODUCTION-FLOW-EMAIL-TEMPLATE-TEST"))
    assert "LIVE RELEASE VERIFICATION" in text("app_pages/dashboard.py")


def test_direct_edit_selectors_are_visible():
    met = text("app_pages/metlab_report.py")
    dim = text("app_pages/dimensional_report.py")
    rmtc = text("app_pages/rmtc_pages.py")
    assert "Select Existing MetLAB Report to Edit" in met
    assert "Load Selected MetLAB Report for Edit" in met
    assert "Select Existing Dimensional Report to Edit" in dim
    assert "Load Selected Dimensional Report for Edit" in dim
    assert "Select Existing RMTC to Edit" in rmtc
    assert "Load Selected RMTC for Edit" in rmtc


def test_stopiteration_guard_and_smtp_tenant_guidance():
    met = text("app_pages/metlab_report.py")
    email = text("app_pages/email_settings.py")
    assert 'next((row for row in all_plans if str(row.get("id")) == plan_id), recommended or {})' in met
    assert "TENANT SMTP AUTH BLOCK" in email
    assert "QCMS cannot override this from application code" in email


def test_deployment_manifest_and_opening_stock_route():
    streamlit = text("streamlit_app.py")
    supply = text("app_pages/supply_chain.py")
    manifest = text("DEPLOYMENT_MANIFEST.json")
    assert "supply-opening-stock" in streamlit
    assert "Opening Stock Excel Import" in supply
    assert '"remote_push_verification"' in manifest
