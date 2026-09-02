from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def v41418_sql() -> str:
    names = [
        "supabase/migrations/20260831161000_qcms_v41418_permissions_employee_access.sql",
        "supabase/migrations/20260831161100_qcms_v41418_osp_same_heat_master_delete.sql",
        "supabase/migrations/20260831161200_qcms_v41418_audit_metlab_rls_release.sql",
    ]
    return "\n".join(text(name) for name in names)


def test_version_build_manifest_and_release_docs_are_v41418():
    # v4.14.18 remains a preserved non-regression baseline even on later controlled releases.
    assert text("VERSION").strip() in {"4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23", "4.14.23", "4.14.24", "4.14.25", "4.14.26"}
    app = text("streamlit_app.py")
    assert any(marker in app for marker in (
        "41418-PERMISSIONS-AUDIT-EMPLOYEE-OSP-RMTC-METLAB-RLS-PDF",
        "41419-PO-LIVE-EMPLOYEE-DELETE-USER-STATUS-SAME-HEAT-CONFIRMATION-IMAGES",
        "41420-RMTC-SAME-HEAT-OSP-EDIT-DELETE",
        "41421-DEPLOY-RESUME-DELETE-ROUTING",
        "41422-PUBLIC-VERIFY-BLANK-MASTER-RMTC-RESET",
        "41423-SOURCE-ONLY-DEPLOY-RMTC-MASTER-DELETE",
        "41424-PO-TECH-GRID-LIVE-IMPORT-APQP-DATE", "41425-PO-EDIT-MASTER-STATE-TRANSACTION-EDIT-PERFORMANCE", "41426-COMPLAINT-MEDIA-CALIBRATION-STANDARD-ROOM-NPD-CARDS",
    ))
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert manifest["version"] in {"4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23", "4.14.23", "4.14.24", "4.14.25", "4.14.26"}
    assert manifest["build"] in {
        "41418-PERMISSIONS-AUDIT-EMPLOYEE-OSP-RMTC-METLAB-RLS-PDF",
        "41419-PO-LIVE-EMPLOYEE-DELETE-USER-STATUS-SAME-HEAT-CONFIRMATION-IMAGES",
        "41420-RMTC-SAME-HEAT-OSP-EDIT-DELETE",
        "41421-DEPLOY-RESUME-DELETE-ROUTING",
        "41422-PUBLIC-VERIFY-BLANK-MASTER-RMTC-RESET",
        "41423-SOURCE-ONLY-DEPLOY-RMTC-MASTER-DELETE",
        "41421-DEPLOY-RESUME-DELETE-ROUTING",
        "41422-PUBLIC-VERIFY-BLANK-MASTER-RMTC-RESET",
        "41423-SOURCE-ONLY-DEPLOY-RMTC-MASTER-DELETE",
        "41424-PO-TECH-GRID-LIVE-IMPORT-APQP-DATE", "41425-PO-EDIT-MASTER-STATE-TRANSACTION-EDIT-PERFORMANCE", "41426-COMPLAINT-MEDIA-CALIBRATION-STANDARD-ROOM-NPD-CARDS",
    }
    assert (ROOT / "docs/RELEASE_4_14_18.md").exists()
    assert (ROOT / "QCMS_NEW_CHAT_HANDOVER_v4.14.18.md").exists()


def test_employee_master_legacy_authorities_are_safe_and_top_level_is_supported():
    page = text("app_pages/employee_master.py")
    sql = v41418_sql()
    assert "authority_options=list(AUTHORITIES)+" in page
    assert "existing_authorities" in page
    assert "Top-level authority / No Reports-To required" in page
    assert "'reports_to_employee_id':None if top_level" in page
    assert "is_top_level_authority" in sql
    assert "QSMS-ADMIN-001" in sql
    assert "reports_to_employee_id=null" in sql


