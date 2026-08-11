from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Mapping

import pandas as pd
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import CondPageBreak, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, Image as RLImage

from core.config import get_settings

NAVY = colors.HexColor("#083B6E")
BLUE = colors.HexColor("#0B76B7")
LIGHT_BLUE = colors.HexColor("#EAF4FB")
BORDER = colors.HexColor("#AFC3D4")
TEXT = colors.HexColor("#17212B")
MUTED = colors.HexColor("#617386")
WHITE = colors.white


def _logo_path() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "fsi_logo.png"


class _PageNumberCanvas(canvas.Canvas):
    def __init__(
        self,
        *args,
        report_title: str,
        heat_number: str = "",
        record_number: str = "",
        report_label: str = "",
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self._report_title = report_title
        self._heat_number = str(heat_number or "").strip()
        self._record_number = str(record_number or "").strip()
        self._report_label = str(report_label or "").strip()

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_header_footer(page_count)
            super().showPage()
        super().save()

    @staticmethod
    def _split_report_title(title: str) -> tuple[str, str]:
        title = str(title or '').strip()
        if ' - ' in title:
            left, right = title.split(' - ', 1)
            return left.strip(), right.strip()
        if len(title) <= 34:
            return title, ''
        split_at = title.rfind(' ', 0, 34)
        if split_at < 18:
            split_at = 34
        return title[:split_at].strip(), title[split_at:].strip()

    def _draw_header_footer(self, page_count: int) -> None:
        width, height = self._pagesize
        settings = get_settings()
        portrait_page = height >= width
        edge = 8 * mm if portrait_page else 10 * mm
        header_height = 20 * mm if portrait_page else 19 * mm
        header_y = height - (27 * mm if portrait_page else 29 * mm)
        header_width = width - (2 * edge)
        right_panel_width = 48 * mm if portrait_page else 63 * mm

        # Header, report grids and footer use the same left/right printable edges.
        self.setFillColor(NAVY)
        self.roundRect(edge, header_y, header_width, header_height, 3.5 * mm, fill=1, stroke=0)
        self.setFillColor(BLUE)
        self.roundRect(width - edge - right_panel_width, header_y, right_panel_width, header_height, 3.5 * mm, fill=1, stroke=0)

        logo = _logo_path()
        logo_box_w = 22 * mm if portrait_page else 24 * mm
        logo_box_h = 14 * mm
        logo_x = edge + 4 * mm
        logo_y = header_y + 3 * mm
        if logo.exists():
            self.setFillColor(WHITE)
            self.roundRect(logo_x, logo_y, logo_box_w, logo_box_h, 2.0 * mm, fill=1, stroke=0)
            try:
                self.drawImage(
                    str(logo), logo_x + 1.5 * mm, logo_y + 1.5 * mm,
                    logo_box_w - 3 * mm, logo_box_h - 3 * mm,
                    preserveAspectRatio=True, mask='auto',
                )
            except Exception:
                pass

        brand_x = logo_x + logo_box_w + 4 * mm
        self.setFillColor(WHITE)
        self.setFont('Helvetica-Bold', 8.4 if portrait_page else 10)
        self.drawString(brand_x, header_y + 12.0 * mm, 'FOUR STAR INDUSTRIES')
        self.setFont('Helvetica', 5.7 if portrait_page else 6.8)
        self.drawString(brand_x, header_y + 7.4 * mm, 'QUALITY CONTROL MONITORING SYSTEM')

        center_left = edge + (72 * mm if portrait_page else 78 * mm)
        center_right = width - edge - right_panel_width - 3 * mm
        center_x = (center_left + center_right) / 2
        if self._heat_number:
            # Heat Number is intentionally 50% larger than the RMTC/record number.
            self.setFont('Helvetica-Bold', 10.5 if portrait_page else 13.5)
            self.drawCentredString(center_x, header_y + 12.0 * mm, f'HEAT NUMBER: {self._heat_number}'[:42])
            self.setFont('Helvetica-Bold', 7.0 if portrait_page else 9.0)
            secondary = f'RMTC NUMBER: {self._record_number}' if self._record_number else self._report_title
            self.drawCentredString(center_x, header_y + 7.1 * mm, secondary[:55])
            if self._report_label:
                self.setFont('Helvetica', 5.0 if portrait_page else 6.3)
                self.drawCentredString(center_x, header_y + 3.6 * mm, self._report_label[:55])
        else:
            title_line_1, title_line_2 = self._split_report_title(self._report_title)
            self.setFont('Helvetica-Bold', 8.4 if portrait_page else 13)
            self.drawCentredString(center_x, header_y + (12.4 * mm if title_line_2 else 10.5 * mm), title_line_1[:48])
            if title_line_2:
                self.setFont('Helvetica-Bold', 7.2 if portrait_page else 9.5)
                self.drawCentredString(center_x, header_y + 7.4 * mm, title_line_2[:52])

        self.setFont('Helvetica-Bold', 6.0 if portrait_page else 7)
        self.drawRightString(width - edge - 4 * mm, header_y + 13.2 * mm, f'Plant: {settings.plant_code}')
        self.setFont('Helvetica', 5.3 if portrait_page else 6.5)
        self.drawRightString(width - edge - 4 * mm, header_y + 8.8 * mm, datetime.now().strftime('Printed: %d-%m-%Y %I:%M %p'))
        self.drawRightString(width - edge - 4 * mm, header_y + 4.8 * mm, f'App Version: {settings.version}')

        # Footer is printed on every PDF page and aligned to the same report edges.
        footer_y = 9.2 * mm
        self.setStrokeColor(BORDER)
        self.setLineWidth(0.45)
        self.line(edge, footer_y, width - edge, footer_y)
        self.setFillColor(MUTED)
        self.setFont('Helvetica', 5.1 if portrait_page else 6.2)
        footer_text = 'Developed by Rajesh Dhokale | dhokaleraj@icloud.com | Copyrights to jrdhokale'
        self.drawString(edge + 1 * mm, 5.6 * mm, footer_text)
        self.drawRightString(width - edge - 1 * mm, 5.6 * mm, f'Version {settings.version} | Page {self._pageNumber} of {page_count}')

def _paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    text = "" if value is None else str(value)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(text, style)


def report_pdf_bytes(
    title: str,
    sections: Mapping[str, pd.DataFrame],
    *,
    subtitle: str = "",
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=34 * mm,
        bottomMargin=14 * mm,
        title=title,
        author="Four Star Industries - Quality Control Monitoring System",
    )
    styles = getSampleStyleSheet()
    section_style = ParagraphStyle(
        "QSMSSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=WHITE,
        backColor=NAVY,
        leftIndent=4,
        rightIndent=4,
        spaceBefore=3,
        spaceAfter=4,
        borderPadding=(4, 5, 4, 5),
    )
    subtitle_style = ParagraphStyle(
        "QSMSSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=MUTED,
        alignment=TA_CENTER,
        spaceAfter=5,
    )
    header_style = ParagraphStyle(
        "QSMSHeaderCell",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=5.7,
        leading=6.8,
        textColor=WHITE,
        alignment=TA_CENTER,
    )
    cell_style = ParagraphStyle(
        "QSMSCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=5.4,
        leading=6.5,
        textColor=TEXT,
        alignment=TA_LEFT,
    )

    story = []
    if subtitle:
        story.append(Paragraph(subtitle, subtitle_style))
    for section_index, (name, frame) in enumerate(sections.items()):
        if section_index:
            story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(name.upper(), section_style))
        display = frame.copy() if frame is not None else pd.DataFrame()
        if display.empty:
            display = pd.DataFrame([{"Information": "No records found for the selected filters."}])
        display = display.fillna("")
        columns = [str(column) for column in display.columns]
        data = [[_paragraph(column, header_style) for column in columns]]
        for row in display.itertuples(index=False, name=None):
            data.append([_paragraph(value, cell_style) for value in row])

        available_width = landscape(A4)[0] - 20 * mm
        # Equal columns are predictable for wide operational reports; long content wraps.
        col_width = available_width / max(len(columns), 1)
        table = Table(data, colWidths=[col_width] * len(columns), repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2.2),
            ("TOPPADDING", (0, 0), (-1, -1), 2.6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BLUE]),
        ]))
        story.append(table)

    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: _PageNumberCanvas(*args, report_title=title, **kwargs),
    )
    return buffer.getvalue()


