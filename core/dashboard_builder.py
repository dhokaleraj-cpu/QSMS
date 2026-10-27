"""QCMS R35 · personal KPI dashboards (multiple per user) - data sources, widget maths, storage.

A dashboard is one row in ``public.qcms_user_dashboards``; its ``layout`` jsonb holds
``{"widgets": [widget, ...]}`` in display order.  A widget:

    {"id", "type": kpi|bar|line|area|pie|table, "title", "source", "group_by", "series_by",
     "agg": count|sum|avg|min|max, "value_field", "filter_field", "filter_value",
     "period_days": 0|7|30|90|180|365, "time_bucket": ""|day|week|month, "width": 1-4, "height": S|M|L, "top": 0|5|10|20}

The maths (``compute``) is pure pandas so it is unit-tested without Supabase.
"""
from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any, Mapping, Sequence

import pandas as pd

WIDGET_TYPES: dict[str, str] = {
    "kpi": "KPI card", "bar": "Bar chart", "line": "Line chart", "area": "Area chart", "pie": "Pie / donut chart", "table": "Table",
}
AGGREGATES: dict[str, str] = {"count": "Count of records", "sum": "Sum", "avg": "Average", "min": "Minimum", "max": "Maximum"}
PERIODS: dict[int, str] = {0: "All time", 7: "Last 7 days", 30: "Last 30 days", 90: "Last 90 days", 180: "Last 6 months", 365: "Last 12 months"}
TIME_BUCKETS: dict[str, str] = {"": "No time grouping", "day": "Per day", "week": "Per week", "month": "Per month"}
HEIGHTS: dict[str, int] = {"S": 230, "M": 330, "L": 460}
WIDTHS: dict[int, str] = {1: "¼ width", 2: "½ width", 3: "¾ width", 4: "Full width"}
FK_LABELS = {"part_id": "parts", "customer_id": "parties", "supplier_id": "parties", "party_id": "parties", "vendor_id": "parties",
             "forging_supplier_id": "parties", "rm_supplier_id": "parties", "steel_mill_id": "parties", "osp_vendor_id": "parties"}

