"""R36b: Inventory & Stock reports, reusable report filters on every Reports route, Report Builder inventory sources."""
from __future__ import annotations

import ast
import inspect
from datetime import date
from pathlib import Path

import pandas as pd

from core import report_filters as rf

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261023110000_qcms_r36b_inventory_reports.sql"

FRAME = pd.DataFrame({
    "Part Number": ["P-100", "P-200", "P-300", "P-400"],
    "Customer": ["Kessler", "Meritor", "Kessler", "Dana"],
    "Status": ["OPEN", "CLOSED", "OPEN", "OPEN"],
    "Heat Number": ["H1001", "H1002", "H1003", "H1004"],
    "Balance kg": [120.5, 0.0, 30.0, 999.0],
    "Receipt Date": ["2026-10-01", "2026-10-05", "2026-10-09", None],
    "Created At": ["2026-10-01T05:00:00+00:00", "2026-10-02T05:00:00+00:00", "2026-10-03T05:00:00+00:00", "2026-10-04T05:00:00+00:00"],
})

STAGE_ROW = {
    "part_id": "11111111-1111-1111-1111-111111111111", "part_number": "P-100", "fsi_part_number": "FSI-100", "part_name": "Yoke",
    "customer_name": "Kessler", "material_grade": "20MnCr5", "open_orders": 2, "open_order_qty_pcs": 1000, "pending_order_pcs": 600,
    "rm_required_kg": 900, "rm_ordered_kg": 900, "rm_received_kg": 800, "rm_pending_receipt_kg": 100, "rm_at_fsi_kg": 300,
    "rm_sent_to_forger_kg": 500, "rm_consumed_at_forger_kg": 200, "rm_at_forger_kg": 300, "forging_ordered_pcs": 700,
    "forging_received_pcs": 400, "forging_rejected_pcs": 10, "forging_pending_at_forger_pcs": 290, "machined_pcs": 350,
    "machining_wip_pcs": 50, "machined_pending_fg_pcs": 20, "fg_produced_pcs": 330, "fg_stock_pcs": 30, "dispatched_pcs": 400,
    "opening_rm_kg": 0, "opening_forging_pcs": 0, "opening_machining_pcs": 0, "opening_fg_pcs": 100, "last_activity_date": "2026-10-20",
}
RM_ROW = {"heat_number": "H1001", "normalized_heat_number": "H1001", "heat_code": "A1", "material_grade": "20MnCr5", "rm_section": "RCS 60",
          "supplier_name": "Steel Mill", "rmtc_number": "RMTC-1", "part_numbers": "P-100", "fsi_part_numbers": "FSI-100",
          "opening_kg": 0, "received_kg": 800, "dispatched_kg": 500, "balance_kg": 300, "last_movement_date": "2026-10-10"}
FORGING_ROW = {"supplier_name": "Forge Co", "supplier_code": "F1", "part_number": "P-100", "fsi_part_number": "FSI-100", "part_name": "Yoke",
               "customer_name": "Kessler", "material_grade": "20MnCr5", "rm_sent_kg": 500, "rm_consumed_kg": 200, "rm_at_forger_kg": 300,
               "forging_ordered_pcs": 700, "forging_received_pcs": 400, "forging_rejected_pcs": 10, "forging_pending_pcs": 290, "last_movement_date": "2026-10-11"}
OSP_ROW = {"vendor_name": "HT Vendor", "osp_job_number": "OSP-1", "part_number": "P-100", "heat_number": "H1001", "process_name": "Heat Treatment",
           "dispatch_date": "2026-10-12", "dispatch_challan": "CH-1", "quantity_dispatched": 100, "quantity_received": 40, "quantity_outstanding": 60,
           "expected_return_date": "2026-10-20", "status": "AT_VENDOR", "created_at": "2026-10-12T05:00:00+00:00"}
