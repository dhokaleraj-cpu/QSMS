from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from core.ui import portal_table

from core.access import current_permissions, section_permissions
from core.auth import current_profile
from core.attachments import AttachmentService, AttachmentSlot, render_attachment_manager
from core.catalog import LearnedValueCatalog
from core.database import get_session_client
from core.delete_service import password_delete_panel
from core.osp_service import OSPService
from core.master_service import MasterService
from core.master_definitions import MASTER_BY_KEY
from core.repository import Repository
from core.reporting import controlled_record_pdf_bytes
from core.permissions import is_admin
from core.selection_labels import customer_standard_label, material_grade_label, part_label, party_label, process_label
from core.ui import consume_master_blank_request, page_header, record_widget_token, save_success_popup, section_bar, stage_section, subpage_navigation, template_download_row

DRAWING_TYPES = (
    ("FINISH_DRAWING", "Finish Drawing"),
    ("FORGING_DRAWING", "Forging Drawing"),
    ("HEAT_TREATMENT_DRAWING", "Heat Treatment Drawing"),
)

RAW_MATERIAL_TYPE_DEFAULTS = ("Round Black Bar", "Bright Bar")


def _labels(rows: list[dict], code: str, name: str) -> dict[str, str]:
    return {str(r["id"]): " · ".join(str(v) for v in (r.get(code), r.get(name)) if v not in (None, "")) for r in rows}


def _storage_token(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", str(value or "").strip()).strip("._-") or "drawing"


def _save_drawing_revision(
    repo: Repository,
    part_id: str,
    document_type: str,
    drawing_number: str,
    revision_number: str,
    revision_date: date,
    file: Any,
) -> dict:
    """Store a new controlled drawing revision without overwriting earlier files."""
    client = get_session_client()
    if client is None:
        raise RuntimeError("Live Supabase session is required for controlled drawing upload.")
    drawing_number = str(drawing_number or "").strip()
    revision_number = str(revision_number or "").strip()
    if not drawing_number:
        raise ValueError("Drawing Number is mandatory.")
    if not revision_number:
        raise ValueError("Revision Number is mandatory.")
    if revision_date is None:
        raise ValueError("Revision Date is mandatory.")
    if file is None:
        raise ValueError("Select the controlled drawing file.")

    ext = Path(file.name).suffix.lower() or ".bin"
    content = file.getvalue()
    if not content:
        raise ValueError("The selected drawing file is empty.")
    object_path = (
        f"{repo.tenant_id}/parts/{part_id}/controlled_drawings/{document_type.lower()}/"
        f"{_storage_token(drawing_number)}/{_storage_token(revision_number)}_"
        f"{uuid.uuid4().hex[:10]}{ext}"
    )
    client.storage.from_("quality-documents").upload(
        object_path,
        content,
        {"content-type": file.type or "application/octet-stream", "upsert": "false"},
    )
    try:
        result = repo.rpc(
            "qcms_activate_part_drawing_revision",
            {
                "p_part_id": part_id,
                "p_document_type": document_type,
                "p_drawing_number": drawing_number,
                "p_revision": revision_number,
                "p_revision_date": revision_date.isoformat(),
                "p_file_name": str(file.name),
                "p_object_path": object_path,
                "p_mime_type": file.type or "application/octet-stream",
                "p_size_bytes": len(content),
                "p_checksum": hashlib.sha256(content).hexdigest(),
            },
        )
    except Exception:
        try:
            client.storage.from_("quality-documents").remove([object_path])
        except Exception:
            pass
        raise
    if isinstance(result, list):
        return dict(result[0]) if result else {}
    return dict(result or {})


def _drawing_label(row: dict) -> str:
    dtype = dict(DRAWING_TYPES).get(str(row.get("document_type")), str(row.get("document_type") or "Drawing"))
    return (
        f"{dtype} · {row.get('drawing_number') or 'No drawing no.'} · "
        f"Rev {row.get('revision') or '-'} · {row.get('revision_date') or '-'} · "
        f"{str(row.get('status') or '').title()}"
    )


def _selected_part(repo: Repository, *, force_new: bool = False) -> tuple[dict, str]:
    parts = repo.select("parts", order_by="part_number", limit=2000)
    requested = str(st.session_state.pop("edit_part_id", "") or "")
    labels = {str(row["id"]): part_label(row) for row in parts}
    options = ["__new__"] + list(labels)
    selector_key = "part_master_record_selector"
    if force_new:
        st.session_state[selector_key] = "__new__"
    elif requested in options:
        st.session_state[selector_key] = requested
    elif st.session_state.get(selector_key) not in options:
        st.session_state[selector_key] = "__new__"
    selected = st.selectbox("Part Master record", options, format_func=lambda x: "＋ New Part" if x == "__new__" else labels[x], key=selector_key)
    return next((row for row in parts if str(row["id"]) == selected), {}), selected


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


def _catalog_add_control(
    catalog: LearnedValueCatalog, field_key: str, label: str, options: list[str], key: str, *, duplicate_word_check: bool = False,
) -> None:
    cols = st.columns([4, 1], gap="small")
    value = cols[0].selectbox(label, options or [""], accept_new_options=True, key=f"catalog_value_{key}")
    if cols[1].button("Add", key=f"catalog_add_{key}", width="stretch"):
        text = str(value or "").strip()
        if not text:
            st.warning(f"Enter {label.lower()} first.")
            return
        normalized = " ".join(re.findall(r"[a-z0-9]+", text.casefold()))
        for existing in options:
            existing_text = str(existing or "").strip()
            existing_normalized = " ".join(re.findall(r"[a-z0-9]+", existing_text.casefold()))
            if normalized and normalized == existing_normalized:
                st.warning(f"{label} already exists in the reusable list: {existing_text}")
                return
            if duplicate_word_check and MasterService._fuzzy_word_duplicate(text, existing_text):
                st.warning(f"Duplicate {label} is not allowed. 2-3 matching words already exist in: {existing_text}")
                return
        catalog.remember(field_key, text)
        save_success_popup(f"{text} added to the reusable list.", queue_for_rerun=True)
        st.rerun()



def _optional_number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _requirement_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        "Parameter": row.get("parameter_name") or "",
        "Type": "TEXT" if str(row.get("characteristic_type") or "NUMBER").upper() in {"TEXT", "ATTRIBUTE"} else "NUMBER",
        "Text Specification": row.get("specification_text") or "",
        "Minimum Specification": row.get("minimum_spec"),
        "Maximum Specification": row.get("maximum_spec"),
    } for row in rows], columns=["Parameter", "Type", "Text Specification", "Minimum Specification", "Maximum Specification"])


