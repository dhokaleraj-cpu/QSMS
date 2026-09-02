from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v4137_release_and_build_markers():
    assert (ROOT / "VERSION").read_text().strip() in {"4.13.7", "4.13.8", "4.13.9", "4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13", "4.14.14", "4.14.15", "4.14.16", "4.14.17", "4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23", "4.14.24", "4.14.25"}
    marker = "4138-MULTI-RM-PO-PRICE-HISTORY-TECH-DATA"
    assert marker in text("core/ui.py")
    assert marker in text("core/auth.py")
    assert marker in text("streamlit_app.py")


def test_fsi_part_number_is_a_separate_controlled_part_master_identity():
    defs = text("core/master_definitions.py")
    part = text("app_pages/part_master.py")
    labels = text("core/selection_labels.py")
    assert '"fsi_part_number"' in defs
    assert 'text_input("FSI Part Number"' in part
    assert 'FSI Part Number' in part
    assert 'FSI {fsi}' in labels


def test_part_master_excel_template_has_fsi_part_number_column():
    path = ROOT / "templates" / "Part_Master_Template.xlsx"
    assert path.exists()
    with ZipFile(path) as z:
        strings = " ".join(z.read(name).decode("utf-8", errors="ignore") for name in z.namelist() if name.endswith(".xml"))
    assert "FSI Part Number" in strings


def test_dedicated_approved_rmtc_part_worksheet_module_exists():
    routes = text("streamlit_app.py")
    page = text("app_pages/rmtc_pages.py")
    assert '"rmtc-approved-worksheet"' in routes
    assert '"Add Part Worksheet"' in routes
    assert "def render_approved_part_worksheet" in page
    assert "ADD PART NUMBER TO APPROVED RMTC" in page
    assert "add_part_to_approved_rmtc" in page


def test_customer_orders_use_live_three_month_stock_procurement_gate():
    service = text("core/supply_chain_service.py")
    page = text("app_pages/supply_chain.py")
    sql = text("supabase/migrations/20260822193000_qcms_supply_po_fsi_part_rmtc_worksheet_v4137.sql")
    assert "def system_available_qty" in service
    assert "def three_month_schedule_demand" in service
    assert "def procurement_check" in service
    assert "rolling three-month schedule quantity" in service
    assert "RM Procurement Required" in page
    for token in ("rm_procurement_required", "available_stock_pcs_snapshot", "three_month_schedule_pcs_snapshot", "procurement_shortage_pcs_snapshot"):
        assert token in sql


def test_controlled_rm_and_forging_purchase_order_module_and_reports_exist():
    page = text("app_pages/supply_chain.py")
    service = text("core/supply_chain_service.py")
    sql = text("supabase/migrations/20260822193000_qcms_supply_po_fsi_part_rmtc_worksheet_v4137.sql")
    routes = text("streamlit_app.py")
    assert "def render_purchase_orders" in page
    assert '"supply-purchase-orders"' in routes
    assert "def create_purchase_order" in service
    assert "create table if not exists public.supply_purchase_orders" in sql
    assert "create table if not exists public.supply_purchase_order_items" in sql
    for report in ("Pending Purchase Orders", "Raw Material Orders", "RM Section Orders", "Supplier Orders", "RM for Part Number Orders"):
        assert report in page


def test_purchase_order_print_uses_fsi_identity_and_controlled_terms_template():
    reporting = text("core/purchase_order_reporting.py")
    assert "FSI_STANDARD_PO_TERMS_2023.pdf" in reporting
    assert 'item.get("item_no")' in reporting
    assert 'item.get("item_description")' in reporting
    assert "original/customer part number remains an internal QCMS field" in reporting
    assert "original_part_number_snapshot" not in reporting
    assert (ROOT / "templates" / "FSI_STANDARD_PO_TERMS_2023.pdf").exists()


def test_rm_inward_and_forging_receipts_track_controlled_purchase_order():
    sql = text("supabase/migrations/20260822193000_qcms_supply_po_fsi_part_rmtc_worksheet_v4137.sql")
    service = text("core/supply_chain_service.py")
    assert "purchase_order_id uuid references public.supply_purchase_orders" in sql
    assert '"purchase_order_id": header.get("id")' in service
    assert "def purchase_order_received_qty" in service
    assert "def sync_purchase_order_status" in service


def test_fsi_part_number_is_propagated_to_major_quality_supply_and_report_modules():
    for rel in (
        "app_pages/material_inward.py", "app_pages/metlab_report.py", "app_pages/dimensional_report.py",
        "app_pages/inspection_home.py", "app_pages/inspection_layouts.py", "app_pages/osp_transactions.py",
        "app_pages/osp_inspections.py", "app_pages/npd_apqp.py", "app_pages/records_center.py",
        "app_pages/reports.py", "app_pages/supply_chain.py", "core/reporting.py",
    ):
        assert "FSI Part Number" in text(rel), rel
