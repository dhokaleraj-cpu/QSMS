from __future__ import annotations
# Legacy controlled PDF label retained for regression traceability: Download MetLAB Report PDF

import re
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st
from core.ui import portal_table
from core.selection_labels import part_label

from core.access import current_permissions
from core.delete_service import password_delete_panel
from core.notification_service import NotificationService
from core.inspection_service import FINAL_DISPOSITIONS, RESULT_OPTIONS, InspectionService
from core.reporting import metlab_record_pdf_bytes, quality_record_excel_bytes
from core.selection_labels import employee_label, party_label
from core.ui import disposition_cards, disposition_label, page_header, save_success_popup, section_bar, stage_section, style_status_dataframe, subpage_navigation, template_download_row


def _maps(service: InspectionService):
    parts = {str(row["id"]): row for row in service.parts()}
    parties = {str(row["id"]): row for row in service.parties()}
    processes = {str(row["id"]): row for row in service.processes()}
    stages = {str(row["id"]): row for row in service.stages()}
    employees = {str(row["id"]): employee_label(row) for row in service.employees()}
    return parts, parties, processes, stages, employees


def _report_exports(service: InspectionService, report_id: str, report_number: str, *, key: str) -> None:
    try:
        payload = service.metlab_report_payload(report_id)
        pdf_bytes = metlab_record_pdf_bytes(payload)
        excel_bytes = quality_record_excel_bytes(payload, "METLAB")
        c1, c2 = st.columns(2, gap="small")
        c1.download_button(
            "Download / Print PDF", data=pdf_bytes,
            file_name=f"{report_number or 'MetLAB_Report'}.pdf", mime="application/pdf",
            icon=":material/picture_as_pdf:", key=f"{key}_pdf", width="stretch",
        )
        c2.download_button(
            "Download Excel Report", data=excel_bytes,
            file_name=f"{report_number or 'MetLAB_Report'}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:", key=f"{key}_xlsx", width="stretch",
        )
    except Exception as exc:
        st.error(f"Report export could not be generated: {exc}")


def _inward_label(row: dict, parts: dict[str, dict], parties: dict[str, dict]) -> str:
    part = parts.get(str(row.get("part_id"))) or {}
    supplier = parties.get(str(row.get("supplier_id"))) or {}
    return (
        f"{row.get('inward_number')} · {part.get('part_number')} · {party_label(supplier)} · "
        f"Heat {row.get('heat_number')} · Steel {float(row.get('steel_quantity_kg') or row.get('quantity_received') or 0):,.3f} kg · "
        f"Production {float(row.get('production_quantity_pcs') or 0):,.0f} pcs"
    )


def _pending_frame(rows: list[dict], parts: dict[str, dict], parties: dict[str, dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Inward": row.get("inward_number"),
        "Date": row.get("inward_date"),
        "Supplier": (parties.get(str(row.get("supplier_id"))) or {}).get("party_name"),
        "Part Number": (parts.get(str(row.get("part_id"))) or {}).get("part_number"),
        "FSI Part Number": (parts.get(str(row.get("part_id"))) or {}).get("fsi_part_number"),
        "Heat Number": row.get("heat_number"),
        "Steel kg": row.get("steel_quantity_kg") or row.get("quantity_received"),
        "Production pcs": row.get("production_quantity_pcs"),
        "Status": row.get("metlab_queue_status"),
    } for row in rows])


def _existing_rows(existing: dict | None, key: str) -> list[dict]:
    payload = (existing or {}).get("results") or {}
    if isinstance(payload, dict):
        return [dict(row) for row in payload.get(key) or []]
    return []


def _existing_conclusion(existing: dict | None) -> str:
    results = dict((existing or {}).get("results") or {})
    value = str(results.get("conclusion") or "").strip().upper().replace(" ", "_")
    options = {"PENDING", *FINAL_DISPOSITIONS}
    if value in options:
        return value
    if str((existing or {}).get("status") or "").upper() == "FINAL":
        disposition = str((existing or {}).get("disposition") or "").strip().upper().replace(" ", "_")
        if disposition in FINAL_DISPOSITIONS:
            return disposition
    return "PENDING"


def _report_picker(service: InspectionService, *, current_id: str) -> str:
    """Open an existing MetLAB report directly from the New / Edit page."""
    labels = {
        str(row.get("id")): f"{row.get('report_number') or '-'} · {row.get('test_date') or '-'} · Heat {row.get('heat_number') or '-'} · {disposition_label(row.get('disposition'))}"
        for row in service.metlab_reports() if row.get("id")
    }
    options = [""] + list(labels)
    selected = st.selectbox(
        "Select Existing MetLAB Report to Edit", options,
        index=options.index(current_id) if current_id in options else 0,
        format_func=lambda value: labels.get(value, "— New MetLAB Report —"),
        key="metlab_direct_report_picker",
    )
    if selected != current_id:
        if selected:
            st.session_state["edit_metlab_id"] = selected
        else:
            st.session_state.pop("edit_metlab_id", None)
        st.rerun()
    if current_id and st.button("Start New MetLAB Report", key="metlab_start_new", width="stretch"):
        st.session_state.pop("edit_metlab_id", None)
        st.rerun()
    return selected


def _number(value: Any) -> float | None:
    try:
        if value in (None, "") or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _band_result(value: Any, minimum: Any, maximum: Any, na: bool = False) -> str:
    if na:
        return "NOT_APPLICABLE"
    actual = _number(value)
    if actual is None:
        return "NOT_EVALUATED"
    low = _number(minimum); high = _number(maximum)
    if low is not None and actual < low:
        return "FAIL"
    if high is not None and actual > high:
        return "FAIL"
    return "PASS"


def _range_from_text(value: Any) -> tuple[float | None, float | None]:
    nums = [float(item) for item in re.findall(r"-?\d+(?:\.\d+)?", str(value or ""))]
    if len(nums) >= 2:
        return min(nums[0], nums[1]), max(nums[0], nums[1])
    if len(nums) == 1:
        return nums[0], nums[0]
    return None, None


def _layout_rows(service: InspectionService, plan_id: str | None, existing: dict | None) -> list[dict]:
    saved = _existing_rows(existing, "rows")
    if saved:
        return saved
    if not plan_id:
        return []
    return [{
        "sequence_no": row.get("sequence_no") or position,
        "inspection_plan_characteristic_id": row.get("id"),
        "parameter": row.get("characteristic"), "specification": row.get("specification"),
        "lower_spec": row.get("lower_spec"), "upper_spec": row.get("upper_spec"), "unit": row.get("unit"),
        "checking_method": row.get("checking_aid_text") or row.get("checking_method"), "actual_value": "",
        "result": "NOT_EVALUATED", "remarks": "", "applicability": "APPLICABLE",
        "characteristic_type": row.get("characteristic_type") or "VARIABLE",
    } for position, row in enumerate(service.plan_characteristics(plan_id), start=1)]


def _controlled_amendment_state(existing: dict | None, perms: dict, *, key_prefix: str) -> tuple[bool, bool]:
    """Return (writable, amendment_enabled) for normal drafts or controlled FINAL amendments."""
    is_final = str((existing or {}).get("status") or "DRAFT").upper() == "FINAL"
    amendment_key = f"{key_prefix}_amend_{(existing or {}).get('id') or 'new'}"
    amendment_enabled = bool(st.session_state.get(amendment_key, False))
    if is_final:
        st.warning("This report is FINAL. Variable inputs are locked until a controlled amendment is enabled. Saving an amendment returns the report to DRAFT and requires fresh validation / approval.")
        if perms.get("can_edit") and perms.get("can_approve"):
            if st.button("Enable Controlled Amendment", key=f"{amendment_key}_button", width="stretch"):
                st.session_state[amendment_key] = True
                amendment_enabled = True
                st.rerun()
        else:
            st.info("Controlled amendment requires both Edit and Approve permission for this report module.")
    writable = bool(perms.get("can_edit") if existing else perms.get("can_create")) and (not is_final or amendment_enabled)
    return writable, amendment_enabled


