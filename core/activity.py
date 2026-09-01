from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from core.config import is_preview_session
from core.database import get_session_client

_TABLE_MODULES = {
    "parts": "PART_MASTER",
    "part_material_grade_links": "PART_MASTER",
    "part_raw_material_details": "PART_MASTER",
    "part_raw_material_technical_data": "PART_MASTER",
    "part_supplier_price_history": "PART_MASTER",
    "part_jominy_requirements": "PART_MASTER",
    "part_heat_treatment_details": "PART_MASTER",
    "part_rmtc_requirements": "PART_MASTER",
    "part_process_specifications": "PART_MASTER",
    "part_process_parameter_specifications": "PART_MASTER",
    "part_metallurgical_requirements": "PART_MASTER",
    "part_standard_links": "PART_MASTER",
    "material_grades": "MATERIAL_GRADE",
    "material_grade_elements": "MATERIAL_GRADE",
    "parties": "REFERENCE_MASTERS",
    "part_supplier_links": "REFERENCE_MASTERS",
    "processes": "REFERENCE_MASTERS",
    "inspection_stages": "REFERENCE_MASTERS",
    "quality_assets": "REFERENCE_MASTERS",
    "jominy_distances": "REFERENCE_MASTERS",
    "master_value_catalog": "REFERENCE_MASTERS",
    "customer_standards": "REFERENCE_MASTERS",
    "company_branches": "REFERENCE_MASTERS",
    "employees": "EMPLOYEE_MASTER",
    "rmtc_approvals": "RMTC_ENTRY",
    "rmtc_part_approvals": "RMTC_ENTRY",
    "rmtc_chemistry_results": "RMTC_ENTRY",
    "rmtc_jominy_results": "RMTC_ENTRY",
    "rmtc_requirement_results": "RMTC_ENTRY",
    "rmtc_decision_revisions": "RMTC_ENTRY",
    "inward_lots": "MATERIAL_INWARD",
    "production_batches": "OSP_TRANSACTIONS",
    "batch_movements": "OSP_TRANSACTIONS",
    "osp_jobs": "OSP_TRANSACTIONS",
    "osp_receipts": "OSP_TRANSACTIONS",
    "inspection_plans": "INSPECTION_LAYOUTS",
    "inspection_plan_characteristics": "INSPECTION_LAYOUTS",
    "test_plans": "INSPECTION_LAYOUTS",
    "inspection_reports": "DIMENSIONAL_REPORT",
    "inspection_results": "DIMENSIONAL_REPORT",
    "lab_tests": "METLAB_REPORT",
    "npd_process_flows": "NPD_APQP",
    "npd_process_flow_steps": "NPD_APQP",
    "npd_process_flow_points": "NPD_APQP",
    "npd_orders": "NPD_APQP",
    "npd_order_steps": "NPD_APQP",
    "npd_order_step_points": "NPD_APQP",
    "ppap_projects": "NPD_APQP",
    "qc_calculation_records": "QC_CALCULATION_TOOLS",
    "quality_complaints": "COMPLAINT_MANAGEMENT",
    "quality_complaint_followups": "COMPLAINT_MANAGEMENT",
    "quality_complaint_actions": "COMPLAINT_MANAGEMENT",
    "supply_customer_orders": "SUPPLY_CHAIN",
    "supply_purchase_orders": "SUPPLY_CHAIN",
    "supply_purchase_order_items": "SUPPLY_CHAIN",
    "supply_purchase_order_sources": "SUPPLY_CHAIN",
    "supply_po_confirmations": "SUPPLY_CHAIN",
    "supply_opening_stock": "SUPPLY_CHAIN",
    "supply_rm_purchase_orders": "SUPPLY_CHAIN",
    "supply_rm_receipts": "SUPPLY_CHAIN",
    "supply_forging_orders": "SUPPLY_CHAIN",
    "supply_rm_dispatches": "SUPPLY_CHAIN",
    "supply_forging_receipts": "SUPPLY_CHAIN",
    "supply_downstream_events": "SUPPLY_CHAIN",
    "user_module_permissions": "USER_ACCESS",
    "user_section_permissions": "USER_ACCESS",
    "department_module_defaults": "USER_ACCESS",
    "role_module_defaults": "USER_ACCESS",
    "qcms_module_approval_routes": "USER_ACCESS",
    "supply_stage_responsibilities": "USER_ACCESS",
}


def module_for_table(table: str | None) -> str | None:
    if not table:
        return None
    return _TABLE_MODULES.get(str(table).strip())


def log_activity(
    action: str,
    *,
    module_key: str | None = None,
    section_key: str | None = None,
    table_name: str | None = None,
    row_id: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> None:
    """Best-effort audit telemetry. Business transactions never fail because logging failed."""
    if is_preview_session() or not st.session_state.get("profile"):
        return
    if str(action or "").upper() == "ACTIVITY_LOG":
        return
    try:
        client = get_session_client()
        client.rpc(
            "qcms_log_user_activity",
            {
                "p_action": str(action or "").upper(),
                "p_module_key": module_key or module_for_table(table_name),
                "p_section_key": section_key,
                "p_table_name": table_name,
                "p_row_id": str(row_id or "") or None,
                "p_details": dict(details or {}),
            },
        ).execute()
    except Exception:
        # Audit logging is deliberately non-blocking; row-change database triggers
        # remain the authoritative mutation audit even if this optional activity
        # telemetry cannot be written during a transient connection problem.
        return


def log_route_view(route_key: str, module_key: str | None, title: str | None = None) -> None:
    route = str(route_key or "").strip()
    if not route:
        return
    st.session_state["_qcms_current_route"] = route
    st.session_state["_qcms_current_route_module"] = module_key
    previous = str(st.session_state.get("_qcms_last_logged_route") or "")
    if previous == route:
        return
    st.session_state["_qcms_last_logged_route"] = route
    # Reset section de-duplication when the user changes page.
    st.session_state["_qcms_logged_sections_for_route"] = []
    log_activity(
        "PAGE_VIEW",
        module_key=module_key,
        section_key=route.replace("-", "_").upper(),
        details={"page_title": str(title or "")},
    )


def log_section_view(section_key: str, title: str | None = None) -> None:
    """Record each rendered workflow section once per page visit.

    Streamlit reruns frequently, so this intentionally de-duplicates section telemetry
    until the user navigates to another route. Database row-change audit remains the
    authoritative history for record mutations.
    """
    key = str(section_key or "").strip().upper()
    if not key:
        return
    route = str(st.session_state.get("_qcms_current_route") or "")
    token = f"{route}:{key}"
    logged = list(st.session_state.get("_qcms_logged_sections_for_route") or [])
    if token in logged:
        return
    logged.append(token)
    st.session_state["_qcms_logged_sections_for_route"] = logged[-200:]
    log_activity(
        "SECTION_VIEW",
        module_key=st.session_state.get("_qcms_current_route_module"),
        section_key=key,
        details={"section_title": str(title or ""), "route": route},
    )
