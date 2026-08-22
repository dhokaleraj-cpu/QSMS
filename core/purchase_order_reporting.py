from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Mapping, Sequence

from reportlab.lib.colors import Color, HexColor, black, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

try:
    from pypdf import PdfReader, PdfWriter
except Exception:  # pragma: no cover - surfaced at runtime with a clear message
    PdfReader = PdfWriter = None  # type: ignore[assignment]


NAVY = HexColor("#0B2E63")
LIGHT_BLUE = HexColor("#D7E1F1")
LIGHT_GREY = HexColor("#E4E5E7")
YELLOW = HexColor("#FFF700")
TEXT = HexColor("#202124")

PLANT = {
    "name": "Four Star Industries Private Limited D9",
    "address1": "Plot No.D9, Chakan MIDC PH II",
    "address2": "Bhamboli, Khed",
    "address3": "Pune 410501",
    "tax_identifier": "27AAGCF3769A1ZP",
    "phone": "022 40104412",
    "email": "orders@fourstarindustries.com",
}

DEFAULT_SPECIAL_INSTRUCTIONS = "\n".join(
    [
        "1. PO number should be mentioned on your Invoice.",
        "2. Material must be packed properly to avoid water damage and free from dent, damages & rust.",
        "3. All QC related reports & TCs to be attached with the Invoices.",
        "4. All reports to be sent to quality@fourstarindustries.com",
        "5. Refer STANDARD PURCHASE ORDER TERMS AND CONDITIONS no FSI/703/F04.",
    ]
)


