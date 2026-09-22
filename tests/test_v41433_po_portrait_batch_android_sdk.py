from io import BytesIO
from pathlib import Path
import json
from pypdf import PdfReader

from core.purchase_order_reporting import purchase_order_pdf_bytes, batch_purchase_order_pdf_bytes

ROOT = Path(__file__).resolve().parents[1]

def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _payload(number: str):
    header = {
        "po_number": number, "order_date": "2026-09-19", "delivery_date": "2026-09-30", "po_type": "FORGING",
        "vendor_snapshot": {"party_name": "TEST SUPPLIER", "city": "Pune"},
        "ship_to_snapshot": {"party_name": "Four Star Industries Private Limited D9", "city": "Pune"},
        "plant_snapshot": {"name": "Four Star Industries Private Limited D9", "address1": "Chakan MIDC", "address2": "Pune"},
        "requisitioner": "Purchasing Team", "subtotal": 1000, "grand_total": 1000,
    }
    item = {
        "item_no": "FSI-40256626", "item_description": "FORGING 24MM", "part_description_master": "DIFF SHAFT PINION",
        "quantity": 100, "unit_price": 10, "uom": "NOS", "gst_percent": 0, "gst_amount": 0, "line_total": 1000,
        "technical_data_snapshot": [], "price_history_snapshot": [],
        "customer_source_rows": [{"customer_po_number": "CPO-1", "po_position": "20", "part_number": "40256626", "part_description": "DIFF SHAFT PINION", "quantity": 100, "uom": "NOS", "customer_delivery_date": "2026-09-30"}],
    }
    return header, [item]


def test_release_identity_source_only():
    version = text("VERSION").strip()
    builds = {
        "4.14.33": ("41433-PO-PORTRAIT-TERMS-BATCH-PRINT-EMAIL-ANDROID-SDK", "4.14.32"),
        "4.14.34": ("41434-INDIVIDUAL-PO-PDF-ZIP-ANDROID-APK-BUILD", "4.14.33"),
        "4.14.35": ("41435-PO-WATERMARK-REMINDER-MOBILE-IOS", "4.14.34"),
        "4.14.36": ("41436-COMPLAINT-EMAIL-REGISTERS-REMINDERS-MOBILE-DRAWER", "4.14.35"),
        "4.14.37": ("41437-MOBILE-FULL-NAV-COMPLAINT-CARDS-PO-APPROVAL-DRAFT-EMAIL", "4.14.36"),
        "4.14.38": ("41438-ANDROID-NAV-SESSION-BRIDGE-FOOTER-REMOVE", "4.14.37"),
        "4.14.39": ("41439-ANDROID-CI-SIGNATURE-PERMANENT-FIX", "4.14.38"),
        "4.14.40": ("41440-ANDROID-NAV-READY-QUEUE-BUTTON-BRIDGE", "4.14.39"),
        "4.14.41": ("41441-ANDROID-LAMBDA-COMPILE-PERMANENT-FIX", "4.14.40"),
        "4.14.42": ("41442-LOCAL-JAVAC-OPTIONAL-CI-COMPILE-GUARD", "4.14.41"),
        "4.14.43": ("41443-ANDROID-STREAMLIT-SIDEBAR-NAV", "4.14.42"),
    }
    assert version in builds
    build, previous = builds[version]
    assert build in text("streamlit_app.py")
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] == version
    assert manifest["build"] == build
    assert manifest["previous_controlled_release"] == previous
    if version in {"4.14.35", "4.14.36", "4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43"}:
        assert manifest["database_schema_required"] == ("4.14.36" if version in {"4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43"} else version)
        assert manifest["database_migration_required"] is True
    else:
        assert manifest["database_schema_required"] == "4.14.28"
        assert manifest["database_migration_required"] is False


def test_terms_are_portrait_and_compacted():
    header, items = _payload("PD90190900033")
    pdf = purchase_order_pdf_bytes(header, items)
    reader = PdfReader(BytesIO(pdf))
    # PO front page + about seven portrait terms pages on the controlled 2023 terms source.
    assert 7 <= len(reader.pages) <= 9
    for page in reader.pages[1:]:
        assert float(page.mediabox.width) < float(page.mediabox.height)


def test_batch_pdf_combines_multiple_pos_and_multiple_copies_without_terms():
    a = _payload("PD-A"); b = _payload("PD-B")
    missing = ROOT / "tests" / "__missing_terms_v41433.pdf"
    single_pages = len(PdfReader(BytesIO(purchase_order_pdf_bytes(*a, terms_path=missing))).pages)
    combined = batch_purchase_order_pdf_bytes([a, b], copies_per_order=2, terms_path=missing)
    assert len(PdfReader(BytesIO(combined)).pages) == single_pages * 4


def test_batch_print_and_email_ui_contract():
    source = text("app_pages/supply_chain.py")
    for token in (
        "BATCH PRINT / EMAIL MULTIPLE PURCHASE ORDERS",
        "Purchase Orders for Batch Print / Email",
        "Copies per PO",
        "Send Selected POs by Email",
        "Confirm Batch Purchase Order Emails",
        "approval != \"APPROVED\"",
    ):
        assert token in source


def test_android_helper_bootstraps_sdk_when_missing():
    helper = text("mobile/android_qcms/BUILD_AND_INSTALL_SAMSUNG.command")
    assert ("QCMS Mobile v${MOBILE_VERSION}" in helper or "QCMS Mobile v0.1.1" in helper or "QCMS Mobile v0.1.2" in helper or "QCMS Mobile v0.1.3" in helper or "QCMS Mobile v0.1.4" in helper or "QCMS Mobile v0.1.5" in helper or "QCMS Mobile v0.1.6" in helper or "QCMS Mobile v0.1.7" in helper)
    assert "ANDROID SDK / CLI BOOTSTRAP" in helper
    assert "https://dl.google.com/android/cli/latest/" in helper
    assert '"platforms;android-35"' in helper
    assert '"build-tools;35.0.0"' in helper
    assert "install -r" in helper
