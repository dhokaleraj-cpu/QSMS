from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_4101_contract():
    assert (ROOT / "VERSION").read_text().strip() in {"4.10.1", "4.10.2", "4.10.3", "4.10.5", "4.10.6", "4.10.7", "4.10.8", "4.10.9", "4.11.0", "4.11.1", "4.11.2", "4.11.3", "4.11.4"}
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
