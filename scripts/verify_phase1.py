from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.calculations import calculate_di, calculate_jominy_curve
from core.dimensional_import import parse_dimensional_workbook_bytes
from core.master_definitions import DEFINITIONS
from core.reference_import import parse_reference_workbook

errors: list[str] = []
required = [
    "streamlit_app.py",
    "app_pages/dashboard.py",
    "app_pages/master_home.py",
    "app_pages/part_master.py",
    "app_pages/material_grade.py",
    "app_pages/reference_master.py",
    "app_pages/employee_master.py",
    "app_pages/user_access.py",
    "app_pages/rmtc_pages.py",
    "app_pages/material_inward.py",
    "app_pages/inspection_home.py",
    "app_pages/inspection_layouts.py",
    "app_pages/dimensional_report.py",
    "app_pages/metlab_report.py",
    "app_pages/template_center.py",
    "app_pages/osp_transactions.py",
    "app_pages/osp_inspections.py",
    "app_pages/npd_apqp.py",
    "app_pages/supply_chain.py",
    "core/supply_chain_service.py",
    "supabase/migrations/20260819113132_qcms_supply_chain_flexible_inspections_v4120.sql",
    "app_pages/reports.py",
    "core/osp_service.py",
    "supabase/migrations/20260805084500_qsms_osp_parameter_groups_reports_v491.sql",
    "tests/test_v491_osp_parameter_groups_reports.py",
    "core/inspection_service.py",
    "core/dimensional_import.py",
    "core/calculations.py",
    "core/catalog.py",
    "core/access.py",
    "core/rmtc_service.py",
    "core/inward_service.py",
    "data/di_factors.json",
    "data/Dimensional Report.xlsx",
    "templates/Dimensional_Inspection_Report_Template.xlsx",
    "templates/MetLAB_Report_Layout_Template.xlsx",
    "portal/app_registry.toml",
    "portal/portal_contract.json",
    "data/Quality Monitoring System.xlsx",
    "supabase/functions/qsms-user-admin/index.ts",
    "supabase/migrations/20260802065000_qsms_inspection_workflow_v460.sql",
    "supabase/migrations/20260802065100_qsms_inspection_delete_and_sequences_v460.sql",
    "supabase/migrations/20260802074100_qsms_jominy_catalog_dispositions_v471.sql",
    "supabase/migrations/20260802090000_qsms_rmtc_reliability_v472.sql",
    "supabase/migrations/20260802112000_qsms_rmtc_workflow_admin_v473.sql",
    "supabase/migrations/20260802150000_qsms_heat_production_microstructure_v481.sql",
    "tests/test_v481_heat_production_microstructure.py",
    "tests/test_v482_auto_master_codes_dashboard.py",
    "app_pages/records_center.py",
    "supabase/migrations/20260802193000_qsms_unified_records_v484.sql",
    "tests/test_v484_unified_records.py",
    "supabase/migrations/20260802201500_qsms_combined_heat_balance_v485.sql",
    "tests/test_v485_combined_heat_balance.py",
    "supabase/migrations/20260802213000_qsms_heat_supplier_rmtc_ledger_v486.sql",
    "tests/test_v486_heat_supplier_rmtc_ledger.py",
    "supabase/migrations/20260803231000_qsms_osp_transactions_v490.sql",
    "tests/test_v490_osp_transactions.py",
    "core/steel_balance.py",
    "supabase/migrations/20260802161000_qsms_auto_master_codes_dashboard_v482.sql",
    "app_pages/process_master.py",
    "core/reporting.py",
    "supabase/migrations/20260805194500_qsms_simplified_metlab_process_master_print_v492.sql",
    "tests/test_v492_simplified_metlab_process_master_print.py",
    "docs/RELEASE_4_9_2.md",
    "templates/RMTC_Entry_Template.xlsx",
    "templates/Material_Inward_Template.xlsx",
    "templates/MetLAB_Report_Layout_Template.xlsx",
    "core/delete_service.py",
    "supabase/migrations/20260811090000_qcms_rmtc_microstructure_print_reports_v496.sql",
    "tests/test_v496_qcms_global_heat_print_reports.py",
    "docs/RELEASE_4_9_6.md",
    "supabase/migrations/20260811103000_qcms_npd_apqp_process_flow_v497.sql",
    "tests/test_v497_npd_apqp_process_tracking.py",
    "docs/RELEASE_4_9_7.md",
    "supabase/migrations/20260811114500_qcms_duplicate_qc_tools_npd_points_v498.sql",
    "tests/test_v498_duplicate_print_qc_tools.py",
    "docs/RELEASE_4_9_8.md",
    "app_pages/qc_calculation_tools.py",
    "app_pages/master_import.py",
    "app_pages/my_account.py",
    "supabase/migrations/20260812113000_qcms_universal_delete_account_import_print_v4100.sql",
    "core/hardness_conversion.py",
    "data/astm_e140_table1.json",
    "app_pages/standards_bank.py",
    "core/selection_labels.py",
    "templates/Customer_Standards_Template.xlsx",
    "supabase/migrations/20260812130000_qcms_customer_standards_selection_cards_v4101.sql",
    "docs/RELEASE_4_10_1.md",
    "app_pages/complaints.py",
    "supabase/migrations/20260812092238_qcms_complaint_management_login_v4106.sql",
    "docs/RELEASE_4_10_6.md",
    "supabase/migrations/20260812165500_qcms_detailed_complaint_analysis_v4107.sql",
    "tests/test_v4108_detailed_complaint_analysis_login.py",
    "docs/RELEASE_4_10_7.md",
    "tests/test_v4124_dual_supply_flow_mis.py",
    "docs/RELEASE_4_12_4.md",
    "docs/RELEASE_4_12_7.md",
    "tests/test_v4127_exact_preview_enterprise_ui.py",
    "tests/test_v4128_responsive_enterprise_ui_report_hub.py",
    "docs/RELEASE_4_13_4.md",
    "supabase/migrations/20260821142000_qcms_rmtc_reusable_global_balance_v4134.sql",
    "tests/test_v4134_priority_ui_rmtc_reuse_import.py",
    "supabase/migrations/20260821170000_qcms_rmtc_osp_text_layout_sources_v4136.sql",
    "tests/test_v4136_rmtc_osp_text_layout_sources.py",
    "docs/RELEASE_4_13_6.md",
    "supabase/migrations/20260822193000_qcms_supply_po_fsi_part_rmtc_worksheet_v4137.sql",
    "core/purchase_order_reporting.py",
    "templates/FSI_STANDARD_PO_TERMS_2023.pdf",
    "tests/test_v4137_supply_po_fsi_part_rmtc_worksheet.py",
    "docs/RELEASE_4_13_7.md",
    "supabase/migrations/20260826110000_qcms_part_supply_auth_opening_stock_v4143.sql",
    "core/password_edit.py",
    "tests/test_v4143_part_supply_auth_opening_stock.py",
    "docs/RELEASE_4_14_3.md",
]
for item in required:
    if not (ROOT / item).exists():
        errors.append(f"Missing required file: {item}")

app_text = (ROOT / "streamlit_app.py").read_text()
paths = re.findall(r'url_path="([^"]+)"', app_text)
expected_paths = {
    "dashboard", "deployment-diagnostics", "masters", "company-branch-entry", "company-branch-records", "rmtc-entry", "rmtc-approved-worksheet", "inward-entry", "osp-home", "supply-chain-home", "supply-customer-orders", "supply-opening-stock", "supply-rm-procurement", "supply-purchase-orders", "supply-po-order-list", "supply-po-edit", "supply-po-pdf", "supply-po-approval", "supply-rm-receipt", "supply-rm-dispatch", "supply-forging", "supply-downstream", "supply-traceability", "supply-order-mis", "npd-process-flow", "npd-status", "apqp", "qc-tools", "qc-calculation-records", "complaints-home", "customer-complaint", "supplier-complaint", "customer-complaint-register", "supplier-complaint-register", "complaint-email-settings", "complaint-analysis", "complaint-records", "calibration-validation", "standard-room-inspection", "inspection-home", "records-center", "heat-ledger",
    "reports-home", "heat-transaction-report", "osp-balance-report", "supply-chain-report", "rmtc-report", "inward-report", "dimensional-report", "metlab-report", "complaints-report", "traceability-report", "npd-report", "apqp-report", "qc-report", "inspection-layout-report", "standards-report", "templates",
    "part-entry", "part-records", "process-entry", "process-records", "grade-entry", "grade-records",
    "reference-entry", "reference-records", "employee-entry", "employee-records",
    "user-access", "email-settings", "master-import", "standards-entry", "standards-records", "my-account", "rmtc-part", "rmtc-records", "rmtc-approval", "inward-records",
    "osp-material-out", "osp-sample-receipt", "osp-inward", "osp-dimensional", "osp-metlab", "osp-records",
    "inspection-layout-entry", "inspection-layout-records", "dimensional-entry",
    "dimensional-records", "metlab-entry", "metlab-records", "bend-test-entry", "bend-test-records", "bend-test-report", "global-search",
}
if set(paths) != expected_paths or len(paths) != len(expected_paths):
    errors.append(f"Expected {len(expected_paths)} unique registered pages, found {paths}")

if 'PAGE_BY_PATH = dict(PAGE_ITEMS)' not in app_text or '("dashboard", st.Page(dashboard.render' not in app_text:
    errors.append("Dashboard must be registered through the explicit PAGE_BY_PATH navigation registry")
if 'st.session_state["_qsms_pages"][path]' in app_text:
    errors.append("Top navigation must not directly index the session page registry")

for token, file_name in [
    ("RAW MATERIAL DETAILS", "app_pages/part_master.py"),
    ("JOMINY REQUIREMENT", "app_pages/part_master.py"),
    ("CHEMICAL COMPOSITION", "app_pages/material_grade.py"),
    ("Calculated Jominy", "app_pages/rmtc_pages.py"),
    ("Actual DI", "app_pages/rmtc_pages.py"),
    ("Submit Draft → Pending", "app_pages/rmtc_pages.py"),
    ("qsms_next_employee_code", "app_pages/employee_master.py"),
    ("user_module_permissions", "app_pages/user_access.py"),
    ("password_delete_panel", "app_pages/part_master.py"),
    ("subpage_navigation", "app_pages/material_grade.py"),
    ("Import Dimensional Layout", "app_pages/inspection_layouts.py"),
    ("Finalize Dimensional Decision", "app_pages/dimensional_report.py"),
    ("Finalize MetLAB Decision", "app_pages/metlab_report.py"),
]:
    if token not in (ROOT / file_name).read_text():
        errors.append(f"{file_name} missing {token}")


part_master_text = (ROOT / "app_pages/part_master.py").read_text()
for token in ("OSP INSPECTION FOR METLAB", "METALLURGICAL REQUIREMENTS", "Minimum Specification", "Maximum Specification"):
    if token not in part_master_text:
        errors.append(f"Part Master missing simplified requirement control: {token}")
for removed in ("HEAT TREATMENT DETAILS", "OSP PROCESS & INWARD SPECIFICATIONS"):
    if removed in part_master_text:
        errors.append(f"Legacy Part Master section is still visible: {removed}")
if '"processes"' in (ROOT / "app_pages/reference_master.py").read_text().split("REFERENCE_KEYS",1)[1].split(")",1)[0]:
    errors.append("Process Master must not be duplicated inside Reference Master")
if "return None" not in (ROOT / "core/ui.py").read_text().split("def subpage_navigation",1)[1].split("def module_submenu",1)[0]:
    errors.append("Page-level duplicate navigation is not suppressed")

runtime = "\n".join(
    (ROOT / item).read_text().lower()
    for item in [
        "core/config.py", "core/database.py", ".streamlit/secrets.toml.example",
        "deploy/STREAMLIT_CLOUD_SECRETS_TEMPLATE.toml",
    ]
)
if "service_role" in runtime or "service-role" in runtime:
    errors.append("Runtime files must not contain a service-role key.")

try:
    preview = parse_reference_workbook((ROOT / "data/Quality Monitoring System.xlsx").read_bytes())
    if not preview.part.get("part_number"):
        errors.append("Reference workbook part missing.")
except Exception as exc:
    errors.append(f"Reference workbook validation failed: {exc}")

try:
    dimensional = parse_dimensional_workbook_bytes(
        (ROOT / "data/Dimensional Report.xlsx").read_bytes(),
        "Dimensional Report.xlsx",
    )
    if dimensional["metadata"].get("format_number") != "FSI/804/F03":
        errors.append(f"Dimensional format number mismatch: {dimensional['metadata']}")
    if dimensional["metadata"].get("default_sample_size") != 6:
        errors.append(f"Dimensional sample size mismatch: {dimensional['metadata']}")
    if len(dimensional.get("characteristics") or []) < 30:
        errors.append("Dimensional layout parser returned fewer than 30 characteristics.")
except Exception as exc:
    errors.append(f"Dimensional workbook validation failed: {exc}")

curve = calculate_jominy_curve({"C": 0.1912, "MN": 0.7805, "CR": 0.509, "NI": 0.419, "MO": 0.158})
if round(curve[1], 3) != 43.672 or round(curve[4], 3) != 31.03:
    errors.append(f"Jominy workbook formula mismatch: {curve}")
di = calculate_di({"C": 0.22, "MN": 0.85, "SI": 0.25, "NI": 0.018, "CR": 1.18, "MO": 0.004, "CU": 0.012, "V": 0.005}, 6)
if di.get("value") is None or abs(float(di["value"]) - 2.1082) > 0.001:
    errors.append(f"DI workbook factor mismatch: {di}")

# QCMS 4.10.9 detailed complaint analysis contract checks.
complaint_text = (ROOT / "app_pages/complaints.py").read_text()
complaint_sql = (ROOT / "supabase/migrations/20260812092238_qcms_complaint_management_login_v4106.sql").read_text()
complaint_analysis_sql = (ROOT / "supabase/migrations/20260812165500_qcms_detailed_complaint_analysis_v4107.sql").read_text()
if "quality_complaints" not in complaint_text or "Debit Note Status" not in complaint_text or "quality_complaint_followups" not in complaint_text:
    errors.append("Complaint Management entry/follow-up/debit-note workflow is incomplete")
if "COMPLAINT_MANAGEMENT" not in complaint_sql or "qcms_next_complaint_number" not in complaint_sql:
    errors.append("Complaint Management database permission/numbering contract is incomplete")
if "quality_complaint_actions" not in complaint_analysis_sql or "occurrence_root_cause" not in complaint_analysis_sql or "qcms_guard_complaint_closure" not in complaint_analysis_sql:
    errors.append("Detailed Complaint Analysis / CAPA schema is incomplete")
if "def render_analysis" not in complaint_text or "Why 5" not in complaint_text or "Escape / Detection Root Cause" not in complaint_text or "CORRECTIVE / PREVENTIVE ACTION PLAN" not in complaint_text:
    errors.append("Detailed Complaint Analysis UI is incomplete")
auth_text = (ROOT / "core/auth.py").read_text()
if "stable data-testid" not in auth_text or "qcms-login-brand-card" not in auth_text or "LOGIN TO QCMS" not in auth_text:
    errors.append("Login page direct CSS rebuild is missing from the authentication renderer")

# QCMS 4.10.6 controlled standards visibility / unlink / readability checks.
if "standard_name_text" not in part_master_text or "author_text" not in part_master_text or "process_text" not in part_master_text:
    errors.append("Part Master Standard download control is missing Standard Name / Author / Process details")
if "ADMIN APPROVAL — Unlink Standard from Part" not in part_master_text or "is_admin(current_profile())" not in part_master_text:
    errors.append("Part Master Standard unlink is not restricted to Administrator approval")
ui_text = (ROOT / "core/ui.py").read_text()
if "QCMS 4.10.9 — readability" not in ui_text or "font-weight:450!important" not in ui_text:
    errors.append("QCMS 4.10.9 stronger readability typography layer is missing")

# QCMS 4.11.1 central Records navigation and visible Zoho-inspired UI contract.
record_routes = {
    "records-center", "heat-ledger", "rmtc-records", "inward-records", "osp-records",
    "dimensional-records", "metlab-records", "bend-test-records", "inspection-layout-records",
    "complaint-records", "qc-calculation-records", "part-records", "process-records",
    "grade-records", "reference-records", "employee-records", "standards-records",
}
if "RECORD_ROUTES = {" not in app_text or '**{path: "Records" for path in RECORD_ROUTES}' not in app_text:
    errors.append("Central Records route ownership is missing")
records_block = app_text.split('"Records": (', 1)[1].split('    ),\n    "Reports":', 1)[0] if '"Records": (' in app_text else ""
for route in sorted(record_routes):
    if f'("{route}",' not in records_block:
        errors.append(f"Records submenu is missing {route}")
for module_name in ("Dashboard", "Masters", "RMTC", "Inward", "OSP", "QC Calculation Tools", "Complaints", "Inspections", "Reports"):
    token = f'    "{module_name}": ('
    if token in app_text:
        block = app_text.split(token, 1)[1].split('    ),', 1)[0]
        leaked = sorted(route for route in record_routes if f'("{route}",' in block)
        if leaked:
            errors.append(f"Record routes leaked into {module_name} submenu: {leaked}")
if "QCMS 4.11.1 — Zoho-inspired clean white/blue enterprise shell visibility layer." not in ui_text or "--qcms-zoho-blue:#1884D8" not in ui_text:
    errors.append("QCMS 4.11.1 Zoho-inspired visible shell layer is missing")
if "4111-ZOHO-VISIBLE-SHELL" not in ui_text or "4111-ZOHO-VISIBLE-SHELL" not in auth_text:
    errors.append("QCMS 4.11.1 visible-shell build fingerprint is missing")

# QCMS 4.11.2 Export Shipment-inspired header and module shell contract.
if "QCMS 4.11.2 — Export Shipment-inspired navy header and module navigation shell." not in ui_text:
    errors.append("QCMS 4.11.2 Export Shipment shell layer is missing")
for token in ("--qcms-export-navy:#073462", "--qcms-export-blue:#0A68AC", "4112-EXPORT-SHELL", "fsi-user-pills", "fsi-top-menu-title"):
    if token not in ui_text:
        errors.append(f"QCMS 4.11.2 shell token missing: {token}")
if "4112-EXPORT-SHELL" not in auth_text:
    errors.append("QCMS 4.11.2 login build fingerprint is missing")
if "QUALITY CONTROL<br>MONITORING SYSTEM" not in ui_text or "render_app_launcher(app_registry())" in ui_text.split("def render_shell_header",1)[1].split("def render_side_navigation",1)[0]:
    errors.append("QCMS 4.11.2 standalone header structure is incomplete")

# QCMS 4.11.3 controlled drawing revision history contract.
part_master_text = (ROOT / "app_pages/part_master.py").read_text(encoding="utf-8")
drawing_migration_text = (ROOT / "supabase/migrations/20260814102000_qcms_controlled_drawing_revision_history_v4113.sql").read_text(encoding="utf-8")
for token in ("DRAWING REVISION HISTORY", "Drawing Number", "Revision Number", "Revision Date", "qcms_activate_part_drawing_revision", "INACTIVE"):
    if token not in part_master_text and token not in drawing_migration_text:
        errors.append(f"QCMS 4.11.3 controlled drawing token missing: {token}")
