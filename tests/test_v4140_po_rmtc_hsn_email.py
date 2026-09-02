from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v4140_version_and_build_marker():
    assert (ROOT / "VERSION").read_text().strip() in {"4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13", "4.14.14", "4.14.15", "4.14.16", "4.14.17", "4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23", "4.14.24", "4.14.25", "4.14.26", "4.14.27"}
    marker = "4140-PO-SOURCE-RMTC-VALIDATION-HSN-EMAIL"
    assert marker in text("streamlit_app.py")
    assert marker in text("core/ui.py")
    assert marker in text("core/auth.py")


def test_po_sources_use_explicit_supply_flow_and_visible_reasons():
    service = text("core/supply_chain_service.py")
    page = text("app_pages/supply_chain.py")
    migration = text("supabase/migrations/20260824121500_qcms_po_hsn_email_notifications_v4140.sql")
    assert 'explicit = str(order.get("supply_flow")' in service
    assert "def purchase_order_source_status" in service
    assert "supply_customer_orders add column if not exists supply_flow" in migration
    assert "CUSTOMER ORDER / SCHEDULE PURCHASE ORDER ELIGIBILITY" in page
    assert "PO Eligibility" in page and "Reason" in page
    assert "Select ELIGIBLE Customer Orders / Schedules for this RM Purchase Order" in page
    assert "Select ELIGIBLE Forging PO Source" in page


def test_added_rmtc_part_can_validate_and_decide_without_reopening_existing_parts():
    page = text("app_pages/rmtc_pages.py")
    assert "incremental_part_review" in page
    assert "Validate Added Part Against Masters" in page
    assert "Save Added Part Final Decision" in page
    assert "svc.validate_added_part" in page
    assert "svc.decide_added_part" in page
    assert "Existing accepted Parts remain released" in page


def test_po_hsn_sac_and_clean_item_layout():
    migration = text("supabase/migrations/20260824121500_qcms_po_hsn_email_notifications_v4140.sql")
    part = text("app_pages/part_master.py")
    po = text("core/purchase_order_reporting.py")
    supply = text("app_pages/supply_chain.py")
    assert "parts add column if not exists hsn_sac_code" in migration
    assert "supply_purchase_order_items add column if not exists hsn_sac_code" in migration
    assert "HSN / SAC Code" in part
    assert "HSN / SAC" in supply
    assert "HSN / SAC:" in po
    assert "No vertical grid lines in the PO item body" in po
    if (ROOT / "VERSION").read_text().strip() == "4.14.0":
        assert "display_items = list(items)[:3]" in po
    else:
        assert "One complete item pocket on the first page" in po
        assert "PRICE REVISION HISTORY" in po
    assert "_continuation_items_bytes" in po


def test_email_server_routing_outbox_and_server_side_delivery():
    migration = text("supabase/migrations/20260824121500_qcms_po_hsn_email_notifications_v4140.sql")
    page = text("app_pages/email_settings.py")
    service = text("core/notification_service.py")
    edge = text("supabase/functions/qcms-send-email/index.ts")
    app = text("streamlit_app.py")
    for token in ("qcms_email_settings", "qcms_notification_routes", "qcms_notification_outbox"):
        assert token in migration
    assert "RMTC_APPROVAL_PENDING" in migration and "DIMENSIONAL_APPROVAL_PENDING" in migration
    assert "EMAIL SERVER SETTINGS" in page
    assert "RESPONSIBILITY ROUTING" in page
    assert "TEST & NOTIFICATION OUTBOX" in page
    assert "class NotificationService" in service
    assert "Workflow execution must never" in service
    assert "qcms-send-email" in service
    assert "nodemailer" in edge
    assert "Email Server & Notifications" in app


def test_notifications_are_wired_to_key_workflows():
    rmtc = text("app_pages/rmtc_pages.py")
    dim = text("app_pages/dimensional_report.py")
    met = text("app_pages/metlab_report.py")
    supply = text("app_pages/supply_chain.py")
    osp = text("app_pages/osp_transactions.py")
    assert "RMTC_APPROVAL_PENDING" in rmtc
    assert "DIMENSIONAL_APPROVAL_PENDING" in dim
    assert "METLAB_APPROVAL_PENDING" in met
    assert "RM_PROCUREMENT_PENDING" in supply
    assert "RM_RECEIPT_PENDING" in supply or "FORGING_RECEIPT_PENDING" in supply
    assert "OSP_SAMPLE_PENDING" in osp
