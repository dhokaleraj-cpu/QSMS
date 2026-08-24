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


def _price_history_rows(item: Mapping[str, Any], *, limit: int = 4) -> list[Mapping[str, Any]]:
    raw = item.get("price_history_snapshot") or []
    if not isinstance(raw, list):
        return []
    rows = [row for row in raw if isinstance(row, Mapping) and _s(row.get("start_date"))]
    rows.sort(key=lambda row: _s(row.get("start_date")), reverse=True)
    # Show the most recent controlled periods, but print them oldest-to-newest for readability.
    return list(reversed(rows[:limit]))


def _draw_price_history(c: canvas.Canvas, x: float, y_top: float, width: float, item: Mapping[str, Any], *, max_rows: int = 4) -> float:
    """Draw the supplier/FSI Part Price Revision History under one PO item."""
    rows = _price_history_rows(item, limit=max_rows)
    _draw_text(c, x, y_top, "PRICE REVISION HISTORY", size=5.8, bold=True, color=NAVY, max_width=width)
    header_y = y_top - 12
    col_widths = [74, 74, 72, max(width - 220, 80)]
    titles = ["START DATE", "END DATE", "PRICE", "REMARK"]
    cx = x
    c.setFillColor(HexColor("#D7E1F1"))
    c.rect(x, header_y - 9, width, 11, stroke=1, fill=1)
    for idx, (cw, title) in enumerate(zip(col_widths, titles)):
        if idx:
            c.line(cx, header_y - 9, cx, header_y + 2)
        _draw_text(c, cx + 2, header_y - 5, title, size=4.8, bold=True, color=NAVY, max_width=cw - 4)
        cx += cw
    if not rows:
        c.setFillColor(white)
        c.rect(x, header_y - 21, width, 12, stroke=1, fill=1)
        _draw_text(c, x + 3, header_y - 17, "No controlled price revision history recorded", size=5.0, color=HexColor("#6B7280"), max_width=width - 6)
        return header_y - 21
    y = header_y - 9
    for row in rows:
        next_y = y - 12
        c.setFillColor(white)
        c.rect(x, next_y, width, 12, stroke=1, fill=1)
        values = [
            _date(row.get("start_date")),
            _date(row.get("end_date")) or "Current",
            f"{_s(row.get('currency') or 'INR')} {_money(row.get('price'))}/{_s(row.get('uom') or '')}".rstrip("/"),
            _s(row.get("remarks")),
        ]
        cx = x
        for idx, (cw, value) in enumerate(zip(col_widths, values)):
            if idx:
                c.line(cx, next_y, cx, y)
            _draw_text(c, cx + 2, next_y + 3.5, value, size=4.9, max_width=cw - 4)
            cx += cw
        y = next_y
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

    # Multi-line item grid. Each supplier-facing FSI Part item is immediately followed
    # by its own compact Raw Material / Forging Parameters + FSI Technical Data block.
    # This keeps technical data item-wise instead of collecting it below unrelated lines.
    y_item_top = y_strip - 45; widths = [218, 44, 62, 42, 40, 70, 63]; titles = ["ITEM #", "QTY", "UNIT PRICE", "UNIT", "GST%", "GST AMOUNT", "TOTAL"]
    x = left
    for sw, title in zip(widths, titles): _bar(c, x, y_item_top, sw, title, height=14); x += sw
    body_top = y_item_top - 14; body_bottom = 245; c.rect(left, body_bottom, w - left - right, body_top - body_bottom, stroke=1, fill=0)
    # v4.14.1 reserves a larger item pocket for HSN/SAC, technical data and Price Revision History.
    display_items = list(items)[:2]
    y = body_top
    available_height = body_top - body_bottom
    block_height = max(min(available_height / max(len(display_items), 1), 126), 110)

    def compact_technical_pairs(item: Mapping[str, Any]) -> list[tuple[str, str]]:
        raw = item.get("technical_data_snapshot") or []
        if not isinstance(raw, list):
            return []
        pairs: list[tuple[str, str]] = []
        # Supplier PO priority: raw-material / forging parameters first, then custom FSI data.
        priority = {name.casefold(): idx for idx, name in enumerate((
            "Raw Material Section", "Forge wt", "Gross wt", "Input wt", "Section Size", "Forging Route",
        ))}
        prepared=[]
        for idx,row in enumerate(raw):
            if not isinstance(row, Mapping): continue
            heading=_s(row.get("heading")); value=_s(row.get("value"))
            if heading and value:
                prepared.append((priority.get(heading.casefold(), 100 + idx), heading, value))
        prepared.sort(key=lambda v: v[0])
        for _,heading,value in prepared[:6]:
            pairs.append((heading,value))
        return pairs

    for row_index, item in enumerate(display_items):
        next_y = max(y - block_height, body_bottom)
        if row_index: c.line(left, y, w-right, y)
        item_row_bottom = y - 29
        c.setFillColor(white); c.rect(left, item_row_bottom, w-left-right, 29, stroke=0, fill=1)
        x = left
        item_display = " ".join(v for v in (_s(item.get("item_no")), _s(item.get("item_description"))) if v)
        vals = [item_display, f"{_n(item.get('quantity')):,.2f}".rstrip("0").rstrip("."), _money(item.get("unit_price")), item.get("uom"), f"{_n(item.get('gst_percent')):g}%", _money(item.get("gst_amount")), _money(item.get("line_total"))]
        for idx, (sw, value) in enumerate(zip(widths, vals)):
            # No vertical grid lines in the PO item body. Whitespace/alignment separates
            # commercial columns while horizontal item separators keep the layout clean.
            if idx == 0:
                _wrap(c, x+5, y-10, value, sw-10, size=6.5, leading=7.2, max_lines=2)
                hsn=_s(item.get("hsn_sac_code"))
                if hsn: _draw_text(c, x+5, y-25, f"HSN / SAC: {hsn}", size=5.6, bold=True, color=HexColor("#4B5563"), max_width=sw-10)
            else:
                _draw_text(c, x+4, y-17, value, size=6.4, max_width=sw-8)
            x += sw

        # Item-wise technical pocket directly under the item line.
        tech_top = item_row_bottom
        c.setStrokeColor(HexColor("#D1D5DB")); c.line(left, tech_top, w-right, tech_top)
        c.setFillColor(HexColor("#F3F4F6")); c.rect(left, next_y, w-left-right, max(tech_top-next_y, 0), stroke=0, fill=1)
        pairs = compact_technical_pairs(item)
        label_y = tech_top - 8
        _draw_text(c, left+5, label_y, "RAW MATERIAL / FORGING PARAMETERS & FSI TECHNICAL DATA", size=5.7, bold=True, color=NAVY, max_width=260)
        if pairs:
            pair_width = (w-left-right-10) / 3.0
            row_y = label_y - 9
            for pair_idx,(heading,value) in enumerate(pairs[:6]):
                row_no = pair_idx // 3; col_no = pair_idx % 3
                px = left + 5 + col_no * pair_width
                py = row_y - row_no * 9
                _draw_text(c, px, py, f"{heading}:", size=5.4, bold=True, max_width=pair_width*0.44)
                _draw_text(c, px + pair_width*0.44, py, value, size=5.4, max_width=pair_width*0.54)
        else:
            _draw_text(c, left+229, label_y, "No controlled supplier technical data configured", size=5.4, color=HexColor("#6B7280"), max_width=260)
        _draw_price_history(c, left+5, tech_top-39, w-left-right-10, item, max_rows=3)
        y = next_y

    _draw_text(c, left + 2, 236, "Remarks:", size=7.6, bold=True); c.setFillColor(YELLOW); c.rect(left, 211, 386, 21, stroke=0, fill=1); _draw_text(c, left + 4, 220, header.get("remarks") or "PART WILL BE SUPPLIED AS PER DRAWING.", size=7.0, bold=True, max_width=378)
    c.setFillColor(LIGHT_GREY); c.rect(left, 192, 386, 14, stroke=0, fill=1); _draw_text(c, left + 3, 196, "Comments or Special Instructions", size=6.8, bold=True); _wrap(c, left + 2, 181, header.get("special_instructions") or DEFAULT_SPECIAL_INSTRUCTIONS, 374, size=6.2, leading=11.3, max_lines=7)

    total_x=417; ytot=205
    for label,val in [("SUBTOTAL",header.get("subtotal")),("CGST 9%",header.get("cgst_amount")),("SGST 9%",header.get("sgst_amount")),("IGST",header.get("igst_amount")),("OTHER",header.get("other_amount"))]:
        _draw_text(c,total_x,ytot,label,size=6.9); c.rect(total_x+55,ytot-5,95,13,stroke=1,fill=0); _draw_text(c,total_x+61,ytot-1,_money(val),size=6.8); ytot-=16
    c.setFont("Helvetica-Bold",8.0); c.drawString(total_x,ytot,"TOTAL"); c.drawString(total_x+61,ytot,f"INR {_money(header.get('grand_total'))}")
    _draw_text(c,w-143,81,"Authorised Signatory",size=7.0,bold=True); _draw_text(c,w-174,67,PLANT["name"],size=6.2); _draw_text(c,left+318,47,"If you have any questions about this purchase order, please contact",size=6.0); _draw_text(c,left+375,36,"FSI, connect@fourstarindustries.com",size=6.0)
    c.showPage(); c.save(); return out.getvalue()


