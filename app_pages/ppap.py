"""R38 · PPAP (Engineering → PPAP): document manager linked to APQP.

Routes
* ``ppap-home``      - KPIs (packages, pending / overdue / due <= 7 days elements, open work by responsible), package
                       register, tracker matrix (elements x parts like the customer PPAP tracker sheet) and tracker import.
* ``ppap-package``   - one package: header (part, customer, PPAP no., level, customer due / interim / full submit dates),
                       element grid (status, due date, responsible employee + department), document upload with revisions,
                       preview, per-element / selected / all ZIP downloads ("NN Element name/" folders + cover sheets),
                       status notes and e-mail of the package to the customer (attachments, or a 7-day link above 10 MB).
* ``ppap-templates`` - default element template (32 elements) and customer-specific templates.

Permissions: module key ``PPAP``; while PPAP has no explicit user / role / department permission row the NPD & APQP
rights apply (same rule as public.qcms_ppap_can in the database).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from core.access import module_permissions, module_permissions_with_source
from core.db_errors import db_message, missing_fields_message
from core.ppap_service import (
    CREATE_FROM_APQP_KEY, DEPARTMENTS, ELEMENT_STATUS_LABELS, MODULE_KEY, OPEN_REQUEST_KEY, PACKAGE_STATUSES, PSW_STATUSES,
    ROUTE_HOME, ROUTE_PACKAGE, ROUTE_TEMPLATES, STATUS_COLORS, SUBMISSION_LEVELS, UI_ELEMENT_STATUSES,
    PpapService, assignment_mail_message, by_responsible, default_department, dmy, element_folder, element_state, foreign_party_recipients,
    match_part, package_cover_xlsx, package_index_pdf, package_progress, parse_date, parse_tracker, party_emails,
    portfolio_kpis, safe_name, split_emails, status_from_label, status_label, submission_method, template_sort_key,
    tracker_workbook_bytes,
)
from core.repository import Repository
from core.selection_labels import employee_label, part_label, party_label, with_status
from core.ui import kpi_grid, page_header, portal_table, record_widget_token, safe, save_success_popup, section_bar, stage_section, status_chip

SELECTOR_KEY = "ppap_package_selector"
NOT_SET = "— Not assigned —"
STATE_LABELS = {"completed": "Completed", "na": "NA", "overdue": "Overdue", "due_soon": "Due ≤ 3 days", "submitted": "Submitted",
                "rejected": "Rejected", "open": "Pending / In progress", "not_planned": "No due date"}
STATUS_OPTIONS = [ELEMENT_STATUS_LABELS[c] for c in UI_ELEMENT_STATUSES]
MAIL_FLASH_KEY = "ppap_assignment_mail_flash"   # R39: assignment e-mail outcome shown after the save rerun
PREVIEW_TYPES = {"pdf": "pdf", "png": "image", "jpg": "image", "jpeg": "image", "gif": "image", "bmp": "image", "webp": "image"}


# ----------------------------------------------------------------------------- helpers
def send_assignment_mail(service: PpapService, package_id: Any, element_ids: Any = None, *, resend: bool = False) -> dict:
    """R39: queue + send the assignment e-mail (part details, drawings, specifications) to the responsible person(s);
    the outcome is kept in the session and shown on the package page after the rerun. Never raises / never blocks saving."""
    try:
        result = service.send_assignment_mail(str(package_id), element_ids, resend=resend)
    except Exception as exc:   # defensive: the service itself never raises
        result = {"queued": 0, "sent": 0, "failed": 0, "error": str(exc)}
    try:
        st.session_state[MAIL_FLASH_KEY] = {"package_id": str(package_id), "result": dict(result)}
    except Exception:
        pass
    return result


def _show_assignment_mail_flash(package_id: str) -> None:
    flash = st.session_state.get(MAIL_FLASH_KEY)
    if not isinstance(flash, Mapping) or str(flash.get("package_id")) != str(package_id):
        return
    st.session_state.pop(MAIL_FLASH_KEY, None)
    level, text = assignment_mail_message(flash.get("result"))
    {"success": st.success, "warning": st.warning}.get(level, st.info)(text, icon=":material/mail:")


def ppap_permissions(profile: Mapping[str, Any] | None = None) -> dict[str, bool]:
    """Module PPAP rights; without an explicit PPAP permission row the NPD & APQP rights apply (mirrors qcms_ppap_can)."""
    profile = profile if profile is not None else (st.session_state.get("profile") or {})
    perms, source = module_permissions_with_source(profile, MODULE_KEY)
    if str(source).upper().startswith("LEGACY"):
        return module_permissions(profile, "NPD_APQP")
    return perms


def ppap_resolve_selection(requested: Any, current: Any, options: list[str]) -> str:
    """Only a real (non-empty) open request overrides the user's current choice (APQP R36b lesson)."""
    requested = str(requested or "").strip()
    current = str(current or "").strip()
    if requested and requested in options:
        return requested
    return current if current in options else ""


def ppap_filter_packages(packages: list[dict], term: str, *, status: str = "ALL", customer_id: str = "", overdue_ids: set[str] | None = None,
                         labels: Mapping[str, str] | None = None) -> list[dict]:
    needle = str(term or "").strip().casefold()
    out = []
    for row in packages:
        if status != "ALL" and str(row.get("status") or "") != status:
            continue
        if customer_id and str(row.get("customer_id") or "") != customer_id:
            continue
        if overdue_ids is not None and str(row.get("id")) not in overdue_ids:
            continue
        hay = " ".join(str(v or "") for v in (row.get("package_no"), row.get("customer_ppap_no"), row.get("customer_part_no"),
                                                row.get("remarks"), row.get("status"), (labels or {}).get(str(row.get("id")), ""))).casefold()
        if not needle or needle in hay:
            out.append(row)
    return out


def ppap_header_errors(*, customer_part_no: str, customer_id: str, package_no: str, packages: list[dict], existing_id: str = "") -> list[str]:
    errors = []
    if not str(customer_part_no or "").strip():
        errors.append("Customer Part No. - required (select a Part or type the customer part number).")
    if not str(customer_id or "").strip():
        errors.append("Customer - select the customer of this PPAP.")
    code = str(package_no or "").strip()
    if code and any(str(p.get("package_no") or "").strip().casefold() == code.casefold() and str(p.get("id")) != str(existing_id or "") for p in packages):
        errors.append(f"PPAP Package No. - '{code}' already exists. Open it from the register instead.")
    return errors


def ppap_matrix_filter(elements_by_package: Mapping[str, list[dict]], *, mode: str = "All", responsible_id: str = "",
                       today: date | None = None) -> dict[str, list[dict]]:
    """Tracker matrix cell filter: All / Open only (Pending, In progress, Rejected) / Overdue only + responsible employee."""
    today = today or date.today()
    out: dict[str, list[dict]] = {}
    for pid, rows in elements_by_package.items():
        kept = []
        for e in rows:
            if responsible_id and str(e.get("responsible_employee_id") or "") != responsible_id:
                continue
            status = str(e.get("status") or "NOT_STARTED").upper()
            if mode == "Open only" and status in {"COMPLETED", "NA", "SUBMITTED"}:
                continue
            if mode == "Overdue only" and element_state(e, today) != "overdue":
                continue
            kept.append(e)
        out[pid] = kept
    return out


