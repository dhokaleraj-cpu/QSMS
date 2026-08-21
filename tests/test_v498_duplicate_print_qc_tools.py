from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_version_and_files():
    assert (ROOT / "VERSION").read_text().strip() in {"4.9.8", "4.9.9", "4.10.0", "4.10.1", "4.10.2", "4.10.3", "4.10.5", "4.10.6", "4.10.7", "4.10.8", "4.10.9", "4.11.0", "4.11.1", "4.11.2", "4.11.3", "4.11.4", "4.11.5", "4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4", "4.12.5", "4.12.6", "4.12.7", "4.12.8", "4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3", "4.13.4"}
    for path in (
        "app_pages/qc_calculation_tools.py",
        "core/hardness_conversion.py",
        "data/astm_e140_table1.json",
        "supabase/migrations/20260811114500_qcms_duplicate_qc_tools_npd_points_v498.sql",
        "docs/RELEASE_4_9_8.md",
    ):
        assert (ROOT / path).exists(), path


def test_qc_tools_navigation_and_storage_contract():
    app = (ROOT / "streamlit_app.py").read_text()
    page = (ROOT / "app_pages/qc_calculation_tools.py").read_text()
    migration = (ROOT / "supabase/migrations/20260811114500_qcms_duplicate_qc_tools_npd_points_v498.sql").read_text()
    for token in ("QC Calculation Tools", "qc-tools", "qc-calculation-records"):
        assert token in app
    for token in ("Jominy Calculator", "DI Value Calculator", "Hardness Conversion", "qc_calculation_records", "Download Selected Calculation PDF"):
        assert token in page
    assert "create table if not exists public.qc_calculation_records" in migration
    assert "QC_CALCULATION_TOOLS" in migration


def test_astm_e140_page3_table_and_approximate_warning():
    source = (ROOT / "core/hardness_conversion.py").read_text()
    data = (ROOT / "data/astm_e140_table1.json").read_text()
    assert "ASTM E 140-02 Table 1" in source
    assert '"HRC": 68.0' in data
    assert '"HV": 940.0' in data
    assert '"HRC": 20.0' in data
    assert '"HV": 238.0' in data
    assert "Extrapolation is not permitted" in source
    assert "approximate" in source.lower()


def test_npd_checkpoints_employee_links_and_pdf():
    page = (ROOT / "app_pages/npd_apqp.py").read_text()
    migration = (ROOT / "supabase/migrations/20260811114500_qcms_duplicate_qc_tools_npd_points_v498.sql").read_text()
    for token in ("PROCESS CHECKPOINTS / BULLET POINTS", "npd_process_flow_points", "npd_order_step_points", "Responsible Employee", "Download Process Flow PDF", "Download NPD Order Status PDF", "Download APQP Project PDF"):
        assert token in page
    for token in ("responsible_employee_id", "coordinator_employee_id", "owner_employee_id"):
        assert token in migration


def test_duplicate_guards_and_common_record_pdf():
    service = (ROOT / "core/master_service.py").read_text()
    migration = (ROOT / "supabase/migrations/20260811114500_qcms_duplicate_qc_tools_npd_points_v498.sql").read_text()
    reporting = (ROOT / "core/reporting.py").read_text()
    assert "assert_no_duplicate" in service
    assert "qcms_guard_process_duplicates" in migration
    assert "qcms_guard_stage_duplicates" in migration
    assert "controlled_record_pdf_bytes" in reporting
    for path in ("part_master.py", "process_master.py", "material_grade.py", "reference_master.py", "employee_master.py", "inspection_layouts.py", "osp_transactions.py"):
        assert "controlled_record_pdf_bytes" in (ROOT / "app_pages" / path).read_text()
