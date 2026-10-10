"""QCMS R16 print design options (for approval) - 2 designs per module."""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Table, TableStyle, Spacer, Image, NextPageTemplate, PageBreak, KeepTogether)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import sys

LOGO = sys.argv[1]; OUT = sys.argv[2]
W, H = A4
M = 12 * mm
CW = W - 2 * M
TEAL = colors.HexColor("#0B6E70"); GREY = colors.HexColor("#E6E9E9"); LINE = colors.HexColor("#4A4A4A"); LIGHT = colors.HexColor("#9AA5A5")

STYLES = {
    "A": dict(name="Design A · Clean Grid", body=10, label=9.5, head=10.5, row=20, head_bg=GREY, head_fg=colors.black, grid=True, title=15),
    "B": dict(name="Design B · Open Lines", body=10.5, label=9, head=10.5, row=22, head_bg=TEAL, head_fg=colors.white, grid=False, title=16),
}

def ps(size, bold=False, align=TA_LEFT, color=colors.black):
    return ParagraphStyle("x", fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size, leading=size * 1.25, alignment=align, textColor=color)

def P(t, size, bold=False, align=TA_LEFT, color=colors.black):
    return Paragraph(str(t), ps(size, bold, align, color))

# ---------------------------------------------------------------- building blocks
def header(st, title, docno, fmt):
    logo = Image(LOGO, width=30 * mm, height=14 * mm, kind="proportional")
    mid = [P("FOUR STAR INDUSTRIES PVT. LTD.", 12, True, TA_CENTER), P(title, st["title"], True, TA_CENTER)]
    right = Table([[P("Report No.", 8.5), P(docno, 9.5, True)], [P("Format", 8.5), P(fmt, 9.5)], [P("Rev / Date", 8.5), P("01 / 10-10-2026", 9.5)]],
                  colWidths=[18 * mm, 42 * mm])
    right.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    t = Table([[logo, mid, right]], colWidths=[36 * mm, CW - 36 * mm - 62 * mm, 62 * mm])
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (0, 0), "LEFT")]
    if st["grid"]:
        style += [("BOX", (0, 0), (-1, -1), 0.8, LINE), ("LINEAFTER", (0, 0), (1, 0), 0.5, LINE)]
    else:
        style += [("LINEBELOW", (0, 0), (-1, 0), 1.6, TEAL)]
    t.setStyle(TableStyle(style))
    return [t, Spacer(1, 4 * mm)]

def heading(st, text):
    t = Table([[P(text.upper(), st["head"], True, color=st["head_fg"])]], colWidths=[CW], rowHeights=[st["row"] - 2])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), st["head_bg"]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("LEFTPADDING", (0, 0), (-1, -1), 6)] + ([("BOX", (0, 0), (-1, -1), 0.6, LINE)] if st["grid"] else [])))
    return t

def kv(st, pairs, cols=2):
    rows, row = [], []
    for k, v in pairs:
        row += [P(k, st["label"], True), P(v, st["body"])]
        if len(row) == cols * 2:
            rows.append(row); row = []
    if row:
        row += [""] * (cols * 2 - len(row)); rows.append(row)
    lw = 34 * mm if cols == 2 else 28 * mm
    vw = (CW - cols * lw) / cols
    t = Table(rows, colWidths=[lw, vw] * cols, rowHeights=[st["row"]] * len(rows))
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 5)]
    if st["grid"]:
        style += [("GRID", (0, 0), (-1, -1), 0.5, LINE)]
    else:
        style += [("LINEBELOW", (0, 0), (-1, -1), 0.4, LIGHT)]
    t.setStyle(TableStyle(style)); return t

def table(st, headers, rows, widths, center_from=1, result_col=None):
    data = [[P(h, st["label"], True, TA_CENTER) for h in headers]]
    for r in rows:
        cells = []
        for i, v in enumerate(r):
            bold = result_col is not None and i == result_col
            cells.append(P(v, st["body"], bold, TA_LEFT if i < center_from else TA_CENTER))
        data.append(cells)
    total = sum(widths); widths = [w * CW / total for w in widths]
    t = Table(data, colWidths=widths, rowHeights=[st["row"] + 2] + [st["row"]] * len(rows), repeatRows=1)
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 2.5), ("RIGHTPADDING", (0, 0), (-1, -1), 2.5)]
    if st["grid"]:
        style += [("GRID", (0, 0), (-1, -1), 0.5, LINE)]
    else:
        style += [("LINEBELOW", (0, 0), (-1, 0), 1.0, colors.black), ("LINEBELOW", (0, 1), (-1, -1), 0.4, LIGHT), ("LINEABOVE", (0, 0), (-1, 0), 1.0, colors.black)]
    t.setStyle(TableStyle(style)); return t

