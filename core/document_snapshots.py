"""R36 · Document snapshots for reminder e-mail attachments.

The scheduled reminder e-mails are sent by Supabase Deno edge functions, which cannot
render the website's print-layout PDFs (those are produced in Python by
``NotificationService._generated_report``).  This module renders the current print
layout of a record and stores it as the record's *snapshot*:

* file: ``quality-documents/{tenant}/document_snapshots/{table}/{record_id}/{file_name}``
* row:  ``public.qcms_document_snapshots`` (one row per tenant + table + record + doc kind)

The edge functions attach the latest snapshot (when it is not older than the record).

Snapshots are refreshed
* in the background after every workflow notification (``NotificationService.enqueue``), and
* at most every 30 minutes per signed-in session for records referenced by pending
  reminders (RPC ``qcms_reminder_snapshot_targets``).

Nothing in this module ever raises to its callers: e-mail attachments are best effort and
must never block or roll back a business transaction or a page render.
"""
from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timezone
from typing import Any

BUCKET = "quality-documents"
# R36b: "PDF_SAFE" = customer-free print-layout PDF. Scheduled reminders also go to suppliers, so a snapshot never
# contains customer details (older "PDF" snapshots are no longer used).
DOC_KIND = "PDF_SAFE"
REFRESH_INTERVAL_SECONDS = 30 * 60
SESSION_KEY = "_qcms_r36_snapshot_refresh_at"

# Tables whose print-layout PDF NotificationService._generated_report can render.
SUPPORTED_TABLES = {
    "supply_purchase_orders",
    "supply_po_confirmations",
    "rmtc_approvals",
    "inspection_reports",
    "lab_tests",
    "quality_complaints",
    "inward_lots",
}

_inflight: set[tuple[str, str]] = set()
_inflight_lock = threading.Lock()


def _safe_name(value: Any, fallback: str = "QCMS_Document.pdf") -> str:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")).strip("_")
    if not name:
        return fallback
    return name if name.lower().endswith(".pdf") else f"{name}.pdf"


def _canonical(repo: Any, table: str, record_id: str) -> tuple[str, str]:
    """A PO confirmation prints the Purchase Order: store it as the PO's snapshot."""
    if table == "supply_po_confirmations":
        confirmation = repo.get("supply_po_confirmations", record_id) or {}
        po_id = str(confirmation.get("purchase_order_id") or "").strip()
        if po_id:
            return "supply_purchase_orders", po_id
    return table, record_id


def _latest(*values: Any) -> str | None:
    best: tuple[datetime, str] | None = None
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            continue
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        if best is None or moment > best[0]:
            best = (moment, text)
    return best[1] if best else None


def _record_updated_at(repo: Any, table: str, record_id: str) -> str | None:
    record = repo.get(table, record_id) or {}
    values: list[Any] = [record.get("updated_at"), record.get("created_at")]
    if table == "supply_purchase_orders":
        try:
            items = repo.select("supply_purchase_order_items", eq={"purchase_order_id": record_id}, limit=500)
        except Exception:
            items = []
        values.extend(item.get("updated_at") for item in items)
    return _latest(*values)


def _default_repo() -> Any:
    from core.repository import Repository

    return Repository()


def refresh(
    table: str,
    record_id: str,
    *,
    repo: Any | None = None,
    rendered: tuple[str, bytes] | None = None,
    record_updated_at: str | None = None,
) -> dict | None:
    """Render (or reuse ``rendered``) the record's print-layout PDF and store it as its snapshot.

    Returns the snapshot row, or None when nothing was stored. Never raises.
    """
    try:
        table = str(table or "").strip()
        record_id = str(record_id or "").strip()
        if table not in SUPPORTED_TABLES or not record_id:
            return None
        repo = repo or _default_repo()
        if getattr(repo, "preview", False) or getattr(repo, "client", None) is None:
            return None
        tenant_id = str(getattr(repo, "tenant_id", "") or "").strip()
        if not tenant_id:
            return None
        source_table, source_id = _canonical(repo, table, record_id)
        # (A PO confirmation renders exactly the Purchase Order PDF, so a supplied rendering is reused.)
        # Read the change marker BEFORE rendering: a change during rendering stays "outdated".
        changed_at = record_updated_at or _record_updated_at(repo, source_table, source_id)

        if rendered is None:
            from core.notification_service import NotificationService

            service = NotificationService(repo)
            service.customer_safe = True
            rendered = service._generated_report(source_table, source_id)
        if not rendered or not rendered[1]:
            return None
        file_name = _safe_name(rendered[0])
        content = bytes(rendered[1])
        path = f"{tenant_id}/document_snapshots/{source_table}/{source_id}/{file_name}"
        client = repo.client
        client.storage.from_(BUCKET).upload(path, content, {"content-type": "application/pdf", "upsert": "true"})
        now = datetime.now(timezone.utc).isoformat()
        row = {
            "tenant_id": tenant_id,
            "source_table": source_table,
            "record_id": source_id,
            "doc_kind": DOC_KIND,
            "bucket": BUCKET,
            "object_path": path,
            "file_name": file_name,
            "mime_type": "application/pdf",
            "size_bytes": len(content),
            "record_updated_at": changed_at,
            "generated_at": now,
            "updated_at": now,
        }
        response = client.table("qcms_document_snapshots").upsert(
            row, on_conflict="tenant_id,source_table,record_id,doc_kind"
        ).execute()
        data = getattr(response, "data", None) or [row]
        return dict(data[0])
    except Exception:
        return None