LEDGER_ROWS = [
    {"movement_date": "2026-10-01", "movement_type": "RM RECEIPT", "stage": "RAW_MATERIAL", "direction": "IN", "part_number": "P-100", "fsi_part_number": "FSI-100",
     "part_name": "Yoke", "customer_name": "Kessler", "material_grade": "20MnCr5", "heat_number": "H1001", "party_name": "Steel Mill", "reference_no": "GRN-1",
     "customer_order_no": "CO-1", "qty_kg": 800, "qty_pcs": 0, "kg_in": 800, "kg_out": 0, "pcs_in": 0, "pcs_out": 0},
    {"movement_date": "2026-10-15", "movement_type": "CUSTOMER DISPATCH", "stage": "CUSTOMER_DISPATCH", "direction": "OUT", "part_number": "P-100", "fsi_part_number": "FSI-100",
     "part_name": "Yoke", "customer_name": "Kessler", "material_grade": "20MnCr5", "heat_number": "H1001", "party_name": "Kessler", "reference_no": "INV-9",
     "customer_order_no": "CO-1", "qty_kg": 0, "qty_pcs": 400, "kg_in": 0, "kg_out": 0, "pcs_in": 0, "pcs_out": 400},
]
FAKE_TABLES = {
    "v_qcms_stock_by_stage": [STAGE_ROW],
    "v_qcms_rm_stock_by_heat": [RM_ROW],
    "v_qcms_forging_stock_by_supplier": [FORGING_ROW],
    "v_qsms_osp_register": [OSP_ROW],
    "v_qcms_stock_movement_ledger": LEDGER_ROWS,
}


# ----------------------------------------------------------------------------- filter helper unit tests
def test_detect_columns_kinds():
    kinds = rf.detect_columns(FRAME)
    assert kinds["Customer"] == "choice" and kinds["Status"] == "choice" and kinds["Part Number"] == "choice"
    assert kinds["Balance kg"] == "number"
    assert kinds["Receipt Date"] == "date" and kinds["Created At"] == "date"
    assert kinds["Heat Number"] != "number"  # identifiers are never number ranges
    defaults = rf.default_filter_columns(FRAME, kinds)
    assert "Status" in defaults and "Customer" in defaults and any(kinds[c] == "date" for c in defaults)


def test_multiselect_filter_is_case_insensitive():
    out = rf.apply_filters(FRAME, {"values": {"Customer": ["kessler"], "Status": ["OPEN"]}})
    assert out["Part Number"].tolist() == ["P-100", "P-300"]
    assert rf.apply_filters(FRAME, {"values": {"Missing Column": ["x"]}}).shape == FRAME.shape


def test_date_range_filter_handles_text_and_timestamps():
    out = rf.apply_filters(FRAME, {"dates": {"Receipt Date": (date(2026, 10, 2), date(2026, 10, 9))}})
    assert out["Part Number"].tolist() == ["P-200", "P-300"]
    out = rf.apply_filters(FRAME, {"dates": {"Created At": (None, date(2026, 10, 2))}})
    assert out["Part Number"].tolist() == ["P-100", "P-200"]
    assert len(rf.apply_filters(FRAME, {"dates": {"Receipt Date": (None, None)}})) == 4


def test_number_range_filter():
    out = rf.apply_filters(FRAME, {"numbers": {"Balance kg": (10, 200)}})
    assert out["Part Number"].tolist() == ["P-100", "P-300"]
    assert rf.apply_filters(FRAME, {"numbers": {"Balance kg": (500, None)}})["Part Number"].tolist() == ["P-400"]


def test_text_search_all_words_across_columns():
    assert rf.apply_filters(FRAME, {"search": "kessler h1003"})["Part Number"].tolist() == ["P-300"]
    assert rf.apply_filters(FRAME, {"search": "dana"})["Part Number"].tolist() == ["P-400"]
    assert rf.apply_filters(FRAME, {"contains": {"Heat Number": "100"}}).shape[0] == 4
    assert rf.apply_filters(FRAME, {"search": "nothing-matches"}).empty


def test_totals_row_and_description():
    totals = rf.totals_row(FRAME, "Part Number")
    assert totals.iloc[-1]["Part Number"] == "TOTAL" and abs(totals.iloc[-1]["Balance kg"] - 1149.5) < 1e-9
    assert totals.iloc[-1]["Heat Number"] is None
    text = rf.describe_spec({"search": "abc", "values": {"Status": ["OPEN"]}, "numbers": {"Balance kg": (1, None)}})
    assert "Search: abc" in text and "Status: OPEN" in text and "Balance kg" in text


# ----------------------------------------------------------------------------- AppTests
def _fake_select(self, table, **kwargs):
    return [dict(r) for r in FAKE_TABLES.get(table, [])]


def _fake_rpc(self, name, params=None):
    if name == "qcms_stock_by_stage":
        return [dict(STAGE_ROW)]
    raise RuntimeError("RPC functions are unavailable in controlled preview mode.")


def _run(script: str):
    from streamlit.testing.v1 import AppTest
    return AppTest.from_string(script).run(timeout=90)


PRELUDE = '''
import streamlit as st
from core.auth import PREVIEW_PROFILE
st.session_state["_qsms_preview"] = True
st.session_state["profile"] = PREVIEW_PROFILE.copy()
'''


