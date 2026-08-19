from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_version_and_supply_chain_files():
    assert tuple(map(int, (ROOT / "VERSION").read_text().strip().split("."))) >= (4, 12, 0)
    for rel in (
        "app_pages/supply_chain.py",
        "core/supply_chain_service.py",
        "supabase/migrations/20260819113132_qcms_supply_chain_flexible_inspections_v4120.sql",
    ):
        assert (ROOT / rel).exists()


def test_supply_chain_navigation_and_permission_module():
    app = (ROOT / "streamlit_app.py").read_text()
    access = (ROOT / "core/access.py").read_text()
    for route in (
        "supply-chain-home", "supply-customer-orders", "supply-rm-procurement", "supply-rm-receipt",
        "supply-rm-dispatch", "supply-forging", "supply-downstream", "supply-traceability",
    ):
        assert route in app
    assert '"Supply Chain": (' in app
    assert '("SUPPLY_CHAIN", "Supply Chain")' in access
    assert "st.columns(13" in app


def test_monthly_schedule_reference_and_database_guards():
    service = (ROOT / "core/supply_chain_service.py").read_text()
    assert 'return f"{part}_{int(month):02d}_{int(year):04d}"' in service
    sql = (ROOT / "supabase/migrations/20260819113132_qcms_supply_chain_flexible_inspections_v4120.sql").read_text()
    for table in (
        "supply_customer_orders", "supply_rm_purchase_orders", "supply_rm_receipts", "supply_forging_orders",
        "supply_rm_dispatches", "supply_forging_receipts", "supply_downstream_events",
    ):
        assert table in sql
    assert "required_rm_kg*1.25" in sql.replace(" ", "")
    assert "uq_supply_monthly_schedule" in sql
    assert "uq_supply_rm_po_order_supplier" in sql
    assert "uq_supply_forging_order_supplier" in sql
    assert "qcms_supply_validate_rm_dispatch" in sql


def test_flexible_dimensional_and_metlab_stages_without_rmtc_linkage():
    dim = (ROOT / "app_pages/dimensional_report.py").read_text()
    met = (ROOT / "app_pages/metlab_report.py").read_text()
    for token in ("RAW_MATERIAL_STAGE", "OSP_STAGE", "FINAL_DISPATCH_STAGE", "Standalone Stage Report"):
        assert token in dim
        assert token in met
    assert '"inward_lot_id":None' in met.replace(" ", "")
    assert '"inward_lot_id":None' in dim.replace(" ", "")


def test_part_raw_material_multiple_sections_and_supplier_location():
    part = (ROOT / "app_pages/part_master.py").read_text()
    assert "Raw Material Section" in part
    assert "Supplier Name / Location" in part
    assert "material_section_name" in part
    assert '("supplier_id", "material_section_name", "section_size", "forging_route")' in part


def test_clickable_npd_cards_and_overdue_flash():
    npd = (ROOT / "app_pages/npd_apqp.py").read_text()
    ui = (ROOT / "core/ui.py").read_text()
    assert "Update Selected NPD Card" in npd
    assert "Remarks shown on the card" in npd
    assert "npd_click_card_overdue" in ui
    assert "qcmsOverduePulse" in ui
    assert "animation:qcmsOverduePulse" in ui


def test_readability_and_card_height_contract():
    ui = (ROOT / "core/ui.py").read_text()
    assert "font-size:12.6px!important" in ui
    assert "font-size:15px!important" in ui
    assert "min-height:51px!important" in ui
    assert "min-height:106px!important" in ui
    assert "min-height:93px!important" in ui


def test_complaint_npd_style_status_cards():
    complaint = (ROOT / "app_pages/complaints.py").read_text()
    ui = (ROOT / "core/ui.py").read_text()
    assert "def _render_complaint_status_rows" in complaint
    assert "Customer & Supplier Complaint Status".upper() in complaint.upper()
    assert "complaint-stage-card" in complaint
    assert ".complaint-stage-strip" in ui
