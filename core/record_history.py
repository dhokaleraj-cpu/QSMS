"""QCMS R20 · record status window (who created / changed a record and what changed)
and linked-record lookup used when a delete is blocked."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence

from core.dependency_map import FOREIGN_KEYS
from core.record_audit import _profile_labels, data_entry_status
from core.repository import Repository

REFERENCE_FIELDS = (
    "po_number", "inward_number", "rmtc_number", "master_reference_no", "supplier_order_no", "receipt_number",
    "receipt_no", "dispatch_number", "dispatch_no", "osp_job_number", "report_number", "inspection_number",
    "test_number", "complaint_number", "document_number", "confirmation_number", "fsi_part_number_snapshot",
    "item_no", "fsi_part_number", "part_number", "heat_number", "code", "party_name", "name", "title",
)
HIDDEN_FIELDS = {"id", "tenant_id", "created_at", "updated_at", "created_by", "updated_by", "search_vector"}

TABLE_LABELS = {
    "supply_purchase_orders": "Purchase Order", "supply_purchase_order_items": "PO Line",
    "supply_purchase_order_sources": "PO Customer Order Source", "supply_rm_purchase_orders": "RM Procurement Stage",
    "supply_forging_orders": "Forging Order Stage", "supply_po_confirmations": "PO Confirmation",
    "supply_rm_receipts": "RM Receipt", "supply_rm_dispatches": "RM Dispatch", "supply_forging_receipts": "Forging Receipt",
    "supply_customer_orders": "Customer Order", "supply_downstream_events": "Downstream Event", "inward_lots": "Material Inward",
    "rmtc_approvals": "RMTC", "inspection_reports": "Inspection Report", "lab_tests": "MetLAB Test", "osp_jobs": "OSP Job",
    "osp_receipts": "OSP Receipt", "part_supplier_price_history": "Price History", "parts": "Part Master",
    "parties": "Party Master", "quality_complaints": "Quality Complaint",
}


def table_label(table: str) -> str:
    return TABLE_LABELS.get(table) or table.replace("supply_", "").replace("_", " ").title()


def record_reference(row: Mapping[str, Any]) -> str:
    for key in REFERENCE_FIELDS:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return str(row.get("id") or "")[:8]


def children_of(table: str) -> list[tuple[str, str]]:
    """(child_table, column) pairs that reference *table* in the live schema."""
    return [(child, column) for child, column, parent in FOREIGN_KEYS if parent == table]


def linked_records(repo: Repository, table: str, record_id: str, *, per_table: int = 50) -> list[dict[str, Any]]:
    """List every row that points at the record, with reference, status and user."""
    found: list[dict[str, Any]] = []
    if not record_id:
        return found
    for child, column in children_of(table):
        try:
            rows = repo.select(child, eq={column: record_id}, limit=per_table)
        except Exception:
            continue
        for row in rows:
            if child == table and str(row.get("id")) == str(record_id):
                continue
            found.append({"_table": child, "_column": column, **dict(row)})
    labels = _profile_labels(repo, [str(r.get("created_by") or "") for r in found])
    out = []
    for row in found:
        creator = str(row.get("created_by") or "")
        out.append({
            "Linked Transaction": table_label(row["_table"]),
            "Reference": record_reference(row),
            "Status": data_entry_status(row),
            "Created By": labels.get(creator, creator or "System / Legacy"),
            "Created At": _short_time(row.get("created_at")),
            "Link Field": row["_column"],
        })
    return out


def _short_time(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%d-%b-%Y %H:%M")
    except ValueError:
        return text[:16]


def _display(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, default=str)
        return text if len(text) <= 80 else text[:77] + "…"
    text = str(value)
    return text if len(text) <= 80 else text[:77] + "…"


def changed_fields(old: Mapping[str, Any] | None, new: Mapping[str, Any] | None) -> list[tuple[str, Any, Any]]:
    old = dict(old or {}); new = dict(new or {})
    keys = [k for k in dict.fromkeys([*old.keys(), *new.keys()]) if k not in HIDDEN_FIELDS]
    return [(k, old.get(k), new.get(k)) for k in keys if old.get(k) != new.get(k)]


def field_label(name: str) -> str:
    return name.replace("_id", "").replace("_", " ").strip().title()


def record_history(repo: Repository, table: str, record_id: str, limit: int = 200) -> list[dict[str, Any]]:
    """Audit events newest first. Uses the R20 RPC (works for module viewers), falls back to audit_log."""
    if not record_id:
        return []
    events: Any = None
    try:
        events = repo.rpc("qcms_record_history", {"p_table_name": table, "p_row_id": record_id, "p_limit": limit})
    except Exception:
        events = None
    if not isinstance(events, list):
        try:
            rows = repo.select("audit_log", eq={"table_name": table, "row_id": record_id}, order_by="changed_at", desc=True, limit=limit)
        except Exception:
            rows = []
        labels = _profile_labels(repo, [str(r.get("changed_by") or "") for r in rows])
        events = [{**r, "changed_by_name": labels.get(str(r.get("changed_by") or ""), "System")} for r in rows]
    return [dict(e) for e in events if isinstance(e, Mapping)]


def history_rows(events: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Flatten audit events into a readable timeline: one row per changed field."""
    out: list[dict[str, str]] = []
    for event in events:
        op = str(event.get("operation") or "").upper()
        action = {"INSERT": "Created", "UPDATE": "Edited", "DELETE": "Deleted"}.get(op, op.title() or "Changed")
        who = str(event.get("changed_by_name") or event.get("changed_by") or "System")
        when = _short_time(event.get("changed_at"))
        if op == "INSERT":
            out.append({"When": when, "User": who, "Action": action, "Field": "—", "Old Value": "—", "New Value": "Record created"})
            continue
        if op == "DELETE":
            out.append({"When": when, "User": who, "Action": action, "Field": "—", "Old Value": "Record deleted", "New Value": "—"})
            continue
        diffs = changed_fields(event.get("old_data"), event.get("new_data"))
        if not diffs:
            out.append({"When": when, "User": who, "Action": action, "Field": "—", "Old Value": "—", "New Value": "Saved (no field change)"})
        for name, old, new in diffs:
            out.append({"When": when, "User": who, "Action": action, "Field": field_label(name), "Old Value": _display(old), "New Value": _display(new)})
    return out


