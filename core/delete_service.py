from __future__ import annotations

from typing import Callable, Mapping, Sequence

import streamlit as st

from core.auth import verify_current_password
from core.config import is_preview_session
from core.repository import Repository
from core.ui import delete_success_popup


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
    if table in TRANSACTION_DELETE_TABLES:
        repo.rpc("qcms_delete_transaction_row", {"p_table_name": table, "p_record_id": record_id})
    else:
        repo.rpc("qsms_delete_master_row", {"p_table_name": table, "p_record_id": record_id})


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
                st.error(f"Deletion blocked: {exc}")
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
                repo.rpc("qcms_delete_transaction_row", {"p_table_name": table, "p_record_id": selected})
            except Exception as exc:
                st.error(f"Deletion blocked: {exc}")
                return False
            delete_success_popup("Selected transaction deleted successfully. The action is recorded in QCMS audit history.", queue_for_rerun=True)
            return True
    return False
