"""R13: Top-10 KPI dashboards, admin AI switch, grouped navigation."""
from datetime import date, timedelta
from pathlib import Path
import pytest
from core.kpi_service import DASHBOARDS, KPIContext

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 10, 9)
D = lambda n: (TODAY - timedelta(days=n)).isoformat()

DATA = {
    "supply_rm_purchase_orders": [{"id": "rp1", "rm_supplier_id": "s1", "expected_date": D(20), "status": "OPEN"}, {"id": "rp2", "rm_supplier_id": "s2", "expected_date": D(10), "status": "OPEN"}],
    "supply_rm_receipts": [{"rm_purchase_order_id": "rp1", "receipt_date": D(21)}, {"rm_purchase_order_id": "rp2", "receipt_date": D(5)}],
    "supply_forging_orders": [{"id": "f1", "forging_supplier_id": "s1", "expected_date": D(3), "status": "OPEN"}],
    "supply_forging_receipts": [{"forging_order_id": "f1", "receipt_date": D(3), "forging_supplier_id": "s1"}],
    "supply_purchase_orders": [
        {"po_number": "PO1", "status": "OPEN", "approval_status": "APPROVED", "grand_total": 1000, "supplier_id": "s1", "order_date": D(30), "delivery_date": D(2), "po_type": "FORGING"},
        {"po_number": "PO2", "status": "PENDING_APPROVAL", "approval_status": "PENDING_APPROVAL", "grand_total": 500, "supplier_id": "s2", "order_date": D(4), "submitted_at": D(4), "po_type": "RAW_MATERIAL"},
        {"po_number": "PO3", "status": "CANCELLED", "grand_total": 9999, "supplier_id": "s2", "order_date": D(4)}],
    "supply_customer_orders": [{"id": "c1", "customer_id": "cu", "part_id": "p1", "order_qty_pcs": 100, "customer_delivery_date": D(5), "status": "IN_PROGRESS"}, {"id": "c2", "customer_id": "cu", "order_qty_pcs": 50, "customer_delivery_date": D(1), "status": "COMPLETED"}],
    "supply_downstream_events": [{"customer_order_id": "c1", "event_type": "CUSTOMER_DISPATCH", "qty_pcs": 60}, {"customer_order_id": "c2", "event_type": "CUSTOMER_DISPATCH", "qty_pcs": 50}],
    "inward_lots": [{"supplier_id": "s1", "inward_date": D(10), "steel_quantity_kg": 1000, "accepted_steel_quantity_kg": 990, "rejected_steel_quantity_kg": 10, "metallurgical_status": "PASS"}],
    "rmtc_approvals": [{"status": "APPROVED", "created_at": D(10), "decision_at": D(8), "steel_mill_id": "s1", "certificate_date": D(10)}, {"status": "PENDING", "created_at": D(2), "certificate_date": D(2)}],
    "lab_tests": [{"overall_result": "PASS", "test_date": D(5), "created_at": D(6), "validated_at": D(5), "part_id": "p1"}, {"overall_result": "FAIL", "test_date": D(4), "part_id": "p1"}],
    "inspection_reports": [{"overall_result": "PASS", "inspection_date": D(3)}],
    "quality_complaints": [{"complaint_number": "C1", "status": "OPEN", "severity": "HIGH", "complaint_date": D(40), "target_closure_date": D(10), "complaint_type": "CUSTOMER", "part_id": "p1"},
                           {"complaint_number": "C2", "status": "CLOSED", "severity": "LOW", "complaint_date": D(30), "closure_date": D(10), "complaint_type": "SUPPLIER"}],
    "osp_jobs": [{"osp_job_number": "J1", "vendor_id": "v1", "quantity_dispatched": 100, "quantity_received": 40, "dispatch_date": D(20), "expected_return_date": D(5), "status": "OPEN"},
                 {"osp_job_number": "J2", "vendor_id": "v1", "quantity_dispatched": 50, "quantity_received": 50, "quantity_rejected_at_receipt": 1, "dispatch_date": D(15), "receipt_date": D(9), "status": "CLOSED"}],
    "quality_assets": [{"asset_code": "G1", "status": "ACTIVE", "next_due_date": D(1), "asset_type": "GAUGE"}, {"asset_code": "G2", "status": "ACTIVE", "next_due_date": (TODAY + timedelta(days=10)).isoformat(), "asset_type": "GAUGE"}, {"asset_code": "G3", "status": "ACTIVE", "next_due_date": (TODAY + timedelta(days=90)).isoformat()}],
    "npd_orders": [{"order_number": "N1", "status": "OPEN", "delivery_date": D(3), "part_id": "p1"}],
    "ppap_projects": [{"project_code": "P1", "status": "IN_PROGRESS", "completion_percent": 40, "target_submission_date": D(1)}],
}
CTX = KPIContext(today=TODAY, start=TODAY - timedelta(days=90), end=TODAY, parties={"s1": "Forge One", "s2": "Mill Two", "cu": "Customer A", "v1": "HT Vendor"}, parts={"p1": "40256626 · Shaft"})


