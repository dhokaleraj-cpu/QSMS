from __future__ import annotations

import re
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.delete_service import password_delete_panel
from core.inspection_service import FINAL_DISPOSITIONS, RESULT_OPTIONS, InspectionService
from core.reporting import metlab_record_pdf_bytes
from core.ui import disposition_cards, disposition_label, page_header, section_bar, style_status_dataframe, subpage_navigation, template_download_row


def _maps(service: InspectionService):
    parts = {str(row["id"]): row for row in service.parts()}
    parties = {str(row["id"]): row for row in service.parties()}
    processes = {str(row["id"]): row for row in service.processes()}
    stages = {str(row["id"]): row for row in service.stages()}
    employees = {str(row["id"]): f"{row.get('employee_code')} · {row.get('first_name')} {row.get('last_name')}" for row in service.employees()}
    return parts, parties, processes, stages, employees


def _inward_label(row: dict, parts: dict[str, dict], parties: dict[str, dict]) -> str:
    part = parts.get(str(row.get("part_id"))) or {}
    supplier = parties.get(str(row.get("supplier_id"))) or {}
    return (
        f"{row.get('inward_number')} · {part.get('part_number')} · {supplier.get('party_name')} · "
        f"Heat {row.get('heat_number')} · Steel {float(row.get('steel_quantity_kg') or row.get('quantity_received') or 0):,.3f} kg · "
        f"Production {float(row.get('production_quantity_pcs') or 0):,.0f} pcs"
    )


