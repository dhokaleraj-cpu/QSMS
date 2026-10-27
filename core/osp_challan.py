"""R37 · OSP Material Out returnable delivery challan.

Data (osp_challans / osp_challan_lines / osp_challan_returns + live OSP genealogy), the supplier-facing
"RETURNABLE DELIVERY CHALLAN" PDF (ReportLab, PO Design-B family) and the vendor e-mail notifier.

Customer confidentiality (R36b): the challan goes to the OSP vendor, so it prints the FSI part number and
part description only - never the customer part number, customer name / code / PO / order / delivery date.
"""
from __future__ import annotations

import re
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from core.repository import Repository

CHALLAN_TITLE = "RETURNABLE DELIVERY CHALLAN"
DEFAULT_GST = 18.0
DEFAULT_UOM = "NOS"
SHIP_VIA_OPTIONS = ("Road", "Hand Delivery", "Courier", "Vendor Vehicle", "FSI Vehicle", "Rail", "Air")
INCOTERM_OPTIONS = ("EXWORKS", "FOR", "DAP", "FCA", "CIF", "FOB")
PAYMENT_TERM_OPTIONS = ("NET 30 DAYS AFTER GRN", "NET 45 DAYS AFTER GRN", "NET 60 DAYS AFTER GRN", "ADVANCE", "NOT APPLICABLE (JOB WORK)")
# Fields that must never reach a vendor-facing challan.
_INTERNAL_KEYS = ("part_number", "customer_id", "customer_name", "customer_part_number", "customer_po_number")


