from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v41416_release_contract_is_retained():
    version = tuple(int(part) for part in (ROOT / "VERSION").read_text().strip().split("."))
    assert version >= (4, 14, 16)
    assert (ROOT / "supabase/migrations/20260828120000_qcms_permissions_po_approval_supply_notifications_v41416.sql").exists()
    assert (ROOT / "docs/RELEASE_4_14_16.md").exists()


def test_permission_precedence_and_three_layers():
    sql = text("supabase/migrations/20260828120000_qcms_permissions_po_approval_supply_notifications_v41416.sql")
    access = text("core/access.py")
    user_access = text("app_pages/user_access.py")
    assert "user_section_permissions" in sql
    assert "department_module_defaults" in sql
    assert "can_validate" in sql
    assert "Explicit user permission is authoritative" in sql
    assert "qcms_current_department" in sql
    assert "Validate/Review" in user_access
    assert "DEPARTMENT → MODULE DEFAULTS" in user_access
    assert "explicit User Module Permission row is authoritative" in access


def test_po_cancel_reissue_and_manager_approval():
    sql = text("supabase/migrations/20260828120000_qcms_permissions_po_approval_supply_notifications_v41416.sql")
    service = text("core/supply_chain_service.py")
    page = text("app_pages/supply_chain.py")
    assert "qcms_cancel_purchase_order" in sql
    assert "qcms_approve_purchase_order" in sql
    assert "reports_to_employee_id" in sql
    assert "PENDING_APPROVAL" in service
    assert "replacement_purchase_order_id" in service
    assert "replaces_purchase_order_id" in service
    assert "Cancel & Reissue with New Supplier" in page
    assert "Approve Purchase Order" in page
    assert "supply_po_reissue_source_ids" in page


def test_pending_approval_is_not_receiptable_and_status_constraints_allow_it():
    sql = text("supabase/migrations/20260828120000_qcms_permissions_po_approval_supply_notifications_v41416.sql")
    service = text("core/supply_chain_service.py")
    assert "supply_rm_purchase_orders_status_check" in sql and "PENDING_APPROVAL" in sql
    assert "supply_forging_orders_status_check" in sql
    assert 'if str(po.get("status")) in {"CANCELLED", "PENDING_APPROVAL"}' in service
    assert 'if str(fo.get("status")) in {"CANCELLED", "PENDING_APPROVAL"}' in service


def test_rm_po_item_identity_and_section_security():
    page = text("app_pages/supply_chain.py")
    part = text("app_pages/part_master.py")
    users = text("app_pages/user_access.py")
    assert '"Raw Material Type"' in page
    assert '"Material Grade"' in page
    assert '"Section Size"' in page
    assert 'SUPPLIER_TECHNICAL' in part
    assert 'PRICE_HISTORY' in part
    assert 'SECTION VISIBILITY / EDIT CONTROL' in users


def test_supply_chain_coloured_excel_and_employee_notifications():
    page = text("app_pages/supply_chain.py")
    assert "PatternFill" in page
    assert "PENDING STAGE RESPONSIBILITY & NOTIFICATIONS" in page
    assert "Send Current-Stage Notifications to Related Employees" in page
    assert "CUSTOMER_ORDER_STAGE_PENDING" in page
