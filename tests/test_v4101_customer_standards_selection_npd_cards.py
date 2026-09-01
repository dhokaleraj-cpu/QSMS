from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_4101_contract():
    assert (ROOT / "VERSION").read_text().strip() in {"4.10.1", "4.10.2", "4.10.3", "4.10.5", "4.10.6", "4.10.7", "4.10.8", "4.10.9", "4.11.0", "4.11.1", "4.11.2", "4.11.3", "4.11.4", "4.11.5", "4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4", "4.12.5", "4.12.6", "4.12.7", "4.12.8", "4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3", "4.13.4", "4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13", "4.14.14", "4.14.15", "4.14.16", "4.14.17", "4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23"}
    assert (ROOT / "docs/RELEASE_4_10_1.md").exists()
    assert (ROOT / "templates/Customer_Standards_Template.xlsx").exists()


def test_customer_standards_bank_and_part_process_links():
    migration = (ROOT / "supabase/migrations/20260812130000_qcms_customer_standards_selection_cards_v4101.sql").read_text()
    assert "create table if not exists public.customer_standards" in migration
    assert "create table if not exists public.part_standard_links" in migration
    assert "CUSTOMER_STANDARD" in migration
    app = (ROOT / "streamlit_app.py").read_text()
    assert 'url_path="standards-entry"' in app and 'url_path="standards-records"' in app
    part = (ROOT / "app_pages/part_master.py").read_text()
    assert "CUSTOMER STANDARDS & SPECIFICATIONS" in part
    assert "part_standard_links" in part
    assert "Save Linked Standards" in part
    assert "part_standard_download_" in part
    process = (ROOT / "app_pages/process_master.py").read_text()
    assert "RELATED CUSTOMER STANDARDS & SPECIFICATIONS" in process
    assert "customer_standards" in process


def test_rich_selection_and_npd_card_pdf():
    labels = (ROOT / "core/selection_labels.py").read_text()
    for token in ("party_label", "process_label", "part_label", "material_grade_label", "employee_label", "customer_standard_label"):
        assert f"def {token}" in labels
    rmtc = (ROOT / "app_pages/rmtc_pages.py").read_text()
    assert "party_label(r)" in rmtc
    npd = (ROOT / "app_pages/npd_apqp.py").read_text()
    assert "npd-order-status-row" in npd
    assert "npd-row-process-card" in npd
    assert "npd_pending_status_pdf_bytes" in npd
    reporting = (ROOT / "core/reporting.py").read_text()
    assert "def npd_pending_status_pdf_bytes" in reporting
    assert '#FFF7ED' in reporting and '#EFF6FF' in reporting and '#FEF2F2' in reporting and '#F0FDF4' in reporting
