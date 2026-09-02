from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st
from core.ui import portal_table

from core.access import current_permissions
from core.attachments import ALLOWED_ATTACHMENT_TYPES, AttachmentService, AttachmentSlot, render_attachment_manager
from core.delete_service import password_delete_panel
from core.master_definitions import MASTER_BY_KEY
from core.master_service import MasterService
from core.reporting import controlled_record_pdf_bytes
from core.selection_labels import customer_standard_label, party_label, process_label
from core.ui import consume_master_blank_request, page_header, record_widget_token, save_success_popup, section_bar, subpage_navigation, template_download_row

STANDARD_SLOT = AttachmentSlot(
    "STANDARD_DOCUMENT",
    "Controlled Standard / Specification Attachment",
    "Upload the controlled customer standard/specification file. PDF, Office documents, drawings and ZIP are supported.",
)


def _maps(service: MasterService):
    repo = service.repo
    customers = repo.select("parties", contains={"party_types": ["CUSTOMER"]}, eq={"status": "ACTIVE"}, order_by="party_code", limit=3000)
    processes = repo.select("processes", eq={"status": "ACTIVE"}, order_by="process_code", limit=3000)
    customer_map = {str(r["id"]): party_label(r) for r in customers}
    process_map = {str(r["id"]): process_label(r) for r in processes}
    return customers, processes, customer_map, process_map


def _label(row: dict, customer_map: dict[str, str], process_map: dict[str, str]) -> str:
    customer = customer_map.get(str(row.get("customer_id")), "")
    process = process_map.get(str(row.get("process_id")), "")
    return customer_standard_label(row, customer_name=customer, process_name=process)


def _attachment_summary(service: MasterService, standard_id: str) -> tuple[dict | None, bytes | None]:
    attachment = service.repo.find_one(
        "document_attachments",
        eq={"entity_type": "CUSTOMER_STANDARD", "entity_id": standard_id, "document_type": "STANDARD_DOCUMENT", "status": "ACTIVE"},
    )
    if not attachment:
        return None, None
    try:
        data = AttachmentService(service.repo).download(attachment)
    except Exception:
        data = None
    return attachment, data


