"""QCMS R13 · Top-10 KPI dashboards.

Pure calculation layer: every function receives plain row lists (as returned by
``Repository.select``) and returns a ``Dashboard`` with headline tiles, charts and
tables. No Streamlit or database access here, so every KPI is unit-testable and the
page can cache/load data however it likes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable, Iterable, Mapping, Sequence

import pandas as pd

# Chart colours (validated with the dataviz palette validator, light mode):
# teal brand series first, then fixed categorical order.
SERIES = ["#00968f", "#eb6834", "#4a3aa7", "#eda100", "#e87ba4", "#2a78d6"]
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b", "neutral": "#898781"}

CLOSED_WORDS = {"CLOSED", "COMPLETED", "CANCELLED", "REJECTED", "SUPERSEDED", "INACTIVE"}
PASS_WORDS = {"PASS", "PASSED", "ACCEPTED", "APPROVED", "OK", "CONFORMING", "RELEASED", "ACCEPTED_UNDER_RESERVE"}
FAIL_WORDS = {"FAIL", "FAILED", "REJECTED", "NOT_OK", "NONCONFORMING", "NON_CONFORMING"}


@dataclass
class Tile:
    label: str
    value: str
    foot: str = ""
    status: str = "neutral"   # good | warning | serious | critical | neutral


@dataclass
class Chart:
    title: str
    kind: str                 # bar | hbar | line | donut | stacked
    frame: pd.DataFrame
    x: str
    y: str
    color: str | None = None  # series column for multi-series charts
    note: str = ""


@dataclass
class Dashboard:
    key: str
    title: str
    module_key: str
    question: str
    tiles: list[Tile] = field(default_factory=list)
    charts: list[Chart] = field(default_factory=list)
    tables: list[tuple[str, pd.DataFrame]] = field(default_factory=list)
    empty: bool = False


# ----------------------------------------------------------------------------- helpers
def _d(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return pd.to_datetime(str(value), errors="coerce", utc=True).date()
    except Exception:
        return None


def _n(value: Any) -> float:
    try:
        number = float(value)
        return 0.0 if number != number else number
    except Exception:
        return 0.0


def _s(value: Any) -> str:
    return str(value or "").strip().upper()


def _pct(part: float, whole: float) -> float | None:
    return round(100.0 * part / whole, 1) if whole else None


def _fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _fmt_num(value: float, decimals: int = 0) -> str:
    return f"{value:,.{decimals}f}"


def _status_for(value: float | None, good: float, warn: float, *, higher_is_better: bool = True) -> str:
    if value is None:
        return "neutral"
    if higher_is_better:
        return "good" if value >= good else ("warning" if value >= warn else "critical")
    return "good" if value <= good else ("warning" if value <= warn else "critical")


def _in_range(value: Any, start: date | None, end: date | None) -> bool:
    day = _d(value)
    if day is None:
        return start is None and end is None
    return (start is None or day >= start) and (end is None or day <= end)


def _month(value: Any) -> str:
    day = _d(value)
    return day.strftime("%Y-%m") if day else "No date"


def _label(mapping: Mapping[str, str], key: Any, default: str = "Unassigned") -> str:
    return mapping.get(str(key or ""), "") or default


def _is_open(row: Mapping[str, Any]) -> bool:
    return _s(row.get("status")) not in CLOSED_WORDS


def _frame(rows: Iterable[Mapping[str, Any]], columns: Sequence[str]) -> pd.DataFrame:
    data = list(rows)
    return pd.DataFrame(data, columns=list(columns)) if data else pd.DataFrame(columns=list(columns))


@dataclass
class KPIContext:
    today: date
    start: date | None
    end: date | None
    parties: dict[str, str] = field(default_factory=dict)
    parts: dict[str, str] = field(default_factory=dict)


# ----------------------------------------------------------------------------- 1
def supplier_delivery(data: Mapping[str, list[dict]], ctx: KPIContext) -> Dashboard:
    board = Dashboard("supplier-otd", "Supplier On-Time Delivery", "SUPPLY_CHAIN", "Are RM and forging suppliers delivering on the promised date?")
    rm_po = {str(r.get("id")): r for r in data.get("supply_rm_purchase_orders", [])}
    fo = {str(r.get("id")): r for r in data.get("supply_forging_orders", [])}
    events: list[dict] = []
    for rec in data.get("supply_rm_receipts", []):
        po = rm_po.get(str(rec.get("rm_purchase_order_id") or ""))
        if po and _in_range(rec.get("receipt_date"), ctx.start, ctx.end):
            events.append({"supplier": _label(ctx.parties, po.get("rm_supplier_id")), "type": "RM", "expected": _d(po.get("expected_date")), "actual": _d(rec.get("receipt_date"))})
    for rec in data.get("supply_forging_receipts", []):
        order = fo.get(str(rec.get("forging_order_id") or ""))
        if order and _in_range(rec.get("receipt_date"), ctx.start, ctx.end):
            events.append({"supplier": _label(ctx.parties, rec.get("forging_supplier_id") or order.get("forging_supplier_id")), "type": "Forging", "expected": _d(order.get("expected_date")), "actual": _d(rec.get("receipt_date"))})
    events = [e for e in events if e["expected"] and e["actual"]]
    for e in events:
        e["delay_days"] = (e["actual"] - e["expected"]).days
        e["on_time"] = e["delay_days"] <= 0
        e["month"] = e["actual"].strftime("%Y-%m")
    total = len(events); on_time = sum(1 for e in events if e["on_time"])
    late = [e for e in events if not e["on_time"]]
    otd = _pct(on_time, total)
    avg_delay = sum(e["delay_days"] for e in late) / len(late) if late else 0.0
    # open orders already past expected date
    overdue_open = sum(1 for r in list(rm_po.values()) + list(fo.values()) if _is_open(r) and _s(r.get("status")) != "PENDING_APPROVAL" and _d(r.get("expected_date")) and _d(r.get("expected_date")) < ctx.today)
    board.tiles = [
        Tile("On-time delivery", _fmt_pct(otd), f"{on_time} of {total} receipts on/before date", _status_for(otd, 95, 85)),
        Tile("Late receipts", _fmt_num(len(late)), "Received after expected date", "good" if not late else "warning"),
        Tile("Avg delay (late only)", f"{avg_delay:.1f} d", "Days after expected date", _status_for(avg_delay, 2, 7, higher_is_better=False)),
        Tile("Open orders overdue", _fmt_num(overdue_open), "Expected date passed, not closed", "good" if not overdue_open else "critical"),
    ]
    if not events:
        board.empty = True
        return board
    df = pd.DataFrame(events)
    by_sup = df.groupby("supplier").agg(receipts=("on_time", "size"), on_time=("on_time", "sum"), avg_delay=("delay_days", lambda s: round(s[s > 0].mean(), 1) if (s > 0).any() else 0.0)).reset_index()
    by_sup["otd_pct"] = (100 * by_sup["on_time"] / by_sup["receipts"]).round(1)
    by_sup = by_sup.sort_values(["otd_pct", "receipts"], ascending=[True, False])
    trend = df.groupby("month").agg(receipts=("on_time", "size"), on_time=("on_time", "sum")).reset_index()
    trend["otd_pct"] = (100 * trend["on_time"] / trend["receipts"]).round(1)
    board.charts = [
        Chart("On-time delivery % by supplier (worst first)", "hbar", by_sup.head(15), "otd_pct", "supplier", note="Target ≥ 95%"),
        Chart("Monthly on-time delivery %", "line", trend.sort_values("month"), "month", "otd_pct"),
    ]
    board.tables = [("Supplier delivery scorecard", by_sup.rename(columns={"supplier": "Supplier", "receipts": "Receipts", "on_time": "On time", "avg_delay": "Avg delay (late) d", "otd_pct": "OTD %"}))]
    return board


# ----------------------------------------------------------------------------- 2
def po_pipeline(data: Mapping[str, list[dict]], ctx: KPIContext) -> Dashboard:
    board = Dashboard("po-pipeline", "Purchase Order Pipeline", "SUPPLY_CHAIN", "How much is on order, what is waiting for approval and what is overdue?")
    pos = [r for r in data.get("supply_purchase_orders", []) if _s(r.get("status")) != "CANCELLED"]
    in_period = [r for r in pos if _in_range(r.get("order_date"), ctx.start, ctx.end)]
    open_pos = [r for r in pos if _s(r.get("status")) in {"OPEN", "PARTIAL", "PART_RECEIVED", "PENDING_APPROVAL", "DRAFT"}]
    pending = [r for r in pos if _s(r.get("approval_status") or r.get("status")) in {"PENDING_APPROVAL", "APPROVAL_PENDING"}]
    ages = [(ctx.today - (_d(r.get("submitted_at")) or _d(r.get("order_date")) or ctx.today)).days for r in pending]
    overdue = [r for r in open_pos if _s(r.get("status")) != "PENDING_APPROVAL" and _d(r.get("delivery_date")) and _d(r.get("delivery_date")) < ctx.today]
    open_value = sum(_n(r.get("grand_total")) for r in open_pos)
    avg_age = sum(ages) / len(ages) if ages else 0.0
    board.tiles = [
        Tile("Open PO value", "₹ " + _fmt_num(open_value), f"{len(open_pos)} open POs", "neutral"),
        Tile("Waiting for approval", _fmt_num(len(pending)), f"Avg age {avg_age:.1f} days", _status_for(avg_age, 1, 3, higher_is_better=False) if pending else "good"),
        Tile("Overdue open POs", _fmt_num(len(overdue)), "Delivery date passed", "good" if not overdue else "critical"),
        Tile("POs raised in period", _fmt_num(len(in_period)), "₹ " + _fmt_num(sum(_n(r.get("grand_total")) for r in in_period)), "neutral"),
    ]
    if not pos:
        board.empty = True
        return board
    df = pd.DataFrame([{"status": _s(r.get("status")).replace("_", " ").title() or "Unknown", "value": _n(r.get("grand_total")), "supplier": _label(ctx.parties, r.get("supplier_id")), "type": _s(r.get("po_type")).replace("_", " ").title(), "month": _month(r.get("order_date"))} for r in pos])
    by_status = df.groupby("status")["value"].sum().reset_index().sort_values("value", ascending=False)
    open_df = pd.DataFrame([{"supplier": _label(ctx.parties, r.get("supplier_id")), "value": _n(r.get("grand_total"))} for r in open_pos]) if open_pos else pd.DataFrame(columns=["supplier", "value"])
    top_sup = open_df.groupby("supplier")["value"].sum().reset_index().sort_values("value", ascending=False).head(10)
    trend = df[df["month"] != "No date"].groupby(["month", "type"])["value"].sum().reset_index().sort_values("month")
    board.charts = [
        Chart("PO value by status (₹)", "bar", by_status, "status", "value"),
        Chart("Top 10 suppliers by open PO value (₹)", "hbar", top_sup.sort_values("value"), "value", "supplier"),
        Chart("Monthly PO value by type (₹)", "stacked", trend, "month", "value", color="type"),
    ]
    queue = _frame(({"PO Number": r.get("po_number"), "Supplier": _label(ctx.parties, r.get("supplier_id")), "Value ₹": round(_n(r.get("grand_total")), 2), "Submitted": str(_d(r.get("submitted_at")) or _d(r.get("order_date")) or ""), "Age days": age} for r, age in sorted(zip(pending, ages), key=lambda t: -t[1])), ["PO Number", "Supplier", "Value ₹", "Submitted", "Age days"])
    late = _frame(({"PO Number": r.get("po_number"), "Supplier": _label(ctx.parties, r.get("supplier_id")), "Delivery date": str(_d(r.get("delivery_date"))), "Days late": (ctx.today - _d(r.get("delivery_date"))).days, "Value ₹": round(_n(r.get("grand_total")), 2)} for r in overdue), ["PO Number", "Supplier", "Delivery date", "Days late", "Value ₹"])
    board.tables = [("Approval queue (oldest first)", queue), ("Overdue open POs", late.sort_values("Days late", ascending=False) if not late.empty else late)]
    return board


# ----------------------------------------------------------------------------- 3
def incoming_quality(data: Mapping[str, list[dict]], ctx: KPIContext) -> Dashboard:
    board = Dashboard("incoming-quality", "Incoming Material Quality", "MATERIAL_INWARD", "How good is the steel / forgings we receive, by supplier?")
    lots = [r for r in data.get("inward_lots", []) if _in_range(r.get("inward_date") or r.get("created_at"), ctx.start, ctx.end)]
    recv = sum(_n(r.get("steel_quantity_kg") or r.get("quantity_received")) for r in lots)
    rej = sum(_n(r.get("rejected_steel_quantity_kg") or r.get("quantity_rejected")) for r in lots)
    hold = sum(_n(r.get("hold_steel_quantity_kg")) for r in lots)
    accepted = sum(_n(r.get("accepted_steel_quantity_kg") or r.get("quantity_accepted")) for r in lots)
    ppm = (rej / recv * 1_000_000) if recv else None
    pending = sum(1 for r in lots if "PENDING" in _s(r.get("metallurgical_status")) or "PENDING" in _s(r.get("dimensional_status")) or "HOLD" in _s(r.get("status")))
    board.tiles = [
        Tile("Lots received", _fmt_num(len(lots)), f"{_fmt_num(recv)} kg received", "neutral"),
        Tile("Acceptance rate", _fmt_pct(_pct(accepted, recv)), f"{_fmt_num(accepted)} kg accepted", _status_for(_pct(accepted, recv), 98, 95)),
        Tile("Rejection PPM", "—" if ppm is None else _fmt_num(ppm), f"{_fmt_num(rej)} kg rejected", _status_for(ppm, 1000, 5000, higher_is_better=False)),
        Tile("On hold / pending", _fmt_num(pending), f"{_fmt_num(hold)} kg on hold", "good" if not pending else "warning"),
    ]
    if not lots:
        board.empty = True
        return board
    df = pd.DataFrame([{"supplier": _label(ctx.parties, r.get("supplier_id")), "received": _n(r.get("steel_quantity_kg") or r.get("quantity_received")), "rejected": _n(r.get("rejected_steel_quantity_kg") or r.get("quantity_rejected")), "hold": _n(r.get("hold_steel_quantity_kg")), "month": _month(r.get("inward_date") or r.get("created_at"))} for r in lots])
    sup = df.groupby("supplier").agg(lots=("received", "size"), received=("received", "sum"), rejected=("rejected", "sum"), hold=("hold", "sum")).reset_index()
    sup["rejection_pct"] = (100 * sup["rejected"] / sup["received"].where(sup["received"] > 0)).round(2).fillna(0.0)
    sup["ppm"] = (1_000_000 * sup["rejected"] / sup["received"].where(sup["received"] > 0)).round(0).fillna(0.0)
    trend = df.groupby("month").agg(received=("received", "sum"), rejected=("rejected", "sum")).reset_index().sort_values("month")
    trend["ppm"] = (1_000_000 * trend["rejected"] / trend["received"].where(trend["received"] > 0)).round(0).fillna(0.0)
    board.charts = [
        Chart("Rejection PPM by supplier (worst first)", "hbar", sup.sort_values("ppm").tail(15), "ppm", "supplier", note="Lower is better"),
        Chart("Monthly rejection PPM", "line", trend, "month", "ppm"),
    ]
    board.tables = [("Supplier quality scorecard", sup.sort_values("ppm", ascending=False).rename(columns={"supplier": "Supplier", "lots": "Lots", "received": "Received kg", "rejected": "Rejected kg", "hold": "On hold kg", "rejection_pct": "Rejection %", "ppm": "PPM"}))]
    return board


# ----------------------------------------------------------------------------- 4
def rmtc_compliance(data: Mapping[str, list[dict]], ctx: KPIContext) -> Dashboard:
    board = Dashboard("rmtc", "RMTC Approval & Compliance", "RMTC_ENTRY", "Are mill certificates approved fast and right first time?")
    rows = [r for r in data.get("rmtc_approvals", []) if _in_range(r.get("certificate_date") or r.get("created_at"), ctx.start, ctx.end)]
    decided = [r for r in rows if _d(r.get("decision_at") or r.get("approved_at"))]
    approved = [r for r in rows if _s(r.get("status") or r.get("disposition")) in PASS_WORDS or _s(r.get("disposition")) in PASS_WORDS]
    rejected = [r for r in rows if _s(r.get("status")) in FAIL_WORDS or _s(r.get("disposition")) in FAIL_WORDS]
    pending = [r for r in rows if r not in approved and r not in rejected and _s(r.get("status")) not in CLOSED_WORDS]
    cycle = [(_d(r.get("decision_at") or r.get("approved_at")) - _d(r.get("created_at"))).days for r in decided if _d(r.get("created_at"))]
    chem_fail = sum(1 for r in rows if r.get("chemistry_compliance") is False or _s(r.get("chemistry_compliance")) in {"FALSE", "FAIL", "NON_COMPLIANT"})
    avg_cycle = sum(cycle) / len(cycle) if cycle else None
    board.tiles = [
        Tile("Certificates", _fmt_num(len(rows)), f"{_fmt_num(sum(_n(r.get('certificate_quantity')) for r in rows))} kg certified", "neutral"),
        Tile("Approval rate", _fmt_pct(_pct(len(approved), len(approved) + len(rejected))), f"{len(rejected)} rejected", _status_for(_pct(len(approved), len(approved) + len(rejected)), 97, 90)),
        Tile("Pending decision", _fmt_num(len(pending)), "Awaiting validation", "good" if not pending else "warning"),
        Tile("Avg decision time", "—" if avg_cycle is None else f"{avg_cycle:.1f} d", f"Chemistry non-compliance: {chem_fail}", _status_for(avg_cycle, 1, 3, higher_is_better=False)),
    ]
    if not rows:
        board.empty = True
        return board
    df = pd.DataFrame([{"status": (_s(r.get("status")) or "UNKNOWN").replace("_", " ").title(), "mill": _label(ctx.parties, r.get("steel_mill_id") or r.get("supplier_id")), "ok": r in approved, "bad": r in rejected} for r in rows])
    status = df.groupby("status").size().reset_index(name="certificates").sort_values("certificates", ascending=False)
    mill = df.groupby("mill").agg(certificates=("ok", "size"), approved=("ok", "sum"), rejected=("bad", "sum")).reset_index()
    mill["approval_pct"] = (100 * mill["approved"] / (mill["approved"] + mill["rejected"]).where((mill["approved"] + mill["rejected"]) > 0)).round(1).fillna(0.0)
    board.charts = [
        Chart("Certificates by status", "bar", status, "status", "certificates"),
        Chart("Approval % by steel mill / supplier", "hbar", mill.sort_values("approval_pct").tail(15), "approval_pct", "mill"),
    ]
    board.tables = [("Mill scorecard", mill.sort_values("certificates", ascending=False).rename(columns={"mill": "Steel mill / supplier", "certificates": "Certificates", "approved": "Approved", "rejected": "Rejected", "approval_pct": "Approval %"}))]
    return board


# ----------------------------------------------------------------------------- 5
def lab_inspection(data: Mapping[str, list[dict]], ctx: KPIContext) -> Dashboard:
    board = Dashboard("lab-inspection", "Lab & Inspection First-Pass Yield", "METLAB_REPORT", "How many MetLAB / dimensional reports pass first time, and how fast are they released?")
    reports: list[dict] = []
    for source, table, date_key in (("MetLAB / Bend", "lab_tests", "test_date"), ("Dimensional", "inspection_reports", "inspection_date")):
        for r in data.get(table, []):
            when = r.get(date_key) or r.get("created_at")
            if not _in_range(when, ctx.start, ctx.end):
                continue
            result = _s(r.get("overall_result") or r.get("disposition"))
            reports.append({"source": source, "result": result, "pass": result in PASS_WORDS, "fail": result in FAIL_WORDS, "month": _month(when), "part": _label(ctx.parts, r.get("part_id"), "No part"),
                            "tat": ((_d(r.get("validated_at") or r.get("decision_at")) - _d(r.get("created_at"))).days if _d(r.get("validated_at") or r.get("decision_at")) and _d(r.get("created_at")) else None)})
    evaluated = [r for r in reports if r["pass"] or r["fail"]]
    fpy = _pct(sum(r["pass"] for r in evaluated), len(evaluated))
    tats = [r["tat"] for r in reports if r["tat"] is not None]
    pending = sum(1 for r in reports if not r["pass"] and not r["fail"])
    board.tiles = [
        Tile("Reports", _fmt_num(len(reports)), f"{sum(r['source'] == 'MetLAB / Bend' for r in reports)} MetLAB · {sum(r['source'] == 'Dimensional' for r in reports)} dimensional", "neutral"),
        Tile("First-pass yield", _fmt_pct(fpy), f"{sum(r['fail'] for r in evaluated)} failed", _status_for(fpy, 98, 95)),
        Tile("Not yet evaluated", _fmt_num(pending), "Pending / hold / not evaluated", "good" if not pending else "warning"),
        Tile("Avg release time", "—" if not tats else f"{sum(tats) / len(tats):.1f} d", "Created → validated", _status_for(sum(tats) / len(tats) if tats else None, 1, 3, higher_is_better=False)),
    ]
    if not reports:
        board.empty = True
        return board
    df = pd.DataFrame(reports)
    ev = df[df["pass"] | df["fail"]]
    trend = ev.groupby(["month", "source"]).agg(n=("pass", "size"), p=("pass", "sum")).reset_index()
    trend["fpy_pct"] = (100 * trend["p"] / trend["n"]).round(1)
    worst = ev.groupby("part").agg(reports=("pass", "size"), failed=("fail", "sum")).reset_index().sort_values(["failed", "reports"], ascending=False)
    worst = worst[worst["failed"] > 0].head(10)
    board.charts = [Chart("Monthly first-pass yield %", "line", trend.sort_values("month"), "month", "fpy_pct", color="source")]
    if not worst.empty:
        board.charts.append(Chart("Parts with most failed reports", "hbar", worst.sort_values("failed"), "failed", "part"))
    board.tables = [("Failed reports by part", worst.rename(columns={"part": "Part", "reports": "Reports", "failed": "Failed"}))]
    return board


# ----------------------------------------------------------------------------- 6
def complaints_capa(data: Mapping[str, list[dict]], ctx: KPIContext) -> Dashboard:
    board = Dashboard("complaints", "Complaints & CAPA (8D)", "COMPLAINT_MANAGEMENT", "How many complaints are open, overdue and how fast do we close them?")
    allrows = data.get("quality_complaints", [])
    rows = [r for r in allrows if _in_range(r.get("complaint_date") or r.get("created_at"), ctx.start, ctx.end)]
    open_rows = [r for r in allrows if _is_open(r)]
    overdue = [r for r in open_rows if _d(r.get("target_closure_date")) and _d(r.get("target_closure_date")) < ctx.today]
    closed = [r for r in rows if _s(r.get("status")) == "CLOSED" and _d(r.get("closure_date")) and _d(r.get("complaint_date") or r.get("created_at"))]
    days = [(_d(r.get("closure_date")) - _d(r.get("complaint_date") or r.get("created_at"))).days for r in closed]
    debit_open = sum(max(_n(r.get("debit_note_amount")) - _n(r.get("debit_note_settled_amount")), 0) for r in allrows if r.get("debit_note_required"))
    board.tiles = [
        Tile("Complaints in period", _fmt_num(len(rows)), f"{sum(_s(r.get('complaint_type')) .startswith('CUSTOMER') for r in rows)} customer · {sum(_s(r.get('complaint_type')).startswith('SUPPLIER') for r in rows)} supplier", "neutral"),
        Tile("Open complaints", _fmt_num(len(open_rows)), f"{sum(_s(r.get('severity')) in {'HIGH', 'CRITICAL'} for r in open_rows)} high / critical", "good" if not open_rows else "warning"),
        Tile("Overdue CAPA", _fmt_num(len(overdue)), "Target closure date passed", "good" if not overdue else "critical"),
        Tile("Avg closure time", "—" if not days else f"{sum(days) / len(days):.0f} d", f"Open debit notes ₹ {_fmt_num(debit_open)}", _status_for(sum(days) / len(days) if days else None, 30, 60, higher_is_better=False)),
    ]
    if not allrows:
        board.empty = True
        return board
    sev = pd.DataFrame([{"severity": (_s(r.get("severity")) or "UNSET").title()} for r in open_rows]) if open_rows else pd.DataFrame(columns=["severity"])
    sev = sev.groupby("severity").size().reset_index(name="open") if not sev.empty else pd.DataFrame(columns=["severity", "open"])
    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    sev = sev.sort_values("severity", key=lambda s: s.map(lambda v: order.get(v, 9)))
    opened = pd.DataFrame([{"month": _month(r.get("complaint_date") or r.get("created_at")), "series": "Opened"} for r in rows] + [{"month": _month(r.get("closure_date")), "series": "Closed"} for r in closed])
    flow = opened.groupby(["month", "series"]).size().reset_index(name="complaints").sort_values("month") if not opened.empty else pd.DataFrame(columns=["month", "series", "complaints"])
    parts = pd.DataFrame([{"part": _label(ctx.parts, r.get("part_id"), "No part")} for r in rows])
    top_parts = parts.groupby("part").size().reset_index(name="complaints").sort_values("complaints", ascending=False).head(10) if not parts.empty else pd.DataFrame(columns=["part", "complaints"])
    board.charts = [Chart("Open complaints by severity", "bar", sev, "severity", "open"), Chart("Complaints opened vs closed per month", "line", flow, "month", "complaints", color="series")]
    if not top_parts.empty:
        board.charts.append(Chart("Top parts by complaints", "hbar", top_parts.sort_values("complaints"), "complaints", "part"))
    board.tables = [("Overdue CAPA", _frame(({"Complaint": r.get("complaint_number"), "Subject": r.get("subject"), "Severity": r.get("severity"), "Status": r.get("status"), "Target": str(_d(r.get("target_closure_date"))), "Days overdue": (ctx.today - _d(r.get("target_closure_date"))).days} for r in overdue), ["Complaint", "Subject", "Severity", "Status", "Target", "Days overdue"]))]
    return board


# ----------------------------------------------------------------------------- 7
def osp_vendor(data: Mapping[str, list[dict]], ctx: KPIContext) -> Dashboard:
    board = Dashboard("osp", "OSP Vendor Performance", "OSP_TRANSACTIONS", "What is at OSP vendors, what is late back and how long do vendors take?")
    jobs = [r for r in data.get("osp_jobs", []) if _s(r.get("status")) != "CANCELLED"]
    period = [r for r in jobs if _in_range(r.get("dispatch_date") or r.get("created_at"), ctx.start, ctx.end)]
    at_vendor = [r for r in jobs if _n(r.get("quantity_dispatched")) > _n(r.get("quantity_received")) and _s(r.get("status")) not in CLOSED_WORDS]
    late = [r for r in at_vendor if _d(r.get("expected_return_date")) and _d(r.get("expected_return_date")) < ctx.today]
    tat = [(_d(r.get("receipt_date")) - _d(r.get("dispatch_date"))).days for r in period if _d(r.get("receipt_date")) and _d(r.get("dispatch_date"))]
    sent = sum(_n(r.get("quantity_dispatched")) for r in period)
    rej = sum(_n(r.get("quantity_rejected_at_receipt")) for r in period)
    board.tiles = [
        Tile("Pcs at vendors", _fmt_num(sum(_n(r.get("quantity_dispatched")) - _n(r.get("quantity_received")) for r in at_vendor)), f"{len(at_vendor)} open jobs", "neutral"),
        Tile("Late returns", _fmt_num(len(late)), "Expected return date passed", "good" if not late else "critical"),
        Tile("Avg turnaround", "—" if not tat else f"{sum(tat) / len(tat):.1f} d", "Dispatch → receipt", _status_for(sum(tat) / len(tat) if tat else None, 5, 10, higher_is_better=False)),
        Tile("Receipt rejection", _fmt_pct(_pct(rej, sent)), f"{_fmt_num(rej)} of {_fmt_num(sent)} pcs", _status_for(_pct(rej, sent), 0.5, 2, higher_is_better=False)),
    ]
    if not jobs:
        board.empty = True
        return board
    pend = pd.DataFrame([{"vendor": _label(ctx.parties, r.get("vendor_id")), "pcs": _n(r.get("quantity_dispatched")) - _n(r.get("quantity_received"))} for r in at_vendor]) if at_vendor else pd.DataFrame(columns=["vendor", "pcs"])
    pend = pend.groupby("vendor")["pcs"].sum().reset_index().sort_values("pcs") if not pend.empty else pend
    tat_df = pd.DataFrame([{"vendor": _label(ctx.parties, r.get("vendor_id")), "days": (_d(r.get("receipt_date")) - _d(r.get("dispatch_date"))).days} for r in period if _d(r.get("receipt_date")) and _d(r.get("dispatch_date"))])
    tat_v = tat_df.groupby("vendor")["days"].mean().round(1).reset_index().sort_values("days") if not tat_df.empty else pd.DataFrame(columns=["vendor", "days"])
    board.charts = [Chart("Pieces currently at each vendor", "hbar", pend.tail(15), "pcs", "vendor")]
    if not tat_v.empty:
        board.charts.append(Chart("Average turnaround days by vendor", "hbar", tat_v.tail(15), "days", "vendor"))
    board.tables = [("Late OSP returns", _frame(({"OSP Job": r.get("osp_job_number"), "Vendor": _label(ctx.parties, r.get("vendor_id")), "Part": _label(ctx.parts, r.get("part_id"), "-"), "Dispatched": str(_d(r.get("dispatch_date")) or ""), "Expected": str(_d(r.get("expected_return_date"))), "Pending pcs": _n(r.get("quantity_dispatched")) - _n(r.get("quantity_received")), "Days late": (ctx.today - _d(r.get("expected_return_date"))).days} for r in late), ["OSP Job", "Vendor", "Part", "Dispatched", "Expected", "Pending pcs", "Days late"]))]
    return board


# ----------------------------------------------------------------------------- 8
def order_fulfilment(data: Mapping[str, list[dict]], ctx: KPIContext) -> Dashboard:
    board = Dashboard("fulfilment", "Customer Order Fulfilment", "SUPPLY_CHAIN", "Are we shipping customer schedules complete and on time?")
    orders = [r for r in data.get("supply_customer_orders", []) if _s(r.get("status")) != "CANCELLED"]
    shipped: dict[str, float] = {}
    for e in data.get("supply_downstream_events", []):
        if _s(e.get("event_type")) == "CUSTOMER_DISPATCH":
            key = str(e.get("customer_order_id") or "")
            shipped[key] = shipped.get(key, 0.0) + _n(e.get("qty_pcs"))
    period = [r for r in orders if _in_range(r.get("customer_delivery_date") or r.get("order_date"), ctx.start, ctx.end)]
    ordered = sum(_n(r.get("order_qty_pcs")) for r in period)
    sent = sum(min(shipped.get(str(r.get("id")), 0.0), _n(r.get("order_qty_pcs"))) for r in period)
    due = [r for r in orders if _d(r.get("customer_delivery_date")) and _d(r.get("customer_delivery_date")) < ctx.today and shipped.get(str(r.get("id")), 0.0) + 0.0001 < _n(r.get("order_qty_pcs"))]
    backlog = sum(max(_n(r.get("order_qty_pcs")) - shipped.get(str(r.get("id")), 0.0), 0) for r in orders if _is_open(r))
    complete = sum(1 for r in period if shipped.get(str(r.get("id")), 0.0) + 0.0001 >= _n(r.get("order_qty_pcs")) > 0)
    fill = _pct(sent, ordered)
    board.tiles = [
        Tile("Fill rate", _fmt_pct(fill), f"{_fmt_num(sent)} of {_fmt_num(ordered)} pcs shipped", _status_for(fill, 98, 90)),
        Tile("Orders complete", _fmt_pct(_pct(complete, len(period))), f"{complete} of {len(period)} schedules", _status_for(_pct(complete, len(period)), 95, 85)),
        Tile("Past-due schedules", _fmt_num(len(due)), "Delivery date passed, not fully shipped", "good" if not due else "critical"),
        Tile("Open backlog", _fmt_num(backlog) + " pcs", f"{sum(1 for r in orders if _is_open(r))} open orders", "neutral"),
    ]
    if not orders:
        board.empty = True
        return board
    rows = [{"customer": _label(ctx.parties, r.get("customer_id")), "month": _month(r.get("customer_delivery_date")), "ordered": _n(r.get("order_qty_pcs")), "shipped": min(shipped.get(str(r.get("id")), 0.0), _n(r.get("order_qty_pcs")))} for r in period]
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["customer", "month", "ordered", "shipped"])
    monthly = df.groupby("month")[["ordered", "shipped"]].sum().reset_index().melt(id_vars="month", var_name="series", value_name="pcs").sort_values("month") if not df.empty else pd.DataFrame(columns=["month", "series", "pcs"])
    monthly["series"] = monthly["series"].str.title()
    back = pd.DataFrame([{"customer": _label(ctx.parties, r.get("customer_id")), "backlog": max(_n(r.get("order_qty_pcs")) - shipped.get(str(r.get("id")), 0.0), 0)} for r in orders if _is_open(r)])
    back = back.groupby("customer")["backlog"].sum().reset_index().sort_values("backlog").tail(15) if not back.empty else pd.DataFrame(columns=["customer", "backlog"])
    board.charts = [Chart("Ordered vs shipped pcs by delivery month", "line", monthly, "month", "pcs", color="series"), Chart("Open backlog pcs by customer", "hbar", back, "backlog", "customer")]
    board.tables = [("Past-due schedules", _frame(({"Order": r.get("master_reference_no") or r.get("customer_order_no"), "Customer": _label(ctx.parties, r.get("customer_id")), "Part": _label(ctx.parts, r.get("part_id"), "-"), "Delivery date": str(_d(r.get("customer_delivery_date"))), "Ordered": _n(r.get("order_qty_pcs")), "Shipped": shipped.get(str(r.get("id")), 0.0), "Days late": (ctx.today - _d(r.get("customer_delivery_date"))).days} for r in due), ["Order", "Customer", "Part", "Delivery date", "Ordered", "Shipped", "Days late"]))]
    return board


# ----------------------------------------------------------------------------- 9
def calibration(data: Mapping[str, list[dict]], ctx: KPIContext) -> Dashboard:
    board = Dashboard("calibration", "Gauge Calibration Compliance", "CALIBRATION_VALIDATION", "Are all gauges, fixtures and instruments calibrated and validated in time?")
    assets = [r for r in data.get("quality_assets", []) if _s(r.get("status") or "ACTIVE") == "ACTIVE"]
    overdue = [r for r in assets if _d(r.get("next_due_date")) and _d(r.get("next_due_date")) < ctx.today]
    soon = [r for r in assets if _d(r.get("next_due_date")) and ctx.today <= _d(r.get("next_due_date")) <= ctx.today + timedelta(days=30)]
    val_over = [r for r in assets if _d(r.get("next_validation_due_date")) and _d(r.get("next_validation_due_date")) < ctx.today]
    no_date = [r for r in assets if not _d(r.get("next_due_date"))]
    compliance = _pct(len(assets) - len(overdue), len(assets))
    board.tiles = [
        Tile("Calibration compliance", _fmt_pct(compliance), f"{len(assets)} active assets", _status_for(compliance, 100, 95)),
        Tile("Overdue calibration", _fmt_num(len(overdue)), "Next due date passed", "good" if not overdue else "critical"),
        Tile("Due in 30 days", _fmt_num(len(soon)), "Plan these now", "good" if not soon else "warning"),
        Tile("Validation overdue", _fmt_num(len(val_over)), f"{len(no_date)} assets without due date", "good" if not val_over else "serious"),
    ]
    if not assets:
        board.empty = True
        return board
    months = [(ctx.today.replace(day=1) + timedelta(days=32 * i)).replace(day=1).strftime("%Y-%m") for i in range(6)]
    due = pd.DataFrame([{"month": _month(r.get("next_due_date"))} for r in assets if _d(r.get("next_due_date"))])
    due = due[due["month"].isin(months)].groupby("month").size().reindex(months, fill_value=0).reset_index(name="assets").rename(columns={"index": "month"}) if not due.empty else pd.DataFrame({"month": months, "assets": [0] * 6})
    types = pd.DataFrame([{"type": (_s(r.get("asset_type")) or "OTHER").replace("_", " ").title(), "ok": not (_d(r.get("next_due_date")) and _d(r.get("next_due_date")) < ctx.today)} for r in assets])
    types = types.groupby("type").agg(assets=("ok", "size"), ok=("ok", "sum")).reset_index()
    types["compliance_pct"] = (100 * types["ok"] / types["assets"]).round(1)
    board.charts = [Chart("Calibrations falling due — next 6 months", "bar", due, "month", "assets"), Chart("Compliance % by asset type", "hbar", types.sort_values("compliance_pct"), "compliance_pct", "type")]
    board.tables = [("Overdue gauges", _frame(({"Asset": r.get("asset_code"), "Name": r.get("asset_name"), "Type": r.get("asset_type"), "Location": r.get("location"), "Due date": str(_d(r.get("next_due_date"))), "Days overdue": (ctx.today - _d(r.get("next_due_date"))).days} for r in sorted(overdue, key=lambda r: _d(r.get("next_due_date")))), ["Asset", "Name", "Type", "Location", "Due date", "Days overdue"]))]
    return board


# ----------------------------------------------------------------------------- 10
def npd_apqp(data: Mapping[str, list[dict]], ctx: KPIContext) -> Dashboard:
    board = Dashboard("npd", "NPD & APQP Health", "NPD_APQP", "Are new parts and PPAP submissions on track?")
    orders = [r for r in data.get("npd_orders", []) if _s(r.get("status")) != "CANCELLED"]
    projects = [r for r in data.get("ppap_projects", []) if _s(r.get("status")) != "CANCELLED"]
    open_o = [r for r in orders if _is_open(r)]
    late_o = [r for r in open_o if _d(r.get("delivery_date")) and _d(r.get("delivery_date")) < ctx.today]
    open_p = [r for r in projects if _is_open(r)]
    late_p = [r for r in open_p if _d(r.get("target_submission_date")) and _d(r.get("target_submission_date")) < ctx.today]
    avg_done = sum(_n(r.get("completion_percent")) for r in open_p) / len(open_p) if open_p else None
    board.tiles = [
        Tile("Open NPD orders", _fmt_num(len(open_o)), f"{len(orders)} in register", "neutral"),
        Tile("NPD orders late", _fmt_num(len(late_o)), "Delivery date passed", "good" if not late_o else "critical"),
        Tile("PPAP avg completion", "—" if avg_done is None else f"{avg_done:.0f}%", f"{len(open_p)} open projects", _status_for(avg_done, 80, 50)),
        Tile("PPAP past target", _fmt_num(len(late_p)), "Target submission date passed", "good" if not late_p else "critical"),
    ]
    if not orders and not projects:
        board.empty = True
        return board
    st_df = pd.DataFrame([{"status": (_s(r.get("status")) or "UNKNOWN").replace("_", " ").title(), "kind": "NPD order"} for r in orders] + [{"status": (_s(r.get("status")) or "UNKNOWN").replace("_", " ").title(), "kind": "PPAP project"} for r in projects])
    st_df = st_df.groupby(["status", "kind"]).size().reset_index(name="count")
    prog = pd.DataFrame([{"project": str(r.get("project_code") or "-"), "completion": _n(r.get("completion_percent"))} for r in open_p]).sort_values("completion").head(15) if open_p else pd.DataFrame(columns=["project", "completion"])
    board.charts = [Chart("Status of NPD orders and PPAP projects", "stacked", st_df, "status", "count", color="kind")]
    if not prog.empty:
        board.charts.append(Chart("Least-complete open PPAP projects (%)", "hbar", prog, "completion", "project"))
    board.tables = [("Late NPD orders / PPAP projects", _frame(([{"Reference": r.get("order_number"), "Type": "NPD order", "Part": _label(ctx.parts, r.get("part_id"), "-"), "Due": str(_d(r.get("delivery_date"))), "Days late": (ctx.today - _d(r.get("delivery_date"))).days} for r in late_o] + [{"Reference": r.get("project_code"), "Type": "PPAP", "Part": _label(ctx.parts, r.get("part_id"), "-"), "Due": str(_d(r.get("target_submission_date"))), "Days late": (ctx.today - _d(r.get("target_submission_date"))).days} for r in late_p]), ["Reference", "Type", "Part", "Due", "Days late"]))]
    return board


DASHBOARDS: list[tuple[str, str, str, tuple[str, ...], Callable[[Mapping[str, list[dict]], KPIContext], Dashboard]]] = [
    # key, title, module_key, tables needed, builder
    ("supplier-otd", "Supplier On-Time Delivery", "SUPPLY_CHAIN", ("supply_rm_purchase_orders", "supply_rm_receipts", "supply_forging_orders", "supply_forging_receipts"), supplier_delivery),
    ("po-pipeline", "Purchase Order Pipeline", "SUPPLY_CHAIN", ("supply_purchase_orders",), po_pipeline),
    ("fulfilment", "Customer Order Fulfilment", "SUPPLY_CHAIN", ("supply_customer_orders", "supply_downstream_events"), order_fulfilment),
    ("incoming-quality", "Incoming Material Quality", "MATERIAL_INWARD", ("inward_lots",), incoming_quality),
    ("rmtc", "RMTC Approval & Compliance", "RMTC_ENTRY", ("rmtc_approvals",), rmtc_compliance),
    ("lab-inspection", "Lab & Inspection First-Pass Yield", "METLAB_REPORT", ("lab_tests", "inspection_reports"), lab_inspection),
    ("osp", "OSP Vendor Performance", "OSP_TRANSACTIONS", ("osp_jobs",), osp_vendor),
    ("complaints", "Complaints & CAPA (8D)", "COMPLAINT_MANAGEMENT", ("quality_complaints",), complaints_capa),
    ("calibration", "Gauge Calibration Compliance", "CALIBRATION_VALIDATION", ("quality_assets",), calibration),
    ("npd", "NPD & APQP Health", "NPD_APQP", ("npd_orders", "ppap_projects"), npd_apqp),
]
