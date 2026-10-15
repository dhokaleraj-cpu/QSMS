"""R33: website print-layout PDFs in the Android app, full report on the record, Reports / Records Centre,
global search bar, About page (app + website) and the OSP Material Out register fix."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mobile/android_qcms_app/app/src/main/java/com/fourstar/qcmsapp"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_report_builders_cover_every_website_layout():
    rep = read(SRC / "RptReports.java")
    for fn in ("static RptDoc metlab(", "static RptDoc bend(", "static RptDoc dimensional(", "static RptDoc inward(", "static RptDoc rmtc(",
               "static RptDoc complaint(", "static RptDoc calibration(", "static RptDoc standardRoom(", "static RptDoc qcCalculation(",
               "static RptDoc universal(", "static RptDoc register("):
        assert fn in rep, fn
    for title in ("RAW MATERIAL METALLURGICAL TEST REPORT", "METALLURGICAL LABORATORY - BEND TEST REPORT", "FINAL INSPECTION / DIMENSIONAL REPORT",
                  "MATERIAL INWARD INSPECTION RECORD", "RMTC HEADER & TRACEABILITY", "DETAILED COMPLAINT ANALYSIS RECORD",
                  "CASE DEPTH / MICROHARDNESS TRAVERSE", "CHEMICAL ANALYSIS · ASTM E 415 / IS 8811", "MICROSTRUCTURE PHOTOGRAPHS"):
        assert title in rep, title
    web = read(ROOT / "core/reporting.py")
    for title in ("RAW MATERIAL METALLURGICAL TEST REPORT", "MATERIAL INWARD INSPECTION RECORD", "RMTC HEADER & TRACEABILITY"):
        assert title in web


def test_pdf_engine_matches_website_header_footer():
    pdf = read(SRC / "RptPdf.java")
    assert 'WEB_VERSION = "4.14.49"' in pdf and (ROOT / "VERSION").read_text().strip() == "4.14.49"
    assert "Copyrights by STAWN" in pdf and "Page \" + pageNo + \" of \"" in pdf
    assert "HEAT NUMBER: " in pdf and "RMTC NUMBER: " in pdf and "Plant: " in pdf and "App Version: " in pdf
    assert "AdmPrint.read(api, doc)" in read(SRC / "RptReports.java")   # Print Layout Designer theme applies


def test_record_screen_shows_full_report_and_layout_pdf():
    rec = read(SRC / "RecordScreen.java")
    assert "Print layout PDF" in rec and "RptView.build(a, doc)" in rec and '"lab_tests", "inspection_reports", "rmtc_approvals", "inward_lots"' in rec
    kit = read(SRC / "ExportKit.java")
    for item in ("View PDF", "Download PDF", "Print", "Email from QCMS (PDF attached)", "Share PDF"):
        assert item in kit


def test_centres_search_and_about():
    gen = read(SRC / "CatGeneral.java")
    assert '"reports_centre"' in gen and '"records_centre"' in gen and '"about"' in gen
    main = read(SRC / "MainActivity.java")
    assert "searchRow" in main and "new GenSearchScreen(this, q)" in main
    about = read(SRC / "GenCentres.java")
    assert "STAWN PRECISION PRIVATE LIMITED" in about and "Copyright Act, 1957" in about
    from core import about as web_about
    assert web_about.COMPANY == "STAWN PRECISION PRIVATE LIMITED"
    assert '("about", st.Page(about_page.render' in read(ROOT / "streamlit_app.py")
    assert './about' in read(ROOT / "core/ui.py")


def test_osp_material_out_register_does_not_select_missing_status():
    ins = read(SRC / "CatInspection.java")
    assert 'titleField("material_out_number").status("")' in ins