def _display_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:,.3f}".rstrip("0").rstrip(".")
    text = str(value).strip()
    if not text:
        return ""
    if "T" in text and len(text) >= 10:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%d-%m-%Y %H:%M")
        except Exception:
            pass
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        try:
            return datetime.fromisoformat(text[:10]).strftime("%d-%m-%Y")
        except Exception:
            pass
    return text.replace("_", " ").title() if text.upper() in {
        "DRAFT", "APPROVAL_PENDING", "APPROVED", "PARTIALLY_APPROVED", "REJECTED",
        "PENDING", "ON_HOLD", "ACCEPTED", "ACCEPTED_UNDER_RESERVE", "PASS", "FAIL",
        "NOT_EVALUATED", "NOT_APPLICABLE",
    } else text


def _employee_name(employee: Mapping[str, object] | None) -> str:
    employee = employee or {}
    name = " ".join(str(employee.get(key) or "").strip() for key in ("first_name", "last_name")).strip()
    code = str(employee.get("employee_code") or "").strip()
    if code and name:
        return f"{code} - {name}"
    return name or code or "-"


def _table_status_color(value: object) -> colors.Color:
    key = str(value or "").strip().upper().replace(" ", "_")
    if key in {"PASS", "APPROVED", "ACCEPTED", "RELEASED", "COMPLETED"}:
        return colors.HexColor("#DCFCE7")
    if key in {"FAIL", "REJECTED", "LOCKED"}:
        return colors.HexColor("#FEE2E2")
    if key in {"ON_HOLD", "HOLD", "APPROVAL_PENDING", "ACCEPTED_UNDER_RESERVE", "PARTIALLY_APPROVED"}:
        return colors.HexColor("#FEF3C7")
    if key in {"PENDING", "DRAFT", "NOT_EVALUATED"}:
        return colors.HexColor("#DBEAFE")
    if key in {"NOT_APPLICABLE", "INACTIVE"}:
        return colors.HexColor("#E2E8F0")
    return WHITE


def _rmtc_grid(
    rows: list[list[object]],
    widths: list[float],
    header_style: ParagraphStyle,
    cell_style: ParagraphStyle,
    *,
    status_columns: tuple[int, ...] = (),
    header_rows: int = 1,
) -> Table:
    prepared: list[list[Paragraph]] = []
    for row_index, row in enumerate(rows):
        style = header_style if row_index < header_rows else cell_style
        prepared.append([_paragraph(value, style) for value in row])
    table = Table(
        prepared,
        colWidths=widths,
        repeatRows=header_rows,
        hAlign="LEFT",
        splitByRow=1,
    )
    commands = [
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, header_rows - 1), WHITE),
        ("GRID", (0, 0), (-1, -1), 0.42, colors.HexColor("#6E8294")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.0),
        ("TOPPADDING", (0, 0), (-1, -1), 2.0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
        ("ROWBACKGROUNDS", (0, header_rows), (-1, -1), [WHITE, LIGHT_BLUE]),
    ]
    for row_index, row in enumerate(rows[header_rows:], start=header_rows):
        for col_index in status_columns:
            if col_index < len(row):
                commands.append(("BACKGROUND", (col_index, row_index), (col_index, row_index), _table_status_color(row[col_index])))
    table.setStyle(TableStyle(commands))
    return table


def _rmtc_section_bar(title: object, width: float, style: ParagraphStyle, *, light: bool = False) -> Table:
    table = Table([[_paragraph(title, style)]], colWidths=[width], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE if light else NAVY),
        ("TEXTCOLOR", (0, 0), (-1, -1), NAVY if light else WHITE),
        ("BOX", (0, 0), (-1, -1), 0.42, colors.HexColor("#6E8294")),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.0),
        ("TOPPADDING", (0, 0), (-1, -1), 2.6 if light else 3.0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6 if light else 3.0),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def _rmtc_labeled_grid(
    rows: list[list[object]],
    widths: list[float],
    label_style: ParagraphStyle,
    cell_style: ParagraphStyle,
    *,
    label_columns: tuple[int, ...] = (0, 2),
) -> Table:
    prepared = []
    for row in rows:
        cells = []
        for index, value in enumerate(row):
            cells.append(_paragraph(_display_value(value), label_style if index in label_columns else cell_style))
        prepared.append(cells)
    table = Table(prepared, colWidths=widths, hAlign="LEFT", splitByRow=1)
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.42, colors.HexColor("#8295A6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.2),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
    ]
    for label_col in label_columns:
        commands.append(("BACKGROUND", (label_col, 0), (label_col, -1), colors.HexColor("#EDF4FA")))
    table.setStyle(TableStyle(commands))
    return table


def _fit_image_flowable(image_bytes: bytes, max_width: float, max_height: float) -> RLImage | None:
    if not image_bytes:
        return None
    try:
        with PILImage.open(BytesIO(image_bytes)) as image:
            width_px, height_px = image.size
        if width_px <= 0 or height_px <= 0:
            return None
        scale = min(max_width / float(width_px), max_height / float(height_px))
        return RLImage(BytesIO(image_bytes), width=width_px * scale, height=height_px * scale)
    except Exception:
        return None


def _microstructure_photo_table(items: list[Mapping[str, object]], content_width: float, caption_style: ParagraphStyle) -> Table:
    column_width = content_width / 3.0
    cells = []
    for slot in range(1, 4):
        item = next((dict(row) for row in items if int(row.get('slot') or 0) == slot), {})
        image = _fit_image_flowable(bytes(item.get('bytes') or b''), column_width - 5 * mm, 40 * mm)
        caption = _paragraph(item.get('caption') or f'Microstructure Photo {slot}', caption_style)
        if image is None:
            placeholder = Table(
                [[_paragraph('No photograph uploaded', caption_style)]],
                colWidths=[column_width - 6 * mm], rowHeights=[36 * mm],
            )
            placeholder.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F7FAFC')),
            ]))
            body = [placeholder, Spacer(1, 1 * mm), caption]
        else:
            body = [image, Spacer(1, 1 * mm), caption]
        cells.append(body)
    table = Table([cells], colWidths=[column_width] * 3, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.55, BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.35, BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2.5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2.5),
        ('TOPPADDING', (0, 0), (-1, -1), 3.0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.0),
    ]))
    return table


