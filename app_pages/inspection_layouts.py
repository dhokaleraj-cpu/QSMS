from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st
from core.ui import portal_table

from core.access import current_permissions
from core.attachments import AttachmentService
from core.delete_service import password_delete_panel
from core.inspection_service import InspectionService
from core.reporting import controlled_record_pdf_bytes
from core.ui import page_header, save_success_popup, section_bar, subpage_navigation, template_download_row
from core.selection_labels import part_label


def _maps(service: InspectionService):
    parts = service.parts(); processes = service.processes(); stages = service.stages()
    return (
        parts, {str(r["id"]): part_label(r) for r in parts},
        {str(r["id"]): f"{r.get('process_code')} · {r.get('process_name')}" for r in processes},
        {str(r["id"]): f"{r.get('stage_code')} · {r.get('stage_name')}" for r in stages},
    )


def _rows_frame(rows: list[dict], default_sample: int) -> pd.DataFrame:
    records = []
    for position, row in enumerate(rows, start=1):
        records.append({
            "Sequence": int(row.get("sequence_no") or position),
            "Characteristic No": row.get("characteristic_no") or str(position),
            "Parameter": row.get("characteristic") or "",
            "Specification": row.get("specification") or "",
            "Minimum": row.get("lower_spec"),
            "Maximum": row.get("upper_spec"),
            "Unit": row.get("unit") or "",
            "Type": "TEXT" if str(row.get("characteristic_type") or "NUMBER").upper() in {"TEXT", "ATTRIBUTE"} else "NUMBER",
            "Checking Aid": row.get("checking_aid_text") or row.get("checking_method") or "",
            "Sample Size": int(row.get("sample_size") or default_sample or 1),
            "Allow NA": bool(row.get("allow_na")),
            "Mandatory": bool(row.get("is_mandatory", True)),
            "Section": row.get("report_section") or "",
            "Status": row.get("status") or "ACTIVE",
            "_id": row.get("id"),
        })
    return pd.DataFrame(records)


