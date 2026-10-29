"""R39 (agent P): PPAP assignment e-mail with part details + current drawings / specifications (server RPC, website,
daily reminder edge function) - migration 20261029100000_qcms_r39_ppap_mail.sql, core/ppap_service.py, app_pages/ppap.py,
app_pages/npd_apqp.py, supabase/functions/qcms-ppap-due-notifier, mobile/PPAP_MAIL_CONTRACT.md."""
from __future__ import annotations

import json
import re
from pathlib import Path

from core import ppap_service
from core.ppap_service import PpapService, assignment_mail_message, needs_assignment_mail

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261029100000_qcms_r39_ppap_mail.sql"
FUNCTION = ROOT / "supabase/functions/qcms-ppap-due-notifier"


def sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_defines_rpcs_with_safe_grants():
    text = sql()
    low = text.lower()
    for fn in ("qcms_ppap_department_label(p_value text)", "qcms_ppap_html(p_value text)", "qcms_ppap_part_context(p_package_id uuid)",
               "qcms_ppap_assignment_mail(p_package_id uuid"):
        assert f"create or replace function public.{fn}" in text, fn
    assert "returns uuid[]" in text
    # invoker functions: tenant RLS applies; write right checked; anon never
    body = text.split("create or replace function public.qcms_ppap_assignment_mail", 1)[1]
    assert "security invoker" in body.split("as $$", 1)[0]
    assert "public.qcms_ppap_can_write()" in body and "auth.uid() is null" in body
    assert "revoke all on function public.qcms_ppap_assignment_mail(uuid, uuid[], boolean, text) from public, anon;" in text
    assert "grant execute on function public.qcms_ppap_assignment_mail(uuid, uuid[], boolean, text) to authenticated;" in text
    assert "revoke all on function public.qcms_ppap_part_context(uuid) from public, anon;" in text
    assert "service_role" not in body.split("revoke all", 1)[0]
    # MCP live apply: no destructive keywords anywhere in the SQL text
    assert not re.search(r"\b(delete|update|drop|truncate)\b", low)


def test_part_context_collects_drawings_and_specifications():
    text = sql()
    for needle in ("'FINISH_DRAWING', 'FORGING_DRAWING', 'HEAT_TREATMENT_DRAWING'", "d.entity_type = 'PART_MASTER'",
                   "d.entity_type = 'PART_PROCESS'", "'PROCESS_DRAWING', 'PROCESS_SPEC'", "d.entity_type = 'PART_PROCESS_SPEC'",
                   "d.entity_type = 'CUSTOMER_STANDARD'", "public.part_standard_links", "d.status = 'ACTIVE'",
                   "'material_grade', v_grade", "'drawing_revision'", "storage.objects", "'in_storage'"):
        assert needle in text, needle


def test_assignment_mail_content_subject_and_limits():
    text = sql()
    assert "c_max_bytes constant bigint := 10 * 1024 * 1024" in text and "c_max_files constant integer := 18" in text
    # department-first subject with the earliest due date
    assert "format('%s · PPAP %s · %s · your %s element(s) %s', v_dept" in text and "'due from ' || to_char(v_min_due, 'DD-MM-YYYY')" in text
    for label in ("PPAP Package No.", "Customer PPAP No.", "Submission Level", "Customer Due Date", "PART DETAILS", "YOUR PPAP ELEMENTS",
                  "CURRENT DRAWINGS &amp; SPECIFICATIONS", "Drawing No. / Rev.", "Material Grade", "Open the PPAP package in QCMS"):
        assert label in text, label
    # internal recipients only (tenant employees), owner in CC, dedupe per day, resend bypass
    assert "from public.employees e" in text and "where e.tenant_id = v_tid" in text
    assert "v_cc := array[btrim(v_owner ->> 'email')]" in text
    assert "on conflict (tenant_id, dedupe_key) where dedupe_key is not null do nothing" in text
    assert "case when p_resend then" in text and "'PPAP_ASSIGNMENT'" in text
    assert "'/ppap-package?ppap='" in text
    assert "parties" not in text.split("-- one e-mail per responsible employee", 1)[1].split("v_html :=", 1)[0]


def test_outbox_trigger_routes_ppap_and_skips_duplicate_bell():
    text = sql()
    assert "when k like 'PPAP%' then 'ppap-package'" in text and "when v_route like 'ppap-%' then 'PPAP'" in text
    assert "if k in ('USER_EMAIL', 'EMAIL_SERVER_TEST', 'PPAP_ASSIGNMENT')" in text


def test_auto_apply_and_deploy_lists():
    files = json.loads((ROOT / "supabase/auto_apply.json").read_text())["files"]
    assert "supabase/migrations/20261029100000_qcms_r39_ppap_mail.sql" in files
    funcs = json.loads((ROOT / "supabase/auto_deploy_functions.json").read_text())["functions"]
    assert {"slug": "qcms-ppap-due-notifier", "verify_jwt": False} in funcs


# ----------------------------------------------------------------------------- website
class Repo:
    tenant_id = "t1"

    def __init__(self, result=None, error=None):
        self.calls: list[tuple[str, dict]] = []
        self.result, self.error = result, error

    def rpc(self, name, params=None):
        self.calls.append((name, dict(params or {})))
        if self.error:
            raise RuntimeError(self.error)
        return self.result