def rmtc_record_pdf_bytes(payload: Mapping[str, object]) -> bytes:
    """Create a compact controlled RMTC Record PDF in A4 portrait orientation."""
    record = dict(payload.get("record") or {})
    part_approvals = [dict(row) for row in (payload.get("part_approvals") or [])]
    parts = dict(payload.get("parts") or {})
    grades = dict(payload.get("material_grades") or {})
    chemistry = [dict(row) for row in (payload.get("chemistry") or [])]
    jominy = [dict(row) for row in (payload.get("jominy") or [])]
    requirements = [dict(row) for row in (payload.get("requirements") or [])]
    supplier = dict(payload.get("supplier") or {})
    steel_mill = dict(payload.get("steel_mill") or {})
    employees = dict(payload.get("employees") or {})
    heat_summary = dict(payload.get("heat_summary") or {})
    heat_usage = [dict(row) for row in (payload.get("heat_usage") or [])]
    microstructure_images = [dict(row) for row in (payload.get("microstructure_images") or [])]

    buffer = BytesIO()
    title = f"RMTC RECORD - {record.get('rmtc_number') or 'QUALITY RECORD'}"
    page_width, page_height = A4
    edge = 8 * mm
    content_width = page_width - (2 * edge)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=edge,
        rightMargin=edge,
        topMargin=30 * mm,
        bottomMargin=12 * mm,
        title=title,
        author="Four Star Industries - Quality Control Monitoring System",
        allowSplitting=1,
    )
    styles = getSampleStyleSheet()
    section_text_style = ParagraphStyle(
        "RmtcSectionText", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=7.1, leading=8.3, textColor=WHITE,
    )
    sub_text_style = ParagraphStyle(
        "RmtcSubText", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=6.3, leading=7.4, textColor=NAVY,
    )
    header_style = ParagraphStyle(
        "RmtcHeaderCell", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=4.9, leading=5.8, textColor=WHITE, alignment=TA_CENTER,
    )
    cell_style = ParagraphStyle(
        "RmtcCell", parent=styles["Normal"], fontName="Helvetica",
        fontSize=5.0, leading=5.9, textColor=TEXT, alignment=TA_LEFT,
    )
    label_style = ParagraphStyle(
        "RmtcLabel", parent=cell_style, fontName="Helvetica-Bold", textColor=NAVY,
    )
    center_style = ParagraphStyle(
        "RmtcCenter", parent=cell_style, alignment=TA_CENTER,
    )
    small_style = ParagraphStyle(
        "RmtcSmall", parent=cell_style, fontSize=4.6, leading=5.4,
    )

    story: list[object] = []

    # Header / traceability. The 4-column grid is exactly the same width as the page header.
    story.append(_rmtc_section_bar("RMTC HEADER & TRACEABILITY", content_width, section_text_style))
    header_pairs = [
        ("QCMS RMTC Number", record.get("rmtc_number"), "Entry Date", record.get("entry_date")),
        ("Supplier RMTC Number", record.get("certificate_reference"), "RMTC Date", record.get("certificate_date")),
        ("Supplier", supplier.get("party_name"), "Steel Mill", steel_mill.get("party_name")),
        ("Heat Number", record.get("heat_number"), "Internal Heat Code", record.get("heat_code")),
        ("Global Heat Steel Qty kg", record.get("certificate_quantity"), "RM Section", record.get("rm_section")),
        ("Forging Route / Root", record.get("forging_route"), "Prepared By", _employee_name(employees.get(str(record.get("prepared_by_employee_id"))))),
        ("Workflow Status", record.get("status"), "Validation Result", record.get("validation_result")),
        ("Final Disposition", record.get("disposition"), "Decision Date", record.get("decision_at")),
    ]
    story.append(_rmtc_labeled_grid(
        [list(row) for row in header_pairs],
        [29 * mm, 68 * mm, 29 * mm, 68 * mm],
        label_style, cell_style,
    ))
    if str(record.get("remarks") or "").strip():
        story.append(_rmtc_labeled_grid(
            [["RMTC Remarks", record.get("remarks")]],
            [29 * mm, content_width - 29 * mm], label_style, cell_style,
            label_columns=(0,),
        ))

    story.append(Spacer(1, 1.6 * mm))
    story.append(_rmtc_section_bar("GLOBAL HEAT QUANTITY BALANCE & RECORD LIST", content_width, section_text_style))
    heat_balance_rows = [
        ["Global Heat Qty kg", heat_summary.get("global_steel_quantity_kg") or record.get("certificate_quantity"),
         "Committed kg", heat_summary.get("committed_steel_quantity_kg"),
         "Unallocated Balance kg", heat_summary.get("available_unallocated_steel_quantity_kg") or heat_summary.get("available_steel_quantity_kg")],
        ["Inward Steel Used kg", heat_summary.get("inward_steel_quantity_kg"),
         "Remaining Planned kg", heat_summary.get("remaining_planned_steel_quantity_kg"),
         "Active RMTC Records", heat_summary.get("active_rmtc_count")],
    ]
    story.append(_rmtc_labeled_grid(
        heat_balance_rows,
        [31*mm, 33*mm, 31*mm, 33*mm, 34*mm, 32*mm],
        label_style, cell_style, label_columns=(0, 2, 4),
    ))
    heat_record_rows = [["RMTC No.", "Supplier RMTC", "Supplier", "Part", "Planned kg", "Inward kg", "Balance Plan kg", "Decision"]]
    for row in heat_usage:
        heat_record_rows.append([
            row.get("rmtc_number"), row.get("supplier_rmtc_number"), row.get("supplier_name"), row.get("part_number"),
            row.get("planned_steel_quantity_kg"), row.get("inward_steel_quantity_kg"), row.get("remaining_planned_steel_quantity_kg"),
            row.get("part_disposition") or row.get("rmtc_disposition") or row.get("rmtc_status"),
        ])
    if len(heat_record_rows) == 1:
        heat_record_rows.append([record.get("rmtc_number"), record.get("certificate_reference"), supplier.get("party_name"), "-", "-", "-", "-", record.get("disposition") or record.get("status")])
    story.append(_rmtc_grid(
        heat_record_rows,
        [24*mm, 27*mm, 34*mm, 21*mm, 21*mm, 21*mm, 25*mm, 21*mm],
        header_style, small_style, status_columns=(7,),
    ))

    story.append(Spacer(1, 1.6 * mm))
    story.append(_rmtc_section_bar("COVERED PART WORKSHEET REGISTER", content_width, section_text_style))
    part_summary = [[
        "Part No.", "Description", "Grade", "Planned Qty", "Input kg", "Steel kg", "Worksheet", "Auto Validation", "Final Decision",
    ]]
    for approval in part_approvals:
        part = parts.get(str(approval.get("part_id"))) or {}
        grade = grades.get(str(part.get("material_grade_id"))) or {}
        part_summary.append([
            part.get("part_number"), part.get("part_name"), grade.get("grade_code") or grade.get("grade_name"),
            approval.get("planned_production_quantity_pcs"), approval.get("input_weight_kg"), approval.get("planned_steel_quantity_kg"),
            "Completed" if approval.get("worksheet_completed_at") else "Pending",
            approval.get("approval_status") or "NOT_EVALUATED", approval.get("disposition") or "PENDING",
        ])
    if len(part_summary) == 1:
        part_summary.append(["-", "No covered part worksheets found", "", "", "", "", "Pending", "NOT_EVALUATED", "PENDING"])
    story.append(_rmtc_grid(
        part_summary,
        [18*mm, 30*mm, 18*mm, 18*mm, 17*mm, 19*mm, 22*mm, 25*mm, 27*mm],
        header_style, small_style, status_columns=(6, 7, 8),
    ))

    mechanical = record.get("mechanical_results") or {}
    story.append(Spacer(1, 1.6 * mm))
    story.append(_rmtc_section_bar("SUPPLIER RMTC MECHANICAL PROPERTIES", content_width, section_text_style))
    mech_rows = [["Property", "Actual / Result", "Source"]]
    if isinstance(mechanical, Mapping) and mechanical:
        for key, value in mechanical.items():
            mech_rows.append([str(key).replace("_", " ").title(), value, "Supplier RMTC"])
    else:
        mech_rows.append(["Mechanical Properties", "No dedicated mechanical property values recorded", "Supplier RMTC"])
    story.append(_rmtc_grid(mech_rows, [55*mm, 94*mm, 45*mm], header_style, cell_style))

    # Worksheets flow continuously. No forced page break is used, reducing total pages.
    for worksheet_index, approval in enumerate(part_approvals, start=1):
        story.append(CondPageBreak(42 * mm))
        part_id = str(approval.get("part_id") or "")
        part = parts.get(part_id) or {}
        grade = grades.get(str(part.get("material_grade_id"))) or {}
        part_title = f"PART WORKSHEET {worksheet_index} - {part.get('part_number') or '-'} - {part.get('part_name') or ''}"
        story.append(_rmtc_section_bar(part_title, content_width, section_text_style))

        identity_rows = [
            ["Part Number", part.get("part_number"), "Part Description", part.get("part_name"), "Material Grade", grade.get("grade_code") or grade.get("grade_name")],
            ["Heat Number", record.get("heat_number"), "Heat Code", record.get("heat_code"), "Worksheet Status", "Completed" if approval.get("worksheet_completed_at") else "Pending"],
            ["Planned Production Qty pcs", approval.get("planned_production_quantity_pcs"), "Input Weight kg", approval.get("input_weight_kg"), "Planned Steel kg", approval.get("planned_steel_quantity_kg")],
        ]
        story.append(_rmtc_labeled_grid(
            identity_rows,
            [25*mm, 37*mm, 27*mm, 43*mm, 27*mm, 35*mm],
            label_style, cell_style,
            label_columns=(0, 2, 4),
        ))

        part_chem = [row for row in chemistry if str(row.get("part_id")) == part_id]
        story.append(_rmtc_section_bar("Chemical Composition", content_width, sub_text_style, light=True))
        chem_rows = [["Element", "Minimum", "Maximum", "Actual", "Unit", "Status"]]
        for row in part_chem:
            chem_rows.append([row.get("element"), row.get("minimum_value"), row.get("maximum_value"), row.get("actual_value"), row.get("unit") or "%", row.get("result")])
        if len(chem_rows) == 1:
            chem_rows.append(["-", "", "", "No chemistry values recorded", "", "NOT_EVALUATED"])
        story.append(_rmtc_grid(chem_rows, [24*mm, 31*mm, 31*mm, 39*mm, 19*mm, 50*mm], header_style, cell_style, status_columns=(5,)))

        part_jominy = [row for row in jominy if str(row.get("part_id")) == part_id]
        story.append(_rmtc_section_bar("Jominy Results", content_width, sub_text_style, light=True))
        j_rows = [["Distance", "mm", "Min HRC", "Max HRC", "Actual", "Actual Status", "Calculated", "Calc. Status", "Applicable"]]
        for row in part_jominy:
            j_rows.append([
                row.get("distance_label"), row.get("distance_mm"), row.get("minimum_hrc"), row.get("maximum_hrc"),
                row.get("actual_hrc"), row.get("result"), row.get("calculated_hrc"), row.get("calculated_result"),
                "No" if str(row.get("applicability")) == "NOT_APPLICABLE" else "Yes",
            ])
        if len(j_rows) == 1:
            j_rows.append(["-", "", "", "", "", "NOT_EVALUATED", "", "NOT_EVALUATED", "No"])
        story.append(_rmtc_grid(
            j_rows,
            [20*mm, 14*mm, 18*mm, 18*mm, 20*mm, 24*mm, 22*mm, 28*mm, 30*mm],
            header_style, small_style, status_columns=(5, 7),
        ))

        story.append(_rmtc_section_bar("DI / Hardenability", content_width, sub_text_style, light=True))
        di_rows = [["Grain Size ASTM E-112", "Actual DI", "Actual DI Status", "Calculated DI", "Calculated DI Status"]]
        di_rows.append([approval.get("grain_size"), approval.get("actual_di"), approval.get("actual_di_status"), approval.get("calculated_di"), approval.get("calculated_di_status")])
        story.append(_rmtc_grid(di_rows, [42*mm, 32*mm, 42*mm, 32*mm, 46*mm], header_style, cell_style, status_columns=(2, 4)))

        part_req = [row for row in requirements if str(row.get("part_id")) == part_id]
        mechanical_tokens = ("tensile", "yield", "elongation", "reduction", "impact", "proof", "mechanical", "uts")
        mech_req = [row for row in part_req if any(token in str(row.get("requirement_name") or row.get("requirement_code") or "").casefold() for token in mechanical_tokens)]
        other_req = [row for row in part_req if row not in mech_req]

        story.append(_rmtc_section_bar("Mechanical Properties", content_width, sub_text_style, light=True))
        mech_part_rows = [["Property", "Specification", "Actual / Observation", "Unit", "Status", "Remarks"]]
        for row in mech_req:
            mech_part_rows.append([row.get("requirement_name") or row.get("requirement_code"), row.get("requirement_value"), row.get("actual_value"), row.get("unit"), row.get("result"), row.get("remarks")])
        if len(mech_part_rows) == 1:
            mech_part_rows.append(["Mechanical Properties", "As supplier RMTC / Part requirement", "No separate part-level mechanical property row", "", "NOT_EVALUATED", ""])
        story.append(_rmtc_grid(mech_part_rows, [38*mm, 42*mm, 40*mm, 18*mm, 24*mm, 32*mm], header_style, small_style, status_columns=(4,)))

        story.append(_rmtc_section_bar("Heat Treatment & Other Requirements", content_width, sub_text_style, light=True))
        req_rows = [["Requirement", "Specification / Part Master", "RMTC Actual / Observation", "Unit", "Status", "Remarks"]]
        for row in other_req:
            req_rows.append([row.get("requirement_name") or row.get("requirement_code"), row.get("requirement_value"), row.get("actual_value"), row.get("unit"), row.get("result"), row.get("remarks")])
        if len(req_rows) == 1:
            req_rows.append(["-", "No additional requirements recorded", "", "", "NOT_EVALUATED", ""])
        story.append(_rmtc_grid(req_rows, [38*mm, 45*mm, 39*mm, 18*mm, 24*mm, 30*mm], header_style, small_style, status_columns=(4,)))

    story.append(CondPageBreak(55 * mm))
    story.append(_rmtc_section_bar("RMTC MICROSTRUCTURE PHOTOGRAPHS", content_width, section_text_style))
    story.append(_microstructure_photo_table(microstructure_images, content_width, center_style))

    story.append(CondPageBreak(44 * mm))
    story.append(_rmtc_section_bar("RMTC VALIDATION STATUS & FINAL DECISION", content_width, section_text_style))
    if not part_approvals:
        story.append(_rmtc_grid(
            [["Validation Check", "Status", "Validation Check", "Status"], ["Record", "NOT_EVALUATED", "Final Decision", "PENDING"]],
            [42*mm, 55*mm, 42*mm, 55*mm], header_style, cell_style, status_columns=(1, 3),
        ))
    else:
        for approval_index, approval in enumerate(part_approvals, start=1):
            part = parts.get(str(approval.get("part_id"))) or {}
            grade = grades.get(str(part.get("material_grade_id"))) or {}
            if approval_index > 1:
                story.append(Spacer(1, 1.2 * mm))
            story.append(_rmtc_section_bar(
                f"{part.get('part_number') or '-'} - {part.get('part_name') or ''} - {grade.get('grade_code') or grade.get('grade_name') or ''}",
                content_width, sub_text_style, light=True,
            ))
            validation_rows = [["Validation Check", "Status", "Validation Check", "Status"],
                ["Source", approval.get("source_status"), "Material Grade", approval.get("material_grade_status")],
                ["Raw Material", approval.get("raw_material_status"), "Chemistry", approval.get("chemistry_status")],
                ["Jominy", approval.get("jominy_status"), "Requirements", approval.get("requirement_status")],
                ["Actual DI", approval.get("actual_di_status"), "Calculated DI", approval.get("calculated_di_status")],
                ["Automated Recommendation", approval.get("approval_status"), "Final Decision", approval.get("disposition")],
            ]
            story.append(_rmtc_grid(
                validation_rows, [42*mm, 55*mm, 42*mm, 55*mm],
                header_style, cell_style, status_columns=(1, 3),
            ))
            reason = approval.get("decision_reason") or record.get("decision_reason") or ""
            story.append(_rmtc_labeled_grid(
                [["Decision / Reserve Reason", reason or "-"]],
                [42*mm, 152*mm], label_style, cell_style, label_columns=(0,),
            ))

    story.append(Spacer(1, 1.6 * mm))
    sign_rows = [[
        "Prepared By", _employee_name(employees.get(str(record.get("prepared_by_employee_id")))),
        "Validated By", _employee_name(employees.get(str(record.get("validated_by_employee_id")))),
        "Approved / Decided By", _employee_name(employees.get(str(record.get("approved_by_employee_id") or record.get("decision_by_employee_id")))),
    ], [
        "Prepared At", _display_value(record.get("prepared_at")),
        "Validated At", _display_value(record.get("validated_at")),
        "Decision At", _display_value(record.get("decision_at") or record.get("approved_at")),
    ]]
    story.append(_rmtc_labeled_grid(
        sign_rows,
        [24*mm, 41*mm, 24*mm, 41*mm, 30*mm, 34*mm],
        label_style, center_style, label_columns=(0, 2, 4),
    ))

    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: _PageNumberCanvas(
            *args, report_title=title,
            heat_number=str(record.get("heat_number") or ""),
            record_number=str(record.get("rmtc_number") or ""),
            report_label="RMTC RECORD",
            **kwargs,
        ),
    )
    return buffer.getvalue()


