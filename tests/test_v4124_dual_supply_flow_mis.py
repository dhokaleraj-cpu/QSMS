from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_and_visible_build_marker():
    assert (ROOT / "VERSION").read_text().strip() in {"4.12.4", "4.12.5", "4.12.6", "4.12.7", "4.12.8", "4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3", "4.13.4", "4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10"}
    assert "4124-DUAL-SUPPLY-FLOW-MIS" in (ROOT / "core/ui.py").read_text()
    assert "4124-DUAL-SUPPLY-FLOW-MIS" in (ROOT / "core/auth.py").read_text()


def test_two_supply_flow_contracts_are_present():
    service = (ROOT / "core/supply_chain_service.py").read_text()
    page = (ROOT / "app_pages/supply_chain.py").read_text()
    for token in (
        'FLOW_FSI_RM = "FSI_RM"',
        'FLOW_DIRECT_FORGING = "DIRECT_FORGING"',
        '"Flow 1 · RM Responsible FSI"',
        '"Flow 2 · RM Responsible Forger / Supplier"',
        "pending_direct_forging_orders",
    ):
        assert token in service
    for token in ("RM Procurement", "RM Receipt", "RM to Forger", "Forging Order", "Forging Receipt", "Part Production", "Dispatch"):
        assert token in page


def test_flow_storage_is_backward_compatible_without_new_database_columns():
    service = (ROOT / "core/supply_chain_service.py").read_text()
    assert "QCMS_SUPPLY_FLOW=" in service
    assert 'p["required_rm_kg"] = round(qty * gross, 3) if flow == FLOW_FSI_RM else 0.0' in service
    assert "Backwards compatibility" not in service or "Backward compatibility" in service
    assert "clean_flow_remarks" in service


def test_direct_flow_cannot_be_changed_after_transactions_start():
    service = (ROOT / "core/supply_chain_service.py").read_text()
    assert "Supply Chain Flow cannot be changed after linked procurement / forging / production / dispatch transactions have started." in service


def test_material_inward_has_explicit_supply_chain_link_switch():
    page = (ROOT / "app_pages/material_inward.py").read_text()
    service = (ROOT / "core/supply_chain_service.py").read_text()
    for token in ("Enable Supply Chain Link", "Linked RM Procurement", "Standalone Material Inward"):
        assert token in page
    assert "unlink_inward_supply_chain" in service


def test_order_mis_reports_monthly_schedule_against_dispatch():
    service = (ROOT / "core/supply_chain_service.py").read_text()
    page = (ROOT / "app_pages/supply_chain.py").read_text()
    for token in ("def order_mis_rows", "def monthly_mis_summary", "Dispatched pcs", "Pending Dispatch pcs", "Dispatch Achievement %"):
        assert token in service
    for token in ("Monthly Schedule / Order MIS", "ORDER / SCHEDULE MIS WITH CUSTOMER DISPATCH", "CUSTOMER / PART MONTHLY DISPATCH SUMMARY"):
        assert token in page


def test_order_mis_is_registered_in_supply_chain_navigation():
    app = (ROOT / "streamlit_app.py").read_text()
    assert "supply-order-mis" in app
    assert "Supply Order MIS" in app


def test_v4124_requires_no_manual_supabase_sql():
    # v4.12.4 reuses the existing v4.12.2 Supply Chain schema, so the release
    # remains a true one-command deployment with no separate SQL task.
    migrations = list((ROOT / "supabase/migrations").glob("*v4124*.sql"))
    assert migrations == []
