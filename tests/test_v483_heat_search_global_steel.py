from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_v483_version_and_migration():
    assert (ROOT/'VERSION').read_text().strip() in {'4.8.3','4.8.4','4.8.5','4.8.6','4.8.7','4.8.8','4.9.0','4.9.1','4.9.2','4.9.3','4.9.4','4.9.5','4.9.6','4.9.7','4.9.8', '4.9.9','4.10.0','4.10.1','4.10.2','4.10.3','4.10.5','4.10.6','4.10.7','4.10.8','4.10.9','4.11.0','4.11.1','4.11.2','4.11.3','4.11.4','4.11.5','4.11.6','4.11.7','4.11.8','4.12.0','4.12.1','4.12.2','4.12.3','4.12.4','4.12.5','4.12.6','4.12.7','4.12.8','4.12.9','4.13.0'}
    sql=(ROOT/'supabase/migrations/20260802172000_qsms_heat_search_global_steel_v483.sql').read_text()
    for token in ['qsms_normalize_heat_number','v_qsms_heat_summary','v_qsms_heat_rmtc_usage','trg_global_heat_inward_limit','Global planned steel']:
        assert token in sql

def test_rmtc_heat_search_ui_and_ledger():
    page=(ROOT/'app_pages/rmtc_pages.py').read_text()
    for token in ['HEAT NUMBER SEARCH','Search / Enter Heat Number','Global Heat Steel','different Supplier RMTC Number','RMTC Number','Supplier','Part Number']:
        assert token in page

def test_rmtc_service_heat_methods():
    service=(ROOT/'core/rmtc_service.py').read_text()
    for token in ['normalize_heat_number','heat_summary','heat_usage','v_qsms_heat_summary','v_qsms_heat_steel_ledger']:
        assert token in service