def test_inventory_page_renders_all_tabs(monkeypatch):
    from core.repository import Repository
    monkeypatch.setattr(Repository, "select", _fake_select)
    monkeypatch.setattr(Repository, "rpc", _fake_rpc)
    app = _run(PRELUDE + '''
import app_pages.inventory_reports as inv
inv.subpage_navigation = lambda *a, **k: None
inv.render()
''')
    assert not app.exception, app.exception
    text = " ".join(str(m.value) for m in app.markdown)
    for token in ("STOCK BY STAGE", "RAW MATERIAL STOCK BY HEAT", "FORGING STOCK AT FORGING SUPPLIERS", "FINISHED GOODS STOCK", "STOCK MOVEMENT LEDGER"):
        assert token in text, token
    assert "300.000 kg" in text  # RM at FSI KPI from the bulk stock-by-stage source
    labels = [w.label for w in app.text_input]
    assert sum("search all columns" in label for label in labels) >= 7
    assert any(b.label == "Clear filters" for b in app.button)


def test_inventory_filters_narrow_rows(monkeypatch):
    from core.repository import Repository
    monkeypatch.setattr(Repository, "select", _fake_select)
    monkeypatch.setattr(Repository, "rpc", _fake_rpc)
    app = _run(PRELUDE + '''
import app_pages.inventory_reports as inv
inv.subpage_navigation = lambda *a, **k: None
inv.render()
''')
    box = next(w for w in app.text_input if w.key == "rf_inv_movement_ledger::search")
    box.input("INV-9").run(timeout=90)
    assert not app.exception
    captions = " ".join(str(c.value) for c in app.caption)
    assert "Showing 1 of 2 row(s)" in captions
    clear = next(b for b in app.button if b.key == "rf_clear_inv_movement_ledger")
    clear.click().run(timeout=90)
    assert not app.exception
    assert next(w for w in app.text_input if w.key == "rf_inv_movement_ledger::search").value == ""
    assert "Showing 2 of 2 row(s)" in " ".join(str(c.value) for c in app.caption)


def test_filters_are_remembered_after_page_switch():
    from streamlit.testing.v1 import AppTest
    script = PRELUDE + '''
import pandas as pd
from core.report_filters import render_filters
if st.session_state.get("show_report", True):
    out = render_filters(pd.DataFrame({"Status": ["OPEN", "CLOSED"], "Qty kg": [1.0, 2.0]}), "memo_test")
    st.write(f"rows={len(out)}")
'''
    app = AppTest.from_string(script).run(timeout=60)
    app.text_input(key="rf_memo_test::search").input("closed").run(timeout=60)
    assert any("rows=1" in str(m.value) for m in app.markdown)
    app.session_state["show_report"] = False
    app.run(timeout=60)  # page switched away: widget state is dropped by Streamlit
    app.session_state["show_report"] = True
    app.run(timeout=60)
    assert not app.exception
    assert app.text_input(key="rf_memo_test::search").value == "closed"
    assert any("rows=1" in str(m.value) for m in app.markdown)


def test_stage_totals_and_frame_helpers():
    import app_pages.inventory_reports as inv
    frame = inv._frame([STAGE_ROW], inv.STAGE_COLUMNS)
    totals = inv.stage_totals(frame).set_index("Stage")
    assert totals.loc["RM at FSI", "Quantity"] == 300 and totals.loc["Finished goods stock", "Quantity"] == 30
    assert totals.loc["Forging pending at forger", "Unit"] == "pcs"


# ----------------------------------------------------------------------------- static contracts
REPORT_ROUTE_FUNCTIONS = {
    "reports-home": None,  # hub of report cards (no table)
    "report-builder": ("app_pages/report_builder.py", ("render",)),
    "master-lists": ("app_pages/report_builder.py", ("render_master_lists",)),
    "inventory-reports": ("app_pages/inventory_reports.py", ("_tab_stock_by_stage", "_tab_rm_by_heat", "_tab_forging_osp", "_tab_fg", "_tab_ledger")),
    "supply-chain-report": ("app_pages/supply_chain.py", ("render_order_mis",)),
    "heat-transaction-report": ("app_pages/reports.py", ("render_heat_transactions",)),
    "osp-balance-report": ("app_pages/reports.py", ("render_osp_balance",)),
    "rmtc-report": ("app_pages/rmtc_pages.py", ("render_records",)),
    "inward-report": ("app_pages/material_inward.py", ("render_records",)),
    "dimensional-report": ("app_pages/dimensional_report.py", ("render_records",)),
    "metlab-report": ("app_pages/metlab_report.py", ("_render_records",)),
    "bend-test-report": ("app_pages/metlab_report.py", ("_render_records",)),
    "complaints-report": ("app_pages/complaints.py", ("render_records",)),
    "traceability-report": ("app_pages/supply_chain.py", ("render_traceability",)),
    "npd-report": ("app_pages/reports.py", ("render_npd_report",)),
    "apqp-report": ("app_pages/reports.py", ("render_apqp_report",)),
    "qc-report": ("app_pages/qc_calculation_tools.py", ("_render_records",)),
    "inspection-layout-report": ("app_pages/inspection_layouts.py", ("render_records",)),
    "standards-report": ("app_pages/standards_bank.py", ("render_records",)),
}
FILTER_CALLS = ("render_filters(", "report_register(", "_status_register(")