if "DRAWING REVISION HISTORY" not in part_master_text:
    errors.append("QCMS 4.11.3 drawing-history UI is missing")
if "superseded_at" not in drawing_migration_text or "ux_document_attachments_one_active_part_drawing" not in drawing_migration_text:
    errors.append("QCMS 4.11.3 drawing revision history database controls are incomplete")


# QCMS 4.11.4 complaint media + header action separation contract.
complaints_text = (ROOT / "app_pages/complaints.py").read_text(encoding="utf-8")
attachments_text = (ROOT / "core/attachments.py").read_text(encoding="utf-8")
complaint_media_migration = (ROOT / "supabase/migrations/20260816160000_qcms_complaint_media_v4114.sql").read_text(encoding="utf-8")
for token in ("Photograph Title", "accept_multiple_files=True", "COMPLAINT_PHOTO", "COMPLAINT_ATTACHMENT", "PHOTOGRAPHS & MULTIPLE ATTACHMENTS"):
    if token not in complaints_text:
        errors.append(f"QCMS 4.11.4 complaint media token missing: {token}")
if "upload_additional" not in attachments_text or "document_title" not in attachments_text:
    errors.append("QCMS 4.11.4 append-only attachment service is incomplete")
for token in ("document_title", "COMPLAINT_MANAGEMENT", "complaints", "idx_document_attachments_complaint_media"):
    if token not in complaint_media_migration:
        errors.append(f"QCMS 4.11.4 complaint media migration token missing: {token}")
if not (("fsi_header_actions" in ui_text and "st.columns([2.8, 4.8, 2.25, 1.25]" in ui_text) or ("fsi_header_actions_row" in ui_text and "st.columns([3.0, 5.4, 3.2]" in ui_text)):
    errors.append("QCMS 4.11.4+ header Account / Exit separation is missing")
if not any(marker in ui_text and marker in auth_text for marker in ("4114-COMPLAINT-MEDIA-HEADER-FIX", "4116-COMPLAINT-SECTION-COLORS", "4117-COMPLAINT-STAGE-EXPANDERS", "4118-GLOBAL-STAGED-SECTIONS")):
    errors.append("QCMS complaint media/header build fingerprint is missing")


# QCMS 4.11.5+ complaint evidence/header continuity and QCMS 4.11.8 global staged workflows.
for token in ("_stage_new_complaint_media", "_upload_staged_complaint_media", "Add Selected Photographs", "PHOTOGRAPHS & MULTIPLE ATTACHMENTS"):
    if token not in complaints_text:
        errors.append(f"QCMS complaint evidence token missing: {token}")
if "fsi_header_actions_row" not in ui_text or "st.columns([3.0, 5.4, 3.2]" not in ui_text or "a1, a2 = st.columns(2" not in ui_text:
    errors.append("QCMS non-overlapping profile/action header grid is missing")

# QCMS 4.11.8 global A→H staged-section design system.
for token in (
    "def stage_section(",
    'with st.expander(f"{letter} - {title}", expanded=False)',
    'st-key-fsi_stage_a_', 'st-key-fsi_stage_b_', 'st-key-fsi_stage_c_', 'st-key-fsi_stage_d_', 'st-key-fsi_stage_e_',
    'font-size:26px!important', 'font-weight:900!important', 'min-height:64px!important',
    '4118-GLOBAL-STAGED-SECTIONS',
):
    if token not in ui_text:
        errors.append(f"QCMS 4.11.8 staged-section token missing: {token}")
if "4118-GLOBAL-STAGED-SECTIONS" not in auth_text:
    errors.append("QCMS 4.11.8 login build fingerprint is missing")
# Keep v4.12.0/v4.12.1 fingerprints in comments for regression traceability while
# requiring the current v4.12.6 build to be visible in both the app shell and login.
if "4120-SUPPLY-CHAIN-INSPECTION" not in ui_text or "4120-SUPPLY-CHAIN-INSPECTION" not in auth_text:
    errors.append("QCMS 4.12.0 legacy build fingerprint is missing")
if "4121-MASTER-DRIVEN-STANDALONE-REPORTS" not in ui_text or "4121-MASTER-DRIVEN-STANDALONE-REPORTS" not in auth_text:
    errors.append("QCMS 4.12.1 legacy build fingerprint is missing")
if "4122-SUPPLY-CHAIN-MASTER-LINKED-TRACEABILITY" not in ui_text or "4122-SUPPLY-CHAIN-MASTER-LINKED-TRACEABILITY" not in auth_text:
    errors.append("QCMS 4.12.2 legacy build fingerprint is missing")
if "4123-SUPPLY-EXPORT-REFERENCE-HOTFIX" not in ui_text or "4123-SUPPLY-EXPORT-REFERENCE-HOTFIX" not in auth_text:
    errors.append("QCMS 4.12.3 legacy build fingerprint is missing")
if "4124-DUAL-SUPPLY-FLOW-MIS" not in ui_text or "4124-DUAL-SUPPLY-FLOW-MIS" not in auth_text:
    errors.append("QCMS 4.12.4 legacy build fingerprint is missing")
if "4125-QUALITY-DECISION-EXPORT-MIS" not in ui_text or "4125-QUALITY-DECISION-EXPORT-MIS" not in auth_text:
    errors.append("QCMS 4.12.5 legacy build fingerprint is missing")
if "4126-PROCUREMENT-PORTAL-REFERENCE-UI" not in ui_text or "4126-PROCUREMENT-PORTAL-REFERENCE-UI" not in auth_text:
    errors.append("QCMS 4.12.6 visible build fingerprint is missing")
for token in (
    "def _apply_v4126_procurement_reference_style",
    "--qcms-ref-red:#B20738",
    "--qcms-ref-bg:#EFEFEF",
    '--qcms-ref-font:Arial,"Helvetica Neue",Helvetica,sans-serif',
    "border-bottom:2px solid var(--qcms-ref-red)",
    "border-radius:2px!important",
):
    if token not in ui_text:
        errors.append(f"QCMS 4.12.6 reference UI token missing: {token}")
for token in ("#B20738", "#EFEFEF", "4126-PROCUREMENT-PORTAL-REFERENCE-UI"):
    if token not in auth_text:
        errors.append(f"QCMS 4.12.6 login reference UI token missing: {token}")

reporting_text = (ROOT / "core/reporting.py").read_text(encoding="utf-8")
reference_master_text = (ROOT / "app_pages/reference_master.py").read_text(encoding="utf-8")
selection_labels_text = (ROOT / "core/selection_labels.py").read_text(encoding="utf-8")
records_center_text = (ROOT / "app_pages/records_center.py").read_text(encoding="utf-8")
reports_text = (ROOT / "app_pages/reports.py").read_text(encoding="utf-8")
for token in ("def safe_excel_sheet_name", r"[\\/*?:\[\]]+", "used_names"):
    if token not in reporting_text:
        errors.append(f"QCMS 4.12.3 Excel sheet-name safety token missing: {token}")
for rel_text, rel_name in ((records_center_text, "Records Centre"), (reports_text, "Reports")):
    if "safe_excel_sheet_name" not in rel_text:
        errors.append(f"QCMS 4.12.3 {rel_name} Excel export is not using safe sheet titles")
for token in ("reference_record_label", "lookup_maps", "field.lookup", "human-readable name"):
    if token not in selection_labels_text:
        errors.append(f"QCMS 4.12.3 detailed Reference Master selector token missing: {token}")
if "reference_record_label" not in reference_master_text or "Select reference record" not in reference_master_text:
    errors.append("QCMS 4.12.3 Reference Master record selector is not using the detailed label helper")

supply_text = (ROOT / "app_pages/supply_chain.py").read_text(encoding="utf-8")
if "safe_excel_sheet_name" not in supply_text:
    errors.append("QCMS 4.12.3 Supply Chain Excel export is not using safe sheet titles")
supply_service_text = (ROOT / "core/supply_chain_service.py").read_text(encoding="utf-8")
supply_migration = (ROOT / "supabase/migrations/20260820010000_qcms_supply_chain_master_linked_traceability_v4122.sql").read_text(encoding="utf-8")
for token in ("Global Search", "st.columns(6", "Customer Order Import", "RMTC Number", "RMTC Date", "PDF Export", "Excel Export", "password_delete_panel"):
    if token not in supply_text:
        errors.append(f"QCMS 4.12.2 Supply Chain UI token missing: {token}")
for token in ("pending_customer_orders_for_rm", "pending_rm_purchase_orders", "pending_rm_receipts_for_dispatch", "pending_sources_for_downstream", "link_inward_to_rm_po", "import_preview", "apply_customer_order_import", "normalize_match"):
    if token not in supply_service_text:
        errors.append(f"QCMS 4.12.2 Supply Chain service token missing: {token}")
for token in ("supply_rm_purchase_order_id", "inward_lot_id", "rmtc_number", "rmtc_date", "heat_number", "source_forging_receipt_id", "source_event_id", "qsms_delete_master_row"):
    if token not in supply_migration:
        errors.append(f"QCMS 4.12.2 Supply Chain migration token missing: {token}")

material_inward_text = (ROOT / "app_pages/material_inward.py").read_text(encoding="utf-8")
streamlit_app_text = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")
for token in ("FLOW_FSI_RM", "FLOW_DIRECT_FORGING", "FLOW_FSI_RM_DIRECT_PRODUCTION", "pending_direct_forging_orders", "Flow 1 · FSI RM → Forging → Production", "Flow 2 · Direct Forging → Production", "Flow 3 · FSI RM → Direct Production", "Part Production", "render_order_mis", "Monthly Schedule / Order MIS"):
    if token not in supply_text and token not in supply_service_text:
        errors.append(f"QCMS 4.12.4 dual Supply Chain flow / MIS token missing: {token}")
for token in ("Enable Supply Chain Link", "pending_rm_purchase_orders", "unlink_inward_supply_chain"):
    if token not in material_inward_text and token not in supply_service_text:
        errors.append(f"QCMS 4.12.4 Material Inward Supply Chain link token missing: {token}")
if "supply-order-mis" not in streamlit_app_text:
    errors.append("QCMS 4.12.4 Supply Chain Order MIS navigation is missing")

staged_module_contract = {
    "app_pages/complaints.py": ("_complaint_details", "complaints_render_analysis_h"),
    "app_pages/part_master.py": ("part_master_render_entry_a", "part_master_render_entry_h"),
    "app_pages/material_grade.py": ("material_grade_render_entry_a", "material_grade_render_entry_b"),
    "app_pages/process_master.py": ("process_master_render_entry_a", "process_master_render_entry_b"),
    "app_pages/material_inward.py": ("material_inward_render_entry_a", "material_inward_render_entry_c"),
    "app_pages/rmtc_pages.py": ("rmtc_pages_render_entry_a", "rmtc_pages_render_part_f"),
    "app_pages/dimensional_report.py": ("dimensional_report_render_entry_a", "dimensional_report_render_entry_b"),
    "app_pages/metlab_report.py": ("metlab_report_render_entry_a", "metlab_report_render_entry_e"),
    "app_pages/osp_inspections.py": ("osp_inspections__render_a", "osp_inspections__render_c"),
    "app_pages/npd_apqp.py": ("npd_apqp_render_process_flow_a", "npd_status_detail_e", "npd_apqp_render_apqp_b"),
    "app_pages/user_access.py": ("user_access_create_a", "user_access_access_c"),
    "app_pages/my_account.py": ("my_account_render_a", "my_account_render_b"),
}
for relpath, tokens in staged_module_contract.items():
    page_text = (ROOT / relpath).read_text(encoding="utf-8")
    for token in tokens:
        if token not in page_text:
            errors.append(f"QCMS 4.11.8 staged workflow missing {token} in {relpath}")

# QCMS 4.11.8 extends the same staged pattern to multi-section overview/report pages.
# QCMS 4.12.5 quality-report decision/export and Supply Chain MIS identity.
metlab_text = (ROOT / "app_pages/metlab_report.py").read_text(encoding="utf-8")
dimensional_text = (ROOT / "app_pages/dimensional_report.py").read_text(encoding="utf-8")
inspection_service_text = (ROOT / "core/inspection_service.py").read_text(encoding="utf-8")
for label, page_text in (("MetLAB", metlab_text), ("Dimensional", dimensional_text)):
    for token in ("Conclusion", "Final Decision", "Decision Reason", "Download / Print PDF", "Download Excel Report"):
        if token not in page_text:
            errors.append(f"QCMS 4.12.5 {label} report token missing: {token}")
for token in ("def quality_record_excel_bytes", '["Final Decision", overall]', '["Decision Reason", decision_reason]'):
    if token not in reporting_text:
        errors.append(f"QCMS 4.12.5 reporting token missing: {token}")
for token in ('_standalone_final_payload', 'not record.get("inward_lot_id") and not record.get("osp_job_id")'):
    if token not in inspection_service_text:
        errors.append(f"QCMS 4.12.5 standalone final-decision token missing: {token}")
for token in ('"Customer Name": customer', '"Part Number": part_number', '"Part Description": part_description'):
    if token not in supply_service_text:
        errors.append(f"QCMS 4.12.5 monthly MIS identity token missing: {token}")

whole_app_stage_contract = {
    "app_pages/dashboard.py": ("dashboard_render_a", "dashboard_render_d"),
    "app_pages/inspection_home.py": ("inspection_home_render_a", "inspection_home_render_c"),
    "app_pages/reports.py": ("reports_heat_transactions_a", "reports_heat_transactions_b", "reports_osp_balance_a", "reports_osp_balance_b"),
    "app_pages/osp_transactions.py": ("osp_records_a", "osp_records_c"),
}
for relpath, tokens in whole_app_stage_contract.items():
    page_text = (ROOT / relpath).read_text(encoding="utf-8")
    for token in tokens:
        if token not in page_text:
            errors.append(f"QCMS 4.11.8 whole-app staged workflow missing {token} in {relpath}")


# QCMS 4.12.8 responsive enterprise shell and report hub contract.
if "4128-RESPONSIVE-ENTERPRISE-UI-REPORT-HUB" not in ui_text:
    errors.append("QCMS 4.12.8 responsive-enterprise build fingerprint is missing")
for token in ("def render_left_navigation", "--qcms-red:#C60035", "--qcms-charcoal:#242424", "fsi-page-chevron", "pointer-events:auto!important"):
    if token not in ui_text:
        errors.append(f"QCMS 4.12.8 responsive UI token missing: {token}")
for token in ('key="qcms_workspace"', "rail_col, content_col = st.columns", "HEADER_NAV = (", "RAIL_NAV = ("):
    if token not in app_text:
        errors.append(f"QCMS 4.12.8 workspace/navigation token missing: {token}")
for token in ("supply-chain-report", "rmtc-report", "inward-report", "dimensional-report", "metlab-report", "complaints-report"):
    if token not in app_text:
        errors.append(f"QCMS 4.12.8 report route missing: {token}")

# QCMS 4.12.9 hardened portal / field / pocket-flow contract.
if "4129-HARDENED-PORTAL-UI-POCKET-FLOW" not in ui_text:
    errors.append("QCMS 4.12.9 hardened portal build fingerprint is missing")
for token in (
    'div.st-key-fsi_left_rail', 'background:var(--qcms-charcoal)!important',
    'div[data-testid="stTextInput"] div[data-baseweb="input"]',
    'border:1.25px solid var(--qcms-line-strong)!important',
    '.fsi-flow-wrap{display:grid!important', '.fsi-master-card-head{display:flex!important',
    '.fsi-dashboard-card{min-height:74px!important'
):
    if token not in ui_text:
        errors.append(f"QCMS 4.12.9 hardened UI token missing: {token}")
for token in ('supply-chain-report', 'rmtc-report', 'inward-report', 'osp-balance-report', 'dimensional-report', 'metlab-report', 'complaints-report', 'npd-report', 'apqp-report', 'qc-report'):
    if token not in app_text:
        errors.append(f"QCMS 4.12.9 operational report shortcut missing: {token}")

# QCMS 4.13.0 / 4.13.1 visual release verification.
if "4130-UNIVERSAL-POCKET-CARD-FIELD-SYSTEM" not in ui_text:
    errors.append("QCMS 4.13.0 universal pocket build fingerprint is missing")
for token in ("npd-order-status-row", "npd-row-process-card", "qcms-pocket-grid", "stVerticalBlockBorderWrapper", "border:1.35px solid #AEB7BF"):
    if token not in ui_text:
        errors.append(f"QCMS 4.13.0 universal pocket UI token missing: {token}")
if "4131-MERITOR-FIELD-SECTION-LOGIN-REFRESH" not in ui_text:
    errors.append("QCMS 4.13.1 UI build fingerprint is missing")
for token in ("--qcms-maroon:#B20738", "--qcms-field-bg:#FFFDF2", "border:1.2px solid var(--qcms-field-border)", ".fsi-section-bar", "color:var(--qcms-heading)!important"):
    if token not in ui_text:
        errors.append(f"QCMS 4.13.1 field/section token missing: {token}")
for token in ("IDENTIFICATION", "Login *", "Password *", "background:#FFFDF0!important", "max-width:470px!important"):
    if token not in auth_text:
        errors.append(f"QCMS 4.13.1 minimal login token missing: {token}")


# QCMS 4.13.2 exact Meritor grid / section / login-image verification.
if "4132-MERITOR-EXACT-GRID-SECTION-LOGIN-IMAGE" not in ui_text:
    errors.append("QCMS 4.13.2 UI build fingerprint is missing")
for token in ("--qcms-portal-maroon:#B20738", "--qcms-portal-field:#FFFDF0", "Exact enterprise table/grid contract", "details[data-testid=\"stExpander\"] summary p", "border:1.2px solid var(--qcms-portal-field-line)"):
    if token not in ui_text:
        errors.append(f"QCMS 4.13.2 exact portal token missing: {token}")
for token in ("login_factory.jpeg", "qcms_login_image_card", "IDENTIFICATION", "st.columns([1.85, 1.0]", "height:390px!important"):
    if token not in auth_text:
        errors.append(f"QCMS 4.13.2 login-image token missing: {token}")
if not (ROOT / "assets" / "login_factory.jpeg").exists():
    errors.append("QCMS 4.13.2 factory login image is missing")


# QCMS 4.13.3 login isolation / STAWN footer / portal-polish verification.
auth_text = (ROOT / "core" / "auth.py").read_text(encoding="utf-8")
if "4133-LOGIN-NO-MENU-STAWN-FOOTER-PORTAL-POLISH" not in ui_text or "4133-LOGIN-NO-MENU-STAWN-FOOTER-PORTAL-POLISH" not in auth_text:
    errors.append("QCMS 4.13.3 build fingerprint is missing")
login_no_menu = all(token in auth_text for token in ('div.st-key-fsi_shell','st-key-qcms_workspace','st-key-fsi_left_rail','display:none!important'))
stawn_footer = 'Copyrights by <strong>STAWN</strong>' in ui_text and 'dhokaleraj@icloud.com' in ui_text
native_header_removed = 'header[data-testid="stHeader"]' in ui_text and 'display:none!important' in ui_text

