"""R36 · STAWN Developer Console section: purge TRIAL / TEST data with every linked record.

Only the STAWN developer login sees this (checked here and again in the database functions)."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from core import dev_purge_service as purge
from core import licence_service as lic
from core.db_errors import db_message
from core.repository import Repository
from core.ui import portal_table, save_success_popup, section_bar, stage_section

_STATE = "qcms_dev_purge_preview"
_RESULT = "qcms_dev_purge_result"


def _selection_key(table: str, ids: list[str]) -> str:
    return f"{table}:{','.join(sorted(ids))}"


def _purge_panel(repo: Repository) -> None:
    last = st.session_state.get(_RESULT)
    if last:
        st.success(f"Last purge removed {last.get('total_deleted', 0)} row(s) and {last.get('storage_removed', 0)} file(s).")
        counts = last.get("deleted_counts") or {}
        if counts:
            portal_table(pd.DataFrame([{"Table": k, "Rows deleted": v} for k, v in sorted(counts.items())]))
        for problem in last.get("storage_problems") or []:
            st.warning(f"File removal: {problem}")

    module = st.selectbox("Transaction module", list(purge.MODULES), key="qcms_dev_purge_module")
    table = purge.module_table(module)
    c1, c2, c3 = st.columns(3, gap="small")
    use_dates = c1.checkbox("Filter by date", value=False, key="qcms_dev_purge_use_dates")
    date_from = c2.date_input("From", value=date.today() - timedelta(days=30), key="qcms_dev_purge_from", disabled=not use_dates)
    date_to = c3.date_input("To", value=date.today(), key="qcms_dev_purge_to", disabled=not use_dates)
    try:
        all_rows = purge.list_records(repo, module, date_from=date_from if use_dates else None, date_to=date_to if use_dates else None)
    except Exception as exc:
        st.error(db_message(exc))
        all_rows = []
    f1, f2 = st.columns(2, gap="small")
    creators = sorted({r["Created By"] for r in all_rows if r.get("Created By")})
    created_by = f1.selectbox("Created by", ["All", *creators], key="qcms_dev_purge_creator")
    text = f2.text_input("Search (reference, part, party, status)", key="qcms_dev_purge_text")
    rows = [r for r in all_rows if (created_by == "All" or r.get("Created By") == created_by)]
    if text.strip():
        needle = text.strip().lower()
        rows = [r for r in rows if needle in " ".join(str(v) for v in r.values()).lower()]

    if not rows:
        st.info("No records match the filters.")
        return
    portal_table(pd.DataFrame(rows).drop(columns=["id"]).head(300), height=min(420, 46 + 34 * min(len(rows), 12)))
    st.caption(f"{len(rows)} record(s) shown.")
    labels = {purge.record_label(r): r["id"] for r in rows}
    picked = st.multiselect("Records to purge", list(labels), key=f"qcms_dev_purge_pick_{table}")
    ids = [labels[p] for p in picked]
    sel_key = _selection_key(table, ids)

    if st.button("Preview everything that will be deleted", type="secondary", disabled=not ids, key="qcms_dev_purge_preview_btn",
                 icon=":material/account_tree:"):
        try:
            result = purge.preview(repo, table, ids, include_rows=True)
            backup = purge.backup_workbook(result)
            st.session_state[_STATE] = {"key": sel_key, "table": table, "ids": ids, "result": result, "backup": backup}
        except Exception as exc:
            st.session_state.pop(_STATE, None)
            st.error(db_message(exc))

    state = st.session_state.get(_STATE)
    if not state or state.get("key") != sel_key:
        if ids:
            st.caption("Run the preview for the current selection before deleting.")
        return
    result = state["result"]
    summary = purge.summary_rows(result)
    st.markdown(f"**{result.get('total_rows', 0)} row(s) in {len(summary)} table(s) will be deleted.**")
    portal_table(pd.DataFrame(summary))
    tables = [s["Table"] for s in summary]
    if tables:
        show = st.selectbox("Show records of", tables, key="qcms_dev_purge_sample_table")
        samples = purge.sample_rows(result, show)
        if samples:
            portal_table(pd.DataFrame(samples).drop(columns=["id"]))
            st.caption("Up to 50 records per table are listed here; the Excel backup contains every row.")
    for item in result.get("nullify") or []:
        st.info(f"{item.get('count')} {item.get('table')} row(s) stay; their link {item.get('column')} → {item.get('references')} is cleared.")
    blockers = result.get("blockers") or []
    for item in blockers:
        st.error(f"Blocked: {item.get('count')} master row(s) in {item.get('table')}.{item.get('column')} require these records.")
    if result.get("depth_limit_reached"):
        st.error("The linked chain is too deep (or loops). Purge a lower-level transaction first.")
    paths = result.get("storage_paths") or []
    if paths:
        st.caption(f"{len(paths)} stored file(s) will also be removed from the document store.")

    st.download_button("Download Excel backup (all rows)", state["backup"],
                       file_name=f"STAWN_QCMS_trial_purge_backup_{table}_{date.today():%Y%m%d}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       key="qcms_dev_purge_backup", icon=":material/download:")

    st.markdown("**Confirm permanent deletion**")
    confirm = st.text_input(f"Type {purge.CONFIRM_PHRASE}", key="qcms_dev_purge_confirm")
    reason = st.text_area("Reason (mandatory)", key="qcms_dev_purge_reason", height=80)
    password = st.text_input("Your current QCMS password", type="password", key="qcms_dev_purge_password")
    agree = st.checkbox("I downloaded the backup. These records are trial / test data and must be deleted with everything linked.",
                        key="qcms_dev_purge_agree")
    ready = (confirm.strip() == purge.CONFIRM_PHRASE and len(reason.strip()) >= 5 and bool(password) and agree
             and not blockers and not result.get("depth_limit_reached"))
    if st.button("Delete trial data permanently", type="primary", disabled=not ready, key="qcms_dev_purge_execute_btn",
                 icon=":material/delete_forever:"):
        try:
            out = purge.execute(repo, state["table"], state["ids"], confirm=confirm, reason=reason, password=password)
        except Exception as exc:
            st.error(db_message(exc))
        else:
            st.session_state.pop(_STATE, None)
            st.session_state[_RESULT] = out
            save_success_popup(f"Trial data purged: {out.get('total_deleted', 0)} row(s) deleted.", queue_for_rerun=True)
            st.rerun()


def render_section() -> None:
    status = lic.licence_status()
    if not status.get("is_stawn_developer"):
        st.error("Trial-data purge is only available to the STAWN developer login.")
        return

    repo = Repository()
    section_bar("TRIAL / TEST DATA PURGE")
    st.caption("Deletes the selected trial transactions together with EVERY record linked to them (lines, receipts, "
               "inwards, reports, attachments, notifications …) in this company only. Master data (parts, parties, grades, "
               "processes, employees, layouts) is never deleted. Every row is archived before it is removed.")

    with stage_section("H", "PURGE TRIAL / TEST DATA (STAWN DEVELOPER ONLY)",
                       "1 choose records · 2 preview everything linked · 3 download the Excel backup · 4 confirm", key="qcms_dev_purge"):
        _purge_panel(repo)

    with stage_section("I", "PREVIOUS TRIAL-DATA PURGES", key="qcms_dev_purge_runs"):
        runs = purge.recent_runs(repo)
        if runs:
            portal_table(pd.DataFrame(runs))
        else:
            st.info("No purge has been run yet.")