def render_entry() -> None:
    subpage_navigation(
        ("masters", "Back to Masters", ":material/arrow_back:"),
        ("standards-records", "Standards Bank Records", ":material/table_view:"),
    )
    page_header(
        "Customer Standards & Specification Bank · Entry",
        "Controlled customer standards linked to Process Master, revisions and downloadable attachments.",
        "New / edit",
    )
    template_download_row(
        [("Customer_Standards_Template.xlsx", "Download Customer Standards Template")],
        key_prefix="customer_standards",
        import_master_key="customer_standards",
    )

    service = MasterService()
    repo = service.repo
    definition = MASTER_BY_KEY["customer_standards"]
    perms = current_permissions("REFERENCE_MASTERS")
    _, _, customer_map, process_map = _maps(service)
    rows = service.list_records(definition, status="All")
    labels = {str(r["id"]): _label(r, customer_map, process_map) for r in rows}
    force_new = consume_master_blank_request("standards-entry", edit_keys=("edit_customer_standard_id",), widget_keys=("customer_standard_record_selector",))
    requested = str(st.session_state.pop("edit_customer_standard_id", "") or "")
    options = ["__new__"] + list(labels); selector_key="customer_standard_record_selector"
    if force_new: st.session_state[selector_key]="__new__"
    elif requested in options: st.session_state[selector_key]=requested
    elif st.session_state.get(selector_key) not in options: st.session_state[selector_key]="__new__"
    selected = st.selectbox(
        "Customer Standard / Specification record",
        options,
        format_func=lambda value: "＋ New Customer Standard" if value == "__new__" else labels[value],
        key=selector_key,
    )
    existing = next((r for r in rows if str(r.get("id")) == selected), {})
    writable = perms["can_edit"] if existing else perms["can_create"]
    scope = record_widget_token("standards-entry", existing, selected=selected)

    auto_key = "_qcms_auto_customer_standard_code"
    if not existing and not st.session_state.get(auto_key):
        try:
            st.session_state[auto_key] = service.next_master_code(definition)
        except Exception:
            st.session_state[auto_key] = ""

    section_bar("STANDARD / SPECIFICATION DETAILS")
    with st.form(f"customer_standard_{scope}"):
        c = st.columns(4, gap="small")
        standard_code = c[0].text_input(
            "Standard Code",
            value=str(existing.get("standard_code") or st.session_state.get(auto_key) or ""),
            help="Generated automatically for new records and editable before saving.",
        )
        standard_name = c[1].text_input("Standard / Specification Name", value=str(existing.get("standard_name") or ""))
        author_name = c[2].text_input("Author / Issuing Authority", value=str(existing.get("author_name") or ""))
        revision_number = c[3].text_input("Revision Number", value=str(existing.get("revision_number") or "00"))

        c = st.columns(4, gap="small")
        customer_options = [""] + list(customer_map)
        current_customer = str(existing.get("customer_id") or "")
        customer_id = c[0].selectbox(
            "Customer",
            customer_options,
            index=customer_options.index(current_customer) if current_customer in customer_options else 0,
            format_func=lambda value: customer_map.get(value, "— General / Not customer-specific —"),
            help="Optional for an industry/general specification; customer-specific standards should select the Customer Master record.",
        )
        if not process_map:
            c[1].warning("Create an active Process Master record first.")
            process_id = ""
        else:
            current_process = str(existing.get("process_id") or next(iter(process_map)))
            process_id = c[1].selectbox(
                "Related Process",
                list(process_map),
                index=list(process_map).index(current_process) if current_process in process_map else 0,
                format_func=lambda value: process_map[value],
            )
        revision_value = None
        if existing.get("revision_date"):
            try:
                revision_value = date.fromisoformat(str(existing.get("revision_date"))[:10])
            except Exception:
                revision_value = None
        revision_date = c[2].date_input("Revision Date", value=revision_value, format="DD-MM-YYYY")
        statuses = ["ACTIVE", "INACTIVE", "SUPERSEDED"]
        current_status = str(existing.get("status") or "ACTIVE")
        status = c[3].selectbox("Status", statuses, index=statuses.index(current_status) if current_status in statuses else 0)
        remarks = st.text_area("Remarks", value=str(existing.get("remarks") or ""), height=80)
        new_standard_attachment = None
        if not existing:
            st.markdown("**Controlled Standard / Specification Attachment**")
            new_standard_attachment = st.file_uploader(
                "Upload Standard / Specification File",
                type=ALLOWED_ATTACHMENT_TYPES,
                key=f"new_customer_standard_attachment_{scope}",
                help="Optional at initial save. The file will be stored against the new Standard record and can later be downloaded, replaced or password-deleted.",
            )
        save = st.form_submit_button("Save Customer Standard / Specification", type="primary", disabled=not writable, width="stretch")

    if save:
        try:
            if not standard_code.strip() or not standard_name.strip() or not revision_number.strip() or not process_id:
                raise ValueError("Standard Code, Standard Name, Revision Number and Related Process are mandatory.")
            raw = {
                "standard_code": standard_code.strip(),
                "standard_name": standard_name.strip(),
                "customer_id": customer_id or None,
                "process_id": process_id,
                "author_name": author_name.strip() or None,
                "revision_number": revision_number.strip(),
                "revision_date": revision_date,
                "status": status,
                "remarks": remarks.strip() or None,
            }
            saved, action = service.save(definition, raw, record_id=str(existing["id"]) if existing else None)
            saved_id = str(saved["id"])
            if not existing and new_standard_attachment is not None:
                AttachmentService(repo).upload(
                    entity_type="CUSTOMER_STANDARD",
                    entity_id=saved_id,
                    folder="customer_standards",
                    slot=STANDARD_SLOT,
                    file=new_standard_attachment,
                )
            st.session_state.pop(auto_key, None)
            st.session_state["edit_customer_standard_id"] = saved_id
            message = f"Customer Standard / Specification {action} successfully."
            if not existing and new_standard_attachment is not None:
                message += " Attachment uploaded successfully."
            save_success_popup(message, queue_for_rerun=True)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    if not existing:
        st.info("You may attach the controlled Standard file during the first save above. After saving, the Attachment Manager below supports download, replacement and password-protected deletion.")
        return

    standard_id = str(existing["id"])
    render_attachment_manager(
        repo=repo,
        entity_type="CUSTOMER_STANDARD",
        entity_id=standard_id,
        folder="customer_standards",
        slots=(STANDARD_SLOT,),
        key_prefix=f"customer_standard_{standard_id}",
        can_add_or_replace=perms["can_edit"],
        can_delete=perms["can_archive"],
        title="CONTROLLED STANDARD / SPECIFICATION ATTACHMENT",
    )

    if password_delete_panel(
        repo=repo,
        table="customer_standards",
        rows=[existing],
        labeler=lambda row: _label(row, customer_map, process_map),
        key=f"delete_customer_standard_{standard_id}",
        can_delete=perms["can_archive"],
        title="Delete Customer Standard / Specification",
        help_text="Permanent deletion requires your current QCMS password. A Standard linked to a Part Master must be unlinked first.",
    ):
        st.rerun()


