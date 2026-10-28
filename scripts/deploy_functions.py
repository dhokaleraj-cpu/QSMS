#!/usr/bin/env python3
"""QCMS R38 · deploy changed Supabase Edge Functions from this Mac (no Supabase CLI needed).

* Functions listed in supabase/auto_deploy_functions.json are uploaded through the Supabase Management API
  (POST /v1/projects/<ref>/functions/deploy?slug=<name>, multipart: metadata + every file of the function folder).
* The same access token as scripts/apply_sql.py is used (macOS Keychain "QCMS_SUPABASE_ACCESS_TOKEN").
* The ledger public.qcms_applied_sql remembers "edge-function:<slug>" + SHA-256 of the files, so an unchanged
  function is never re-deployed.
Exit code 0 = deployed / nothing pending, 2 = no token, 1 = a deploy failed (the website still works; only the
scheduled e-mail wording / new reminder branch waits for the next successful run).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_sql import LEDGER_SQL, PROJECT_REF, SqlError, _lit, get_token, run_query  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "supabase" / "auto_deploy_functions.json"
DEPLOY_API = "https://api.supabase.com/v1/projects/{ref}/functions/deploy?slug={slug}"


def function_files(slug: str) -> list[Path]:
    folder = ROOT / "supabase" / "functions" / slug
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix in {".ts", ".json", ".jsonc"})


def digest(files: list[Path]) -> str:
    h = hashlib.sha256()
    for path in files:
        h.update(path.name.encode()); h.update(b"\0"); h.update(path.read_bytes()); h.update(b"\0")
    return h.hexdigest()


def deploy(token: str, slug: str, verify_jwt: bool, files: list[Path]) -> None:
    if not shutil.which("curl"):
        raise SqlError("curl is not installed")
    names = {p.name for p in files}
    meta = {"name": slug, "entrypoint_path": "index.ts", "verify_jwt": bool(verify_jwt)}
    if "deno.json" in names:
        meta["import_map_path"] = "deno.json"
    with tempfile.TemporaryDirectory(prefix="qcms-fn-") as tmp:
        headers = Path(tmp) / "headers.txt"
        headers.write_text(f"Authorization: Bearer {token}\nAccept: application/json\n", encoding="utf-8")
        os.chmod(headers, 0o600)
        cmd = ["curl", "-sS", "-X", "POST", "-H", f"@{headers}", "-F", f"metadata={json.dumps(meta)};type=application/json"]
        for path in files:
            mime = "application/typescript" if path.suffix == ".ts" else "application/json"
            cmd += ["-F", f"file=@{path};filename={path.name};type={mime}"]
        cmd += ["-w", "\n%{http_code}", "--max-time", "300", DEPLOY_API.format(ref=PROJECT_REF, slug=slug)]
        out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise SqlError(f"network error: {out.stderr.strip()[:400]}")
    text, _, code = out.stdout.rpartition("\n")
    if not code.startswith("2"):
        raise SqlError(f"HTTP {code}: {text.strip()[:400]}")


def main(argv: list[str]) -> int:
    if not MANIFEST.exists():
        return 0
    token = get_token(interactive="--no-prompt" not in argv)
    if not token:
        print("EDGE FUNCTIONS: skipped - no Supabase access token. Re-run later:  python3 scripts/deploy_functions.py")
        return 2
    try:
        ledger = {r["file_name"]: r["sha256"] for r in run_query(token, LEDGER_SQL)}
    except SqlError as exc:
        print(f"EDGE FUNCTIONS: could not reach Supabase - {exc}")
        return 1
    failed = 0
    for entry in json.loads(MANIFEST.read_text(encoding="utf-8")).get("functions", []):
        slug = str(entry["slug"]); key = f"edge-function:{slug}"
        files = function_files(slug); sha = digest(files)
        if ledger.get(key) == sha:
            print(f"already deployed  {slug}")
            continue
        print(f"deploying  {slug} ...", flush=True)
        try:
            deploy(token, slug, bool(entry.get("verify_jwt", False)), files)
            run_query(token, "insert into public.qcms_applied_sql (file_name, sha256, result) values (" + _lit(key) + ", " + _lit(sha)
                      + ", '{\"deployed\": true}'::jsonb) on conflict (file_name) do update set sha256 = excluded.sha256, applied_at = now(), result = excluded.result")
            print(f"DEPLOYED   {slug}")
        except SqlError as exc:
            failed += 1
            print(f"FAILED     {slug}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