def _login_approval_employee(service: InspectionService) -> tuple[str, str]:
    employee = service.employee_for_profile(st.session_state.get("profile") or {})
    employee_id = str(employee.get("id") or "")
    return employee_id, employee_label(employee) if employee_id else "No Employee Master mapping for current login"


def _case_depth_editor(existing: dict | None, *, key: str, disabled: bool = False) -> dict[str, Any]:
    """Edit a multi-location Case Depth / Microhardness Traverse.

    QCMS v4.14.1 fixes the controlled distance pattern to 0.05 mm first, followed by
    0.10, 0.20, 0.30 ... mm. The location columns remain dynamic so one report can
    contain Ground Face / ID / OD or any other controlled measurement locations.
    """
    saved_results = dict((existing or {}).get("results") or {})
    saved = dict(saved_results.get("case_depth_traverse") or {})
    saved_locations = [str(value).strip() for value in (saved.get("locations") or []) if str(value).strip()]
    default_locations = saved_locations or ["Ground Face", "ID", "OD"]
    saved_rows = [dict(row) for row in (saved.get("rows") or []) if isinstance(row, dict)]
    existing_max = max([_number(row.get("distance_mm")) or 0.0 for row in saved_rows] or [1.0])

    c1, c2 = st.columns([3, 1], gap="small")
    location_text = c1.text_input(
        "Traverse Locations",
        value=", ".join(default_locations),
        help="Comma-separated locations, e.g. Ground Face, ID, OD. Up to 8 locations.",
        disabled=disabled, key=f"{key}_locations",
    )
    max_distance = c2.number_input(
        "Maximum Distance (mm)", min_value=0.10, max_value=5.00,
        value=float(max(round(existing_max, 2), 0.10)), step=0.10, format="%.2f",
        disabled=disabled, key=f"{key}_max_distance",
    )
    locations: list[str] = []
    for raw in location_text.split(","):
        name = raw.strip()
        if name and name not in locations:
            locations.append(name)
    locations = locations[:8]
    if not locations:
        locations = ["Ground Face"]

    distance_map = {round(float(row.get("distance_mm") or 0), 4): row for row in saved_rows}
    distances = [0.05]
    distances.extend(round(index / 10.0, 2) for index in range(1, int(round(float(max_distance) * 10)) + 1))
    frame_rows: list[dict[str, Any]] = []
    for distance in distances:
        existing_row = distance_map.get(round(distance, 4), {})
        row: dict[str, Any] = {"Distance (mm)": distance}
        for location in locations:
            row[location] = _number(existing_row.get(location))
        frame_rows.append(row)
    frame = pd.DataFrame(frame_rows)
    column_config: dict[str, Any] = {"Distance (mm)": st.column_config.NumberColumn(format="%.2f")}
    for location in locations:
        column_config[location] = st.column_config.NumberColumn(format="%.1f", help="Hardness reading (HV / HV1 as applicable).")
    edited = st.data_editor(
        frame, hide_index=True, width="stretch", height=min(560, max(250, 95 + len(frame) * 30)),
        disabled=True if disabled else ["Distance (mm)"], column_config=column_config, key=f"{key}_grid",
    )
    chart = edited.set_index("Distance (mm)")[locations].apply(pd.to_numeric, errors="coerce")
    if chart.notna().any().any():
        st.caption("Case Depth Traverse preview · Distance (mm) vs Hardness")
        st.line_chart(chart, height=260)

    output_rows: list[dict[str, Any]] = []
    for _, row in edited.iterrows():
        item: dict[str, Any] = {"distance_mm": float(row.get("Distance (mm)"))}
        for location in locations:
            item[location] = _number(row.get(location))
        output_rows.append(item)
    return {"distance_unit": "mm", "hardness_unit": "HV1", "locations": locations, "rows": output_rows}


def _metlab_validation_preview(rows: list[dict], *, key: str) -> None:
    if not rows:
        return
    preview = pd.DataFrame([{
        "Sr No": index,
        "Parameter": row.get("parameter") or row.get("requirement_name") or row.get("element") or row.get("distance_label"),
        "Specification": row.get("specification") or row.get("requirement_value") or (
            f"{row.get('minimum_value') or row.get('minimum_hrc') or ''} - {row.get('maximum_value') or row.get('maximum_hrc') or ''}".strip(" -")
        ),
        "Actual / Observation": row.get("actual_value"),
        "Result": row.get("result"),
        "Remark": row.get("remarks"),
    } for index, row in enumerate(rows, start=1)])
    st.caption("Validation Preview · Out-of-spec observations are highlighted automatically.")
    portal_table(preview, hide_index=True, width="stretch", height=min(380, 84 + 36 * len(preview)))



STANDALONE_STAGES = {
    "RAW_MATERIAL_STAGE": "Raw Material Stage",
    "OSP_STAGE": "OSP Stage",
    "FINAL_DISPATCH_STAGE": "Final Dispatch Stage",
}


