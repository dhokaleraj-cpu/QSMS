from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reference_masters_have_auto_code_metadata():
    text = (ROOT / "core" / "master_definitions.py").read_text()
    for fragment in [
        'auto_code_field="party_code"',
        'auto_code_field="source_code"',
        'auto_code_field="process_code"',
        'auto_code_field="stage_code"',
        'auto_code_field="asset_code"',
    ]:
        assert fragment in text


def test_auto_code_rpc_and_migration_present():
    service = (ROOT / "core" / "master_service.py").read_text()
    migration = (ROOT / "supabase" / "migrations" / "20260802161000_qsms_auto_master_codes_dashboard_v482.sql").read_text()
    assert "def next_master_code" in service
    assert "qsms_next_master_code" in service
    assert "create or replace function public.qsms_next_master_code" in migration.lower()
    for prefix in ["CUST", "SUP", "MILL", "OSPV", "SRC", "PROC", "STG", "AST"]:
        assert prefix in migration


def test_reference_entry_prefills_editable_generated_code():
    text = (ROOT / "app_pages" / "reference_master.py").read_text()
    assert "_qsms_auto_master_code_" in text
    assert "Generated automatically for new records" in text
    assert "service.next_master_code" in text


def test_dashboard_has_multiple_kpis_and_three_pie_charts():
    text = (ROOT / "app_pages" / "dashboard.py").read_text()
    for label in ["RMTC Steel kg", "Inward Steel kg", "Planned Production", "Accepted Production"]:
        assert label in text
    assert 'section_bar("STATUS PIE CHARTS")' in text
    assert '_donut("Recent Inwards"' in text
    assert '_donut("RMTC Validation Status"' in text
    assert '_donut("Inward Status"' in text
    assert "px.pie" in text


def test_release_version_482():
    assert tuple(map(int,(ROOT / "VERSION").read_text().strip().split("."))) >= (4,8,2)
    assert (ROOT / "docs" / "RELEASE_4_8_2.md").exists()