def photos(st, captions, height=48 * mm):
    n = len(captions); w = CW / n
    boxes = [[Table([[P("[ photo ]", 9, False, TA_CENTER, LIGHT)]], colWidths=[w - 6], rowHeights=[height]) for _ in captions],
             [P(c, st["label"], True, TA_CENTER) for c in captions]]
    for b in boxes[0]:
        b.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LIGHT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    t = Table(boxes, colWidths=[w] * n)
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")] + ([("GRID", (0, 0), (-1, -1), 0.5, LINE)] if st["grid"] else [])))
    return t

def text(st, label, value):
    t = Table([[P(label, st["label"], True), P(value, st["body"])]], colWidths=[34 * mm, CW - 34 * mm], rowHeights=[st["row"] + 4])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")] + ([("GRID", (0, 0), (-1, -1), 0.5, LINE)] if st["grid"] else [("LINEBELOW", (0, 0), (-1, -1), 0.4, LIGHT)])))
    return t

def signs(st, names):
    w = CW / len(names)
    data = [[P("", 9) for _ in names], [P(n[0], st["label"], True, TA_CENTER) for n in names], [P(n[1], st["body"] - 1, False, TA_CENTER) for n in names]]
    t = Table(data, colWidths=[w] * len(names), rowHeights=[12 * mm, st["row"] - 4, st["row"] - 4])
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    style += [("GRID", (0, 0), (-1, -1), 0.5, LINE)] if st["grid"] else [("LINEABOVE", (0, 1), (-1, 1), 0.6, colors.black)]
    t.setStyle(TableStyle(style)); return t

def result_banner(st, text_):
    t = Table([[P(text_, 12, True, TA_CENTER)]], colWidths=[CW], rowHeights=[st["row"] + 4])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1.2, colors.black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return t

GAP = lambda: Spacer(1, 2.6 * mm)

# ---------------------------------------------------------------- module content
def dimensional(st):
    s = header(st, "DIMENSIONAL INSPECTION REPORT", "D9-DIR-2026-00112", "FSI/QA/F-12")
    s += [heading(st, "Report Details"), kv(st, [("Part Number", "40256626"), ("Part Name", "Yoke Forging"), ("FSI Part No.", "FSI-7237"), ("Drawing / Rev", "D-40256626 / C"),
          ("Customer", "Dana India Pvt. Ltd."), ("Supplier", "Bharat Forge Ltd."), ("Heat Number", "H-24578"), ("Batch / Lot Qty", "B-1167 / 1,200 pcs"),
          ("Inspection Date", "07-10-2026"), ("Sample Size", "5 pcs")]), GAP()]
    rows = [["1", "Overall Length", "120.00 ± 0.20", "119.80", "120.20", "120.05", "120.02", "119.98", "120.06", "120.01", "OK"],
            ["2", "Bore Diameter", "Ø 35.00 +0.03/0", "35.00", "35.03", "35.01", "35.02", "35.01", "35.02", "35.01", "OK"],
            ["3", "Flange Thickness", "12.00 ± 0.10", "11.90", "12.10", "12.03", "11.98", "12.04", "12.01", "11.99", "OK"],
            ["4", "Hole PCD", "Ø 80.00 ± 0.05", "79.95", "80.05", "80.01", "80.02", "79.99", "80.00", "80.03", "OK"],
            ["5", "Bend / Flatness", "0.10 max", "0.00", "0.10", "0.04", "0.05", "0.03", "0.06", "0.04", "OK"],
            ["6", "Hole ID", "GO / NO-GO gauge", "-", "-", "OK", "OK", "OK", "OK", "OK", "OK"],
            ["7", "Batch Code Marking", "Visual", "-", "-", "OK", "OK", "OK", "OK", "OK", "OK"]]
    s += [heading(st, "Inspection Results"), table(st, ["Sr", "Characteristic", "Specification", "Min", "Max", "1", "2", "3", "4", "5", "Result"], rows, [7, 34, 32, 13, 13, 13, 13, 13, 13, 13, 12], center_from=3, result_col=10), GAP()]
    s += [heading(st, "Decision"), kv(st, [("Accepted Qty", "1,200 pcs"), ("Rejected Qty", "0"), ("Decision", "ACCEPTED"), ("Remarks", "All characteristics within limits")]), GAP()]
    s += [signs(st, [("Prepared By", "Akshay Bharambe · 07-10-2026"), ("Validated By", "Nitin Nanavare · 07-10-2026"), ("Approved By", "Nitin Nanavare · 08-10-2026")])]
    return s

