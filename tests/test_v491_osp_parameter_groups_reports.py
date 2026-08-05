from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_osp_parameter_group_schema_and_layout_generation():
    migration = (ROOT / "supabase/migrations/20260805084500_qsms_osp_parameter_groups_reports_v491.sql").read_text()
    for token in (
        "part_process_parameter_specifications",
        "process_specification_id",
        "inspection_type",
        "minimum_spec",
        "maximum_spec",
        "qsms_generate_osp_inspection_layouts",
        "source_process_specification_id",
        "PART_PROCESS_SPEC",
    ):
        assert token in migration


def test_part_master_groups_parameters_drawings_and_generated_layouts():
    page = (ROOT / "app_pages/part_master.py").read_text()
    for token in (
        "OSP PROCESS & INWARD SPECIFICATIONS",
        "Select OSP Process Group for Parameters and Drawing",
        "Select or add Parameters for this OSP Process",
        "Minimum",
        "Maximum",
        "Create / Update Inspection Layouts",
    ):
        assert token in page


def test_inspection_layout_loads_part_process_parameters():
    page = (ROOT / "app_pages/inspection_layouts.py").read_text()
    service = (ROOT / "core/inspection_service.py").read_text()
    assert "osp_parameter_characteristics" in service
    assert "Part Master OSP group loaded" in page
    assert "Download OSP Process Drawing" in page


def test_reports_routes_views_and_excel_exports():
    app = (ROOT / "streamlit_app.py").read_text()
    page = (ROOT / "app_pages/reports.py").read_text()
    migration = (ROOT / "supabase/migrations/20260805084500_qsms_osp_parameter_groups_reports_v491.sql").read_text()
    for route in ("reports-home", "heat-transaction-report", "osp-balance-report"):
        assert route in app
    for token in (
        "Heat Number Global Balance with Transactions",
        "Heat-wise OSP Inward, Outward and Balance",
        "Download Heat Balance and Transactions",
        "Download OSP Inward / Outward and Balance",
    ):
        assert token in page
    for view in (
        "v_qsms_heat_transaction_report",
        "v_qsms_heat_global_balance_report",
        "v_qsms_heat_osp_balance_report",
    ):
        assert view in migration
