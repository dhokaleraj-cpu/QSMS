from io import BytesIO
from pathlib import Path
import json

from pypdf import PdfReader

from core.purchase_order_reporting import purchase_order_pdf_bytes

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v41432_release_identity_and_source_only_schema():
    version = text("VERSION").strip()
    assert version in {"4.14.32", "4.14.33", "4.14.34", "4.14.35", "4.14.36", "4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43"}
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] == version
    if version == "4.14.32":
        assert manifest["build"] == "41432-PO-PRINT-COMPACT-RM-TYPES-ANDROID-TEST"
        assert manifest["previous_controlled_release"] == "4.14.31"
    elif version == "4.14.33":
        assert manifest["build"] == "41433-PO-PORTRAIT-TERMS-BATCH-PRINT-EMAIL-ANDROID-SDK"
        assert manifest["previous_controlled_release"] == "4.14.32"
    elif version == "4.14.34":
        assert manifest["build"] == "41434-INDIVIDUAL-PO-PDF-ZIP-ANDROID-APK-BUILD"
        assert manifest["previous_controlled_release"] == "4.14.33"
    elif version == "4.14.35":
        assert manifest["build"] == "41435-PO-WATERMARK-REMINDER-MOBILE-IOS"
        assert manifest["previous_controlled_release"] == "4.14.34"
    elif version == "4.14.36":
        assert manifest["build"] == "41436-COMPLAINT-EMAIL-REGISTERS-REMINDERS-MOBILE-DRAWER"
        assert manifest["previous_controlled_release"] == "4.14.35"
    elif version == "4.14.37":
        assert manifest["build"] == "41437-MOBILE-FULL-NAV-COMPLAINT-CARDS-PO-APPROVAL-DRAFT-EMAIL"
        assert manifest["previous_controlled_release"] == "4.14.36"
    elif version == "4.14.38":
        assert manifest["build"] == "41438-ANDROID-NAV-SESSION-BRIDGE-FOOTER-REMOVE"
        assert manifest["previous_controlled_release"] == "4.14.37"
    elif version == "4.14.39":
        assert manifest["build"] == "41439-ANDROID-CI-SIGNATURE-PERMANENT-FIX"
        assert manifest["previous_controlled_release"] == "4.14.38"
    elif version == "4.14.40":
        assert manifest["build"] == "41440-ANDROID-NAV-READY-QUEUE-BUTTON-BRIDGE"
        assert manifest["previous_controlled_release"] == "4.14.39"
    elif version == "4.14.41":
        assert manifest["build"] == "41441-ANDROID-LAMBDA-COMPILE-PERMANENT-FIX"
        assert manifest["previous_controlled_release"] == "4.14.40"
    elif manifest["version"] == "4.14.42":
        assert manifest["build"] == "41442-LOCAL-JAVAC-OPTIONAL-CI-COMPILE-GUARD"
        assert manifest["previous_controlled_release"] == "4.14.41"
    else:
        assert manifest["build"] == "41443-ANDROID-STREAMLIT-SIDEBAR-NAV"
        assert manifest["previous_controlled_release"] == "4.14.42"
    if version in {"4.14.35", "4.14.36", "4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43"}:
        assert manifest["database_schema_required"] == ("4.14.36" if version in {"4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43"} else version)
        assert manifest["database_migration_required"] is True
    else:
        assert manifest["database_schema_required"] == "4.14.28"
        assert manifest["database_migration_required"] is False


