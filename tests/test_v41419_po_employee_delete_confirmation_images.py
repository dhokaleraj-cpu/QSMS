from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_release_identity_and_manifest():
    assert (ROOT / "VERSION").read_text().strip() in {"4.14.19","4.14.20", "4.14.21", "4.14.22", "4.14.23", "4.14.24", "4.14.25", "4.14.26", "4.14.27"}
    manifest = text("DEPLOYMENT_MANIFEST.json")
    app = text("streamlit_app.py")
    assert any(v in manifest for v in ('"version": "4.14.19"','"version": "4.14.20"','"version": "4.14.21"','"version": "4.14.22"','"version": "4.14.23"', '"version": "4.14.24"', '"version": "4.14.25"', '"version": "4.14.26"', '"version": "4.14.27"' ))
    assert any(b in manifest for b in ("41419-PO-LIVE-EMPLOYEE-DELETE-USER-STATUS-SAME-HEAT-CONFIRMATION-IMAGES","41420-RMTC-SAME-HEAT-OSP-EDIT-DELETE","41421-DEPLOY-RESUME-DELETE-ROUTING","41422-PUBLIC-VERIFY-BLANK-MASTER-RMTC-RESET","41423-SOURCE-ONLY-DEPLOY-RMTC-MASTER-DELETE","41424-PO-TECH-GRID-LIVE-IMPORT-APQP-DATE", "41425-PO-EDIT-MASTER-STATE-TRANSACTION-EDIT-PERFORMANCE", "41426-COMPLAINT-MEDIA-CALIBRATION-STANDARD-ROOM-NPD-CARDS", "41427-FINAL-METLAB-LAYOUT-PO-EMAIL-FIELDS"))
    assert any(b in app for b in ("41419-PO-LIVE-EMPLOYEE-DELETE-USER-STATUS-SAME-HEAT-CONFIRMATION-IMAGES","41420-RMTC-SAME-HEAT-OSP-EDIT-DELETE","41421-DEPLOY-RESUME-DELETE-ROUTING","41422-PUBLIC-VERIFY-BLANK-MASTER-RMTC-RESET","41423-SOURCE-ONLY-DEPLOY-RMTC-MASTER-DELETE","41424-PO-TECH-GRID-LIVE-IMPORT-APQP-DATE", "41425-PO-EDIT-MASTER-STATE-TRANSACTION-EDIT-PERFORMANCE", "41426-COMPLAINT-MEDIA-CALIBRATION-STANDARD-ROOM-NPD-CARDS", "41427-FINAL-METLAB-LAYOUT-PO-EMAIL-FIELDS"))


def test_po_create_uses_live_employee_and_visible_blockers():
    auth = text("core/auth.py")
    supply = text("app_pages/supply_chain.py")
    service = text("core/supply_chain_service.py")
    assert "def refresh_current_employee_link" in auth
    assert 'qcms_current_login_employee_id' in auth
    assert "current_employee_id(refresh=True)" in supply
    assert "po_blockers" in supply
    assert "signed-in user is not linked to an ACTIVE Employee Master" in supply
    assert "current_employee_id(refresh=True)" in service


def test_user_employee_link_is_persistent_and_employee_email_is_independent():
    edge = text("supabase/functions/qsms-user-admin/index.ts")
    assert "effectiveEmployeeId" in edge
    assert "allowUnlinkEmployee" in edge
    assert "Employee link did not persist" in edge
    assert '.update({ profile_id: userId, email' not in edge


def test_transaction_user_and_status_columns_are_present():
    audit = text("core/record_audit.py")
    supply = text("app_pages/supply_chain.py")
    osp = text("app_pages/osp_transactions.py")
    center = text("app_pages/records_center.py")
    for token in ("Created By User", "Last Modified By User", "Data Entry Status"):
        assert token in audit
        assert token in supply or token in center
        assert token in osp


