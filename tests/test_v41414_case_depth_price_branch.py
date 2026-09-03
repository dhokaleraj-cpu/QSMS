from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = "41414-LAYOUT-CASE-DEPTH-RM-PRICE-COMPANY-BRANCH"


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v41414_version_and_build() -> None:
    assert (ROOT / "VERSION").read_text().strip() in {"4.14.14", "4.14.15", "4.14.16", "4.14.17", "4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23", "4.14.24", "4.14.25", "4.14.26", "4.14.27", "4.14.28"}
    assert BUILD in _text("streamlit_app.py") or "41415-DIRECT-PRODUCTION-FLOW-EMAIL-TEMPLATE-TEST" in _text("streamlit_app.py")


def test_case_depth_is_derived_only_from_additional_layout_parameter() -> None:
    metlab = _text("app_pages/metlab_report.py")
    reporting = _text("core/reporting.py")
    assert "def _case_depth_layout_locations" in metlab
    assert 'CASE_DEPTH_PARAMETER_RE.search(_case_depth_parameter(row))' in metlab
    assert 'row.get("parameter") or row.get("characteristic")' in metlab
    assert "Locations and specifications below are controlled by Additional Layout Characteristics" in metlab
    assert "layout_rows=layout_source" in metlab
    assert "case_depth_source_rows" not in metlab
    assert '"Controlled Parameter", "Specification"' in reporting
    assert "The first Case Depth traverse reading must start at 0.05 mm." in metlab


def test_rm_price_lookup_is_raw_detail_specific_with_uom_fallback() -> None:
    service = _text("core/supply_chain_service.py")
    part = _text("app_pages/part_master.py")
    supply = _text("app_pages/supply_chain.py")
    assert "raw_material_detail_id: str | None = None" in service
    assert "exact_raw = [r for r in rows" in service
    assert "exact_uom = [r for r in covering" in service
    assert "if exact_uom:" in service
    assert 'raw_material_detail_id=str(raw.get("id") or "") or None' in supply
    assert '"raw_material_detail_id": selected_raw_id' in part
    assert '("part_id", "supplier_id", "raw_material_detail_id", "uom", "start_date")' in part


def test_company_branch_master_and_po_ship_to_branch_are_registered() -> None:
    app = _text("streamlit_app.py")
    master = _text("app_pages/master_home.py")
    service = _text("core/supply_chain_service.py")
    supply = _text("app_pages/supply_chain.py")
    reporting = _text("core/purchase_order_reporting.py")
    migration = _text("supabase/migrations/20260826173000_qcms_case_depth_price_branch_v41414.sql")
    assert "company-branch-entry" in app and "company-branch-records" in app
    assert "Company Branch Master" in master
    assert '"BRANCH": "Company Branch Master"' in supply
    assert "Company Branch / Plant" in supply
    assert "ship_to_branch_id" in supply and "company_branch_id" in service
    assert "PLANT / COMPANY BRANCH" in reporting
    assert "create table if not exists public.company_branches" in migration
    assert "ship_to_source_type in ('BRANCH','CUSTOMER','SUPPLIER','VENDOR')" in migration


def test_branch_context_is_visible_across_authenticated_modules() -> None:
    ui = _text("core/ui.py")
    branch = _text("core/branch_context.py")
    assert "resolve_current_branch" in ui
    assert "Branch {safe(branch_code)}" in ui
    assert "Employee Master``plant``" not in branch  # sanity: docstring uses normal formatting
    assert "Employee Master" in branch and "plant" in branch
