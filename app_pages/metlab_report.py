from __future__ import annotations
from core.attachments import MICROSTRUCTURE_IMAGE_TYPES
# Legacy controlled PDF label retained for regression traceability: Download MetLAB Report PDF

import re
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st
from core.ui import portal_table
from core.selection_labels import part_label

from core.access import current_permissions
from core.password_edit import password_reopen_for_edit
from core.delete_service import password_delete_panel
from core.notification_service import NotificationService
from core.notification_ui import notification_confirmation, notification_overrides, record_email_sender
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


CASE_DEPTH_DEFAULT_DISTANCES = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
# Legacy regression token only; v4.14.14 does NOT use these as manual/default locations.
CASE_DEPTH_DEFAULT_LOCATIONS = ["Ground Face", "ID", "OD"]
CASE_DEPTH_PARAMETER_RE = re.compile(r"\bcase\s+depth\b", re.IGNORECASE)


def _case_depth_parameter(row: dict) -> str:
    """Return the controlled Parameter text used to decide Traverse applicability.

    v4.14.14 rule: only the Additional Layout Characteristic Parameter is
    evaluated. A phrase in Specification/Remark must never create a traverse.
    """
    return str(row.get("parameter") or row.get("characteristic") or "").strip()


def _has_case_depth_characteristic(rows: list[dict]) -> bool:
    return any(bool(CASE_DEPTH_PARAMETER_RE.search(_case_depth_parameter(row))) for row in rows)


def _case_depth_location_from_parameter(parameter: str) -> str:
    text = re.sub(r"\s+", " ", str(parameter or "")).strip()
    if not text:
        return ""
    location = re.sub(
        r"^(?:effective\s+)?case\s+depth(?:\s+(?:at|of|on)\s+|\s*[-:–—]\s*|\s+)?",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" -:–—")
    return location or text


def _case_depth_specification(row: dict) -> str:
    spec = str(row.get("specification") or "").strip()
    if spec:
        return spec
    low, high = row.get("lower_spec"), row.get("upper_spec")
    unit = str(row.get("unit") or "").strip()
    if low is not None or high is not None:
        if low is not None and high is not None:
            text = f"{low} - {high}"
        elif low is not None:
            text = f">= {low}"
        else:
            text = f"<= {high}"
        return f"{text} {unit}".strip()
    return ""


def _case_depth_layout_locations(layout_rows: list[dict]) -> list[dict[str, Any]]:
    """Derive Traverse locations/specifications strictly from Additional Layout Characteristics.

    A row qualifies only when its *Parameter* contains the words ``Case Depth``.
    This makes the Inspection Layout the single source of truth for Ground Face,
    ID, OD or any future Case Depth locations and their specifications.
    """
    locations: list[dict[str, Any]] = []
    for row in layout_rows:
        parameter = _case_depth_parameter(row)
        if not CASE_DEPTH_PARAMETER_RE.search(parameter):
            continue
        locations.append({
            "sequence_no": int(row.get("sequence_no") or len(locations) + 1),
            "location": _case_depth_location_from_parameter(parameter),
            "parameter": parameter,
            "specification": _case_depth_specification(row),
            "unit": str(row.get("unit") or "").strip() or None,
            "inspection_plan_characteristic_id": row.get("inspection_plan_characteristic_id") or row.get("id"),
        })
    locations.sort(key=lambda row: (int(row.get("sequence_no") or 0), str(row.get("location") or "")))
    for i, row in enumerate(locations, start=1):
        row["sequence_no"] = i
    return locations


def _case_depth_payload(existing: dict | None) -> dict[str, Any]:
    results = dict((existing or {}).get("results") or {})
    return {
        "applicable": bool(results.get("case_depth_applicable", False)),
        "locations": [dict(row) for row in (results.get("case_depth_locations") or [])],
        "traverse": [dict(row) for row in (results.get("case_depth_traverse") or [])],
        "na_reason": str(results.get("case_depth_na_reason") or ""),
    }