def status_summary(row: Mapping[str, Any], events: Sequence[Mapping[str, Any]], labels: Mapping[str, str] | None = None) -> dict[str, str]:
    labels = dict(labels or {})
    creates = [e for e in events if str(e.get("operation") or "").upper() == "INSERT"]
    edits = [e for e in events if str(e.get("operation") or "").upper() == "UPDATE"]
    created_by = str(row.get("created_by") or "")
    created_name = (creates[-1].get("changed_by_name") if creates else None) or labels.get(created_by) or created_by or "System / Legacy"
    last = edits[0] if edits else None
    return {
        "Status": data_entry_status(row),
        "Created By": str(created_name),
        "Created At": _short_time(row.get("created_at") or (creates[-1].get("changed_at") if creates else "")),
        "Last Edited By": str((last or {}).get("changed_by_name") or "—"),
        "Last Edited At": _short_time((last or {}).get("changed_at")) or "—",
        "Edits": str(len(edits)),
        "Users Involved": str(len({str(e.get("changed_by_name") or e.get("changed_by")) for e in events})),
    }


def record_history_panel(repo: Repository, table: str, row: Mapping[str, Any] | None, *, key: str, expanded: bool = False) -> None:
    """Render the status window for one record (Streamlit)."""
    import pandas as pd
    import streamlit as st

    if not row or not row.get("id"):
        return
    with st.expander(f"Status window · {table_label(table)} {record_reference(row)}", expanded=expanded, icon=":material/history:"):
        events = record_history(repo, table, str(row.get("id")))
        labels = _profile_labels(repo, [str(row.get("created_by") or ""), str(row.get("updated_by") or "")])
        summary = status_summary(row, events, labels)
        cols = st.columns(4)
        for col, name in zip(cols, ("Status", "Created By", "Last Edited By", "Edits")):
            col.metric(name, summary[name])
        st.caption(f"Created {summary['Created At'] or '—'} · Last edited {summary['Last Edited At']} · {summary['Users Involved']} user(s)")
        timeline = history_rows(events)
        if timeline:
            st.dataframe(pd.DataFrame(timeline), hide_index=True, width="stretch", key=f"{key}_history")
        else:
            st.info("No audit entries yet for this record.")
