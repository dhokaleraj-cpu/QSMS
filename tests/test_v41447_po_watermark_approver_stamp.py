from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from core import purchase_order_reporting as por


def test_watermark_is_20_percent_and_light():
    text = Path(por.__file__).read_text()
    assert 'setFillAlpha(0.20)' in text
    assert 'HexColor("#E8EBF0")' in text


def test_approved_stamp_contains_identity_and_timestamp():
    header = {
        "po_number": "PD9010100001",
        "order_date": "2026-09-22",
        "approval_status": "APPROVED",
        "approver_employee_name": "Rajesh Dhokale",
        "approver_employee_code": "EMP001",
        "approved_at": "2026-09-22T06:30:00+00:00",
        "subtotal": 100, "grand_total": 100,
    }
    item = {"item_no":"P-001","item_description":"Test Part","quantity":1,"uom":"PCS","unit_price":100,"gst_percent":0,"line_total":100}
    pdf = por.purchase_order_pdf_bytes(header, [item], terms_path="/__qcms_missing_terms__.pdf")
    page_text = PdfReader(BytesIO(pdf)).pages[0].extract_text()
    assert "APPROVED" in page_text
    assert "Rajesh Dhokale" in page_text
    assert "EMP001" in page_text
    assert "22-09-2026" in page_text
    assert "QCMS DIGITAL APPROVAL" in page_text


def test_pending_po_has_no_digital_approval_stamp():
    header = {
        "po_number": "PD9010100002",
        "order_date": "2026-09-22",
        "approval_status": "PENDING_APPROVAL",
        "subtotal": 100, "grand_total": 100,
    }
    item = {"item_no":"P-001","item_description":"Test Part","quantity":1,"uom":"PCS","unit_price":100,"gst_percent":0,"line_total":100}
    pdf = por.purchase_order_pdf_bytes(header, [item], terms_path="/__qcms_missing_terms__.pdf")
    page_text = PdfReader(BytesIO(pdf)).pages[0].extract_text()
    assert "QCMS DIGITAL APPROVAL" not in page_text
