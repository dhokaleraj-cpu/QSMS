from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Mapping, Sequence

from core.repository import Repository
from core.selection_labels import party_label
from core.purchase_order_reporting import DEFAULT_SPECIAL_INSTRUCTIONS

MONTHS = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December",
}

SUPPLY_TABLES = (
    "supply_customer_orders", "supply_rm_purchase_orders", "supply_rm_receipts",
    "supply_rm_dispatches", "supply_forging_orders", "supply_forging_receipts",
    "supply_downstream_events",
)

FLOW_FSI_RM = "FSI_RM"
FLOW_DIRECT_FORGING = "DIRECT_FORGING"
FLOW_LABELS = {
    FLOW_FSI_RM: "Flow 1 · RM Responsible FSI",
    FLOW_DIRECT_FORGING: "Flow 2 · RM Responsible Forger / Supplier",
}
_FLOW_RE = re.compile(r"\s*\[\[QCMS_SUPPLY_FLOW=(FSI_RM|DIRECT_FORGING)\]\]\s*", re.I)


def clean_flow_remarks(value: Any) -> str:
    return _FLOW_RE.sub(" ", str(value or "")).strip()


def flow_remarks(value: Any, flow: str) -> str:
    clean = clean_flow_remarks(value)
    code = flow if flow in FLOW_LABELS else FLOW_FSI_RM
    return f"{clean} [[QCMS_SUPPLY_FLOW={code}]]".strip()


def number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def month_start(value: date | str | None = None) -> date:
    if isinstance(value, date):
        d = value
    else:
        try:
            d = datetime.fromisoformat(str(value or date.today().isoformat())[:10]).date()
        except ValueError:
            d = date.today()
    return date(d.year, d.month, 1)


def add_months(value: date, months: int) -> date:
    index = value.year * 12 + (value.month - 1) + int(months)
    return date(index // 12, index % 12 + 1, 1)


def monthly_reference(part_number: str, month: int, year: int) -> str:
    part = str(part_number or "").strip()
    if not part:
        raise ValueError("Part Number is required before generating a monthly schedule reference.")
    return f"{part}_{int(month):02d}_{int(year):04d}"


def normalize_match(value: Any) -> str:
    """Normalize user-entered identifiers for duplicate/import matching.

    Spaces, punctuation and case differences do not create a second business record.
    This intentionally supports customer files where order/position values may be
    formatted slightly differently from the QCMS screen.
    """
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def parse_business_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text).date().isoformat()
    except ValueError:
        return None


