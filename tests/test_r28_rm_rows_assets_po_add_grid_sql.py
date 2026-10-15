"""R28: Part Master grid rows never move to another Part; recovery SQL; duplicate asset names
with unique asset numbers; instrument calibration without Part link; add Customer Orders to an
existing PO; cancelled PO releases orders; scrollable grids; automatic SQL apply."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


class MemRepo:
    def __init__(self, tables=None):
        self.tables = {k: [dict(r) for r in v] for k, v in (tables or {}).items()}
        self.n = 0
        self.rpcs = []

    def select(self, table, *, eq=None, in_=None, limit=500, **_):
        rows = [dict(r) for r in self.tables.get(table, [])]
        for k, v in (eq or {}).items():
            rows = [r for r in rows if str(r.get(k)) == str(v)]
        for k, vals in (in_ or {}).items():
            rows = [r for r in rows if str(r.get(k)) in {str(v) for v in vals}]
        return rows[:limit]

    def get(self, table, rid):
        return next((dict(r) for r in self.tables.get(table, []) if str(r.get("id")) == str(rid)), None)

    def insert(self, table, payload):
        self.n += 1
        row = {"id": f"{table}-{self.n}", **payload}
        self.tables.setdefault(table, []).append(row)
        return dict(row)

    def update(self, table, rid, payload):
        for row in self.tables.get(table, []):
            if str(row.get("id")) == str(rid):
                row.update(payload)
                return dict(row)
        raise KeyError(rid)

    def upsert_by(self, table, payload, natural_key):
        for row in self.tables.get(table, []):
            if all(str(row.get(k)) == str(v) for k, v in natural_key.items()):
                row.update(payload)
                return dict(row)
        return self.insert(table, payload)

    def delete(self, table, rid):
        self.tables[table] = [r for r in self.tables.get(table, []) if str(r.get("id")) != str(rid)]

    def rpc(self, name, params=None):
        self.rpcs.append((name, params))
        return {}


# ---------------------------------------------------------------- Part Master rows
def test_save_rows_never_moves_a_row_of_another_part():
    from app_pages.part_master import _save_rows
    repo = MemRepo({"part_raw_material_details": [
        {"id": "R160", "part_id": "K160", "supplier_id": "S1", "material_section_name": "Round Black Bar", "section_size": "85 MM", "status": "ACTIVE"},
    ]})
    frame = pd.DataFrame([{"supplier_id": "S1", "material_section_name": "Round Black Bar", "section_size": "85 MM"}])
    _save_rows(repo, "part_raw_material_details", "K11696", frame, ("part_id", "supplier_id", "material_section_name", "section_size"), lambda r, i: {k: v for k, v in dict(r).items()})
    rows = repo.tables["part_raw_material_details"]
    assert {r["part_id"] for r in rows} == {"K160", "K11696"}            # K160 keeps its row
    assert next(r for r in rows if r["id"] == "R160")["part_id"] == "K160"


def test_save_rows_rejects_a_grid_row_id_of_another_part():
    from app_pages.part_master import _save_rows
    repo = MemRepo({"part_raw_material_details": [{"id": "R160", "part_id": "K160", "supplier_id": "S1"}]})
    frame = pd.DataFrame([{"id": "R160", "supplier_id": "S1"}])
    try:
        _save_rows(repo, "part_raw_material_details", "K11696", frame, ("part_id", "supplier_id"), lambda r, i: {k: v for k, v in dict(r).items()})
    except ValueError as exc:
        assert "another Part" in str(exc)
    else:
        raise AssertionError("row of another Part must not be updated")
    assert repo.tables["part_raw_material_details"][0]["part_id"] == "K160"


def test_recovery_sql_contract():
    sql = (ROOT / "supabase/migrations/20261017100000_qcms_r28_part_rows_recovery_assets.sql").read_text()
    assert "restored by QCMS R28" in sql and "part_raw_material_technical_data" in sql
    assert "part_supplier_price_history" in sql and "part_jominy_requirements" in sql
    assert "qcms_r28_release_customer_order" in sql and "trg_qcms_r28_release_orders_after_po_cancel" in sql
    check = (ROOT / "supabase/migrations/20261017100000_qcms_r28_part_rows_recovery_assets.check.sql").read_text()
    assert "restored by QCMS R28" in check


# ---------------------------------------------------------------- assets / calibration
def test_asset_name_may_repeat_asset_number_unique():
    from core.master_service import MasterService
    assert MasterService._IDENTITY_DUPLICATE_FIELDS["quality_assets"] == ("asset_number",)
    src = (ROOT / "app_pages/master_import.py").read_text()
    assert 'extra_unique_fields = ("asset_number",)' in src


def test_instrument_calibration_without_part_link():
    src = (ROOT / "app_pages/calibration_validation.py").read_text()
    assert 'PART_LINKED_ASSET_TYPES = {"GAUGE", "FIXTURE", "JIG"}' in src
    assert "Direct calibration (no Part link)" in src


# ---------------------------------------------------------------- PO add orders / cancel
def _svc(repo):
    from core.supply_chain_service import SupplyChainService
    svc = SupplyChainService.__new__(SupplyChainService)
    svc.repo = repo
    svc._page_cache = {}
    return svc


def test_add_orders_uses_existing_po_and_clubs_same_item(monkeypatch):
    repo = MemRepo({
        "supply_purchase_orders": [{"id": "PO1", "po_number": "FSI-PO-7", "po_type": "RAW_MATERIAL", "status": "APPROVED", "supplier_id": "S1", "company_branch_id": "B1"}],
        "supply_purchase_order_items": [{"id": "I1", "purchase_order_id": "PO1", "item_no": "RB85", "raw_material_detail_id": "RM1", "unit_price": 70, "gst_percent": 18}],
        "supply_purchase_order_sources": [{"id": "S-1", "purchase_order_id": "PO1", "purchase_order_item_id": "I1", "customer_order_id": "CO1"}],
        "supply_rm_purchase_orders": [{"id": "ST1", "purchase_order_id": "PO1", "purchase_order_item_id": "I1", "customer_order_id": "CO1", "status": "APPROVED"}],
    })
    svc = _svc(repo)
    monkeypatch.setattr(svc, "purchase_order", lambda pid: repo.get("supply_purchase_orders", pid))
    monkeypatch.setattr(svc, "purchase_order_received_qty", lambda pid: 0.0)
    monkeypatch.setattr(svc, "rm_purchase_orders", lambda: repo.select("supply_rm_purchase_orders"))
    seen = {}

    def fake_create(payload):
        seen["number"] = svc._next_po_number()
        header = svc._insert_po_header({"po_number": "NEW"})
        seen["header"] = header
        item = repo.insert("supply_purchase_order_items", {"purchase_order_id": header["id"], "item_no": "rb85", "raw_material_detail_id": "RM1", "unit_price": 70})
        repo.insert("supply_purchase_order_sources", {"purchase_order_id": header["id"], "purchase_order_item_id": item["id"], "customer_order_id": "CO2"})
        repo.insert("supply_rm_purchase_orders", {"purchase_order_id": header["id"], "purchase_order_item_id": item["id"], "customer_order_id": "CO2", "status": "PENDING_APPROVAL"})
        return {"header": header, "items": [item]}

    monkeypatch.setattr(svc, "create_purchase_order", fake_create)
    monkeypatch.setattr(svc, "update_purchase_order", lambda pid, p: {"header": repo.get("supply_purchase_orders", pid)})
    result = svc.add_orders_to_purchase_order("PO1", {"customer_order_ids": ["CO2"], "allocations": {"CO2": 100}})
    assert seen["number"] == "FSI-PO-7" and seen["header"]["id"] == "PO1"       # no new PO / number
    assert result["added_orders"] == 1 and result["clubbed_lines"] == 1
    assert [i["id"] for i in repo.tables["supply_purchase_order_items"]] == ["I1"]  # clubbed into line I1
    assert {s["purchase_order_item_id"] for s in repo.tables["supply_purchase_order_sources"]} == {"I1"}
    assert getattr(svc, "_po_append_target", None) is None


def test_add_orders_rejects_duplicates_cancelled_and_received(monkeypatch):
    repo = MemRepo({
        "supply_purchase_orders": [{"id": "PO1", "po_type": "RAW_MATERIAL", "status": "PENDING_APPROVAL"}, {"id": "PO2", "po_type": "RAW_MATERIAL", "status": "CANCELLED"}],
        "supply_purchase_order_sources": [{"id": "S-1", "purchase_order_id": "PO1", "customer_order_id": "CO1"}],
        "supply_customer_orders": [{"id": "CO1", "master_reference_no": "K11696/OCT"}],
    })
    svc = _svc(repo)
    monkeypatch.setattr(svc, "purchase_order", lambda pid: repo.get("supply_purchase_orders", pid))
    monkeypatch.setattr(svc, "order", lambda oid: repo.get("supply_customer_orders", oid))
    received = {"v": 0.0}
    monkeypatch.setattr(svc, "purchase_order_received_qty", lambda pid: received["v"])
    for pid, payload, text in (("PO2", {"customer_order_ids": ["CO9"]}, "Cancelled"), ("PO1", {"customer_order_ids": ["CO1"]}, "already on this PO")):
        try:
            svc.add_orders_to_purchase_order(pid, payload)
        except ValueError as exc:
            assert text in str(exc)
        else:
            raise AssertionError(text)
    received["v"] = 5.0
    try:
        svc.add_orders_to_purchase_order("PO1", {"customer_order_ids": ["CO9"]})
    except ValueError as exc:
        assert "already been received" in str(exc)


def test_failed_addition_never_cancels_the_existing_po(monkeypatch):
    repo = MemRepo({"supply_purchase_orders": [{"id": "PO1", "po_type": "RAW_MATERIAL", "status": "APPROVED", "supplier_id": "S1"}]})
    svc = _svc(repo)
    monkeypatch.setattr(svc, "purchase_order", lambda pid: repo.get("supply_purchase_orders", pid))
    monkeypatch.setattr(svc, "purchase_order_received_qty", lambda pid: 0.0)
    monkeypatch.setattr(svc, "rm_purchase_orders", lambda: repo.select("supply_rm_purchase_orders"))

    def boom(payload):
        header = svc._insert_po_header({})
        repo.insert("supply_rm_purchase_orders", {"purchase_order_id": header["id"], "customer_order_id": "CO2", "status": "PENDING_APPROVAL"})
        svc._abort_purchase_order(header, RuntimeError("x"))
        raise ValueError("price missing")

    monkeypatch.setattr(svc, "create_purchase_order", boom)
    try:
        svc.add_orders_to_purchase_order("PO1", {"customer_order_ids": ["CO2"]})
    except ValueError:
        pass
    assert repo.get("supply_purchase_orders", "PO1")["status"] == "APPROVED"
    assert not [r for r in repo.rpcs if r[0] == "qcms_cancel_purchase_order"]
    assert repo.tables["supply_rm_purchase_orders"][0]["status"] == "CANCELLED"   # addition rolled back


def test_cancel_po_releases_customer_orders(monkeypatch):
    repo = MemRepo({"supply_purchase_order_sources": [{"id": "S1", "purchase_order_id": "PO1", "customer_order_id": "CO1"}]})
    svc = _svc(repo)
    monkeypatch.setattr(svc, "rm_purchase_orders", lambda: [])
    monkeypatch.setattr(svc, "forging_orders", lambda: [])
    synced = []
    monkeypatch.setattr(svc, "sync_order_status", lambda oid: synced.append(oid) or "OPEN")
    svc.cancel_purchase_order("PO1", "wrong supplier")
    assert repo.rpcs[0][0] == "qcms_cancel_purchase_order" and synced == ["CO1"]


def test_po_edit_ui_has_add_orders_and_all_fields():
    src = (ROOT / "app_pages/supply_chain.py").read_text()
    assert "def _render_po_add_orders" in src and "add_orders_to_purchase_order" in src
    assert '"currency": currency, "other_amount": other_amount' in src


# ---------------------------------------------------------------- grids / auto SQL
def test_grids_scroll_both_ways(monkeypatch):
    import core.ui as ui
    captured = []
    monkeypatch.setattr(ui.st, "markdown", lambda html, **_: captured.append(html))
    import core.excel_grid as eg   # R30 component path disabled -> HTML fallback is still scrollable
    monkeypatch.setattr(eg, "render_grid", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no components")))
    ui.portal_table(pd.DataFrame([{f"Col {c}": r for c in range(12)} for r in range(40)]))
    html = captured[-1]
    assert "qcms-scroll-grid" in html and f"max-height:{ui.GRID_MAX_HEIGHT}px" in html and "scroll / swipe" in html
    css = ui.GRID_SCROLL_CSS
    assert "overflow:auto" in css and "position:sticky" in css and ".dvn-scroller" in css
    assert "grid_scroll_css()" in (ROOT / "core/ui.py").read_text()


def test_auto_apply_sql_manifest_and_token_safety():
    manifest = json.loads((ROOT / "supabase/auto_apply.json").read_text())
    assert manifest["files"] == ["supabase/migrations/20261017100000_qcms_r28_part_rows_recovery_assets.sql"]
    for name in manifest["files"]:
        assert (ROOT / name).exists()
    src = (ROOT / "scripts/apply_sql.py").read_text()
    assert "qcms_applied_sql" in src and "find-generic-password" in src and "getpass" in src
    assert "@{headers}" in src   # token passed in a 0600 header file, never on the command line
    import scripts.apply_sql as apply_sql
    assert apply_sql.PROJECT_REF == "xxrxopzxzyjnzumrwuwy"
    assert apply_sql._lit("a'b") == "'a''b'"
