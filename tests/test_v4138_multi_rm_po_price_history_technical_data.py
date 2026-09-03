from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")

def test_release_build_marker():
    assert (ROOT / "VERSION").read_text().strip() in {"4.13.8", "4.13.9", "4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13", "4.14.14", "4.14.15", "4.14.16", "4.14.17", "4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23", "4.14.24", "4.14.25", "4.14.26", "4.14.27", "4.14.28"}
    marker = "4138-MULTI-RM-PO-PRICE-HISTORY-TECH-DATA"
    for rel in ("streamlit_app.py", "core/ui.py", "core/auth.py"):
        assert marker in text(rel)

def test_multi_customer_order_rm_po_allocation_schema_and_ui():
    sql = text("supabase/migrations/20260822213000_qcms_multi_rm_po_price_history_technical_data_v4138.sql")
    page = text("app_pages/supply_chain.py")
    service = text("core/supply_chain_service.py")
    assert "create table if not exists public.supply_purchase_order_sources" in sql
    assert "purchase_order_item_id" in sql
    assert "Select ELIGIBLE Customer Orders / Schedules for this RM Purchase Order" in page
    assert '"customer_order_ids":source_order_ids' in page
    assert 'raw_order_ids = p.get("customer_order_ids")' in service
    assert 'self.repo.insert("supply_purchase_order_sources"' in service

def test_supplier_fsi_part_price_history_start_end_price():
    sql = text("supabase/migrations/20260822213000_qcms_multi_rm_po_price_history_technical_data_v4138.sql")
    part = text("app_pages/part_master.py")
    po = text("app_pages/supply_chain.py")
    service = text("core/supply_chain_service.py")
    assert "create table if not exists public.part_supplier_price_history" in sql
    for token in ("start_date", "end_date", "price", "supplier_id", "part_id"):
        assert token in sql
    assert "Save Supplier / FSI Part Price History" in part
    assert "Start Date" in part and "End Date" in part and "Price" in part
    assert "PART MASTER TECHNICAL DATA & PRICE HISTORY" in po
    assert "def current_price" in service
    assert "def _record_purchase_price" in service

def test_part_master_supplier_technical_heading_value_rows_feed_po():
    sql = text("supabase/migrations/20260822213000_qcms_multi_rm_po_price_history_technical_data_v4138.sql")
    part = text("app_pages/part_master.py")
    service = text("core/supply_chain_service.py")
    reporting = text("core/purchase_order_reporting.py")
    assert "create table if not exists public.part_raw_material_technical_data" in sql
    assert "Heading" in part and "Value" in part and "Include on PO" in part
    assert "Save Supplier Technical Data" in part
    assert "def technical_data_snapshot" in service
    assert '"technical_data_snapshot":line["technical"]' in service
    assert "TECHNICAL DATA" in reporting
    assert 'item.get("technical_data_snapshot")' in reporting

def test_po_screen_no_longer_retypes_old_technical_commercial_fields():
    page = text("app_pages/supply_chain.py")
    # Technical values are maintained in Part Master instead of the PO entry screen.
    assert 'number_input("RM Rate / kg"' not in page
    assert 'text_input("Tool Cost"' not in page
    assert 'number_input("Profit %"' not in page
    assert 'text_input("Rejection + ICC"' not in page

def test_po_pdf_supports_multiple_vendor_lines_and_item_specific_history():
    reporting = text("core/purchase_order_reporting.py")
    assert "_continuation_items_bytes" in reporting
    assert "RAW MATERIAL / FORGING PARAMETERS & SUPPLIER TECHNICAL DATA" in reporting
    assert "PRICE REVISION HISTORY" in reporting
    assert "original/customer part number remains an internal qcms field" in reporting.lower()
    if (ROOT / "VERSION").read_text().strip() == "4.14.0":
        assert "display_items = list(items)[:3]" in reporting
    else:
        assert "One complete item pocket on the first page" in reporting
        assert "complete Price Revision History" in reporting

def test_v4137_po_history_is_backfilled_into_sources_and_price_history():
    sql = text("supabase/migrations/20260822213100_qcms_multi_rm_po_history_backfill_v4138.sql")
    assert "insert into public.supply_purchase_order_sources" in sql
    assert "Backfilled from controlled QCMS Purchase Order history" in sql
    assert "part_supplier_price_history" in sql
    assert "part_raw_material_technical_data" in sql
