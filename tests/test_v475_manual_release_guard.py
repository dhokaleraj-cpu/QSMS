from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260802123000_qsms_manual_decision_release_guard_v475.sql"


def test_manual_release_guard_uses_final_disposition_not_automatic_approval() -> None:
    sql = MIGRATION.read_text()
    assert "disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE')" in sql
    assert "approval_status = 'APPROVED'" not in sql
    assert "approval_status <> 'APPROVED'" in sql
    assert "manual acceptance, reserve or rejection reason is mandatory" in sql


def test_legacy_approved_part_error_removed_from_latest_guard() -> None:
    sql = MIGRATION.read_text()
    assert "RMTC release requires at least one approved part validation" not in sql
    assert "RMTC release requires at least one Accepted or Accepted Under Reserve Part Number" in sql


def test_manual_acceptance_decision_function_still_records_override_reason() -> None:
    migration = (
        ROOT
        / "supabase"
        / "migrations"
        / "20260802115000_qsms_authorized_manual_acceptance_v474.sql"
    ).read_text()
    assert "manual_override" in migration
    assert "Manual acceptance reason is mandatory" in migration