# Whitelisted data sources: table, date column, groupable fields, numeric fields, View-permission module key.
DATA_SOURCES: dict[str, dict[str, Any]] = {
    "inward_lots": {"label": "Material Inward", "table": "inward_lots", "date": "inward_date", "module": "MATERIAL_INWARD",
        "fields": {"status": "Status", "quality_disposition": "Quality decision", "receipt_disposition": "Receipt decision", "supplier_id": "Supplier",
                   "part_id": "Part", "metallurgical_status": "MetLAB status", "dimensional_status": "Dimensional status", "heat_number": "Heat number"},
        "numbers": {"steel_quantity_kg": "Steel kg", "production_quantity_pcs": "Production pcs", "accepted_production_quantity_pcs": "Accepted pcs",
                    "rejected_production_quantity_pcs": "Rejected pcs", "quantity_received": "Quantity received"}},
    "lab_tests": {"label": "MetLAB / Bend Test reports", "table": "lab_tests", "date": "test_date", "module": "METLAB_REPORT",
        "fields": {"status": "Status", "disposition": "Decision", "overall_result": "Result", "part_id": "Part", "supplier_id": "Supplier",
                   "customer_id": "Customer", "layout_type_name": "Layout type", "metlab_subcategory": "MetLAB sub-category"},
        "numbers": {"steel_quantity_kg": "Steel kg", "production_quantity_pcs": "Production pcs"}},
    "inspection_reports": {"label": "Dimensional reports", "table": "inspection_reports", "date": "inspection_date", "module": "DIMENSIONAL_REPORT",
        "fields": {"status": "Status", "disposition": "Decision", "overall_result": "Result", "part_id": "Part", "supplier_id": "Supplier",
                   "customer_id": "Customer", "inspection_scope": "Inspection scope", "inspector": "Inspector"},
        "numbers": {"accepted_quantity": "Accepted qty", "rejected_quantity": "Rejected qty", "lot_quantity": "Lot qty", "sample_size": "Sample size"}},
    "rmtc_approvals": {"label": "RMTC", "table": "rmtc_approvals", "date": "certificate_date", "module": "RMTC_ENTRY",
        "fields": {"status": "Status", "disposition": "Decision", "validation_result": "Validation result", "supplier_id": "Supplier",
                   "steel_mill_id": "Steel mill", "part_id": "Part", "rm_section": "RM section", "chemistry_compliance": "Chemistry"},
        "numbers": {"certificate_quantity": "Certificate qty kg", "actual_di": "Actual DI", "grain_size": "Grain size"}},
    "quality_complaints": {"label": "Complaints", "table": "quality_complaints", "date": "complaint_date", "module": "COMPLAINT_MANAGEMENT",
        "fields": {"status": "Status", "complaint_type": "Complaint type", "severity": "Severity", "party_id": "Customer / supplier",
                   "part_id": "Part", "defect_mode": "Defect mode", "debit_note_status": "Debit note status"},
        "numbers": {"affected_quantity": "Affected qty", "debit_note_amount": "Debit note amount"}},
    "quality_assets": {"label": "Gauges / instruments", "table": "quality_assets", "date": "next_due_date", "module": "CALIBRATION_VALIDATION",
        "fields": {"status": "Status", "asset_type": "Asset type", "location": "Location", "service_type": "Service type", "manufacturer": "Manufacturer"},
        "numbers": {"calibration_frequency_days": "Calibration frequency days"}},
    "supply_customer_orders": {"label": "Customer orders / schedules", "table": "supply_customer_orders", "date": "schedule_month", "module": "SUPPLY_CHAIN",
        "fields": {"status": "Status", "customer_id": "Customer", "part_id": "Part", "order_type": "Order type", "supply_flow": "Supply flow",
                   "procurement_decision": "Procurement decision", "forging_supplier_id": "Forging supplier"},
        "numbers": {"order_qty_pcs": "Order qty pcs", "required_rm_kg": "Required RM kg"}},
    "supply_purchase_orders": {"label": "Purchase orders", "table": "supply_purchase_orders", "date": "order_date", "module": "SUPPLY_CHAIN",
        "fields": {"status": "Status", "approval_status": "Approval", "supplier_id": "Supplier", "po_type": "PO type", "currency": "Currency"},
        "numbers": {"grand_total": "Grand total", "subtotal": "Sub total"}},
    "supply_rm_purchase_orders": {"label": "RM orders", "table": "supply_rm_purchase_orders", "date": "order_date", "module": "SUPPLY_CHAIN",
        "fields": {"status": "Status", "rm_supplier_id": "RM supplier"}, "numbers": {"ordered_qty_kg": "Ordered kg"}},
    "supply_rm_receipts": {"label": "RM receipts", "table": "supply_rm_receipts", "date": "receipt_date", "module": "SUPPLY_CHAIN",
        "fields": {"heat_number": "Heat number"}, "numbers": {"received_qty_kg": "Received kg"}},
    "supply_forging_orders": {"label": "Forging orders", "table": "supply_forging_orders", "date": "order_date", "module": "SUPPLY_CHAIN",
        "fields": {"status": "Status", "forging_supplier_id": "Forging supplier"}, "numbers": {"order_qty_pcs": "Order pcs", "required_rm_kg": "Required RM kg"}},
    "supply_forging_receipts": {"label": "Forging receipts", "table": "supply_forging_receipts", "date": "receipt_date", "module": "SUPPLY_CHAIN",
        "fields": {"forging_supplier_id": "Forging supplier", "heat_number": "Heat number"},
        "numbers": {"received_qty_pcs": "Received pcs", "rejected_qty_pcs": "Rejected pcs", "actual_rm_consumed_kg": "RM consumed kg"}},
    "supply_downstream_events": {"label": "Machining / FG / dispatch", "table": "supply_downstream_events", "date": "event_date", "module": "SUPPLY_CHAIN",
        "fields": {"event_type": "Stage", "heat_number": "Heat number"}, "numbers": {"qty_pcs": "Quantity pcs", "rejected_qty_pcs": "Rejected pcs"}},
    "osp_jobs": {"label": "OSP jobs", "table": "osp_jobs", "date": "dispatch_date", "module": "OSP_TRANSACTIONS",
        "fields": {"status": "Status", "vendor_id": "OSP vendor", "part_id": "Part", "sample_gate_status": "Sample gate", "receipt_quality_disposition": "Receipt decision"},
        "numbers": {"quantity_dispatched": "Dispatched qty", "quantity_received": "Received qty", "quantity_rejected_at_receipt": "Rejected at receipt"}},
    "production_batches": {"label": "Production batches", "table": "production_batches", "date": "created_at", "module": "OSP_TRANSACTIONS",
        "fields": {"status": "Status", "part_id": "Part", "heat_number": "Heat number"}, "numbers": {"quantity_available": "Available qty", "quantity_started": "Started qty"}},
    "npd_orders": {"label": "NPD orders", "table": "npd_orders", "date": "order_date", "module": "NPD_APQP",
        "fields": {"status": "Status", "customer_id": "Customer", "part_id": "Part"}, "numbers": {"order_qty": "Order qty"}},
    "ppap_projects": {"label": "APQP / PPAP projects", "table": "ppap_projects", "date": "target_submission_date", "module": "NPD_APQP",
        "fields": {"status": "Status", "customer_id": "Customer", "submission_level": "Submission level", "coordinator": "Coordinator"},
        "numbers": {"completion_percent": "Completion %"}},
}


