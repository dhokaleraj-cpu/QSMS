from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_marker_and_direct_production_flow_are_registered():
    assert (ROOT / "VERSION").read_text().strip() in {"4.14.15", "4.14.16", "4.14.17", "4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23", "4.14.24", "4.14.25", "4.14.26"}
    app = (ROOT / "streamlit_app.py").read_text()
    assert "41415-DIRECT-PRODUCTION-FLOW-EMAIL-TEMPLATE-TEST" in app
    service = (ROOT / "core/supply_chain_service.py").read_text()
    assert 'FLOW_FSI_RM_DIRECT_PRODUCTION = "FSI_RM_DIRECT_PRODUCTION"' in service
    assert 'FLOW_REQUIRES_FSI_RM = {FLOW_FSI_RM, FLOW_FSI_RM_DIRECT_PRODUCTION}' in service
    assert "Flow 3 · FSI RM → Direct Production" in service


def test_direct_production_keeps_rm_procurement_but_bypasses_forging():
    service = (ROOT / "core/supply_chain_service.py").read_text()
    ui = (ROOT / "app_pages/supply_chain.py").read_text()
    assert 'if flow not in FLOW_REQUIRES_FSI_RM:' in service
    assert 'elif flow == FLOW_FSI_RM_DIRECT_PRODUCTION:' in service
    assert 'reason = "Direct Production flow · Forging PO not required"' in service
    assert 'if self.flow_for_order(order) != FLOW_FSI_RM:' in service  # RM-to-Forger list remains Flow 1 only
    assert "Customer Order → RM Procurement → RM Receipt → Direct Production/Machining → Dispatch" in ui
    assert "FLOW_FSI_RM_DIRECT_PRODUCTION" in ui


def test_direct_production_machining_can_source_rm_receipt_with_genealogy():
    service = (ROOT / "core/supply_chain_service.py").read_text()
    migration = (ROOT / "supabase/migrations/20260827081500_qcms_direct_production_flow_v41415.sql").read_text()
    assert '"_source_type":"RM_RECEIPT"' in service
    assert 'accepted_production_quantity_pcs' in service
    assert 'source_rm_receipt_id' in migration
    assert "FSI_RM_DIRECT_PRODUCTION" in migration
    assert "Direct RM-to-Production is allowed only" in migration


def test_email_template_manual_test_has_dedicated_ui_and_confirmation():
    settings = (ROOT / "app_pages/email_settings.py").read_text()
    ui = (ROOT / "core/notification_ui.py").read_text()
    assert '"D", "TEST EMAIL TEMPLATE"' in settings
    assert "template_test_sender(" in settings
    assert 'Manual Test Recipient' in ui
    assert 'Manual Test CC' in ui
    assert 'Confirm Template Test Email' in ui