def _continuation_items_bytes(header: Mapping[str, Any], items: Sequence[Mapping[str, Any]]) -> bytes:
    """Render supplier PO item continuation pages with generous item-wise technical pockets."""
    out=BytesIO(); c=canvas.Canvas(out,pagesize=A4); w,h=A4; left,right=28,28
    widths=[218,44,62,42,40,70,63]; titles=["ITEM #","QTY","UNIT PRICE","UNIT","GST%","GST AMOUNT","TOTAL"]
    remaining=list(items)
    while remaining:
        page_items=remaining[:3]; remaining=remaining[3:]
        logo_path=Path(__file__).resolve().parent.parent / "assets" / "fsi_logo.png"
        if logo_path.exists():
            try:c.drawImage(str(logo_path),left,h-58,width=105,height=39,preserveAspectRatio=True,mask="auto")
            except Exception:pass
        c.setFillColor(black);c.setFont("Helvetica-Bold",18);c.drawRightString(w-right,h-34,"PURCHASE ORDER · ITEMS CONTINUED")
        _draw_text(c,w-168,h-52,f"PO # {_s(header.get('po_number'))}",size=7.2,bold=True)
        _draw_text(c,w-168,h-65,f"DATE {_date(header.get('order_date'))}",size=7.2)
        y_top=h-92; x=left
        for sw,title in zip(widths,titles): _bar(c,x,y_top,sw,title,height=16); x+=sw
        y=y_top-16; bottom=48; block_height=(y-bottom)/max(len(page_items),1)
        for idx,item in enumerate(page_items):
            next_y=max(y-block_height,bottom)
            if idx:c.setStrokeColor(HexColor("#9CA3AF"));c.line(left,y,w-right,y)
            item_row_bottom=y-34
            item_display=" ".join(v for v in (_s(item.get("item_no")),_s(item.get("item_description"))) if v)
            vals=[item_display,f"{_n(item.get('quantity')):,.2f}".rstrip("0").rstrip("."),_money(item.get("unit_price")),item.get("uom"),f"{_n(item.get('gst_percent')):g}%",_money(item.get("gst_amount")),_money(item.get("line_total"))]
            x=left
            for col,(sw,value) in enumerate(zip(widths,vals)):
                if col==0:
                    _wrap(c,x+5,y-11,value,sw-10,size=6.7,leading=7.6,max_lines=2)
                    hsn=_s(item.get("hsn_sac_code"))
                    if hsn:_draw_text(c,x+5,y-28,f"HSN / SAC: {hsn}",size=5.8,bold=True,color=HexColor("#4B5563"),max_width=sw-10)
                else:_draw_text(c,x+4,y-20,value,size=6.5,max_width=sw-8)
                x+=sw
            c.setStrokeColor(HexColor("#D1D5DB"));c.line(left,item_row_bottom,w-right,item_row_bottom)
            c.setFillColor(HexColor("#F3F4F6"));c.rect(left,next_y,w-left-right,max(item_row_bottom-next_y,0),stroke=0,fill=1)
            _draw_text(c,left+5,item_row_bottom-10,"RAW MATERIAL / FORGING PARAMETERS & FSI TECHNICAL DATA",size=6.0,bold=True,color=NAVY,max_width=260)
            raw=item.get("technical_data_snapshot") or []
            pairs=[]
            if isinstance(raw,list):
                for row in raw:
                    if isinstance(row,Mapping) and _s(row.get("heading")) and _s(row.get("value")):pairs.append((_s(row.get("heading")),_s(row.get("value"))))
            pair_width=(w-left-right-10)/3.0; row_y=item_row_bottom-24
            for pidx,(heading,value) in enumerate(pairs[:6]):
                row_no=pidx//3;col_no=pidx%3;px=left+5+col_no*pair_width;py=row_y-row_no*12
                _draw_text(c,px,py,f"{heading}:",size=5.5,bold=True,max_width=pair_width*0.43)
                _draw_text(c,px+pair_width*0.43,py,value,size=5.5,max_width=pair_width*0.55)
            _draw_price_history(c,left+5,item_row_bottom-55,w-left-right-10,item,max_rows=4)
            y=next_y
        _draw_text(c,left,25,"QCMS controlled continuation · Technical data is item-specific and supplier-specific.",size=5.8,color=HexColor("#6B7280"))
        c.showPage()
    c.save();return out.getvalue()

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
    Each supplier-facing part section includes its controlled Price Revision History snapshot
    (Start Date / End Date / Price / Remark) immediately below the item technical data.
    Any extra item lines continue on clean item pages before the controlled FSI/703/F04 terms template.
    """
    if PdfReader is None or PdfWriter is None:
        raise RuntimeError("pypdf is not installed. Add pypdf to requirements.txt.")
    normalized = [dict(items)] if isinstance(items, Mapping) else [dict(v) for v in items]
    if not normalized:
        raise ValueError("At least one Purchase Order line is required.")
    first = _first_page_bytes(header, normalized)
    writer = PdfWriter(); writer.add_page(PdfReader(BytesIO(first)).pages[0])
    if len(normalized) > 2:
        continuation = PdfReader(BytesIO(_continuation_items_bytes(header, normalized[2:])))
        for page in continuation.pages: writer.add_page(page)
    path = Path(terms_path) if terms_path else Path(__file__).resolve().parent.parent / "templates" / "FSI_STANDARD_PO_TERMS_2023.pdf"
    if path.exists():
        for page in _terms_with_dynamic_header(path, po_number=_s(header.get("po_number")), order_date=_s(header.get("order_date"))): writer.add_page(page)
    out = BytesIO(); writer.write(out); return out.getvalue()