def metlab(st):
    s = header(st, "METALLURGICAL LABORATORY REPORT", "MLAB-D9-26-00145", "FSI/QA/F-21")
    s += [heading(st, "Material Details"), kv(st, [("Part Number", "40256626"), ("Part Name", "Yoke Forging"), ("Material Grade", "20MnCr5 (EN 10084)"), ("Heat Number", "H-24578"),
          ("Supplier", "Bharat Forge Ltd."), ("Steel Mill", "JSW Steel"), ("Heat Treatment", "Case Carburising"), ("Test Date", "07-10-2026")]), GAP()]
    chem = [["C %", "0.17 - 0.22", "0.19", "OK"], ["Mn %", "1.10 - 1.40", "1.24", "OK"], ["Si %", "0.15 - 0.40", "0.26", "OK"], ["Cr %", "1.00 - 1.30", "1.12", "OK"], ["S % / P %", "0.035 / 0.025 max", "0.021 / 0.014", "OK"]]
    s += [heading(st, "Chemical Composition"), table(st, ["Element", "Specification", "Actual", "Result"], chem, [25, 35, 25, 15], result_col=3), GAP()]
    mech = [["Surface Hardness", "58 - 62 HRC", "60 / 61 / 60", "OK"], ["Core Hardness", "30 - 42 HRC", "36", "OK"], ["Effective Case Depth @ 550 HV", "0.80 - 1.10 mm", "0.95 mm", "OK"],
            ["Grain Size (ASTM E112)", "5 or finer", "7", "OK"], ["Microstructure", "Tempered martensite", "Tempered martensite + fine carbides", "OK"]]
    s += [heading(st, "Mechanical & Metallurgical Properties"), table(st, ["Parameter", "Specification", "Observed", "Result"], mech, [32, 26, 30, 12], result_col=3), GAP()]
    s += [heading(st, "Microstructure Photographs"), photos(st, ["Case 500X", "Core 500X", "Case depth traverse"], 27 * mm), GAP()]
    s += [result_banner(st, "RESULT: ACCEPTED"), GAP(), signs(st, [("Tested By", "Lab Technician"), ("Verified By", "Lab Incharge"), ("Approved By", "QA Head")])]
    return s

def rmtc(st):
    s = header(st, "RAW MATERIAL TEST CERTIFICATE EVALUATION", "RMTC-2026-00342", "FSI/QA/F-05")
    s += [heading(st, "Certificate Details"), kv(st, [("Supplier", "JSW Steel Ltd."), ("Mill TC No.", "JSW/TC/88412"), ("Heat Number", "H-24578"), ("Grade", "20MnCr5"),
          ("Section / Size", "RCS 120 mm"), ("Quantity", "18.450 MT"), ("Invoice / Date", "INV-5521 / 02-10-2026"), ("Applicable Parts", "40256626, 40256630")]), GAP()]
    chem = [["C %", "0.17", "0.22", "0.19", "0.19", "OK"], ["Mn %", "1.10", "1.40", "1.24", "1.23", "OK"], ["Si %", "0.15", "0.40", "0.26", "0.27", "OK"], ["Cr %", "1.00", "1.30", "1.12", "1.13", "OK"],
            ["S %", "-", "0.035", "0.021", "0.020", "OK"], ["P %", "-", "0.025", "0.014", "0.015", "OK"], ["Al %", "0.020", "0.050", "0.031", "0.030", "OK"]]
    s += [heading(st, "Chemical Analysis - Mill vs Specification"), table(st, ["Element", "Min", "Max", "Mill TC", "FSI Check", "Result"], chem, [20, 14, 14, 18, 18, 16], result_col=5), GAP()]
    phys = [["Hardness (Annealed)", "≤ 207 HB", "187 HB", "OK"], ["Grain Size", "5 or finer", "6", "OK"], ["Inclusion Rating", "As per IS 4163", "A1 B1 C0 D1", "OK"], ["Jominy J9", "34 - 42 HRC", "38", "OK"], ["Ultrasonic Test", "SEP 1921 C/c", "Passed", "OK"]]
    s += [heading(st, "Physical / Cleanliness"), table(st, ["Test", "Specification", "Actual", "Result"], phys, [32, 28, 26, 14], result_col=3), GAP()]
    s += [heading(st, "Decision"), kv(st, [("Decision", "ACCEPTED"), ("Released Qty", "18.450 MT"), ("Remarks", "Heat released for forging"), ("Valid For", "All listed parts")]), GAP()]
    s += [signs(st, [("Prepared By", "QA Engineer"), ("Verified By", "QA Manager"), ("Approved By", "Plant Head")])]
    return s