def _photo_grid_table(
    items: list[Mapping[str, object]],
    content_width: float,
    caption_style: ParagraphStyle,
    *,
    columns: int = 2,
    max_height: float = 46 * mm,
) -> Table:
    columns = max(1, int(columns))
    col_width = content_width / columns
    normalized = [dict(item) for item in items] or []
    cells: list[list[object]] = []
    for index, item in enumerate(normalized, start=1):
        image = _fit_image_flowable(bytes(item.get("bytes") or b""), col_width - 6 * mm, max_height)
        caption = _paragraph(item.get("caption") or f"Microstructure Photo {index}", caption_style)
        if image is None:
            placeholder = Table(
                [[_paragraph("No photograph uploaded", caption_style)]],
                colWidths=[col_width - 8 * mm], rowHeights=[max_height - 5 * mm],
            )
            placeholder.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
            ]))
            cell = [placeholder, Spacer(1, 1 * mm), caption]
        else:
            cell = [image, Spacer(1, 1 * mm), caption]
        if (index - 1) % columns == 0:
            cells.append([])
        cells[-1].append(cell)
    if not cells:
        cells = [[[_paragraph("No microstructure photographs recorded", caption_style)]]]
        columns = 1
        col_width = content_width
    while len(cells[-1]) < columns:
        cells[-1].append("")
    table = Table(cells, colWidths=[col_width] * columns, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.55, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _controlled_styles() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    cell = ParagraphStyle("QcCell", parent=styles["Normal"], fontName="Helvetica", fontSize=5.4, leading=6.4, textColor=TEXT)
    return {
        "section": ParagraphStyle("QcSection", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.2, leading=8.4, textColor=WHITE),
        "sub": ParagraphStyle("QcSub", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=6.5, leading=7.6, textColor=NAVY),
        "header": ParagraphStyle("QcHeader", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=5.2, leading=6.1, textColor=WHITE, alignment=TA_CENTER),
        "cell": cell,
        "small": ParagraphStyle("QcSmall", parent=cell, fontSize=4.8, leading=5.6),
        "label": ParagraphStyle("QcLabel", parent=cell, fontName="Helvetica-Bold", textColor=NAVY),
        "center": ParagraphStyle("QcCenter", parent=cell, alignment=TA_CENTER),
    }


def metlab_record_pdf_bytes(payload: Mapping[str, object]) -> bytes:
    """Controlled A4 portrait MetLAB report for Material Inward and OSP modules."""
    record = dict(payload.get("record") or {})
    part = dict(payload.get("part") or {})
    inward = dict(payload.get("inward") or {})
    supplier = dict(payload.get("supplier") or {})
    steel_mill = dict(payload.get("steel_mill") or {})
    grade = dict(payload.get("material_grade") or {})
    process = dict(payload.get("process") or {})
    stage = dict(payload.get("stage") or {})
    osp_job = dict(payload.get("osp_job") or {})
    employees = dict(payload.get("employees") or {})
    results = dict(payload.get("results") or {})
    microstructure_images = [dict(row) for row in (payload.get("microstructure_images") or [])]

    scope = str(record.get("inspection_scope") or "MATERIAL_INWARD")
    is_osp = scope.startswith("OSP_") or bool(record.get("osp_job_id"))
    title = "OSP METALLURGICAL TEST REPORT" if is_osp else "RAW MATERIAL METALLURGICAL TEST REPORT"
    buffer = BytesIO()
    page_width, _ = A4
    edge = 8 * mm
    content_width = page_width - 2 * edge
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=edge, rightMargin=edge, topMargin=30 * mm, bottomMargin=12 * mm,
        title=title, author="Four Star Industries - Quality Control Monitoring System", allowSplitting=1,
    )
    sty = _controlled_styles()
    story: list[object] = []

    story.append(_rmtc_section_bar(title, content_width, sty["section"]))
    vendor_or_supplier = osp_job.get("vendor_name") if is_osp else supplier.get("party_name")
    supply_condition = osp_job.get("process_name") or process.get("process_name") or record.get("layout_name_snapshot")
    qty = osp_job.get("sample_quantity") if scope == "OSP_SAMPLE" else (osp_job.get("quantity_received") if is_osp else record.get("production_quantity_pcs"))
    meta = [
        ["Report No.", record.get("report_number"), "Date", record.get("test_date")],
        ["Part Name", part.get("part_name"), "Part No.", part.get("part_number")],
        ["Supplier / OSP Vendor", vendor_or_supplier, "Material Used", grade.get("grade_code") or grade.get("grade_name")],
        ["Supply / Process Condition", supply_condition, "Inspection Stage", stage.get("stage_name") or scope.replace("_", " ").title()],
        ["Heat Number", record.get("heat_number") or inward.get("heat_number") or osp_job.get("heat_number"), "Heat Code", record.get("heat_code") or inward.get("heat_code")],
        ["Sample / Inward Reference", record.get("sample_reference") or inward.get("inward_number") or osp_job.get("sample_reference"), "Quantity", qty],
        ["Specification Reference", record.get("specification_reference"), "Vendor Batch / Steel Mill", osp_job.get("vendor_batch_number") or steel_mill.get("party_name")],
    ]
    story.append(_rmtc_labeled_grid(meta, [32*mm, 65*mm, 32*mm, 65*mm], sty["label"], sty["cell"], label_columns=(0, 2)))

    section_rows = [dict(row) for row in (results.get("rows") or [])]
    requirement_rows = [dict(row) for row in (results.get("requirement_rows") or [])]
    test_rows = [["Sr.", "Parameter", "Specification", "Observations", "Unit", "Result"]]
    sequence = 1
    for row in section_rows:
        spec = row.get("specification")
        if not spec:
            lo, hi = row.get("lower_spec"), row.get("upper_spec")
            if lo is not None or hi is not None:
                spec = f"{'' if lo is None else lo} - {'' if hi is None else hi}".strip(" -")
        test_rows.append([row.get("sequence_no") or sequence, row.get("parameter"), spec, row.get("actual_value"), row.get("unit"), row.get("result")])
        sequence += 1
    for row in requirement_rows:
        test_rows.append([sequence, row.get("requirement_name"), row.get("requirement_value"), row.get("actual_value"), row.get("unit"), row.get("result")])
        sequence += 1
    if len(test_rows) == 1:
        test_rows.append([1, "Metallurgical requirements", "As approved inspection layout", "No result rows recorded", "", "NOT_EVALUATED"])
    story.append(Spacer(1, 1.4 * mm))
    story.append(_rmtc_section_bar("METALLURGICAL TEST RESULTS", content_width, sty["section"]))
    story.append(_rmtc_grid(test_rows, [12*mm, 54*mm, 50*mm, 46*mm, 14*mm, 18*mm], sty["header"], sty["small"], status_columns=(5,)))

    chemistry_rows = [dict(row) for row in (results.get("chemistry_rows") or [])]
    if chemistry_rows:
        story.append(_rmtc_section_bar("Chemical Composition Verification", content_width, sty["sub"], light=True))
        rows = [["Element", "Minimum", "Maximum", "RMTC Actual", "MetLAB Actual", "Unit", "Result"]]
        for row in chemistry_rows:
            rows.append([row.get("element"), row.get("minimum_value"), row.get("maximum_value"), row.get("rmtc_actual_value"), row.get("actual_value"), row.get("unit"), row.get("result")])
        story.append(_rmtc_grid(rows, [22*mm, 26*mm, 26*mm, 32*mm, 32*mm, 18*mm, 38*mm], sty["header"], sty["small"], status_columns=(6,)))

    jominy_rows = [dict(row) for row in (results.get("jominy_rows") or [])]
    if jominy_rows:
        story.append(_rmtc_section_bar("HARDNESS / JOMINY TRAVERSE", content_width, sty["sub"], light=True))
        rows = [["Distance", "mm", "Min HRC", "Max HRC", "RMTC HRC", "MetLAB HRC", "Result", "Remark"]]
        for row in jominy_rows:
            rows.append([row.get("distance_label"), row.get("distance_mm"), row.get("minimum_hrc"), row.get("maximum_hrc"), row.get("rmtc_actual_hrc"), row.get("actual_value"), row.get("result"), row.get("remarks")])
        story.append(_rmtc_grid(rows, [20*mm, 17*mm, 22*mm, 22*mm, 25*mm, 28*mm, 22*mm, 38*mm], sty["header"], sty["small"], status_columns=(6,)))

    story.append(CondPageBreak(70 * mm))
    story.append(_rmtc_section_bar("MICROSTRUCTURE PHOTOGRAPHS", content_width, sty["section"]))
    story.append(_photo_grid_table(microstructure_images, content_width, sty["center"], columns=2, max_height=46*mm))

    prepared = _employee_name(employees.get(str(record.get("prepared_by_employee_id"))))
    validated = _employee_name(employees.get(str(record.get("validated_by_employee_id"))))
    approved = _employee_name(employees.get(str(record.get("approved_by_employee_id"))))
    overall = record.get("disposition") or record.get("overall_result") or "NOT_EVALUATED"
    conclusion = record.get("disposition_reason") or record.get("remarks") or f"Overall result: {overall}"
    story.append(Spacer(1, 1.5 * mm))
    story.append(_rmtc_labeled_grid([["Conclusion", conclusion], ["Overall Decision", overall]], [32*mm, 162*mm], sty["label"], sty["cell"], label_columns=(0,)))
    story.append(_rmtc_labeled_grid([
        ["Prepared By", prepared, "Validated By", validated, "Verified & Approved By", approved],
        ["Prepared / Test Date", record.get("test_date"), "Validated At", record.get("validated_at"), "Decision At", record.get("decision_at")],
    ], [25*mm, 37*mm, 25*mm, 37*mm, 34*mm, 36*mm], sty["label"], sty["center"], label_columns=(0, 2, 4)))

    doc.build(story, canvasmaker=lambda *args, **kwargs: _PageNumberCanvas(*args, report_title=title, **kwargs))
    return buffer.getvalue()