def refresh_pending(limit: int = 20, *, repo: Any | None = None) -> int:
    """Refresh missing/outdated snapshots of records referenced by pending reminders. Never raises."""
    try:
        repo = repo or _default_repo()
        if getattr(repo, "preview", False):
            return 0
        rows = repo.rpc("qcms_reminder_snapshot_targets", {"p_limit": int(limit)}) or []
        done = 0
        for row in rows if isinstance(rows, list) else []:
            if refresh(
                str(row.get("source_table") or ""),
                str(row.get("record_id") or ""),
                repo=repo,
                record_updated_at=row.get("record_updated_at"),
            ):
                done += 1
        return done
    except Exception:
        return 0


def _start_thread(target, *args: Any, **kwargs: Any) -> bool:
    """Daemon thread with the Streamlit script context attached (services read st.session_state)."""
    try:
        thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True, name="qcms-r36-snapshots")
        try:
            from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

            ctx = get_script_run_ctx()
            if ctx is not None:
                add_script_run_ctx(thread, ctx)
        except Exception:
            pass
        thread.start()
        return True
    except Exception:
        return False


def refresh_async(table: str, record_id: str, *, repo: Any | None = None, rendered: tuple[str, bytes] | None = None) -> bool:
    """Background ``refresh``; one in-flight refresh per record. Never raises or blocks."""
    try:
        table = str(table or "").strip()
        record_id = str(record_id or "").strip()
        if table not in SUPPORTED_TABLES or not record_id or repo is None or getattr(repo, "client", None) is None:
            return False
        key = (table, record_id)
        with _inflight_lock:
            if key in _inflight:
                return False
            _inflight.add(key)

        def run() -> None:
            try:
                refresh(table, record_id, repo=repo, rendered=rendered)
            finally:
                with _inflight_lock:
                    _inflight.discard(key)

        if not _start_thread(run):
            with _inflight_lock:
                _inflight.discard(key)
            return False
        return True
    except Exception:
        return False


def schedule_pending_refresh(limit: int = 20) -> bool:
    """Streamlit hook: at most every 30 minutes per session, refresh pending-reminder snapshots
    in a daemon thread. The repository (session client + tenant) is captured here, in the
    script thread. Never raises or blocks."""
    try:
        import streamlit as st

        now = time.time()
        last = float(st.session_state.get(SESSION_KEY) or 0)
        if now - last < REFRESH_INTERVAL_SECONDS:
            return False
        st.session_state[SESSION_KEY] = now
        repo = _default_repo()
        if getattr(repo, "preview", False) or getattr(repo, "client", None) is None or not getattr(repo, "tenant_id", ""):
            return False
        return _start_thread(refresh_pending, limit, repo=repo)
    except Exception:
        return False


def snapshot_summary(repo: Any | None = None) -> dict:
    """Count / last generated time for the Email Settings page. Never raises."""
    try:
        repo = repo or _default_repo()
        count = int(repo.count("qcms_document_snapshots", eq={"doc_kind": DOC_KIND}) or 0)
        latest = repo.select("qcms_document_snapshots", eq={"doc_kind": DOC_KIND}, order_by="generated_at", desc=True, limit=1)
        pending = repo.rpc("qcms_reminder_snapshot_targets", {"p_limit": 200}) or []
        return {
            "count": count,
            "last_generated_at": (latest[0].get("generated_at") if latest else None),
            "pending": len(pending) if isinstance(pending, list) else 0,
        }
    except Exception:
        return {"count": 0, "last_generated_at": None, "pending": None}