def bend(st):
    s = header(st, "BEND TEST REPORT", "1006/2026/7237", "FSI/QA/F-34")
    s += [heading(st, "Report Details"), kv(st, [("Part #", "D9OV-1167"), ("Part Name", "U-Bolt"), ("Customer", "KO"), ("Material Used", "SAE 1541"), ("Baking Batch No.", "BK-0925"), ("Batch Quantity", "2,400 pcs"),
          ("Steel Heat Code", "H-24578"), ("Part Diameter", "Ø 16 mm"), ("FSI Batch No.", "FSI-B-7237"), ("HT Batch No.", "HT-1185")]), GAP()]
    bake = [["Baking Temperature", "400 °C / as approved process", "405 °C", "OK"], ["Baking Time", "60 minutes minimum", "75 min", "OK"], ["Hardness", "45 - 52 HRC (avg of 3)", "48 / 49 / 48", "OK"]]
    s += [heading(st, "Baking / Ageing"), table(st, ["Parameter", "Specification", "Actual", "Result"], bake, [26, 36, 24, 14], result_col=3), GAP()]
    res = [["Load Vs Cross Head Travel", "Record", "38.6 kN @ 42 mm", "Passed"], ["Included Bend Angle", "Record", "171°", "Passed"], ["Plating Surface", "No peeling / flaking", "No peeling, no flaking", "Passed"]]
    s += [heading(st, "Bend Test Results"), table(st, ["Test", "Requirement", "Observed", "Status"], res, [30, 26, 30, 14], result_col=3), GAP()]
    s += [heading(st, "Bend Test Photographs"), photos(st, ["Load Vs CHT graph", "Bent part", "Plating close-up"], 46 * mm), GAP()]
    s += [text(st, "Conclusion", "Part bent to 171° included angle without crack, peeling or flaking. Batch ACCEPTED."), GAP()]
    s += [signs(st, [("Prepared By", "Metallurgist"), ("Verified & Approved By", "QA Head")])]
    return s

def osp(st):
    s = header(st, "OSP INSPECTION REPORT · POST-RECEIPT", "D9-OSP-2026-00058", "FSI/QA/F-41")
    s += [heading(st, "OSP Batch Details"), kv(st, [("OSP Job No.", "OSP-D9-2026-00058"), ("Process", "Zinc Flake Coating"), ("Vendor", "Surface Tech Pvt. Ltd."), ("Vendor Batch", "ST-9921"),
          ("Part Number", "40256626"), ("FSI Batch", "FSI-B-7237"), ("Heat Number", "H-24578"), ("Qty Received", "1,200 pcs")]), GAP()]
    rows = [["1", "Coating Thickness", "8 - 12 µm", "8", "12", "10.2", "OK"], ["2", "Adhesion (Cross-cut)", "GT0 / GT1", "-", "-", "GT0", "OK"], ["3", "Salt Spray", "720 h no red rust", "-", "-", "Passed (lab)", "OK"],
            ["4", "Appearance", "Uniform silver, no bare spots", "-", "-", "OK", "OK"], ["5", "Thread Gauge", "GO / NO-GO", "-", "-", "OK", "OK"]]
    s += [heading(st, "Process-Specific Parameters"), table(st, ["Sr", "Parameter", "Specification", "Min", "Max", "Actual", "Result"], rows, [5, 24, 27, 9, 9, 15, 11], center_from=3, result_col=6), GAP()]
    gate = [["Sample Dimensional", "Finalized · Accepted"], ["Sample MetLAB", "Finalized · Accepted"], ["Receipt Dimensional", "Finalized · Accepted"], ["Receipt MetLAB", "Finalized · Accepted"]]
    s += [heading(st, "OSP Quality Gate"), table(st, ["Gate Report", "Status"], gate, [50, 50], center_from=1), GAP()]
    s += [result_banner(st, "OSP BATCH RELEASED"), GAP(), signs(st, [("Prepared By", "Inspector"), ("Validated By", "QA Engineer"), ("Approved By", "QA Manager")])]
    return s