def dimensional_record_pdf_bytes(payload: Mapping[str, object]) -> bytes:
    """A4 portrait Final / Dimensional Inspection report using the controlled report layout."""
    record = dict(payload.get("record") or {})
    part = dict(payload.get("part") or {})
    inward = dict(payload.get("inward") or {})
    supplier = dict(payload.get("supplier") or {})
    process = dict(payload.get("process") or {})
    stage = dict(payload.get("stage") or {})
    osp_job = dict(payload.get("osp_job") or {})
    employees = dict(payload.get("employees") or {})
    results = [dict(row) for row in (payload.get("results") or [])]
    scope = str(record.get("inspection_scope") or "MATERIAL_INWARD")
    is_osp = scope.startswith("OSP_") or bool(record.get("osp_job_id"))
    title = "OSP DIMENSIONAL INSPECTION REPORT" if is_osp else "FINAL INSPECTION / DIMENSIONAL REPORT"
    buffer = BytesIO(); page_width, _ = A4; edge = 8*mm; content_width = page_width - 2*edge
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=edge, rightMargin=edge, topMargin=30*mm, bottomMargin=12*mm, title=title, author="Four Star Industries - Quality Control Monitoring System", allowSplitting=1)
    sty = _controlled_styles(); story: list[object] = []
    story.append(_rmtc_section_bar(title, content_width, sty["section"]))
    meta = [
        ["Report No.", record.get("report_number"), "Date", record.get("inspection_date")],
        ["Part Name", part.get("part_name"), "Part No.", part.get("part_number")],
        ["Supplier / OSP Vendor", osp_job.get("vendor_name") or supplier.get("party_name"), "Heat Number", record.get("heat_number") or inward.get("heat_number") or osp_job.get("heat_number")],
        ["Process", osp_job.get("process_name") or process.get("process_name"), "Inspection Stage", stage.get("stage_name") or record.get("layout_type_name")],
        ["Drawing", record.get("drawing_number") or part.get("drawing_number"), "Revision", record.get("drawing_revision") or part.get("drawing_revision")],
        ["Layout", record.get("layout_name_snapshot"), "Lot / Production Qty", record.get("production_quantity_pcs") or record.get("lot_quantity")],
        ["Sample Size", record.get("sample_size"), "Vendor Batch / Heat Code", osp_job.get("vendor_batch_number") or record.get("heat_code")],
    ]
    story.append(_rmtc_labeled_grid(meta, [32*mm,65*mm,32*mm,65*mm], sty["label"], sty["cell"], label_columns=(0,2)))
    story.append(Spacer(1,1.5*mm)); story.append(_rmtc_section_bar("INSPECTION RESULTS", content_width, sty["section"]))
    rows = [["Sr.", "Parameter / Characteristic", "Specification", "Observations", "Method / Aid", "Result"]]
    for index, row in enumerate(results, start=1):
        observations = row.get("observations") or []
        if isinstance(observations, list): observations = ", ".join(str(v) for v in observations if v not in (None, ""))
        specification = row.get("specification")
        if not specification and (row.get("lower_spec") is not None or row.get("upper_spec") is not None):
            specification = f"{row.get('lower_spec') if row.get('lower_spec') is not None else ''} - {row.get('upper_spec') if row.get('upper_spec') is not None else ''} {row.get('unit') or ''}".strip()
        rows.append([row.get("sequence_no") or row.get("characteristic_no") or index, row.get("characteristic"), specification, observations or row.get("attribute_result"), row.get("checking_aid"), row.get("result")])
    if len(rows)==1: rows.append([1,"Inspection characteristic","As approved layout","No results recorded","","NOT_EVALUATED"])
    story.append(_rmtc_grid(rows, [12*mm,54*mm,48*mm,42*mm,22*mm,16*mm], sty["header"], sty["small"], status_columns=(5,)))
    overall = record.get("disposition") or record.get("overall_result") or "NOT_EVALUATED"
    story.append(Spacer(1,1.5*mm)); story.append(_rmtc_labeled_grid([["Conclusion / Remarks", record.get("disposition_reason") or record.get("remarks") or f"Overall result: {overall}"],["Overall Decision", overall]], [36*mm,158*mm], sty["label"], sty["cell"], label_columns=(0,)))
    story.append(_rmtc_labeled_grid([["Prepared By",_employee_name(employees.get(str(record.get("prepared_by_employee_id")))),"Validated By",_employee_name(employees.get(str(record.get("validated_by_employee_id")))),"Approved By",_employee_name(employees.get(str(record.get("approved_by_employee_id"))))]], [25*mm,39*mm,25*mm,39*mm,25*mm,41*mm], sty["label"], sty["center"], label_columns=(0,2,4)))
    doc.build(story, canvasmaker=lambda *args, **kwargs: _PageNumberCanvas(*args, report_title=title, **kwargs))
    return buffer.getvalue()