def _render_standalone_metlab(service: InspectionService, perms: dict, parts: dict[str, dict], parties: dict[str, dict], processes: dict[str, dict], stages: dict[str, dict], employee_map: dict[str, str], existing: dict | None) -> None:
    existing_id = str((existing or {}).get("id") or "")
    writable, amendment_enabled = _controlled_amendment_state(existing, perms, key_prefix="metlab_standalone")
    login_approver_id, login_approver_label = _login_approval_employee(service)

    with stage_section("A", "STANDALONE METLAB CONTEXT", "Master-driven Part / Customer / Material / OSP context. No RMTC or inward transaction linkage is required.", key="metlab_standalone_context"):
        scope_keys = list(STANDALONE_STAGES)
        current_scope = str((existing or {}).get("inspection_scope") or "RAW_MATERIAL_STAGE")
        scope = st.selectbox("Report Stage", scope_keys, index=scope_keys.index(current_scope) if current_scope in scope_keys else 0, format_func=lambda v: STANDALONE_STAGES[v], disabled=bool(existing))

        part_map = {pid: part_label(row) for pid, row in parts.items()}
        if not part_map:
            st.warning("No active Parts are available.")
            return
        current_part = str((existing or {}).get("part_id") or next(iter(part_map)))
        part_id = st.selectbox("Part Number", list(part_map), index=list(part_map).index(current_part) if current_part in part_map else 0, format_func=lambda v: part_map[v], disabled=bool(existing))
        context = service.standalone_part_context(part_id)
        part = context.get("part") or parts.get(part_id) or {}
        customer = context.get("customer") or {}
        grade = context.get("material_grade") or {}

        process_group = None
        process_id = None
        if scope == "OSP_STAGE":
            groups = service.standalone_osp_process_groups(part_id, "METLAB")
            if not groups:
                st.warning("No active OSP MetLAB Process requirements are configured in Part Master for this Part Number.")
                return
            group_map = {str(row["id"]): f"{(processes.get(str(row.get('process_id'))) or {}).get('process_code') or '-'} · {(processes.get(str(row.get('process_id'))) or {}).get('process_name') or '-'}" for row in groups}
            existing_process = str((existing or {}).get("process_id") or "")
            default_group = next((str(row["id"]) for row in groups if str(row.get("process_id")) == existing_process), next(iter(group_map)))
            group_id = st.selectbox("OSP Process", list(group_map), index=list(group_map).index(default_group), format_func=lambda value: group_map[value], disabled=bool(existing))
            process_group = next(row for row in groups if str(row["id"]) == group_id)
            process_id = str(process_group.get("process_id") or "") or None

        plan = service.auto_standalone_plan("METLAB", part_id, scope, process_id)
        if not plan:
            if scope == "OSP_STAGE":
                st.warning("The Part Master OSP MetLAB requirements exist, but the controlled OSP MetLAB layout has not been generated/approved. Use Part Master → OSP Inspection for MetLAB → Create / Update OSP MetLAB Inspection Layout.")
            elif scope == "FINAL_DISPATCH_STAGE":
                st.warning("No approved Final Metallurgical layout is available for this Part. Generate it from Part Master → Metallurgical Requirements.")
            else:
                st.warning("No approved MetLAB layout is configured for this Part Number.")
            return
        plan_id = str(plan["id"])
        if not process_id:
            process_id = str(plan.get("process_id") or "") or None
        process = processes.get(str(process_id or "")) or {}

        supplier_ids = [pid for pid in list(context.get("supplier_ids") or []) if pid in parties and "SUPPLIER" in (parties[pid].get("party_types") or [])]
        if not supplier_ids:
            supplier_ids = [pid for pid, row in parties.items() if "SUPPLIER" in (row.get("party_types") or [])]
        osp_vendor_ids = [pid for pid, row in parties.items() if "OSP_VENDOR" in (row.get("party_types") or [])]
        supplier_options = [""] + supplier_ids
        osp_vendor_options = [""] + osp_vendor_ids
        current_supplier = str((existing or {}).get("supplier_id") or "")
        current_osp_vendor = str((existing or {}).get("osp_vendor_id") or "")
        vc1, vc2 = st.columns(2, gap="small")
        supplier_id = vc1.selectbox("Supplier", supplier_options, index=supplier_options.index(current_supplier) if current_supplier in supplier_options else 0, format_func=lambda v: party_label(parties.get(v) or {}) if v else "— Select Supplier from Master —", disabled=not writable)
        osp_vendor_id = vc2.selectbox("OSP Vendor", osp_vendor_options, index=osp_vendor_options.index(current_osp_vendor) if current_osp_vendor in osp_vendor_options else 0, format_func=lambda v: party_label(parties.get(v) or {}) if v else "— Select OSP Vendor from Master —", disabled=not writable)

        c1, c2, c3, c4 = st.columns(4, gap="small")
        c1.text_input("Part Name", value=str(part.get("part_name") or ""), disabled=True)
        c2.text_input("Customer", value=str(customer.get("party_name") or ""), disabled=True)
        c3.text_input("Material Grade", value=str(grade.get("grade_code") or grade.get("grade_name") or ""), disabled=True)
        c4.text_input("Drawing / Revision", value=f"{part.get('drawing_number') or '-'} / {part.get('drawing_revision') or '-'}", disabled=True)
        if scope == "OSP_STAGE":
            c1, c2, c3, c4 = st.columns(4, gap="small")
            c1.text_input("OSP Process", value=str(process.get("process_name") or ""), disabled=True)
            c2.text_input("Process Specification", value=str((process_group or {}).get("process_specification") or ""), disabled=True)
            c3.text_input("Process Drawing", value=str((process_group or {}).get("drawing_number") or ""), disabled=True)
            c4.text_input("Process Drawing Rev", value=str((process_group or {}).get("drawing_revision") or ""), disabled=True)
        st.info(f"Auto Layout from Part Master: {plan.get('layout_name') or plan.get('plan_number')} · Rev {plan.get('revision') or '-'}")

        c1, c2, c3, c4 = st.columns(4, gap="small")
        report_no = c1.text_input("Report Number", value=str((existing or {}).get("report_number") or ""), placeholder="Generated automatically on first save · YY year", disabled=True)
        test_date = c2.date_input("Test Date", value=date.fromisoformat(str((existing or {}).get("test_date"))[:10]) if (existing or {}).get("test_date") else date.today(), format="DD-MM-YYYY", disabled=not writable)
        heat = c3.text_input("Heat Number", value=str((existing or {}).get("heat_number") or ""), disabled=not writable)
        heat_code = c4.text_input("Heat Code", value=str((existing or {}).get("heat_code") or ""), disabled=not writable)
        c1, c2, c3, c4 = st.columns(4, gap="small")
        vendor_batch_number = c1.text_input("Supplier / HT / OSP Batch Number", value=str((existing or {}).get("vendor_batch_number_snapshot") or ""), disabled=not writable)
        batch_number = c2.text_input("Internal / FSI Batch Number", value=str((existing or {}).get("batch_number") or ""), disabled=not writable)
        supplier_reference = c3.text_input("Supplier Invoice / Reference", value=str((existing or {}).get("supplier_reference_number") or ""), disabled=not writable)
        c1, c2, c3, c4 = st.columns(4, gap="small")
        quantity_pcs = c1.number_input("Quantity (pcs)", min_value=0.0, value=float((existing or {}).get("production_quantity_pcs") or 0), step=1.0, disabled=not writable)
        sample_ref = c2.text_input("Sample / Reference", value=str((existing or {}).get("sample_reference") or ""), disabled=not writable)
        default_condition = (process_group or {}).get("process_specification") or process.get("process_name") or STANDALONE_STAGES[scope]
        supply_condition = st.text_input("Supply / Process Condition", value=str((existing or {}).get("supply_condition") or default_condition or ""), disabled=not writable)
        spec_ref = st.text_input("Specification Reference", value=str((existing or {}).get("specification_reference") or plan.get("format_number") or part.get("drawing_number") or ""), disabled=not writable)

    with stage_section("B", "METLAB CHARACTERISTICS", "The inspection grid is loaded automatically from the approved Part Master controlled layout.", key="metlab_standalone_characteristics"):
        layout_source = _layout_rows(service, plan_id, existing)
        frame = pd.DataFrame([{"Sr No": r.get("sequence_no"), "Parameter": r.get("parameter"), "Specification": r.get("specification"), "Min": r.get("lower_spec"), "Max": r.get("upper_spec"), "Method / Aid": r.get("checking_method"), "Actual Value": r.get("actual_value"), "Unit": r.get("unit"), "NA": r.get("applicability") == "NOT_APPLICABLE", "Result": r.get("result"), "Remark": r.get("remarks"), "_characteristic_id": r.get("inspection_plan_characteristic_id"), "_type": r.get("characteristic_type")} for r in layout_source])
        locked_columns = ["Sr No", "Parameter", "Specification", "Min", "Max", "Method / Aid", "Result", "_characteristic_id", "_type"]
        edited = st.data_editor(frame, hide_index=True, width="stretch", height=min(620, max(220, 80 + len(frame) * 30)), disabled=True if not writable else locked_columns, column_config={"NA": st.column_config.CheckboxColumn(), "_characteristic_id": None, "_type": None}, key=f"standalone_metlab_grid_{existing_id or 'new'}_{plan_id}")
        employee_options = [""] + list(employee_map)
        c1, c2, c3 = st.columns(3, gap="small")
        current_prepared = str((existing or {}).get("prepared_by_employee_id") or "")
        prepared = c1.selectbox("Prepared By", employee_options, index=employee_options.index(current_prepared) if current_prepared in employee_options else 0, format_func=lambda v: employee_map.get(v, "— Select —"), disabled=not writable)
        conclusion_options = ["PENDING", *FINAL_DISPOSITIONS]
        current_conclusion = "PENDING" if amendment_enabled else _existing_conclusion(existing)
        conclusion = c2.selectbox("Conclusion", conclusion_options, index=conclusion_options.index(current_conclusion), format_func=disposition_label, disabled=not writable, help="Controlled MetLAB conclusion: Pending, On Hold, Accepted, Accepted Under Reserve or Rejected.")
        conclusion_remarks = c3.text_input("Conclusion Remark", value=str((existing or {}).get("remarks") or ""), help="Required when Conclusion is On Hold, Accepted Under Reserve or Rejected.", disabled=not writable)
        c1, c2 = st.columns(2, gap="small")
        disposition_options = ["PENDING", *FINAL_DISPOSITIONS]
        current_decision = "PENDING" if amendment_enabled else str((existing or {}).get("disposition") or "PENDING")
        disposition = c1.selectbox("Final Decision", disposition_options, index=disposition_options.index(current_decision) if current_decision in disposition_options else 0, format_func=disposition_label, disabled=not writable)
        reason_default = "" if amendment_enabled else str((existing or {}).get("disposition_reason") or "")
        reason = c2.text_input("Decision Reason", value=reason_default, help="Required for On Hold, Accepted Under Reserve and Rejected decisions.", disabled=not writable)
        attachment = st.file_uploader("Attach MetLAB Report", type=["pdf", "xlsx", "xls", "png", "jpg", "jpeg"], key=f"standalone_metlab_attachment_{existing_id or 'new'}", disabled=not writable)
        layout_rows = []
        for _, row in edited.iterrows():
            na = bool(row.get("NA"))
            result = service.evaluate_characteristic({"characteristic_type": row.get("_type"), "specification": row.get("Specification"), "lower_spec": row.get("Min"), "upper_spec": row.get("Max")}, [row.get("Actual Value")], na)
            layout_rows.append({"sequence_no": int(row.get("Sr No") or len(layout_rows) + 1), "inspection_plan_characteristic_id": row.get("_characteristic_id"), "parameter": row.get("Parameter"), "specification": row.get("Specification"), "lower_spec": row.get("Min"), "upper_spec": row.get("Max"), "checking_method": row.get("Method / Aid"), "actual_value": row.get("Actual Value"), "unit": row.get("Unit"), "applicability": "NOT_APPLICABLE" if na else "APPLICABLE", "result": result, "remarks": row.get("Remark"), "characteristic_type": row.get("_type")})
        _metlab_validation_preview(layout_rows, key=f"standalone_metlab_preview_{existing_id or 'new'}")

    with stage_section("C", "CASE DEPTH / MICROHARDNESS TRAVERSE", "Distance starts at 0.05 mm, then 0.10, 0.20, 0.30 mm and continues in 0.10 mm increments. Add multiple measurement locations as required.", key="metlab_standalone_case_depth"):
        case_depth_traverse = _case_depth_editor(existing, key=f"standalone_metlab_case_depth_{existing_id or 'new'}", disabled=not writable)

    with stage_section("D", "MICROSTRUCTURE PHOTOS", "Up to four report photographs with controlled titles.", key="metlab_standalone_photos"):
        micro_cols = st.columns(4, gap="small")
        micro_files = []
        micro_captions = []
        for slot, col in enumerate(micro_cols, start=1):
            with col:
                if (existing or {}).get(f"microstructure_image_{slot}_path"):
                    st.caption(f"Photo {slot} already uploaded")
                micro_files.append(st.file_uploader(f"Photo {slot}", type=["png", "jpg", "jpeg"], key=f"standalone_metlab_photo_{slot}_{existing_id or 'new'}", disabled=not writable))
                micro_captions.append(st.text_input(f"Photo {slot} Title", value=str((existing or {}).get(f"microstructure_caption_{slot}") or ""), key=f"standalone_metlab_caption_{slot}_{existing_id or 'new'}", disabled=not writable))

    if st.button("Save Standalone MetLAB Report", type="primary", width="stretch", disabled=not writable or not prepared or not sample_ref.strip()):
        try:
            final_number = str((existing or {}).get("report_number") or "").strip() or service.next_number("METLAB")
            payload = {
                "report_number": final_number, "test_type": "METLAB", "layout_plan_id": plan_id,
                "process_id": process_id, "inspection_stage_id": plan.get("inspection_stage_id"), "part_id": part_id,
                "inward_lot_id": None, "osp_job_id": None, "batch_id": None, "rmtc_approval_id": None,
                "supplier_id": supplier_id or None, "osp_vendor_id": osp_vendor_id or None, "customer_id": part.get("customer_id"), "material_grade_id": part.get("material_grade_id"),
                "test_date": test_date.isoformat(), "sample_reference": sample_ref.strip(), "reference_text": sample_ref.strip(),
                "specification_reference": spec_ref.strip() or None, "overall_result": "NOT_EVALUATED",
                "status": "DRAFT" if amendment_enabled else str((existing or {}).get("status") or "DRAFT"), "remarks": conclusion_remarks.strip() or None,
                "disposition": disposition, "disposition_reason": reason.strip() or None, "heat_number": heat.strip() or None,
                "heat_code": heat_code.strip() or None, "batch_number": batch_number.strip() or None,
                "supplier_reference_number": supplier_reference.strip() or None, "supply_condition": supply_condition.strip() or None,
                "prepared_by_employee_id": prepared, "layout_name_snapshot": plan.get("layout_name"),
                "layout_type_name": STANDALONE_STAGES[scope], "steel_quantity_kg": None,
                "production_quantity_pcs": quantity_pcs or None, "inspection_scope": scope,
                "process_specification_snapshot": (process_group or {}).get("process_specification") or plan.get("remarks"),
                "vendor_batch_number_snapshot": vendor_batch_number.strip() or None,
                **{f"microstructure_caption_{slot}": micro_captions[slot - 1].strip() or None for slot in range(1, 5)},
            }
            if amendment_enabled:
                payload.update({"disposition": "PENDING", "disposition_reason": None, "overall_result": "NOT_EVALUATED", "validated_by_employee_id": None, "approved_by_employee_id": None, "validated_at": None, "decision_at": None})
            saved = service.save_metlab(payload, {"rows": layout_rows, "case_depth_traverse": case_depth_traverse, "conclusion": conclusion}, existing_id or None)
            if not existing_id or amendment_enabled:
                NotificationService(service.repo).notify(
                    "METLAB_APPROVAL_PENDING",
                    subject=f"QCMS · MetLAB approval pending · {saved.get('report_number') or final_number}",
                    body_text=(f"MetLAB Report {saved.get('report_number') or final_number} is ready for validation / approval.\n"
                               f"Part: {(parts.get(str(saved.get('part_id'))) or {}).get('part_number') or '-'}\n"
                               f"Test Date: {saved.get('test_date') or test_date}"),
                    related_table="lab_tests", related_id=str(saved.get("id")),
                    context={"lab_test_id": str(saved.get("id")), "next_task": "MetLAB Approval"},
                )
            if attachment is not None:
                service.upload_attachment("METLAB_REPORT", str(saved["id"]), "REPORT_COPY", attachment, "lab_tests", "attachment_path")
            for slot, image in enumerate(micro_files, start=1):
                if image is not None:
                    service.upload_attachment("METLAB_REPORT", str(saved["id"]), f"MICROSTRUCTURE_{slot}", image, "lab_tests", f"microstructure_image_{slot}_path")
            st.session_state["edit_metlab_id"] = str(saved["id"])
            if amendment_enabled:
                st.session_state.pop(f"metlab_standalone_amend_{existing_id}", None)
            save_success_popup(f"Standalone MetLAB Report {final_number} saved successfully.", queue_for_rerun=True)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    if existing:
        disposition_cards([
            {"label": "Report", "value": existing.get("status"), "foot": existing.get("report_number")},
            {"label": "Final Decision", "value": existing.get("disposition")},
            {"label": "Conclusion", "value": _existing_conclusion(existing), "foot": existing.get("remarks") or ""},
        ])
        employee_options = [""] + list(employee_map)
        c1, c2, c3 = st.columns(3, gap="small")
        current_validator = str(existing.get("validated_by_employee_id") or "")
        validator = c1.selectbox("Validated By", employee_options, index=employee_options.index(current_validator) if current_validator in employee_options else 0, format_func=lambda value: employee_map.get(value, "— Select —"), key=f"met_standalone_validator_{existing_id}")
        c2.text_input("Approved By (Current Login)", value=login_approver_label, disabled=True, key=f"met_standalone_approver_{existing_id}")
        finalize_disabled = not perms.get("can_approve") or disposition == "PENDING" or not validator or not login_approver_id or str(existing.get("status") or "").upper() == "FINAL"
        if not login_approver_id:
            st.info("The current login is not mapped to an active Employee Master row. Approval is blocked until the user/employee mapping is completed.")
        if c3.button("Finalize MetLAB Decision", disabled=finalize_disabled, width="stretch", key=f"met_standalone_finalize_{existing_id}"):
            try:
                service.finalize_metlab(existing_id, disposition, reason, validator, login_approver_id)
                save_success_popup("Standalone MetLAB conclusion and final decision completed successfully.", queue_for_rerun=True)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        section_bar("PDF / EXCEL / PRINT EXPORT")
        _report_exports(service, existing_id, str(existing.get("report_number") or "MetLAB_Report"), key=f"met_standalone_export_{existing_id}")


