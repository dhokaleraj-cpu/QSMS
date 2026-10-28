"""QCMS R38 · Engineering / Process Change Notes (ECN / PCN, format FSI/806/F05) and the Part Master section
"Part Processes & Drawings".

* ``render()``                       route ``ecn-register`` (Engineering): register, filters, open / edit, approve /
                                     disapprove, attachments, print PDF + Excel, e-mail
* ``render_part_processes(...)``     Part Master section: process list (mandatory, in-house / OSP), optional process
                                     drawings / specifications with revision records, "Raise PCN"
* ``queue_pending_ecn`` / ``render_pending_ecn``  replacing a current drawing / spec revision opens a pre-filled ECN; the
                                     new revision is released only together with its ECN
* ``render_ecn_register_panel(...)`` register panel (all Parts or one Part)
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.attachments import AttachmentService, AttachmentSlot, render_attachment_manager
from core.db_errors import db_message
from core.delete_service import password_delete_panel
from core.ecn_service import (
    ATTACHMENT_ENTITY, CHANGE_TYPES, CONTACT_FIELDS, CUSTOMER_APPROVALS, DEPARTMENT, DOCUMENT_SCOPES, DRAWING_CHANGE_MODES,
    FORMAT_NO, FORMAT_REV_NO, PRIORITIES, SUPPORTING_DOCUMENTS, TRANSITION_LABELS, ECNService, allowed_targets, change_title,
    default_representative, ecn_email_text, ecn_notifier, employee_name, normalize_status, release_with_ecn, revision_defaults,
    status_label,
)
from core.part_process_service import (
    PROCESS_DOCUMENT_TYPES, PROCESS_SOURCE_TYPES, PartProcessService, StoredUpload, part_process_payloads,
    process_change_defaults, revision_status, route_text, save_part_drawing_revision, save_process_document_revision,
)
from core.repository import Repository
from core.selection_labels import part_label
from core.ui import kpi_grid, page_header, portal_table, save_success_popup, section_bar, subpage_navigation

PENDING_ECN_KEY = "_r38_pending_ecn_{part_id}"
PCN_BEFORE_KEY = "_r38_pcn_before_{part_id}"
PCN_OPEN_KEY = "_r38_pcn_open_{part_id}"
DOC_TYPES = dict(PROCESS_DOCUMENT_TYPES)


def _profile() -> dict:
    try:
        from core.auth import current_profile
        return dict(current_profile() or {})
    except Exception:
        return dict(st.session_state.get("profile") or {})


def _my_employee_id(employees: list[dict]) -> str | None:
    ids = default_representative(employees, _profile())
    return ids[0] if ids else None


def _employee_options(employees: list[dict]) -> dict[str, str]:
    return {str(r["id"]): employee_name(r) + (f" · {r.get('designation')}" if r.get("designation") else "") for r in employees if r.get("id")}


def _profile_names(employees: list[dict]) -> dict[str, str]:
    return {str(r.get("profile_id")): employee_name(r) for r in employees if r.get("profile_id")}


def _date_or_none(value: Any) -> date | None:
    text = str(value or "")[:10]
    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return None


def _index(options: list, value: Any, fallback: int = 0) -> int:
    return options.index(value) if value in options else fallback


# ---------------------------------------------------------------------------------------------------------------- form
def ecn_form(employees: list[dict], *, key: str, defaults: dict, actions: tuple[tuple[str, str], ...], disabled: bool = False,
             header_locked: bool = False) -> tuple[dict, str | None]:
    """ECN / PCN form in the FSI/806/F05 field order. Returns (form values, clicked action)."""
    emp = _employee_options(employees)
    emp_ids = list(emp)
    d = dict(defaults or {})
    if not d.get("fsi_representative_ids") and not d.get("ecn_number"):
        d["fsi_representative_ids"] = default_representative(employees, _profile())
    locked = disabled or header_locked

    with st.form(f"ecn_form_{key}"):
        st.markdown(f"**{change_title(d.get('change_type'))} · {FORMAT_NO} Rev {FORMAT_REV_NO}**"
                    + (f" · {d.get('ecn_number')} · {status_label(d.get('status'))}" if d.get("ecn_number") else ""))
        c = st.columns(5, gap="small")
        type_options = list(CHANGE_TYPES)
        change_type = c[0].selectbox("Type", type_options, index=_index(type_options, str(d.get("change_type") or "ECN").upper()),
                                     format_func=lambda v: f"{v} · {CHANGE_TYPES[v].title()}", disabled=locked or bool(d.get("ecn_number")), key=f"ecn_type_{key}")
        ecn_date = c[1].date_input("Date", value=_date_or_none(d.get("ecn_date")) or date.today(), format="DD-MM-YYYY", disabled=locked, key=f"ecn_date_{key}")
        priority = c[2].selectbox("Requested Priority & Response", list(PRIORITIES), index=_index(list(PRIORITIES), d.get("requested_priority")), disabled=locked, key=f"ecn_priority_{key}")
        response_by = c[3].date_input("Request Response By", value=_date_or_none(d.get("response_by")), format="DD-MM-YYYY", disabled=locked, key=f"ecn_response_{key}")
        response_party = c[4].text_input("Response From", value=str(d.get("response_by_party") or "FSI"), disabled=locked, key=f"ecn_response_party_{key}")
        reps = st.multiselect("FSI Representative(s)", emp_ids, default=[v for v in (d.get("fsi_representative_ids") or []) if v in emp],
                              format_func=lambda v: emp.get(v, v), disabled=locked, key=f"ecn_reps_{key}")
        reps_text = st.text_input("Other FSI Representative(s) (optional text)", value=str(d.get("fsi_representatives_text") or ""), disabled=locked, key=f"ecn_reps_text_{key}")
        st.markdown("**Identification**")
        contacts: dict[str, dict[str, str]] = {}
        cols = st.columns(3, gap="small")
        for col, (field, title) in zip(cols, (("to_contact", "To"), ("cc_contact", "CC"), ("from_contact", "From"))):
            existing_contact = dict(d.get(field) or {})
            with col:
                st.caption(title)
                contacts[field] = {
                    name: st.text_input(f"{title} · {label}", value=str(existing_contact.get(name) or ""), disabled=locked, key=f"ecn_{field}_{name}_{key}")
                    for name, label in CONTACT_FIELDS
                }
        st.markdown("**Drawing criteria** · fill in the information completely to expedite the process")
        c = st.columns(5, gap="small")
        drawing_number = c[0].text_input("Drawing No.", value=str(d.get("drawing_number") or ""), disabled=locked, key=f"ecn_drawing_{key}")
        part_number = c[1].text_input("Part No.", value=str(d.get("part_number") or ""), disabled=locked, key=f"ecn_part_no_{key}")
        part_name = c[2].text_input("Part Name", value=str(d.get("part_name") or ""), disabled=locked, key=f"ecn_part_name_{key}")
        previous_revision = c[3].text_input("Revision From", value=str(d.get("previous_revision") or ""), disabled=locked, key=f"ecn_rev_from_{key}")
        new_revision = c[4].text_input("Revision To", value=str(d.get("new_revision") or ""), disabled=locked, key=f"ecn_rev_to_{key}")
        previous_description = st.text_area("Previous Description", value=str(d.get("previous_description") or ""), height=110, disabled=locked, key=f"ecn_prev_{key}")
        revision_requested = st.text_area("Revision Requested (new description)", value=str(d.get("revision_requested") or ""), height=130, disabled=locked, key=f"ecn_req_{key}")
        is_pcn = str(change_type).upper() == "PCN"
        st.markdown("**Supporting documents required** (Purchase Orders, PPAP, PFD, CP, PFMEA, inventory)" if is_pcn
                    else "**Supporting documents attached** (redline drawings, datasheets, etc.)")
        docs_now = dict(d.get("supporting_documents") or {})
        cols = st.columns(4, gap="small")
        supporting = {doc_key: cols[i % 4].checkbox(label, value=bool(docs_now.get(doc_key)), disabled=locked, key=f"ecn_doc_{doc_key}_{key}")
                      for i, (doc_key, label) in enumerate(SUPPORTING_DOCUMENTS)}
        c = st.columns(5, gap="small")
        po_affected = c[0].checkbox("Purchase Orders Affected", value=bool(d.get("po_affected")), disabled=locked, key=f"ecn_po_{key}")
        inventory_affected = c[1].checkbox("Current Inventory Affected", value=bool(d.get("inventory_affected")), disabled=locked, key=f"ecn_inv_{key}")
        inventory_qty = c[2].number_input("Inventory Qty.", min_value=0.0, value=float(d.get("inventory_qty") or 0), step=1.0, disabled=locked, key=f"ecn_inv_qty_{key}")
        demands_affected = c[3].checkbox("Current Demands Affected", value=bool(d.get("demands_affected")), disabled=locked, key=f"ecn_dem_{key}")
        demands_qty = c[4].number_input("Demands Qty.", min_value=0.0, value=float(d.get("demands_qty") or 0), step=1.0, disabled=locked, key=f"ecn_dem_qty_{key}")
        st.markdown("**FSI use only · approvals**")
        c = st.columns(4, gap="small")
        modes = list(DRAWING_CHANGE_MODES)
        drawing_change_mode = c[0].selectbox("Drawing change to occur", modes, index=_index(modes, d.get("drawing_change_mode")),
                                             format_func=lambda v: DRAWING_CHANGE_MODES[v], disabled=disabled, key=f"ecn_mode_{key}")
        customer_name = c[1].text_input("Customer (for approval)", value=str(d.get("customer_name_text") or ""), disabled=disabled, key=f"ecn_customer_{key}")
        approvals = list(CUSTOMER_APPROVALS)
        customer_approval = c[2].selectbox("Customer Approval", approvals, index=_index(approvals, d.get("customer_approval")),
                                           format_func=lambda v: v.replace("_", " ").title(), disabled=disabled, key=f"ecn_cust_appr_{key}")
        customer_approver = c[3].text_input("Customer Approval Signatory", value=str(d.get("customer_approver_name") or ""), disabled=disabled, key=f"ecn_cust_sign_{key}")
        c = st.columns(5, gap="small")
        opt = [""] + emp_ids
        fsi_approver = c[0].selectbox("FSI Approval Signatory", opt, index=_index(opt, str(d.get("fsi_approver_employee_id") or "")),
                                      format_func=lambda v: emp.get(v, "—"), disabled=disabled, key=f"ecn_fsi_sign_{key}")
        fsi_approval_date = c[1].date_input("FSI Approval Date", value=_date_or_none(d.get("fsi_approval_date")), format="DD-MM-YYYY", disabled=disabled, key=f"ecn_fsi_date_{key}")
        customer_approval_date = c[2].date_input("Customer Approval Date", value=_date_or_none(d.get("customer_approval_date")), format="DD-MM-YYYY", disabled=disabled, key=f"ecn_cust_date_{key}")
        completed_by = c[3].selectbox("Completed By", opt, index=_index(opt, str(d.get("completed_by_employee_id") or "")),
                                      format_func=lambda v: emp.get(v, "—"), disabled=disabled, key=f"ecn_done_by_{key}")
        completed_date = c[4].date_input("Completed Date", value=_date_or_none(d.get("completed_date")), format="DD-MM-YYYY", disabled=disabled, key=f"ecn_done_date_{key}")
        comments = st.text_area("Comments", value=str(d.get("comments") or ""), height=70, disabled=disabled, key=f"ecn_comments_{key}")
        benefit = st.text_area("Benefit to this Change", value=str(d.get("benefit_of_change") or ""), height=60, disabled=disabled, key=f"ecn_benefit_{key}")
        email_ids = st.multiselect("E-mail the ECN print to (employees)", emp_ids, default=[v for v in (d.get("email_employee_ids") or []) if v in emp],
                                   format_func=lambda v: emp.get(v, v), disabled=disabled, key=f"ecn_mail_{key}")
        clicked: str | None = None
        bcols = st.columns(len(actions), gap="small")
        for col, (action, label) in zip(bcols, actions):
            if col.form_submit_button(label, type="primary" if action != "CANCEL" else "secondary", disabled=disabled and action != "CANCEL", width="stretch"):
                clicked = action
    form = {
        **{k: d.get(k) for k in ("part_id", "process_route_id", "document_scope", "previous_attachment_id", "plant_code")},
        "change_type": change_type, "ecn_date": ecn_date, "requested_priority": priority, "response_by": response_by,
        "response_by_party": response_party, "fsi_representative_ids": reps, "fsi_representatives_text": reps_text, **contacts,
        "drawing_number": drawing_number, "part_number": part_number, "part_name": part_name, "previous_revision": previous_revision,
        "new_revision": new_revision, "previous_description": previous_description, "revision_requested": revision_requested,
        "supporting_documents": supporting, "po_affected": po_affected, "inventory_affected": inventory_affected,
        "inventory_qty": inventory_qty if inventory_affected else None, "demands_affected": demands_affected,
        "demands_qty": demands_qty if demands_affected else None, "drawing_change_mode": drawing_change_mode,
        "customer_name_text": customer_name, "customer_approval": customer_approval, "customer_approver_name": customer_approver,
        "fsi_approver_employee_id": fsi_approver or None, "fsi_approval_date": fsi_approval_date, "customer_approval_date": customer_approval_date,
        "completed_by_employee_id": completed_by or None, "completed_date": completed_date, "comments": comments,
        "benefit_of_change": benefit, "email_employee_ids": email_ids,
    }
    if d.get("fsi_decision"):
        form["fsi_decision"] = d.get("fsi_decision")
    return form, clicked


def email_ecn(repo: Any, ecn: dict, employee_ids: list[str], employees: list[dict], *, subject: str | None = None,
              body: str | None = None) -> tuple[int, str]:
    """Queue + send the ECN print to selected employees (internal recipients only; subject starts with Engineering)."""
    by_id = {str(r.get("id")): r for r in employees}
    emails: list[str] = []
    for emp_id in employee_ids or []:
        mail = str((by_id.get(str(emp_id)) or {}).get("email") or "").strip()
        if "@" in mail and mail.casefold() not in {m.casefold() for m in emails}:
            emails.append(mail)
    if not emails:
        return 0, "The selected employees have no e-mail address in Employee Master."
    default_subject, default_body = ecn_email_text(ecn)
    notifier = ecn_notifier(repo)
    row = notifier.enqueue("ECN_" + ("PCN" if str(ecn.get("change_type") or "").upper() == "PCN" else "ECN"),
                           subject=subject or default_subject, body_text=body or default_body,
                           related_table="part_ecns", related_id=str(ecn.get("id")), recipient_email=emails[0],
                           cc_emails=emails[1:], context={"department": DEPARTMENT}, include_supplier=False,
                           include_generated_pdf=True, include_record_attachments=False)
    if not row:
        return 0, "The e-mail could not be queued."
    result = notifier.dispatch([row])
    ECNService(repo).mark_emailed(ecn.get("id"))
    if result.get("error"):
        return len(emails), f"E-mail queued; delivery returned: {result.get('error')}. It is retried from My Sent Emails / outbox."
    return len(emails), ""


def _notify_created(repo: Any, ecn: dict) -> str:
    """R38: every new ECN / PCN is e-mailed to Quality + NPD (event ECN_CREATED); failures never block the save."""
    try:
        from core.ecn_service import notify_ecn_created
        sent, message = notify_ecn_created(repo, ecn)
    except Exception as exc:
        return f" Quality / NPD notification failed: {db_message(exc)}"
    if sent and not message:
        return f" Quality / NPD notified ({sent})."
    return f" {message}" if message else ""


def _mail_after_save(repo: Any, ecn: dict, form: dict, employees: list[dict]) -> str:
    """Called right after an ECN / PCN is created: ECN_CREATED notification + the optional e-mail to selected employees."""
    created_note = _notify_created(repo, ecn)
    if not form.get("email_employee_ids"):
        return created_note
    return created_note + _mail_selected(repo, ecn, form, employees)


def _mail_selected(repo: Any, ecn: dict, form: dict, employees: list[dict]) -> str:
    try:
        sent, message = email_ecn(repo, ecn, list(form.get("email_employee_ids") or []), employees)
    except Exception as exc:
        return f" E-mail failed: {db_message(exc)}"
    return f" E-mailed to {sent} employee(s)." if sent and not message else (f" {message}" if message else "")


# ---------------------------------------------------------------------------------------------------------------- replace
def queue_pending_ecn(part_id: str, data: dict, file: Any) -> None:
    """Keep the replacement file in the session until its ECN is completed (nothing is released yet)."""
    content = file.getvalue() if file is not None else b""
    if not content:
        raise ValueError("The selected file is empty.")
    st.session_state[PENDING_ECN_KEY.format(part_id=part_id)] = {
        **data, "file_name": str(file.name), "file_type": getattr(file, "type", None), "file_bytes": content,
    }


def release_pending(repo: Any, pending: dict) -> dict:
    upload = StoredUpload(pending["file_name"], pending["file_bytes"], pending.get("file_type"))
    rev_date = date.fromisoformat(str(pending["revision_date"])[:10])
    if pending.get("kind") == "PROCESS_DOC":
        return save_process_document_revision(repo, pending["route"], pending["document_type"], pending["document_number"],
                                              pending.get("title") or "", pending["revision"], rev_date, upload)
    return save_part_drawing_revision(repo, pending["part_id"], pending["document_type"], pending["document_number"],
                                      pending["revision"], rev_date, upload)


def render_pending_ecn(repo: Any, part: dict, kind: str, perms: dict) -> None:
    """Mandatory ECN for a drawing / document REPLACEMENT. The new revision is released only with its ECN."""
    part_id = str(part.get("id") or "")
    state_key = PENDING_ECN_KEY.format(part_id=part_id)
    pending = st.session_state.get(state_key)
    if not pending or pending.get("kind") != kind:
        return
    scope_label = DOCUMENT_SCOPES.get(str(pending.get("document_type")), str(pending.get("document_type")))
    current = dict(pending.get("current") or {})
    with st.container(border=True, key=f"pending_ecn_{kind}_{part_id}"):
        section_bar("ECN REQUIRED FOR DRAWING / DOCUMENT REPLACEMENT")
        st.warning(
            f"You are replacing {scope_label} {pending.get('document_number')} Rev {current.get('revision') or '-'} with "
            f"Rev {pending.get('revision')} ({pending.get('file_name')}). Complete the Engineering Change Note: the new revision "
            "is released together with the ECN (Save as DRAFT or Submit for approval). Nothing is saved if you cancel."
        )
        defaults = revision_defaults(
            part, document_scope=str(pending.get("document_type")), drawing_number=pending.get("document_number"), current=current,
            new_revision=pending.get("revision"), new_revision_date=pending.get("revision_date"), process_text=str(pending.get("process_text") or ""),
            new_title=str(pending.get("title") or ""),
        )
        defaults["change_type"] = "ECN"  # a drawing / spec replacement is an Engineering Change Note
        if pending.get("route"):
            defaults["process_route_id"] = str((pending.get("route") or {}).get("id") or "") or None
        service = ECNService(repo)
        employees = service.employees()
        form, action = ecn_form(
            employees, key=f"pending_{kind}_{part_id}", defaults=defaults,
            actions=(("DRAFT", "Save ECN as DRAFT & Release Revision"), ("PENDING_APPROVAL", "Submit ECN for Approval & Release Revision"),
                     ("CANCEL", "Cancel Replacement")),
            disabled=not (perms.get("can_edit") or perms.get("can_create")),
        )
        if action == "CANCEL":
            st.session_state.pop(state_key, None)
            st.rerun()
        if action in {"DRAFT", "PENDING_APPROVAL"}:
            try:
                ecn, _released = release_with_ecn(service, form, lambda: release_pending(repo, pending), status=action)
                st.session_state.pop(state_key, None)
                note = _mail_after_save(repo, ecn, form, employees)
                save_success_popup(
                    f"{scope_label} {pending.get('document_number')} Rev {pending.get('revision')} released with "
                    f"{ecn.get('ecn_number')} ({status_label(ecn.get('status'))}). Previous revision is now OBSOLETE.{note}",
                    queue_for_rerun=True,
                )
                st.rerun()
            except Exception as exc:
                st.error(db_message(exc))


# ---------------------------------------------------------------------------------------------------------------- PCN
def _render_pcn_panel(repo: Any, part: dict, routes: list[dict], processes: dict[str, dict], perms: dict) -> None:
    """Optional PCN for a process list change (Raise PCN) - pre-filled with the previous and the new process list."""
    part_id = str(part.get("id") or "")
    writable = bool(perms.get("can_edit") or perms.get("can_create"))
    before = st.session_state.get(PCN_BEFORE_KEY.format(part_id=part_id))
    after = route_text(routes, processes)
    open_key = PCN_OPEN_KEY.format(part_id=part_id)
    if before is not None and before != after and not st.session_state.get(open_key):
        st.info("The process list of this Part was changed. Raise a Process Change Note (PCN) for the customer / internal approval if required.")
    c1, c2 = st.columns([1, 1], gap="small")
    if c1.button("Raise PCN", icon=":material/published_with_changes:", width="stretch", key=f"raise_pcn_{part_id}", disabled=not writable):
        st.session_state[open_key] = True
    if before is not None and c2.button("Dismiss process change", width="stretch", key=f"dismiss_pcn_{part_id}"):
        st.session_state.pop(PCN_BEFORE_KEY.format(part_id=part_id), None)
        st.session_state.pop(open_key, None)
        st.rerun()
    if not st.session_state.get(open_key):
        return
    service = ECNService(repo)
    employees = service.employees()
    defaults = process_change_defaults(part, before if before is not None else after, after)
    with st.container(border=True, key=f"pcn_panel_{part_id}"):
        section_bar("PROCESS CHANGE NOTE (PCN)")
        form, action = ecn_form(employees, key=f"pcn_{part_id}", defaults=defaults,
                                actions=(("DRAFT", "Save PCN as DRAFT"), ("PENDING_APPROVAL", "Submit PCN for Approval"), ("CANCEL", "Close")),
                                disabled=not writable)
    if action == "CANCEL":
        st.session_state.pop(open_key, None)
        st.rerun()
    if action in {"DRAFT", "PENDING_APPROVAL"}:
        try:
            form["change_type"] = "PCN"
            ecn = service.create(form, status=action)
            note = _mail_after_save(repo, ecn, form, employees)
            st.session_state.pop(open_key, None)
            st.session_state.pop(PCN_BEFORE_KEY.format(part_id=part_id), None)
            save_success_popup(f"{ecn.get('ecn_number')} saved as {status_label(ecn.get('status'))}.{note}", queue_for_rerun=True)
            st.rerun()
        except Exception as exc:
            st.error(db_message(exc))


# ---------------------------------------------------------------------------------------------------------------- Part Master section
def render_part_processes(repo: Any, existing: dict, writable: bool, perms: dict) -> None:
    """Part Master · Part Processes & Drawings: ordered process list with optional controlled drawings / specs per process."""
    part_id = str(existing.get("id") or "")
    service = PartProcessService(repo)
    can_delete = bool(perms.get("can_archive"))
    processes = service.processes()
    process_by_id = {str(r["id"]): r for r in processes}
    process_labels = {str(r["id"]): f"{r.get('process_code') or '-'} · {r.get('process_name') or '-'}" for r in processes}
    label_to_process = {label: pid for pid, label in process_labels.items()}
    routes_all = service.routes(part_id)
    routes = [r for r in routes_all if str(r.get("status") or "ACTIVE").upper() == "ACTIVE"]

    def _route_name(route: dict) -> str:
        return process_labels.get(str(route.get("process_id")), str(route.get("process_name_snapshot") or "-"))

    section_bar("PART PROCESSES", "Ordered list of processes for this Part.")
    st.caption(
        "Op No. orders the processes. Mandatory = the process must be completed for this Part (other modules read it through "
        "core.part_process_service.mandatory_processes). Source = In-house or OSP (note the OSP vendor in Remarks). Drawings and "
        "specifications per process are optional. Set Status INACTIVE to retire a process; a process list change can raise a PCN."
    )
    if not processes:
        st.warning("Create active Processes in Process Master first.")
    mandatory = [r for r in routes if r.get("is_mandatory", True)]
    st.caption(f"{len(routes)} active process(es) · {len(mandatory)} mandatory · {len(routes) - len(mandatory)} optional")
    if not routes_all:
        flows = repo.select("npd_process_flows", eq={"part_id": part_id}, order_by="effective_date", desc=True, limit=20)
        if flows:
            flow = flows[0]
            if st.button(f"Copy processes from NPD Process Flow Rev {flow.get('revision') or '-'}", icon=":material/content_copy:",
                         disabled=not writable, width="stretch", key=f"copy_npd_routes_{part_id}"):
                try:
                    count = service.copy_from_npd(part_id, flow["id"])
                    save_success_popup(f"{count} process(es) copied from the NPD Process Flow.", queue_for_rerun=True)
                    st.rerun()
                except Exception as exc:
                    st.error(db_message(exc))
    if password_delete_panel(
        repo=repo, table="part_process_routes", rows=routes_all,
        labeler=lambda r: f"Op {r.get('operation_no')} · {_route_name(r)}",
        key=f"delete_part_process_{part_id}", can_delete=can_delete, title="Delete Part Process",
        help_text="Permanent deletion requires the current QCMS password. Process drawings / specifications stay in history.",
    ):
        st.rerun()
    route_df = pd.DataFrame([{
        "_id": str(r.get("id")),
        "Op No.": int(r.get("operation_no") or 0),
        "Process": _route_name(r),
        "Mandatory": bool(r.get("is_mandatory", True)),
        "Source": str(r.get("source_type") or "IN_HOUSE"),
        "Remarks": r.get("remarks") or "",
        "Status": str(r.get("status") or "ACTIVE"),
    } for r in routes_all], columns=["_id", "Op No.", "Process", "Mandatory", "Source", "Remarks", "Status"])
    with st.form(f"part_process_routes_form_{part_id}"):
        route_edit = st.data_editor(
            route_df, num_rows="dynamic", hide_index=True, width="stretch", height=min(430, max(210, 90 + max(len(routes_all), 1) * 36)),
            disabled=not writable, key=f"part_process_routes_grid_{part_id}",
            column_config={
                "_id": None,
                "Op No.": st.column_config.NumberColumn(min_value=1, step=1, required=True, help="Operation / sequence number, e.g. 10, 20, 30."),
                "Process": st.column_config.SelectboxColumn(options=list(label_to_process), required=True, width="large"),
                "Mandatory": st.column_config.CheckboxColumn(default=True, help="Ticked = Yes, the process is mandatory for this Part."),
                "Source": st.column_config.SelectboxColumn(options=list(PROCESS_SOURCE_TYPES), required=True, default="IN_HOUSE",
                                                           help="IN_HOUSE or OSP (outside processing)."),
                "Remarks": st.column_config.TextColumn(width="large", help="Remarks, e.g. OSP vendor."),
                "Status": st.column_config.SelectboxColumn(options=["ACTIVE", "INACTIVE"], default="ACTIVE"),
            },
        )
        save_routes = st.form_submit_button("Save Part Processes", type="primary", disabled=not writable, width="stretch")
    if save_routes:
        try:
            before = route_text(routes, process_by_id)
            payloads = part_process_payloads(route_edit, label_to_process, process_by_id)
            count = service.save_routes(part_id, payloads)
            if routes:
                st.session_state[PCN_BEFORE_KEY.format(part_id=part_id)] = before
            save_success_popup(f"{count} Part process(es) saved." + (" Raise a PCN below if the process change needs approval." if routes else ""),
                               queue_for_rerun=True)
            st.rerun()
        except Exception as exc:
            st.error(db_message(exc))
    if routes:
        _render_pcn_panel(repo, existing, routes, process_by_id, perms)

    section_bar("PROCESS DRAWINGS & SPECIFICATIONS", "Optional. Revision-controlled per process.")
    if not routes:
        st.info("Save at least one ACTIVE Part process to attach process drawings / specifications.")
        return
    route_labels = {
        str(r["id"]): f"Op {r.get('operation_no')} · {_route_name(r)} · {'Mandatory' if r.get('is_mandatory', True) else 'Optional'} · {r.get('source_type') or 'IN_HOUSE'}"
        for r in routes
    }
    route_id = st.selectbox("Process", list(route_labels), format_func=lambda v: route_labels[v], key=f"process_doc_route_{part_id}")
    route = next(r for r in routes if str(r.get("id")) == route_id)
    docs = service.documents(route_id)
    employees = ECNService(repo).employees()
    profiles = _profile_names(employees)
    ecn_by_attachment = {str(e.get("document_attachment_id")): e for e in repo.select("part_ecns", eq={"part_id": part_id}, limit=2000) if e.get("document_attachment_id")}
    if docs:
        portal_table(pd.DataFrame([{
            "Type": DOC_TYPES.get(str(d.get("document_type")), str(d.get("document_type"))),
            "Drawing / Spec No.": d.get("drawing_number") or "",
            "Title / Description": d.get("document_title") or "",
            "Rev No.": d.get("revision") or "",
            "Rev Date": d.get("revision_date") or "",
            "Status": revision_status(d),
            "File": d.get("file_name") or "",
            "Uploaded By": profiles.get(str(d.get("created_by") or ""), ""),
            "Uploaded At": str(d.get("created_at") or "")[:16],
            "ECN": (ecn_by_attachment.get(str(d.get("id"))) or {}).get("ecn_number") or "",
        } for d in docs]), hide_index=True, width="stretch", height=min(360, 72 + len(docs) * 34))
        doc_labels = {str(d["id"]): f"{DOC_TYPES.get(str(d.get('document_type')), '')} · {d.get('drawing_number')} · Rev {d.get('revision')} · {revision_status(d)}" for d in docs}
        selected_doc_id = st.selectbox("Select revision to view / download (previous revisions are OBSOLETE but viewable)", list(doc_labels),
                                       format_func=lambda v: doc_labels[v], key=f"process_doc_pick_{route_id}")
        selected_doc = next(d for d in docs if str(d.get("id")) == selected_doc_id)
        try:
            st.download_button("Download Selected Process Document Revision", data=AttachmentService(repo).download(selected_doc),
                               file_name=str(selected_doc.get("file_name") or "process_document"), mime=str(selected_doc.get("mime_type") or "application/octet-stream"),
                               key=f"process_doc_download_{selected_doc_id}", width="stretch")
        except Exception as exc:
            st.caption(f"File unavailable: {exc}")
    else:
        st.caption("No process drawings / specifications released for this process yet (optional).")

    with st.container(border=True, key=f"process_doc_release_{route_id}"):
        st.markdown("**Release a process drawing / specification revision**")
        c = st.columns(3, gap="small")
        doc_type = c[0].selectbox("Document Type", [k for k, _ in PROCESS_DOCUMENT_TYPES], format_func=lambda v: DOC_TYPES[v], key=f"process_doc_type_{route_id}", disabled=not writable)
        known_numbers = sorted({str(d.get("drawing_number") or "") for d in docs if str(d.get("document_type")) == doc_type and d.get("drawing_number")})
        doc_no = c[1].selectbox("Drawing / Spec No.", known_numbers or [""], accept_new_options=True, key=f"process_doc_no_{route_id}_{doc_type}", disabled=not writable,
                                help="Select an existing number to release its next revision (ECN required) or type a new number.")
        title = c[2].text_input("Title / Description", key=f"process_doc_title_{route_id}", disabled=not writable)
        c = st.columns(3, gap="small")
        revision_no = c[0].text_input("Revision Number", key=f"process_doc_rev_{route_id}", disabled=not writable)
        revision_dt = c[1].date_input("Revision Date", value=date.today(), format="DD-MM-YYYY", key=f"process_doc_rev_date_{route_id}", disabled=not writable)
        file = c[2].file_uploader("File", type=["pdf", "png", "jpg", "jpeg", "dwg", "dxf", "xlsx", "docx"], key=f"process_doc_file_{route_id}", disabled=not writable)
        if st.button("Release Process Document Revision", type="primary", width="stretch", key=f"process_doc_release_btn_{route_id}",
                     disabled=not writable or file is None or not str(doc_no or "").strip() or not revision_no.strip()):
            try:
                doc_no_s = str(doc_no or "").strip()
                if any(str(d.get("document_type")) == doc_type and str(d.get("drawing_number") or "").casefold() == doc_no_s.casefold()
                       and str(d.get("revision") or "").casefold() == revision_no.strip().casefold() for d in docs):
                    raise ValueError("This Drawing / Specification Number and Revision Number already exist in revision history.")
                current = next((d for d in docs if str(d.get("document_type")) == doc_type and str(d.get("status") or "").upper() == "ACTIVE"
                                and str(d.get("drawing_number") or "").casefold() == doc_no_s.casefold()), None)
                if current:
                    # Replacing the CURRENT revision needs an ECN - the form opens below, nothing is released yet.
                    queue_pending_ecn(part_id, {
                        "kind": "PROCESS_DOC", "part_id": part_id, "document_type": doc_type, "document_number": doc_no_s, "title": title,
                        "revision": revision_no.strip(), "revision_date": revision_dt.isoformat(), "current": dict(current),
                        "route": {"id": str(route.get("id")), "part_id": part_id}, "process_text": f"Op {route.get('operation_no')} · {_route_name(route)}",
                    }, file)
                    st.rerun()
                save_process_document_revision(repo, route, doc_type, doc_no_s, title, revision_no, revision_dt, file)
                save_success_popup(f"{DOC_TYPES[doc_type]} {doc_no_s} Rev {revision_no.strip()} released.", queue_for_rerun=True)
                st.rerun()
            except Exception as exc:
                st.error(db_message(exc))
    render_pending_ecn(repo, existing, "PROCESS_DOC", perms)


def process_route_print_rows(repo: Any, part_id: str, processes: dict[str, dict]) -> list[dict]:
    """Part Master print rows: process list with the CURRENT process drawing / spec revisions."""
    return PartProcessService(repo).print_rows(part_id, processes)


# ---------------------------------------------------------------------------------------------------------------- register
def _render_ecn_actions(service: ECNService, ecn: dict, employees: list[dict], *, writable: bool, key: str) -> list[dict]:
    """Implementation actions (affected document, action, responsible, target date, status). Returns the saved rows."""
    from core.ecn_service import ACTION_STATUSES, default_actions, normalize_action_rows
    ecn_id = str(ecn.get("id") or "")
    saved = service.actions(ecn_id)
    status = normalize_status(ecn.get("status"))
    locked = status in {"COMPLETED", "CANCELLED"} or not writable
    section_bar("IMPLEMENTATION ACTIONS", "Affected documents (drawing, PFD, CP, PFMEA, PPAP, POs, stock) with responsible and target date. "
                "The ECN can be COMPLETED only when every action is DONE or NOT REQUIRED.")
    emp = _employee_options(employees)
    label_to_id = {label: emp_id for emp_id, label in emp.items()}
    rows = saved or default_actions(ecn)
    frame = pd.DataFrame([{
        "_id": str(r.get("id") or ""),
        "Affected Document": r.get("affected_document") or "",
        "Action": r.get("action_text") or "",
        "Responsible": emp.get(str(r.get("responsible_employee_id") or ""), r.get("responsible_text") or ""),
        "Target Date": _date_or_none(r.get("target_date")),
        "Status": str(r.get("status") or "OPEN"),
        "Done On": _date_or_none(r.get("completed_date")),
        "Remarks": r.get("remarks") or "",
    } for r in rows], columns=["_id", "Affected Document", "Action", "Responsible", "Target Date", "Status", "Done On", "Remarks"])
    if not saved and rows:
        st.caption("Suggested from the ticked supporting documents - review and save.")
    with st.form(f"{key}_form"):
        edited = st.data_editor(
            frame, hide_index=True, width="stretch", num_rows="dynamic", disabled=True if locked else ["_id"], key=f"{key}_grid",
            column_config={
                "_id": None,
                "Responsible": st.column_config.SelectboxColumn("Responsible", options=list(label_to_id) or [""]),
                "Target Date": st.column_config.DateColumn("Target Date", format="DD.MM.YYYY"),
                "Done On": st.column_config.DateColumn("Done On", format="DD.MM.YYYY"),
                "Status": st.column_config.SelectboxColumn("Status", options=list(ACTION_STATUSES), required=True),
            },
        )
        save = st.form_submit_button("Save Implementation Actions", type="primary", disabled=locked, width="stretch")
    if save:
        try:
            grid = [{
                "id": row.get("_id"), "affected_document": row.get("Affected Document"), "action_text": row.get("Action"),
                "responsible_employee_id": label_to_id.get(str(row.get("Responsible") or "")),
                "responsible_text": None if label_to_id.get(str(row.get("Responsible") or "")) else row.get("Responsible"),
                "target_date": row.get("Target Date"), "status": row.get("Status"), "completed_date": row.get("Done On"),
                "remarks": row.get("Remarks"), "sequence_no": (index + 1) * 10,
            } for index, row in enumerate(edited.fillna("").to_dict("records"))]
            count = service.save_actions(ecn_id, normalize_action_rows(grid))
            save_success_popup(f"{count} implementation action(s) saved for {ecn.get('ecn_number')}.", queue_for_rerun=True)
            st.rerun()
        except Exception as exc:
            st.error(db_message(exc))
    open_count = sum(1 for r in saved if str(r.get("status") or "").upper() in {"OPEN", "IN_PROGRESS"})
    if saved:
        st.caption(f"{len(saved)} action(s) · {open_count} open.")
    return saved


def render_ecn_register_panel(repo: Any, perms: dict, *, part_id: str | None = None, key: str = "ecn_register") -> None:
    """ECN / PCN register with filters, detail, approvals, attachments, print (PDF / Excel) and e-mail."""
    service = ECNService(repo)
    rows = service.list(part_id=part_id)
    parts = {str(p["id"]): p for p in repo.select("parts", limit=10000)} if not part_id else {part_id: repo.get("parts", part_id) or {}}
    employees = service.employees()
    writable = bool(perms.get("can_edit") or perms.get("can_create"))

    with st.container(border=True, key=f"{key}_new"):
        if st.toggle("Raise a new ECN / PCN (without a drawing replacement)", value=False, key=f"{key}_new_open", disabled=not writable):
            choices = {pid: part_label(p) for pid, p in parts.items() if p}
            new_part_id = part_id or (st.selectbox("Part", list(choices), format_func=lambda v: choices[v], key=f"{key}_new_part") if choices else None)
            new_part = parts.get(str(new_part_id)) or {}
            defaults = {"part_id": new_part_id, "part_number": new_part.get("part_number"), "part_name": new_part.get("part_name"),
                        "drawing_number": new_part.get("drawing_number"), "previous_revision": new_part.get("drawing_revision"),
                        "document_scope": "GENERAL", "change_type": "ECN", "customer_approval": "PENDING", "drawing_change_mode": "AS_SUGGESTED"}
            form, action = ecn_form(employees, key=f"{key}_new_{new_part_id}", defaults=defaults,
                                    actions=(("DRAFT", "Save as DRAFT"), ("PENDING_APPROVAL", "Submit for Approval")), disabled=not writable)
            if action in {"DRAFT", "PENDING_APPROVAL"}:
                try:
                    ecn = service.create(form, status=action)
                    note = _mail_after_save(repo, ecn, form, employees)
                    save_success_popup(f"{ecn.get('ecn_number')} saved as {status_label(ecn.get('status'))}.{note}", queue_for_rerun=True)
                    st.rerun()
                except Exception as exc:
                    st.error(db_message(exc))

    if not rows:
        st.info("No Engineering / Process Change Notes yet. An ECN is requested automatically whenever a controlled drawing or a process drawing / specification revision is replaced.")
        return
    frame = service.register_frame(rows, parts)
    frame.insert(0, "_id", [str(r.get("id")) for r in rows])
    from core.report_filters import report_register
    filtered = report_register(frame, f"{key}_filters", "ECN / PCN Register", height=360, date_cols=["Date", "Response By"], exclude=["_id"])
    ids = [str(v) for v in filtered["_id"].tolist()] if "_id" in filtered.columns else []
    if not ids:
        st.info("No ECN matches the filters.")
        return
    by_id = {str(r.get("id")): r for r in rows}
    labels = {i: f"{by_id[i].get('ecn_number')} · {by_id[i].get('change_type')} · Part {by_id[i].get('part_number') or '-'} · {status_label(by_id[i].get('status'))}" for i in ids if i in by_id}
    selected_id = st.selectbox("Open ECN / PCN", list(labels), format_func=lambda v: labels[v], key=f"{key}_pick")
    ecn = by_id[selected_id]
    status = normalize_status(ecn.get("status"))
    kpi_grid([
        {"label": "ECN / PCN No.", "value": ecn.get("ecn_number"), "foot": f"{change_title(ecn.get('change_type')).title()} · {ecn.get('ecn_date') or '-'}", "color": "#0B6E70", "background": "#E3F2F2"},
        {"label": "Status", "value": status_label(status), "foot": f"Customer approval: {str(ecn.get('customer_approval') or '-').replace('_', ' ').title()}", "color": "#2563EB", "background": "#EFF6FF"},
        {"label": "Drawing / Revision", "value": f"{ecn.get('drawing_number') or '-'}", "foot": f"Rev {ecn.get('previous_revision') or '-'} → {ecn.get('new_revision') or '-'}", "color": "#7C3AED", "background": "#F5F3FF"},
        {"label": "Linked Revision", "value": "Yes" if ecn.get("document_attachment_id") else "No", "foot": DOCUMENT_SCOPES.get(str(ecn.get("document_scope") or ""), str(ecn.get("document_scope") or "General")), "color": "#B45309", "background": "#FFFBEB"},
    ])
    if ecn.get("document_attachment_id") or ecn.get("previous_attachment_id"):
        att_service = AttachmentService(repo)
        dcols = st.columns(2, gap="small")
        for col, (field, label) in zip(dcols, (("previous_attachment_id", "Download Previous Revision"), ("document_attachment_id", "Download New Revision"))):
            attachment = repo.get("document_attachments", str(ecn.get(field) or "")) if ecn.get(field) else None
            if attachment:
                try:
                    col.download_button(f"{label} (Rev {attachment.get('revision') or '-'})", data=att_service.download(attachment),
                                        file_name=str(attachment.get("file_name") or "drawing"), mime=str(attachment.get("mime_type") or "application/octet-stream"),
                                        key=f"{key}_{field}_{selected_id}", width="stretch")
                except Exception as exc:
                    col.caption(f"File unavailable: {exc}")

    targets = allowed_targets(status, perms)
    if targets:
        c = st.columns([3] + [1] * len(targets), gap="small")
        remarks = c[0].text_input("Remarks for the status change (optional)", key=f"{key}_remarks_{selected_id}")
        for col, target in zip(c[1:], targets):
            if col.button(TRANSITION_LABELS.get(target, target.title()), key=f"{key}_{target}_{selected_id}", width="stretch",
                          type="primary" if target in {"APPROVED", "PENDING_APPROVAL", "COMPLETED"} else "secondary"):
                try:
                    updated = service.transition(selected_id, target, perms, remarks=remarks, approver_employee_id=_my_employee_id(employees))
                    save_success_popup(f"{updated.get('ecn_number') or ecn.get('ecn_number')} is now {status_label(target)}.", queue_for_rerun=True)
                    st.rerun()
                except Exception as exc:
                    st.error(db_message(exc))
    elif status == "PENDING_APPROVAL" and not perms.get("can_approve"):
        st.caption("Approve / disapprove requires Part Master approve permission.")

    if st.toggle("Edit ECN details", value=False, key=f"{key}_edit_{selected_id}", disabled=not writable or status in {"CANCELLED", "COMPLETED"}):
        if status not in {"DRAFT", "DISAPPROVED"}:
            st.caption("After submission only the FSI-use / approval / completion block, comments and e-mail list can be changed.")
        form, action = ecn_form(employees, key=f"{key}_edit_{selected_id}", defaults=ecn, actions=(("SAVE", "Save ECN"),),
                                disabled=not writable, header_locked=status not in {"DRAFT", "DISAPPROVED"})
        if action == "SAVE":
            try:
                service.save(selected_id, form)
                save_success_popup(f"{ecn.get('ecn_number')} saved.", queue_for_rerun=True)
                st.rerun()
            except Exception as exc:
                st.error(db_message(exc))

    actions = _render_ecn_actions(service, ecn, employees, writable=writable, key=f"{key}_actions_{selected_id}")

    render_attachment_manager(
        repo=repo, entity_type=ATTACHMENT_ENTITY, entity_id=selected_id, folder=f"part_ecns/{selected_id}",
        slots=(AttachmentSlot("REDLINE_DRAWING", "Redline Drawing", "Marked-up drawing for the change"),
               AttachmentSlot("DATASHEET", "Datasheet", "Datasheet / calculation"),
               AttachmentSlot("SUPPORTING_DOCUMENT", "Other Supporting Document", "PFD / CP / PFMEA / customer approval etc.")),
        key_prefix=f"{key}_att_{selected_id}", can_add_or_replace=writable and status != "CANCELLED", can_delete=bool(perms.get("can_archive")),
        title="SUPPORTING DOCUMENTS ATTACHED",
    )

    try:
        from core.ecn_pdf import build_ecn_pdf, build_ecn_xlsx
        emp_map = {str(r.get("id")): r for r in employees}
        part_row = parts.get(str(ecn.get("part_id"))) or {}
        pdf = build_ecn_pdf(ecn, employees=emp_map, part=part_row, actions=actions)
        c1, c2, c3 = st.columns(3, gap="small")
        show_key = f"{key}_show_pdf_{selected_id}"
        if c1.button("Preview ECN Print", icon=":material/preview:", width="stretch", key=f"{key}_preview_{selected_id}"):
            st.session_state[show_key] = not st.session_state.get(show_key, False)
        c2.download_button("Download ECN PDF", data=pdf, file_name=f"{ecn.get('ecn_number') or 'ECN'}.pdf", mime="application/pdf",
                           icon=":material/picture_as_pdf:", width="stretch", key=f"{key}_pdf_{selected_id}", on_click="ignore")
        c3.download_button("Download ECN Excel", data=build_ecn_xlsx(ecn, employees=emp_map, part=part_row, actions=actions),
                           file_name=f"{ecn.get('ecn_number') or 'ECN'}.xlsx", icon=":material/table_view:", width="stretch",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"{key}_xlsx_{selected_id}", on_click="ignore")
        if st.session_state.get(show_key):
            from core.pdf_preview import render_pdf
            render_pdf(pdf, key=f"{key}_pdfview_{selected_id}")
    except Exception as exc:
        st.error(f"ECN print could not be prepared: {db_message(exc)}")

    with st.container(border=True, key=f"{key}_mail_{selected_id}"):
        emp = _employee_options(employees)
        recipients = st.multiselect("E-mail this ECN print to (employees)", list(emp), default=[v for v in (ecn.get("email_employee_ids") or []) if v in emp],
                                    format_func=lambda v: emp.get(v, v), key=f"{key}_mailto_{selected_id}")
        subject, body = ecn_email_text(ecn)
        subject = st.text_input("Subject", value=subject, key=f"{key}_mailsub_{selected_id}")
        body = st.text_area("Message", value=body, height=140, key=f"{key}_mailbody_{selected_id}")
        if st.button("Send ECN e-mail", icon=":material/send:", width="stretch", key=f"{key}_send_{selected_id}", disabled=not recipients):
            try:
                sent, message = email_ecn(repo, ecn, recipients, employees, subject=subject, body=body)
                if message and not sent:
                    st.error(message)
                elif message:
                    st.warning(message)
                else:
                    save_success_popup(f"{ecn.get('ecn_number')} e-mailed to {sent} employee(s) with the ECN print.")
            except Exception as exc:
                st.error(db_message(exc))


def render() -> None:
    """Route ``ecn-register`` (Engineering): ECN / PCN register across all Parts."""
    subpage_navigation(
        ("part-entry", "Part Master Entry", ":material/edit_note:"),
    )
    page_header("Engineering Change Notes", f"ECN / PCN register (format {FORMAT_NO}) raised from Part Master drawing replacements and process changes.", "Engineering")
    repo = Repository()
    perms = current_permissions("PART_MASTER")
    render_ecn_register_panel(repo, perms, key="ecn_register_all")


__all__ = [
    "render", "render_part_processes", "render_ecn_register_panel", "render_pending_ecn", "queue_pending_ecn", "release_pending",
    "ecn_form", "email_ecn", "process_route_print_rows", "PENDING_ECN_KEY",
]