def test_exactly_ten_dashboards_with_unique_keys():
    assert len(DASHBOARDS) == 10 and len({d[0] for d in DASHBOARDS}) == 10


@pytest.mark.parametrize("entry", DASHBOARDS, ids=[d[0] for d in DASHBOARDS])
def test_every_dashboard_builds_with_data_and_empty(entry):
    board = entry[4](DATA, CTX)
    assert len(board.tiles) == 4 and not board.empty and board.charts
    empty = entry[4]({}, CTX)
    assert len(empty.tiles) == 4 and empty.empty


def tiles(key):
    builder = next(d[4] for d in DASHBOARDS if d[0] == key)
    return {t.label: t.value for t in builder(DATA, CTX).tiles}


def test_kpi_values():
    assert tiles("supplier-otd")["On-time delivery"] == "66.7%"     # rp1 late by 1 day, rp2 & f1 on time
    po = tiles("po-pipeline")
    assert po["Open PO value"] == "₹ 1,500" and po["Waiting for approval"] == "1" and po["Overdue open POs"] == "1"
    ful = tiles("fulfilment")
    assert ful["Fill rate"] == "73.3%" and ful["Past-due schedules"] == "1" and ful["Open backlog"] == "40 pcs"
    assert tiles("incoming-quality")["Rejection PPM"] == "10,000"
    assert tiles("lab-inspection")["First-pass yield"] == "66.7%"
    cx = tiles("complaints")
    assert cx["Open complaints"] == "1" and cx["Overdue CAPA"] == "1" and cx["Avg closure time"] == "20 d"
    osp = tiles("osp")
    assert osp["Pcs at vendors"] == "60" and osp["Late returns"] == "1" and osp["Avg turnaround"] == "6.0 d"
    cal = tiles("calibration")
    assert cal["Overdue calibration"] == "1" and cal["Due in 30 days"] == "1" and cal["Calibration compliance"] == "66.7%"
    npd = tiles("npd")
    assert npd["NPD orders late"] == "1" and npd["PPAP past target"] == "1"


class CatalogRepo:
    def __init__(self): self.rows = []; self.n = 0
    def select(self, table, eq=None, **k):
        rows = [dict(r) for r in self.rows if all(r.get(a) == b for a, b in (eq or {}).items())]
        return sorted(rows, key=lambda r: r.get("last_used_at") or "", reverse=bool(k.get("desc")))
    def insert(self, table, payload):
        self.n += 1; row = {"id": f"r{self.n}", **payload}; self.rows.append(row); return row
    def update(self, table, rid, payload):
        row = next(r for r in self.rows if r["id"] == rid); row.update(payload); return row


def test_admin_ai_switch(monkeypatch):
    from core import system_settings as ss
    monkeypatch.setattr(ss, "_secret_mode", lambda: "")
    repo = CatalogRepo()
    admin, user = {"role": "ADMIN"}, {"role": "QUALITY_MANAGER"}
    assert ss.get_ai_mode(repo) == ("ALL", "default")
    with pytest.raises(PermissionError):
        ss.set_ai_mode(repo, "DISABLED", user)
    ss.set_ai_mode(repo, "DISABLED", admin)
    assert ss.get_ai_mode(repo) == ("DISABLED", "admin") and not ss.ai_allowed("DISABLED", admin)
    ss.set_ai_mode(repo, "ADMIN_ONLY", admin)
    assert ss.get_ai_mode(repo)[0] == "ADMIN_ONLY" and ss.ai_allowed("ADMIN_ONLY", admin) and not ss.ai_allowed("ADMIN_ONLY", user)
    ss.set_ai_mode(repo, "DISABLED", admin)
    assert [r["value_text"] for r in repo.rows if r["status"] == "ACTIVE"] == ["DISABLED"]
    monkeypatch.setattr(ss, "_secret_mode", lambda: "ALL")
    assert ss.get_ai_mode(repo) == ("ALL", "secret")


def test_global_search_respects_switch_and_layout_registered():
    gs = (ROOT / "app_pages/global_search.py").read_text()
    assert "ai_allowed(ai_mode, profile)" in gs and "_render_keyword_search(repo, profile)\n        return" in gs
    app = (ROOT / "streamlit_app.py").read_text()
    for token in ('"kpi-dashboards"', '"system-settings"', '(None, "Quality", "", "")', '(None, "Engineering", "", "")', '"KPIs", "KPI Dashboards"', '("system-settings", "System Settings"'):
        assert token in app
    assert "qcms-rail-head" in (ROOT / "core/ui.py").read_text()


def test_kpi_page_renders_in_preview_mode():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
import streamlit as st
from core.auth import PREVIEW_PROFILE
st.session_state["_qsms_preview"] = True
st.session_state["profile"] = PREVIEW_PROFILE.copy()
from app_pages import kpi_dashboards
kpi_dashboards.render()
''').run(timeout=60)
    assert not app.exception
    assert any("KPI OVERVIEW" in str(m.value) for m in app.markdown)