def test_user_admin_payload_is_normalized_and_existing_employee_link_is_selected():
    page = text("app_pages/user_access.py")
    edge = text("supabase/functions/qsms-user-admin/index.ts")
    assert "def _normalize_user" in page
    assert 'profile = dict(row.get("profile") or {})' in page
    assert 'employee = dict(row.get("employee") or {})' in page
    assert "employee_index = employee_options.index(current_employee_id)" in page
    assert 'role: profile?.role ?? "VIEWER"' in edge
    assert "employee_id: employee?.id ?? null" in edge
    assert "Flat fields are returned for Streamlit compatibility" in edge


def test_user_admin_never_overwrites_employee_email_and_does_not_unlink_without_explicit_change():
    edge = text("supabase/functions/qsms-user-admin/index.ts")
    assert '.update({ profile_id: userId, updated_by: actorId })' in edge
    assert '.update({ profile_id: userId, email' not in edge
    assert "currentEmployeeId && currentEmployeeId !== employeeId" in edge
    assert "Selected Employee is already linked to another QCMS user" in edge
    for role in ("MANAGEMENT", "SUPPLY_CHAIN", "PROCUREMENT", "BUSINESS_DEVELOPMENT"):
        assert f'"{role}"' in edge


def test_effective_permissions_share_user_role_department_precedence_and_fix_po_mapping():
    access = text("core/access.py")
    sql = v41418_sql()
    assert "ADMIN → explicit User override → Role defaults → Department defaults → legacy fallback" in access
    assert "role_module_defaults" in access
    assert "department_module_defaults" in access
    assert "qcms_effective_module_permission" in sql
    assert "role_module_defaults" in sql
    assert "supply_purchase_orders','supply_purchase_order_items','supply_purchase_order_sources','supply_opening_stock" in sql
    assert "then 'SUPPLY_CHAIN'" in sql
    assert "qsms_has_module_write" in sql


def test_permission_admin_has_role_department_user_override_and_archive_layers():
    page = text("app_pages/user_access.py")
    assert "ROLE → MODULE DEFAULTS" in page
    assert "DEPARTMENT → MODULE DEFAULTS" in page
    assert "EXPLICIT USER MODULE PERMISSIONS" in page
    assert '"Override"' in page
    assert '"Entry/Create"' in page
    assert '"Validate/Review"' in page
    assert '"Delete/Archive"' in page
    assert "Clear All User Overrides" in page


def test_sections_default_visible_with_view_create_edit_overrides_and_sensitive_rls():
    page = text("app_pages/user_access.py")
    access = text("core/access.py")
    sql = v41418_sql()
    assert "SECTION VIEW / CREATE / EDIT" in page
    assert "Reset Sections to Default Visible" in page
    assert '"Create": create' in page
    assert '"can_create": bool(row["Create"])' in page
    assert '"can_create": bool(module.get("can_create"))' in access
    assert "add column if not exists can_create" in sql
    assert "PRICE_HISTORY" in sql and "SUPPLIER_TECHNICAL" in sql
    assert "qcms_effective_section_permission" in sql


def test_safe_employee_recovery_is_conservative_and_audit_backed():
    sql = v41418_sql()
    assert "profile_matches=1 and employee_matches=1" in sql
    assert "not exists" in sql and "already_linked.profile_id=p.id" in sql
    assert "first_employee_email" in sql
    assert "original_email" in sql
    assert "lower(btrim(coalesce(f.original_email,'')))=lower(btrim(coalesce(p.email,'')))" in sql
    assert "delete from public.employees" not in sql.lower()


def test_comprehensive_record_audit_and_user_activity_are_present():
    sql = v41418_sql()
    activity = text("core/activity.py")
    repo = text("core/repository.py")
    app = text("streamlit_app.py")
    users = text("app_pages/user_access.py")
    assert "qcms_user_activity_log" in sql
    assert "qcms_log_user_activity" in sql
    assert "log_row_change" in sql
    assert "pg_trigger" in sql and "trg_audit_row_change" in sql
    assert 'log_activity("CREATE"' in repo
    assert 'log_activity("UPDATE"' in repo
    assert 'log_activity("DELETE"' in repo
    assert "log_route_view" in app
    assert "USER ACTIVITY" in users
    assert "RECORD CHANGE AUDIT" in users
    assert "def log_route_view" in activity


