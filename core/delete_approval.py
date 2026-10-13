"""QCMS R25 · Approved transactions are deleted only after Admin approval, and every deleted
record stays viewable / printable in the Deleted Records archive."""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Mapping, Sequence

from core.repository import Repository

APPROVED_STATUSES = {"APPROVED", "RELEASED", "FINAL", "CLOSED", "COMPLETED"}
SQL_HINT = "Admin-approved deletion needs the R25 database step: run QCMS_R25_RUN_IN_SUPABASE.sql once in Supabase SQL Editor."


def is_approved(row: Mapping[str, Any] | None) -> bool:
    """Python mirror of public.qcms_record_is_approved."""
    row = row or {}
    return (str(row.get("approval_status") or "").upper() == "APPROVED"
            or str(row.get("status") or "").upper() in APPROVED_STATUSES
            or str(row.get("confirmation_status") or "").upper() == "CONFIRMED")


def _missing(exc: Exception) -> bool:
    text = str(exc).lower()
    return "pgrst202" in text or "could not find the function" in text or "qcms_delete_requests" in text and "does not exist" in text


def request_delete(repo: Repository, table: str, record_id: str, reason: str, label: str = "") -> dict:
    try:
        row = repo.rpc("qcms_request_delete", {"p_table_name": table, "p_record_id": record_id, "p_reason": reason, "p_label": label})
    except Exception as exc:
        if _missing(exc):
            raise RuntimeError(SQL_HINT) from exc
        raise
    _notify_admins(repo, table, label, reason)
    return dict(row or {})


def decide(repo: Repository, request_id: str, approve: bool, note: str = "") -> dict:
    try:
        return dict(repo.rpc("qcms_decide_delete_request", {"p_request_id": request_id, "p_approve": bool(approve), "p_note": note or None}) or {})
    except Exception as exc:
        if _missing(exc):
            raise RuntimeError(SQL_HINT) from exc
        raise


def requests(repo: Repository, *, status: str | None = None, limit: int = 500) -> list[dict]:
    try:
        eq = {"status": status} if status else None
        return repo.select("qcms_delete_requests", eq=eq, order_by="requested_at", desc=True, limit=limit)
    except Exception:
        return []


def deleted_records(repo: Repository, *, table: str | None = None, date_from: date | None = None, date_to: date | None = None, limit: int = 1000) -> list[dict]:
    params = {"p_table_name": table or None, "p_from": date_from.isoformat() if date_from else None, "p_to": date_to.isoformat() if date_to else None, "p_limit": limit}
    try:
        rows = repo.rpc("qcms_deleted_records", params)
        if isinstance(rows, list):
            return [dict(r) for r in rows]
    except Exception:
        pass
    try:  # fallback before the R25 SQL (Admin / Quality Manager can read audit_log)
        eq = {"operation": "DELETE", **({"table_name": table} if table else {})}
        rows = repo.select("audit_log", eq=eq, order_by="changed_at", desc=True, limit=limit)
        return [{"audit_id": r.get("id"), "table_name": r.get("table_name"), "record_id": r.get("row_id"), "deleted_at": r.get("changed_at"),
                 "deleted_by": r.get("changed_by"), "deleted_by_name": "", "old_data": r.get("old_data")} for r in rows]
    except Exception:
        return []


def _notify_admins(repo: Repository, table: str, label: str, reason: str) -> None:
    try:
        admins = [r for r in repo.select("profiles", eq={"role": "ADMIN"}, limit=50) if "@" in str(r.get("email") or "")]
        if not admins:
            return
        from core.notification_service import NotificationService
        from core.record_history import table_label
        notifier = NotificationService(repo)
        row = notifier.enqueue(
            "DELETE_APPROVAL_REQUEST", recipient_email=str(admins[0]["email"]), recipient_name=admins[0].get("full_name"),
            cc_emails=[str(a["email"]) for a in admins[1:]],
            subject=f"QCMS · Deletion approval needed · {table_label(table)} {label}",
            body_text=f"A deletion request is waiting for Admin approval.\nRecord: {table_label(table)} {label}\nReason: {reason}\n\nOpen QCMS → Records → Deletion Requests to approve or reject.",
            include_generated_pdf=False, include_record_attachments=False, include_supplier=False,
        )
        if row:
            notifier.dispatch([row])
    except Exception:
        pass


# ------------------------------------------------------------------ printing
def _fmt_time(value: Any) -> str:
    text = str(value or "")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%d-%m-%Y %H:%M")
    except ValueError:
        return text[:16]


