from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v41417_version_build_manifest_are_synchronized():
    version = tuple(int(part) for part in text("VERSION").strip().split("."))
    assert version >= (4, 14, 17)
    assert "41417-AUTO-MIGRATION-APPROVAL-ROUTES-MANIFEST-SYNC" in text("docs/RELEASE_4_14_17.md")
    manifest=json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert tuple(int(part) for part in manifest["version"].split(".")) >= (4, 14, 17)


def test_new_permission_tables_are_tenant_scoped_for_repository_writes():
    repo=text("core/repository.py")
    for table in ("department_module_defaults","user_section_permissions","qcms_module_approval_routes","supply_stage_responsibilities"):
        assert f'"{table}"' in repo


def test_configured_route_precedes_reports_to_and_self_approval_is_blocked():
    sql=text("supabase/migrations/20260828130000_qcms_auto_migration_approval_routes_v41417.sql")
    assert "qcms_purchase_order_approval_target" in sql
    assert "CONFIGURED_ROUTE" in sql
    assert "REPORTS_TO" in sql
    assert "PERMISSION_FALLBACK" in sql
    assert "Self-approval is not permitted" in sql
    assert "qcms_module_approval_routes" in sql
    assert "qcms_release_schema_version" in sql
    assert "revoke all on function public.qcms_cancel_purchase_order(uuid,text) from public, anon" in sql


def test_approval_route_admin_ui_and_po_notification_use_authoritative_target():
    users=text("app_pages/user_access.py")
    supply=text("app_pages/supply_chain.py")
    service=text("core/supply_chain_service.py")
    assert "MODULE APPROVAL ROUTES" in users
    assert "Save Approval Route" in users
    assert "qcms_module_approval_routes" in users
    assert "purchase_order_approval_target" in service
    assert "Required Approver" in supply
    assert "approval_target=service.purchase_order_approval_target" in supply


def test_automatic_remote_schema_guard_is_specific_and_non_destructive():
    guard=text("scripts/qcms_remote_schema_guard.py")
    assert "/database/query" in guard
    assert "/rest/v1/rpc/qcms_release_schema_version" in guard
    assert "QCMS_V41416_READY" in guard
    assert "QCMS_V41417_READY" in guard
    assert "20260828120000_qcms_permissions_po_approval_supply_notifications_v41416.sql" in guard
    assert "20260828130000_qcms_auto_migration_approval_routes_v41417.sql" in guard
    assert '"db", "query", "--linked", "--file"' in guard
    assert "db reset" not in guard
    assert "db push" not in guard


def test_release_docs_and_handover_are_current():
    for rel in ("docs/RELEASE_4_14_15.md","docs/RELEASE_4_14_16.md","docs/RELEASE_4_14_17.md","QCMS_NEW_CHAT_HANDOVER_v4.14.17.md"):
        assert (ROOT / rel).exists()