def _pending_frame(rows: list[dict], parts: dict[str, dict], parties: dict[str, dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Inward": row.get("inward_number"),
        "Date": row.get("inward_date"),
        "Supplier": (parties.get(str(row.get("supplier_id"))) or {}).get("party_name"),
        "Part Number": (parts.get(str(row.get("part_id"))) or {}).get("part_number"),
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


def render_entry() -> None:
    subpage_navigation(("inspection-home", "Inspections", ":material/biotech:"), ("inward-records", "Material Inward", ":material/input:"), ("metlab-records", "MetLAB Records", ":material/table_view:"))
    page_header("Raw Material MetLAB Inspection Report", context="RMTC worksheet verification")
    template_download_row([("MetLAB_Report_Layout_Template.xlsx", "Download MetLAB Report Template")], key_prefix="metlab_report")
    service = InspectionService(); perms = current_permissions("METLAB_REPORT")
    parts, parties, processes, stages, employee_map = _maps(service)
    pending_queue = [row for row in service.inspection_queue() if row.get("metlab_pending")]
    section_bar("METLAB PENDING LIST")
    if pending_queue:
        st.dataframe(
            style_status_dataframe(_pending_frame(pending_queue, parts, parties)),
            hide_index=True, width="stretch", height=min(300, 84 + 38 * len(pending_queue)),
        )
    else:
        st.success("No Metlab inspections are pending.")
    inward_rows = service.inward_lots()
    if not inward_rows:
        st.warning("No Accepted or Accepted Under Reserve Material Inward is available.")
        return

    existing_id = str(st.session_state.get("edit_metlab_id") or "")
    existing = service.get_metlab(existing_id) if existing_id else None
    inward_map = {str(row["id"]): _inward_label(row, parts, parties) for row in inward_rows}
    current_inward = str((existing or {}).get("inward_lot_id") or st.session_state.get("inspection_inward_id") or next(iter(inward_map)))
    inward_id = st.selectbox("Material Inward / Part / Supplier / Quantity", list(inward_map), index=list(inward_map).index(current_inward) if current_inward in inward_map else 0, format_func=lambda value: inward_map[value], disabled=bool(existing))
    inward = next(row for row in inward_rows if str(row["id"]) == inward_id)
    part_id = str(inward.get("part_id")); part = parts.get(part_id) or {}
    snapshot = service.rmtc_material_snapshot(inward)
    rmtc = snapshot.get("rmtc") or {}; grade = snapshot.get("grade") or {}; supplier = snapshot.get("supplier") or {}; steel_mill = snapshot.get("steel_mill") or {}

    all_plans = service.plans("METLAB", part_id, approved_only=True)
    plan_id: str | None = None; plan: dict = {}
    if all_plans:
        plan_map = {str(row["id"]): f"{row.get('layout_name')} · {row.get('plan_number')} Rev {row.get('revision')}" for row in all_plans}
        recommended = service.ranked_plans("METLAB", part_id)[0]
        selection_mode = st.radio("Layout Selection", ["Automatic", "Manual"], horizontal=True, disabled=bool(existing))
        if existing:
            plan_id = str(existing.get("layout_plan_id") or recommended.get("id"))
        elif selection_mode == "Automatic":
            plan_id = str(recommended["id"]); st.info(f"Automatically selected: {plan_map[plan_id]}")
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

    c1, c2, c3, c4, c5 = st.columns(5, gap="small")
    report_no = c1.text_input("Report Number", value=str((existing or {}).get("report_number") or ""), placeholder="Auto on save")
    test_date = c2.date_input("Test Date", value=date.fromisoformat(str((existing or {}).get("test_date"))[:10]) if (existing or {}).get("test_date") else date.today(), format="DD-MM-YYYY")
    c3.text_input("Part Number", value=str(part.get("part_number") or ""), disabled=True)
    c4.text_input("Heat Number", value=str(inward.get("heat_number") or ""), disabled=True)
    c5.text_input("Heat Code", value=str(inward.get("heat_code") or ""), disabled=True)
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

    section_bar("MICROSTRUCTURE PHOTOS", "Upload up to four microstructure images for the selected heat and Part Number.")
    micro_cols = st.columns(4, gap="small")
    micro_files = []
    micro_captions = []
    for slot, column in enumerate(micro_cols, start=1):
        with column:
            existing_path = str((existing or {}).get(f"microstructure_image_{slot}_path") or "")
            if existing_path:
                st.caption(f"Photo {slot} already uploaded")
            micro_files.append(st.file_uploader(f"Microstructure Photo {slot}", type=["png", "jpg", "jpeg"], key=f"microstructure_{slot}_{existing_id or 'new'}"))
            micro_captions.append(st.text_input(f"Photo {slot} Caption", value=str((existing or {}).get(f"microstructure_caption_{slot}") or ""), key=f"micro_caption_{slot}_{existing_id or 'new'}"))

    existing_chem = {str(row.get("element")): row for row in _existing_rows(existing, "chemistry_rows")}
    chem_frame = pd.DataFrame([{
        "Element": row.get("element"), "Min": row.get("minimum_value"), "Max": row.get("maximum_value"),
        "RMTC Actual": row.get("actual_value"), "MetLAB Actual": (existing_chem.get(str(row.get("element"))) or {}).get("actual_value"),
        "Unit": row.get("unit") or "%", "NA": (existing_chem.get(str(row.get("element"))) or {}).get("result") == "NOT_APPLICABLE",
        "Result": (existing_chem.get(str(row.get("element"))) or {}).get("result") or "NOT_EVALUATED",
        "Remark": (existing_chem.get(str(row.get("element"))) or {}).get("remarks") or "",
    } for row in snapshot.get("chemistry") or []])
    section_bar("CHEMICAL COMPOSITION")
    chem_edit = st.data_editor(chem_frame, hide_index=True, width="stretch", disabled=["Element", "Min", "Max", "RMTC Actual", "Unit", "Result"], column_config={"NA": st.column_config.CheckboxColumn()}, key=f"metlab_chem_{existing_id or 'new'}_{inward_id}")

    existing_jom = {str(row.get("distance_label")): row for row in _existing_rows(existing, "jominy_rows")}
    jom_frame = pd.DataFrame([{
        "Distance": row.get("distance_label"), "MM": row.get("distance_mm"), "Min HRC": row.get("minimum_hrc"), "Max HRC": row.get("maximum_hrc"),
        "RMTC Actual HRC": row.get("actual_hrc"), "MetLAB Actual HRC": (existing_jom.get(str(row.get("distance_label"))) or {}).get("actual_value"),
        "NA": (existing_jom.get(str(row.get("distance_label"))) or {}).get("result") == "NOT_APPLICABLE",
        "Result": (existing_jom.get(str(row.get("distance_label"))) or {}).get("result") or "NOT_EVALUATED",
        "Remark": (existing_jom.get(str(row.get("distance_label"))) or {}).get("remarks") or "",
    } for row in snapshot.get("jominy") or []])
    section_bar("JOMINY HARDENABILITY")
    jom_edit = st.data_editor(jom_frame, hide_index=True, width="stretch", disabled=["Distance", "MM", "Min HRC", "Max HRC", "RMTC Actual HRC", "Result"], column_config={"NA": st.column_config.CheckboxColumn()}, key=f"metlab_jom_{existing_id or 'new'}_{inward_id}")

    existing_req = {str(row.get("requirement_name")): row for row in _existing_rows(existing, "requirement_rows")}
    req_frame = pd.DataFrame([{
        "Parameter": row.get("requirement_name"), "Requirement": row.get("requirement_value"), "RMTC Actual": row.get("actual_value"),
        "MetLAB Actual": (existing_req.get(str(row.get("requirement_name"))) or {}).get("actual_value"), "Unit": row.get("unit"),
        "NA": (existing_req.get(str(row.get("requirement_name"))) or {}).get("result") == "NOT_APPLICABLE",
        "Result": (existing_req.get(str(row.get("requirement_name"))) or {}).get("result") or "NOT_EVALUATED",
        "Remark": (existing_req.get(str(row.get("requirement_name"))) or {}).get("remarks") or "",
    } for row in snapshot.get("requirements") or []])
    section_bar("HEAT TREATMENT / MECHANICAL REQUIREMENTS")
    req_edit = st.data_editor(req_frame, hide_index=True, width="stretch", disabled=["Parameter", "Requirement", "RMTC Actual", "Unit"], column_config={"NA": st.column_config.CheckboxColumn(), "Result": st.column_config.SelectboxColumn(options=list(RESULT_OPTIONS))}, key=f"metlab_req_{existing_id or 'new'}_{inward_id}")

    layout_source = _layout_rows(service, plan_id, existing)
    layout_frame = pd.DataFrame([{"Sr No": row.get("sequence_no"), "Parameter": row.get("parameter"), "Specification": row.get("specification"), "Min": row.get("lower_spec"), "Max": row.get("upper_spec"), "Method / Aid": row.get("checking_method"), "Actual Value": row.get("actual_value"), "Unit": row.get("unit"), "NA": row.get("applicability") == "NOT_APPLICABLE", "Result": row.get("result"), "Remark": row.get("remarks"), "_characteristic_id": row.get("inspection_plan_characteristic_id"), "_type": row.get("characteristic_type")} for row in layout_source])
    if not layout_frame.empty:
        section_bar("ADDITIONAL LAYOUT CHARACTERISTICS")
        layout_edit = st.data_editor(layout_frame, hide_index=True, width="stretch", disabled=["Sr No", "Parameter", "Specification", "Min", "Max", "Method / Aid", "Result", "_characteristic_id", "_type"], column_config={"NA": st.column_config.CheckboxColumn(), "_characteristic_id": None, "_type": None}, key=f"metlab_layout_{existing_id or 'new'}_{plan_id or 'auto'}")
    else:
        layout_edit = pd.DataFrame()

    employee_options = [""] + list(employee_map)
    c1, c2, c3, c4 = st.columns(4, gap="small")
    prepared_current = str((existing or {}).get("prepared_by_employee_id") or "")
    prepared = c1.selectbox("Prepared By", employee_options, index=employee_options.index(prepared_current) if prepared_current in employee_options else 0, format_func=lambda value: employee_map.get(value, "— Select —"))
    decision_options = ["PENDING", *FINAL_DISPOSITIONS]
    disposition = c2.selectbox("Validation Decision", decision_options, index=decision_options.index(str((existing or {}).get("disposition") or "PENDING")), format_func=disposition_label)
    reason = c3.text_input("Hold / Reserve / Rejection / Override Reason", value=str((existing or {}).get("disposition_reason") or ""))
    remarks = c4.text_input("Report Remarks", value=str((existing or {}).get("remarks") or ""))

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
        na = bool(row.get("NA")); result = service.evaluate_characteristic({"characteristic_type": row.get("_type"), "lower_spec": row.get("Min"), "upper_spec": row.get("Max")}, [row.get("Actual Value")], na)
        layout_rows.append({"sequence_no": int(row.get("Sr No") or len(layout_rows) + 1), "inspection_plan_characteristic_id": row.get("_characteristic_id"), "parameter": row.get("Parameter"), "specification": row.get("Specification"), "lower_spec": row.get("Min"), "upper_spec": row.get("Max"), "checking_method": row.get("Method / Aid"), "actual_value": row.get("Actual Value"), "unit": row.get("Unit"), "applicability": "NOT_APPLICABLE" if na else "APPLICABLE", "result": result, "remarks": row.get("Remark"), "characteristic_type": row.get("_type")})

    writable = (perms["can_edit"] if existing else perms["can_create"]) and str((existing or {}).get("status") or "DRAFT") != "FINAL"
    if st.button("Save Raw Material MetLAB Draft", type="primary", disabled=not writable or not prepared or not sample_ref.strip(), width="stretch"):
        try:
            final_number = report_no.strip() or service.next_number("METLAB")
            payload = {"report_number": final_number, "test_type": "METLAB", "layout_plan_id": plan_id, "process_id": plan.get("process_id"), "inspection_stage_id": plan.get("inspection_stage_id"), "part_id": part_id, "inward_lot_id": inward_id, "rmtc_approval_id": inward.get("rmtc_approval_id"), "supplier_id": inward.get("supplier_id"), "steel_mill_id": rmtc.get("steel_mill_id"), "material_grade_id": part.get("material_grade_id"), "test_date": test_date.isoformat(), "sample_reference": sample_ref.strip(), "specification_reference": spec_ref.strip() or None, "overall_result": "NOT_EVALUATED", "status": str((existing or {}).get("status") or "DRAFT"), "remarks": remarks.strip() or None, "disposition": str((existing or {}).get("disposition") or "PENDING"), "heat_number": inward.get("heat_number"), "heat_code": inward.get("heat_code"), "prepared_by_employee_id": prepared, "layout_name_snapshot": layout_name, "layout_type_name": layout_type, "steel_quantity_kg": inward.get("steel_quantity_kg") or inward.get("quantity_received"), "production_quantity_pcs": inward.get("production_quantity_pcs"), **{f"microstructure_caption_{slot}": micro_captions[slot-1].strip() or None for slot in range(1,5)}}
            results = {"rows": layout_rows, "chemistry_rows": chemistry_rows, "jominy_rows": jominy_rows, "requirement_rows": requirement_rows}
            with st.spinner("Saving RMTC verification sections…"):
                saved = service.save_metlab(payload, results, str(existing["id"]) if existing else None)
                if attachment is not None:
                    service.upload_attachment("METLAB_REPORT", str(saved["id"]), "REPORT_COPY", attachment, "lab_tests", "attachment_path")
                for slot, image in enumerate(micro_files, start=1):
                    if image is not None:
                        service.upload_attachment("METLAB_REPORT", str(saved["id"]), f"MICROSTRUCTURE_{slot}", image, "lab_tests", f"microstructure_image_{slot}_path")
            st.session_state["edit_metlab_id"] = str(saved["id"])
            st.success(f"Raw Material MetLAB Report {final_number} saved.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    if existing:
        disposition_cards([{"label": "Report", "value": existing.get("status"), "foot": existing.get("report_number")}, {"label": "Decision", "value": existing.get("disposition")}, {"label": "Layout", "value": existing.get("layout_name_snapshot") or layout_name}])
        c1, c2, c3 = st.columns(3, gap="small")
        validator = c1.selectbox("Validated By", employee_options, index=employee_options.index(str(existing.get("validated_by_employee_id") or "")) if str(existing.get("validated_by_employee_id") or "") in employee_options else 0, format_func=lambda value: employee_map.get(value, "— Select —"))
        approver = c2.selectbox("Approved By", employee_options, index=employee_options.index(str(existing.get("approved_by_employee_id") or "")) if str(existing.get("approved_by_employee_id") or "") in employee_options else 0, format_func=lambda value: employee_map.get(value, "— Select —"))
        if c3.button("Finalize MetLAB Decision", disabled=not perms["can_approve"] or disposition == "PENDING" or not validator or not approver or str(existing.get("status")) == "FINAL", width="stretch"):
            try:
                service.finalize_metlab(str(existing["id"]), disposition, reason, validator, approver)
                st.success("MetLAB decision finalized.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def render_records() -> None:
    subpage_navigation(("inspection-home", "Inspections", ":material/biotech:"), ("metlab-entry", "New / Edit Report", ":material/edit_note:"))
    page_header("MetLAB Report Records", context="Select before action")
    service = InspectionService(); perms = current_permissions("METLAB_REPORT"); parts, _, _, _, _ = _maps(service)
    rows = service.metlab_reports(); search = st.text_input("Search Report, Part, Heat or Inward")
    filtered = [row for row in rows if not search or search.casefold() in " ".join(str(row.get(key) or "") for key in ("report_number", "heat_number", "heat_code", "sample_reference", "remarks", "layout_name_snapshot")).casefold()]
    if filtered:
        labels = {str(row["id"]): f"{row.get('report_number')} · Heat {row.get('heat_number')} · {row.get('layout_name_snapshot') or 'Layout'} · {disposition_label(row.get('disposition'))}" for row in filtered}
        selected = st.selectbox("Select MetLAB Report", list(labels), format_func=lambda value: labels[value]); selected_row = next(row for row in filtered if str(row["id"]) == selected); st.session_state["edit_metlab_id"] = selected
        c1, c2, c3 = st.columns(3, gap="small")
        with c1: st.page_link(st.session_state["_qsms_pages"]["metlab-entry"], label="Open Selected Report", icon=":material/edit:", width="stretch")
        with c2:
            try:
                pdf_bytes = metlab_record_pdf_bytes(service.metlab_report_payload(selected))
                st.download_button("Download MetLAB Report PDF", data=pdf_bytes, file_name=f"{selected_row.get('report_number') or 'MetLAB_Report'}.pdf", mime="application/pdf", key=f"metlab_pdf_{selected}", width="stretch")
            except Exception as exc:
                st.error(f"PDF could not be generated: {exc}")
        with c3:
            if password_delete_panel(repo=service.repo, table="lab_tests", rows=[selected_row], labeler=lambda row: row.get("report_number"), key=f"delete_metlab_{selected}", can_delete=perms["can_archive"], title="Delete Selected MetLAB Report"):
                st.rerun()
    section_bar("METLAB REGISTER")
    display = pd.DataFrame([{"Report Number": row.get("report_number"), "Date": row.get("test_date"), "Part Number": (parts.get(str(row.get("part_id"))) or {}).get("part_number"), "Heat Number": row.get("heat_number"), "Layout": row.get("layout_name_snapshot"), "Section": row.get("layout_type_name"), "Steel kg": row.get("steel_quantity_kg"), "Production pcs": row.get("production_quantity_pcs"), "Microstructure Photos": sum(1 for slot in range(1,5) if row.get(f"microstructure_image_{slot}_path")), "Result": row.get("overall_result"), "Decision": row.get("disposition"), "Status": row.get("status")} for row in filtered])
    st.dataframe(style_status_dataframe(display), hide_index=True, width="stretch", height=520)
