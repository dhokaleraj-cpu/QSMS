from __future__ import annotations

from typing import Callable, Mapping, Sequence

import streamlit as st

from core.auth import verify_current_password
from core.config import is_preview_session
from core.repository import Repository
from core.ui import delete_success_popup
from core.selection_labels import with_status
from core.delete_approval import approved_delete_controls, is_approved

# R20: tables with a dedicated delete RPC that removes the record's OWN child rows
# (e.g. a PO with its lines, sources and stages) and blocks only on real genealogy.
DEDICATED_DELETE_RPCS = {
    "supply_purchase_orders": ("qcms_delete_purchase_order", "p_purchase_order_id"),
    "supply_customer_orders": ("qcms_delete_customer_order", "p_customer_order_id"),
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

    message = clean_block_message(exc)
    if "downstream linked records" in message:
        message = "This record is still used by other transactions (listed below)."
    if "APPROVED_DELETE_BLOCKED" in message:
        st.error("This record is approved / released. Delete it through a deletion request - the Admin must approve it (Records → Deletion Requests).")
        return
    st.error(f"Deletion blocked: {message}")
    try:
        linked = linked_records(repo, table, record_id)
    except Exception:
        linked = []
    if linked:
        st.markdown(f"**Why it cannot be deleted — {len(linked)} linked record(s). Follow 'How to fix' in this order, then delete again:**")
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
            st.warning(f"{len(linked)} linked record(s) will block this delete:")
            st.dataframe(pd.DataFrame(linked), hide_index=True, width="stretch")
        else:
            st.success("Nothing blocks this delete.")


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
        labels = {str(row.get("id")): with_status(labeler(row), row) for row in rows if row.get("id")}
        selected = st.selectbox(
            "Selected row",
            list(labels),
            format_func=lambda value: labels[value],
            key=f"{key}_row",
            disabled=not can_delete,
        )
        linked_records_button(repo, table, selected, key)
        selected_row = next((r for r in rows if str(r.get("id")) == str(selected)), {})
        if is_approved(selected_row):
            approved_delete_controls(repo, table, selected_row, labels.get(str(selected), str(selected)), key=key, can_delete=can_delete)
            return False
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
        labels = {str(row.get("id")): with_status(labeler(row), row) for row in rows if row.get("id")}
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
                from core.db_errors import db_message
                st.error(f"Deletion blocked: {db_message(exc)}")
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
        labels = {str(row.get("id")): with_status(labeler(row), row) for row in rows if row.get("id")}
        selected = st.selectbox(
            "Selected transaction", list(labels), format_func=lambda value: labels[value],
            key=f"{key}_row", disabled=not can_delete,
        )
        linked_records_button(repo, table, selected, key)
        selected_row = next((r for r in rows if str(r.get("id")) == str(selected)), {})
        if is_approved(selected_row):
            approved_delete_controls(repo, table, selected_row, labels.get(str(selected), str(selected)), key=key, can_delete=can_delete)
            return False
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
                # R35: keep the "blocked" explanation + guided fix on screen across reruns.
                st.session_state[f"{key}_blocked"] = {"id": str(selected), "message": clean_block_message(exc)}
                st.session_state.pop(f"{key}_confirm", None)
            else:
                st.session_state.pop(f"{key}_blocked", None)
                delete_success_popup("Selected transaction deleted successfully. The action is recorded in QCMS audit history.", queue_for_rerun=True)
                return True
        blocked = st.session_state.get(f"{key}_blocked") or {}
        if blocked.get("id") == str(selected):
            render_delete_blocked(repo, table, str(selected), blocked.get("message", ""), key=key)
    return False


def clean_block_message(exc: object) -> str:
    """R35: never show a raw {'message': ..., 'code': 'P0001', ...} dict to the user."""
    import ast
    import re
    from core.db_errors import db_message
    message = db_message(exc)
    text = str(message or "")
    match = re.search(r"\{.*['\"]message['\"]\s*:.*\}", text, flags=re.S)
    if match:
        try:
            parsed = ast.literal_eval(match.group(0))
            if isinstance(parsed, dict) and parsed.get("message"):
                text = str(parsed["message"])
        except Exception:
            inner = re.search(r"['\"]message['\"]\s*:\s*(['\"])(.*?)\1", text, flags=re.S)
            if inner:
                text = inner.group(2)
    return text.strip()


def render_delete_blocked(repo: Repository, table: str, record_id: str, message: str, *, key: str) -> None:
    """R35: plain reason, the linked records, and a guided way out (Customer Order held by a PO)."""
    import pandas as pd
    from core.record_history import linked_records

    if "APPROVED_DELETE_BLOCKED" in message:
        st.error("This record is approved / released. Delete it through a deletion request - the Admin must approve it (Records → Deletion Requests).")
        return
    if "downstream linked records" in message or "downstream" in message.lower():
        st.error("This transaction cannot be deleted yet: other transactions still use it. Handle the linked records below first, then delete again.")
    else:
        st.error(f"Deletion blocked: {message}")
    try:
        linked = linked_records(repo, table, record_id)
    except Exception:
        linked = []
    if linked:
        st.markdown(f"**{len(linked)} linked record(s) — follow 'How to fix' in this order, then delete again:**")
        st.dataframe(pd.DataFrame(linked), hide_index=True, width="stretch")
    if table == "supply_customer_orders":
        _customer_order_po_fix(repo, record_id, key=key)


def _customer_order_po_fix(repo: Repository, customer_order_id: str, *, key: str) -> None:
    """Guided fix: take the Customer Order off the Purchase Order(s) that still hold it."""
    from core.access import current_permissions
    from core.supply_chain_service import SupplyChainService

    service = SupplyChainService(repo)
    try:
        holders = service.po_sources_for_customer_order(customer_order_id)
    except Exception:
        holders = []
    if not holders:
        return
    can_edit = bool(current_permissions("SUPPLY_CHAIN").get("can_edit"))
    st.markdown("**Purchase Orders holding this Customer Order**")
    for i, h in enumerate(holders):
        po = h.get("po") or {}; src = h.get("source") or {}
        approval = str(po.get("approval_status") or po.get("status") or "-").upper()
        status = str(po.get("status") or "-").upper()
        with st.container(border=True):
            st.markdown(f"PO **{po.get('po_number') or '-'}** · {str(po.get('po_type') or '').replace('_', ' ').title()} · Status **{status.replace('_', ' ')}** · Approval **{approval.replace('_', ' ')}** · Allocated {float(src.get('allocated_qty') or 0):,.3f} {src.get('allocation_uom') or ''}")
            pages = st.session_state.get("_qsms_pages", {})
            if st.button("Open this PO in Edit Purchase Order", key=f"{key}_open_po_{i}", icon=":material/edit_note:"):
                st.session_state["supply_po_edit_request_id"] = str(po.get("id") or "")
                if pages.get("supply-po-edit"):
                    st.switch_page(pages["supply-po-edit"])
            if status == "CANCELLED":
                st.caption("This PO is cancelled — the order is released automatically when the Customer Order is deleted.")
                continue
            if h.get("received_kg", 0) > 0 or h.get("received_pcs", 0) > 0:
                st.warning(f"Material is already received against this order on PO {po.get('po_number')} "
                           f"({h.get('received_kg', 0):,.3f} kg / {h.get('received_pcs', 0):,.0f} pcs). Genealogy is protected: reverse the RM Receipt / "
                           "Material Inward link or Forging Receipt first, then remove the order from the PO.")
                continue
            if int(h.get("other_orders") or 0) == 0:
                st.info(f"This is the only Customer Order on PO {po.get('po_number')}. Cancel or delete the whole PO (Supply Chain → Purchase Order List), then delete the Customer Order.")
                continue
            if approval == "APPROVED":
                st.warning("This PO is APPROVED. Removing the order revises the PO (totals recalculated) and sends it back for re-approval; the supplier must be informed of the amended PO.")
            reason = st.text_input("Reason for removing this order from the PO", key=f"{key}_rm_reason_{i}", disabled=not can_edit)
            password = st.text_input("Current QCMS password", type="password", key=f"{key}_rm_pwd_{i}", disabled=not can_edit)
            ok = st.checkbox(f"Remove Customer Order from PO {po.get('po_number')}" + (" and send the PO for re-approval" if approval == "APPROVED" else ""), key=f"{key}_rm_ok_{i}", disabled=not can_edit)
            if not can_edit:
                st.caption("Supply Chain Edit permission is needed to change a Purchase Order.")
            if st.button("Remove this order from the PO", key=f"{key}_rm_btn_{i}", type="primary", disabled=not (can_edit and ok and reason.strip() and password)):
                try:
                    verify_current_password(password)
                    result = service.remove_order_from_po(str(src.get("id")), reason)
                except Exception as exc:
                    st.error(clean_block_message(exc))
                else:
                    note = "" if result.get("recalculated", True) else " Open the PO in Edit Purchase Order and save once to recalculate its totals."
                    st.success(f"Customer Order removed from PO {result.get('po_number') or po.get('po_number')}. The PO returned to approval.{note} You can now delete the Customer Order.")
                    st.session_state.pop(f"{key}_blocked", None)
