from __future__ import annotations

from typing import Callable, Mapping, Sequence

import streamlit as st

from core.auth import verify_current_password
from core.config import is_preview_session
from core.repository import Repository
from core.ui import delete_success_popup

# R20: tables with a dedicated delete RPC that removes the record's OWN child rows
# (e.g. a PO with its lines, sources and stages) and blocks only on real genealogy.
DEDICATED_DELETE_RPCS = {
    "supply_purchase_orders": ("qcms_delete_purchase_order", "p_purchase_order_id"),
}


# Root transaction tables use the controlled transaction-delete RPC.
# Child/master rows that are not in this list continue through the master-row RPC.
TRANSACTION_DELETE_TABLES = {
    "supply_customer_orders", "supply_purchase_orders", "supply_po_confirmations",
    "supply_rm_purchase_orders", "supply_rm_receipts", "supply_rm_dispatches",
    "supply_forging_orders", "supply_forging_receipts", "supply_downstream_events",
    "supply_opening_stock", "osp_jobs", "osp_receipts", "rmtc_approvals",
    "inward_lots", "inspection_reports", "lab_tests", "npd_orders",
    "npd_process_flows", "ppap_projects", "pfd_headers", "pfmea_headers",
    "control_plan_headers", "spc_studies", "msa_studies", "capacity_studies",
    "qc_calculation_records", "quality_complaints",
    "quality_asset_part_process_links", "quality_asset_calibration_records",
    "standard_room_inspection_records",
}


def secure_delete(repo: Repository, table: str, record_id: str, password: str) -> None:
    """Delete one tenant-scoped row after current-password verification."""
    if not record_id:
        raise ValueError("Select a row to delete.")
    if is_preview_session():
        raise PermissionError("Deletion is disabled in controlled preview mode.")
    verify_current_password(password)
    run_delete(repo, table, record_id)


def _rpc_missing(exc: Exception) -> bool:
    text = str(exc).lower()
    return "pgrst202" in text or "could not find the function" in text or ("function" in text and "does not exist" in text)


def run_delete(repo: Repository, table: str, record_id: str) -> None:
    """Server-side delete: dedicated RPC first (R20), then the generic transaction/master RPC."""
    dedicated = DEDICATED_DELETE_RPCS.get(table)
    if dedicated:
        try:
            repo.rpc(dedicated[0], {dedicated[1]: record_id})
            return
        except Exception as exc:
            if not _rpc_missing(exc):
                raise
    if table in TRANSACTION_DELETE_TABLES:
        repo.rpc("qcms_delete_transaction_row", {"p_table_name": table, "p_record_id": record_id})
    else:
        repo.rpc("qsms_delete_master_row", {"p_table_name": table, "p_record_id": record_id})


def show_delete_blocked(repo: Repository, table: str, record_id: str, exc: Exception) -> None:
    """Explain a blocked delete and list the dependent transactions that hold the record."""
    import pandas as pd
    from core.record_history import linked_records

    st.error(f"Deletion blocked: {exc}")
    try:
        linked = linked_records(repo, table, record_id)
    except Exception:
        linked = []
    if linked:
        st.markdown(f"**Linked records holding this entry ({len(linked)})** — handle or delete these first:")
        st.dataframe(pd.DataFrame(linked), hide_index=True, width="stretch")
    else:
        st.caption("No linked rows are visible to your role. Ask an administrator to check the linked transactions.")


def linked_records_button(repo: Repository, table: str, record_id: str, key: str) -> None:
    """Optional pre-check: show what is linked to the selected record before deleting it."""
    import pandas as pd
    from core.record_history import linked_records

    if record_id and st.button("Check linked records", key=f"{key}_linked", icon=":material/account_tree:"):
        linked = linked_records(repo, table, record_id)
        if linked:
            st.dataframe(pd.DataFrame(linked), hide_index=True, width="stretch")
        else:
            st.success("No linked transactions found.")


