"""R17: print Design B everywhere, coloured conclusion/remarks, default email server only, KPI Dashboards first."""
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from core import reporting as r

ROOT = Path(__file__).resolve().parents[1]


def test_design_b_helpers_use_lines_not_fills():
    from reportlab.lib.styles import ParagraphStyle
    st = r._controlled_styles()
    assert st["cell"].fontSize >= 8.5 and st["section"].fontSize >= 10
    grid = r._rmtc_grid([["Sr", "Parameter", "Result", "Remarks"], ["1", "Hardness", "PASS", "3 readings"]], [20, 60, 30, 60], st["header"], st["small"], status_columns=(2,))
    cmds = [c[0] for c in grid._bkgrndcmds] if hasattr(grid, "_bkgrndcmds") else []
    assert "BACKGROUND" not in cmds and "ROWBACKGROUNDS" not in cmds
    assert grid._cellvalues[1][2].style.textColor == r.STATUS_TEXT["good"]
    assert grid._cellvalues[1][3].style.textColor == r.REMARK_COLOR
    concl = r._quality_conclusion_table(conclusion="OK", conclusion_remark="Retest not required", final_decision="ACCEPTED", decision_reason="", content_width=180, styles=st)
    assert concl._cellvalues[0][1].style.textColor == r.CONCLUSION_COLOR
    assert concl._cellvalues[1][1].style.textColor == r.REMARK_COLOR


def test_reports_render_with_white_header():
    src = (ROOT / "core/reporting.py").read_text()
    assert "R17 Design B header" in src and "self.roundRect(edge, header_y" not in src
    pdf = r.dimensional_record_pdf_bytes({"record": {"report_number": "DIM-1", "inspection_date": "2026-10-07", "disposition": "ACCEPTED", "remarks": "All OK"}, "part": {"part_number": "P1"}, "employees": {}, "results": []})
    text = PdfReader(BytesIO(pdf)).pages[0].extract_text()
    assert "Conclusion" in text and "All OK" in text and "FOUR STAR INDUSTRIES" in text


def test_email_uses_default_server_only():
    page = (ROOT / "app_pages/email_center.py").read_text()
    assert "mode = COMPANY_MODE" in page and "st.radio(\"Send using\"" not in page
    assert "Sign in with Microsoft" not in page
    settings = (ROOT / "app_pages/system_settings.py").read_text()
    assert "EMAIL MODULE · DEFAULT EMAIL SERVER" in settings and "MICROSOFT 365 SIGN-IN FOR EMAIL" not in settings


def test_kpi_dashboards_is_first_page():
    app = (ROOT / "streamlit_app.py").read_text()
    line = next(l for l in app.splitlines() if 'st.Page(kpi_dashboards.render' in l)
    assert "default=True" in line and app.count("default=True") == 1
    assert app.index('(PAGE_BY_PATH["kpi-dashboards"], "KPIs", "KPI Dashboards")') < app.index('(PAGE_BY_PATH["dashboard"], "Home", "Dashboard")')