def test_osp_and_universal_delete_are_permission_password_controlled():
    osp = text("app_pages/osp_transactions.py")
    delete = text("core/delete_service.py")
    migration = text("supabase/migrations/20260901170000_qcms_v41419_po_enable_delete_audit_confirmation_images.sql")
    assert "qcms_delete_osp_transaction" in osp
    assert "qcms_delete_osp_receipt" in osp
    assert 'perms["can_archive"]' in osp
    assert "verify_current_password" in delete
    assert "qcms_delete_transaction_row" in delete
    assert "qcms_effective_module_permission(module_name,'archive')" in migration
    assert "foreign_key_violation" in migration


def test_same_heat_new_tc_is_fresh_and_only_exact_tc_duplicate_is_blocked():
    rmtc = text("app_pages/rmtc_pages.py")
    migration = text("supabase/migrations/20260901170000_qcms_v41419_po_enable_delete_audit_confirmation_images.sql")
    assert "rmtc_new_form_nonce" in rmtc
    assert "rmtc_direct_edit_selector" in rmtc
    assert "Enter a NEW Supplier RMTC / TC Number" in rmtc
    assert "uq_rmtc_heat_supplier_rmtc_number" in migration
    assert "qcms_enforce_same_heat_code" in migration
    assert "canonical_code" in migration


def test_microstructure_accepts_bmp_and_other_common_images():
    attachments = text("core/attachments.py")
    metlab = text("app_pages/metlab_report.py")
    osp = text("app_pages/osp_inspections.py")
    rmtc = text("app_pages/rmtc_pages.py")
    for ext in ('"png"','"jpg"','"jpeg"','"bmp"','"tif"','"tiff"','"webp"','"gif"'):
        assert ext in attachments
    assert "MICROSTRUCTURE_IMAGE_TYPES" in metlab
    assert "MICROSTRUCTURE_IMAGE_TYPES" in osp
    assert "MICROSTRUCTURE_IMAGE_TYPES" in rmtc


def test_supplier_po_confirmation_stage_attachment_and_daily_priority_reminder():
    migration = text("supabase/migrations/20260901170000_qcms_v41419_po_enable_delete_audit_confirmation_images.sql")
    supply = text("app_pages/supply_chain.py")
    notifier = text("supabase/functions/qcms-po-confirmation-reminder/index.ts")
    notification = text("core/notification_service.py")
    for token in ("supply_po_confirmations", "qcms_ensure_po_confirmation", "qcms_confirm_purchase_order", "PO_CONFIRMATION_REQUIRED", "PO_CONFIRMATION_DAILY", "SUPPLIER_PO_CONFIRMATION"):
        assert token in migration
    assert "SUPPLIER PURCHASE ORDER CONFIRMATION" in supply
    assert "Supplier PO Confirmation Attachment" in supply
    assert "PO_CONFIRMATION_REQUIRED" in supply
    assert "daily priority reminder" in supply.lower()
    assert "PO_CONFIRMATION_DAILY" in notifier
    assert "reminder_count" in notifier
    assert '"supply_po_confirmations": "PO_CONFIRMATION"' in notification
    assert 'related_table == "supply_po_confirmations"' in notification


def test_supplier_confirmation_stage_uses_actual_stage_responsibility_schema():
    migration = text("supabase/migrations/20260901170000_qcms_v41419_po_enable_delete_audit_confirmation_images.sql")
    assert "(tenant_id,stage_key,stage_label,department,employee_id,notify_supplier,enabled)" in migration
    assert "responsible_department" not in migration
    assert "responsible_employee_id" not in migration


def test_remote_guard_knows_v41419():
    guard = text("scripts/qcms_remote_schema_guard.py")
    assert "V41419_MIGRATION" in guard
    assert "QCMS_V41419_READY" in guard
    assert 'public_marker in {"4.14.19","4.14.20", "4.14.21", "4.14.22", "4.14.23"}' in guard
    assert "PO_CONFIRMATION_DAILY" in guard


def test_v41419_daily_supplier_confirmation_has_dedicated_edge_and_cron():
    migration = text("supabase/migrations/20260901170000_qcms_v41419_po_enable_delete_audit_confirmation_images.sql")
    edge = text("supabase/functions/qcms-po-confirmation-reminder/index.ts")
    assert "qcms-po-confirmation-reminder-daily" in migration
    assert "30 2 * * *" in migration
    assert "X-QCMS-Scheduler" in edge
    assert "PO_CONFIRMATION_DAILY" in edge
    assert "PRIORITY · Purchase Order confirmation pending" in edge
    assert "reminder_count" in edge


