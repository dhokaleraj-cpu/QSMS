from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def txt(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v4136_release_and_build_markers():
    assert (ROOT / "VERSION").read_text().strip() in {"4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10"}
    marker = "4136-RMTC-OSP-TEXT-LAYOUT-SOURCES"
    assert marker in txt("core/ui.py")
    assert marker in txt("core/auth.py")


def test_approved_rmtc_can_add_compatible_part_without_blocking_existing_parts():
    ui = txt("app_pages/rmtc_pages.py")
    svc = txt("core/rmtc_service.py")
    sql = txt("supabase/migrations/20260821170000_qcms_rmtc_osp_text_layout_sources_v4136.sql")
    assert "ADD PART NUMBER TO APPROVED RMTC" in ui
    assert "add_part_to_approved_rmtc" in ui
    assert "qsms_add_part_to_approved_rmtc" in svc
    assert "existing_parts_remain_released" in sql
    assert "selected Part Material Grade does not match this RMTC Heat Material Grade" in sql


def test_metlab_has_separate_supplier_and_osp_vendor_master_fields():
    page = txt("app_pages/metlab_report.py")
    osp = txt("app_pages/osp_inspections.py")
    service = txt("core/inspection_service.py")
    reporting = txt("core/reporting.py")
    assert 'selectbox("Supplier"' in page
    assert 'selectbox("OSP Vendor"' in page
    assert '"osp_vendor_id": osp_vendor_id or None' in page
    assert '"osp_vendor_id": job.get("vendor_id")' in osp
    assert 'record.get("osp_vendor_id")' in service
    assert '["OSP Vendor", osp_vendor_name' in reporting


def test_osp_sample_selection_shows_vendor_batch_and_partial_receipts_are_supported():
    page = txt("app_pages/osp_transactions.py")
    svc = txt("core/osp_service.py")
    sql = txt("supabase/migrations/20260821170000_qcms_rmtc_osp_text_layout_sources_v4136.sql")
    assert "Vendor Batch" in page
    assert "Receipt Batch Qty (pcs)" in page
    assert "Balance at Vendor pcs" in page
    assert "def receipts" in svc
    assert "create table if not exists public.osp_receipts" in sql
    assert "receipt_status=case when new_total>=quantity_dispatched then 'COMPLETE' else 'PARTIAL' end" in sql


def test_approved_sources_removed_from_reference_master_and_controlled_in_part_master():
    ref = txt("app_pages/reference_master.py")
    imp = txt("app_pages/master_import.py")
    part = txt("app_pages/part_master.py")
    ref_keys = ref.split("REFERENCE_KEYS", 1)[1].split(")", 1)[0]
    assert "approved_sources" not in ref_keys
    assert "approved_sources" not in imp
    assert "Approved Suppliers" in part
    assert "Approved Steel Mills" in part
    assert "part_supplier_links" in part


def test_all_layout_characteristics_support_number_or_text_with_75pct_matching():
    layout = txt("app_pages/inspection_layouts.py")
    part = txt("app_pages/part_master.py")
    svc = txt("core/inspection_service.py")
    sql = txt("supabase/migrations/20260821170000_qcms_rmtc_osp_text_layout_sources_v4136.sql")
    assert 'options=["NUMBER", "TEXT"]' in layout
    assert 'options=["NUMBER", "TEXT"]' in part
    assert "SequenceMatcher" in svc
    assert "< 0.75" in svc
    assert "characteristic_type text not null default 'NUMBER'" in sql
    assert "specification_text text" in sql


def test_duplicate_master_validation_uses_two_or_three_significant_words():
    master = txt("core/master_service.py")
    imp = txt("app_pages/master_import.py")
    assert "def _significant_words" in master
    assert "def _fuzzy_word_duplicate" in master
    assert "needed = 2 if" in master or "needed=2 if" in master
    assert "else 3" in master
    assert "duplicate_match" in imp


def test_heat_transaction_report_has_quantity_and_balance_kilos():
    reports = txt("app_pages/reports.py")
    assert '"Qty kg": "steel_quantity_kg"' in reports
    assert '"Balance kg": "current_heat_balance_kg"' in reports


def test_v4136_migration_contains_separate_metlab_vendor_and_text_metallurgy():
    sql = txt("supabase/migrations/20260821170000_qcms_rmtc_osp_text_layout_sources_v4136.sql")
    assert "add column if not exists osp_vendor_id" in sql
    assert "part_metallurgical_characteristic_type_check" in sql
    assert "TEXT" in sql and "NUMBER" in sql
    assert "qsms_receive_osp_batch" in sql
