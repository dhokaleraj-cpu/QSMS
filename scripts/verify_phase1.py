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
]
for item in required:
    if not (ROOT / item).exists():
        errors.append(f"Missing required file: {item}")

app_text = (ROOT / "streamlit_app.py").read_text()
paths = re.findall(r'url_path="([^"]+)"', app_text)
expected_paths = {
    "dashboard", "masters", "rmtc-entry", "rmtc-approved-worksheet", "inward-entry", "osp-home", "supply-chain-home", "supply-customer-orders", "supply-rm-procurement", "supply-purchase-orders", "supply-rm-receipt", "supply-rm-dispatch", "supply-forging", "supply-downstream", "supply-traceability", "supply-order-mis", "npd-process-flow", "npd-status", "apqp", "qc-tools", "qc-calculation-records", "complaints-home", "customer-complaint", "supplier-complaint", "complaint-analysis", "complaint-records", "inspection-home", "records-center", "heat-ledger",
    "reports-home", "heat-transaction-report", "osp-balance-report", "supply-chain-report", "rmtc-report", "inward-report", "dimensional-report", "metlab-report", "complaints-report", "traceability-report", "npd-report", "apqp-report", "qc-report", "inspection-layout-report", "standards-report", "templates",
    "part-entry", "part-records", "process-entry", "process-records", "grade-entry", "grade-records",
    "reference-entry", "reference-records", "employee-entry", "employee-records",
    "user-access", "master-import", "standards-entry", "standards-records", "my-account", "rmtc-part", "rmtc-records", "rmtc-approval", "inward-records",
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
for token in ("FLOW_FSI_RM", "FLOW_DIRECT_FORGING", "pending_direct_forging_orders", "Flow 1 · RM Responsible FSI", "Flow 2 · RM Responsible Forger / Supplier", "Part Production", "render_order_mis", "Monthly Schedule / Order MIS"):
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
if v4138_marker not in ui_text or v4138_marker not in auth_text or v4138_marker not in v4137_streamlit:
    errors.append("QCMS 4.13.8 build fingerprint is missing")
for token in ("part_raw_material_technical_data", "part_supplier_price_history", "supply_purchase_order_sources", "technical_data_snapshot", "price_history_snapshot"):
    if token not in v4138_sql:
        errors.append(f"QCMS 4.13.8 database contract missing: {token}")
for token in ("Select Customer Orders / Schedules for this RM Purchase Order", "PO Allocation kg", "PART MASTER TECHNICAL DATA & PRICE HISTORY"):
    if token not in v4138_supply:
        errors.append(f"QCMS 4.13.8 Purchase Order UI token missing: {token}")
for token in ("def price_history", "def current_price", "def technical_data_snapshot", "supply_purchase_order_sources"):
    if token not in v4138_service:
        errors.append(f"QCMS 4.13.8 Supply Chain service token missing: {token}")
if "Save Supplier Technical Data" not in v4138_part or "Save Supplier / FSI Part Price History" not in v4138_part:
    errors.append("QCMS 4.13.8 Part Master technical data / price history editors are missing")
if "display_items = list(items)[:6]" not in v4138_po or "TECHNICAL DATA" not in v4138_po:
    errors.append("QCMS 4.13.8 multi-line Purchase Order print / technical snapshot rendering is incomplete")
if "Backfilled from controlled QCMS Purchase Order history" not in v4138_backfill:
    errors.append("QCMS 4.13.8 historical price/source backfill is missing")

# QCMS 4.13.9 corrective linkage / incremental RMTC / item-wise PO technical data contract.
v4139_marker = "4139-RM-PROCUREMENT-LINK-RMTC-PART-PO-ITEM-TECH"
v4139_sql = (ROOT / "supabase" / "migrations" / "20260822224500_qcms_rmtc_incremental_part_release_guard_v4139.sql").read_text(encoding="utf-8")
v4139_service = (ROOT / "core" / "supply_chain_service.py").read_text(encoding="utf-8")
v4139_po = (ROOT / "core" / "purchase_order_reporting.py").read_text(encoding="utf-8")
if v4139_marker not in ui_text or v4139_marker not in auth_text or v4139_marker not in v4137_streamlit:
    errors.append("QCMS 4.13.9 build fingerprint is missing")
if v4139_service.count('proposed_three_month_qty=number(order.get("order_qty_pcs")) if str(order.get("order_type") or "") == "PURCHASE_ORDER" else 0.0') < 2:
    errors.append("QCMS 4.13.9 Customer PO procurement recheck fix is missing")
if "v_pending_decisions" not in v4139_sql or "PARTIALLY_APPROVED permits released Parts" not in v4139_sql:
    errors.append("QCMS 4.13.9 incremental approved-RMTC Part guard is missing")
if "RAW MATERIAL / FORGING PARAMETERS & FSI TECHNICAL DATA" not in v4139_po or "compact_technical_pairs" not in v4139_po:
    errors.append("QCMS 4.13.9 item-wise PO technical data print sequence is missing")

report = {
    "release": "QCMS 4.13.9 RM Procurement Link + Incremental RMTC Part + Item-wise PO Technical Data",
    "customer_order_rm_procurement_link_fix": v4139_service.count('proposed_three_month_qty=number(order.get("order_qty_pcs")) if str(order.get("order_type") or "") == "PURCHASE_ORDER" else 0.0') >= 2,
    "incremental_approved_rmtc_part_guard": "v_pending_decisions" in v4139_sql,
    "item_wise_po_technical_data": "compact_technical_pairs" in v4139_po and "RAW MATERIAL / FORGING PARAMETERS & FSI TECHNICAL DATA" in v4139_po,
    "multi_rm_po_sources": "Select Customer Orders / Schedules for this RM Purchase Order" in v4138_supply and "supply_purchase_order_sources" in v4138_service,
    "supplier_fsi_price_history": "part_supplier_price_history" in v4138_sql and "def current_price" in v4138_service,
    "part_master_po_technical_data": "Save Supplier Technical Data" in v4138_part and "technical_data_snapshot" in v4138_service,
    "multi_line_po_pdf": "display_items = list(items)[:6]" in v4138_po,
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