def _matrix_html(packages: list[dict], elements_by_package: Mapping[str, list[dict]], today: date,
                 progress_source: Mapping[str, list[dict]] | None = None) -> str:
    numbers: dict[int, str] = {}
    for rows in (progress_source or elements_by_package).values():
        for e in rows:
            numbers.setdefault(int(e.get("element_no") or 0), str(e.get("element_name") or ""))
    head = '<th style="position:sticky;left:0;background:#1F3A5F;color:#fff;min-width:230px">Element</th>' + "".join(
        f'<th style="background:#1F3A5F;color:#fff;min-width:118px">{safe(p.get("customer_part_no") or p.get("package_no"))}'
        f'<br><span style="font-weight:400;font-size:10px">PPAP {safe(p.get("customer_ppap_no") or "-")}</span></th>' for p in packages)
    body = []
    for number in sorted(numbers):
        cells = [f'<td style="position:sticky;left:0;background:#F8FAFC;font-weight:700">{number:02d} · {safe(numbers[number])}</td>']
        for package in packages:
            row = next((e for e in elements_by_package.get(str(package.get("id")), []) if int(e.get("element_no") or 0) == number), None)
            if not row:
                cells.append('<td style="background:#fff;color:#94A3B8">–</td>')
                continue
            state = element_state(row, today)
            fg, bg = STATUS_COLORS.get(state, ("#334155", "#F1F5F9"))
            due = dmy(row.get("due_date"))
            cells.append(f'<td style="background:{bg};color:{fg};font-weight:700;font-size:11px">{safe(status_label(row.get("status")))}'
                         f'{"<br><span style=font-weight:400>" + safe(due) + "</span>" if due else ""}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    progress = []
    for package in packages:
        pct = package_progress((progress_source or elements_by_package).get(str(package.get("id")), []))["percent"]
        progress.append(f'<td style="font-weight:800;background:#EFF6FF">{pct:.0f}%</td>')
    body.append('<tr><td style="position:sticky;left:0;background:#EFF6FF;font-weight:800">Progress (applicable elements)</td>' + "".join(progress) + "</tr>")
    return ('<div class="qcms-enterprise-table-wrap qcms-scroll-grid" tabindex="0" style="max-height:640px;overflow:auto">'
            '<table class="qcms-enterprise-table" style="border-collapse:collapse;font-size:11.5px"><thead><tr>' + head + "</tr></thead><tbody>"
            + "".join(body) + "</tbody></table></div>")


def _status_strip(elements: list[dict], today: date) -> str:
    chips = []
    for e in elements:
        state = element_state(e, today)
        fg, bg = STATUS_COLORS.get(state, ("#334155", "#F1F5F9"))
        tip = f"{e.get('element_name')} · {status_label(e.get('status'))} · due {dmy(e.get('due_date')) or 'not set'}"
        chips.append(f'<span title="{safe(tip)}" style="display:inline-block;min-width:34px;margin:2px;padding:4px 6px;border-radius:4px;'
                     f'background:{bg};color:{fg};font-weight:800;font-size:11px;text-align:center">{int(e.get("element_no") or 0):02d}</span>')
    legend = " ".join(f'<span style="padding:2px 6px;border-radius:3px;background:{STATUS_COLORS[k][1]};color:{STATUS_COLORS[k][0]};font-size:10px;font-weight:700">{v}</span>'
                      for k, v in STATE_LABELS.items())
    return f'<div style="margin:4px 0 8px">{"".join(chips)}</div><div style="margin-bottom:8px">{legend}</div>'


def _session_name() -> str:
    profile = st.session_state.get("profile") or {}
    return str(profile.get("full_name") or profile.get("email") or "QCMS user")


def _switch_to(route: str) -> None:
    pages = st.session_state.get("_qsms_pages") or {}
    if route in pages:
        st.switch_page(pages[route])


def _open_package(package_id: str) -> None:
    st.session_state.pop(CREATE_FROM_APQP_KEY, None)
    st.session_state[OPEN_REQUEST_KEY] = str(package_id or "")
    _switch_to(ROUTE_PACKAGE)
    st.rerun()


def _load(repo: Repository, service: PpapService) -> dict[str, Any] | None:
    try:
        parts = repo.select("parts", order_by="part_number", limit=4000) or []
        customers = repo.select("parties", contains={"party_types": ["CUSTOMER"]}, order_by="party_name", limit=3000) or []
        all_parties = repo.select("parties", limit=5000) or []
        employees = repo.select("employees", eq={"status": "ACTIVE"}, order_by="first_name", limit=3000) or []
        projects = repo.select("ppap_projects", order_by="project_code", limit=2000) or []
        packages = service.packages()
        elements = service.all_elements([str(p["id"]) for p in packages]) if packages else []
    except Exception as exc:
        st.error(db_message(exc))
        return None
    elements_by_package: dict[str, list[dict]] = {}
    for e in elements:
        elements_by_package.setdefault(str(e.get("package_id")), []).append(e)
    for rows in elements_by_package.values():
        rows.sort(key=template_sort_key)
    party_by_id = {str(p["id"]): p for p in all_parties}
    customer_labels = {str(c["id"]): party_label(c) for c in customers}
    for package in packages:  # keep saved customers selectable even when no longer flagged CUSTOMER / ACTIVE
        cid = str(package.get("customer_id") or "")
        if cid and cid not in customer_labels and cid in party_by_id:
            customer_labels[cid] = party_label(party_by_id[cid])
    return {"parts": parts, "customers": customers, "all_parties": all_parties, "employees": employees, "projects": projects,
            "packages": packages, "elements": elements, "elements_by_package": elements_by_package, "party_by_id": party_by_id,
            "customer_labels": customer_labels, "employee_labels": {str(e["id"]): employee_label(e) for e in employees}}


def _nav_row(current: str) -> None:
    items = [(ROUTE_HOME, "PPAP Home", ":material/dashboard:"), (ROUTE_PACKAGE, "PPAP Package", ":material/folder_zip:"),
             (ROUTE_TEMPLATES, "Element Templates", ":material/list_alt:")]
    cols = st.columns(len(items) + 2, gap="small")
    for col, (route, label, icon) in zip(cols, items):
        if col.button(label, icon=icon, key=f"ppap_nav_{current}_{route}", width="stretch", type="primary" if route == current else "secondary",
                      disabled=route == current):
            if route == ROUTE_PACKAGE:
                st.session_state[SELECTOR_KEY] = st.session_state.get(SELECTOR_KEY, "")
            _switch_to(route)


# ----------------------------------------------------------------------------- PPAP home
def render_ppap_home() -> None:
    page_header("PPAP", "PPAP packages linked to APQP: element due dates, responsible employees, documents and customer submission")
    _nav_row(ROUTE_HOME)
    repo = Repository()
    perms = ppap_permissions()
    service = PpapService(repo)
    today = date.today()
    data = _load(repo, service)
    if data is None:
        return
    packages, elements = data["packages"], data["elements"]
    kpi = portfolio_kpis(packages, elements, today)
    kpi_grid([
        {"label": "PPAP Packages", "value": kpi["packages"], "foot": f"{kpi['active']} active", "color": "#1469A8", "background": "#EFF6FF"},
        {"label": "Elements Pending", "value": kpi["pending"], "foot": "Pending / In progress / Rejected (active packages)", "color": "#92400E", "background": "#FEF3C7"},
        {"label": "Overdue Elements", "value": kpi["overdue"], "foot": "Due date passed, not completed", "color": "#B91C1C", "background": "#FEF2F2"},
        {"label": "Due ≤ 7 Days", "value": kpi["due_week"], "foot": f"{dmy(today)} – {dmy(today + timedelta(days=7))}", "color": "#D97706", "background": "#FFF7ED"},
        {"label": "% Complete", "value": f"{kpi['percent']:.0f}%", "foot": f"{kpi['completed']}/{kpi['applicable']} applicable elements", "color": "#15803D", "background": "#F0FDF4"},
    ])
    if st.button("New PPAP Package", icon=":material/add_circle:", key="ppap_home_new", disabled=not perms["can_create"]):
        st.session_state[SELECTOR_KEY] = ""
        _open_package("")

    section_bar("OPEN PPAP WORK BY RESPONSIBLE", "Active packages · Pending / In progress / Rejected elements · daily e-mail goes to each responsible employee")
    workload = by_responsible(packages, elements, data["employees"], today)
    if workload:
        portal_table(pd.DataFrame([{k: v for k, v in row.items() if k != "employee_id"} for row in workload]), hide_index=True,
                     height=min(360, 80 + 34 * len(workload)))
    else:
        st.caption("No open PPAP element.")

    tabs = st.tabs(["PPAP Packages", "Tracker Matrix", "Import Tracker (Excel)"])
    with tabs[0]:
        _render_register(data, perms, today)
    with tabs[1]:
        _render_matrix(service, data, today)
    with tabs[2]:
        _render_import(service, perms, data["parts"], data["employees"], packages)


# backwards compatible entry point (first R38 build registered render_ppap)
render_ppap = render_ppap_home


def _render_register(data: Mapping[str, Any], perms: Mapping[str, bool], today: date) -> None:
    packages, elements_by_package = data["packages"], data["elements_by_package"]
    customer_labels, party_by_id = data["customer_labels"], data["party_by_id"]
    part_labels = {str(p["id"]): part_label(p) for p in data["parts"]}
    section_bar("PPAP PACKAGE REGISTER", "Search packages and open one to manage elements, documents and submission")
    f1, f2, f3, f4 = st.columns([2.6, 1.3, 1.9, 1.0], gap="small", vertical_alignment="bottom")
    term = f1.text_input("Search PPAP Packages", key="ppap_register_search", placeholder="Package / PPAP no., part no., customer, remarks")
    status_filter = f2.selectbox("Status", ["ALL", *PACKAGE_STATUSES], key="ppap_register_status", format_func=lambda v: "All" if v == "ALL" else status_label(v))
    customer_filter = f3.selectbox("Customer", [""] + list(customer_labels), format_func=lambda v: "All customers" if not v else customer_labels.get(v, v), key="ppap_register_customer")
    overdue_only = f4.toggle("Overdue only", key="ppap_register_overdue")
    overdue_ids = {pid for pid, rows in elements_by_package.items() if any(element_state(e, today) == "overdue" for e in rows)} if overdue_only else None
    search_labels = {str(p["id"]): " ".join([customer_labels.get(str(p.get("customer_id")), ""), part_labels.get(str(p.get("part_id")), "")]) for p in packages}
    filtered = ppap_filter_packages(packages, term, status=status_filter, customer_id=customer_filter, overdue_ids=overdue_ids, labels=search_labels)
    if not packages:
        st.caption("No PPAP package yet. Create one, create it from an APQP project, or import the customer PPAP tracker.")
        return
    if not filtered:
        st.caption("No PPAP package matches the filters.")
        return
    widths = [1.7, 0.9, 1.4, 2.0, 1.0, 0.9, 0.8, 0.8, 0.8]
    head = st.columns(widths, gap="small")
    for col, label in zip(head, ["Package No.", "PPAP No.", "Part No.", "Customer", "Due Date", "Status", "Done %", "Overdue", ""]):
        col.markdown(f"**{label}**")
    for row in filtered[:60]:
        rid = str(row["id"])
        rows = elements_by_package.get(rid, [])
        progress = package_progress(rows)
        overdue = sum(element_state(e, today) == "overdue" for e in rows)
        cols = st.columns(widths, gap="small", vertical_alignment="center")
        cols[0].markdown(safe(row.get("package_no")))
        cols[1].markdown(safe(row.get("customer_ppap_no") or "-"))
        cols[2].markdown(safe(row.get("customer_part_no") or "-"))
        cols[3].markdown(safe((party_by_id.get(str(row.get("customer_id"))) or {}).get("party_name") or "-"))
        cols[4].markdown(dmy(row.get("customer_due_date")) or "-")
        cols[5].markdown(status_chip(row.get("status")), unsafe_allow_html=True)
        cols[6].markdown(f"{progress['percent']:.0f}%")
        cols[7].markdown(f":red[**{overdue}**]" if overdue else "0")
        if cols[8].button("Open", key=f"ppap_open_{rid}", width="stretch"):
            _open_package(rid)
    if len(filtered) > 60:
        st.caption(f"Showing 60 of {len(filtered)} packages. Refine the search to narrow the list.")


def _render_matrix(service: PpapService, data: Mapping[str, Any], today: date) -> None:
    packages, elements_by_package = data["packages"], data["elements_by_package"]
    section_bar("PPAP TRACKER MATRIX", "Parts as columns, PPAP elements as rows - like the customer PPAP tracker sheet")
    if not packages:
        st.info("No PPAP package yet.")
        return
    customer_labels, employee_labels = data["customer_labels"], data["employee_labels"]
    m1, m2, m3 = st.columns([1.6, 1.6, 1.2], gap="small")
    customer = m1.selectbox("Customer", [""] + sorted({str(p.get("customer_id")) for p in packages if p.get("customer_id")}),
                            format_func=lambda v: "All customers" if not v else customer_labels.get(v, v), key="ppap_matrix_customer")
    responsible = m2.selectbox("Responsible", [""] + list(employee_labels), format_func=lambda v: "Everyone" if not v else employee_labels.get(v, v),
                               key="ppap_matrix_responsible")
    mode = m3.selectbox("Elements", ["All", "Open only", "Overdue only"], key="ppap_matrix_mode")
    candidates = [p for p in packages if not customer or str(p.get("customer_id") or "") == customer]
    labels = {str(p["id"]): f"{p.get('customer_part_no') or p.get('package_no')} · PPAP {p.get('customer_ppap_no') or '-'}" for p in candidates}
    active = [str(p["id"]) for p in candidates if str(p.get("status") or "") not in {"CANCELLED", "CLOSED"}]
    chosen = st.multiselect("Packages (columns)", list(labels), default=active[:12], format_func=lambda v: labels[v], key=f"ppap_matrix_packages_{customer or 'all'}")
    shown = [p for p in candidates if str(p["id"]) in set(chosen)]
    by_package = ppap_matrix_filter(elements_by_package, mode=mode, responsible_id=responsible, today=today)
    if not shown:
        st.caption("Select at least one package.")
        return
    st.markdown(_matrix_html(shown, by_package, today, progress_source=elements_by_package), unsafe_allow_html=True)
    st.caption("Legend: " + " · ".join(STATE_LABELS.values()))
    e1, e2 = st.columns(2, gap="small")
    if e1.button("Prepare tracker export (Excel, customer layout)", key="ppap_matrix_prepare", icon=":material/table_view:", width="stretch"):
        try:
            st.session_state["ppap_matrix_export_bytes"] = tracker_workbook_bytes(
                service.element_master(), shown, elements_by_package,
                [str(n.get("note") or "") for p in shown for n in service.notes(str(p["id"]))])
        except Exception as exc:
            st.warning(db_message(exc))
    if st.session_state.get("ppap_matrix_export_bytes"):
        e2.download_button("Download tracker Excel", st.session_state["ppap_matrix_export_bytes"], file_name=f"PPAP_Tracker_{today.isoformat()}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="ppap_matrix_export",
                           icon=":material/download:", width="stretch")


def _render_import(service: PpapService, perms: Mapping[str, bool], parts: list[dict], employees: list[dict], packages: list[dict]) -> None:
    section_bar("IMPORT CUSTOMER PPAP TRACKER", "PART NO. / PPAP NO. columns with Status + Due Date per part; the 'status' sheet becomes status notes")
    try:
        template = tracker_workbook_bytes(service.element_master())
        st.download_button("Download PPAP tracker template (Excel)", template, file_name="QCMS_PPAP_Tracker_Template.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="ppap_template_download", icon=":material/download:")
    except Exception as exc:
        st.warning(db_message(exc))
    upload = st.file_uploader("Upload PPAP tracker (.xlsx)", type=["xlsx", "xlsm"], key="ppap_tracker_upload")
    if upload is None:
        return
    try:
        parsed = parse_tracker(upload.getvalue())
    except Exception as exc:
        st.error(f"The tracker could not be read: {exc}")
        return
    for warning in parsed.warnings:
        st.warning(warning)
    preview = []
    for column in parsed.columns:
        match = match_part(column.part_token, parts)
        exists = any(str(p.get("customer_part_no") or "") == column.part_text and str(p.get("customer_ppap_no") or "") == column.ppap_no for p in packages)
        progress = package_progress(column.elements)
        preview.append({"Part No. (tracker)": column.part_text, "PPAP No.": column.ppap_no or "-", "Part Master": (match or {}).get("part_number") or "Not found",
                        "Action": "Update" if exists else "Create", "Elements": len(column.elements),
                        "Completed": progress["completed"], "NA": progress["na"], "Open": progress["open"], "Progress %": progress["percent"]})
    st.markdown(f"**Sheet '{safe(parsed.sheet)}' · {len(parsed.columns)} part column(s) · {len(parsed.element_names)} elements · {len(parsed.notes)} status note(s)**")
    portal_table(pd.DataFrame(preview), hide_index=True)
    if parsed.notes:
        st.caption("Status notes: " + " | ".join(parsed.notes[:5]))
    options = list(range(len(parsed.columns)))
    labels = {i: f"{c.part_text} · PPAP {c.ppap_no or '-'}" for i, c in enumerate(parsed.columns)}
    chosen = st.multiselect("Columns to import", options, default=options, format_func=lambda i: labels[i], key="ppap_import_columns")
    employee_labels = {str(e["id"]): employee_label(e) for e in employees}
    owner = st.selectbox("PPAP owner for new packages", [""] + list(employee_labels), format_func=lambda v: NOT_SET if not v else employee_labels[v], key="ppap_import_owner")
    if st.button("Import tracker", type="primary", key="ppap_import_btn", disabled=not (perms["can_create"] and perms["can_edit"]) or not chosen, width="stretch"):
        try:
            summary = service.import_tracker(parsed, parts=parts, selected=chosen, owner_employee_id=owner or None, author=_session_name())
            save_success_popup(f"Tracker imported: {summary['created']} package(s) created, {summary['updated']} updated, "
                               f"{summary['elements']} element row(s), {summary['notes']} status note(s).", queue_for_rerun=True)
            st.rerun()
        except Exception as exc:
            st.error(db_message(exc))


# ----------------------------------------------------------------------------- PPAP package
def render_ppap_package() -> None:
    page_header("PPAP Package", "Header, elements with due dates and responsible employees, documents, downloads and customer submission")
    _nav_row(ROUTE_PACKAGE)
    repo = Repository()
    perms = ppap_permissions()
    service = PpapService(repo)
    today = date.today()
    data = _load(repo, service)
    if data is None:
        return
    _render_package(repo, service, perms, today, data)


def _render_package(repo: Repository, service: PpapService, perms: Mapping[str, bool], today: date, data: Mapping[str, Any]) -> None:
    parts, projects, packages = data["parts"], data["projects"], data["packages"]
    party_by_id, customer_labels, employee_labels = data["party_by_id"], data["customer_labels"], data["employee_labels"]
    part_by_id = {str(p["id"]): p for p in parts}
    part_labels = {str(p["id"]): with_status(part_label(p), p) for p in parts}
    project_labels = {str(p["id"]): with_status(f"{p.get('project_code')} · {part_labels.get(str(p.get('part_id')), '')}", p) for p in projects}
    package_options = [""] + [str(p["id"]) for p in packages]
    package_labels = {str(p["id"]): with_status(f"{p.get('package_no')} · PPAP {p.get('customer_ppap_no') or '-'} · Part {p.get('customer_part_no') or '-'}", p) for p in packages}

    requested = st.session_state.pop(OPEN_REQUEST_KEY, "")
    resolved = ppap_resolve_selection(requested, st.session_state.get(SELECTOR_KEY), package_options)
    from_apqp = str(st.session_state.get(CREATE_FROM_APQP_KEY) or "")
    if from_apqp:
        resolved = ""
    if st.session_state.get(SELECTOR_KEY) != resolved:
        st.session_state[SELECTOR_KEY] = resolved

    selected_id = st.selectbox("Open / Edit PPAP Package", package_options, key=SELECTOR_KEY,
                               format_func=lambda v: "New PPAP Package" if not v else package_labels.get(v, v))
    existing = next((p for p in packages if str(p["id"]) == selected_id), None)
    if existing:
        st.session_state.pop(CREATE_FROM_APQP_KEY, None)
    project_for_new = next((p for p in projects if str(p["id"]) == from_apqp), None) if not existing else None
    defaults = dict(existing or (service.header_from_apqp(project_for_new, parts) if project_for_new else {}))
    if project_for_new:
        st.info(f"New PPAP package from APQP project **{safe(project_for_new.get('project_code'))}** - check the header and Save.")

    # ------------------------------------------------------------- A · header
    can_save = bool(perms["can_edit"]) if existing else bool(perms["can_create"])
    scope = record_widget_token("ppap-package", existing or {}, selected=selected_id or f"new-{from_apqp}")
    owner_options = [""] + list(employee_labels)
    with stage_section("A", "PPAP PACKAGE HEADER", "Part, customer, PPAP no., submission level, customer due date, interim / full submit dates, status and APQP link", key="ppap_package_a"):
        with st.form(f"ppap_header_form_{scope}"):
            c = st.columns(4, gap="small")
            package_no = c[0].text_input("PPAP Package No.", value=str(defaults.get("package_no") or ""), placeholder="Blank = automatic")
            project_options = [""] + list(project_labels)
            default_project = str(defaults.get("apqp_project_id") or "")
            apqp_id = c[1].selectbox("APQP Project (link)", project_options, index=project_options.index(default_project) if default_project in project_options else 0,
                                     format_func=lambda v: "— Not linked —" if not v else project_labels.get(v, v))
            part_options = [""] + list(part_labels)
            default_part = str(defaults.get("part_id") or "")
            part_id = c[2].selectbox("Part (Part Master)", part_options, index=part_options.index(default_part) if default_part in part_options else 0,
                                     format_func=lambda v: "— Not linked —" if not v else part_labels.get(v, v))
            customer_options = [""] + list(customer_labels)
            default_customer = str(defaults.get("customer_id") or (part_by_id.get(default_part) or {}).get("customer_id") or "")
            customer_id = c[3].selectbox("Customer", customer_options, index=customer_options.index(default_customer) if default_customer in customer_options else 0,
                                         format_func=lambda v: "— Select —" if not v else customer_labels.get(v, v))
            c = st.columns(4, gap="small")
            customer_part_no = c[0].text_input("Customer Part No.", value=str(defaults.get("customer_part_no") or ""), placeholder="Blank = Part Master part number")
            customer_ppap_no = c[1].text_input("Customer PPAP No.", value=str(defaults.get("customer_ppap_no") or ""))
            level = int(defaults.get("submission_level") or 3)
            submission_level = c[2].selectbox("Submission Level", SUBMISSION_LEVELS, index=SUBMISSION_LEVELS.index(level) if level in SUBMISSION_LEVELS else 2,
                                              format_func=lambda v: f"Level {v}")
            psw = str(defaults.get("psw_status") or "NOT_SUBMITTED")
            psw_status = c[3].selectbox("PSW Status", PSW_STATUSES, index=PSW_STATUSES.index(psw) if psw in PSW_STATUSES else 0, format_func=status_label)
            c = st.columns(5, gap="small")
            customer_due = c[0].date_input("Customer Due Date", value=parse_date(defaults.get("customer_due_date")), format="DD-MM-YYYY")
            interim_submit = c[1].date_input("Interim Submit", value=parse_date(defaults.get("interim_submit_date")), format="DD-MM-YYYY")
            interim_approved = c[2].date_input("Interim Approved", value=parse_date(defaults.get("interim_approved_date")), format="DD-MM-YYYY")
            full_submit = c[3].date_input("Full Submit", value=parse_date(defaults.get("full_submit_date")), format="DD-MM-YYYY")
            approval_date = c[4].date_input("Approval", value=parse_date(defaults.get("approval_date")), format="DD-MM-YYYY")
            c = st.columns(3, gap="small")
            default_owner = str(defaults.get("owner_employee_id") or "")
            owner_id = c[0].selectbox("PPAP Owner", owner_options, index=owner_options.index(default_owner) if default_owner in owner_options else 0,
                                      format_func=lambda v: NOT_SET if not v else employee_labels.get(v, v))
            contact_email = c[1].text_input("Customer PPAP Contact E-mail", value=str(defaults.get("customer_contact_email") or ""),
                                            placeholder="Blank = customer master e-mail")
            status_value = str(defaults.get("status") or "IN_PROGRESS")
            package_status = c[2].selectbox("Package Status", PACKAGE_STATUSES, index=PACKAGE_STATUSES.index(status_value) if status_value in PACKAGE_STATUSES else 0,
                                            format_func=status_label)
            remarks = st.text_area("Remarks", value=str(defaults.get("remarks") or ""), height=68)
            default_due = default_resp = None
            if not existing:
                c = st.columns(2, gap="small")
                default_due = c[0].date_input("Default element due date (new package)", value=parse_date(defaults.get("customer_due_date")), format="DD-MM-YYYY")
                default_resp = c[1].selectbox("Default responsible employee (new package)", owner_options, format_func=lambda v: NOT_SET if not v else employee_labels.get(v, v))
                st.caption("The element list comes from the customer's own PPAP template when it exists, otherwise from the default template (PPAP → Element Templates).")
            submitted = st.form_submit_button("Update PPAP Package" if existing else "Save PPAP Package", type="primary", width="stretch", disabled=not can_save)
        if not can_save:
            st.caption("PPAP edit permission is required." if existing else "PPAP create permission is required.")
        if submitted:
            part_no_value = customer_part_no.strip() or str((part_by_id.get(part_id) or {}).get("part_number") or "")
            errors = ppap_header_errors(customer_part_no=part_no_value, customer_id=customer_id, package_no=package_no, packages=packages,
                                        existing_id=str((existing or {}).get("id") or ""))
            emails = split_emails(contact_email)
            if contact_email.strip() and not emails:
                errors.append("Customer PPAP Contact E-mail - enter a valid e-mail address.")
            if errors:
                st.error(missing_fields_message(errors))
            else:
                def _iso(value: Any) -> str | None:
                    return value.isoformat() if isinstance(value, date) else None
                payload = {
                    "apqp_project_id": apqp_id or None, "part_id": part_id or None, "customer_id": customer_id or None,
                    "customer_part_no": part_no_value, "customer_ppap_no": customer_ppap_no.strip() or None,
                    "submission_level": int(submission_level), "psw_status": psw_status,
                    "customer_due_date": _iso(customer_due), "interim_submit_date": _iso(interim_submit),
                    "interim_approved_date": _iso(interim_approved), "full_submit_date": _iso(full_submit), "approval_date": _iso(approval_date),
                    "owner_employee_id": owner_id or None, "customer_contact_email": "; ".join(emails) or None,
                    "status": package_status, "remarks": remarks.strip() or None,
                }
                try:
                    if existing:
                        if package_no.strip():
                            payload["package_no"] = package_no.strip()
                        saved = repo.update("ppap_packages", str(existing["id"]), payload)
                        message = f"PPAP package {saved.get('package_no') or existing.get('package_no')} updated."
                    else:
                        payload["package_no"] = package_no.strip()
                        saved = service.create_package(payload, default_due=default_due if isinstance(default_due, date) else None,
                                                       responsible_employee_id=default_resp or None)
                        message = f"PPAP package {saved.get('package_no')} created with the element list from the PPAP template."
                        if saved.get("id"):
                            send_assignment_mail(service, saved["id"])   # R39: e-mail the responsible person(s) right away
                    st.session_state.pop(CREATE_FROM_APQP_KEY, None)
                    st.session_state[OPEN_REQUEST_KEY] = str(saved.get("id") or (existing or {}).get("id") or "")
                    save_success_popup(message, queue_for_rerun=True)
                    st.rerun()
                except Exception as exc:
                    st.error(db_message(exc))

    if not existing:
        st.caption("Save the package header to load its PPAP elements, documents and customer submission.")
        return
    package_id = str(existing["id"])
    package_elements = service.elements(package_id)
    documents = service.documents(package_id)
    latest_docs = [d for d in documents if d.get("is_latest")]
    docs_by_element: dict[str, list[dict]] = {}
    for doc in documents:
        docs_by_element.setdefault(str(doc.get("package_element_id")), []).append(doc)
    progress = package_progress(package_elements)
    overdue = sum(element_state(e, today) == "overdue" for e in package_elements)
    due_soon = sum(element_state(e, today) == "due_soon" for e in package_elements)
    apqp = next((p for p in projects if str(p["id"]) == str(existing.get("apqp_project_id") or "")), None)
    kpi_grid([
        {"label": "Progress", "value": f"{progress['percent']:.0f}%", "foot": f"{progress['completed']}/{progress['applicable']} applicable · {progress['na']} NA", "color": "#15803D", "background": "#F0FDF4"},
        {"label": "Overdue", "value": overdue, "foot": "Elements past due date", "color": "#B91C1C", "background": "#FEF2F2"},
        {"label": "Due ≤ 3 days", "value": due_soon, "foot": "Daily e-mail goes to the responsible", "color": "#D97706", "background": "#FFF7ED"},
        {"label": "Documents", "value": len(latest_docs), "foot": f"{len(documents)} file version(s)", "color": "#1469A8", "background": "#EFF6FF"},
        {"label": "PSW Status", "value": status_label(existing.get("psw_status")), "foot": f"Level {existing.get('submission_level') or 3}", "color": "#0F766E", "background": "#F0FDFA"},
        {"label": "APQP Project", "value": (apqp or {}).get("project_code") or "Not linked", "foot": f"Customer due {dmy(existing.get('customer_due_date')) or '-'}", "color": "#6D28D9", "background": "#F5F3FF"},
    ])
    if apqp and st.button("Open linked APQP project", icon=":material/assignment_turned_in:", key=f"ppap_open_apqp_{package_id}"):
        st.session_state["apqp_project_edit_request_id"] = str(apqp["id"])
        _switch_to("apqp")

    _show_assignment_mail_flash(package_id)
    m1, m2 = st.columns([3, 1.4], gap="small", vertical_alignment="center")
    m1.caption("Responsible persons get an e-mail with the part details, current drawings and specifications when elements are "
               "assigned to them (and a daily reminder for elements due within 3 days or overdue).")
    if m2.button("Send assignment e-mail again", icon=":material/forward_to_inbox:", key=f"ppap_assign_mail_{package_id}",
                 disabled=not (perms.get("can_edit") or perms.get("can_create")), width="stretch"):
        with st.spinner("Sending the assignment e-mail…"):
            send_assignment_mail(service, package_id, None, resend=True)
        st.session_state[OPEN_REQUEST_KEY] = package_id
        st.rerun()
    _render_elements(service, perms, today, existing, package_elements, docs_by_element, employee_labels)
    _render_documents(service, perms, existing, package_elements, docs_by_element)
    _render_notes(service, perms, today, package_id)
    _render_submission(repo, service, perms, existing, package_elements, latest_docs, data, part_by_id, apqp)
    _render_delete(repo, service, perms, existing, documents)


def _render_elements(service: PpapService, perms: Mapping[str, bool], today: date, existing: Mapping[str, Any], package_elements: list[dict],
                     docs_by_element: Mapping[str, list[dict]], employee_labels: Mapping[str, str]) -> None:
    package_id = str(existing["id"])
    employee_options = [NOT_SET] + [employee_labels[k] for k in employee_labels]
    label_to_employee = {v: k for k, v in employee_labels.items()}
    department_options = sorted(set(DEPARTMENTS) | {str(e.get("responsible_department")) for e in package_elements if e.get("responsible_department")})
    with stage_section("B", "PPAP ELEMENTS · STATUS, DUE DATE & RESPONSIBLE",
                       "Status Pending / In progress / Completed / NA / Rejected. Colour: green completed · grey NA · red overdue · orange due ≤ 3 days. "
                       "Responsible employees get a daily e-mail (CC reporting manager when overdue) for elements due within 3 days or overdue.",
                       key="ppap_package_b"):
        st.markdown(_status_strip(package_elements, today), unsafe_allow_html=True)
        frame = pd.DataFrame([{
            "ID": str(e["id"]), "No.": int(e.get("element_no") or 0), "Element": e.get("element_name") or "",
            "Applicable": str(e.get("status") or "").upper() != "NA",
            "Status": status_label(e.get("status") or "NOT_STARTED"), "Due Date": parse_date(e.get("due_date")),
            "Responsible": employee_labels.get(str(e.get("responsible_employee_id") or ""), NOT_SET),
            "Department": e.get("responsible_department") or default_department(e.get("element_no")),
            "Completed Date": parse_date(e.get("completed_date")), "Remarks": e.get("remarks") or "",
            "Files": len(docs_by_element.get(str(e["id"]), [])),
        } for e in package_elements], columns=["ID", "No.", "Element", "Applicable", "Status", "Due Date", "Responsible", "Department", "Completed Date", "Remarks", "Files"])
        edited = st.data_editor(
            frame, hide_index=True, width="stretch", num_rows="dynamic", height=min(900, 90 + 36 * max(1, len(frame))),
            key=f"ppap_elements_{package_id}", disabled=not perms["can_edit"],
            column_config={
                "ID": None, "No.": st.column_config.NumberColumn(min_value=1, max_value=999, step=1, width="small"),
                "Element": st.column_config.TextColumn(width="large"),
                "Applicable": st.column_config.CheckboxColumn(help="Untick = NA (not applicable for this part)"),
                "Status": st.column_config.SelectboxColumn(options=STATUS_OPTIONS, required=True),
                "Due Date": st.column_config.DateColumn(format="DD-MM-YYYY"),
                "Responsible": st.column_config.SelectboxColumn(options=employee_options, width="large"),
                "Department": st.column_config.SelectboxColumn(options=department_options),
                "Completed Date": st.column_config.DateColumn(format="DD-MM-YYYY"),
                "Remarks": st.column_config.TextColumn(width="large"), "Files": st.column_config.NumberColumn(disabled=True, width="small"),
            },
        )
        if st.button("Save PPAP Elements", type="primary", width="stretch", key=f"ppap_save_elements_{package_id}", disabled=not perms["can_edit"]):
            try:
                records = edited.to_dict("records") if hasattr(edited, "to_dict") else list(edited)
                rows = []
                seen: set[int] = set()

                def _value(value: Any) -> Any:
                    return None if value is None or (isinstance(value, float) and pd.isna(value)) else value

                for r in records:
                    number = _value(r.get("No."))
                    if number in (None, ""):
                        continue
                    number = int(float(number))
                    if number in seen:
                        raise ValueError(f"Element No. {number} is duplicated.")
                    seen.add(number)
                    status = status_from_label(r.get("Status"))
                    applicable = _value(r.get("Applicable"))
                    if applicable is False:
                        status = "NA"
                    elif applicable is True and status == "NA":
                        status = "NOT_STARTED"
                    rows.append({"id": r.get("ID") if isinstance(r.get("ID"), str) and r.get("ID") else None, "element_no": number,
                                 "element_name": str(r.get("Element") or "").strip() or f"Element {number}", "status": status,
                                 "due_date": _value(r.get("Due Date")),
                                 "responsible_employee_id": label_to_employee.get(str(r.get("Responsible") or "")),
                                 "responsible_department": _value(r.get("Department")) or default_department(number),
                                 "completed_date": _value(r.get("Completed Date")),
                                 "remarks": r.get("Remarks") if isinstance(r.get("Remarks"), str) else ""})
                assigned = service.save_elements(package_id, rows)
                notified = service.notify_assignments(existing, assigned)
                if service.last_mail_element_ids:   # R39: only the newly assigned / re-dated elements' responsible persons
                    send_assignment_mail(service, package_id, list(service.last_mail_element_ids))
                save_success_popup(f"PPAP elements saved. {notified} responsible employee notification(s) sent." if assigned else "PPAP elements saved.", queue_for_rerun=True)
                st.session_state[OPEN_REQUEST_KEY] = package_id
                st.rerun()
            except Exception as exc:
                st.error(db_message(exc))

        st.markdown("**Assign several elements at once**")
        element_labels = {str(e["id"]): f"{int(e.get('element_no') or 0):02d} · {e.get('element_name')}" for e in package_elements}
        a1, a2, a3, a4 = st.columns([3, 2, 1.3, 1.3], gap="small", vertical_alignment="bottom")
        chosen = a1.multiselect("Elements", list(element_labels), format_func=lambda v: element_labels[v], key=f"ppap_bulk_el_{package_id}")
        bulk_resp = a2.selectbox("Responsible", [""] + list(employee_labels), format_func=lambda v: "— Keep —" if not v else employee_labels[v], key=f"ppap_bulk_resp_{package_id}")
        bulk_due = a3.date_input("Due date", value=None, format="DD-MM-YYYY", key=f"ppap_bulk_due_{package_id}")
        bulk_status = a4.selectbox("Status", [""] + UI_ELEMENT_STATUSES, format_func=lambda v: "— Keep —" if not v else status_label(v), key=f"ppap_bulk_status_{package_id}")
        if st.button("Apply to selected elements", key=f"ppap_bulk_apply_{package_id}", disabled=not (perms["can_edit"] and chosen), width="stretch"):
            try:
                assigned = service.bulk_assign(package_id, chosen, responsible_employee_id=bulk_resp or None,
                                               due_date=bulk_due if isinstance(bulk_due, date) else None, status=bulk_status or None)
                service.notify_assignments(existing, assigned)
                if service.last_mail_element_ids:   # R39
                    send_assignment_mail(service, package_id, list(service.last_mail_element_ids))
                save_success_popup(f"{len(chosen)} element(s) updated.", queue_for_rerun=True)
                st.session_state[OPEN_REQUEST_KEY] = package_id
                st.rerun()
            except Exception as exc:
                st.error(db_message(exc))
        removable = [e for e in package_elements if not docs_by_element.get(str(e["id"]))]
        if removable and perms.get("can_archive"):
            r1, r2 = st.columns([4, 1.3], gap="small", vertical_alignment="bottom")
            to_remove = r1.multiselect("Remove elements from this package (only elements without documents)", [str(e["id"]) for e in removable],
                                       format_func=lambda v: element_labels.get(v, v), key=f"ppap_remove_el_{package_id}")
            if r2.button("Remove", key=f"ppap_remove_btn_{package_id}", disabled=not to_remove, width="stretch"):
                try:
                    for element_id in to_remove:
                        service.repo.delete("ppap_package_elements", element_id)
                    service.refresh_progress(package_id)
                    save_success_popup(f"{len(to_remove)} element(s) removed.", queue_for_rerun=True)
                    st.session_state[OPEN_REQUEST_KEY] = package_id
                    st.rerun()
                except Exception as exc:
                    st.error(db_message(exc))


def _render_documents(service: PpapService, perms: Mapping[str, bool], existing: Mapping[str, Any], package_elements: list[dict],
                      docs_by_element: Mapping[str, list[dict]]) -> None:
    package_id = str(existing["id"])
    with stage_section("C", "PPAP DOCUMENTS · UPLOAD / REPLACE · PREVIEW · ELEMENT DOWNLOAD",
                       "Each upload is kept as a revision; the newest is the current document used in the package. "
                       "Files are stored under <company>/ppap/<package>/<NN_Element>/.", key="ppap_package_c"):
        element_labels = {str(e["id"]): f"{int(e.get('element_no') or 0):02d} · {e.get('element_name')} · {status_label(e.get('status'))} · {len(docs_by_element.get(str(e['id']), []))} file(s)"
                          for e in package_elements}
        if not element_labels:
            st.info("Add PPAP elements first.")
            return
        element_id = st.selectbox("PPAP Element", list(element_labels), format_func=lambda v: element_labels[v], key=f"ppap_doc_element_{package_id}")
        element = next(e for e in package_elements if str(e["id"]) == element_id)
        versions = sorted(docs_by_element.get(element_id, []), key=lambda d: str(d.get("uploaded_at") or d.get("created_at") or ""), reverse=True)
        current = next((d for d in versions if d.get("is_latest")), None)
        from core.attachments import ALLOWED_ATTACHMENT_TYPES
        from core.ppap_service import next_revision
        u1, u2 = st.columns([3, 1], gap="small")
        upload = u1.file_uploader("Upload / replace document", type=ALLOWED_ATTACHMENT_TYPES + ["pptx", "ppt", "stp", "step", "igs", "msg", "eml", "zip"],
                                  key=f"ppap_upload_{element_id}")
        revision = u2.text_input("Revision", value=next_revision((current or {}).get("revision")) if current else "A", key=f"ppap_rev_{element_id}")
        doc_remarks = st.text_input("Document remarks", key=f"ppap_doc_remarks_{element_id}")
        if st.button("Upload document", type="primary", key=f"ppap_upload_btn_{element_id}", disabled=not (perms["can_edit"] or perms["can_create"]) or upload is None, width="stretch"):
            try:
                from core.auth import current_employee_id
                service.upload_document(existing, element, file_name=upload.name, content=upload.getvalue(), mime_type=getattr(upload, "type", None),
                                        revision=revision, remarks=doc_remarks, uploader_name=_session_name(),
                                        uploader_employee_id=current_employee_id(refresh=False) or None)
                save_success_popup(f"Document uploaded to {int(element.get('element_no') or 0):02d} {element.get('element_name')} (Rev. {revision or 'auto'}).", queue_for_rerun=True)
                st.session_state[OPEN_REQUEST_KEY] = package_id
                st.rerun()
            except Exception as exc:
                st.error(db_message(exc))
        if not versions:
            st.caption("No document uploaded for this element yet.")
            return
        portal_table(pd.DataFrame([{
            "Current": "✓" if d.get("is_latest") else "", "Rev.": d.get("revision"), "File": d.get("file_name"),
            "Size (KB)": round(int(d.get("size_bytes") or 0) / 1024, 1), "Uploaded by": d.get("uploaded_by_name") or "",
            "Uploaded on": dmy(d.get("uploaded_at")), "Remarks": d.get("remarks") or "",
        } for d in versions]), hide_index=True, height=min(320, 80 + 34 * len(versions)))
        version_labels = {str(d["id"]): f"Rev. {d.get('revision')} · {d.get('file_name')}{' · current' if d.get('is_latest') else ''}" for d in versions}
        v1, v2, v3, v4, v5 = st.columns([3, 1.1, 1.1, 1.1, 1.1], gap="small", vertical_alignment="bottom")
        version_id = v1.selectbox("Document version", list(version_labels), format_func=lambda v: version_labels[v], key=f"ppap_version_{element_id}")
        version = next(d for d in versions if str(d["id"]) == version_id)
        cache_key = f"ppap_file_cache_{version_id}"
        if v2.button("Prepare download", key=f"ppap_prep_{version_id}", width="stretch"):
            try:
                st.session_state[cache_key] = service.document_bytes(version)
            except Exception as exc:
                st.error(db_message(exc))
        if st.session_state.get(cache_key):
            v2.download_button("Download file", st.session_state[cache_key], file_name=str(version.get("file_name") or "document"),
                               key=f"ppap_dl_{version_id}", width="stretch")
        kind = PREVIEW_TYPES.get(str(version.get("file_name") or "").rsplit(".", 1)[-1].lower())
        if v3.button("Preview", key=f"ppap_preview_{version_id}", width="stretch", disabled=kind is None,
                     help=None if kind else "Preview is available for PDF and image files - download other files."):
            try:
                st.session_state[cache_key] = st.session_state.get(cache_key) or service.document_bytes(version)
                st.session_state[f"ppap_preview_on_{version_id}"] = True
            except Exception as exc:
                st.error(db_message(exc))
        if v4.button("Make current", key=f"ppap_latest_{version_id}", disabled=not perms["can_edit"] or bool(version.get("is_latest")), width="stretch"):
            try:
                service.set_latest(version)
                st.session_state[OPEN_REQUEST_KEY] = package_id
                st.rerun()
            except Exception as exc:
                st.error(db_message(exc))
        if v5.button("Archive version", key=f"ppap_archive_{version_id}", disabled=not perms.get("can_archive"), width="stretch"):
            try:
                service.archive_document(version)
                save_success_popup("Document version archived.", queue_for_rerun=True)
                st.session_state[OPEN_REQUEST_KEY] = package_id
                st.rerun()
            except Exception as exc:
                st.error(db_message(exc))
        if st.session_state.get(f"ppap_preview_on_{version_id}") and st.session_state.get(cache_key):
            if kind == "pdf":
                from core.pdf_preview import render_pdf
                render_pdf(st.session_state[cache_key], key=f"ppap_pdf_{version_id}", height=720)
            else:
                st.image(st.session_state[cache_key], caption=str(version.get("file_name") or ""), width="stretch")
        current_docs = [d for d in versions if d.get("is_latest")]
        zip_key = f"ppap_element_zip_{element_id}"
        e1, e2 = st.columns(2, gap="small")
        if e1.button(f"Prepare element ZIP ({element_folder(element.get('element_no'), element.get('element_name'))})", key=f"ppap_el_zip_btn_{element_id}",
                     icon=":material/folder_zip:", width="stretch", disabled=not current_docs):
            try:
                st.session_state[zip_key] = service.package_zip(existing, current_docs, package_elements)
            except Exception as exc:
                st.error(db_message(exc))
        if st.session_state.get(zip_key):
            e2.download_button("Download element ZIP", st.session_state[zip_key],
                               file_name=f"{safe_name(existing.get('package_no'), keep_spaces=False)}_{safe_name(element_folder(element.get('element_no'), element.get('element_name')), keep_spaces=False)}.zip",
                               mime="application/zip", key=f"ppap_el_zip_dl_{element_id}", width="stretch")


def _render_notes(service: PpapService, perms: Mapping[str, bool], today: date, package_id: str) -> None:
    with stage_section("D", "STATUS NOTES LOG", "Free-text status updates (e.g. 'waiting for customer to enable Final Submit').", key="ppap_package_d"):
        n1, n2 = st.columns([4, 1.2], gap="small")
        note_text = n1.text_area("New status note", key=f"ppap_note_{package_id}", height=70)
        note_date = n2.date_input("Note date", value=today, format="DD-MM-YYYY", key=f"ppap_note_date_{package_id}")
        if st.button("Add status note", key=f"ppap_note_btn_{package_id}", disabled=not (perms["can_edit"] or perms["can_create"]), width="stretch"):
            try:
                service.add_note(package_id, note_text, note_date=note_date, author=_session_name())
                save_success_popup("Status note added.", queue_for_rerun=True)
                st.session_state[OPEN_REQUEST_KEY] = package_id
                st.rerun()
            except Exception as exc:
                st.error(db_message(exc))
        notes = service.notes(package_id)
        if notes:
            portal_table(pd.DataFrame([{"Date": dmy(n.get("note_date")), "Note": n.get("note"), "By": n.get("author_name") or "",
                                        "Source": str(n.get("source") or "").title()} for n in notes]), hide_index=True, height=min(360, 80 + 40 * len(notes)))
        else:
            st.caption("No status note yet.")


def _render_submission(repo: Repository, service: PpapService, perms: Mapping[str, bool], existing: Mapping[str, Any], package_elements: list[dict],
                       latest_docs: list[dict], data: Mapping[str, Any], part_by_id: Mapping[str, dict], apqp: Mapping[str, Any] | None) -> None:
    package_id = str(existing["id"])
    employee_labels, party_by_id = data["employee_labels"], data["party_by_id"]
    part = part_by_id.get(str(existing.get("part_id") or "")) or {}
    customer = party_by_id.get(str(existing.get("customer_id") or "")) or {}
    owner_label = employee_labels.get(str(existing.get("owner_employee_id") or ""), "")
    with stage_section("E", "PPAP PACKAGE · DOWNLOAD & SEND TO CUSTOMER",
                       "ZIP = one folder per element ('NN Element name/file') + cover sheets (PSW index PDF, tracker Excel). "
                       "E-mails above 10 MB (or 18 files) send a secure 7-day download link instead of attachments.", key="ppap_package_e"):
        element_by_id = {str(e["id"]): e for e in package_elements}
        doc_labels = {str(d["id"]): f"{int((element_by_id.get(str(d.get('package_element_id'))) or {}).get('element_no') or 0):02d} · "
                                     f"{(element_by_id.get(str(d.get('package_element_id'))) or {}).get('element_name')} · {d.get('file_name')} · Rev. {d.get('revision')}"
                      for d in sorted(latest_docs, key=lambda d: int((element_by_id.get(str(d.get("package_element_id"))) or {}).get("element_no") or 0))}
        if not doc_labels:
            st.info("Upload documents in section C to build the PPAP package.")
        selection = st.multiselect("Selected documents (current revisions)", list(doc_labels), default=list(doc_labels),
                                   format_func=lambda v: doc_labels[v], key=f"ppap_pkg_docs_{package_id}")
        selected_docs = [d for d in latest_docs if str(d["id"]) in set(selection)]
        total = sum(int(d.get("size_bytes") or 0) for d in selected_docs)
        method = submission_method(selected_docs) if selected_docs else "EMAIL_ATTACHMENTS"
        st.caption(f"{len(selected_docs)} of {len(latest_docs)} document(s) selected · {total / 1048576:.2f} MB · e-mail method: "
                   f"{'attachments' if method == 'EMAIL_ATTACHMENTS' else 'secure 7-day download link (ZIP)'}")
        k1, k2 = st.columns(2, gap="small")
        include_index = k1.checkbox("Cover sheet: PSW / package index PDF", value=True, key=f"ppap_include_index_{package_id}")
        include_xlsx = k2.checkbox("Cover sheet: PPAP tracker Excel", value=True, key=f"ppap_include_xlsx_{package_id}")

        def _index_pdf(docs: list[dict]) -> bytes:
            from core.record_print import _Resolver, _company
            company = _company(existing, _Resolver(repo))
            return package_index_pdf(existing, package_elements, docs, part=part, customer=customer, apqp=apqp, owner=owner_label,
                                     employee_labels=employee_labels, company=company)

        def _cover(docs: list[dict]) -> bytes:
            return package_cover_xlsx(existing, package_elements, docs, employee_labels=employee_labels,
                                      notes=[str(n.get("note") or "") for n in service.notes(package_id)])

        def _zip(docs: list[dict]) -> bytes:
            return service.package_zip(existing, docs, package_elements, index_pdf=_index_pdf(docs) if include_index else None,
                                       cover_xlsx=_cover(docs) if include_xlsx else None)

        b1, b2, b3, b4 = st.columns(4, gap="small")
        all_key, sel_key, pdf_key, xlsx_key = (f"ppap_zip_all_{package_id}", f"ppap_zip_sel_{package_id}", f"ppap_index_{package_id}", f"ppap_cover_{package_id}")
        if b1.button("Download all (ZIP)", icon=":material/folder_zip:", key=f"ppap_build_all_{package_id}", disabled=not latest_docs, width="stretch"):
            try:
                st.session_state[all_key] = _zip(latest_docs)
                service.log_submission(existing, latest_docs, package_elements, sent_to="Download all (ZIP)", method="DOWNLOAD", status="DOWNLOADED", sender=_session_name())
            except Exception as exc:
                st.error(db_message(exc))
        if st.session_state.get(all_key):
            b1.download_button(f"Save ZIP · all {len(latest_docs)} file(s)", st.session_state[all_key], file_name=f"{safe_name(existing.get('package_no'), keep_spaces=False)}_PPAP_Package.zip",
                               mime="application/zip", key=f"ppap_dl_all_{package_id}", width="stretch")
        if b2.button("Download selected (ZIP)", icon=":material/checklist:", key=f"ppap_build_sel_{package_id}", disabled=not selected_docs, width="stretch"):
            try:
                st.session_state[sel_key] = _zip(selected_docs)
                service.log_submission(existing, selected_docs, package_elements, sent_to="Download selected (ZIP)", method="DOWNLOAD", status="DOWNLOADED", sender=_session_name())
            except Exception as exc:
                st.error(db_message(exc))
        if st.session_state.get(sel_key):
            b2.download_button(f"Save ZIP · {len(selected_docs)} selected", st.session_state[sel_key], file_name=f"{safe_name(existing.get('package_no'), keep_spaces=False)}_PPAP_Selected.zip",
                               mime="application/zip", key=f"ppap_dl_sel_{package_id}", width="stretch")
        if b3.button("Generate PSW / index PDF", icon=":material/picture_as_pdf:", key=f"ppap_build_pdf_{package_id}", width="stretch"):
            try:
                st.session_state[pdf_key] = _index_pdf(selected_docs)
            except Exception as exc:
                st.error(db_message(exc))
        if st.session_state.get(pdf_key):
            b3.download_button("Download PSW / index PDF", st.session_state[pdf_key], file_name=f"{existing.get('package_no')}_PSW_Index.pdf",
                               mime="application/pdf", key=f"ppap_dl_pdf_{package_id}", width="stretch")
        if b4.button("Generate tracker Excel", icon=":material/table_view:", key=f"ppap_build_xlsx_{package_id}", width="stretch"):
            try:
                st.session_state[xlsx_key] = _cover(selected_docs or latest_docs)
            except Exception as exc:
                st.error(db_message(exc))
        if st.session_state.get(xlsx_key):
            b4.download_button("Download tracker Excel", st.session_state[xlsx_key], file_name=f"{existing.get('package_no')}_PPAP_Tracker.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"ppap_dl_xlsx_{package_id}", width="stretch")
        from core.pdf_preview import preview_button
        preview_button("ppap_packages", package_id, key="ppap_package", record=existing)

        st.markdown("**Send the PPAP package to the customer**")
        contact = split_emails(existing.get("customer_contact_email")) or party_emails(customer)
        s1, s2 = st.columns(2, gap="small")
        to_selected = s1.multiselect("To (customer contacts)", contact, default=contact[:1], key=f"ppap_to_{package_id}")
        to_typed = s2.text_input("Other To address(es)", key=f"ppap_to_typed_{package_id}", placeholder="name@customer.com; …")
        cc_text = s1.text_input("CC", key=f"ppap_cc_{package_id}")
        subject = s2.text_input("Subject", value=f"PPAP Submission · PPAP {existing.get('customer_ppap_no') or existing.get('package_no')} · Part {existing.get('customer_part_no') or ''}".strip(),
                                key=f"ppap_subject_{package_id}")
        message = st.text_area("Message", value=f"Dear {customer.get('contact_person') or 'Sir / Madam'},\n\nPlease find our PPAP submission (Level {existing.get('submission_level') or 3}) for part {existing.get('customer_part_no') or '-'}.",
                               height=110, key=f"ppap_msg_{package_id}")
        st.caption("Only this package's selected documents are sent - never documents of another customer. Recipients that belong to another "
                   "customer / supplier in the party master are refused.")
        if st.button("Send PPAP package to customer", type="primary", icon=":material/send:", key=f"ppap_send_{package_id}",
                     disabled=not (perms["can_edit"] or perms["can_create"]) or not selected_docs, width="stretch"):
            to = [*to_selected, *split_emails(to_typed)]
            cc = split_emails(cc_text)
            errors = []
            if not to:
                errors.append("To - select a customer contact or type an e-mail address.")
            if to_typed.strip() and not split_emails(to_typed):
                errors.append("Other To address(es) - enter valid e-mail addresses.")
            foreign = foreign_party_recipients([*to, *cc], data["all_parties"], existing.get("customer_id"))
            if foreign:
                errors.append(f"Recipients - {', '.join(foreign)} belong(s) to another customer / supplier. A PPAP package is confidential to its customer.")
            if errors:
                st.error(missing_fields_message(errors))
            else:
                try:
                    result = service.send_to_customer(existing, selected_docs, package_elements, to=to, cc=cc, subject=subject, message=message,
                                                      sender=_session_name(), index_pdf=_index_pdf(selected_docs) if include_index else None,
                                                      customer_name=str(customer.get("party_name") or ""))
                    how = "with a secure 7-day download link" if result["method"] == "SECURE_LINK" else "with attachments"
                    if result["status"] == "FAILED":
                        st.error("The e-mail could not be sent (check Admin → Email Settings). The submission is logged as FAILED; retry from the Email Centre.")
                    else:
                        save_success_popup(f"PPAP package e-mailed to {', '.join(to)} {how} ({result['status'].title()}).", queue_for_rerun=True)
                        st.session_state[OPEN_REQUEST_KEY] = package_id
                        st.rerun()
                except Exception as exc:
                    st.error(db_message(exc))
        submissions = service.submissions(package_id)
        if submissions:
            st.markdown("**Submission / download log**")
            portal_table(pd.DataFrame([{
                "Date": dmy(s.get("submitted_at")), "To": s.get("sent_to"), "CC": s.get("cc_emails") or "", "Method": status_label(s.get("method")),
                "Documents": s.get("document_count"), "Revisions": ", ".join(f"{int(d.get('element_no') or 0):02d}:{d.get('revision')}" for d in (s.get("documents") or [])[:12]),
                "Status": s.get("status"), "By": s.get("sent_by_name") or "", "Link valid to": dmy(s.get("link_expires_at")),
            } for s in submissions]), hide_index=True, height=min(360, 80 + 36 * len(submissions)))


def _render_delete(repo: Repository, service: PpapService, perms: Mapping[str, bool], existing: Mapping[str, Any], documents: list[dict]) -> None:
    package_id = str(existing["id"])
    with stage_section("F", "DELETE PPAP PACKAGE", "Deletes the package with its elements, document register, notes and submission log. Current QCMS password is required.", key="ppap_package_f"):
        can_delete = bool(perms.get("can_archive"))
        password = st.text_input("Current QCMS password", type="password", key=f"ppap_del_pw_{package_id}", disabled=not can_delete)
        confirm = st.checkbox(f"I understand that PPAP package {existing.get('package_no')} will be permanently deleted.", key=f"ppap_del_ok_{package_id}", disabled=not can_delete)
        if st.button("Delete PPAP Package", key=f"ppap_del_btn_{package_id}", disabled=not (can_delete and confirm and password), width="stretch"):
            try:
                from core.auth import verify_current_password
                verify_current_password(password)
                for doc in documents:
                    try:
                        service._storage().remove([str(doc.get("object_path"))])
                    except Exception:
                        pass
                repo.delete("ppap_packages", package_id)
                st.session_state[SELECTOR_KEY] = ""
                save_success_popup(f"PPAP package {existing.get('package_no')} deleted.", queue_for_rerun=True)
                st.rerun()
            except Exception as exc:
                st.error(db_message(exc))
        if not can_delete:
            st.caption("PPAP archive (delete) permission is required.")


# ----------------------------------------------------------------------------- element templates
def render_ppap_templates() -> None:
    page_header("PPAP Element Templates", "Default element list for new packages and customer-specific templates (add / rename / reorder / department / lead days)")
    _nav_row(ROUTE_TEMPLATES)
    repo = Repository()
    perms = ppap_permissions()
    service = PpapService(repo)
    try:
        customers = repo.select("parties", contains={"party_types": ["CUSTOMER"]}, order_by="party_name", limit=3000) or []
        master = service.ensure_master() if perms["can_create"] or perms["can_edit"] else service.element_master()
        with_template = service.template_customers()
    except Exception as exc:
        st.error(db_message(exc))
        return
    customer_labels = {str(c["id"]): party_label(c) for c in customers}
    options = [""] + [cid for cid in with_template if cid in customer_labels]
    t1, t2, t3 = st.columns([2.4, 2.0, 1.2], gap="small", vertical_alignment="bottom")
    chosen = t1.selectbox("Template", options, key="ppap_template_select",
                          format_func=lambda v: "Default template (all customers)" if not v else f"Customer · {customer_labels.get(v, v)}")
    new_customer = t2.selectbox("New customer template (copy of the default)", [""] + [c for c in customer_labels if c not in with_template],
                                format_func=lambda v: "— Select customer —" if not v else customer_labels[v], key="ppap_template_new_customer")
    if t3.button("Create", key="ppap_template_create", disabled=not (perms["can_create"] and new_customer), width="stretch"):
        try:
            count = service.copy_template_to_customer(new_customer)
            st.session_state["ppap_template_select"] = new_customer
            save_success_popup(f"Customer template created with {count} element(s).", queue_for_rerun=True)
            st.rerun()
        except Exception as exc:
            st.error(db_message(exc))
    rows = sorted(service.customer_template(chosen) if chosen else master, key=template_sort_key)
    section_bar("PPAP ELEMENTS OF THE TEMPLATE",
                "'Required' = the element starts as Pending (else NA) · Lead days = due date of new packages (today + days) · "
                "Order = position in the package (reorder) · Department = default responsible department")
    departments = sorted(set(DEPARTMENTS) | {str(r.get("default_department")) for r in rows if r.get("default_department")})
    frame = pd.DataFrame([{
        "ID": str(m["id"]), "Order": int(template_sort_key(m)[0]), "No.": int(m.get("element_no") or 0), "Element": m.get("element_name") or "",
        "Description": m.get("description") or "", "Required": bool(m.get("default_required", True)), "Lead Days": int(m.get("default_lead_days") or 0),
        "Department": m.get("default_department") or default_department(m.get("element_no")), "Status": m.get("status") or "ACTIVE",
    } for m in rows], columns=["ID", "Order", "No.", "Element", "Description", "Required", "Lead Days", "Department", "Status"])
    edited = st.data_editor(frame, hide_index=True, width="stretch", num_rows="dynamic", height=min(900, 90 + 36 * max(1, len(frame))),
                            key=f"ppap_master_editor_{chosen or 'default'}", disabled=not perms["can_edit"],
                            column_config={"ID": None, "Order": st.column_config.NumberColumn(min_value=1, max_value=999, step=1, width="small"),
                                           "No.": st.column_config.NumberColumn(min_value=1, max_value=999, step=1, required=True, width="small"),
                                           "Element": st.column_config.TextColumn(required=True, width="large"),
                                           "Description": st.column_config.TextColumn(width="large"),
                                           "Required": st.column_config.CheckboxColumn(), "Lead Days": st.column_config.NumberColumn(min_value=0, step=1),
                                           "Department": st.column_config.SelectboxColumn(options=departments),
                                           "Status": st.column_config.SelectboxColumn(options=["ACTIVE", "INACTIVE"], required=True)})
    if st.button("Save Element Template", type="primary", key="ppap_master_save", disabled=not perms["can_edit"], width="stretch"):
        try:
            records = edited.to_dict("records") if hasattr(edited, "to_dict") else list(edited)

            def _num(value: Any, fallback: Any = None) -> Any:
                return fallback if value is None or value == "" or (isinstance(value, float) and pd.isna(value)) else value

            payload = [{"id": r.get("ID") if isinstance(r.get("ID"), str) else None, "element_no": _num(r.get("No.")),
                        "element_name": str(r.get("Element") or "").strip(), "description": r.get("Description") if isinstance(r.get("Description"), str) else "",
                        "default_required": bool(_num(r.get("Required"), True)), "default_lead_days": _num(r.get("Lead Days"), 0),
                        "default_department": _num(r.get("Department"), ""), "sort_order": _num(r.get("Order"), _num(r.get("No."))),
                        "status": r.get("Status") or "ACTIVE"} for r in records]
            payload.sort(key=lambda r: (float(r["sort_order"] or 0), float(r["element_no"] or 0)))
            counts = service.save_template(payload, customer_id=chosen or None)
            save_success_popup(f"PPAP element template saved ({counts['saved']} kept, {counts['added']} added, {counts['removed']} removed).", queue_for_rerun=True)
            st.rerun()
        except Exception as exc:
            st.error(db_message(exc))
