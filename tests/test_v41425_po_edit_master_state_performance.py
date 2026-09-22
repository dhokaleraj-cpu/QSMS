from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v41425_release_identity_and_source_only_baseline():
    assert text("VERSION").strip() in {"4.14.25", "4.14.26", "4.14.27", "4.14.28", "4.14.29", "4.14.30", "4.14.31", "4.14.32", "4.14.33", '4.14.34', '4.14.35', '4.14.36', '4.14.37', '4.14.38', '4.14.39', '4.14.40', '4.14.41', '4.14.42'}
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] in {"4.14.25", "4.14.26", "4.14.27", "4.14.28", "4.14.29", "4.14.30", "4.14.31", "4.14.32", "4.14.33", '4.14.34', '4.14.35', '4.14.36', '4.14.37', '4.14.38', '4.14.39', '4.14.40', '4.14.41', '4.14.42'}
    assert manifest["build"] in {"41425-PO-EDIT-MASTER-STATE-TRANSACTION-EDIT-PERFORMANCE", "41426-COMPLAINT-MEDIA-CALIBRATION-STANDARD-ROOM-NPD-CARDS", "41427-FINAL-METLAB-LAYOUT-PO-EMAIL-FIELDS", "41428-OSP-BATCH-GENEALOGY-TWO-DAY-EXCEL", "41429-RMTC-BEND-CHEM-CASEDEPTH-PERMISSIONS", "41430-RMTC-SUPPLIER-DEDUP-BEND-GLOBAL-SEARCH", "41431-PO-WORKSPACE-PREAPPROVAL-EDIT-CUSTOMER-REF-PDF", "41432-PO-PRINT-COMPACT-RM-TYPES-ANDROID-TEST", "41433-PO-PORTRAIT-TERMS-BATCH-PRINT-EMAIL-ANDROID-SDK", '41434-INDIVIDUAL-PO-PDF-ZIP-ANDROID-APK-BUILD', '41435-PO-WATERMARK-REMINDER-MOBILE-IOS', '41436-COMPLAINT-EMAIL-REGISTERS-REMINDERS-MOBILE-DRAWER', '41437-MOBILE-FULL-NAV-COMPLAINT-CARDS-PO-APPROVAL-DRAFT-EMAIL', '41438-ANDROID-NAV-SESSION-BRIDGE-FOOTER-REMOVE', '41439-ANDROID-CI-SIGNATURE-PERMANENT-FIX', '41440-ANDROID-NAV-READY-QUEUE-BUTTON-BRIDGE', '41441-ANDROID-LAMBDA-COMPILE-PERMANENT-FIX', '41442-LOCAL-JAVAC-OPTIONAL-CI-COMPILE-GUARD'}
    assert manifest["database_schema_required"] in {"4.14.22", "4.14.26", "4.14.27", "4.14.28", "4.14.29", "4.14.30", "4.14.31", "4.14.32", "4.14.33", '4.14.34', '4.14.35', '4.14.36', '4.14.37', '4.14.38', '4.14.39', '4.14.40', '4.14.41', '4.14.42'}
    assert manifest["database_migration_required"] is (manifest["version"] in {"4.14.35", "4.14.36", "4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42"})


def test_po_register_exposes_controlled_edit_and_reapproval():
    page = text("app_pages/supply_chain.py")
    service = text("core/supply_chain_service.py")
    assert "Edit Selected Purchase Order" in page
    assert "def _render_purchase_order_edit" in page
    assert "def update_purchase_order" in service
    assert '"approval_status":"PENDING_APPROVAL"' in service.replace(" ", "")
    # v4.14.31: Supplier Confirmation remains downstream and never blocks PO editing.
    assert "Supplier Confirmation never gates editing" in service
    assert "supplier_confirmation_blocks_edit" in service
    assert "if confirmation and was_approved" in service


def test_po_edit_refreshes_latest_master_and_protects_identity_genealogy():
    service = text("core/supply_chain_service.py")
    assert 'refresh_master=bool(p.get("refresh_master_data",True))' in service
    assert "Supplier and source Part identities remain immutable" in service
    assert "Cancel & Reissue" in service
    assert "already received" in service
    assert "technical_data_snapshot" in service
    assert "price_history_snapshot" in service


def test_record_widget_token_drives_exact_master_reload():
    ui = text("core/ui.py")
    assert "def record_widget_token" in ui
    assert 'row.get("updated_at") or row.get("created_at")' in ui
    for rel in (
        "app_pages/reference_master.py", "app_pages/employee_master.py", "app_pages/company_branch.py",
        "app_pages/material_grade.py", "app_pages/process_master.py", "app_pages/part_master.py",
        "app_pages/inspection_layouts.py", "app_pages/standards_bank.py",
    ):
        assert "record_widget_token" in text(rel), rel


def test_reference_master_edit_preserves_persisted_value_before_suggestions():
    source = text("app_pages/reference_master.py")
    assert "Existing-record value must always be the selected/default option" in source
    assert "ref_{definition.key}_{field.name}_{scope}" in source
    assert "reference_{key}_{scope}" in source


def test_major_transaction_editors_use_record_specific_state():
    expected = {
        "app_pages/material_inward.py": "material-inward-entry",
        "app_pages/osp_transactions.py": "osp-material-out-edit",
        "app_pages/npd_apqp.py": "npd-order-entry",
        "app_pages/complaints.py": "complaint-",
        "app_pages/supply_chain.py": "transaction-{table}",
    }
    for rel, marker in expected.items():
        source = text(rel)
        assert "record_widget_token" in source
        assert marker in source


def test_records_center_routes_selected_records_to_controlled_source_editor():
    source = text("app_pages/records_center.py")
    assert "def _open_selected_record_for_edit" in source
    assert "Open Selected Record for Controlled Edit" in source
    for marker in ("supply_po_edit_request_id", "edit_inward_id", "edit_metlab_id", "edit_dimensional_id", "edit_rmtc_id"):
        assert marker in source


def test_po_page_uses_bulk_request_cache_instead_of_n_plus_one_reads():
    service = text("core/supply_chain_service.py")
    assert "self._page_cache" in service
    assert "def _memo" in service
    assert "def _totals_bulk" in service
    assert "def purchase_order_rows" in service
    assert "purchase_order_confirmations" in service


def test_live_build_marker_is_v41425():
    source = text("streamlit_app.py")
    assert any(marker in source for marker in ("41425-PO-EDIT-MASTER-STATE-TRANSACTION-EDIT-PERFORMANCE", "41426-COMPLAINT-MEDIA-CALIBRATION-STANDARD-ROOM-NPD-CARDS", "41427-FINAL-METLAB-LAYOUT-PO-EMAIL-FIELDS", "41428-OSP-BATCH-GENEALOGY-TWO-DAY-EXCEL", "41429-RMTC-BEND-CHEM-CASEDEPTH-PERMISSIONS", "41430-RMTC-SUPPLIER-DEDUP-BEND-GLOBAL-SEARCH", "41431-PO-WORKSPACE-PREAPPROVAL-EDIT-CUSTOMER-REF-PDF", "41432-PO-PRINT-COMPACT-RM-TYPES-ANDROID-TEST", "41433-PO-PORTRAIT-TERMS-BATCH-PRINT-EMAIL-ANDROID-SDK", '41434-INDIVIDUAL-PO-PDF-ZIP-ANDROID-APK-BUILD', '41435-PO-WATERMARK-REMINDER-MOBILE-IOS'))
