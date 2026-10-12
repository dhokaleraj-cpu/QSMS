"""R20: RM PO clubbing by RM section, PO delete with linked-record listing, record status window,
supplier To / others CC with preview, number-first KPI page, company login name, PO print themes."""
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


class FakeRepo:
    def __init__(self, tables=None, rpc_result=None, rpc_error=None):
        self.tables = tables or {}
        self.rpc_calls = []
        self.rpc_result = rpc_result
        self.rpc_error = rpc_error

    def select(self, table, *, eq=None, in_=None, limit=500, order_by=None, desc=False, **_):
        rows = list(self.tables.get(table, []))
        for k, v in (eq or {}).items():
            rows = [r for r in rows if str(r.get(k)) == str(v)]
        for k, vals in (in_ or {}).items():
            rows = [r for r in rows if str(r.get(k)) in {str(v) for v in vals}]
        return rows[:limit]

    def get(self, table, rid):
        return next((r for r in self.tables.get(table, []) if str(r.get("id")) == str(rid)), None)

    def rpc(self, name, params=None):
        self.rpc_calls.append((name, dict(params or {})))
        if self.rpc_error and name in self.rpc_error:
            raise self.rpc_error[name]
        return self.rpc_result


def test_rm_section_clubbing_ignores_forging_fields():
    from core.supply_chain_service import SupplyChainService
    svc = SupplyChainService.__new__(SupplyChainService)
    a = svc.raw_material_po_group_key({"id": "p1"}, {"id": "r1", "material_grade_id": "G1", "material_section_name": "Round Bar", "section_size": "Ø45 mm", "forging_weight_kg": 1.2, "supplier_forging_part_number": "F-1"})
    b = svc.raw_material_po_group_key({"id": "p2"}, {"id": "r2", "material_grade_id": "G1", "material_section_name": "Round Bar", "section_size": "45", "forging_weight_kg": 3.4, "supplier_forging_part_number": "F-2"})
    c = svc.raw_material_po_group_key({"id": "p3"}, {"id": "r3", "material_grade_id": "G1", "material_section_name": "Round Bar", "section_size": "50"})
    assert a == b and a.startswith("RM_SECTION|") and a != c


def test_friendly_po_error_and_atomic_abort_present():
    from core.supply_chain_service import friendly_po_error
    msg = friendly_po_error(Exception('duplicate key value violates unique constraint "uq_supply_rm_supplier_order_no"'))
    assert "QCMS_R20_RUN_IN_SUPABASE.sql" in msg and "cancelled automatically" in msg
    assert "Cancel that PO first" in friendly_po_error(Exception("uq_supply_rm_po_order_supplier"))
    src = (ROOT / "core/supply_chain_service.py").read_text()
    assert "self._abort_purchase_order(header, exc)" in src and "def rm_section_label" in src


def test_r20_sql_contract():
    sql = (ROOT / "supabase/migrations/20261012100000_qcms_r20_po_club_delete_history.sql").read_text()
    assert "lower(supplier_order_no), customer_order_id)" in sql
    assert "function public.qcms_delete_purchase_order(p_purchase_order_id uuid)" in sql
    assert "function public.qcms_record_history(p_table_name text, p_row_id uuid" in sql
    assert "supply_rm_receipts" in sql and "inward_lots" in sql and "security definer" in sql


def test_dependency_map_and_linked_records():
    from core.record_history import children_of, linked_records
    kids = children_of("supply_purchase_orders")
    assert ("supply_purchase_order_items", "purchase_order_id") in kids
    repo = FakeRepo({
        "supply_rm_receipts": [{"id": "x1", "rm_purchase_order_id": "S1", "receipt_number": "RMR-1", "status": "RECEIVED", "created_by": "u1", "created_at": "2026-10-10T05:00:00+00:00"}],
        "profiles": [{"id": "u1", "full_name": "Asha", "email": "asha@x.com"}],
    })
    rows = linked_records(repo, "supply_rm_purchase_orders", "S1")
    assert rows and rows[0]["Reference"] == "RMR-1" and rows[0]["Linked Transaction"] == "RM Receipt"
    assert rows[0]["Created By"] == "Asha · asha@x.com" and rows[0]["Status"] == "Received"