def material_inward_record_pdf_bytes(payload: Mapping[str, object]) -> bytes:
    """Controlled A4 portrait Material Inward quality record."""
    record = dict(payload.get("record") or {})
    register = dict(payload.get("register") or {})
    part = dict(payload.get("part") or {})
    supplier = dict(payload.get("supplier") or {})
    rmtc = dict(payload.get("rmtc") or {})
    employees = dict(payload.get("employees") or {})
    metlab = dict(payload.get("metlab") or {})
    dimensional = dict(payload.get("dimensional") or {})
    title = "MATERIAL INWARD INSPECTION RECORD"
    buffer=BytesIO(); page_width,_=A4; edge=8*mm; content_width=page_width-2*edge
    doc=SimpleDocTemplate(buffer,pagesize=A4,leftMargin=edge,rightMargin=edge,topMargin=30*mm,bottomMargin=12*mm,title=title,author="Four Star Industries - Quality Control Monitoring System",allowSplitting=1)
    sty=_controlled_styles(); story:list[object]=[]
    story.append(_rmtc_section_bar(title,content_width,sty["section"]))
    meta=[
        ["Inward No.",record.get("inward_number"),"Date",record.get("inward_date")],
        ["GRN Number",record.get("grn_number"),"Supplier Invoice",record.get("invoice_number")],
        ["Part Name",part.get("part_name") or register.get("part_name"),"Part No.",part.get("part_number") or register.get("part_number")],
        ["Supplier",supplier.get("party_name") or register.get("supplier_name"),"Heat Number",record.get("heat_number")],
        ["Heat Code",record.get("heat_code"),"RMTC Number",rmtc.get("rmtc_number") or register.get("rmtc_number")],
        ["Supplier RMTC",rmtc.get("certificate_reference") or register.get("supplier_rmtc_number"),"Input Weight kg/part",record.get("input_weight_kg")],
    ]
    story.append(_rmtc_labeled_grid(meta,[32*mm,65*mm,32*mm,65*mm],sty["label"],sty["cell"],label_columns=(0,2)))
    story.append(Spacer(1,1.5*mm)); story.append(_rmtc_section_bar("QUANTITY & STEEL ALLOCATION",content_width,sty["section"]))
    qty_rows=[
        ["Quantity", "Production pcs", "Steel kg", "Disposition / Status"],
        ["Total",record.get("production_quantity_pcs"),record.get("required_steel_quantity_kg") or record.get("steel_quantity_kg"),record.get("receipt_disposition")],
        ["Accepted",record.get("accepted_production_quantity_pcs"),record.get("accepted_steel_quantity_kg"),"ACCEPTED"],
        ["Rejected",record.get("rejected_production_quantity_pcs"),record.get("rejected_steel_quantity_kg"),"REJECTED"],
        ["On Hold",record.get("hold_production_quantity_pcs"),record.get("hold_steel_quantity_kg"),"ON_HOLD"],
    ]
    story.append(_rmtc_grid(qty_rows,[44*mm,45*mm,45*mm,60*mm],sty["header"],sty["cell"],status_columns=(3,)))
    story.append(_rmtc_section_bar("QUALITY GATE & LINKED INSPECTIONS",content_width,sty["section"]))
    quality_rows=[
        ["Quality Gate","Status","Linked Report","Report / Decision"],
        ["RMTC Validation",rmtc.get("disposition") or register.get("rmtc_disposition"),rmtc.get("rmtc_number"),rmtc.get("validation_result")],
        ["MetLAB",record.get("metallurgical_status"),metlab.get("report_number") or "-",metlab.get("disposition") or metlab.get("overall_result")],
        ["Dimensional / Final Inspection",record.get("dimensional_status"),dimensional.get("report_number") or "-",dimensional.get("disposition") or dimensional.get("overall_result")],
        ["Final Quality Decision",record.get("quality_disposition"),"Material Inward",record.get("status")],
    ]
    story.append(_rmtc_grid(quality_rows,[50*mm,42*mm,47*mm,55*mm],sty["header"],sty["cell"],status_columns=(1,3)))
    if record.get("reserve_reason") or record.get("remarks"):
        story.append(_rmtc_labeled_grid([["Hold / Reserve / Rejection Reason",record.get("reserve_reason") or "-"],["Remarks",record.get("remarks") or "-"]],[48*mm,146*mm],sty["label"],sty["cell"],label_columns=(0,)))
    story.append(Spacer(1,1.5*mm)); story.append(_rmtc_labeled_grid([["Prepared By",_employee_name(employees.get(str(record.get("prepared_by_employee_id")))),"Validated By",_employee_name(employees.get(str(record.get("validated_by_employee_id"))))]], [32*mm,65*mm,32*mm,65*mm],sty["label"],sty["center"],label_columns=(0,2)))
    doc.build(story,canvasmaker=lambda *args,**kwargs:_PageNumberCanvas(*args,report_title=title,**kwargs))
    return buffer.getvalue()