def _value(value: Any) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)[:400]
    return str(value)[:400]


def deleted_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    from core.record_history import record_reference, table_label
    data = row.get("old_data") if isinstance(row.get("old_data"), Mapping) else {}
    return {
        "Deleted At": _fmt_time(row.get("deleted_at")),
        "Record Type": table_label(str(row.get("table_name") or "")),
        "Reference": record_reference(data) if data else str(row.get("record_id") or "")[:8],
        "Status When Deleted": str((data or {}).get("approval_status") or (data or {}).get("status") or "-").replace("_", " "),
        "Deleted By": row.get("deleted_by_name") or "-",
        "Delete Reason": row.get("delete_reason") or "-",
        "Requested By": row.get("requested_by_name") or "-",
        "Approved By": row.get("approved_by_name") or "-",
    }


def deleted_record_pdf(row: Mapping[str, Any]) -> bytes:
    from core.record_history import HIDDEN_FIELDS, field_label
    from core.reporting import controlled_record_pdf_bytes
    summary = deleted_summary(row)
    data = dict(row.get("old_data") or {})
    fields = [{"Field": field_label(k), "Value at deletion": _value(v)} for k, v in data.items() if k not in {"tenant_id", "search_vector"}]
    return controlled_record_pdf_bytes(
        "DELETED RECORD", summary, {"RECORD DATA AT THE TIME OF DELETION": fields},
        record_number=str(summary["Reference"]), subtitle="QCMS deleted-record archive · audit evidence",
    )


def deleted_register_pdf(rows: Sequence[Mapping[str, Any]], title: str = "DELETED RECORDS REGISTER") -> bytes:
    from core.reporting import controlled_record_pdf_bytes
    table = [deleted_summary(r) for r in rows]
    return controlled_record_pdf_bytes(title, {"Records": len(table), "Printed": datetime.now().strftime("%d-%m-%Y %H:%M")},
                                       {"DELETED RECORDS": table or [{"Information": "No deleted records in this selection."}]},
                                       record_number="DELETED-REGISTER")


# ------------------------------------------------------------------ Streamlit UI
def approved_delete_controls(repo: Repository, table: str, row: Mapping[str, Any], label: str, *, key: str, can_delete: bool) -> None:
    """Shown instead of the delete button when the selected record is approved."""
    import streamlit as st
    from core.auth import current_profile, verify_current_password
    from core.db_errors import db_message
    from core.permissions import is_admin

    admin = is_admin(current_profile() or {})
    st.warning(f"**{label}** is approved / released. It can only be deleted after **Admin approval**. "
               "Send a deletion request with the reason; the Admin approves it in Records → Deletion Requests.")
    pending = [r for r in requests(repo, status="PENDING") if str(r.get("table_name")) == table and str(r.get("record_id")) == str(row.get("id"))]
    if pending:
        st.info(f"A deletion request is already waiting for Admin approval (sent {_fmt_time(pending[0].get('requested_at'))}).")
        if not admin:
            return
    reason = st.text_area("Reason for deletion (mandatory)", key=f"{key}_approved_reason", height=70, disabled=not can_delete)
    password = st.text_input("Current QCMS password", type="password", key=f"{key}_approved_password", disabled=not can_delete)
    c1, c2 = st.columns(2, gap="small")
    if not pending and c1.button("Send deletion request to Admin", type="primary", width="stretch", key=f"{key}_approved_request",
                                 disabled=not can_delete or not reason.strip() or not password, icon=":material/outgoing_mail:"):
        try:
            verify_current_password(password)
            request_delete(repo, table, str(row.get("id")), reason.strip(), label)
            st.success("Deletion request sent. The record stays until the Admin approves it.")
        except Exception as exc:
            st.error(db_message(exc))
    if admin and c2.button("Admin: approve & delete now", width="stretch", key=f"{key}_approved_admin",
                           disabled=not reason.strip() or not password, icon=":material/gavel:"):
        try:
            verify_current_password(password)
            request = pending[0] if pending else request_delete(repo, table, str(row.get("id")), reason.strip(), label)
            result = decide(repo, str(request.get("id")), True, f"Approved by Admin: {reason.strip()}")
            if str(result.get("status")) == "EXECUTED":
                st.success("Approved and deleted. The record is kept in Records → Deleted Records.")
            else:
                st.error(f"Deletion failed: {result.get('error') or result}")
        except Exception as exc:
            st.error(db_message(exc))