def new_widget(**values: Any) -> dict:
    widget = {"id": uuid.uuid4().hex[:10], "type": "bar", "title": "New widget", "source": "lab_tests", "group_by": "status",
              "series_by": "", "agg": "count", "value_field": "", "filter_field": "", "filter_value": "", "period_days": 0,
              "time_bucket": "", "width": 2, "height": "M", "top": 0}
    widget.update({k: v for k, v in values.items() if v is not None})
    return normalize_widget(widget)


def normalize_widget(widget: Mapping[str, Any]) -> dict:
    w = dict(widget)
    w["id"] = str(w.get("id") or uuid.uuid4().hex[:10])
    w["type"] = w.get("type") if w.get("type") in WIDGET_TYPES else "bar"
    w["source"] = w.get("source") if w.get("source") in DATA_SOURCES else "lab_tests"
    w["agg"] = w.get("agg") if w.get("agg") in AGGREGATES else "count"
    try:
        w["width"] = min(4, max(1, int(w.get("width") or 2)))
    except (TypeError, ValueError):
        w["width"] = 2
    w["height"] = w.get("height") if w.get("height") in HEIGHTS else "M"
    try:
        w["period_days"] = int(w.get("period_days") or 0)
    except (TypeError, ValueError):
        w["period_days"] = 0
    try:
        w["top"] = max(0, int(w.get("top") or 0))
    except (TypeError, ValueError):
        w["top"] = 0
    w["time_bucket"] = w.get("time_bucket") if w.get("time_bucket") in TIME_BUCKETS else ""
    for key in ("title", "group_by", "series_by", "value_field", "filter_field", "filter_value"):
        w[key] = str(w.get(key) or "")
    return w


def layout_widgets(layout: Any) -> list[dict]:
    widgets = (layout or {}).get("widgets") if isinstance(layout, Mapping) else None
    return [normalize_widget(w) for w in (widgets or []) if isinstance(w, Mapping)]


def move_widget(widgets: Sequence[Mapping[str, Any]], widget_id: str, step: int) -> list[dict]:
    items = [dict(w) for w in widgets]
    index = next((i for i, w in enumerate(items) if w.get("id") == widget_id), None)
    if index is None:
        return items
    target = max(0, min(len(items) - 1, index + step))
    items.insert(target, items.pop(index))
    return items


def duplicate_widget(widgets: Sequence[Mapping[str, Any]], widget_id: str) -> list[dict]:
    items = [dict(w) for w in widgets]
    for index, w in enumerate(items):
        if w.get("id") == widget_id:
            copy = deepcopy(w)
            copy["id"] = uuid.uuid4().hex[:10]
            copy["title"] = f"{w.get('title') or 'Widget'} (copy)"
            items.insert(index + 1, copy)
            break
    return items


def pack_rows(widgets: Sequence[Mapping[str, Any]], columns: int = 4) -> list[list[dict]]:
    """Group widgets into grid rows whose widths add up to at most ``columns``."""
    rows: list[list[dict]] = []
    current: list[dict] = []
    used = 0
    for widget in widgets:
        width = min(columns, max(1, int(widget.get("width") or 1)))
        if current and used + width > columns:
            rows.append(current); current = []; used = 0
        current.append(dict(widget)); used += width
    if current:
        rows.append(current)
    return rows


