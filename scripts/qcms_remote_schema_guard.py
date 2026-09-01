from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PROJECT_REF = "xxrxopzxzyjnzumrwuwy"
DEFAULT_SUPABASE_URL = "https://xxrxopzxzyjnzumrwuwy.supabase.co"
DEFAULT_PUBLISHABLE_KEY = "sb_publishable_o1EpvnCYWnfJaSWQH5vfFA_EWzN4QGh"
BASELINE_MIGRATION = ROOT / "supabase/migrations/20260828120000_qcms_permissions_po_approval_supply_notifications_v41416.sql"
PREVIOUS_MIGRATION = ROOT / "supabase/migrations/20260828130000_qcms_auto_migration_approval_routes_v41417.sql"
V41418_MIGRATIONS = (
    ROOT / "supabase/migrations/20260831161000_qcms_v41418_permissions_employee_access.sql",
    ROOT / "supabase/migrations/20260831161100_qcms_v41418_osp_same_heat_master_delete.sql",
    ROOT / "supabase/migrations/20260831161200_qcms_v41418_audit_metlab_rls_release.sql",
)

BASELINE_VERIFY_SQL = r"""
select case when
  to_regclass('public.department_module_defaults') is not null
  and to_regclass('public.user_section_permissions') is not null
  and to_regclass('public.qcms_module_approval_routes') is not null
  and to_regclass('public.supply_stage_responsibilities') is not null
  and exists(select 1 from information_schema.columns where table_schema='public' and table_name='supply_purchase_orders' and column_name='approval_status')
  and to_regprocedure('public.qcms_approve_purchase_order(uuid,text)') is not null
  and to_regprocedure('public.qcms_cancel_purchase_order(uuid,text)') is not null
then 'QCMS_V41416_READY' else 'QCMS_V41416_MISSING' end as qcms_release_state;
"""

PREVIOUS_VERIFY_SQL = r"""
select case when
  to_regprocedure('public.qcms_purchase_order_approval_target(uuid)') is not null
  and to_regclass('public.qcms_release_schema_state') is not null
  and exists(
    select 1 from pg_proc p join pg_namespace n on n.oid=p.pronamespace
    where n.nspname='public' and p.proname='qcms_approve_purchase_order'
      and position('qcms_purchase_order_approval_target' in pg_get_functiondef(p.oid))>0
      and position('Self-approval is not permitted' in pg_get_functiondef(p.oid))>0
  )
then 'QCMS_V41417_READY' else 'QCMS_V41417_MISSING' end as qcms_release_state;
"""

V41418_VERIFY_SQL = r"""
select case when
  to_regclass('public.role_module_defaults') is not null
  and to_regclass('public.qcms_user_activity_log') is not null
  and exists(select 1 from information_schema.columns where table_schema='public' and table_name='employees' and column_name='is_top_level_authority')
  and exists(select 1 from information_schema.columns where table_schema='public' and table_name='user_section_permissions' and column_name='can_create')
  and exists(select 1 from information_schema.columns where table_schema='public' and table_name='department_module_defaults' and column_name='can_archive')
  and to_regprocedure('public.qcms_effective_module_permission(text,text)') is not null
  and to_regprocedure('public.qcms_effective_section_permission(text,text,text)') is not null
  and to_regprocedure('public.qcms_log_user_activity(text,text,text,text,text,jsonb)') is not null
  and to_regprocedure('public.qcms_delete_osp_transaction(uuid)') is not null
  and to_regprocedure('public.qcms_delete_osp_receipt(uuid)') is not null
  and to_regprocedure('public.qcms_enforce_same_heat_code()') is not null
  and public.qsms_module_for_table('osp_receipts')='OSP_TRANSACTIONS'
  and public.qsms_module_for_table('supply_purchase_orders')='SUPPLY_CHAIN'
  and public.qsms_module_for_table('supply_purchase_order_items')='SUPPLY_CHAIN'
  and public.qsms_module_for_table('supply_purchase_order_sources')='SUPPLY_CHAIN'
  and public.qsms_module_for_table('supply_opening_stock')='SUPPLY_CHAIN'
then 'QCMS_V41418_READY' else 'QCMS_V41418_MISSING' end as qcms_release_state;
"""

