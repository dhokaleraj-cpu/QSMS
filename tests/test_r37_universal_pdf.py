"""R37: universal print layout - record_pdf for every table, preview / download control, wiring in pages."""
from __future__ import annotations

import io
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]

DB: dict[str, list[dict]] = {
    "parts": [{"id": "p1", "part_number": "40256626", "fsi_part_number": "FSI-777", "part_name": "Pinion Gear", "customer_id": "c1",
               "material_grade_id": "g1", "customer_part_number": "CUST-PN-9", "status": "ACTIVE"}],
    "part_raw_material_details": [{"id": "rm1", "part_id": "p1", "sequence_no": 1, "supplier_id": "s1", "section_size": "RCS 60", "input_weight_kg": 2.45}],
    "part_supplier_links": [{"id": "sl1", "part_id": "p1", "supplier_id": "s1", "supplier_part_number": "SUP-PN-1"}],
    "part_heat_treatment_details": [{"id": "ht1", "part_id": "p1", "sequence_no": 1, "treatment": "Carburising", "case_depth": "0.8-1.2"}],
    "parties": [{"id": "c1", "party_code": "CUST01", "party_name": "Acme Tractors"},
                {"id": "s1", "party_code": "SUP01", "party_name": "Bharat Forge"},
                {"id": "v1", "party_code": "OSP01", "party_name": "Heat Treat Works"}],
    "employees": [{"id": "e1", "employee_code": "E100", "first_name": "Rajesh", "last_name": "Dhokale", "department": "Purchase"},
                  {"id": "e2", "employee_code": "E200", "first_name": "Namrata", "last_name": "Patil", "reports_to_employee_id": "e1"}],
    "processes": [{"id": "pr1", "process_code": "HT", "process_name": "Heat Treatment"}],
    "material_grades": [{"id": "g1", "grade_code": "20MnCr5", "standard": "EN 10084", "revision": "2"}],
    "material_grade_elements": [{"id": "ge1", "material_grade_id": "g1", "element": "C", "min_value": 0.17, "max_value": 0.22},
                                {"id": "ge2", "material_grade_id": "g1", "element": "Mn", "min_value": 1.1, "max_value": 1.4}],
    "company_branches": [{"id": "b1", "branch_code": "D9", "branch_name": "Four Star Industries D9", "address_line1": "Plot D9, Chakan MIDC",
                          "city": "Pune", "gstin": "27AAGCF3769A1ZP", "status": "ACTIVE"}],
    "supply_rm_dispatches": [{"id": "d1", "dispatch_number": "RMD-0031", "heat_number": "H777", "forging_supplier_id": "s1", "qty_kg": 900,
                              "dispatch_date": "2026-10-07", "challan_number": "CH-31", "customer_order_id": "o1"}],
    "supply_forging_orders": [{"id": "f1", "rm_dispatch_id": "d1", "supplier_order_no": "FO-0077", "order_qty_pcs": 500}],
    "supply_customer_orders": [{"id": "o1", "master_reference_no": "MR-0001", "customer_order_no": "CPO-555", "customer_id": "c1",
                                "part_id": "p1", "order_qty": 100, "status": "OPEN", "order_date": "2026-10-01"}],
    "osp_jobs": [{"id": "j1", "osp_job_number": "OSP-0100", "vendor_id": "v1", "process_id": "pr1", "part_id": "p1", "status": "AT_VENDOR"}],
    "qc_calculation_records": [{"id": "q1", "calculation_number": "QC-0001", "calculation_type": "HARDNESS_CONVERSION", "primary_value": 30,
                                "primary_unit": "HRC", "result_value": 286, "conversion_unit": "HB", "status": "SAVED", "result_payload": {}}],
    "indirect_purchase_orders": [{"id": "ip1", "po_number": "IPO-0009", "supplier_id": "s1", "status": "RELEASED"}],
    "indirect_grns": [{"id": "ig1", "grn_number": "IGRN-0004", "supplier_id": "s1", "purchase_order_id": "ip1"}],
}


