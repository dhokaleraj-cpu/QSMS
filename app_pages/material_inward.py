from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.attachments import AttachmentService, AttachmentSlot, new_attachment_uploaders, render_attachment_manager
from core.delete_service import password_delete_panel
from core.inward_service import InwardService
from core.reporting import material_inward_record_pdf_bytes
from core.ui import disposition_cards, disposition_label, page_header, save_success_popup, section_bar, style_status_dataframe, subpage_navigation, template_download_row

DISPOSITIONS = ["PENDING", "ON_HOLD", "ACCEPTED", "ACCEPTED_UNDER_RESERVE", "REJECTED"]

INWARD_ATTACHMENT_SLOTS = (
    AttachmentSlot('INWARD_COPY', 'Attachment 1 · GRN / Inward Document', 'Optional GRN, inward note or receipt document', 'inward_lots', 'inward_copy_path'),
    AttachmentSlot('INWARD_ATTACHMENT_2', 'Attachment 2 · Supplier Invoice', 'Optional supplier invoice or delivery document'),
    AttachmentSlot('INWARD_ATTACHMENT_3', 'Attachment 3 · Supporting Document', 'Optional additional inward or quality document'),
)


def _employee_map(rows: list[dict]) -> dict[str, str]:
    return {
        str(row["id"]): f"{row.get('employee_code')} · {row.get('first_name')} {row.get('last_name')}"
        for row in rows
    }


def _record_from_state(service: InwardService) -> dict:
    record_id = str(st.session_state.get("edit_inward_id", "") or "").strip()
    return service.get(record_id) or {}


def _source_label(row: dict) -> str:
    return (
        f"{row.get('rmtc_number')} · {row.get('part_number')} · {row.get('supplier_name')} · "
        f"Heat {row.get('heat_number')} · Available {float(row.get('available_production_quantity_pcs') or 0):,.0f} pcs / "
        f"{float(row.get('available_steel_quantity_kg') or row.get('available_quantity') or 0):,.3f} kg"
    )


