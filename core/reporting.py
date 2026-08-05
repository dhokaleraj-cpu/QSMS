from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Mapping

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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
    def __init__(self, *args, report_title: str, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self._report_title = report_title

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

    def _draw_header_footer(self, page_count: int) -> None:
        width, height = landscape(A4)
        settings = get_settings()

        # Header theme follows the approved Export Shipment screen style.
        self.setFillColor(NAVY)
        self.roundRect(10 * mm, height - 29 * mm, width - 20 * mm, 19 * mm, 4 * mm, fill=1, stroke=0)
        self.setFillColor(BLUE)
        self.roundRect(width - 73 * mm, height - 29 * mm, 63 * mm, 19 * mm, 4 * mm, fill=1, stroke=0)

        logo = _logo_path()
        if logo.exists():
            self.setFillColor(WHITE)
            self.roundRect(14 * mm, height - 26.5 * mm, 24 * mm, 14 * mm, 2.2 * mm, fill=1, stroke=0)
            try:
                self.drawImage(str(logo), 16 * mm, height - 24.8 * mm, 20 * mm, 10.5 * mm, preserveAspectRatio=True, mask="auto")
            except Exception:
                pass

        self.setFillColor(WHITE)
        self.setFont("Helvetica-Bold", 10)
        self.drawString(41 * mm, height - 17.2 * mm, "FOUR STAR INDUSTRIES")
        self.setFont("Helvetica", 6.8)
        self.drawString(41 * mm, height - 22.0 * mm, "QUALITY SYSTEM MONITORING SYSTEM")

        self.setFont("Helvetica-Bold", 13)
        self.drawCentredString(width / 2, height - 18.0 * mm, self._report_title[:72])

        self.setFont("Helvetica-Bold", 7)
        self.drawRightString(width - 15 * mm, height - 16.0 * mm, f"Plant: {settings.plant_code}")
        self.setFont("Helvetica", 6.5)
        self.drawRightString(width - 15 * mm, height - 20.5 * mm, datetime.now().strftime("Printed: %d-%m-%Y %I:%M %p"))
        self.drawRightString(width - 15 * mm, height - 24.5 * mm, f"QSMS {settings.version}")

        # Footer with page count on every page.
        self.setStrokeColor(BORDER)
        self.line(10 * mm, 10.5 * mm, width - 10 * mm, 10.5 * mm)
        self.setFillColor(MUTED)
        self.setFont("Helvetica", 6.5)
        self.drawString(11 * mm, 6.7 * mm, "FOUR STAR INDUSTRIES · CONTROLLED QSMS REPORT")
        self.drawCentredString(width / 2, 6.7 * mm, "Generated from the live Supabase quality database")
        self.drawRightString(width - 11 * mm, 6.7 * mm, f"Page {self._pageNumber} of {page_count}")


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
        author="Four Star Industries QSMS",
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
