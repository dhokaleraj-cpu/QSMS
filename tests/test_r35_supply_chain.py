"""R35 Supply Chain: detailed + searchable stage selectors, guided delete of a Customer Order held by a PO,
RM PO clubbing (per-order mismatch explanation, split lines by price/HSN), editable PO quantity,
inward over-receipt tolerance, six-month schedule override and the live stage-stock panel."""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ----------------------------------------------------------------------------- selectors
def test_stage_record_label_shows_order_position_part_heat_qty():
    from core.selection_labels import stage_record_label
    label = stage_record_label({"customer_order_no": "2417081", "order_position": "3"},
                               {"part_number": "10.11696", "fsi_part_number": "K11696", "part_name": "BOLT"},
                               reference="eqeqe777", stage="Forging → Production", heat="A68654", qty=300)
    for piece in ("CO 2417081", "Pos 3", "Part 10.11696", "FSI K11696", "BOLT", "Heat A68654", "Qty 300 pcs", "Ref eqeqe777", "Forging → Production"):
        assert piece in label, piece
    assert "kg" in stage_record_label({}, {}, qty=12.5, unit="kg")


def test_filter_labels_matches_every_word_case_insensitive():
    from core.selection_labels import filter_labels
    labels = {"a": "CO 2417081 · Pos 3 · Part 10.11696 · Heat A68654", "b": "CO 2423918 · Pos 1 · Part W160.2 · Heat A42863"}
    assert list(filter_labels(labels, "a68654 pos 3")) == ["a"]
    assert list(filter_labels(labels, "w160")) == ["b"]
    assert filter_labels(labels, "") == labels
    assert filter_labels(labels, "nothing-here") == {}


def test_downstream_and_stage_selectors_use_searchable_detailed_labels():
    page = read("app_pages/supply_chain.py")
    assert 'source_id=_find_select("Select Previous Stage Record",labels' in page
    for key in ('"supply_rm_receipt_po"', '"supply_rm_dispatch_receipt"', '"supply_forging_dispatch"', '"supply_forging_receipt_order"', '"supply_forging_direct_order"'):
        assert f"_find_select(" in page and key in page
    assert "def _find_select(" in page and "filter_labels(labels, query)" in page
    assert "def _stage_label(" in page and "stage_record_label(" in page


# ----------------------------------------------------------------------------- guided delete
def test_block_message_never_shows_raw_dict():
    from core.delete_service import clean_block_message
    raw = "{'message': 'This transaction has downstream linked records.', 'code': 'P0001', 'hint': None, 'details': None}"
    assert clean_block_message(RuntimeError(raw)) == "This transaction has downstream linked records."
    assert clean_block_message(RuntimeError("APIError: " + raw)) == "This transaction has downstream linked records."


def test_customer_order_delete_offers_remove_from_po():
    svc = read("core/delete_service.py")
    assert "def render_delete_blocked(" in svc and "def _customer_order_po_fix(" in svc
    assert "remove_order_from_po(" in svc and "verify_current_password(password)" in svc
    assert 'st.session_state[f"{key}_blocked"]' in svc  # explanation survives reruns
    service = read("core/supply_chain_service.py")
    assert '"qcms_remove_po_source"' in service and "def po_sources_for_customer_order(" in service
    sql = read("supabase/migrations/20261021110000_qcms_r35_supply_chain.sql")
    assert "create or replace function public.qcms_remove_po_source(" in sql
    assert "qcms_effective_module_permission('SUPPLY_CHAIN', 'edit')" in sql
    assert "already has % kg received" in sql and "is the only order on PO" in sql
    assert "grant execute on function public.qcms_remove_po_source(uuid, text) to authenticated" in sql


# ----------------------------------------------------------------------------- RM PO clubbing
class _Svc:
    pass


def _service(**methods):
    from core.supply_chain_service import SupplyChainService
    svc = SupplyChainService.__new__(SupplyChainService)
    svc._page_cache = {}
    for name, fn in methods.items():
        setattr(svc, name, fn)
    return svc


