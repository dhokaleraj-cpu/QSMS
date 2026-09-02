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
    # Supports both Party Master snapshots (address/city/state/country) and
    # legacy plant snapshots (address1/address2/address3) so historical POs
    # keep printing correctly while v4.14.10 Ship-To can come from any master.
    party_name = _s(snapshot.get("party_name") or snapshot.get("name"))
    address1 = _s(snapshot.get("address") or snapshot.get("address1"))
    locality = ", ".join(v for v in (_s(snapshot.get("city")), _s(snapshot.get("state")), _s(snapshot.get("country"))) if v)
    legacy_locality = ", ".join(v for v in (_s(snapshot.get("address2")), _s(snapshot.get("address3"))) if v)
    return [
        party_name,
        address1,
        locality or legacy_locality,
        _s(snapshot.get("tax_identifier")),
        _s(snapshot.get("contact_person")),
        _s(snapshot.get("phone")),
        _s(snapshot.get("email")),
    ]


def _block(c: canvas.Canvas, x: float, y_top: float, width: float, title: str, lines: list[str], *, max_lines: int = 7) -> float:
    _bar(c, x, y_top, width, title)
    y = y_top - 24
    for line in [v for v in lines if _s(v)][:max_lines]:
        y = _wrap(c, x + 4, y, line, width - 8, size=7.0, leading=8.2, max_lines=2)
    return y


FIRST_HISTORY_ROWS = 8
CONT_HISTORY_ROWS = 28
HISTORY_ONLY_ROWS = 42


def _technical_pairs(item: Mapping[str, Any], *, po_type: str = "FORGING", limit: int = 12) -> list[tuple[str, str]]:
    """Return supplier-facing controlled technical data in display order.

    For Raw Material POs, FSI forging-only standard fields remain suppressed, but
    every supplier-controlled custom row marked Include on PO is printed. This
    preserves the RM-only print contract while allowing rows such as PACKING, RM
    RATE, CONVERSION COST, CUTTING COST and SHOT BLASTING to appear on the PDF.
    """
    raw = item.get("technical_data_snapshot") or []
    if not isinstance(raw, list):
        return []
    po_kind = _s(po_type).upper()
    rm_allowed_standard = {
        "raw material type", "raw material section", "material grade", "section size",
        "supplier rm item code", "supplier lead time",
    }
    rm_forging_only = {
        "supplier forging part no.", "supplier forging part no", "forge wt", "gross wt",
        "input wt", "forging route",
    }
    priority_names = (
        "Raw Material Type", "Raw Material Section", "Material Grade", "Section Size",
        "Supplier RM Item Code", "Supplier Lead Time", "Forge wt", "Gross wt",
        "Input wt", "Forging Route",
    )
    priority = {name.casefold(): idx for idx, name in enumerate(priority_names)}
    prepared: list[tuple[int, str, str]] = []
    for idx, row in enumerate(raw):
        if not isinstance(row, Mapping):
            continue
        heading = _s(row.get("heading")); value = _s(row.get("value"))
        if not heading or not value:
            continue
        heading_key = heading.casefold()
        source = _s(row.get("source")).upper()
        if po_kind == "RAW_MATERIAL":
            # Explicit custom rows always print when they were snapshotted from an
            # Include-on-PO technical-data row. Legacy snapshots without source are
            # treated as custom unless they are known forging-only standard fields.
            if source == "STANDARD" and heading_key not in rm_allowed_standard:
                continue
            if source != "CUSTOM" and heading_key in rm_forging_only:
                continue
        if heading_key == "raw material section":
            heading = "Raw Material Type"; heading_key = "raw material type"
        prepared.append((priority.get(heading_key, 100 + idx), heading, value))
    prepared.sort(key=lambda v: v[0])
    return [(h, v) for _, h, v in prepared[:limit]]