def render_entry() -> None:
    subpage_navigation(
        ("dashboard", "Dashboard", ":material/arrow_back:"),
        ("inward-records", "Material Inward Records", ":material/table_view:"),
        ("rmtc-records", "RMTC Records", ":material/fact_check:"),
        ("records-center", "Records Centre", ":material/table_view:"),
    )
    page_header("Material Inward · Entry", context="Steel quantity and production conversion")
    template_download_row([("Material_Inward_Template.xlsx", "Download Material Inward Template")], key_prefix="material_inward")

    service = InwardService()
    perms = current_permissions("MATERIAL_INWARD")
    existing = _record_from_state(service)
    writable = perms["can_edit"] if existing else perms["can_create"]

    recent_rows = service.list()
    if recent_rows:
        section_bar("CURRENT MATERIAL INWARD STATUS")
        recent_labels = {
            str(row["id"]): (
                f"{row.get('inward_number')} · {row.get('supplier_name') or '-'} · "
                f"{row.get('part_number') or '-'} · Heat {row.get('heat_number')} · "
                f"{disposition_label(row.get('status'))}"
            )
            for row in recent_rows[:100]
        }
        c1, c2 = st.columns([4, 1], gap="small")
        selected_existing_id = c1.selectbox(
            "Open Existing Material Inward",
            [""] + list(recent_labels),
            format_func=lambda value: recent_labels.get(value, "— Select an existing inward record —"),
            key="inward_entry_existing_selector",
        )
        if c2.button("Open Record", icon=":material/edit:", width="stretch", disabled=not selected_existing_id):
            st.session_state["edit_inward_id"] = selected_existing_id
            st.rerun()
        recent_frame = pd.DataFrame([{
            "Inward": row.get("inward_number"),
            "Supplier": row.get("supplier_name"),
            "Part Number": row.get("part_number"),
            "Heat": row.get("heat_number"),
            "Steel kg": row.get("steel_quantity_kg") or row.get("quantity_received"),
            "Production pcs": row.get("production_quantity_pcs"),
            "MetLAB": row.get("metallurgical_status"),
            "Dimensional": row.get("dimensional_status"),
            "Quality Decision": row.get("quality_disposition"),
            "Status": row.get("status"),
        } for row in recent_rows[:8]])
        st.dataframe(style_status_dataframe(recent_frame), hide_index=True, width="stretch", height=min(330, 75 + len(recent_frame) * 36))

    accepted_all = service.accepted_rmtc_parts()
    accepted = accepted_all if existing else [row for row in accepted_all if float(row.get("available_steel_quantity_kg") or row.get("available_quantity") or 0) > 0]
    source_map = {str(row["rmtc_part_approval_id"]): _source_label(row) for row in accepted}
    selected_existing = str(existing.get("rmtc_part_approval_id") or "")
    options = [""] + list(source_map)
    if selected_existing and selected_existing not in source_map:
        options.append(selected_existing)
        source_map[selected_existing] = f"Existing linked RMTC Part · {selected_existing}"

    section_bar("ACCEPTED RMTC STEEL SOURCE")
    source_id = st.selectbox(
        "RMTC / Part / Supplier / Available Steel",
        options,
        index=options.index(selected_existing) if selected_existing in options else 0,
        format_func=lambda value: source_map.get(value, "— Select accepted RMTC steel source —"),
        disabled=bool(existing),
    )
    source = next((row for row in accepted if str(row.get("rmtc_part_approval_id")) == source_id), {})
    if not source and existing:
        source = next((row for row in accepted_all if str(row.get("rmtc_part_approval_id")) == selected_existing), {})

    input_weight = float(existing.get("input_weight_kg") or source.get("source_input_weight_kg") or source.get("input_weight_kg") or source.get("gross_weight_kg") or source.get("forging_weight_kg") or 0)
    part_remaining_steel = float(source.get("part_remaining_planned_steel_quantity_kg") or 0)
    other_remaining_planned_steel = float(source.get("other_remaining_planned_steel_quantity_kg") or 0)
    heat_unallocated_balance = float(source.get("heat_unallocated_balance_kg") or 0)
    heat_committed_steel = float(source.get("heat_committed_steel_quantity_kg") or 0)
    available_steel = float(source.get("available_steel_for_selected_entry_kg") or source.get("available_steel_quantity_kg") or source.get("available_quantity") or 0)
    existing_steel = float(existing.get("required_steel_quantity_kg") or existing.get("steel_quantity_kg") or existing.get("quantity_received") or 0)
    available_for_entry = available_steel + (existing_steel if existing else 0)
    available_production = float(source.get("available_production_quantity_pcs") or 0)
    existing_production = float(existing.get("production_quantity_pcs") or 0)
    available_production_for_entry = available_production + (existing_production if existing else 0)

    if source:
        disposition_cards([
            {"label": "Supplier", "value": source.get("supplier_name"), "foot": source.get("forging_route")},
            {"label": "Global Heat Steel", "value": f"{float(source.get('rmtc_steel_quantity_kg') or 0):,.3f} kg", "foot": f"Committed {heat_committed_steel:,.3f} kg"},
            {"label": "Part Plan Remaining", "value": f"{available_production_for_entry:,.0f} pcs", "foot": f"{part_remaining_steel + (existing_steel if existing else 0):,.3f} kg reserved"},
            {"label": "Available for Entry", "value": f"{available_for_entry:,.3f} kg", "foot": f"Unallocated Heat {heat_unallocated_balance:,.3f} kg"},
        ])
        st.dataframe(pd.DataFrame([{
            "Part Number": source.get("part_number"), "Part Description": source.get("part_name"),
            "Supplier": source.get("supplier_name"), "Steel Mill": source.get("steel_mill_name"),
            "Material Grade": source.get("material_grade"), "Heat Number": source.get("heat_number"),
            "Internal Heat Code": source.get("heat_code"), "Section": source.get("section_size"),
            "Forging Route": source.get("forging_route"), "RMTC Decision": disposition_label(source.get("disposition")),
        }]), hide_index=True, width="stretch")

    section_bar("INWARD AND PRODUCTION QUANTITY")
    employees = service.employees()
    employee_map = _employee_map(employees)
    validator_map = _employee_map(service.employees("RAW_MATERIAL_INSPECTION"))

    c = st.columns(4, gap="small")
    inward_no = c[0].text_input("Inward Number", value=str(existing.get("inward_number") or ""), placeholder="Auto on save")
    inward_date = c[1].date_input("Inward Date", value=date.fromisoformat(str(existing.get("inward_date"))[:10]) if existing.get("inward_date") else date.today(), format="DD-MM-YYYY")
    grn = c[2].text_input("GRN Number", value=str(existing.get("grn_number") or ""))
    invoice = c[3].text_input("Supplier Invoice Number", value=str(existing.get("invoice_number") or ""))

    c = st.columns(4, gap="small")
    accepted_pcs = c[0].number_input("Accepted Production Quantity (pcs)", min_value=0.0, value=float(existing.get("accepted_production_quantity_pcs") or 0), step=1.0)
    rejected_pcs = c[1].number_input("Rejected Production Quantity (pcs)", min_value=0.0, value=float(existing.get("rejected_production_quantity_pcs") or 0), step=1.0)
    hold_pcs = c[2].number_input("On Hold Production Quantity (pcs)", min_value=0.0, value=float(existing.get("hold_production_quantity_pcs") or 0), step=1.0)
    production_qty = float(accepted_pcs) + float(rejected_pcs) + float(hold_pcs)
    c[3].number_input("Total Production Quantity (pcs)", min_value=0.0, value=production_qty, step=1.0, disabled=True)

    accepted_steel = round(float(accepted_pcs) * input_weight, 3)
    rejected_steel = round(float(rejected_pcs) * input_weight, 3)
    hold_steel = round(float(hold_pcs) * input_weight, 3)
    required_steel = round(production_qty * input_weight, 3)
    c = st.columns(4, gap="small")
    c[0].number_input("Accepted Steel Quantity (kg)", min_value=0.0, value=accepted_steel, step=0.001, format="%.3f", disabled=True)
    c[1].number_input("Rejected Steel Quantity (kg)", min_value=0.0, value=rejected_steel, step=0.001, format="%.3f", disabled=True)
    c[2].number_input("On Hold Steel Quantity (kg)", min_value=0.0, value=hold_steel, step=0.001, format="%.3f", disabled=True)
    c[3].number_input("Total Steel Quantity (kg)", min_value=0.0, value=required_steel, step=0.001, format="%.3f", disabled=True)

    c = st.columns(4, gap="small")
    c[0].number_input("Input Weight (kg/part)", min_value=0.0, value=input_weight, step=0.001, format="%.3f", disabled=True)
    c[1].number_input("Available Part Production (pcs)", min_value=0.0, value=available_production_for_entry, step=1.0, disabled=True)
    c[2].number_input("Heat Steel Available Before Entry (kg)", min_value=0.0, value=available_for_entry, step=0.001, format="%.3f", disabled=True)
    remaining_steel=max(available_for_entry-required_steel,0)
    c[3].number_input("Heat Steel Balance After Entry (kg)", min_value=0.0, value=remaining_steel, step=0.001, format="%.3f", disabled=True)

    if source_id and production_qty > available_production_for_entry + 0.001:
        st.error(f"Production quantity {production_qty:,.0f} pcs exceeds the available RMTC part plan {available_production_for_entry:,.0f} pcs.")
    elif source_id and required_steel > available_for_entry + 0.001:
        st.error(f"Total production steel {required_steel:,.3f} kg exceeds the Heat steel available before this entry {available_for_entry:,.3f} kg. The after-entry balance cannot be negative.")
    elif source_id and production_qty > 0 and input_weight > 0:
        st.success(f"Automatic conversion: {production_qty:,.0f} pcs × {input_weight:,.3f} kg = {required_steel:,.3f} kg. Heat balance after entry: {remaining_steel:,.3f} kg.")

    c = st.columns(2, gap="small")
    disposition = c[0].selectbox("Receipt Disposition", DISPOSITIONS, index=DISPOSITIONS.index(str(existing.get("receipt_disposition") or "PENDING")), format_func=disposition_label)
    c[1].text_input("Quality Gate", value=disposition_label(existing.get("quality_disposition") or "PENDING"), disabled=True)

    c = st.columns(4, gap="small")
    c[0].text_input("MetLAB Status", value=disposition_label(existing.get("metallurgical_status") or "PENDING"), disabled=True)
    c[1].text_input("Dimensional Status", value=disposition_label(existing.get("dimensional_status") or "PENDING"), disabled=True)
    prepared_options = [""] + list(employee_map)
    prepared_current = str(existing.get("prepared_by_employee_id") or "")
    prepared = c[2].selectbox("Prepared By", prepared_options, index=prepared_options.index(prepared_current) if prepared_current in prepared_options else 0, format_func=lambda value: employee_map.get(value, "— Select Employee —"))
    validator_options = [""] + list(validator_map)
    validator_current = str(existing.get("validated_by_employee_id") or "")
    validator = c[3].selectbox("Validated By", validator_options, index=validator_options.index(validator_current) if validator_current in validator_options else 0, format_func=lambda value: validator_map.get(value, "— Select Quality Employee —"))

    reserve_reason = st.text_input("Hold / Reserve / Rejection Reason", value=str(existing.get("reserve_reason") or ""))
    remarks = st.text_area("Remarks", value=str(existing.get("remarks") or ""), height=70)
    new_attachments = {} if existing else new_attachment_uploaders(
        INWARD_ATTACHMENT_SLOTS, key_prefix='inward_new', title='OPTIONAL MATERIAL INWARD ATTACHMENTS'
    )

    invalid_quantity = production_qty > available_production_for_entry + 0.001 or required_steel > available_for_entry + 0.001
    if st.button("Save Material Inward", type="primary", disabled=not writable or invalid_quantity, width="stretch"):
        try:
            if not source_id:
                raise ValueError("Select an Accepted or Accepted Under Reserve RMTC Part Number.")
            if not grn.strip() or production_qty <= 0 or input_weight <= 0 or not prepared:
                raise ValueError("GRN, Production Quantity, Input Weight and Prepared By are mandatory.")
            if production_qty > available_production_for_entry:
                raise ValueError("Production quantity cannot exceed the remaining RMTC part production plan.")
            if required_steel > available_for_entry:
                raise ValueError("Calculated steel quantity cannot exceed the available RMTC heat balance.")
            if disposition == "REJECTED" and (accepted_pcs > 0 or hold_pcs > 0 or rejected_pcs <= 0):
                raise ValueError("Rejected disposition requires only Rejected Production Quantity.")
            if disposition == "ON_HOLD" and hold_pcs <= 0:
                raise ValueError("On Hold disposition requires On Hold Production Quantity.")
            if disposition in ("ACCEPTED", "ACCEPTED_UNDER_RESERVE") and accepted_pcs <= 0:
                raise ValueError("Accepted disposition requires Accepted Production Quantity.")
            if disposition in ("ON_HOLD", "ACCEPTED_UNDER_RESERVE", "REJECTED") and not reserve_reason.strip():
                raise ValueError("Reason is mandatory for On Hold, Accepted Under Reserve or Rejected disposition.")
            final_number = inward_no.strip() or service.next_number()
            payload: dict[str, Any] = {
                "inward_number": final_number, "inward_date": inward_date.isoformat(), "grn_number": grn.strip(),
                "invoice_number": invoice.strip() or None, "rmtc_approval_id": source.get("rmtc_approval_id"),
                "rmtc_part_approval_id": source_id, "part_id": source.get("part_id"), "supplier_id": source.get("supplier_id"),
                "supplier_source_detail_id": source.get("supplier_source_detail_id"), "heat_number": source.get("heat_number"),
                "heat_code": source.get("heat_code"), "steel_quantity_kg": required_steel, "quantity_received": required_steel,
                "production_quantity_pcs": production_qty, "accepted_production_quantity_pcs": accepted_pcs,
                "rejected_production_quantity_pcs": rejected_pcs, "hold_production_quantity_pcs": hold_pcs,
                "input_weight_kg": input_weight, "required_steel_quantity_kg": required_steel,
                "accepted_steel_quantity_kg": accepted_steel, "rejected_steel_quantity_kg": rejected_steel,
                "hold_steel_quantity_kg": hold_steel, "quantity_accepted": accepted_steel,
                "quantity_rejected": rejected_steel, "metallurgical_status": str(existing.get("metallurgical_status") or "PENDING"),
                "dimensional_status": str(existing.get("dimensional_status") or "PENDING"), "receipt_disposition": disposition,
                "reserve_reason": reserve_reason.strip() or None, "prepared_by_employee_id": prepared,
                "validated_by_employee_id": validator or None, "status": str(existing.get("status") or "HOLD_PENDING_INSPECTION"),
                "remarks": remarks.strip() or None,
            }
            with st.spinner("Saving steel and production allocation…"):
                saved = service.save(payload, str(existing["id"]) if existing else None)
                attachment_service = AttachmentService(service.repo)
                for slot in INWARD_ATTACHMENT_SLOTS:
                    selected_file = new_attachments.get(slot.document_type)
                    if selected_file is not None:
                        attachment_service.upload(
                            entity_type='MATERIAL_INWARD', entity_id=str(saved['id']), folder='inward',
                            slot=slot, file=selected_file,
                        )
            st.session_state["edit_inward_id"] = str(saved["id"])
            st.session_state["inspection_inward_id"] = str(saved["id"])
            save_success_popup(f"Material Inward {saved.get('inward_number')} saved successfully.", queue_for_rerun=True)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    if existing:
        st.session_state["inspection_inward_id"] = str(existing.get("id"))
        render_attachment_manager(
            repo=service.repo, entity_type='MATERIAL_INWARD', entity_id=str(existing.get('id')), folder='inward',
            slots=INWARD_ATTACHMENT_SLOTS, key_prefix=f'inward_entry_{existing.get("id")}',
            can_add_or_replace=perms['can_edit'], can_delete=perms['can_archive'],
            title='MATERIAL INWARD ATTACHMENTS',
        )
        c1, c2 = st.columns(2, gap="small")
        with c1:
            st.page_link(st.session_state["_qsms_pages"]["metlab-entry"], label="Open MetLAB Report", icon=":material/science:", width="stretch")
        with c2:
            st.page_link(st.session_state["_qsms_pages"]["dimensional-entry"], label="Open Dimensional Report", icon=":material/straighten:", width="stretch")