def render_records() -> None:
    subpage_navigation(
        ("masters", "Back to Masters", ":material/arrow_back:"),
        ("standards-entry", "New / Edit Standard", ":material/edit_note:"),
    )
    page_header(
        "Customer Standards & Specification Bank · Records",
        "Search, download controlled attachments, print or open a customer/process-linked specification.",
        "Records",
    )
    service = MasterService()
    repo = service.repo
    definition = MASTER_BY_KEY["customer_standards"]
    perms = current_permissions("REFERENCE_MASTERS")
    _, _, customer_map, process_map = _maps(service)
    c1, c2 = st.columns([3, 1], gap="small")
    search = c1.text_input("Search Standard Code, Name, Author or Revision")
    status = c2.selectbox("Status", ["All", "Active", "Inactive", "Superseded"])
    status_map = {"All": "All", "Active": "Active", "Inactive": "Inactive", "Superseded": "All"}
    rows = service.list_records(definition, search=search, status=status_map[status])
    if status == "Superseded":
        rows = [r for r in rows if str(r.get("status")) == "SUPERSEDED"]

    if rows:
        labels = {str(r["id"]): _label(r, customer_map, process_map) for r in rows}
        selected_id = st.selectbox("Select Customer Standard / Specification", list(labels), format_func=lambda value: labels[value])
        selected = next(r for r in rows if str(r["id"]) == selected_id)
        st.session_state["edit_customer_standard_id"] = selected_id
        attachment, data = _attachment_summary(service, selected_id)
        c = st.columns(4, gap="small")
        with c[0]:
            st.page_link(st.session_state["_qsms_pages"]["standards-entry"], label="Open Selected Standard", icon=":material/edit:", width="stretch")
        with c[1]:
            if attachment and data is not None:
                st.download_button(
                    "Download Standard Attachment",
                    data=data,
                    file_name=str(attachment.get("file_name") or f"{selected.get('standard_code')}.pdf"),
                    mime=str(attachment.get("mime_type") or "application/octet-stream"),
                    width="stretch",
                )
            else:
                st.button("No Attachment Available", disabled=True, width="stretch")
        with c[2]:
            pdf = controlled_record_pdf_bytes(
                "CUSTOMER STANDARD / SPECIFICATION RECORD",
                {
                    "Standard Code": selected.get("standard_code"),
                    "Standard / Specification": selected.get("standard_name"),
                    "Customer": customer_map.get(str(selected.get("customer_id")), "General / Not customer-specific"),
                    "Related Process": process_map.get(str(selected.get("process_id")), ""),
                    "Author / Issuing Authority": selected.get("author_name"),
                    "Revision Number": selected.get("revision_number"),
                    "Revision Date": selected.get("revision_date"),
                    "Status": selected.get("status"),
                    "Attachment": (attachment or {}).get("file_name") or "Not attached",
                    "Remarks": selected.get("remarks"),
                },
                record_number=str(selected.get("standard_code") or ""),
            )
            st.download_button("Download Record PDF", pdf, file_name=f"Customer_Standard_{selected.get('standard_code')}_Rev_{selected.get('revision_number')}.pdf", mime="application/pdf", width="stretch")
        with c[3]:
            if password_delete_panel(
                repo=repo,
                table="customer_standards",
                rows=[selected],
                labeler=lambda row: _label(row, customer_map, process_map),
                key=f"delete_customer_standard_record_{selected_id}",
                can_delete=perms["can_archive"],
                title="Delete Selected Standard",
                help_text="Permanent deletion requires your current QCMS password. Unlink the Standard from Part Master records first.",
            ):
                st.rerun()
    else:
        st.info("No Customer Standards / Specifications match the selected filters.")

    section_bar("CUSTOMER STANDARDS & SPECIFICATION REGISTER")
    frame = pd.DataFrame([
        {
            "Standard Code": r.get("standard_code"),
            "Standard / Specification": r.get("standard_name"),
            "Customer": customer_map.get(str(r.get("customer_id")), "General"),
            "Related Process": process_map.get(str(r.get("process_id")), ""),
            "Author": r.get("author_name"),
            "Revision": r.get("revision_number"),
            "Revision Date": r.get("revision_date"),
            "Status": r.get("status"),
        }
        for r in rows
    ])
    portal_table(frame, hide_index=True, width="stretch", height=620)
