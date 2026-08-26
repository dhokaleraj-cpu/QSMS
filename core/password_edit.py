from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from core.auth import verify_current_password
from core.repository import Repository
from core.ui import save_success_popup


def password_reopen_for_edit(
    *,
    repo: Repository,
    table: str,
    record: Mapping[str, Any] | None,
    entity_type: str,
    can_edit: bool,
    key: str,
    title: str = "Edit Finalized Record",
) -> bool:
    """Password-controlled controlled-amendment entry point.

    A finalized/approved record is returned to DRAFT and its final approval is reset,
    so edits can be made by a user who has module Edit permission without requiring
    Administrator access.  The unlock itself is permanently recorded in the audit table.
    """
    row = dict(record or {})
    record_id = str(row.get("id") or "")
    status = str(row.get("status") or "DRAFT").upper()
    if not record_id or status in {"DRAFT", "NEW"}:
        return False

    with st.expander(title, expanded=False):
        st.caption(
            "Administrator access is not required. Your current QCMS password and module Edit permission are required. "
            "The record returns to Draft and must be validated/approved again after the amendment."
        )
        reason = st.text_input("Edit / Amendment Reason", key=f"{key}_reason")
        password = st.text_input("Current QCMS Password", type="password", key=f"{key}_password")
        unlock = st.button("Unlock for Controlled Edit", type="primary", width="stretch", disabled=not can_edit, key=f"{key}_unlock")
        if unlock:
            try:
                if not can_edit:
                    raise PermissionError("Edit permission is required for this module.")
                if not reason.strip():
                    raise ValueError("Enter the amendment reason before unlocking the record.")
                verify_current_password(password)
                repo.insert(
                    "qcms_password_edit_audit",
                    {
                        "entity_type": entity_type,
                        "entity_id": record_id,
                        "reason": reason.strip(),
                        "status_before": row.get("status"),
                        "disposition_before": row.get("disposition"),
                    },
                )
                payload: dict[str, Any] = {"status": "DRAFT"}
                # Final inspection/report decisions require fresh approval after amendment.
                if table in {"lab_tests", "inspection_reports", "rmtc_approvals"}:
                    payload.update(
                        {
                            "disposition": "PENDING",
                            "disposition_reason": f"Controlled amendment: {reason.strip()}",
                            "validated_by_employee_id": None,
                            "approved_by_employee_id": None,
                            "validated_at": None,
                            "decision_at": None,
                        }
                    )
                repo.update(table, record_id, payload)
                st.session_state[f"{key}_unlocked_id"] = record_id
                save_success_popup("Record unlocked for controlled editing. Re-validation / approval is required after saving.", queue_for_rerun=True)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    return False
