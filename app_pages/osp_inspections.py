from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st
from core.ui import portal_table

from core.access import current_permissions
from core.delete_service import password_delete_panel
from core.inspection_service import FINAL_DISPOSITIONS, InspectionService
from core.osp_service import OSPService
from core.ui import disposition_cards, disposition_label, page_header, save_success_popup, section_bar, stage_section, style_status_dataframe, subpage_navigation


def _employee_map(service: InspectionService) -> dict[str, str]:
    return {str(r["id"]): f"{r.get('employee_code')} · {r.get('first_name')} {r.get('last_name')}" for r in service.employees()}


def _job_label(row: dict) -> str:
    return f"{row.get('osp_job_number')} · {row.get('part_number')} · Heat {row.get('heat_number')} · {row.get('process_name')} · {row.get('vendor_name')} · Batch {row.get('vendor_batch_number') or '-'}"


def _scope_label(scope: str) -> str:
    return "Pre-inward Sample" if scope == "OSP_SAMPLE" else "Post-receipt Full Batch"


def _source_rows(service: InspectionService, plan_id: str, existing_rows: list[dict] | None = None) -> list[dict]:
    if existing_rows:
        by_characteristic = {str(r.get("inspection_plan_characteristic_id")): r for r in existing_rows}
    else:
        by_characteristic = {}
    rows = []
    for position, characteristic in enumerate(service.plan_characteristics(plan_id), start=1):
        saved = by_characteristic.get(str(characteristic.get("id"))) or {}
        observations = saved.get("observations") or []
        actual = observations[0] if observations else saved.get("actual_value")
        rows.append({
            "Sr No": characteristic.get("characteristic_no") or characteristic.get("sequence_no") or position,
            "Parameter": characteristic.get("characteristic"),
            "Specification": characteristic.get("specification"),
            "Min": characteristic.get("lower_spec"),
            "Max": characteristic.get("upper_spec"),
            "Unit": characteristic.get("unit"),
            "Method / Aid": characteristic.get("checking_aid_text") or characteristic.get("checking_method"),
            "Actual Value": actual,
            "NA": saved.get("applicability") == "NOT_APPLICABLE",
            "Result": saved.get("result") or "NOT_EVALUATED",
            "Remark": saved.get("remarks") or "",
            "_sequence": characteristic.get("sequence_no") or position,
            "_characteristic_id": characteristic.get("id"),
            "_type": characteristic.get("characteristic_type") or "VARIABLE",
        })
    return rows


def _pending_table(rows: list[dict], report_type: str, scope: str) -> None:
    disposition_key = (
        "sample_dimensional_disposition" if scope == "OSP_SAMPLE" and report_type == "DIMENSIONAL" else
        "sample_metlab_disposition" if scope == "OSP_SAMPLE" else
        "receipt_dimensional_disposition" if report_type == "DIMENSIONAL" else
        "receipt_metlab_disposition"
    )
    frame = pd.DataFrame([{
        "OSP Job": r.get("osp_job_number"), "Heat Number": r.get("heat_number"), "Part Number": r.get("part_number"),
        "OSP Vendor": r.get("vendor_name"), "Process": r.get("process_name"), "Vendor Batch": r.get("vendor_batch_number"),
        "Quantity pcs": r.get("sample_quantity") if scope == "OSP_SAMPLE" else r.get("quantity_received"),
        "Decision": r.get(disposition_key) or "PENDING", "Status": r.get("status"),
    } for r in rows])
    portal_table(style_status_dataframe(frame), hide_index=True, width="stretch", height=min(320, 86 + max(len(frame), 1) * 36))


def _existing_report(service: InspectionService, report_type: str, job_id: str, scope: str) -> dict | None:
    table = "inspection_reports" if report_type == "DIMENSIONAL" else "lab_tests"
    rows = service.repo.select(table, eq={"osp_job_id": job_id, "inspection_scope": scope}, order_by="updated_at", desc=True, limit=1)
    return rows[0] if rows else None