def test_record_history_timeline():
    from core.record_history import history_rows, record_history, status_summary
    events = [
        {"changed_at": "2026-10-11T10:00:00+00:00", "operation": "UPDATE", "changed_by_name": "Ravi", "old_data": {"status": "DRAFT", "updated_at": "a"}, "new_data": {"status": "APPROVED", "updated_at": "b"}},
        {"changed_at": "2026-10-10T10:00:00+00:00", "operation": "INSERT", "changed_by_name": "Asha", "new_data": {"status": "DRAFT"}},
    ]
    rows = history_rows(events)
    assert rows[0]["Field"] == "Status" and rows[0]["Old Value"] == "DRAFT" and rows[0]["New Value"] == "APPROVED"
    assert rows[1]["Action"] == "Created" and rows[1]["User"] == "Asha"
    summary = status_summary({"status": "APPROVED"}, events)
    assert summary["Created By"] == "Asha" and summary["Last Edited By"] == "Ravi" and summary["Edits"] == "1"
    repo = FakeRepo(rpc_result=events)
    assert record_history(repo, "parts", "id1") == events and repo.rpc_calls[0][0] == "qcms_record_history"


def test_delete_uses_dedicated_po_rpc_with_fallback():
    from core import delete_service as ds
    repo = FakeRepo()
    ds.run_delete(repo, "supply_purchase_orders", "po1")
    assert repo.rpc_calls == [("qcms_delete_purchase_order", {"p_purchase_order_id": "po1"})]
    repo = FakeRepo(rpc_error={"qcms_delete_purchase_order": Exception("PGRST202 Could not find the function")})
    ds.run_delete(repo, "supply_purchase_orders", "po1")
    assert repo.rpc_calls[-1][0] == "qcms_delete_transaction_row"
    src = (ROOT / "core/delete_service.py").read_text()
    assert "show_delete_blocked(repo, table, selected, exc)" in src and "Check linked records" in src


def test_supplier_is_to_and_others_cc():
    from core.notification_service import NotificationService
    to, name, cc = NotificationService.supplier_first("qa@fsi.com", "QA", ["dept@fsi.com"], ["sales@vendor.com", "ops@vendor.com"], "Vendor")
    assert to == "sales@vendor.com" and name == "Vendor"
    assert cc == ["qa@fsi.com", "dept@fsi.com", "ops@vendor.com"]
    assert NotificationService.supplier_first("qa@fsi.com", "QA", [], [])[0] == "qa@fsi.com"
    ui = (ROOT / "core/notification_ui.py").read_text()
    assert "def email_preview_block" in ui and "Preview email" in ui and "Email body preview" in ui
    sc = (ROOT / "app_pages/supply_chain.py").read_text()
    assert "To (Supplier)" in sc and "Open PO PDF preview" in sc and "Club by Raw Material Section" in sc


def test_record_status_window_wired():
    rc = (ROOT / "app_pages/records_center.py").read_text()
    assert '"Record History"' in rc and "render_record_history_center(repo)" in rc
    assert "record_history_panel" in (ROOT / "app_pages/part_master.py").read_text()
    assert 'record_history_panel(service.repo, "supply_purchase_orders"' in (ROOT / "app_pages/supply_chain.py").read_text()


def test_kpi_number_first_and_login_company_name():
    kpi = (ROOT / "app_pages/kpi_dashboards.py").read_text()
    assert "board.question" not in kpi and "font-size:34px" in kpi and 'page_header("KPI Dashboards", "Live numbers"' in kpi
    auth = (ROOT / "core/auth.py").read_text()
    assert 'COMPANY_LEGAL_NAME = "FOUR STAR INDUSTRIES PRIVATE LIMITED"' in auth


def test_po_print_five_designs_render():
    from core import purchase_order_reporting as por
    assert list(por.PO_DESIGNS) == ["B1", "B2", "B3", "B4", "B5"] and por.DEFAULT_PO_DESIGN == "B1"
    header = {"po_number": "PD1", "order_date": "2026-10-12", "subtotal": 100, "grand_total": 118}
    item = {"item_no": "RM-1", "item_description": "Round Bar", "quantity": 1, "uom": "KGS", "unit_price": 100, "gst_percent": 18, "line_total": 100}
    for code in por.PO_DESIGNS:
        pdf = por.purchase_order_pdf_bytes(header, [item], terms_path="/__none__.pdf", design=code)
        text = PdfReader(BytesIO(pdf)).pages[0].extract_text()
        assert "PURCHASE ORDER" in text and "COMMENTS OR SPECIAL INSTRUCTIONS" in text
    assert por._ACTIVE["name"].startswith("B1")