class FakeRepo:
    def select(self, table, eq=None, in_=None, limit=None, order_by=None, desc=False, **_):
        rows = list(DB.get(table, []))
        return [dict(r) for r in rows if all(str(r.get(k)) == str(v) for k, v in (eq or {}).items())]

    def get(self, table, record_id):
        rows = self.select(table, eq={"id": record_id})
        return rows[0] if rows else None


def _text(pdf: bytes) -> str:
    from pypdf import PdfReader
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)


def _marker_pdf(text: str) -> bytes:
    from reportlab.pdfgen import canvas
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(72, 720, text)
    c.save()
    return buffer.getvalue()


@pytest.fixture()
def no_partner_modules(monkeypatch):
    """Agents A / B modules absent (ImportError path)."""
    monkeypatch.setitem(sys.modules, "core.osp_challan_pdf", None)
    monkeypatch.setitem(sys.modules, "core.indirect_po_pdf", None)


def test_generic_print_for_transactions_and_masters(no_partner_modules):
    from core.universal_pdf import record_pdf
    cases = [
        ("supply_rm_dispatches", "d1", "RM DISPATCH TO FORGING", ["RMD-0031", "Forging Supplier", "Bharat Forge", "FORGING ORDERS", "FO-0077", "H777"]),
        ("parts", "p1", "PART MASTER", ["40256626", "Pinion Gear", "Acme Tractors", "20MnCr5", "RAW MATERIAL DETAILS", "RCS 60",
                                        "SUPPLIERS / STEEL MILLS", "SUP-PN-1", "HEAT TREATMENT", "Carburising"]),
        ("material_grades", "g1", "MATERIAL GRADE", ["20MnCr5", "CHEMICAL ELEMENTS", "Mn", "0.17"]),
        ("employees", "e1", "EMPLOYEE", ["E100", "Rajesh", "TEAM MEMBERS", "Namrata"]),
        ("parties", "s1", "PARTY MASTER", ["Bharat Forge", "PARTS SUPPLIED", "40256626"]),
        ("indirect_purchase_orders", "ip1", "INDIRECT PURCHASE ORDER", ["IPO-0009", "Bharat Forge", "GOODS RECEIPTS", "IGRN-0004"]),
    ]
    for table, rid, title, labels in cases:
        name, pdf = record_pdf(table, rid, FakeRepo())
        assert pdf[:4] == b"%PDF" and name.endswith(".pdf"), (table, name)
        text = _text(pdf)
        assert title in text, (table, text[:300])
        assert "Four Star Industries D9" in text and "Page 1 of" in text
        for label in labels:
            assert label in text, (table, label)
        for raw in ("c1", "s1", "g1", "p1", "e1", "d1"):
            assert raw not in text.split(), (table, raw)  # uuids are resolved, never printed


def test_customer_safe_strips_customer(no_partner_modules):
    from core.universal_pdf import record_pdf
    internal = _text(record_pdf("parts", "p1", FakeRepo())[1])
    assert "Acme Tractors" in internal and "CUST-PN-9" in internal
    name, pdf = record_pdf("parts", "p1", FakeRepo(), customer_safe=True)
    text = _text(pdf)
    assert "customer_safe" in name and "Customer-safe copy" in text
    for secret in ("Acme Tractors", "CUST01", "CUST-PN-9"):
        assert secret not in text, secret
    assert "40256626" in text
    # a customer's own parts never print on the customer-safe copy of the party
    party = _text(record_pdf("parties", "c1", FakeRepo(), customer_safe=True)[1])
    assert "PARTS (CUSTOMER)" not in party
    assert "PARTS (CUSTOMER)" in _text(record_pdf("parties", "c1", FakeRepo())[1])


