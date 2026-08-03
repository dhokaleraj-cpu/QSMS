from __future__ import annotations

from typing import Any, Mapping, Sequence

CLOSED_DISPOSITIONS = frozenset({"ACCEPTED", "ACCEPTED_UNDER_RESERVE", "REJECTED"})
ELIGIBLE_RECEIPT_DISPOSITIONS = frozenset({"ACCEPTED", "ACCEPTED_UNDER_RESERVE"})


def _text(value: Any) -> str:
    return str(value or "").strip().upper()


def _latest_by_inward(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for source in rows:
        inward_id = str(source.get("inward_lot_id") or "").strip()
        if not inward_id:
            continue
        row = dict(source)
        key = (
            str(row.get("decision_at") or ""),
            str(row.get("updated_at") or ""),
            str(row.get("created_at") or ""),
            str(row.get("id") or ""),
        )
        previous = latest.get(inward_id)
        previous_key = (
            str((previous or {}).get("decision_at") or ""),
            str((previous or {}).get("updated_at") or ""),
            str((previous or {}).get("created_at") or ""),
            str((previous or {}).get("id") or ""),
        )
        if previous is None or key > previous_key:
            latest[inward_id] = row
    return latest


def report_queue_status(report: Mapping[str, Any] | None) -> tuple[str, bool]:
    """Return display status and whether an inspection still needs action.

    A missing report is pending immediately after Material Inward. Draft reports,
    pending decisions and on-hold decisions remain in the work queue. Only a
    final Accepted, Accepted Under Reserve or Rejected decision closes the queue.
    """
    if not report:
        return "PENDING", True
    status = _text(report.get("status"))
    disposition = _text(report.get("disposition"))
    if status == "FINAL" and disposition in CLOSED_DISPOSITIONS:
        return "COMPLETED", False
    if disposition == "ON_HOLD":
        return "ON_HOLD", True
    if disposition == "PENDING" or not disposition:
        return "PENDING", True
    return "IN_PROGRESS", True


def build_inspection_queue(
    inward_rows: Sequence[Mapping[str, Any]],
    dimensional_reports: Sequence[Mapping[str, Any]],
    metlab_reports: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    dimensional_by_inward = _latest_by_inward(dimensional_reports)
    metlab_by_inward = _latest_by_inward(metlab_reports)
    queue: list[dict[str, Any]] = []

    for source in inward_rows:
        receipt = _text(source.get("receipt_disposition"))
        inward_status = _text(source.get("status"))
        if receipt not in ELIGIBLE_RECEIPT_DISPOSITIONS or inward_status == "REJECTED":
            continue

        row = dict(source)
        inward_id = str(row.get("id") or "")
        dimensional = dimensional_by_inward.get(inward_id)
        metlab = metlab_by_inward.get(inward_id)
        dimensional_status, dimensional_pending = report_queue_status(dimensional)
        metlab_status, metlab_pending = report_queue_status(metlab)

        row.update({
            "dimensional_report_id": (dimensional or {}).get("id"),
            "dimensional_report_number": (dimensional or {}).get("report_number"),
            "dimensional_report_status": (dimensional or {}).get("status"),
            "dimensional_report_disposition": (dimensional or {}).get("disposition") or "PENDING",
            "dimensional_queue_status": dimensional_status,
            "dimensional_pending": dimensional_pending,
            "metlab_report_id": (metlab or {}).get("id"),
            "metlab_report_number": (metlab or {}).get("report_number"),
            "metlab_report_status": (metlab or {}).get("status"),
            "metlab_report_disposition": (metlab or {}).get("disposition") or "PENDING",
            "metlab_queue_status": metlab_status,
            "metlab_pending": metlab_pending,
        })
        queue.append(row)

    return sorted(
        queue,
        key=lambda row: (str(row.get("created_at") or ""), str(row.get("inward_number") or "")),
        reverse=True,
    )


def pending_count(rows: Sequence[Mapping[str, Any]], report_type: str) -> int:
    key = "dimensional_pending" if _text(report_type) == "DIMENSIONAL" else "metlab_pending"
    return sum(1 for row in rows if bool(row.get(key)))


def pending_rows(rows: Sequence[Mapping[str, Any]], report_type: str) -> list[dict[str, Any]]:
    key = "dimensional_pending" if _text(report_type) == "DIMENSIONAL" else "metlab_pending"
    return [dict(row) for row in rows if bool(row.get(key))]
