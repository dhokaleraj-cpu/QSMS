"""R37b · Controlled save of the Part Master Supplier / FSI Part price-history grid.

Root cause fixed here (live evidence 26-10-2026, PostgREST P0001 on POST
part_supplier_price_history): the grid carried no row id, so a row was matched back to
the database by its natural key (Part + Supplier + RM record + UOM + Start Date). When the
user changed a row's Start Date (or UOM) the lookup missed, the edited row was INSERTED as
a new period and the guard trigger rejected it because it overlapped the original row it
was meant to replace ("Price period 01-08-2026 to open overlaps the existing period
01-09-2026 to open"). Rows saved before the failing one were already written (partial save).

Now every grid row carries its hidden database id, the whole edited set is validated
before the first write (one clear message, no partial save), the previous period is
closed automatically exactly like the database trigger does for a new open price, and the
writes are ordered so every intermediate state passes the non-overlap guard.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Iterable, Mapping, Sequence

PRICE_TABLE = "part_supplier_price_history"
EDITABLE_FIELDS = (
    "start_date", "end_date", "price", "freight", "tool_cost", "packing_forwarding", "profit",
    "icc_rejection", "currency", "uom", "remarks", "status",
)


def _d(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    if not text or text.lower() in {"nat", "nan", "none"}:
        return None
    return date.fromisoformat(text)


def _fmt(value: date | None) -> str:
    return value.strftime("%d-%m-%Y") if value else "open"


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else out   # NaN -> None


@dataclass
class _Row:
    id: str | None
    data: dict[str, Any]
    original: dict[str, Any] | None = None
    user_edited_end: bool = True
    label: str = ""

    @property
    def start(self) -> date | None:
        return _d(self.data.get("start_date"))

    @property
    def end(self) -> date | None:
        return _d(self.data.get("end_date"))

    @property
    def uom(self) -> str:
        return str(self.data.get("uom") or "KGS").strip().upper()

    @property
    def active(self) -> bool:
        return str(self.data.get("status") or "ACTIVE").upper() == "ACTIVE"


@dataclass
class PriceHistoryPlan:
    updates: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    inserts: list[dict[str, Any]] = field(default_factory=list)
    auto_closed: list[str] = field(default_factory=list)

    @property
    def changed(self) -> int:
        return len(self.updates) + len(self.inserts)


def _clean_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in EDITABLE_FIELDS:
        if key not in row:
            continue
        value = row.get(key)
        if key in {"start_date", "end_date"}:
            d = _d(value); out[key] = d.isoformat() if d else None
        elif key in {"price", "freight", "tool_cost", "packing_forwarding", "profit", "icc_rejection"}:
            out[key] = _num(value)
        elif key in {"currency", "uom", "status"}:
            out[key] = str(value or {"currency": "INR", "uom": "KGS", "status": "ACTIVE"}[key]).strip().upper()
        else:
            text = str(value or "").strip(); out[key] = text or None
    return out


def _same(key: str, a: Any, b: Any) -> bool:
    if key in {"start_date", "end_date"}:
        return _d(a) == _d(b)
    if key in {"price", "freight", "tool_cost", "packing_forwarding", "profit", "icc_rejection"}:
        na, nb = _num(a), _num(b)
        return (na is None and nb is None) or (na is not None and nb is not None and abs(na - nb) < 1e-9)
    if key in {"currency", "uom", "status"}:
        return str(a or "").strip().upper() == str(b or "").strip().upper()
    return (str(a or "").strip() or None) == (str(b or "").strip() or None)


def plan_price_history_save(existing: Sequence[Mapping[str, Any]], edited: Iterable[Mapping[str, Any]], *, base: Mapping[str, Any]) -> PriceHistoryPlan:
    """Validate the complete edited grid and return ordered writes.

    ``existing`` = database rows of this Part + Supplier + RM record. ``edited`` = grid rows as
    payload dicts (``id`` for saved rows, none for new rows). ``base`` = identity columns
    (part_id, supplier_id, raw_material_detail_id) added to new rows.
    Raises ValueError with a row-specific message; nothing is written by this function.
    """
    by_id = {str(r.get("id")): dict(r) for r in existing if r.get("id")}
    rows: list[_Row] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(edited, start=1):
        rid = str(raw.get("id") or "").strip() or None
        payload = _clean_payload(raw)
        label = f"Price row {index}"
        if not payload.get("start_date") and payload.get("price") is None:
            continue   # blank grid row
        if not payload.get("start_date"):
            raise ValueError(f"{label}: Start Date is required.")
        if payload.get("price") is None:
            raise ValueError(f"{label} ({_fmt(_d(payload['start_date']))}): Basic Rate is required.")
        if payload["price"] < 0:
            raise ValueError(f"{label}: Basic Rate cannot be negative.")
        for key in ("freight", "tool_cost", "packing_forwarding", "profit", "icc_rejection"):
            if payload.get(key) is not None and payload[key] < 0:
                raise ValueError(f"{label}: {key.replace('_', ' ').title()} cannot be negative.")
        if payload.get("status") not in {None, "ACTIVE", "INACTIVE"}:
            raise ValueError(f"{label}: Status must be ACTIVE or INACTIVE.")
        start, end = _d(payload["start_date"]), _d(payload.get("end_date"))
        if end and start and end < start:
            raise ValueError(f"{label}: End Date {_fmt(end)} is before Start Date {_fmt(start)}.")
        if rid and rid not in by_id:
            # Legacy / stale grid: id not found for this Part + Supplier + RM record.
            raise ValueError(f"{label}: this price row no longer exists for the selected Part / Supplier / Raw Material. Refresh the page and save again.")
        if rid in seen_ids:
            continue
        if not rid:
            # Backward compatible natural-key match (grid without the hidden id column).
            match = next((r for r in existing if str(r.get("id")) not in seen_ids and _d(r.get("start_date")) == start
                          and str(r.get("uom") or "KGS").upper() == str(payload.get("uom") or "KGS").upper()), None)
            rid = str(match.get("id")) if match else None
        original = by_id.get(rid) if rid else None
        if rid:
            seen_ids.add(rid)
        user_end = original is None or not _same("end_date", original.get("end_date"), payload.get("end_date"))
        rows.append(_Row(rid, payload, original, user_end, label))
    # Saved rows that are not in the grid stay in the database (deletion is password-controlled).
    for rid, original in by_id.items():
        if rid not in seen_ids:
            rows.append(_Row(rid, _clean_payload(original), original, False, f"Saved row {_fmt(_d(original.get('start_date')))}"))

    # Duplicate start dates are rejected by the database unique key (Part + Supplier + UOM + Start Date).
    starts: dict[tuple[str, date], _Row] = {}
    for row in rows:
        key = (row.uom, row.start)
        if key in starts:
            raise ValueError(f"Two price rows start on {_fmt(row.start)} ({row.uom}). Each price revision needs its own Start Date.")
        starts[key] = row

    plan = PriceHistoryPlan()
    # Close the previous period automatically (same rule the database applies to a new open price).
    for uom in sorted({r.uom for r in rows}):
        active = sorted([r for r in rows if r.uom == uom and r.active], key=lambda r: r.start)
        for prev, nxt in zip(active, active[1:]):
            if prev.end is None or prev.end >= nxt.start:
                if prev.end is None or not prev.user_edited_end:
                    new_end = nxt.start - timedelta(days=1)
                    prev.data["end_date"] = new_end.isoformat()
                    plan.auto_closed.append(f"{_fmt(prev.start)} closed on {_fmt(new_end)}")
                else:
                    raise ValueError(
                        f"Price period {_fmt(nxt.start)} to {_fmt(nxt.end)} overlaps {_fmt(prev.start)} to {_fmt(prev.end)}. "
                        f"Set the End Date of the {_fmt(prev.start)} row to {_fmt(nxt.start - timedelta(days=1))} or earlier, or change the Start Date.")
        for a_index, a in enumerate(active):
            for b in active[a_index + 1:]:
                a_end = a.end or date.max; b_end = b.end or date.max
                if a.start <= b_end and b.start <= a_end:
                    raise ValueError(f"Price period {_fmt(b.start)} to {_fmt(b.end)} overlaps {_fmt(a.start)} to {_fmt(a.end)}. Correct the dates and save again.")

    # Order the writes so every intermediate state passes the non-overlap guard:
    # 1) rows that shrink / become inactive, 2) other changed rows by start date, 3) new rows by start date.
    shrinking: list[tuple[date, str, dict]] = []; growing: list[tuple[date, str, dict]] = []
    for row in rows:
        if not row.id:
            continue
        original = row.original or {}
        changes = {k: v for k, v in row.data.items() if not _same(k, original.get(k), v)}
        if not changes:
            continue
        o_start, o_end = _d(original.get("start_date")), _d(original.get("end_date"))
        was_active = str(original.get("status") or "ACTIVE").upper() == "ACTIVE"
        inside = (o_start is not None and row.start >= o_start and (o_end is None or (row.end is not None and row.end <= o_end)))
        target = shrinking if (not row.active or (was_active and inside)) else growing
        target.append((row.start, row.id, changes))
    for bucket in (sorted(shrinking, key=lambda t: t[0]), sorted(growing, key=lambda t: t[0])):
        plan.updates.extend((rid, changes) for _start, rid, changes in bucket)
    for row in sorted((r for r in rows if not r.id), key=lambda r: r.start):
        plan.inserts.append({**dict(base), **row.data})
    return plan


def save_price_history_grid(repo: Any, *, part_id: str, supplier_id: str, raw_material_detail_id: str | None, edited: Iterable[Mapping[str, Any]]) -> PriceHistoryPlan:
    """Validate, plan and write the grid. Returns the executed plan."""
    if not part_id or not supplier_id:
        raise ValueError("Select the Part and Supplier Raw Material record before saving price history.")
    eq: dict[str, Any] = {"part_id": part_id, "supplier_id": supplier_id}
    if raw_material_detail_id:
        eq["raw_material_detail_id"] = raw_material_detail_id
    existing = repo.select(PRICE_TABLE, eq=eq, order_by="start_date", limit=5000)
    base = {"part_id": part_id, "supplier_id": supplier_id, "raw_material_detail_id": raw_material_detail_id}
    plan = plan_price_history_save(existing, edited, base=base)
    for rid, changes in plan.updates:
        repo.update(PRICE_TABLE, rid, changes)
    for payload in plan.inserts:
        repo.insert(PRICE_TABLE, payload)
    return plan