def test_clubbed_rm_group_is_split_by_price_instead_of_failing():
    prices = {"p1": 290.6, "p2": 301.0, "p3": 290.6}
    svc = _service(current_price=lambda part_id, supplier_id, **kw: prices[part_id])
    members = [{"part": {"id": pid, "hsn_sac_code": "7228"}, "raw": {"id": "r" + pid}, "order": {"id": "o" + pid}, "allocation": 100.0} for pid in ("p1", "p2", "p3")]
    groups = {"RM_SECTION|g|bar|85": {"part": members[0]["part"], "raw": members[0]["raw"], "quantity": 300.0, "orders": [], "members": members}}
    out = svc._split_rm_groups_by_price(groups, "sup", "2026-10-21")
    assert len(out) == 2
    qty = sorted(round(g["quantity"]) for g in out.values())
    assert qty == [100, 200]
    assert all(g.get("split") and g.get("base_key") == "RM_SECTION|g|bar|85" for g in out.values())
    single = svc._split_rm_groups_by_price({"k": {"members": members[:1], "part": {}, "raw": {}, "quantity": 1}}, "sup", "2026-10-21")
    assert list(single) == ["k"]


def test_rm_club_mismatch_is_explained_per_order():
    page = read("app_pages/supply_chain.py")
    assert "_explain_rm_club_mismatch(service, selected_orders" in page
    assert "do not share one common supplier-specific Raw Material record" not in page
    assert "is missing on:" in page and "_warn_rm_identity_differences(" in page


# ----------------------------------------------------------------------------- PO qty / inward
def test_po_line_quantity_is_editable():
    page = read("app_pages/supply_chain.py")
    assert 'disabled=["Item ID", "Finished Part", "UOM", "Received Qty"],' in page
    service = read("core/supply_chain_service.py")
    assert "Ordered Qty is editable on the PO line" in service


def test_inward_over_receipt_tolerance():
    from core.supply_chain_service import SupplyChainService

    class Repo:
        def get(self, table, rid):
            return {"id": rid, "ordered_qty_kg": 1000, "supplier_order_no": "PD1"}

    svc = _service(rm_receipts=lambda: [{"rm_purchase_order_id": "po", "inward_lot_id": "x", "received_qty_kg": 600}],
                   inward_over_po_tolerance_pct=lambda: 10.0)
    svc.repo = Repo()
    assert SupplyChainService.check_inward_against_po(svc, "po", 300)["status"] == "OK"
    warn = SupplyChainService.check_inward_against_po(svc, "po", 480)
    assert warn["status"] == "WARN" and warn["excess_kg"] == 80
    assert SupplyChainService.check_inward_against_po(svc, "po", 600)["status"] == "BLOCK"
    assert SupplyChainService.check_inward_against_po(svc, "po", 600, "x")["status"] == "OK"  # editing the same inward


def test_inward_duplicate_grn_message_and_pre_check():
    from core.inward_service import inward_error_message
    msg = inward_error_message(RuntimeError('duplicate key value violates unique constraint "inward_lots_tenant_id_grn_number_part_id_heat_number_key"'), grn="G1", heat="H1")
    assert "GRN G1" in msg and "already exists" in msg
    page = read("app_pages/material_inward.py")
    assert "assert_inward_link_ready(supply_po_id" in page
    assert 'st.session_state["edit_inward_id"] = str(saved["id"])' in page
    assert "allow_over_tolerance=allow_over" in page


