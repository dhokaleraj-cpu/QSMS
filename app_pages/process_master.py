from __future__ import annotations

import pandas as pd
import streamlit as st
from core.ui import portal_table

from core.access import current_permissions
from core.delete_service import password_delete_panel
from core.master_definitions import MASTER_BY_KEY
from core.master_service import MasterService
from core.reporting import controlled_record_pdf_bytes
from core.attachments import AttachmentService
from core.selection_labels import customer_standard_label, party_label, process_label
from core.ui import consume_master_blank_request, page_header, save_success_popup, section_bar, stage_section, template_download_row


def _label(row: dict) -> str:
    return process_label(row)


def _related_standards(repo, process_id: str) -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    rows = repo.select("customer_standards", eq={"process_id": process_id}, order_by="standard_code", limit=3000) if process_id else []
    parties = {str(r["id"]): r for r in repo.select("parties", limit=3000)}
    attachments = repo.select("document_attachments", eq={"entity_type": "CUSTOMER_STANDARD", "status": "ACTIVE"}, limit=5000)
    amap = {str(r.get("entity_id")): r for r in attachments if str(r.get("document_type")) == "STANDARD_DOCUMENT"}
    return rows, parties, amap


def _render_related_standards(repo, process: dict, *, key_prefix: str, show_heading: bool = True) -> list[dict]:
    standards, parties, attachments = _related_standards(repo, str(process.get("id") or ""))
    if show_heading:
        section_bar("RELATED CUSTOMER STANDARDS & SPECIFICATIONS", "Standards linked to this Process Master. Attachments can be downloaded directly.")
    if not standards:
        st.info("No Customer Standards / Specifications are linked to this Process yet.")
        st.page_link(st.session_state["_qsms_pages"]["standards-entry"], label="Open Customer Standards Bank", icon=":material/library_books:", width="stretch")
        return []
    display = [{
        "Code": row.get("standard_code"), "Standard / Specification": row.get("standard_name"),
        "Customer": party_label(parties.get(str(row.get("customer_id"))) or {}) or "General",
        "Author": row.get("author_name"), "Revision": row.get("revision_number"),
        "Revision Date": row.get("revision_date"), "Status": row.get("status"),
        "Attachment": (attachments.get(str(row.get("id"))) or {}).get("file_name") or "Not attached",
    } for row in standards]
    portal_table(pd.DataFrame(display), hide_index=True, width="stretch", height=min(280, 72 + len(display) * 36))
    service = AttachmentService(repo)
    cols = st.columns(min(3, len(standards)), gap="small")
    for index, row in enumerate(standards):
        attachment = attachments.get(str(row.get("id")))
        if not attachment:
            continue
        try:
            content = service.download(attachment)
        except Exception:
            content = None
        if content is not None:
            with cols[index % len(cols)]:
                st.download_button(
                    f"Download {row.get('standard_code')} · Rev {row.get('revision_number') or '-'}", content,
                    file_name=str(attachment.get("file_name") or f"{row.get('standard_code')}.pdf"),
                    mime=str(attachment.get("mime_type") or "application/octet-stream"),
                    key=f"{key_prefix}_{row.get('id')}", width="stretch",
                )
    return display