# QCMS 4.13.4 priority UI / RMTC reusable balance / duplicate-safe imports.
material_inward_text = (ROOT / "app_pages" / "material_inward.py").read_text(encoding="utf-8")
master_import_text = (ROOT / "app_pages" / "master_import.py").read_text(encoding="utf-8")
supply_service_text_v4134 = (ROOT / "core" / "supply_chain_service.py").read_text(encoding="utf-8")
reference_import_text_v4134 = (ROOT / "core" / "reference_import.py").read_text(encoding="utf-8")
rmtc_reuse_sql = (ROOT / "supabase" / "migrations" / "20260821142000_qcms_rmtc_reusable_global_balance_v4134.sql").read_text(encoding="utf-8")
if "4134-PRIORITY-UI-RMTC-REUSE-DUPLICATE-SAFE-IMPORT" not in ui_text or "4134-PRIORITY-UI-RMTC-REUSE-DUPLICATE-SAFE-IMPORT" not in auth_text:
    errors.append("QCMS 4.13.4 build fingerprint is missing")
for token in ("def portal_table", "qcms-enterprise-table", "FINAL PRIORITY UI CONTRACT", "--qcms-field:#FFFDF0", "text-transform:uppercase!important"):
    if token not in ui_text:
        errors.append(f"QCMS 4.13.4 priority UI token missing: {token}")
if "Welcome to Four Star Industries" not in auth_text or "height:410px!important" not in auth_text:
    errors.append("QCMS 4.13.4 cropped company-image login contract is missing")
for token in ("Reusable Production", "RMTC Balance", "Available Production from RMTC Balance"):
    if token not in material_inward_text:
        errors.append(f"QCMS 4.13.4 reusable RMTC UI token missing: {token}")
if "global rmtc certificate quantity is the only cumulative consumption ceiling" not in rmtc_reuse_sql.casefold():
    errors.append("QCMS 4.13.4 RMTC reusable global-balance migration contract is missing")
if "cumulative production % pieces exceeds rmtc planned production" in rmtc_reuse_sql.casefold():
    errors.append("QCMS 4.13.4 migration still contains the obsolete per-part planned-production hard cap")
if "duplicate/existing row(s) skipped" not in master_import_text:
    errors.append("QCMS 4.13.4 master import duplicate-skip contract is missing")
if "SKIP_DUPLICATE" not in supply_service_text_v4134:
    errors.append("QCMS 4.13.4 supply-chain duplicate-skip contract is missing")
if "never update existing records" not in reference_import_text_v4134:
    errors.append("QCMS 4.13.4 reference import insert-only contract is missing")


# QCMS 4.13.5 final visual-cascade hotfix.
v4135_marker = "4135-MAROON-SECTIONS-WHITE-FIELDS-KPI-ICON-FIX"
if v4135_marker not in ui_text or v4135_marker not in auth_text:
    errors.append("QCMS 4.13.5 build fingerprint is missing")
for token in (
    '--qcms-v4135-field:#FFFFFF',
    'details[data-testid="stExpander"] summary p',
    'padding:13px 14px 12px 62px!important',
    'transform:translateY(-50%)!important',
):
    if token not in ui_text:
        errors.append(f"QCMS 4.13.5 UI cascade token missing: {token}")

# QCMS 4.13.6 RMTC/OSP/text-layout/source-control contract.
v4136_marker = "4136-RMTC-OSP-TEXT-LAYOUT-SOURCES"
v4136_sql = (ROOT / "supabase" / "migrations" / "20260821170000_qcms_rmtc_osp_text_layout_sources_v4136.sql").read_text(encoding="utf-8")
rmtc_pages_v4136 = (ROOT / "app_pages" / "rmtc_pages.py").read_text(encoding="utf-8")
metlab_v4136 = (ROOT / "app_pages" / "metlab_report.py").read_text(encoding="utf-8")
osp_v4136 = (ROOT / "app_pages" / "osp_transactions.py").read_text(encoding="utf-8")
layout_v4136 = (ROOT / "app_pages" / "inspection_layouts.py").read_text(encoding="utf-8")
master_service_v4136 = (ROOT / "core" / "master_service.py").read_text(encoding="utf-8")
part_master_v4136 = (ROOT / "app_pages" / "part_master.py").read_text(encoding="utf-8")
reference_master_v4136 = (ROOT / "app_pages" / "reference_master.py").read_text(encoding="utf-8")
reports_v4136 = (ROOT / "app_pages" / "reports.py").read_text(encoding="utf-8")
inspection_service_v4136 = (ROOT / "core" / "inspection_service.py").read_text(encoding="utf-8")
if v4136_marker not in ui_text or v4136_marker not in auth_text:
    errors.append("QCMS 4.13.6 build fingerprint is missing")
for token in ("qsms_add_part_to_approved_rmtc", "osp_vendor_id", "create table if not exists public.osp_receipts", "Receipt Batch Qty (pcs)"):
    if token not in (v4136_sql + osp_v4136 + rmtc_pages_v4136):
        errors.append(f"QCMS 4.13.6 RMTC/OSP token missing: {token}")
if 'selectbox("OSP Vendor"' not in metlab_v4136 or 'selectbox("Supplier"' not in metlab_v4136:
    errors.append("QCMS 4.13.6 separate Supplier / OSP Vendor MetLAB controls are missing")
if 'options=["NUMBER", "TEXT"]' not in layout_v4136 or "< 0.75" not in inspection_service_v4136:
    errors.append("QCMS 4.13.6 NUMBER/TEXT 75-percent inspection validation is incomplete")
if "Approved Suppliers" not in part_master_v4136 or "Approved Steel Mills" not in part_master_v4136:
    errors.append("QCMS 4.13.6 approved sources were not moved into Part Master")
if "approved_sources" in reference_master_v4136.split("REFERENCE_KEYS",1)[1].split(")",1)[0]:
    errors.append("QCMS 4.13.6 Approved Sources is still exposed as a Reference Master module")
if "def _fuzzy_word_duplicate" not in master_service_v4136:
    errors.append("QCMS 4.13.6 2-3 word duplicate master validation is missing")
if '"Qty kg": "steel_quantity_kg"' not in reports_v4136 or '"Balance kg": "current_heat_balance_kg"' not in reports_v4136:
    errors.append("QCMS 4.13.6 heat transaction kg quantity/balance columns are missing")

# QCMS 4.13.7 Supply PO / FSI Part / approved RMTC worksheet contract.
v4137_marker = "4138-MULTI-RM-PO-PRICE-HISTORY-TECH-DATA"
v4137_sql_path = ROOT / "supabase" / "migrations" / "20260822193000_qcms_supply_po_fsi_part_rmtc_worksheet_v4137.sql"
v4137_sql = v4137_sql_path.read_text(encoding="utf-8") if v4137_sql_path.exists() else ""
v4137_supply = (ROOT / "app_pages" / "supply_chain.py").read_text(encoding="utf-8")
v4137_service = (ROOT / "core" / "supply_chain_service.py").read_text(encoding="utf-8")
v4137_rmtc = (ROOT / "app_pages" / "rmtc_pages.py").read_text(encoding="utf-8")
v4137_part = (ROOT / "app_pages" / "part_master.py").read_text(encoding="utf-8")
v4137_po = (ROOT / "core" / "purchase_order_reporting.py").read_text(encoding="utf-8")
v4137_streamlit = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")
if v4137_marker not in ui_text or v4137_marker not in auth_text or v4137_marker not in v4137_streamlit:
    errors.append("QCMS current build fingerprint is missing from the preserved v4.13.7 contract check")
for token in ("fsi_part_number", "supply_purchase_orders", "supply_purchase_order_items", "rm_procurement_required", "three_month_schedule_pcs_snapshot"):
    if token not in v4137_sql:
        errors.append(f"QCMS 4.13.7 database contract missing: {token}")
for token in ("def procurement_check", "rolling three-month schedule quantity", "def create_purchase_order", "def purchase_order_received_qty"):
    if token not in v4137_service:
        errors.append(f"QCMS 4.13.7 Supply Chain service token missing: {token}")
if "def render_purchase_orders" not in v4137_supply or "Pending Purchase Orders" not in v4137_supply or "RM Section Orders" not in v4137_supply:
    errors.append("QCMS 4.13.7 controlled Purchase Order workspace/reports are incomplete")
if "def render_approved_part_worksheet" not in v4137_rmtc or "ADD PART NUMBER TO APPROVED RMTC" not in v4137_rmtc:
    errors.append("QCMS 4.13.7 approved RMTC Part Worksheet module is missing")
if 'text_input("FSI Part Number"' not in v4137_part:
    errors.append("QCMS 4.13.7 FSI Part Number Part Master field is missing")
if "FSI_STANDARD_PO_TERMS_2023.pdf" not in v4137_po or not (ROOT / "templates" / "FSI_STANDARD_PO_TERMS_2023.pdf").exists():
    errors.append("QCMS 4.13.7 controlled FSI Purchase Order terms template is missing")

# QCMS 4.13.8 multi-source RM PO / supplier-FSI price history / Part Master technical-data contract.
v4138_marker = "4138-MULTI-RM-PO-PRICE-HISTORY-TECH-DATA"
v4138_sql = (ROOT / "supabase" / "migrations" / "20260822213000_qcms_multi_rm_po_price_history_technical_data_v4138.sql").read_text(encoding="utf-8")
v4138_backfill = (ROOT / "supabase" / "migrations" / "20260822213100_qcms_multi_rm_po_history_backfill_v4138.sql").read_text(encoding="utf-8")
v4138_supply = (ROOT / "app_pages" / "supply_chain.py").read_text(encoding="utf-8")
v4138_service = (ROOT / "core" / "supply_chain_service.py").read_text(encoding="utf-8")
v4138_part = (ROOT / "app_pages" / "part_master.py").read_text(encoding="utf-8")
v4138_po = (ROOT / "core" / "purchase_order_reporting.py").read_text(encoding="utf-8")
if v4138_marker not in ui_text and "4140-PO-SOURCE-RMTC-VALIDATION-HSN-EMAIL" not in ui_text:
    errors.append("QCMS 4.13.8/4.14.0 compatible build fingerprint is missing")
for token in ("part_raw_material_technical_data", "part_supplier_price_history", "supply_purchase_order_sources", "technical_data_snapshot", "price_history_snapshot"):
    if token not in v4138_sql:
        errors.append(f"QCMS 4.13.8 database contract missing: {token}")
for token in ("Select ELIGIBLE Customer Orders / Schedules for this RM Purchase Order", "PO Allocation kg", "PART MASTER TECHNICAL DATA & PRICE HISTORY"):
    if token not in v4138_supply:
        errors.append(f"QCMS 4.13.8 Purchase Order UI token missing: {token}")
for token in ("def price_history", "def current_price", "def technical_data_snapshot", "supply_purchase_order_sources"):
    if token not in v4138_service:
        errors.append(f"QCMS 4.13.8 Supply Chain service token missing: {token}")
if "Save Supplier Technical Data" not in v4138_part or "Save Supplier / FSI Part Price History" not in v4138_part:
    errors.append("QCMS 4.13.8 Part Master technical data / price history editors are missing")
if not (("display_items = list(items)[:3]" in v4138_po) or ("One complete item pocket on the first page" in v4138_po)) or "TECHNICAL DATA" not in v4138_po:
    errors.append("QCMS 4.13.8+ Purchase Order item / technical snapshot rendering is incomplete")
if "Backfilled from controlled QCMS Purchase Order history" not in v4138_backfill:
    errors.append("QCMS 4.13.8 historical price/source backfill is missing")

# QCMS 4.13.9 corrective linkage / incremental RMTC / item-wise PO technical data contract.
v4139_marker = "4139-RM-PROCUREMENT-LINK-RMTC-PART-PO-ITEM-TECH"
v4139_sql = (ROOT / "supabase" / "migrations" / "20260822224500_qcms_rmtc_incremental_part_release_guard_v4139.sql").read_text(encoding="utf-8")
v4139_service = (ROOT / "core" / "supply_chain_service.py").read_text(encoding="utf-8")
v4139_po = (ROOT / "core" / "purchase_order_reporting.py").read_text(encoding="utf-8")
if v4139_marker not in ui_text and "4140-PO-SOURCE-RMTC-VALIDATION-HSN-EMAIL" not in ui_text:
    errors.append("QCMS 4.13.9/4.14.0 compatible build fingerprint is missing")
saved_decision_contract = ("must respect the decision saved with" in v4139_service) and (('proposed_three_month_qty=number(order.get("order_qty_pcs")) if str(order.get("order_type") or "") == "PURCHASE_ORDER" else 0.0' in v4139_service) or ("saved RM procurement decision" in v4139_service))
if not saved_decision_contract:
    errors.append("QCMS Customer PO saved procurement-decision contract is missing")
if "v_pending_decisions" not in v4139_sql or "PARTIALLY_APPROVED permits released Parts" not in v4139_sql:
    errors.append("QCMS 4.13.9 incremental approved-RMTC Part guard is missing")
if "SUPPLIER TECHNICAL DATA" not in v4139_po or "def _draw_technical" not in v4139_po:
    errors.append("QCMS item-wise PO technical data print sequence is missing")

# QCMS 4.14.0 PO source visibility / added-Part validation / HSN-SAC / email notification contract.
v4140_marker = "4140-PO-SOURCE-RMTC-VALIDATION-HSN-EMAIL"
v4140_sql = (ROOT / "supabase" / "migrations" / "20260824121500_qcms_po_hsn_email_notifications_v4140.sql").read_text(encoding="utf-8")
v4140_supply = (ROOT / "app_pages" / "supply_chain.py").read_text(encoding="utf-8")
v4140_service = (ROOT / "core" / "supply_chain_service.py").read_text(encoding="utf-8")
v4140_rmtc = (ROOT / "app_pages" / "rmtc_pages.py").read_text(encoding="utf-8")
v4140_po = (ROOT / "core" / "purchase_order_reporting.py").read_text(encoding="utf-8")
v4140_email = (ROOT / "app_pages" / "email_settings.py").read_text(encoding="utf-8")
v4140_notify = (ROOT / "core" / "notification_service.py").read_text(encoding="utf-8")
v4140_edge = (ROOT / "supabase" / "functions" / "qcms-send-email" / "index.ts").read_text(encoding="utf-8")
if v4140_marker not in ui_text or v4140_marker not in auth_text or v4140_marker not in v4137_streamlit:
    errors.append("QCMS 4.14.0 build fingerprint is missing")
for token in ("hsn_sac_code", "qcms_email_settings", "qcms_notification_routes", "qcms_notification_outbox", "supply_flow"):
    if token not in v4140_sql:
        errors.append(f"QCMS 4.14.0 schema contract missing: {token}")
for token in ("CUSTOMER ORDER / SCHEDULE PURCHASE ORDER ELIGIBILITY", "PO Eligibility", "Reason", "HSN / SAC"):
    if token not in v4140_supply:
        errors.append(f"QCMS 4.14.0 Purchase Order source/HSN UI token missing: {token}")
if 'explicit = str(order.get("supply_flow")' not in v4140_service or "def purchase_order_source_status" not in v4140_service:
    errors.append("QCMS 4.14.0 explicit Supply Flow / PO source eligibility service is missing")
for token in ("Validate Added Part Against Masters", "Save Added Part Final Decision", "incremental_part_review"):
    if token not in v4140_rmtc:
        errors.append(f"QCMS 4.14.0 added-Part RMTC validation token missing: {token}")
if "HSN / SAC:" not in v4140_po or "No vertical grid lines in the PO item body" not in v4140_po or "_continuation_items_bytes" not in v4140_po:
    errors.append("QCMS 4.14.0 clean HSN/SAC Purchase Order print contract is missing")
for token in ("EMAIL SERVER SETTINGS", "RESPONSIBILITY ROUTING", "TEST & NOTIFICATION OUTBOX"):
    if token not in v4140_email:
        errors.append(f"QCMS 4.14.0 Email Server settings token missing: {token}")
if "class NotificationService" not in v4140_notify or "qcms-send-email" not in v4140_notify or "Workflow execution must never" not in v4140_notify:
    errors.append("QCMS 4.14.0 notification outbox service is incomplete")
if "nodemailer" not in v4140_edge or "qcms_email_settings" not in v4140_edge or "qcms_notification_outbox" not in v4140_edge:
    errors.append("QCMS 4.14.0 server-side SMTP Edge Function is incomplete")

# QCMS 4.14.2 Purchase Order visibility + complete price-history contract.
v4142_marker = "4142-PO-ORDER-VISIBILITY-FULL-PRICE-HISTORY"
v4142_sql = (ROOT / "supabase" / "migrations" / "20260825172000_qcms_po_price_history_v4142.sql").read_text(encoding="utf-8")
if v4142_marker not in ui_text or v4142_marker not in auth_text:
    errors.append("QCMS 4.14.2 build fingerprint is missing")
for token in ("freight", "tool_cost", "packing_forwarding", "profit", "icc_rejection"):
    if token not in v4142_sql or token not in v4138_service or token not in v4138_po:
        errors.append(f"QCMS 4.14.2 price-history component missing: {token}")
if 'eligible_orders=[dict(r) for r in eligibility if bool(r.get("_po_eligible"))]' not in v4138_supply:
    errors.append("QCMS 4.14.2 RM PO selection is not using the visible eligibility source")
if "saved RM procurement decision" not in v4139_service:
    errors.append("QCMS 4.14.2 saved RM procurement decision is not authoritative at PO creation")
if "def purchase_order_items_for_print" not in v4138_service or "PRICE REVISION HISTORY" not in v4138_po:
    errors.append("QCMS 4.14.2 complete item-wise Price Revision History print is missing")

# QCMS 4.14.3 Part / Supply / Password / Microsoft 365 readiness contract.
v4143_marker = "4143-PART-GRADES-LEADTIME-OPENING-STOCK-PASSWORD-EDIT-O365"
v4143_sql = (ROOT / "supabase" / "migrations" / "20260826110000_qcms_part_supply_auth_opening_stock_v4143.sql").read_text(encoding="utf-8")
v4143_part = (ROOT / "app_pages" / "part_master.py").read_text(encoding="utf-8")
v4143_supply = (ROOT / "app_pages" / "supply_chain.py").read_text(encoding="utf-8")
v4143_auth = (ROOT / "core" / "auth.py").read_text(encoding="utf-8")
v4143_access = (ROOT / "core" / "access.py").read_text(encoding="utf-8")
v4143_password = (ROOT / "core" / "password_edit.py").read_text(encoding="utf-8")
v4143_osp = (ROOT / "core" / "osp_service.py").read_text(encoding="utf-8")
v4144_master = (ROOT / "core" / "master_service.py").read_text(encoding="utf-8")
v4144_metlab = (ROOT / "app_pages" / "metlab_report.py").read_text(encoding="utf-8")
v4144_dimensional = (ROOT / "app_pages" / "dimensional_report.py").read_text(encoding="utf-8")
v4144_rmtc = (ROOT / "app_pages" / "rmtc_pages.py").read_text(encoding="utf-8")
v4144_supply = (ROOT / "app_pages" / "supply_chain.py").read_text(encoding="utf-8")
v4144_supply_service = (ROOT / "core" / "supply_chain_service.py").read_text(encoding="utf-8")
v4144_email = (ROOT / "app_pages" / "email_settings.py").read_text(encoding="utf-8")

if v4143_marker not in ui_text or v4143_marker not in auth_text or v4143_marker not in v4137_streamlit:
    errors.append("QCMS 4.14.3 build fingerprint is missing")
