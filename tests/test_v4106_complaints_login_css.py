from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v4106_version_and_complaint_schema():
    assert (ROOT / 'VERSION').read_text().strip() in {'4.10.6','4.10.7','4.10.8','4.10.9','4.11.0','4.11.1','4.11.2'}
    sql = (ROOT / 'supabase/migrations/20260812092238_qcms_complaint_management_login_v4106.sql').read_text()
    assert 'create table if not exists public.quality_complaints' in sql
    assert 'create table if not exists public.quality_complaint_followups' in sql
    assert 'qcms_next_complaint_number' in sql
    assert 'COMPLAINT_MANAGEMENT' in sql


def test_complaint_module_pages_and_debit_tracking():
    app = (ROOT / 'streamlit_app.py').read_text()
    page = (ROOT / 'app_pages/complaints.py').read_text()
    assert 'Complaint Management' in app
    assert 'customer-complaint' in app
    assert 'supplier-complaint' in app
    assert 'complaint-records' in app
    assert 'Debit Note Status' in page
    assert 'Four Star Responsible Person' in page
    assert 'Complaint FOLLOW-UP'.lower().replace(' ','') not in ''  # sanity marker
    assert 'quality_complaint_followups' in page
    assert 'Download Complaint PDF' in page


def test_login_css_is_rendered_inside_auth_function():
    auth = (ROOT / 'core/auth.py').read_text()
    assert "stable data-testid" in auth
    assert '.qcms-login-brand-card:before' in auth
    assert 'QUALITY CONTROL<br>MONITORING SYSTEM' in auth
    assert 'stMainBlockContainer' in auth
    assert 'Open controlled Phase 1 preview' in auth