def _s(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _f(value: Any) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number and number not in (float("inf"), float("-inf")) else 0.0


def _date_text(value: Any) -> str:
    text = _s(value)
    if not text:
        return ""
    try:
        y, m, d = text[:10].split("-")
        return f"{d}-{m}-{y}"
    except Exception:
        return text[:10]


def _qty(value: Any) -> str:
    number = _f(value)
    return f"{number:,.0f}" if float(number).is_integer() else f"{number:,.3f}".rstrip("0").rstrip(".")


# ----------------------------------------------------------------------------------- pure helpers
def next_number_from(existing: Iterable[Any], plant_code: str | None = "D9") -> str:
    """Python mirror of qcms_next_osp_challan_number: JWC + plant code + 5 digits."""
    prefix = "JWC" + re.sub(r"[^A-Za-z0-9]", "", str(plant_code or "D9")).upper()
    pattern = re.compile("^" + re.escape(prefix) + r"([0-9]{1,12})$")
    best = 0
    for value in existing:
        match = pattern.match(_s(value).upper())
        if match:
            best = max(best, int(match.group(1)))
    return f"{prefix}{best + 1:05d}"


def line_amounts(line: Mapping[str, Any]) -> dict[str, float]:
    qty = _f(line.get("quantity") if line.get("quantity") is not None else line.get("quantity_dispatched"))
    taxable = round(qty * _f(line.get("unit_price")), 2)
    gst = round(taxable * _f(line.get("gst_percent")) / 100.0, 2)
    return {"quantity": qty, "taxable": taxable, "gst": gst}


def challan_totals(lines: Sequence[Mapping[str, Any]], shipping: Any = 0, other: Any = 0) -> dict[str, float]:
    subtotal = round(sum(line_amounts(l)["taxable"] for l in lines), 2)
    tax = round(sum(line_amounts(l)["gst"] for l in lines), 2)
    return {"subtotal": subtotal, "tax": tax, "shipping": round(_f(shipping), 2), "other": round(_f(other), 2),
            "total": round(subtotal + tax + _f(shipping) + _f(other), 2)}


def merge_returns(receipts: Sequence[Mapping[str, Any]], entries: Sequence[Mapping[str, Any]]) -> list[dict]:
    """One row per vendor return.

    * every OSP Inward receipt is a return (quantity = receipt quantity); a return entry linked to the receipt
      (osp_receipt_id) only adds vendor challan / vehicle / rejected quantity -> never counted twice;
    * entries without a receipt are returns recorded only on the challan (e.g. unprocessed / rejected material).
    """
    linked = {str(e.get("osp_receipt_id")): e for e in entries if e.get("osp_receipt_id")}
    receipt_ids = {str(r.get("id")) for r in receipts}
    rows: list[dict] = []
    for receipt in receipts:
        entry = linked.get(str(receipt.get("id"))) or {}
        rows.append({
            "source": "OSP Inward", "receipt_id": receipt.get("id"), "entry_id": entry.get("id"),
            "osp_job_id": receipt.get("osp_job_id"), "receipt_number": receipt.get("receipt_number"),
            "challan_no": _s(entry.get("vendor_challan_number")) or _s(receipt.get("receipt_challan")),
            "challan_date": entry.get("vendor_challan_date") or receipt.get("receipt_date"),
            "invoice_no": _s(entry.get("vendor_invoice_number")) or _s(receipt.get("vendor_invoice_number")),
            "invoice_date": entry.get("vendor_invoice_date") or receipt.get("vendor_invoice_date"),
            "qty_returned": _f(receipt.get("quantity_received")), "qty_rejected": _f(entry.get("quantity_rejected")),
            "vehicle_no": _s(entry.get("vehicle_number")), "remarks": _s(entry.get("remarks")) or _s(receipt.get("remarks")),
        })
    for entry in entries:
        if entry.get("osp_receipt_id") and str(entry.get("osp_receipt_id")) in receipt_ids:
            continue
        if entry.get("osp_receipt_id"):
            # Receipt no longer visible (deleted): the FK cascade removes the entry; never count it here.
            continue
        rows.append({
            "source": "Vendor return", "receipt_id": None, "entry_id": entry.get("id"), "osp_job_id": entry.get("osp_job_id"),
            "receipt_number": None, "challan_no": _s(entry.get("vendor_challan_number")), "challan_date": entry.get("vendor_challan_date"),
            "invoice_no": _s(entry.get("vendor_invoice_number")), "invoice_date": entry.get("vendor_invoice_date"),
            "qty_returned": _f(entry.get("quantity_returned")), "qty_rejected": _f(entry.get("quantity_rejected")),
            "vehicle_no": _s(entry.get("vehicle_number")), "remarks": _s(entry.get("remarks")),
        })
    rows.sort(key=lambda r: (str(r.get("challan_date") or ""), str(r.get("challan_no") or "")))
    return rows


def balance_summary(dispatched: Any, returns: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    sent = _f(dispatched)
    returned = round(sum(_f(r.get("qty_returned")) for r in returns), 3)
    rejected = round(sum(_f(r.get("qty_rejected")) for r in returns), 3)
    return {"dispatched": sent, "returned": returned, "rejected": rejected, "balance": round(max(sent - returned - rejected, 0.0), 3)}


def vendor_safe(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Drop every customer / internal key from a challan payload (deep)."""
    from core.customer_privacy import strip_customer
    clean = strip_customer(dict(payload))
    for line in clean.get("lines") or []:
        for key in _INTERNAL_KEYS:
            line.pop(key, None)
    return clean


# ----------------------------------------------------------------------------------- service
class OSPChallanService:
    """Challan header / lines / vendor returns over the live OSP genealogy (RLS: OSP_TRANSACTIONS)."""

    def __init__(self, repo: Repository | None = None) -> None:
        self.repo = repo or Repository()

    # -- reads
    def _select(self, table: str, **kwargs: Any) -> list[dict]:
        try:
            return list(self.repo.select(table, **kwargs) or [])
        except Exception:
            return []

    def branches(self) -> list[dict]:
        return self._select("company_branches", eq={"status": "ACTIVE"}, order_by="branch_name", limit=200)

    def ship_to_parties(self) -> list[dict]:
        return self._select("parties", eq={"status": "ACTIVE"}, order_by="party_name", limit=3000)

    def challans(self) -> list[dict]:
        return self._select("osp_challans", order_by="challan_date", desc=True, limit=5000)

    def challan_for(self, document: Mapping[str, Any]) -> dict | None:
        if document.get("is_group") or document.get("material_out_id"):
            group = str(document.get("material_out_id") or document.get("id"))
            rows = self._select("osp_challans", eq={"material_out_id": group}, limit=1)
        else:
            rows = self._select("osp_challans", eq={"osp_job_id": str(document.get("id"))}, limit=1)
        return rows[0] if rows else None

    def lines(self, challan_id: str) -> list[dict]:
        return self._select("osp_challan_lines", eq={"challan_id": challan_id}, order_by="line_no", limit=500)

    def return_entries(self, challan_id: str) -> list[dict]:
        return self._select("osp_challan_returns", eq={"challan_id": challan_id}, order_by="created_at", limit=500)

    def receipts(self, job_ids: Sequence[str]) -> list[dict]:
        ids = [str(v) for v in job_ids if v]
        return self._select("osp_receipts", in_={"osp_job_id": ids}, order_by="receipt_date", limit=2000) if ids else []

    def returns_for(self, challan: Mapping[str, Any] | None, job_ids: Sequence[str]) -> list[dict]:
        entries = self.return_entries(str(challan["id"])) if challan and challan.get("id") else []
        return merge_returns(self.receipts(job_ids), entries)

    def next_number(self, branch_id: str | None = None) -> str:
        try:
            value = self.repo.rpc("qcms_next_osp_challan_number", {"p_branch_id": branch_id or None})
            if isinstance(value, str) and value.strip():
                return value.strip()
        except Exception:
            pass
        code = "D9"
        for branch in self.branches():
            if not branch_id or str(branch.get("id")) == str(branch_id):
                code = branch.get("plant_code") or branch.get("branch_code") or code
                break
        existing = [r.get("challan_number") for r in self.challans()]
        existing += [r.get("dispatch_challan") for r in self._select("osp_jobs", order_by="created_at", desc=True, limit=5000)]
        return next_number_from(existing, code)

    def default_prices(self, part_id: str | None, vendor_id: str | None, process_id: str | None = None) -> dict[str, Any]:
        """Last challan price for the same Part + OSP Vendor (+ Process), else the Part/Supplier price master."""
        result: dict[str, Any] = {"unit_price": 0.0, "gst_percent": DEFAULT_GST, "uom": DEFAULT_UOM}
        if not part_id:
            return result
        jobs = self._select("osp_jobs", eq={"part_id": part_id, **({"vendor_id": vendor_id} if vendor_id else {})}, order_by="created_at", desc=True, limit=200)
        if process_id:
            jobs = [j for j in jobs if str(j.get("process_id")) == str(process_id)] or jobs
        job_ids = [str(j["id"]) for j in jobs if j.get("id")]
        if job_ids:
            lines = self._select("osp_challan_lines", in_={"osp_job_id": job_ids[:150]}, order_by="updated_at", desc=True, limit=1)
            if lines:
                line = lines[0]
                return {"unit_price": _f(line.get("unit_price")), "gst_percent": _f(line.get("gst_percent")) if line.get("gst_percent") is not None else DEFAULT_GST, "uom": line.get("uom") or DEFAULT_UOM}
        if vendor_id:
            prices = self._select("part_supplier_price_history", eq={"part_id": part_id, "supplier_id": vendor_id}, order_by="start_date", desc=True, limit=5)
            active = [p for p in prices if str(p.get("status") or "ACTIVE").upper() == "ACTIVE"] or prices
            if active:
                result["unit_price"] = _f(active[0].get("price"))
                result["uom"] = _s(active[0].get("uom")).upper() or DEFAULT_UOM
        return result

    # -- writes
    @staticmethod
    def clean_header(header: Mapping[str, Any]) -> dict[str, Any]:
        number = _s(header.get("challan_number")).upper()
        if not number:
            raise ValueError("Enter the Challan Number (use the suggested series number or your own).")
        out: dict[str, Any] = {"challan_number": number}
        for key in ("challan_date", "branch_id", "vendor_id", "ship_to_party_id", "ship_to_text", "user_name", "ship_via", "incoterm",
                    "delivery_date", "payment_term", "reference_details", "old_po_details", "process_text", "vehicle_number",
                    "transporter_name", "eway_bill_number", "remarks", "status"):
            if key in header:
                value = header.get(key)
                if isinstance(value, date):
                    value = value.isoformat()
                out[key] = (_s(value) or None) if not isinstance(value, (int, float)) else value
        for key in ("shipping_amount", "other_amount"):
            if key in header:
                amount = _f(header.get(key))
                if amount < 0:
                    raise ValueError("Shipping and Other amounts cannot be negative.")
                out[key] = round(amount, 2)
        out.setdefault("status", "ISSUED")
        return out

    @staticmethod
    def clean_lines(lines: Sequence[Mapping[str, Any]]) -> list[dict]:
        result = []
        for position, line in enumerate(lines, start=1):
            if not line.get("osp_job_id"):
                raise ValueError("Every challan line must belong to an OSP heat line.")
            price, gst = _f(line.get("unit_price")), _f(line.get("gst_percent"))
            if price < 0:
                raise ValueError("Unit price cannot be negative.")
            if not 0 <= gst <= 100:
                raise ValueError("GST % must be between 0 and 100.")
            result.append({"osp_job_id": str(line["osp_job_id"]), "line_no": int(line.get("line_no") or position),
                           "item_code": _s(line.get("item_code")) or None, "item_description": _s(line.get("item_description")) or None,
                           "hsn_code": _s(line.get("hsn_code")) or None, "uom": _s(line.get("uom")).upper() or DEFAULT_UOM,
                           "unit_price": round(price, 4), "gst_percent": round(gst, 2), "batch_code": _s(line.get("batch_code")) or None,
                           "remarks": _s(line.get("remarks")) or None})
        return result

    def duplicate_number(self, number: str, challan_id: str | None, document: Mapping[str, Any] | None = None) -> bool:
        wanted = _s(number).upper()
        for row in self._select("osp_challans", eq={"challan_number": wanted}, limit=5):
            if str(row.get("id")) != str(challan_id or ""):
                return True
        return False

    def save(self, document: Mapping[str, Any], header: Mapping[str, Any], lines: Sequence[Mapping[str, Any]], challan_id: str | None = None) -> dict:
        payload = self.clean_header(header)
        clean_lines = self.clean_lines(lines)
        if challan_id:
            saved = self.repo.update("osp_challans", challan_id, payload)
        else:
            if document.get("is_group") or document.get("material_out_id"):
                payload["material_out_id"] = str(document.get("material_out_id") or document.get("id"))
            else:
                payload["osp_job_id"] = str(document.get("id"))
            saved = self.repo.insert("osp_challans", payload)
        cid = str((saved or {}).get("id") or challan_id or "")
        if not cid:
            raise RuntimeError("QCMS did not receive the saved challan ID from the database.")
        existing = {str(r.get("osp_job_id")): r for r in self.lines(cid)}
        rows = []
        for line in clean_lines:
            row = {"challan_id": cid, **line}
            if existing.get(line["osp_job_id"]):
                row["id"] = existing[line["osp_job_id"]]["id"]
            rows.append(row)
        for row in rows:
            line_id = row.pop("id", None)
            if line_id:
                self.repo.update("osp_challan_lines", str(line_id), row)
            else:
                self.repo.insert("osp_challan_lines", row)
        return {**dict(saved or {}), "id": cid}

    @staticmethod
    def clean_return(payload: Mapping[str, Any]) -> dict[str, Any]:
        returned, rejected = _f(payload.get("quantity_returned")), _f(payload.get("quantity_rejected"))
        if returned < 0 or rejected < 0:
            raise ValueError("Returned and rejected quantities cannot be negative.")
        linked = bool(payload.get("osp_receipt_id"))
        if not linked and returned <= 0 and rejected <= 0:
            raise ValueError("Enter the returned or rejected quantity.")
        if not linked and not (_s(payload.get("vendor_challan_number")) or _s(payload.get("vendor_invoice_number"))):
            raise ValueError("Enter the vendor challan number or the vendor invoice number.")
        out: dict[str, Any] = {"quantity_returned": 0.0 if linked else round(returned, 3), "quantity_rejected": round(rejected, 3)}
        for key in ("osp_job_id", "osp_receipt_id", "vendor_challan_number", "vendor_challan_date", "vendor_invoice_number",
                    "vendor_invoice_date", "vehicle_number", "remarks"):
            value = payload.get(key)
            if isinstance(value, date):
                value = value.isoformat()
            out[key] = _s(value) or None
        return out

    def save_return(self, challan_id: str, payload: Mapping[str, Any], entry_id: str | None = None) -> dict:
        row = self.clean_return(payload)
        if entry_id:
            return self.repo.update("osp_challan_returns", entry_id, row)
        return self.repo.insert("osp_challan_returns", {"challan_id": challan_id, **row})

    def link_receipt(self, job: Mapping[str, Any], receipt_id: str | None, *, vehicle_number: str = "", quantity_rejected: Any = 0, remarks: str = "") -> dict | None:
        """OSP Inward -> challan: one receipt = one vendor return (the receipt quantity is the returned quantity);
        this only stores the extra return details. Returns None when the Material Out has no challan yet
        (the receipt still appears on the challan once it is created, because returns merge by OSP job)."""
        if not receipt_id or not (_s(vehicle_number) or _f(quantity_rejected) or _s(remarks)):
            return None
        document = {"is_group": bool(job.get("material_out_id")), "material_out_id": job.get("material_out_id"), "id": job.get("material_out_id") or job.get("id")}
        challan = self.challan_for(document)
        if not challan:
            return None
        existing = self._select("osp_challan_returns", eq={"osp_receipt_id": str(receipt_id)}, limit=1)
        payload = {"osp_job_id": job.get("id"), "osp_receipt_id": str(receipt_id), "vehicle_number": vehicle_number, "quantity_rejected": quantity_rejected, "remarks": remarks}
        return self.save_return(str(challan["id"]), payload, str(existing[0]["id"]) if existing else None)

    def delete_return(self, entry_id: str) -> None:
        self.repo.delete("osp_challan_returns", entry_id)

    def mark_emailed(self, challan_id: str, recipients: str) -> None:
        try:
            from datetime import datetime, timezone
            self.repo.update("osp_challans", challan_id, {"emailed_at": datetime.now(timezone.utc).isoformat(), "emailed_to": recipients[:500]})
        except Exception:
            pass

    # -- print payload
    def document_rows(self, challan: Mapping[str, Any]) -> list[dict]:
        if challan.get("material_out_id"):
            ids = [str(r["id"]) for r in self._select("osp_jobs", eq={"material_out_id": str(challan["material_out_id"])}, limit=200)]
        else:
            ids = [str(challan.get("osp_job_id"))]
        rows = self._select("v_qsms_osp_register", in_={"id": ids}, limit=max(len(ids), 1) + 5) if ids else []
        raw = {str(r["id"]): r for r in self._select("osp_jobs", in_={"id": ids}, limit=max(len(ids), 1) + 5)} if ids else {}
        part_ids = sorted({str(r.get("part_id")) for r in rows if r.get("part_id")})
        parts = {str(p["id"]): p for p in self._select("parts", in_={"id": part_ids}, limit=len(part_ids) + 5)} if part_ids else {}
        out = []
        for row in rows:
            part = parts.get(str(row.get("part_id"))) or {}
            out.append({**row, "material_out_line_no": (raw.get(str(row["id"])) or {}).get("material_out_line_no") or 1,
                        "fsi_part_number": part.get("fsi_part_number"), "hsn_sac_code": part.get("hsn_sac_code"),
                        "part_name": part.get("part_name") or row.get("part_name")})
        return sorted(out, key=lambda r: (int(r.get("material_out_line_no") or 1), str(r.get("id"))))

    def print_payload_for(self, challan_id: str) -> dict:
        challan = self.repo.get("osp_challans", challan_id) or {}
        if not challan:
            raise ValueError("Challan not found.")
        rows = self.document_rows(challan)
        branch = self.repo.get("company_branches", str(challan.get("branch_id") or "")) if challan.get("branch_id") else None
        vendor = self.repo.get("parties", str(challan.get("vendor_id") or (rows[0].get("vendor_id") if rows else "") or "")) or {}
        ship = self.repo.get("parties", str(challan.get("ship_to_party_id") or "")) if challan.get("ship_to_party_id") else None
        returns = self.returns_for(challan, [str(r["id"]) for r in rows])
        return build_print_payload(challan, rows, self.lines(challan_id), returns, branch=branch, vendor=vendor, ship_to=ship)


def build_print_payload(challan: Mapping[str, Any], rows: Sequence[Mapping[str, Any]], lines: Sequence[Mapping[str, Any]],
                        returns: Sequence[Mapping[str, Any]], *, branch: Mapping[str, Any] | None = None,
                        vendor: Mapping[str, Any] | None = None, ship_to: Mapping[str, Any] | None = None) -> dict:
    """Vendor-facing challan payload (pure; FSI part number as ITEM #, no customer data)."""
    by_job = {str(l.get("osp_job_id")): l for l in lines}
    items = []
    for position, row in enumerate(rows, start=1):
        line = by_job.get(str(row.get("id"))) or {}
        items.append({
            "line_no": line.get("line_no") or row.get("material_out_line_no") or position,
            "item_code": _s(line.get("item_code")) or _s(row.get("fsi_part_number")) or "-",
            "item_description": _s(line.get("item_description")) or _s(row.get("part_name")),
            "hsn_code": _s(line.get("hsn_code")) or _s(row.get("hsn_sac_code")),
            "quantity": _f(row.get("quantity_dispatched")), "uom": _s(line.get("uom")) or DEFAULT_UOM,
            "unit_price": _f(line.get("unit_price")), "gst_percent": _f(line.get("gst_percent")) if line else DEFAULT_GST,
            "heat_number": _s(row.get("heat_number")), "batch_code": _s(line.get("batch_code")) or _s(row.get("osp_batch_code")),
            "process_name": _s(row.get("process_name")),
        })
    process = _s(challan.get("process_text")) or ", ".join(dict.fromkeys(i["process_name"].upper() for i in items if i["process_name"]))
    plant = dict(branch or {})
    plant_block = {
        "name": plant.get("branch_name"), "address1": plant.get("address_line1"),
        "address2": ", ".join(v for v in (_s(plant.get("address_line2")), _s(plant.get("address_line3"))) if v),
        "address3": " ".join(v for v in (_s(plant.get("city")), _s(plant.get("postal_code"))) if v),
        "gstin": plant.get("gstin"), "phone": plant.get("phone"), "email": plant.get("email"),
    } if plant else {}
    vendor = dict(vendor or {})
    ship = dict(ship_to or {}) or ({"party_name": challan.get("ship_to_text")} if _s(challan.get("ship_to_text")) else vendor)
    dispatched = sum(i["quantity"] for i in items)
    summary = balance_summary(dispatched, returns)
    payload = {
        "title": CHALLAN_TITLE, "challan_number": _s(challan.get("challan_number")), "challan_date": challan.get("challan_date"),
        "status": _s(challan.get("status")).upper() or "DRAFT", "saved": bool(challan.get("id")),
        "plant": plant_block, "vendor": {k: vendor.get(k) for k in ("party_name", "address", "city", "state", "country", "tax_identifier", "phone", "email")},
        "ship_to": {k: ship.get(k) for k in ("party_name", "address", "city", "state", "country", "tax_identifier", "phone", "email")},
        "user_name": challan.get("user_name"), "ship_via": challan.get("ship_via"), "incoterm": challan.get("incoterm"),
        "delivery_date": challan.get("delivery_date"), "payment_term": challan.get("payment_term"),
        "reference_details": challan.get("reference_details"), "old_po_details": challan.get("old_po_details"),
        "process_text": process, "vehicle_number": challan.get("vehicle_number"), "transporter_name": challan.get("transporter_name"),
        "eway_bill_number": challan.get("eway_bill_number"), "remarks": challan.get("remarks"),
        "lines": items, "totals": challan_totals(items, challan.get("shipping_amount"), challan.get("other_amount")),
        "returns": [dict(r) for r in returns], "summary": summary,
    }
    return vendor_safe(payload)


# ----------------------------------------------------------------------------------- PDF
# R37: the challan print lives in core/osp_challan_pdf.py (status watermark, Excel, job-id entry point).
def challan_pages(lines: Sequence[Any]) -> list[list[Any]]:
    from core.osp_challan_pdf import challan_pages as _pages
    return _pages(lines)


def osp_challan_pdf_bytes(payload: Mapping[str, Any]) -> bytes:
    """Challan PDF from a print payload (see core.osp_challan_pdf.osp_challan_pdf_bytes for a job id)."""
    from core.osp_challan_pdf import render_challan_pdf
    return render_challan_pdf(payload)


# ----------------------------------------------------------------------------------- e-mail
def challan_notifier(repo: Repository | None = None):
    """NotificationService whose generated PDF for related_table='osp_challans' is the vendor challan."""
    from core.notification_service import NotificationService

    class _ChallanNotifier(NotificationService):
        def _generated_report(self, related_table: str, related_id: str):  # type: ignore[override]
            if related_table == "osp_challans":
                try:
                    service = OSPChallanService(self.repo)
                    payload = service.print_payload_for(related_id)
                    return f"{payload.get('challan_number') or 'OSP_Challan'}.pdf", osp_challan_pdf_bytes(payload)
                except Exception:
                    return None
            return super()._generated_report(related_table, related_id)

    return _ChallanNotifier(repo)


def vendor_emails(vendor: Mapping[str, Any] | None) -> list[str]:
    raw = " ".join(str((vendor or {}).get(k) or "") for k in ("notification_emails", "email"))
    seen: list[str] = []
    for value in re.split(r"[\s,;]+", raw):
        value = value.strip()
        if "@" in value and value.casefold() not in {v.casefold() for v in seen}:
            seen.append(value)
    return seen


def email_body(payload: Mapping[str, Any]) -> tuple[str, str]:
    """Vendor-facing subject + body (FSI part number only; customer details are internal)."""
    data = vendor_safe(payload)
    items = data.get("lines") or []
    lines = [f"Please find attached Returnable Delivery Challan {data.get('challan_number')} dated {_date_text(data.get('challan_date'))}.", ""]
    for item in items:
        lines.append(f"- FSI Part {item.get('item_code')} · {item.get('item_description') or ''} · Heat {item.get('heat_number') or '-'} · Batch {item.get('batch_code') or '-'} · Qty {_qty(item.get('quantity'))} {item.get('uom') or ''}")
    lines += ["", f"Process to be done: {data.get('process_text') or '-'}",
              f"Expected delivery: {_date_text(data.get('delivery_date')) or '-'}",
              "", "Please mention this challan number on your return delivery challan / invoice.", "", "Regards,", "Four Star Industries · QCMS"]
    return f"Returnable Delivery Challan {data.get('challan_number')} · OSP job work", "\n".join(lines)