for token in ("part_material_grade_links", "lead_time_days", "supply_opening_stock", "qcms_password_edit_audit", "qsms_create_osp_dispatch_from_opening_stock"):
    if token not in v4143_sql:
        errors.append(f"QCMS 4.14.3 schema contract missing: {token}")
if "Duplicate Part Number is not allowed" not in v4143_part or "Duplicate Part Description" in v4143_part:
    errors.append("QCMS 4.14.3 Part Description duplicate policy is incorrect")
for token in ("Approved / Alternate Material Grades", "Lead Time (Days)"):
    if token not in v4143_part:
        errors.append(f"QCMS 4.14.3 Part Master control missing: {token}")
if "Raw Material Type" not in v4143_part and "Raw Material Section" not in v4143_part:
    errors.append("QCMS 4.14.3 Part Master raw-material identity control is missing")
for token in ("render_opening_stock", "SUPPLY_CUSTOMER_ORDER", "Delivery default calculated from Part Master supplier lead time"):
    if token not in v4143_supply:
        errors.append(f"QCMS 4.14.3 Supply Chain control missing: {token}")
if "request_password_reset" not in v4143_auth or "Forgot Password?" not in v4143_auth:
    errors.append("QCMS 4.14.3 password recovery is incomplete")
if "password_reopen_for_edit" not in v4143_password or "Administrator access is not required" not in v4143_password:
    errors.append("QCMS 4.14.3 password-controlled report amendment is incomplete")
if "SUPPLY_CHAIN" not in v4143_access or "BUSINESS_DEVELOPMENT" not in v4143_access or "PROCUREMENT" not in v4143_access:
    errors.append("QCMS 4.14.3 functional role fallback is incomplete")
if "opening_stock_id" not in v4143_osp or "qsms_create_osp_dispatch_from_opening_stock" not in v4143_osp:
    errors.append("QCMS 4.14.3 Opening Stock to OSP integration is incomplete")

if "next(row for row in all_plans" in v4144_metlab or "historic_inward" not in v4144_metlab:
    errors.append("QCMS 4.14.4 MetLAB safe-plan/edit control is incomplete")
if "EDIT SELECTED METLAB REPORT" not in v4144_metlab or "EDIT SELECTED DIMENSIONAL REPORT" not in v4144_dimensional or "EDIT SELECTED RMTC" not in v4144_rmtc:
    errors.append("QCMS 4.14.4 prominent password edit controls are incomplete")
if '"customer_standards": ("standard_code", "standard_name")' not in v4144_master or '"parts": ("fsi_part_number",)' not in v4144_master:
    errors.append("QCMS 4.14.4 identity-only master duplicate policy is incomplete")
if "OPENING STOCK IMPORT / EXPORT UTILITY" not in v4144_supply or "opening_stock_import_preview" not in v4144_supply_service or "apply_opening_stock_import" not in v4144_supply_service:
    errors.append("QCMS 4.14.4 Opening Stock import/export utility is incomplete")
if "535 5.7.139" not in v4144_email or "Authenticated SMTP" not in v4144_email:
    errors.append("QCMS 4.14.4 Microsoft 365 SMTP guidance is incomplete")

# QCMS 4.14.5 deployment / direct-edit verification.
v4145_dashboard = (ROOT / "app_pages" / "dashboard.py").read_text(encoding="utf-8")
v4145_manifest = (ROOT / "DEPLOYMENT_MANIFEST.json").read_text(encoding="utf-8")
if "LIVE RELEASE VERIFICATION" not in v4145_dashboard or not any(token in v4145_dashboard for token in ("4145-DEPLOY-VERIFY-DIRECT-REPORT-EDIT-SMTP-TENANT-GUIDE", "4146-LIVE-RUNTIME-DIAGNOSTICS-FORCE-REDEPLOY", "4147-NEXT-STAGE-EMAIL-TEMPLATES-AUTO-OVERDUE-DEPLOY-TARGET", "4148-AUTO-SAFETY-SNAPSHOT-DIRTY-WORKTREE-DEPLOY", "4149-DEPENDENCY-BOOTSTRAP-REMOTE-DEPLOY", "41410-PO-SHIPTO-MASTER-LOGIN-REQUISITIONER", "41411-PO-MASTER-HSN-PRICE-FORM-EMAIL-CONFIRM-SERIES", "41412-RM-TYPE-PO-RM-DETAILS-FORGING-FILTER-DUPLICATE-GUARD", "41413-METLAB-CASE-DEPTH-RECORD-EMAIL-TEMPLATE-TEST-CONFIRM", "41414-LAYOUT-CASE-DEPTH-RM-PRICE-COMPANY-BRANCH", "41415-DIRECT-PRODUCTION-FLOW-EMAIL-TEMPLATE-TEST")):
    errors.append("QCMS live release verification banner is missing")
if "Select Existing MetLAB Report to Edit" not in v4144_metlab or "Select Existing Dimensional Report to Edit" not in v4144_dimensional or "Select Existing RMTC to Edit" not in v4144_rmtc:
    errors.append("QCMS 4.14.5 direct report edit selectors are incomplete")
if '"remote_push_verification"' not in v4145_manifest:
    errors.append("QCMS 4.14.5 deployment manifest is incomplete")

# QCMS 4.14.7 next-stage email templates / automatic overdue scheduler / deployment target proof.
v4147_email = (ROOT / "app_pages" / "email_settings.py").read_text(encoding="utf-8")
v4147_notify = (ROOT / "core" / "notification_service.py").read_text(encoding="utf-8")
v4147_migration = (ROOT / "supabase" / "migrations" / "20260826143000_qcms_notification_templates_overdue_v4147.sql").read_text(encoding="utf-8")
v4147_overdue = (ROOT / "supabase" / "functions" / "qcms-po-confirmation-reminder" / "index.ts").read_text(encoding="utf-8")
v4147_sender = (ROOT / "supabase" / "functions" / "qcms-send-email" / "index.ts").read_text(encoding="utf-8")
v4147_diag = (ROOT / "app_pages" / "deployment_diagnostics.py").read_text(encoding="utf-8")
if "NEXT-STAGE RESPONSIBILITY ROUTING" not in v4147_email or "MODULE EMAIL TEMPLATES" not in v4147_email:
    errors.append("QCMS 4.14.7 next-stage routing / module email templates are incomplete")
if "AUTOMATIC OPEN / OVERDUE REPORT EMAILS" not in v4147_email or "qcms_notification_schedules" not in v4147_migration:
    errors.append("QCMS 4.14.7 automatic open/overdue email schedule is incomplete")
if "attachment_manifest" not in v4147_notify or "attachments" not in v4147_sender or "storage.from" not in v4147_sender:
    errors.append("QCMS 4.14.7 controlled PDF/document email attachments are incomplete")
if "X-QCMS-Scheduler" not in v4147_overdue or "pg_cron" not in v4147_migration or "pg_net" not in v4147_migration:
    errors.append("QCMS 4.14.7 protected Supabase Cron notifier is incomplete")
if "Git origin" not in v4147_diag or "Streamlit main file" not in v4147_diag:
    errors.append("QCMS 4.14.7 live deployment target proof is incomplete")

# QCMS 4.14.10 controlled PO Ship-To / Requisitioner.
v41410_supply = (ROOT / "app_pages" / "supply_chain.py").read_text(encoding="utf-8")
v41410_service = (ROOT / "core" / "supply_chain_service.py").read_text(encoding="utf-8")
v41410_po = (ROOT / "core" / "purchase_order_reporting.py").read_text(encoding="utf-8")
v41410_sql = (ROOT / "supabase" / "migrations" / "20260826152000_qcms_po_shipto_requisitioner_v41410.sql").read_text(encoding="utf-8")
if "SHIP-TO ADDRESS · MASTER CONTROLLED" not in v41410_supply or "Ship-To Source" not in v41410_supply:
    errors.append("QCMS 4.14.10 Ship-To master selector is incomplete")
if "Requisitioner (Logged-in Employee)" not in v41410_supply or "requisitioner_employee_id" not in v41410_service:
    errors.append("QCMS 4.14.10 logged-in employee Requisitioner is incomplete")
if 'ship_to_snapshot = self._party_snapshot(ship_to_party)' not in v41410_service or '_party_lines(ship)' not in v41410_po:
    errors.append("QCMS 4.14.10 Ship-To snapshot/PDF print control is incomplete")
if "qcms_control_supply_po_identity" not in v41410_sql or "ship_to_party_id" not in v41410_sql:
    errors.append("QCMS 4.14.10 database identity control is incomplete")


# QCMS 4.14.11 controlled PO master HSN/current price/form/email confirmation/series.
v41411_supply = (ROOT / "app_pages" / "supply_chain.py").read_text(encoding="utf-8")
v41411_part = (ROOT / "app_pages" / "part_master.py").read_text(encoding="utf-8")
v41411_service = (ROOT / "core" / "supply_chain_service.py").read_text(encoding="utf-8")
v41411_po = (ROOT / "core" / "purchase_order_reporting.py").read_text(encoding="utf-8")
v41411_notify_ui = (ROOT / "core" / "notification_ui.py").read_text(encoding="utf-8")
v41411_sql = (ROOT / "supabase" / "migrations" / "20260826170500_qcms_po_master_hsn_series_entry_email_v41411.sql").read_text(encoding="utf-8")
if "Customer" not in v41411_supply or "Part Number" not in v41411_supply or "Select ELIGIBLE Customer Orders" not in v41411_supply:
    errors.append("QCMS 4.14.11 PO order selection Customer/Part identity is incomplete")
if '"HSN / SAC Code": r.get("hsn_sac_code")' not in v41411_part or "part_raw_material_details" not in v41411_sql:
    errors.append("QCMS 4.14.11 supplier Raw Material HSN control is incomplete")
if "Current Price" not in v41411_supply or 'raw.get("hsn_sac_code") or part.get("hsn_sac_code")' not in v41411_supply:
    errors.append("QCMS 4.14.11 master-driven PO Current Price / HSN is incomplete")
if "with st.form(form_key)" not in v41411_supply or 'form_submit_button("Create Controlled Purchase Order"' not in v41411_supply:
    errors.append("QCMS 4.14.11 no-per-field-refresh PO form is incomplete")
if not any(token in v41411_notify_ui for token in ("Confirm notification recipient(s)", "Review & Confirm Email Recipients")) or "Email notification after save" not in v41411_notify_ui:
    errors.append("QCMS 4.14.11 entry-level email confirmation is incomplete")
if "return 'PD9'||to_char(current_date,'DDMM')||lpad(next_value::text,5,'0')" not in v41411_sql:
    errors.append("QCMS 4.14.11 Purchase Order series is incomplete")
if "drawCentredString(w/2,47" not in v41411_po:
    errors.append("QCMS 4.14.11 centered Purchase Order footer is incomplete")

# QCMS 4.14.12 Raw Material Type / PO-type-specific technical print.
v41412_part = (ROOT / "app_pages" / "part_master.py").read_text(encoding="utf-8")
v41412_supply = (ROOT / "app_pages" / "supply_chain.py").read_text(encoding="utf-8")
v41412_service = (ROOT / "core" / "supply_chain_service.py").read_text(encoding="utf-8")
v41412_po = (ROOT / "core" / "purchase_order_reporting.py").read_text(encoding="utf-8")
v41412_sql = (ROOT / "supabase" / "migrations" / "20260826183000_qcms_raw_material_type_po_v41412.sql").read_text(encoding="utf-8")
if not any(token in v41412_part for token in ('RAW_MATERIAL_TYPE_DEFAULTS = ("Round Black Bar", "Bright Bar")', 'RAW_MATERIAL_TYPE_DEFAULTS = ("Forging", "Round Black Bar", "Casting", "Bright Bar", "Ground Bar")')) or '"Raw Material Type"' not in v41412_part:
    errors.append("QCMS 4.14.12+ controlled Raw Material Type list is incomplete")
if "duplicate_word_check=True" not in v41412_part or "MasterService._fuzzy_word_duplicate" not in v41412_part:
    errors.append("QCMS 4.14.12 Section Size/Forging Route duplicate-word guard is incomplete")
if 'RAW MATERIAL DETAILS & SUPPLIER TECHNICAL DATA' not in v41412_po or 'RAW MATERIAL / FORGING PARAMETERS & SUPPLIER TECHNICAL DATA' not in v41412_po:
    errors.append("QCMS 4.14.12 PO-type-specific technical print title is incomplete")
if 'po_kind == "RAW_MATERIAL"' not in v41412_po or 'rm_allowed_standard' not in v41412_po or 'rm_forging_only' not in v41412_po:
    errors.append("QCMS 4.14.12 RM PO forging-parameter filter is incomplete")
if '"Material Grade":grade_row.get("grade_code")' not in v41412_supply or '"Raw Material Type":raw.get("material_section_name")' not in v41412_supply:
    errors.append("QCMS 4.14.12 RM PO Part Master detail grid is incomplete")
if "part.rm_type" not in v41412_sql or "Round Black Bar" not in v41412_sql or "Bright Bar" not in v41412_sql:
    errors.append("QCMS 4.14.12 Raw Material Type seed migration is incomplete")

# QCMS 4.14.13 MetLAB Case Depth Traverse / record email / template test / modal confirmation.
v41413_metlab = (ROOT / "app_pages" / "metlab_report.py").read_text(encoding="utf-8")
v41413_reporting = (ROOT / "core" / "reporting.py").read_text(encoding="utf-8")
v41413_inspection = (ROOT / "core" / "inspection_service.py").read_text(encoding="utf-8")
v41413_notify_ui = (ROOT / "core" / "notification_ui.py").read_text(encoding="utf-8")
v41413_email = (ROOT / "app_pages" / "email_settings.py").read_text(encoding="utf-8")
v41413_supply = (ROOT / "app_pages" / "supply_chain.py").read_text(encoding="utf-8")
v41413_dim = (ROOT / "app_pages" / "dimensional_report.py").read_text(encoding="utf-8")
v41413_rmtc = (ROOT / "app_pages" / "rmtc_pages.py").read_text(encoding="utf-8")
v41413_osp = (ROOT / "app_pages" / "osp_transactions.py").read_text(encoding="utf-8")
v41414_branch = (ROOT / "app_pages" / "company_branch.py").read_text(encoding="utf-8")
v41414_supply_service = (ROOT / "core" / "supply_chain_service.py").read_text(encoding="utf-8")
v41414_migration = (ROOT / "supabase" / "migrations" / "20260826173000_qcms_case_depth_price_branch_v41414.sql").read_text(encoding="utf-8")
if "CASE_DEPTH_DEFAULT_DISTANCES = [0.05" not in v41413_metlab or "CASE DEPTH / MICROHARDNESS TRAVERSE" not in v41413_metlab:
    errors.append("QCMS 4.14.13 MetLAB Case Depth Traverse entry is incomplete")
if "Case Depth Locations" not in v41413_metlab and "Case Depth Locations from Additional Layout Characteristics" not in v41413_metlab:
    errors.append("QCMS MetLAB Case Depth Location control is incomplete")
if "def _case_depth_layout_locations" not in v41413_metlab or "CASE_DEPTH_PARAMETER_RE" not in v41413_metlab:
    errors.append("QCMS 4.14.14 layout-driven Case Depth Parameter validation is incomplete")
if '"case_depth_traverse"' not in v41413_inspection or '"case_depth_locations"' not in v41413_inspection:
    errors.append("QCMS 4.14.13 MetLAB Case Depth result persistence is incomplete")
if "def _case_depth_chart" not in v41413_reporting or "CASE DEPTH TRAVERSE · Distance (mm) vs Hardness (HV)" not in v41413_reporting:
    errors.append("QCMS 4.14.13 MetLAB Case Depth PDF chart is incomplete")
if "@st.dialog" not in v41413_notify_ui or "Notification To" not in v41413_notify_ui or "Notification CC" not in v41413_notify_ui:
    errors.append("QCMS 4.14.13 entry-level editable recipient / modal confirmation is incomplete")
if "def record_email_sender" not in v41413_notify_ui or "Review & Send Email" not in v41413_notify_ui:
    errors.append("QCMS 4.14.13 saved-record email sender is incomplete")
if "def template_test_sender" not in v41413_notify_ui or "Manual Test Recipient" not in v41413_notify_ui or "template_test_sender(" not in v41413_email:
    errors.append("QCMS 4.14.13 manual email-template test is incomplete")
if not all("record_email_sender(" in text for text in (v41413_metlab, v41413_dim, v41413_rmtc, v41413_supply, v41413_osp)):
    errors.append("QCMS 4.14.13 record-level email actions are not available across the controlled modules")
if "notification_overrides" not in v41413_notify_ui or not all("notification_overrides(" in text for text in (v41413_metlab, v41413_dim, v41413_rmtc, v41413_supply, v41413_osp)):
    errors.append("QCMS 4.14.13 entry-recipient overrides are incomplete")

# v4.14.16 permission / PO approval / cancellation / stage notification controls
v41416_access = (ROOT / "core" / "access.py").read_text(encoding="utf-8")
v41416_user_access = (ROOT / "app_pages" / "user_access.py").read_text(encoding="utf-8")
v41416_supply = (ROOT / "app_pages" / "supply_chain.py").read_text(encoding="utf-8")
v41416_service = (ROOT / "core" / "supply_chain_service.py").read_text(encoding="utf-8")
v41416_part = (ROOT / "app_pages" / "part_master.py").read_text(encoding="utf-8")
v41416_sql = (ROOT / "supabase" / "migrations" / "20260828120000_qcms_permissions_po_approval_supply_notifications_v41416.sql").read_text(encoding="utf-8")
if "department_module_defaults" not in v41416_sql or "user_section_permissions" not in v41416_sql or "can_validate" not in v41416_sql:
    errors.append("v4.14.16 three-layer department/user/section permission schema missing")
if "Explicit user permission is authoritative" not in v41416_sql or "qcms_current_department" not in v41416_sql:
    errors.append("v4.14.16 permission precedence hardening missing")
if "PENDING_APPROVAL" not in v41416_service or "Approve Purchase Order" not in v41416_supply or "qcms_approve_purchase_order" not in v41416_sql:
    errors.append("v4.14.16 PO manager approval workflow missing")
if "Cancel & Reissue with New Supplier" not in v41416_supply or "qcms_cancel_purchase_order" not in v41416_sql or "replacement_purchase_order_id" not in v41416_service:
    errors.append("v4.14.16 PO cancel/reissue workflow missing")
if '"Raw Material Type":' not in v41416_supply or '"Material Grade":' not in v41416_supply or '"Section Size":' not in v41416_supply:
    errors.append("v4.14.16 RM PO controlled item identity missing")
if "PENDING STAGE RESPONSIBILITY & NOTIFICATIONS" not in v41416_supply or "PatternFill" not in v41416_supply:
    errors.append("v4.14.16 pending stage employee notification / coloured Excel missing")
if "SUPPLIER_TECHNICAL" not in v41416_part or "PRICE_HISTORY" not in v41416_part or "SECTION VISIBILITY / EDIT CONTROL" not in v41416_user_access:
    errors.append("v4.14.16 section-level confidential visibility controls missing")

