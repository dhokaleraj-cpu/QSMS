from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_build_and_migration_present():
    assert (ROOT / "VERSION").read_text().strip() in {"4.12.2", "4.12.3", "4.12.4", "4.12.5", "4.12.6", "4.12.7", "4.12.8", "4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3"}
    ui = (ROOT / "core/ui.py").read_text()
    auth = (ROOT / "core/auth.py").read_text()
    assert "4122-SUPPLY-CHAIN-MASTER-LINKED-TRACEABILITY" in ui
    assert "4122-SUPPLY-CHAIN-MASTER-LINKED-TRACEABILITY" in auth
    migration = ROOT / "supabase/migrations/20260820010000_qcms_supply_chain_master_linked_traceability_v4122.sql"
    assert migration.exists()


def test_supply_chain_sequential_pending_queues_and_inherited_lineage():
    service = (ROOT / "core/supply_chain_service.py").read_text()
    page = (ROOT / "app_pages/supply_chain.py").read_text()
    for token in (
        "pending_customer_orders_for_rm", "pending_rm_purchase_orders",
        "pending_rm_receipts_for_dispatch", "pending_rm_dispatches_for_forging_order",
        "pending_forging_orders", "pending_sources_for_downstream",
        "link_inward_to_rm_po", "Heat Number", "Heat Code",
    ):
        assert token in service or token in page
    assert '"rm_receipt_id":rec_id' in page
    assert '"source_forging_receipt_id"' in page
    assert '"source_event_id"' in page


def test_supply_chain_search_cards_edit_delete_and_exports():
    page = (ROOT / "app_pages/supply_chain.py").read_text()
    ui = (ROOT / "core/ui.py").read_text()
    for token in (
        "Global Search", "PDF Export", "Excel Export", "password_delete_panel",
        "supply-order-card", "supply-card-complete", "OVERDUE", "REJECTED",
    ):
        assert token in page or token in ui
    migration = (ROOT / "supabase/migrations/20260820010000_qcms_supply_chain_master_linked_traceability_v4122.sql").read_text()
    for table in (
        "supply_customer_orders", "supply_rm_purchase_orders", "supply_rm_receipts",
        "supply_rm_dispatches", "supply_forging_orders", "supply_forging_receipts",
        "supply_downstream_events",
    ):
        assert table in migration
    assert "qsms_delete_master_row" in migration


def test_customer_schedule_is_six_months_in_one_row_and_import_is_a_to_f():
    page = (ROOT / "app_pages/supply_chain.py").read_text()
    service = (ROOT / "core/supply_chain_service.py").read_text()
    assert "st.columns(6" in page
    assert "Six-month schedule entry" in page
    assert 'usecols="A:F"' in page
    for token in ('"Item"', '"Description"', '"Order no."', '"PosNr"', '"Quantity"', '"Delivery date"'):
        assert token in page
    assert "import_preview" in page and "apply_customer_order_import" in page
    assert "normalize_match" in service
    assert "confirm_updates" in service


def test_material_inward_is_rm_receipt_source_and_rmtc_fields_are_exposed():
    page = (ROOT / "app_pages/material_inward.py").read_text()
    supply = (ROOT / "app_pages/supply_chain.py").read_text()
    migration = (ROOT / "supabase/migrations/20260820010000_qcms_supply_chain_master_linked_traceability_v4122.sql").read_text()
    assert "supply_rm_po_link_id" in page
    assert "supply_rm_purchase_order_id" in page
    assert "link_inward_to_rm_po" in page
    for token in ("RMTC Number", "RMTC Date", "RMTC Qty kg"):
        assert token in supply
    for token in ("inward_lot_id", "rmtc_number", "rmtc_date", "rmtc_qty_kg", "qcms_supply_inherit_rm_receipt"):
        assert token in migration


def test_typography_and_duplicate_matching_rules():
    ui = (ROOT / "core/ui.py").read_text()
    masters = (ROOT / "core/master_service.py").read_text()
    assert "font-size:21px!important" in ui
    assert "font-size:13.9px!important" in ui
    assert "font-size:16.5px!important" in ui
    assert "_matching_words_value" in masters
    assert "Matching words already exist" in masters


def test_customer_import_parser_matches_attached_lte_format():
    service = (ROOT / "core/supply_chain_service.py").read_text()
    assert "def parse_import_quantity" in service
    assert r"\d{1,3}(?:\.\d{3})+" in service
    assert '"%d.%m.%Y"' in service
