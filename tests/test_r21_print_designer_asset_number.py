"""R21: approved B5 PO + L1 login, Print Layout Designer (design selector + editor), Asset Number."""
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def test_b5_is_default_and_l1_login():
    from core import purchase_order_reporting as por
    from core.print_designer import default_layout
    assert por.DEFAULT_PO_DESIGN == "B5" and default_layout("PURCHASE_ORDER")["label_fill"] == "#F3F8F8"
    assert 'COMPANY_LEGAL_NAME = "FOUR STAR INDUSTRIES PRIVATE LIMITED"' in (ROOT / "core/auth.py").read_text()


def test_layout_normalize_validates_and_keeps_report_design_b():
    from core.print_designer import normalize_layout, relabel
    lay = normalize_layout("PURCHASE_ORDER", {"preset": "B2", "accent": "#112233", "rule": "red", "body_pt": 99, "labels": {"VENDOR": "SUPPLIER", "X": ""}, "show_technical": 0})
    assert lay["bar"] == "underline" and lay["accent"] == "#112233" and lay["rule"] == "#C9D6D6"
    assert lay["labels"] == {"VENDOR": "SUPPLIER"} and lay["show_technical"] is False
    assert relabel(lay, "VENDOR") == "SUPPLIER" and relabel({"labels": {"PRICE REVISION HISTORY": "PRICE LOG"}}, "PRICE REVISION HISTORY · FSI PART X") == "PRICE LOG · FSI PART X"
    rep = normalize_layout("METLAB", {})
    assert rep["rule"] == "#9AA5A5" and rep["body_pt"] == 8.6 and normalize_layout("METLAB", {"body_pt": 99})["body_pt"] == 14.0


def test_po_layout_applies_title_labels_sections_footer():
    from core.print_samples import po_sample
    from core.purchase_order_reporting import purchase_order_pdf_bytes
    header, items = po_sample()
    layout = {"title": "SUPPLIER ORDER", "labels": {"VENDOR": "SUPPLIER"}, "show_technical": False, "footer_text": "QA DESK"}
    text = PdfReader(BytesIO(purchase_order_pdf_bytes(header, items, terms_path="/__none__.pdf", layout=layout))).pages[0].extract_text()
    assert "SUPPLIER ORDER" in text and "SUPPLIER" in text and "QA DESK" in text
    assert "SUPPLIER TECHNICAL DATA" not in text and "PRICE REVISION HISTORY" in text


def test_report_layout_changes_font_and_restores_globals():
    from core import reporting as r
    from core.print_samples import metlab_sample
    before = (r.TEAL.hexval(), r.BODY_PT)
    pdf = r.metlab_record_pdf_bytes(metlab_sample(), layout={"accent": "#7C2D12", "body_pt": 11, "footer_text": "FSI QA FOOTER", "labels": {"METALLURGICAL TEST RESULTS": "LAB RESULTS"}})
    text = "".join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    assert "FSI QA FOOTER" in text and "LAB RESULTS" in text
    assert (r.TEAL.hexval(), r.BODY_PT) == before


def test_every_document_previews():
    from core.print_designer import DOCUMENTS, normalize_layout
    from core.print_samples import sample_pdf
    for doc in DOCUMENTS:
        assert sample_pdf(doc, normalize_layout(doc, {"preset": "B3"})).startswith(b"%PDF")


def test_designer_page_route_and_saving():
    app = (ROOT / "streamlit_app.py").read_text()
    assert 'url_path="print-designer"' in app and '"print-designer":"USER_ACCESS"' in app
    page = (ROOT / "app_pages/print_designer.py").read_text()
    for token in ("A · DESIGN SELECTOR", "B · COLOURS & STYLE", "D · SECTIONS SHOWN ON PRINT", "E · RENAME HEADINGS", "LIVE PREVIEW", "Layout versions"):
        assert token in page
    from core.print_designer import save_layout, read_layout

    class Repo:
        rows = []
        def select(self, table, eq=None, **k):
            return [r for r in self.rows if all(r.get(a) == b for a, b in (eq or {}).items())]
        def update(self, table, rid, data):
            row = next(r for r in self.rows if r["id"] == rid); row.update(data); return row
        def insert(self, table, data):
            row = {"id": str(len(self.rows) + 1), **data}; self.rows.append(row); return row
    repo = Repo()
    save_layout(repo, "PURCHASE_ORDER", {"preset": "B4", "title": "PO"}, {"role": "ADMIN", "app_role": "ADMIN"})
    assert read_layout(repo, "PURCHASE_ORDER")["title"] == "PO" and read_layout(repo, "PURCHASE_ORDER")["accent"] == "#334155"
    sc = (ROOT / "app_pages/supply_chain.py").read_text()
    assert '"Print design"' in sc


def test_asset_number_master_and_calibration():
    sql = (ROOT / "supabase/migrations/20261013100000_qcms_r21_asset_number.sql").read_text()
    assert "add column if not exists asset_number text" in sql and "uq_quality_assets_asset_number" in sql
    from core.master_definitions import DEFINITIONS as MASTER_DEFINITIONS
    qa = next(d for d in MASTER_DEFINITIONS if d.key == "quality_assets")
    assert "asset_number" in [f.name for f in qa.fields] and "asset_number" in qa.columns and "asset_number" in qa.search_fields
    cal = (ROOT / "app_pages/calibration_validation.py").read_text()
    assert cal.count("asset_number") >= 8 and '"Asset Number": asset.get("asset_number")' in cal
    assert '"asset number": "asset_number"' in (ROOT / "app_pages/master_import.py").read_text()