def test_send_assignment_mail_calls_rpc_then_dispatcher():
    repo = Repo(result=["o1", "o2"])
    sent: list[list[str]] = []
    result = PpapService(repo).send_assignment_mail("p1", None, app_url="https://qcms.example", dispatcher=lambda ids: sent.append(ids) or {"sent": 2})
    assert repo.calls == [("qcms_ppap_assignment_mail", {"p_package_id": "p1", "p_element_ids": None, "p_resend": False, "p_app_url": "https://qcms.example"})]
    assert sent == [["o1", "o2"]] and result["queued"] == 2 and result["sent"] == 2
    assert assignment_mail_message(result)[0] == "success"


def test_send_assignment_mail_never_raises_and_skips_empty():
    repo = Repo(error="PPAP create / edit permission is required")
    result = PpapService(repo).send_assignment_mail("p1", ["e1"], resend=True, app_url="", dispatcher=lambda ids: {"sent": 1})
    assert result["queued"] == 0 and "permission" in result["error"]
    assert repo.calls[0][1]["p_element_ids"] == ["e1"] and repo.calls[0][1]["p_resend"] is True
    assert assignment_mail_message(result)[0] == "warning"
    empty = Repo(result=[])
    called = []
    assert PpapService(empty).send_assignment_mail("p1", app_url="", dispatcher=lambda ids: called.append(ids))["queued"] == 0 and not called
    assert PpapService(Repo(result=["x"])).send_assignment_mail("p1", [], app_url="")["queued"] == 0   # explicit empty selection: nothing
    # Postgres array text form
    assert PpapService(Repo(result="{a,b}")).send_assignment_mail("p1", app_url="", dispatcher=lambda ids: {"sent": len(ids)})["sent"] == 2


def test_needs_assignment_mail_rule():
    assert needs_assignment_mail(None, {"responsible_employee_id": "e1", "status": "NOT_STARTED"})
    assert needs_assignment_mail({"responsible_employee_id": "e1", "due_date": "2026-11-01"}, {"responsible_employee_id": "e2", "status": "IN_PROGRESS", "due_date": "2026-11-01"})
    assert needs_assignment_mail({"responsible_employee_id": "e1", "due_date": "2026-11-01"}, {"responsible_employee_id": "e1", "status": "NOT_STARTED", "due_date": "2026-11-05"})
    assert not needs_assignment_mail({"responsible_employee_id": "e1", "due_date": "2026-11-01"}, {"responsible_employee_id": "e1", "status": "NOT_STARTED", "due_date": "2026-11-01"})
    assert not needs_assignment_mail(None, {"responsible_employee_id": "e1", "status": "COMPLETED"})
    assert not needs_assignment_mail(None, {"responsible_employee_id": "", "status": "NOT_STARTED"})
    assert ppap_service.ASSIGNMENT_RPC == "qcms_ppap_assignment_mail" and ppap_service.SEND_EMAIL_FUNCTION == "qcms-send-email"


def test_pages_send_on_create_reassign_and_resend():
    page = (ROOT / "app_pages/ppap.py").read_text(encoding="utf-8")
    assert "send_assignment_mail(service, saved[\"id\"])" in page                       # package created
    assert page.count("send_assignment_mail(service, package_id, list(service.last_mail_element_ids))") == 2   # editor + bulk
    assert "Send assignment e-mail again" in page and "send_assignment_mail(service, package_id, None, resend=True)" in page
    apqp = (ROOT / "app_pages/npd_apqp.py").read_text(encoding="utf-8")
    assert "from app_pages.ppap import send_assignment_mail" in apqp and "send_assignment_mail(service, created[\"id\"])" in apqp


# ----------------------------------------------------------------------------- reminders
def test_reminder_function_part_details_and_weekly_attachments():
    ts = (FUNCTION / "index.ts").read_text(encoding="utf-8")
    assert 'admin.rpc("qcms_ppap_part_context", { p_package_id: packageId })' in ts
    assert "export const ATTACH_REPEAT_DAYS = 7;" in ts
    assert 'const PPAP_MAIL_EVENTS = ["PPAP_ASSIGNMENT", "PPAP_DOCUMENT_DUE_DIGEST"];' in ts
    assert "recentAttachmentPaths(admin, tenantId, digest.email, addDays(today, -(ATTACH_REPEAT_DAYS - 1)))" in ts
    assert "planAttachments(allDocs, MAX_MAIL_FILES, MAX_MAIL_BYTES, recent)" in ts
    assert 'eq("status", "SENT")' in ts and "Attached on ${dmy(" in ts
    assert "partDetailsHtml(packageNo, ctx)" in ts and '["Material Grade", grade]' in ts and '"Drawing No. / Rev."' in ts
    # department-first subject kept
    assert "subject: `${label} · PPAP elements due · ${rows.length} item(s) · ${dmy(today)}`" in ts
    assert "SUPABASE_SERVICE_ROLE_KEY" in ts and "X-QCMS-Scheduler" in ts   # server-side only, scheduler token auth
    assert json.loads((FUNCTION / "deno.json").read_text()) == {"imports": {}}


def test_contract_document():
    doc = (ROOT / "mobile/PPAP_MAIL_CONTRACT.md").read_text(encoding="utf-8")
    for needle in ("qcms_ppap_assignment_mail", "qcms-send-email", "p_resend", "within the last 7 days", "18 files / 10 MB",
                   "PPAP_PACKAGE_SUBMISSION", "never service_role"):
        assert needle in doc, needle
