from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_497_files_and_version():
    assert (ROOT / "VERSION").read_text().strip() in {"4.9.7", "4.9.8", "4.9.9", "4.10.0", "4.10.1", "4.10.2", "4.10.3", "4.10.5", "4.10.6", "4.10.7", "4.10.8", "4.10.9", "4.11.0", "4.11.1", "4.11.2", "4.11.3", "4.11.4", "4.11.5", "4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4", "4.12.5", "4.12.6", "4.12.7", "4.12.8", "4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3", "4.13.4", "4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0"}
    assert (ROOT / "docs" / "RELEASE_4_9_7.md").exists()
    assert (ROOT / "app_pages" / "npd_apqp.py").exists()
    assert (ROOT / "supabase" / "migrations" / "20260811103000_qcms_npd_apqp_process_flow_v497.sql").exists()


def test_top_level_npd_apqp_navigation_contract():
    source = (ROOT / "streamlit_app.py").read_text()
    for token in ("NPD / APQP", "NPD & APQP", "Process Flow Designer", "NPD Status", 'title="APQP"'):
        assert token in source
    assert '"npd-process-flow"' in source
    assert '"npd-status"' in source
    assert '"apqp"' in source
    assert "st.columns(13" in source


def test_process_flow_designer_uses_part_and_process_masters():
    source = (ROOT / "app_pages" / "npd_apqp.py").read_text()
    for token in (
        'repo.select("parts"', 'repo.select("processes"', "Operation No.", "Target Lead Days",
        'repo.insert("npd_process_flow_steps"', "Save Process Flow",
    ):
        assert token in source
    assert "duplicated. Each operation number must be unique" in source


def test_npd_order_status_realtime_target_date_contract():
    source = (ROOT / "app_pages" / "npd_apqp.py").read_text()
    for token in (
        "Order Qty (pcs)", "Customer Delivery Date", "Open Order Status", "ORDER PROCESS STATUS",
        "UPDATE PROCESS TARGETS & STATUS", "Overdue Processes", "Real-time Status", "target_date",
        "completed_date", "day(s) overdue", "Update Order Process Status",
    ):
        assert token in source
    for css in ("npd-completed", "npd-in_progress", "npd-pending", "npd-overdue", "npd-hold"):
        assert css in (ROOT / "core" / "ui.py").read_text()


def test_apqp_project_and_gate_tracking_contract():
    source = (ROOT / "app_pages" / "npd_apqp.py").read_text()
    for token in (
        "APQP PROJECT HEADER", "PPAP Submission Level", "Load Standard APQP Gates",
        "APQP Completion", "Update APQP Gates", 'repo.select("ppap_projects"',
        'repo.insert("ppap_documents"',
    ):
        assert token in source


def test_additive_database_and_permission_contract():
    migration = (ROOT / "supabase" / "migrations" / "20260811103000_qcms_npd_apqp_process_flow_v497.sql").read_text()
    for table in ("npd_process_flows", "npd_process_flow_steps", "npd_orders", "npd_order_steps"):
        assert f"create table if not exists public.{table}" in migration
        assert table in (ROOT / "core" / "repository.py").read_text()
    assert "NPD_APQP" in migration
    assert '("NPD_APQP", "NPD & APQP")' in (ROOT / "core" / "access.py").read_text()
    assert "alter table public.ppap_documents add column if not exists apqp_phase" in migration
    assert "alter table public.ppap_documents add column if not exists sequence_no" in migration