def _as_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")[:26]).date()
    except ValueError:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None


def _bucket(value: Any, bucket: str) -> str:
    day = _as_date(value)
    if day is None:
        return "No date"
    if bucket == "month":
        return day.strftime("%Y-%m")
    if bucket == "week":
        start = day - timedelta(days=day.weekday())
        return start.strftime("%Y-%m-%d")
    return day.isoformat()


def _label(value: Any, field: str, labels: Mapping[str, Mapping[str, str]]) -> str:
    text = str(value if value is not None else "").strip()
    if not text:
        return "Not set"
    table = FK_LABELS.get(field)
    if table:
        return str((labels.get(table) or {}).get(text) or text[:8])
    return text.replace("_", " ").title() if text.isupper() else text


def filter_rows(rows: Sequence[Mapping[str, Any]], widget: Mapping[str, Any], *, today: date | None = None,
                labels: Mapping[str, Mapping[str, str]] | None = None) -> list[Mapping[str, Any]]:
    source = DATA_SOURCES[widget["source"]]
    out = list(rows)
    days = int(widget.get("period_days") or 0)
    if days:
        start = (today or date.today()) - timedelta(days=days)
        date_field = source["date"]
        out = [r for r in out if (_as_date(r.get(date_field)) or _as_date(r.get("created_at")) or date.min) >= start]
    field = str(widget.get("filter_field") or "")
    wanted = str(widget.get("filter_value") or "").strip().casefold()
    if field and wanted:
        out = [r for r in out if wanted in (str(r.get(field) or "").casefold() + " " + _label(r.get(field), field, labels or {}).casefold())]
    return out


def compute(rows: Sequence[Mapping[str, Any]], widget: Mapping[str, Any], *, today: date | None = None,
            labels: Mapping[str, Mapping[str, str]] | None = None) -> tuple[float | None, pd.DataFrame]:
    """Return (single KPI value, grouped frame with columns Group[, Series], Value)."""
    widget = normalize_widget(widget)
    labels = labels or {}
    data = filter_rows(rows, widget, today=today, labels=labels)
    agg = widget["agg"]
    value_field = widget["value_field"]

    def aggregate(values: list[Any]) -> float:
        if agg == "count":
            return float(len(values))
        numbers = []
        for v in values:
            try:
                numbers.append(float(v))
            except (TypeError, ValueError):
                continue
        if not numbers:
            return 0.0
        if agg == "sum":
            return float(sum(numbers))
        if agg == "avg":
            return float(sum(numbers) / len(numbers))
        if agg == "min":
            return float(min(numbers))
        return float(max(numbers))

    pick = (lambda r: r.get(value_field)) if value_field else (lambda r: 1)
    total = aggregate([pick(r) for r in data])
    if widget["type"] == "kpi":
        return round(total, 2), pd.DataFrame({"Group": ["Total"], "Value": [round(total, 2)]})

    group_field = widget["group_by"] or ""
    series_field = widget["series_by"] or ""
    bucket = widget["time_bucket"]
    date_field = DATA_SOURCES[widget["source"]]["date"]
    groups: dict[tuple[str, str], list[Any]] = {}
    for row in data:
        if bucket:
            g = _bucket(row.get(date_field) or row.get("created_at"), bucket)
        else:
            g = _label(row.get(group_field), group_field, labels) if group_field else "Total"
        s = _label(row.get(series_field), series_field, labels) if series_field else ""
        groups.setdefault((g, s), []).append(pick(row))
    records = [{"Group": g, "Series": s, "Value": round(aggregate(v), 2)} for (g, s), v in groups.items()]
    frame = pd.DataFrame(records, columns=["Group", "Series", "Value"])
    if frame.empty:
        return round(total, 2), frame
    if bucket:
        frame = frame.sort_values(["Group", "Series"])
    else:
        order = frame.groupby("Group")["Value"].sum().sort_values(ascending=False)
        if widget["top"]:
            order = order.head(widget["top"])
            frame = frame[frame["Group"].isin(order.index)]
        frame["_o"] = frame["Group"].map({k: i for i, k in enumerate(order.index)})
        frame = frame.sort_values(["_o", "Series"]).drop(columns="_o")
    if not series_field:
        frame = frame.drop(columns="Series")
    return round(total, 2), frame.reset_index(drop=True)


