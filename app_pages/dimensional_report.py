from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.delete_service import password_delete_panel
from core.inspection_service import FINAL_DISPOSITIONS, InspectionService
from core.reporting import dimensional_record_pdf_bytes
from core.ui import disposition_cards, disposition_label, page_header, save_success_popup, section_bar, style_status_dataframe, subpage_navigation, template_download_row


def _maps(service: InspectionService):
    parts = {str(row["id"]): row for row in service.parts()}
    parties = {str(row["id"]): row for row in service.parties()}
    processes = {str(row["id"]): row for row in service.processes()}
    stages = {str(row["id"]): row for row in service.stages()}
    employees = service.employees()
    employee_map = {str(row["id"]): f"{row.get('employee_code')} · {row.get('first_name')} {row.get('last_name')}" for row in employees}
    return parts, parties, processes, stages, employee_map


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
        "Status": row.get("dimensional_queue_status"),
    } for row in rows])


def _report_rows(service: InspectionService, plan_id: str, report_id: str | None, sample_size: int, section_name: str) -> list[dict]:
    if report_id:
        existing = service.dimensional_results(report_id)
        if existing:
            chars = {str(row["id"]): row for row in service.plan_characteristics(plan_id)}
            return [{
                "sequence_no": row.get("sequence_no") or position,
                "inspection_plan_characteristic_id": row.get("inspection_plan_characteristic_id"),
                "characteristic_no": row.get("characteristic_no"), "characteristic": row.get("characteristic"),
                "specification": row.get("specification"), "lower_spec": row.get("lower_spec"), "upper_spec": row.get("upper_spec"),
                "unit": row.get("unit"), "checking_aid": row.get("checking_aid"), "observations": row.get("observations") or [],
                "result": row.get("result"), "remarks": row.get("remarks"), "applicability": row.get("applicability"),
                "report_section": row.get("report_section") or section_name,
                "characteristic_type": (chars.get(str(row.get("inspection_plan_characteristic_id"))) or {}).get("characteristic_type") or "VARIABLE",
            } for position, row in enumerate(existing, start=1)]
    return [{
        "sequence_no": row.get("sequence_no") or position, "inspection_plan_characteristic_id": row.get("id"),
        "characteristic_no": row.get("characteristic_no"), "characteristic": row.get("characteristic"),
        "specification": row.get("specification"), "lower_spec": row.get("lower_spec"), "upper_spec": row.get("upper_spec"),
        "unit": row.get("unit"), "checking_aid": row.get("checking_aid_text") or row.get("checking_method"),
        "observations": [""] * int(row.get("sample_size") or sample_size), "result": "NOT_EVALUATED", "remarks": "",
        "applicability": "APPLICABLE", "report_section": row.get("report_section") or section_name,
        "characteristic_type": row.get("characteristic_type") or "VARIABLE",
    } for position, row in enumerate(service.plan_characteristics(plan_id), start=1)]


def _editor_frame(rows: list[dict], sample_size: int) -> pd.DataFrame:
    output = []
    for row in rows:
        observations = list(row.get("observations") or []) + [""] * sample_size
        item = {
            "Section": row.get("report_section"), "Sr No": row.get("characteristic_no") or row.get("sequence_no"),
            "Parameter": row.get("characteristic"), "Specification": row.get("specification"),
            "Min": row.get("lower_spec"), "Max": row.get("upper_spec"), "Checking Aid": row.get("checking_aid"),
            "NA": row.get("applicability") == "NOT_APPLICABLE", "Result": row.get("result") or "NOT_EVALUATED",
            "Remark": row.get("remarks") or "", "_sequence": row.get("sequence_no"),
            "_characteristic_id": row.get("inspection_plan_characteristic_id"), "_type": row.get("characteristic_type"),
            "_unit": row.get("unit"),
        }
        for index in range(sample_size):
            item[f"Actual {index + 1}"] = observations[index]
        output.append(item)
    return pd.DataFrame(output)


