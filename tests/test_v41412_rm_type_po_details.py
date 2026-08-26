from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from core.purchase_order_reporting import purchase_order_pdf_bytes

ROOT = Path(__file__).resolve().parents[1]


def _pdf_text(po_type: str) -> str:
    header = {
        "po_number": "PD9260800123", "po_type": po_type, "order_date": "2026-08-26",
        "delivery_date": "2026-09-05", "requisitioner": "Test Employee", "ship_via": "Road",
        "incoterm": "DAP", "payment_term": "NET 30",
        "vendor_snapshot": {"party_name": "Supplier One"}, "ship_to_snapshot": {"party_name": "FSI D9"},
        "subtotal": 1000, "grand_total": 1000,
    }
    item = {
        "item_no": "RM-100", "item_description": "Steel Bar", "hsn_sac_code": "72283019",
        "quantity": 100, "uom": "KGS", "unit_price": 10, "line_total": 1000,
        "technical_data_snapshot": [
            {"heading": "Raw Material Type", "value": "Round Black Bar"},
            {"heading": "Material Grade", "value": "20MnCr5"},
            {"heading": "Section Size", "value": "Dia 50 mm"},
            {"heading": "Forge wt", "value": "2.2 Kgs"},
            {"heading": "Gross wt", "value": "2.5 Kgs"},
            {"heading": "Forging Route", "value": "Closed Die Forging"},
        ],
        "price_history_snapshot": [{"start_date": "2026-08-01", "end_date": None, "price": 10}],
    }
    pdf = purchase_order_pdf_bytes(header, [item], terms_path=ROOT / "tests" / "missing_terms.pdf")
    return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)


def test_rm_po_prints_only_raw_material_identity_beneath_item():
    text = _pdf_text("RAW_MATERIAL")
    assert "RAW MATERIAL DETAILS" in text
    assert "Raw Material Type" in text and "Round Black Bar" in text
    assert "Material Grade" in text and "20MnCr5" in text
    assert "Section Size" in text and "Dia 50 mm" in text
    assert "Forge wt" not in text
    assert "Gross wt" not in text
    assert "Forging Route" not in text


def test_forging_po_retains_forging_parameters():
    text = _pdf_text("FORGING")
    assert "RAW MATERIAL / FORGING PARAMETERS & FSI TECHNICAL DATA" in text
    assert "Forging Route" in text and "Closed Die Forging" in text
    assert "Forge wt" in text


def test_part_master_rm_type_and_duplicate_word_controls_present():
    source = (ROOT / "app_pages" / "part_master.py").read_text(encoding="utf-8")
    assert '"Raw Material Type"' in source
    assert 'RAW_MATERIAL_TYPE_DEFAULTS = ("Round Black Bar", "Bright Bar")' in source
    assert 'duplicate_word_check=True' in source
    assert 'MasterService._fuzzy_word_duplicate' in source