def render_entry() -> None:
    page_header("Process Master · Entry")
    template_download_row([("Reference_Masters_Template.xlsx", "Download Process Master Template")], key_prefix="process_master", import_master_key="processes")
    service = MasterService()
    definition = MASTER_BY_KEY["processes"]
    perms = current_permissions("REFERENCE_MASTERS")
    rows = service.list_records(definition, status="All")
    labels = {str(row["id"]): _label(row) for row in rows}
    force_new = consume_master_blank_request("process-entry", edit_keys=("edit_process_id",), widget_keys=("process_master_record_selector",))
    requested = str(st.session_state.pop("edit_process_id", "") or "")
    options = ["__new__"] + list(labels); selector_key="process_master_record_selector"
    if force_new: st.session_state[selector_key]="__new__"
    elif requested in options: st.session_state[selector_key]=requested
    elif st.session_state.get(selector_key) not in options: st.session_state[selector_key]="__new__"
    selected = st.selectbox(
        "Process Master record",
        options,
        format_func=lambda value: "＋ New Process" if value == "__new__" else labels[value],
        key=selector_key,
    )
    existing = next((row for row in rows if str(row.get("id")) == selected), {})
    writable = perms["can_edit"] if existing else perms["can_create"]

    auto_key = "_qsms_auto_process_code"
    if not existing and not st.session_state.get(auto_key):
        try:
            st.session_state[auto_key] = service.next_master_code(definition)
        except Exception:
            st.session_state[auto_key] = ""

    with stage_section("A", "PROCESS DETAILS", key="process_master_render_entry_a"):
        with st.form(f"process_master_{selected}"):
            c1, c2, c3 = st.columns(3, gap="small")
            process_code = c1.text_input(
                "Process Code",
                value=str(existing.get("process_code") or st.session_state.get(auto_key) or ""),
                help="Generated automatically for new records and editable before saving.",
            )
            process_name = c2.text_input("Process Name", value=str(existing.get("process_name") or ""))
            process_type = c3.selectbox(
                "Process Type",
                ["IN_HOUSE", "OUTSOURCED"],
                index=0 if str(existing.get("process_type") or "IN_HOUSE") == "IN_HOUSE" else 1,
            )
            c1, c2, c3 = st.columns(3, gap="small")
            special_process = c1.checkbox("Special Process", value=bool(existing.get("special_process", False)))
            cqi_standard = c2.text_input("CQI Standard", value=str(existing.get("cqi_standard") or ""), placeholder="CQI-9")
            status = c3.selectbox(
                "Status", ["ACTIVE", "INACTIVE"],
                index=0 if str(existing.get("status") or "ACTIVE") == "ACTIVE" else 1,
            )
            remarks = st.text_area("Remarks", value=str(existing.get("remarks") or ""), height=80)
            save = st.form_submit_button("Save Process Master", type="primary", disabled=not writable, width="stretch")

        if save:
            try:
                if not process_code.strip() or not process_name.strip():
                    raise ValueError("Process Code and Process Name are mandatory.")
                payload = {
                    "process_code": process_code.strip(),
                    "process_name": process_name.strip(),
                    "process_type": process_type,
                    "special_process": special_process,
                    "cqi_standard": cqi_standard.strip() or None,
                    "status": status,
                    "remarks": remarks.strip() or None,
                }
                service.assert_no_duplicate(
                    definition,
                    payload,
                    record_id=str(existing["id"]) if existing else None,
                    extra_unique_fields=("process_name",),
                )
                if existing:
                    service.repo.update("processes", str(existing["id"]), payload)
                else:
                    service.repo.insert("processes", payload)
                st.session_state.pop(auto_key, None)
                save_success_popup("Process Master saved successfully.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    if existing:
        with stage_section("B", "RELATED CUSTOMER STANDARDS & SPECIFICATIONS", "Standards linked to this Process Master. Attachments can be downloaded directly.", key="process_master_render_entry_b"):
            _render_related_standards(service.repo, existing, key_prefix=f"process_standard_entry_{existing.get('id')}", show_heading=False)

    if existing and password_delete_panel(
        repo=service.repo,
        table="processes",
        rows=[existing],
        labeler=_label,
        key=f"delete_process_{existing.get('id')}",
        can_delete=perms["can_archive"],
        title="Delete Process Master",
        help_text="Permanent deletion requires the current QCMS password. Linked Process records cannot be deleted; deactivate them instead.",
    ):
        st.rerun()


def render_records() -> None:
    page_header("Process Master · Records")
    service = MasterService()
    perms = current_permissions("REFERENCE_MASTERS")
    definition = MASTER_BY_KEY["processes"]
    c1, c2 = st.columns([3, 1], gap="small")
    search = c1.text_input("Search Process Code or Name")
    status = c2.selectbox("Status", ["All", "Active", "Inactive"])
    rows = service.list_records(definition, search=search, status=status)

    if rows:
        labels = {str(row["id"]): _label(row) for row in rows}
        selected = st.selectbox("Select Process", list(labels), format_func=lambda value: labels[value])
        selected_row = next(row for row in rows if str(row.get("id")) == selected)
        st.session_state["edit_process_id"] = selected
        c1, c2, c3 = st.columns(3, gap="small")
        with c1:
            st.page_link(
                st.session_state["_qsms_pages"]["process-entry"],
                label="Open Selected Process",
                icon=":material/edit:",
                width="stretch",
            )
        standards, standard_parties, standard_attachments = _related_standards(service.repo, selected)
        standard_pdf_rows = [{
            "Standard Code": row.get("standard_code"), "Standard / Specification": row.get("standard_name"),
            "Customer": party_label(standard_parties.get(str(row.get("customer_id"))) or {}) or "General",
            "Revision": row.get("revision_number"), "Revision Date": row.get("revision_date"),
            "Author": row.get("author_name"), "Attachment": (standard_attachments.get(str(row.get("id"))) or {}).get("file_name") or "Not attached",
        } for row in standards]
        with c2:
            pdf = controlled_record_pdf_bytes(
                "PROCESS MASTER RECORD",
                {"Process Code": selected_row.get("process_code"), "Process Name": selected_row.get("process_name"), "Process Type": selected_row.get("process_type"), "Special Process": selected_row.get("special_process"), "CQI Standard": selected_row.get("cqi_standard"), "Status": selected_row.get("status"), "Remarks": selected_row.get("remarks")},
                {"Related Customer Standards / Specifications": standard_pdf_rows},
                record_number=str(selected_row.get("process_code") or ""),
            )
            st.download_button("Download Process PDF", pdf, file_name=f"Process_{selected_row.get('process_code')}.pdf", mime="application/pdf", width="stretch")
        with c3:
            delete_clicked = password_delete_panel(
                repo=service.repo,
                table="processes",
                rows=[selected_row],
                labeler=_label,
                key=f"delete_process_record_{selected}",
                can_delete=perms["can_archive"],
                title="Delete Selected Process",
                help_text="Permanent deletion requires the current QCMS password. Linked Process records cannot be deleted.",
            )
            if delete_clicked:
                st.rerun()
        _render_related_standards(service.repo, selected_row, key_prefix=f"process_standard_record_{selected}")
    else:
        st.info("No Process Master records match the selected filters.")

    section_bar("PROCESS MASTER REGISTER")
    frame = pd.DataFrame([{
        "Process Code": row.get("process_code"),
        "Process Name": row.get("process_name"),
        "Process Type": row.get("process_type"),
        "Special Process": row.get("special_process"),
        "CQI Standard": row.get("cqi_standard"),
        "Status": row.get("status"),
        "Remarks": row.get("remarks"),
    } for row in rows])
    portal_table(frame, hide_index=True, width="stretch", height=620)