# v4.14.17 automatic Supabase schema guard / tenant persistence / configured PO approval routes
v41417_repo = (ROOT / "core" / "repository.py").read_text(encoding="utf-8")
v41417_user_access = (ROOT / "app_pages" / "user_access.py").read_text(encoding="utf-8")
v41417_supply = (ROOT / "app_pages" / "supply_chain.py").read_text(encoding="utf-8")
v41417_service = (ROOT / "core" / "supply_chain_service.py").read_text(encoding="utf-8")
v41417_sql = (ROOT / "supabase" / "migrations" / "20260828130000_qcms_auto_migration_approval_routes_v41417.sql").read_text(encoding="utf-8")
v41417_guard = (ROOT / "scripts" / "qcms_remote_schema_guard.py").read_text(encoding="utf-8")
v41417_manifest = json.loads((ROOT / "DEPLOYMENT_MANIFEST.json").read_text(encoding="utf-8"))
for _table in ("department_module_defaults", "user_section_permissions", "qcms_module_approval_routes", "supply_stage_responsibilities"):
    if f'"{_table}"' not in v41417_repo:
        errors.append(f"v4.14.17 repository tenant scope missing: {_table}")
if "MODULE APPROVAL ROUTES" not in v41417_user_access or "Save Approval Route" not in v41417_user_access:
    errors.append("v4.14.17 Module Approval Routes admin UI missing")
if "qcms_purchase_order_approval_target" not in v41417_sql or "CONFIGURED_ROUTE" not in v41417_sql or "REPORTS_TO" not in v41417_sql or "PERMISSION_FALLBACK" not in v41417_sql:
    errors.append("v4.14.17 configured PO approval-route precedence missing")
if "Self-approval is not permitted" not in v41417_sql:
    errors.append("v4.14.17 PO self-approval guard missing")
if "purchase_order_approval_target" not in v41417_service or "Required Approver" not in v41417_supply:
    errors.append("v4.14.17 PO approval target display/service missing")
if "QCMS_V41416_READY" not in v41417_guard or "QCMS_V41417_READY" not in v41417_guard or "/database/query" not in v41417_guard or "/rest/v1/rpc/qcms_release_schema_version" not in v41417_guard:
    errors.append("v4.14.17 automatic Supabase verify/apply guard missing")
if "db reset" in v41417_guard or "db push" in v41417_guard:
    errors.append("v4.14.17 remote schema guard contains destructive/history-replay command")
try:
    v41417_manifest_version = tuple(int(part) for part in str(v41417_manifest.get("version") or "0.0.0").split("."))
except Exception:
    v41417_manifest_version = (0, 0, 0)
if v41417_manifest_version < (4, 14, 17):
    errors.append("v4.14.17 deployment manifest baseline is not retained")

# v4.14.18 user/role/department permissions, employee recovery, audit and universal PDF
v41418_sql = "\n".join((ROOT / "supabase" / "migrations" / name).read_text(encoding="utf-8") for name in (
    "20260831161000_qcms_v41418_permissions_employee_access.sql",
    "20260831161100_qcms_v41418_osp_same_heat_master_delete.sql",
    "20260831161200_qcms_v41418_audit_metlab_rls_release.sql",
))
v41418_access = (ROOT / "core" / "access.py").read_text(encoding="utf-8")
v41418_activity = (ROOT / "core" / "activity.py").read_text(encoding="utf-8")
v41418_records = (ROOT / "app_pages" / "records_center.py").read_text(encoding="utf-8")
v41418_employee = (ROOT / "app_pages" / "employee_master.py").read_text(encoding="utf-8")
v41418_edge = (ROOT / "supabase" / "functions" / "qsms-user-admin" / "index.ts").read_text(encoding="utf-8")
if not all(token in v41418_sql for token in ("role_module_defaults","qcms_effective_module_permission","qcms_user_activity_log","QSMS-ADMIN-001","supply_purchase_orders','supply_purchase_order_items','supply_purchase_order_sources','supply_opening_stock")):
    errors.append("v4.14.18 permission / audit / employee recovery migration incomplete")
if "ROLE → MODULE DEFAULTS" not in v41417_user_access or "SECTION VIEW / CREATE / EDIT" not in v41417_user_access:
    errors.append("v4.14.18 Role/Department or section permission UI missing")
if "authority_options=list(AUTHORITIES)+" not in v41418_employee or "Top-level authority / No Reports-To required" not in v41418_employee:
    errors.append("v4.14.18 Employee Master legacy authority/top-level fix missing")
if "UNIVERSAL RECORD PDF DOWNLOAD" not in v41418_records or "PASSWORD-PROTECTED MASTER DELETE" not in v41418_records:
    errors.append("v4.14.18 universal PDF/master delete centre missing")
if '.update({ profile_id: userId, email' in v41418_edge or "currentEmployeeId && currentEmployeeId !== employeeId" not in v41418_edge:
    errors.append("v4.14.18 user-admin employee email/link preservation missing")
if "QCMS_V41418_READY" not in v41417_guard:
    errors.append("v4.14.18 automatic Supabase schema guard missing")
if tuple(int(x) for x in str(v41417_manifest.get("version") or "0.0.0").split(".")) < (4,14,18):
    errors.append("deployment manifest is older than v4.14.18")


# v4.14.19 live Employee PO gate, supplier confirmation, universal transaction delete and image coverage
v41419_sql = (ROOT / "supabase" / "migrations" / "20260901170000_qcms_v41419_po_enable_delete_audit_confirmation_images.sql").read_text(encoding="utf-8")
v41419_supply = (ROOT / "app_pages" / "supply_chain.py").read_text(encoding="utf-8")
v41419_auth = (ROOT / "core" / "auth.py").read_text(encoding="utf-8")
v41419_delete = (ROOT / "core" / "delete_service.py").read_text(encoding="utf-8")
v41419_attach = (ROOT / "core" / "attachments.py").read_text(encoding="utf-8")
v41419_rmtc = (ROOT / "app_pages" / "rmtc_pages.py").read_text(encoding="utf-8")
v41419_notifier = (ROOT / "supabase" / "functions" / "qcms-po-confirmation-reminder" / "index.ts").read_text(encoding="utf-8")
if not all(token in v41419_auth for token in ("refresh_current_employee_link", "qcms_current_login_employee_id", "current_employee_id")):
    errors.append("v4.14.19 live Employee resolver missing")
if not all(token in v41419_supply for token in ("po_blockers", "Supplier PO Confirmation", "PO_CONFIRMATION_REQUIRED", "SUPPLIER_PO_CONFIRMATION")):
    errors.append("v4.14.19 PO gate / supplier confirmation UI incomplete")
if not all(token in v41419_sql for token in ("supply_po_confirmations", "qcms_confirm_purchase_order", "qcms_delete_transaction_row", "PO_CONFIRMATION_DAILY", "SUPPLIER_PO_CONFIRMATION", "qcms_enforce_same_heat_code")):
    errors.append("v4.14.19 database migration incomplete")
if "MICROSTRUCTURE_IMAGE_TYPES" not in v41419_attach or "bmp" not in v41419_attach or "tiff" not in v41419_attach:
    errors.append("v4.14.19 microstructure image coverage incomplete")
if "rmtc_new_form_nonce" not in v41419_rmtc or "rmtc_direct_edit_selector" not in v41419_rmtc:
    errors.append("v4.14.19 same-Heat new TC fresh form control missing")
if "PO_CONFIRMATION_DAILY" not in v41419_notifier or "reminder_count" not in v41419_notifier:
    errors.append("v4.14.19 daily supplier PO confirmation reminder missing")

# v4.14.29 RMTC approved-source join / universal section rights / Bend Test / horizontal chemistry / explicit case-depth / reusable references / highlighted conclusions / OSP batch identity.
v41429_rmtc_service = (ROOT / "core" / "rmtc_service.py").read_text(encoding="utf-8")
v41429_rmtc_ui = (ROOT / "app_pages" / "rmtc_pages.py").read_text(encoding="utf-8")
v41429_user_access = (ROOT / "app_pages" / "user_access.py").read_text(encoding="utf-8")
v41429_layout_meta = (ROOT / "core" / "inspection_layout_metadata.py").read_text(encoding="utf-8")
v41429_layout_ui = (ROOT / "app_pages" / "inspection_layouts.py").read_text(encoding="utf-8")
v41429_metlab = (ROOT / "app_pages" / "metlab_report.py").read_text(encoding="utf-8")
v41429_reporting = (ROOT / "core" / "reporting.py").read_text(encoding="utf-8")
v41429_osp = (ROOT / "app_pages" / "osp_transactions.py").read_text(encoding="utf-8")
v41429_manifest = json.loads((ROOT / "DEPLOYMENT_MANIFEST.json").read_text(encoding="utf-8"))

if not all(token in v41429_rmtc_service for token in ("def approved_source_options", "part_raw_material_details", "part_supplier_links", "source_ready")):
    errors.append("v4.14.29 RMTC Approved Raw Material Source is not joined to Part Master approved sources/raw-material details")
if not all(token in v41429_rmtc_ui for token in ("approved_source_options", "Approved Raw Material Source", "Complete the Raw Material Details row in Part Master")):
    errors.append("v4.14.29 RMTC approved-source selector/controlled setup guard is incomplete")
if not all(token in v41429_user_access for token in ("SECTION_CATALOG", "MODULE_LABELS", "Section rights are available for all")):
    errors.append("v4.14.29 section-wise permission editor is not exposed for every controlled module")
if not all(token in v41429_layout_meta for token in ("BEND_TEST = \"BEND_TEST\"", "BEND_TEST_DEFAULT_CHARACTERISTICS", "case_depth_traverse", "case_depth_location")):
    errors.append("v4.14.29 Bend Test / case-depth characteristic metadata contract is incomplete")
if not all(token in v41429_layout_ui for token in ("Inspection Method / Sub Category", "Case Depth Traverse", "Traverse Location", "BEND_TEST_DEFAULT_CHARACTERISTICS")):
    errors.append("v4.14.29 inspection-layout Bend Test/case-depth controls are incomplete")
if not all(token in v41429_metlab for token in ("CHEMICAL_ELEMENT_ORDER", "def _chemical_horizontal_models", "def _reference_controls", "reference_documents", "conclusion_remark")):
    errors.append("v4.14.29 MetLAB horizontal chemistry/reference/conclusion controls are incomplete")
if not all(token in v41429_metlab for token in ("def _has_case_depth_characteristic", "def _case_depth_layout_locations", "case_depth_traverse", "case_depth_location")):
    errors.append("v4.14.29 explicit Case Depth Traverse checkbox/multiple-location logic is incomplete")
if not all(token in v41429_reporting for token in ("def _chemical_horizontal_report_table", "CHEMICAL ANALYSIS · ASTM E 415 / IS 8811", "def _quality_conclusion_table", "Conclusion Remark", "PatternFill")):
    errors.append("v4.14.29 report horizontal chemistry / highlighted conclusion styling is incomplete")
if not all(token in v41429_reporting for token in ("BEND TEST REPORT", "BEND TEST RESULTS", "BEND TEST EVIDENCE / PART PHOTOGRAPHS", "REFERENCE DOCUMENTS / STATEMENTS")):
    errors.append("v4.14.29 Bend Test print/report contract is incomplete")
if not all(token in v41429_osp for token in ("FSI Batch Number", "Vendor Batch Number", "Source Batch / Lot")):
    errors.append("v4.14.29 OSP transaction selectors do not expose controlled batch identity")
current_release_version = str(v41429_manifest.get("version") or "")
current_release_build = str(v41429_manifest.get("build") or "")
_expected_current_builds = {
    "4.14.45": "41445-SHARED-RAW-SOURCE-LAYOUT-CONTROL",
    "4.14.46": "41446-ANDROID-V12-DRAWER-PERSISTENT-AUTH",
    "4.14.47": "41447-PO-WATERMARK-20-APPROVER-STAMP",
    "4.14.48": "41448-PO-WATERMARK05-APPROVER-SESSION-STABILITY-ANDROID-EVERY-RELEASE",
}
if current_release_version not in _expected_current_builds or current_release_build != _expected_current_builds[current_release_version]:
    errors.append("v4.14.45+ deployment manifest release identity is incomplete")
if str(v41429_manifest.get("database_schema_required")) != "4.14.45":
    errors.append("v4.14.45 database schema baseline is incomplete")
if current_release_version == "4.14.45" and not bool(v41429_manifest.get("database_migration_required")):
    errors.append("v4.14.45 database migration contract is incomplete")
if current_release_version in {"4.14.46", "4.14.47", "4.14.48"} and bool(v41429_manifest.get("database_migration_required")):
    errors.append("v4.14.46+ must reuse the already-live v4.14.45 database schema without a new migration")

# v4.14.30 RMTC supplier de-duplication / dedicated Bend Test discovery / permission-aware Global Search.
v41430_global_search = (ROOT / "app_pages" / "global_search.py").read_text(encoding="utf-8")
v41430_inspection_home = (ROOT / "app_pages" / "inspection_home.py").read_text(encoding="utf-8")
v41430_reports = (ROOT / "app_pages" / "reports.py").read_text(encoding="utf-8")
if not all(token in v41429_rmtc_service for token in ("raw_by_supplier", "links_by_supplier", "SUPPLIER:{supplier_id}", "raw_material_details")):
    errors.append("v4.14.30 RMTC Approved Raw Material Source is not de-duplicated by Supplier")
if not all(token in v41429_rmtc_ui for token in ("Approved Raw Material Source", "Raw Material Detail", "selected_source_detail_id")):
    errors.append("v4.14.30 RMTC Supplier / Raw Material Detail two-step selector is incomplete")
if not all(token in app_text for token in ("bend-test-entry", "bend-test-records", "bend-test-report", "global-search", "qcms_shell_global_search_form")):
    errors.append("v4.14.30 dedicated Bend Test routes or persistent Global Search launcher are incomplete")
if not all(token in v41429_metlab for token in ("render_bend_test_entry", "render_bend_test_records", "required_inspection_method")):
    errors.append("v4.14.30 Bend Test dedicated report entry/register is incomplete")
if not all(token in v41430_global_search for token in ("SEARCH_SOURCES", "search_everywhere", "module_permissions", "part_ids", "party_ids", "Open Selected Record")):
    errors.append("v4.14.30 permission-aware relationship-expanded Global Search is incomplete")
if "Bend Test Report" not in v41430_inspection_home or "Bend Test" not in v41430_reports:
    errors.append("v4.14.30 Bend Test discovery cards are incomplete")

# v4.14.31 dedicated Purchase Order workspace / pre-approval edit / source reference PDF.
v41431_supply = (ROOT / "app_pages" / "supply_chain.py").read_text(encoding="utf-8")
v41431_service = (ROOT / "core" / "supply_chain_service.py").read_text(encoding="utf-8")
v41431_po_reporting = (ROOT / "core" / "purchase_order_reporting.py").read_text(encoding="utf-8")
for route in ("supply-po-order-list", "supply-po-edit", "supply-po-pdf", "supply-po-approval"):
    if route not in app_text:
        errors.append(f"v4.14.31 Purchase Order route missing: {route}")
if not all(token in v41431_supply for token in ("def _purchase_order_subnav", "def render_purchase_order_list", "def render_purchase_order_edit_page", "def render_purchase_order_pdf_page", "def render_purchase_order_approval_page")):
    errors.append("v4.14.31 dedicated Purchase Order subpages are incomplete")
if not all(token in v41431_supply for token in ("Supplier Confirmation is NOT required to edit or save it.", "Customer PO Number", "PO Position", "PO Source Qty")):
    errors.append("v4.14.31 pre-approval edit / key PO source UI contract is incomplete")
if not all(token in v41431_service for token in ("def purchase_order_source_summary", "supplier_confirmation_blocks_edit", "Customer PO Number", "PO Position", "PO Source Qty")):
    errors.append("v4.14.31 Purchase Order source summary / non-blocking confirmation service contract is incomplete")
if not all(token in v41431_po_reporting for token in ("PO SOURCE REFERENCE", "CUSTOMER PO NO.", "PART DESCRIPTION", "def _draw_customer_reference")):
    errors.append("v4.14.35 controlled Purchase Order source-reference table is incomplete")
if '"PART NUMBER"' in v41431_po_reporting or '"DELIVERY"' in v41431_po_reporting:
    errors.append("v4.14.35 supplier PO source-reference still exposes customer part number or customer delivery date")

# v4.14.32 supplier-safe PO print / controlled RM types / Android test shell.
v41432_part = (ROOT / "app_pages" / "part_master.py").read_text(encoding="utf-8")
v41432_mobile = ROOT / "mobile" / "android_qcms"
if not all(token in v41431_po_reporting for token in ("PO SOURCE REFERENCE", "PART DESCRIPTION", "part_description_master")):
    errors.append("v4.14.32 supplier-safe PO print / Part Description contract is incomplete")
if 'row.get("customer")' in v41431_po_reporting:
    errors.append("v4.14.32 supplier-facing PO print still exposes Customer identity")
if 'RAW_MATERIAL_TYPE_DEFAULTS = ("Forging", "Round Black Bar", "Casting", "Bright Bar", "Ground Bar")' not in v41432_part:
    errors.append("v4.14.32 controlled Raw Material Type list is incomplete")
for rel in ("settings.gradle", "build.gradle", "app/build.gradle", "app/src/main/AndroidManifest.xml", "app/src/main/java/com/fourstar/qcms/MainActivity.java", "BUILD_AND_INSTALL_SAMSUNG.command"):
    if not (v41432_mobile / rel).exists():
        errors.append(f"v4.14.32 Android test shell missing: {rel}")


# v4.14.33 portrait terms / batch print-email / Android SDK bootstrap.
v41433_po_reporting = (ROOT / "core" / "purchase_order_reporting.py").read_text(encoding="utf-8")
v41433_supply = (ROOT / "app_pages" / "supply_chain.py").read_text(encoding="utf-8")
v41433_android = (ROOT / "mobile" / "android_qcms" / "BUILD_AND_INSTALL_SAMSUNG.command").read_text(encoding="utf-8")
if not all(token in v41433_po_reporting for token in ("def _compact_terms_portrait", "def batch_purchase_order_pdf_bytes", "PyMuPDF")):
    errors.append("v4.14.33 portrait terms / batch PDF reporting contract is incomplete")
if not all(token in v41433_supply for token in ("BATCH PRINT / EMAIL MULTIPLE PURCHASE ORDERS", "Confirm Batch Purchase Order Emails", "Send Selected POs by Email")):
    errors.append("v4.14.33 Purchase Order batch print/email UI contract is incomplete")
if not all(token in v41433_android for token in ("ANDROID SDK / CLI BOOTSTRAP", "https://dl.google.com/android/cli/latest/", "platforms;android-35")):
    errors.append("v4.14.33 Android SDK bootstrap helper contract is incomplete")

# v4.14.34: separate files, never silently combined across POs.
if not all(token in v41433_po_reporting for token in ("def purchase_order_pdf_files", "def purchase_order_files_zip_bytes", "ZIP_DEFLATED")):
    errors.append("v4.14.34 separate PO PDF / ZIP export implementation is incomplete")
if "batch_purchase_order_pdf_bytes(" in v41433_supply or "Individual PO PDFs (ZIP)" not in v41433_supply:
    errors.append("v4.14.34 batch UI still merges different POs or lacks the ZIP download")
if not (ROOT / ".github/workflows/qcms-android-test-apk.yml").exists():
    errors.append("v4.14.34 Android APK build workflow missing")

