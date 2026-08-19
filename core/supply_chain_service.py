from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from core.repository import Repository
from core.selection_labels import party_label

MONTHS = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December",
}


def number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def monthly_reference(part_number: str, month: int, year: int) -> str:
    part = str(part_number or "").strip()
    if not part:
        raise ValueError("Part Number is required before generating a monthly schedule reference.")
    return f"{part}_{int(month):02d}_{int(year):04d}"


class SupplyChainService:
    def __init__(self, repo: Repository | None = None):
        self.repo = repo or Repository()

    def parties(self) -> list[dict]:
        return self.repo.select("parties", eq={"status": "ACTIVE"}, order_by="party_name", limit=5000)

    def customers(self) -> list[dict]:
        return self.repo.select("parties", contains={"party_types": ["CUSTOMER"]}, eq={"status": "ACTIVE"}, order_by="party_name", limit=3000)

    def suppliers(self) -> list[dict]:
        rows = self.parties()
        return [r for r in rows if set(str(v).upper() for v in (r.get("party_types") or [])) & {"SUPPLIER", "STEEL_MILL", "OSP_VENDOR"}]

    def parts(self) -> list[dict]:
        return self.repo.select("parts", eq={"status": "ACTIVE"}, order_by="part_number", limit=5000)

    def raw_material_options(self, part_id: str) -> list[dict]:
        return self.repo.select("part_raw_material_details", eq={"part_id": part_id, "status": "ACTIVE"}, order_by="sequence_no", limit=1000)

    def customer_orders(self) -> list[dict]:
        return self.repo.select("supply_customer_orders", order_by="created_at", desc=True, limit=10000)

    def order(self, order_id: str) -> dict | None:
        return self.repo.get("supply_customer_orders", order_id)

    def order_label(self, order: Mapping[str, Any], parts: Mapping[str, Mapping[str, Any]] | None = None, parties: Mapping[str, Mapping[str, Any]] | None = None) -> str:
        parts = parts or {}; parties = parties or {}
        part = parts.get(str(order.get("part_id"))) or {}
        customer = parties.get(str(order.get("customer_id"))) or {}
        return (
            f"{order.get('master_reference_no')} · Pos {order.get('order_position') or '-'} · "
            f"{part.get('part_number') or ''} · {party_label(customer)} · {number(order.get('order_qty_pcs')):,.0f} pcs"
        )

    def create_customer_order(self, payload: Mapping[str, Any]) -> dict:
        p = dict(payload)
        qty = number(p.get("order_qty_pcs")); gross = number(p.get("gross_weight_kg_snapshot"))
        if qty <= 0 or gross <= 0:
            raise ValueError("Order Quantity and Forging Supplier Gross Weight must be greater than zero.")
        p["required_rm_kg"] = round(qty * gross, 3)
        if str(p.get("order_type")) == "MONTHLY_SCHEDULE":
            schedule = str(p.get("schedule_month") or "")[:10]
            if not schedule:
                raise ValueError("Month and Year are required for a Monthly Schedule.")
            y, m = int(schedule[:4]), int(schedule[5:7])
            part = self.repo.get("parts", str(p.get("part_id") or "")) or {}
            p["master_reference_no"] = monthly_reference(str(part.get("part_number") or ""), m, y)
            p["customer_order_no"] = None
            p["order_position"] = p.get("order_position") or f"{m:02d}-{y}"
        else:
            ref = str(p.get("customer_order_no") or "").strip()
            if not ref:
                raise ValueError("Customer Order Number is required for a Purchase Order.")
            p["master_reference_no"] = ref
        return self.repo.insert("supply_customer_orders", p)

    def totals(self, order_id: str) -> dict[str, float]:
        rm_pos = self.repo.select("supply_rm_purchase_orders", eq={"customer_order_id": order_id}, limit=5000)
        rm_receipts = self.repo.select("supply_rm_receipts", eq={"customer_order_id": order_id}, limit=5000)
        rm_dispatch = self.repo.select("supply_rm_dispatches", eq={"customer_order_id": order_id}, limit=5000)
        forg_orders = self.repo.select("supply_forging_orders", eq={"customer_order_id": order_id}, limit=5000)
        forg_receipts = self.repo.select("supply_forging_receipts", eq={"customer_order_id": order_id}, limit=5000)
        downstream = self.repo.select("supply_downstream_events", eq={"customer_order_id": order_id}, limit=10000)
        return {
            "rm_ordered_kg": sum(number(r.get("ordered_qty_kg")) for r in rm_pos if r.get("status") != "CANCELLED"),
            "rm_received_kg": sum(number(r.get("received_qty_kg")) for r in rm_receipts),
            "rm_dispatched_kg": sum(number(r.get("qty_kg")) for r in rm_dispatch),
            "forging_ordered_pcs": sum(number(r.get("order_qty_pcs")) for r in forg_orders if r.get("status") != "CANCELLED"),
            "forging_received_pcs": sum(number(r.get("received_qty_pcs")) for r in forg_receipts),
            "rm_consumed_kg": sum(number(r.get("actual_rm_consumed_kg")) if r.get("actual_rm_consumed_kg") is not None else number(r.get("received_qty_pcs"))*number(r.get("gross_weight_kg_snapshot")) for r in forg_receipts),
            "machined_pcs": sum(number(r.get("qty_pcs")) for r in downstream if r.get("event_type") == "MACHINING"),
            "finished_goods_pcs": sum(number(r.get("qty_pcs")) for r in downstream if r.get("event_type") == "FINISHED_GOODS"),
            "customer_dispatched_pcs": sum(number(r.get("qty_pcs")) for r in downstream if r.get("event_type") == "CUSTOMER_DISPATCH"),
        }

    def sync_order_status(self, order_id: str) -> str:
        order = self.order(order_id) or {}
        if not order or str(order.get("status")) == "CANCELLED":
            return str(order.get("status") or "")
        totals = self.totals(order_id); qty = number(order.get("order_qty_pcs"))
        if qty > 0 and totals["customer_dispatched_pcs"] >= qty:
            status = "COMPLETED"
        elif any(value > 0 for value in totals.values()):
            status = "IN_PROGRESS"
        else:
            status = "OPEN"
        if str(order.get("status")) != status:
            self.repo.update("supply_customer_orders", order_id, {"status": status})
        return status

    def supplier_balances(self, order_id: str) -> list[dict]:
        order = self.order(order_id) or {}
        suppliers = {str(r["id"]): r for r in self.parties()}
        dispatches = self.repo.select("supply_rm_dispatches", eq={"customer_order_id": order_id}, limit=5000)
        receipts = self.repo.select("supply_forging_receipts", eq={"customer_order_id": order_id}, limit=5000)
        ids = sorted({str(r.get("forging_supplier_id") or "") for r in dispatches + receipts if r.get("forging_supplier_id")})
        rows = []
        for sid in ids:
            sent = sum(number(r.get("qty_kg")) for r in dispatches if str(r.get("forging_supplier_id")) == sid)
            consumed = sum(
                number(r.get("actual_rm_consumed_kg")) if r.get("actual_rm_consumed_kg") is not None else number(r.get("received_qty_pcs"))*number(r.get("gross_weight_kg_snapshot"))
                for r in receipts if str(r.get("forging_supplier_id")) == sid
            )
            rows.append({"Supplier": party_label(suppliers.get(sid) or {}), "RM Dispatched kg": round(sent,3), "RM Consumed kg": round(consumed,3), "RM Balance kg": round(sent-consumed,3), "Order Reference": order.get("master_reference_no")})
        return rows

    def timeline(self, order_id: str) -> list[dict]:
        order = self.order(order_id) or {}
        events = [{"Date": order.get("order_date"), "Stage": "Customer Order", "Reference": order.get("master_reference_no"), "Quantity": f"{number(order.get('order_qty_pcs')):,.0f} pcs", "Status": order.get("status"), "Remarks": order.get("remarks") or ""}]
        table_map = [
            ("supply_rm_purchase_orders", "RM Procurement", "order_date", "supplier_order_no", "ordered_qty_kg", "kg"),
            ("supply_rm_receipts", "RM Receipt", "receipt_date", "receipt_number", "received_qty_kg", "kg"),
            ("supply_rm_dispatches", "RM Dispatch to Forging", "dispatch_date", "dispatch_number", "qty_kg", "kg"),
            ("supply_forging_orders", "Forging Order", "order_date", "supplier_order_no", "order_qty_pcs", "pcs"),
            ("supply_forging_receipts", "Forging Receipt", "receipt_date", "receipt_number", "received_qty_pcs", "pcs"),
        ]
        for table, stage, date_key, ref_key, qty_key, unit in table_map:
            for row in self.repo.select(table, eq={"customer_order_id": order_id}, limit=10000):
                events.append({"Date": row.get(date_key), "Stage": stage, "Reference": row.get(ref_key), "Quantity": f"{number(row.get(qty_key)):,.3f} {unit}", "Status": row.get("status") or "POSTED", "Remarks": row.get("remarks") or ""})
        for row in self.repo.select("supply_downstream_events", eq={"customer_order_id": order_id}, limit=10000):
            label = {"MACHINING":"Machining", "FINISHED_GOODS":"Finished Goods", "CUSTOMER_DISPATCH":"Customer Dispatch"}.get(str(row.get("event_type")), str(row.get("event_type")))
            extra = " · ".join(x for x in [f"Invoice {row.get('invoice_no')}" if row.get('invoice_no') else "", f"ASN {row.get('asn_no')}" if row.get('asn_no') else ""] if x)
            events.append({"Date": row.get("event_date"), "Stage": label, "Reference": row.get("reference_no"), "Quantity": f"{number(row.get('qty_pcs')):,.0f} pcs", "Status": "POSTED", "Remarks": (extra + (" · " if extra and row.get("remarks") else "") + str(row.get("remarks") or ""))})
        events.sort(key=lambda r: str(r.get("Date") or ""))
        return events
