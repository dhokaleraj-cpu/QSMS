#!/usr/bin/env python3
"""QCMS R28 · apply pending database SQL to Supabase automatically (no SQL Editor copy/paste).

How it works
* The SQL files listed in supabase/auto_apply.json are applied in order to project
  xxrxopzxzyjnzumrwuwy through the Supabase Management API (HTTPS, via curl).
* A ledger table public.qcms_applied_sql remembers what was applied (file + SHA-256), so a file
  runs only once; every file is also written to be safe to re-run.
* Authentication: a Supabase *personal access token* (Dashboard → Account → Access Tokens).
  It is asked for ONCE and stored only in the macOS Keychain of this Mac
  (service "QCMS_SUPABASE_ACCESS_TOKEN"). It is never written to the project, Git or logs.
  Alternatively export QCMS_SUPABASE_ACCESS_TOKEN for one run.

Usage:  python3 scripts/apply_sql.py            (apply pending SQL)
        python3 scripts/apply_sql.py --status   (show ledger only)
        python3 scripts/apply_sql.py --forget-token
Exit code 0 = all applied (or nothing pending), 2 = token missing/declined, 1 = SQL failed.
"""
from __future__ import annotations

import getpass
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_REF = "xxrxopzxzyjnzumrwuwy"
API = "https://api.supabase.com/v1/projects/{ref}/database/query"
KEYCHAIN_SERVICE = "QCMS_SUPABASE_ACCESS_TOKEN"
MANIFEST = ROOT / "supabase" / "auto_apply.json"

LEDGER_SQL = """
create table if not exists public.qcms_applied_sql (
  file_name text primary key,
  sha256 text not null,
  applied_at timestamptz not null default now(),
  result jsonb
);
alter table public.qcms_applied_sql enable row level security;
revoke all on public.qcms_applied_sql from anon, authenticated;
select file_name, sha256, applied_at from public.qcms_applied_sql order by applied_at;
"""


class SqlError(RuntimeError):
    pass


def _account() -> str:
    return os.environ.get("USER") or getpass.getuser() or "qcms"


def keychain_get() -> str:
    if not shutil.which("security"):
        return ""
    try:
        out = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", _account(), "-w"],
                             capture_output=True, text=True, timeout=20)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def keychain_set(token: str) -> bool:
    if not shutil.which("security"):
        return False
    out = subprocess.run(["security", "add-generic-password", "-U", "-s", KEYCHAIN_SERVICE, "-a", _account(),
                          "-l", "QCMS Supabase access token", "-w", token], capture_output=True, text=True, timeout=20)
    return out.returncode == 0


def keychain_delete() -> None:
    if shutil.which("security"):
        subprocess.run(["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", _account()], capture_output=True, timeout=20)


def run_query(token: str, sql: str, ref: str = PROJECT_REF) -> list:
    """POST one SQL text (may hold many statements) and return the rows of the last statement."""
    if not shutil.which("curl"):
        raise SqlError("curl is not installed")
    with tempfile.TemporaryDirectory(prefix="qcms-sql-") as tmp:
        body = Path(tmp) / "body.json"; headers = Path(tmp) / "headers.txt"
        body.write_text(json.dumps({"query": sql}), encoding="utf-8")
        headers.write_text(f"Authorization: Bearer {token}\nContent-Type: application/json\nAccept: application/json\n", encoding="utf-8")
        os.chmod(body, 0o600); os.chmod(headers, 0o600)
        out = subprocess.run(["curl", "-sS", "-X", "POST", "-H", f"@{headers}", "--data-binary", f"@{body}",
                              "-w", "\n%{http_code}", "--max-time", "600", API.format(ref=ref)],
                             capture_output=True, text=True)
    if out.returncode != 0:
        raise SqlError(f"network error: {out.stderr.strip()[:400]}")
    text, _, code = out.stdout.rpartition("\n")
    try:
        data = json.loads(text) if text.strip() else []
    except ValueError:
        data = text
    if not code.startswith("2"):
        message = data.get("message") if isinstance(data, dict) else str(data)
        if code in {"401", "403"}:
            raise SqlError(f"HTTP {code}: the Supabase access token is not valid for project {ref} ({message})")
        raise SqlError(f"HTTP {code}: {message}")
    return data if isinstance(data, list) else []


def get_token(interactive: bool = True) -> str:
    token = os.environ.get("QCMS_SUPABASE_ACCESS_TOKEN", "").strip() or keychain_get()
    if token:
        return token
    if not interactive or not sys.stdin.isatty():
        return ""
    print("\nQCMS can apply the database update to Supabase for you (one-time setup).")
    print("1. Open https://supabase.com/dashboard/account/tokens  2. Generate new token (name: QCMS updater)")
    print("3. Paste it below (it is hidden and stored only in this Mac's Keychain). Press Enter to skip.")
    token = getpass.getpass("Supabase access token: ").strip()
    if not token:
        return ""
    try:
        run_query(token, "select 1 as ok")
    except SqlError as exc:
        print(f"Token check failed: {exc}")
        return ""
    print("Token stored in macOS Keychain." if keychain_set(token) else "Keychain not available - token used for this run only.")
    return token


def manifest() -> list[Path]:
    names = json.loads(MANIFEST.read_text(encoding="utf-8")).get("files", [])
    return [ROOT / name for name in names]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str]) -> int:
    if "--forget-token" in argv:
        keychain_delete(); print("Stored QCMS Supabase token removed from Keychain."); return 0
    token = get_token(interactive="--no-prompt" not in argv)
    if not token:
        print("DATABASE: skipped - no Supabase access token. Re-run later:  python3 scripts/apply_sql.py")
        return 2
    try:
        ledger = {r["file_name"]: r["sha256"] for r in run_query(token, LEDGER_SQL)}
    except SqlError as exc:
        print(f"DATABASE: could not reach Supabase - {exc}")
        return 1
    if "--status" in argv:
        for name, digest in ledger.items():
            print(f"applied  {name}  {digest[:12]}")
        return 0
    failed = 0
    for path in manifest():
        rel = str(path.relative_to(ROOT)); digest = sha(path)
        if ledger.get(rel) == digest:
            print(f"already applied  {rel}")
            continue
        print(f"applying  {rel} ...", flush=True)
        try:
            result = run_query(token, path.read_text(encoding="utf-8"))
            check = path.with_suffix(".check.sql")
            if check.exists():
                result = run_query(token, check.read_text(encoding="utf-8"))
            run_query(token, "insert into public.qcms_applied_sql (file_name, sha256, result) values ("
                      + _lit(rel) + ", " + _lit(digest) + ", " + _lit(json.dumps(result, default=str)) + "::jsonb) "
                      "on conflict (file_name) do update set sha256 = excluded.sha256, applied_at = now(), result = excluded.result")
            print(f"APPLIED   {rel}")
            for row in result[:50]:
                print("          " + ", ".join(f"{k}: {v}" for k, v in row.items()))
        except SqlError as exc:
            failed += 1
            print(f"FAILED    {rel}: {exc}")
    return 1 if failed else 0


def _lit(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