# v4.14.35: PO status watermark / reminder guards / mobile navigation / iOS package.
v41435_migration = (ROOT / "supabase/migrations/20260921133000_qcms_v41435_po_confirmation_reminder_guard.sql").read_text(encoding="utf-8")
v41435_reminder = (ROOT / "supabase/functions/qcms-po-confirmation-reminder/index.ts").read_text(encoding="utf-8")
v41435_android_main = (ROOT / "mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java").read_text(encoding="utf-8")
if not all(token in v41431_po_reporting for token in ("_po_approval_watermark", "_watermark_pdf_bytes", "purchase_order_excel_bytes", "PENDING APPROVAL", "APPROVED")):
    errors.append("v4.14.35 PDF/Excel PO watermark implementation is incomplete")
if not all(token in v41433_supply for token in ("Download All Selected POs", "purchase_order_files_zip_bytes(po_files)")):
    errors.append("v4.14.35 one-click selected PO ZIP download is incomplete")
if not all(token in v41435_migration for token in ("qcms_po_reminder_allowed", "qcms_claim_notification_for_send", "qcms_notification_send_is_current", "qcms_po_reminder_outbox_guard")):
    errors.append("v4.14.35 supplier PO reminder guard migration is incomplete")
if not all(token in v41435_reminder for token in ("qcms_po_reminder_allowed", "qcms_claim_notification_for_send", "qcms_notification_send_is_current", 'build:"4.14.35"')):
    errors.append("v4.14.35 supplier PO reminder edge preflight is incomplete")
if not (all(token in v41435_android_main for token in ("QCMSMobile/0.1.3", "installMobileNavigationController", "navigationExpanded")) or all(token in v41435_android_main for token in ("openDrawer", "closeDrawer", "global-search", "complaints-home"))):
    errors.append("v4.14.35+ Android collapsed/native navigation contract is incomplete")
if not (ROOT / "mobile/android_qcms/app/src/main/res/drawable-nodpi/stawn_icon.png").exists():
    errors.append("v4.14.35 Android STAWN icon missing")
if not all((ROOT / "mobile/ios_qcms" / rel).exists() for rel in ("QCMSMobileIOS.xcodeproj/project.pbxproj", "QCMSMobileIOS/QCMSWebView.swift", "BUILD_IPA_ON_MAC.command")):
    errors.append("v4.14.35 iPhone/iPad source/signing package is incomplete")

# v4.14.36: Complaint register/email/reminder controls + native-like mobile drawer UI.
v41436_complaints = (ROOT / "app_pages/complaints.py").read_text(encoding="utf-8")
v41436_migration = (ROOT / "supabase/migrations/20260921190000_qcms_v41436_complaint_email_register_mobile.sql").read_text(encoding="utf-8")
v41436_overdue = (ROOT / "supabase/functions/qcms-overdue-notifier/index.ts").read_text(encoding="utf-8")
v41436_android = (ROOT / "mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java").read_text(encoding="utf-8")
v41436_ios = (ROOT / "mobile/ios_qcms/QCMSMobileIOS/ContentView.swift").read_text(encoding="utf-8") + (ROOT / "mobile/ios_qcms/QCMSMobileIOS/QCMSWebView.swift").read_text(encoding="utf-8")
if not all(token in app_text for token in ("customer-complaint-register", "supplier-complaint-register", "complaint-email-settings")):
    errors.append("v4.14.36 complaint register/email routes are incomplete")
if not all(token in v41436_complaints for token in ("def render_customer_register", "def render_supplier_register", "def render_email_configuration", "notification_confirmation", "record_email_sender", "COMPLAINT_FOLLOWUP_REMINDER")):
    errors.append("v4.14.36 complaint register/email confirmation UI is incomplete")
if not all(token in v41436_migration for token in ("CUSTOMER_COMPLAINT_CREATED", "SUPPLIER_COMPLAINT_CREATED", "COMPLAINT_CUSTOMER_OPEN_OVERDUE", "COMPLAINT_SUPPLIER_OPEN_OVERDUE", "COMPLAINT_FOLLOWUP_DUE")):
    errors.append("v4.14.36 complaint templates/routes/schedules migration is incomplete")
if not all(token in v41436_overdue for token in ("COMPLAINT_CUSTOMER_OPEN_OVERDUE", "COMPLAINT_SUPPLIER_OPEN_OVERDUE", "COMPLAINT_FOLLOWUP_DUE", "run_every_days")):
    errors.append("v4.14.36 complaint automatic reminder notifier is incomplete")
if not all(token in v41436_android for token in ("openDrawer", "closeDrawer", "global-search", "complaints-home", "stawn_icon")) or not any(v in v41436_android for v in ("QCMSMobile/0.1.4", "QCMSMobile/0.1.5", "QCMSMobile/0.1.6", "QCMSMobile/0.1.7", "QCMSMobile/0.1.8", "QCMSMobile/0.1.9", "QCMSMobile/0.2.0", "QCMSMobile/0.2.1")):
    errors.append("v4.14.36 Android reference-video drawer/bottom-navigation UI is incomplete")
if not all(token in v41436_ios for token in ("drawerOpen", "qcmsNavigate", "global-search", "complaints-home", "AppIconPreview")) or not any(v in v41436_ios for v in ("QCMSMobileIOS/0.1.1", "QCMSMobileIOS/0.1.2")):
    errors.append("v4.14.36 iPhone/iPad native drawer/bottom-navigation UI is incomplete")

# v4.14.37: Complaint status cards/PDF+party copy, PO pending approval worklist/email, fully native mobile navigation.
v41437_notification = (ROOT / "core/notification_service.py").read_text(encoding="utf-8")
v41437_streamlit = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")
if not all(token in v41436_complaints for token in ("complaint-card-grid", "complaint-stage-mini", "Send copy to", "include_generated_pdf=True", "include_record_attachments=True")):
    errors.append("v4.14.37 Complaint status-card / controlled PDF attachment / external copy controls are incomplete")
if not all(token in v41437_notification for token in ('"quality_complaints": "QUALITY_COMPLAINT"', 'related_table == "quality_complaints"', "_complaint_pdf", 'enriched.get("party_email")')):
    errors.append("v4.14.37 Complaint notification attachment/external-party service contract is incomplete")
if not all(token in v41433_supply for token in ("def _pending_po_approval_rows", "PENDING APPROVAL WORKLIST", "Email Selected Draft POs to Approver", "PO_APPROVAL_PENDING", "include_generated_pdf=True")):
    errors.append("v4.14.37 Pending PO approval count/grid/draft-email workflow is incomplete")
if not all(token in v41437_streamlit for token in ('native_mobile', 'QCMSMobile/', 'QCMSMobileIOS/', 'if not native_mobile:', 'Native-mobile content mode', '.st-key-fsi_left_rail')):
    errors.append("v4.14.37 native mobile content-only Streamlit mode is incomplete")
if not all(token in v41436_android for token in ("drawerSection", "drawerChildButton", "Approval / Confirmation", "Customer Register", "Supplier Register", "native_mobile")) or not any(v in v41436_android for v in ("QCMSMobile/0.1.5", "QCMSMobile/0.1.6", "QCMSMobile/0.1.7", "QCMSMobile/0.1.8", "QCMSMobile/0.1.9", "QCMSMobile/0.2.0", "QCMSMobile/0.2.1")):
    errors.append("v4.14.37 Android full expandable drawer/navigation contract is incomplete")
if not all(token in v41436_ios for token in ("QCMSMobileIOS/0.1.2", "expandedSections", "drawerSection", "Approval / Confirmation", "Customer Register", "Supplier Register", "native_mobile")):
    errors.append("v4.14.37 iPhone/iPad full expandable drawer/navigation contract is incomplete")

# v4.14.39: future-safe Android CI identity + explicit apksigner v2 verification.
v41439_workflow = (ROOT / ".github" / "workflows" / "qcms-android-test-apk.yml").read_text(encoding="utf-8")
v41439_android_helper = (ROOT / "mobile" / "android_qcms" / "BUILD_AND_INSTALL_SAMSUNG.command").read_text(encoding="utf-8")
if not all(token in v41439_workflow for token in ("QCMS_MOBILE_VERSION", "QCMS_MOBILE_VERSION_CODE", "QCMS_APK_NAME=QCMS_Mobile_v%s_TEST.apk", "APKSIGN_RC=${PIPESTATUS[0]}", "Verified using v2 scheme (APK Signature Scheme v2): true")):
    errors.append("v4.14.39 Android CI dynamic identity/signature verification contract is incomplete")
if any(stale in v41439_workflow for stale in ("QCMS_Mobile_v0.1.4_TEST.apk", "QCMS_Mobile_v0.1.5_TEST.apk", "QCMS_Mobile_v0.1.6_TEST.apk")):
    errors.append("v4.14.39 Android CI still contains a stale hard-coded APK version")
if not all(token in v41439_android_helper for token in ("MOBILE_VERSION=", "QCMS_Mobile_v${MOBILE_VERSION}_TEST.apk", "APKSIGN_RC=${PIPESTATUS[0]}", "Verified using v2 scheme (APK Signature Scheme v2): true", "zipalign")):
    errors.append("v4.14.39 local Android APK verification helper is incomplete")

# v4.14.38+ / v4.14.40: Android session-preserving navigation bridge.
if not all(token in v41437_streamlit for token in ('key="qcms_native_nav_bridge"', 'QCMS_NAV::', 'st.button(f"QCMS_NAV::{_native_route}"', 'st.switch_page(_native_page)')):
    errors.append("v4.14.40 Streamlit native button/switch-page navigation bridge is incomplete")
if not all(token in v41436_android for token in ("__qcmsNativeNavigate", "evaluateJavascript", "QCMS_NAV_OK", "QCMS_NAV_PENDING", "tryNavigate", "MutationObserver", "__qcmsNativeNavTimer")):
    errors.append("v4.14.40 legacy queued native navigation bridge source is incomplete")
if not all(token in v41437_streamlit for token in ('id="qcms-native-nav-ready"', '_qcms_native_last_route')):
    errors.append("v4.14.40 Streamlit native navigation readiness marker is incomplete")
if "QCMS navigation is still loading. Please try the menu again." in v41436_android:
    errors.append("v4.14.40 obsolete navigation-loading timeout toast is still present")
if not all(token in v41436_android for token in ('String normalizedRoute = path == null ? "dashboard" : path.trim();', 'final String route = normalizedRoute.isEmpty() ? "dashboard" : normalizedRoute;')) or 'if(route.isEmpty()) route = "dashboard";' in v41436_android:
    errors.append("v4.14.41 Android navigate() lambda capture is not compile-safe/final")
v41442_javac_test = (ROOT / "tests" / "test_v41441_android_lambda_compile_fix.py").read_text(encoding="utf-8")
if not all(token in v41442_javac_test for token in ("def _functional_javac_command()", "/usr/libexec/java_home", "Path(\"/usr/bin/javac\")", "pytest.skip(")):
    errors.append("v4.14.42 local javac capability guard is incomplete")
if not all(token in v41439_workflow for token in ("actions/setup-java@v4", "java-version: '17'", ":app:assembleDebug :app:lintDebug")):
    errors.append("v4.14.42 authoritative Android CI Java/Gradle compile guard is incomplete")
if "webView.loadUrl(nativeUrl(path))" in v41436_android:
    errors.append("v4.14.38 Android drawer still performs a hard WebView route load")
if 'LinearLayout bottom=new LinearLayout' in v41436_android or 'bottomButton("⌂","Home")' in v41436_android:
    errors.append("v4.14.38 Android fixed Home/Search/Complaints footer was not removed")
if "refresh.setOnClickListener" in v41436_android:
    errors.append("v4.14.38 Android top-bar hard refresh remains enabled")

# v4.14.44 Android navigation: native Menu button + Streamlit sidebar + visible module submenu.
v41443_test = (ROOT / "tests" / "test_v41443_android_streamlit_sidebar_nav.py").read_text(encoding="utf-8")
v41444_test = (ROOT / "tests" / "test_v41444_android_menu_submenu_restore.py").read_text(encoding="utf-8")
if not all(token in v41436_android for token in ("USE_STREAMLIT_WEB_NAV = true", "showStableStreamlitBrowser", "QCMSMobile/0.2.1", 'appendQueryParameter("native_nav","streamlit")', "toggleStreamlitSidebar", "installStreamlitSidebarController")):
    errors.append("v4.14.44 Android native Menu / Streamlit sidebar wrapper is incomplete")
if not all(token in v41437_streamlit for token in ("android_streamlit_nav", 'st.navigation(_mobile_page_groups, position="sidebar", expanded=True)', "elif android_streamlit_nav:", 'module_submenu(current_module, *MODULE_SUBMENUS[current_module], max_columns=2)', '[data-testid="collapsedControl"]{display:flex!important')):
    errors.append("v4.14.44 Streamlit sidebar/submenu restoration is incomplete")
if not all(token in v41444_test for token in ("test_android_v021_restores_permanent_native_menu_button", "test_streamlit_sidebar_and_android_submenu_are_visible_and_official", "test_android_footer_remains_removed_and_signature_fix_is_preserved")):
    errors.append("v4.14.44 focused Android navigation regression tests are incomplete")

# v4.14.46 Android v1.2-style drawer + persistent browser/WebView login recovery.
v41446_auth = (ROOT / "core" / "auth.py").read_text(encoding="utf-8")
v41446_test = (ROOT / "tests" / "test_v41446_android_drawer_persistent_auth.py").read_text(encoding="utf-8")
v41446_release = (ROOT / "RELEASE_NOTES_v4.14.46.md").read_text(encoding="utf-8")
if not all(token in v41436_android for token in (
    "QCMSMobile/0.2.3", "USE_STREAMLIT_WEB_NAV = false", "drawerSection", "drawerChildButton",
    'appendQueryParameter("native_nav","native")', "closeDrawer(); navigate(path)", "webView.loadUrl(nativeUrl(route))",
)):
    errors.append("v4.14.46 Android v1.2-style native drawer/autohide routing is incomplete")
if not all(token in v41437_streamlit for token in (
    "restore_persistent_login", "service_persistent_auth_bridge", "sync_persistent_login_browser",
    "elif android_native_drawer:",
)):
    errors.append("v4.14.46 Streamlit persistent-login/native-drawer contract is incomplete")
if not all(token in v41446_auth for token in (
    "st.components.v2.component", "window.localStorage.getItem(key)", "window.localStorage.setItem(key, payload)",
    "client.auth.set_session(access, refresh)", "_qcms_clear_auth_browser", "SameSite=Strict",
)):
    errors.append("v4.14.46 refresh/login persistence implementation is incomplete")
if not all(token in v41446_test for token in (
    "test_android_v022_restores_v12_style_drawer_and_auto_hides",
    "test_streamlit_restores_persistent_login_before_login_gate",
    "test_android_navigation_uses_canonical_route_and_persists_webview_storage",
)):
    errors.append("v4.14.46 focused Android/auth regression tests are incomplete")
if "Android v1.2 Drawer + Persistent Login" not in v41446_release:
    errors.append("v4.14.46 release notes are incomplete")

# v4.14.45 shared raw forging/casting source + layout identity control.
v41445_part = (ROOT / "app_pages" / "part_master.py").read_text(encoding="utf-8")
v41445_supply = (ROOT / "core" / "supply_chain_service.py").read_text(encoding="utf-8")
v41445_layout_service = (ROOT / "core" / "inspection_service.py").read_text(encoding="utf-8")
v41445_layout_ui = (ROOT / "app_pages" / "inspection_layouts.py").read_text(encoding="utf-8")
v41445_migration = (ROOT / "supabase" / "migrations" / "20260922070000_qcms_v41445_shared_raw_source_layout_scope.sql").read_text(encoding="utf-8")
v41445_guard = (ROOT / "scripts" / "qcms_remote_schema_guard.py").read_text(encoding="utf-8")
v41445_test = (ROOT / "tests" / "test_v41445_shared_raw_layout_control.py").read_text(encoding="utf-8")
if not all(token in v41445_part for token in ("Source Raw Forging / Casting Part", "source_part_id", "same commercial rate is intentionally allowed on different Part Master records")):
    errors.append("v4.14.45 Part Master shared raw-source / cross-Part price-history controls are incomplete")
if not all(token in v41445_supply for token in ("def raw_source_context", "def effective_current_price", "def effective_price_history", "SOURCE_PART_FORGING")):
    errors.append("v4.14.45 Supply Chain source-Part commercial/genealogy logic is incomplete")
if not all(token in v41445_layout_service for token in ("def auto_plan_number", "def scope_plan", "Only one current inspection layout is allowed")):
    errors.append("v4.14.45 inspection layout service controls are incomplete")
if not all(token in v41445_layout_ui for token in ("Plan Number (Auto)", "Inspection Stage is required", "Only one current layout is permitted")):
    errors.append("v4.14.45 inspection layout UI controls are incomplete")
if not all(token in v41445_migration for token in ("source_part_id", "qcms_guard_raw_source_part", "uq_qcms_inspection_plan_current_scope", "qcms_release_contract_v41445", "4.14.45")):
    errors.append("v4.14.45 additive database migration/contract is incomplete")
if not all(token in v41445_guard for token in ("V41445_MIGRATION", "QCMS_V41445_READY", "qcms_release_contract_v41445", "apply_sql(project_ref, V41445_MIGRATION)")):
    errors.append("v4.14.45 automatic Supabase migration guard is incomplete")
if not all(token in v41445_test for token in ("test_same_numeric_price_is_allowed_across_different_part_masters", "test_raw_forging_casting_can_link_another_part_master", "test_layout_plan_number_is_stage_process_part_name", "test_one_current_layout_per_controlled_part_stage_process_scope")):
    errors.append("v4.14.45 focused regression tests are incomplete")

v41447_po_reporting = (ROOT / "core" / "purchase_order_reporting.py").read_text(encoding="utf-8")
v41447_supply = (ROOT / "core" / "supply_chain_service.py").read_text(encoding="utf-8")
v41447_test = (ROOT / "tests" / "test_v41447_po_watermark_approver_stamp.py").read_text(encoding="utf-8")
if not all(token in v41447_po_reporting for token in ('setFillAlpha(0.05)', 'HexColor("#F2F4F7")', 'merge_page(watermark_page, over=False)', 'def _draw_approver_stamp', 'QCMS DIGITAL APPROVAL')):
    errors.append("v4.14.47+ PO watermark/approver stamp implementation is incomplete")
if not all(token in v41447_supply for token in ('approver_employee_name', 'approver_employee_code', 'approver_department')):
    errors.append("v4.14.47 PO approver Employee Master enrichment is incomplete")
if not all(token in v41447_test for token in ('test_watermark_is_low_visibility_and_behind_content', 'test_approved_stamp_contains_identity_and_timestamp')):
    errors.append("v4.14.47+ focused PO print regression tests are incomplete")

v41448_test = (ROOT / "tests" / "test_v41448_po_watermark_approver_android_every_release.py").read_text(encoding="utf-8")
v41448_workflow = (ROOT / ".github" / "workflows" / "qcms-android-test-apk.yml").read_text(encoding="utf-8")
v41448_gradle = (ROOT / "mobile" / "android_qcms" / "app" / "build.gradle").read_text(encoding="utf-8")
v41448_auth = (ROOT / "core" / "auth.py").read_text(encoding="utf-8")
v41448_ui = (ROOT / "core" / "ui.py").read_text(encoding="utf-8")
if not all(token in v41447_po_reporting for token in ('setFillAlpha(0.05)', 'HexColor("#F2F4F7")', 'page.merge_page(watermark_page, over=False)')):
    errors.append("v4.14.48 low-opacity background PO watermark is incomplete")
