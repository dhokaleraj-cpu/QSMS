from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.attachments import AttachmentService, AttachmentSlot, render_attachment_manager
from core.catalog import LearnedValueCatalog
from core.database import get_session_client
from core.delete_service import password_delete_panel
from core.osp_service import OSPService
from core.repository import Repository
from core.reporting import controlled_record_pdf_bytes
from core.selection_labels import customer_standard_label, material_grade_label, part_label, party_label, process_label
from core.ui import page_header, save_success_popup, section_bar, subpage_navigation, template_download_row

DRAWING_TYPES = (
    ("FINISH_DRAWING", "Finish Drawing"),
    ("FORGING_DRAWING", "Forging Drawing"),
    ("HEAT_TREATMENT_DRAWING", "Heat Treatment Drawing"),
)


def _labels(rows: list[dict], code: str, name: str) -> dict[str, str]:
    return {str(r["id"]): " · ".join(str(v) for v in (r.get(code), r.get(name)) if v not in (None, "")) for r in rows}


def _upload(repo: Repository, part_id: str, document_type: str, file: Any) -> None:
    client = get_session_client()
    if client is None:
        raise RuntimeError("Live Supabase session is required for drawing upload.")
    ext = Path(file.name).suffix.lower() or ".bin"
    object_path = f"{repo.tenant_id}/parts/{part_id}/{document_type.lower()}_{hashlib.sha1(file.name.encode()).hexdigest()[:8]}{ext}"
    content = file.getvalue()
    client.storage.from_("quality-documents").upload(object_path, content, {"content-type": file.type or "application/octet-stream", "upsert": "true"})
    existing = repo.find_one("document_attachments", eq={"entity_type": "PART_MASTER", "entity_id": part_id, "document_type": document_type})
    payload = {"entity_type": "PART_MASTER", "entity_id": part_id, "document_type": document_type, "file_name": file.name, "object_path": object_path, "mime_type": file.type, "size_bytes": len(content), "checksum": hashlib.sha256(content).hexdigest(), "status": "ACTIVE"}
    if existing:
        repo.update("document_attachments", str(existing["id"]), payload)
    else:
        repo.insert("document_attachments", payload)


def _selected_part(repo: Repository) -> dict:
    parts = repo.select("parts", order_by="part_number", limit=2000)
    requested = str(st.session_state.pop("edit_part_id", "") or "")
    labels = {str(row["id"]): part_label(row) for row in parts}
    options = ["__new__"] + list(labels)
    index = options.index(requested) if requested in options else 0
    selected = st.selectbox("Part Master record", options, index=index, format_func=lambda x: "＋ New Part" if x == "__new__" else labels[x])
    return next((row for row in parts if str(row["id"]) == selected), {})


def _save_rows(repo: Repository, table: str, part_id: str, rows: pd.DataFrame, key_fields: tuple[str, ...], mapper) -> None:
    """Insert/update edited rows. Missing rows are preserved until password deletion."""
    for index, row in rows.iterrows():
        payload = mapper(row, index)
        if not payload:
            continue
        payload["part_id"] = part_id
        natural = {key: payload[key] for key in key_fields}
        repo.upsert_by(table, payload, natural_key=natural)



def _catalog_options(catalog: LearnedValueCatalog, field_key: str, current_values: list[Any]) -> list[str]:
    values = list(catalog.suggestions(field_key))
    values.extend(str(value).strip() for value in current_values if str(value or "").strip())
    return sorted(set(values), key=str.casefold)


def _catalog_add_control(catalog: LearnedValueCatalog, field_key: str, label: str, options: list[str], key: str) -> None:
    cols = st.columns([4, 1], gap="small")
    value = cols[0].selectbox(label, options or [""], accept_new_options=True, key=f"catalog_value_{key}")
    if cols[1].button("Add", key=f"catalog_add_{key}", width="stretch"):
        text = str(value or "").strip()
        if not text:
            st.warning(f"Enter {label.lower()} first.")
        else:
            catalog.remember(field_key, text)
            save_success_popup(f"{text} added to the reusable list.", queue_for_rerun=True)
            st.rerun()



def _optional_number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _three_column_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Parameter": row.get("parameter_name") or "",
        "Minimum Specification": row.get("minimum_spec"),
        "Maximum Specification": row.get("maximum_spec"),
    } for row in rows], columns=["Parameter", "Minimum Specification", "Maximum Specification"])


