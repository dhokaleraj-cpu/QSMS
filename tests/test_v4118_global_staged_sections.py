from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v4118_release_and_global_build():
    assert (ROOT / "VERSION").read_text().strip() in {"4.11.8", "4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4", "4.12.5", "4.12.6", "4.12.7", "4.12.8", "4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3", "4.13.4", "4.13.5", "4.13.6"}
    ui = (ROOT / "core/ui.py").read_text()
    auth = (ROOT / "core/auth.py").read_text()
    assert "4118-GLOBAL-STAGED-SECTIONS" in ui
    assert "4118-GLOBAL-STAGED-SECTIONS" in auth


def test_one_blue_family_progressive_grading_and_collapsed_default():
    ui = (ROOT / "core/ui.py").read_text()
    assert 'with st.expander(f"{letter} - {title}", expanded=False)' in ui
    for stage in "abcdefgh":
        assert f"st-key-fsi_stage_{stage}_" in ui
    for color in ("#E3F1FD", "#DAECFB", "#D1E7F9", "#C8E2F7", "#BFDCF5", "#B6D7F2", "#ADD2F0", "#A4CDEE"):
        assert color in ui
    assert "font-size:26px!important" in ui
    assert "font-weight:900!important" in ui
    assert "min-height:64px!important" in ui


def test_multi_section_workflows_use_global_stage_framework():
    expected = {
        "complaints.py": ("_complaint_details", "complaints_render_analysis_h"),
        "part_master.py": ("part_master_render_entry_a", "part_master_render_entry_h"),
        "material_grade.py": ("material_grade_render_entry_a", "material_grade_render_entry_b"),
        "process_master.py": ("process_master_render_entry_a", "process_master_render_entry_b"),
        "material_inward.py": ("material_inward_render_entry_a", "material_inward_render_entry_c"),
        "rmtc_pages.py": ("rmtc_pages_render_entry_a", "rmtc_pages_render_part_f"),
        "dimensional_report.py": ("dimensional_report_render_entry_a", "dimensional_report_render_entry_b"),
        "metlab_report.py": ("metlab_report_render_entry_a", "metlab_report_render_entry_e"),
        "osp_inspections.py": ("osp_inspections__render_a", "osp_inspections__render_c"),
        "npd_apqp.py": ("npd_apqp_render_process_flow_a", "npd_status_detail_e", "npd_apqp_render_apqp_b"),
        "user_access.py": ("user_access_create_a", "user_access_access_c"),
        "my_account.py": ("my_account_render_a", "my_account_render_b"),
    }
    for filename, tokens in expected.items():
        text = (ROOT / "app_pages" / filename).read_text()
        assert "stage_section(" in text
        for token in tokens:
            assert token in text


def test_multi_section_dashboard_inspection_reports_are_staged_too():
    expected = {
        "dashboard.py": ("dashboard_render_a", "dashboard_render_d"),
        "inspection_home.py": ("inspection_home_render_a", "inspection_home_render_c"),
        "reports.py": ("reports_heat_transactions_a", "reports_heat_transactions_b", "reports_osp_balance_a", "reports_osp_balance_b"),
        "osp_transactions.py": ("osp_records_a", "osp_records_c"),
    }
    for filename, tokens in expected.items():
        text = (ROOT / "app_pages" / filename).read_text()
        assert "stage_section(" in text
        for token in tokens:
            assert token in text
    # Records Centre already separates registers into tabs; it does not expose multiple simultaneous workflow sections.
    assert "st.tabs(" in (ROOT / "app_pages" / "records_center.py").read_text()