def test_password_master_delete_and_universal_pdf_center_cover_business_records():
    records = text("app_pages/records_center.py")
    sql = v41418_sql()
    assert "PASSWORD-PROTECTED MASTER DELETE" in records
    assert "password_delete_panel" in records
    assert "UNIVERSAL RECORD PDF DOWNLOAD" in records
    assert "Download Full Register PDF" in records
    assert "Download Selected Record PDF" in records
    for table in ("parts", "employees", "rmtc_approvals", "inward_lots", "lab_tests", "supply_purchase_orders", "supply_rm_receipts"):
        assert f'"{table}"' in records
    assert "qsms_delete_master_row" in sql
    assert "qcms_effective_module_permission(module_name,'archive')" in sql


def test_v41418_remote_schema_guard_is_automatic_and_non_destructive():
    guard = text("scripts/qcms_remote_schema_guard.py")
    assert "QCMS_V41418_READY" in guard
    assert "20260831161000_qcms_v41418_permissions_employee_access.sql" in guard
    assert "20260831161100_qcms_v41418_osp_same_heat_master_delete.sql" in guard
    assert "20260831161200_qcms_v41418_audit_metlab_rls_release.sql" in guard
    assert any(marker in guard for marker in ('public_marker == "4.14.18"', 'public_marker == "4.14.19"'))
    assert "Applying additive v4.14.18" in guard
    assert "db reset" not in guard
    assert "db push" not in guard


def test_v41418_osp_delete_is_user_permission_password_and_allocation_controlled():
    page = text("app_pages/osp_transactions.py")
    service = text("core/osp_service.py")
    delete_service = text("core/delete_service.py")
    sql = v41418_sql()
    assert 'rpc_name="qcms_delete_osp_transaction"' in page
    assert 'rpc_name="qcms_delete_osp_receipt"' in page
    assert 'can_delete=perms["can_archive"]' in page
    assert "password_rpc_delete_panel" in page
    assert "verify_current_password(password)" in delete_service
    assert "def delete_receipt" in service and "def delete_transaction" in service
    assert "qcms_delete_osp_transaction" in sql and "qcms_delete_osp_receipt" in sql
    assert "OSP Transactions Delete/Archive permission is required" in sql
    assert "restored_open" in sql and "other_allocated" in sql
    assert "already released to production and cannot be deleted" in sql

def test_v41418_same_heat_reuses_internal_heat_code_and_is_distinct_in_inward():
    service = text("core/rmtc_service.py")
    rmtc = text("app_pages/rmtc_pages.py")
    inward = text("app_pages/material_inward.py")
    sql = v41418_sql()
    assert "def canonical_heat_code" in service
    assert "Existing Heat detected · Internal Heat Code" in rmtc
    assert "final_heat_code=canonical_heat_code or heat_code.strip()" in rmtc
    assert "Supplier RMTC {row.get('certificate_reference')" in inward
    assert "Heat Code {row.get('heat_code')" in inward
    assert "qcms_enforce_same_heat_code" in sql
    assert "new.heat_code:=canonical_code" in sql
    assert "same global Heat steel balance" in rmtc


def test_v41418_metlab_dimensional_rls_uses_effective_module_permissions():
    sql = v41418_sql()
    assert "public.qcms_effective_module_permission('METLAB_REPORT','create')" in sql
    assert "public.qcms_effective_module_permission('METLAB_REPORT','edit')" in sql
    assert "public.qcms_effective_module_permission('DIMENSIONAL_REPORT','create')" in sql
    assert "public.qcms_effective_module_permission('DIMENSIONAL_REPORT','edit')" in sql
    assert "qsms_can_manage_attachment" in sql
    assert "qcms_effective_module_permission(module_name,'create')" in sql


def test_v41418_section_activity_is_deduplicated_per_route():
    activity = text("core/activity.py")
    ui = text("core/ui.py")
    assert "def log_section_view" in activity
    assert '"SECTION_VIEW"' in activity
    assert "_qcms_logged_sections_for_route" in activity
    assert "log_section_view(str(key or slug).upper(), title)" in ui