def _render_osp_metlab_requirements(
    repo: Repository,
    catalog: LearnedValueCatalog,
    part_id: str,
    writable: bool,
    can_delete: bool,
) -> None:
    section_bar("OSP INSPECTION FOR METLAB")
    processes = repo.select(
        "processes",
        eq={"status": "ACTIVE", "process_type": "OUTSOURCED"},
        order_by="process_name",
        limit=1000,
    )
    if not processes:
        st.warning("Create an active OUTSOURCED Process in Process Master before adding OSP MetLAB requirements.")
        st.page_link(
            st.session_state["_qsms_pages"]["process-entry"],
            label="Open Process Master",
            icon=":material/settings:",
            width="stretch",
        )
        return

    process_labels = {
        str(row["id"]): f"{row.get('process_code') or '-'} · {row.get('process_name') or '-'}"
        for row in processes
    }
    selected_process_id = st.selectbox(
        "OSP Process",
        list(process_labels),
        format_func=lambda value: process_labels[value],
        key=f"osp_metlab_process_{part_id}",
    )
    process = next(row for row in processes if str(row["id"]) == selected_process_id)
    group = repo.find_one(
        "part_process_specifications",
        eq={"part_id": part_id, "process_id": selected_process_id, "inward_type": "OSP_PROCESS"},
    )
    parameter_rows = []
    if group:
        parameter_rows = repo.select(
            "part_process_parameter_specifications",
            eq={
                "process_specification_id": str(group["id"]),
                "inspection_type": "METLAB",
                "status": "ACTIVE",
            },
            order_by="sequence_no",
            limit=500,
        )

    if password_delete_panel(
        repo=repo,
        table="part_process_parameter_specifications",
        rows=parameter_rows,
        labeler=lambda row: f"{process.get('process_name')} · {row.get('parameter_name')}",
        key=f"delete_osp_metlab_{part_id}_{selected_process_id}",
        can_delete=can_delete,
        title="Delete OSP MetLAB Parameter",
        help_text="Permanent deletion requires the current QCMS password.",
    ):
        st.rerun()

    editor = st.data_editor(
        _three_column_frame(parameter_rows),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        height=min(430, max(210, 90 + max(len(parameter_rows), 1) * 36)),
        disabled=not writable,
        column_config={
            "Parameter": st.column_config.TextColumn(required=True, width="large"),
            "Minimum Specification": st.column_config.NumberColumn(format="%.4f", width="medium"),
            "Maximum Specification": st.column_config.NumberColumn(format="%.4f", width="medium"),
        },
        key=f"osp_metlab_grid_{part_id}_{selected_process_id}",
    )

    if st.button(
        "Save OSP MetLAB Requirements",
        type="primary",
        disabled=not writable,
        width="stretch",
        key=f"save_osp_metlab_{part_id}_{selected_process_id}",
    ):
        try:
            group_payload = {
                "part_id": part_id,
                "process_id": selected_process_id,
                "inward_type": "OSP_PROCESS",
                "process_specification": f"{process.get('process_name')} MetLAB Inspection",
                "dimensional_required": False,
                "metlab_required": True,
                "sample_quantity": 1,
                "sequence_no": 10,
                "status": "ACTIVE",
            }
            if group:
                group = repo.update("part_process_specifications", str(group["id"]), group_payload)
            else:
                group = repo.insert("part_process_specifications", group_payload)

            existing_by_name = {
                str(row.get("parameter_name") or "").strip().casefold(): row
                for row in parameter_rows
            }
            seen: set[str] = set()
            saved_count = 0
            for index, row in editor.iterrows():
                parameter = str(row.get("Parameter") or "").strip()
                if not parameter:
                    continue
                key = parameter.casefold()
                if key in seen:
                    raise ValueError(f"Duplicate OSP MetLAB Parameter: {parameter}")
                seen.add(key)
                minimum = _optional_number(row.get("Minimum Specification"))
                maximum = _optional_number(row.get("Maximum Specification"))
                if minimum is None and maximum is None:
                    raise ValueError(f"Enter Minimum or Maximum Specification for {parameter}.")
                if minimum is not None and maximum is not None and minimum > maximum:
                    raise ValueError(f"{parameter}: Minimum Specification exceeds Maximum Specification.")
                payload = {
                    "process_specification_id": str(group["id"]),
                    "part_id": part_id,
                    "process_id": selected_process_id,
                    "inward_type": "OSP_PROCESS",
                    "inspection_type": "METLAB",
                    "parameter_name": parameter,
                    "minimum_spec": minimum,
                    "maximum_spec": maximum,
                    "specification_text": None,
                    "unit": None,
                    "characteristic_type": "VARIABLE",
                    "checking_method": None,
                    "sample_size": 1,
                    "is_mandatory": True,
                    "allow_na": False,
                    "sequence_no": 10 * (index + 1),
                    "status": "ACTIVE",
                }
                existing = existing_by_name.get(key)
                if existing:
                    repo.update("part_process_parameter_specifications", str(existing["id"]), payload)
                else:
                    repo.insert("part_process_parameter_specifications", payload)
                catalog.remember("part.osp_metlab_parameter", parameter)
                saved_count += 1
            save_success_popup(f"{saved_count} OSP MetLAB requirement(s) saved for {process.get('process_name')}.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    if group:
        render_attachment_manager(
            repo=repo,
            entity_type="PART_PROCESS_SPEC",
            entity_id=str(group["id"]),
            folder="osp-process-drawings",
            slots=(AttachmentSlot("OSP_PROCESS_DRAWING", "OSP Process Drawing", "Optional controlled drawing for the selected OSP Process"),),
            key_prefix=f"osp_metlab_drawing_{group['id']}",
            can_add_or_replace=writable,
            can_delete=can_delete,
            title=f"{process.get('process_name')} · PROCESS DRAWING",
        )
        active_count = len(parameter_rows)
        if st.button(
            "Create / Update OSP MetLAB Inspection Layout",
            icon=":material/auto_awesome:",
            type="primary",
            disabled=not writable or active_count == 0,
            width="stretch",
            key=f"generate_osp_metlab_layout_{group['id']}",
        ):
            try:
                result = OSPService().generate_layouts(str(group["id"]))
                save_success_popup(
                    f"OSP MetLAB layout generated with {int(result.get('characteristics') or 0)} parameter(s).", queue_for_rerun=True
                )
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _render_metallurgical_requirements(
    repo: Repository,
    catalog: LearnedValueCatalog,
    part_id: str,
    writable: bool,
    can_delete: bool,
) -> None:
    section_bar("METALLURGICAL REQUIREMENTS")
    rows = repo.select(
        "part_metallurgical_requirements",
        eq={"part_id": part_id, "status": "ACTIVE"},
        order_by="sequence_no",
        limit=500,
    )
    if password_delete_panel(
        repo=repo,
        table="part_metallurgical_requirements",
        rows=rows,
        labeler=lambda row: str(row.get("parameter_name") or "Metallurgical Requirement"),
        key=f"delete_metallurgical_{part_id}",
        can_delete=can_delete,
        title="Delete Metallurgical Requirement",
        help_text="Permanent deletion requires the current QCMS password.",
    ):
        st.rerun()

    editor = st.data_editor(
        _three_column_frame(rows),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        height=min(430, max(210, 90 + max(len(rows), 1) * 36)),
        disabled=not writable,
        column_config={
            "Parameter": st.column_config.TextColumn(required=True, width="large"),
            "Minimum Specification": st.column_config.NumberColumn(format="%.4f", width="medium"),
            "Maximum Specification": st.column_config.NumberColumn(format="%.4f", width="medium"),
        },
        key=f"metallurgical_grid_{part_id}",
    )

    if st.button(
        "Save Metallurgical Requirements",
        type="primary",
        disabled=not writable,
        width="stretch",
        key=f"save_metallurgical_{part_id}",
    ):
        try:
            existing_by_name = {
                str(row.get("parameter_name") or "").strip().casefold(): row for row in rows
            }
            seen: set[str] = set()
            saved_count = 0
            for index, row in editor.iterrows():
                parameter = str(row.get("Parameter") or "").strip()
                if not parameter:
                    continue
                key = parameter.casefold()
                if key in seen:
                    raise ValueError(f"Duplicate Metallurgical Parameter: {parameter}")
                seen.add(key)
                minimum = _optional_number(row.get("Minimum Specification"))
                maximum = _optional_number(row.get("Maximum Specification"))
                if minimum is None and maximum is None:
                    raise ValueError(f"Enter Minimum or Maximum Specification for {parameter}.")
                if minimum is not None and maximum is not None and minimum > maximum:
                    raise ValueError(f"{parameter}: Minimum Specification exceeds Maximum Specification.")
                payload = {
                    "part_id": part_id,
                    "parameter_name": parameter,
                    "minimum_spec": minimum,
                    "maximum_spec": maximum,
                    "sequence_no": 10 * (index + 1),
                    "status": "ACTIVE",
                }
                existing = existing_by_name.get(key)
                if existing:
                    repo.update("part_metallurgical_requirements", str(existing["id"]), payload)
                else:
                    repo.insert("part_metallurgical_requirements", payload)
                catalog.remember("part.metallurgical_parameter", parameter)
                saved_count += 1
            save_success_popup(f"{saved_count} Metallurgical Requirement(s) saved successfully.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    if st.button(
        "Create / Update Final Metallurgical Inspection Layout",
        icon=":material/auto_awesome:",
        type="primary",
        disabled=not writable or len(rows) == 0,
        width="stretch",
        key=f"generate_final_metallurgical_layout_{part_id}",
    ):
        try:
            result = repo.rpc("qsms_generate_final_metallurgical_layout", {"p_part_id": part_id}) or {}
            save_success_popup(
                f"Final Metallurgical layout {result.get('plan_number') or ''} Rev {result.get('revision') or ''} generated with {int(result.get('characteristics') or 0)} parameter(s).", queue_for_rerun=True
            )
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

def render_entry() -> None:
    subpage_navigation(
        ("masters", "Back to Masters", ":material/arrow_back:"),
        ("part-records", "Part Master Records", ":material/table_view:"),
    )
    page_header("Part Master · Entry", "Part identity, controlled drawings and all RMTC validation grids.", "New / edit")
    template_download_row([("Part_Master_Template.xlsx", "Download Part Master Template")], key_prefix="part_master")
    repo = Repository(); catalog = LearnedValueCatalog(repo); perms = current_permissions("PART_MASTER")
    existing = _selected_part(repo); writable = perms["can_edit"] if existing else perms["can_create"]

    customers = repo.select("parties", contains={"party_types": ["CUSTOMER"]}, eq={"status": "ACTIVE"}, order_by="party_name", limit=1000)
    grades = repo.select("material_grades", eq={"status": "ACTIVE"}, order_by="grade_code", limit=1000)
    customer_map = {str(row["id"]): party_label(row) for row in customers}
    grade_map = {str(row["id"]): material_grade_label(row) for row in grades}

    section_bar("PART DETAILS", "All fields shown in the approved Part Master layout.")
    with st.form("part_header"):
        c = st.columns(4, gap="small")
        part_number = c[0].text_input("Part Number", value=str(existing.get("part_number") or ""))
        part_name = c[1].text_input("Part Description", value=str(existing.get("part_name") or ""))
        finish_weight = c[2].number_input("Part Finish Weight (kg)", min_value=0.0, value=float(existing.get("finished_weight_kg") or 0), step=0.01)
        status = c[3].selectbox("Status", ["ACTIVE", "INACTIVE"], index=0 if str(existing.get("status") or "ACTIVE") == "ACTIVE" else 1)
        c = st.columns(4, gap="small")
        customer_id = c[0].selectbox("Customer", list(customer_map), format_func=lambda x: customer_map[x], index=list(customer_map).index(str(existing.get("customer_id"))) if str(existing.get("customer_id")) in customer_map else 0) if customer_map else None
        grade_id = c[1].selectbox("Material Grade", list(grade_map), format_func=lambda x: grade_map[x], index=list(grade_map).index(str(existing.get("material_grade_id"))) if str(existing.get("material_grade_id")) in grade_map else 0) if grade_map else None
        drawing_number = c[2].text_input("Drawing Number", value=str(existing.get("drawing_number") or ""))
        drawing_revision = c[3].text_input("Drawing Revision", value=str(existing.get("drawing_revision") or ""))
        remarks = st.text_area("Remarks", value=str(existing.get("remarks") or ""), height=80)
        submitted = st.form_submit_button("Save Part Master", type="primary", disabled=not writable, width="stretch")
    if submitted:
        try:
            if not all([part_number.strip(), part_name.strip(), customer_id, grade_id]):
                raise ValueError("Part Number, Description, Customer and Material Grade are mandatory.")
            payload = {"part_number": part_number.strip(), "part_name": part_name.strip(), "customer_id": customer_id, "material_grade_id": grade_id, "finished_weight_kg": finish_weight, "drawing_number": drawing_number.strip() or None, "drawing_revision": drawing_revision.strip() or None, "status": status, "remarks": remarks.strip() or None}
            for row in repo.select("parts", limit=5000):
                if existing and str(row.get("id")) == str(existing.get("id")):
                    continue
                if str(row.get("part_number") or "").strip().casefold() == part_number.strip().casefold():
                    raise ValueError("Duplicate Part Number is not allowed.")
            saved = repo.update("parts", str(existing["id"]), payload) if existing else repo.insert("parts", payload)
            catalog.remember_many("part.drawing_revision", [drawing_revision])
            st.session_state["edit_part_id"] = str(saved["id"]); save_success_popup("Part Master saved successfully.", queue_for_rerun=True); st.rerun()
        except Exception as exc:
            st.error(str(exc))

    if not existing:
        st.info("Save the Part header first. Drawing attachments and requirement grids will then become available.")
        return
    part_id = str(existing["id"])

    section_bar("CONTROLLED DRAWINGS", "Finish, forging and heat-treatment drawings are stored in private Supabase Storage.")
    attachments = repo.select("document_attachments", eq={"entity_type": "PART_MASTER", "entity_id": part_id, "status": "ACTIVE"}, limit=50)
    amap = {str(a.get("document_type")): a for a in attachments}
    cols = st.columns(3, gap="small")
    for col, (dtype, label) in zip(cols, DRAWING_TYPES):
        with col:
            file = st.file_uploader(label, type=["pdf", "png", "jpg", "jpeg", "dwg", "dxf"], key=f"draw_{dtype}_{part_id}")
            st.caption("Current: " + str((amap.get(dtype) or {}).get("file_name") or "Not attached"))
            if st.button(f"Upload {label}", key=f"up_{dtype}", disabled=not writable or file is None, width="stretch"):
                try:
                    _upload(repo, part_id, dtype, file); save_success_popup(f"{label} uploaded successfully.", queue_for_rerun=True); st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    # Customer Standards / Specifications linked to this Part Master.
    section_bar("CUSTOMER STANDARDS & SPECIFICATIONS", "Link multiple customer/process standards to this Part. Controlled attachments can be downloaded directly from the Part Master.")
    all_standards = repo.select("customer_standards", eq={"status": "ACTIVE"}, order_by="standard_code", limit=3000)
    standards = [
        row for row in all_standards
        if not row.get("customer_id") or str(row.get("customer_id")) == str(existing.get("customer_id"))
    ]
    standard_processes = {str(r["id"]): r for r in repo.select("processes", limit=3000)}
    standard_customers = {str(r["id"]): r for r in repo.select("parties", limit=3000)}
    standard_map = {
        str(row["id"]): customer_standard_label(
            row,
            customer_name=party_label(standard_customers.get(str(row.get("customer_id"))) or {}),
            process_name=process_label(standard_processes.get(str(row.get("process_id"))) or {}),
        )
        for row in standards
    }
    existing_links = repo.select("part_standard_links", eq={"part_id": part_id}, order_by="sequence_no", limit=1000)
    linked_ids = [str(row.get("standard_id")) for row in existing_links if str(row.get("standard_id")) in standard_map]
    selected_standard_ids = st.multiselect(
        "Linked Customer Standards / Specifications",
        list(standard_map),
        default=linked_ids,
        format_func=lambda value: standard_map[value],
        disabled=not writable,
        help="Select one or more controlled standards. Standards are filtered to General standards or the Customer selected in this Part Master.",
    ) if standard_map else []
    if not standard_map:
        st.info("No active Customer Standards / Specifications are available for this Part customer. Create them in the Standards Bank first.")
        st.page_link(st.session_state["_qsms_pages"]["standards-entry"], label="Open Customer Standards Bank", icon=":material/library_books:", width="stretch")
    elif st.button("Save Linked Standards", type="primary", disabled=not writable, width="stretch", key=f"save_part_standards_{part_id}"):
        try:
            keep = set(selected_standard_ids)
            by_standard = {str(row.get("standard_id")): row for row in existing_links}
            for seq, standard_id in enumerate(selected_standard_ids, start=1):
                payload = {"part_id": part_id, "standard_id": standard_id, "sequence_no": seq * 10, "status": "ACTIVE"}
                if standard_id in by_standard:
                    repo.update("part_standard_links", str(by_standard[standard_id]["id"]), payload)
                else:
                    repo.insert("part_standard_links", payload)
            for standard_id, row in by_standard.items():
                if standard_id not in keep:
                    repo.delete("part_standard_links", str(row["id"]))
            save_success_popup("Linked Customer Standards / Specifications saved successfully.", queue_for_rerun=True)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    active_link_rows = repo.select("part_standard_links", eq={"part_id": part_id, "status": "ACTIVE"}, order_by="sequence_no", limit=1000)
    standard_by_id = {str(row["id"]): row for row in all_standards}
    attachment_service = AttachmentService(repo)
    attachment_rows = repo.select("document_attachments", eq={"entity_type": "CUSTOMER_STANDARD", "status": "ACTIVE"}, limit=5000)
    attachment_by_standard = {str(row.get("entity_id")): row for row in attachment_rows if str(row.get("document_type")) == "STANDARD_DOCUMENT"}
    linked_display = []
    for link in active_link_rows:
        standard = standard_by_id.get(str(link.get("standard_id"))) or {}
        if not standard:
            continue
        linked_display.append({
            "Code": standard.get("standard_code"),
            "Standard / Specification": standard.get("standard_name"),
            "Revision": standard.get("revision_number"),
            "Revision Date": standard.get("revision_date"),
            "Related Process": process_label(standard_processes.get(str(standard.get("process_id"))) or {}),
            "Customer": party_label(standard_customers.get(str(standard.get("customer_id"))) or {}) or "General",
            "Author": standard.get("author_name"),
            "Attachment": (attachment_by_standard.get(str(standard.get("id"))) or {}).get("file_name") or "Not attached",
        })
    if linked_display:
        st.dataframe(pd.DataFrame(linked_display), hide_index=True, width="stretch", height=min(280, 72 + len(linked_display) * 36))
        dl_cols = st.columns(min(3, len(active_link_rows)), gap="small") if active_link_rows else []
        for idx, link in enumerate(active_link_rows):
            standard = standard_by_id.get(str(link.get("standard_id"))) or {}
            attachment = attachment_by_standard.get(str(standard.get("id")))
            if not attachment:
                continue
            try:
                content = attachment_service.download(attachment)
            except Exception:
                content = None
            if content is not None:
                with dl_cols[idx % len(dl_cols)]:
                    st.download_button(
                        f"Download {standard.get('standard_code') or 'Standard'} · Rev {standard.get('revision_number') or '-'}",
                        data=content,
                        file_name=str(attachment.get("file_name") or f"{standard.get('standard_code')}.pdf"),
                        mime=str(attachment.get("mime_type") or "application/octet-stream"),
                        key=f"part_standard_download_{part_id}_{standard.get('id')}",
                        width="stretch",
                    )

    suppliers = repo.select("parties", contains={"party_types": ["SUPPLIER"]}, eq={"status": "ACTIVE"}, order_by="party_name", limit=1000)
    supplier_map = {str(row["id"]): party_label(row) for row in suppliers}
    supplier_by_name = {name: sid for sid, name in supplier_map.items()}

    section_bar("RAW MATERIAL DETAILS", "Supplier forging parameters used for steel-to-production quantity validation.")
    raw = repo.select("part_raw_material_details", eq={"part_id": part_id}, order_by="sequence_no", limit=200)
    if password_delete_panel(repo=repo, table="part_raw_material_details", rows=raw, labeler=lambda r: f"{supplier_map.get(str(r.get('supplier_id')), 'Supplier')} · {r.get('section_size') or '-'} · {r.get('forging_route') or '-'}", key=f"delete_raw_{part_id}", can_delete=perms["can_archive"], title="Delete Raw Material row"):
        st.rerun()
    raw_df = pd.DataFrame([{
        "Supplier Name": supplier_map.get(str(r.get("supplier_id")), ""),
        "Forging Weight": r.get("forging_weight_kg"),
        "Gross Weight": r.get("gross_weight_kg"),
        "Input Weight kg/part": r.get("input_weight_kg") or r.get("gross_weight_kg") or r.get("forging_weight_kg"),
        "Section": r.get("section_size"), "Forging Route": r.get("forging_route"),
        "Status": r.get("status") or "ACTIVE"
    } for r in raw], columns=["Supplier Name", "Forging Weight", "Gross Weight", "Input Weight kg/part", "Section", "Forging Route", "Status"])
    section_options = _catalog_options(catalog, "part.rm_section", [r.get("section_size") for r in raw])
    route_options = _catalog_options(catalog, "part.forging_route", [r.get("forging_route") for r in raw])
    with st.expander("Manage reusable Section and Forging Route lists", expanded=False):
        _catalog_add_control(catalog, "part.rm_section", "Section", section_options, f"section_{part_id}")
        _catalog_add_control(catalog, "part.forging_route", "Forging Route", route_options, f"route_{part_id}")
    raw_edit = st.data_editor(
        raw_df, num_rows="dynamic", hide_index=True, width="stretch", height=280, key=f"raw_{part_id}", disabled=not writable,
        column_config={
            "Supplier Name": st.column_config.SelectboxColumn(options=list(supplier_by_name), required=True),
            "Forging Weight": st.column_config.NumberColumn(min_value=0.0, format="%.3f"),
            "Gross Weight": st.column_config.NumberColumn(min_value=0.0, format="%.3f"),
            "Input Weight kg/part": st.column_config.NumberColumn(min_value=0.001, format="%.3f", required=True, help="Steel input required for one production part."),
            "Section": st.column_config.SelectboxColumn(options=section_options or [""], required=True),
            "Forging Route": st.column_config.SelectboxColumn(options=route_options or [""], required=True),
            "Status": st.column_config.SelectboxColumn(options=["ACTIVE", "INACTIVE"]),
        },
    )
    if st.button("Save Raw Material Details", type="primary", disabled=not writable, width="stretch"):
        try:
            def mapper(row, index):
                name = str(row.get("Supplier Name") or "").strip(); sid = supplier_by_name.get(name)
                if not sid: return {}
                catalog.remember_many("part.rm_section", [row.get("Section")]); catalog.remember_many("part.forging_route", [row.get("Forging Route")])
                input_weight = None if pd.isna(row.get("Input Weight kg/part")) else row.get("Input Weight kg/part")
                if input_weight is None or float(input_weight) <= 0:
                    raise ValueError(f"Input Weight kg/part is required for {name}.")
                return {"supplier_id": sid, "forging_weight_kg": None if pd.isna(row.get("Forging Weight")) else row.get("Forging Weight"), "gross_weight_kg": None if pd.isna(row.get("Gross Weight")) else row.get("Gross Weight"), "input_weight_kg": input_weight, "section_size": str(row.get("Section") or "").strip() or None, "forging_route": str(row.get("Forging Route") or "").strip() or None, "sequence_no": 10 * (index + 1), "status": str(row.get("Status") or "ACTIVE")}
            _save_rows(repo, "part_raw_material_details", part_id, raw_edit, ("supplier_id",), mapper); save_success_popup("Raw Material Details saved successfully.", queue_for_rerun=True); st.rerun()
        except Exception as exc:
            st.error(str(exc))
    section_bar("JOMINY REQUIREMENT", "Controlled 1/16 inch to millimetre conversion and HRC requirement band.")
    distances = repo.select("jominy_distances", eq={"status": "ACTIVE"}, order_by="distance_16th", limit=100)
    dmap = {str(d.get("distance_label")): d for d in distances}
    jom = repo.select("part_jominy_requirements", eq={"part_id": part_id}, order_by="sequence_no", limit=100)
    if password_delete_panel(repo=repo, table="part_jominy_requirements", rows=jom, labeler=lambda r: f"{r.get('distance_label')} · {r.get('minimum_hrc')}–{r.get('maximum_hrc')} HRC", key=f"delete_jom_{part_id}", can_delete=perms["can_archive"], title="Delete Jominy Requirement row"):
        st.rerun()
    jdf = pd.DataFrame([{"Distance (inch)": r.get("distance_label"), "MM (Auto)": round(float((dmap.get(str(r.get("distance_label"))) or {}).get("distance_16th") or 0) * 25.4 / 16, 2), "Minimum HRC": r.get("minimum_hrc"), "Maximum HRC": r.get("maximum_hrc"), "Status": r.get("status") or "ACTIVE"} for r in jom], columns=["Distance (inch)", "MM (Auto)", "Minimum HRC", "Maximum HRC", "Status"])
    disabled = True if not writable else ["MM (Auto)"]
    jedit = st.data_editor(jdf, num_rows="dynamic", hide_index=True, width="stretch", height=280, key=f"jom_{part_id}", disabled=disabled, column_config={"Distance (inch)": st.column_config.SelectboxColumn(options=list(dmap), required=True), "MM (Auto)": st.column_config.NumberColumn(format="%.2f"), "Minimum HRC": st.column_config.NumberColumn(format="%.2f"), "Maximum HRC": st.column_config.NumberColumn(format="%.2f"), "Status": st.column_config.SelectboxColumn(options=["ACTIVE", "INACTIVE"])})
    if st.button("Save Jominy Requirements", type="primary", disabled=not writable, width="stretch"):
        try:
            def mapper(row, index):
                label = str(row.get("Distance (inch)") or "").strip()
                if not label: return {}
                distance = dmap.get(label)
                if not distance: raise ValueError(f"Select a valid Jominy distance for {label}.")
                low = None if pd.isna(row.get("Minimum HRC")) else row.get("Minimum HRC"); high = None if pd.isna(row.get("Maximum HRC")) else row.get("Maximum HRC")
                if low is not None and high is not None and float(low) > float(high): raise ValueError(f"Jominy {label}: minimum exceeds maximum.")
                return {"jominy_distance_id": distance.get("id"), "distance_label": label, "minimum_hrc": low, "maximum_hrc": high, "sequence_no": 10 * (index + 1), "status": str(row.get("Status") or "ACTIVE")}
            _save_rows(repo, "part_jominy_requirements", part_id, jedit, ("jominy_distance_id",), mapper); save_success_popup("Jominy Requirements saved successfully.", queue_for_rerun=True); st.rerun()
        except Exception as exc:
            st.error(str(exc))
    _render_osp_metlab_requirements(repo, catalog, part_id, writable, perms["can_archive"])
    _render_metallurgical_requirements(repo, catalog, part_id, writable, perms["can_archive"])



def render_records() -> None:
    subpage_navigation(
        ("dashboard", "Back to Dashboard", ":material/arrow_back:"),
        ("masters", "Back to Masters", ":material/dataset:"),
        ("part-entry", "New Part / Edit", ":material/edit_note:"),
    )
    page_header("Part Master · Records", "Select a Part Master above the full-width register for controlled editing and deletion.", "Records")
    repo = Repository(); perms = current_permissions("PART_MASTER")
    parts = repo.select("parts", order_by="part_number", limit=3000)
    grades = {str(g["id"]): g for g in repo.select("material_grades", limit=3000)}
    customers = {str(p["id"]): p for p in repo.select("parties", contains={"party_types": ["CUSTOMER"]}, limit=3000)}
    search = st.text_input("Search Part Number or Description")
    rows = [p for p in parts if not search or search.casefold() in (str(p.get("part_number")) + " " + str(p.get("part_name"))).casefold()]

    if rows:
        labels = {str(row["id"]): part_label(row) for row in rows}
        selected = st.selectbox("Select Part Master record", list(labels), format_func=lambda x: labels[x])
        st.session_state["edit_part_id"] = selected
        selected_row = next(p for p in rows if str(p.get("id")) == selected)
        c1, c2, c3 = st.columns(3, gap="small")
        with c1:
            st.page_link(st.session_state["_qsms_pages"]["part-entry"], label="Open Selected Part Master", icon=":material/edit:", width="stretch")
        with c2:
            raw_rows = repo.select("part_raw_material_details", eq={"part_id": selected}, order_by="sequence_no", limit=300)
            jominy_rows = repo.select("part_jominy_requirements", eq={"part_id": selected}, order_by="sequence_no", limit=300)
            process_rows = repo.select("part_process_parameter_specifications", eq={"part_id": selected}, order_by="sequence_no", limit=500)
            metallurgy_rows = repo.select("part_metallurgical_requirements", eq={"part_id": selected}, order_by="sequence_no", limit=500)
            standard_links = repo.select("part_standard_links", eq={"part_id": selected, "status": "ACTIVE"}, order_by="sequence_no", limit=500)
            standards_all = {str(r["id"]): r for r in repo.select("customer_standards", limit=3000)}
            processes_all = {str(r["id"]): r for r in repo.select("processes", limit=3000)}
            parties_all = {str(r["id"]): r for r in repo.select("parties", limit=3000)}
            standard_rows = [{
                "Standard Code": (standards_all.get(str(link.get("standard_id"))) or {}).get("standard_code"),
                "Standard / Specification": (standards_all.get(str(link.get("standard_id"))) or {}).get("standard_name"),
                "Revision": (standards_all.get(str(link.get("standard_id"))) or {}).get("revision_number"),
                "Revision Date": (standards_all.get(str(link.get("standard_id"))) or {}).get("revision_date"),
                "Related Process": process_label(processes_all.get(str((standards_all.get(str(link.get("standard_id"))) or {}).get("process_id"))) or {}),
                "Customer": party_label(parties_all.get(str((standards_all.get(str(link.get("standard_id"))) or {}).get("customer_id"))) or {}) or "General",
            } for link in standard_links]
            pdf = controlled_record_pdf_bytes(
                "PART MASTER RECORD",
                {
                    "Part Number": selected_row.get("part_number"), "Part Description": selected_row.get("part_name"),
                    "Customer": (customers.get(str(selected_row.get("customer_id"))) or {}).get("party_name"),
                    "Material Grade": (grades.get(str(selected_row.get("material_grade_id"))) or {}).get("grade_code"),
                    "Finish Weight kg": selected_row.get("finished_weight_kg"), "Drawing Number": selected_row.get("drawing_number"),
                    "Drawing Revision": selected_row.get("drawing_revision"), "Status": selected_row.get("status"), "Remarks": selected_row.get("remarks"),
                },
                {
                    "Linked Customer Standards / Specifications": standard_rows,
                    "Raw Material Details": raw_rows,
                    "Jominy Requirements": jominy_rows,
                    "OSP / Process Inspection Requirements": process_rows,
                    "Metallurgical Requirements": metallurgy_rows,
                },
                record_number=str(selected_row.get("part_number") or ""),
            )
            st.download_button("Download Part Master PDF", pdf, file_name=f"Part_Master_{selected_row.get('part_number')}.pdf", mime="application/pdf", width="stretch")
        with c3:
            if password_delete_panel(
                repo=repo,
                table="parts",
                rows=[selected_row],
                labeler=lambda r: f"{r.get('part_number')} · {r.get('part_name')}",
                key=f"delete_part_{selected}",
                can_delete=perms["can_archive"],
                title="Delete Selected Part Master",
                help_text="Permanent deletion is allowed only when no protected transaction depends on this Part. Otherwise set the Part to Inactive.",
            ):
                st.rerun()
    else:
        st.info("No Part Master records match the search.")

    section_bar("PART MASTER REGISTER", "The selected record and actions are intentionally shown above the register.")
    df = pd.DataFrame([{"Part Number": p.get("part_number"), "Part Description": p.get("part_name"), "Finish Weight kg": p.get("finished_weight_kg"), "Customer": (customers.get(str(p.get("customer_id"))) or {}).get("party_name"), "Material Grade": (grades.get(str(p.get("material_grade_id"))) or {}).get("grade_code"), "Drawing": p.get("drawing_number"), "Revision": p.get("drawing_revision"), "Status": p.get("status")} for p in rows])
    st.dataframe(df, hide_index=True, width="stretch", height=620)
