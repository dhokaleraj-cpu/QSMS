from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.attachments import AttachmentSlot, render_attachment_manager
from core.catalog import LearnedValueCatalog
from core.database import get_session_client
from core.delete_service import password_delete_panel
from core.osp_service import OSPService
from core.repository import Repository
from core.ui import page_header, section_bar, subpage_navigation, template_download_row

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
    labels = _labels(parts, "part_number", "part_name")
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
            st.success(f"{text} added to the reusable list.")
            st.rerun()

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
    customer_map = _labels(customers, "party_code", "party_name")
    grade_map = {str(g["id"]): f"{g.get('grade_code')} · {g.get('material_number') or g.get('standard') or '-'}" for g in grades}

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
            saved = repo.update("parts", str(existing["id"]), payload) if existing else repo.insert("parts", payload)
            catalog.remember_many("part.drawing_revision", [drawing_revision])
            st.session_state["edit_part_id"] = str(saved["id"]); st.success("Part Master saved."); st.rerun()
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
                    _upload(repo, part_id, dtype, file); st.success(f"{label} uploaded."); st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    suppliers = repo.select("parties", contains={"party_types": ["SUPPLIER"]}, eq={"status": "ACTIVE"}, order_by="party_name", limit=1000)
    supplier_map = {str(s["id"]): str(s.get("party_name")) for s in suppliers}
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
            _save_rows(repo, "part_raw_material_details", part_id, raw_edit, ("supplier_id",), mapper); st.success("Raw Material Details saved."); st.rerun()
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
            _save_rows(repo, "part_jominy_requirements", part_id, jedit, ("jominy_distance_id",), mapper); st.success("Jominy Requirements saved."); st.rerun()
        except Exception as exc:
            st.error(str(exc))
    section_bar("HEAT TREATMENT DETAILS", "Heat Treatment Process, Case Depth, Core Hardness and additional controlled requirements.")
    ht = repo.select("part_heat_treatment_details", eq={"part_id": part_id}, order_by="sequence_no", limit=200)
    if password_delete_panel(repo=repo, table="part_heat_treatment_details", rows=ht, labeler=lambda r: f"{r.get('parameter_name')} · {r.get('requirement_value')}", key=f"delete_ht_{part_id}", can_delete=perms["can_archive"], title="Delete Heat Treatment row"):
        st.rerun()
    hdf = pd.DataFrame([{"Parameter": r.get("parameter_name"), "Requirement": r.get("requirement_value"), "Status": r.get("status") or "ACTIVE"} for r in ht], columns=["Parameter", "Requirement", "Status"])
    parameter_options = _catalog_options(catalog, "part.heat_parameter", [r.get("parameter_name") for r in ht])
    requirement_options = _catalog_options(catalog, "part.heat_requirement", [r.get("requirement_value") for r in ht])
    with st.expander("Manage reusable Heat Treatment Parameter and Requirement lists", expanded=False):
        _catalog_add_control(catalog, "part.heat_parameter", "Heat Treatment Parameter", parameter_options, f"heat_parameter_{part_id}")
        _catalog_add_control(catalog, "part.heat_requirement", "Heat Treatment Requirement", requirement_options, f"heat_requirement_{part_id}")
    hedit = st.data_editor(
        hdf, num_rows="dynamic", hide_index=True, width="stretch", height=280, key=f"heat_{part_id}", disabled=not writable,
        column_config={
            "Parameter": st.column_config.SelectboxColumn(options=parameter_options or [""], required=True),
            "Requirement": st.column_config.SelectboxColumn(options=requirement_options or [""], required=True),
            "Status": st.column_config.SelectboxColumn(options=["ACTIVE", "INACTIVE"]),
        },
    )
    if st.button("Save Heat Treatment Details", type="primary", disabled=not writable, width="stretch"):
        try:
            def mapper(row, index):
                parameter = str(row.get("Parameter") or "").strip(); requirement = str(row.get("Requirement") or "").strip()
                if not parameter: return {}
                if not requirement: raise ValueError(f"Requirement is required for {parameter}.")
                catalog.remember_many("part.heat_parameter", [parameter]); catalog.remember_many("part.heat_requirement", [requirement])
                return {"parameter_name": parameter, "requirement_value": requirement, "sequence_no": 10 * (index + 1), "status": str(row.get("Status") or "ACTIVE")}
            _save_rows(repo, "part_heat_treatment_details", part_id, hedit, ("parameter_name",), mapper); st.success("Heat Treatment Details saved."); st.rerun()
        except Exception as exc:
            st.error(str(exc))

    section_bar(
        "OSP PROCESS & INWARD SPECIFICATIONS",
        "OSP Process is the key field. Every Process group keeps its own specification reference, drawing and inspection parameters.",
    )
    processes = repo.select("processes", eq={"status": "ACTIVE"}, order_by="process_name", limit=1000)
    process_by_name = {str(row.get("process_name")): row for row in processes}
    process_names = list(process_by_name)
    process_specs = repo.select("part_process_specifications", eq={"part_id": part_id}, order_by="sequence_no", limit=500)
    if password_delete_panel(
        repo=repo, table="part_process_specifications", rows=process_specs,
        labeler=lambda row: f"{next((p.get('process_name') for p in processes if str(p.get('id')) == str(row.get('process_id'))), 'Process')} · {str(row.get('inward_type') or '').replace('_',' ').title()}",
        key=f"delete_process_spec_{part_id}", can_delete=perms["can_archive"],
        title="Delete OSP Process Specification Group",
        help_text="Current password and Part Master delete permission are required. A group linked to an OSP transaction cannot be deleted.",
    ):
        st.rerun()

    spec_frame = pd.DataFrame([{
        "OSP Process": next((p.get("process_name") for p in processes if str(p.get("id")) == str(row.get("process_id"))), ""),
        "Process Type": next((p.get("process_type") for p in processes if str(p.get("id")) == str(row.get("process_id"))), ""),
        "Inward Type": row.get("inward_type") or "OSP_PROCESS",
        "Specification / Standard": row.get("process_specification") or "",
        "Specification Reference": row.get("specification_reference") or "",
        "Drawing Number": row.get("drawing_number") or "",
        "Drawing Revision": row.get("drawing_revision") or "",
        "Dimensional Required": bool(row.get("dimensional_required", True)),
        "MetLAB Required": bool(row.get("metlab_required", True)),
        "Sample Qty": int(row.get("sample_quantity") or 1),
        "Status": row.get("status") or "ACTIVE",
    } for row in process_specs], columns=[
        "OSP Process", "Process Type", "Inward Type", "Specification / Standard",
        "Specification Reference", "Drawing Number", "Drawing Revision",
        "Dimensional Required", "MetLAB Required", "Sample Qty", "Status",
    ])
    process_edit = st.data_editor(
        spec_frame, num_rows="dynamic", hide_index=True, width="stretch",
        height=min(440, max(220, 90 + max(len(spec_frame), 1) * 34)), key=f"part_process_specs_{part_id}",
        disabled=True if not writable else ["Process Type", "Inward Type"],
        column_config={
            "OSP Process": st.column_config.SelectboxColumn(options=process_names, required=True, width="medium"),
            "Process Type": st.column_config.TextColumn(width="small"),
            "Inward Type": st.column_config.TextColumn(width="small"),
            "Specification / Standard": st.column_config.TextColumn(required=True, width="large"),
            "Specification Reference": st.column_config.TextColumn(width="medium"),
            "Drawing Number": st.column_config.TextColumn(width="medium"),
            "Drawing Revision": st.column_config.TextColumn(width="small"),
            "Dimensional Required": st.column_config.CheckboxColumn(),
            "MetLAB Required": st.column_config.CheckboxColumn(),
            "Sample Qty": st.column_config.NumberColumn(min_value=1, max_value=20, step=1, required=True),
            "Status": st.column_config.SelectboxColumn(options=["ACTIVE", "INACTIVE"], required=True),
        },
    )
    st.caption(
        "Only OUTSOURCED Process Masters are accepted as OSP groups. Case Carburizing, QT, Gas Nitriding and Nitro Carburising therefore remain separate controlled groups."
    )
    if st.button("Save OSP Process Specification Groups", type="primary", disabled=not writable, width="stretch"):
        try:
            for index, row in process_edit.iterrows():
                process_name = str(row.get("OSP Process") or "").strip()
                if not process_name:
                    continue
                process = process_by_name.get(process_name)
                if not process:
                    raise ValueError(f"Select a valid OSP Process for row {index + 1}.")
                if str(process.get("process_type")) != "OUTSOURCED":
                    raise ValueError(f"{process_name} must be an OUTSOURCED Process Master.")
                standard = str(row.get("Specification / Standard") or "").strip()
                if not standard:
                    raise ValueError(f"Specification / Standard is required for {process_name}.")
                payload = {
                    "part_id": part_id,
                    "process_id": process.get("id"),
                    "inward_type": "OSP_PROCESS",
                    "process_specification": standard,
                    "specification_reference": str(row.get("Specification Reference") or "").strip() or None,
                    "drawing_number": str(row.get("Drawing Number") or "").strip() or None,
                    "drawing_revision": str(row.get("Drawing Revision") or "").strip() or None,
                    "dimensional_required": bool(row.get("Dimensional Required")),
                    "metlab_required": bool(row.get("MetLAB Required")),
                    "sample_quantity": int(row.get("Sample Qty") or 1),
                    "sequence_no": 10 * (index + 1),
                    "status": str(row.get("Status") or "ACTIVE"),
                }
                repo.upsert_by(
                    "part_process_specifications", payload,
                    natural_key={"part_id": part_id, "process_id": process.get("id"), "inward_type": "OSP_PROCESS"},
                )
            st.success("OSP Process Specification Groups saved.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    # Reload after save so process parameters and drawings are always linked to a persistent group ID.
    process_specs = repo.select(
        "part_process_specifications",
        eq={"part_id": part_id, "inward_type": "OSP_PROCESS"},
        order_by="sequence_no", limit=500,
    )
    if not process_specs:
        st.info("Save at least one OSP Process Specification Group to add parameters, drawing and generated layouts.")
        return

    process_map = {str(row.get("id")): next(
        (p for p in processes if str(p.get("id")) == str(row.get("process_id"))), {}
    ) for row in process_specs}
    group_labels = {
        str(row["id"]): f"{(process_map.get(str(row['id'])) or {}).get('process_name')} · {row.get('process_specification')}"
        for row in process_specs
    }
    requested_group = str(st.session_state.get("selected_osp_process_spec_id") or "")
    group_ids = list(group_labels)
    selected_group_id = st.selectbox(
        "Select OSP Process Group for Parameters and Drawing",
        group_ids,
        index=group_ids.index(requested_group) if requested_group in group_ids else 0,
        format_func=lambda value: group_labels[value],
        key=f"selected_osp_process_group_{part_id}",
    )
    st.session_state["selected_osp_process_spec_id"] = selected_group_id
    selected_group = next(row for row in process_specs if str(row.get("id")) == selected_group_id)
    selected_process = process_map.get(selected_group_id) or {}

    section_bar(
        f"{selected_process.get('process_name') or 'OSP PROCESS'} · CONTROLLED DRAWING",
        "The drawing is attached to this Part + OSP Process group only and is available during layout preparation.",
    )
    render_attachment_manager(
        repo=repo,
        entity_type="PART_PROCESS_SPEC",
        entity_id=selected_group_id,
        folder="osp-process-drawings",
        slots=(AttachmentSlot("OSP_PROCESS_DRAWING", "OSP Process Drawing", "PDF, image, DWG or DXF process drawing"),),
        key_prefix=f"osp_process_drawing_{selected_group_id}",
        can_add_or_replace=writable,
        can_delete=perms["can_archive"],
        title="OSP PROCESS DRAWING ATTACHMENT",
    )

    section_bar(
        f"{selected_process.get('process_name') or 'OSP PROCESS'} · INSPECTION PARAMETERS",
        "All rows below belong only to the selected OSP Process group. Minimum and Maximum values flow into generated inspection layouts.",
    )
    osp_service = OSPService()
    parameter_rows = osp_service.parameter_specs(selected_group_id)
    if password_delete_panel(
        repo=repo, table="part_process_parameter_specifications", rows=parameter_rows,
        labeler=lambda row: f"{row.get('inspection_type')} · {row.get('parameter_name')}",
        key=f"delete_osp_parameter_{selected_group_id}", can_delete=perms["can_archive"],
        title="Delete OSP Process Parameter",
        help_text="Current password is required. Existing generated inspection reports remain unchanged.",
    ):
        st.rerun()

    option_rows = osp_service.parameter_options(str(selected_group.get("process_id")))
    known_names = sorted({
        str(row.get("parameter_name") or "").strip()
        for row in option_rows + parameter_rows if str(row.get("parameter_name") or "").strip()
    }, key=str.casefold)
    current_names = [str(row.get("parameter_name") or "").strip() for row in parameter_rows if str(row.get("parameter_name") or "").strip()]
    selected_names = st.multiselect(
        "Select or add Parameters for this OSP Process",
        known_names,
        default=current_names,
        accept_new_options=True,
        help="Previously used parameters for the selected OSP Process are offered as reusable options.",
        key=f"osp_parameter_picker_{selected_group_id}",
    )
    existing_keys = {
        (str(row.get("inspection_type") or "DIMENSIONAL"), str(row.get("parameter_name") or "").casefold())
        for row in parameter_rows
    }
    new_parameter_rows = []
    for name in selected_names:
        if not any(key[1] == str(name).casefold() for key in existing_keys):
            new_parameter_rows.append({
                "inspection_type": "DIMENSIONAL", "parameter_name": name,
                "specification_text": "", "minimum_spec": None, "maximum_spec": None,
                "unit": "", "characteristic_type": "VARIABLE", "checking_method": "",
                "sample_size": int(selected_group.get("sample_quantity") or 1),
                "is_mandatory": True, "allow_na": False, "sequence_no": 10 * (len(parameter_rows) + len(new_parameter_rows) + 1),
                "status": "ACTIVE", "id": None,
            })

    parameter_frame = pd.DataFrame([{
        "Inspection Type": row.get("inspection_type") or "DIMENSIONAL",
        "Parameter": row.get("parameter_name") or "",
        "Specification": row.get("specification_text") or "",
        "Minimum": row.get("minimum_spec"),
        "Maximum": row.get("maximum_spec"),
        "Unit": row.get("unit") or "",
        "Type": row.get("characteristic_type") or "VARIABLE",
        "Checking Method": row.get("checking_method") or "",
        "Sample Size": int(row.get("sample_size") or selected_group.get("sample_quantity") or 1),
        "Mandatory": bool(row.get("is_mandatory", True)),
        "Allow NA": bool(row.get("allow_na", False)),
        "Sequence": int(row.get("sequence_no") or 10),
        "Status": row.get("status") or "ACTIVE",
        "_id": row.get("id"),
    } for row in parameter_rows + new_parameter_rows], columns=[
        "Inspection Type", "Parameter", "Specification", "Minimum", "Maximum", "Unit", "Type",
        "Checking Method", "Sample Size", "Mandatory", "Allow NA", "Sequence", "Status", "_id",
    ])
    parameter_edit = st.data_editor(
        parameter_frame, num_rows="dynamic", hide_index=True, width="stretch",
        height=min(620, max(250, 105 + max(len(parameter_frame), 1) * 34)),
        disabled=not writable,
        column_config={
            "Inspection Type": st.column_config.SelectboxColumn(options=["DIMENSIONAL", "METLAB"], required=True),
            "Parameter": st.column_config.SelectboxColumn(options=sorted(set(known_names + list(selected_names)), key=str.casefold) or [""], required=True, width="medium"),
            "Specification": st.column_config.TextColumn(width="large"),
            "Minimum": st.column_config.NumberColumn(format="%.4f"),
            "Maximum": st.column_config.NumberColumn(format="%.4f"),
            "Unit": st.column_config.TextColumn(width="small"),
            "Type": st.column_config.SelectboxColumn(options=["VARIABLE", "ATTRIBUTE"], required=True),
            "Checking Method": st.column_config.TextColumn(width="medium"),
            "Sample Size": st.column_config.NumberColumn(min_value=1, max_value=20, step=1, required=True),
            "Mandatory": st.column_config.CheckboxColumn(),
            "Allow NA": st.column_config.CheckboxColumn(),
            "Sequence": st.column_config.NumberColumn(min_value=1, step=1, required=True),
            "Status": st.column_config.SelectboxColumn(options=["ACTIVE", "INACTIVE"], required=True),
            "_id": None,
        },
        key=f"osp_parameter_grid_{selected_group_id}",
    )
    if st.button("Save OSP Process Parameters", type="primary", disabled=not writable, width="stretch"):
        try:
            existing_by_key = {
                (str(row.get("inspection_type") or "").upper(), str(row.get("parameter_name") or "").casefold()): row
                for row in parameter_rows
            }
            saved_count = 0
            for index, row in parameter_edit.iterrows():
                inspection_type = str(row.get("Inspection Type") or "").upper().strip()
                parameter_name = str(row.get("Parameter") or "").strip()
                if not parameter_name:
                    continue
                lower = None if pd.isna(row.get("Minimum")) else float(row.get("Minimum"))
                upper = None if pd.isna(row.get("Maximum")) else float(row.get("Maximum"))
                specification = str(row.get("Specification") or "").strip()
                characteristic_type = str(row.get("Type") or "VARIABLE").upper()
                if lower is not None and upper is not None and lower > upper:
                    raise ValueError(f"{parameter_name}: Minimum specification exceeds Maximum specification.")
                if characteristic_type == "VARIABLE" and lower is None and upper is None and not specification:
                    raise ValueError(f"{parameter_name}: Enter Minimum, Maximum or Specification.")
                payload = {
                    "process_specification_id": selected_group_id,
                    "part_id": part_id,
                    "process_id": selected_group.get("process_id"),
                    "inward_type": "OSP_PROCESS",
                    "inspection_type": inspection_type,
                    "parameter_name": parameter_name,
                    "specification_text": specification or None,
                    "minimum_spec": lower,
                    "maximum_spec": upper,
                    "unit": str(row.get("Unit") or "").strip() or None,
                    "characteristic_type": characteristic_type,
                    "checking_method": str(row.get("Checking Method") or "").strip() or None,
                    "sample_size": int(row.get("Sample Size") or selected_group.get("sample_quantity") or 1),
                    "is_mandatory": bool(row.get("Mandatory")),
                    "allow_na": bool(row.get("Allow NA")),
                    "sequence_no": int(row.get("Sequence") or 10 * (index + 1)),
                    "status": str(row.get("Status") or "ACTIVE"),
                }
                existing_parameter = existing_by_key.get((inspection_type, parameter_name.casefold()))
                if existing_parameter:
                    repo.update("part_process_parameter_specifications", str(existing_parameter["id"]), payload)
                else:
                    repo.insert("part_process_parameter_specifications", payload)
                saved_count += 1
            st.success(f"{saved_count} OSP Process parameter(s) saved under {selected_process.get('process_name')}.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    layout_perms = current_permissions("INSPECTION_LAYOUTS")
    active_parameters = [row for row in parameter_rows if str(row.get("status")) == "ACTIVE"]
    c1, c2 = st.columns([2, 1], gap="small")
    with c1:
        st.caption(
            "Generate approved Dimensional and MetLAB layouts directly from this Process group. Layouts are versioned automatically after they have been used."
        )
    with c2:
        if st.button(
            "Create / Update Inspection Layouts",
            icon=":material/auto_awesome:",
            type="primary",
            disabled=not active_parameters or not writable or not (layout_perms["can_create"] or layout_perms["can_edit"]),
            width="stretch",
            key=f"generate_osp_layouts_{selected_group_id}",
        ):
            try:
                result = osp_service.generate_layouts(selected_group_id)
                st.success(
                    f"{int(result.get('layouts') or 0)} layout(s) and {int(result.get('characteristics') or 0)} characteristic(s) generated."
                )
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    generated = osp_service.generated_layouts(selected_group_id)
    if generated:
        st.dataframe(pd.DataFrame([{
            "Layout Type": row.get("layout_type"),
            "Plan Number": row.get("plan_number"),
            "Revision": row.get("revision"),
            "Layout Name": row.get("layout_name"),
            "Status": row.get("status"),
            "Effective Date": row.get("effective_date"),
        } for row in generated]), hide_index=True, width="stretch", height=min(260, 80 + len(generated) * 36))
        st.page_link(
            st.session_state["_qsms_pages"]["inspection-layout-records"],
            label="Open Generated Inspection Layouts", icon=":material/open_in_new:", width="stretch",
        )


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
        labels = {str(p["id"]): f"{p.get('part_number')} · {p.get('part_name')}" for p in rows}
        selected = st.selectbox("Select Part Master record", list(labels), format_func=lambda x: labels[x])
        st.session_state["edit_part_id"] = selected
        selected_row = next(p for p in rows if str(p.get("id")) == selected)
        c1, c2 = st.columns(2, gap="small")
        with c1:
            st.page_link(st.session_state["_qsms_pages"]["part-entry"], label="Open Selected Part Master", icon=":material/edit:", width="stretch")
        with c2:
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
