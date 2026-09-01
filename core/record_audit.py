from __future__ import annotations

from typing import Any, Mapping, Sequence

from core.repository import Repository


def _profile_labels(repo: Repository, ids: Sequence[str]) -> dict[str, str]:
    wanted = {str(value or "").strip() for value in ids if str(value or "").strip()}
    if not wanted:
        return {}
    labels: dict[str, str] = {}
    try:
        rows = repo.select("profiles", in_={"id": list(wanted)}, limit=max(100, len(wanted) + 10))
    except Exception:
        rows = []
    for row in rows:
        pid = str(row.get("id") or "")
        name = str(row.get("full_name") or "").strip()
        email = str(row.get("email") or "").strip()
        labels[pid] = f"{name} · {email}" if name and email else name or email or pid
    return labels


def data_entry_status(row: Mapping[str, Any]) -> str:
    """Return the most useful workflow status for a transaction row."""
    for key in (
        "approval_status", "status", "receipt_status", "inspection_status", "disposition",
        "quality_disposition", "receipt_quality_disposition", "sample_gate_status",
    ):
        value = str(row.get(key) or "").strip()
        if value:
            return value.replace("_", " ").title()
    return "Saved"


def annotate_transaction_rows(repo: Repository, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Add user and data-entry state columns without changing the underlying records."""
    prepared = [dict(row) for row in rows]
    ids = [str(row.get(key) or "") for row in prepared for key in ("created_by", "updated_by")]
    labels = _profile_labels(repo, ids)
    for row in prepared:
        created = str(row.get("created_by") or "").strip()
        updated = str(row.get("updated_by") or "").strip()
        row["Created By User"] = labels.get(created, created or "System / Legacy")
        row["Last Modified By User"] = labels.get(updated, updated or labels.get(created, created or "System / Legacy"))
        row["Data Entry Status"] = data_entry_status(row)
    return prepared