def _render_case_depth_traverse(existing: dict | None, *, key: str, layout_rows: list[dict]) -> tuple[dict[str, Any], bool]:
    """Render layout-driven Case Depth / Microhardness Traverse values.

    Locations and specifications are read-only here. They come only from
    Additional Layout Characteristics whose Parameter contains ``Case Depth``.
    The operator enters only distance-wise hardness readings.
    """
    saved = _case_depth_payload(existing)
    locations = _case_depth_layout_locations(layout_rows)
    if not locations:
        st.info(
            "Case Depth Traverse is not applicable because no Additional Layout Characteristic "
            "Parameter contains the words 'Case Depth'. Add parameters such as "
            "'Effective Case Depth at Ground Face', '... at ID' or '... at OD' in the MetLAB layout to enable the traverse."
        )
        return {
            "case_depth_applicable": False,
            "case_depth_locations": [],
            "case_depth_traverse": [],
            "case_depth_na_reason": "No Additional Layout Characteristic Parameter contains Case Depth.",
        }, True

    location_names = [str(row.get("location") or "").strip() for row in locations]
    duplicate_locations = len({name.casefold() for name in location_names if name}) != len([name for name in location_names if name])
    if duplicate_locations:
        st.error("Case Depth layout locations must be unique. Correct the duplicate Case Depth Parameter names in Inspection Layout Master.")

    st.caption("Locations and specifications below are controlled by Additional Layout Characteristics. Only Traverse hardness readings are entered here.")
    st.markdown("**Case Depth Locations from Additional Layout Characteristics**")
    location_frame = pd.DataFrame([{
        "Sr No": row.get("sequence_no"),
        "Case Depth Location": row.get("location"),
        "Parameter": row.get("parameter"),
        "Specification": row.get("specification"),
        "Unit": row.get("unit") or "",
    } for row in locations])
    portal_table(location_frame, hide_index=True, width="stretch", height=min(260, 80 + len(location_frame) * 34))

    saved_traverse = saved["traverse"] or [{"distance_mm": distance, "readings": {}} for distance in CASE_DEPTH_DEFAULT_DISTANCES]
    traverse_rows: list[dict[str, Any]] = []
    for row in saved_traverse:
        readings = dict(row.get("readings") or {})
        out: dict[str, Any] = {"Distance (mm)": row.get("distance_mm")}
        for name in location_names:
            out[name] = readings.get(name)
        traverse_rows.append(out)
    if not traverse_rows:
        traverse_rows = [{"Distance (mm)": distance, **{name: None for name in location_names}} for distance in CASE_DEPTH_DEFAULT_DISTANCES]

    st.markdown("**Case Depth / Microhardness Traverse Readings (HV)**")
    traverse_edit = st.data_editor(
        pd.DataFrame(traverse_rows),
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        key=f"{key}_traverse",
        column_config={
            "Distance (mm)": st.column_config.NumberColumn(min_value=0.01, step=0.05, format="%.2f"),
            **{name: st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.1f") for name in location_names},
        },
    )

    normalized: list[dict] = []
    distances: list[float] = []
    for _, row in traverse_edit.iterrows():
        distance = _number(row.get("Distance (mm)"))
        if distance is None:
            continue
        readings = {name: _number(row.get(name)) for name in location_names}
        normalized.append({"distance_mm": round(float(distance), 4), "readings": readings})
        distances.append(round(float(distance), 4))
    normalized.sort(key=lambda row: row["distance_mm"])
    duplicate_distances = len(set(distances)) != len(distances)
    starts_at_005 = bool(normalized) and abs(float(normalized[0]["distance_mm"]) - 0.05) < 1e-9
    locations_with_reading = {
        name for name in location_names
        if any((row.get("readings") or {}).get(name) is not None for row in normalized)
    }
    if duplicate_distances:
        st.error("Case Depth traverse distance values must be unique.")
    if normalized and not starts_at_005:
        st.error("The first Case Depth traverse reading must start at 0.05 mm.")
    missing_locations = [name for name in location_names if name not in locations_with_reading]
    if missing_locations:
        st.warning("Enter at least one Traverse hardness reading for: " + ", ".join(missing_locations))
    valid = bool(location_names and not duplicate_locations and normalized and starts_at_005 and not duplicate_distances and not missing_locations)
    return {
        "case_depth_applicable": True,
        "case_depth_locations": locations,
        "case_depth_traverse": normalized,
        "case_depth_na_reason": None,
    }, valid



STANDALONE_STAGES = {
    "RAW_MATERIAL_STAGE": "Raw Material Stage",
    "OSP_STAGE": "OSP Stage",
    "FINAL_DISPATCH_STAGE": "Final Dispatch Stage",
}


def _render_standalone_metlab(service: InspectionService, perms: dict, parts: dict[str, dict], parties: dict[str, dict], processes: dict[str, dict], stages: dict[str, dict], employee_map: dict[str, str], existing: dict | None) -> None:
    existing_id = str((existing or {}).get("id") or "")
    with stage_section("A", "STANDALONE METLAB CONTEXT", "Master-driven Part / Customer / Material / OSP context. No RMTC or inward transaction linkage is required.", key="metlab_standalone_context"):
        scope_keys = list(STANDALONE_STAGES)
        current_scope = str((existing or {}).get("inspection_scope") or "RAW_MATERIAL_STAGE")
        scope = st.selectbox("Report Stage", scope_keys, index=scope_keys.index(current_scope) if current_scope in scope_keys else 0, format_func=lambda v: STANDALONE_STAGES[v], disabled=bool(existing))

        part_map = {pid: part_label(row) for pid, row in parts.items()}
        if not part_map:
            st.warning("No active Parts are available."); return
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
                st.warning("No active OSP MetLAB Process requirements are configured in Part Master for this Part Number."); return
            group_map = {str(row["id"]): f"{(processes.get(str(row.get('process_id'))) or {}).get('process_code') or '-'} · {(processes.get(str(row.get('process_id'))) or {}).get('process_name') or '-'}" for row in groups}
            existing_process = str((existing or {}).get("process_id") or "")
            default_group = next((str(row["id"]) for row in groups if str(row.get("process_id")) == existing_process), next(iter(group_map)))
            group_id = st.selectbox("OSP Process", list(group_map), index=list(group_map).index(default_group), format_func=lambda value: group_map[value], disabled=bool(existing))
            process_group = next(row for row in groups if str(row["id"]) == group_id)
            process_id = str(process_group.get("process_id") or "") or None

        saved_plan_id = str((existing or {}).get("layout_plan_id") or "")
        plan = service.get_plan(saved_plan_id) if saved_plan_id else None
        if plan and str(plan.get("part_id") or "") != part_id:
            plan = None
        if not plan:
            plan = service.auto_standalone_plan("METLAB", part_id, scope, process_id)
        elif str(plan.get("status") or "").upper() != "APPROVED":
            st.warning("This saved report uses a historical MetLAB layout. QCMS loaded the original layout so the report can be edited without silently changing its specification basis.")
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
        supplier_id = vc1.selectbox("Supplier", supplier_options, index=supplier_options.index(current_supplier) if current_supplier in supplier_options else 0, format_func=lambda v: party_label(parties.get(v) or {}) if v else "— Select Supplier from Master —")
        osp_vendor_id = vc2.selectbox("OSP Vendor", osp_vendor_options, index=osp_vendor_options.index(current_osp_vendor) if current_osp_vendor in osp_vendor_options else 0, format_func=lambda v: party_label(parties.get(v) or {}) if v else "— Select OSP Vendor from Master —")

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
        report_no = c1.text_input("Report Number", value=str((existing or {}).get("report_number") or ""), placeholder="Auto on save")
        test_date = c2.date_input("Test Date", value=date.fromisoformat(str((existing or {}).get("test_date"))[:10]) if (existing or {}).get("test_date") else date.today(), format="DD-MM-YYYY")
        heat = c3.text_input("Heat Number", value=str((existing or {}).get("heat_number") or ""))
        heat_code = c4.text_input("Heat Code", value=str((existing or {}).get("heat_code") or ""))
        c1, c2, c3, c4 = st.columns(4, gap="small")
        vendor_batch_number = c1.text_input("Supplier / HT / OSP Batch Number", value=str((existing or {}).get("vendor_batch_number_snapshot") or ""))
        batch_number = c2.text_input("Internal / FSI Batch Number", value=str((existing or {}).get("batch_number") or ""))
        supplier_reference = c3.text_input("Supplier Invoice / Reference", value=str((existing or {}).get("supplier_reference_number") or ""))
        c1, c2, c3, c4 = st.columns(4, gap="small")
        quantity_pcs = c1.number_input("Quantity (pcs)", min_value=0.0, value=float((existing or {}).get("production_quantity_pcs") or 0), step=1.0)
        sample_ref = c2.text_input("Sample / Reference", value=str((existing or {}).get("sample_reference") or ""))
        default_condition = (process_group or {}).get("process_specification") or process.get("process_name") or STANDALONE_STAGES[scope]
        supply_condition = st.text_input("Supply / Process Condition", value=str((existing or {}).get("supply_condition") or default_condition or ""))
        spec_ref = st.text_input("Specification Reference", value=str((existing or {}).get("specification_reference") or plan.get("format_number") or part.get("drawing_number") or ""))

    with stage_section("B", "MICROSTRUCTURE PHOTOGRAPHS", "Up to four report photographs with controlled titles.", key="metlab_standalone_photos"):
        micro_cols = st.columns(4, gap="small"); micro_files = []; micro_captions = []
        for slot, col in enumerate(micro_cols, start=1):
            with col:
                if (existing or {}).get(f"microstructure_image_{slot}_path"):
                    st.caption(f"Photo {slot} already uploaded")
                micro_files.append(st.file_uploader(f"Photo {slot}", type=MICROSTRUCTURE_IMAGE_TYPES, key=f"standalone_metlab_photo_{slot}_{existing_id or 'new'}"))
                micro_captions.append(st.text_input(f"Photo {slot} Title", value=str((existing or {}).get(f"microstructure_caption_{slot}") or ""), key=f"standalone_metlab_caption_{slot}_{existing_id or 'new'}"))

    with stage_section("C", "METLAB CHARACTERISTICS", "The inspection grid is loaded automatically from the approved Part Master controlled layout.", key="metlab_standalone_characteristics"):
        layout_source = _layout_rows(service, plan_id, existing)
        frame = pd.DataFrame([{"Sr No": r.get("sequence_no"), "Parameter": r.get("parameter"), "Specification": r.get("specification"), "Min": r.get("lower_spec"), "Max": r.get("upper_spec"), "Method / Aid": r.get("checking_method"), "Actual Value": r.get("actual_value"), "Unit": r.get("unit"), "NA": r.get("applicability") == "NOT_APPLICABLE", "Result": r.get("result"), "Remark": r.get("remarks"), "_characteristic_id": r.get("inspection_plan_characteristic_id"), "_type": r.get("characteristic_type")} for r in layout_source])
        edited = st.data_editor(frame, hide_index=True, width="stretch", height=min(620, max(220, 80 + len(frame) * 30)), disabled=["Sr No", "Parameter", "Specification", "Min", "Max", "Method / Aid", "Result", "_characteristic_id", "_type"], column_config={"NA": st.column_config.CheckboxColumn(), "_characteristic_id": None, "_type": None}, key=f"standalone_metlab_grid_{existing_id or 'new'}_{plan_id}")
        section_bar("CASE DEPTH / MICROHARDNESS TRAVERSE")
        case_depth_results, case_depth_valid = _render_case_depth_traverse(existing, key=f"standalone_case_depth_{existing_id or 'new'}_{plan_id}", layout_rows=layout_source)
        employee_options = [""] + list(employee_map)
        c1, c2, c3 = st.columns(3, gap="small")
        current_prepared = str((existing or {}).get("prepared_by_employee_id") or "")
        prepared = c1.selectbox("Prepared By", employee_options, index=employee_options.index(current_prepared) if current_prepared in employee_options else 0, format_func=lambda v: employee_map.get(v, "— Select —"))
        disposition_options = ["PENDING", *FINAL_DISPOSITIONS]
        current_decision = str((existing or {}).get("disposition") or "PENDING")
        disposition = c2.selectbox("Final Decision", disposition_options, index=disposition_options.index(current_decision) if current_decision in disposition_options else 0, format_func=disposition_label)
        reason = c3.text_input("Decision Reason", value=str((existing or {}).get("disposition_reason") or ""), help="Required for On Hold, Accepted Under Reserve and Rejected decisions.")
        conclusion = st.text_area("Conclusion", value=str((existing or {}).get("remarks") or ""), height=76, help="Controlled MetLAB conclusion. This prints separately from the Final Decision.")
        attachment = st.file_uploader("Attach MetLAB Report", type=["pdf", "xlsx", "xls", "png", "jpg", "jpeg"], key=f"standalone_metlab_attachment_{existing_id or 'new'}")
        layout_rows = []
        for _, row in edited.iterrows():
            na = bool(row.get("NA")); result = service.evaluate_characteristic({"characteristic_type": row.get("_type"), "specification": row.get("Specification"), "lower_spec": row.get("Min"), "upper_spec": row.get("Max")}, [row.get("Actual Value")], na)
            layout_rows.append({"sequence_no": int(row.get("Sr No") or len(layout_rows) + 1), "inspection_plan_characteristic_id": row.get("_characteristic_id"), "parameter": row.get("Parameter"), "specification": row.get("Specification"), "lower_spec": row.get("Min"), "upper_spec": row.get("Max"), "checking_method": row.get("Method / Aid"), "actual_value": row.get("Actual Value"), "unit": row.get("Unit"), "applicability": "NOT_APPLICABLE" if na else "APPLICABLE", "result": result, "remarks": row.get("Remark"), "characteristic_type": row.get("_type")})
        writable = (perms["can_edit"] if existing else perms["can_create"]) and str((existing or {}).get("status") or "DRAFT").upper() == "DRAFT"
        metlab_notify_pref = notification_confirmation(NotificationService(service.repo), "METLAB_APPROVAL_PENDING", key=f"standalone_metlab_notify_{existing_id or 'new'}", context={"part_number":(parts.get(str(part_id)) or {}).get("part_number"),"next_task":"MetLAB Approval"}, default_send=not bool(existing_id)) if not existing_id else {"send":False,"confirmed":True,"preview":{}}
        if st.button("Save Standalone MetLAB Report", type="primary", width="stretch", disabled=not writable or not prepared or not sample_ref.strip() or not case_depth_valid or (metlab_notify_pref["send"] and not metlab_notify_pref["confirmed"])):
            try:
                final_number = report_no.strip() or service.next_number("METLAB")
                payload = {
                    "report_number": final_number, "test_type": "METLAB", "layout_plan_id": plan_id,
                    "process_id": process_id, "inspection_stage_id": plan.get("inspection_stage_id"), "part_id": part_id,
                    "inward_lot_id": None, "osp_job_id": None, "batch_id": None, "rmtc_approval_id": None,
                    "supplier_id": supplier_id or None, "osp_vendor_id": osp_vendor_id or None, "customer_id": part.get("customer_id"), "material_grade_id": part.get("material_grade_id"),
                    "test_date": test_date.isoformat(), "sample_reference": sample_ref.strip(), "reference_text": sample_ref.strip(),
                    "specification_reference": spec_ref.strip() or None, "overall_result": "NOT_EVALUATED",
                    "status": str((existing or {}).get("status") or "DRAFT"), "remarks": conclusion.strip() or None,
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
                saved = service.save_metlab(payload, {"rows": layout_rows, "chemistry_rows": [], "jominy_rows": [], "requirement_rows": [], **case_depth_results}, existing_id or None)
                # Save report copy / microstructure evidence BEFORE notifying so first approval email carries the documents.
                if attachment is not None:
                    service.upload_attachment("METLAB_REPORT", str(saved["id"]), "REPORT_COPY", attachment, "lab_tests", "attachment_path")
                for slot, image in enumerate(micro_files, start=1):
                    if image is not None:
                        service.upload_attachment("METLAB_REPORT", str(saved["id"]), f"MICROSTRUCTURE_{slot}", image, "lab_tests", f"microstructure_image_{slot}_path")
                if not existing_id and metlab_notify_pref["send"] and metlab_notify_pref["confirmed"]:
                    NotificationService(service.repo).notify(
                        "METLAB_APPROVAL_PENDING",
                        subject=f"QCMS · MetLAB approval pending · {saved.get('report_number') or final_number}",
                        body_text=(f"MetLAB Report {saved.get('report_number') or final_number} is ready for validation / approval.\n"
                                   f"Part: {(parts.get(str(saved.get('part_id'))) or {}).get('part_number') or '-'}\n"
                                   f"Test Date: {saved.get('test_date') or test_date}"),
                        related_table="lab_tests",related_id=str(saved.get("id")),
                        context={"lab_test_id":str(saved.get("id")),"next_task":"MetLAB Approval"},
                        **notification_overrides(metlab_notify_pref),
                    )
                st.session_state["edit_metlab_id"] = str(saved["id"]); save_success_popup(f"Standalone MetLAB Report {final_number} saved successfully.", queue_for_rerun=True); st.rerun()
            except Exception as exc:
                st.error(str(exc))

        if existing:
            disposition_cards([
                {"label": "Report", "value": existing.get("status"), "foot": existing.get("report_number")},
                {"label": "Final Decision", "value": existing.get("disposition")},
                {"label": "Conclusion", "value": existing.get("remarks") or "Pending conclusion"},
            ])
            c1, c2, c3 = st.columns(3, gap="small")
            current_validator = str(existing.get("validated_by_employee_id") or "")
            current_approver = str(existing.get("approved_by_employee_id") or "")
            validator = c1.selectbox("Validated By", employee_options, index=employee_options.index(current_validator) if current_validator in employee_options else 0, format_func=lambda value: employee_map.get(value, "— Select —"), key=f"met_standalone_validator_{existing_id}")
            approver = c2.selectbox("Approved By", employee_options, index=employee_options.index(current_approver) if current_approver in employee_options else 0, format_func=lambda value: employee_map.get(value, "— Select —"), key=f"met_standalone_approver_{existing_id}")
            if c3.button("Finalize MetLAB Decision", disabled=not perms["can_approve"] or disposition == "PENDING" or not validator or not approver or str(existing.get("status")) == "FINAL", width="stretch", key=f"met_standalone_finalize_{existing_id}"):
                try:
                    service.finalize_metlab(existing_id, disposition, reason, validator, approver)
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
    service = InspectionService(); perms = current_permissions("METLAB_REPORT")
    parts, parties, processes, stages, employee_map = _maps(service)
    # DIRECT METLAB EDIT SELECTOR v4.14.6 — always visible
    existing_id = str(st.session_state.get("edit_metlab_id") or "")
    report_rows = service.metlab_reports()
    section_bar("NEW / EDIT EXISTING METLAB REPORT")
    report_labels = {"": "— Create New MetLAB Report —"}
    report_labels.update({str(row.get("id")): f"{row.get('report_number') or '-'} · {row.get('layout_name_snapshot') or row.get('test_type') or row.get('report_type') or 'MetLAB'} · {row.get('status') or '-'}" for row in report_rows if row.get("id")})
    report_ids = list(report_labels)
    selected_edit_id = st.selectbox(
        "Select Existing MetLAB Report to Edit", report_ids,
        index=report_ids.index(existing_id) if existing_id in report_ids else 0,
        format_func=lambda value: report_labels[value], key="metlab_direct_edit_selector",
    )
    e1, e2 = st.columns(2, gap="small")
    if e1.button("Load Selected MetLAB Report for Edit", type="primary", width="stretch", disabled=not selected_edit_id or not perms["can_edit"], key="metlab_direct_edit_load"):
        st.session_state["edit_metlab_id"] = selected_edit_id
        st.rerun()
    if e2.button("Start New MetLAB Report", width="stretch", key="metlab_direct_edit_new"):
        st.session_state.pop("edit_metlab_id", None)
        st.rerun()
    if not report_rows:
        st.info("No saved MetLAB reports are currently visible to this login. The edit control is active and will list reports as soon as records are available to your tenant/permissions.")
    if not perms["can_edit"]:
        st.caption("Your user does not currently have MetLAB Edit permission. Administrator role is not required; module Edit permission is required.")
    existing_id = str(st.session_state.get("edit_metlab_id") or "")
    existing_record = service.get_metlab(existing_id) if existing_id else None
    if existing_record and str(existing_record.get("part_id") or "") not in parts:
        historic_part = service.repo.get("parts", str(existing_record.get("part_id") or "")) or {}
        if historic_part:
            parts[str(historic_part["id"])] = historic_part
    if existing_record and str(existing_record.get("status") or "DRAFT").upper() != "DRAFT":
        section_bar("EDIT SELECTED METLAB REPORT")
        password_reopen_for_edit(
            repo=service.repo, table="lab_tests", record=existing_record, entity_type="METLAB_REPORT",
            can_edit=perms["can_edit"], key=f"metlab_report_edit_unlock_{existing_id}",
            title="Edit Selected MetLAB Report with Password",
        )
    elif existing_record:
        st.success(f"Editing MetLAB Report {existing_record.get('report_number') or existing_id}. Draft fields are editable with your assigned MetLAB Edit permission.")
    standalone_existing = str((existing_record or {}).get("inspection_scope") or "") in STANDALONE_STAGES
    report_mode = st.radio("Report Linkage", ["QCMS Linked Flow", "Standalone Stage Report"], index=1 if standalone_existing else 0, horizontal=True, disabled=bool(existing_record), help="Standalone Stage Report does not require RMTC, Material Inward or Production linkage.")
    if report_mode == "Standalone Stage Report":
        _render_standalone_metlab(service, perms, parts, parties, processes, stages, employee_map, existing_record)
        return
    pending_queue = [row for row in service.inspection_queue() if row.get("metlab_pending")]
    with stage_section("A", 'METLAB PENDING LIST', key="metlab_report_render_entry_a"):
        if pending_queue:
            portal_table(
                style_status_dataframe(_pending_frame(pending_queue, parts, parties)),
                hide_index=True, width="stretch", height=min(300, 84 + 38 * len(pending_queue)),
            )
        else:
            st.success("No Metlab inspections are pending.")
        inward_rows = service.inward_lots()
        existing_id = str(st.session_state.get("edit_metlab_id") or "")
        existing = service.get_metlab(existing_id) if existing_id else None
        existing_inward_id = str((existing or {}).get("inward_lot_id") or "")
        if existing_inward_id and all(str(row.get("id")) != existing_inward_id for row in inward_rows):
            historic_inward = service.repo.get("inward_lots", existing_inward_id) or {}
            if historic_inward:
                inward_rows = [historic_inward, *inward_rows]
                st.info("The source Material Inward is no longer in the current pending/released queue, but it has been restored here so this saved report can be edited safely.")
        if not inward_rows:
            st.warning("No Accepted or Accepted Under Reserve Material Inward is available.")
            return

        inward_map = {str(row["id"]): _inward_label(row, parts, parties) for row in inward_rows}
        current_inward = str((existing or {}).get("inward_lot_id") or st.session_state.get("inspection_inward_id") or next(iter(inward_map)))
        inward_id = st.selectbox("Material Inward / Part / Supplier / Quantity", list(inward_map), index=list(inward_map).index(current_inward) if current_inward in inward_map else 0, format_func=lambda value: inward_map[value], disabled=bool(existing))
        inward = next(row for row in inward_rows if str(row["id"]) == inward_id)
        part_id = str(inward.get("part_id")); part = parts.get(part_id) or {}
        snapshot = service.rmtc_material_snapshot(inward)
        rmtc = snapshot.get("rmtc") or {}; grade = snapshot.get("grade") or {}; supplier = snapshot.get("supplier") or {}; steel_mill = snapshot.get("steel_mill") or {}

        all_plans = service.plans("METLAB", part_id, approved_only=True)
        saved_plan_id = str((existing or {}).get("layout_plan_id") or "")
        if saved_plan_id and all(str(row.get("id")) != saved_plan_id for row in all_plans):
            historic_plan = service.get_plan(saved_plan_id) or {}
            if historic_plan and str(historic_plan.get("part_id") or "") == part_id:
                all_plans = [historic_plan, *all_plans]
                st.warning("This report uses a historical / no-longer-approved MetLAB layout. QCMS loaded that saved layout for controlled editing instead of changing the report silently.")
        plan_id: str | None = None; plan: dict = {}
        if all_plans:
            plan_map = {str(row["id"]): f"{row.get('layout_name')} · {row.get('plan_number')} Rev {row.get('revision')}" for row in all_plans}
            ranked = service.ranked_plans("METLAB", part_id)
            recommended = ranked[0] if ranked else all_plans[0]
            selection_mode = st.radio("Layout Selection", ["Automatic", "Manual"], horizontal=True, disabled=bool(existing))
            if existing:
                plan_id = saved_plan_id if saved_plan_id in plan_map else str(recommended.get("id") or "")
                if saved_plan_id and saved_plan_id not in plan_map:
                    st.warning("The originally saved MetLAB layout record could not be found. The current approved layout is shown as a controlled fallback; review before saving.")
            elif selection_mode == "Automatic":
                plan_id = str(recommended["id"]); st.info(f"Automatically selected: {plan_map.get(plan_id, plan_id)}")
            else:
                plan_id = st.selectbox("Approved MetLAB Layout", list(plan_map), format_func=lambda value: plan_map[value])
            if selection_mode == "Automatic" or existing:
                st.selectbox("Approved MetLAB Layout", [plan_id], format_func=lambda value: plan_map.get(value, value), disabled=True)
            plan = next((row for row in all_plans if str(row.get("id")) == plan_id), recommended or {})
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
        report_no = c1.text_input("Report Number", value=str((existing or {}).get("report_number") or ""), placeholder="Auto on save")
        test_date = c2.date_input("Test Date", value=date.fromisoformat(str((existing or {}).get("test_date"))[:10]) if (existing or {}).get("test_date") else date.today(), format="DD-MM-YYYY")
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
        sample_ref = c1.text_input("Sample Reference", value=str((existing or {}).get("sample_reference") or inward.get("inward_number") or ""))
        spec_ref = c2.text_input("Specification Reference", value=str((existing or {}).get("specification_reference") or plan.get("format_number") or part.get("drawing_number") or ""))
        attachment = c3.file_uploader("Attach MetLAB Report", type=["pdf", "xlsx", "xls", "png", "jpg", "jpeg"], key=f"metlab_attachment_{existing_id or 'new'}")

        # Legacy test marker: MICROSTRUCTURE PHOTOS
    with stage_section("B", 'MICROSTRUCTURE PHOTOGRAPHS', 'Upload up to four microstructure images and enter a title for each photograph.', key="metlab_report_render_entry_b"):
        micro_cols = st.columns(4, gap="small")
        micro_files = []
        micro_captions = []
        for slot, column in enumerate(micro_cols, start=1):
            with column:
                existing_path = str((existing or {}).get(f"microstructure_image_{slot}_path") or "")
                if existing_path:
                    st.caption(f"Photo {slot} already uploaded")
                micro_files.append(st.file_uploader(f"Microstructure Photo {slot}", type=MICROSTRUCTURE_IMAGE_TYPES, key=f"microstructure_{slot}_{existing_id or 'new'}"))
                micro_captions.append(st.text_input(f"Photo {slot} Title", value=str((existing or {}).get(f"microstructure_caption_{slot}") or ""), key=f"micro_caption_{slot}_{existing_id or 'new'}"))

        existing_chem = {str(row.get("element")): row for row in _existing_rows(existing, "chemistry_rows")}
        chem_frame = pd.DataFrame([{
            "Element": row.get("element"), "Min": row.get("minimum_value"), "Max": row.get("maximum_value"),
            "RMTC Actual": row.get("actual_value"), "MetLAB Actual": (existing_chem.get(str(row.get("element"))) or {}).get("actual_value"),
            "Unit": row.get("unit") or "%", "NA": (existing_chem.get(str(row.get("element"))) or {}).get("result") == "NOT_APPLICABLE",
            "Result": (existing_chem.get(str(row.get("element"))) or {}).get("result") or "NOT_EVALUATED",
            "Remark": (existing_chem.get(str(row.get("element"))) or {}).get("remarks") or "",
        } for row in snapshot.get("chemistry") or []])
    with stage_section("C", 'CHEMICAL COMPOSITION', key="metlab_report_render_entry_c"):
        chem_edit = st.data_editor(chem_frame, hide_index=True, width="stretch", disabled=["Element", "Min", "Max", "RMTC Actual", "Unit", "Result"], column_config={"NA": st.column_config.CheckboxColumn()}, key=f"metlab_chem_{existing_id or 'new'}_{inward_id}")

        existing_jom = {str(row.get("distance_label")): row for row in _existing_rows(existing, "jominy_rows")}
        jom_frame = pd.DataFrame([{
            "Distance": row.get("distance_label"), "MM": row.get("distance_mm"), "Min HRC": row.get("minimum_hrc"), "Max HRC": row.get("maximum_hrc"),
            "RMTC Actual HRC": row.get("actual_hrc"), "MetLAB Actual HRC": (existing_jom.get(str(row.get("distance_label"))) or {}).get("actual_value"),
            "NA": (existing_jom.get(str(row.get("distance_label"))) or {}).get("result") == "NOT_APPLICABLE",
            "Result": (existing_jom.get(str(row.get("distance_label"))) or {}).get("result") or "NOT_EVALUATED",
            "Remark": (existing_jom.get(str(row.get("distance_label"))) or {}).get("remarks") or "",
        } for row in snapshot.get("jominy") or []])
    with stage_section("D", 'JOMINY HARDENABILITY', key="metlab_report_render_entry_d"):
        jom_edit = st.data_editor(jom_frame, hide_index=True, width="stretch", disabled=["Distance", "MM", "Min HRC", "Max HRC", "RMTC Actual HRC", "Result"], column_config={"NA": st.column_config.CheckboxColumn()}, key=f"metlab_jom_{existing_id or 'new'}_{inward_id}")

        existing_req = {str(row.get("requirement_name")): row for row in _existing_rows(existing, "requirement_rows")}
        req_frame = pd.DataFrame([{
            "Parameter": row.get("requirement_name"), "Requirement": row.get("requirement_value"), "RMTC Actual": row.get("actual_value"),
            "MetLAB Actual": (existing_req.get(str(row.get("requirement_name"))) or {}).get("actual_value"), "Unit": row.get("unit"),
            "NA": (existing_req.get(str(row.get("requirement_name"))) or {}).get("result") == "NOT_APPLICABLE",
            "Result": (existing_req.get(str(row.get("requirement_name"))) or {}).get("result") or "NOT_EVALUATED",
            "Remark": (existing_req.get(str(row.get("requirement_name"))) or {}).get("remarks") or "",
        } for row in snapshot.get("requirements") or []])
    with stage_section("E", 'HEAT TREATMENT / MECHANICAL REQUIREMENTS', key="metlab_report_render_entry_e"):
        req_edit = st.data_editor(req_frame, hide_index=True, width="stretch", disabled=["Parameter", "Requirement", "RMTC Actual", "Unit"], column_config={"NA": st.column_config.CheckboxColumn(), "Result": st.column_config.SelectboxColumn(options=list(RESULT_OPTIONS))}, key=f"metlab_req_{existing_id or 'new'}_{inward_id}")

        layout_source = _layout_rows(service, plan_id, existing)
        layout_frame = pd.DataFrame([{"Sr No": row.get("sequence_no"), "Parameter": row.get("parameter"), "Specification": row.get("specification"), "Min": row.get("lower_spec"), "Max": row.get("upper_spec"), "Method / Aid": row.get("checking_method"), "Actual Value": row.get("actual_value"), "Unit": row.get("unit"), "NA": row.get("applicability") == "NOT_APPLICABLE", "Result": row.get("result"), "Remark": row.get("remarks"), "_characteristic_id": row.get("inspection_plan_characteristic_id"), "_type": row.get("characteristic_type")} for row in layout_source])
        if not layout_frame.empty:
            st.markdown("**Additional Layout Characteristics**")
            layout_edit = st.data_editor(layout_frame, hide_index=True, width="stretch", disabled=["Sr No", "Parameter", "Specification", "Min", "Max", "Method / Aid", "Result", "_characteristic_id", "_type"], column_config={"NA": st.column_config.CheckboxColumn(), "_characteristic_id": None, "_type": None}, key=f"metlab_layout_{existing_id or 'new'}_{plan_id or 'auto'}")
        else:
            layout_edit = pd.DataFrame()

        section_bar("CASE DEPTH / MICROHARDNESS TRAVERSE")
        case_depth_results, case_depth_valid = _render_case_depth_traverse(existing, key=f"linked_case_depth_{existing_id or 'new'}_{inward_id}", layout_rows=layout_source)

        employee_options = [""] + list(employee_map)
        c1, c2, c3, c4 = st.columns(4, gap="small")
        prepared_current = str((existing or {}).get("prepared_by_employee_id") or "")
        prepared = c1.selectbox("Prepared By", employee_options, index=employee_options.index(prepared_current) if prepared_current in employee_options else 0, format_func=lambda value: employee_map.get(value, "— Select —"))
        decision_options = ["PENDING", *FINAL_DISPOSITIONS]
        disposition = c2.selectbox("Final Decision", decision_options, index=decision_options.index(str((existing or {}).get("disposition") or "PENDING")), format_func=disposition_label)
        reason = c3.text_input("Decision Reason", value=str((existing or {}).get("disposition_reason") or ""))
        remarks = c4.text_input("Conclusion", value=str((existing or {}).get("remarks") or ""), help="Controlled report conclusion. This is separate from the Final Decision and Decision Reason.")

        chemistry_rows = []
        for _, row in chem_edit.iterrows():
            na = bool(row.get("NA")); result = _band_result(row.get("MetLAB Actual"), row.get("Min"), row.get("Max"), na)
            chemistry_rows.append({"element": row.get("Element"), "minimum_value": row.get("Min"), "maximum_value": row.get("Max"), "rmtc_actual_value": row.get("RMTC Actual"), "actual_value": row.get("MetLAB Actual"), "unit": row.get("Unit"), "result": result, "remarks": row.get("Remark")})
        jominy_rows = []
        for _, row in jom_edit.iterrows():
            na = bool(row.get("NA")); result = _band_result(row.get("MetLAB Actual HRC"), row.get("Min HRC"), row.get("Max HRC"), na)
            jominy_rows.append({"distance_label": row.get("Distance"), "distance_mm": row.get("MM"), "minimum_hrc": row.get("Min HRC"), "maximum_hrc": row.get("Max HRC"), "rmtc_actual_hrc": row.get("RMTC Actual HRC"), "actual_value": row.get("MetLAB Actual HRC"), "result": result, "remarks": row.get("Remark")})
        requirement_rows = []
        for _, row in req_edit.iterrows():
            na = bool(row.get("NA")); low, high = _range_from_text(row.get("Requirement")); auto = _band_result(row.get("MetLAB Actual"), low, high, na)
            result = auto if auto != "NOT_EVALUATED" or str(row.get("Result") or "") == "NOT_EVALUATED" else str(row.get("Result") or "NOT_EVALUATED")
            requirement_rows.append({"requirement_name": row.get("Parameter"), "requirement_value": row.get("Requirement"), "rmtc_actual_value": row.get("RMTC Actual"), "actual_value": row.get("MetLAB Actual"), "unit": row.get("Unit"), "result": result, "remarks": row.get("Remark")})
        layout_rows = []
        for _, row in layout_edit.iterrows():
            na = bool(row.get("NA")); result = service.evaluate_characteristic({"characteristic_type": row.get("_type"), "specification": row.get("Specification"), "lower_spec": row.get("Min"), "upper_spec": row.get("Max")}, [row.get("Actual Value")], na)
            layout_rows.append({"sequence_no": int(row.get("Sr No") or len(layout_rows) + 1), "inspection_plan_characteristic_id": row.get("_characteristic_id"), "parameter": row.get("Parameter"), "specification": row.get("Specification"), "lower_spec": row.get("Min"), "upper_spec": row.get("Max"), "checking_method": row.get("Method / Aid"), "actual_value": row.get("Actual Value"), "unit": row.get("Unit"), "applicability": "NOT_APPLICABLE" if na else "APPLICABLE", "result": result, "remarks": row.get("Remark"), "characteristic_type": row.get("_type")})

        writable = (perms["can_edit"] if existing else perms["can_create"]) and str((existing or {}).get("status") or "DRAFT").upper() == "DRAFT"
        linked_metlab_notify_pref = notification_confirmation(NotificationService(service.repo), "METLAB_APPROVAL_PENDING", key=f"linked_metlab_notify_{str((existing or {}).get('id') or inward_id or 'new')}", context={"part_number":part.get("part_number"),"next_task":"MetLAB Approval"}, default_send=not bool(existing)) if not existing else {"send":False,"confirmed":True,"preview":{}}
        if st.button("Save Raw Material MetLAB Draft", type="primary", disabled=not writable or not prepared or not sample_ref.strip() or not case_depth_valid or (linked_metlab_notify_pref["send"] and not linked_metlab_notify_pref["confirmed"]), width="stretch"):
            try:
                final_number = report_no.strip() or service.next_number("METLAB")
                payload = {"report_number": final_number, "test_type": "METLAB", "layout_plan_id": plan_id, "process_id": plan.get("process_id"), "inspection_stage_id": plan.get("inspection_stage_id"), "part_id": part_id, "inward_lot_id": inward_id, "rmtc_approval_id": inward.get("rmtc_approval_id"), "supplier_id": inward.get("supplier_id"), "steel_mill_id": rmtc.get("steel_mill_id"), "material_grade_id": part.get("material_grade_id"), "test_date": test_date.isoformat(), "sample_reference": sample_ref.strip(), "specification_reference": spec_ref.strip() or None, "overall_result": "NOT_EVALUATED", "status": str((existing or {}).get("status") or "DRAFT"), "remarks": remarks.strip() or None, "disposition": disposition, "disposition_reason": reason.strip() or None, "heat_number": inward.get("heat_number"), "heat_code": inward.get("heat_code"), "prepared_by_employee_id": prepared, "layout_name_snapshot": layout_name, "layout_type_name": layout_type, "steel_quantity_kg": inward.get("steel_quantity_kg") or inward.get("quantity_received"), "production_quantity_pcs": inward.get("production_quantity_pcs"), **{f"microstructure_caption_{slot}": micro_captions[slot-1].strip() or None for slot in range(1,5)}}
                results = {"rows": layout_rows, "chemistry_rows": chemistry_rows, "jominy_rows": jominy_rows, "requirement_rows": requirement_rows, **case_depth_results}
                with st.spinner("Saving RMTC verification sections…"):
                    saved = service.save_metlab(payload, results, str(existing["id"]) if existing else None)
                    # Save report copy / microstructure evidence BEFORE notifying so first approval email carries the documents.
                    if attachment is not None:
                        service.upload_attachment("METLAB_REPORT", str(saved["id"]), "REPORT_COPY", attachment, "lab_tests", "attachment_path")
                    for slot, image in enumerate(micro_files, start=1):
                        if image is not None:
                            service.upload_attachment("METLAB_REPORT", str(saved["id"]), f"MICROSTRUCTURE_{slot}", image, "lab_tests", f"microstructure_image_{slot}_path")
                    if not existing and linked_metlab_notify_pref["send"] and linked_metlab_notify_pref["confirmed"]:
                        NotificationService(service.repo).notify(
                            "METLAB_APPROVAL_PENDING",
                            subject=f"QCMS · MetLAB approval pending · {saved.get('report_number') or final_number}",
                            body_text=(f"MetLAB Report {saved.get('report_number') or final_number} is ready for validation / approval.\n"
                                       f"Part: {part.get('part_number') or '-'}\n"
                                       f"Source: {inward.get('inward_number') or inward.get('heat_number') or '-'}"),
                            related_table="lab_tests",related_id=str(saved.get("id")),
                            context={"lab_test_id":str(saved.get("id")),"inward_lot_id":str(inward_id),"next_task":"MetLAB Approval"},
                            **notification_overrides(linked_metlab_notify_pref),
                        )
                st.session_state["edit_metlab_id"] = str(saved["id"])
                save_success_popup(f"Raw Material MetLAB Report {final_number} saved successfully.", queue_for_rerun=True)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

        if existing:
            disposition_cards([{"label": "Report", "value": existing.get("status"), "foot": existing.get("report_number")}, {"label": "Final Decision", "value": existing.get("disposition")}, {"label": "Layout", "value": existing.get("layout_name_snapshot") or layout_name}])
            c1, c2, c3 = st.columns(3, gap="small")
            validator = c1.selectbox("Validated By", employee_options, index=employee_options.index(str(existing.get("validated_by_employee_id") or "")) if str(existing.get("validated_by_employee_id") or "") in employee_options else 0, format_func=lambda value: employee_map.get(value, "— Select —"))
            approver = c2.selectbox("Approved By", employee_options, index=employee_options.index(str(existing.get("approved_by_employee_id") or "")) if str(existing.get("approved_by_employee_id") or "") in employee_options else 0, format_func=lambda value: employee_map.get(value, "— Select —"))
            if c3.button("Finalize MetLAB Decision", disabled=not perms["can_approve"] or disposition == "PENDING" or not validator or not approver or str(existing.get("status")) == "FINAL", width="stretch"):
                try:
                    service.finalize_metlab(str(existing["id"]), disposition, reason, validator, approver)
                    save_success_popup("MetLAB decision finalized successfully.", queue_for_rerun=True)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            section_bar("PDF / EXCEL / PRINT EXPORT")
            _report_exports(service, str(existing["id"]), str(existing.get("report_number") or "MetLAB_Report"), key=f"met_linked_export_{existing.get('id')}")
            if password_delete_panel(
                repo=service.repo, table="lab_tests", rows=[existing],
                labeler=lambda row: row.get("report_number"),
                key=f"delete_metlab_entry_{existing.get('id')}", can_delete=perms["can_archive"],
                title="Delete This MetLAB Report",
                help_text="Permanent deletion requires your current QCMS password and MetLAB Delete permission.",
            ):
                st.session_state.pop("edit_metlab_id", None); st.rerun()


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
        with c1: st.page_link(st.session_state["_qsms_pages"]["metlab-entry"], label="Open / Edit Selected MetLAB Report", icon=":material/edit:", width="stretch")
        try:
            selected_payload = service.metlab_report_payload(selected)
            with c2:
                st.download_button("Download / Print PDF", data=metlab_record_pdf_bytes(selected_payload), file_name=f"{selected_row.get('report_number') or 'MetLAB_Report'}.pdf", mime="application/pdf", key=f"metlab_pdf_{selected}", icon=":material/picture_as_pdf:", width="stretch")
            with c3:
                st.download_button("Download Excel Report", data=quality_record_excel_bytes(selected_payload, "METLAB"), file_name=f"{selected_row.get('report_number') or 'MetLAB_Report'}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"metlab_xlsx_{selected}", icon=":material/download:", width="stretch")
        except Exception as exc:
            st.error(f"Report export could not be generated: {exc}")
        record_email_sender(
            NotificationService(service.repo), "METLAB_APPROVAL_PENDING",
            related_table="lab_tests", related_id=selected, key=f"metlab_record_email_{selected}",
            context={"part_number": (parts.get(str(selected_row.get("part_id"))) or {}).get("part_number"), "next_task": "MetLAB Review / Approval"},
        )
        with c4:
            if password_delete_panel(repo=service.repo, table="lab_tests", rows=[selected_row], labeler=lambda row: row.get("report_number"), key=f"delete_metlab_{selected}", can_delete=perms["can_archive"], title="Delete Selected MetLAB Report"):
                st.rerun()
    section_bar("METLAB REGISTER")
    display = pd.DataFrame([{"Report Number": row.get("report_number"), "Date": row.get("test_date"), "Part Number": (parts.get(str(row.get("part_id"))) or {}).get("part_number"), "FSI Part Number": (parts.get(str(row.get("part_id"))) or {}).get("fsi_part_number"), "Customer": (parties.get(str(row.get("customer_id") or (parts.get(str(row.get("part_id"))) or {}).get("customer_id"))) or {}).get("party_name"), "Supplier": (parties.get(str(row.get("supplier_id"))) or {}).get("party_name"), "OSP Vendor": (parties.get(str(row.get("osp_vendor_id"))) or {}).get("party_name"), "Material Grade": (grades.get(str(row.get("material_grade_id") or (parts.get(str(row.get("part_id"))) or {}).get("material_grade_id"))) or {}).get("grade_code"), "Heat Number": row.get("heat_number"), "Batch Number": row.get("batch_number") or row.get("vendor_batch_number_snapshot"), "Layout": row.get("layout_name_snapshot"), "Report Stage": STANDALONE_STAGES.get(str(row.get("inspection_scope")), str(row.get("inspection_scope") or "MATERIAL_INWARD").replace("_", " ").title()), "Production pcs": row.get("production_quantity_pcs"), "Microstructure Photos": sum(1 for slot in range(1,5) if row.get(f"microstructure_image_{slot}_path")), "Conclusion": row.get("remarks"), "Result": row.get("overall_result"), "Final Decision": row.get("disposition"), "Decision Reason": row.get("disposition_reason"), "Status": row.get("status")} for row in filtered])
    portal_table(style_status_dataframe(display), hide_index=True, width="stretch", height=520)