# ----------------------------------------------------------------------------- schedules
def test_six_month_schedule_override_plan():
    orders = [
        {"id": "past", "order_type": "MONTHLY_SCHEDULE", "customer_id": "c", "part_id": "p", "schedule_month": "2026-09-01", "order_qty_pcs": 100, "status": "OPEN", "customer_delivery_date": "2026-09-01", "master_reference_no": "P_09_2026"},
        {"id": "cur", "order_type": "MONTHLY_SCHEDULE", "customer_id": "c", "part_id": "p", "schedule_month": "2026-10-01", "order_qty_pcs": 100, "status": "OPEN", "customer_delivery_date": "2026-10-01", "master_reference_no": "P_10_2026"},
        {"id": "nov", "order_type": "MONTHLY_SCHEDULE", "customer_id": "c", "part_id": "p", "schedule_month": "2026-11-01", "order_qty_pcs": 200, "status": "OPEN", "customer_delivery_date": "2026-11-01", "master_reference_no": "P_11_2026", "gross_weight_kg_snapshot": 2},
        {"id": "dec", "order_type": "MONTHLY_SCHEDULE", "customer_id": "c", "part_id": "p", "schedule_month": "2026-12-01", "order_qty_pcs": 50, "status": "OPEN", "customer_delivery_date": "2026-12-01", "master_reference_no": "P_12_2026"},
    ]
    consumed = {"cur": 0, "nov": 150, "dec": 0, "past": 100}
    svc = _service(customer_orders=lambda: orders,
                   totals=lambda oid: {"forging_ordered_pcs": consumed.get(oid, 0), "rm_ordered_kg": 0})
    months = [(9, 2026, 500, date(2026, 9, 1)), (10, 2026, 120, date(2026, 10, 1)), (11, 2026, 100, date(2026, 11, 1)),
              (12, 2026, 0, date(2026, 12, 1)), (1, 2027, 80, date(2027, 1, 1)), (2, 2027, 0, date(2027, 2, 1))]
    plan = svc.schedule_override_plan("c", "p", months, today=date(2026, 10, 21))
    actions = {r["Month"]: r["Action"] for r in plan}
    assert actions == {"09-2026": "PAST_LOCKED", "10-2026": "UPDATE", "11-2026": "BELOW_CONSUMED", "12-2026": "CANCEL", "01-2027": "INSERT"}
    nov = next(r for r in plan if r["Month"] == "11-2026")
    assert nov["_apply_qty"] == 150
    counts = svc.schedule_plan_counts(plan)
    assert counts["PAST_LOCKED"] == 1 and counts["INSERT"] == 1 and counts["CANCEL"] == 1


def test_schedule_on_po_is_not_cancelled():
    orders = [{"id": "nov", "order_type": "MONTHLY_SCHEDULE", "customer_id": "c", "part_id": "p", "schedule_month": "2026-11-01", "order_qty_pcs": 200, "status": "OPEN"}]
    svc = _service(customer_orders=lambda: orders, totals=lambda oid: {"rm_ordered_kg": 400})
    plan = svc.schedule_override_plan("c", "p", [(11, 2026, 0, date(2026, 11, 1))], today=date(2026, 10, 21))
    assert plan[0]["Action"] == "LOCKED_LINKED"


def test_schedule_entry_uses_override_preview():
    page = read("app_pages/supply_chain.py")
    assert "schedule_override_plan(" in page and "apply_schedule_override(schedule_plan" in page
    assert "SCHEDULE REVISION PREVIEW" in page


# ----------------------------------------------------------------------------- stage stock
def test_live_stage_stock_panel_and_rpc():
    page = read("app_pages/supply_chain.py")
    assert page.count("_stage_stock_panel(service") >= 3
    sql = read("supabase/migrations/20261021110000_qcms_r35_supply_chain.sql")
    assert "create or replace function public.qcms_part_stage_stock(p_part_id uuid, p_heat_number text default null)" in sql
    for key in ("'stages'", "'available_pcs'", "'pending_at_forger_pcs'", "'fg_stock_pcs'", "'at_fsi_kg'"):
        assert key in sql, key
    service = read("core/supply_chain_service.py")
    assert '"qcms_part_stage_stock"' in service and "_part_stage_stock_fallback" in service