def test_dedicated_layouts_are_used(monkeypatch, no_partner_modules):
    from core.notification_service import NotificationService
    from core.universal_pdf import record_pdf
    name, pdf = record_pdf("qc_calculation_records", "q1", FakeRepo())
    assert name.startswith("QC-0001") and "QC CALCULATION RECORD" in _text(pdf)
    seen = {}

    def fake_report(self, table, record_id):
        seen["safe"] = self.customer_safe
        return f"RMTC-{record_id}.pdf", _marker_pdf(f"DEDICATED {table}")
    monkeypatch.setattr(NotificationService, "_generated_report", fake_report)
    DB["rmtc_approvals"] = [{"id": "r9", "rmtc_number": "RMTC-9"}]
    try:
        name, pdf = record_pdf("rmtc_approvals", "r9", FakeRepo())
        assert name == "RMTC-r9.pdf" and "DEDICATED rmtc_approvals" in _text(pdf) and seen["safe"] is False
        name, pdf = record_pdf("rmtc_approvals", "r9", FakeRepo(), customer_safe=True)
        assert seen["safe"] is True and name.endswith("_customer_safe.pdf")
    finally:
        DB.pop("rmtc_approvals", None)


def test_partner_layouts_osp_and_indirect(monkeypatch):
    from core.universal_pdf import partner_pdf, record_pdf
    osp = types.ModuleType("core.osp_challan_pdf")
    osp.osp_challan_pdf_bytes = lambda job_id, repo=None: _marker_pdf(f"VENDOR CHALLAN {job_id}")
    ind = types.ModuleType("core.indirect_po_pdf")
    ind.indirect_po_pdf_bytes = lambda po_id, repo=None: _marker_pdf(f"INDIRECT PO {po_id}")
    ind.indirect_grn_pdf_bytes = lambda grn_id: _marker_pdf(f"INDIRECT GRN {grn_id}")  # no repo argument
    monkeypatch.setitem(sys.modules, "core.osp_challan_pdf", osp)
    monkeypatch.setitem(sys.modules, "core.indirect_po_pdf", ind)
    name, pdf = record_pdf("osp_jobs", "j1", FakeRepo())
    assert name == "OSP-0100_Challan.pdf" and "VENDOR CHALLAN j1" in _text(pdf)
    name, pdf = record_pdf("indirect_purchase_orders", "ip1", FakeRepo())
    assert name == "IPO-0009.pdf" and "INDIRECT PO ip1" in _text(pdf)
    # a builder that cannot take our repository is never run against a test / preview double -> generic print
    assert partner_pdf("indirect_grns", "ig1", FakeRepo()) is None
    name, pdf = record_pdf("indirect_grns", "ig1", FakeRepo())
    assert "INDIRECT GOODS RECEIPT NOTE" in _text(pdf) and "IGRN-0004" in name
    # a failing partner builder falls back to the generic print
    osp.osp_challan_pdf_bytes = lambda job_id, repo=None: (_ for _ in ()).throw(RuntimeError("boom"))
    name, pdf = record_pdf("osp_jobs", "j1", FakeRepo())
    assert "OSP MATERIAL OUT" in _text(pdf) and "Heat Treat Works" in _text(pdf)


def test_register_pdf_routes_and_labels():
    from core.global_search_service import TABLE_ROUTES
    from core.universal_pdf import WEB_ROUTES, record_label, record_route, register_pdf
    text = _text(register_pdf("Forging Register", pd.DataFrame([{"Order": "FO-1", "Qty pcs": 10}, {"Order": "FO-2", "Qty pcs": 5}]), "Supplier: All"))
    assert "FORGING REGISTER" in text and "TOTAL" in text and "Supplier: All" in text
    for table, route in TABLE_ROUTES.items():
        assert WEB_ROUTES.get(table) == route, table
    app = (ROOT / "streamlit_app.py").read_text()
    for table, route in WEB_ROUTES.items():
        assert f'"{route}"' in app, (table, route)
    assert record_label("lab_tests") == "MetLAB / Bend Test Report" and record_route("parts", {"part-records": 1}) == "part-records"
    assert record_route("parts", {}) is None


