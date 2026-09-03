from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_release_markers_are_v41427():
    assert text("VERSION").strip() in {"4.14.27", "4.14.28"}
    app = text("streamlit_app.py")
    assert any(x in app for x in ("41427-FINAL-METLAB-LAYOUT-PO-EMAIL-FIELDS", "41428-OSP-BATCH-GENEALOGY-TWO-DAY-EXCEL"))
    assert any(x in text("DEPLOYMENT_MANIFEST.json") for x in ('"version": "4.14.27"', '"version": "4.14.28"'))


def test_part_master_metallurgy_is_final_dispatch_only():
    src = text("app_pages/part_master.py")
    assert "FINAL DISPATCH METALLURGICAL REQUIREMENTS" in src
    assert "not used for Raw Material Inward MetLAB inspection" in src
    assert "Create / Update Final Dispatch Metallurgical Inspection Layout" in src


def test_raw_material_metlab_uses_layout_master_and_excludes_final_scope():
    service = text("core/inspection_service.py")
    page = text("app_pages/metlab_report.py")
    assert "def raw_material_metlab_plans" in service
    assert '!= "FINAL_METALLURGICAL"' in service
    assert "Raw Material Inward MetLAB Layout · Layout Master" in page
    assert "Part Master Final Metallurgical Requirements are excluded from Raw Material Inward inspection" in page
    assert "No approved Raw Material Inward MetLAB layout is available in Layout Master" in page
    assert "RMTC Raw Material layout is generated automatically from the Part Worksheet" not in page


def test_email_template_has_database_field_picker():
    src = text("app_pages/email_settings.py")
    assert "Add Database Field to Template" in src
    assert "Add Field to Subject" in src
    assert "Add Field to Email Body" in src
    assert "supply_purchase_orders.po_number" in src
    assert "supply_purchase_order_items.quantity + uom" in src


def test_po_notification_context_aggregates_items():
    src = text("core/notification_service.py")
    assert '"quantity_value": qty_value' in src
    assert '"quantity": f"{qty_value} {uom_text}".strip()' in src
    assert '"part_number": ", ".join(supplier_parts)' in src
    assert 'self.repo.select("supply_purchase_order_items", eq={"purchase_order_id": rid}' in src


def test_supplier_release_email_uses_po_type_event_after_approval():
    src = text("app_pages/supply_chain.py")
    assert 'release_event = "RM_PO_CREATED" if' in src
    assert 'else "FORGING_PO_CREATED"' in src
    assert 'release_next_stage = "Raw Material Receipt"' in src
    assert '"Forging Receipt"' in src


def test_forging_email_migration_matches_requested_template():
    sql = text("supabase/migrations/20260902143000_qcms_v41427_final_metlab_layout_po_email_fields.sql")
    assert "Dear Supplier," in sql
    assert "Forging Purchase Order {{po_number}} has been released through QCMS." in sql
    assert "Supplier: {{supplier_name}}" in sql
    assert "Part Number: {{part_number}}" in sql
    assert "Quantity: {{quantity}}" in sql
    assert "Delivery Date: {{delivery_date}}" in sql
    assert "Next Stage: {{next_stage}}" in sql
    assert "Please send us the order confirmation in next 2-3 days with duly stamp and sign." in sql
    assert "The controlled Purchase Order PDF and available supporting documents are attached." in sql
    assert "Four Star Industries Pvt Ltd" in sql
    assert "Purchasing Team" in sql
