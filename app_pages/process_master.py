from __future__ import annotations

import pandas as pd
import streamlit as st

from core.access import current_permissions
from core.delete_service import password_delete_panel
from core.master_definitions import MASTER_BY_KEY
from core.master_service import MasterService
from core.ui import page_header, section_bar


def _label(row: dict) -> str:
    return f"{row.get('process_code') or '-'} · {row.get('process_name') or '-'}"


def render_entry() -> None:
    page_header("Process Master · Entry")
    service = MasterService()
    definition = MASTER_BY_KEY["processes"]
    perms = current_permissions("REFERENCE_MASTERS")
    rows = service.list_records(definition, status="All")
    labels = {str(row["id"]): _label(row) for row in rows}
    requested = str(st.session_state.pop("edit_process_id", "") or "")
    options = ["__new__"] + list(labels)
    selected = st.selectbox(
        "Process Master record",
        options,
        index=options.index(requested) if requested in options else 0,
        format_func=lambda value: "＋ New Process" if value == "__new__" else labels[value],
    )
    existing = next((row for row in rows if str(row.get("id")) == selected), {})
    writable = perms["can_edit"] if existing else perms["can_create"]

    auto_key = "_qsms_auto_process_code"
    if not existing and not st.session_state.get(auto_key):
        try:
            st.session_state[auto_key] = service.next_master_code(definition)
        except Exception:
            st.session_state[auto_key] = ""

    section_bar("PROCESS DETAILS")
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
            if existing:
                service.repo.update("processes", str(existing["id"]), payload)
            else:
                service.repo.insert("processes", payload)
            st.session_state.pop(auto_key, None)
            st.success("Process Master saved.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    if existing and password_delete_panel(
        repo=service.repo,
        table="processes",
        rows=[existing],
        labeler=_label,
        key=f"delete_process_{existing.get('id')}",
        can_delete=perms["can_archive"],
        title="Delete Process Master",
        help_text="Permanent deletion requires the current QSMS password. Linked Process records cannot be deleted; deactivate them instead.",
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
        st.page_link(
            st.session_state["_qsms_pages"]["process-entry"],
            label="Open Selected Process",
            icon=":material/edit:",
            width="stretch",
        )
        if password_delete_panel(
            repo=service.repo,
            table="processes",
            rows=[selected_row],
            labeler=_label,
            key=f"delete_process_record_{selected}",
            can_delete=perms["can_archive"],
            title="Delete Selected Process",
            help_text="Permanent deletion requires the current QSMS password. Linked Process records cannot be deleted.",
        ):
            st.rerun()
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
    st.dataframe(frame, hide_index=True, width="stretch", height=620)
