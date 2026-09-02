from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_version_4107():
    assert (ROOT / "VERSION").read_text().strip() in {"4.10.7", "4.10.8", "4.10.9", "4.11.0", "4.11.1", "4.11.2", "4.11.3", "4.11.4", "4.11.5", "4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4", "4.12.5", "4.12.6", "4.12.7", "4.12.8", "4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3", "4.13.4", "4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13", "4.14.14", "4.14.15", "4.14.16", "4.14.17", "4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23", "4.14.24", "4.14.25", "4.14.26", "4.14.27"}


def test_detailed_complaint_analysis_route_and_ui():
    nav = (ROOT / "streamlit_app.py").read_text()
    page = (ROOT / "app_pages/complaints.py").read_text()
    assert 'complaint-analysis' in nav
    assert 'def render_analysis()' in page
    assert 'Why 5' in page
    assert 'Occurrence Root Cause - Why defect happened' in page
    assert 'Escape / Detection Root Cause - Why it was not detected' in page
    assert 'CORRECTIVE / PREVENTIVE ACTION PLAN & RESPONSIBILITY' in page


def test_complaint_action_schema_and_closure_guard():
    sql = (ROOT / "supabase/migrations/20260812165500_qcms_detailed_complaint_analysis_v4107.sql").read_text()
    assert 'quality_complaint_actions' in sql
    assert 'occurrence_root_cause' in sql
    assert 'escape_root_cause' in sql
    assert 'systemic_root_cause' in sql
    assert 'qcms_guard_complaint_closure' in sql


def test_complaint_pdf_contains_detailed_analysis_and_responsibility():
    page = (ROOT / "app_pages/complaints.py").read_text()
    assert 'DETAILED COMPLAINT ANALYSIS RECORD' in page
    assert 'RESPONSIBILITY MATRIX' in page
    assert 'CORRECTIVE / PREVENTIVE ACTION PLAN' in page
    assert 'DEBIT NOTE / COMMERCIAL STATUS' in page


def test_login_css_targets_streamlit_container_directly():
    auth = (ROOT / "core/auth.py").read_text()
    assert 'div[data-testid="stMainBlockContainer"]' in auth
    assert '.qcms-login-brand-card' in auth
    assert '.qcms-login-form-title' in auth
    assert 'LOGIN TO QCMS' in auth
    assert 'app_footer(); st.stop()' not in (ROOT / 'streamlit_app.py').read_text()