APP_SCRIPT = '''
import sys
sys.path.insert(0, %r)
import streamlit as st
from tests.test_r37_universal_pdf import FakeRepo
from core.pdf_preview import pdf_actions, preview_button
sys.modules["core.osp_challan_pdf"] = None
sys.modules["core.indirect_po_pdf"] = None
pdf_actions("supply_rm_dispatches", "d1", key="t", repo=FakeRepo(), customer_safe=None)
pdf_actions("material_grades", "g1", key="inl", repo=FakeRepo(), inline=True)
preview_button("parts", "p1", key="pv", record={"id": "p1", "updated_at": "x"})
'''


def test_pdf_actions_preview_and_download():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string(APP_SCRIPT % str(ROOT)).run(timeout=90)
    assert not app.exception, app.exception
    labels = [b.label for b in app.button]
    assert "Preview Print layout PDF" in labels and "Preview print layout" in labels
    assert any(t.label.startswith("Customer-safe copy") for t in app.toggle)
    cache = app.session_state["_qcms_pdf_actions_cache"]
    assert any(k.startswith("supply_rm_dispatches:d1:") for k in cache) and any(k.startswith("material_grades:g1:") for k in cache)
    app.button(key="qcms_pdfa_t_supply_rm_dispatches_d1_preview").click().run(timeout=90)
    assert not app.exception, app.exception
    app.button(key="qcms_pdfa_inl_material_grades_g1_preview").click().run(timeout=90)
    assert not app.exception, app.exception
    app.toggle(key="qcms_pdfa_t_supply_rm_dispatches_d1_safe").set_value(True).run(timeout=90)
    assert not app.exception and any(k.endswith(":1") and k.startswith("supply_rm_dispatches") for k in app.session_state["_qcms_pdf_actions_cache"])


def test_global_search_records_centre_and_pages_are_wired():
    gs = (ROOT / "app_pages/global_search.py").read_text()
    viewer = gs[gs.index("def _record_viewer"):gs.index("def _open_record")]
    assert "print_panel(" in viewer and "record_route(" in viewer and "Open the module register" in viewer
    area = gs[gs.index("def _result_print_area"):gs.index("def _render_classic_results")]
    assert "Open record" in area and "Open module register" in area and "print_panel(" in area
    opener = gs[gs.index("def _open_record"):gs.index("def _render_everything")]
    assert "warn=False" in opener and "_record_viewer(" in opener
    rc = (ROOT / "app_pages/records_center.py").read_text()
    for table in ("osp_challans", "indirect_purchase_orders", "indirect_grns", "quality_assets", "standard_room_inspection_records"):
        assert f'("{table}"' in rc, table
    assert "return True" in rc[rc.index("def _open_selected_record_for_edit"):]
    expected = {
        "supply_chain.py": ("pdf_actions(table,selected", '"supply_opening_stock"', '"supply_rm_receipts"'),
        "material_inward.py": ('"inward_lots"',), "rmtc_pages.py": ("'rmtc_approvals'",), "metlab_report.py": ('"lab_tests"',),
        "dimensional_report.py": ('"inspection_reports"',), "complaints.py": ('"quality_complaints"',),
        "calibration_validation.py": ('"quality_asset_calibration_records"', '"standard_room_inspection_records"'),
        "qc_calculation_tools.py": ('"qc_calculation_records"',), "npd_apqp.py": ('"npd_orders"', '"npd_process_flows"', '"ppap_projects"'),
        "part_master.py": ('"parts"',), "reference_master.py": ("definition.table",), "material_grade.py": ('"material_grades"',),
        "process_master.py": ('"processes"',), "employee_master.py": ('"employees"',), "inspection_layouts.py": ('"inspection_plans"',),
        "standards_bank.py": ('"customer_standards"',), "company_branch.py": ('"company_branches"',),
    }
    for page, tokens in expected.items():
        src = (ROOT / "app_pages" / page).read_text()
        assert "from core.pdf_preview import" in src, page
        for token in tokens:
            assert token in src, (page, token)
    for page in (ROOT / "app_pages").glob("*.py"):
        assert "st.dataframe(" not in page.read_text(), page.name
    from app_pages import global_search, records_center  # noqa: F401 - import check
