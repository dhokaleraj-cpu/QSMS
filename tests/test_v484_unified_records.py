from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_v484_version_and_migration():
    assert (ROOT/'VERSION').read_text().strip() in {'4.8.4','4.8.5','4.8.6','4.8.7','4.8.8','4.9.0','4.9.1','4.9.2','4.9.3','4.9.4','4.9.5','4.9.6','4.9.7','4.9.8', '4.9.9'}
    sql=(ROOT/'supabase/migrations/20260802193000_qsms_unified_records_v484.sql').read_text()
    for token in ['v_qsms_inward_register','supplier_name','part_number','dimensional_report_disposition','metlab_report_disposition']:
        assert token in sql

def test_unified_records_page_and_route():
    page=(ROOT/'app_pages/records_center.py').read_text()
    app=(ROOT/'streamlit_app.py').read_text()
    for token in ['Records Centre','Material Inward','Dimensional','MetLAB','Layouts','Masters']:
        assert token in page
    assert 'records-center' in app
    assert 'st.columns(11' in app

def test_dashboard_and_inward_share_register():
    dashboard=(ROOT/'app_pages/dashboard.py').read_text()
    service=(ROOT/'core/inward_service.py').read_text()
    inward=(ROOT/'app_pages/material_inward.py').read_text()
    assert 'v_qsms_inward_register' in dashboard
    assert 'v_qsms_inward_register' in service
    assert 'CURRENT MATERIAL INWARD STATUS' in inward
    assert 'supplier_name' in inward and 'part_number' in inward

def test_same_heat_new_rmtc_action():
    page=(ROOT/'app_pages/rmtc_pages.py').read_text()
    for token in ['Add New RMTC for This Heat Number','_start_new_rmtc_for_heat','rmtc_new_form_nonce']:
        assert token in page
