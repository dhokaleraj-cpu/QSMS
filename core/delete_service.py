from __future__ import annotations

from typing import Callable, Mapping, Sequence

import streamlit as st

from core.auth import verify_current_password
from core.config import is_preview_session
from core.repository import Repository
from core.ui import delete_success_popup


def secure_delete(repo: Repository, table: str, record_id: str, password: str) -> None:
    """Delete one tenant-scoped row after current-password verification."""
    if not record_id:
        raise ValueError("Select a row to delete.")
    if is_preview_session():
        raise PermissionError("Deletion is disabled in controlled preview mode.")
    verify_current_password(password)
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
            secure_delete(repo, table, selected, password)
            delete_success_popup("Selected row deleted successfully.", queue_for_rerun=True)
            return True
    return False