def render_entry() -> None:
    subpage_navigation(("inspection-home", "Inspections", ":material/biotech:"), ("inward-records", "Material Inward", ":material/input:"), ("metlab-records", "MetLAB Records", ":material/table_view:"))
    page_header("MetLAB Inspection Report", context="Linked or standalone Raw Material / OSP / Final Dispatch stage")
    template_download_row([("MetLAB_Report_Layout_Template.xlsx", "Download MetLAB Report Template")], key_prefix="metlab_report")
    service = InspectionService()
    perms = current_permissions("METLAB_REPORT")
    parts, parties, processes, stages, employee_map = _maps(service)
    existing_id = str(st.session_state.get("edit_metlab_id") or "")
    _report_picker(service, current_id=existing_id)
    existing_id = str(st.session_state.get("edit_metlab_id") or "")
    existing_record = service.get_metlab(existing_id) if existing_id else None
    standalone_existing = str((existing_record or {}).get("inspection_scope") or "") in STANDALONE_STAGES
    report_mode = st.radio("Report Linkage", ["QCMS Linked Flow", "Standalone Stage Report"], index=1 if standalone_existing else 0, horizontal=True, disabled=bool(existing_record), help="Standalone Stage Report does not require RMTC, Material Inward or Production linkage.")
    if report_mode == "Standalone Stage Report":
        _render_standalone_metlab(service, perms, parts, parties, processes, stages, employee_map, existing_record)
        return

    existing = existing_record
    writable, amendment_enabled = _controlled_amendment_state(existing, perms, key_prefix="metlab_linked")
    login_approver_id, login_approver_label = _login_approval_employee(service)
    pending_queue = [row for row in service.inspection_queue() if row.get("metlab_pending")]

    with stage_section("A", "METLAB PENDING LIST / REPORT CONTEXT", "Select the accepted Material Inward record. Existing reports retain their controlled inward, part and layout identity while variable report inputs remain editable.", key="metlab_report_render_entry_a"):
        if pending_queue:
            portal_table(style_status_dataframe(_pending_frame(pending_queue, parts, parties)), hide_index=True, width="stretch", height=min(300, 84 + 38 * len(pending_queue)))
        else:
            st.success("No MetLAB inspections are pending.")
        inward_rows = service.inward_lots()
        if not inward_rows:
            st.warning("No Accepted or Accepted Under Reserve Material Inward is available.")
            return

        inward_map = {str(row["id"]): _inward_label(row, parts, parties) for row in inward_rows}
        current_inward = str((existing or {}).get("inward_lot_id") or st.session_state.get("inspection_inward_id") or next(iter(inward_map)))
        inward_id = st.selectbox("Material Inward / Part / Supplier / Quantity", list(inward_map), index=list(inward_map).index(current_inward) if current_inward in inward_map else 0, format_func=lambda value: inward_map[value], disabled=bool(existing))
        inward = next(row for row in inward_rows if str(row["id"]) == inward_id)
        part_id = str(inward.get("part_id"))
        part = parts.get(part_id) or {}
        snapshot = service.rmtc_material_snapshot(inward)
        rmtc = snapshot.get("rmtc") or {}
        grade = snapshot.get("grade") or {}
        supplier = snapshot.get("supplier") or {}
        steel_mill = snapshot.get("steel_mill") or {}

        all_plans = service.plans("METLAB", part_id, approved_only=True)
        plan_id: str | None = None
        plan: dict = {}
        if all_plans:
            plan_map = {str(row["id"]): f"{row.get('layout_name')} · {row.get('plan_number')} Rev {row.get('revision')}" for row in all_plans}
            recommended = service.ranked_plans("METLAB", part_id)[0]
            selection_mode = st.radio("Layout Selection", ["Automatic", "Manual"], horizontal=True, disabled=bool(existing))
            if existing:
                plan_id = str(existing.get("layout_plan_id") or recommended.get("id"))
            elif selection_mode == "Automatic":
                plan_id = str(recommended["id"])
                st.info(f"Automatically selected: {plan_map[plan_id]}")
            else:
                plan_id = st.selectbox("Approved MetLAB Layout", list(plan_map), format_func=lambda value: plan_map[value])
            if selection_mode == "Automatic" or existing:
                st.selectbox("Approved MetLAB Layout", [plan_id], format_func=lambda value: plan_map.get(value, value), disabled=True)
            plan = next(row for row in all_plans if str(row["id"]) == plan_id)
        else:
            st.info("No approved MetLAB layout exists. The RMTC Raw Material layout is generated automatically from the Part Worksheet.")

        layout_name = str(plan.get("layout_name") or "RMTC Raw Material Inspection")
        layout_type = str(plan.get("layout_type") or "METLAB")
        c1, c2, c3, c4 = st.columns(4, gap="small")
        c1.text_input("Layout Name", value=layout_name, disabled=True)
        c2.text_input("Section / Layout Type", value=layout_type, disabled=True)
        c3.text_input("Process", value=str((processes.get(str(plan.get("process_id"))) or {}).get("process_name") or "Raw Material Inward"), disabled=True)
        c4.text_input("Inspection Stage", value=str((stages.get(str(plan.get("inspection_stage_id"))) or {}).get("stage_name") or "Incoming Inspection"), disabled=True)

        c1, c2, c3, c4, c5, c6 = st.columns(6, gap="small")
        report_no = c1.text_input("Report Number", value=str((existing or {}).get("report_number") or ""), placeholder="Generated automatically on first save · YY year", disabled=True)
        test_date = c2.date_input("Test Date", value=date.fromisoformat(str((existing or {}).get("test_date"))[:10]) if (existing or {}).get("test_date") else date.today(), format="DD-MM-YYYY", disabled=not writable)
        c3.text_input("Part Number", value=str(part.get("part_number") or ""), disabled=True)
        c4.text_input("FSI Part Number", value=str(part.get("fsi_part_number") or ""), disabled=True)
        c5.text_input("Heat Number", value=str(inward.get("heat_number") or ""), disabled=True)
        c6.text_input("Heat Code", value=str(inward.get("heat_code") or ""), disabled=True)
        c1, c2, c3, c4, c5 = st.columns(5, gap="small")
        c1.text_input("Supplier", value=str(supplier.get("party_name") or ""), disabled=True)
        c2.text_input("Steel Mill", value=str(steel_mill.get("party_name") or ""), disabled=True)
        c3.text_input("Material Grade", value=str(grade.get("grade_code") or ""), disabled=True)
        c4.text_input("Steel Quantity (kg)", value=f"{float(inward.get('steel_quantity_kg') or inward.get('quantity_received') or 0):,.3f}", disabled=True)
        c5.text_input("Production Quantity (pcs)", value=f"{float(inward.get('production_quantity_pcs') or 0):,.0f}", disabled=True)

        c1, c2, c3 = st.columns(3, gap="small")
        sample_ref = c1.text_input("Sample Reference", value=str((existing or {}).get("sample_reference") or inward.get("inward_number") or ""), disabled=not writable)
        spec_ref = c2.text_input("Specification Reference", value=str((existing or {}).get("specification_reference") or plan.get("format_number") or part.get("drawing_number") or ""), disabled=not writable)
        attachment = c3.file_uploader("Attach MetLAB Report", type=["pdf", "xlsx", "xls", "png", "jpg", "jpeg"], key=f"metlab_attachment_{existing_id or 'new'}", disabled=not writable)

    existing_chem = {str(row.get("element")): row for row in _existing_rows(existing, "chemistry_rows")}
    chem_frame = pd.DataFrame([{
        "Element": row.get("element"), "Min": row.get("minimum_value"), "Max": row.get("maximum_value"),
        "RMTC Actual": row.get("actual_value"), "MetLAB Actual": (existing_chem.get(str(row.get("element"))) or {}).get("actual_value"),
        "Unit": row.get("unit") or "%", "NA": (existing_chem.get(str(row.get("element"))) or {}).get("result") == "NOT_APPLICABLE",
        "Result": (existing_chem.get(str(row.get("element"))) or {}).get("result") or "NOT_EVALUATED",
        "Remark": (existing_chem.get(str(row.get("element"))) or {}).get("remarks") or "",
    } for row in snapshot.get("chemistry") or []])
    with stage_section("B", "CHEMICAL COMPOSITION", "RMTC values remain reference-only; MetLAB observations and remarks are editable.", key="metlab_report_render_entry_b"):
        chem_edit = st.data_editor(chem_frame, hide_index=True, width="stretch", disabled=True if not writable else ["Element", "Min", "Max", "RMTC Actual", "Unit", "Result"], column_config={"NA": st.column_config.CheckboxColumn()}, key=f"metlab_chem_{existing_id or 'new'}_{inward_id}")

    existing_jom = {str(row.get("distance_label")): row for row in _existing_rows(existing, "jominy_rows")}
    jom_frame = pd.DataFrame([{
        "Distance": row.get("distance_label"), "MM": row.get("distance_mm"), "Min HRC": row.get("minimum_hrc"), "Max HRC": row.get("maximum_hrc"),
        "RMTC Actual HRC": row.get("actual_hrc"), "MetLAB Actual HRC": (existing_jom.get(str(row.get("distance_label"))) or {}).get("actual_value"),
        "NA": (existing_jom.get(str(row.get("distance_label"))) or {}).get("result") == "NOT_APPLICABLE",
        "Result": (existing_jom.get(str(row.get("distance_label"))) or {}).get("result") or "NOT_EVALUATED",
        "Remark": (existing_jom.get(str(row.get("distance_label"))) or {}).get("remarks") or "",
    } for row in snapshot.get("jominy") or []])
    with stage_section("C", "JOMINY HARDENABILITY", key="metlab_report_render_entry_c"):
        jom_edit = st.data_editor(jom_frame, hide_index=True, width="stretch", disabled=True if not writable else ["Distance", "MM", "Min HRC", "Max HRC", "RMTC Actual HRC", "Result"], column_config={"NA": st.column_config.CheckboxColumn()}, key=f"metlab_jom_{existing_id or 'new'}_{inward_id}")

    existing_req = {str(row.get("requirement_name")): row for row in _existing_rows(existing, "requirement_rows")}
    req_frame = pd.DataFrame([{
        "Parameter": row.get("requirement_name"), "Requirement": row.get("requirement_value"), "RMTC Actual": row.get("actual_value"),
        "MetLAB Actual": (existing_req.get(str(row.get("requirement_name"))) or {}).get("actual_value"), "Unit": row.get("unit"),
        "NA": (existing_req.get(str(row.get("requirement_name"))) or {}).get("result") == "NOT_APPLICABLE",
        "Result": (existing_req.get(str(row.get("requirement_name"))) or {}).get("result") or "NOT_EVALUATED",
        "Remark": (existing_req.get(str(row.get("requirement_name"))) or {}).get("remarks") or "",
    } for row in snapshot.get("requirements") or []])
    with stage_section("D", "HEAT TREATMENT / MECHANICAL REQUIREMENTS", key="metlab_report_render_entry_d"):
        req_edit = st.data_editor(req_frame, hide_index=True, width="stretch", disabled=True if not writable else ["Parameter", "Requirement", "RMTC Actual", "Unit"], column_config={"NA": st.column_config.CheckboxColumn(), "Result": st.column_config.SelectboxColumn(options=list(RESULT_OPTIONS))}, key=f"metlab_req_{existing_id or 'new'}_{inward_id}")

    layout_source = _layout_rows(service, plan_id, existing)
    layout_frame = pd.DataFrame([{"Sr No": row.get("sequence_no"), "Parameter": row.get("parameter"), "Specification": row.get("specification"), "Min": row.get("lower_spec"), "Max": row.get("upper_spec"), "Method / Aid": row.get("checking_method"), "Actual Value": row.get("actual_value"), "Unit": row.get("unit"), "NA": row.get("applicability") == "NOT_APPLICABLE", "Result": row.get("result"), "Remark": row.get("remarks"), "_characteristic_id": row.get("inspection_plan_characteristic_id"), "_type": row.get("characteristic_type")} for row in layout_source])
    with stage_section("E", "ADDITIONAL METLAB LAYOUT CHARACTERISTICS", key="metlab_report_render_entry_e"):
        if not layout_frame.empty:
            layout_edit = st.data_editor(layout_frame, hide_index=True, width="stretch", disabled=True if not writable else ["Sr No", "Parameter", "Specification", "Min", "Max", "Method / Aid", "Result", "_characteristic_id", "_type"], column_config={"NA": st.column_config.CheckboxColumn(), "_characteristic_id": None, "_type": None}, key=f"metlab_layout_{existing_id or 'new'}_{plan_id or 'auto'}")
        else:
            st.info("No additional layout characteristics are configured for this report.")
            layout_edit = pd.DataFrame()

    chemistry_rows = []
    for _, row in chem_edit.iterrows():
        na = bool(row.get("NA"))
        result = _band_result(row.get("MetLAB Actual"), row.get("Min"), row.get("Max"), na)
        chemistry_rows.append({"element": row.get("Element"), "minimum_value": row.get("Min"), "maximum_value": row.get("Max"), "rmtc_actual_value": row.get("RMTC Actual"), "actual_value": row.get("MetLAB Actual"), "unit": row.get("Unit"), "result": result, "remarks": row.get("Remark")})
    jominy_rows = []
    for _, row in jom_edit.iterrows():
        na = bool(row.get("NA"))
        result = _band_result(row.get("MetLAB Actual HRC"), row.get("Min HRC"), row.get("Max HRC"), na)
        jominy_rows.append({"distance_label": row.get("Distance"), "distance_mm": row.get("MM"), "minimum_hrc": row.get("Min HRC"), "maximum_hrc": row.get("Max HRC"), "rmtc_actual_hrc": row.get("RMTC Actual HRC"), "actual_value": row.get("MetLAB Actual HRC"), "result": result, "remarks": row.get("Remark")})
    requirement_rows = []
    for _, row in req_edit.iterrows():
        na = bool(row.get("NA"))
        low, high = _range_from_text(row.get("Requirement"))
        auto = _band_result(row.get("MetLAB Actual"), low, high, na)
        result = auto if auto != "NOT_EVALUATED" or str(row.get("Result") or "") == "NOT_EVALUATED" else str(row.get("Result") or "NOT_EVALUATED")
        requirement_rows.append({"requirement_name": row.get("Parameter"), "requirement_value": row.get("Requirement"), "rmtc_actual_value": row.get("RMTC Actual"), "actual_value": row.get("MetLAB Actual"), "unit": row.get("Unit"), "result": result, "remarks": row.get("Remark")})
    layout_rows = []
    for _, row in layout_edit.iterrows():
        na = bool(row.get("NA"))
        result = service.evaluate_characteristic({"characteristic_type": row.get("_type"), "specification": row.get("Specification"), "lower_spec": row.get("Min"), "upper_spec": row.get("Max")}, [row.get("Actual Value")], na)
        layout_rows.append({"sequence_no": int(row.get("Sr No") or len(layout_rows) + 1), "inspection_plan_characteristic_id": row.get("_characteristic_id"), "parameter": row.get("Parameter"), "specification": row.get("Specification"), "lower_spec": row.get("Min"), "upper_spec": row.get("Max"), "checking_method": row.get("Method / Aid"), "actual_value": row.get("Actual Value"), "unit": row.get("Unit"), "applicability": "NOT_APPLICABLE" if na else "APPLICABLE", "result": result, "remarks": row.get("Remark"), "characteristic_type": row.get("_type")})

    with stage_section("F", "VALIDATION PREVIEW", "Out-of-spec MetLAB observations are highlighted in red/bold before the report is saved or finalized.", key="metlab_report_validation_preview"):
        _metlab_validation_preview([*layout_rows, *chemistry_rows, *jominy_rows, *requirement_rows], key=f"metlab_preview_{existing_id or 'new'}")

    with stage_section("G", "CASE DEPTH / MICROHARDNESS TRAVERSE", "Distance starts at 0.05 mm, then 0.10, 0.20, 0.30 mm and continues in 0.10 mm increments. Add multiple measurement locations as required by the part.", key="metlab_report_case_depth"):
        case_depth_traverse = _case_depth_editor(existing, key=f"metlab_case_depth_{existing_id or 'new'}", disabled=not writable)

    with stage_section("H", "MICROSTRUCTURE PHOTOS", "Upload up to four microstructure images and enter a title for each photograph.", key="metlab_report_photos"):
        micro_cols = st.columns(4, gap="small")
        micro_files = []
        micro_captions = []
        for slot, column in enumerate(micro_cols, start=1):
            with column:
                existing_path = str((existing or {}).get(f"microstructure_image_{slot}_path") or "")
                if existing_path:
                    st.caption(f"Photo {slot} already uploaded")
                micro_files.append(st.file_uploader(f"Microstructure Photo {slot}", type=["png", "jpg", "jpeg"], key=f"microstructure_{slot}_{existing_id or 'new'}", disabled=not writable))
                micro_captions.append(st.text_input(f"Photo {slot} Title", value=str((existing or {}).get(f"microstructure_caption_{slot}") or ""), key=f"micro_caption_{slot}_{existing_id or 'new'}", disabled=not writable))

    with stage_section("I", "CONCLUSION / FINAL DECISION / SIGN-OFF", "Conclusion and Final Decision use the same controlled quality dispositions. Approved By is always the employee mapped to the current login.", key="metlab_report_signoff"):
        employee_options = [""] + list(employee_map)
        c1, c2, c3 = st.columns(3, gap="small")
        prepared_current = str((existing or {}).get("prepared_by_employee_id") or "")
        prepared = c1.selectbox("Prepared By", employee_options, index=employee_options.index(prepared_current) if prepared_current in employee_options else 0, format_func=lambda value: employee_map.get(value, "— Select —"), disabled=not writable)
        conclusion_options = ["PENDING", *FINAL_DISPOSITIONS]
        current_conclusion = "PENDING" if amendment_enabled else _existing_conclusion(existing)
        conclusion = c2.selectbox("Conclusion", conclusion_options, index=conclusion_options.index(current_conclusion), format_func=disposition_label, disabled=not writable, help="Controlled MetLAB conclusion: Pending, On Hold, Accepted, Accepted Under Reserve or Rejected.")
        remarks = c3.text_input("Conclusion Remark", value=str((existing or {}).get("remarks") or ""), help="Required for On Hold, Accepted Under Reserve and Rejected conclusions.", disabled=not writable)
        c1, c2 = st.columns(2, gap="small")
        decision_options = ["PENDING", *FINAL_DISPOSITIONS]
        current_decision = "PENDING" if amendment_enabled else str((existing or {}).get("disposition") or "PENDING")
        disposition = c1.selectbox("Final Decision", decision_options, index=decision_options.index(current_decision) if current_decision in decision_options else 0, format_func=disposition_label, disabled=not writable)
        reason = c2.text_input("Decision Reason", value="" if amendment_enabled else str((existing or {}).get("disposition_reason") or ""), disabled=not writable)

    if st.button("Save Raw Material MetLAB Draft", type="primary", disabled=not writable or not prepared or not sample_ref.strip(), width="stretch"):
        try:
            final_number = str((existing or {}).get("report_number") or "").strip() or service.next_number("METLAB")
            payload = {
                "report_number": final_number, "test_type": "METLAB", "layout_plan_id": plan_id,
                "process_id": plan.get("process_id"), "inspection_stage_id": plan.get("inspection_stage_id"), "part_id": part_id,
                "inward_lot_id": inward_id, "rmtc_approval_id": inward.get("rmtc_approval_id"), "supplier_id": inward.get("supplier_id"),
                "steel_mill_id": rmtc.get("steel_mill_id"), "material_grade_id": part.get("material_grade_id"),
                "test_date": test_date.isoformat(), "sample_reference": sample_ref.strip(), "reference_text": sample_ref.strip(),
                "specification_reference": spec_ref.strip() or None, "overall_result": "NOT_EVALUATED",
                "status": "DRAFT" if amendment_enabled else str((existing or {}).get("status") or "DRAFT"), "remarks": remarks.strip() or None,
                "disposition": disposition, "disposition_reason": reason.strip() or None, "heat_number": inward.get("heat_number"), "heat_code": inward.get("heat_code"),
                "prepared_by_employee_id": prepared, "layout_name_snapshot": layout_name, "layout_type_name": layout_type,
                "steel_quantity_kg": inward.get("steel_quantity_kg") or inward.get("quantity_received"), "production_quantity_pcs": inward.get("production_quantity_pcs"),
                **{f"microstructure_caption_{slot}": micro_captions[slot - 1].strip() or None for slot in range(1, 5)},
            }
            if amendment_enabled:
                payload.update({"disposition": "PENDING", "disposition_reason": None, "overall_result": "NOT_EVALUATED", "validated_by_employee_id": None, "approved_by_employee_id": None, "validated_at": None, "decision_at": None})
            results = {"rows": layout_rows, "chemistry_rows": chemistry_rows, "jominy_rows": jominy_rows, "requirement_rows": requirement_rows, "case_depth_traverse": case_depth_traverse, "conclusion": conclusion}
            with st.spinner("Saving MetLAB verification sections…"):
                saved = service.save_metlab(payload, results, str(existing["id"]) if existing else None)
                if not existing or amendment_enabled:
                    NotificationService(service.repo).notify(
                        "METLAB_APPROVAL_PENDING",
                        subject=f"QCMS · MetLAB approval pending · {saved.get('report_number') or final_number}",
                        body_text=(f"MetLAB Report {saved.get('report_number') or final_number} is ready for validation / approval.\n"
                                   f"Part: {part.get('part_number') or '-'}\n"
                                   f"Source: {inward.get('inward_number') or inward.get('heat_number') or '-'}"),
                        related_table="lab_tests", related_id=str(saved.get("id")),
                        context={"lab_test_id": str(saved.get("id")), "inward_lot_id": str(inward_id), "next_task": "MetLAB Approval"},
                    )
                if attachment is not None:
                    service.upload_attachment("METLAB_REPORT", str(saved["id"]), "REPORT_COPY", attachment, "lab_tests", "attachment_path")
                for slot, image in enumerate(micro_files, start=1):
                    if image is not None:
                        service.upload_attachment("METLAB_REPORT", str(saved["id"]), f"MICROSTRUCTURE_{slot}", image, "lab_tests", f"microstructure_image_{slot}_path")
            st.session_state["edit_metlab_id"] = str(saved["id"])
            if amendment_enabled:
                st.session_state.pop(f"metlab_linked_amend_{existing_id}", None)
            save_success_popup(f"MetLAB Report {final_number} saved successfully.", queue_for_rerun=True)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    if existing:
        disposition_cards([{"label": "Report", "value": existing.get("status"), "foot": existing.get("report_number")}, {"label": "Final Decision", "value": existing.get("disposition")}, {"label": "Layout", "value": existing.get("layout_name_snapshot") or layout_name}])
        employee_options = [""] + list(employee_map)
        c1, c2, c3 = st.columns(3, gap="small")
        current_validator = str(existing.get("validated_by_employee_id") or "")
        validator = c1.selectbox("Validated By", employee_options, index=employee_options.index(current_validator) if current_validator in employee_options else 0, format_func=lambda value: employee_map.get(value, "— Select —"), key=f"met_linked_validator_{existing_id}")
        c2.text_input("Approved By (Current Login)", value=login_approver_label, disabled=True, key=f"met_linked_approver_{existing_id}")
        finalize_disabled = not perms.get("can_approve") or disposition == "PENDING" or not validator or not login_approver_id or str(existing.get("status") or "").upper() == "FINAL"
        if not login_approver_id:
            st.info("The current login is not mapped to an active Employee Master row. Approval is blocked until the user/employee mapping is completed.")
        if c3.button("Finalize MetLAB Decision", disabled=finalize_disabled, width="stretch"):
            try:
                service.finalize_metlab(str(existing["id"]), disposition, reason, validator, login_approver_id)
                save_success_popup("MetLAB decision finalized successfully.", queue_for_rerun=True)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        section_bar("PDF / EXCEL / PRINT EXPORT")
        _report_exports(service, str(existing["id"]), str(existing.get("report_number") or "MetLAB_Report"), key=f"met_linked_export_{existing.get('id')}")
        if password_delete_panel(
            repo=service.repo, table="lab_tests", rows=[existing], labeler=lambda row: row.get("report_number"),
            key=f"delete_metlab_entry_{existing.get('id')}", can_delete=perms["can_archive"], title="Delete This MetLAB Report",
            help_text="Permanent deletion requires your current QCMS password and MetLAB Delete permission.",
        ):
            st.session_state.pop("edit_metlab_id", None)
            st.rerun()