def _render(report_type: str) -> None:
    is_dimensional = report_type == "DIMENSIONAL"
    module = "DIMENSIONAL_REPORT" if is_dimensional else "METLAB_REPORT"
    title = "OSP Dimensional Inspection" if is_dimensional else "OSP MetLAB Inspection"
    subpage_navigation(("osp-home", "OSP Home", ":material/arrow_back:"), ("osp-sample-receipt", "Sample Receipt", ":material/experiment:"), ("osp-inward", "OSP Inward", ":material/input:"), ("osp-records", "OSP Records", ":material/table_view:"))
    page_header(title, "Process-specific parameters are pulled only from the approved Part + OSP Process layout.", "Two-stage quality gate")
    inspection = InspectionService(); osp = OSPService(); perms = current_permissions(module); employees = _employee_map(inspection)

    scope_options = ["OSP_SAMPLE", "OSP_RECEIPT"]
    requested_scope = str(st.session_state.get("osp_inspection_scope") or "OSP_SAMPLE")
    scope = st.radio("Inspection Stage", scope_options, index=scope_options.index(requested_scope) if requested_scope in scope_options else 0, horizontal=True, format_func=_scope_label)
    pending = osp.jobs_for_inspection(scope, report_type)
    with stage_section("A", f'{_scope_label(scope).upper()} · PENDING LIST', key="osp_inspections__render_a"):
        if not pending:
            st.success(f"No {_scope_label(scope)} {report_type.title()} inspections are pending.")
            return
        _pending_table(pending, report_type, scope)

        labels = {str(r["id"]): _job_label(r) for r in pending}
        requested_job = str(st.session_state.get("osp_inspection_job_id") or "")
        job_id = st.selectbox("OSP Batch", list(labels), index=list(labels).index(requested_job) if requested_job in labels else 0, format_func=lambda value: labels[value])
        job = next(r for r in pending if str(r["id"]) == job_id)
        st.session_state["osp_inspection_job_id"] = job_id; st.session_state["osp_inspection_scope"] = scope

        plans = inspection.plans(report_type, str(job.get("part_id")), approved_only=True, process_id=str(job.get("process_id")), inward_type="OSP_PROCESS")
        if not plans:
            st.warning(f"No Approved OSP {report_type.title()} layout matches Part {job.get('part_number')} and Process {job.get('process_name')}.")
            st.page_link(st.session_state["_qsms_pages"]["inspection-layout-entry"], label="Create / Approve OSP Inspection Layout", icon=":material/add:", width="stretch")
            return
        plan_map = {str(r["id"]): f"{r.get('layout_name')} · {r.get('plan_number')} Rev {r.get('revision')}" for r in plans}
        existing = _existing_report(inspection, report_type, job_id, scope)
        current_plan = str((existing or {}).get("inspection_plan_id" if is_dimensional else "layout_plan_id") or plans[0]["id"])
        plan_id = st.selectbox("Approved OSP Layout", list(plan_map), index=list(plan_map).index(current_plan) if current_plan in plan_map else 0, format_func=lambda value: plan_map[value], disabled=bool(existing))
        plan = next(r for r in plans if str(r["id"]) == plan_id)

    with stage_section("B", 'OSP BATCH & PROCESS SPECIFICATION', key="osp_inspections__render_b"):
        c = st.columns(5, gap="small")
        c[0].text_input("Heat Number", value=str(job.get("heat_number") or ""), disabled=True)
        c[1].text_input("Part Number", value=str(job.get("part_number") or ""), disabled=True)
        c[2].text_input("OSP Vendor", value=str(job.get("vendor_name") or ""), disabled=True)
        c[3].text_input("OSP Process", value=str(job.get("process_name") or ""), disabled=True)
        c[4].text_input("Vendor Batch", value=str(job.get("vendor_batch_number") or ""), disabled=True)
        st.text_area("Process Specification", value=str(job.get("process_specification") or ""), disabled=True, height=68)

        report_id = str((existing or {}).get("id") or "")
        existing_detail = inspection.dimensional_results(report_id) if is_dimensional and report_id else []
        existing_layout_rows = []
        if not is_dimensional and existing:
            existing_layout_rows = list(((existing.get("results") or {}).get("rows") or []))
        micro_files: list[Any] = []
        micro_titles: list[str] = []
        if not is_dimensional:
            st.markdown("**Microstructure Photographs**")
            st.caption("Add up to four photographs and a title for each OSP MetLAB photograph.")
            micro_cols = st.columns(4, gap="small")
            for slot, column in enumerate(micro_cols, start=1):
                with column:
                    if (existing or {}).get(f"microstructure_image_{slot}_path"):
                        st.caption(f"Photo {slot} already uploaded · upload another file to replace it")
                    micro_files.append(st.file_uploader(
                        f"Microstructure Photo {slot}", type=["png", "jpg", "jpeg"],
                        key=f"osp_metlab_micro_{scope}_{job_id}_{slot}",
                    ))
                    micro_titles.append(st.text_input(
                        f"Photo {slot} Title",
                        value=str((existing or {}).get(f"microstructure_caption_{slot}") or ""),
                        key=f"osp_metlab_micro_title_{scope}_{job_id}_{slot}",
                    ))

        frame = pd.DataFrame(_source_rows(inspection, plan_id, existing_detail or existing_layout_rows))
    with stage_section("C", 'PROCESS-SPECIFIC INSPECTION PARAMETERS', key="osp_inspections__render_c"):
        edited = st.data_editor(
            frame, hide_index=True, width="stretch", height=min(620, max(260, 90 + len(frame) * 34)),
            disabled=["Sr No", "Parameter", "Specification", "Min", "Max", "Unit", "Method / Aid", "Result", "_sequence", "_characteristic_id", "_type"],
            column_config={"NA": st.column_config.CheckboxColumn(), "_sequence": None, "_characteristic_id": None, "_type": None},
            key=f"osp_{report_type.lower()}_{scope}_{job_id}_{plan_id}",
        )

        employee_options = [""] + list(employees)
        c = st.columns(4, gap="small")
        report_no = c[0].text_input("Report Number", value=str((existing or {}).get("report_number") or ""), disabled=bool(existing))
        inspection_date = c[1].date_input("Inspection Date", value=date.fromisoformat(str((existing or {}).get("inspection_date" if is_dimensional else "test_date"))[:10]) if (existing or {}).get("inspection_date" if is_dimensional else "test_date") else date.today(), format="DD-MM-YYYY")
        prepared_current = str((existing or {}).get("prepared_by_employee_id") or "")
        prepared = c[2].selectbox("Prepared By", employee_options, index=employee_options.index(prepared_current) if prepared_current in employee_options else 0, format_func=lambda value: employees.get(value, "— Select —"))
        decision_options = ["PENDING", *FINAL_DISPOSITIONS]
        disposition = c[3].selectbox("Validation Decision", decision_options, index=decision_options.index(str((existing or {}).get("disposition") or "PENDING")), format_func=disposition_label)
        c1, c2 = st.columns(2, gap="small")
        reason = c1.text_input("Hold / Reserve / Rejection Reason", value=str((existing or {}).get("disposition_reason") or ""))
        remarks = c2.text_input("Report Remarks", value=str((existing or {}).get("remarks") or ""))

        result_rows: list[dict[str, Any]] = []
        for _, row in edited.iterrows():
            na = bool(row.get("NA")); actual = row.get("Actual Value")
            result = inspection.evaluate_characteristic({"characteristic_type": row.get("_type"), "lower_spec": row.get("Min"), "upper_spec": row.get("Max")}, [actual], na)
            result_rows.append({
                "sequence_no": int(row.get("_sequence") or len(result_rows) + 1), "inspection_plan_characteristic_id": row.get("_characteristic_id"),
                "characteristic_no": row.get("Sr No"), "characteristic": row.get("Parameter"), "parameter": row.get("Parameter"),
                "specification": row.get("Specification"), "lower_spec": row.get("Min"), "upper_spec": row.get("Max"), "unit": row.get("Unit"),
                "checking_aid": row.get("Method / Aid"), "checking_method": row.get("Method / Aid"), "observations": [actual], "actual_value": actual,
                "result": result, "remarks": row.get("Remark"), "applicability": "NOT_APPLICABLE" if na else "APPLICABLE", "report_section": report_type,
                "characteristic_type": row.get("_type"),
            })

        writable = (perms["can_edit"] if existing else perms["can_create"]) and str((existing or {}).get("status") or "DRAFT") != "FINAL"
        if st.button(f"Save OSP {report_type.title()} Draft", type="primary", disabled=not writable or not prepared, width="stretch"):
            try:
                final_number = report_no.strip() or inspection.next_number(report_type)
                quantity = float(job.get("sample_quantity") if scope == "OSP_SAMPLE" else job.get("quantity_received") or 0)
                common = {
                    "report_number": final_number, "part_id": job.get("part_id"), "osp_job_id": job_id, "batch_id": job.get("osp_batch_id"),
                    "process_id": job.get("process_id"), "inspection_scope": scope, "heat_number": job.get("heat_number"), "heat_code": job.get("heat_code"),
                    "supplier_id": job.get("vendor_id"), "status": str((existing or {}).get("status") or "DRAFT"), "overall_result": "NOT_EVALUATED",
                    "disposition": str((existing or {}).get("disposition") or "PENDING"), "remarks": remarks.strip() or None,
                    "prepared_by_employee_id": prepared, "layout_name_snapshot": plan.get("layout_name"), "layout_type_name": report_type,
                    "production_quantity_pcs": quantity, "process_specification_snapshot": job.get("process_specification"),
                    "vendor_batch_number_snapshot": job.get("vendor_batch_number"),
                }
                if is_dimensional:
                    payload = {**common, "report_type": "DIMENSIONAL", "inspection_plan_id": plan_id, "inspection_stage_id": plan.get("inspection_stage_id"),
                        "inspection_date": inspection_date.isoformat(), "sample_size": 1, "lot_quantity": quantity, "accepted_quantity": 0, "rejected_quantity": 0,
                        "inspector": employees.get(prepared), "source_layout_revision": plan.get("revision")}
                    saved = inspection.save_dimensional(payload, result_rows, report_id or None)
                else:
                    payload = {**common, "test_type": "METLAB", "layout_plan_id": plan_id, "inspection_stage_id": plan.get("inspection_stage_id"),
                        "test_date": inspection_date.isoformat(), "sample_reference": f"{job.get('osp_job_number')} / {job.get('vendor_batch_number')}",
                        "specification_reference": job.get("process_specification"),
                        **{f"microstructure_caption_{slot}": (micro_titles[slot - 1].strip() or None) for slot in range(1, 5)}}
                    saved = inspection.save_metlab(payload, {"rows": result_rows, "chemistry_rows": [], "jominy_rows": [], "requirement_rows": []}, report_id or None)
                    for slot, image in enumerate(micro_files, start=1):
                        if image is not None:
                            inspection.upload_attachment(
                                "METLAB_REPORT", str(saved["id"]), f"MICROSTRUCTURE_{slot}", image,
                                "lab_tests", f"microstructure_image_{slot}_path",
                            )
                save_success_popup(f"OSP {report_type.title()} Report {saved.get('report_number')} saved successfully.", queue_for_rerun=True); st.rerun()
            except Exception as exc: st.error(str(exc))

        if existing:
            disposition_cards([{"label": "Report", "value": existing.get("status"), "foot": existing.get("report_number")}, {"label": "Decision", "value": existing.get("disposition")}, {"label": "Gate", "value": _scope_label(scope)}])
            c = st.columns(3, gap="small")
            validator = c[0].selectbox("Validated By", employee_options, format_func=lambda value: employees.get(value, "— Select —"), key=f"osp_validator_{report_type}_{scope}_{job_id}")
            approver = c[1].selectbox("Approved By", employee_options, format_func=lambda value: employees.get(value, "— Select —"), key=f"osp_approver_{report_type}_{scope}_{job_id}")
            if c[2].button("Finalize OSP Decision", disabled=not perms["can_approve"] or disposition == "PENDING" or not validator or not approver or str(existing.get("status")) == "FINAL", width="stretch"):
                try:
                    if is_dimensional: inspection.finalize_dimensional(report_id, disposition, reason, validator, approver)
                    else: inspection.finalize_metlab(report_id, disposition, reason, validator, approver)
                    save_success_popup("OSP inspection decision finalized and the OSP quality gate was refreshed.", queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))

            delete_table = "inspection_reports" if is_dimensional else "lab_tests"
            if password_delete_panel(
                repo=inspection.repo, table=delete_table, rows=[existing],
                labeler=lambda row: f"{row.get('report_number')} · {_scope_label(scope)}",
                key=f"osp_inspection_delete_{report_type}_{report_id}", can_delete=perms["can_archive"],
                title=f"Delete OSP {report_type.title()} report",
                help_text="Permanently deletes this OSP inspection record after verifying your current QCMS password.",
            ):
                st.rerun()


def render_dimensional() -> None:
    _render("DIMENSIONAL")


def render_metlab() -> None:
    _render("METLAB")
