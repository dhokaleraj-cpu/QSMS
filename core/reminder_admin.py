"""R41 · Delete automatic e-mail reminders (qcms_notification_schedules).

Every automatic reminder / digest e-mail of QCMS is driven by one row of ``qcms_notification_schedules``:
the hourly ``qcms-overdue-notifier`` and ``qcms-supply-digest-notifier`` read the enabled rows, and the dedicated
reminder functions are gated by their schedule row as well:

* PO_CONFIRMATION_DAILY -> qcms-po-confirmation-reminder (needs the enabled row)
* PO_PENDING_APPROVAL   -> qcms-po-approval-overdue (R41: skipped when the row is deleted or disabled)
* PPAP_DOCUMENT_DUE     -> qcms-ppap-due-notifier (R41: skipped when the row is deleted or disabled)

So deleting a schedule row stops that reminder for the company. Only administrators may delete (RLS policy
``qcms_notification_schedules_admin``) and the user's current QCMS password is re-checked first, like every other
permanent delete in QCMS. Disabling (the "Enabled" switch) remains the reversible alternative.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping, Sequence

TABLE = "qcms_notification_schedules"

# Reminder functions that are controlled by one schedule row (shown to the user before deleting).
LINKED_FUNCTIONS: dict[str, str] = {
    "PO_CONFIRMATION_DAILY": "Supplier PO confirmation reminder e-mails",
    "PO_PENDING_APPROVAL": "PO approval overdue reminders to approvers (and the pending-approval digest)",
    "PPAP_DOCUMENT_DUE": "Daily PPAP element due / overdue reminders",
}


def schedule_label(row: Mapping[str, Any]) -> str:
    label = str(row.get("schedule_label") or row.get("schedule_key") or "Reminder")
    module = str(row.get("module_key") or "").replace("_", " ").title()
    state = "Enabled" if bool(row.get("enabled", True)) else "Disabled"
    return f"{label} · {module} · {state}" if module else f"{label} · {state}"


def impact_lines(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """Plain-language list of what stops when the selected schedules are deleted."""
    out: list[str] = []
    for row in rows:
        key = str(row.get("schedule_key") or "")
        text = f"{row.get('schedule_label') or key}: this automatic e-mail stops for everyone"
        extra = LINKED_FUNCTIONS.get(key)
        if extra:
            text += f" (also stops: {extra})"
        out.append(text)
    return out


def delete_schedules(
    repo: Any,
    ids: Sequence[str],
    password: str,
    *,
    verify: Callable[[str], None] | None = None,
) -> int:
    """Delete the selected reminder schedules after re-checking the current password. Returns the number deleted."""
    wanted = [str(i) for i in ids if str(i or "").strip()]
    if not wanted:
        raise ValueError("Select at least one automatic reminder to delete.")
    if not str(password or "").strip():
        raise ValueError("Enter your current QCMS password.")
    if verify is None:
        from core.auth import verify_current_password as verify  # lazy: keeps this module importable without a session
    verify(password)
    deleted = 0
    for schedule_id in wanted:
        repo.delete(TABLE, schedule_id)
        deleted += 1
    return deleted
