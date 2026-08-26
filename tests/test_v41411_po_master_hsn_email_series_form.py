from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from core.purchase_order_reporting import purchase_order_pdf_bytes

ROOT = Path(__file__).resolve().parents[1]


def test_v41411_source_contracts():
    supply = (ROOT / "app_pages" / "supply_chain.py").read_text(encoding="utf-8")
    part = (ROOT / "app_pages" / "part_master.py").read_text(encoding="utf-8")
    notify_ui = (ROOT / "core" / "notification_ui.py").read_text(encoding="utf-8")
    reporting = (ROOT / "core" / "purchase_order_reporting.py").read_text(encoding="utf-8")
    migration = (ROOT / "supabase" / "migrations" / "20260826170500_qcms_po_master_hsn_series_entry_email_v41411.sql").read_text(encoding="utf-8")

    assert "Customer" in supply and "Part Number" in supply
    assert '"HSN / SAC Code": r.get("hsn_sac_code")' in part
    assert "Current Price" in supply
    assert 'raw.get("hsn_sac_code") or part.get("hsn_sac_code")' in supply
    assert "with st.form(form_key)" in supply
    assert any(token in notify_ui for token in ("Confirm notification recipient(s)", "Review & Confirm Email Recipients"))
    assert "Email notification after save" in notify_ui
    assert "drawCentredString(w/2,47" in reporting
    assert "return 'PD9'||to_char(current_date,'DDMM')||lpad(next_value::text,5,'0')" in migration


def test_v41411_po_pdf_footer_and_master_values_render():
    header = {
        "po_number": "PD9260800001",
        "order_date": "2026-08-26",
        "delivery_date": "2026-09-05",
        "requisitioner": "Test Employee",
        "ship_via": "Road",
        "incoterm": "DAP",
        "payment_term": "NET 30",
        "vendor_snapshot": {"party_name": "Supplier One", "address": "Supplier Address"},
        "ship_to_snapshot": {"party_name": "Customer Plant", "address": "Customer Ship To Address", "city": "Pune", "state": "Maharashtra", "country": "India"},
        "subtotal": 1200,
        "cgst_amount": 108,
        "sgst_amount": 108,
        "igst_amount": 0,
        "other_amount": 0,
        "grand_total": 1416,
    }
    item = {
        "item_no": "FSI-100",
        "fsi_part_number_snapshot": "FSI-100",
        "item_description": "Raw Material Item",
        "hsn_sac_code": "73261910",
        "quantity": 10,
        "uom": "KGS",
        "unit_price": 120,
        "line_total": 1200,
        "technical_data_snapshot": [{"heading": "RM Section", "value": "Dia 50"}],
        "price_history_snapshot": [{"start_date": "2026-08-01", "end_date": None, "price": 120, "remarks": "Current"}],
    }
    pdf = purchase_order_pdf_bytes(header, [item], terms_path=ROOT / "tests" / "no_terms_here.pdf")
    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)
    assert "PD9260800001" in text
    assert "73261910" in text
    assert "Test Employee" in text
    assert "Customer Ship To Address" in text
    assert "connect@fourstarindustries.com" in text
