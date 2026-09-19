from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v41431_release_identity_and_source_only_schema_contract():
    assert text("VERSION").strip() in {"4.14.31", "4.14.32"}
    builds = {"41431-PO-WORKSPACE-PREAPPROVAL-EDIT-CUSTOMER-REF-PDF", "41432-PO-PRINT-COMPACT-RM-TYPES-ANDROID-TEST"}
    assert any(build in text("streamlit_app.py") for build in builds)
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] in {"4.14.31", "4.14.32"}
    assert manifest["build"] in builds
    assert manifest["previous_controlled_release"] == ("4.14.31" if manifest["version"] == "4.14.32" else "4.14.30")
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
    assert '"PART NUMBER"' in reporting
    assert '"QTY"' in reporting
    assert '"DELIVERY"' in reporting
    assert "customer_source_rows" in reporting
    assert 'item["customer_source_rows"] = customer_sources' in service


def test_records_center_routes_purchase_order_edit_to_dedicated_page():
    records = text("app_pages/records_center.py")
    assert 'route = "supply-po-edit"' in records


def test_v41431_online_verification_knows_new_po_release():
    phase = text("scripts/verify_phase1.py")
    readiness = text("scripts/check_online_readiness.py")
    assert ("41431-PO-WORKSPACE-PREAPPROVAL-EDIT-CUSTOMER-REF-PDF" in phase) or ("41432-PO-PRINT-COMPACT-RM-TYPES-ANDROID-TEST" in phase)
    assert "v41431_po_workspace" in phase
    assert "v41431_preapproval_edit" in phase
    assert "v41431_customer_reference_pdf" in phase
    assert "tests/test_v41431_po_workspace_preapproval_pdf.py" in readiness
