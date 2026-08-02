from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_authorized_manual_acceptance_ui_requires_reason() -> None:
    pages = (ROOT / "app_pages" / "rmtc_pages.py").read_text()
    assert "Manual acceptance reason is mandatory" in pages
    assert "role=='ADMIN' and disposition=='ACCEPTED'" not in pages


def test_manual_acceptance_migration_allows_authorized_override() -> None:
    sql = (ROOT / "supabase" / "migrations" / "20260802115000_qsms_authorized_manual_acceptance_v474.sql").read_text()
    assert "manual_override" in sql
    assert "Manual acceptance reason is mandatory" in sql
    assert "v_override and v_role<>'ADMIN'" not in sql
    assert "disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE')" in sql