def parse_import_quantity(value: Any) -> float:
    """Parse German/European style customer schedule quantities (e.g. 15.000)."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip().replace(" ", "")
    if not text:
        return 0.0
    # The Kessler LTE sheet uses a dot as the thousands separator in Quantity.
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", text):
        text = text.replace(".", "")
    elif "," in text and "." not in text:
        text = text.replace(",", ".")
    elif "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


# Compatibility notes retained for v4.13.7 regression contracts:
# Raw Material Purchase Orders remain blocked when system stock covers the rolling three-month schedule quantity.
# Linked execution stages still carry the controlled PO header reference using: "purchase_order_id": header.get("id")

class SupplyChainService:
    def __init__(self, repo: Repository | None = None):
        self.repo = repo or Repository()

    # ------------------------------------------------------------------ masters
    def parties(self) -> list[dict]:
        return self.repo.select("parties", eq={"status": "ACTIVE"}, order_by="party_name", limit=5000)

    def customers(self) -> list[dict]:
        return self.repo.select("parties", contains={"party_types": ["CUSTOMER"]}, eq={"status": "ACTIVE"}, order_by="party_name", limit=3000)

    def suppliers(self) -> list[dict]:
        rows = self.parties()
        return [r for r in rows if set(str(v).upper() for v in (r.get("party_types") or [])) & {"SUPPLIER", "STEEL_MILL", "OSP_VENDOR"}]

    def parts(self) -> list[dict]:
        return self.repo.select("parts", eq={"status": "ACTIVE"}, order_by="part_number", limit=5000)

    def material_grades(self) -> list[dict]:
        return self.repo.select("material_grades", eq={"status": "ACTIVE"}, order_by="grade_code", limit=3000)

    def raw_material_options(self, part_id: str) -> list[dict]:
        return self.repo.select("part_raw_material_details", eq={"part_id": part_id, "status": "ACTIVE"}, order_by="sequence_no", limit=1000)

    def master_maps(self) -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
        return (
            {str(r["id"]): r for r in self.parts()},
            {str(r["id"]): r for r in self.parties()},
            {str(r["id"]): r for r in self.material_grades()},
        )

    # ---------------------------------------------------------------- transactions
    def customer_orders(self) -> list[dict]:
        rows = self.repo.select("supply_customer_orders", order_by="created_at", desc=True, limit=10000)
        result = []
        for row in rows:
            item = dict(row)
            item["supply_flow"] = self.flow_for_order(row)
            item["remarks"] = clean_flow_remarks(row.get("remarks"))
            result.append(item)
        return result

    def purchase_orders(self) -> list[dict]:
        return self.repo.select("supply_purchase_orders", order_by="created_at", desc=True, limit=10000)

    def purchase_order_items(self, purchase_order_id: str | None = None) -> list[dict]:
        return self.repo.select("supply_purchase_order_items", eq={"purchase_order_id": purchase_order_id} if purchase_order_id else None, order_by="created_at", desc=False, limit=10000)

    def purchase_order_sources(self, purchase_order_id: str | None = None) -> list[dict]:
        return self.repo.select("supply_purchase_order_sources", eq={"purchase_order_id": purchase_order_id} if purchase_order_id else None, order_by="created_at", desc=False, limit=10000)

    def raw_material_for_supplier(self, part_id: str, supplier_id: str, preferred_id: str | None = None) -> dict | None:
        if preferred_id:
            row = self.repo.get("part_raw_material_details", preferred_id) or {}
            if row and str(row.get("part_id")) == str(part_id) and str(row.get("supplier_id")) == str(supplier_id) and str(row.get("status") or "ACTIVE") == "ACTIVE":
                return row
        rows = self.repo.select("part_raw_material_details", eq={"part_id": part_id, "supplier_id": supplier_id, "status": "ACTIVE"}, order_by="sequence_no", limit=100)
        return rows[0] if rows else None

    def raw_material_technical_data(self, raw_material_detail_id: str | None) -> list[dict]:
        if not raw_material_detail_id:
            return []
        return self.repo.select("part_raw_material_technical_data", eq={"raw_material_detail_id": raw_material_detail_id, "status": "ACTIVE"}, order_by="sequence_no", limit=500)

    def technical_data_snapshot(self, raw: Mapping[str, Any], part: Mapping[str, Any]) -> list[dict[str, str]]:
        custom = self.raw_material_technical_data(str(raw.get("id") or ""))
        custom_map = {normalize_match(r.get("heading")): {"heading": str(r.get("heading") or "").strip(), "value": str(r.get("value_text") or "").strip()} for r in custom if bool(r.get("include_on_po", True)) and str(r.get("heading") or "").strip() and str(r.get("value_text") or "").strip()}
        standard = [
            ("Raw Material Section", raw.get("material_section_name")),
            ("Forge wt", f"{number(raw.get('forging_weight_kg') or part.get('forging_weight_kg')):g} Kgs" if (raw.get("forging_weight_kg") is not None or part.get("forging_weight_kg") is not None) else ""),
            ("Gross wt", f"{number(raw.get('gross_weight_kg') or part.get('gross_weight_kg')):g} Kgs" if (raw.get("gross_weight_kg") is not None or part.get("gross_weight_kg") is not None) else ""),
            ("Input wt", f"{number(raw.get('input_weight_kg')):g} kg/part" if raw.get("input_weight_kg") is not None else ""),
            ("Section Size", raw.get("section_size") or part.get("section_size")),
            ("Forging Route", raw.get("forging_route") or part.get("manufacturing_route")),
        ]
        result: list[dict[str, str]] = []
        used: set[str] = set()
        for heading, value in standard:
            key = normalize_match(heading)
            if key in custom_map:
                result.append(custom_map[key]); used.add(key)
            elif str(value or "").strip():
                result.append({"heading": heading, "value": str(value).strip()})
        for r in custom:
            key = normalize_match(r.get("heading"))
            if key in used or not bool(r.get("include_on_po", True)):
                continue
            heading = str(r.get("heading") or "").strip(); value = str(r.get("value_text") or "").strip()
            if heading and value:
                result.append({"heading": heading, "value": value}); used.add(key)
        return result

    def price_history(self, part_id: str, supplier_id: str, *, uom: str | None = None) -> list[dict]:
        rows = self.repo.select("part_supplier_price_history", eq={"part_id": part_id, "supplier_id": supplier_id, "status": "ACTIVE"}, order_by="start_date", desc=True, limit=1000)
        if uom:
            rows = [r for r in rows if str(r.get("uom") or "").upper() == str(uom).upper()]
        return rows

    def current_price(self, part_id: str, supplier_id: str, *, on_date: date | str | None = None, uom: str = "KGS") -> float:
        target = parse_business_date(on_date) or date.today().isoformat()
        for row in self.price_history(part_id, supplier_id, uom=uom):
            start = str(row.get("start_date") or "")[:10]; end = str(row.get("end_date") or "")[:10]
            if start and start <= target and (not end or target <= end):
                return number(row.get("price"))
        return 0.0

    def _record_purchase_price(self, *, part_id: str, supplier_id: str, raw_material_detail_id: str | None, po_date: date | str, price: float, uom: str, currency: str, source_item_id: str) -> None:
        price = max(number(price), 0.0)
        if price <= 0:
            return
        target_text = parse_business_date(po_date) or date.today().isoformat()
        target = date.fromisoformat(target_text)
        history = self.price_history(part_id, supplier_id, uom=uom)
        same_start = next((r for r in history if str(r.get("start_date") or "")[:10] == target_text), None)
        if same_start:
            self.repo.update("part_supplier_price_history", str(same_start["id"]), {"price": price, "currency": currency, "raw_material_detail_id": raw_material_detail_id, "source_purchase_order_item_id": source_item_id})
            return
        covering = next((r for r in history if str(r.get("start_date") or "")[:10] <= target_text and (not str(r.get("end_date") or "")[:10] or target_text <= str(r.get("end_date") or "")[:10])), None)
        if covering and abs(number(covering.get("price")) - price) < 0.000001:
            if not covering.get("source_purchase_order_item_id"):
                self.repo.update("part_supplier_price_history", str(covering["id"]), {"source_purchase_order_item_id": source_item_id})
            return
        next_start = min((date.fromisoformat(str(r.get("start_date"))[:10]) for r in history if str(r.get("start_date") or "")[:10] > target_text), default=None)
        new_end = (next_start - timedelta(days=1)).isoformat() if next_start else None
        if covering:
            old_end = str(covering.get("end_date") or "")[:10] or None
            self.repo.update("part_supplier_price_history", str(covering["id"]), {"end_date": (target - timedelta(days=1)).isoformat()})
            new_end = old_end
        self.repo.insert("part_supplier_price_history", {"part_id": part_id, "supplier_id": supplier_id, "raw_material_detail_id": raw_material_detail_id, "start_date": target_text, "end_date": new_end, "price": price, "currency": currency or "INR", "uom": str(uom or "KGS").upper(), "source_purchase_order_item_id": source_item_id, "status": "ACTIVE"})

    def rm_purchase_orders(self) -> list[dict]:
        return self.repo.select("supply_rm_purchase_orders", order_by="created_at", desc=True, limit=10000)

    def rm_receipts(self) -> list[dict]:
        return self.repo.select("supply_rm_receipts", order_by="created_at", desc=True, limit=10000)

    def rm_dispatches(self) -> list[dict]:
        return self.repo.select("supply_rm_dispatches", order_by="created_at", desc=True, limit=10000)

    def forging_orders(self) -> list[dict]:
        return self.repo.select("supply_forging_orders", order_by="created_at", desc=True, limit=10000)

    def forging_receipts(self) -> list[dict]:
        return self.repo.select("supply_forging_receipts", order_by="created_at", desc=True, limit=10000)

    def downstream_events(self) -> list[dict]:
        return self.repo.select("supply_downstream_events", order_by="created_at", desc=True, limit=20000)

    def inward_register(self) -> list[dict]:
        return self.repo.select("v_qsms_inward_register", order_by="created_at", desc=True, limit=10000)

    def order(self, order_id: str) -> dict | None:
        return self.repo.get("supply_customer_orders", order_id)

    def flow_for_order(self, order: Mapping[str, Any] | str | None) -> str:
        if isinstance(order, str):
            order = self.order(order) or {}
        order = order or {}
        match = _FLOW_RE.search(str(order.get("remarks") or ""))
        if match:
            code = str(match.group(1) or "").upper()
            return code if code in FLOW_LABELS else FLOW_FSI_RM
        # Backward compatibility: all pre-v4.12.4 orders are the original FSI-RM flow.
        return FLOW_FSI_RM

    def order_label(self, order: Mapping[str, Any], parts: Mapping[str, Mapping[str, Any]] | None = None, parties: Mapping[str, Mapping[str, Any]] | None = None) -> str:
        parts = parts or {}; parties = parties or {}
        part = parts.get(str(order.get("part_id"))) or {}
        customer = parties.get(str(order.get("customer_id"))) or {}
        return (
            f"{order.get('master_reference_no')} · Pos {order.get('order_position') or '-'} · "
            f"{part.get('part_number') or ''} · FSI {part.get('fsi_part_number') or '-'} · {party_label(customer)} · {number(order.get('order_qty_pcs')):,.0f} pcs"
        )

    def order_context(self, order: Mapping[str, Any] | str) -> dict[str, Any]:
        if isinstance(order, str):
            order = self.order(order) or {}
        parts, parties, grades = self.master_maps()
        part = parts.get(str(order.get("part_id"))) or {}
        customer = parties.get(str(order.get("customer_id"))) or {}
        forging_supplier = parties.get(str(order.get("forging_supplier_id"))) or {}
        grade = grades.get(str(part.get("material_grade_id"))) or {}
        return {
            "Customer Ref": order.get("master_reference_no"),
            "Supply Flow": FLOW_LABELS.get(self.flow_for_order(order), self.flow_for_order(order)),
            "Customer Order No": order.get("customer_order_no"),
            "Position": order.get("order_position"),
            "Customer": party_label(customer),
            "Part Number": part.get("part_number"),
            "FSI Part Number": part.get("fsi_part_number"),
            "Part Description": part.get("part_name"),
            "Material Grade": grade.get("grade_code"),
            "Drawing / Revision": " / ".join(v for v in (str(part.get("drawing_number") or "").strip(), str(part.get("drawing_revision") or "").strip()) if v),
            "Forging Supplier": party_label(forging_supplier),
            "Order Qty pcs": number(order.get("order_qty_pcs")),
            "Gross kg/pc": number(order.get("gross_weight_kg_snapshot")),
            "RM Required kg": number(order.get("required_rm_kg")),
            "Available Stock pcs": number(order.get("available_stock_pcs_snapshot")),
            "3 Month Schedule pcs": number(order.get("three_month_schedule_pcs_snapshot")),
            "RM Procurement Required": bool(order.get("rm_procurement_required", True)),
            "Procurement Decision": order.get("procurement_decision"),
            "Delivery Date": order.get("customer_delivery_date"),
            "Status": order.get("status"),
        }

    # ------------------------------------------------ stock / procurement decision
    def system_available_qty(self, part_id: str) -> float:
        """Production quantity currently available in QCMS for this Part Number."""
        rows = self.repo.select("production_batches", eq={"part_id": part_id}, limit=20000)
        return round(sum(max(number(r.get("quantity_available")), 0.0) for r in rows if str(r.get("status") or "").upper() not in {"REJECTED", "CANCELLED", "SCRAPPED"}), 3)

    def three_month_schedule_demand(self, part_id: str, customer_id: str | None = None, *, anchor: date | str | None = None, exclude_order_id: str | None = None) -> float:
        start = month_start(anchor)
        end = add_months(start, 3)
        total = 0.0
        for row in self.customer_orders():
            if str(row.get("id")) == str(exclude_order_id or "") or str(row.get("status")) == "CANCELLED":
                continue
            if str(row.get("part_id")) != str(part_id):
                continue
            if customer_id and str(row.get("customer_id")) != str(customer_id):
                continue
            if str(row.get("order_type")) != "MONTHLY_SCHEDULE":
                continue
            schedule = parse_business_date(row.get("schedule_month"))
            if not schedule:
                continue
            d = month_start(schedule)
            if start <= d < end:
                total += number(row.get("order_qty_pcs"))
        return round(total, 3)

    def procurement_check(self, part_id: str, customer_id: str | None = None, *, anchor: date | str | None = None, proposed_three_month_qty: float = 0.0, exclude_order_id: str | None = None) -> dict[str, Any]:
        stock = self.system_available_qty(part_id)
        existing = self.three_month_schedule_demand(part_id, customer_id, anchor=anchor, exclude_order_id=exclude_order_id)
        demand = round(existing + max(number(proposed_three_month_qty), 0.0), 3)
        shortage = round(max(demand - stock, 0.0), 3)
        return {
            "available_stock_pcs": stock,
            "existing_three_month_schedule_pcs": existing,
            "three_month_schedule_pcs": demand,
            "shortage_pcs": shortage,
            "rm_procurement_allowed": shortage > 0.0001,
        }

    # ------------------------------------------------ controlled Purchase Orders
    def purchase_order(self, purchase_order_id: str) -> dict | None:
        return self.repo.get("supply_purchase_orders", purchase_order_id)

    def purchase_order_item(self, purchase_order_id: str) -> dict | None:
        rows = self.purchase_order_items(purchase_order_id)
        return rows[0] if rows else None

    @staticmethod
    def _party_snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
        return {key: row.get(key) for key in ("party_code", "party_name", "address", "city", "state", "country", "tax_identifier", "phone", "email", "contact_person")}

    def purchase_order_received_qty(self, purchase_order_id: str) -> float:
        po = self.purchase_order(purchase_order_id) or {}
        if str(po.get("po_type")) == "RAW_MATERIAL":
            stages = self.repo.select("supply_rm_purchase_orders", eq={"purchase_order_id": purchase_order_id}, limit=1000)
            ids = {str(r.get("id")) for r in stages}
            return round(sum(number(r.get("received_qty_kg")) for r in self.rm_receipts() if str(r.get("rm_purchase_order_id")) in ids), 3)
        stages = self.repo.select("supply_forging_orders", eq={"purchase_order_id": purchase_order_id}, limit=1000)
        ids = {str(r.get("id")) for r in stages}
        return round(sum(number(r.get("received_qty_pcs")) for r in self.forging_receipts() if str(r.get("forging_order_id")) in ids), 3)

    def purchase_order_item_received_qty(self, purchase_order_item_id: str) -> float:
        item = self.repo.get("supply_purchase_order_items", purchase_order_item_id) or {}
        if not item:
            return 0.0
        header = self.purchase_order(str(item.get("purchase_order_id") or "")) or {}
        if str(header.get("po_type")) == "RAW_MATERIAL":
            stages = self.repo.select("supply_rm_purchase_orders", eq={"purchase_order_item_id": purchase_order_item_id}, limit=1000)
            # Backward compatibility for v4.13.7 single-source POs created before item-level genealogy existed.
            if not stages and item.get("customer_order_id"):
                stages = [r for r in self.repo.select("supply_rm_purchase_orders", eq={"purchase_order_id": item.get("purchase_order_id")}, limit=1000)
                          if str(r.get("customer_order_id") or "") == str(item.get("customer_order_id") or "")]
            ids = {str(r.get("id")) for r in stages}
            return round(sum(number(r.get("received_qty_kg")) for r in self.rm_receipts() if str(r.get("rm_purchase_order_id")) in ids), 3)
        # v4.13.7 Forging POs are one controlled item per PO. Preserve that behavior.
        return self.purchase_order_received_qty(str(item.get("purchase_order_id") or ""))

    def sync_purchase_order_status(self, purchase_order_id: str | None) -> str:
        if not purchase_order_id:
            return ""
        po = self.purchase_order(purchase_order_id) or {}
        if not po or str(po.get("status")) == "CANCELLED":
            return str(po.get("status") or "")
        ordered = sum(number(r.get("quantity")) for r in self.purchase_order_items(purchase_order_id))
        received = self.purchase_order_received_qty(purchase_order_id)
        status = "CLOSED" if ordered > 0 and received + 0.0001 >= ordered else ("PARTIAL" if received > 0 else "OPEN")
        if str(po.get("status")) != status:
            self.repo.update("supply_purchase_orders", purchase_order_id, {"status": status})
        return status

    def pending_forging_po_sources(self) -> list[dict]:
        rows: list[dict] = []
        # Direct-forging flow: Customer Order is the PO source.
        for order in self.pending_direct_forging_orders():
            row = dict(order)
            row["_source_type"] = "CUSTOMER_ORDER"
            row["_source_id"] = str(order.get("id"))
            row["_customer_order_id"] = str(order.get("id"))
            row["_balance_pcs"] = number(order.get("forging_balance_pcs"))
            rows.append(row)
        # FSI-RM flow: Forging PO is released after RM-to-Forger dispatch.
        linked = {str(r.get("rm_dispatch_id")) for r in self.forging_orders() if r.get("rm_dispatch_id") and str(r.get("status")) != "CANCELLED"}
        for dispatch in self.rm_dispatches():
            if str(dispatch.get("id")) in linked:
                continue
            order = self.order(str(dispatch.get("customer_order_id") or "")) or {}
            if not order or self.flow_for_order(order) != FLOW_FSI_RM:
                continue
            row = {**order, **{f"dispatch_{k}": v for k, v in dispatch.items()}}
            row["_source_type"] = "RM_DISPATCH"
            row["_source_id"] = str(dispatch.get("id"))
            row["_customer_order_id"] = str(order.get("id"))
            row["_balance_pcs"] = max(number(order.get("order_qty_pcs")) - self.totals(str(order.get("id")))["forging_ordered_pcs"], 0.0)
            row["_rm_dispatch"] = dispatch
            rows.append(row)
        rows.sort(key=lambda r: (str(r.get("customer_delivery_date") or "9999-12-31"), str(r.get("master_reference_no") or "")))
        return rows

    def create_purchase_order(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        p = dict(payload)
        po_type = str(p.get("po_type") or "").upper()
        if po_type not in {"RAW_MATERIAL", "FORGING"}:
            raise ValueError("Select Raw Material or Forging Purchase Order type.")
        supplier_id = str(p.get("supplier_id") or "")
        supplier = self.repo.get("parties", supplier_id) or {}
        if not supplier:
            raise ValueError("Select a valid Supplier.")

        # ------------------------------------------------------------------
        # RAW MATERIAL: one controlled PO can consolidate multiple Customer
        # Orders / Monthly Schedules. Each source retains its own execution
        # register row so Material Inward genealogy remains order-specific.
        # ------------------------------------------------------------------
        if po_type == "RAW_MATERIAL":
            raw_order_ids = p.get("customer_order_ids") or ([p.get("customer_order_id")] if p.get("customer_order_id") else [])
            order_ids = list(dict.fromkeys(str(v) for v in raw_order_ids if str(v or "").strip()))
            if not order_ids:
                raise ValueError("Select at least one Customer Order / Schedule for the Raw Material Purchase Order.")
            allocation_map = {str(k): number(v) for k, v in dict(p.get("allocations") or {}).items()}
            line_prices = {str(k): number(v) for k, v in dict(p.get("line_prices") or {}).items()}
            prepared: list[dict[str, Any]] = []
            groups: dict[str, dict[str, Any]] = {}
            for order_id in order_ids:
                order = self.order(order_id) or {}
                if not order:
                    raise ValueError("One selected Customer Order / Schedule no longer exists.")
                if self.flow_for_order(order) != FLOW_FSI_RM:
                    raise ValueError(f"{order.get('master_reference_no')}: Raw Material Purchase Order is not applicable to the Direct Forging flow.")
                if not bool(order.get("rm_procurement_required", True)):
                    raise ValueError(f"{order.get('master_reference_no')}: RM Procurement is not enabled because available stock covers the saved three-month decision.")
                live_check = self.procurement_check(
                    str(order.get("part_id") or ""), str(order.get("customer_id") or ""),
                    anchor=order.get("schedule_month") or order.get("customer_delivery_date") or order.get("order_date"),
                    proposed_three_month_qty=number(order.get("order_qty_pcs")) if str(order.get("order_type") or "") == "PURCHASE_ORDER" else 0.0,
                )
                if not bool(live_check.get("rm_procurement_allowed")):
                    raise ValueError(f"{order.get('master_reference_no')}: current system stock is sufficient for the rolling three-month schedule.")
                balance = max(number(order.get("required_rm_kg")) - self.totals(order_id)["rm_ordered_kg"], 0.0)
                allocation = allocation_map.get(order_id, balance)
                if allocation <= 0 or allocation > balance + 0.0001:
                    raise ValueError(f"{order.get('master_reference_no')}: PO allocation must be greater than zero and cannot exceed the pending RM balance of {balance:,.3f} kg.")
                part = self.repo.get("parts", str(order.get("part_id") or "")) or {}
                fsi = str(part.get("fsi_part_number") or "").strip()
                if not fsi:
                    raise ValueError(f"FSI Part Number is required for {part.get('part_number') or order.get('master_reference_no')} before supplier PO creation.")
                raw = self.raw_material_for_supplier(str(part.get("id") or ""), supplier_id, str(order.get("raw_material_detail_id") or ""))
                if not raw:
                    raise ValueError(f"FSI {fsi}: add an ACTIVE Raw Material Detail for the selected Supplier in Part Master first.")
                key = f"{part.get('id')}|{raw.get('id')}"
                prepared.append({"order": order, "part": part, "raw": raw, "allocation": allocation, "key": key})
                group = groups.setdefault(key, {"part": part, "raw": raw, "quantity": 0.0, "orders": []})
                group["quantity"] += allocation; group["orders"].append((order, allocation))

            gst_percent = max(number(p.get("gst_percent")), 0.0)
            order_date_value = p.get("order_date") or date.today().isoformat()
            currency = str(p.get("currency") or "INR").upper()
            line_data: list[dict[str, Any]] = []
            subtotal = 0.0
            for key, group in groups.items():
                part, raw = group["part"], group["raw"]
                price = line_prices.get(key)
                if price is None or price <= 0:
                    price = self.current_price(str(part.get("id")), supplier_id, on_date=order_date_value, uom="KGS")
                price = max(number(price), 0.0)
                qty = round(number(group["quantity"]), 3)
                line_total = round(qty * price, 2); subtotal += line_total
                history = self.price_history(str(part.get("id")), supplier_id, uom="KGS")
                line_data.append({"key": key, "part": part, "raw": raw, "quantity": qty, "unit_price": price, "line_total": line_total, "gst_amount": round(line_total*gst_percent/100.0,2), "technical": self.technical_data_snapshot(raw, part), "price_history": [{"start_date":h.get("start_date"),"end_date":h.get("end_date"),"price":h.get("price"),"currency":h.get("currency"),"uom":h.get("uom")} for h in history[:50]], "orders": group["orders"]})
            subtotal = round(subtotal, 2)
            gst_amount = round(subtotal * gst_percent / 100.0, 2)
            state = str(supplier.get("state") or "").strip().casefold(); intra_state = not state or state in {"maharashtra", "mh"}
            cgst = round(gst_amount/2.0,2) if intra_state else 0.0; sgst = round(gst_amount/2.0,2) if intra_state else 0.0; igst = gst_amount if not intra_state else 0.0
            other = max(number(p.get("other_amount")),0.0); grand_total = round(subtotal+cgst+sgst+igst+other,2)
            po_number = str(self.repo.rpc("qcms_next_supply_po_number") or "").strip()
            if not po_number:
                raise RuntimeError("QCMS could not allocate the next Purchase Order number.")
            header = self.repo.insert("supply_purchase_orders", {"po_number":po_number,"po_type":po_type,"supplier_id":supplier_id,"order_date":order_date_value,"delivery_date":p.get("delivery_date"),"requisitioner":p.get("requisitioner"),"ship_via":p.get("ship_via") or "Road","incoterm":p.get("incoterm") or "DAP, CHAKAN","payment_term":p.get("payment_term") or "NET 30 DAYS AFTER GRN","quotation_reference":p.get("quotation_reference"),"quotation_date":p.get("quotation_date"),"old_po_reference":p.get("old_po_reference"),"currency":currency,"plant_snapshot":{"name":"Four Star Industries Private Limited D9","address1":"Plot No.D9, Chakan MIDC PH II","address2":"Bhamboli, Khed","address3":"Pune 410501","tax_identifier":"27AAGCF3769A1ZP","phone":"022 40104412","email":"orders@fourstarindustries.com"},"vendor_snapshot":self._party_snapshot(supplier),"ship_to_snapshot":{"name":"Four Star Industries Private Limited D9","address1":"Plot No.D9, Chakan MIDC PH II","address2":"Bhamboli, Khed","address3":"Pune 410501","tax_identifier":"27AAGCF3769A1ZP","phone":"022 40104412","email":"orders@fourstarindustries.com"},"remarks":p.get("remarks") or "PART WILL BE SUPPLIED AS PER DRAWING.","special_instructions":p.get("special_instructions") or DEFAULT_SPECIAL_INSTRUCTIONS,"subtotal":subtotal,"cgst_amount":cgst,"sgst_amount":sgst,"igst_amount":igst,"other_amount":other,"grand_total":grand_total,"status":"OPEN"})
            items: list[dict] = []; stages: list[dict] = []
            for line in line_data:
                part, raw = line["part"], line["raw"]; fsi = str(part.get("fsi_part_number") or "").strip()
                first_order = line["orders"][0][0]
                item = self.repo.insert("supply_purchase_order_items", {"purchase_order_id":header.get("id"),"customer_order_id":first_order.get("id"),"part_id":part.get("id"),"material_grade_id":part.get("material_grade_id"),"raw_material_detail_id":raw.get("id"),"item_no":fsi,"fsi_part_number_snapshot":fsi,"original_part_number_snapshot":part.get("part_number"),"item_description":part.get("part_name") or "Raw Material","rm_section":raw.get("section_size") or part.get("section_size"),"quantity":line["quantity"],"uom":"KGS","unit_price":line["unit_price"],"gst_percent":gst_percent,"gst_amount":line["gst_amount"],"line_total":line["line_total"],"forging_weight_kg":raw.get("forging_weight_kg") or part.get("forging_weight_kg"),"gross_weight_kg":raw.get("gross_weight_kg") or part.get("gross_weight_kg"),"technical_data_snapshot":line["technical"],"price_history_snapshot":line["price_history"],"remarks":p.get("item_remarks")})
                items.append(item)
                self._record_purchase_price(part_id=str(part.get("id")),supplier_id=supplier_id,raw_material_detail_id=str(raw.get("id")),po_date=order_date_value,price=line["unit_price"],uom="KGS",currency=currency,source_item_id=str(item.get("id")))
                for order, allocation in line["orders"]:
                    self.repo.insert("supply_purchase_order_sources", {"purchase_order_id":header.get("id"),"purchase_order_item_id":item.get("id"),"customer_order_id":order.get("id"),"allocated_qty":round(number(allocation),3),"allocation_uom":"KGS"})
                    stage = self.save_transaction("supply_rm_purchase_orders", {"customer_order_id":order.get("id"),"rm_supplier_id":supplier_id,"supplier_order_no":po_number,"order_date":header.get("order_date"),"ordered_qty_kg":round(number(allocation),3),"expected_date":header.get("delivery_date"),"status":"OPEN","remarks":"Controlled Purchase Order "+po_number,"purchase_order_id":header.get("id"),"purchase_order_item_id":item.get("id")})
                    stages.append(stage); self.sync_order_status(str(order.get("id")))
            return {"header":header,"items":items,"stages":stages,"item":items[0] if items else {},"stage":stages[0] if stages else {}}

        # ------------------------------------------------------------------
        # FORGING: preserve the existing single-source flow. Technical data
        # is still snapshot from the selected supplier-specific RM row.
        # ------------------------------------------------------------------
        order_id = str(p.get("customer_order_id") or ""); order = self.order(order_id) or {}
        if not order:
            raise ValueError("Select a valid Customer Order / Schedule source.")
        part = self.repo.get("parts", str(order.get("part_id") or "")) or {}; fsi = str(part.get("fsi_part_number") or "").strip()
        if not fsi:
            raise ValueError("FSI Part Number is required in Part Master before a supplier-facing Purchase Order can be created.")
        raw = self.raw_material_for_supplier(str(part.get("id") or ""), supplier_id, str(order.get("raw_material_detail_id") or "")) or self.repo.get("part_raw_material_details", str(order.get("raw_material_detail_id") or "")) or {}
        quantity = number(p.get("quantity"));
        if quantity <= 0: raise ValueError("Purchase Order quantity must be greater than zero.")
        unit_price = max(number(p.get("unit_price")),0.0); gst_percent=max(number(p.get("gst_percent")),0.0); subtotal=round(quantity*unit_price,2); gst_amount=round(subtotal*gst_percent/100.0,2)
        state=str(supplier.get("state") or "").strip().casefold(); intra_state=not state or state in {"maharashtra","mh"}; cgst=round(gst_amount/2,2) if intra_state else 0.0; sgst=round(gst_amount/2,2) if intra_state else 0.0; igst=gst_amount if not intra_state else 0.0; other=max(number(p.get("other_amount")),0.0); grand_total=round(subtotal+cgst+sgst+igst+other,2)
        po_number=str(self.repo.rpc("qcms_next_supply_po_number") or "").strip();
        if not po_number: raise RuntimeError("QCMS could not allocate the next Purchase Order number.")
        header=self.repo.insert("supply_purchase_orders", {"po_number":po_number,"po_type":po_type,"supplier_id":supplier_id,"order_date":p.get("order_date") or date.today().isoformat(),"delivery_date":p.get("delivery_date"),"requisitioner":p.get("requisitioner"),"ship_via":p.get("ship_via") or "Road","incoterm":p.get("incoterm") or "DAP, CHAKAN","payment_term":p.get("payment_term") or "NET 30 DAYS AFTER GRN","quotation_reference":p.get("quotation_reference"),"quotation_date":p.get("quotation_date"),"old_po_reference":p.get("old_po_reference"),"currency":p.get("currency") or "INR","plant_snapshot":{"name":"Four Star Industries Private Limited D9","address1":"Plot No.D9, Chakan MIDC PH II","address2":"Bhamboli, Khed","address3":"Pune 410501","tax_identifier":"27AAGCF3769A1ZP","phone":"022 40104412","email":"orders@fourstarindustries.com"},"vendor_snapshot":self._party_snapshot(supplier),"ship_to_snapshot":{"name":"Four Star Industries Private Limited D9","address1":"Plot No.D9, Chakan MIDC PH II","address2":"Bhamboli, Khed","address3":"Pune 410501","tax_identifier":"27AAGCF3769A1ZP","phone":"022 40104412","email":"orders@fourstarindustries.com"},"remarks":p.get("remarks") or "PART WILL BE SUPPLIED AS PER DRAWING.","special_instructions":p.get("special_instructions") or DEFAULT_SPECIAL_INSTRUCTIONS,"subtotal":subtotal,"cgst_amount":cgst,"sgst_amount":sgst,"igst_amount":igst,"other_amount":other,"grand_total":grand_total,"status":"OPEN"})
        item=self.repo.insert("supply_purchase_order_items", {"purchase_order_id":header.get("id"),"customer_order_id":order_id,"part_id":part.get("id"),"material_grade_id":part.get("material_grade_id"),"raw_material_detail_id":raw.get("id"),"item_no":fsi,"fsi_part_number_snapshot":fsi,"original_part_number_snapshot":part.get("part_number"),"item_description":part.get("part_name") or "","rm_section":raw.get("section_size") or part.get("section_size"),"quantity":quantity,"uom":p.get("uom") or "NOS","unit_price":unit_price,"gst_percent":gst_percent,"gst_amount":gst_amount,"line_total":subtotal,"forging_weight_kg":raw.get("forging_weight_kg") or part.get("forging_weight_kg"),"gross_weight_kg":raw.get("gross_weight_kg") or part.get("gross_weight_kg"),"technical_data_snapshot":self.technical_data_snapshot(raw,part),"price_history_snapshot":[{"start_date":h.get("start_date"),"end_date":h.get("end_date"),"price":h.get("price"),"currency":h.get("currency"),"uom":h.get("uom")} for h in self.price_history(str(part.get("id")),supplier_id,uom="NOS")[:50]],"remarks":p.get("item_remarks")})
        self._record_purchase_price(part_id=str(part.get("id")),supplier_id=supplier_id,raw_material_detail_id=str(raw.get("id") or "") or None,po_date=header.get("order_date"),price=unit_price,uom="NOS",currency=str(header.get("currency") or "INR"),source_item_id=str(item.get("id")))
        dispatch=p.get("rm_dispatch") or {}; stage_payload={"customer_order_id":order_id,"forging_supplier_id":supplier_id,"supplier_order_no":po_number,"order_date":header.get("order_date"),"order_qty_pcs":quantity,"required_rm_kg":round(quantity*number(order.get("gross_weight_kg_snapshot")),3),"expected_date":header.get("delivery_date"),"status":"OPEN","remarks":"Controlled Purchase Order "+po_number,"purchase_order_id":header.get("id")}
        if dispatch: stage_payload.update({"rm_dispatch_id":dispatch.get("id"),"inward_lot_id":dispatch.get("inward_lot_id"),"heat_number":dispatch.get("heat_number"),"heat_code":dispatch.get("heat_code")})
        stage=self.save_transaction("supply_forging_orders",stage_payload); self.sync_order_status(order_id)
        return {"header":header,"item":item,"items":[item],"stage":stage,"stages":[stage]}

    def purchase_order_rows(self) -> list[dict]:
        parts, parties, grades = self.master_maps()
        headers = {str(r.get("id")): r for r in self.purchase_orders()}
        rows: list[dict] = []
        for item in self.purchase_order_items():
            header = headers.get(str(item.get("purchase_order_id"))) or {}
            part = parts.get(str(item.get("part_id"))) or {}
            supplier = parties.get(str(header.get("supplier_id"))) or {}
            grade = grades.get(str(item.get("material_grade_id"))) or {}
            received = self.purchase_order_item_received_qty(str(item.get("id")))
            ordered = number(item.get("quantity"))
            sources = self.repo.select("supply_purchase_order_sources", eq={"purchase_order_item_id": item.get("id")}, limit=1000)
            source_labels = []
            for source in sources:
                src_order = self.order(str(source.get("customer_order_id") or "")) or {}
                source_labels.append(f"{src_order.get('master_reference_no') or '-'} ({number(source.get('allocated_qty')):,.3f} {source.get('allocation_uom') or item.get('uom')})")
            if not source_labels and item.get("customer_order_id"):
                src_order = self.order(str(item.get("customer_order_id") or "")) or {}
                if src_order:
                    source_labels.append(str(src_order.get("master_reference_no") or src_order.get("customer_order_no") or "-"))
            rows.append({
                "PO Number": header.get("po_number"), "PO Type": str(header.get("po_type") or "").replace("_", " ").title(), "PO Date": header.get("order_date"),
                "Delivery Date": header.get("delivery_date"), "Supplier": party_label(supplier), "Part Number": item.get("original_part_number_snapshot") or part.get("part_number"),
                "FSI Part Number": item.get("fsi_part_number_snapshot") or part.get("fsi_part_number"), "Part Description": item.get("item_description") or part.get("part_name"),
                "Customer Orders / Schedules": " · ".join(source_labels) if source_labels else "",
                "Material Grade": grade.get("grade_code"), "RM Section": item.get("rm_section"), "Ordered Qty": ordered, "UOM": item.get("uom"),
                "Received Qty": received, "Pending Qty": max(ordered-received, 0), "Unit Price": item.get("unit_price"), "GST %": item.get("gst_percent"),
                "Total": header.get("grand_total"), "Status": header.get("status"), "_po_id": header.get("id"), "_item_id": item.get("id"), "_part_id": item.get("part_id"), "_supplier_id": header.get("supplier_id"),
            })
        rows.sort(key=lambda r: (str(r.get("Delivery Date") or "9999-12-31"), str(r.get("PO Number") or "")))
        return rows

    # ----------------------------------------------------------- duplicate guards
    def _assert_purchase_order_duplicate(self, payload: Mapping[str, Any], *, record_id: str | None = None) -> None:
        if str(payload.get("order_type") or "") != "PURCHASE_ORDER":
            return
        customer_id = str(payload.get("customer_id") or "")
        order_no = normalize_match(payload.get("customer_order_no"))
        position = normalize_match(payload.get("order_position"))
        if not customer_id or not order_no:
            return
        for row in self.customer_orders():
            if str(row.get("id")) == str(record_id or "") or str(row.get("status")) == "CANCELLED":
                continue
            if str(row.get("customer_id")) == customer_id and normalize_match(row.get("customer_order_no") or row.get("master_reference_no")) == order_no and normalize_match(row.get("order_position")) == position:
                raise ValueError("Duplicate Customer Order is not allowed. Customer + Order No. + PosNr already exists.")

    def _assert_transaction_duplicate(self, table: str, payload: Mapping[str, Any], *, record_id: str | None = None) -> None:
        keys: dict[str, tuple[str, ...]] = {
            "supply_rm_purchase_orders": ("rm_supplier_id", "supplier_order_no", "customer_order_id"),
            "supply_rm_receipts": ("rm_purchase_order_id", "receipt_number"),
            "supply_rm_dispatches": ("dispatch_number",),
            "supply_forging_orders": ("forging_supplier_id", "supplier_order_no"),
            "supply_forging_receipts": ("forging_order_id", "receipt_number"),
            "supply_downstream_events": ("customer_order_id", "event_type", "reference_no"),
        }
        fields = keys.get(table)
        if not fields:
            return
        expected = tuple(normalize_match(payload.get(k)) for k in fields)
        if not any(expected):
            return
        for row in self.repo.select(table, limit=10000):
            if str(row.get("id")) == str(record_id or ""):
                continue
            if tuple(normalize_match(row.get(k)) for k in fields) == expected:
                raise ValueError("Duplicate entry is not allowed. A record with the same controlled reference already exists.")

    # ---------------------------------------------------------------- save/update
    def create_customer_order(self, payload: Mapping[str, Any]) -> dict:
        p = dict(payload)
        flow = str(p.pop("supply_flow", FLOW_FSI_RM) or FLOW_FSI_RM).upper()
        if flow not in FLOW_LABELS:
            raise ValueError("Select a valid Supply Chain Flow.")
        qty = number(p.get("order_qty_pcs")); gross = number(p.get("gross_weight_kg_snapshot"))
        if qty <= 0 or gross <= 0:
            raise ValueError("Order Quantity and Forging Supplier Gross Weight must be greater than zero.")
        p["required_rm_kg"] = round(qty * gross, 3) if flow == FLOW_FSI_RM else 0.0
        check_override = p.pop("_procurement_check", None)
        check = dict(check_override) if isinstance(check_override, Mapping) else self.procurement_check(str(p.get("part_id") or ""), str(p.get("customer_id") or ""), anchor=p.get("schedule_month") or p.get("customer_delivery_date") or p.get("order_date"), proposed_three_month_qty=number(p.pop("proposed_three_month_qty", qty if str(p.get("order_type")) == "PURCHASE_ORDER" else 0)))
        requested = bool(p.get("rm_procurement_required", check["rm_procurement_allowed"]))
        if flow == FLOW_DIRECT_FORGING:
            requested = False; decision = "DIRECT_FORGING"
        elif not check["rm_procurement_allowed"]:
            requested = False; decision = "AVAILABLE_STOCK"
        else:
            decision = "REQUIRED" if requested else "MANUAL_NOT_REQUIRED"
        p.update({
            "rm_procurement_required": requested,
            "available_stock_pcs_snapshot": check["available_stock_pcs"],
            "three_month_schedule_pcs_snapshot": check["three_month_schedule_pcs"],
            "procurement_shortage_pcs_snapshot": check["shortage_pcs"],
            "procurement_decision": decision,
        })
        p["remarks"] = flow_remarks(p.get("remarks"), flow)
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
            self._assert_purchase_order_duplicate(p)
        return self.repo.insert("supply_customer_orders", p)

    def update_customer_order(self, record_id: str, payload: Mapping[str, Any]) -> dict:
        existing = self.order(record_id) or {}
        if not existing:
            raise ValueError("Customer Order was not found.")
        p = dict(payload)
        existing_flow = self.flow_for_order(existing)
        flow = str(p.pop("supply_flow", existing_flow) or existing_flow).upper()
        if flow not in FLOW_LABELS:
            raise ValueError("Select a valid Supply Chain Flow.")
        if flow != existing_flow and any(value > 0 for value in self.totals(record_id).values()):
            raise ValueError("Supply Chain Flow cannot be changed after linked procurement / forging / production / dispatch transactions have started.")
        merged = dict(existing); merged.update(p)
        qty = number(merged.get("order_qty_pcs")); gross = number(merged.get("gross_weight_kg_snapshot"))
        if qty <= 0 or gross <= 0:
            raise ValueError("Order Quantity and Gross Weight must be greater than zero.")
        p["required_rm_kg"] = round(qty * gross, 3) if flow == FLOW_FSI_RM else 0.0
        check = self.procurement_check(str(merged.get("part_id") or ""), str(merged.get("customer_id") or ""), anchor=merged.get("schedule_month") or merged.get("customer_delivery_date") or merged.get("order_date"), proposed_three_month_qty=number(p.pop("proposed_three_month_qty", 0)), exclude_order_id=record_id)
        requested = bool(merged.get("rm_procurement_required", check["rm_procurement_allowed"])) if flow == FLOW_FSI_RM else False
        if flow == FLOW_DIRECT_FORGING:
            decision = "DIRECT_FORGING"
        elif not check["rm_procurement_allowed"]:
            requested = False; decision = "AVAILABLE_STOCK"
        else:
            decision = "REQUIRED" if requested else "MANUAL_NOT_REQUIRED"
        p.update({"rm_procurement_required":requested,"available_stock_pcs_snapshot":check["available_stock_pcs"],"three_month_schedule_pcs_snapshot":check["three_month_schedule_pcs"],"procurement_shortage_pcs_snapshot":check["shortage_pcs"],"procurement_decision":decision})
        p["remarks"] = flow_remarks(merged.get("remarks"), flow)
        if str(merged.get("order_type")) == "PURCHASE_ORDER":
            ref = str(merged.get("customer_order_no") or "").strip()
            p["master_reference_no"] = ref
            self._assert_purchase_order_duplicate(merged, record_id=record_id)
        return self.repo.update("supply_customer_orders", record_id, p)

    def save_transaction(self, table: str, payload: Mapping[str, Any], *, record_id: str | None = None) -> dict:
        if table not in SUPPLY_TABLES:
            raise ValueError("Unsupported Supply Chain table.")
        if table == "supply_customer_orders":
            return self.update_customer_order(str(record_id), payload) if record_id else self.create_customer_order(payload)
        self._assert_transaction_duplicate(table, payload, record_id=record_id)
        return self.repo.update(table, str(record_id), payload) if record_id else self.repo.insert(table, payload)

    # -------------------------------------------------------------- linked stages
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

    def pending_customer_orders_for_rm(self) -> list[dict]:
        rows = []
        for order in self.customer_orders():
            if str(order.get("status")) in {"COMPLETED", "CANCELLED"}:
                continue
            if self.flow_for_order(order) != FLOW_FSI_RM:
                continue
            if not bool(order.get("rm_procurement_required", True)):
                continue
            # Recheck against current stock without losing the demand that was saved when
            # the Customer Order was created. Customer Purchase Orders are not rows in the
            # Monthly Schedule table, so their own order quantity must be passed explicitly.
            live_check = self.procurement_check(
                str(order.get("part_id") or ""), str(order.get("customer_id") or ""),
                anchor=order.get("schedule_month") or order.get("customer_delivery_date") or order.get("order_date"),
                proposed_three_month_qty=number(order.get("order_qty_pcs")) if str(order.get("order_type") or "") == "PURCHASE_ORDER" else 0.0,
            )
            if not bool(live_check.get("rm_procurement_allowed")):
                continue
            total = self.totals(str(order["id"]))["rm_ordered_kg"]
            required = number(order.get("required_rm_kg"))
            if total + 0.0001 < required:
                row = dict(order); row["rm_ordered_kg"] = total; row["rm_balance_kg"] = max(required-total, 0)
                rows.append(row)
        rows.sort(key=lambda r: (str(r.get("customer_delivery_date") or "9999-12-31"), str(r.get("master_reference_no") or "")))
        return rows

    def pending_rm_purchase_orders(self) -> list[dict]:
        receipts = self.rm_receipts()
        received_by_po: dict[str, float] = {}
        for r in receipts:
            key = str(r.get("rm_purchase_order_id") or "")
            received_by_po[key] = received_by_po.get(key, 0.0) + number(r.get("received_qty_kg"))
        rows=[]
        for po in self.rm_purchase_orders():
            if str(po.get("status")) == "CANCELLED":
                continue
            received = received_by_po.get(str(po.get("id")), 0.0)
            ordered = number(po.get("ordered_qty_kg"))
            if received + 0.0001 < ordered:
                row=dict(po); row["received_qty_kg"] = received; row["balance_qty_kg"] = max(ordered-received,0)
                rows.append(row)
        rows.sort(key=lambda r: (str(r.get("expected_date") or "9999-12-31"), str(r.get("supplier_order_no") or "")))
        return rows

    def pending_rm_receipts_for_dispatch(self) -> list[dict]:
        dispatches = self.rm_dispatches()
        sent_by_receipt: dict[str, float] = {}
        for d in dispatches:
            key = str(d.get("rm_receipt_id") or "")
            if key:
                sent_by_receipt[key] = sent_by_receipt.get(key,0.0) + number(d.get("qty_kg"))
        rows=[]
        for rec in self.rm_receipts():
            sent = sent_by_receipt.get(str(rec.get("id")),0.0)
            received = number(rec.get("received_qty_kg"))
            if sent + 0.0001 < received:
                row=dict(rec); row["dispatched_qty_kg"] = sent; row["balance_qty_kg"] = max(received-sent,0)
                rows.append(row)
        rows.sort(key=lambda r: (str(r.get("receipt_date") or "9999-12-31"), str(r.get("receipt_number") or "")))
        return rows

    def pending_rm_dispatches_for_forging_order(self) -> list[dict]:
        linked = {str(r.get("rm_dispatch_id")) for r in self.forging_orders() if r.get("rm_dispatch_id") and str(r.get("status")) != "CANCELLED"}
        return [r for r in self.rm_dispatches() if str(r.get("id")) not in linked]

    def pending_direct_forging_orders(self) -> list[dict]:
        rows = []
        for order in self.customer_orders():
            if self.flow_for_order(order) != FLOW_DIRECT_FORGING or str(order.get("status")) in {"COMPLETED", "CANCELLED"}:
                continue
            ordered = self.totals(str(order.get("id")))["forging_ordered_pcs"]
            target = number(order.get("order_qty_pcs"))
            if ordered + 0.0001 < target:
                row = dict(order)
                row["forging_ordered_pcs"] = ordered
                row["forging_balance_pcs"] = max(target - ordered, 0)
                rows.append(row)
        rows.sort(key=lambda r: (str(r.get("customer_delivery_date") or "9999-12-31"), str(r.get("master_reference_no") or "")))
        return rows

    def pending_forging_orders(self) -> list[dict]:
        receipts=self.forging_receipts(); totals:dict[str,float]={}
        for r in receipts:
            key=str(r.get("forging_order_id") or ""); totals[key]=totals.get(key,0)+number(r.get("received_qty_pcs"))
        rows=[]
        for fo in self.forging_orders():
            if str(fo.get("status"))=="CANCELLED": continue
            received=totals.get(str(fo.get("id")),0); ordered=number(fo.get("order_qty_pcs"))
            if received + .0001 < ordered:
                row=dict(fo); row["received_qty_pcs"]=received; row["balance_qty_pcs"]=max(ordered-received,0); rows.append(row)
        rows.sort(key=lambda r:(str(r.get("expected_date") or "9999-12-31"),str(r.get("supplier_order_no") or "")))
        return rows

    def pending_sources_for_downstream(self, event_type: str) -> list[dict]:
        event_type=str(event_type).upper()
        downstream=self.downstream_events()
        if event_type=="MACHINING":
            used={str(e.get("source_forging_receipt_id")) for e in downstream if e.get("event_type")=="MACHINING" and e.get("source_forging_receipt_id")}
            return [r for r in self.forging_receipts() if str(r.get("id")) not in used and number(r.get("received_qty_pcs"))>0]
        previous="MACHINING" if event_type=="FINISHED_GOODS" else "FINISHED_GOODS"
        used={str(e.get("source_event_id")) for e in downstream if e.get("event_type")==event_type and e.get("source_event_id")}
        return [e for e in downstream if e.get("event_type")==previous and str(e.get("id")) not in used and number(e.get("qty_pcs"))>0]

    # ------------------------------------------------------ Material Inward bridge
    def eligible_inwards_for_po(self, po_id: str) -> list[dict]:
        po=self.repo.get("supply_rm_purchase_orders",po_id) or {}; order=self.order(str(po.get("customer_order_id") or "")) or {}
        if not po or not order: return []
        rows=[]
        for inward in self.inward_register():
            if str(inward.get("part_id")) != str(order.get("part_id")): continue
            linked_po=str(inward.get("supply_rm_purchase_order_id") or "")
            if linked_po and linked_po != po_id: continue
            rows.append(inward)
        return rows

    def assert_inward_can_unlink(self, inward_id: str) -> None:
        mirror=self.repo.find_one("supply_rm_receipts",eq={"inward_lot_id":inward_id})
        if mirror and self.repo.select("supply_rm_dispatches",eq={"rm_receipt_id":str(mirror.get("id"))},limit=1):
            raise ValueError("Supply Chain link cannot be disabled because this RM Receipt already has an RM-to-Forger dispatch. Reverse the downstream Supply Chain transaction first.")

    def unlink_inward_supply_chain(self, inward_id: str) -> None:
        inward=self.repo.get("inward_lots",inward_id) or {}
        if not inward:
            return
        mirror=self.repo.find_one("supply_rm_receipts",eq={"inward_lot_id":inward_id})
        if mirror:
            try:
                self.repo.delete("supply_rm_receipts",str(mirror.get("id")))
            except Exception as exc:
                raise ValueError("Supply Chain link cannot be disabled because this RM Receipt is already used by a downstream RM-to-Forger / forging transaction.") from exc
        self.repo.update("inward_lots",inward_id,{"supply_customer_order_id":None,"supply_rm_purchase_order_id":None})

    def link_inward_to_rm_po(self, po_id: str, inward_id: str) -> dict:
        po=self.repo.get("supply_rm_purchase_orders",po_id) or {}
        order=self.order(str(po.get("customer_order_id") or "")) or {}
        inward=self.repo.get("inward_lots",inward_id) or {}
        if not po or not order or not inward:
            raise ValueError("RM Purchase Order or Material Inward record was not found.")
        if str(inward.get("part_id")) != str(order.get("part_id")):
            raise ValueError("Material Inward Part Number must match the Customer Order Part Number.")
        other=str(inward.get("supply_rm_purchase_order_id") or "")
        if other and other != po_id:
            raise ValueError("This Material Inward is already linked to another RM Procurement record.")
        try:
            self.repo.update("inward_lots", inward_id, {"supply_customer_order_id": order.get("id"), "supply_rm_purchase_order_id": po_id})
        except Exception as exc:
            raise RuntimeError("Supply Chain v4.12.2 database migration must be applied before linking Material Inward.") from exc
        rmtc=self.repo.get("rmtc_approvals",str(inward.get("rmtc_approval_id") or "")) or {}
        payload={
            "customer_order_id":order.get("id"), "rm_purchase_order_id":po_id, "inward_lot_id":inward_id,
            "receipt_number":inward.get("inward_number"), "receipt_date":inward.get("inward_date"),
            "heat_number":inward.get("heat_number"), "heat_code":inward.get("heat_code"),
            "received_qty_kg":number(inward.get("steel_quantity_kg") or inward.get("quantity_received")),
            "supplier_challan":inward.get("grn_number"), "rmtc_number":rmtc.get("rmtc_number"),
            "rmtc_date":rmtc.get("certificate_date"), "rmtc_qty_kg":number(rmtc.get("certificate_quantity")),
            "remarks":"Linked automatically from Material Inward",
        }
        existing=self.repo.find_one("supply_rm_receipts",eq={"inward_lot_id":inward_id})
        saved=self.repo.update("supply_rm_receipts",str(existing["id"]),payload) if existing else self.repo.insert("supply_rm_receipts",payload)
        self.sync_order_status(str(order.get("id")))
        self.sync_purchase_order_status(str(po.get("purchase_order_id") or ""))
        return saved

    # --------------------------------------------------------------- import logic
    def resolve_part_for_import(self, item: Any, customer_id: str) -> dict | None:
        item_exact=str(item or "").strip().casefold()
        parts=[p for p in self.parts() if str(p.get("customer_id") or "") in {"",str(customer_id)}]
        exact=[p for p in parts if str(p.get("part_number") or "").strip().casefold()==item_exact]
        if len(exact)==1: return exact[0]
        sig=normalize_match(item)
        fuzzy=[p for p in parts if normalize_match(p.get("part_number"))==sig]
        return fuzzy[0] if len(fuzzy)==1 else None

    def import_preview(self, customer_id: str, rows: Sequence[Mapping[str, Any]]) -> list[dict]:
        existing=self.customer_orders(); preview=[]
        for index, source in enumerate(rows, start=1):
            item=str(source.get("Item") or "").strip(); order_no=str(source.get("Order no.") or "").strip(); pos=str(source.get("PosNr") or "").strip()
            qty=parse_import_quantity(source.get("Quantity")); delivery=parse_business_date(source.get("Delivery date"))
            part=self.resolve_part_for_import(item, customer_id)
            result={"Row":index,"Item":item,"Description":source.get("Description"),"Order no.":order_no,"PosNr":pos,"Quantity":qty,"Delivery date":delivery,"Part Master":part.get("part_number") if part else None,"Action":"NEW","Changes":""}
            if not item or not order_no or not pos or qty<=0 or not delivery:
                result["Action"]="ERROR"; result["Changes"]="Mandatory Item / Order no. / PosNr / Quantity / Delivery date is invalid."; preview.append(result); continue
            if not part:
                result["Action"]="ERROR"; result["Changes"]="Item not found uniquely in Part Master for selected Customer."; preview.append(result); continue
            match=next((r for r in existing if str(r.get("customer_id"))==str(customer_id) and normalize_match(r.get("customer_order_no") or r.get("master_reference_no"))==normalize_match(order_no) and normalize_match(r.get("order_position"))==normalize_match(pos) and str(r.get("status"))!="CANCELLED"),None)
            result["_part_id"]=part.get("id"); result["_existing_id"]=(match or {}).get("id")
            if match:
                # v4.13.4 import rule: matching Customer + Order No. + PosNr is a duplicate.
                # Existing database records are never modified by bulk import.
                result["Action"]="SKIP_DUPLICATE"
                result["Changes"]="Existing Order No. + PosNr already present; row will be skipped."
            preview.append(result)
        return preview

    def apply_customer_order_import(self, customer_id: str, preview: Sequence[Mapping[str, Any]], *, confirm_updates: bool = False, supply_flow: str = FLOW_FSI_RM) -> dict[str,int]:
        """Create only missing customer-order keys; never update duplicates during import."""
        result={"created":0,"skipped":0,"errors":0}
        seen: set[tuple[str,str]] = set()
        for row in preview:
            action=str(row.get("Action") or "")
            if action=="ERROR": result["errors"]+=1; continue
            key=(normalize_match(row.get("Order no.")), normalize_match(row.get("PosNr")))
            if action in {"SKIP_DUPLICATE","UNCHANGED","UPDATE"} or key in seen:
                result["skipped"]+=1; continue
            seen.add(key)
            part_id=str(row.get("_part_id") or ""); raw=self.raw_material_options(part_id)
            if not raw:
                raise ValueError(f"Part {row.get('Item')} has no active Part Master Raw Material Details.")
            selected_raw=raw[0]; gross=number(selected_raw.get("gross_weight_kg") or selected_raw.get("input_weight_kg") or selected_raw.get("forging_weight_kg"))
            if gross<=0: raise ValueError(f"Part {row.get('Item')} Raw Material gross/input weight is missing in Part Master.")
            payload={"order_type":"PURCHASE_ORDER","customer_id":customer_id,"part_id":part_id,"customer_order_no":str(row.get("Order no.") or "").strip(),"order_position":str(row.get("PosNr") or "").strip(),"order_date":date.today().isoformat(),"customer_delivery_date":row.get("Delivery date"),"order_qty_pcs":number(row.get("Quantity")),"forging_supplier_id":selected_raw.get("supplier_id"),"raw_material_detail_id":selected_raw.get("id"),"gross_weight_kg_snapshot":gross,"status":"OPEN","remarks":"Imported from Customer Order / Schedule file (Columns A-F)","supply_flow":supply_flow}
            self.create_customer_order(payload); result["created"]+=1
        return result

    # --------------------------------------------------------------- MIS / dispatch reporting
    def order_mis_rows(self) -> list[dict]:
        parts, parties, _ = self.master_maps()
        downstream = self.downstream_events()
        rows = []
        for order in self.customer_orders():
            oid = str(order.get("id") or "")
            part = parts.get(str(order.get("part_id"))) or {}
            customer = parties.get(str(order.get("customer_id"))) or {}
            dispatches = [r for r in downstream if str(r.get("customer_order_id") or "") == oid and r.get("event_type") == "CUSTOMER_DISPATCH"]
            dispatched = sum(number(r.get("qty_pcs")) for r in dispatches)
            latest = max(dispatches, key=lambda r: str(r.get("event_date") or ""), default={})
            qty = number(order.get("order_qty_pcs"))
            due = str(order.get("customer_delivery_date") or "")[:10]
            month = str(order.get("schedule_month") or due or order.get("order_date") or "")[:7]
            rows.append({
                "Month": month,
                "Order Type": str(order.get("order_type") or "").replace("_", " ").title(),
                "Supply Flow": FLOW_LABELS.get(self.flow_for_order(order), self.flow_for_order(order)),
                "Customer Ref": order.get("master_reference_no"),
                "Customer Order No": order.get("customer_order_no"),
                "PosNr": order.get("order_position"),
                "Customer": party_label(customer),
                "Part Number": part.get("part_number"),
                "FSI Part Number": part.get("fsi_part_number"),
                "Part Description": part.get("part_name"),
                "Order / Schedule Qty pcs": qty,
                "Dispatched pcs": dispatched,
                "Pending Dispatch pcs": max(qty - dispatched, 0),
                "Completion %": round((dispatched / qty * 100.0), 1) if qty else 0.0,
                "Delivery Date": due,
                "Latest Dispatch Date": latest.get("event_date"),
                "Latest Dispatch Ref": latest.get("reference_no"),
                "Invoice No.": latest.get("invoice_no"),
                "ASN No.": latest.get("asn_no"),
                "Status": order.get("status"),
            })
        rows.sort(key=lambda r: (str(r.get("Month") or "9999-99"), str(r.get("Delivery Date") or "9999-12-31"), str(r.get("Customer Ref") or "")))
        return rows

    def monthly_mis_summary(self, rows: Sequence[Mapping[str, Any]] | None = None) -> list[dict]:
        """Management MIS grouped by Month + Customer + Part Number.

        Keeping the customer and part identity in this summary prevents a month-only
        total from hiding which customer schedule / purchase-order demand actually
        drives the dispatch balance.
        """
        source = list(rows or self.order_mis_rows())
        groups: dict[tuple[str, str, str, str, str], dict[str, float]] = {}
        for row in source:
            key = (
                str(row.get("Month") or "Unscheduled"),
                str(row.get("Customer") or "-"),
                str(row.get("Part Number") or "-"),
                str(row.get("FSI Part Number") or "-"),
                str(row.get("Part Description") or "-"),
            )
            bucket = groups.setdefault(key, {"ordered": 0.0, "dispatched": 0.0})
            bucket["ordered"] += number(row.get("Order / Schedule Qty pcs"))
            bucket["dispatched"] += number(row.get("Dispatched pcs"))
        result = []
        for key in sorted(groups):
            month, customer, part_number, fsi_part_number, part_description = key
            ordered = groups[key]["ordered"]
            dispatched = groups[key]["dispatched"]
            result.append({
                "Month": month,
                "Customer Name": customer,
                "Part Number": part_number,
                "FSI Part Number": fsi_part_number,
                "Part Description": part_description,
                "Order / Schedule Qty pcs": ordered,
                "Dispatched pcs": dispatched,
                "Pending Dispatch pcs": max(ordered - dispatched, 0),
                "Dispatch Achievement %": round((dispatched / ordered * 100.0), 1) if ordered else 0.0,
            })
        return result

    # --------------------------------------------------------------- genealogy
    def genealogy_context(self, order_id: str) -> list[dict]:
        order=self.order(order_id) or {}; ctx=self.order_context(order)
        rows=[]
        for table, stage, date_key, ref_key, qty_key, unit in (
            ("supply_rm_purchase_orders","RM Procurement","order_date","supplier_order_no","ordered_qty_kg","kg"),
            ("supply_rm_receipts","Material Inward / RM Receipt","receipt_date","receipt_number","received_qty_kg","kg"),
            ("supply_rm_dispatches","RM to Forging","dispatch_date","dispatch_number","qty_kg","kg"),
            ("supply_forging_orders","Forging Order","order_date","supplier_order_no","order_qty_pcs","pcs"),
            ("supply_forging_receipts","Forging Receipt","receipt_date","receipt_number","received_qty_pcs","pcs"),
        ):
            for r in self.repo.select(table,eq={"customer_order_id":order_id},limit=10000):
                rows.append({**ctx,"Stage":stage,"Stage Date":r.get(date_key),"Stage Reference":r.get(ref_key),"Stage Qty":f"{number(r.get(qty_key)):,.3f} {unit}","Heat Number":r.get("heat_number"),"Heat Code":r.get("heat_code"),"RMTC Number":r.get("rmtc_number"),"Status":r.get("status") or "POSTED","Remarks":clean_flow_remarks(r.get("remarks"))})
        for r in self.repo.select("supply_downstream_events",eq={"customer_order_id":order_id},limit=10000):
            rows.append({**ctx,"Stage":str(r.get("event_type") or "").replace("_"," ").title(),"Stage Date":r.get("event_date"),"Stage Reference":r.get("reference_no"),"Stage Qty":f"{number(r.get('qty_pcs')):,.0f} pcs","Heat Number":r.get("heat_number"),"Heat Code":r.get("heat_code"),"RMTC Number":None,"Status":"POSTED","Remarks":clean_flow_remarks(r.get("remarks"))})
        return rows

    def supplier_balances(self, order_id: str) -> list[dict]:
        order = self.order(order_id) or {}
        if self.flow_for_order(order) == FLOW_DIRECT_FORGING:
            return []
        suppliers = {str(r["id"]): r for r in self.parties()}
        dispatches = self.repo.select("supply_rm_dispatches", eq={"customer_order_id": order_id}, limit=5000)
        receipts = self.repo.select("supply_forging_receipts", eq={"customer_order_id": order_id}, limit=5000)
        ids = sorted({str(r.get("forging_supplier_id") or "") for r in dispatches + receipts if r.get("forging_supplier_id")})
        rows = []
        for sid in ids:
            sent = sum(number(r.get("qty_kg")) for r in dispatches if str(r.get("forging_supplier_id")) == sid)
            consumed = sum(number(r.get("actual_rm_consumed_kg")) if r.get("actual_rm_consumed_kg") is not None else number(r.get("received_qty_pcs"))*number(r.get("gross_weight_kg_snapshot")) for r in receipts if str(r.get("forging_supplier_id")) == sid)
            rows.append({"Supplier": party_label(suppliers.get(sid) or {}), "RM Dispatched kg": round(sent,3), "RM Consumed kg": round(consumed,3), "RM Balance kg": round(sent-consumed,3), "Order Reference": order.get("master_reference_no")})
        return rows

    def timeline(self, order_id: str) -> list[dict]:
        order = self.order(order_id) or {}
        events = [{"Date": order.get("order_date"), "Stage": "Customer Order", "Reference": order.get("master_reference_no"), "Quantity": f"{number(order.get('order_qty_pcs')):,.0f} pcs", "Heat Number":"", "Status": order.get("status"), "Remarks": clean_flow_remarks(order.get("remarks"))}]
        for row in self.genealogy_context(order_id):
            events.append({"Date":row.get("Stage Date"),"Stage":row.get("Stage"),"Reference":row.get("Stage Reference"),"Quantity":row.get("Stage Qty"),"Heat Number":row.get("Heat Number") or "","Status":row.get("Status"),"Remarks":row.get("Remarks") or ""})
        events.sort(key=lambda r: str(r.get("Date") or ""))
        return events
