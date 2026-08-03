from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_heat_columns_and_category_colors():
    dashboard = (ROOT / "app_pages/dashboard.py").read_text()
    ui = (ROOT / "core/ui.py").read_text()
    assert "Global Heat Qty kg" in dashboard
    assert "Global Heat Balance kg" in dashboard
    assert '"#D97706"' in dashboard  # pending / hold orange
    assert '"#15803D"' in dashboard  # accepted / released green
    assert '"#B91C1C"' in dashboard  # rejected red
    assert 'item.get("color")' in ui and 'item.get("background")' in ui


def test_osp_pages_and_navigation_are_registered():
    app = (ROOT / "streamlit_app.py").read_text()
    for route in ("osp-home", "osp-material-out", "osp-sample-receipt", "osp-inward", "osp-dimensional", "osp-metlab", "osp-records"):
        assert route in app
    assert '"OSP": (' in app
    assert 'st.columns(8' in app


def test_part_master_and_layout_have_osp_classification():
    part = (ROOT / "app_pages/part_master.py").read_text()
    layouts = (ROOT / "app_pages/inspection_layouts.py").read_text()
    service = (ROOT / "core/inspection_service.py").read_text()
    for token in ("PROCESS & INWARD SPECIFICATIONS", "Process Type", "Inward Type", "Process Specification", "part_process_specifications"):
        assert token in part
    assert 'inward_type = c2.selectbox' in layouts
    assert 'eq["inward_type"] = inward_type' in service


def test_osp_database_quality_gates_and_genealogy():
    migration = (ROOT / "supabase/migrations/20260803231000_qsms_osp_transactions_v490.sql").read_text()
    for token in (
        "create table if not exists public.part_process_specifications",
        "qsms_create_osp_dispatch",
        "qsms_record_osp_sample",
        "qsms_receive_osp_batch",
        "qsms_refresh_osp_quality_gate",
        "OSP_SAMPLE",
        "OSP_RECEIPT",
        "v_qsms_osp_register",
        "v_qsms_osp_dispatch_candidates",
        "Full OSP inward requires Accepted or Accepted Under Reserve",
    ):
        assert token in migration


def test_osp_inspections_only_use_matching_osp_layouts():
    page = (ROOT / "app_pages/osp_inspections.py").read_text()
    assert 'process_id=str(job.get("process_id"))' in page
    assert 'inward_type="OSP_PROCESS"' in page
    assert "PROCESS-SPECIFIC INSPECTION PARAMETERS" in page
    assert "Pre-inward Sample" in page
    assert "Post-receipt Full Batch" in page
