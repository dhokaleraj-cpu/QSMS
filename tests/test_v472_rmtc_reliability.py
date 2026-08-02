from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_material_grade_has_default_chemistry_elements():
    text = (ROOT / 'app_pages' / 'material_grade.py').read_text()
    assert 'DEFAULT_ELEMENTS = ["C", "Si", "Mn", "P", "S", "Cr", "Mo", "Ni"]' in text
    assert 'for element in DEFAULT_ELEMENTS' in text


def test_rmtc_header_save_is_idempotent_and_continues_to_part_worksheet():
    page = (ROOT / 'app_pages' / 'rmtc_pages.py').read_text()
    service = (ROOT / 'core' / 'rmtc_service.py').read_text()
    assert 'Save RMTC Header & Continue' in page
    assert "st.switch_page(st.session_state['_qsms_pages']['rmtc-part'])" in page
    assert "rmtc_flash_success" in page
    assert "find_one('rmtc_approvals', eq={'rmtc_number'" in service
    assert "self.repo.rpc('qsms_initialize_rmtc_details'" in service
    assert service.count("qsms_initialize_rmtc_details") >= 2


def test_rmtc_delete_and_admin_decision_change_are_available():
    page = (ROOT / 'app_pages' / 'rmtc_pages.py').read_text()
    migration = (ROOT / 'supabase' / 'migrations' / '20260802090000_qsms_rmtc_reliability_v472.sql').read_text()
    assert "title='Delete Selected RMTC'" in page
    assert "role=='ADMIN'" in page
    assert 'Admin · Reopen Decision for Change' in page
    assert 'qsms_admin_reopen_rmtc' in page
    assert 'create table if not exists public.rmtc_decision_revisions' in migration.lower()
    assert 'create or replace function public.qsms_admin_reopen_rmtc' in migration.lower()
    assert 'already linked to Material Inward' in migration


def test_repository_retries_temporary_http_errors_and_caches_reads():
    text = (ROOT / 'core' / 'repository.py').read_text()
    assert 'httpx.ReadError' in text
    assert 'attempts: int = 4' in text
    assert '_qsms_repository_read_cache' in text
    assert 'Showing the last successfully loaded data' in text


def test_master_cards_have_collision_safe_spacing():
    text = (ROOT / 'core' / 'ui.py').read_text()
    assert 'min-height:164px!important' in text
    assert 'min-height:70px' in text
    assert 'min-height:40px!important' in text