def controlled_record_pdf_bytes(
    title: str,
    header_fields: Mapping[str, object],
    sections: Mapping[str, object] | None = None,
    *,
    record_number: str = "",
    subtitle: str = "",
) -> bytes:
    """Create a compact A4 portrait controlled-record PDF with the common QCMS header/footer.

    `sections` may contain pandas DataFrames, lists of dictionaries, dictionaries,
    or scalar values. It is intentionally reusable so every record-centric module
    can offer the same print-layout behavior without duplicating PDF code.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=8 * mm,
        rightMargin=8 * mm,
        topMargin=32 * mm,
        bottomMargin=14 * mm,
        title=title,
        author="Four Star Industries - Quality Control Monitoring System",
    )
    styles = _controlled_styles()
    content_width = A4[0] - 16 * mm
    story: list[object] = []
    if subtitle:
        sub = ParagraphStyle(
            "ControlledRecordSubtitle",
            parent=styles["cell"],
            fontSize=6.2,
            leading=7.4,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=2 * mm,
        )
        story.append(_paragraph(subtitle, sub))

    header_items = [(str(key), _display_value(value)) for key, value in header_fields.items()]
    if header_items:
        story.append(_rmtc_section_bar("RECORD DETAILS", content_width, styles["section"]))
        rows: list[list[object]] = []
        for index in range(0, len(header_items), 2):
            left = header_items[index]
            right = header_items[index + 1] if index + 1 < len(header_items) else ("", "")
            rows.append([left[0], left[1], right[0], right[1]])
        story.append(_rmtc_labeled_grid(
            rows,
            [33 * mm, 61 * mm, 33 * mm, content_width - 127 * mm],
            styles["label"],
            styles["cell"],
        ))

    for section_name, raw in (sections or {}).items():
        story.append(Spacer(1, 2.4 * mm))
        story.append(_rmtc_section_bar(section_name, content_width, styles["section"]))
        if isinstance(raw, pd.DataFrame):
            frame = raw.copy()
        elif isinstance(raw, Mapping):
            frame = pd.DataFrame([{"Field": key, "Value": value} for key, value in raw.items()])
        elif isinstance(raw, list):
            if raw and isinstance(raw[0], Mapping):
                frame = pd.DataFrame(raw)
            else:
                frame = pd.DataFrame({"Value": raw})
        elif raw is None:
            frame = pd.DataFrame()
        else:
            frame = pd.DataFrame([{"Information": raw}])
        if frame.empty:
            frame = pd.DataFrame([{"Information": "No records available."}])
        frame = frame.fillna("")
        columns = [str(column) for column in frame.columns]
        table_rows: list[list[object]] = [columns]
        table_rows.extend([list(row) for row in frame.itertuples(index=False, name=None)])
        widths = [content_width / max(1, len(columns))] * max(1, len(columns))
        status_columns = tuple(index for index, name in enumerate(columns) if "status" in name.casefold() or "result" in name.casefold())
        story.append(_rmtc_grid(table_rows, widths, styles["header"], styles["cell"], status_columns=status_columns))

    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: _PageNumberCanvas(
            *args,
            report_title=title,
            record_number=record_number,
            report_label=subtitle,
            **kwargs,
        ),
    )
    return buffer.getvalue()


def qc_calculation_pdf_bytes(payload: Mapping[str, object]) -> bytes:
    record = dict(payload.get("record") or {})
    employee = dict(payload.get("employee") or {})
    part = dict(payload.get("part") or {})
    grade = dict(payload.get("grade") or {})
    input_payload = dict(record.get("input_payload") or {})
    result_payload = dict(record.get("result_payload") or {})
    header = {
        "Calculation No.": record.get("calculation_number"),
        "Calculation Type": str(record.get("calculation_type") or "").replace("_", " ").title(),
        "Calculation Date": record.get("calculation_date"),
        "Performed By": _employee_name(employee),
        "Part Number": part.get("part_number"),
        "Material Grade": grade.get("grade_code"),
        "Heat Number": record.get("heat_number"),
        "Standard / Basis": record.get("standard_reference"),
        "Status": record.get("status"),
        "Remarks": record.get("remarks"),
    }
    sections: dict[str, object] = {
        "Calculation Inputs": input_payload,
    }
    calc_type = str(record.get("calculation_type") or "")
    if calc_type == "JOMINY":
        curve = result_payload.get("curve") or {}
        sections["Calculated Jominy Curve"] = pd.DataFrame([
            {"Distance (1/16 in.)": key, "Calculated HRC": value}
            for key, value in sorted(((int(k), v) for k, v in dict(curve).items()), key=lambda item: item[0])
        ])
    elif calc_type == "DI_VALUE":
        factors = result_payload.get("factors") or {}
        sections["DI Factor Details"] = pd.DataFrame([{"Factor": key, "Value": value} for key, value in dict(factors).items()])
        sections["Calculated Result"] = {"Calculated DI": result_payload.get("value"), "Error": result_payload.get("error") or ""}
    elif calc_type == "HARDNESS_CONVERSION":
        sections["Hardness Conversion Result"] = {
            "Primary Value": f"{record.get('primary_value')} {record.get('primary_unit') or ''}".strip(),
            "Converted Value": f"{record.get('result_value')} {record.get('conversion_unit') or ''}".strip(),
            "Method": result_payload.get("method"),
            "Warning": result_payload.get("warning"),
            "Interpolation Bracket": result_payload.get("bracket"),
        }
    return controlled_record_pdf_bytes(
        "QC CALCULATION RECORD",
        header,
        sections,
        record_number=str(record.get("calculation_number") or ""),
        subtitle="Stored quality calculation result",
    )