def drill_rows(rows: Sequence[Mapping[str, Any]], widget: Mapping[str, Any], *, today: date | None = None,
               labels: Mapping[str, Mapping[str, str]] | None = None) -> list[dict]:
    """R37: the records behind a widget's number (same period + filter as ``compute``) in the KPI Details row shape."""
    from core.kpi_service import local_drill_rows
    widget = normalize_widget(widget)
    source = DATA_SOURCES[widget["source"]]
    data = filter_rows(rows, widget, today=today, labels=labels or {})
    return local_drill_rows(source["table"], data, date_field=source["date"], labels=labels or {})


def starter_widgets() -> list[dict]:
    return [
        new_widget(type="kpi", title="MetLAB / Bend reports (30 days)", source="lab_tests", period_days=30, width=1, height="S"),
        new_widget(type="kpi", title="Dimensional reports (30 days)", source="inspection_reports", period_days=30, width=1, height="S"),
        new_widget(type="kpi", title="Open complaints", source="quality_complaints", filter_field="status", filter_value="OPEN", width=1, height="S"),
        new_widget(type="kpi", title="Open PO value", source="supply_purchase_orders", agg="sum", value_field="grand_total", filter_field="status", filter_value="OPEN", width=1, height="S"),
        new_widget(type="bar", title="Reports per month by decision", source="lab_tests", time_bucket="month", series_by="disposition", period_days=180, width=2),
        new_widget(type="pie", title="Complaints by customer / supplier", source="quality_complaints", group_by="party_id", top=8, width=2),
        new_widget(type="line", title="RM received kg per month", source="supply_rm_receipts", agg="sum", value_field="received_qty_kg", time_bucket="month", period_days=365, width=2),
        new_widget(type="table", title="Open orders by customer", source="supply_customer_orders", group_by="customer_id", agg="sum", value_field="order_qty_pcs", filter_field="status", filter_value="OPEN", width=2),
    ]


# ---------------------------------------------------------------------------------------------
# Storage (Supabase table public.qcms_user_dashboards; RLS: owner, or shared within the company)
# ---------------------------------------------------------------------------------------------
TABLE = "qcms_user_dashboards"


def list_dashboards(repo: Any, profile_id: str) -> list[dict]:
    rows = repo.select(TABLE, order_by="sort_order", limit=200)
    mine = [r for r in rows if str(r.get("owner_profile_id") or "") == profile_id]
    shared = [r for r in rows if str(r.get("owner_profile_id") or "") != profile_id and r.get("shared_with_tenant")]
    mine.sort(key=lambda r: (not r.get("is_default"), int(r.get("sort_order") or 0), str(r.get("name") or "")))
    return mine + shared


def create_dashboard(repo: Any, profile_id: str, name: str, *, widgets: Sequence[Mapping[str, Any]] | None = None, sort_order: int = 0) -> dict:
    name = str(name or "").strip() or "My dashboard"
    return repo.insert(TABLE, {"owner_profile_id": profile_id, "name": name[:80], "layout": {"widgets": [normalize_widget(w) for w in widgets or []]},
                               "sort_order": sort_order, "is_default": False, "shared_with_tenant": False})


def save_widgets(repo: Any, dashboard_id: str, widgets: Sequence[Mapping[str, Any]]) -> dict:
    return repo.update(TABLE, dashboard_id, {"layout": {"widgets": [normalize_widget(w) for w in widgets]}, "updated_at": datetime.now().astimezone().isoformat()})


def update_dashboard(repo: Any, dashboard_id: str, **changes: Any) -> dict:
    allowed = {k: v for k, v in changes.items() if k in {"name", "description", "is_default", "shared_with_tenant", "sort_order"}}
    allowed["updated_at"] = datetime.now().astimezone().isoformat()
    return repo.update(TABLE, dashboard_id, allowed)


def delete_dashboard(repo: Any, dashboard_id: str) -> None:
    repo.delete(TABLE, dashboard_id)
