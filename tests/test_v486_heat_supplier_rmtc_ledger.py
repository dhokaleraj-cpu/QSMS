from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v486_version_and_migration():
    assert (ROOT / "VERSION").read_text().strip() == "4.8.6"
    sql = (ROOT / "supabase/migrations/20260802213000_qsms_heat_supplier_rmtc_ledger_v486.sql").read_text()
    for token in [
        "normalized_supplier_rmtc_number",
        "uq_rmtc_heat_supplier_rmtc_number",
        "Supplier RMTC Number is required",
        "trg_heat_part_supplier_duplicate",
        "v_qsms_heat_steel_ledger",
        "heat_balance_quantity_kg",
        "heat_balance_status",
    ]:
        assert token in sql


def test_same_heat_is_controlled_by_supplier_rmtc_number_not_supplier_part():
    sql = (ROOT / "supabase/migrations/20260802213000_qsms_heat_supplier_rmtc_ledger_v486.sql").read_text()
    assert "drop trigger if exists trg_heat_part_supplier_duplicate" in sql
    assert "normalized_heat_number,normalized_supplier_rmtc_number" in sql
    assert "Enter a different Supplier RMTC Number" in sql


def test_heat_ledger_page_has_required_quantities_and_export():
    page = (ROOT / "app_pages/records_center.py").read_text()
    for token in [
        "Heat Steel Ledger",
        "Global Heat Qty kg",
        "Supplier RMTC Number",
        "Planned Steel kg",
        "Inward Steel kg",
        "Heat Balance kg",
        "Heat Validation",
        "Download Heat Steel Ledger",
    ]:
        assert token in page


def test_rmtc_entry_checks_supplier_rmtc_duplicate_and_opens_ledger():
    page = (ROOT / "app_pages/rmtc_pages.py").read_text()
    service = (ROOT / "core/rmtc_service.py").read_text()
    assert "supplier_rmtc_duplicate" in page
    assert "different Supplier RMTC Number" in page
    assert "Open Heat Steel Ledger" in page
    assert "v_qsms_heat_steel_ledger" in service
    assert "normalize_supplier_rmtc_number" in service


def test_heat_ledger_route_is_registered():
    app = (ROOT / "streamlit_app.py").read_text()
    assert '("heat-ledger", st.Page(records_center.render_heat_ledger' in app
    assert 'url_path="heat-ledger"' in app
