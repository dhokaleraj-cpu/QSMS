"""R11: Part duplicate control, admin Part delete, save popup and AI Global Search."""
from pathlib import Path
import json
import pandas as pd
import pytest
from core.part_identity import find_part_conflicts, longest_common_digit_run, normalize_part_identity
from core.ai_assistant import QCMSAIAssistant, report_excel_bytes, TOOLS

ROOT = Path(__file__).resolve().parents[1]
PARTS = [
    {"id": "p1", "part_number": "40256626", "fsi_part_number": "FSI-6626", "part_name": "Diff shaft", "status": "ACTIVE"},
    {"id": "p2", "part_number": "10121529", "fsi_part_number": "1529", "part_name": "Raw forging", "status": "ACTIVE"},
    {"id": "p3", "part_number": "AB-77", "fsi_part_number": None, "part_name": "Bracket", "status": "INACTIVE"},
]


def test_normalize_and_digit_run():
    assert normalize_part_identity(" 40-256 626 ") == "40256626"
    assert normalize_part_identity("ab.77") == normalize_part_identity("AB-77")
    assert longest_common_digit_run("40256626", "40257237") == "4025"
    assert longest_common_digit_run("X-12", "Y-12") == "12"


@pytest.mark.parametrize("pn,fsi", [("40-256-626", ""), ("ab 77", ""), ("NEW1", "fsi 6626"), ("99", "40256626")])
def test_exact_duplicates_ignore_case_spaces_dashes(pn, fsi):
    assert find_part_conflicts(pn, fsi, PARTS)["exact"]


def test_four_digit_overlap_is_similar_not_exact():
    result = find_part_conflicts("40257237", "", PARTS)
    assert not result["exact"]
    assert [r["Part Number"] for r in result["similar"]] == ["40256626"]
    assert result["similar"][0]["Matching Digits"] == "4025"


def test_three_digits_is_not_similar_and_self_is_excluded():
    assert find_part_conflicts("40299999", "", PARTS)["similar"] == []
    assert find_part_conflicts("40256626", "FSI-6626", PARTS, exclude_id="p1") == {"exact": [], "similar": []}


def test_part_master_wires_duplicate_confirm_dialog_and_admin_delete():
    page = (ROOT / "app_pages/part_master.py").read_text()
    assert "find_part_conflicts(" in page and "Not a duplicate" in page
    assert 'save_success_dialog("Part Master Saved"' in page
    assert "_admin_part_delete_panel(repo, existing" in page and "_admin_part_delete_panel(repo, selected_row" in page
    assert "can_delete=admin" in page
    ui = (ROOT / "core/ui.py").read_text()
    assert "_qcms_pending_save_dialog" in ui and "@st.dialog(title)" in ui


def test_save_dialog_is_shown_after_rerun():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
import streamlit as st
from core.ui import save_success_dialog, render_pending_popups
if st.button("save"):
    save_success_dialog("Part Master Saved", "Part Number: **123**")
    st.rerun()
