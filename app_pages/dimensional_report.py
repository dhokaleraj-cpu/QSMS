from __future__ import annotations
# Legacy controlled PDF label retained for regression traceability: Download Final / Dimensional PDF

from datetime import date

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.delete_service import password_delete_panel
from core.inspection_service import FINAL_DISPOSITIONS, InspectionService
from core.reporting import dimensional_record_pdf_bytes, quality_record_excel_bytes
from core.selection_labels import employee_label, party_label
from core.ui import disposition_cards, disposition_label, page_header, save_success_popup, section_bar, stage_section, style_status_dataframe, subpage_navigation, template_download_row


def _maps(service: InspectionService):
    parts = {str(row["id"]): row for row in service.parts()}
    parties = {str(row["id"]): row for row in service.parties()}
    processes = {str(row["id"]): row for row in service.processes()}
    stages = {str(row["id"]): row for row in service.stages()}
    employees = service.employees()
    employee_map = {str(row["id"]): employee_label(row) for row in employees}
    return parts, parties, processes, stages, employee_map


def _report_exports(service: InspectionService, report_id: str, report_number: str, *, key: str) -> None:
    try:
        payload = service.dimensional_report_payload(report_id)
        pdf_bytes = dimensional_record_pdf_bytes(payload)
        excel_bytes = quality_record_excel_bytes(payload, "DIMENSIONAL")
        c1, c2 = st.columns(2, gap="small")
        c1.download_button(
            "Download / Print PDF", data=pdf_bytes,
            file_name=f"{report_number or 'Dimensional_Report'}.pdf", mime="application/pdf",
            icon=":material/picture_as_pdf:", key=f"{key}_pdf", width="stretch",
        )
        c2.download_button(
            "Download Excel Report", data=excel_bytes,
            file_name=f"{report_number or 'Dimensional_Report'}.xlsx",
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



STANDALONE_STAGES = {
    "RAW_MATERIAL_STAGE": "Raw Material Stage",
    "OSP_STAGE": "OSP Stage",
    "FINAL_DISPATCH_STAGE": "Final Dispatch Stage",
}


def _render_standalone_entry(service: InspectionService, perms: dict, parts: dict[str, dict], parties: dict[str, dict], processes: dict[str, dict], stages: dict[str, dict], employee_map: dict[str, str], existing: dict | None) -> None:
    existing_id = str((existing or {}).get("id") or "")
    with stage_section("A", "STANDALONE REPORT CONTEXT", "Master-driven Part / Customer / Material / OSP context. No RMTC or inward transaction linkage is required.", key="dimensional_standalone_context"):
        scope_keys = list(STANDALONE_STAGES)
        current_scope = str((existing or {}).get("inspection_scope") or "RAW_MATERIAL_STAGE")
        scope = st.selectbox("Report Stage", scope_keys, index=scope_keys.index(current_scope) if current_scope in scope_keys else 0, format_func=lambda v: STANDALONE_STAGES[v], disabled=bool(existing))
        part_map = {pid: f"{row.get('part_number')} · {row.get('part_name')}" for pid, row in parts.items()}
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
            groups = service.standalone_osp_process_groups(part_id, "DIMENSIONAL")
            if not groups:
                st.warning("No active OSP Dimensional Process requirements are configured in Part Master for this Part Number."); return
            group_map = {str(row["id"]): f"{(processes.get(str(row.get('process_id'))) or {}).get('process_code') or '-'} · {(processes.get(str(row.get('process_id'))) or {}).get('process_name') or '-'}" for row in groups}
            existing_process = str((existing or {}).get("process_id") or "")
            default_group = next((str(row["id"]) for row in groups if str(row.get("process_id")) == existing_process), next(iter(group_map)))
            group_id = st.selectbox("OSP Process", list(group_map), index=list(group_map).index(default_group), format_func=lambda value: group_map[value], disabled=bool(existing))
            process_group = next(row for row in groups if str(row["id"]) == group_id)
            process_id = str(process_group.get("process_id") or "") or None

        plan = service.auto_standalone_plan("DIMENSIONAL", part_id, scope, process_id)
        if not plan:
            if scope == "OSP_STAGE":
                st.warning("The Part Master OSP Dimensional requirements exist, but the controlled OSP Dimensional layout has not been generated/approved. Create/update the OSP inspection layout from the Part Master process section.")
            else:
                st.warning("No approved Dimensional layout is configured for this Part Number.")
            return
        plan_id = str(plan["id"])
        if not process_id:
            process_id = str(plan.get("process_id") or "") or None
        process = processes.get(str(process_id or "")) or {}
        section_name = STANDALONE_STAGES[scope]

        supplier_ids = list(context.get("supplier_ids") or [])
        if scope == "OSP_STAGE":
            supplier_ids = [pid for pid, row in parties.items() if "OSP_VENDOR" in (row.get("party_types") or []) or "SUPPLIER" in (row.get("party_types") or [])]
        if not supplier_ids:
            supplier_ids = [pid for pid, row in parties.items() if "SUPPLIER" in (row.get("party_types") or [])]
        supplier_ids = [pid for pid in supplier_ids if pid in parties]
        supplier_options = [""] + supplier_ids
        current_supplier = str((existing or {}).get("supplier_id") or "")
        supplier_id = st.selectbox("Supplier / OSP Vendor", supplier_options, index=supplier_options.index(current_supplier) if current_supplier in supplier_options else 0, format_func=lambda v: party_label(parties.get(v) or {}) if v else "— Select from Master —")

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
        inspection_date = c2.date_input("Inspection Date", value=date.fromisoformat(str((existing or {}).get("inspection_date"))[:10]) if (existing or {}).get("inspection_date") else date.today(), format="DD-MM-YYYY")
        heat_number = c3.text_input("Heat Number", value=str((existing or {}).get("heat_number") or ""))
        heat_code = c4.text_input("Heat Code", value=str((existing or {}).get("heat_code") or ""))
        c1, c2, c3, c4 = st.columns(4, gap="small")
        vendor_batch_number = c1.text_input("Supplier / HT / OSP Batch Number", value=str((existing or {}).get("vendor_batch_number_snapshot") or ""))
        batch_number = c2.text_input("Internal / FSI Batch Number", value=str((existing or {}).get("batch_number") or ""))
        supplier_reference = c3.text_input("Supplier Invoice / Reference", value=str((existing or {}).get("supplier_reference_number") or ""))
        c1, c2, c3, c4 = st.columns(4, gap="small")
        lot_qty = c1.number_input("Lot / Production Quantity pcs", min_value=0.0, value=float((existing or {}).get("production_quantity_pcs") or (existing or {}).get("lot_quantity") or 0), step=1.0)
        reference_text = c2.text_input("Lot / Sample Reference", value=str((existing or {}).get("reference_text") or ""))
        default_condition = (process_group or {}).get("process_specification") or process.get("process_name") or section_name
        supply_condition = st.text_input("Supply / Process Condition", value=str((existing or {}).get("supply_condition") or default_condition or ""))
        sample_size = min(max(int((existing or {}).get("sample_size") or plan.get("default_sample_size") or 1), 1), 10)
        sample_size = st.number_input("Sample Size", min_value=1, max_value=10, value=int(sample_size), step=1)

    with stage_section("B", "DIMENSIONAL CHARACTERISTICS", "The inspection grid is loaded automatically from the approved Part Master controlled layout.", key="dimensional_standalone_characteristics"):
        rows = _report_rows(service, plan_id, existing_id or None, int(sample_size), section_name)
        frame = _editor_frame(rows, int(sample_size))
        edited = st.data_editor(frame, hide_index=True, width="stretch", height=min(620, max(220, 80 + len(frame) * 30)), disabled=["Section", "Sr No", "Parameter", "Specification", "Min", "Max", "Checking Aid", "Result", "_sequence", "_characteristic_id", "_type", "_unit"], column_config={"NA": st.column_config.CheckboxColumn(), "_sequence": None, "_characteristic_id": None, "_type": None, "_unit": None}, key=f"dimensional_standalone_grid_{existing_id or 'new'}_{plan_id}")
        c1, c2 = st.columns([3, 1], gap="small")
        conclusion = c1.text_area("Conclusion", value=str((existing or {}).get("remarks") or ""), height=76, help="Controlled report conclusion. This prints separately from the Final Decision.")
        attachment = c2.file_uploader("Attach Report", type=["pdf", "xlsx", "xls", "png", "jpg", "jpeg"], key=f"dim_standalone_attachment_{existing_id or 'new'}")
        employee_options = [""] + list(employee_map)
        c1, c2, c3 = st.columns(3, gap="small")
        current_prepared = str((existing or {}).get("prepared_by_employee_id") or "")
        prepared = c1.selectbox("Inspected / Prepared By", employee_options, index=employee_options.index(current_prepared) if current_prepared in employee_options else 0, format_func=lambda v: employee_map.get(v, "— Select —"))
        disposition_options = ["PENDING", *FINAL_DISPOSITIONS]
        current_decision = str((existing or {}).get("disposition") or "PENDING")
        disposition = c2.selectbox("Final Decision", disposition_options, index=disposition_options.index(current_decision) if current_decision in disposition_options else 0, format_func=disposition_label)
        reason = c3.text_input("Decision Reason", value=str((existing or {}).get("disposition_reason") or ""), help="Required for On Hold, Accepted Under Reserve and Rejected decisions.")
        saved_rows = []
        for _, row in edited.iterrows():
            observations = [row.get(f"Actual {i + 1}") for i in range(int(sample_size))]; na = bool(row.get("NA")); result = service.evaluate_characteristic({"characteristic_type": row.get("_type"), "lower_spec": row.get("Min"), "upper_spec": row.get("Max")}, observations, na)
            saved_rows.append({"sequence_no": int(row.get("_sequence") or len(saved_rows) + 1), "inspection_plan_characteristic_id": row.get("_characteristic_id"), "characteristic_no": row.get("Sr No"), "characteristic": row.get("Parameter"), "specification": row.get("Specification"), "lower_spec": row.get("Min"), "upper_spec": row.get("Max"), "unit": row.get("_unit"), "checking_aid": row.get("Checking Aid"), "observations": observations, "result": result, "remarks": row.get("Remark"), "applicability": "NOT_APPLICABLE" if na else "APPLICABLE", "report_section": section_name})
        writable = (perms["can_edit"] if existing else perms["can_create"]) and str((existing or {}).get("status") or "DRAFT") != "FINAL"
        if st.button("Save Standalone Dimensional Report", type="primary", width="stretch", disabled=not writable or not prepared):
            try:
                final_number = report_no.strip() or service.next_number("DIMENSIONAL")
                payload = {
                    "report_number": final_number, "report_type": "DIMENSIONAL", "inspection_plan_id": plan_id,
                    "inspection_stage_id": plan.get("inspection_stage_id"), "process_id": process_id, "part_id": part_id,
                    "inward_lot_id": None, "batch_id": None, "osp_job_id": None, "inspection_date": inspection_date.isoformat(),
                    "sample_size": int(sample_size), "accepted_quantity": 0, "rejected_quantity": 0,
                    "inspector": employee_map.get(prepared), "overall_result": "NOT_EVALUATED",
                    "status": str((existing or {}).get("status") or "DRAFT"), "remarks": conclusion.strip() or None,
                    "disposition": disposition, "disposition_reason": reason.strip() or None, "heat_number": heat_number.strip() or None,
                    "heat_code": heat_code.strip() or None, "batch_number": batch_number.strip() or None,
                    "supplier_reference_number": supplier_reference.strip() or None, "supply_condition": supply_condition.strip() or None,
                    "reference_text": reference_text.strip() or None, "lot_quantity": lot_qty or None, "production_quantity_pcs": lot_qty or None,
                    "supplier_id": supplier_id or None, "customer_id": part.get("customer_id"), "material_grade_id": part.get("material_grade_id"),
                    "drawing_number": part.get("drawing_number"), "drawing_revision": part.get("drawing_revision"),
                    "prepared_by_employee_id": prepared, "source_layout_revision": plan.get("revision"),
                    "layout_name_snapshot": plan.get("layout_name"), "layout_type_name": section_name,
                    "steel_quantity_kg": None, "inspection_scope": scope,
                    "process_specification_snapshot": (process_group or {}).get("process_specification") or plan.get("remarks"),
                    "vendor_batch_number_snapshot": vendor_batch_number.strip() or None,
                }
                saved = service.save_dimensional(payload, saved_rows, existing_id or None)
                if attachment is not None:
                    service.upload_attachment("DIMENSIONAL_REPORT", str(saved["id"]), "REPORT_COPY", attachment, "inspection_reports", "attachment_path")
                st.session_state["edit_dimensional_id"] = str(saved["id"]); save_success_popup(f"Standalone Dimensional Report {final_number} saved successfully.", queue_for_rerun=True); st.rerun()
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
            validator = c1.selectbox("Validated By", employee_options, index=employee_options.index(current_validator) if current_validator in employee_options else 0, format_func=lambda value: employee_map.get(value, "— Select —"), key=f"dim_standalone_validator_{existing_id}")
            approver = c2.selectbox("Approved By", employee_options, index=employee_options.index(current_approver) if current_approver in employee_options else 0, format_func=lambda value: employee_map.get(value, "— Select —"), key=f"dim_standalone_approver_{existing_id}")
            if c3.button("Finalize Dimensional Decision", disabled=not perms["can_approve"] or disposition == "PENDING" or not validator or not approver or str(existing.get("status")) == "FINAL", width="stretch", key=f"dim_standalone_finalize_{existing_id}"):
                try:
                    service.finalize_dimensional(existing_id, disposition, reason, validator, approver)
                    save_success_popup("Standalone Dimensional conclusion and final decision completed successfully.", queue_for_rerun=True)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            section_bar("PDF / EXCEL / PRINT EXPORT")
            _report_exports(service, existing_id, str(existing.get("report_number") or "Dimensional_Report"), key=f"dim_standalone_export_{existing_id}")


def render_entry() -> None:
    subpage_navigation(("inspection-home", "Inspections", ":material/biotech:"), ("inward-records", "Material Inward", ":material/input:"), ("dimensional-records", "Dimensional Records", ":material/table_view:"))
    page_header("Dimensional Inspection Report", context="Automatic part/process/stage layout")
    template_download_row([("Dimensional_Inspection_Report_Template.xlsx", "Download Dimensional Report Template")], key_prefix="dimensional_report")
    service = InspectionService(); perms = current_permissions("DIMENSIONAL_REPORT")
    parts, parties, processes, stages, employee_map = _maps(service)
    existing_id = str(st.session_state.get("edit_dimensional_id") or "")
    existing_record = service.get_dimensional(existing_id) if existing_id else None
    standalone_existing = str((existing_record or {}).get("inspection_scope") or "") in STANDALONE_STAGES
    report_mode = st.radio("Report Linkage", ["QCMS Linked Flow", "Standalone Stage Report"], index=1 if standalone_existing else 0, horizontal=True, disabled=bool(existing_record), help="Standalone Stage Report does not require RMTC, Material Inward or Production linkage.")
    if report_mode == "Standalone Stage Report":
        _render_standalone_entry(service, perms, parts, parties, processes, stages, employee_map, existing_record)
        return
    pending_queue = [row for row in service.inspection_queue() if row.get("dimensional_pending")]
    with stage_section("A", 'DIMENSIONAL PENDING LIST', key="dimensional_report_render_entry_a"):
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
    with stage_section("B", 'LAYOUT CHARACTERISTICS', key="dimensional_report_render_entry_b"):
        edited = st.data_editor(frame, hide_index=True, width="stretch", height=min(620, max(260, 90 + len(frame) * 32)), disabled=["Section", "Sr No", "Parameter", "Specification", "Min", "Max", "Checking Aid", "Result", "_sequence", "_characteristic_id", "_type", "_unit"], column_config={"NA": st.column_config.CheckboxColumn(), "_sequence": None, "_characteristic_id": None, "_type": None, "_unit": None}, key=f"dimensional_grid_{existing_id or 'new'}_{plan_id}")

        c1, c2 = st.columns([3, 1], gap="small")
        remarks = c1.text_area("Conclusion", value=str((existing or {}).get("remarks") or ""), height=72, help="Controlled report conclusion. This is separate from the Final Decision and Decision Reason.")
        attachment = c2.file_uploader("Attach Report", type=["pdf", "xlsx", "xls", "png", "jpg", "jpeg"], key=f"dim_attachment_{existing_id or 'new'}")

        employee_options = [""] + list(employee_map)
        c1, c2, c3 = st.columns(3, gap="small")
        prepared_current = str((existing or {}).get("prepared_by_employee_id") or "")
        prepared = c1.selectbox("Inspected / Prepared By", employee_options, index=employee_options.index(prepared_current) if prepared_current in employee_options else 0, format_func=lambda value: employee_map.get(value, "— Select —"))
        disposition_options = ["PENDING", *FINAL_DISPOSITIONS]
        disposition = c2.selectbox("Final Decision", disposition_options, index=disposition_options.index(str((existing or {}).get("disposition") or "PENDING")), format_func=disposition_label)
        reason = c3.text_input("Decision Reason", value=str((existing or {}).get("disposition_reason") or ""))

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
                payload = {"report_number": final_number, "report_type": "DIMENSIONAL", "inspection_plan_id": plan_id, "inspection_stage_id": plan.get("inspection_stage_id"), "process_id": plan.get("process_id"), "part_id": part_id, "inward_lot_id": inward_id, "inspection_date": inspection_date.isoformat(), "sample_size": int(sample_size), "accepted_quantity": 0, "rejected_quantity": 0, "inspector": employee_map.get(prepared), "overall_result": "NOT_EVALUATED", "status": str((existing or {}).get("status") or "DRAFT"), "remarks": remarks.strip() or None, "disposition": disposition, "disposition_reason": reason.strip() or None, "heat_number": inward.get("heat_number"), "heat_code": inward.get("heat_code"), "lot_quantity": lot_qty, "supplier_id": inward.get("supplier_id"), "drawing_number": part.get("drawing_number"), "drawing_revision": part.get("drawing_revision"), "prepared_by_employee_id": prepared, "source_layout_revision": plan.get("revision"), "layout_name_snapshot": plan.get("layout_name"), "layout_type_name": section_name, "steel_quantity_kg": inward.get("steel_quantity_kg") or inward.get("quantity_received"), "production_quantity_pcs": inward.get("production_quantity_pcs")}
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
            disposition_cards([{"label": "Report", "value": existing.get("status"), "foot": existing.get("report_number")}, {"label": "Final Decision", "value": existing.get("disposition")}, {"label": "Layout", "value": existing.get("layout_name_snapshot") or plan.get("layout_name")}])
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
            section_bar("PDF / EXCEL / PRINT EXPORT")
            _report_exports(service, str(existing["id"]), str(existing.get("report_number") or "Dimensional_Report"), key=f"dim_linked_export_{existing.get('id')}")
            if password_delete_panel(
                repo=service.repo, table="inspection_reports", rows=[existing],
                labeler=lambda row: row.get("report_number"),
                key=f"delete_dimensional_entry_{existing.get('id')}", can_delete=perms["can_archive"],
                title="Delete This Dimensional Report",
                help_text="Permanent deletion requires your current QCMS password and Dimensional Delete permission.",
            ):
                st.session_state.pop("edit_dimensional_id", None); st.rerun()


def render_records() -> None:
    subpage_navigation(("inspection-home", "Inspections", ":material/biotech:"), ("dimensional-entry", "New / Edit Report", ":material/edit_note:"))
    page_header("Dimensional Report Records", context="Select before action")
    service = InspectionService(); perms = current_permissions("DIMENSIONAL_REPORT"); parts, parties, _, _, _ = _maps(service); grades = {str(row["id"]): row for row in service.material_grades()}
    rows = service.dimensional_reports(); search = st.text_input("Search Report, Part, Heat or Inward")
    filtered = [row for row in rows if not search or search.casefold() in " ".join(str(row.get(key) or "") for key in ("report_number", "heat_number", "heat_code", "batch_number", "supplier_reference_number", "reference_text", "remarks", "layout_name_snapshot")).casefold()]
    if filtered:
        labels = {str(row["id"]): f"{row.get('report_number')} · Heat {row.get('heat_number')} · {row.get('layout_name_snapshot') or 'Layout'} · {disposition_label(row.get('disposition'))}" for row in filtered}
        selected = st.selectbox("Select Dimensional Report", list(labels), format_func=lambda value: labels[value])
        selected_row = next(row for row in filtered if str(row["id"]) == selected); st.session_state["edit_dimensional_id"] = selected
        c1, c2, c3, c4 = st.columns(4, gap="small")
        with c1: st.page_link(st.session_state["_qsms_pages"]["dimensional-entry"], label="Open Selected Report", icon=":material/edit:", width="stretch")
        try:
            selected_payload = service.dimensional_report_payload(selected)
            with c2:
                st.download_button("Download / Print PDF", data=dimensional_record_pdf_bytes(selected_payload), file_name=f"{selected_row.get('report_number') or 'Dimensional_Report'}.pdf", mime="application/pdf", key=f"dimensional_pdf_{selected}", icon=":material/picture_as_pdf:", width="stretch")
            with c3:
                st.download_button("Download Excel Report", data=quality_record_excel_bytes(selected_payload, "DIMENSIONAL"), file_name=f"{selected_row.get('report_number') or 'Dimensional_Report'}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dimensional_xlsx_{selected}", icon=":material/download:", width="stretch")
        except Exception as exc:
            st.error(f"Report export could not be generated: {exc}")
        with c4:
            if password_delete_panel(repo=service.repo, table="inspection_reports", rows=[selected_row], labeler=lambda row: row.get("report_number"), key=f"delete_dimensional_{selected}", can_delete=perms["can_archive"], title="Delete Selected Dimensional Report"):
                st.rerun()
    section_bar("DIMENSIONAL REGISTER")
    display = pd.DataFrame([{"Report Number": row.get("report_number"), "Date": row.get("inspection_date"), "Part Number": (parts.get(str(row.get("part_id"))) or {}).get("part_number"), "Customer": (parties.get(str(row.get("customer_id") or (parts.get(str(row.get("part_id"))) or {}).get("customer_id"))) or {}).get("party_name"), "Supplier": (parties.get(str(row.get("supplier_id"))) or {}).get("party_name"), "Material Grade": (grades.get(str(row.get("material_grade_id") or (parts.get(str(row.get("part_id"))) or {}).get("material_grade_id"))) or {}).get("grade_code"), "Heat Number": row.get("heat_number"), "Batch Number": row.get("batch_number") or row.get("vendor_batch_number_snapshot"), "Layout": row.get("layout_name_snapshot"), "Report Stage": STANDALONE_STAGES.get(str(row.get("inspection_scope")), str(row.get("inspection_scope") or "MATERIAL_INWARD").replace("_", " ").title()), "Production pcs": row.get("production_quantity_pcs"), "Conclusion": row.get("remarks"), "Result": row.get("overall_result"), "Final Decision": row.get("disposition"), "Decision Reason": row.get("disposition_reason"), "Status": row.get("status")} for row in filtered])
    st.dataframe(style_status_dataframe(display), hide_index=True, width="stretch", height=520)