def render_records() -> None:
    subpage_navigation(("inspection-home", "Inspections", ":material/biotech:"), ("metlab-entry", "New / Edit Report", ":material/edit_note:"))
    page_header("MetLAB Report Records", context="Select before action")
    service = InspectionService(); perms = current_permissions("METLAB_REPORT"); parts, parties, _, _, _ = _maps(service); grades = {str(row["id"]): row for row in service.material_grades()}
    rows = service.metlab_reports(); search = st.text_input("Search Report, Part, Heat or Inward")
    filtered = [row for row in rows if not search or search.casefold() in " ".join(str(row.get(key) or "") for key in ("report_number", "heat_number", "heat_code", "batch_number", "supplier_reference_number", "sample_reference", "remarks", "layout_name_snapshot")).casefold()]
    if filtered:
        labels = {str(row["id"]): f"{row.get('report_number')} · Heat {row.get('heat_number')} · {row.get('layout_name_snapshot') or 'Layout'} · {disposition_label(row.get('disposition'))}" for row in filtered}
        selected = st.selectbox("Select MetLAB Report", list(labels), format_func=lambda value: labels[value]); selected_row = next(row for row in filtered if str(row["id"]) == selected); st.session_state["edit_metlab_id"] = selected
        c1, c2, c3, c4 = st.columns(4, gap="small")
        with c1: st.page_link(st.session_state["_qsms_pages"]["metlab-entry"], label="Open Selected Report", icon=":material/edit:", width="stretch")
        try:
            selected_payload = service.metlab_report_payload(selected)
            with c2:
                st.download_button("Download / Print PDF", data=metlab_record_pdf_bytes(selected_payload), file_name=f"{selected_row.get('report_number') or 'MetLAB_Report'}.pdf", mime="application/pdf", key=f"metlab_pdf_{selected}", icon=":material/picture_as_pdf:", width="stretch")
            with c3:
                st.download_button("Download Excel Report", data=quality_record_excel_bytes(selected_payload, "METLAB"), file_name=f"{selected_row.get('report_number') or 'MetLAB_Report'}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"metlab_xlsx_{selected}", icon=":material/download:", width="stretch")
        except Exception as exc:
            st.error(f"Report export could not be generated: {exc}")
        with c4:
            if password_delete_panel(repo=service.repo, table="lab_tests", rows=[selected_row], labeler=lambda row: row.get("report_number"), key=f"delete_metlab_{selected}", can_delete=perms["can_archive"], title="Delete Selected MetLAB Report"):
                st.rerun()
    section_bar("METLAB REGISTER")
    display = pd.DataFrame([{"Report Number": row.get("report_number"), "Date": row.get("test_date"), "Part Number": (parts.get(str(row.get("part_id"))) or {}).get("part_number"), "FSI Part Number": (parts.get(str(row.get("part_id"))) or {}).get("fsi_part_number"), "Customer": (parties.get(str(row.get("customer_id") or (parts.get(str(row.get("part_id"))) or {}).get("customer_id"))) or {}).get("party_name"), "Supplier": (parties.get(str(row.get("supplier_id"))) or {}).get("party_name"), "OSP Vendor": (parties.get(str(row.get("osp_vendor_id"))) or {}).get("party_name"), "Material Grade": (grades.get(str(row.get("material_grade_id") or (parts.get(str(row.get("part_id"))) or {}).get("material_grade_id"))) or {}).get("grade_code"), "Heat Number": row.get("heat_number"), "Batch Number": row.get("batch_number") or row.get("vendor_batch_number_snapshot"), "Layout": row.get("layout_name_snapshot"), "Report Stage": STANDALONE_STAGES.get(str(row.get("inspection_scope")), str(row.get("inspection_scope") or "MATERIAL_INWARD").replace("_", " ").title()), "Production pcs": row.get("production_quantity_pcs"), "Microstructure Photos": sum(1 for slot in range(1,5) if row.get(f"microstructure_image_{slot}_path")), "Conclusion": _existing_conclusion(row), "Conclusion Remark": row.get("remarks"), "Result": row.get("overall_result"), "Final Decision": row.get("disposition"), "Decision Reason": row.get("disposition_reason"), "Status": row.get("status")} for row in filtered])
    portal_table(style_status_dataframe(display), hide_index=True, width="stretch", height=520)