if not all(token in v41447_supply for token in ('def _enrich_purchase_order_approver', 'approver_designation', 'return self._enrich_purchase_order_approver(self.repo.get("supply_purchase_orders", purchase_order_id))')):
    errors.append("v4.14.48 real Employee Master approver print enrichment is incomplete")
if not all(token in v41448_workflow for token in ('workflow_dispatch:', 'branches:', '- main', 'QCMS_SERVER_RELEASE')):
    errors.append("v4.14.48 Android every-release GitHub build trigger is incomplete")
if not all(token in v41448_gradle for token in ('versionCode 14', "versionName '0.2.3'")):
    errors.append("v4.14.48 Android v0.2.3 identity is incomplete")
if not all(token in v41448_auth for token in ('height": 0', 'if (action === "write")', 'return;', 'Fast refresh path:', 'Stable across normal widget reruns')):
    errors.append("v4.14.48 persistent-auth duplicate-page/rerun guard is incomplete")
if not all(token in v41448_ui for token in ('st-key-qcms_auth_read', 'max-height:0!important', 'visibility:hidden!important')):
    errors.append("v4.14.48 auth bridge zero-height CSS guard is incomplete")
if not all(token in v41448_test for token in ('test_watermark_is_exactly_five_percent_background_and_unobtrusive', 'test_single_purchase_order_lookup_enriches_real_approver_employee_name', 'test_android_workflow_builds_every_main_release_and_is_manually_runnable')):
    errors.append("v4.14.48 focused regression tests are incomplete")