MODULES = [("Dimensional Inspection Report", dimensional), ("MetLAB Report", metlab), ("RMTC Evaluation", rmtc), ("Bend Test Report", bend), ("OSP Inspection Report", osp)]

# ---------------------------------------------------------------- document
def on_page(canvas, doc):
    label = getattr(doc, "_label", "")
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.drawString(M, 7 * mm, "QCMS · Four Star Industries · Controlled copy when printed from QCMS")
    canvas.drawRightString(W - M, 7 * mm, f"Page {doc.page}")
    if label:
        canvas.setFillColor(colors.HexColor("#C0392B")); canvas.setFont("Helvetica-Bold", 9)
        canvas.drawRightString(W - M, H - 7 * mm, label)
    canvas.restoreState()

class Doc(BaseDocTemplate):
    def handle_flowable(self, flowables):
        f = flowables[0]
        if hasattr(f, "_qcms_label"):
            self._label = f._qcms_label
        return super().handle_flowable(flowables)

class Marker(Spacer):
    def __init__(self, label):
        super().__init__(0, 0); self._qcms_label = label

doc = Doc(OUT, pagesize=A4, leftMargin=M, rightMargin=M, topMargin=11 * mm, bottomMargin=13 * mm, title="QCMS Print Design Options R16")
doc.addPageTemplates([PageTemplate("p", [Frame(M, 13 * mm, CW, H - 24 * mm, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=on_page)])
story = [Marker(""), Spacer(1, 30 * mm), P("QCMS PRINT DESIGN OPTIONS", 22, True, TA_CENTER), Spacer(1, 6 * mm), P("For approval · R16 · 10-10-2026", 12, False, TA_CENTER), Spacer(1, 14 * mm)]
info = [["Rule", "Design A · Clean Grid", "Design B · Open Lines"],
        ["Background colour", "None. Only section headings: light grey band", "None. Only section headings: teal band, white text"],
        ["Lines", "Full black grid on every table", "Horizontal lines only, no vertical lines"],
        ["Body font", "10 pt (was 5.5 - 7 pt)", "10.5 pt"],
        ["Row height", "20 pt (about 7 mm)", "22 pt (about 8 mm)"],
        ["Look", "Traditional QA form, easy to audit", "Modern, airy, easier to read on screen"]]
t = Table([[P(c, 10, i == 0 or j == 0) for j, c in enumerate(r)] for i, r in enumerate(info)], colWidths=[40 * mm, (CW - 40 * mm) / 2, (CW - 40 * mm) / 2], rowHeights=[22] * len(info))
t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BACKGROUND", (0, 0), (-1, 0), GREY)]))
story += [t, Spacer(1, 10 * mm)]
idx = [[P("Page", 10, True), P("Module", 10, True), P("Design", 10, True)]]
page = 2
for name, _ in MODULES:
    for key in "AB":
        idx.append([P(str(page), 10), P(name, 10), P(STYLES[key]["name"], 10)]); page += 1
t = Table(idx, colWidths=[18 * mm, 80 * mm, CW - 98 * mm], rowHeights=[18] * len(idx))
t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LIGHT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
story += [t, Spacer(1, 8 * mm), P("Reply with your choice per module, e.g. <b>Dimensional A, MetLAB B, RMTC A, Bend B, OSP A</b> — or one design for all.", 11, False, TA_CENTER)]
for name, fn in MODULES:
    for key in "AB":
        story += [Marker(f"{name} · {STYLES[key]['name']}"), PageBreak()] + fn(STYLES[key])
doc.build(story)
print("ok", OUT)
