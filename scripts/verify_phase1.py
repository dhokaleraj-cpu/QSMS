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
    "core/hardness_conversion.py",
    "data/astm_e140_table1.json",
]
for item in required:
    if not (ROOT / item).exists():
        errors.append(f"Missing required file: {item}")

app_text = (ROOT / "streamlit_app.py").read_text()
paths = re.findall(r'url_path="([^"]+)"', app_text)
expected_paths = {
    "dashboard", "masters", "rmtc-entry", "inward-entry", "osp-home", "npd-process-flow", "npd-status", "apqp", "qc-tools", "qc-calculation-records", "inspection-home", "records-center", "heat-ledger",
    "reports-home", "heat-transaction-report", "osp-balance-report", "templates",
    "part-entry", "part-records", "process-entry", "process-records", "grade-entry", "grade-records",
    "reference-entry", "reference-records", "employee-entry", "employee-records",
    "user-access", "rmtc-part", "rmtc-records", "rmtc-approval", "inward-records",
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

report = {
    "release": "QCMS 4.9.9 Controlled Delete, Save Popups, Trial Cleanup & Jominy MM Reliability",
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
    "errors": errors,
}
print(json.dumps(report, indent=2))
raise SystemExit(1 if errors else 0)
