from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_version_4107():
    assert (ROOT / "VERSION").read_text().strip() in {"4.10.7", "4.10.8", "4.10.9", "4.11.0", "4.11.1", "4.11.2", "4.11.3", "4.11.4", "4.11.5", "4.11.6"}


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