def render_entry() -> None:
    subpage_navigation(("masters", "Masters", ":material/dataset:"), ("inspection-home", "Inspections", ":material/biotech:"), ("inspection-layout-records", "Layout Records", ":material/table_view:"))
    page_header("Inspection Layout Master", context="Part · Process · Stage")
    template_download_row([("Inspection_Layout_Template.xlsx", "Download Generic Layout Template"), ("Dimensional_Inspection_Report_Template.xlsx", "Download Dimensional Template"), ("MetLAB_Report_Layout_Template.xlsx", "Download MetLAB Template")], key_prefix="inspection_layout")
    service = InspectionService(); perms = current_permissions("INSPECTION_LAYOUTS")
    parts, part_map, process_map, stage_map = _maps(service)
    process_rows = {str(row["id"]): row for row in service.processes()}
    if not parts:
        st.warning("Create an active Part Master first.")
        return

    requested = str(st.session_state.get("edit_inspection_layout_id") or "")
    existing = service.get_plan(requested) if requested else None
    layout_type = st.selectbox("Layout Type", ["DIMENSIONAL", "METLAB"], index=0 if not existing or existing.get("layout_type") == "DIMENSIONAL" else 1)
    all_plans = service.plans(layout_type)
    labels = {str(row["id"]): f"{row.get('plan_number')} Rev {row.get('revision')} · {part_map.get(str(row.get('part_id')), 'Part')}" for row in all_plans}
    options = ["__new__"] + list(labels)
    selected = st.selectbox("Select Layout", options, index=options.index(requested) if requested in options else 0, format_func=lambda value: "＋ New Layout" if value == "__new__" else labels[value])
    if selected != "__new__" and selected != requested:
        st.session_state["edit_inspection_layout_id"] = selected
        st.rerun()
    if selected == "__new__" and requested:
        st.session_state.pop("edit_inspection_layout_id", None)
        existing = None
    elif selected != "__new__":
        existing = service.get_plan(selected)

    current_part = str((existing or {}).get("part_id") or next(iter(part_map)))
    current_process = str((existing or {}).get("process_id") or "")
    current_stage = str((existing or {}).get("inspection_stage_id") or "")
    inward_type_options = ["MATERIAL_INWARD", "OSP_PROCESS"]
    current_inward_type = str((existing or {}).get("inward_type") or "MATERIAL_INWARD")
    c1, c2, c3, c4, c5 = st.columns(5, gap="small")
    part_id = c1.selectbox("Part Number", list(part_map), index=list(part_map).index(current_part) if current_part in part_map else 0, format_func=lambda value: part_map[value])
    inward_type = c2.selectbox("Inward Type", inward_type_options, index=inward_type_options.index(current_inward_type) if current_inward_type in inward_type_options else 0, format_func=lambda value: value.replace("_", " ").title())
    allowed_process_ids = [pid for pid in process_map if inward_type != "OSP_PROCESS" or str((process_rows.get(pid) or {}).get("process_type")) == "OUTSOURCED"]
    process_options = [""] + allowed_process_ids
    if current_process and current_process not in process_options:
        process_options.append(current_process)
    process_id = c3.selectbox("Process", process_options, index=process_options.index(current_process) if current_process in process_options else 0, format_func=lambda value: process_map.get(value, "— Not selected —"))
    stage_options = [""] + list(stage_map)
    stage_id = c4.selectbox("Inspection Stage", stage_options, index=stage_options.index(current_stage) if current_stage in stage_options else 0, format_func=lambda value: stage_map.get(value, "— Not selected —"))
    status = c5.selectbox("Status", ["DRAFT", "APPROVAL_PENDING", "APPROVED", "SUPERSEDED"], index=["DRAFT", "APPROVAL_PENDING", "APPROVED", "SUPERSEDED"].index(str((existing or {}).get("status") or "DRAFT")))
    if inward_type == "OSP_PROCESS" and not process_id:
        st.warning("An OSP Process layout requires the outsourced Process selected in the Part Master specification.")

    c1, c2, c3, c4 = st.columns(4, gap="small")
    plan_no = c1.text_input("Plan Number", value=str((existing or {}).get("plan_number") or ""))
    revision = c2.text_input("Revision", value=str((existing or {}).get("revision") or "00"))
    layout_name = c3.text_input("Layout Name", value=str((existing or {}).get("layout_name") or ""))
    default_sample = c4.number_input("Default Sample Size", min_value=1, max_value=20, value=int((existing or {}).get("default_sample_size") or (6 if layout_type == "DIMENSIONAL" else 1)), step=1)

    c1, c2, c3, c4 = st.columns(4, gap="small")
    report_title = c1.text_input("Report Title", value=str((existing or {}).get("report_title") or ("DIMENSIONAL INSPECTION REPORT" if layout_type == "DIMENSIONAL" else "METLAB REPORT")))
    format_no = c2.text_input("Format Number", value=str((existing or {}).get("format_number") or ""))
    format_rev = c3.text_input("Format Revision", value=str((existing or {}).get("format_revision") or "00"))
    effective = c4.date_input("Effective Date", value=date.fromisoformat(str((existing or {}).get("effective_date"))[:10]) if (existing or {}).get("effective_date") else date.today(), format="DD-MM-YYYY")

    imported = None
    if layout_type == "DIMENSIONAL":
        upload = st.file_uploader("Import Dimensional Layout (.xlsx)", type=["xlsx"], key=f"layout_import_{selected}")
        if upload is not None:
            try:
                imported = service.parse_dimensional_workbook(upload)
                st.session_state["inspection_layout_import"] = imported
                st.success(f"Imported {len(imported['characteristics'])} characteristics from {upload.name}.")
            except Exception as exc:
                st.error(str(exc))
    imported = imported or st.session_state.get("inspection_layout_import")

    source_rows = service.plan_characteristics(str((existing or {}).get("id"))) if existing else []
    osp_group = None
    if inward_type == "OSP_PROCESS" and process_id:
        if existing and (existing or {}).get("source_process_specification_id"):
            osp_group = service.repo.get("part_process_specifications", str((existing or {}).get("source_process_specification_id")))
        if osp_group is None:
            osp_group, grouped_rows = service.osp_parameter_characteristics(part_id, process_id, layout_type)
            if not existing and not imported:
                source_rows = grouped_rows
        if osp_group:
            st.info(
                f"Part Master OSP group loaded: {osp_group.get('process_specification')} · "
                f"Drawing {osp_group.get('drawing_number') or 'not numbered'} Rev {osp_group.get('drawing_revision') or '-'}"
            )
            drawing_rows = AttachmentService(service.repo).list_active("PART_PROCESS_SPEC", str(osp_group.get("id")))
            drawing = next((row for row in drawing_rows if str(row.get("document_type")) == "OSP_PROCESS_DRAWING"), None)
            if drawing:
                try:
                    st.download_button(
                        "Download OSP Process Drawing",
                        data=AttachmentService(service.repo).download(drawing),
                        file_name=str(drawing.get("file_name") or "OSP_Process_Drawing"),
                        mime=str(drawing.get("mime_type") or "application/octet-stream"),
                        icon=":material/download:", width="stretch",
                        key=f"layout_process_drawing_{osp_group.get('id')}_{layout_type}",
                    )
                except Exception as exc:
                    st.warning(f"OSP Process drawing is linked but cannot be downloaded: {exc}")
            if not existing and source_rows:
                st.success(f"{len(source_rows)} {layout_type.title()} parameter(s) loaded from the selected Part + OSP Process group.")
        elif not existing:
            st.warning("No active Part Master OSP Process group and parameters match this Part and Process.")

    if imported and not existing:
        source_rows = imported.get("characteristics") or []
        metadata = imported.get("metadata") or {}
        report_title = metadata.get("report_title") or report_title
        format_no = metadata.get("format_number") or format_no
        format_rev = metadata.get("format_revision") or format_rev
        default_sample = int(metadata.get("default_sample_size") or default_sample)

    section_bar("LAYOUT CHARACTERISTICS")
    frame = _rows_frame(source_rows, int(default_sample))
    if not frame.empty:
        frame["Section"] = layout_type
    if frame.empty:
        frame = pd.DataFrame([{
            "Sequence": 10, "Characteristic No": "1", "Parameter": "", "Specification": "", "Minimum": None,
            "Maximum": None, "Unit": "", "Type": "NUMBER", "Checking Aid": "", "Sample Size": int(default_sample),
            "Allow NA": False, "Mandatory": True, "Section": layout_type, "Status": "ACTIVE", "_id": None,
        }])
    edited = st.data_editor(
        frame,
        hide_index=True,
        width="stretch",
        height=min(600, max(220, 95 + len(frame) * 34)),
        num_rows="dynamic",
        disabled=["Section"],
        column_config={
            "Type": st.column_config.SelectboxColumn(options=["NUMBER", "TEXT"], required=True),
            "Status": st.column_config.SelectboxColumn(options=["ACTIVE", "INACTIVE"], required=True),
            "Allow NA": st.column_config.CheckboxColumn(),
            "Mandatory": st.column_config.CheckboxColumn(),
            "_id": None,
        },
        key=f"layout_grid_{selected}_{layout_type}",
    )

    writable = perms["can_edit"] if existing else perms["can_create"]
    if st.button("Save Inspection Layout", type="primary", disabled=not writable, width="stretch"):
        try:
            if not plan_no.strip() or not layout_name.strip():
                raise ValueError("Plan Number and Layout Name are required.")
            if inward_type == "OSP_PROCESS" and not process_id:
                raise ValueError("Select the outsourced Process for an OSP Process layout.")
            if inward_type == "OSP_PROCESS" and str((process_rows.get(process_id) or {}).get("process_type")) != "OUTSOURCED":
                raise ValueError("OSP Process layouts can use only an OUTSOURCED Process Master.")
            if not existing:
                duplicate_plan = service.repo.find_one("inspection_plans", eq={
                    "part_id": part_id, "plan_number": plan_no.strip(), "revision": revision.strip() or "00", "layout_type": layout_type,
                })
                if duplicate_plan:
                    raise ValueError("Duplicate inspection layout was skipped. The same Part + Plan Number + Revision + Layout Type already exists in QCMS.")
            payload = {
                "part_id": part_id, "process_id": process_id or None, "inspection_stage_id": stage_id or None, "inward_type": inward_type,
                "plan_number": plan_no.strip(), "revision": revision.strip() or "00", "effective_date": effective.isoformat(),
                "sample_plan": f"{int(default_sample)} samples", "status": status, "layout_type": layout_type,
                "layout_name": layout_name.strip(), "report_title": report_title.strip() or None,
                "format_number": format_no.strip() or None, "format_revision": format_rev.strip() or None,
                "default_sample_size": int(default_sample),
                "source_template_name": ((imported or {}).get("metadata") or {}).get("source_template_name") if imported else ((existing or {}).get("source_template_name") or ("PART_MASTER_OSP_PROCESS_GROUP" if osp_group else None)),
                "source_process_specification_id": str(osp_group.get("id")) if osp_group else (existing or {}).get("source_process_specification_id"),
            }
            rows = []
            for _, row in edited.iterrows():
                if not str(row.get("Parameter") or "").strip():
                    continue
                ctype = str(row.get("Type") or "NUMBER").upper()
                specification = str(row.get("Specification") or "").strip() or None
                lower = None if pd.isna(row.get("Minimum")) else row.get("Minimum")
                upper = None if pd.isna(row.get("Maximum")) else row.get("Maximum")
                if ctype == "TEXT":
                    if not specification:
                        raise ValueError(f"Text Specification is mandatory for {row.get('Parameter')}.")
                    lower = upper = None
                elif lower is None and upper is None:
                    raise ValueError(f"Minimum or Maximum Specification is mandatory for numeric parameter {row.get('Parameter')}.")
                rows.append({
                    "sequence_no": int(row.get("Sequence") or len(rows) + 1), "characteristic_no": row.get("Characteristic No"),
                    "characteristic": row.get("Parameter"), "specification": specification,
                    "lower_spec": lower, "upper_spec": upper, "unit": row.get("Unit"),
                    "characteristic_type": ctype, "checking_aid_text": row.get("Checking Aid"),
                    "sample_size": int(row.get("Sample Size") or default_sample), "allow_na": bool(row.get("Allow NA")),
                    "is_mandatory": bool(row.get("Mandatory")), "report_section": layout_type,
                    "status": row.get("Status") or "ACTIVE", "id": row.get("_id"),
                })
            saved = service.save_plan(payload, rows, str(existing["id"]) if existing else None)
            st.session_state["edit_inspection_layout_id"] = str(saved["id"])
            st.session_state.pop("inspection_layout_import", None)
            save_success_popup("Inspection layout saved successfully.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def render_records() -> None:
    subpage_navigation(("masters", "Masters", ":material/dataset:"), ("inspection-home", "Inspections", ":material/biotech:"), ("inspection-layout-entry", "New / Edit Layout", ":material/edit_note:"))
    page_header("Inspection Layout Records", context="Select before action")
    service = InspectionService(); perms = current_permissions("INSPECTION_LAYOUTS")
    parts = {str(row["id"]): row for row in service.parts()}; processes = {str(row["id"]): row for row in service.processes()}; stages = {str(row["id"]): row for row in service.stages()}
    c1, c2 = st.columns([1, 3], gap="small")
    layout_type = c1.selectbox("Layout Type", ["ALL", "DIMENSIONAL", "METLAB"])
    search = c2.text_input("Search Plan, Layout or Part")
    rows = service.plans(None if layout_type == "ALL" else layout_type)
    filtered = []
    for row in rows:
        part = parts.get(str(row.get("part_id"))) or {}
        text = " ".join(str(value or "") for value in (row.get("plan_number"), row.get("layout_name"), part.get("part_number"), part.get("part_name")))
        if not search or search.casefold() in text.casefold(): filtered.append(row)

    if filtered:
        labels = {str(row["id"]): f"{row.get('plan_number')} Rev {row.get('revision')} · {(parts.get(str(row.get('part_id'))) or {}).get('part_number')} · {row.get('layout_type')}" for row in filtered}
        selected = st.selectbox("Select Layout Record", list(labels), format_func=lambda value: labels[value])
        selected_row = next(row for row in filtered if str(row["id"]) == selected)
        st.session_state["edit_inspection_layout_id"] = selected
        c1, c2, c3 = st.columns(3, gap="small")
        with c1:
            st.page_link(st.session_state["_qsms_pages"]["inspection-layout-entry"], label="Open Selected Layout", icon=":material/edit:", width="stretch")
        with c2:
            characteristics = service.plan_characteristics(selected)
            pdf = controlled_record_pdf_bytes(
                "INSPECTION LAYOUT RECORD",
                {
                    "Plan Number": selected_row.get("plan_number"), "Revision": selected_row.get("revision"), "Layout Type": selected_row.get("layout_type"),
                    "Layout Name": selected_row.get("layout_name"), "Part Number": (parts.get(str(selected_row.get("part_id"))) or {}).get("part_number"), "FSI Part Number": (parts.get(str(selected_row.get("part_id"))) or {}).get("fsi_part_number"),
                    "Process": (processes.get(str(selected_row.get("process_id"))) or {}).get("process_name"), "Stage": (stages.get(str(selected_row.get("inspection_stage_id"))) or {}).get("stage_name"),
                    "Default Samples": selected_row.get("default_sample_size"), "Format": selected_row.get("format_number"), "Status": selected_row.get("status"),
                },
                {"Inspection Characteristics": [{
                    "Seq": row.get("sequence_no"), "Characteristic No.": row.get("characteristic_no"), "Parameter": row.get("characteristic"),
                    "Specification": row.get("specification"), "Minimum": row.get("lower_spec"), "Maximum": row.get("upper_spec"),
                    "Unit": row.get("unit"), "Type": row.get("characteristic_type"), "Checking Method": row.get("checking_method"),
                    "Sample Size": row.get("sample_size"), "Frequency": row.get("frequency"),
                } for row in characteristics]},
                record_number=f"{selected_row.get('plan_number')}-REV-{selected_row.get('revision')}",
            )
            st.download_button("Download Layout PDF", pdf, file_name=f"Inspection_Layout_{selected_row.get('plan_number')}_Rev_{selected_row.get('revision')}.pdf", mime="application/pdf", width="stretch")
        with c3:
            if password_delete_panel(repo=service.repo, table="inspection_plans", rows=[selected_row], labeler=lambda row: f"{row.get('plan_number')} Rev {row.get('revision')}", key=f"delete_layout_{selected}", can_delete=perms["can_archive"], title="Delete Selected Layout", help_text="Current password and Layout Delete permission are required. Characteristics are removed with the layout."):
                st.rerun()
    else:
        st.info("No layout records found.")

    section_bar("LAYOUT REGISTER")
    display = pd.DataFrame([{
        "Plan Number": row.get("plan_number"), "Revision": row.get("revision"), "Layout Type": row.get("layout_type"),
        "Inward Type": str(row.get("inward_type") or "MATERIAL_INWARD").replace("_", " ").title(),
        "Layout Name": row.get("layout_name"), "Part Number": (parts.get(str(row.get("part_id"))) or {}).get("part_number"), "FSI Part Number": (parts.get(str(row.get("part_id"))) or {}).get("fsi_part_number"),
        "Process": (processes.get(str(row.get("process_id"))) or {}).get("process_name"),
        "Stage": (stages.get(str(row.get("inspection_stage_id"))) or {}).get("stage_name"),
        "Samples": row.get("default_sample_size"), "Format": row.get("format_number"), "Status": row.get("status"),
    } for row in filtered])
    portal_table(display, hide_index=True, width="stretch", height=520)