render_pending_popups()
''').run()
    app.button[0].click().run()
    assert not app.exception
    assert any("Part Master Saved" in str(m.value) for m in app.markdown)


class Repo:
    def __init__(self):
        self.tables = {
            "parts": [{"id": "p1", "part_number": "40256626", "fsi_part_number": "F1", "part_name": "Shaft"}],
            "parties": [{"id": "s1", "party_code": "S01", "party_name": "Forge One"}, {"id": "s2", "party_code": "S02", "party_name": "Forge Two"}],
            "supply_purchase_orders": [
                {"id": "a", "po_number": "PO-1", "supplier_id": "s1", "grand_total": 100.0, "status": "OPEN", "order_date": "2026-09-02"},
                {"id": "b", "po_number": "PO-2", "supplier_id": "s1", "grand_total": 50.0, "status": "OPEN", "order_date": "2026-10-01"},
                {"id": "c", "po_number": "PO-3", "supplier_id": "s2", "grand_total": 70.0, "status": "CANCELLED", "order_date": "2026-10-03"},
            ],
            "quality_complaints": [{"id": "q", "complaint_number": "C-1", "part_id": "p1"}],
        }
        self.calls = []
    def select(self, table, **kw):
        self.calls.append((table, kw))
        rows = [dict(r) for r in self.tables.get(table, [])]
        for k, v in (kw.get("eq") or {}).items():
            rows = [r for r in rows if r.get(k) == v]
        if kw.get("search_term"):
            t = kw["search_term"].casefold()
            rows = [r for r in rows if any(t in str(r.get(c) or "").casefold() for c in kw.get("search_columns") or ())]
        return rows
    def insert(self, *a, **k): raise AssertionError("AI must never write")
    update = delete = rpc = insert


SOURCES = [
    {"table": "supply_purchase_orders", "record_type": "Purchase Order", "module": "Supply Chain", "module_key": "SUPPLY_CHAIN", "columns": ("po_number", "status")},
    {"table": "quality_complaints", "record_type": "Quality Complaint", "module": "Complaints", "module_key": "COMPLAINT_MANAGEMENT", "columns": ("complaint_number",)},
]


def assistant(post=None, allowed=("SUPPLY_CHAIN", "REFERENCE_MASTERS", "PART_MASTER")):
    return QCMSAIAssistant(Repo(), SOURCES, lambda key: key in allowed, api_key="test", post=post)


def test_only_permitted_datasets_and_read_only_tools():
    ai = assistant()
    assert set(ai.datasets) == {"supply_purchase_orders"}
    assert "error" in ai.run_tool("query_records", {"dataset": "quality_complaints"})
    assert {t["name"] for t in TOOLS} == {"describe_dataset", "query_records", "aggregate_records"}


def test_query_filters_labels_and_report():
    ai = assistant()
    out = ai.run_tool("query_records", {"dataset": "supply_purchase_orders", "filters": [{"column": "status", "op": "eq", "value": "open"}, {"column": "order_date", "op": "gte", "value": "2026-09-15"}], "show_as_report": True, "report_title": "Open POs"})
    assert out["matched_rows"] == 1 and out["rows"][0]["po_number"] == "PO-2"
    assert out["rows"][0]["supplier_id_label"] == "S01 · Forge One"
    assert ai.reports[0].title == "Open POs" and len(ai.reports[0].frame) == 1
    assert report_excel_bytes(ai.reports[0])[:2] == b"PK"


def test_aggregate_by_supplier_and_month():
    ai = assistant()
    out = ai.run_tool("aggregate_records", {"dataset": "supply_purchase_orders", "group_by": ["supplier_id_label"], "metric": "sum", "value_column": "grand_total", "filters": [{"column": "status", "op": "neq", "value": "CANCELLED"}]})
    assert out["groups"] == [{"supplier_id_label": "S01 · Forge One", "sum_grand_total": 150.0}]
    out = ai.run_tool("aggregate_records", {"dataset": "supply_purchase_orders", "group_by": ["order_date:month"], "metric": "count", "show_as_report": True, "chart": {"type": "bar", "x": "order_date:month"}})
    assert {g["order_date:month"]: g["count"] for g in out["groups"]} == {"2026-10": 2, "2026-09": 1}
    assert ai.reports[-1].chart["y"] == "count"


def test_bad_column_returns_error_to_model():
    out = assistant().run_tool("query_records", {"dataset": "supply_purchase_orders", "filters": [{"column": "nope", "op": "eq", "value": 1}]})
    assert "does not exist" in out["error"]


def test_ask_runs_tool_loop_without_network():
    sent = []
    def post(payload):
        sent.append(payload)
        if len(sent) == 1:
            return {"stop_reason": "tool_use", "content": [{"type": "tool_use", "id": "t1", "name": "aggregate_records", "input": {"dataset": "supply_purchase_orders", "metric": "count"}}]}
        result = json.loads(payload["messages"][-1]["content"][0]["content"])
        return {"stop_reason": "end_turn", "content": [{"type": "text", "text": f"There are {result['groups'][0]['count']} POs."}]}
    answer = assistant(post).ask("How many POs?")
    assert answer.text == "There are 3 POs." and not answer.error
    assert "supply_purchase_orders" in sent[0]["system"] and "quality_complaints" not in sent[0]["system"]


def test_ask_without_key_is_explained():
    ai = QCMSAIAssistant(Repo(), SOURCES, lambda k: True, api_key="")
    assert "ANTHROPIC_API_KEY" in ai.ask("hi").error


def test_global_search_page_has_ai_tab_and_keyword_search():
    page = (ROOT / "app_pages/global_search.py").read_text()
    assert "AI Assistant" in page and "_render_keyword_search" in page and "QCMSAIAssistant(" in page