def _s(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _n(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _date(value: Any) -> str:
    text = _s(value)
    if not text:
        return ""
    try:
        y, m, d = text[:10].split("-")
        return f"{d}-{m}-{y}"
    except Exception:
        return text[:10]


def _money(value: Any) -> str:
    return f"{_n(value):,.2f}"


def _draw_text(c: canvas.Canvas, x: float, y: float, text: Any, *, size: float = 8.0, bold: bool = False, color=TEXT, max_width: float | None = None) -> None:
    value = _s(text)
    if max_width and value:
        font = "Helvetica-Bold" if bold else "Helvetica"
        if stringWidth(value, font, size) > max_width:
            while len(value) > 3 and stringWidth(value + "...", font, size) > max_width:
                value = value[:-1]
            value = value.rstrip() + "..."
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x, y, value)


def _wrap(c: canvas.Canvas, x: float, y: float, text: Any, width: float, *, size: float = 7.4, leading: float = 9.2, bold: bool = False, max_lines: int = 8) -> float:
    font = "Helvetica-Bold" if bold else "Helvetica"
    words = _s(text).split()
    line = ""
    lines: list[str] = []
    for word in words:
        test = f"{line} {word}".strip()
        if stringWidth(test, font, size) <= width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
            if len(lines) >= max_lines:
                break
    if line and len(lines) < max_lines:
        lines.append(line)
    for index, value in enumerate(lines):
        c.setFillColor(TEXT)
        c.setFont(font, size)
        c.drawString(x, y - index * leading, value)
    return y - len(lines) * leading


def _bar(c: canvas.Canvas, x: float, y: float, width: float, title: str, *, height: float = 13) -> None:
    c.setFillColor(NAVY)
    c.rect(x, y - height, width, height, stroke=0, fill=1)
    _draw_text(c, x + 4, y - height + 3.1, title, size=7.2, bold=True, color=white)


def _party_lines(snapshot: Mapping[str, Any]) -> list[str]:
    return [
        _s(snapshot.get("party_name") or snapshot.get("name")),
        _s(snapshot.get("address")),
        ", ".join(v for v in (_s(snapshot.get("city")), _s(snapshot.get("state")), _s(snapshot.get("country"))) if v),
        _s(snapshot.get("tax_identifier")),
        _s(snapshot.get("phone")),
        _s(snapshot.get("email")),
    ]


def _block(c: canvas.Canvas, x: float, y_top: float, width: float, title: str, lines: list[str], *, max_lines: int = 7) -> float:
    _bar(c, x, y_top, width, title)
    y = y_top - 24
    for line in [v for v in lines if _s(v)][:max_lines]:
        y = _wrap(c, x + 4, y, line, width - 8, size=7.0, leading=8.2, max_lines=2)
    return y


def _first_page_bytes(header: Mapping[str, Any], items: Sequence[Mapping[str, Any]]) -> bytes:
    out = BytesIO()
    c = canvas.Canvas(out, pagesize=A4)
    w, h = A4
    left, right = 28, 28
    logo_path = Path(__file__).resolve().parent.parent / "assets" / "fsi_logo.png"
    if logo_path.exists():
        try:
            c.drawImage(str(logo_path), left, h - 58, width=105, height=39, preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

    c.setFillColor(black); c.setFont("Helvetica-Bold", 24); c.drawRightString(w - right, h - 34, "PURCHASE ORDER")
    _draw_text(c, w - 137, h - 51, "DATE", size=7.4); c.rect(w - 91, h - 58, 62, 12, stroke=1, fill=0); _draw_text(c, w - 86, h - 55, _date(header.get("order_date")), size=7.2)
    _draw_text(c, w - 137, h - 65, "PO #", size=7.4); c.rect(w - 91, h - 72, 62, 12, stroke=1, fill=0); _draw_text(c, w - 86, h - 69, header.get("po_number"), size=7.2)

    col_w = 230; left_x = left; right_x = w - right - 184; y0 = h - 62
    _block(c, left_x, y0, col_w, "PLANT", [PLANT["name"], PLANT["address1"], PLANT["address2"], PLANT["address3"], PLANT["tax_identifier"], PLANT["phone"], PLANT["email"]])
    vendor = dict(header.get("vendor_snapshot") or {}); _block(c, left_x, h - 154, col_w, "VENDOR", _party_lines(vendor), max_lines=7)
    _block(c, right_x, h - 86, 184, "REFERENCE DETAILS", [f"QUOTATION DATE: {_date(header.get('quotation_date'))}", _s(header.get("quotation_reference"))], max_lines=3)
    _block(c, right_x, h - 136, 184, "OLD PO DETAILS", [_s(header.get("old_po_reference"))], max_lines=2)
    ship = dict(header.get("ship_to_snapshot") or PLANT)
    _block(c, right_x, h - 174, 184, "SHIP TO", [ship.get("name") or PLANT["name"], ship.get("address1") or PLANT["address1"], ship.get("address2") or PLANT["address2"], ship.get("address3") or PLANT["address3"], ship.get("tax_identifier") or PLANT["tax_identifier"], ship.get("phone") or PLANT["phone"], ship.get("email") or PLANT["email"]], max_lines=7)

    y_strip = h - 284; strip_widths = [78, 106, 82, 93, w - left - right - 359]
    strip_titles = ["REQUISITIONER", "SHIP VIA", "INCOTERM", "DELIVERY DATE", "PAYMENT TERM"]
    strip_values = [header.get("requisitioner"), header.get("ship_via"), header.get("incoterm"), _date(header.get("delivery_date")), header.get("payment_term")]
    x = left
    for sw, title, value in zip(strip_widths, strip_titles, strip_values):
        _bar(c, x, y_strip, sw, title, height=14); c.rect(x, y_strip - 34, sw, 20, stroke=1, fill=0); _draw_text(c, x + 4, y_strip - 27, value, size=6.6, max_width=sw - 8); x += sw

    # Multi-line item grid. One supplier PO may consolidate several Customer Orders / Schedules.
    y_item_top = y_strip - 45; widths = [218, 44, 62, 42, 40, 70, 63]; titles = ["ITEM #", "QTY", "UNIT PRICE", "UNIT", "GST%", "GST AMOUNT", "TOTAL"]
    x = left
    for sw, title in zip(widths, titles): _bar(c, x, y_item_top, sw, title, height=14); x += sw
    body_top = y_item_top - 14; body_bottom = 245; c.rect(left, body_bottom, w - left - right, body_top - body_bottom, stroke=1, fill=0)
    row_h = 24; display_items = list(items)[:6]
    y = body_top
    for row_index, item in enumerate(display_items):
        next_y = y - row_h
        if row_index: c.line(left, y, w-right, y)
        x = left
        item_display = " ".join(v for v in (_s(item.get("item_no")), _s(item.get("item_description"))) if v)
        vals = [item_display, f"{_n(item.get('quantity')):,.2f}".rstrip("0").rstrip("."), _money(item.get("unit_price")), item.get("uom"), f"{_n(item.get('gst_percent')):g}%", _money(item.get("gst_amount")), _money(item.get("line_total"))]
        for idx, (sw, value) in enumerate(zip(widths, vals)):
            if idx: c.line(x, next_y, x, y)
            if idx == 0: _wrap(c, x+5, y-10, value, sw-10, size=6.6, leading=7.4, max_lines=2)
            else: _draw_text(c, x+4, y-15, value, size=6.5, max_width=sw-8)
            x += sw
        y = next_y

    # Supplier-specific technical data comes from Part Master Raw Material Details.
    tech_y = y - 10
    max_tech_lines = max(int((tech_y - body_bottom - 6) // 9), 0); used_lines = 0
    for item in display_items:
        if used_lines >= max_tech_lines: break
        technical = item.get("technical_data_snapshot") or []
        if not isinstance(technical, list) or not technical: continue
        _draw_text(c, left + 8, tech_y, f"FSI {item.get('item_no') or '-'} · TECHNICAL DATA", size=6.6, bold=True); tech_y -= 9; used_lines += 1
        pairs=[]
        for row in technical:
            if not isinstance(row, Mapping): continue
            heading=_s(row.get("heading")); value=_s(row.get("value"))
            if heading and value: pairs.append((heading,value))
        for i in range(0,len(pairs),2):
            if used_lines >= max_tech_lines: break
            left_pair=pairs[i]; right_pair=pairs[i+1] if i+1<len(pairs) else ("","")
            _draw_text(c,left+14,tech_y,left_pair[0],size=6.1,bold=True,max_width=72); _draw_text(c,left+88,tech_y,left_pair[1],size=6.1,max_width=122)
            if right_pair[0]: _draw_text(c,left+225,tech_y,right_pair[0],size=6.1,bold=True,max_width=72); _draw_text(c,left+299,tech_y,right_pair[1],size=6.1,max_width=144)
            tech_y -= 9; used_lines += 1

    _draw_text(c, left + 2, 236, "Remarks:", size=7.6, bold=True); c.setFillColor(YELLOW); c.rect(left, 211, 386, 21, stroke=0, fill=1); _draw_text(c, left + 4, 220, header.get("remarks") or "PART WILL BE SUPPLIED AS PER DRAWING.", size=7.0, bold=True, max_width=378)
    c.setFillColor(LIGHT_GREY); c.rect(left, 192, 386, 14, stroke=0, fill=1); _draw_text(c, left + 3, 196, "Comments or Special Instructions", size=6.8, bold=True); _wrap(c, left + 2, 181, header.get("special_instructions") or DEFAULT_SPECIAL_INSTRUCTIONS, 374, size=6.2, leading=11.3, max_lines=7)

    total_x=417; ytot=205
    for label,val in [("SUBTOTAL",header.get("subtotal")),("CGST 9%",header.get("cgst_amount")),("SGST 9%",header.get("sgst_amount")),("IGST",header.get("igst_amount")),("OTHER",header.get("other_amount"))]:
        _draw_text(c,total_x,ytot,label,size=6.9); c.rect(total_x+55,ytot-5,95,13,stroke=1,fill=0); _draw_text(c,total_x+61,ytot-1,_money(val),size=6.8); ytot-=16
    c.setFont("Helvetica-Bold",8.0); c.drawString(total_x,ytot,"TOTAL"); c.drawString(total_x+61,ytot,f"INR {_money(header.get('grand_total'))}")
    _draw_text(c,w-143,81,"Authorised Signatory",size=7.0,bold=True); _draw_text(c,w-174,67,PLANT["name"],size=6.2); _draw_text(c,left+318,47,"If you have any questions about this purchase order, please contact",size=6.0); _draw_text(c,left+375,36,"FSI, connect@fourstarindustries.com",size=6.0)
    c.showPage(); c.save(); return out.getvalue()

def _terms_with_dynamic_header(terms_path: Path, *, po_number: str, order_date: str) -> list[Any]:
    if PdfReader is None:
        raise RuntimeError("pypdf is required for the controlled Purchase Order terms pages.")
    reader = PdfReader(str(terms_path))
    result = []
    for source_page in reader.pages:
        overlay = BytesIO()
        w = float(source_page.mediabox.width)
        h = float(source_page.mediabox.height)
        c = canvas.Canvas(overlay, pagesize=(w, h))
        # Controlled terms pages are US Letter. Cover the original DATE / PO area
        # from the reference document, then stamp this saved QCMS PO identity.
        c.setFillColor(white)
        # Original FSI/703/F04 Letter template places DATE/PO at x≈492..580,
        # 65..84 points from the top. Replace only that small cell area.
        c.rect(487, h - 89, 111, 31, stroke=0, fill=1)
        _draw_text(c, 492, h - 73, "DATE", size=7.4)
        c.rect(532, h - 75, 52, 12, stroke=1, fill=0)
        _draw_text(c, 536, h - 72, _date(order_date), size=6.8)
        _draw_text(c, 495, h - 84, "PO #", size=7.4)
        c.rect(532, h - 86, 52, 12, stroke=1, fill=0)
        _draw_text(c, 536, h - 83, po_number, size=6.8)
        c.save(); overlay.seek(0)
        overlay_page = PdfReader(overlay).pages[0]
        page = source_page
        page.merge_page(overlay_page)
        result.append(page)
    return result


def purchase_order_pdf_bytes(header: Mapping[str, Any], items: Mapping[str, Any] | Sequence[Mapping[str, Any]], *, terms_path: str | Path | None = None) -> bytes:
    """Return the controlled FSI Purchase Order PDF.

    Page 1 supports multiple supplier-facing FSI Part Number lines under one controlled
    PO and prints supplier-specific technical heading/value snapshots from Part Master.
    The original/customer part number remains an internal QCMS field and is never printed.
    Price history stays internal to QCMS and is not exposed on the supplier document.
    Pages 2-13 remain the controlled FSI/703/F04 terms template.
    """
    if PdfReader is None or PdfWriter is None:
        raise RuntimeError("pypdf is not installed. Add pypdf to requirements.txt.")
    normalized = [dict(items)] if isinstance(items, Mapping) else [dict(v) for v in items]
    if not normalized:
        raise ValueError("At least one Purchase Order line is required.")
    first = _first_page_bytes(header, normalized)
    writer = PdfWriter(); writer.add_page(PdfReader(BytesIO(first)).pages[0])
    path = Path(terms_path) if terms_path else Path(__file__).resolve().parent.parent / "templates" / "FSI_STANDARD_PO_TERMS_2023.pdf"
    if path.exists():
        for page in _terms_with_dynamic_header(path, po_number=_s(header.get("po_number")), order_date=_s(header.get("order_date"))): writer.add_page(page)
    out = BytesIO(); writer.write(out); return out.getvalue()