def _technical_height(item: Mapping[str, Any], *, po_type: str) -> float:
    pairs = _technical_pairs(item, po_type=po_type, limit=12)
    rows = max(1, (len(pairs) + 2) // 3)
    return max(42.0, 22.0 + rows * 13.0)


def _price_history_rows(item: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = item.get("price_history_snapshot") or []
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, Mapping):
            continue
        rows.append({
            "start_date": row.get("start_date"),
            "end_date": row.get("end_date"),
            "price": row.get("price"),
            "freight": row.get("freight"),
            "tool_cost": row.get("tool_cost"),
            "packing_forwarding": row.get("packing_forwarding"),
            "profit": row.get("profit"),
            "icc_rejection": row.get("icc_rejection"),
            "currency": row.get("currency") or "INR",
            "uom": row.get("uom") or item.get("uom") or "",
            "remarks": row.get("remarks") or row.get("remark") or "",
            "status": row.get("status") or "ACTIVE",
        })
    rows.sort(key=lambda r: (str(r.get("start_date") or ""), str(r.get("end_date") or "9999-12-31")))
    return rows


# No vertical grid lines in the PO item body; item identity and values use open-column spacing.
def _draw_item_row(c: canvas.Canvas, item: Mapping[str, Any], *, y_top: float, left: float, right: float, page_width: float) -> float:
    widths = [218, 44, 62, 42, 40, 70, 63]
    titles = ["ITEM #", "QTY", "UNIT PRICE", "UNIT", "GST%", "GST AMOUNT", "TOTAL"]
    x = left
    for sw, title in zip(widths, titles):
        _bar(c, x, y_top, sw, title, height=14); x += sw
    row_top = y_top - 14
    row_bottom = row_top - 34
    c.setFillColor(white); c.rect(left, row_bottom, page_width-left-right, 34, stroke=1, fill=1)
    item_display = " ".join(v for v in (_s(item.get("item_no") or item.get("fsi_part_number_snapshot")), _s(item.get("item_description"))) if v)
    vals = [item_display, f"{_n(item.get('quantity')):,.2f}".rstrip("0").rstrip("."), _money(item.get("unit_price")), item.get("uom"), f"{_n(item.get('gst_percent')):g}%", _money(item.get("gst_amount")), _money(item.get("line_total"))]
    x = left
    for idx, (sw, value) in enumerate(zip(widths, vals)):
        if idx == 0:
            _wrap(c, x+5, row_top-10, value, sw-10, size=7.0, leading=7.8, max_lines=2)
            hsn = _s(item.get("hsn_sac_code"))
            if hsn:
                _draw_text(c, x+5, row_top-28, f"HSN / SAC: {hsn}", size=5.8, bold=True, color=HexColor("#4B5563"), max_width=sw-10)
        else:
            _draw_text(c, x+4, row_top-20, value, size=6.7, max_width=sw-8)
        x += sw
    return row_bottom


def _draw_technical(c: canvas.Canvas, item: Mapping[str, Any], *, po_type: str, top: float, bottom: float, left: float, right: float, page_width: float) -> None:
    total_w = page_width-left-right
    is_rm = _s(po_type).upper() == "RAW_MATERIAL"
    title = "RAW MATERIAL DETAILS & SUPPLIER TECHNICAL DATA" if is_rm else "RAW MATERIAL / FORGING PARAMETERS & SUPPLIER TECHNICAL DATA"
    c.setFillColor(HexColor("#F8FAFC")); c.rect(left, bottom, total_w, max(top-bottom, 0), stroke=1, fill=1)
    _bar(c, left, top, total_w, title, height=15)
    pairs = _technical_pairs(item, po_type=po_type, limit=12)
    if not pairs:
        _draw_text(c, left+5, top-29, "No controlled supplier technical data configured", size=5.8, color=HexColor("#6B7280"), max_width=310)
        return

    # Compact 3-pair grid: HEADING | VALUE repeated three times. This keeps the
    # Part Master technical-data table visible on the same supplier item page.
    row_h = 13.0
    inner_left = left + 3
    inner_w = total_w - 6
    pair_w = inner_w / 3.0
    label_w = pair_w * 0.43
    first_row_top = top - 17
    for row_index in range((len(pairs) + 2) // 3):
        y_top = first_row_top - row_index * row_h
        y_bottom = y_top - row_h
        if y_bottom < bottom + 2:
            break
        for col_index in range(3):
            pair_index = row_index * 3 + col_index
            px = inner_left + col_index * pair_w
            if pair_index >= len(pairs):
                c.setFillColor(white); c.rect(px, y_bottom, pair_w, row_h, stroke=1, fill=1)
                continue
            heading, value = pairs[pair_index]
            c.setFillColor(HexColor("#E9EDF1")); c.rect(px, y_bottom, label_w, row_h, stroke=1, fill=1)
            c.setFillColor(white); c.rect(px+label_w, y_bottom, pair_w-label_w, row_h, stroke=1, fill=1)
            _draw_text(c, px+3, y_bottom+4.1, heading, size=5.2, bold=True, color=HexColor("#30363B"), max_width=label_w-6)
            _draw_text(c, px+label_w+3, y_bottom+4.1, value, size=5.2, color=HexColor("#202124"), max_width=pair_w-label_w-6)


def _draw_price_history(c: canvas.Canvas, item: Mapping[str, Any], history: Sequence[Mapping[str, Any]], *, top: float, bottom: float, left: float, right: float, page_width: float, max_rows: int) -> int:
    """Draw all item-wise price revisions in the compact Part Master format.

    The approved print contract follows the supplied table: Start Date / End Date / Price /
    Remark. Closed revisions remain visible and the open-ended row prints as CURRENT.
    """
    _bar(c, left, top, page_width-left-right, f"PRICE REVISION HISTORY · FSI PART {_s(item.get('item_no') or item.get('fsi_part_number_snapshot'))}", height=15)
    y = top - 15
    total_w = page_width-left-right
    widths = [92, 92, 100, total_w-284]
    headers = ["START DATE", "END DATE", "PRICE", "REMARK"]
    x = left
    for sw, title in zip(widths, headers):
        c.setFillColor(HexColor("#E5E7EB"))
        c.rect(x, y-15, sw, 15, stroke=1, fill=1)
        _draw_text(c, x+3, y-10.4, title, size=5.4, bold=True, color=HexColor("#111827"), max_width=sw-6)
        x += sw
    y -= 15
    available_rows = max(int((y-bottom) // 15), 0)
    count = min(len(history), max_rows, available_rows)
    if count == 0 and not history and y-15 >= bottom:
        c.setFillColor(white); c.rect(left, y-15, total_w, 15, stroke=1, fill=1)
        _draw_text(c, left+4, y-10.5, "No controlled price revision history is recorded for this Supplier / FSI Part.", size=5.8, color=HexColor("#6B7280"), max_width=total_w-8)
        return 0
    for row in list(history)[:count]:
        x = left
        vals = [
            _date(row.get("start_date")),
            _date(row.get("end_date")) if row.get("end_date") else "CURRENT",
            _money(row.get("price")) if row.get("price") not in (None, "") else "-",
            _s(row.get("remarks") or row.get("remark")),
        ]
        for sw, value in zip(widths, vals):
            c.setFillColor(white); c.rect(x, y-15, sw, 15, stroke=1, fill=1)
            _draw_text(c, x+3, y-10.5, value, size=5.35, max_width=sw-6)
            x += sw
        y -= 15
    remaining = len(history) - count
    if remaining > 0 and y-12 >= bottom:
        _draw_text(c, left+4, y-9, f"Continued on next controlled item page · {remaining} more revision(s)", size=5.6, bold=True, color=NAVY, max_width=total_w-8)
    return count


def _draw_continuation_header(c: canvas.Canvas, header: Mapping[str, Any], *, title: str) -> tuple[float, float, float, float]:
    w, h = A4; left, right = 28, 28
    logo_path = Path(__file__).resolve().parent.parent / "assets" / "fsi_logo.png"
    if logo_path.exists():
        try: c.drawImage(str(logo_path), left, h-58, width=105, height=39, preserveAspectRatio=True, mask="auto")
        except Exception: pass
    c.setFillColor(black); c.setFont("Helvetica-Bold", 16.5); c.drawRightString(w-right, h-33, title)
    _draw_text(c, w-176, h-51, f"PO # {_s(header.get('po_number'))}", size=7.2, bold=True)
    _draw_text(c, w-176, h-64, f"DATE {_date(header.get('order_date'))}", size=7.2)
    return w, h, left, right


def _history_continuation_pages(c: canvas.Canvas, header: Mapping[str, Any], item: Mapping[str, Any], history: Sequence[Mapping[str, Any]]) -> None:
    remaining = list(history)
    while remaining:
        w, h, left, right = _draw_continuation_header(c, header, title="PURCHASE ORDER · PRICE HISTORY CONTINUED")
        _draw_text(c, left, h-88, f"FSI PART: {_s(item.get('item_no') or item.get('fsi_part_number_snapshot'))} · {_s(item.get('item_description'))}", size=7.2, bold=True, color=NAVY, max_width=w-left-right)
        rendered = _draw_price_history(c, item, remaining, top=h-102, bottom=50, left=left, right=right, page_width=w, max_rows=HISTORY_ONLY_ROWS)
        if rendered <= 0:
            break
        remaining = remaining[rendered:]
        c.setFillColor(HexColor("#6B7280")); c.setFont("Helvetica",5.8); c.drawCentredString(w/2,27,"QCMS controlled Purchase Order · Price revision history is item-specific and supplier-specific.")
        c.showPage()


def _first_page_bytes(header: Mapping[str, Any], items: Sequence[Mapping[str, Any]]) -> bytes:
    out = BytesIO(); c = canvas.Canvas(out, pagesize=A4); w, h = A4; left, right = 28, 28
    logo_path = Path(__file__).resolve().parent.parent / "assets" / "fsi_logo.png"
    if logo_path.exists():
        try: c.drawImage(str(logo_path), left, h-58, width=105, height=39, preserveAspectRatio=True, mask="auto")
        except Exception: pass

    c.setFillColor(black); c.setFont("Helvetica-Bold", 24); c.drawRightString(w-right, h-34, "PURCHASE ORDER")
    _draw_text(c, w-137, h-51, "DATE", size=7.4); c.rect(w-91, h-58, 62, 12, stroke=1, fill=0); _draw_text(c, w-86, h-55, _date(header.get("order_date")), size=7.2)
    _draw_text(c, w-137, h-65, "PO #", size=7.4); c.rect(w-91, h-72, 62, 12, stroke=1, fill=0); _draw_text(c, w-86, h-69, header.get("po_number"), size=7.2)

    col_w = 230; left_x = left; right_x = w-right-184; y0 = h-62
    plant = dict(header.get("plant_snapshot") or PLANT)
    _block(c, left_x, y0, col_w, "PLANT / COMPANY BRANCH", [plant.get("name") or plant.get("branch_name"), plant.get("address1"), plant.get("address2"), plant.get("address3"), plant.get("tax_identifier") or plant.get("gstin"), plant.get("phone"), plant.get("email")])
    vendor = dict(header.get("vendor_snapshot") or {}); _block(c, left_x, h-154, col_w, "VENDOR", _party_lines(vendor), max_lines=7)
    _block(c, right_x, h-86, 184, "REFERENCE DETAILS", [f"QUOTATION DATE: {_date(header.get('quotation_date'))}", _s(header.get("quotation_reference"))], max_lines=3)
    _block(c, right_x, h-136, 184, "OLD PO DETAILS", [_s(header.get("old_po_reference"))], max_lines=2)
    ship = dict(header.get("ship_to_snapshot") or PLANT)
    _block(c, right_x, h-174, 184, "SHIP TO", _party_lines(ship), max_lines=7)

    y_strip = h-284; strip_widths = [78,106,82,93,w-left-right-359]
    strip_titles = ["REQUISITIONER","SHIP VIA","INCOTERM","DELIVERY DATE","PAYMENT TERM"]
    strip_values = [header.get("requisitioner"),header.get("ship_via"),header.get("incoterm"),_date(header.get("delivery_date")),header.get("payment_term")]
    x = left
    for sw,title,value in zip(strip_widths,strip_titles,strip_values):
        _bar(c,x,y_strip,sw,title,height=14); c.rect(x,y_strip-34,sw,20,stroke=1,fill=0); _draw_text(c,x+4,y_strip-27,value,size=6.6,max_width=sw-8); x += sw

    # One complete item pocket on the first page. Additional items continue on controlled
    # item pages so each supplier line keeps its own technical data and full price history.
    item = dict(items[0])
    y_item_top = y_strip-45
    row_bottom = _draw_item_row(c, item, y_top=y_item_top, left=left, right=right, page_width=w)
    po_type = _s(header.get("po_type") or "FORGING").upper()
    tech_bottom = row_bottom-_technical_height(item, po_type=po_type)
    _draw_technical(c, item, po_type=po_type, top=row_bottom, bottom=tech_bottom, left=left, right=right, page_width=w)
    history = _price_history_rows(item)
    _draw_price_history(c, item, history, top=tech_bottom-4, bottom=245, left=left, right=right, page_width=w, max_rows=FIRST_HISTORY_ROWS)

    _draw_text(c,left+2,236,"Remarks:",size=7.6,bold=True); c.setFillColor(YELLOW); c.rect(left,211,386,21,stroke=0,fill=1); _draw_text(c,left+4,220,header.get("remarks") or "PART WILL BE SUPPLIED AS PER DRAWING.",size=7.0,bold=True,max_width=378)
    c.setFillColor(LIGHT_GREY); c.rect(left,192,386,14,stroke=0,fill=1); _draw_text(c,left+3,196,"Comments or Special Instructions",size=6.8,bold=True); _wrap(c,left+2,181,header.get("special_instructions") or DEFAULT_SPECIAL_INSTRUCTIONS,374,size=6.2,leading=11.3,max_lines=7)
    total_x=417; ytot=205
    for label,val in [("SUBTOTAL",header.get("subtotal")),("CGST 9%",header.get("cgst_amount")),("SGST 9%",header.get("sgst_amount")),("IGST",header.get("igst_amount")),("OTHER",header.get("other_amount"))]:
        _draw_text(c,total_x,ytot,label,size=6.9); c.rect(total_x+55,ytot-5,95,13,stroke=1,fill=0); _draw_text(c,total_x+61,ytot-1,_money(val),size=6.8); ytot -= 16
    c.setFont("Helvetica-Bold",8.0); c.drawString(total_x,ytot,"TOTAL"); c.drawString(total_x+61,ytot,f"INR {_money(header.get('grand_total'))}")
    _draw_text(c,w-143,81,"Authorised Signatory",size=7.0,bold=True); _draw_text(c,w-174,67,plant.get("name") or plant.get("branch_name") or PLANT["name"],size=6.2)
    c.setFillColor(HexColor("#6B7280")); c.setFont("Helvetica",6.0)
    c.drawCentredString(w/2,47,"If you have any questions about this purchase order, please contact")
    c.drawCentredString(w/2,36,"FSI · connect@fourstarindustries.com")
    c.showPage(); c.save(); return out.getvalue()


def _continuation_items_bytes(header: Mapping[str, Any], items: Sequence[Mapping[str, Any]]) -> bytes:
    """One clean supplier item per continuation page, including full price history."""
    out = BytesIO(); c = canvas.Canvas(out, pagesize=A4)
    for item_src in items:
        item = dict(item_src)
        w,h,left,right = _draw_continuation_header(c, header, title="PURCHASE ORDER · ITEM CONTINUED")
        row_bottom = _draw_item_row(c, item, y_top=h-92, left=left, right=right, page_width=w)
        po_type = _s(header.get("po_type") or "FORGING").upper()
        tech_bottom = row_bottom-_technical_height(item, po_type=po_type)
        _draw_technical(c, item, po_type=po_type, top=row_bottom, bottom=tech_bottom, left=left, right=right, page_width=w)
        history = _price_history_rows(item)
        rendered = _draw_price_history(c, item, history, top=tech_bottom-6, bottom=50, left=left, right=right, page_width=w, max_rows=CONT_HISTORY_ROWS)
        c.setFillColor(HexColor("#6B7280")); c.setFont("Helvetica",5.8); c.drawCentredString(w/2,27,"QCMS controlled continuation · Technical data and Price Revision History are item-specific and supplier-specific.")
        c.showPage()
        if rendered < len(history):
            _history_continuation_pages(c, header, item, history[rendered:])
    c.save(); return out.getvalue()


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


# original/customer part number remains an internal QCMS field and is never printed on supplier Purchase Orders.
def purchase_order_pdf_bytes(header: Mapping[str, Any], items: Mapping[str, Any] | Sequence[Mapping[str, Any]], *, terms_path: str | Path | None = None) -> bytes:
    """Return the controlled FSI Purchase Order PDF.

    Page 1 prints one supplier-facing FSI Part Number line with its own supplier-specific
    technical data and complete Price Revision History. Additional items continue on
    controlled item pages with the same structure. The original/customer part number
    remains an internal QCMS field and is never printed. Closed historical price revisions
    remain visible; Start Date / End Date / Price / Remark are printed for every item.
    """
    if PdfReader is None or PdfWriter is None:
        raise RuntimeError("pypdf is not installed. Add pypdf to requirements.txt.")
    normalized = [dict(items)] if isinstance(items, Mapping) else [dict(v) for v in items]
    if not normalized:
        raise ValueError("At least one Purchase Order line is required.")
    first = _first_page_bytes(header, normalized)
    writer = PdfWriter(); writer.add_page(PdfReader(BytesIO(first)).pages[0])
    first_history = _price_history_rows(normalized[0])
    if len(first_history) > FIRST_HISTORY_ROWS:
        overflow = BytesIO(); overflow_canvas = canvas.Canvas(overflow, pagesize=A4)
        _history_continuation_pages(overflow_canvas, header, normalized[0], first_history[FIRST_HISTORY_ROWS:])
        overflow_canvas.save(); overflow.seek(0)
        for page in PdfReader(overflow).pages: writer.add_page(page)
    if len(normalized) > 1:
        continuation = PdfReader(BytesIO(_continuation_items_bytes(header, normalized[1:])))
        for page in continuation.pages: writer.add_page(page)
    path = Path(terms_path) if terms_path else Path(__file__).resolve().parent.parent / "templates" / "FSI_STANDARD_PO_TERMS_2023.pdf"
    if path.exists():
        for page in _terms_with_dynamic_header(path, po_number=_s(header.get("po_number")), order_date=_s(header.get("order_date"))): writer.add_page(page)
    out = BytesIO(); writer.write(out); return out.getvalue()

