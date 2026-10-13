"""R22: clear delete reasons + fixes, status in selection lists, Customer PO/Pos/Part labels,
opening stock at supplier/vendor, Part Designation (K4404-0, -10, -20) and price-history auto close."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Repo:
    def __init__(self, tables):
        self.tables = tables
    def select(self, table, *, eq=None, in_=None, limit=500, **_):
        rows = list(self.tables.get(table, []))
        for k, v in (eq or {}).items():
            rows = [r for r in rows if str(r.get(k)) == str(v)]
        for k, vals in (in_ or {}).items():
            rows = [r for r in rows if str(r.get(k)) in {str(x) for x in vals}]
        return rows[:limit]
    def rpc(self, *a, **k):
        return None


def test_db_message_strips_postgrest_dict():
    from core.db_errors import db_message
    raw = "{'message': 'This transaction has downstream linked records.', 'code': 'P0001', 'hint': None, 'details': None}"
    assert db_message(raw) == "This transaction has downstream linked records."
    assert db_message(ValueError("plain")) == "plain"


def test_customer_order_blockers_name_po_and_fix_and_skip_cancelled():
    from core.record_history import linked_records
    repo = Repo({
        "supply_purchase_orders": [{"id": "po1", "po_number": "PD9121000079", "status": "PENDING_APPROVAL"}, {"id": "po2", "po_number": "PD9121000080", "status": "CANCELLED"}],
        "supply_purchase_order_sources": [{"id": "s1", "purchase_order_id": "po1", "customer_order_id": "co1"}, {"id": "s2", "purchase_order_id": "po2", "customer_order_id": "co1"}],
    })
    rows = linked_records(repo, "supply_customer_orders", "co1")
    assert len(rows) == 1
    assert rows[0]["Reference"] == "PD9121000079" and rows[0]["Belongs To"] == "PO PD9121000079 [PENDING APPROVAL]"
    assert "Cancel or delete Purchase Order PD9121000079" in rows[0]["How to fix"]


def test_po_blockers_look_through_own_rows():
    from core.record_history import linked_records
    repo = Repo({
        "supply_purchase_order_items": [{"id": "i1", "purchase_order_id": "po1"}],
        "supply_rm_purchase_orders": [{"id": "st1", "purchase_order_id": "po1", "customer_order_id": "co1"}],
        "supply_rm_receipts": [{"id": "r1", "rm_purchase_order_id": "st1", "receipt_number": "RMR-0007"}],
        "supply_purchase_orders": [{"id": "po1", "po_number": "PD1", "status": "APPROVED"}],
    })
    rows = linked_records(repo, "supply_purchase_orders", "po1")
    assert [r["Reference"] for r in rows] == ["RMR-0007"] and "Delete RM Receipt RMR-0007" in rows[0]["How to fix"]


def test_customer_order_delete_uses_dedicated_rpc():
    from core.delete_service import DEDICATED_DELETE_RPCS
    assert DEDICATED_DELETE_RPCS["supply_customer_orders"] == ("qcms_delete_customer_order", "p_customer_order_id")
    sql = (ROOT / "supabase/migrations/20261014100000_qcms_r22_delete_price_opening_designation.sql").read_text()
    for token in ("function public.qcms_delete_customer_order(p_customer_order_id uuid)", "status = 'CANCELLED'", "set end_date = new.start_date - 1",
                  "stock_location in ('FSI','SUPPLIER','VENDOR')", "'CASTING'", "part_designation", "qcms_part_designation_base"):
        assert token in sql


def test_status_and_customer_order_labels():
    from core.selection_labels import customer_order_label, part_label, party_label, with_status
    assert part_label({"part_number": "4028", "status": "INACTIVE"}).endswith("[INACTIVE]")
    assert party_label({"party_name": "ARORA", "status": "ACTIVE"}).endswith("[ACTIVE]")
    assert with_status("X [ACTIVE]", {"status": "ACTIVE"}) == "X [ACTIVE]"
    label = customer_order_label({"customer_order_no": "45001", "order_position": "10", "master_reference_no": "2423725", "status": "OPEN"}, {"part_number": "4028", "fsi_part_number": "K4404"})
    assert label.startswith("Customer PO 45001 · Pos 10 · Part 4028 · FSI K4404 · Ref 2423725") and label.endswith("[OPEN]")
    sc = (ROOT / "app_pages/supply_chain.py").read_text()
    assert sc.count("service.order_label(") >= 7 and "f\"{r.get('master_reference_no')} · Pos" not in sc


def test_opening_stock_location_rules():
    import pytest
    from core.supply_chain_service import SupplyChainService, OPENING_STAGE_CODES

    class R:
        def get(self, t, i): return {"id": i}
        def insert(self, t, p): return p
        def update(self, t, i, p): return p
    svc = SupplyChainService.__new__(SupplyChainService); svc.repo = R()
    assert "CASTING" in OPENING_STAGE_CODES
    saved = svc.save_opening_stock({"part_id": "p", "stage": "CASTING", "quantity_pcs": 5, "stock_location": "VENDOR", "location_party_id": "v1"})
    assert saved["stock_location"] == "VENDOR" and saved["location_party_id"] == "v1"
    with pytest.raises(ValueError, match="Select the Supplier"):
        svc.save_opening_stock({"part_id": "p", "stage": "RAW_MATERIAL", "quantity_kg": 100, "stock_location": "SUPPLIER"})
    assert svc.save_opening_stock({"part_id": "p", "stage": "FORGING", "quantity_pcs": 1, "location_party_id": "x"})["location_party_id"] is None


def test_part_designation_auto_numbers():
    from app_pages.npd_apqp import auto_operation_numbers, part_designation_base
    assert part_designation_base({"fsi_part_number": "K 4404", "part_number": "4028"}) == "K4404"
    procs = {"Forging": {"process_name": "Forging"}, "Facing": {"process_name": "Face & Bore"}, "Turning": {"process_name": "Turning"}}
    rows = auto_operation_numbers([{"Process": "Forging"}, {"Process": "Facing"}, {"Process": "Turning"}], procs)
    assert [r["Operation No."] for r in rows] == [0, 10, 20]
    page = (ROOT / "app_pages/npd_apqp.py").read_text()
    assert "Part Designations (generated automatically)" in page and '"npd_process_flow_steps", str(match["id"]), {"operation_no": 900000 + index}' in page
