from __future__ import annotations

from typing import Any, Mapping

from core.database import get_session_client
from core.repository import Repository


class NotificationService:
    """QCMS workflow e-mail outbox and responsibility routing.

    Transactions never fail because SMTP is unavailable. The notification is first
    written to the controlled outbox and then a best-effort Edge Function delivery is
    attempted. Failed messages remain available to the Administrator for retry.
    """

    def __init__(self, repo: Repository | None = None) -> None:
        self.repo = repo or Repository()

    def route(self, event_key: str) -> dict | None:
        rows = self.repo.select(
            "qcms_notification_routes",
            eq={"event_key": str(event_key).upper(), "enabled": True},
            limit=1,
        )
        return rows[0] if rows else None

    def recipient_for_route(self, route: Mapping[str, Any]) -> tuple[str, str]:
        employee_id = str(route.get("employee_id") or "").strip()
        if employee_id:
            employee = self.repo.get("employees", employee_id) or {}
            email = str(employee.get("email") or "").strip()
            name = " ".join(
                v for v in (str(employee.get("first_name") or "").strip(), str(employee.get("last_name") or "").strip()) if v
            )
            if email:
                return email, name or str(employee.get("employee_code") or "")
        return str(route.get("fallback_email") or "").strip(), str(route.get("route_label") or "").strip()

    def enqueue(
        self,
        event_key: str,
        *,
        subject: str | None = None,
        body_text: str,
        related_table: str | None = None,
        related_id: str | None = None,
        context: Mapping[str, Any] | None = None,
        recipient_email: str | None = None,
        recipient_name: str | None = None,
    ) -> dict | None:
        event = str(event_key or "").strip().upper()
        if not event:
            return None
        route = self.route(event)
        if not route and not recipient_email:
            return None
        email, name = (recipient_email or "").strip(), (recipient_name or "").strip()
        if not email and route:
            email, name = self.recipient_for_route(route)
        if not email:
            return None
        final_subject = str(subject or (route or {}).get("subject_template") or f"QCMS · {event.replace('_', ' ').title()}").strip()
        return self.repo.insert(
            "qcms_notification_outbox",
            {
                "event_key": event,
                "recipient_email": email,
                "recipient_name": name or None,
                "subject": final_subject,
                "body_text": str(body_text or "").strip(),
                "related_table": related_table or None,
                "related_id": related_id or None,
                "context": dict(context or {}),
                "status": "PENDING",
            },
        )

    @staticmethod
    def _invoke(outbox_ids: list[str]) -> dict:
        if not outbox_ids:
            return {"processed": 0}
        client = get_session_client()
        if client is None:
            return {"processed": 0, "message": "Preview mode"}
        response = client.functions.invoke(
            "qcms-send-email",
            invoke_options={"body": {"outbox_ids": outbox_ids}},
        )
        data = getattr(response, "data", response)
        if isinstance(data, bytes):
            import json
            return json.loads(data.decode("utf-8"))
        return dict(data or {}) if isinstance(data, Mapping) else {"result": data}

    def dispatch(self, rows: list[Mapping[str, Any]]) -> dict:
        ids = [str(row.get("id")) for row in rows if row.get("id")]
        try:
            return self._invoke(ids)
        except Exception as exc:
            # Delivery failure must not roll back the business transaction. The outbox
            # stays PENDING/FAILED and is visible from Email Server & Notifications.
            return {"processed": 0, "error": str(exc)}

    def notify(self, event_key: str, **kwargs: Any) -> dict | None:
        # Workflow execution must never be rolled back or shown as failed merely
        # because notification routing / SMTP is temporarily unavailable.
        try:
            row = self.enqueue(event_key, **kwargs)
            if row:
                self.dispatch([row])
            return row
        except Exception:
            return None

    def retry_pending(self, *, limit: int = 50) -> dict:
        pending = self.repo.select("qcms_notification_outbox", eq={"status": "PENDING"}, order_by="created_at", limit=limit)
        failed = self.repo.select("qcms_notification_outbox", eq={"status": "FAILED"}, order_by="created_at", limit=limit)
        rows = (pending + failed)[:limit]
        return self.dispatch(rows)