def _function_source(path: str, name: str) -> str:
    source = (ROOT / path).read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(source, node) or ""
    raise AssertionError(f"{path}:{name} not found")


def test_every_reports_route_calls_the_filter_helper():
    app = (ROOT / "streamlit_app.py").read_text()
    reports_block = app.split('"Reports": (', 1)[1].split("),\n    \"Search\"", 1)[0]
    routes = [line.split('"')[1] for line in reports_block.splitlines() if line.strip().startswith('("')]
    home = (ROOT / "app_pages/reports.py").read_text()
    for route in routes:
        assert route in REPORT_ROUTE_FUNCTIONS, f"new Reports route {route} needs filters"
        assert route == "reports-home" or f'("{route}"' in home, f"{route} missing from the Reports home cards"
        target = REPORT_ROUTE_FUNCTIONS[route]
        if target is None:
            continue
        path, functions = target
        for fn in functions:
            body = _function_source(path, fn)
            assert any(call in body for call in FILTER_CALLS), f"{route}: {path}:{fn} has no report filters"
    for route in ("inventory-reports", "report-builder", "master-lists"):
        assert route in routes


def test_routes_registered_for_inventory_reports():
    app = (ROOT / "streamlit_app.py").read_text()
    assert 'url_path="inventory-reports"' in app and "inventory_reports.render" in app
    assert '"inventory-reports": "Reports"' in app and '"Inventory & Stock Reports": "inventory-reports"' in app
    assert "reports.render_npd_report" in app and "reports.render_apqp_report" in app
    assert '"inventory-reports"' in (ROOT / "scripts/verify_phase1.py").read_text()


def test_report_builder_has_inventory_sources_and_quick_filters():
    from core import report_builder as rb
    tables = {s["table"] for s in rb.INVENTORY_SOURCES}
    assert {"v_qcms_stock_by_stage", "v_qcms_rm_stock_by_heat", "v_qcms_forging_stock_by_supplier", "v_qcms_stock_movement_ledger"} <= tables
    for source in rb.INVENTORY_SOURCES:
        assert source["module_key"] and source["record_type"] and source["columns"]
    page = (ROOT / "app_pages/report_builder.py").read_text()
    assert "rb.INVENTORY_SOURCES" in page and 'render_filters(frame, f"rb_quick_{dataset}"' in page


def test_exports_use_filtered_frames():
    for path in ("app_pages/rmtc_pages.py", "app_pages/material_inward.py", "app_pages/dimensional_report.py", "app_pages/metlab_report.py",
                 "app_pages/complaints.py", "app_pages/qc_calculation_tools.py", "app_pages/inspection_layouts.py", "app_pages/standards_bank.py"):
        assert "report_register(" in (ROOT / path).read_text(), path
    body = inspect.getsource(rf.report_register)
    assert "report_exports(shown" in body and "render_filters(frame" in body


def test_migration_is_safe_and_invoker():
    sql = MIGRATION.read_text()
    low = sql.lower()
    for token in ("create or replace function public.qcms_stock_by_stage(p_part_id uuid default null)", "security invoker",
                  "v_qcms_stock_by_stage", "v_qcms_rm_stock_by_heat", "v_qcms_forging_stock_by_supplier", "v_qcms_stock_movement_ledger",
                  "grant execute on function public.qcms_stock_by_stage(uuid) to authenticated"):
        assert token in low, token
    assert low.count("with (security_invoker = true)") == 4
    assert "security definer" not in low
    for word in ("drop ", "delete ", "update ", "truncate"):
        assert word not in low, word
    auto = (ROOT / "supabase/auto_apply.json").read_text()
    assert "20261023110000_qcms_r36b_inventory_reports.sql" in auto


def test_no_st_dataframe_in_new_pages():
    for path in ("app_pages/inventory_reports.py", "app_pages/reports.py"):
        assert "st.dataframe(" not in (ROOT / path).read_text()
