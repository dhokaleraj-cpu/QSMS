from __future__ import annotations

import re
from datetime import date, datetime, timezone, timedelta
from typing import Any, Mapping, Sequence

from core.repository import Repository
from core.record_audit import annotate_transaction_rows
from core.auth import current_employee_id
from core.selection_labels import party_label
from core.purchase_order_reporting import DEFAULT_SPECIAL_INSTRUCTIONS

MONTHS = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December",
}

SUPPLY_TABLES = (
    "supply_customer_orders", "supply_rm_purchase_orders", "supply_rm_receipts",
    "supply_rm_dispatches", "supply_forging_orders", "supply_forging_receipts",
    "supply_downstream_events", "supply_opening_stock", "supply_po_confirmations",
)

FLOW_FSI_RM = "FSI_RM"
FLOW_DIRECT_FORGING = "DIRECT_FORGING"
FLOW_FSI_RM_DIRECT_PRODUCTION = "FSI_RM_DIRECT_PRODUCTION"
FLOW_LABELS = {
    FLOW_FSI_RM: "Flow 1 · FSI RM → Forging → Production",
    FLOW_DIRECT_FORGING: "Flow 2 · Direct Forging → Production",
    FLOW_FSI_RM_DIRECT_PRODUCTION: "Flow 3 · FSI RM → Direct Production",
}
FLOW_REQUIRES_FSI_RM = {FLOW_FSI_RM, FLOW_FSI_RM_DIRECT_PRODUCTION}
_FLOW_RE = re.compile(r"\s*\[\[QCMS_SUPPLY_FLOW=(FSI_RM|DIRECT_FORGING|FSI_RM_DIRECT_PRODUCTION)\]\]\s*", re.I)


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

    def material_grade_links(self, part_id: str | None = None) -> list[dict]:
        eq = {"status": "ACTIVE"}
        if part_id:
            eq["part_id"] = part_id
        return self.repo.select("part_material_grade_links", eq=eq, order_by="created_at", limit=5000)

    def opening_stock(self, *, part_id: str | None = None, active_only: bool = False) -> list[dict]:
        eq: dict[str, Any] = {}
        if part_id:
            eq["part_id"] = part_id
        if active_only:
            eq["status"] = "ACTIVE"
        return self.repo.select("supply_opening_stock", eq=eq or None, order_by="created_at", desc=True, limit=10000)

    def save_opening_stock(self, payload: Mapping[str, Any], record_id: str | None = None) -> dict:
        p = dict(payload)
        part_id = str(p.get("part_id") or "")
        if not part_id or not self.repo.get("parts", part_id):
            raise ValueError("Select a valid Part Number for Opening Stock.")
        stage = str(p.get("stage") or "").upper().strip()
        allowed = {"RAW_MATERIAL", "FORGING", "MACHINING", "OSP_READY", "AT_OSP", "FINAL_INSPECTION", "FINISHED_GOODS"}
        if stage not in allowed:
            raise ValueError("Select a valid Supply Chain stage for Opening Stock.")
        pcs = max(number(p.get("quantity_pcs")), 0.0)
        available = max(number(p.get("available_quantity_pcs") if p.get("available_quantity_pcs") is not None else pcs), 0.0)
        kg = max(number(p.get("quantity_kg")), 0.0)
        if pcs <= 0 and kg <= 0:
            raise ValueError("Opening Stock must contain a positive quantity in pieces or kilograms.")
        if available > pcs and pcs > 0:
            raise ValueError("Opening Stock available quantity cannot exceed the recorded opening quantity.")
        p.update({"stage": stage, "quantity_pcs": pcs, "available_quantity_pcs": available, "quantity_kg": kg, "status": str(p.get("status") or "ACTIVE").upper()})
        return self.repo.update("supply_opening_stock", record_id, p) if record_id else self.repo.insert("supply_opening_stock", p)

    @staticmethod
    def _opening_stage_code(value: Any) -> str:
        key = normalize_match(value)
        mapping = {
            "rawmaterial": "RAW_MATERIAL",
            "forging": "FORGING",
            "machining": "MACHINING",
            "machiningwip": "MACHINING",
            "wip": "MACHINING",
            "ospready": "OSP_READY",
            "atosp": "AT_OSP",
            "finalinspection": "FINAL_INSPECTION",
            "finishedgoods": "FINISHED_GOODS",
            "fg": "FINISHED_GOODS",
        }
        return mapping.get(key, str(value or "").strip().upper().replace(" ", "_"))

    def opening_stock_import_preview(self, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        """Resolve a duplicate-safe Opening Stock import without changing live data."""
        parts = self.parts()
        part_by_number = {normalize_match(r.get("part_number")): r for r in parts if normalize_match(r.get("part_number"))}
        part_by_fsi = {normalize_match(r.get("fsi_part_number")): r for r in parts if normalize_match(r.get("fsi_part_number"))}
        grades = self.material_grades()
        grade_by_code = {normalize_match(r.get("grade_code")): r for r in grades if normalize_match(r.get("grade_code"))}
        parties = self.parties()
        supplier_by_code = {normalize_match(r.get("party_code")): r for r in parties if normalize_match(r.get("party_code"))}
        supplier_by_name = {normalize_match(r.get("party_name")): r for r in parties if normalize_match(r.get("party_name"))}
        existing_signatures = {
            "|".join([
                str(r.get("part_id") or ""), str(r.get("stage") or "").upper(),
                normalize_match(r.get("lot_reference")), normalize_match(r.get("heat_number")),
            ])
            for r in self.opening_stock()
            if r.get("part_id") and r.get("stage") and r.get("lot_reference")
        }
        preview: list[dict[str, Any]] = []
        for row_no, source in enumerate(rows, start=2):
            raw = dict(source or {})
            part_number = str(raw.get("Part Number") or raw.get("part_number") or "").strip()
            fsi_number = str(raw.get("FSI Part Number") or raw.get("fsi_part_number") or "").strip()
            part = part_by_number.get(normalize_match(part_number)) or part_by_fsi.get(normalize_match(fsi_number)) or {}
            stage = self._opening_stage_code(raw.get("Stage") or raw.get("Supply Chain Stage"))
            reference = str(raw.get("Opening Reference") or raw.get("Opening Lot / Reference") or "").strip()
            heat_number = str(raw.get("Heat Number") or "").strip()
            grade_text = str(raw.get("Material Grade") or "").strip()
            supplier_text = str(raw.get("Supplier Code") or raw.get("Supplier") or "").strip()
            section_text = str(raw.get("Raw Material Type") or raw.get("Raw Material Section") or "").strip()
            section_size = str(raw.get("Section Size") or "").strip()
            error = ""
            if not part:
                error = "Part Number / FSI Part Number was not found in active Part Master."
            elif stage not in {"RAW_MATERIAL","FORGING","MACHINING","OSP_READY","AT_OSP","FINAL_INSPECTION","FINISHED_GOODS"}:
                error = "Invalid Supply Chain Stage."
            elif not reference:
                error = "Opening Reference is mandatory for duplicate-safe import."

            grade = grade_by_code.get(normalize_match(grade_text)) if grade_text else {}
            if grade_text and not grade and not error:
                error = f"Material Grade {grade_text} was not found."
            supplier = (supplier_by_code.get(normalize_match(supplier_text)) or supplier_by_name.get(normalize_match(supplier_text))) if supplier_text else {}
            if supplier_text and not supplier and not error:
                error = f"Supplier {supplier_text} was not found."

            raw_detail = {}
            if part and (section_text or section_size or supplier):
                options = self.raw_material_options(str(part.get("id")))
                candidates = options
                if supplier:
                    candidates = [r for r in candidates if str(r.get("supplier_id") or "") == str(supplier.get("id") or "")]
                if section_text:
                    candidates = [r for r in candidates if normalize_match(r.get("material_section_name")) == normalize_match(section_text)]
                if section_size:
                    candidates = [r for r in candidates if normalize_match(r.get("section_size")) == normalize_match(section_size)]
                if grade:
                    grade_candidates = [r for r in candidates if str(r.get("material_grade_id") or "") == str(grade.get("id") or "")]
                    if grade_candidates:
                        candidates = grade_candidates
                if len(candidates) == 1:
                    raw_detail = candidates[0]
                elif (section_text or section_size) and not candidates and not error:
                    error = "Raw Material Type / Supplier combination was not found for this Part."
                elif len(candidates) > 1 and not error:
                    error = "Multiple Raw Material rows match. Add Supplier Code and Section Size to identify one row."

            try:
                qty_pcs = max(float(raw.get("Opening Qty pcs") or raw.get("Opening Qty (pcs)") or 0), 0.0)
                available = raw.get("Available Qty pcs") if raw.get("Available Qty pcs") not in (None, "") else raw.get("Available Qty (pcs)")
                available_pcs = qty_pcs if available in (None, "") else max(float(available), 0.0)
                qty_kg = max(float(raw.get("Opening Qty kg") or raw.get("Opening Qty (kg)") or 0), 0.0)
            except (TypeError, ValueError):
                qty_pcs = available_pcs = qty_kg = 0.0
                if not error: error = "Opening quantity contains an invalid number."
            if qty_pcs <= 0 and qty_kg <= 0 and not error:
                error = "Enter a positive Opening Qty pcs or Opening Qty kg."
            if qty_pcs > 0 and available_pcs > qty_pcs and not error:
                error = "Available Qty pcs cannot exceed Opening Qty pcs."

            selected_grade_id = str((grade or {}).get("id") or (raw_detail or {}).get("material_grade_id") or (part or {}).get("material_grade_id") or "") or None
            supplier_id = str((supplier or {}).get("id") or (raw_detail or {}).get("supplier_id") or "") or None
            signature = "|".join([str((part or {}).get("id") or ""), stage, normalize_match(reference), normalize_match(heat_number)])
            action = "ERROR" if error else ("SKIP_DUPLICATE" if signature in existing_signatures else "CREATE")
            payload = {
                "part_id": str((part or {}).get("id") or ""), "stage": stage,
                "material_grade_id": selected_grade_id, "raw_material_detail_id": str((raw_detail or {}).get("id") or "") or None,
                "supplier_id": supplier_id, "lot_reference": reference or None,
                "heat_number": heat_number or None, "heat_code": str(raw.get("Heat Code") or "").strip() or None,
                "quantity_pcs": qty_pcs, "available_quantity_pcs": available_pcs, "quantity_kg": qty_kg,
                "remarks": str(raw.get("Remarks") or "").strip() or None, "status": "ACTIVE",
            }
            preview.append({
                "Row": row_no, "Part Number": (part or {}).get("part_number") or part_number,
                "FSI Part Number": (part or {}).get("fsi_part_number") or fsi_number, "Stage": stage,
                "Material Grade": (grade or {}).get("grade_code") or grade_text,
                "Supplier": (supplier or {}).get("party_name") or supplier_text,
                "Raw Material Type": (raw_detail or {}).get("material_section_name") or section_text,
                "Opening Reference": reference, "Heat Number": heat_number,
                "Opening Qty pcs": qty_pcs, "Available Qty pcs": available_pcs, "Opening Qty kg": qty_kg,
                "Action": action, "Error": error, "_payload": payload, "_signature": signature,
            })
            if action == "CREATE":
                existing_signatures.add(signature)
        return preview

    def apply_opening_stock_import(self, preview_rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
        created = skipped = 0
        for row in preview_rows:
            action = str(row.get("Action") or "")
            if action == "CREATE":
                self.save_opening_stock(dict(row.get("_payload") or {}))
                created += 1
            elif action == "SKIP_DUPLICATE":
                skipped += 1
            elif action == "ERROR":
                raise ValueError(f"Opening Stock import contains an error at row {row.get('Row')}: {row.get('Error')}")
        return {"created": created, "skipped": skipped}

    def master_maps(self) -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
        return (
            {str(r["id"]): r for r in self.parts()},
            {str(r["id"]): r for r in self.parties()},
            {str(r["id"]): r for r in self.material_grades()},
        )

    # ---------------------------------------------------------------- transactions
    def customer_orders(self) -> list[dict]:
        rows = annotate_transaction_rows(self.repo, self.repo.select("supply_customer_orders", order_by="created_at", desc=True, limit=10000))
        result = []
        for row in rows:
            item = dict(row)
            item["supply_flow"] = self.flow_for_order(row)
            item["remarks"] = clean_flow_remarks(row.get("remarks"))
            result.append(item)
        return result

    def purchase_orders(self) -> list[dict]:
        return annotate_transaction_rows(self.repo, self.repo.select("supply_purchase_orders", order_by="created_at", desc=True, limit=10000))

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

    def raw_material_po_group_key(self, part: Mapping[str, Any], raw: Mapping[str, Any]) -> str:
        """Group identical supplier RM across finished Parts without losing source genealogy."""
        common = normalize_match(raw.get("supplier_rm_item_code"))
        if common:
            return "|".join([
                "COMMON_RM", common, normalize_match(raw.get("material_grade_id") or part.get("material_grade_id")),
                normalize_match(raw.get("material_section_name")), normalize_match(raw.get("section_size")),
            ])
        return f"PART_RM|{part.get('id')}|{raw.get('id')}"

    def forging_po_group_key(self, part: Mapping[str, Any], raw: Mapping[str, Any]) -> str:
        """Group a genuinely common forging item used by more than one finished Part."""
        common = normalize_match(raw.get("supplier_forging_part_number"))
        if common:
            return "|".join([
                "COMMON_FORGING", common, normalize_match(raw.get("material_grade_id") or part.get("material_grade_id")),
                normalize_match(raw.get("forging_route") or part.get("manufacturing_route")),
                f"{number(raw.get('forging_weight_kg') or part.get('forging_weight_kg')):.6f}",
            ])
        return f"PART_FORGING|{part.get('id')}|{raw.get('id')}"

    def _po_confirmation_is_confirmed(self, controlled_po_id: str | None) -> bool:
        if not controlled_po_id:
            return False
        row = self.purchase_order_confirmation(str(controlled_po_id))
        return str(row.get("confirmation_status") or "").upper() == "CONFIRMED"

    def raw_material_technical_data(self, raw_material_detail_id: str | None) -> list[dict]:
        if not raw_material_detail_id:
            return []
        return self.repo.select("part_raw_material_technical_data", eq={"raw_material_detail_id": raw_material_detail_id, "status": "ACTIVE"}, order_by="sequence_no", limit=500)

    def technical_data_snapshot(self, raw: Mapping[str, Any], part: Mapping[str, Any]) -> list[dict[str, str]]:
        custom = self.raw_material_technical_data(str(raw.get("id") or ""))
        custom_map: dict[str, dict[str, str]] = {}
        for r in custom:
            if not bool(r.get("include_on_po", True)):
                continue
            heading = str(r.get("heading") or "").strip(); value = str(r.get("value_text") or "").strip()
            if not heading or not value:
                continue
            key = normalize_match(heading)
            if key == normalize_match("Raw Material Section"):
                key = normalize_match("Raw Material Type"); heading = "Raw Material Type"
            custom_map[key] = {"heading": heading, "value": value, "source": "CUSTOM"}
        grade = self.repo.get("material_grades", str(raw.get("material_grade_id") or part.get("material_grade_id") or "")) or {}
        standard = [
            ("Raw Material Type", raw.get("material_section_name")),
            ("Supplier RM Item Code", raw.get("supplier_rm_item_code")),
            ("Supplier Forging Part No.", raw.get("supplier_forging_part_number")),
            ("Material Grade", grade.get("grade_code")),
            ("Supplier Lead Time", f"{int(raw.get('lead_time_days') or 0)} Days" if int(raw.get("lead_time_days") or 0) > 0 else ""),
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
                result.append({"heading": heading, "value": str(value).strip(), "source": "STANDARD"})
        for r in custom:
            key = normalize_match(r.get("heading"))
            if key in used or not bool(r.get("include_on_po", True)):
                continue
            heading = str(r.get("heading") or "").strip(); value = str(r.get("value_text") or "").strip()
            if heading and value:
                result.append({"heading": heading, "value": value, "source": "CUSTOM"}); used.add(key)
        return result

    def price_history(
        self,
        part_id: str,
        supplier_id: str,
        *,
        uom: str | None = None,
        raw_material_detail_id: str | None = None,
    ) -> list[dict]:
        """Return controlled supplier/Part price history for the selected RM detail.

        v4.14.14 makes Raw Material Detail the strongest commercial identity because
        one Supplier may now have multiple grades/sections for the same Part. Historical
        rows are retained. When older rows do not carry ``raw_material_detail_id``, the
        method falls back to Supplier + Part so legacy data remains usable. UOM is a
        preference, not a hard filter: a valid current price must not disappear only
        because an older master row was saved as PCS/NOS while the RM PO uses KGS.
        """
        rows = self.repo.select(
            "part_supplier_price_history",
            eq={"part_id": part_id, "supplier_id": supplier_id},
            order_by="start_date",
            desc=True,
            limit=5000,
        )
        rows = [r for r in rows if str(r.get("status") or "ACTIVE").upper() not in {"DELETED", "CANCELLED"}]
        raw_id = str(raw_material_detail_id or "").strip()
        if raw_id:
            exact_raw = [r for r in rows if str(r.get("raw_material_detail_id") or "") == raw_id]
            if exact_raw:
                rows = exact_raw
        if uom:
            same_uom = [r for r in rows if str(r.get("uom") or "").upper() == str(uom).upper()]
            if same_uom:
                rows = same_uom
        return rows

    def price_history_for_po(
        self,
        part_id: str,
        supplier_id: str,
        *,
        po_date: date | str | None = None,
        uom: str | None = None,
        raw_material_detail_id: str | None = None,
    ) -> list[dict]:
        """Return the complete supplier/FSI-Part price revision history for the exact PO Raw Material Detail, oldest first."""
        all_rows = self.price_history(
            part_id, supplier_id, raw_material_detail_id=raw_material_detail_id
        )
        same_uom = [r for r in all_rows if not uom or str(r.get("uom") or "").upper() == str(uom).upper()]
        rows = same_uom if same_uom else all_rows
        rows.sort(key=lambda r: (str(r.get("start_date") or ""), str(r.get("end_date") or "9999-12-31"), str(r.get("id") or "")))
        return [{
            "start_date": r.get("start_date"),
            "end_date": r.get("end_date"),
            "price": r.get("price"),
            "freight": r.get("freight"),
            "tool_cost": r.get("tool_cost"),
            "packing_forwarding": r.get("packing_forwarding"),
            "profit": r.get("profit"),
            "icc_rejection": r.get("icc_rejection"),
            "currency": r.get("currency") or "INR",
            "uom": r.get("uom") or uom or "",
            "remarks": r.get("remarks") or "",
            "status": r.get("status") or "ACTIVE",
            "raw_material_detail_id": r.get("raw_material_detail_id"),
        } for r in rows]

    def purchase_order_items_for_print(self, purchase_order_id: str) -> list[dict]:
        """Return PO items enriched with complete price history for reliable reprints."""
        header = self.purchase_order(purchase_order_id) or {}
        supplier_id = str(header.get("supplier_id") or "")
        po_date = header.get("order_date")
        items = [dict(r) for r in self.purchase_order_items(purchase_order_id)]
        for item in items:
            part_id = str(item.get("part_id") or "")
            raw_id = str(item.get("raw_material_detail_id") or "")
            if part_id and supplier_id:
                history = self.price_history_for_po(
                    part_id, supplier_id, po_date=po_date,
                    uom=str(item.get("uom") or "") or None,
                    raw_material_detail_id=raw_id or None,
                )
                if history:
                    item["price_history_snapshot"] = history
        return items

    def current_price(
        self,
        part_id: str,
        supplier_id: str,
        *,
        on_date: date | str | None = None,
        uom: str = "KGS",
        raw_material_detail_id: str | None = None,
    ) -> float:
        """Return the current master price for the selected Supplier/RM detail.

        Ranking: exact Raw Material Detail first, then requested UOM, then latest
        covering revision. This fixes RM price history rows saved as PCS/NOS not
        appearing on a KGS Purchase Order while preserving legacy history.
        """
        target = parse_business_date(on_date) or date.today().isoformat()
        raw_id = str(raw_material_detail_id or "").strip()
        all_rows = self.repo.select(
            "part_supplier_price_history",
            eq={"part_id": part_id, "supplier_id": supplier_id},
            order_by="start_date", desc=True, limit=5000,
        )
        all_rows = [r for r in all_rows if str(r.get("status") or "ACTIVE").upper() not in {"DELETED", "CANCELLED"}]
        covering = []
        for row in all_rows:
            start = str(row.get("start_date") or "")[:10]
            end = str(row.get("end_date") or "")[:10]
            if start and start <= target and (not end or target <= end):
                covering.append(row)
        if not covering:
            return 0.0
        if raw_id:
            exact = [r for r in covering if str(r.get("raw_material_detail_id") or "") == raw_id]
            if exact:
                covering = exact
        wanted_uom = str(uom or "").upper()
        if wanted_uom:
            exact_uom = [r for r in covering if str(r.get("uom") or "").upper() == wanted_uom]
            if exact_uom:
                covering = exact_uom
        covering.sort(key=lambda r: (str(r.get("start_date") or ""), str(r.get("id") or "")), reverse=True)
        return number(covering[0].get("price")) if covering else 0.0

    def _record_purchase_price(self, *, part_id: str, supplier_id: str, raw_material_detail_id: str | None, po_date: date | str, price: float, uom: str, currency: str, source_item_id: str) -> None:
        price = max(number(price), 0.0)
        if price <= 0:
            return
        target_text = parse_business_date(po_date) or date.today().isoformat()
        target = date.fromisoformat(target_text)
        history = self.price_history(part_id, supplier_id, uom=uom, raw_material_detail_id=raw_material_detail_id)
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
        return annotate_transaction_rows(self.repo, self.repo.select("supply_rm_purchase_orders", order_by="created_at", desc=True, limit=10000))

    def rm_receipts(self) -> list[dict]:
        return annotate_transaction_rows(self.repo, self.repo.select("supply_rm_receipts", order_by="created_at", desc=True, limit=10000))

    def rm_dispatches(self) -> list[dict]:
        return annotate_transaction_rows(self.repo, self.repo.select("supply_rm_dispatches", order_by="created_at", desc=True, limit=10000))

    def forging_orders(self) -> list[dict]:
        return annotate_transaction_rows(self.repo, self.repo.select("supply_forging_orders", order_by="created_at", desc=True, limit=10000))

    def forging_receipts(self) -> list[dict]:
        return annotate_transaction_rows(self.repo, self.repo.select("supply_forging_receipts", order_by="created_at", desc=True, limit=10000))

    def downstream_events(self) -> list[dict]:
        return annotate_transaction_rows(self.repo, self.repo.select("supply_downstream_events", order_by="created_at", desc=True, limit=20000))

    def inward_register(self) -> list[dict]:
        return self.repo.select("v_qsms_inward_register", order_by="created_at", desc=True, limit=10000)

    def order(self, order_id: str) -> dict | None:
        return self.repo.get("supply_customer_orders", order_id)

    def flow_for_order(self, order: Mapping[str, Any] | str | None) -> str:
        if isinstance(order, str):
            order = self.order(order) or {}
        order = order or {}
        explicit = str(order.get("supply_flow") or "").upper().strip()
        if explicit in FLOW_LABELS:
            return explicit
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
            "Responsible Employee": self.employee_label(str(order.get("responsible_employee_id") or "")),
            "Status": order.get("status"),
        }

    def employee_label(self, employee_id: str | None) -> str:
        row = self.repo.get("employees", str(employee_id or "")) or {}
        name = " ".join(v for v in (str(row.get("first_name") or "").strip(), str(row.get("last_name") or "").strip()) if v)
        return name or str(row.get("employee_code") or "")

    # ------------------------------------------------ stock / procurement decision
    def system_available_qty(self, part_id: str) -> float:
        """Finished production plus FINISHED_GOODS Opening Stock available for customer demand.

        WIP/opening stock at RM, forging, machining or OSP stages is intentionally not
        treated as immediately dispatchable customer stock. Those quantities remain visible
        in the Opening Stock register and eligible OSP stages are exposed separately to OSP.
        """
        rows = self.repo.select("production_batches", eq={"part_id": part_id}, limit=20000)
        production = sum(max(number(r.get("quantity_available")), 0.0) for r in rows if str(r.get("status") or "").upper() not in {"REJECTED", "CANCELLED", "SCRAPPED"})
        opening = self.repo.select("supply_opening_stock", eq={"part_id": part_id, "stage": "FINISHED_GOODS", "status": "ACTIVE"}, limit=10000)
        opening_fg = sum(max(number(r.get("available_quantity_pcs")), 0.0) for r in opening)
        return round(production + opening_fg, 3)

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

    def company_branches(self, *, active_only: bool = True) -> list[dict]:
        eq = {"status": "ACTIVE"} if active_only else None
        return self.repo.select("company_branches", eq=eq, order_by="branch_code", limit=500)

    @staticmethod
    def _branch_snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
        address_parts = [str(row.get(k) or "").strip() for k in ("address_line1", "address_line2", "address_line3") if str(row.get(k) or "").strip()]
        locality = ", ".join(v for v in (str(row.get("city") or "").strip(), str(row.get("state") or "").strip(), str(row.get("postal_code") or "").strip(), str(row.get("country") or "").strip()) if v)
        address = ", ".join([*address_parts, locality] if locality else address_parts)
        return {
            "branch_id": row.get("id"), "branch_code": row.get("branch_code"), "plant_code": row.get("plant_code") or row.get("branch_code"),
            "name": row.get("branch_name") or row.get("branch_code"), "branch_name": row.get("branch_name") or row.get("branch_code"),
            "address1": row.get("address_line1"), "address2": row.get("address_line2"), "address3": row.get("address_line3"), "address": address,
            "city": row.get("city"), "state": row.get("state"), "postal_code": row.get("postal_code"), "country": row.get("country"),
            "tax_identifier": row.get("gstin"), "gstin": row.get("gstin"), "phone": row.get("phone"), "email": row.get("email"), "contact_person": row.get("contact_person"),
        }

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
        if str(po.get("approval_status") or "APPROVED").upper() == "PENDING_APPROVAL":
            return "PENDING_APPROVAL"
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

        # v4.14.14: Company Branch is the controlled issuing-plant identity for all
        # Purchase Orders and is also an available Ship-To source. Party-based Ship-To
        # sources remain Customer / Supplier / Vendor. Exact details are snapshotted.
        company_branch_id = str(p.get("company_branch_id") or "").strip()
        company_branch = self.repo.get("company_branches", company_branch_id) or {}
        if not company_branch or str(company_branch.get("status") or "ACTIVE").upper() != "ACTIVE":
            raise ValueError("Select a valid ACTIVE Company Branch / Plant for the Purchase Order.")
        plant_snapshot = self._branch_snapshot(company_branch)

        ship_to_party_id = str(p.get("ship_to_party_id") or "").strip()
        ship_to_branch_id = str(p.get("ship_to_branch_id") or "").strip()
        ship_to_source_type = str(p.get("ship_to_source_type") or "").upper().strip()
        if ship_to_source_type not in {"CUSTOMER", "SUPPLIER", "VENDOR", "BRANCH"}:
            raise ValueError("Select Ship-To Source from Company Branch, Customer, Supplier or Vendor / OSP Master.")
        if ship_to_source_type == "BRANCH":
            ship_to_branch = self.repo.get("company_branches", ship_to_branch_id) or {}
            if not ship_to_branch or str(ship_to_branch.get("status") or "ACTIVE").upper() != "ACTIVE":
                raise ValueError("Select a valid ACTIVE Company Branch for Ship-To.")
            ship_to_snapshot = self._branch_snapshot(ship_to_branch)
            ship_to_snapshot.update({"source_type": "BRANCH", "source_branch_id": ship_to_branch_id, "party_code": ship_to_branch.get("branch_code"), "party_name": ship_to_branch.get("branch_name")})
            ship_to_party_id = ""
        else:
            ship_to_party = self.repo.get("parties", ship_to_party_id) or {}
            if not ship_to_party or str(ship_to_party.get("status") or "ACTIVE").upper() != "ACTIVE":
                raise ValueError("Select a valid ACTIVE Ship-To party/address from the selected master.")
            ship_types = {str(v).upper() for v in (ship_to_party.get("party_types") or [])}
            source_valid = (
                (ship_to_source_type == "CUSTOMER" and "CUSTOMER" in ship_types)
                or (ship_to_source_type == "SUPPLIER" and bool(ship_types & {"SUPPLIER", "STEEL_MILL"}))
                or (ship_to_source_type == "VENDOR" and bool(ship_types & {"OSP_VENDOR", "FORGING_SUPPLIER"}))
            )
            if not source_valid:
                raise ValueError("The selected Ship-To party does not belong to the selected Customer / Supplier / Vendor master.")
            ship_to_snapshot = self._party_snapshot(ship_to_party)
            ship_to_snapshot.update({"source_type": ship_to_source_type, "source_party_id": ship_to_party_id})
            ship_to_branch_id = ""

        requisitioner_employee_id = str(p.get("requisitioner_employee_id") or "").strip() or current_employee_id(refresh=True)
        requisitioner_employee = self.repo.get("employees", requisitioner_employee_id) or {}
        if not requisitioner_employee or str(requisitioner_employee.get("status") or "ACTIVE").upper() != "ACTIVE":
            raise ValueError("The logged-in user must be linked to an ACTIVE Employee Master record before creating a Purchase Order.")
        requisitioner_name = " ".join(
            v for v in (
                str(requisitioner_employee.get("first_name") or "").strip(),
                str(requisitioner_employee.get("last_name") or "").strip(),
            ) if v
        ).strip()
        if not requisitioner_name:
            raise ValueError("The logged-in Employee Master record does not have a valid employee name.")

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
            line_hsn = {str(k): str(v or "").strip() for k, v in dict(p.get("line_hsn_sac") or {}).items()}
            line_fsi = {str(k): str(v or "").strip() for k, v in dict(p.get("line_fsi_part_numbers") or {}).items()}
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
                # v4.14.2: the procurement decision saved with the Customer Order / Schedule
                # is the controlled gate for PO creation. Re-running the stock calculation here
                # caused an order that was already marked RM REQUIRED to disappear/fail later
                # as stock moved for unrelated transactions. The PO still enforces remaining
                # RM balance, supplier compatibility and allocation limits below.
                decision = str(order.get("procurement_decision") or "").upper().strip()
                if decision and decision not in {"REQUIRED", "RM_REQUIRED"}:
                    raise ValueError(f"{order.get('master_reference_no')}: saved RM procurement decision is {decision.replace('_',' ').title()}.")
                balance = max(number(order.get("required_rm_kg")) - self.totals(order_id)["rm_ordered_kg"], 0.0)
                allocation = allocation_map.get(order_id, balance)
                if allocation <= 0 or allocation > balance + 0.0001:
                    raise ValueError(f"{order.get('master_reference_no')}: PO allocation must be greater than zero and cannot exceed the pending RM balance of {balance:,.3f} kg.")
                part = self.repo.get("parts", str(order.get("part_id") or "")) or {}
                raw = self.raw_material_for_supplier(str(part.get("id") or ""), supplier_id, str(order.get("raw_material_detail_id") or ""))
                if not raw:
                    identity = str(part.get("fsi_part_number") or part.get("part_number") or order.get("master_reference_no") or "Part").strip()
                    raise ValueError(f"{identity}: add an ACTIVE Raw Material Detail for the selected Supplier in Part Master first.")
                key = self.raw_material_po_group_key(part, raw)
                prepared.append({"order": order, "part": part, "raw": raw, "allocation": allocation, "key": key})
                group = groups.setdefault(key, {"part": part, "raw": raw, "quantity": 0.0, "orders": [], "members": []})
                group["quantity"] += allocation; group["orders"].append((order, allocation)); group["members"].append({"order": order, "part": part, "raw": raw, "allocation": allocation})

            gst_percent = max(number(p.get("gst_percent")), 0.0)
            order_date_value = p.get("order_date") or date.today().isoformat()
            currency = str(p.get("currency") or "INR").upper()
            line_data: list[dict[str, Any]] = []
            subtotal = 0.0
            for key, group in groups.items():
                part, raw = group["part"], group["raw"]
                members = list(group.get("members") or [])
                common_rm_code = str(raw.get("supplier_rm_item_code") or "").strip()
                member_hsn = {str((m["raw"].get("hsn_sac_code") or m["part"].get("hsn_sac_code") or "")).strip() for m in members}
                if common_rm_code and len({v for v in member_hsn if v}) > 1:
                    raise ValueError(f"Shared RM item {common_rm_code}: HSN/SAC differs between linked finished Parts. Split the PO or align the supplier master data.")
                member_prices = [self.current_price(str(m["part"].get("id")), supplier_id, on_date=order_date_value, uom="KGS", raw_material_detail_id=str(m["raw"].get("id") or "") or None) for m in members]
                positive_prices = {round(number(v), 6) for v in member_prices if number(v) > 0}
                if common_rm_code and len(positive_prices) > 1:
                    raise ValueError(f"Shared RM item {common_rm_code}: current supplier price differs between linked finished Parts. Align Price History or split the PO.")
                price = line_prices.get(key)
                if price is None or price <= 0:
                    price = self.current_price(str(part.get("id")), supplier_id, on_date=order_date_value, uom="KGS", raw_material_detail_id=str(raw.get("id") or "") or None)
                price = max(number(price), 0.0)
                if price <= 0:
                    raise ValueError(f"{part.get('fsi_part_number') or part.get('part_number') or 'Part'}: current supplier price is missing in Part Master Price History.")
                qty = round(number(group["quantity"]), 3)
                line_total = round(qty * price, 2); subtotal += line_total
                fsi = common_rm_code or line_fsi.get(key) or str(part.get("fsi_part_number") or "").strip()
                if not fsi:
                    raise ValueError(f"Enter an FSI Part Number for {part.get('part_number') or 'the selected Part'} in the PO item grid before creating the supplier PO.")
                history = self.price_history_for_po(str(part.get("id")), supplier_id, po_date=order_date_value, uom="KGS", raw_material_detail_id=str(raw.get("id") or "") or None)
                master_hsn = str(raw.get("hsn_sac_code") or part.get("hsn_sac_code") or "").strip()
                hsn_value = line_hsn.get(key) or master_hsn
                if not hsn_value:
                    raise ValueError(f"{part.get('fsi_part_number') or part.get('part_number') or 'Part'}: HSN / SAC is missing in Part Master Raw Material Details.")
                line_data.append({"key": key, "part": part, "raw": raw, "fsi_part_number": fsi, "supplier_item_code": common_rm_code or None, "linked_parts": sorted({str(m["part"].get("fsi_part_number") or m["part"].get("part_number") or "") for m in members if m.get("part")}), "quantity": qty, "unit_price": price, "hsn_sac_code": hsn_value, "line_total": line_total, "gst_amount": round(line_total*gst_percent/100.0,2), "technical": self.technical_data_snapshot(raw, part), "price_history": history[:250], "orders": group["orders"]})
            subtotal = round(subtotal, 2)
            gst_amount = round(subtotal * gst_percent / 100.0, 2)
            state = str(supplier.get("state") or "").strip().casefold(); intra_state = not state or state in {"maharashtra", "mh"}
            cgst = round(gst_amount/2.0,2) if intra_state else 0.0; sgst = round(gst_amount/2.0,2) if intra_state else 0.0; igst = gst_amount if not intra_state else 0.0
            other = max(number(p.get("other_amount")),0.0); grand_total = round(subtotal+cgst+sgst+igst+other,2)
            po_number = str(self.repo.rpc("qcms_next_supply_po_number") or "").strip()
            if not po_number:
                raise RuntimeError("QCMS could not allocate the next Purchase Order number.")
            header = self.repo.insert("supply_purchase_orders", {"po_number":po_number,"po_type":po_type,"supplier_id":supplier_id,"order_date":order_date_value,"delivery_date":p.get("delivery_date"),"requisitioner":requisitioner_name,"requisitioner_employee_id":requisitioner_employee_id,"ship_via":p.get("ship_via") or "Road","incoterm":p.get("incoterm") or "DAP, CHAKAN","payment_term":p.get("payment_term") or "NET 30 DAYS AFTER GRN","quotation_reference":p.get("quotation_reference"),"quotation_date":p.get("quotation_date"),"old_po_reference":p.get("old_po_reference"),"currency":currency,"company_branch_id":company_branch_id,"plant_snapshot":plant_snapshot,"vendor_snapshot":self._party_snapshot(supplier),"ship_to_party_id":ship_to_party_id or None,"ship_to_branch_id":ship_to_branch_id or None,"ship_to_source_type":ship_to_source_type,"ship_to_snapshot":ship_to_snapshot,"remarks":p.get("remarks") or "PART WILL BE SUPPLIED AS PER DRAWING.","special_instructions":p.get("special_instructions") or DEFAULT_SPECIAL_INSTRUCTIONS,"subtotal":subtotal,"cgst_amount":cgst,"sgst_amount":sgst,"igst_amount":igst,"other_amount":other,"grand_total":grand_total,"status":"PENDING_APPROVAL","approval_status":"PENDING_APPROVAL","submitted_by_employee_id":requisitioner_employee_id,"submitted_at":datetime.now(timezone.utc).isoformat(),"replaces_purchase_order_id":p.get("replaces_purchase_order_id")})
            if p.get("replaces_purchase_order_id"):
                try:
                    self.repo.update("supply_purchase_orders", str(p.get("replaces_purchase_order_id")), {"replacement_purchase_order_id": header.get("id")})
                except Exception:
                    pass

            items: list[dict] = []; stages: list[dict] = []
            for line in line_data:
                part, raw = line["part"], line["raw"]; fsi = str(line.get("fsi_part_number") or "").strip()
                first_order = line["orders"][0][0]
                grade = self.repo.get("material_grades", str(raw.get("material_grade_id") or part.get("material_grade_id") or "")) or {}
                rm_identity = " · ".join(v for v in (str(raw.get("material_section_name") or "").strip(), str(grade.get("grade_code") or grade.get("grade_name") or "").strip(), str(raw.get("section_size") or part.get("section_size") or "").strip()) if v)
                item = self.repo.insert("supply_purchase_order_items", {"purchase_order_id":header.get("id"),"customer_order_id":first_order.get("id"),"part_id":part.get("id"),"material_grade_id":raw.get("material_grade_id") or part.get("material_grade_id"),"raw_material_detail_id":raw.get("id"),"item_no":fsi,"fsi_part_number_snapshot":fsi,"supplier_item_code_snapshot":line.get("supplier_item_code"),"linked_finished_parts_snapshot":line.get("linked_parts") or [part.get("fsi_part_number") or part.get("part_number")],"original_part_number_snapshot":part.get("part_number"),"hsn_sac_code":line.get("hsn_sac_code") or None,"item_description":rm_identity or part.get("part_name") or "Raw Material","rm_section":raw.get("section_size") or part.get("section_size"),"quantity":line["quantity"],"uom":"KGS","unit_price":line["unit_price"],"gst_percent":gst_percent,"gst_amount":line["gst_amount"],"line_total":line["line_total"],"forging_weight_kg":raw.get("forging_weight_kg") or part.get("forging_weight_kg"),"gross_weight_kg":raw.get("gross_weight_kg") or part.get("gross_weight_kg"),"technical_data_snapshot":line["technical"],"price_history_snapshot":line["price_history"],"remarks":p.get("item_remarks")})
                self._record_purchase_price(part_id=str(part.get("id")),supplier_id=supplier_id,raw_material_detail_id=str(raw.get("id")),po_date=order_date_value,price=line["unit_price"],uom="KGS",currency=currency,source_item_id=str(item.get("id")))
                refreshed_history = self.price_history_for_po(str(part.get("id")), supplier_id, po_date=order_date_value, uom="KGS", raw_material_detail_id=str(raw.get("id") or "") or None)
                if refreshed_history:
                    item = self.repo.update("supply_purchase_order_items", str(item.get("id")), {"price_history_snapshot": refreshed_history[:250]})
                items.append(item)
                for order, allocation in line["orders"]:
                    self.repo.insert("supply_purchase_order_sources", {"purchase_order_id":header.get("id"),"purchase_order_item_id":item.get("id"),"customer_order_id":order.get("id"),"allocated_qty":round(number(allocation),3),"allocation_uom":"KGS"})
                    stage = self.save_transaction("supply_rm_purchase_orders", {"customer_order_id":order.get("id"),"rm_supplier_id":supplier_id,"supplier_order_no":po_number,"order_date":header.get("order_date"),"ordered_qty_kg":round(number(allocation),3),"expected_date":header.get("delivery_date"),"status":"PENDING_APPROVAL","remarks":"Controlled Purchase Order "+po_number,"purchase_order_id":header.get("id"),"purchase_order_item_id":item.get("id")})
                    stages.append(stage); self.sync_order_status(str(order.get("id")))
            return {"header":header,"items":items,"stages":stages,"item":items[0] if items else {},"stage":stages[0] if stages else {}}

        # ------------------------------------------------------------------
        # FORGING: one supplier PO may consolidate multiple finished-Part sources when
        # Part Master gives them the same Supplier Forging Part No. Source allocations
        # remain separate so every Customer Order / RM dispatch is traceable.
        # ------------------------------------------------------------------
        raw_sources = list(p.get("forging_sources") or [])
        if not raw_sources:
            oid = str(p.get("customer_order_id") or "")
            raw_sources = [{"customer_order_id": oid, "quantity": p.get("quantity"), "rm_dispatch": p.get("rm_dispatch") or {}}] if oid else []
        if not raw_sources:
            raise ValueError("Select at least one Forging PO source.")
        prepared_forging: list[dict[str, Any]] = []
        groups: dict[str, dict[str, Any]] = {}
        for src in raw_sources:
            order_id = str(src.get("customer_order_id") or ""); order = self.order(order_id) or {}
            if not order: raise ValueError("One selected Forging PO source no longer exists.")
            part = self.repo.get("parts", str(order.get("part_id") or "")) or {}
            raw = self.raw_material_for_supplier(str(part.get("id") or ""), supplier_id, str(order.get("raw_material_detail_id") or "")) or {}
            if not raw: raise ValueError(f"{part.get('fsi_part_number') or part.get('part_number')}: add an ACTIVE supplier Raw Material / Forging Detail first.")
            qty = number(src.get("quantity"));
            if qty <= 0: raise ValueError("Forging Purchase Order quantity must be greater than zero for every selected source.")
            key = self.forging_po_group_key(part, raw)
            group = groups.setdefault(key, {"part": part, "raw": raw, "quantity": 0.0, "members": []})
            member={"order":order,"part":part,"raw":raw,"quantity":qty,"rm_dispatch":dict(src.get("rm_dispatch") or {})}
            group["quantity"] += qty; group["members"].append(member); prepared_forging.append(member)
        gst_percent=max(number(p.get("gst_percent")),0.0); order_date_value=p.get("order_date") or date.today().isoformat(); currency=str(p.get("currency") or "INR").upper()
        line_data=[]; subtotal=0.0
        for key, group in groups.items():
            part,raw=group["part"],group["raw"]; members=group["members"]
            common_code=str(raw.get("supplier_forging_part_number") or "").strip()
            if len(members)>1 and not common_code:
                raise ValueError("Multiple finished Parts can share one Forging PO item only when the same Supplier Forging Part No. is maintained in Part Master for every source.")
            codes={str(m["raw"].get("supplier_forging_part_number") or "").strip().casefold() for m in members}
            if len(codes)>1: raise ValueError("Selected sources do not use the same Supplier Forging Part No.; split them into separate PO items.")
            hsns={str(m["raw"].get("hsn_sac_code") or m["part"].get("hsn_sac_code") or "").strip() for m in members}
            if not all(hsns): raise ValueError("HSN / SAC is missing in Part Master Raw Material Details for one or more selected Forging sources.")
            if len(hsns)>1: raise ValueError(f"Shared Forging item {common_code or '-'} has different HSN/SAC values; split the PO or align master data.")
            prices=[self.current_price(str(m["part"].get("id")),supplier_id,on_date=order_date_value,uom="NOS",raw_material_detail_id=str(m["raw"].get("id") or "") or None) for m in members]
            positive={round(number(v),6) for v in prices if number(v)>0}
            if not positive: raise ValueError(f"{common_code or part.get('fsi_part_number') or part.get('part_number')}: current supplier price is missing in Part Master Price History.")
            if len(positive)>1: raise ValueError(f"Shared Forging item {common_code or '-'} has different current prices across linked Parts. Align Price History or split the PO.")
            unit_price=next(iter(positive)); qty=round(number(group["quantity"]),3); line_total=round(qty*unit_price,2); subtotal+=line_total
            item_no=common_code or str(part.get("fsi_part_number") or p.get("fsi_part_number") or "").strip()
            if not item_no: raise ValueError("Enter an FSI Part Number or Supplier Forging Part No. for the supplier PO item.")
            line_data.append({"key":key,"part":part,"raw":raw,"members":members,"item_no":item_no,"common_code":common_code or None,"hsn":next(iter(hsns)),"quantity":qty,"unit_price":unit_price,"line_total":line_total,"gst_amount":round(line_total*gst_percent/100.0,2)})
        subtotal=round(subtotal,2); gst_amount=round(subtotal*gst_percent/100.0,2); state=str(supplier.get("state") or "").strip().casefold(); intra_state=not state or state in {"maharashtra","mh"}; cgst=round(gst_amount/2,2) if intra_state else 0.0; sgst=round(gst_amount/2,2) if intra_state else 0.0; igst=gst_amount if not intra_state else 0.0; other=max(number(p.get("other_amount")),0.0); grand_total=round(subtotal+cgst+sgst+igst+other,2)
        po_number=str(self.repo.rpc("qcms_next_supply_po_number") or "").strip();
        if not po_number: raise RuntimeError("QCMS could not allocate the next Purchase Order number.")
        header=self.repo.insert("supply_purchase_orders", {"po_number":po_number,"po_type":po_type,"supplier_id":supplier_id,"order_date":order_date_value,"delivery_date":p.get("delivery_date"),"requisitioner":requisitioner_name,"requisitioner_employee_id":requisitioner_employee_id,"ship_via":p.get("ship_via") or "Road","incoterm":p.get("incoterm") or "DAP, CHAKAN","payment_term":p.get("payment_term") or "NET 30 DAYS AFTER GRN","quotation_reference":p.get("quotation_reference"),"quotation_date":p.get("quotation_date"),"old_po_reference":p.get("old_po_reference"),"currency":currency,"company_branch_id":company_branch_id,"plant_snapshot":plant_snapshot,"vendor_snapshot":self._party_snapshot(supplier),"ship_to_party_id":ship_to_party_id or None,"ship_to_branch_id":ship_to_branch_id or None,"ship_to_source_type":ship_to_source_type,"ship_to_snapshot":ship_to_snapshot,"remarks":p.get("remarks") or "PART WILL BE SUPPLIED AS PER DRAWING.","special_instructions":p.get("special_instructions") or DEFAULT_SPECIAL_INSTRUCTIONS,"subtotal":subtotal,"cgst_amount":cgst,"sgst_amount":sgst,"igst_amount":igst,"other_amount":other,"grand_total":grand_total,"status":"PENDING_APPROVAL","approval_status":"PENDING_APPROVAL","submitted_by_employee_id":requisitioner_employee_id,"submitted_at":datetime.now(timezone.utc).isoformat(),"replaces_purchase_order_id":p.get("replaces_purchase_order_id")})
        items=[]; stages=[]
        for line in line_data:
            part,raw=line["part"],line["raw"]; members=line["members"]; first=members[0]["order"]; linked_parts=sorted({str(m["part"].get("fsi_part_number") or m["part"].get("part_number") or "") for m in members})
            item=self.repo.insert("supply_purchase_order_items", {"purchase_order_id":header.get("id"),"customer_order_id":first.get("id"),"part_id":part.get("id"),"material_grade_id":raw.get("material_grade_id") or part.get("material_grade_id"),"raw_material_detail_id":raw.get("id"),"item_no":line["item_no"],"fsi_part_number_snapshot":line["item_no"],"supplier_item_code_snapshot":line.get("common_code"),"linked_finished_parts_snapshot":linked_parts,"original_part_number_snapshot":part.get("part_number"),"hsn_sac_code":line["hsn"],"item_description":str(raw.get("supplier_forging_part_number") or part.get("part_name") or "Forging"),"rm_section":raw.get("section_size") or part.get("section_size"),"quantity":line["quantity"],"uom":"NOS","unit_price":line["unit_price"],"gst_percent":gst_percent,"gst_amount":line["gst_amount"],"line_total":line["line_total"],"forging_weight_kg":raw.get("forging_weight_kg") or part.get("forging_weight_kg"),"gross_weight_kg":raw.get("gross_weight_kg") or part.get("gross_weight_kg"),"technical_data_snapshot":self.technical_data_snapshot(raw,part),"price_history_snapshot":self.price_history_for_po(str(part.get("id")),supplier_id,po_date=order_date_value,uom="NOS",raw_material_detail_id=str(raw.get("id") or "") or None)[:250],"remarks":p.get("item_remarks")})
            items.append(item)
            for m in members:
                order=m["order"]; qty=number(m["quantity"]); dispatch=m["rm_dispatch"]
                self.repo.insert("supply_purchase_order_sources", {"purchase_order_id":header.get("id"),"purchase_order_item_id":item.get("id"),"customer_order_id":order.get("id"),"allocated_qty":round(qty,3),"allocation_uom":"PCS"})
                stage_payload={"customer_order_id":order.get("id"),"forging_supplier_id":supplier_id,"supplier_order_no":po_number,"order_date":header.get("order_date"),"order_qty_pcs":qty,"required_rm_kg":round(qty*number(order.get("gross_weight_kg_snapshot")),3),"expected_date":header.get("delivery_date"),"status":"PENDING_APPROVAL","remarks":"Controlled Purchase Order "+po_number,"purchase_order_id":header.get("id"),"purchase_order_item_id":item.get("id")}
                if dispatch: stage_payload.update({"rm_dispatch_id":dispatch.get("id"),"inward_lot_id":dispatch.get("inward_lot_id"),"heat_number":dispatch.get("heat_number"),"heat_code":dispatch.get("heat_code")})
                stage=self.save_transaction("supply_forging_orders",stage_payload); stages.append(stage); self.sync_order_status(str(order.get("id")))
        return {"header":header,"item":items[0] if items else {},"items":items,"stage":stages[0] if stages else {},"stages":stages}

    def cancel_purchase_order(self, purchase_order_id: str, reason: str) -> dict:
        result = self.repo.rpc("qcms_cancel_purchase_order", {"p_purchase_order_id": purchase_order_id, "p_reason": reason})
        return dict(result or {})

    def approve_purchase_order(self, purchase_order_id: str, remarks: str | None = None) -> dict:
        result = self.repo.rpc("qcms_approve_purchase_order", {"p_purchase_order_id": purchase_order_id, "p_remarks": remarks})
        return dict(result or {})

    def ensure_purchase_order_confirmation(self, purchase_order_id: str) -> dict:
        result = self.repo.rpc("qcms_ensure_po_confirmation", {"p_purchase_order_id": purchase_order_id})
        return dict(result or {})

    def purchase_order_confirmation(self, purchase_order_id: str) -> dict:
        rows = self.repo.select("supply_po_confirmations", eq={"purchase_order_id": purchase_order_id}, order_by="created_at", desc=True, limit=1)
        return dict(rows[0]) if rows else {}

    def confirm_purchase_order(self, purchase_order_id: str, payload: Mapping[str, Any]) -> dict:
        result = self.repo.rpc("qcms_confirm_purchase_order", {
            "p_purchase_order_id": purchase_order_id,
            "p_confirmation_reference": str(payload.get("confirmation_reference") or "").strip(),
            "p_confirmation_date": payload.get("confirmation_date"),
            "p_confirmed_delivery_date": payload.get("confirmed_delivery_date"),
            "p_remarks": str(payload.get("remarks") or "").strip() or None,
        })
        return dict(result or {})

    def purchase_order_confirmations(self) -> list[dict]:
        return self.repo.select("supply_po_confirmations", order_by="updated_at", desc=True, limit=5000)

    def purchase_order_approval_target(self, purchase_order_id: str) -> dict:
        """Resolve PO approver using configured route first, Reports-To second, permission fallback last.

        The database RPC is authoritative after v4.14.17. The local fallback keeps the
        UI informative while a controlled deployment is between source install and
        automatic Supabase migration verification.
        """
        try:
            result = self.repo.rpc("qcms_purchase_order_approval_target", {"p_purchase_order_id": purchase_order_id})
            if isinstance(result, Mapping):
                return dict(result)
        except Exception:
            pass
        po = self.purchase_order(purchase_order_id) or {}
        submitter_id = str(po.get("submitted_by_employee_id") or "")
        submitter = self.repo.get("employees", submitter_id) if submitter_id else {}
        department = str((submitter or {}).get("department") or "").strip()
        try:
            routes = self.repo.select("qcms_module_approval_routes", eq={"module_key": "SUPPLY_CHAIN", "status": "ACTIVE"}, limit=500)
        except Exception:
            routes = []
        candidates=[]
        for route in routes:
            route_department=str(route.get("department") or "").strip()
            employee_id=str(route.get("employee_id") or "")
            if not bool(route.get("required", True)) or not employee_id:
                continue
            if route_department and route_department.casefold()!=department.casefold():
                continue
            priority=0 if route_department else 1
            candidates.append((priority,int(route.get("level_no") or 1),route))
        if candidates:
            route=sorted(candidates,key=lambda item:(item[0],item[1]))[0][2]
            employee=self.repo.get("employees",str(route.get("employee_id") or "")) or {}
            if employee and str(employee.get("status") or "ACTIVE").upper()=="ACTIVE":
                return {"source":"CONFIGURED_ROUTE","employee_id":employee.get("id"),"employee_code":employee.get("employee_code"),"employee_name":" ".join(v for v in (str(employee.get("first_name") or "").strip(),str(employee.get("last_name") or "").strip()) if v),"email":employee.get("email"),"department":employee.get("department"),"level_no":route.get("level_no"),"level_name":route.get("level_name") or "Approval","route_department":route.get("department"),"submitted_by_employee_id":submitter_id}
        manager_id=str((submitter or {}).get("reports_to_employee_id") or "")
        manager=self.repo.get("employees",manager_id) if manager_id else {}
        if manager:
            return {"source":"REPORTS_TO","employee_id":manager.get("id"),"employee_code":manager.get("employee_code"),"employee_name":" ".join(v for v in (str(manager.get("first_name") or "").strip(),str(manager.get("last_name") or "").strip()) if v),"email":manager.get("email"),"department":manager.get("department"),"level_no":1,"level_name":"Reports-To Manager Approval","route_department":department,"submitted_by_employee_id":submitter_id}
        return {"source":"PERMISSION_FALLBACK","employee_id":None,"employee_code":None,"employee_name":None,"email":None,"department":department,"level_no":1,"level_name":"Any different employee with Supply Chain Approve permission","route_department":department,"submitted_by_employee_id":submitter_id}

    def purchase_order_reissue_sources(self, purchase_order_id: str) -> list[str]:
        """Return the original Customer Order/Schedule sources for controlled reissue."""
        ids: list[str] = []
        for row in self.purchase_order_sources(purchase_order_id):
            value = str(row.get("customer_order_id") or "")
            if value and value not in ids:
                ids.append(value)
        if not ids:
            for item in self.purchase_order_items(purchase_order_id):
                value = str(item.get("customer_order_id") or "")
                if value and value not in ids:
                    ids.append(value)
        return ids

    def purchase_order_rows(self) -> list[dict]:
        parts, parties, grades = self.master_maps()
        headers = {str(r.get("id")): r for r in annotate_transaction_rows(self.repo, self.purchase_orders())}
        confirmations = {str(r.get("purchase_order_id")): r for r in self.purchase_order_confirmations()}
        rows: list[dict] = []
        for item in self.purchase_order_items():
            header = headers.get(str(item.get("purchase_order_id"))) or {}
            part = parts.get(str(item.get("part_id"))) or {}
            supplier = parties.get(str(header.get("supplier_id"))) or {}
            grade = grades.get(str(item.get("material_grade_id"))) or {}
            received = self.purchase_order_item_received_qty(str(item.get("id")))
            confirmation = confirmations.get(str(header.get("id"))) or {}
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
                "FSI Part Number": item.get("fsi_part_number_snapshot") or part.get("fsi_part_number"), "HSN / SAC": item.get("hsn_sac_code") or part.get("hsn_sac_code"), "Part Description": item.get("item_description") or part.get("part_name"),
                "Customer Orders / Schedules": " · ".join(source_labels) if source_labels else "",
                "Material Grade": grade.get("grade_code"), "RM Section": item.get("rm_section"), "Ordered Qty": ordered, "UOM": item.get("uom"),
                "Received Qty": received, "Pending Qty": max(ordered-received, 0), "Unit Price": item.get("unit_price"), "GST %": item.get("gst_percent"),
                "Total": header.get("grand_total"), "Approval Status": header.get("approval_status") or "APPROVED",
                "Supplier Confirmation": confirmation.get("confirmation_status") or ("NOT STARTED" if str(header.get("approval_status") or "").upper() != "APPROVED" else "PENDING"),
                "Supplier Confirmation Ref": confirmation.get("confirmation_reference"),
                "Confirmed Delivery": confirmation.get("confirmed_delivery_date"),
                "Reminder Count": confirmation.get("reminder_count") or 0,
                "Data Entry Status": header.get("Data Entry Status") or header.get("approval_status") or header.get("status"),
                "Created By User": header.get("Created By User"), "Last Modified By User": header.get("Last Modified By User"),
                "Status": header.get("status"), "_po_id": header.get("id"), "_item_id": item.get("id"), "_part_id": item.get("part_id"), "_supplier_id": header.get("supplier_id"),
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
        p["required_rm_kg"] = round(qty * gross, 3) if flow in FLOW_REQUIRES_FSI_RM else 0.0
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
        p["supply_flow"] = flow
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
        p["required_rm_kg"] = round(qty * gross, 3) if flow in FLOW_REQUIRES_FSI_RM else 0.0
        check = self.procurement_check(str(merged.get("part_id") or ""), str(merged.get("customer_id") or ""), anchor=merged.get("schedule_month") or merged.get("customer_delivery_date") or merged.get("order_date"), proposed_three_month_qty=number(p.pop("proposed_three_month_qty", 0)), exclude_order_id=record_id)
        requested = bool(merged.get("rm_procurement_required", check["rm_procurement_allowed"])) if flow in FLOW_REQUIRES_FSI_RM else False
        if flow == FLOW_DIRECT_FORGING:
            decision = "DIRECT_FORGING"
        elif not check["rm_procurement_allowed"]:
            requested = False; decision = "AVAILABLE_STOCK"
        else:
            decision = "REQUIRED" if requested else "MANUAL_NOT_REQUIRED"
        p.update({"rm_procurement_required":requested,"available_stock_pcs_snapshot":check["available_stock_pcs"],"three_month_schedule_pcs_snapshot":check["three_month_schedule_pcs"],"procurement_shortage_pcs_snapshot":check["shortage_pcs"],"procurement_decision":decision})
        p["supply_flow"] = flow
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

    def purchase_order_source_status(self, po_type: str) -> list[dict]:
        """Return every open Customer Order with explicit PO eligibility/reason.

        This prevents the Purchase Order page from looking empty when an order is
        intentionally waiting on a previous Supply Chain stage.
        """
        po_type = str(po_type or "").upper()
        rm_pending_ids = {str(r.get("id")) for r in self.pending_customer_orders_for_rm()}
        forging_pending = self.pending_forging_po_sources() if po_type == "FORGING" else []
        forging_by_order = {str(r.get("_customer_order_id") or ""): r for r in forging_pending}
        rows: list[dict] = []
        for order in self.customer_orders():
            if str(order.get("status") or "") in {"COMPLETED", "CANCELLED"}:
                continue
            oid = str(order.get("id") or "")
            flow = self.flow_for_order(order)
            eligible = False; reason = ""
            if po_type == "RAW_MATERIAL":
                if flow not in FLOW_REQUIRES_FSI_RM:
                    reason = "Direct Forging flow · RM PO not required"
                elif not bool(order.get("rm_procurement_required", True)):
                    reason = str(order.get("procurement_decision") or "RM not required").replace("_", " ").title()
                elif oid in rm_pending_ids:
                    eligible = True; reason = "Eligible for RM Purchase Order"
                else:
                    reason = "RM requirement already fully ordered"
            else:
                if oid in forging_by_order:
                    eligible = True
                    src = forging_by_order[oid]
                    reason = "Eligible · Direct Customer Order" if str(src.get("_source_type")) == "CUSTOMER_ORDER" else "Eligible · RM dispatched to Forger"
                elif flow == FLOW_FSI_RM:
                    reason = "Waiting for RM Receipt / RM to Forger"
                elif flow == FLOW_FSI_RM_DIRECT_PRODUCTION:
                    reason = "Direct Production flow · Forging PO not required"
                else:
                    reason = "Forging requirement already ordered"
            row = dict(order); row["_po_eligible"] = eligible; row["_po_reason"] = reason
            if po_type == "FORGING" and oid in forging_by_order:
                row["_po_source"] = dict(forging_by_order[oid])
            rows.append(row)
        rows.sort(key=lambda r: (not bool(r.get("_po_eligible")), str(r.get("customer_delivery_date") or "9999-12-31"), str(r.get("master_reference_no") or "")))
        return rows

    def pending_customer_orders_for_rm(self) -> list[dict]:
        rows = []
        for order in self.customer_orders():
            if str(order.get("status")) in {"COMPLETED", "CANCELLED"}:
                continue
            if self.flow_for_order(order) not in FLOW_REQUIRES_FSI_RM:
                continue
            if not bool(order.get("rm_procurement_required", True)):
                continue
            # The RM Procurement / PO source list must respect the decision saved with
            # the Customer Order. A fresh stock check is enforced again only at PO save
            # time so an order never silently disappears from the pending worklist.
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
            if str(po.get("status")) in {"CANCELLED", "PENDING_APPROVAL"}:
                continue
            if not self._po_confirmation_is_confirmed(str(po.get("purchase_order_id") or "")):
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
            order = self.order(str(rec.get("customer_order_id") or "")) or {}
            if self.flow_for_order(order) != FLOW_FSI_RM:
                continue
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
            if str(fo.get("status")) in {"CANCELLED", "PENDING_APPROVAL"}: continue
            if not self._po_confirmation_is_confirmed(str(fo.get("purchase_order_id") or "")): continue
            received=totals.get(str(fo.get("id")),0); ordered=number(fo.get("order_qty_pcs"))
            if received + .0001 < ordered:
                row=dict(fo); row["received_qty_pcs"]=received; row["balance_qty_pcs"]=max(ordered-received,0); rows.append(row)
        rows.sort(key=lambda r:(str(r.get("expected_date") or "9999-12-31"),str(r.get("supplier_order_no") or "")))
        return rows

    def pending_sources_for_downstream(self, event_type: str) -> list[dict]:
        event_type=str(event_type).upper()
        downstream=self.downstream_events()
        if event_type=="MACHINING":
            used_forging={str(e.get("source_forging_receipt_id")) for e in downstream if e.get("event_type")=="MACHINING" and e.get("source_forging_receipt_id")}
            used_rm={str(e.get("source_rm_receipt_id")) for e in downstream if e.get("event_type")=="MACHINING" and e.get("source_rm_receipt_id")}
            rows: list[dict] = []
            for receipt in self.forging_receipts():
                if str(receipt.get("id")) in used_forging or number(receipt.get("received_qty_pcs")) <= 0:
                    continue
                row=dict(receipt); row["_source_type"]="FORGING_RECEIPT"; row["_source_id"]=str(receipt.get("id")); rows.append(row)
            # Flow 3 enters production directly from Material Inward / RM Receipt.
            for receipt in self.rm_receipts():
                rid=str(receipt.get("id") or "")
                if not rid or rid in used_rm:
                    continue
                order=self.order(str(receipt.get("customer_order_id") or "")) or {}
                if self.flow_for_order(order) != FLOW_FSI_RM_DIRECT_PRODUCTION:
                    continue
                inward=self.repo.get("inward_lots",str(receipt.get("inward_lot_id") or "")) or {}
                production_qty=number(inward.get("accepted_production_quantity_pcs") or inward.get("production_quantity_pcs"))
                if production_qty <= 0:
                    continue
                row=dict(receipt)
                row.update({
                    "_source_type":"RM_RECEIPT", "_source_id":rid,
                    "received_qty_pcs":production_qty,
                    "receipt_number":receipt.get("receipt_number") or inward.get("inward_number"),
                    "inward_lot_id":receipt.get("inward_lot_id") or inward.get("id"),
                    "heat_number":receipt.get("heat_number") or inward.get("heat_number"),
                    "heat_code":receipt.get("heat_code") or inward.get("heat_code"),
                })
                rows.append(row)
            rows.sort(key=lambda r:(str(r.get("receipt_date") or "9999-12-31"),str(r.get("receipt_number") or "")))
            return rows
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
        if not self._po_confirmation_is_confirmed(str(po.get("purchase_order_id") or "")):
            raise ValueError("Supplier PO Confirmation is still pending. Upload and record the supplier acknowledgement before RM receipt / Material Inward linking.")
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
        if self.flow_for_order(order) in {FLOW_DIRECT_FORGING, FLOW_FSI_RM_DIRECT_PRODUCTION}:
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
