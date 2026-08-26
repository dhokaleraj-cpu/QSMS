from pathlib import Path
from io import BytesIO

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v41410_version_and_po_ship_to_controls():
    assert (ROOT / "VERSION").read_text().strip() in {"4.14.10", "4.14.11", "4.14.12", "4.14.13"}
    app = text("streamlit_app.py")
    page = text("app_pages/supply_chain.py")
    service = text("core/supply_chain_service.py")
    sql = text("supabase/migrations/20260826152000_qcms_po_shipto_requisitioner_v41410.sql")
    assert any(token in app for token in ("41410-PO-SHIPTO-MASTER-LOGIN-REQUISITIONER", "41411-PO-MASTER-HSN-PRICE-FORM-EMAIL-CONFIRM-SERIES", "41412-RM-TYPE-PO-RM-DETAILS-FORGING-FILTER-DUPLICATE-GUARD", "41413-METLAB-CASE-DEPTH-RECORD-EMAIL-TEMPLATE-TEST-CONFIRM"))
    assert "SHIP-TO ADDRESS · MASTER CONTROLLED" in page
    assert "Customer Master" in page and "Supplier Master" in page and "Vendor / OSP Master" in page
    assert "ship_to_party_id" in page and "ship_to_source_type" in page
    assert "ship_to_snapshot = self._party_snapshot(ship_to_party)" in service
    assert "qcms_control_supply_po_identity" in sql
    assert "ship_to_party_id" in sql and "ship_to_source_type" in sql


def test_v41410_requisitioner_is_logged_in_employee_and_read_only():
    page = text("app_pages/supply_chain.py")
    service = text("core/supply_chain_service.py")
    sql = text("supabase/migrations/20260826152000_qcms_po_shipto_requisitioner_v41410.sql")
    assert "current_profile" in page
    assert "Requisitioner (Logged-in Employee)" in page
    assert "disabled=True" in page[page.index("Requisitioner (Logged-in Employee)")-250:page.index("Requisitioner (Logged-in Employee)")+350]
    assert "requisitioner_employee_id" in page and "requisitioner_employee_id" in service
    assert "qcms_current_login_employee_id()" in sql
    assert "new.requisitioner_employee_id" in sql and "new.requisitioner" in sql


def test_v41410_po_pdf_prints_selected_master_ship_to_and_requisitioner():
    import sys
    sys.path.insert(0, str(ROOT))
    from core.purchase_order_reporting import purchase_order_pdf_bytes

    header = {
        "po_number": "PD901010",
        "order_date": "2026-08-26",
        "delivery_date": "2026-09-15",
        "requisitioner": "Logged Employee",
        "ship_via": "Road",
        "incoterm": "DAP",
        "payment_term": "NET 30 DAYS",
        "quotation_reference": "QTN-100",
        "quotation_date": "2026-08-25",
        "currency": "INR",
        "subtotal": 1000,
        "grand_total": 1180,
        "vendor_snapshot": {"party_name": "PO Supplier", "address": "Supplier Address", "city": "Pune", "state": "Maharashtra"},
        "ship_to_snapshot": {
            "source_type": "CUSTOMER",
            "party_name": "Selected Customer Plant",
            "address": "Plot 22 Industrial Area",
            "city": "Chennai",
            "state": "Tamil Nadu",
            "country": "India",
            "tax_identifier": "GSTIN-TEST",
            "contact_person": "Stores Team",
            "phone": "9999999999",
            "email": "stores@example.com",
        },
    }
    items = [{
        "item_no": "FSI-1010",
        "item_description": "Controlled Item",
        "quantity": 10,
        "unit_price": 100,
        "uom": "NOS",
        "gst_percent": 18,
        "gst_amount": 180,
        "line_total": 1000,
        "technical_data_snapshot": [],
        "price_history_snapshot": [],
    }]
    pdf = purchase_order_pdf_bytes(header, items, terms_path=ROOT / "templates" / "__missing__.pdf")
    joined = "\n".join((p.extract_text() or "") for p in PdfReader(BytesIO(pdf)).pages)
    assert "SHIP TO" in joined
    assert "Selected Customer Plant" in joined
    assert "Plot 22 Industrial Area" in joined
    assert "Chennai" in joined
    assert "Logged Employee" in joined