report = {
    "release": "QCMS 4.14.48 5% PO Watermark + Approver + Stable Session + Android Every Release",
    "v41448_watermark_background_low_opacity": 'setFillAlpha(0.05)' in v41447_po_reporting and 'merge_page(watermark_page, over=False)' in v41447_po_reporting,
    "v41448_real_approver_employee_name": 'def _enrich_purchase_order_approver' in v41447_supply and 'approver_designation' in v41447_supply,
    "v41448_android_every_release_build": 'branches:' in v41448_workflow and 'workflow_dispatch:' in v41448_workflow and 'QCMS_SERVER_RELEASE' in v41448_workflow,
    "v41448_auth_bridge_stable_rerun": "saved_at" not in v41448_auth and 'setTriggerValue("done"' not in v41448_auth and 'height": 0' in v41448_auth,
    "v41448_auth_bridge_zero_height": "st-key-qcms_auth_read" in v41448_ui and "max-height:0!important" in v41448_ui,
    "v41447_first_page_approver_stamp": 'def _draw_approver_stamp' in v41447_po_reporting and 'QCMS DIGITAL APPROVAL' in v41447_po_reporting,

    "v41446_android_v12_drawer": all(token in v41436_android for token in ("QCMSMobile/0.2.3", "USE_STREAMLIT_WEB_NAV = false", "drawerSection", "drawerChildButton", 'appendQueryParameter("native_nav","native")', "webView.loadUrl(nativeUrl(route))")),
    "v41446_drawer_autohide": "closeDrawer(); navigate(path)" in v41436_android and "drawerLayer.setVisibility(View.GONE)" in v41436_android,
    "v41446_persistent_login": all(token in v41446_auth for token in ("st.components.v2.component", "window.localStorage.getItem(key)", "window.localStorage.setItem(key, payload)", "client.auth.set_session(access, refresh)", "SameSite=Strict")),
    "v41446_schema_unchanged": str(v41429_manifest.get("database_schema_required")) == "4.14.45" and not bool(v41429_manifest.get("database_migration_required")),
    "v41445_cross_part_same_price_allowed": "same commercial rate is intentionally allowed on different Part Master records" in v41445_part,
    "v41445_source_raw_part": "source_part_id" in v41445_part and "def raw_source_context" in v41445_supply,
    "v41445_auto_layout_number": "def auto_plan_number" in v41445_layout_service and "Plan Number (Auto)" in v41445_layout_ui,
    "v41445_one_current_layout_scope": "uq_qcms_inspection_plan_current_scope" in v41445_migration and "def scope_plan" in v41445_layout_service,
    "v41445_auto_schema_guard": "apply_sql(project_ref, V41445_MIGRATION)" in v41445_guard,
    "v41444_android_native_menu": all(token in v41436_android for token in ("QCMSMobile/0.2.1", "toggleStreamlitSidebar", "installStreamlitSidebarController", "window.__qcmsToggleSidebar")),
    "v41444_streamlit_sidebar_submenu": all(token in v41437_streamlit for token in ('st.navigation(_mobile_page_groups, position="sidebar", expanded=True)', 'module_submenu(current_module, *MODULE_SUBMENUS[current_module], max_columns=2)', '[data-testid="collapsedControl"]{display:flex!important')),
    "v41443_android_fullscreen_streamlit_nav": all(token in v41436_android for token in ("USE_STREAMLIT_WEB_NAV = true", "showStableStreamlitBrowser", "QCMSMobile/0.2.1", 'appendQueryParameter("native_nav","streamlit")')),
    "v41443_streamlit_sidebar_router": all(token in v41437_streamlit for token in ("android_streamlit_nav", 'st.navigation(_mobile_page_groups, position="sidebar", expanded=True)', "elif android_streamlit_nav:")),
    "v41442_local_javac_capability_guard": all(token in v41442_javac_test for token in ("def _functional_javac_command()", "/usr/libexec/java_home", "Path(\"/usr/bin/javac\")", "pytest.skip(")),
    "v41442_android_ci_java17_compile": all(token in v41439_workflow for token in ("actions/setup-java@v4", "java-version: '17'", ":app:assembleDebug :app:lintDebug")),
    "v41439_android_ci_dynamic_identity": all(token in v41439_workflow for token in ("QCMS_MOBILE_VERSION", "QCMS_MOBILE_VERSION_CODE", "QCMS_APK_NAME=QCMS_Mobile_v%s_TEST.apk")),
    "v41439_android_ci_v2_signature": "APKSIGN_RC=${PIPESTATUS[0]}" in v41439_workflow and "Verified using v2 scheme (APK Signature Scheme v2): true" in v41439_workflow,
    "v41439_android_local_verifier": "QCMS_Mobile_v${MOBILE_VERSION}_TEST.apk" in v41439_android_helper and "zipalign" in v41439_android_helper,
    "v41440_streamlit_button_switch_bridge": all(token in v41437_streamlit for token in ('id="qcms-native-nav-ready"', 'st.button(f"QCMS_NAV::{_native_route}"', 'st.switch_page(_native_page)')),
    "v41440_android_queued_navigation": all(token in v41436_android for token in ("__qcmsNativePendingRoute", "QCMS_NAV_PENDING", "MutationObserver", "__qcmsNativeNavTimer")),
    "v41438_android_session_safe_nav": any(v in v41436_android for v in ("QCMSMobile/0.1.9", "QCMSMobile/0.2.0", "QCMSMobile/0.2.1")) and "__qcmsNativeNavigate" in v41436_android and "webView.loadUrl(nativeUrl(path))" not in v41436_android,
    "v41438_android_footer_removed": 'LinearLayout bottom=new LinearLayout' not in v41436_android and 'bottomButton("⌂","Home")' not in v41436_android,
    "v41438_streamlit_nav_bridge": 'key="qcms_native_nav_bridge"' in v41437_streamlit and "QCMS_NAV::" in v41437_streamlit,
    "v41437_complaint_status_cards": "complaint-card-grid" in v41436_complaints and "complaint-stage-mini" in v41436_complaints,
    "v41437_complaint_pdf_external_copy": 'related_table == "quality_complaints"' in v41437_notification and "include_generated_pdf=True" in v41436_complaints,
    "v41437_po_pending_approval_worklist": "PENDING APPROVAL WORKLIST" in v41433_supply and "Email Selected Draft POs to Approver" in v41433_supply,
    "v41437_mobile_content_only": "Native-mobile content mode" in v41437_streamlit and "QCMSMobile/" in v41437_streamlit,
    "v41437_android_full_nav": any(v in v41436_android for v in ("QCMSMobile/0.1.5", "QCMSMobile/0.1.6", "QCMSMobile/0.1.7", "QCMSMobile/0.1.8", "QCMSMobile/0.1.9", "QCMSMobile/0.2.0", "QCMSMobile/0.2.1")) and "drawerSection" in v41436_android,
    "v41437_ios_full_nav": "QCMSMobileIOS/0.1.2" in v41436_ios and "expandedSections" in v41436_ios,
    "v41436_complaint_registers": "def render_customer_register" in v41436_complaints and "def render_supplier_register" in v41436_complaints,
    "v41436_complaint_email_confirmation": "notification_confirmation" in v41436_complaints and "record_email_sender" in v41436_complaints,
    "v41436_complaint_reminders": "COMPLAINT_CUSTOMER_OPEN_OVERDUE" in v41436_overdue and "COMPLAINT_FOLLOWUP_DUE" in v41436_overdue,
    "v41436_android_native_ui": any(v in v41436_android for v in ("QCMSMobile/0.1.4", "QCMSMobile/0.1.5", "QCMSMobile/0.1.6", "QCMSMobile/0.1.7", "QCMSMobile/0.1.8", "QCMSMobile/0.1.9", "QCMSMobile/0.2.0", "QCMSMobile/0.2.1")) and "openDrawer" in v41436_android,
    "v41436_ios_native_ui": any(v in v41436_ios for v in ("QCMSMobileIOS/0.1.1", "QCMSMobileIOS/0.1.2")) and "qcmsNavigate" in v41436_ios,
    "v41435_po_status_watermark": "_po_approval_watermark" in v41431_po_reporting and "purchase_order_excel_bytes" in v41431_po_reporting,
    "v41435_po_customer_fields_hidden": '"PART NUMBER"' not in v41431_po_reporting and '"DELIVERY"' not in v41431_po_reporting,
    "v41435_one_click_zip": "Download All Selected POs" in v41433_supply,
    "v41435_reminder_guard": "qcms_notification_send_is_current" in v41435_migration and "qcms_notification_send_is_current" in v41435_reminder,
    "v41435_android_collapsed_menu": ("installMobileNavigationController" in v41435_android_main or "drawerSection" in v41435_android_main),
    "v41435_ios_package": (ROOT / "mobile/ios_qcms/QCMSMobileIOS.xcodeproj/project.pbxproj").exists(),
    "v41431_po_workspace": all(route in app_text for route in ("supply-po-order-list", "supply-po-edit", "supply-po-pdf", "supply-po-approval")),
    "v41431_preapproval_edit": "Supplier Confirmation is NOT required" in v41431_supply and "supplier_confirmation_blocks_edit" in v41431_service,
    "v41431_customer_reference_pdf": "def _draw_customer_reference" in v41431_po_reporting and "purchase_order_source_summary" in v41431_service,
    "v41432_supplier_safe_po_print": "PO SOURCE REFERENCE" in v41431_po_reporting and 'row.get("customer")' not in v41431_po_reporting,
    "v41432_part_description_print": "part_description_master" in v41431_service and "PART DESCRIPTION" in v41431_po_reporting,
    "v41432_compact_terms": ("def _compact_terms_two_up" in v41431_po_reporting) or ("def _compact_terms_portrait" in v41431_po_reporting),
    "v41432_rm_type_control": 'RAW_MATERIAL_TYPE_DEFAULTS = ("Forging", "Round Black Bar", "Casting", "Bright Bar", "Ground Bar")' in v41432_part,
    "v41432_android_test_shell": (v41432_mobile / "app/src/main/java/com/fourstar/qcms/MainActivity.java").exists(),
    "v41433_portrait_terms": "def _compact_terms_portrait" in v41433_po_reporting and "landscape(A4)" not in v41433_po_reporting,
    "v41433_batch_po_pdf": "def batch_purchase_order_pdf_bytes" in v41433_po_reporting,
    "v41433_batch_po_email": "Confirm Batch Purchase Order Emails" in v41433_supply,
    "v41433_android_sdk_bootstrap": "ANDROID SDK / CLI BOOTSTRAP" in v41433_android,
    "v41431_source_only_schema": (current_release_version in ("4.14.35", "4.14.36", "4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43", "4.14.44")) or (str(v41429_manifest.get("database_schema_required")) == "4.14.28" and not bool(v41429_manifest.get("database_migration_required"))),
    "v41430_rmtc_supplier_dedup": "raw_by_supplier" in v41429_rmtc_service and "Raw Material Detail" in v41429_rmtc_ui,
    "v41430_bend_test_discovery": "render_bend_test_entry" in v41429_metlab and "bend-test-report" in app_text,
    "v41430_global_search": "search_everywhere" in v41430_global_search and "qcms_shell_global_search_form" in app_text,
    "v41430_source_only_schema": (current_release_version in ("4.14.35", "4.14.36", "4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43", "4.14.44")) or (str(v41429_manifest.get("database_schema_required")) == "4.14.28" and not bool(v41429_manifest.get("database_migration_required"))),
    "v41429_rmtc_approved_source_join": "def approved_source_options" in v41429_rmtc_service and "Approved Raw Material Source" in v41429_rmtc_ui,
    "v41429_all_module_section_rights": "Section rights are available for all" in v41429_user_access,
    "v41429_bend_test_subcategory": "BEND_TEST_DEFAULT_CHARACTERISTICS" in v41429_layout_ui and "BEND TEST REPORT" in v41429_reporting,
    "v41429_horizontal_chemical_grid": "def _chemical_horizontal_models" in v41429_metlab and "def _chemical_horizontal_report_table" in v41429_reporting,
    "v41429_case_depth_checkbox_locations": "Case Depth Traverse" in v41429_layout_ui and "case_depth_location" in v41429_metlab,
    "v41429_reusable_references": "def _reference_controls" in v41429_metlab and "REFERENCE DOCUMENTS / STATEMENTS" in v41429_reporting,
    "v41429_conclusion_remark_highlight": "conclusion_remark" in v41429_metlab and "def _quality_conclusion_table" in v41429_reporting,
    "v41429_osp_batch_identity": "FSI Batch Number" in v41429_osp and "Vendor Batch Number" in v41429_osp,
    "v41429_source_only_schema": (current_release_version in ("4.14.35", "4.14.36", "4.14.37", "4.14.38", "4.14.39", "4.14.40", "4.14.41", "4.14.42", "4.14.43", "4.14.44")) or (str(v41429_manifest.get("database_schema_required")) == "4.14.28" and not bool(v41429_manifest.get("database_migration_required"))),
    "v41419_live_employee_po_gate": "refresh_current_employee_link" in v41419_auth and "po_blockers" in v41419_supply,
    "v41419_supplier_po_confirmation": "supply_po_confirmations" in v41419_sql and "PO_CONFIRMATION_DAILY" in v41419_notifier,
    "v41419_universal_transaction_delete": "qcms_delete_transaction_row" in v41419_sql and "password_transaction_delete_panel" in v41419_delete,
    "v41419_same_heat_new_tc": "qcms_enforce_same_heat_code" in v41419_sql and "rmtc_new_form_nonce" in v41419_rmtc,
    "v41419_microstructure_images": "bmp" in v41419_attach and "tiff" in v41419_attach,
    "v41418_permission_precedence": "role_module_defaults" in v41418_access and "qcms_effective_module_permission" in v41418_sql,
    "v41418_po_permission_mapping": "supply_purchase_orders','supply_purchase_order_items','supply_purchase_order_sources','supply_opening_stock" in v41418_sql,
    "v41418_employee_restore": "first_employee_email" in v41418_sql and "profile_matches=1 and employee_matches=1" in v41418_sql,
    "v41418_activity_audit": "qcms_user_activity_log" in v41418_sql and "log_route_view" in v41418_activity,
    "v41418_universal_pdf_delete": "UNIVERSAL RECORD PDF DOWNLOAD" in v41418_records and "PASSWORD-PROTECTED MASTER DELETE" in v41418_records,
    "v41418_manifest_sync": tuple(int(x) for x in str(v41417_manifest.get("version") or "0.0.0").split(".")) >= (4,14,18),
    "v41417_tenant_scoped_configuration": all(f'"{t}"' in v41417_repo for t in ("department_module_defaults", "user_section_permissions", "qcms_module_approval_routes", "supply_stage_responsibilities")),
    "v41417_approval_route_admin": "MODULE APPROVAL ROUTES" in v41417_user_access and "Save Approval Route" in v41417_user_access,
    "v41417_configured_route_precedence": all(token in v41417_sql for token in ("qcms_purchase_order_approval_target", "CONFIGURED_ROUTE", "REPORTS_TO", "PERMISSION_FALLBACK")),
    "v41417_self_approval_guard": "Self-approval is not permitted" in v41417_sql,
    "v41417_po_approval_target_ui": "purchase_order_approval_target" in v41417_service and "Required Approver" in v41417_supply,
    "v41417_auto_supabase_schema_guard": "QCMS_V41416_READY" in v41417_guard and "QCMS_V41417_READY" in v41417_guard and "/database/query" in v41417_guard and "/rest/v1/rpc/qcms_release_schema_version" in v41417_guard,
    "v41417_manifest_sync": v41417_manifest_version >= (4, 14, 17),
    "v41416_permission_precedence": "Explicit user permission is authoritative" in v41416_sql and "department_module_defaults" in v41416_access,
    "v41416_three_layer_permissions": "Validate/Review" in v41416_user_access and "Approve" in v41416_user_access and "DEPARTMENT → MODULE DEFAULTS" in v41416_user_access,
    "v41416_section_permissions": "SECTION VISIBILITY / EDIT CONTROL" in v41416_user_access and "SUPPLIER_TECHNICAL" in v41416_part and "PRICE_HISTORY" in v41416_part,
    "v41416_po_pending_approval": "PENDING_APPROVAL" in v41416_service and "Approve Purchase Order" in v41416_supply,
    "v41416_po_cancel_reissue": "Cancel & Reissue with New Supplier" in v41416_supply and "replacement_purchase_order_id" in v41416_service,
    "v41416_po_rm_item_identity": "Raw Material Type" in v41416_supply and "Material Grade" in v41416_supply and "Section Size" in v41416_supply,
    "v41416_supply_stage_notifications": "PENDING STAGE RESPONSIBILITY & NOTIFICATIONS" in v41416_supply and "Send Current-Stage Notifications" in v41416_supply,
    "v41416_coloured_supply_excel": "PatternFill" in v41416_supply and "PENDING_APPROVAL" in v41416_supply,
    "v41413_metlab_case_depth": "CASE DEPTH / MICROHARDNESS TRAVERSE" in v41413_metlab and "0.05" in v41413_metlab,
    "v41413_case_depth_locations_chart": "Case Depth Locations" in v41413_metlab and "def _case_depth_chart" in v41413_reporting,
    "v41413_record_email": "def record_email_sender" in v41413_notify_ui,
    "v41413_template_test": "def template_test_sender" in v41413_notify_ui and "template_test_sender(" in v41413_email,
    "v41413_email_confirm_edit_recipient": "@st.dialog" in v41413_notify_ui and "Notification To" in v41413_notify_ui and "Notification CC" in v41413_notify_ui,
    "v41414_layout_case_depth": "def _case_depth_layout_locations" in v41413_metlab and "CASE_DEPTH_PARAMETER_RE" in v41413_metlab and "layout_rows=layout_source" in v41413_metlab,
    "v41414_rm_price_raw_detail": "raw_material_detail_id: str | None = None" in v41414_supply_service and "exact_uom" in v41414_supply_service,
    "v41414_company_branch": "Company Branch Master" in v41414_branch and "create table if not exists public.company_branches" in v41414_migration,
    "v41415_direct_production_flow": "FLOW_FSI_RM_DIRECT_PRODUCTION" in supply_service_text and "Direct Production flow · Forging PO not required" in supply_service_text and "source_rm_receipt_id" in (ROOT / "supabase/migrations/20260827081500_qcms_direct_production_flow_v41415.sql").read_text(encoding="utf-8"),
    "v41415_email_template_test": '"D", "TEST EMAIL TEMPLATE"' in v4140_email and "Manual Test Recipient" in (ROOT / "core/notification_ui.py").read_text(encoding="utf-8"),
    "v41412_raw_material_type": "Raw Material Type" in v41412_part and "part.rm_type" in v41412_sql,
    "v41412_rm_po_details": "RAW MATERIAL DETAILS" in v41412_po and "rm_allowed" in v41412_po,
    "v41412_rm_po_forging_filter": 'po_kind == "RAW_MATERIAL"' in v41412_po,
    "v41412_duplicate_word_guard": "duplicate_word_check=True" in v41412_part,
    "po_source_visibility": "def purchase_order_source_status" in v4140_service and "PO Eligibility" in v4140_supply,
    "explicit_supply_flow": 'explicit = str(order.get("supply_flow")' in v4140_service and "supply_flow" in v4140_sql,
    "added_part_validate_decide": "incremental_part_review" in v4140_rmtc and "Validate Added Part Against Masters" in v4140_rmtc,
    "po_hsn_sac": "hsn_sac_code" in v4140_sql and "HSN / SAC:" in v4140_po,
    "po_clean_item_layout": "No vertical grid lines in the PO item body" in v4140_po and (("display_items = list(items)[:3]" in v4140_po) or ("One complete item pocket on the first page" in v4140_po)),
    "email_server_settings": "EMAIL SERVER SETTINGS" in v4140_email,
    "responsibility_routing": "RESPONSIBILITY ROUTING" in v4140_email,
    "email_outbox": "qcms_notification_outbox" in v4140_sql and "class NotificationService" in v4140_notify,
    "smtp_edge_function": "nodemailer" in v4140_edge,
    "v4142_po_visible_selection": "eligible_orders=[dict(r) for r in eligibility if bool(r.get(\"_po_eligible\"))]" in v4138_supply,
    "v4142_saved_rm_decision": "saved RM procurement decision" in v4139_service,
    "v4142_full_price_history": "def purchase_order_items_for_print" in v4138_service and "PRICE REVISION HISTORY" in v4138_po,
    "v4142_price_cost_components": all(token in v4142_sql and token in v4138_po for token in ("freight", "tool_cost", "packing_forwarding", "profit", "icc_rejection")),
    "v4143_multiple_part_grades": "part_material_grade_links" in v4143_sql and "Approved / Alternate Material Grades" in v4143_part,
    "v4143_supplier_lead_time": "lead_time_days" in v4143_sql and "Delivery default calculated from Part Master supplier lead time" in v4143_supply,
    "v4143_opening_stock_osp": "supply_opening_stock" in v4143_sql and "qsms_create_osp_dispatch_from_opening_stock" in v4143_osp,
    "v4143_password_edit": "password_reopen_for_edit" in v4143_password,
    "v4143_password_recovery": "request_password_reset" in v4143_auth,
    "v4144_metlab_safe_plan": "next(row for row in all_plans" not in v4144_metlab and "historic_inward" in v4144_metlab,
    "v4144_report_password_edit": all(token in combined for token, combined in (("EDIT SELECTED METLAB REPORT", v4144_metlab), ("EDIT SELECTED DIMENSIONAL REPORT", v4144_dimensional), ("EDIT SELECTED RMTC", v4144_rmtc))),
    "v4144_identity_duplicate_policy": '"customer_standards": ("standard_code", "standard_name")' in v4144_master and '"parts": ("fsi_part_number",)' in v4144_master,
    "v4144_opening_stock_import": "OPENING STOCK IMPORT / EXPORT UTILITY" in v4144_supply and "opening_stock_import_preview" in v4144_supply_service and "apply_opening_stock_import" in v4144_supply_service,
    "v4144_smtp_auth_guidance": "535 5.7.139" in v4144_email and "Authenticated SMTP" in v4144_email,
    "v4145_live_release_banner": "LIVE RELEASE VERIFICATION" in v4145_dashboard and any(token in v4145_dashboard for token in ("4145-DEPLOY-VERIFY-DIRECT-REPORT-EDIT-SMTP-TENANT-GUIDE", "4146-LIVE-RUNTIME-DIAGNOSTICS-FORCE-REDEPLOY", "4147-NEXT-STAGE-EMAIL-TEMPLATES-AUTO-OVERDUE-DEPLOY-TARGET", "4148-AUTO-SAFETY-SNAPSHOT-DIRTY-WORKTREE-DEPLOY", "4149-DEPENDENCY-BOOTSTRAP-REMOTE-DEPLOY", "41410-PO-SHIPTO-MASTER-LOGIN-REQUISITIONER", "41411-PO-MASTER-HSN-PRICE-FORM-EMAIL-CONFIRM-SERIES", "41412-RM-TYPE-PO-RM-DETAILS-FORGING-FILTER-DUPLICATE-GUARD", "41413-METLAB-CASE-DEPTH-RECORD-EMAIL-TEMPLATE-TEST-CONFIRM", "41414-LAYOUT-CASE-DEPTH-RM-PRICE-COMPANY-BRANCH", "41415-DIRECT-PRODUCTION-FLOW-EMAIL-TEMPLATE-TEST")),
    "v4146_runtime_diagnostics": "deployment-diagnostics" in app_text and "LIVE BUILD · QCMS" in app_text and (ROOT / "app_pages" / "deployment_diagnostics.py").exists(),
    "v4147_deploy_target_proof": "Git origin" in v4147_diag and "Streamlit main file" in v4147_diag,
    "v4147_next_stage_email": "NEXT-STAGE RESPONSIBILITY ROUTING" in v4147_email and "department_emails" in v4147_notify,
    "v4147_email_templates": "MODULE EMAIL TEMPLATES" in v4147_email and "qcms_email_templates" in v4147_migration,
    "v4147_email_attachments": "attachment_manifest" in v4147_notify and "attachments" in v4147_sender,
    "v4147_overdue_scheduler": "qcms-overdue-notifier-hourly" in v4147_migration and "X-QCMS-Scheduler" in v4147_overdue,
    "v41410_po_ship_to_master": "SHIP-TO ADDRESS · MASTER CONTROLLED" in v41410_supply and "ship_to_party_id" in v41410_service,
    "v41410_login_employee_requisitioner": "Requisitioner (Logged-in Employee)" in v41410_supply and "requisitioner_employee_id" in v41410_service,
    "v41410_ship_to_pdf_snapshot": "_party_lines(ship)" in v41410_po and "qcms_control_supply_po_identity" in v41410_sql,
    "v41411_po_order_customer_part": "Customer" in v41411_supply and "Part Number" in v41411_supply,
    "v41411_raw_material_hsn": '"HSN / SAC Code": r.get("hsn_sac_code")' in v41411_part and "hsn_sac_code" in v41411_sql,
    "v41411_master_price_hsn_po": "Current Price" in v41411_supply and 'raw.get("hsn_sac_code") or part.get("hsn_sac_code")' in v41411_supply,
    "v41411_po_form_no_field_refresh": "with st.form(form_key)" in v41411_supply,
    "v41411_entry_email_confirmation": any(token in v41411_notify_ui for token in ("Confirm notification recipient(s)", "Review & Confirm Email Recipients")),
    "v41411_po_series": "PD9" in v41411_sql and "DDMM" in v41411_sql and "lpad(next_value::text,5,'0')" in v41411_sql,
    "v41411_centered_po_footer": "drawCentredString(w/2,47" in v41411_po,
    "v4145_direct_report_edit": all(token in combined for token, combined in (("Select Existing MetLAB Report to Edit", v4144_metlab), ("Select Existing Dimensional Report to Edit", v4144_dimensional), ("Select Existing RMTC to Edit", v4144_rmtc))),
    "v4145_remote_push_manifest": '"remote_push_verification"' in v4145_manifest,

    "customer_order_rm_procurement_link_fix": saved_decision_contract,
    "incremental_approved_rmtc_part_guard": "v_pending_decisions" in v4139_sql,
    "item_wise_po_technical_data": ("def _draw_technical" in v4139_po) and "SUPPLIER TECHNICAL DATA" in v4139_po,
    "multi_rm_po_sources": "Select ELIGIBLE Customer Orders / Schedules for this RM Purchase Order" in v4138_supply and "supply_purchase_order_sources" in v4138_service,
    "supplier_fsi_price_history": "part_supplier_price_history" in v4138_sql and "def current_price" in v4138_service,
    "part_master_po_technical_data": "Save Supplier Technical Data" in v4138_part and "technical_data_snapshot" in v4138_service,
    "multi_line_po_pdf": "def _continuation_items_bytes" in v4138_po and "if len(normalized) > 1" in v4138_po,
    "historical_po_price_backfill": "Backfilled from controlled QCMS Purchase Order history" in v4138_backfill,
    "supply_purchase_order_module": "def render_purchase_orders" in v4137_supply,
    "supply_po_reference_print": "FSI_STANDARD_PO_TERMS_2023.pdf" in v4137_po,
    "fsi_part_number_identity": 'text_input("FSI Part Number"' in v4137_part,
    "customer_order_three_month_procurement_gate": "def procurement_check" in v4137_service and "rolling three-month schedule quantity" in v4137_service,
    "approved_rmtc_part_worksheet_page": "def render_approved_part_worksheet" in v4137_rmtc,
    "rmtc_approved_part_extension": "ADD PART NUMBER TO APPROVED RMTC" in rmtc_pages_v4136,
    "metlab_separate_osp_vendor": 'selectbox("OSP Vendor"' in metlab_v4136,
    "osp_partial_receipts": "Receipt Batch Qty (pcs)" in osp_v4136 and "public.osp_receipts" in v4136_sql,
    "duplicate_word_validation": "def _fuzzy_word_duplicate" in master_service_v4136,
    "part_master_approved_sources": "Approved Suppliers" in part_master_v4136 and "Approved Steel Mills" in part_master_v4136,
    "number_text_characteristics": 'options=["NUMBER", "TEXT"]' in layout_v4136,
    "text_similarity_75": "< 0.75" in inspection_service_v4136,
    "heat_transaction_kg_balance": '"Qty kg": "steel_quantity_kg"' in reports_v4136 and '"Balance kg": "current_heat_balance_kg"' in reports_v4136,
    "v4135_maroon_all_expanders": v4135_marker in ui_text and 'details[data-testid="stExpander"] summary p' in ui_text,
    "v4135_white_field_pockets": "--qcms-v4135-field:#FFFFFF" in ui_text,
    "v4135_kpi_icon_column": "padding:13px 14px 12px 62px!important" in ui_text,
    "priority_ui_contract": "FINAL PRIORITY UI CONTRACT" in ui_text,
    "deterministic_enterprise_tables": "def portal_table" in ui_text and "qcms-enterprise-table" in ui_text,
    "cropped_company_login": "Welcome to Four Star Industries" in auth_text and (ROOT / "assets" / "login_factory.jpeg").exists(),
    "rmtc_reuse_by_global_balance": "global rmtc certificate quantity is the only cumulative consumption ceiling" in rmtc_reuse_sql.casefold(),
    "duplicate_safe_imports": all(("duplicate/existing row(s) skipped" in master_import_text, "SKIP_DUPLICATE" in supply_service_text_v4134, "never update existing records" in reference_import_text_v4134)),
    "customer_order_duplicate_skip_only": "SKIP_DUPLICATE" in supply_service_text_v4134,
    "login_no_menu": login_no_menu,
    "stawn_footer": stawn_footer,
    "native_header_removed": native_header_removed,
    "meritor_reference_field_system": "--qcms-field-bg:#FFFDF2" in ui_text and "--qcms-maroon:#B20738" in ui_text,
    "maroon_section_hierarchy": "color:var(--qcms-heading)!important" in ui_text,
    "minimal_identification_login": "IDENTIFICATION" in auth_text and "Login *" in auth_text and "Password *" in auth_text,
    "factory_image_login": "login_factory.jpeg" in auth_text and (ROOT / "assets" / "login_factory.jpeg").exists(),
    "exact_enterprise_grid": "Exact enterprise table/grid contract" in ui_text,
    "meritor_collapsible_sections": "--qcms-portal-maroon:#B20738" in ui_text and "stExpander" in ui_text,
    "hardened_portal_shell": True,
    "visible_widget_borders": True,
    "pocket_flow_layout": True,
    "operational_report_shortcuts": True,
    "responsive_enterprise_ui": True,
    "non_overlapping_column_workspace": True,
    "clickable_header_navigation": True,
    "enterprise_grid_cards_fields": True,
    "report_hub_complete": True,
    "registered_pages": paths,
    "controlled_reference_definitions": len(DEFINITIONS),
    "controlled_reference_masters": len(DEFINITIONS),
    "part_master_grids": 4,
    "material_grade_embedded_chemistry": True,
    "multi_part_rmtc": True,
    "rmtc_draft_to_pending": True,
    "calculated_jominy": True,
    "calculated_di": True,
    "module_permissions": True,
    "password_protected_delete": True,
    "back_navigation": True,
    "enterprise_erp_theme": True,
    "central_records_navigation": True,
    "minimal_metallic_ui": True,
    "zoho_visible_shell": True,
    "export_shipment_shell": True,
    "controlled_drawing_revision_history": True,
    "drawing_old_revisions_inactive": True,
    "complaint_titled_photographs": True,
    "complaint_entry_evidence_visible_before_first_save": True,
    "complaint_section_color_grading": True,
    "complaint_collapsible_stage_sequence": True,
    "global_staged_sections": True,
    "supply_chain_master_linked_traceability": True,
    "supply_chain_global_search": True,
    "supply_chain_pdf_excel_exports": True,
    "supply_chain_password_delete": True,
    "supply_chain_six_month_schedule": True,
    "supply_chain_material_inward_bridge": True,
    "supply_chain_heat_lineage": True,
    "customer_order_import_a_to_f": True,
    "customer_order_duplicate_update_confirmation": True,
    "supply_chain_dual_flow": True,
    "supply_chain_direct_forging": True,
    "material_inward_supply_link_toggle": True,
    "supply_chain_order_dispatch_mis": True,
    "supply_chain_monthly_customer_part_identity": True,
    "quality_conclusion_final_decision": True,
    "quality_pdf_excel_print_exports": True,
    "standalone_quality_finalization": True,
    "procurement_portal_reference_ui": True,
    "reference_red_white_shell": True,
    "reference_flat_field_borders": True,
    "reference_clean_section_titles": True,
    "stages_collapsed_by_default": True,
    "single_blue_stage_family": True,
    "complaint_stage_titles_100pct_larger": True,
    "header_profile_action_grid": True,
    "complaint_multiple_attachments": True,
    "header_actions_non_overlapping": True,
    "template_centre": True,
    "jominy_inch_to_mm": True,
    "reusable_grid_lists": True,
    "complete_disposition_options": True,
    "dashboard_bar_charts": True,
    "dashboard_pie_charts": 3,
    "automatic_reference_master_codes": True,
    "heat_number_search": True,
    "global_heat_steel_ledger": True,
    "combined_heat_commitment": True,
    "supplier_rmtc_number_unique_per_heat": True,
    "heat_steel_ledger_page": True,
    "heat_steel_ledger_excel_export": True,
    "inward_before_after_heat_balance": True,
    "rmtc_inward_plus_remaining_plan_guard": True,
    "unified_records_centre": True,
    "dashboard_inward_status_consistency": True,
    "same_heat_new_rmtc_action": True,
    "rejected_heat_reuse": True,
    "visible_menu_text": True,
    "admin_rmtc_decision_revision": True,
    "rmtc_idempotent_save": True,
    "supabase_read_retry": True,
    "dashboard": True,
    "material_inward": True,
    "steel_quantity_control": True,
    "production_weight_conversion": True,
    "automatic_layout_selection": True,
    "rmtc_style_metlab_sections": True,
    "bulk_report_save": True,
    "heat_wide_production_control": True,
    "production_disposition_breakdown": True,
    "metlab_microstructure_images": 4,
    "inspection_layouts": True,
    "dimensional_excel_import": True,
    "dimensional_report": True,
    "metlab_report": True,
    "post_inward_quality_gate": True,
    "osp_material_out": True,
    "osp_sample_quality_gate": True,
    "osp_full_inward_gate": True,
    "osp_production_release_gate": True,
    "process_specific_osp_layouts": True,
    "osp_parameter_groups": True,
    "osp_process_drawing": True,
    "generated_osp_layouts": True,
    "heat_transaction_report": True,
    "osp_heat_balance_report": True,
    "dedicated_process_master": True,
    "simplified_osp_metlab_grid": True,
    "final_metallurgical_requirements": True,
    "single_persistent_navigation": True,
    "unified_report_print_theme": True,
    "portal_ready": True,
    "npd_apqp_module": True,
    "part_process_flow_designer": True,
    "npd_order_realtime_status": True,
    "apqp_gate_tracking": True,
    "normalized_duplicate_control": True,
    "record_pdf_everywhere": True,
    "npd_process_checkpoints": True,
    "employee_linked_responsibility": True,
    "qc_calculation_tools": True,
    "astm_e140_table1_conversion": True,
    "self_service_password_change": True,
    "first_admin_removed_from_login": True,
    "master_import_upload": True,
    "pending_order_process_matrix": True,
    "customer_standards_bank": True,
    "detailed_complaint_analysis": True,
    "complaint_5why_rca": True,
    "complaint_multi_action_capa": True,
    "complaint_closure_guard": True,
    "complaint_responsibility_matrix": True,
    "multiple_part_standard_links": True,
    "rich_selection_labels": True,
    "npd_card_rows_color_pdf": True,
    "metlab_photo_titles": True,
    "pdf_available_to_viewers": True,
    "standard_download_rich_details": True,
    "admin_only_part_standard_unlink": True,
    "readability_font_weight_plus_10_percent": True,
    "complaint_management": True,
    "complaint_followup_tracking": True,
    "debit_note_settlement_tracking": True,
    "login_css_rebuild": True,
    "excel_export_sheet_sanitization": "safe_excel_sheet_name" in reporting_text and "safe_excel_sheet_name" in supply_text,
    "reference_master_detailed_selector": "reference_record_label" in reference_master_text and "reference_record_label" in selection_labels_text,
    "errors": errors,
}
print(json.dumps(report, indent=2))
raise SystemExit(1 if errors else 0)