def test_po_print_omits_customer_identity_adds_part_description_and_compacts_terms():
    header = {
        "po_number": "PD90190900001",
        "order_date": "2026-09-19",
        "delivery_date": "2026-09-30",
        "po_type": "FORGING",
        "vendor_snapshot": {"party_name": "TEST FORGING SUPPLIER", "city": "Pune"},
        "ship_to_snapshot": {"party_name": "Four Star Industries Private Limited D9", "city": "Pune"},
        "plant_snapshot": {"name": "Four Star Industries Private Limited D9", "address1": "Chakan MIDC", "address2": "Pune"},
        "requisitioner": "Purchasing Team",
        "subtotal": 1000,
        "grand_total": 1000,
    }
    item = {
        "item_no": "FSI-40256626",
        "item_description": "FORGING 24MM",
        "part_description_master": "DIFF SHAFT PINION",
        "hsn_sac_code": "73269099",
        "quantity": 100,
        "unit_price": 10,
        "uom": "NOS",
        "gst_percent": 0,
        "gst_amount": 0,
        "line_total": 1000,
        "technical_data_snapshot": [],
        "price_history_snapshot": [],
        "customer_source_rows": [{
            "customer": "SECRET CUSTOMER NAME MUST NOT PRINT",
            "customer_po_number": "CPO-778899",
            "po_position": "20",
            "part_number": "40256626",
            "part_description": "DIFF SHAFT PINION",
            "quantity": 100,
            "uom": "NOS",
            "customer_delivery_date": "2026-09-30",
        }],
    }
    pdf = purchase_order_pdf_bytes(header, [item])
    reader = PdfReader(BytesIO(pdf))
    all_text = "\n".join((p.extract_text() or "") for p in reader.pages)
    first_text = reader.pages[0].extract_text() or ""
    assert "SECRET CUSTOMER NAME MUST NOT PRINT" not in all_text
    assert "PO SOURCE REFERENCE" in first_text
    assert "CPO-778899" in first_text
    assert "40256626" in first_text
    assert "DIFF SHAFT PINION" in first_text
    assert "PART DESCRIPTION" in first_text.upper()
    # v4.14.33 supersedes the landscape imposition: controlled terms are compact portrait A4.
    assert 2 <= len(reader.pages) <= 9
    assert all(float(page.mediabox.width) < float(page.mediabox.height) for page in reader.pages[1:])


def test_controlled_raw_material_type_list():
    part = text("app_pages/part_master.py")
    assert 'RAW_MATERIAL_TYPE_DEFAULTS = ("Forging", "Round Black Bar", "Casting", "Bright Bar", "Ground Bar")' in part
    assert '_catalog_add_control(catalog, "part.rm_type"' not in part
    for value in ("Forging", "Round Black Bar", "Casting", "Bright Bar", "Ground Bar"):
        assert value in part


def test_android_test_shell_and_samsung_install_helper_are_packaged():
    mobile = ROOT / "mobile" / "android_qcms"
    required = [
        "settings.gradle",
        "build.gradle",
        "app/build.gradle",
        "app/src/main/AndroidManifest.xml",
        "app/src/main/java/com/fourstar/qcms/MainActivity.java",
        "BUILD_AND_INSTALL_SAMSUNG.command",
        "README_ANDROID.md",
    ]
    for rel in required:
        assert (mobile / rel).exists(), rel
    manifest = (mobile / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    activity = (mobile / "app/src/main/java/com/fourstar/qcms/MainActivity.java").read_text(encoding="utf-8")
    build = (mobile / "app/build.gradle").read_text(encoding="utf-8")
    installer = (mobile / "BUILD_AND_INSTALL_SAMSUNG.command").read_text(encoding="utf-8")
    assert "android.permission.INTERNET" in manifest
    assert 'android:usesCleartextTraffic="false"' in manifest
    assert "https://" in activity and ("QCMSMobile/0.1.0" in activity or "QCMSMobile/0.1.1" in activity or "QCMSMobile/0.1.2" in activity or "QCMSMobile/0.1.3" in activity or "QCMSMobile/0.1.4" in activity or "QCMSMobile/0.1.5" in activity or "QCMSMobile/0.1.6" in activity or "QCMSMobile/0.1.7" in activity or "QCMSMobile/0.1.8" in activity or "QCMSMobile/0.1.9" in activity)
    assert "service-role" not in activity.lower()
    assert "targetSdk 35" in build and "minSdk 26" in build
    assert "adb" in installer and "install -r" in installer and "assembleDebug" in installer