V41419_MIGRATION = ROOT / "supabase/migrations/20260901170000_qcms_v41419_po_enable_delete_audit_confirmation_images.sql"
V41420_MIGRATION = ROOT / "supabase/migrations/20260901232000_qcms_v41420_rmtc_same_heat_osp_edit_delete.sql"
V41421_MIGRATION = ROOT / "supabase/migrations/20260902002000_qcms_v41421_deploy_resume_delete_routing.sql"
V41422_MIGRATION = ROOT / "supabase/migrations/20260902010000_qcms_v41422_public_verify_blank_master.sql"
# Backward-compatible direct REST path retained for older deployment-contract checks.
LEGACY_RELEASE_RPC_PATH = "/rest/v1/rpc/qcms_release_schema_version"
# Full v4.14.19 verification includes the supplier-confirmation daily schedule, not only the version marker.
V41419_REQUIRED_SCHEDULES = ("PO_CONFIRMATION_DAILY", "PO_PENDING_APPROVAL", "RM_PROCUREMENT_PENDING_DUE")
V41420_VERIFY_SQL = r"""
select case when
  exists(select 1 from public.qcms_release_schema_state where version='4.14.20')
  and to_regprocedure('public.qcms_update_osp_material_out(uuid,date,text,numeric,date,text)') is not null
  and to_regprocedure('public.qcms_clear_osp_sample(uuid)') is not null
  and to_regprocedure('public.qcms_update_osp_receipt(uuid,date,text,text,date,text,date,text,numeric,text)') is not null
then 'QCMS_V41420_READY' else 'QCMS_V41420_MISSING' end as qcms_release_state;
"""
V41419_VERIFY_SQL = r"""
select case when
  public.qcms_release_contract_v41419()='QCMS_V41419_FULL_READY'
  and public.qcms_release_schema_version()='4.14.19'
then 'QCMS_V41419_READY' else 'QCMS_V41419_MISSING' end as qcms_release_state;
"""
V41421_VERIFY_SQL = r"""
select case when
  public.qcms_release_schema_version()='4.14.21'
  and to_regprocedure('public.qcms_release_contract_v41421()') is not null
  and public.qcms_release_contract_v41421()='QCMS_V41421_FULL_READY'
then 'QCMS_V41421_READY' else 'QCMS_V41421_MISSING' end as qcms_release_state;
"""


def _project_ref_from_config() -> str:
    text = (ROOT / "supabase/config.toml").read_text(encoding="utf-8")
    match = re.search(r'^project_id\s*=\s*["\']([^"\']+)["\']', text, re.M)
    return match.group(1).strip() if match else ""


def _token_from_files() -> str:
    value = os.getenv("SUPABASE_ACCESS_TOKEN", "").strip()
    if value:
        return value
    token_path = Path.home() / ".supabase/access-token"
    if token_path.exists():
        try:
            return token_path.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    env_path = ROOT / ".env"
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("SUPABASE_ACCESS_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"\'')
        except OSError:
            pass
    return ""


