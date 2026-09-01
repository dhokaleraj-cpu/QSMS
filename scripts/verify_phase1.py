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
    "dashboard", "deployment-diagnostics", "masters", "company-branch-entry", "company-branch-records", "rmtc-entry", "rmtc-approved-worksheet", "inward-entry", "osp-home", "supply-chain-home", "supply-customer-orders", "supply-opening-stock", "supply-rm-procurement", "supply-purchase-orders", "supply-rm-receipt", "supply-rm-dispatch", "supply-forging", "supply-downstream", "supply-traceability", "supply-order-mis", "npd-process-flow", "npd-status", "apqp", "qc-tools", "qc-calculation-records", "complaints-home", "customer-complaint", "supplier-complaint", "complaint-analysis", "complaint-records", "inspection-home", "records-center", "heat-ledger",
    "reports-home", "heat-transaction-report", "osp-balance-report", "supply-chain-report", "rmtc-report", "inward-report", "dimensional-report", "metlab-report", "complaints-report", "traceability-report", "npd-report", "apqp-report", "qc-report", "inspection-layout-report", "standards-report", "templates",
    "part-entry", "part-records", "process-entry", "process-records", "grade-entry", "grade-records",
    "reference-entry", "reference-records", "employee-entry", "employee-records",
    "user-access", "email-settings", "master-import", "standards-entry", "standards-records", "my-account", "rmtc-part", "rmtc-records", "rmtc-approval", "inward-records",
    "osp-material-out", "osp-sample-receipt", "osp-inward", "osp-dimensional", "osp-metlab", "osp-records",
    "inspection-layout-entry", "inspection-layout-records", "dimensional-entry",
    "dimensional-records", "metlab-entry", "metlab-records",
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
    "dimensional-records", "metlab-records", "inspection-layout-records",
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
if "RAW MATERIAL / FORGING PARAMETERS & FSI TECHNICAL DATA" not in v4139_po or not (("compact_technical_pairs" in v4139_po) or ("def _draw_technical" in v4139_po)):
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
if 'RAW_MATERIAL_TYPE_DEFAULTS = ("Round Black Bar", "Bright Bar")' not in v41412_part or '"Raw Material Type"' not in v41412_part:
    errors.append("QCMS 4.14.12 controlled Raw Material Type list is incomplete")
if "duplicate_word_check=True" not in v41412_part or "MasterService._fuzzy_word_duplicate" not in v41412_part:
    errors.append("QCMS 4.14.12 Section Size/Forging Route duplicate-word guard is incomplete")
if 'title = "RAW MATERIAL DETAILS" if is_rm else "RAW MATERIAL / FORGING PARAMETERS & FSI TECHNICAL DATA"' not in v41412_po:
    errors.append("QCMS 4.14.12 PO-type-specific technical print title is incomplete")
if 'po_kind == "RAW_MATERIAL"' not in v41412_po or 'rm_allowed' not in v41412_po:
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

report = {
    "release": "QCMS 4.14.19 PO Employee Gate / Delete / User Status / Same Heat / Supplier Confirmation / Images",
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
    "item_wise_po_technical_data": (("compact_technical_pairs" in v4139_po) or ("def _draw_technical" in v4139_po)) and "RAW MATERIAL / FORGING PARAMETERS & FSI TECHNICAL DATA" in v4139_po,
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