def render_entry() -> None:
    subpage_navigation(("inspection-home", "Inspections", ":material/biotech:"), ("inward-records", "Material Inward", ":material/input:"), ("dimensional-records", "Dimensional Records", ":material/table_view:"))
    page_header("Dimensional Inspection Report", context="Automatic part/process/stage layout")
    template_download_row([("Dimensional_Inspection_Report_Template.xlsx", "Download Dimensional Report Template")], key_prefix="dimensional_report")
    service = InspectionService(); perms = current_permissions("DIMENSIONAL_REPORT")
    parts, parties, processes, stages, employee_map = _maps(service)
    pending_queue = [row for row in service.inspection_queue() if row.get("dimensional_pending")]
    section_bar("DIMENSIONAL PENDING LIST")
    if pending_queue:
        st.dataframe(
            style_status_dataframe(_pending_frame(pending_queue, parts, parties)),
            hide_index=True, width="stretch", height=min(300, 84 + 38 * len(pending_queue)),
        )
    else:
        st.success("No Dimensional inspections are pending.")
    inward_rows = service.inward_lots()
    if not inward_rows:
        st.warning("No Accepted or Accepted Under Reserve Material Inward is available.")
        return

    existing_id = str(st.session_state.get("edit_dimensional_id") or "")
    existing = service.get_dimensional(existing_id) if existing_id else None
    inward_map = {str(row["id"]): _inward_label(row, parts, parties) for row in inward_rows}
    current_inward = str((existing or {}).get("inward_lot_id") or st.session_state.get("inspection_inward_id") or next(iter(inward_map)))
    inward_id = st.selectbox("Material Inward / Part / Supplier / Quantity", list(inward_map), index=list(inward_map).index(current_inward) if current_inward in inward_map else 0, format_func=lambda value: inward_map[value], disabled=bool(existing))
    inward = next(row for row in inward_rows if str(row["id"]) == inward_id)
    part_id = str(inward.get("part_id")); part = parts.get(part_id) or {}

    all_plans = service.plans("DIMENSIONAL", part_id, approved_only=True)
    if not all_plans:
        st.warning("No Approved Dimensional Layout is configured for this Part Number.")
        st.page_link(st.session_state["_qsms_pages"]["inspection-layout-entry"], label="Create / Approve Dimensional Layout", icon=":material/add:", width="stretch")
        return

    selection_mode = st.radio("Layout Selection", ["Automatic", "Manual"], horizontal=True, disabled=bool(existing), help="Automatic uses the approved Part + Process + Inspection Stage layout. Manual allows an approved alternative.")
    plan_map = {str(row["id"]): f"{row.get('layout_name')} · {row.get('plan_number')} Rev {row.get('revision')}" for row in all_plans}
    recommended = service.ranked_plans("DIMENSIONAL", part_id)[0]
    if existing:
        plan_id = str(existing.get("inspection_plan_id") or recommended.get("id"))
    elif selection_mode == "Automatic":
        plan_id = str(recommended["id"])
        st.info(f"Automatically selected: {plan_map[plan_id]}")
    else:
        plan_id = st.selectbox("Approved Layout Plan", list(plan_map), format_func=lambda value: plan_map[value])
    if selection_mode == "Automatic" or existing:
        st.selectbox("Approved Layout Plan", [plan_id], format_func=lambda value: plan_map.get(value, value), disabled=True)
    plan = next(row for row in all_plans if str(row["id"]) == plan_id)
    section_name = str(plan.get("layout_type") or "DIMENSIONAL")

    c1, c2, c3, c4 = st.columns(4, gap="small")
    c1.text_input("Layout Name", value=str(plan.get("layout_name") or ""), disabled=True)
    c2.text_input("Section / Layout Type", value=section_name, disabled=True)
    c3.text_input("Process", value=str((processes.get(str(plan.get("process_id"))) or {}).get("process_name") or "Not assigned"), disabled=True)
    c4.text_input("Inspection Stage", value=str((stages.get(str(plan.get("inspection_stage_id"))) or {}).get("stage_name") or "Not assigned"), disabled=True)

    sample_size = min(max(int((existing or {}).get("sample_size") or plan.get("default_sample_size") or 1), 1), 10)
    c1, c2, c3, c4, c5 = st.columns(5, gap="small")
    report_no = c1.text_input("Report Number", value=str((existing or {}).get("report_number") or ""), placeholder="Auto on first save")
    inspection_date = c2.date_input("Inspection Date", value=date.fromisoformat(str((existing or {}).get("inspection_date"))[:10]) if (existing or {}).get("inspection_date") else date.today(), format="DD-MM-YYYY")
    c3.text_input("Part Number", value=str(part.get("part_number") or ""), disabled=True)
    c4.text_input("Heat Number", value=str(inward.get("heat_number") or ""), disabled=True)
    c5.text_input("Heat Code", value=str(inward.get("heat_code") or ""), disabled=True)
    c1, c2, c3, c4, c5 = st.columns(5, gap="small")
    c1.text_input("Supplier", value=str((parties.get(str(inward.get("supplier_id"))) or {}).get("party_name") or ""), disabled=True)
    c2.text_input("Steel Quantity (kg)", value=f"{float(inward.get('steel_quantity_kg') or inward.get('quantity_received') or 0):,.3f}", disabled=True)
    c3.text_input("Production Quantity (pcs)", value=f"{float(inward.get('production_quantity_pcs') or 0):,.0f}", disabled=True)
    lot_qty = c4.number_input("Lot Quantity (pcs)", min_value=0.0, value=float((existing or {}).get("lot_quantity") or inward.get("production_quantity_pcs") or 0), step=1.0)
    sample_size = c5.number_input("Sample Size", min_value=1, max_value=10, value=sample_size, step=1, disabled=bool(existing))

    rows = _report_rows(service, plan_id, str(existing.get("id")) if existing else None, int(sample_size), section_name)
    frame = _editor_frame(rows, int(sample_size))
    section_bar("LAYOUT CHARACTERISTICS")
    edited = st.data_editor(frame, hide_index=True, width="stretch", height=min(620, max(260, 90 + len(frame) * 32)), disabled=["Section", "Sr No", "Parameter", "Specification", "Min", "Max", "Checking Aid", "Result", "_sequence", "_characteristic_id", "_type", "_unit"], column_config={"NA": st.column_config.CheckboxColumn(), "_sequence": None, "_characteristic_id": None, "_type": None, "_unit": None}, key=f"dimensional_grid_{existing_id or 'new'}_{plan_id}")

    c1, c2 = st.columns([3, 1], gap="small")
    remarks = c1.text_area("Report Remarks", value=str((existing or {}).get("remarks") or ""), height=52)
    attachment = c2.file_uploader("Attach Report", type=["pdf", "xlsx", "xls", "png", "jpg", "jpeg"], key=f"dim_attachment_{existing_id or 'new'}")

    employee_options = [""] + list(employee_map)
    c1, c2, c3 = st.columns(3, gap="small")
    prepared_current = str((existing or {}).get("prepared_by_employee_id") or "")
    prepared = c1.selectbox("Inspected / Prepared By", employee_options, index=employee_options.index(prepared_current) if prepared_current in employee_options else 0, format_func=lambda value: employee_map.get(value, "— Select —"))
    disposition_options = ["PENDING", *FINAL_DISPOSITIONS]
    disposition = c2.selectbox("Validation Decision", disposition_options, index=disposition_options.index(str((existing or {}).get("disposition") or "PENDING")), format_func=disposition_label)
    reason = c3.text_input("Hold / Reserve / Rejection Reason", value=str((existing or {}).get("disposition_reason") or ""))

    saved_rows = []
    for _, row in edited.iterrows():
        observations = [row.get(f"Actual {index + 1}") for index in range(int(sample_size))]
        na = bool(row.get("NA"))
        result = service.evaluate_characteristic({"characteristic_type": row.get("_type"), "lower_spec": row.get("Min"), "upper_spec": row.get("Max")}, observations, na)
        saved_rows.append({"sequence_no": int(row.get("_sequence") or len(saved_rows) + 1), "inspection_plan_characteristic_id": row.get("_characteristic_id"), "characteristic_no": row.get("Sr No"), "characteristic": row.get("Parameter"), "specification": row.get("Specification"), "lower_spec": row.get("Min"), "upper_spec": row.get("Max"), "unit": row.get("_unit"), "checking_aid": row.get("Checking Aid"), "observations": observations, "result": result, "remarks": row.get("Remark"), "applicability": "NOT_APPLICABLE" if na else "APPLICABLE", "report_section": section_name})

    writable = (perms["can_edit"] if existing else perms["can_create"]) and str((existing or {}).get("status") or "DRAFT") != "FINAL"
    if st.button("Save Dimensional Report Draft", type="primary", disabled=not writable or not prepared, width="stretch"):
        try:
            final_number = report_no.strip() or service.next_number("DIMENSIONAL")
            payload = {"report_number": final_number, "report_type": "DIMENSIONAL", "inspection_plan_id": plan_id, "inspection_stage_id": plan.get("inspection_stage_id"), "process_id": plan.get("process_id"), "part_id": part_id, "inward_lot_id": inward_id, "inspection_date": inspection_date.isoformat(), "sample_size": int(sample_size), "accepted_quantity": 0, "rejected_quantity": 0, "inspector": employee_map.get(prepared), "overall_result": "NOT_EVALUATED", "status": str((existing or {}).get("status") or "DRAFT"), "remarks": remarks.strip() or None, "disposition": str((existing or {}).get("disposition") or "PENDING"), "heat_number": inward.get("heat_number"), "heat_code": inward.get("heat_code"), "lot_quantity": lot_qty, "supplier_id": inward.get("supplier_id"), "drawing_number": part.get("drawing_number"), "drawing_revision": part.get("drawing_revision"), "prepared_by_employee_id": prepared, "source_layout_revision": plan.get("revision"), "layout_name_snapshot": plan.get("layout_name"), "layout_type_name": section_name, "steel_quantity_kg": inward.get("steel_quantity_kg") or inward.get("quantity_received"), "production_quantity_pcs": inward.get("production_quantity_pcs")}
            with st.spinner("Saving report and layout characteristics…"):
                saved = service.save_dimensional(payload, saved_rows, str(existing["id"]) if existing else None)
                if attachment is not None:
                    service.upload_attachment("DIMENSIONAL_REPORT", str(saved["id"]), "REPORT_COPY", attachment, "inspection_reports", "attachment_path")
            st.session_state["edit_dimensional_id"] = str(saved["id"])
            save_success_popup(f"Dimensional Report {final_number} saved successfully.", queue_for_rerun=True)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    if existing:
        disposition_cards([{"label": "Report", "value": existing.get("status"), "foot": existing.get("report_number")}, {"label": "Decision", "value": existing.get("disposition")}, {"label": "Layout", "value": existing.get("layout_name_snapshot") or plan.get("layout_name")}])
        c1, c2, c3 = st.columns(3, gap="small")
        validator = c1.selectbox("Validated By", employee_options, index=employee_options.index(str(existing.get("validated_by_employee_id") or "")) if str(existing.get("validated_by_employee_id") or "") in employee_options else 0, format_func=lambda value: employee_map.get(value, "— Select —"))
        approver = c2.selectbox("Approved By", employee_options, index=employee_options.index(str(existing.get("approved_by_employee_id") or "")) if str(existing.get("approved_by_employee_id") or "") in employee_options else 0, format_func=lambda value: employee_map.get(value, "— Select —"))
        if c3.button("Finalize Dimensional Decision", disabled=not perms["can_approve"] or disposition == "PENDING" or not validator or not approver or str(existing.get("status")) == "FINAL", width="stretch"):
            try:
                service.finalize_dimensional(str(existing["id"]), disposition, reason, validator, approver)
                save_success_popup("Dimensional decision finalized successfully.", queue_for_rerun=True)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def render_records() -> None:
    subpage_navigation(("inspection-home", "Inspections", ":material/biotech:"), ("dimensional-entry", "New / Edit Report", ":material/edit_note:"))
    page_header("Dimensional Report Records", context="Select before action")
    service = InspectionService(); perms = current_permissions("DIMENSIONAL_REPORT"); parts, _, _, _, _ = _maps(service)
    rows = service.dimensional_reports(); search = st.text_input("Search Report, Part, Heat or Inward")
    filtered = [row for row in rows if not search or search.casefold() in " ".join(str(row.get(key) or "") for key in ("report_number", "heat_number", "heat_code", "remarks", "layout_name_snapshot")).casefold()]
    if filtered:
        labels = {str(row["id"]): f"{row.get('report_number')} · Heat {row.get('heat_number')} · {row.get('layout_name_snapshot') or 'Layout'} · {disposition_label(row.get('disposition'))}" for row in filtered}
        selected = st.selectbox("Select Dimensional Report", list(labels), format_func=lambda value: labels[value])
        selected_row = next(row for row in filtered if str(row["id"]) == selected); st.session_state["edit_dimensional_id"] = selected
        c1, c2, c3 = st.columns(3, gap="small")
        with c1: st.page_link(st.session_state["_qsms_pages"]["dimensional-entry"], label="Open Selected Report", icon=":material/edit:", width="stretch")
        with c2:
            try:
                pdf_bytes = dimensional_record_pdf_bytes(service.dimensional_report_payload(selected))
                st.download_button("Download Final / Dimensional PDF", data=pdf_bytes, file_name=f"{selected_row.get('report_number') or 'Dimensional_Report'}.pdf", mime="application/pdf", key=f"dimensional_pdf_{selected}", width="stretch")
            except Exception as exc:
                st.error(f"PDF could not be generated: {exc}")
        with c3:
            if password_delete_panel(repo=service.repo, table="inspection_reports", rows=[selected_row], labeler=lambda row: row.get("report_number"), key=f"delete_dimensional_{selected}", can_delete=perms["can_archive"], title="Delete Selected Dimensional Report"):
                st.rerun()
    section_bar("DIMENSIONAL REGISTER")
    display = pd.DataFrame([{"Report Number": row.get("report_number"), "Date": row.get("inspection_date"), "Part Number": (parts.get(str(row.get("part_id"))) or {}).get("part_number"), "Heat Number": row.get("heat_number"), "Layout": row.get("layout_name_snapshot"), "Section": row.get("layout_type_name"), "Steel kg": row.get("steel_quantity_kg"), "Production pcs": row.get("production_quantity_pcs"), "Result": row.get("overall_result"), "Decision": row.get("disposition"), "Status": row.get("status")} for row in filtered])
    st.dataframe(style_status_dataframe(display), hide_index=True, width="stretch", height=520)
