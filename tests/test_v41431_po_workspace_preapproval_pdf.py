from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v41431_release_identity_and_source_only_schema_contract():
    assert text("VERSION").strip() in {"4.14.31", "4.14.32", "4.14.33", "4.14.34", "4.14.35", "4.14.36", "4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43"}
    builds = {"41431-PO-WORKSPACE-PREAPPROVAL-EDIT-CUSTOMER-REF-PDF", "41432-PO-PRINT-COMPACT-RM-TYPES-ANDROID-TEST", "41433-PO-PORTRAIT-TERMS-BATCH-PRINT-EMAIL-ANDROID-SDK", "41434-INDIVIDUAL-PO-PDF-ZIP-ANDROID-APK-BUILD", "41435-PO-WATERMARK-REMINDER-MOBILE-IOS", "41436-COMPLAINT-EMAIL-REGISTERS-REMINDERS-MOBILE-DRAWER", "41437-MOBILE-FULL-NAV-COMPLAINT-CARDS-PO-APPROVAL-DRAFT-EMAIL", "41438-ANDROID-NAV-SESSION-BRIDGE-FOOTER-REMOVE", "41439-ANDROID-CI-SIGNATURE-PERMANENT-FIX", "41440-ANDROID-NAV-READY-QUEUE-BUTTON-BRIDGE", "41441-ANDROID-LAMBDA-COMPILE-PERMANENT-FIX", "41442-LOCAL-JAVAC-OPTIONAL-CI-COMPILE-GUARD", "41443-ANDROID-STREAMLIT-SIDEBAR-NAV"}
    assert any(build in text("streamlit_app.py") for build in builds)
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] in {"4.14.31", "4.14.32", "4.14.33", "4.14.34", "4.14.35", "4.14.36", "4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43"}
    assert manifest["build"] in builds
    assert manifest["previous_controlled_release"] == {"4.14.30": "4.14.29", "4.14.31": "4.14.30", "4.14.32": "4.14.31", "4.14.33": "4.14.32", "4.14.34": "4.14.33", "4.14.35": "4.14.34", "4.14.36": "4.14.35", "4.14.37": "4.14.36", "4.14.38": "4.14.37", "4.14.39": "4.14.38", "4.14.40": "4.14.39", "4.14.41": "4.14.40", "4.14.42": "4.14.41", "4.14.43": "4.14.42"}[manifest["version"]]
    if manifest["version"] in {"4.14.35", "4.14.36", "4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43"}:
        assert manifest["database_schema_required"] == ("4.14.36" if manifest["version"] in {"4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43"} else manifest["version"])
        assert manifest["database_migration_required"] is True
        assert manifest["source_only_updater"] is False
    else:
        assert manifest["database_schema_required"] == "4.14.28"
        assert manifest["database_migration_required"] is False
        assert manifest["source_only_updater"] is True


def test_purchase_order_workspace_has_requested_separate_subpages():
    app = text("streamlit_app.py")
    page = text("app_pages/supply_chain.py")
    for route in (
        "supply-purchase-orders",
        "supply-po-order-list",
        "supply-po-edit",
        "supply-po-pdf",
        "supply-po-approval",
    ):
        assert route in app
        assert route in page
    for function_name in (
        "render_purchase_order_list",
        "render_purchase_order_edit_page",
        "render_purchase_order_pdf_page",
        "render_purchase_order_approval_page",
    ):
        assert f"def {function_name}" in page
    for label in ("PO Entry", "Order List", "Edit Purchase Order", "Purchase Order PDF", "Approval / Supplier Confirmation"):
        assert label in page


def test_pending_purchase_order_edit_does_not_require_supplier_confirmation():
    page = text("app_pages/supply_chain.py")
    service = text("core/supply_chain_service.py")
    assert "Supplier Confirmation is NOT required to edit or save it." in page
    assert "Supplier Confirmation is a separate downstream stage and NEVER blocks PO editing." in page
    assert '"supplier_confirmation_blocks_edit":False' in service.replace(" ", "")
    assert "if confirmation and was_approved" in service
    # The old pre-edit confirmation checkbox must not return.
    assert "I confirm this PO revision must be re-approved and re-confirmed" not in page


def test_po_source_selectors_and_list_show_customer_po_position_part_and_qty():
    page = text("app_pages/supply_chain.py")
    service = text("core/supply_chain_service.py")
    assert "Customer PO" in page
    assert "Pos" in page
    assert "Part" in page
    assert "Qty" in page
    for field in ("Customer PO Number", "PO Position", "Part Number", "PO Qty"):
        assert field in service
    for field in ("Customer PO Number", "PO Position", "Part Number", "PO Source Qty"):
        assert field in service


def test_controlled_po_pdf_prints_customer_source_reference_table():
    reporting = text("core/purchase_order_reporting.py")
    service = text("core/supply_chain_service.py")
    assert ("CUSTOMER PO / SOURCE REFERENCE" in reporting) or ("PO SOURCE REFERENCE" in reporting)
    assert "CUSTOMER PO NO." in reporting
    assert '"POS"' in reporting
    if text("VERSION").strip() in {"4.14.35", "4.14.36", "4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43"}:
        assert '"PART NUMBER"' not in reporting  # customer source PN intentionally hidden from supplier print
    else:
        assert '"PART NUMBER"' in reporting
    assert '"QTY"' in reporting
    if text("VERSION").strip() in {"4.14.35", "4.14.36", "4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43"}:
        assert '"DELIVERY"' not in reporting  # customer delivery date intentionally hidden from supplier print
    else:
        assert '"DELIVERY"' in reporting
    assert "customer_source_rows" in reporting
    assert 'item["customer_source_rows"] = customer_sources' in service


def test_records_center_routes_purchase_order_edit_to_dedicated_page():
    records = text("app_pages/records_center.py")
    assert 'route = "supply-po-edit"' in records


def test_v41431_online_verification_knows_new_po_release():
    phase = text("scripts/verify_phase1.py")
    readiness = text("scripts/check_online_readiness.py")
    assert ("41431-PO-WORKSPACE-PREAPPROVAL-EDIT-CUSTOMER-REF-PDF" in phase) or ("41432-PO-PRINT-COMPACT-RM-TYPES-ANDROID-TEST" in phase) or ("41433-PO-PORTRAIT-TERMS-BATCH-PRINT-EMAIL-ANDROID-SDK" in phase) or (("41434-INDIVIDUAL-PO-PDF-ZIP-ANDROID-APK-BUILD" in phase) or ("41435-PO-WATERMARK-REMINDER-MOBILE-IOS" in phase) or ("41436-COMPLAINT-EMAIL-REGISTERS-REMINDERS-MOBILE-DRAWER" in phase) or ("41437-MOBILE-FULL-NAV-COMPLAINT-CARDS-PO-APPROVAL-DRAFT-EMAIL" in phase) or ("41438-ANDROID-NAV-SESSION-BRIDGE-FOOTER-REMOVE", "41439-ANDROID-CI-SIGNATURE-PERMANENT-FIX" in phase))
    assert "v41431_po_workspace" in phase
    assert "v41431_preapproval_edit" in phase
    assert "v41431_customer_reference_pdf" in phase
    assert "tests/test_v41431_po_workspace_preapproval_pdf.py" in readiness
