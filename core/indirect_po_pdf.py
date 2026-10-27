"""QCMS R37 · Indirect Purchase Order and Indirect GRN prints.

Public contract (used by other modules, e.g. e-mail / reminders):
* ``indirect_po_pdf_bytes(po_id)``  → controlled Indirect PO PDF of a saved PO (status watermark).
* ``indirect_grn_pdf_bytes(grn_id)`` → Indirect Inward (GRN) PDF of a saved GRN.
* ``build_indirect_po_pdf(header, items)`` / ``build_indirect_grn_pdf(grn, items, po=...)`` render unsaved data (preview).

The Indirect PO uses the exact Direct Purchase Order look (core.purchase_order_reporting, Design B family driven by
the Print Layout Designer saved layout "PURCHASE_ORDER"): same logo position, title block with DATE / PO # boxes,
PLANT / VENDOR / REFERENCE / SHIP TO blocks, requisitioner strip, totals block, digital approver stamp and the
low-visibility approval watermark. Indirect POs carry no customer data, so nothing customer-related is printed.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Mapping, Sequence

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from core import purchase_order_reporting as por

TITLE = "INDIRECT PURCHASE ORDER"
GRN_TITLE = "INDIRECT GOODS RECEIPT NOTE"
DEFAULT_INDIRECT_INSTRUCTIONS = "\n".join([
    "1. Indirect PO number must be mentioned on your Invoice / Delivery Challan.",
    "2. Material / service must conform to the specification, make and quantity stated in this order.",
    "3. Warranty / guarantee certificates, manuals and test certificates (where applicable) to accompany the supply.",
    "4. Delivery to the Ship-To address within the delivery date; partial supply only with prior written consent.",
    "5. Payment as per the payment term after receipt and acceptance (GRN) of the material / service.",
])

_s = por._s
_n = por._n
_date = por._date
_money = por._money


def _qty(value: Any) -> str:
    return f"{_n(value):,.3f}".rstrip("0").rstrip(".") or "0"


def watermark_label(header: Mapping[str, Any]) -> str:
    approval = _s(header.get("approval_status")).upper()
    status = _s(header.get("status")).upper()
    if status == "CANCELLED" or approval == "CANCELLED":
        return "CANCELLED"
    if approval == "APPROVED":
        return "APPROVED"
    if approval == "REJECTED":
        return "REJECTED"
    if approval in {"DRAFT", "PREVIEW"} or status in {"DRAFT", "PREVIEW"}:
        return "DRAFT"
    return "PENDING APPROVAL"


def _logo(c: canvas.Canvas, left: float, h: float) -> None:
    logo_path = Path(__file__).resolve().parent.parent / "assets" / "fsi_logo.png"
    if logo_path.exists():
        try:
            c.drawImage(str(logo_path), left, h - 58, width=105, height=39, preserveAspectRatio=True, mask="auto")
        except Exception:
            pass


def _wrap_lines(text: Any, width: float, *, size: float, bold: bool = False, max_lines: int = 3) -> list[str]:
    font = "Helvetica-Bold" if bold else "Helvetica"
    lines: list[str] = []
    for paragraph in str(text or "").splitlines() or [""]:
        line = ""
        for word in _s(paragraph).split():
            test = f"{line} {word}".strip()
            if stringWidth(test, font, size) <= width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max(len(lines[-1]) - 3, 1)] + "..."
    return lines


# Line table: # | ITEM CODE / DESCRIPTION | HSN/SAC | QTY | UOM | RATE | DISC % | TAXABLE | GST % | GST AMT | AMOUNT
COLS = (("#", 18), ("ITEM CODE / DESCRIPTION", 160), ("HSN/SAC", 44), ("QTY", 40), ("UOM", 30), ("RATE", 48),
        ("DISC %", 30), ("TAXABLE", 54), ("GST %", 28), ("GST AMT", 47), ("AMOUNT", 40))
_NUMERIC = {3, 5, 6, 7, 8, 9, 10}


def _col_widths(total: float) -> list[float]:
    base = [w for _, w in COLS]
    scale = total / sum(base)
    return [w * scale for w in base]


def _table_head(c: canvas.Canvas, x: float, y_top: float, widths: Sequence[float]) -> float:
    for (title, _), width in zip(COLS, widths):
        por._bar(c, x, y_top, width, title, height=14)
        x += width
    return y_top - 14


def _row_lines(item: Mapping[str, Any], width: float) -> list[str]:
    head = " · ".join(v for v in (_s(item.get("item_code")), _s(item.get("item_name"))) if v)
    lines = _wrap_lines(head, width - 6, size=6.4, bold=True, max_lines=2)
    desc = _s(item.get("description"))
    if desc and desc.casefold() != _s(item.get("item_name")).casefold():
        lines += _wrap_lines(desc, width - 6, size=5.8, max_lines=3)
    if _s(item.get("required_date")):
        lines.append(f"Required by {_date(item.get('required_date'))}")
    return lines or ["-"]


def _row_height(item: Mapping[str, Any], widths: Sequence[float]) -> float:
    return max(16.0, 6.0 + 7.6 * len(_row_lines(item, widths[1])))


def _draw_row(c: canvas.Canvas, item: Mapping[str, Any], *, x: float, y_top: float, widths: Sequence[float]) -> float:
    height = _row_height(item, widths)
    bottom = y_top - height
    por._rules(c)
    c.setFillColor(white)
    c.rect(x, bottom, sum(widths), height, stroke=1, fill=1)
    values = [
        str(item.get("line_no") or ""), None, _s(item.get("hsn_sac")), _qty(item.get("quantity")), _s(item.get("uom")),
        _money(item.get("rate")), f"{_n(item.get('discount_percent')):g}", _money(item.get("taxable_amount")),
        f"{_n(item.get('gst_percent')):g}", _money(item.get("gst_amount")), _money(item.get("line_total")),
    ]
    cx = x
    for index, (width, value) in enumerate(zip(widths, values)):
        if index == 1:
            ly = y_top - 9
            for n, line in enumerate(_row_lines(item, width)):
                por._draw_text(c, cx + 3, ly, line, size=6.4 if n == 0 else 5.8, bold=n == 0, max_width=width - 6,
                               color=por.TEXT if n == 0 else HexColor("#374151"))
                ly -= 7.6
        elif index in _NUMERIC:
            c.setFillColor(por.TEXT); c.setFont("Helvetica", 6.3)
            text = str(value)
            while len(text) > 1 and stringWidth(text, "Helvetica", 6.3) > width - 4:
                text = text[:-1]
            c.drawRightString(cx + width - 2, y_top - 10, text)
        else:
            por._draw_text(c, cx + 3, y_top - 10, value, size=6.3, max_width=width - 5)
        cx += width
    return bottom


def _footer(c: canvas.Canvas, w: float, document: str = "purchase order") -> None:
    c.setFillColor(HexColor("#6B7280")); c.setFont("Helvetica", 6.0)
    c.drawCentredString(w / 2, 47, f"If you have any questions about this {document}, please contact")
    c.drawCentredString(w / 2, 36, por._ACTIVE.get("footer_text") or "FSI · connect@fourstarindustries.com")


def _continuation_header(c: canvas.Canvas, header: Mapping[str, Any], title: str, number_label: str = "IPO #") -> tuple[float, float]:
    w, h = A4
    _logo(c, 28, h)
    c.setFillColor(por._accent()); c.setFont("Helvetica-Bold", 15.5); c.drawRightString(w - 28, h - 33, title); por._rules(c)
    por._draw_text(c, w - 176, h - 51, f"{number_label} {_s(header.get('po_number') or header.get('grn_number'))}", size=7.2, bold=True)
    por._draw_text(c, w - 176, h - 64, f"DATE {_date(header.get('po_date') or header.get('grn_date'))}", size=7.2)
    return w, h


def _first_page_header(c: canvas.Canvas, header: Mapping[str, Any]) -> float:
    w, h = A4; left, right = 28, 28
    _logo(c, left, h)
    title = _s(por._ACTIVE.get("indirect_title")) or TITLE
    c.setFillColor(por._accent()); c.setFont("Helvetica-Bold", 20); c.drawRightString(w - right, h - 34, title); por._rules(c)
    por._draw_text(c, w - 150, h - 51, "DATE", size=7.4); c.rect(w - 104, h - 58, 76, 12, stroke=1, fill=0)
    por._draw_text(c, w - 100, h - 55, _date(header.get("po_date")), size=7.2)
    por._draw_text(c, w - 150, h - 65, "IPO #", size=7.4); c.rect(w - 104, h - 72, 76, 12, stroke=1, fill=0)
    por._draw_text(c, w - 100, h - 69, header.get("po_number"), size=6.8, max_width=72)

    col_w = 230; right_x = w - right - 184; y0 = h - 62
    plant = dict(header.get("plant_snapshot") or por.PLANT)
    if por._show("show_plant"):
        por._block(c, left, y0, col_w, "PLANT / COMPANY BRANCH", [plant.get("name") or plant.get("branch_name"), plant.get("address1") or plant.get("address"), plant.get("address2"), plant.get("address3"), plant.get("tax_identifier") or plant.get("gstin"), plant.get("phone"), plant.get("email")])
    if por._show("show_vendor"):
        por._block(c, left, h - 154, col_w, "VENDOR", por._party_lines(dict(header.get("vendor_snapshot") or {})), max_lines=7)
    if por._show("show_reference"):
        por._block(c, right_x, h - 86, 184, "REFERENCE DETAILS", [f"QUOTATION DATE: {_date(header.get('quotation_date'))}", _s(header.get("quotation_reference")), f"CURRENCY: {_s(header.get('currency') or 'INR')}"], max_lines=3)
    por._block(c, right_x, h - 136, 184, "DEPARTMENT / COST CENTRE", [" · ".join(v for v in (_s(header.get("department")), _s(header.get("cost_centre"))) if v) or "-"], max_lines=2)
    if por._show("show_ship_to"):
        por._block(c, right_x, h - 174, 184, "SHIP TO", por._party_lines(dict(header.get("ship_to_snapshot") or plant)), max_lines=7)

    y_strip = h - 284; widths = [78, 106, 82, 93, w - left - right - 359]
    titles = ["REQUISITIONER", "SHIP VIA", "INCOTERM", "DELIVERY DATE", "PAYMENT TERM"]
    values = [header.get("requisitioner"), header.get("ship_via"), header.get("incoterm"), _date(header.get("delivery_date")), header.get("payment_term")]
    x = left
    for sw, t, v in zip(widths, titles, values):
        por._bar(c, x, y_strip, sw, t, height=14); c.rect(x, y_strip - 34, sw, 20, stroke=1, fill=0)
        por._draw_text(c, x + 4, y_strip - 27, v, size=6.6, max_width=sw - 8); x += sw
    return y_strip - 45


SUMMARY_TOP = 300  # the totals / remarks / instructions area occupies y < SUMMARY_TOP on the last page


def _summary(c: canvas.Canvas, header: Mapping[str, Any], items: Sequence[Mapping[str, Any]]) -> None:
    w, h = A4; left = 28
    accent = por._accent()
    remark_color = HexColor(por._ACTIVE.get("remark") or "#9A3412")
    # Amount in words
    por._draw_text(c, left + 2, 286, "Amount in words:", size=7.2, bold=True, color=accent)
    por._rules(c); c.setFillColor(por._fill_or_white("remark_fill")); c.rect(left, 262, 386, 20, stroke=1, fill=1)
    por._draw_text(c, left + 4, 269, header.get("amount_in_words") or "-", size=6.8, bold=True, max_width=378)
    por._draw_text(c, left + 2, 250, "Remarks:", size=7.4, bold=True, color=accent)
    por._rules(c); c.setFillColor(por._fill_or_white("remark_fill")); c.rect(left, 226, 386, 20, stroke=1, fill=1)
    por._draw_text(c, left + 4, 233, header.get("remarks") or "-", size=7.0, bold=True, color=remark_color, max_width=378)
    if por._show("show_special_instructions"):
        por._bar(c, left, 220, 386, "TERMS & SPECIAL INSTRUCTIONS", height=14)
        text = "\n".join(v for v in (_s(header.get("terms")) and str(header.get("terms")), str(header.get("special_instructions") or DEFAULT_INDIRECT_INSTRUCTIONS)) if v)
        por._special_lines(c, left + 2, 196, text, 374, bottom=96)

    total_x = 417; y = 286
    gst_mode = _s(header.get("gst_mode")).upper() or "INTRA"
    rates = sorted({_n(i.get("gst_percent")) for i in items if _n(i.get("gst_percent")) > 0})
    rate_txt = f" {rates[0] / 2:g}%" if len(rates) == 1 and gst_mode == "INTRA" else (f" {rates[0]:g}%" if len(rates) == 1 else "")
    rows = [("PO LINES", str(len(items))), ("GROSS", _money(header.get("gross_amount"))), ("DISCOUNT", _money(header.get("discount_amount"))),
            ("TAXABLE", _money(header.get("subtotal")))]
    if gst_mode == "INTER":
        rows.append(("IGST" + rate_txt, _money(header.get("igst_amount"))))
    else:
        rows += [("CGST" + rate_txt, _money(header.get("cgst_amount"))), ("SGST" + rate_txt, _money(header.get("sgst_amount")))]
    rows += [("FREIGHT", _money(header.get("freight_amount"))), ("OTHER", _money(header.get("other_amount"))), ("ROUND OFF", _money(header.get("round_off")))]
    for label, value in rows:
        por._draw_text(c, total_x, y, label, size=6.8, bold=label == "PO LINES"); c.rect(total_x + 58, y - 5, 92, 13, stroke=1, fill=0)
        c.setFillColor(por.TEXT); c.setFont("Helvetica", 6.8); c.drawRightString(total_x + 147, y - 1, value); y -= 15
    c.setFillColor(accent); c.setFont("Helvetica-Bold", 8.2)
    c.drawString(total_x, y - 2, "TOTAL"); c.drawRightString(total_x + 147, y - 2, f"{_s(header.get('currency') or 'INR')} {_money(header.get('grand_total'))}")

    plant = dict(header.get("plant_snapshot") or por.PLANT)
    signatory = por._ACTIVE.get("company_name") or plant.get("name") or plant.get("branch_name") or por.PLANT["name"]
    if _s(header.get("approval_status")).upper() == "APPROVED" and por._show("show_approval_stamp"):
        por._draw_approver_stamp(c, header, page_width=w)
    else:
        por._draw_text(c, w - 143, 81, "Authorised Signatory", size=7.0, bold=True); por._draw_text(c, w - 174, 67, signatory, size=6.2)
    _footer(c, w)


def _indirect_pdf(header: Mapping[str, Any], items: list[dict], *, include_terms: bool) -> bytes:
    out = BytesIO(); c = canvas.Canvas(out, pagesize=A4)
    w, h = A4; left, right = 28, 28
    widths = _col_widths(w - left - right)
    y = _first_page_header(c, header)
    y = _table_head(c, left, y, widths)
    for index, item in enumerate(items):
        need = _row_height(item, widths)
        is_last = index == len(items) - 1
        floor = SUMMARY_TOP + 4 if is_last else 60
        if y - need < floor:
            c.setFillColor(HexColor("#6B7280")); c.setFont("Helvetica", 5.8)
            c.drawCentredString(w / 2, 27, "QCMS controlled Indirect Purchase Order · continued on next page")
            c.showPage()
            _, h2 = _continuation_header(c, header, f"{TITLE} · ITEMS CONTINUED")
            y = _table_head(c, left, h2 - 92, widths)
        y = _draw_row(c, item, x=left, y_top=y, widths=widths)
    if y < SUMMARY_TOP + 4:
        c.showPage(); _continuation_header(c, header, f"{TITLE} · TOTALS")
    _summary(c, header, items)
    c.showPage(); c.save()
    data = out.getvalue()
    if include_terms and por.PdfReader is not None and por.PdfWriter is not None:
        path = Path(__file__).resolve().parent.parent / "templates" / "FSI_STANDARD_PO_TERMS_2023.pdf"
        if path.exists():
            try:
                writer = por.PdfWriter()
                for page in por.PdfReader(BytesIO(data)).pages:
                    writer.add_page(page)
                for page in por._compact_terms_portrait(path, po_number=_s(header.get("po_number")), order_date=_s(header.get("po_date"))):
                    writer.add_page(page)
                buf = BytesIO(); writer.write(buf); data = buf.getvalue()
            except Exception:
                pass
    if por.PdfReader is not None and por.PdfWriter is not None:
        return por._watermark_pdf_bytes(data, watermark_label(header))
    return data


def _normalized(items: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> list[dict]:
    rows = [dict(items)] if isinstance(items, Mapping) else [dict(v) for v in items]
    for index, row in enumerate(rows, start=1):
        row.setdefault("line_no", index)
        if not row.get("line_no"):
            row["line_no"] = index
    return rows


def build_indirect_po_pdf(header: Mapping[str, Any], items: Mapping[str, Any] | Sequence[Mapping[str, Any]], *,
                          design: str | None = None, layout: Mapping[str, Any] | None = None, include_terms: bool = True) -> bytes:
    """Return the controlled Indirect Purchase Order PDF (Direct PO style; saved Print Layout Designer theme)."""
    rows = _normalized(items)
    if not rows:
        raise ValueError("At least one Indirect Purchase Order line is required.")
    if layout is None and not design:
        layout = por._saved_layout("PURCHASE_ORDER")
    options = header.get("print_options") if isinstance(header, Mapping) else None
    if isinstance(options, Mapping) and options:
        layout = {**dict(layout or {}), **{k: bool(v) for k, v in options.items() if str(k).startswith("show_")}}
    por.set_po_design(design, layout)
    try:
        return _indirect_pdf(header, rows, include_terms=include_terms)
    finally:
        por.set_po_design(None)


# ---------------------------------------------------------------------------------------------------------- GRN
GRN_COLS = (("#", 18), ("ITEM CODE / DESCRIPTION", 170), ("UOM", 32), ("ORDERED", 46), ("RECEIVED", 46), ("ACCEPTED", 46),
            ("REJECTED", 46), ("REJECT REASON", 76), ("LOCATION", 59))


def build_indirect_grn_pdf(grn: Mapping[str, Any], items: Sequence[Mapping[str, Any]], *, po: Mapping[str, Any] | None = None) -> bytes:
    """Indirect Inward (GRN) print in the same Design B theme."""
    rows = _normalized(items)
    por.set_po_design(None, por._saved_layout("PURCHASE_ORDER"))
    try:
        out = BytesIO(); c = canvas.Canvas(out, pagesize=A4)
        w, h = A4; left, right = 28, 28
        _logo(c, left, h)
        c.setFillColor(por._accent()); c.setFont("Helvetica-Bold", 17); c.drawRightString(w - right, h - 34, GRN_TITLE); por._rules(c)
        por._draw_text(c, w - 150, h - 51, "DATE", size=7.4); c.rect(w - 104, h - 58, 76, 12, stroke=1, fill=0)
        por._draw_text(c, w - 100, h - 55, _date(grn.get("grn_date")), size=7.2)
        por._draw_text(c, w - 150, h - 65, "GRN #", size=7.4); c.rect(w - 104, h - 72, 76, 12, stroke=1, fill=0)
        por._draw_text(c, w - 100, h - 69, grn.get("grn_number"), size=6.8, max_width=72)
        plant = dict((po or {}).get("plant_snapshot") or grn.get("plant_snapshot") or por.PLANT)
        por._block(c, left, h - 62, 260, "PLANT / COMPANY BRANCH", [plant.get("name") or plant.get("branch_name"), plant.get("address1") or plant.get("address"), plant.get("tax_identifier") or plant.get("gstin")], max_lines=4)
        vendor = dict((po or {}).get("vendor_snapshot") or {})
        supplier_lines = por._party_lines(vendor) if vendor else [grn.get("supplier_name") or "-"]
        por._block(c, left, h - 136, 260, "SUPPLIER", supplier_lines, max_lines=5)
        por._block(c, w - right - 260, h - 86, 260, "RECEIPT DETAILS", [
            f"GRN TYPE: {_s(grn.get('grn_type')).replace('_', ' ')} · PAYMENT: {_s(grn.get('payment_mode')).replace('_', ' ')}",
            f"INDIRECT PO: {_s((po or {}).get('po_number')) or '-'}  {_date((po or {}).get('po_date'))}",
            f"INVOICE: {_s(grn.get('supplier_invoice_no')) or '-'}  {_date(grn.get('supplier_invoice_date'))}",
            f"CHALLAN: {_s(grn.get('challan_no')) or '-'}  {_date(grn.get('challan_date'))}",
            f"GATE ENTRY: {_s(grn.get('gate_entry_no')) or '-'}  {_date(grn.get('gate_entry_date'))} · VEHICLE: {_s(grn.get('vehicle_no')) or '-'}",
            f"DEPARTMENT: {_s(grn.get('department')) or '-'} · COST CENTRE: {_s(grn.get('cost_centre')) or '-'}",
        ], max_lines=6)
        y = h - 232
        base = [wd for _, wd in GRN_COLS]; scale = (w - left - right) / sum(base); widths = [wd * scale for wd in base]
        x = left
        for (title, _), width in zip(GRN_COLS, widths):
            por._bar(c, x, y, width, title, height=14); x += width
        y -= 14
        for item in rows:
            lines = _wrap_lines(" · ".join(v for v in (_s(item.get("item_code")), _s(item.get("item_name") or item.get("description"))) if v), widths[1] - 6, size=6.3, max_lines=2)
            reason = _wrap_lines(item.get("rejection_reason"), widths[7] - 6, size=5.8, max_lines=2)
            height = max(16.0, 6 + 7.6 * max(len(lines), len(reason), 1))
            if y - height < 150:
                c.showPage(); _continuation_header(c, grn, f"{GRN_TITLE} · CONTINUED", "GRN #"); y = h - 92
            por._rules(c); c.setFillColor(white); c.rect(left, y - height, sum(widths), height, stroke=1, fill=1)
            values = [str(item.get("line_no")), None, _s(item.get("uom")), _qty(item.get("ordered_qty")) if item.get("ordered_qty") not in (None, "") else "-",
                      _qty(item.get("received_qty")), _qty(item.get("accepted_qty")), _qty(item.get("rejected_qty")), None,
                      _s(item.get("storage_location") or grn.get("storage_location"))]
            cx = left
            for index, (width, value) in enumerate(zip(widths, values)):
                if index == 1:
                    for n, line in enumerate(lines):
                        por._draw_text(c, cx + 3, y - 9 - n * 7.6, line, size=6.3, bold=n == 0, max_width=width - 6)
                elif index == 7:
                    for n, line in enumerate(reason):
                        por._draw_text(c, cx + 3, y - 9 - n * 7.6, line, size=5.8, max_width=width - 6)
                elif index in {3, 4, 5, 6}:
                    c.setFillColor(por.TEXT); c.setFont("Helvetica", 6.4); c.drawRightString(cx + width - 3, y - 10, str(value))
                else:
                    por._draw_text(c, cx + 3, y - 10, value, size=6.3, max_width=width - 5)
                cx += width
            y -= height
        por._draw_text(c, left + 2, 132, "Remarks:", size=7.2, bold=True, color=por._accent())
        por._draw_text(c, left + 50, 132, grn.get("remarks") or "-", size=7.0, max_width=w - left - right - 60)
        sig_w = (w - left - right) / 4
        for index, label in enumerate(("RECEIVED BY", "STORES", "QUALITY / USER DEPT.", "APPROVED BY")):
            x = left + index * sig_w
            por._bar(c, x, 118, sig_w - 4, label, height=13)
            c.rect(x, 78, sig_w - 4, 27, stroke=1, fill=0)
            value = ""
            if index == 0:
                value = _s(grn.get("received_by_name"))
            elif index == 3:
                value = _s(grn.get("approver_name"))
            por._draw_text(c, x + 4, 88, value, size=6.6, max_width=sig_w - 12)
        _footer(c, w, "goods receipt note")
        c.showPage(); c.save()
        data = out.getvalue()
        status = _s(grn.get("status")).upper()
        label = {"POSTED": "POSTED", "PENDING_APPROVAL": "PENDING APPROVAL", "REJECTED": "REJECTED", "CANCELLED": "CANCELLED"}.get(status, "DRAFT")
        if por.PdfReader is not None and por.PdfWriter is not None:
            return por._watermark_pdf_bytes(data, label)
        return data
    finally:
        por.set_po_design(None)


# ---------------------------------------------------------------------------------------------------------- by id
def indirect_po_pdf_bytes(po_id: Any, repo: Any | None = None, *, include_terms: bool = True) -> bytes:
    """Controlled PDF of a saved Indirect Purchase Order (current approval watermark). Raises ValueError when not found."""
    from core.indirect_purchase_service import IndirectPurchaseService
    service = IndirectPurchaseService(repo)
    header = service.purchase_order(po_id)
    if not header:
        raise ValueError("Indirect Purchase Order not found.")
    return build_indirect_po_pdf(header, service.po_items(str(header.get("id") or po_id)), include_terms=include_terms)


def indirect_grn_pdf_bytes(grn_id: Any, repo: Any | None = None) -> bytes:
    """PDF of a saved Indirect Inward (GRN). Raises ValueError when not found."""
    from core.indirect_purchase_service import IndirectPurchaseService, employee_name
    service = IndirectPurchaseService(repo)
    grn = service.grn(grn_id)
    if not grn:
        raise ValueError("Indirect GRN not found.")
    po = service.purchase_order(grn.get("purchase_order_id")) if grn.get("purchase_order_id") else None
    approver = service.employee(grn.get("approver_employee_id")) if grn.get("approver_employee_id") else {}
    return build_indirect_grn_pdf({**grn, "approver_name": employee_name(approver) if approver else ""}, service.grn_items(str(grn.get("id") or grn_id)), po=po or None)


__all__ = ["TITLE", "GRN_TITLE", "DEFAULT_INDIRECT_INSTRUCTIONS", "watermark_label", "build_indirect_po_pdf", "build_indirect_grn_pdf",
           "indirect_po_pdf_bytes", "indirect_grn_pdf_bytes"]