def password_delete_panel(
    *,
    repo: Repository,
    table: str,
    rows: Sequence[Mapping],
    labeler: Callable[[Mapping], str],
    key: str,
    can_delete: bool,
    title: str = "Delete selected row",
    help_text: str = "Deletion is permanent and requires your current QCMS password.",
) -> bool:
    """Render a controlled delete panel and return True after deletion."""
    if not rows:
        return False
    with st.expander(title, expanded=False):
        st.caption(help_text)
        labels = {str(row.get("id")): labeler(row) for row in rows if row.get("id")}
        selected = st.selectbox(
            "Selected row",
            list(labels),
            format_func=lambda value: labels[value],
            key=f"{key}_row",
            disabled=not can_delete,
        )
        linked_records_button(repo, table, selected, key)
        password = st.text_input(
            "Current QCMS password",
            type="password",
            key=f"{key}_password",
            disabled=not can_delete,
        )
        confirm = st.checkbox(
            "I understand that this row will be permanently deleted.",
            key=f"{key}_confirm",
            disabled=not can_delete,
        )
        if st.button(
            "Delete selected row",
            type="primary",
            key=f"{key}_button",
            disabled=not can_delete or not confirm or not password,
            width="stretch",
        ):
            try:
                secure_delete(repo, table, selected, password)
            except Exception as exc:
                show_delete_blocked(repo, table, selected, exc)
                return False
            delete_success_popup("Selected row deleted successfully.", queue_for_rerun=True)
            return True
    return False


def password_rpc_delete_panel(
    *,
    repo: Repository,
    rpc_name: str,
    rpc_param: str,
    rows: Sequence[Mapping],
    labeler: Callable[[Mapping], str],
    key: str,
    can_delete: bool,
    title: str,
    help_text: str,
    success_message: str = "Selected transaction deleted successfully.",
) -> bool:
    """Password-confirm one controlled server-side delete that also reverses linked allocations."""
    if not rows:
        return False
    with st.expander(title, expanded=False):
        st.caption(help_text)
        labels = {str(row.get("id")): labeler(row) for row in rows if row.get("id")}
        selected = st.selectbox(
            "Selected row", list(labels), format_func=lambda value: labels[value],
            key=f"{key}_row", disabled=not can_delete,
        )
        password = st.text_input(
            "Current QCMS password", type="password", key=f"{key}_password", disabled=not can_delete,
        )
        confirm = st.checkbox(
            "I understand that this transaction will be permanently deleted and its controlled allocation will be reversed.",
            key=f"{key}_confirm", disabled=not can_delete,
        )
        if st.button(
            "Delete selected transaction", type="primary", key=f"{key}_button",
            disabled=not can_delete or not confirm or not password, width="stretch",
        ):
            if is_preview_session():
                raise PermissionError("Deletion is disabled in controlled preview mode.")
            try:
                verify_current_password(password)
                repo.rpc(rpc_name, {rpc_param: selected})
            except Exception as exc:
                st.error(f"Deletion blocked: {exc}")
                return False
            delete_success_popup(success_message, queue_for_rerun=True)
            return True
    return False


def password_transaction_delete_panel(
    *,
    repo: Repository,
    table: str,
    rows: Sequence[Mapping],
    labeler: Callable[[Mapping], str],
    key: str,
    can_delete: bool,
    title: str = "Delete transaction",
    help_text: str = "Deletion is permanent, audited and blocked when downstream genealogy exists.",
) -> bool:
    """Delete a root transaction through the unified module permission RPC."""
    if not rows:
        return False
    with st.expander(title, expanded=False):
        st.caption(help_text)
        labels = {str(row.get("id")): labeler(row) for row in rows if row.get("id")}
        selected = st.selectbox(
            "Selected transaction", list(labels), format_func=lambda value: labels[value],
            key=f"{key}_row", disabled=not can_delete,
        )
        linked_records_button(repo, table, selected, key)
        password = st.text_input(
            "Current QCMS password", type="password", key=f"{key}_password", disabled=not can_delete,
        )
        confirm = st.checkbox(
            "I confirm permanent deletion of this selected transaction.",
            key=f"{key}_confirm", disabled=not can_delete,
        )
        if st.button(
            "Delete selected transaction", type="primary", key=f"{key}_button",
            disabled=not can_delete or not confirm or not password, width="stretch",
        ):
            if is_preview_session():
                raise PermissionError("Deletion is disabled in controlled preview mode.")
            try:
                verify_current_password(password)
                run_delete(repo, table, selected)
            except Exception as exc:
                show_delete_blocked(repo, table, selected, exc)
                return False
            delete_success_popup("Selected transaction deleted successfully. The action is recorded in QCMS audit history.", queue_for_rerun=True)
            return True
    return False
