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
    table = Table(prepared, colWidths=widths, repeatRows=header_rows, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, header_rows - 1), WHITE),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#6E8294")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.0),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("ROWBACKGROUNDS", (0, header_rows), (-1, -1), [WHITE, LIGHT_BLUE]),
    ]
    for row_index, row in enumerate(rows[header_rows:], start=header_rows):
        for col_index in status_columns:
            if col_index < len(row):
                commands.append(("BACKGROUND", (col_index, row_index), (col_index, row_index), _table_status_color(row[col_index])))
    table.setStyle(TableStyle(commands))
    return table


def rmtc_record_pdf_bytes(payload: Mapping[str, object]) -> bytes:
    """Create a controlled RMTC Record PDF with header, worksheets and validation grids."""
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

    buffer = BytesIO()
    title = f"RMTC RECORD - {record.get('rmtc_number') or 'QUALITY RECORD'}"
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
        "RmtcSection", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=9, leading=11, textColor=WHITE, backColor=NAVY,
        leftIndent=4, rightIndent=4, spaceBefore=4, spaceAfter=5,
        borderPadding=(4, 5, 4, 5),
    )
    sub_style = ParagraphStyle(
        "RmtcSub", parent=styles["Heading3"], fontName="Helvetica-Bold",
        fontSize=8, leading=10, textColor=NAVY, spaceBefore=4, spaceAfter=4, keepWithNext=1,
    )
    header_style = ParagraphStyle(
        "RmtcHeaderCell", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=6.2, leading=7.5, textColor=WHITE, alignment=TA_CENTER,
    )
    cell_style = ParagraphStyle(
        "RmtcCell", parent=styles["Normal"], fontName="Helvetica",
        fontSize=6.1, leading=7.4, textColor=TEXT, alignment=TA_LEFT,
    )
    label_style = ParagraphStyle(
        "RmtcLabel", parent=cell_style, fontName="Helvetica-Bold", textColor=NAVY,
    )
    center_style = ParagraphStyle(
        "RmtcCenter", parent=cell_style, alignment=TA_CENTER,
    )

    width = landscape(A4)[0] - 20 * mm
    story: list[object] = []

    story.append(Paragraph("RMTC HEADER & TRACEABILITY", section_style))
    header_pairs = [
        ("QSMS RMTC Number", record.get("rmtc_number"), "Entry Date", record.get("entry_date")),
        ("Supplier RMTC Number", record.get("certificate_reference"), "RMTC Date", record.get("certificate_date")),
        ("Supplier", supplier.get("party_name"), "Steel Mill", steel_mill.get("party_name")),
        ("Heat Number", record.get("heat_number"), "Internal Heat Code", record.get("heat_code")),
        ("Global Heat Steel Quantity (kg)", record.get("certificate_quantity"), "RM Section", record.get("rm_section")),
        ("Forging Route / Root", record.get("forging_route"), "Prepared By", _employee_name(employees.get(str(record.get("prepared_by_employee_id"))))),
        ("Workflow Status", record.get("status"), "Validation Result", record.get("validation_result")),
        ("Final Disposition", record.get("disposition"), "Decision Date", record.get("decision_at")),
    ]
    hp_data: list[list[Paragraph]] = []
    for left_label, left_value, right_label, right_value in header_pairs:
        hp_data.append([
            _paragraph(left_label, label_style), _paragraph(_display_value(left_value), cell_style),
            _paragraph(right_label, label_style), _paragraph(_display_value(right_value), cell_style),
        ])
    header_table = Table(hp_data, colWidths=[38 * mm, 92 * mm, 38 * mm, width - 168 * mm])
    header_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#8295A6")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EDF4FA")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#EDF4FA")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(header_table)
    if str(record.get("remarks") or "").strip():
        story.append(Spacer(1, 2 * mm))
        remarks = Table([
            [_paragraph("RMTC Remarks", label_style), _paragraph(record.get("remarks"), cell_style)]
        ], colWidths=[38 * mm, width - 38 * mm])
        remarks.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#8295A6")),
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#EDF4FA")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(remarks)

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("COVERED PART WORKSHEET REGISTER", section_style))
    part_summary = [[
        "Part Number", "Part Description", "Material Grade", "Planned Qty pcs", "Input Wt kg",
        "Planned Steel kg", "Worksheet", "Automated Validation", "Final Decision",
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
        [22*mm, 42*mm, 23*mm, 23*mm, 20*mm, 24*mm, 21*mm, 29*mm, 27*mm],
        header_style, cell_style, status_columns=(6, 7, 8),
    ))

    mechanical = record.get("mechanical_results") or {}
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("SUPPLIER RMTC MECHANICAL PROPERTIES", section_style))
    mech_rows = [["Property", "Actual / Result", "Source"]]
    if isinstance(mechanical, Mapping) and mechanical:
        for key, value in mechanical.items():
            mech_rows.append([str(key).replace("_", " ").title(), value, "Supplier RMTC"])
    else:
        mech_rows.append(["Mechanical Properties", "No dedicated mechanical property values recorded", "Supplier RMTC"])
    story.append(_rmtc_grid(mech_rows, [72*mm, 105*mm, width - 177*mm], header_style, cell_style))

    for worksheet_index, approval in enumerate(part_approvals, start=1):
        story.append(PageBreak())
        part_id = str(approval.get("part_id") or "")
        part = parts.get(part_id) or {}
        grade = grades.get(str(part.get("material_grade_id"))) or {}
        part_title = f"PART WORKSHEET {worksheet_index} - {part.get('part_number') or '-'} - {part.get('part_name') or ''}"
        story.append(Paragraph(part_title, section_style))

        identity_rows = [
            ["Part Number", part.get("part_number"), "Part Description", part.get("part_name"), "Material Grade", grade.get("grade_code") or grade.get("grade_name")],
            ["Heat Number", record.get("heat_number"), "Heat Code", record.get("heat_code"), "Worksheet Status", "Completed" if approval.get("worksheet_completed_at") else "Pending"],
            ["Planned Production Qty pcs", approval.get("planned_production_quantity_pcs"), "Input Weight kg", approval.get("input_weight_kg"), "Planned Steel kg", approval.get("planned_steel_quantity_kg")],
        ]
        identity_prepared = []
        for row in identity_rows:
            identity_prepared.append([
                _paragraph(row[0], label_style), _paragraph(_display_value(row[1]), cell_style),
                _paragraph(row[2], label_style), _paragraph(_display_value(row[3]), cell_style),
                _paragraph(row[4], label_style), _paragraph(_display_value(row[5]), cell_style),
            ])
        ident = Table(identity_prepared, colWidths=[30*mm, 52*mm, 34*mm, 65*mm, 30*mm, width - 211*mm])
        ident.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#8295A6")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EDF4FA")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#EDF4FA")),
            ("BACKGROUND", (4, 0), (4, -1), colors.HexColor("#EDF4FA")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3.2), ("RIGHTPADDING", (0, 0), (-1, -1), 3.2),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        story.append(ident)

        part_chem = [row for row in chemistry if str(row.get("part_id")) == part_id]
        story.append(Paragraph("Chemical Composition", sub_style))
        chem_rows = [["Element", "Minimum", "Maximum", "Actual", "Unit", "Status"]]
        for row in part_chem:
            chem_rows.append([row.get("element"), row.get("minimum_value"), row.get("maximum_value"), row.get("actual_value"), row.get("unit") or "%", row.get("result")])
        if len(chem_rows) == 1:
            chem_rows.append(["-", "", "", "No chemistry values recorded", "", "NOT_EVALUATED"])
        story.append(_rmtc_grid(chem_rows, [31*mm, 37*mm, 37*mm, 42*mm, 28*mm, width-175*mm], header_style, cell_style, status_columns=(5,)))

        part_jominy = [row for row in jominy if str(row.get("part_id")) == part_id]
        story.append(Paragraph("Jominy Results", sub_style))
        j_rows = [["Distance", "mm", "Min HRC", "Max HRC", "Actual", "Actual Status", "Calculated", "Calculated Status", "Applicable"]]
        for row in part_jominy:
            j_rows.append([
                row.get("distance_label"), row.get("distance_mm"), row.get("minimum_hrc"), row.get("maximum_hrc"),
                row.get("actual_hrc"), row.get("result"), row.get("calculated_hrc"), row.get("calculated_result"),
                "No" if str(row.get("applicability")) == "NOT_APPLICABLE" else "Yes",
            ])
        if len(j_rows) == 1:
            j_rows.append(["-", "", "", "", "", "NOT_EVALUATED", "", "NOT_EVALUATED", "No"])
        story.append(_rmtc_grid(j_rows, [24*mm, 20*mm, 22*mm, 22*mm, 24*mm, 30*mm, 27*mm, 34*mm, width-203*mm], header_style, cell_style, status_columns=(5, 7)))

        story.append(Paragraph("DI / Hardenability", sub_style))
        di_rows = [["Grain Size ASTM E-112", "Actual DI", "Actual DI Status", "Calculated DI", "Calculated DI Status"]]
        di_rows.append([approval.get("grain_size"), approval.get("actual_di"), approval.get("actual_di_status"), approval.get("calculated_di"), approval.get("calculated_di_status")])
        story.append(_rmtc_grid(di_rows, [48*mm, 45*mm, 55*mm, 45*mm, width-193*mm], header_style, cell_style, status_columns=(2, 4)))

        part_req = [row for row in requirements if str(row.get("part_id")) == part_id]
        mechanical_tokens = ("tensile", "yield", "elongation", "reduction", "impact", "proof", "mechanical", "uts")
        mech_req = [row for row in part_req if any(token in str(row.get("requirement_name") or row.get("requirement_code") or "").casefold() for token in mechanical_tokens)]
        other_req = [row for row in part_req if row not in mech_req]

        story.append(Paragraph("Mechanical Properties", sub_style))
        mech_part_rows = [["Property", "Specification", "Actual / Observation", "Unit", "Status", "Remarks"]]
        for row in mech_req:
            mech_part_rows.append([row.get("requirement_name") or row.get("requirement_code"), row.get("requirement_value"), row.get("actual_value"), row.get("unit"), row.get("result"), row.get("remarks")])
        if len(mech_part_rows) == 1:
            mech_part_rows.append(["Mechanical Properties", "As supplier RMTC / Part requirement", "No separate part-level mechanical property row", "", "NOT_EVALUATED", ""])
        story.append(_rmtc_grid(mech_part_rows, [55*mm, 67*mm, 67*mm, 24*mm, 28*mm, width-241*mm], header_style, cell_style, status_columns=(4,)))

        story.append(Paragraph("Heat Treatment & Other Requirements", sub_style))
        req_rows = [["Requirement", "Specification / Part Master", "RMTC Actual / Observation", "Unit", "Status", "Remarks"]]
        for row in other_req:
            req_rows.append([row.get("requirement_name") or row.get("requirement_code"), row.get("requirement_value"), row.get("actual_value"), row.get("unit"), row.get("result"), row.get("remarks")])
        if len(req_rows) == 1:
            req_rows.append(["-", "No additional requirements recorded", "", "", "NOT_EVALUATED", ""])
        story.append(_rmtc_grid(req_rows, [56*mm, 68*mm, 69*mm, 22*mm, 28*mm, width-243*mm], header_style, cell_style, status_columns=(4,)))

    story.append(PageBreak())
    story.append(Paragraph("RMTC VALIDATION STATUS & FINAL DECISION", section_style))
    validation_rows = [[
        "Part Number", "Source", "Material Grade", "Raw Material", "Chemistry", "Jominy", "Requirements",
        "Actual DI", "Calculated DI", "Automated Recommendation", "Final Decision", "Decision / Reserve Reason",
    ]]
    for approval in part_approvals:
        part = parts.get(str(approval.get("part_id"))) or {}
        validation_rows.append([
            part.get("part_number"), approval.get("source_status"), approval.get("material_grade_status"), approval.get("raw_material_status"),
            approval.get("chemistry_status"), approval.get("jominy_status"), approval.get("requirement_status"), approval.get("actual_di_status"),
            approval.get("calculated_di_status"), approval.get("approval_status"), approval.get("disposition"), approval.get("decision_reason"),
        ])
    if len(validation_rows) == 1:
        validation_rows.append(["-", "NOT_EVALUATED", "NOT_EVALUATED", "NOT_EVALUATED", "NOT_EVALUATED", "NOT_EVALUATED", "NOT_EVALUATED", "NOT_EVALUATED", "NOT_EVALUATED", "NOT_EVALUATED", "PENDING", ""])
    story.append(_rmtc_grid(
        validation_rows,
        [18*mm, 18*mm, 20*mm, 20*mm, 18*mm, 18*mm, 20*mm, 18*mm, 22*mm, 26*mm, 22*mm, width-220*mm],
        header_style, cell_style, status_columns=tuple(range(1, 11)),
    ))

    story.append(Spacer(1, 5 * mm))
    sign_rows = [[
        "Prepared By", _employee_name(employees.get(str(record.get("prepared_by_employee_id")))),
        "Validated By", _employee_name(employees.get(str(record.get("validated_by_employee_id")))),
        "Approved / Decided By", _employee_name(employees.get(str(record.get("approved_by_employee_id") or record.get("decision_by_employee_id")))),
    ], [
        "Prepared At", _display_value(record.get("prepared_at")),
        "Validated At", _display_value(record.get("validated_at")),
        "Decision At", _display_value(record.get("decision_at") or record.get("approved_at")),
    ]]
    sign_prepared = []
    for row in sign_rows:
        sign_prepared.append([
            _paragraph(row[0], label_style), _paragraph(row[1], center_style),
            _paragraph(row[2], label_style), _paragraph(row[3], center_style),
            _paragraph(row[4], label_style), _paragraph(row[5], center_style),
        ])
    sign_table = Table(sign_prepared, colWidths=[28*mm, 60*mm, 28*mm, 60*mm, 36*mm, width-212*mm])
    sign_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#8295A6")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EDF4FA")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#EDF4FA")),
        ("BACKGROUND", (4, 0), (4, -1), colors.HexColor("#EDF4FA")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(sign_table)

    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: _PageNumberCanvas(*args, report_title=title, **kwargs),
    )
    return buffer.getvalue()
