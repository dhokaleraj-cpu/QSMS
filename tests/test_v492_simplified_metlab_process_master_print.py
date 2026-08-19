from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_and_release_files():
    assert (ROOT / "VERSION").read_text().strip() in {"4.9.2", "4.9.3", "4.9.4", "4.9.5", "4.9.6", "4.9.7", "4.9.8", "4.9.9", "4.10.0", "4.10.1", "4.10.2", "4.10.3", "4.10.5", "4.10.6", "4.10.7", "4.10.8", "4.10.9", "4.11.0", "4.11.1", "4.11.2", "4.11.3", "4.11.4", "4.11.5", "4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2"}
    assert (ROOT / "docs/RELEASE_4_9_2.md").exists()
    assert (ROOT / "supabase/migrations/20260805194500_qsms_simplified_metlab_process_master_print_v492.sql").exists()


def test_part_master_has_only_approved_metlab_requirement_sections():
    page = (ROOT / "app_pages/part_master.py").read_text()
    assert "OSP INSPECTION FOR METLAB" in page
    assert "METALLURGICAL REQUIREMENTS" in page
    assert "HEAT TREATMENT DETAILS" not in page
    assert "OSP PROCESS & INWARD SPECIFICATIONS" not in page
    assert page.count('"Parameter"') >= 2
    assert page.count('"Minimum Specification"') >= 2
    assert page.count('"Maximum Specification"') >= 2


def test_process_master_is_dedicated_and_not_duplicated():
    app = (ROOT / "streamlit_app.py").read_text()
    process = (ROOT / "app_pages/process_master.py").read_text()
    reference = (ROOT / "app_pages/reference_master.py").read_text()
    assert '"process-entry"' in app and '"process-records"' in app
    assert "Process Code" in process and "Process Type" in process
    reference_keys = reference.split("REFERENCE_KEYS", 1)[1].split(")", 1)[0]
    assert '"processes"' not in reference_keys


def test_requirement_schema_and_generated_layouts():
    migration = (ROOT / "supabase/migrations/20260805194500_qsms_simplified_metlab_process_master_print_v492.sql").read_text()
    for token in (
        "part_metallurgical_requirements",
        "minimum_spec",
        "maximum_spec",
        "OSP_METLAB",
        "FINAL_METALLURGICAL",
        "qsms_generate_final_metallurgical_layout",
        "v_qsms_osp_metlab_requirements",
        "v_qsms_part_metallurgical_requirements",
    ):
        assert token in migration


def test_osp_queue_skips_non_required_inspection_types():
    service = (ROOT / "core/osp_service.py").read_text()
    assert 'requirement_flag = "dimensional_required" if report_type == "DIMENSIONAL" else "metlab_required"' in service
    assert "if not bool(row.get(requirement_flag))" in service


def test_single_navigation_and_export_shipment_theme():
    ui = (ROOT / "core/ui.py").read_text()
    app = (ROOT / "streamlit_app.py").read_text()
    suppressed = ui.split("def subpage_navigation", 1)[1].split("def module_submenu", 1)[0]
    assert "return None" in suppressed
    assert "linear-gradient(110deg,#082F5C" in ui
    assert "menu_active_{slug}" in app
    assert "MODULES" in app


def test_report_print_header_footer_and_excel_theme():
    reporting = (ROOT / "core/reporting.py").read_text()
    reports = (ROOT / "app_pages/reports.py").read_text()
    requirements = (ROOT / "requirements.txt").read_text()
    for token in ("FOUR STAR INDUSTRIES", "QUALITY CONTROL MONITORING SYSTEM", "Page {self._pageNumber} of {page_count}"):
        assert token in reporting
    assert "report_pdf_bytes" in reports
    assert "oddHeader" in reports and "oddFooter" in reports
    assert "reportlab" in requirements