def render_records() -> None:
    subpage_navigation(("dashboard", "Dashboard", ":material/arrow_back:"), ("records-center", "Records Centre", ":material/table_view:"), ("inward-entry", "New Material Inward / Edit", ":material/input:"))
    page_header("Material Inward · Records", context="Steel and production register")
    service = InwardService(); perms = current_permissions("MATERIAL_INWARD")
    rows = service.list(); search = st.text_input("Search Inward, GRN, Supplier Invoice or Heat")
    filtered = [row for row in rows if not search or search.casefold() in " ".join(str(row.get(key) or "") for key in ("inward_number", "grn_number", "heat_number", "heat_code", "invoice_number")).casefold()]

    if filtered:
        labels = {str(row["id"]): f"{row.get('inward_number')} · {row.get('supplier_name') or '-'} · {row.get('part_number') or '-'} · Heat {row.get('heat_number')} · {disposition_label(row.get('status'))}" for row in filtered}
        selected = st.selectbox("Select Material Inward record", list(labels), format_func=lambda value: labels[value])
        st.session_state["edit_inward_id"] = selected; st.session_state["inspection_inward_id"] = selected
        selected_row = next(row for row in filtered if str(row.get("id")) == selected)
        c1, c2, c3, c4, c5 = st.columns(5, gap="small")
        with c1: st.page_link(st.session_state["_qsms_pages"]["inward-entry"], label="Open Inward", icon=":material/edit:", width="stretch")
        with c2: st.page_link(st.session_state["_qsms_pages"]["metlab-entry"], label="MetLAB", icon=":material/science:", width="stretch")
        with c3: st.page_link(st.session_state["_qsms_pages"]["dimensional-entry"], label="Dimensional", icon=":material/straighten:", width="stretch")
        with c4:
            try:
                pdf_bytes = material_inward_record_pdf_bytes(service.report_payload(selected))
                st.download_button("Download Inward PDF", data=pdf_bytes, file_name=f"{selected_row.get('inward_number') or 'Material_Inward'}.pdf", mime="application/pdf", key=f"inward_pdf_{selected}", width="stretch")
            except Exception as exc:
                st.error(f"PDF could not be generated: {exc}")
        with c5:
            if password_delete_panel(repo=service.repo, table="inward_lots", rows=[selected_row], labeler=lambda row: f"{row.get('inward_number')} · {row.get('grn_number')}", key=f"delete_inward_{selected}", can_delete=perms["can_archive"], title="Delete Selected Material Inward", help_text="Current password and Material Inward Delete permission are required."):
                st.rerun()
        render_attachment_manager(
            repo=service.repo, entity_type='MATERIAL_INWARD', entity_id=selected, folder='inward',
            slots=INWARD_ATTACHMENT_SLOTS, key_prefix=f'inward_records_{selected}',
            can_add_or_replace=perms['can_edit'], can_delete=perms['can_archive'],
            title='SELECTED MATERIAL INWARD ATTACHMENTS',
        )
    else:
        st.info("No Material Inward records match the search.")

    section_bar("MATERIAL INWARD REGISTER")
    df = pd.DataFrame([{
        "Inward Number": row.get("inward_number"), "Date": row.get("inward_date"), "GRN": row.get("grn_number"),
        "Supplier": row.get("supplier_name"), "Part Number": row.get("part_number"), "Part Description": row.get("part_name"),
        "Heat Number": row.get("heat_number"), "Heat Code": row.get("heat_code"),
        "Steel Qty kg": row.get("steel_quantity_kg") or row.get("quantity_received"),
        "Production Qty pcs": row.get("production_quantity_pcs"), "Accepted pcs": row.get("accepted_production_quantity_pcs"), "Rejected pcs": row.get("rejected_production_quantity_pcs"), "On Hold pcs": row.get("hold_production_quantity_pcs"), "Input Weight kg": row.get("input_weight_kg"),
        "Required Steel kg": row.get("required_steel_quantity_kg"), "Accepted Steel kg": row.get("accepted_steel_quantity_kg"), "Rejected Steel kg": row.get("rejected_steel_quantity_kg"), "On Hold Steel kg": row.get("hold_steel_quantity_kg"), "RMTC Decision": row.get("rmtc_disposition"),
        "Receipt Decision": row.get("receipt_disposition"), "MetLAB": row.get("metallurgical_status"),
        "Dimensional": row.get("dimensional_status"), "Quality Decision": row.get("quality_disposition"), "Status": row.get("status"),
    } for row in filtered])
    st.dataframe(style_status_dataframe(df), hide_index=True, width="stretch", height=620)
