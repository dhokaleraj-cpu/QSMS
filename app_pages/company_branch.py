from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.branch_context import branch_label
from core.repository import Repository
from core.ui import page_header, portal_table, save_success_popup, section_bar, subpage_navigation


def _norm(value: object) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def _rows(repo: Repository) -> list[dict]:
    return repo.select("company_branches", order_by="branch_code", limit=1000)


def _assert_duplicate(rows: list[dict], payload: dict, record_id: str | None) -> None:
    code = _norm(payload.get("branch_code")); name = _norm(payload.get("branch_name"))
    for row in rows:
        if record_id and str(row.get("id")) == str(record_id):
            continue
        if code and _norm(row.get("branch_code")) == code:
            raise ValueError("Duplicate Company Branch Code is not allowed.")
        if name and _norm(row.get("branch_name")) == name:
            raise ValueError("Duplicate Company Branch Name is not allowed.")


def render_entry() -> None:
    subpage_navigation(("masters", "Masters", ":material/dataset:"), ("company-branch-records", "Branch Records", ":material/table_view:"))
    page_header("Company Branch Master", context="Reusable company / plant / address identity")
    repo = Repository(); perms = current_permissions("REFERENCE_MASTERS")
    rows = _rows(repo)
    labels = {str(r["id"]): branch_label(r) for r in rows}
    options = [""] + list(labels)
    selected = st.selectbox("New / Edit Company Branch", options, format_func=lambda v: "— New Company Branch —" if not v else labels[v], key="company_branch_edit_select")
    existing = repo.get("company_branches", selected) if selected else None
    writable = perms["can_edit"] if existing else perms["can_create"]

    section_bar("COMPANY / BRANCH IDENTITY", "This master is reusable throughout QCMS. The logged-in employee Plant resolves to this Branch, and Purchase Orders use it for issuing-branch and Ship-To data.")
    with st.form(f"company_branch_form_{selected or 'new'}"):
        c = st.columns(4, gap="small")
        branch_code = c[0].text_input("Branch Code", value=str((existing or {}).get("branch_code") or ""), placeholder="D9")
        plant_code = c[1].text_input("Plant Code", value=str((existing or {}).get("plant_code") or ""), placeholder="D9")
        branch_name = c[2].text_input("Branch Name", value=str((existing or {}).get("branch_name") or ""), placeholder="Four Star Industries - D9")
        status = c[3].selectbox("Status", ["ACTIVE", "INACTIVE"], index=0 if str((existing or {}).get("status") or "ACTIVE") == "ACTIVE" else 1)
        is_default = st.checkbox("Default Company Branch", value=bool((existing or {}).get("is_default", False)), help="Used when the logged-in Employee Master Plant does not map to a Branch Code / Plant Code.")
        c = st.columns(3, gap="small")
        address1 = c[0].text_input("Address Line 1", value=str((existing or {}).get("address_line1") or ""))
        address2 = c[1].text_input("Address Line 2", value=str((existing or {}).get("address_line2") or ""))
        address3 = c[2].text_input("Address Line 3", value=str((existing or {}).get("address_line3") or ""))
        c = st.columns(4, gap="small")
        city = c[0].text_input("City", value=str((existing or {}).get("city") or ""))
        state = c[1].text_input("State", value=str((existing or {}).get("state") or ""))
        postal_code = c[2].text_input("Postal Code", value=str((existing or {}).get("postal_code") or ""))
        country = c[3].text_input("Country", value=str((existing or {}).get("country") or "India"))
        c = st.columns(4, gap="small")
        gstin = c[0].text_input("GSTIN / Tax ID", value=str((existing or {}).get("gstin") or ""))
        contact_person = c[1].text_input("Contact Person", value=str((existing or {}).get("contact_person") or ""))
        phone = c[2].text_input("Phone", value=str((existing or {}).get("phone") or ""))
        email = c[3].text_input("Email", value=str((existing or {}).get("email") or ""))
        remarks = st.text_area("Remarks", value=str((existing or {}).get("remarks") or ""), height=70)
        save = st.form_submit_button("Save Company Branch", type="primary", width="stretch", disabled=not writable)
    if save:
        try:
            if not branch_code.strip() or not branch_name.strip():
                raise ValueError("Branch Code and Branch Name are required.")
            payload = {
                "branch_code": branch_code.strip().upper(), "plant_code": plant_code.strip().upper() or branch_code.strip().upper(),
                "branch_name": branch_name.strip(), "address_line1": address1.strip() or None, "address_line2": address2.strip() or None,
                "address_line3": address3.strip() or None, "city": city.strip() or None, "state": state.strip() or None,
                "postal_code": postal_code.strip() or None, "country": country.strip() or None, "gstin": gstin.strip() or None,
                "contact_person": contact_person.strip() or None, "phone": phone.strip() or None, "email": email.strip().lower() or None,
                "is_default": bool(is_default), "status": status, "remarks": remarks.strip() or None,
            }
            _assert_duplicate(rows, payload, str((existing or {}).get("id") or "") or None)
            if is_default:
                for row in rows:
                    if bool(row.get("is_default")) and str(row.get("id")) != str((existing or {}).get("id") or ""):
                        repo.update("company_branches", str(row["id"]), {"is_default": False})
            saved = repo.update("company_branches", str(existing["id"]), payload) if existing else repo.insert("company_branches", payload)
            st.session_state.pop("_qcms_current_company_branch", None)
            st.session_state["company_branch_edit_select"] = str(saved.get("id") or "")
            save_success_popup("Company Branch saved successfully.", queue_for_rerun=True)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def render_records() -> None:
    subpage_navigation(("masters", "Masters", ":material/dataset:"), ("company-branch-entry", "New / Edit", ":material/edit_note:"))
    page_header("Company Branch Records", context="Reusable branch / plant / Ship-To master")
    repo = Repository(); rows = _rows(repo)
    search = st.text_input("Search Branch / Plant / Address")
    filtered = []
    for row in rows:
        text = " ".join(str(row.get(k) or "") for k in ("branch_code", "plant_code", "branch_name", "address_line1", "city", "state", "gstin", "email"))
        if not search or search.casefold() in text.casefold():
            filtered.append(row)
    frame = pd.DataFrame([{
        "Branch Code": r.get("branch_code"), "Plant Code": r.get("plant_code"), "Branch Name": r.get("branch_name"),
        "Address": ", ".join(v for v in (r.get("address_line1"), r.get("address_line2"), r.get("address_line3")) if v),
        "City": r.get("city"), "State": r.get("state"), "GSTIN": r.get("gstin"), "Phone": r.get("phone"), "Email": r.get("email"),
        "Default": bool(r.get("is_default")), "Status": r.get("status"),
    } for r in filtered])
    portal_table(frame, hide_index=True, width="stretch", height=min(580, 100 + len(frame) * 36))
    if rows:
        labels = {str(r["id"]): branch_label(r) for r in rows}
        selected = st.selectbox("Select Branch to Edit", list(labels), format_func=lambda v: labels[v])
        if st.button("Edit Selected Company Branch", type="primary", width="stretch"):
            st.session_state["company_branch_edit_select"] = selected
            st.switch_page(st.session_state["_qsms_pages"]["company-branch-entry"])
