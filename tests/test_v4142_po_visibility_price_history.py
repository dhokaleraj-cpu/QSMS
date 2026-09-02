from pathlib import Path
from io import BytesIO

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v4142_version_build_and_purchase_order_source_contract():
    assert (ROOT / "VERSION").read_text().strip() in {"4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13", "4.14.14", "4.14.15", "4.14.16", "4.14.17", "4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23", "4.14.24", "4.14.25", "4.14.26"}
    marker = "4142-PO-ORDER-VISIBILITY-FULL-PRICE-HISTORY"
    assert marker in text("core/ui.py")
    assert marker in text("core/auth.py")
    page = text("app_pages/supply_chain.py")
    service = text("core/supply_chain_service.py")
    assert "eligible_orders=[dict(r) for r in eligibility if bool(r.get(\"_po_eligible\"))]" in page
    assert "forging_eligible=[dict(r) for r in eligibility if bool(r.get(\"_po_eligible\")) and r.get(\"_po_source\")]" in page
    assert "Every open order remains visible in the status table above" in page
    assert "saved RM procurement decision" in service
    assert "current system stock is sufficient for the rolling three-month schedule" not in service
    assert "line_fsi_part_numbers" in page and "line_fsi_part_numbers" in service
    assert "section_bar," in page, "Purchase Order page must import section_bar before using the technical/price-history section"


def test_v4142_price_history_keeps_closed_rows_and_cost_components():
    service = text("core/supply_chain_service.py")
    part = text("app_pages/part_master.py")
    migration = text("supabase/migrations/20260825172000_qcms_po_price_history_v4142.sql")
    report = text("core/purchase_order_reporting.py")
    assert 'eq={"part_id": part_id, "supplier_id": supplier_id}' in service
    assert '"INACTIVE"' not in service[service.index("def price_history("):service.index("def price_history_for_po(")]
    for token in ("freight", "tool_cost", "packing_forwarding", "profit", "icc_rejection"):
        assert token in migration
        assert token in service
    for label in ("Basic Rate", "Freight", "Tool Cost", "P&F", "Profit", "ICC/Rej.", "Remark"):
        assert label in part
    po_history = service[service.index("def price_history_for_po("):service.index("def purchase_order_items_for_print(")]
    assert "<= target" not in po_history
    assert "complete supplier/FSI-Part price revision history" in po_history


def test_v4142_po_pdf_prints_full_history_for_each_item():
    import sys
    sys.path.insert(0, str(ROOT))
    from core.purchase_order_reporting import purchase_order_pdf_bytes

    header = {
        "po_number": "PD900999", "order_date": "2026-08-25", "delivery_date": "2026-09-10",
        "requisitioner": "Rajesh Dhokale", "ship_via": "Road", "incoterm": "DAP, CHAKAN",
        "payment_term": "NET 30 DAYS AFTER GRN", "quotation_reference": "QTN-88",
        "quotation_date": "2026-08-20", "currency": "INR", "subtotal": 1000, "grand_total": 1180,
        "vendor_snapshot": {"party_name": "Sunrise Engineering", "address": "Pune, Maharashtra"},
    }
    history_a = [
        {"start_date": "2024-11-13", "end_date": "2026-04-29", "price": 171.44, "freight": 50, "tool_cost": 20, "packing_forwarding": 9.5, "profit": 1.8, "icc_rejection": 3.8, "remarks": "Old price"},
        {"start_date": "2026-04-30", "end_date": "2026-07-30", "price": 225.41, "freight": 50, "tool_cost": 50, "packing_forwarding": 10, "profit": 1.8, "icc_rejection": 3.8, "remarks": "Raw Material Price Increase"},
        {"start_date": "2026-07-31", "end_date": None, "price": 242.18, "freight": 50, "tool_cost": 50, "packing_forwarding": 10, "profit": 1.8, "icc_rejection": 3.8, "remarks": "New Price"},
    ]
    history_b = [
        {"start_date": "2025-01-01", "end_date": "2025-08-31", "price": 400, "remarks": "Initial approved price"},
        {"start_date": "2025-09-01", "end_date": "2026-03-31", "price": 500, "remarks": "Price Increase 2/kg"},
        {"start_date": "2026-04-01", "end_date": None, "price": 450, "remarks": "Price decrease 5/kg"},
    ]
    items = [
        {"item_no": "9346", "item_description": "Differential Spider", "quantity": 1000, "unit_price": 242.18, "uom": "NOS", "gst_percent": 18, "gst_amount": 0, "line_total": 242180, "hsn_sac_code": "87085000", "technical_data_snapshot": [{"heading": "Section Size", "value": "50 mm Round"}], "price_history_snapshot": history_a},
        {"item_no": "2731", "item_description": "Bush", "quantity": 2000, "unit_price": 450, "uom": "NOS", "gst_percent": 18, "gst_amount": 0, "line_total": 900000, "hsn_sac_code": "87085000", "technical_data_snapshot": [{"heading": "Section Size", "value": "42 mm Round"}], "price_history_snapshot": history_b},
    ]
    pdf = purchase_order_pdf_bytes(header, items, terms_path=ROOT / "templates" / "__missing__.pdf")
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) >= 2
    joined = "\n".join((p.extract_text() or "") for p in reader.pages)
    assert "PRICE REVISION HISTORY" in joined
    assert "Old price" in joined and "New Price" in joined
    assert "Price decrease 5/kg" in joined
    assert "START DATE" in joined and "END DATE" in joined and "PRICE" in joined and "REMARK" in joined
    assert "9346" in joined and "2731" in joined