def test_v41419_controlled_delete_covers_major_transaction_roots():
    migration = text("supabase/migrations/20260901170000_qcms_v41419_po_enable_delete_audit_confirmation_images.sql")
    records = text("app_pages/records_center.py")
    for table in ("npd_orders","ppap_projects","pfd_headers","pfmea_headers","control_plan_headers","spc_studies","msa_studies","capacity_studies"):
        assert table in migration
        assert table in records


def test_v41419_common_rm_and_forging_multi_part_po_contract():
    part = text("app_pages/part_master.py")
    service = text("core/supply_chain_service.py")
    supply = text("app_pages/supply_chain.py")
    migration = text("supabase/migrations/20260901170000_qcms_v41419_po_enable_delete_audit_confirmation_images.sql")
    for token in ("Supplier RM Item Code", "Supplier Forging Part No."):
        assert token in part
    for token in ("raw_material_po_group_key", "forging_po_group_key", "supplier_item_code_snapshot", "linked_finished_parts_snapshot", "forging_sources"):
        assert token in service
    assert "Select ELIGIBLE Forging PO Source(s)" in supply
    assert "purchase_order_item_id" in migration
    assert "uq_supply_forging_supplier_order_source" in migration


def test_v41419_supplier_confirmation_blocks_receipt_until_confirmed():
    service = text("core/supply_chain_service.py")
    migration = text("supabase/migrations/20260901170000_qcms_v41419_po_enable_delete_audit_confirmation_images.sql")
    assert "_po_confirmation_is_confirmed" in service
    assert "Supplier PO Confirmation is still pending" in service
    assert "qcms_require_supplier_po_confirmation" in migration
    assert "LEGACY RECEIPT EXISTS" in migration
    assert "trg_qcms_rm_receipt_po_confirmation" in migration
    assert "trg_qcms_forging_receipt_po_confirmation" in migration


def test_v41419_daily_pending_po_and_rm_procurement_notifications():
    migration = text("supabase/migrations/20260901170000_qcms_v41419_po_enable_delete_audit_confirmation_images.sql")
    edge = text("supabase/functions/qcms-overdue-notifier/index.ts")
    for token in ("PO_PENDING_APPROVAL", "RM_PROCUREMENT_PENDING_DUE"):
        assert token in migration
        assert token in edge
    assert "RM_PO_OPEN_OVERDUE" in edge
    assert "FORGING_ORDER_OPEN_OVERDUE" in edge


def test_v41419_metlab_rls_and_osp_records_delete_reasserted():
    migration = text("supabase/migrations/20260901170000_qcms_v41419_po_enable_delete_audit_confirmation_images.sql")
    records = text("app_pages/records_center.py")
    assert "qcms_effective_module_permission('METLAB_REPORT','create')" in migration
    assert "qcms_effective_module_permission('METLAB_REPORT','edit')" in migration
    assert "p_table_name='osp_jobs'" in migration
    assert "p_table_name='osp_receipts'" in migration
    assert '"OSP Transaction / Job": ("osp_jobs", "OSP_TRANSACTIONS")' in records
    assert '"OSP Inward Receipt": ("osp_receipts", "OSP_TRANSACTIONS")' in records


def test_v41419_full_release_contract_prevents_partial_marker_false_positive():
    migration = (ROOT / "supabase/migrations/20260901170000_qcms_v41419_po_enable_delete_audit_confirmation_images.sql").read_text()
    guard = (ROOT / "scripts/qcms_remote_schema_guard.py").read_text()
    assert "qcms_release_contract_v41419" in migration
    assert "supplier_rm_item_code" in migration
    assert "PO_PENDING_APPROVAL" in migration
    assert "RM_PROCUREMENT_PENDING_DUE" in migration
    assert "QCMS_V41419_FULL_READY" in migration
    assert "_data_api_full_contract_marker" in guard
    assert "full release contract is incomplete" in guard
    assert "public.qcms_release_contract_v41419()='QCMS_V41419_FULL_READY'" in guard