def _render_osp_metlab_requirements(
    repo: Repository,
    catalog: LearnedValueCatalog,
    part_id: str,
    writable: bool,
    can_delete: bool,
    *,
    show_heading: bool = True,
) -> None:
    if show_heading:
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

    with st.form(f"osp_metlab_requirements_form_{part_id}_{selected_process_id}"):
        editor = st.data_editor(
            _requirement_frame(parameter_rows),
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            height=min(430, max(210, 90 + max(len(parameter_rows), 1) * 36)),
            disabled=not writable,
            column_config={
                "Parameter": st.column_config.TextColumn(required=True, width="large"),
                "Type": st.column_config.SelectboxColumn(options=["NUMBER", "TEXT"], required=True, width="small"),
                "Text Specification": st.column_config.TextColumn(width="large", help="Required for TEXT parameters. Actual text passes at 75% or greater similarity."),
                "Minimum Specification": st.column_config.NumberColumn(format="%.4f", width="medium"),
                "Maximum Specification": st.column_config.NumberColumn(format="%.4f", width="medium"),
            },
            key=f"osp_metlab_grid_{part_id}_{selected_process_id}",
        )
        save_requirements = st.form_submit_button(
            "Save OSP MetLAB Requirements",
            type="primary",
            disabled=not writable,
            width="stretch",
        )

    if save_requirements:
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
                ctype = str(row.get("Type") or "NUMBER").upper()
                text_spec = str(row.get("Text Specification") or "").strip()
                minimum = _optional_number(row.get("Minimum Specification"))
                maximum = _optional_number(row.get("Maximum Specification"))
                if ctype == "TEXT":
                    if not text_spec:
                        raise ValueError(f"Enter Text Specification for {parameter}.")
                    minimum = maximum = None
                else:
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
                    "specification_text": text_spec or None,
                    "unit": None,
                    "characteristic_type": ctype,
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
    *,
    show_heading: bool = True,
) -> None:
    if show_heading:
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

    with st.form(f"metallurgical_requirements_form_{part_id}"):
        editor = st.data_editor(
            _requirement_frame(rows),
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            height=min(430, max(210, 90 + max(len(rows), 1) * 36)),
            disabled=not writable,
            column_config={
                "Parameter": st.column_config.TextColumn(required=True, width="large"),
                "Type": st.column_config.SelectboxColumn(options=["NUMBER", "TEXT"], required=True, width="small"),
                "Text Specification": st.column_config.TextColumn(width="large", help="Required for TEXT parameters. Actual text passes at 75% or greater similarity."),
                "Minimum Specification": st.column_config.NumberColumn(format="%.4f", width="medium"),
                "Maximum Specification": st.column_config.NumberColumn(format="%.4f", width="medium"),
            },
            key=f"metallurgical_grid_{part_id}",
        )
        save_metallurgy = st.form_submit_button(
            "Save Metallurgical Requirements",
            type="primary",
            disabled=not writable,
            width="stretch",
        )

    if save_metallurgy:
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
                ctype = str(row.get("Type") or "NUMBER").upper()
                text_spec = str(row.get("Text Specification") or "").strip()
                minimum = _optional_number(row.get("Minimum Specification"))
                maximum = _optional_number(row.get("Maximum Specification"))
                if ctype == "TEXT":
                    if not text_spec:
                        raise ValueError(f"Enter Text Specification for {parameter}.")
                    minimum = maximum = None
                else:
                    if minimum is None and maximum is None:
                        raise ValueError(f"Enter Minimum or Maximum Specification for {parameter}.")
                    if minimum is not None and maximum is not None and minimum > maximum:
                        raise ValueError(f"{parameter}: Minimum Specification exceeds Maximum Specification.")
                payload = {
                    "part_id": part_id,
                    "parameter_name": parameter,
                    "characteristic_type": ctype,
                    "specification_text": text_spec or None,
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
    force_new = consume_master_blank_request("part-entry", edit_keys=("edit_part_id",), widget_keys=("part_master_record_selector",))
    existing, selected_record = _selected_part(repo, force_new=force_new); writable = perms["can_edit"] if existing else perms["can_create"]
    header_scope = record_widget_token("part-entry", existing, selected=selected_record)

    customers = repo.select("parties", contains={"party_types": ["CUSTOMER"]}, eq={"status": "ACTIVE"}, order_by="party_name", limit=1000)
    grades = repo.select("material_grades", eq={"status": "ACTIVE"}, order_by="grade_code", limit=1000)
    customer_map = {str(row["id"]): party_label(row) for row in customers}
    grade_map = {str(row["id"]): material_grade_label(row) for row in grades}
    existing_grade_links = repo.select("part_material_grade_links", eq={"part_id": str(existing.get("id"))}, limit=500) if existing else []
    existing_alt_grades = [
        str(row.get("material_grade_id")) for row in existing_grade_links
        if str(row.get("status") or "ACTIVE") == "ACTIVE" and not bool(row.get("is_primary"))
    ]

    with stage_section("A", 'PART DETAILS', 'All fields shown in the approved Part Master layout.', key="part_master_render_entry_a"):
        with st.form(f"part_header_{header_scope}"):
            c = st.columns(6, gap="small")
            part_number = c[0].text_input("Part Number", value=str(existing.get("part_number") or ""), help="Original / customer Part Number. Internal QCMS identity.")
            fsi_part_number = c[1].text_input("FSI Part Number", value=str(existing.get("fsi_part_number") or ""), help="Secondary FSI identity used on supplier-facing documents so the original Part Number remains confidential.")
            part_name = c[2].text_input("Part Description", value=str(existing.get("part_name") or ""))
            finish_weight = c[3].number_input("Part Finish Weight (kg)", min_value=0.0, value=float(existing.get("finished_weight_kg") or 0), step=0.01)
            hsn_sac_code = c[4].text_input("HSN / SAC Code", value=str(existing.get("hsn_sac_code") or ""), help="Default supplier Purchase Order HSN/SAC. It can be overridden on the PO line.")
            status = c[5].selectbox("Status", ["ACTIVE", "INACTIVE"], index=0 if str(existing.get("status") or "ACTIVE") == "ACTIVE" else 1)
            c = st.columns(4, gap="small")
            customer_id = c[0].selectbox("Customer", list(customer_map), format_func=lambda x: customer_map[x], index=list(customer_map).index(str(existing.get("customer_id"))) if str(existing.get("customer_id")) in customer_map else 0) if customer_map else None
            grade_id = c[1].selectbox("Primary Material Grade", list(grade_map), format_func=lambda x: grade_map[x], index=list(grade_map).index(str(existing.get("material_grade_id"))) if str(existing.get("material_grade_id")) in grade_map else 0, help="Primary/default grade retained for compatibility. Alternate approved grades are selected below.") if grade_map else None
            c[2].text_input("Current Finish Drawing No.", value=str(existing.get("drawing_number") or ""), disabled=True, help="Controlled by the latest ACTIVE Finish Drawing revision below.")
            c[3].text_input("Current Finish Revision", value=str(existing.get("drawing_revision") or ""), disabled=True, help="Controlled by the latest ACTIVE Finish Drawing revision below.")
            alternate_grade_ids = st.multiselect(
                "Approved / Alternate Material Grades", list(grade_map),
                default=[gid for gid in existing_alt_grades if gid in grade_map],
                format_func=lambda x: grade_map[x],
                help="A Part may use multiple approved grades. Each supplier Raw Material row below selects the applicable grade.",
            ) if grade_map else []
            remarks = st.text_area("Remarks", value=str(existing.get("remarks") or ""), height=80)
            submitted = st.form_submit_button("Save Part Master", type="primary", disabled=not writable, width="stretch")
        if submitted:
            try:
                if not all([part_number.strip(), part_name.strip(), customer_id, grade_id]):
                    raise ValueError("Part Number, Description, Customer and Material Grade are mandatory.")
                payload = {"part_number": part_number.strip(), "fsi_part_number": fsi_part_number.strip() or None, "part_name": part_name.strip(), "customer_id": customer_id, "material_grade_id": grade_id, "finished_weight_kg": finish_weight, "hsn_sac_code": hsn_sac_code.strip() or None, "status": status, "remarks": remarks.strip() or None}
                if existing:
                    payload["drawing_number"] = existing.get("drawing_number")
                    payload["drawing_revision"] = existing.get("drawing_revision")
                for row in repo.select("parts", limit=5000):
                    if existing and str(row.get("id")) == str(existing.get("id")):
                        continue
                    if str(row.get("part_number") or "").strip().casefold() == part_number.strip().casefold():
                        raise ValueError("Duplicate Part Number is not allowed.")
                    if fsi_part_number.strip() and str(row.get("fsi_part_number") or "").strip().casefold() == fsi_part_number.strip().casefold():
                        raise ValueError("Duplicate FSI Part Number is not allowed.")
                saved = repo.update("parts", str(existing["id"]), payload) if existing else repo.insert("parts", payload)
                saved_part_id = str(saved["id"])
                # Multiple approved grades: parts.material_grade_id stays the primary grade
                # for legacy workflows while the link table holds the complete approved set.
                wanted_grades = {str(grade_id), *[str(v) for v in alternate_grade_ids if v]}
                links = repo.select("part_material_grade_links", eq={"part_id": saved_part_id}, limit=500)
                by_grade = {str(row.get("material_grade_id")): row for row in links}
                # Clear the previous primary first to avoid the unique-primary guard.
                for link in links:
                    if bool(link.get("is_primary")):
                        repo.update("part_material_grade_links", str(link["id"]), {"is_primary": False})
                for gid in wanted_grades:
                    data = {"part_id": saved_part_id, "material_grade_id": gid, "is_primary": gid == str(grade_id), "status": "ACTIVE"}
                    if gid in by_grade:
                        repo.update("part_material_grade_links", str(by_grade[gid]["id"]), data)
                    else:
                        repo.insert("part_material_grade_links", data)
                for gid, link in by_grade.items():
                    if gid not in wanted_grades:
                        repo.update("part_material_grade_links", str(link["id"]), {"is_primary": False, "status": "INACTIVE"})
                st.session_state["edit_part_id"] = saved_part_id; save_success_popup("Part Master saved successfully.", queue_for_rerun=True); st.rerun()
            except Exception as exc:
                st.error(str(exc))

        if not existing:
            st.info("Save the Part header first. Drawing attachments and requirement grids will then become available.")
            return
        part_id = str(existing["id"])

    with stage_section("B", 'CONTROLLED DRAWINGS', 'Drawing Number, Revision Number and Revision Date are revision-controlled. Uploading a new revision automatically makes the previous revision INACTIVE; old drawings remain downloadable in history.', key="part_master_render_entry_b"):
        drawing_rows = [
            row for row in repo.select(
                "document_attachments",
                eq={"entity_type": "PART_MASTER", "entity_id": part_id},
                order_by="created_at",
                desc=True,
                limit=500,
            )
            if str(row.get("document_type")) in dict(DRAWING_TYPES)
        ]
        active_drawings = {
            str(row.get("document_type")): row
            for row in drawing_rows
            if str(row.get("status") or "").upper() == "ACTIVE"
        }
        drawing_service = AttachmentService(repo)
        cols = st.columns(3, gap="small")
        for col, (dtype, label) in zip(cols, DRAWING_TYPES):
            current = active_drawings.get(dtype) or {}
            with col:
                with st.container(border=True, key=f"controlled_drawing_{dtype}_{part_id}"):
                    st.markdown(f"**{label}**")
                    if current:
                        st.caption(
                            f"ACTIVE · Drawing {current.get('drawing_number') or '-'} · "
                            f"Rev {current.get('revision') or '-'} · {current.get('revision_date') or '-'}"
                        )
                        try:
                            st.download_button(
                                "Download Current",
                                data=drawing_service.download(current),
                                file_name=str(current.get("file_name") or f"{dtype}.pdf"),
                                mime=str(current.get("mime_type") or "application/octet-stream"),
                                key=f"download_current_{dtype}_{current.get('id')}",
                                width="stretch",
                            )
                        except Exception as exc:
                            st.caption(f"Current file unavailable: {exc}")
                    else:
                        st.caption("No ACTIVE controlled drawing")

                    default_drawing_no = str(current.get("drawing_number") or (existing.get("drawing_number") if dtype == "FINISH_DRAWING" else "") or "")
                    drawing_no = st.text_input(
                        "Drawing Number",
                        value=default_drawing_no,
                        key=f"drawing_no_{dtype}_{part_id}",
                        disabled=not writable,
                    )
                    revision_no = st.text_input(
                        "Revision Number",
                        value="",
                        key=f"drawing_rev_{dtype}_{part_id}",
                        disabled=not writable,
                    )
                    revision_dt = st.date_input(
                        "Revision Date",
                        value=date.today(),
                        key=f"drawing_rev_date_{dtype}_{part_id}",
                        disabled=not writable,
                    )
                    file = st.file_uploader(
                        "Controlled Drawing File",
                        type=["pdf", "png", "jpg", "jpeg", "dwg", "dxf"],
                        key=f"draw_{dtype}_{part_id}",
                        disabled=not writable,
                    )
                    if st.button(
                        f"Release New {label} Revision",
                        key=f"up_{dtype}_{part_id}",
                        disabled=not writable or file is None or not drawing_no.strip() or not revision_no.strip(),
                        width="stretch",
                    ):
                        try:
                            _save_drawing_revision(repo, part_id, dtype, drawing_no, revision_no, revision_dt, file)
                            save_success_popup(
                                f"{label} {drawing_no} Rev {revision_no} released. Previous revision is now INACTIVE.",
                                queue_for_rerun=True,
                            )
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

    with stage_section("C", 'DRAWING REVISION HISTORY', 'All released drawings remain traceable. Only the latest revision for each drawing type is ACTIVE.', key="part_master_render_entry_c"):
        if not drawing_rows:
            st.info("No controlled drawing revisions have been released for this Part yet.")
        else:
            history_df = pd.DataFrame([
                {
                    "Drawing Type": dict(DRAWING_TYPES).get(str(row.get("document_type")), str(row.get("document_type") or "")),
                    "Drawing Number": row.get("drawing_number") or "",
                    "Revision Number": row.get("revision") or "",
                    "Revision Date": row.get("revision_date") or "",
                    "Status": str(row.get("status") or "").upper(),
                    "File": row.get("file_name") or "",
                    "Released At": row.get("created_at") or "",
                    "Superseded At": row.get("superseded_at") or "",
                }
                for row in drawing_rows
            ])
            portal_table(history_df, hide_index=True, width="stretch")
            history_map = {str(row["id"]): _drawing_label(row) for row in drawing_rows}
            selected_drawing_id = st.selectbox(
                "Select Drawing Revision to Download",
                list(history_map),
                format_func=lambda value: history_map[value],
                key=f"drawing_history_select_{part_id}",
            )
            selected_drawing = next(row for row in drawing_rows if str(row.get("id")) == selected_drawing_id)
            try:
                st.download_button(
                    "Download Selected Drawing Revision",
                    data=drawing_service.download(selected_drawing),
                    file_name=str(selected_drawing.get("file_name") or "controlled_drawing"),
                    mime=str(selected_drawing.get("mime_type") or "application/octet-stream"),
                    key=f"drawing_history_download_{selected_drawing_id}",
                    width="stretch",
                )
            except Exception as exc:
                st.error(f"Drawing download unavailable: {exc}")

        # Customer Standards / Specifications linked to this Part Master.
    with stage_section("D", 'CUSTOMER STANDARDS & SPECIFICATIONS', 'Link multiple customer/process standards to this Part. Controlled attachments can be downloaded directly from the Part Master.', key="part_master_render_entry_d"):
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
        # Backward contract: Save Linked Standards now means add-only; unlinking is a separate ADMIN/password action.
        existing_links = repo.select("part_standard_links", eq={"part_id": part_id}, order_by="sequence_no", limit=1000)
        linked_ids = [str(row.get("standard_id")) for row in existing_links if str(row.get("standard_id")) in standard_map]
        available_standard_ids = [standard_id for standard_id in standard_map if standard_id not in set(linked_ids)]
        selected_standard_ids = st.multiselect(
            "Add Customer Standards / Specifications",
            available_standard_ids,
            format_func=lambda value: standard_map[value],
            disabled=not writable,
            help=(
                "Select one or more additional controlled standards. Existing links remain protected. "
                "Unlinking an existing Standard from a Part requires QCMS Administrator approval and password confirmation."
            ),
        ) if standard_map else []
        if not standard_map:
            st.info("No active Customer Standards / Specifications are available for this Part customer. Create them in the Standards Bank first.")
            st.page_link(st.session_state["_qsms_pages"]["standards-entry"], label="Open Customer Standards Bank", icon=":material/library_books:", width="stretch")
        elif st.button("Add Selected Standards", type="primary", disabled=not writable or not selected_standard_ids, width="stretch", key=f"save_part_standards_{part_id}"):
            try:
                by_standard = {str(row.get("standard_id")): row for row in existing_links}
                next_sequence = max([int(row.get("sequence_no") or 0) for row in existing_links] + [0]) + 10
                for standard_id in selected_standard_ids:
                    if standard_id in by_standard:
                        continue
                    repo.insert(
                        "part_standard_links",
                        {"part_id": part_id, "standard_id": standard_id, "sequence_no": next_sequence, "status": "ACTIVE"},
                    )
                    next_sequence += 10
                save_success_popup("Selected Customer Standards / Specifications linked successfully.", queue_for_rerun=True)
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
            portal_table(pd.DataFrame(linked_display), hide_index=True, width="stretch", height=min(280, 72 + len(linked_display) * 36))
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
                        process_text = process_label(standard_processes.get(str(standard.get("process_id"))) or {}) or "No Process"
                        author_text = str(standard.get("author_name") or "Author not specified").strip()
                        standard_name_text = str(standard.get("standard_name") or "Standard / Specification").strip()
                        st.download_button(
                            (
                                f"Download {standard.get('standard_code') or 'Standard'} · {standard_name_text} · "
                                f"{author_text} · {process_text} · Rev {standard.get('revision_number') or '-'}"
                            ),
                            data=content,
                            file_name=str(attachment.get("file_name") or f"{standard.get('standard_code')}.pdf"),
                            mime=str(attachment.get("mime_type") or "application/octet-stream"),
                            key=f"part_standard_download_{part_id}_{standard.get('id')}",
                            width="stretch",
                        )

            admin_unlink_allowed = is_admin(current_profile())
            if not admin_unlink_allowed:
                st.caption("Standard unlink is restricted to the QCMS Administrator. Contact the Administrator if a linked Standard must be removed from this Part.")
            if password_delete_panel(
                repo=repo,
                table="part_standard_links",
                rows=active_link_rows,
                labeler=lambda link: customer_standard_label(
                    standard_by_id.get(str(link.get("standard_id"))) or {},
                    customer_name=party_label(standard_customers.get(str((standard_by_id.get(str(link.get("standard_id"))) or {}).get("customer_id"))) or {}),
                    process_name=process_label(standard_processes.get(str((standard_by_id.get(str(link.get("standard_id"))) or {}).get("process_id"))) or {}),
                ) or str(link.get("standard_id") or "Standard"),
                key=f"admin_unlink_part_standard_{part_id}",
                can_delete=admin_unlink_allowed,
                title="ADMIN APPROVAL — Unlink Standard from Part",
                help_text=(
                    "Only an active QCMS Administrator can unlink a controlled Standard / Specification from a Part. "
                    "Administrator password confirmation is mandatory and the action is permanent."
                ),
            ):
                st.rerun()

        suppliers = repo.select("parties", contains={"party_types": ["SUPPLIER"]}, eq={"status": "ACTIVE"}, order_by="party_name", limit=1000)
        supplier_map = {str(row["id"]): party_label(row) for row in suppliers}
        supplier_by_name = {name: sid for sid, name in supplier_map.items()}

    with stage_section("E", 'RAW MATERIAL DETAILS & APPROVED SOURCES', 'Approved Supplier / Steel Mill combinations and raw-material forging parameters are controlled directly in Part Master.', key="part_master_render_entry_e"):
        section_bar('APPROVED SOURCES', 'Select multiple approved Suppliers and Steel Mills for this Part. This replaces the former Reference Master → Approved Sources module.')
        steel_mills = repo.select('parties', contains={'party_types':['STEEL_MILL']}, eq={'status':'ACTIVE'}, order_by='party_name', limit=1000)
        steel_map = {str(row['id']): party_label(row) for row in steel_mills}
        existing_source_links = repo.select('part_supplier_links', eq={'part_id':part_id}, limit=2000)
        approved_supplier_ids = sorted({str(row.get('supplier_id')) for row in existing_source_links if row.get('supplier_id') and bool(row.get('approved', True))})
        approved_mill_ids = sorted({str(row.get('steel_mill_id')) for row in existing_source_links if row.get('steel_mill_id') and bool(row.get('approved', True))})
        sc1,sc2 = st.columns(2,gap='small')
        selected_suppliers = sc1.multiselect('Approved Suppliers', list(supplier_map), default=[v for v in approved_supplier_ids if v in supplier_map], format_func=lambda v:supplier_map[v], disabled=not writable)
        selected_mills = sc2.multiselect('Approved Steel Mills', list(steel_map), default=[v for v in approved_mill_ids if v in steel_map], format_func=lambda v:steel_map[v], disabled=not writable)
        sc1,sc2,sc3,sc4 = st.columns(4,gap='small')
        supplier_part_number = sc1.text_input('Supplier Part Number', key=f'approved_source_spn_{part_id}')
        approval_reference = sc2.text_input('Approval Reference', key=f'approved_source_ref_{part_id}')
        valid_from = sc3.date_input('Valid From', value=date.today(), format='DD-MM-YYYY', key=f'approved_source_from_{part_id}')
        valid_to = sc4.date_input('Valid To', value=None, format='DD-MM-YYYY', key=f'approved_source_to_{part_id}')
        if st.button('Save Approved Sources', type='primary', width='stretch', disabled=not writable or not selected_suppliers, key=f'save_approved_sources_{part_id}'):
            try:
                wanted={(sid, mid or '') for sid in selected_suppliers for mid in (selected_mills or [''])}
                existing_by_pair={(str(row.get('supplier_id') or ''),str(row.get('steel_mill_id') or '')):row for row in existing_source_links}
                for pair,row in existing_by_pair.items():
                    if pair not in wanted and bool(row.get('approved', True)):
                        repo.update('part_supplier_links',str(row['id']),{'approved':False})
                source_def=MASTER_BY_KEY.get('approved_sources')
                for sid,mid in wanted:
                    payload={'part_id':part_id,'supplier_id':sid,'steel_mill_id':mid or None,'supplier_part_number':supplier_part_number.strip() or None,'approval_reference':approval_reference.strip() or None,'approved':True,'valid_from':valid_from.isoformat() if valid_from else None,'valid_to':valid_to.isoformat() if valid_to else None}
                    existing_link=existing_by_pair.get((sid,mid))
                    if source_def and not existing_link:
                        payload['source_code']=MasterService(repo).next_master_code(source_def)
                    if existing_link: repo.update('part_supplier_links',str(existing_link['id']),payload)
                    else: repo.insert('part_supplier_links',payload)
                save_success_popup('Approved Part sources saved successfully.', queue_for_rerun=True); st.rerun()
            except Exception as exc: st.error(str(exc))
        if existing_source_links:
            portal_table(pd.DataFrame([{
                'Supplier':supplier_map.get(str(r.get('supplier_id')),''), 'Steel Mill':steel_map.get(str(r.get('steel_mill_id')),''),
                'Supplier Part No.':r.get('supplier_part_number'),'Approval Reference':r.get('approval_reference'),
                'Valid From':r.get('valid_from'),'Valid To':r.get('valid_to'),'Approved':bool(r.get('approved'))
            } for r in existing_source_links]),hide_index=True,width='stretch',height=min(300,80+len(existing_source_links)*34))

        section_bar('RAW MATERIAL DETAILS / FORGING PARAMETERS')
        raw = repo.select("part_raw_material_details", eq={"part_id": part_id}, order_by="sequence_no", limit=200)
        if password_delete_panel(repo=repo, table="part_raw_material_details", rows=raw, labeler=lambda r: f"{supplier_map.get(str(r.get('supplier_id')), 'Supplier')} · {r.get('section_size') or '-'} · {r.get('forging_route') or '-'}", key=f"delete_raw_{part_id}", can_delete=perms["can_archive"], title="Delete Raw Material row"):
            st.rerun()
        # Compatibility marker for the pre-v4.14.3 raw-material natural key regression:
        # ("supplier_id", "material_section_name", "section_size", "forging_route")
        grade_by_name = {label: gid for gid, label in grade_map.items()}
        raw_df = pd.DataFrame([{
            "Raw Material Type": r.get("material_section_name") or "Round Black Bar",
            "Material Grade": grade_map.get(str(r.get("material_grade_id")), grade_map.get(str(existing.get("material_grade_id")), "")),
            "Supplier Name / Location": supplier_map.get(str(r.get("supplier_id")), ""),
            "Supplier RM Item Code": r.get("supplier_rm_item_code") or "",
            "Supplier Forging Part No.": r.get("supplier_forging_part_number") or "",
            "HSN / SAC Code": r.get("hsn_sac_code") or existing.get("hsn_sac_code") or "",
            "Lead Time (Days)": int(r.get("lead_time_days") or 0),
            "Forging Weight": r.get("forging_weight_kg"),
            "Gross Weight": r.get("gross_weight_kg"),
            "Input Weight kg/part": r.get("input_weight_kg") or r.get("gross_weight_kg") or r.get("forging_weight_kg"),
            "Section Size": r.get("section_size"), "Forging Route": r.get("forging_route"),
            "Status": r.get("status") or "ACTIVE"
        } for r in raw], columns=["Raw Material Type", "Material Grade", "Supplier Name / Location", "Supplier RM Item Code", "Supplier Forging Part No.", "HSN / SAC Code", "Lead Time (Days)", "Forging Weight", "Gross Weight", "Input Weight kg/part", "Section Size", "Forging Route", "Status"])
        rm_type_options = _catalog_options(catalog, "part.rm_type", [*RAW_MATERIAL_TYPE_DEFAULTS, *[r.get("material_section_name") for r in raw]])
        section_options = _catalog_options(catalog, "part.rm_section", [r.get("section_size") for r in raw])
        route_options = _catalog_options(catalog, "part.forging_route", [r.get("forging_route") for r in raw])
        with st.expander("Manage reusable Raw Material Type, Section Size and Forging Route lists", expanded=False):
            _catalog_add_control(catalog, "part.rm_type", "Raw Material Type", rm_type_options, f"rm_type_{part_id}")
            _catalog_add_control(catalog, "part.rm_section", "Section Size", section_options, f"section_{part_id}", duplicate_word_check=True)
            _catalog_add_control(catalog, "part.forging_route", "Forging Route", route_options, f"route_{part_id}", duplicate_word_check=True)
        with st.form(f"raw_material_grid_form_{part_id}"):
            raw_edit = st.data_editor(
                raw_df, num_rows="dynamic", hide_index=True, width="stretch", height=280, key=f"raw_{part_id}", disabled=not writable,
                column_config={
                    "Raw Material Type": st.column_config.SelectboxColumn(options=rm_type_options or list(RAW_MATERIAL_TYPE_DEFAULTS), required=True, help="Controlled material form/type for this supplier row, e.g. Round Black Bar or Bright Bar."),
                    "Material Grade": st.column_config.SelectboxColumn(options=list(grade_by_name), required=True),
                    "Supplier Name / Location": st.column_config.SelectboxColumn(options=list(supplier_by_name), required=True),
                    "Supplier RM Item Code": st.column_config.TextColumn(help="Optional common supplier-facing RM item code. Use the SAME code on different finished Parts when they buy the exact same RM. QCMS can consolidate those sources into one RM PO line while retaining each finished-Part allocation."),
                    "Supplier Forging Part No.": st.column_config.TextColumn(help="Optional common supplier forging part number. Use the SAME value for different finished Parts when the purchased forging is genuinely identical before downstream machining."),
                    "HSN / SAC Code": st.column_config.TextColumn(help="Supplier/raw-material specific HSN or SAC. Purchase Orders inherit this value automatically; Part Master header HSN is used only as fallback."),
                    "Lead Time (Days)": st.column_config.NumberColumn(min_value=0, step=1, required=True, help="Used to calculate the default PO delivery date; it remains editable in the PO."),
                    "Forging Weight": st.column_config.NumberColumn(min_value=0.0, format="%.3f"),
                    "Gross Weight": st.column_config.NumberColumn(min_value=0.0, format="%.3f"),
                    "Input Weight kg/part": st.column_config.NumberColumn(min_value=0.001, format="%.3f", required=True, help="Steel input required for one production part."),
                    "Section Size": st.column_config.SelectboxColumn(options=section_options or [""], required=True),
                    "Forging Route": st.column_config.SelectboxColumn(options=route_options or [""], required=True),
                    "Status": st.column_config.SelectboxColumn(options=["ACTIVE", "INACTIVE"]),
                },
            )
            save_raw = st.form_submit_button("Save Raw Material Details", type="primary", disabled=not writable, width="stretch")
        if save_raw:
            try:
                def mapper(row, index):
                    name = str(row.get("Supplier Name / Location") or "").strip(); sid = supplier_by_name.get(name)
                    grade_name = str(row.get("Material Grade") or "").strip(); row_grade_id = grade_by_name.get(grade_name)
                    if not sid: return {}
                    if not row_grade_id: raise ValueError(f"Material Grade is required for {name}.")
                    catalog.remember_many("part.rm_type", [row.get("Raw Material Type")]); catalog.remember_many("part.rm_section", [row.get("Section Size")]); catalog.remember_many("part.forging_route", [row.get("Forging Route")])
                    input_weight = None if pd.isna(row.get("Input Weight kg/part")) else row.get("Input Weight kg/part")
                    if input_weight is None or float(input_weight) <= 0:
                        raise ValueError(f"Input Weight kg/part is required for {name}.")
                    material_section = str(row.get("Raw Material Type") or "").strip() or "Round Black Bar"
                    return {"supplier_id": sid, "material_grade_id": row_grade_id, "supplier_rm_item_code": str(row.get("Supplier RM Item Code") or "").strip() or None, "supplier_forging_part_number": str(row.get("Supplier Forging Part No.") or "").strip() or None, "hsn_sac_code": str(row.get("HSN / SAC Code") or "").strip() or None, "lead_time_days": int(row.get("Lead Time (Days)") or 0), "material_section_name": material_section, "forging_weight_kg": None if pd.isna(row.get("Forging Weight")) else row.get("Forging Weight"), "gross_weight_kg": None if pd.isna(row.get("Gross Weight")) else row.get("Gross Weight"), "input_weight_kg": input_weight, "section_size": str(row.get("Section Size") or "").strip() or None, "forging_route": str(row.get("Forging Route") or "").strip() or None, "sequence_no": 10 * (index + 1), "status": str(row.get("Status") or "ACTIVE")}
                _save_rows(repo, "part_raw_material_details", part_id, raw_edit, ("supplier_id", "material_grade_id", "material_section_name", "section_size", "forging_route"), mapper); save_success_popup("Raw Material Details saved successfully.", queue_for_rerun=True); st.rerun()
            except Exception as exc:
                st.error(str(exc))


        # v4.13.8: supplier-specific technical heading/value data and price history
        # are controlled from Part Master and pulled automatically into the PO.
        current_raw = repo.select("part_raw_material_details", eq={"part_id": part_id}, order_by="sequence_no", limit=500)
        raw_labels = {
            str(r["id"]): f"{supplier_map.get(str(r.get('supplier_id')), 'Supplier')} · HSN {r.get('hsn_sac_code') or existing.get('hsn_sac_code') or '-'} · {grade_map.get(str(r.get('material_grade_id')), 'Grade -')} · {r.get('material_section_name') or 'Raw Material Type -'} · {r.get('section_size') or '-'} · LT {int(r.get('lead_time_days') or 0)}d"
            for r in current_raw
        }
        section_bar("SUPPLIER TECHNICAL DATA & PRICE HISTORY", "Select the supplier-specific Raw Material record. Heading/value technical rows are copied automatically to the Purchase Order; price history is matched by the selected Supplier + Raw Material Detail + FSI Part Number.")
        selected_raw_id = st.selectbox("Raw Material / Supplier Record", list(raw_labels), format_func=lambda v: raw_labels[v], key=f"rm_supplier_detail_select_{part_id}") if raw_labels else None
        if not selected_raw_id:
            st.info("Save at least one Raw Material Detail row before adding supplier technical data or price history.")
        else:
            selected_raw = next(r for r in current_raw if str(r.get("id")) == str(selected_raw_id))
            selected_supplier_id = str(selected_raw.get("supplier_id") or "")

            tech_section_perm = section_permissions(st.session_state.get("profile") or {}, "PART_MASTER", "SUPPLIER_TECHNICAL", repo)
            tech_rows = repo.select("part_raw_material_technical_data", eq={"raw_material_detail_id": selected_raw_id}, order_by="sequence_no", limit=500) if tech_section_perm["can_view"] else []
            if tech_section_perm["can_view"] and password_delete_panel(repo=repo, table="part_raw_material_technical_data", rows=tech_rows, labeler=lambda r: f"{r.get('heading') or '-'} · {r.get('value_text') or '-'}", key=f"delete_rm_technical_{selected_raw_id}", can_delete=perms["can_archive"] and tech_section_perm["can_edit"], title="Delete Technical Data row"):
                st.rerun()
            tech_df = pd.DataFrame([{
                "Heading": r.get("heading") or "",
                "Value": r.get("value_text") or "",
                "Include on PO": bool(r.get("include_on_po", True)),
                "Sequence": int(r.get("sequence_no") or 10),
                "Status": r.get("status") or "ACTIVE",
            } for r in tech_rows], columns=["Heading", "Value", "Include on PO", "Sequence", "Status"])
            with st.form(f"rm_technical_form_{selected_raw_id}"):
                tech_edit = st.data_editor(
                    tech_df, num_rows="dynamic", hide_index=True, width="stretch", height=250, key=f"rm_technical_data_{selected_raw_id}", disabled=(not writable or not tech_section_perm["can_edit"]),
                    column_config={
                        "Heading": st.column_config.TextColumn(required=True, help="Example: RM May'26, Tool Cost, Profit, Rej + ICC, Packaging, Heat Treatment Condition."),
                        "Value": st.column_config.TextColumn(required=True),
                        "Include on PO": st.column_config.CheckboxColumn(default=True),
                        "Sequence": st.column_config.NumberColumn(min_value=1, step=1),
                        "Status": st.column_config.SelectboxColumn(options=["ACTIVE", "INACTIVE"]),
                    },
                )
                save_tech = st.form_submit_button("Save Supplier Technical Data", type="primary", width="stretch", disabled=(not writable or not tech_section_perm["can_edit"]))
            if save_tech:
                try:
                    def tech_mapper(row, index):
                        heading = str(row.get("Heading") or "").strip(); value = str(row.get("Value") or "").strip()
                        if not heading and not value: return {}
                        if not heading or not value: raise ValueError("Both Technical Data Heading and Value are required.")
                        return {"raw_material_detail_id": selected_raw_id, "supplier_id": selected_supplier_id, "heading": heading, "value_text": value, "include_on_po": bool(row.get("Include on PO", True)), "sequence_no": int(row.get("Sequence") or (index + 1) * 10), "status": str(row.get("Status") or "ACTIVE")}
                    _save_rows(repo, "part_raw_material_technical_data", part_id, tech_edit, ("raw_material_detail_id", "heading"), tech_mapper)
                    save_success_popup("Supplier technical data saved. Active rows will populate Purchase Orders automatically.", queue_for_rerun=True); st.rerun()
                except Exception as exc: st.error(str(exc))

            if not tech_section_perm["can_view"]:
                st.info("Supplier Technical Data is hidden by your section permission.")
            price_section_perm = section_permissions(st.session_state.get("profile") or {}, "PART_MASTER", "PRICE_HISTORY", repo)
            if price_section_perm["can_view"]:
                price_rows = repo.select("part_supplier_price_history", eq={"part_id": part_id, "supplier_id": selected_supplier_id, "raw_material_detail_id": selected_raw_id}, order_by="start_date", limit=500)
                if password_delete_panel(repo=repo, table="part_supplier_price_history", rows=price_rows, labeler=lambda r: f"{r.get('start_date')} to {r.get('end_date') or 'Current'} · {r.get('price')} {r.get('currency') or 'INR'}/{r.get('uom') or 'KGS'}", key=f"delete_price_history_{selected_raw_id}", can_delete=perms["can_archive"], title="Delete Price History row"):
                    st.rerun()
                price_df = pd.DataFrame([{
                    "Start Date": pd.to_datetime(r.get("start_date"), errors="coerce"),
                    "End Date": pd.to_datetime(r.get("end_date"), errors="coerce") if r.get("end_date") else pd.NaT,
                    "Basic Rate": r.get("price"),
                    "Freight": r.get("freight"),
                    "Tool Cost": r.get("tool_cost"),
                    "P&F": r.get("packing_forwarding"),
                    "Profit": r.get("profit"),
                    "ICC/Rej.": r.get("icc_rejection"),
                    "Currency": r.get("currency") or "INR", "UOM": r.get("uom") or "KGS",
                    "Remark": r.get("remarks") or "", "Status": r.get("status") or "ACTIVE",
                } for r in price_rows], columns=["Start Date", "End Date", "Basic Rate", "Freight", "Tool Cost", "P&F", "Profit", "ICC/Rej.", "Currency", "UOM", "Remark", "Status"])
                with st.form(f"price_history_form_{selected_raw_id}"):
                    price_edit = st.data_editor(
                        price_df, num_rows="dynamic", hide_index=True, width="stretch", height=240, key=f"price_history_{selected_raw_id}", disabled=not writable,
                        column_config={
                            "Start Date": st.column_config.DateColumn(required=True, format="DD/MM/YYYY"),
                            "End Date": st.column_config.DateColumn(format="DD/MM/YYYY", help="Leave blank for the current/open-ended price."),
                            "Basic Rate": st.column_config.NumberColumn(required=True, min_value=0.0, format="%.2f", help="Controlled supplier basic rate used as the default PO unit price."),
                            "Freight": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
                            "Tool Cost": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
                            "P&F": st.column_config.NumberColumn(min_value=0.0, format="%.2f", help="Packing & Forwarding component."),
                            "Profit": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
                            "ICC/Rej.": st.column_config.NumberColumn(min_value=0.0, format="%.2f", help="ICC / rejection component."),
                            "Currency": st.column_config.SelectboxColumn(options=["INR", "USD", "EUR", "GBP"], required=True),
                            "UOM": st.column_config.SelectboxColumn(options=["KGS", "NOS", "PCS"], required=True),
                            "Remark": st.column_config.TextColumn(help="Reason / commercial note for this price revision; printed in the PO Price Revision History table."),
                            "Status": st.column_config.SelectboxColumn(options=["ACTIVE", "INACTIVE"]),
                        },
                    )
                    save_price = st.form_submit_button("Save Supplier / FSI Part Price History", type="primary", width="stretch", disabled=not writable)
                if save_price:
                    try:
                        # Old period rows are saved first so a newly-added current period can pass the non-overlap guard.
                        frame = price_edit.copy()
                        if not frame.empty: frame = frame.sort_values("Start Date", na_position="last")
                        def date_text(value):
                            if value is None or pd.isna(value): return None
                            if hasattr(value, "date"): value = value.date()
                            return value.isoformat() if hasattr(value, "isoformat") else str(value)[:10]
                        def price_mapper(row, index):
                            start = date_text(row.get("Start Date")); end = date_text(row.get("End Date"))
                            if not start and (row.get("Basic Rate") is None or pd.isna(row.get("Basic Rate"))): return {}
                            if not start: raise ValueError("Start Date is required for every price-history row.")
                            if end and end < start: raise ValueError("Price History End Date cannot be earlier than Start Date.")
                            def money_value(key):
                                value = row.get(key)
                                return None if value is None or pd.isna(value) else float(value)
                            price = money_value("Basic Rate") or 0.0
                            return {
                                "supplier_id": selected_supplier_id, "raw_material_detail_id": selected_raw_id,
                                "start_date": start, "end_date": end, "price": price,
                                "freight": money_value("Freight"), "tool_cost": money_value("Tool Cost"),
                                "packing_forwarding": money_value("P&F"), "profit": money_value("Profit"),
                                "icc_rejection": money_value("ICC/Rej."),
                                "currency": str(row.get("Currency") or "INR"), "uom": str(row.get("UOM") or "KGS"),
                                "remarks": str(row.get("Remark") or "").strip() or None, "status": str(row.get("Status") or "ACTIVE")
                            }
                        _save_rows(repo, "part_supplier_price_history", part_id, frame, ("part_id", "supplier_id", "raw_material_detail_id", "uom", "start_date"), price_mapper)
                        save_success_popup("Supplier / FSI Part price history saved successfully.", queue_for_rerun=True); st.rerun()
                    except Exception as exc: st.error(str(exc))
            else:
                st.info("Supplier Price History is hidden by your section permission.")
    with stage_section("F", 'JOMINY REQUIREMENT', 'Controlled 1/16 inch to millimetre conversion and HRC requirement band.', key="part_master_render_entry_f"):
        distances = repo.select("jominy_distances", eq={"status": "ACTIVE"}, order_by="distance_16th", limit=100)
        dmap = {str(d.get("distance_label")): d for d in distances}
        jom = repo.select("part_jominy_requirements", eq={"part_id": part_id}, order_by="sequence_no", limit=100)
        if password_delete_panel(repo=repo, table="part_jominy_requirements", rows=jom, labeler=lambda r: f"{r.get('distance_label')} · {r.get('minimum_hrc')}–{r.get('maximum_hrc')} HRC", key=f"delete_jom_{part_id}", can_delete=perms["can_archive"], title="Delete Jominy Requirement row"):
            st.rerun()
        jdf = pd.DataFrame([{"Distance (inch)": r.get("distance_label"), "MM (Auto)": round(float((dmap.get(str(r.get("distance_label"))) or {}).get("distance_16th") or 0) * 25.4 / 16, 2), "Minimum HRC": r.get("minimum_hrc"), "Maximum HRC": r.get("maximum_hrc"), "Status": r.get("status") or "ACTIVE"} for r in jom], columns=["Distance (inch)", "MM (Auto)", "Minimum HRC", "Maximum HRC", "Status"])
        disabled = True if not writable else ["MM (Auto)"]
        with st.form(f"jominy_grid_form_{part_id}"):
            jedit = st.data_editor(jdf, num_rows="dynamic", hide_index=True, width="stretch", height=280, key=f"jom_{part_id}", disabled=disabled, column_config={"Distance (inch)": st.column_config.SelectboxColumn(options=list(dmap), required=True), "MM (Auto)": st.column_config.NumberColumn(format="%.2f"), "Minimum HRC": st.column_config.NumberColumn(format="%.2f"), "Maximum HRC": st.column_config.NumberColumn(format="%.2f"), "Status": st.column_config.SelectboxColumn(options=["ACTIVE", "INACTIVE"])})
            save_jominy = st.form_submit_button("Save Jominy Requirements", type="primary", disabled=not writable, width="stretch")
        if save_jominy:
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
    with stage_section("G", "OSP INSPECTION FOR METLAB", key="part_master_render_entry_g"):
        _render_osp_metlab_requirements(repo, catalog, part_id, writable, perms["can_archive"], show_heading=False)

    with stage_section("H", "METALLURGICAL REQUIREMENTS", key="part_master_render_entry_h"):
        _render_metallurgical_requirements(repo, catalog, part_id, writable, perms["can_archive"], show_heading=False)



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
    search = st.text_input("Search Part Number, FSI Part Number or Description")
    rows = [p for p in parts if not search or search.casefold() in (str(p.get("part_number")) + " " + str(p.get("fsi_part_number")) + " " + str(p.get("part_name"))).casefold()]

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
                    "Part Number": selected_row.get("part_number"), "FSI Part Number": selected_row.get("fsi_part_number"), "HSN / SAC": selected_row.get("hsn_sac_code"), "Part Description": selected_row.get("part_name"),
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
    df = pd.DataFrame([{"Part Number": p.get("part_number"), "FSI Part Number": p.get("fsi_part_number"), "HSN / SAC": p.get("hsn_sac_code"), "Part Description": p.get("part_name"), "Finish Weight kg": p.get("finished_weight_kg"), "Customer": (customers.get(str(p.get("customer_id"))) or {}).get("party_name"), "Material Grade": (grades.get(str(p.get("material_grade_id"))) or {}).get("grade_code"), "Drawing": p.get("drawing_number"), "Revision": p.get("drawing_revision"), "Status": p.get("status")} for p in rows])
    portal_table(df, hide_index=True, width="stretch", height=620)