def _runtime_supabase_value(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    env_path = ROOT / ".env"
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith(name + "="):
                    return stripped.split("=", 1)[1].strip().strip('"\'')
        except OSError:
            pass
    secrets_path = ROOT / ".streamlit/secrets.toml"
    if secrets_path.exists():
        try:
            import tomllib
            data = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
            if name in data and data[name] is not None:
                return str(data[name]).strip()
            for section in ("supabase", "app", "portal"):
                block = data.get(section) or {}
                if isinstance(block, dict) and name in block and block[name] is not None:
                    return str(block[name]).strip()
        except Exception:
            pass
    return ""


def _data_api_rpc_marker(function_name: str) -> str:
    url = (_runtime_supabase_value("SUPABASE_URL") or DEFAULT_SUPABASE_URL).rstrip("/")
    key = (
        _runtime_supabase_value("SUPABASE_PUBLISHABLE_KEY")
        or _runtime_supabase_value("SUPABASE_ANON_KEY")
        or _runtime_supabase_value("SUPABASE_KEY")
        or DEFAULT_PUBLISHABLE_KEY
    )
    if not url or not key:
        return ""
    request = urllib.request.Request(
        url + f"/rest/v1/rpc/{function_name}",
        data=b"{}", method="POST",
        headers={"apikey": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace").strip()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return ""
    try:
        return str(json.loads(body) or "").strip()
    except Exception:
        return body.strip('"')


def _data_api_release_marker() -> str:
    # LEGACY_RELEASE_RPC_PATH = /rest/v1/rpc/qcms_release_schema_version
    return _data_api_rpc_marker("qcms_release_schema_version")


def _data_api_full_contract_marker() -> str:
    return _data_api_rpc_marker("qcms_release_contract_v41419")


def _data_api_v41421_contract_marker() -> str:
    return _data_api_rpc_marker("qcms_release_contract_v41421")


def _data_api_v41422_contract_marker() -> str:
    return _data_api_rpc_marker("qcms_release_contract_v41422")


def _management_query(project_ref: str, sql: str) -> str | None:
    token = _token_from_files()
    if not token:
        return None
    url = f"https://api.supabase.com/v1/projects/{project_ref}/database/query"
    body = json.dumps({"query": sql, "read_only": False}).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code in {401, 403}:
            print(f"Management API token was not accepted (HTTP {exc.code}); trying authenticated Supabase CLI fallback...")
            return None
        raise RuntimeError(f"Supabase Management API query failed with HTTP {exc.code}: {detail[:500]}") from exc
    except urllib.error.URLError:
        return None


def _cli_prefix() -> list[str] | None:
    direct = shutil.which("supabase")
    if direct:
        return [direct]
    npx = shutil.which("npx")
    if npx:
        return [npx, "-y", "supabase@latest"]
    return None


def _run_cli(prefix: list[str], args: list[str], *, input_text: str | None = None, timeout: int = 240) -> subprocess.CompletedProcess[str]:
    return subprocess.run(prefix + args, input=input_text, text=True, capture_output=True, timeout=timeout, cwd=ROOT)


def _ensure_cli_link(prefix: list[str], project_ref: str) -> None:
    help_result = _run_cli(prefix, ["db", "query", "--help"], timeout=180)
    help_text = (help_result.stdout or "") + (help_result.stderr or "")
    if help_result.returncode != 0 or "--linked" not in help_text or "--file" not in help_text:
        raise RuntimeError("Installed Supabase CLI does not support 'db query --linked --file'. Upgrade to a current CLI release.")
    linked = _run_cli(prefix, ["link", "--project-ref", project_ref, "--yes"], input_text="\n", timeout=180)
    if linked.returncode != 0:
        message = ((linked.stdout or "") + "\n" + (linked.stderr or "")).strip()
        raise RuntimeError("Automatic Supabase authentication/linking failed. The updater did not run manual SQL. " + message[-900:])


def _cli_query(prefix: list[str], project_ref: str, sql: str) -> str:
    _ensure_cli_link(prefix, project_ref)
    with tempfile.NamedTemporaryFile("w", suffix=".sql", encoding="utf-8", delete=False) as handle:
        handle.write(sql)
        temp_path = Path(handle.name)
    try:
        result = _run_cli(prefix, ["db", "query", "--linked", "--file", str(temp_path)], timeout=300)
        output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        if result.returncode != 0:
            raise RuntimeError("Supabase CLI remote SQL execution failed: " + output[-1200:])
        return output
    finally:
        temp_path.unlink(missing_ok=True)


def remote_query(project_ref: str, sql: str) -> str:
    management = _management_query(project_ref, sql)
    if management is not None:
        return management
    prefix = _cli_prefix()
    if prefix is None:
        raise RuntimeError(
            "Automatic Supabase migration needs an authenticated Supabase Management API token or Supabase CLI. "
            "No manual SQL is requested; configure SUPABASE_ACCESS_TOKEN or log in to the Supabase CLI once, then rerun this same updater."
        )
    return _cli_query(prefix, project_ref, sql)


def verify(project_ref: str, sql: str, marker: str) -> bool:
    return marker in remote_query(project_ref, sql)


def apply_sql(project_ref: str, path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    remote_query(project_ref, path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="QCMS controlled remote Supabase schema verifier/migrator")
    parser.add_argument("--project-ref", default=_project_ref_from_config())
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--public-only", action="store_true", help="Verify the read-only Data API release contract only; never invoke CLI/Management API login")
    parser.add_argument("--source-only-nonblocking", action="store_true", help="For a source-only release with a preverified schema baseline, report online status but never fail deployment when the public Data API is unreachable")
    args = parser.parse_args()
    project_ref = str(args.project_ref or "").strip()
    if not project_ref:
        raise RuntimeError("Supabase project ref is missing from supabase/config.toml")

    print(f"Supabase project ref : {project_ref}")
    public_marker = _data_api_release_marker()
    full_contract = _data_api_full_contract_marker()
    v41421_contract = _data_api_v41421_contract_marker()
    v41422_contract = _data_api_v41422_contract_marker()
    if public_marker:
        print(f"Data API version marker : {public_marker}")
    if v41422_contract == "QCMS_V41422_FULL_READY" and public_marker == "4.14.22":
        print("v4.14.22 public Data API contract : READY")
        print("AUTOMATIC SUPABASE SCHEMA VERIFY/APPLY: SUCCESS (publishable-key public contract verified; no CLI login required)")
        return 0
    if v41421_contract == "QCMS_V41421_FULL_READY" and public_marker == "4.14.21":
        print("v4.14.21 public Data API contract : READY")
        print("AUTOMATIC SUPABASE SCHEMA VERIFY/APPLY: SUCCESS (public full release contract verified)")
        return 0
    if full_contract == "QCMS_V41419_FULL_READY" and public_marker == "4.14.19":
        print("v4.14.19 full Data API contract : READY")
        print("AUTOMATIC SUPABASE SCHEMA VERIFY/APPLY: SUCCESS (full release contract verified)")
        return 0
    if public_marker in {"4.14.19","4.14.20", "4.14.21", "4.14.22", "4.14.23"}:
        print("Public version marker exists but the full release contract is incomplete.")
    if args.source_only_nonblocking:
        print("SOURCE-ONLY RELEASE: online Supabase recheck unavailable/incomplete. Continuing because this release has no database migration and requires the preverified v4.14.22 baseline only.")
        return 0
    if args.public_only:
        print("PUBLIC-ONLY SUPABASE VERIFY FAILED: no Supabase CLI login or Management API authentication was attempted.")
        return 12

    baseline_ready = verify(project_ref, BASELINE_VERIFY_SQL, "QCMS_V41416_READY")
    print(f"v4.14.16 baseline    : {'READY' if baseline_ready else 'MISSING'}")
    if not baseline_ready:
        if args.verify_only:
            return 2
        print("Applying additive v4.14.16 baseline migration automatically...")
        apply_sql(project_ref, BASELINE_MIGRATION)
        if not verify(project_ref, BASELINE_VERIFY_SQL, "QCMS_V41416_READY"):
            raise RuntimeError("v4.14.16 baseline migration verification failed after automatic application")

    previous_ready = verify(project_ref, PREVIOUS_VERIFY_SQL, "QCMS_V41417_READY")
    print(f"v4.14.17 schema      : {'READY' if previous_ready else 'MISSING'}")
    if not previous_ready:
        if args.verify_only:
            return 3
        print("Applying additive v4.14.17 approval-route migration automatically...")
        apply_sql(project_ref, PREVIOUS_MIGRATION)
        if not verify(project_ref, PREVIOUS_VERIFY_SQL, "QCMS_V41417_READY"):
            raise RuntimeError("v4.14.17 migration verification failed after automatic application")

    v41418_ready = verify(project_ref, V41418_VERIFY_SQL, "QCMS_V41418_READY")
    print(f"v4.14.18 schema      : {'READY' if v41418_ready else 'MISSING'}")
    if not v41418_ready:
        if args.verify_only:
            return 4
        print("Applying additive v4.14.18 controlled migrations automatically...")
        for migration_path in V41418_MIGRATIONS:
            print(f"  Applying {migration_path.name} ...")
            apply_sql(project_ref, migration_path)
        if not verify(project_ref, V41418_VERIFY_SQL, "QCMS_V41418_READY"):
            raise RuntimeError("v4.14.18 migration verification failed after automatic application")

    v41419_ready = verify(project_ref, V41419_VERIFY_SQL, "QCMS_V41419_READY")
    print(f"v4.14.19 schema      : {'READY' if v41419_ready else 'MISSING'}")
    if not v41419_ready:
        if args.verify_only:
            return 5
        print("Applying additive v4.14.19 PO/confirmation/delete/image migration automatically...")
        apply_sql(project_ref, V41419_MIGRATION)
        if not verify(project_ref, V41419_VERIFY_SQL, "QCMS_V41419_READY"):
            raise RuntimeError("v4.14.19 migration verification failed after automatic application")

    v41420_ready = verify(project_ref, V41420_VERIFY_SQL, "QCMS_V41420_READY")
    print(f"v4.14.20 schema      : {'READY' if v41420_ready else 'MISSING'}")
    if not v41420_ready:
        if args.verify_only:
            return 6
        print("Applying additive v4.14.20 RMTC/OSP edit-delete migration automatically...")
        apply_sql(project_ref, V41420_MIGRATION)
        if not verify(project_ref, V41420_VERIFY_SQL, "QCMS_V41420_READY"):
            raise RuntimeError("v4.14.20 migration verification failed after automatic application")

    v41421_ready = verify(project_ref, V41421_VERIFY_SQL, "QCMS_V41421_READY")
    print(f"v4.14.21 schema      : {'READY' if v41421_ready else 'MISSING'}")
    if not v41421_ready:
        if args.verify_only:
            return 7
        print("Applying additive v4.14.21 deployment-resume migration automatically...")
        apply_sql(project_ref, V41421_MIGRATION)
        if not verify(project_ref, V41421_VERIFY_SQL, "QCMS_V41421_READY"):
            raise RuntimeError("v4.14.21 migration verification failed after automatic application")

    print("AUTOMATIC SUPABASE SCHEMA VERIFY/APPLY: SUCCESS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
