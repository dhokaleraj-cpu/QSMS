"""R14: personal Microsoft 365 email, compact search bar, startup guard, memory fix."""
import json
from pathlib import Path
import pytest
from core import mail_service as ms

ROOT = Path(__file__).resolve().parents[1]
KEY = ms.new_credential_key()
CFG = ms.MailConfig("11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222", KEY)
EMP = [
    {"id": "e1", "first_name": "Asha", "last_name": "Patil", "email": "asha@fsi.in", "department": "Quality", "status": "ACTIVE"},
    {"id": "e2", "first_name": "Ravi", "email": "ravi@fsi.in", "department": "Quality", "status": "ACTIVE"},
    {"id": "e3", "first_name": "Old", "email": "old@fsi.in", "department": "Quality", "status": "INACTIVE"},
    {"id": "e4", "first_name": "Nomail", "department": "Stores", "status": "ACTIVE"},
    {"id": "e5", "first_name": "Sam", "email": "sam@fsi.in", "department": "Purchase", "status": "ACTIVE"},
]
GROUPS = [{"id": "g1", "group_name": "Plant Heads", "member_employee_ids": ["e5", "e3"], "extra_emails": ["md@fsi.in"], "status": "ACTIVE"}]


class Resp:
    def __init__(self, code, body): self.status_code = code; self._b = body
    def json(self): return self._b


def test_encryption_roundtrip_and_wrong_key():
    token = ms.encrypt_secret("refresh-123", KEY)
    assert "refresh-123" not in token and ms.decrypt_secret(token, KEY) == "refresh-123"
    with pytest.raises(ms.MailAuthError):
        ms.decrypt_secret(token, ms.new_credential_key())


def test_recipients_departments_groups_dedupe_and_warnings():
    rec, warn = ms.resolve_recipients(employees=EMP, groups=GROUPS, employee_ids=["e1", "e4"], departments=["quality"], group_ids=["g1"], extra_emails=["asha@fsi.in; x@y.com, bad"])
    emails = [r.email for r in rec]
    assert emails == ["asha@fsi.in", "ravi@fsi.in", "sam@fsi.in", "md@fsi.in", "x@y.com"]   # inactive e3 excluded, duplicate removed
    assert any("Nomail" in w for w in warn) and any("bad" in w for w in warn)


def test_build_messages_splits_large_bcc_and_limits():
    to = [ms.Recipient("a@x.com")]
    bcc = [ms.Recipient(f"u{i}@x.com") for i in range(1000)]
    msgs = ms.build_messages(subject="Hi", html_body=ms.body_html("Hello\n<script>"), to=to, bcc=bcc)
    assert len(msgs) == 3 and msgs[0]["saveToSentItems"] and not msgs[1]["saveToSentItems"]
    assert sum(len(m["message"]["bccRecipients"]) for m in msgs) == 1000
    assert all(len(m["message"]["toRecipients"]) + len(m["message"]["bccRecipients"]) <= ms.MAX_RECIPIENTS_PER_MESSAGE for m in msgs)
    assert "&lt;script&gt;" in msgs[0]["message"]["body"]["content"]
    with pytest.raises(ValueError):
        ms.build_messages(subject="Big", html_body="x", to=to, attachments=[("a.bin", b"0" * (4 * 1024 * 1024), "")])
    with pytest.raises(ValueError):
        ms.build_messages(subject="", html_body="x", to=to)


def test_device_login_flow_and_login_mailbox_check():
    calls = []
    def http(method, url, **kw):
        calls.append((method, url, kw))
        if url.endswith("/devicecode"):
            return Resp(200, {"device_code": "D", "user_code": "ABCD-EFGH", "verification_uri": "https://microsoft.com/devicelogin", "expires_in": 900, "interval": 5})
        if url.endswith("/token") and kw["data"].get("grant_type") == ms.DEVICE_GRANT:
            return Resp(400, {"error": "authorization_pending"}) if len(calls) < 3 else Resp(200, {"access_token": "AT", "refresh_token": "RT", "scope": ms.SCOPES})
        raise AssertionError(url)
    flow = ms.start_device_login(CFG, http=http)
    assert flow["user_code"] == "ABCD-EFGH" and "Mail.Send" in calls[0][2]["data"]["scope"]
    assert ms.poll_device_login(CFG, "D", http=http)["status"] == "pending"
    assert ms.poll_device_login(CFG, "D", http=http)["status"] == "ok"
    assert ms.assert_login_mailbox({"mail": "Rajesh@FSI.in"}, "rajesh@fsi.in") == "Rajesh@FSI.in"
    with pytest.raises(ms.MailSetupError):
        ms.assert_login_mailbox({"mail": "someone.else@fsi.in"}, "rajesh@fsi.in")


class Repo:
    def __init__(self): self.rows = []; self.n = 0
    def select(self, table, eq=None, **k): return [dict(r) for r in self.rows if all(r.get(a) == b for a, b in (eq or {}).items())]
    def insert(self, table, p): self.n += 1; r = {"id": f"r{self.n}", **p}; self.rows.append(r); return r
    def update(self, table, rid, p): r = next(x for x in self.rows if x["id"] == rid); r.update(p); return r
    def delete(self, table, rid): self.rows = [x for x in self.rows if x["id"] != rid]


def test_account_store_encrypts_rotates_and_sends():
    repo = Repo(); store = ms.MailAccountStore(repo, CFG, "user-1")
    store.save(mailbox="r@fsi.in", display_name="R", refresh_token="RT1", scope="")
    assert "RT1" not in json.dumps(repo.rows)
    sent = []
    def http(method, url, **kw):
        if url.endswith("/token"):
            assert kw["data"]["refresh_token"] == "RT1"
            return Resp(200, {"access_token": "AT2", "refresh_token": "RT2"})
        sent.append(kw["json"]); return Resp(202, {})
    token, _ = store.access_token(http=http)
    assert token == "AT2" and ms.decrypt_secret(repo.rows[0]["encrypted_refresh_token"], KEY) == "RT2"
    payloads = ms.build_messages(subject="S", html_body="B", to=[ms.Recipient("a@x.com")])
    assert ms.send_messages(token, payloads, http=http) == [] and sent[0]["message"]["subject"] == "S"
    def denied(method, url, **kw): return Resp(401, {"error": {"message": "expired"}})
    with pytest.raises(ms.MailAuthError):
        ms.send_messages("AT", payloads, http=denied)
    store.disconnect(); assert store.get() is None


def test_migration_is_owner_only_without_admin_policy():
    sql = (ROOT / "supabase/migrations/20261009100000_qcms_r14_personal_mail.sql").read_text()
    block = sql.split("create table if not exists public.qcms_mail_groups")[0]
    assert "force row level security" in block and block.count("user_id = auth.uid()") >= 4
    assert "ADMIN" not in block.split("-- Security model")[1].split("create table")[1]


def test_app_wiring_search_bar_and_startup_guard():
    app = (ROOT / "streamlit_app.py").read_text()
    for token in ('"email-send"', '"email-my-settings"', '(None, "Communication", "", "")', 'key="qcms_top_search"', "_qcms_auth_restore_attempts", "qcms_shell_global_search_form"):
        assert token in app
    repo_src = (ROOT / "core/repository.py").read_text()
    assert "stored = deepcopy(rows)" in repo_src and "len(cache) > 200" in repo_src
    assert "MICROSOFT 365 SIGN-IN FOR EMAIL" in (ROOT / "app_pages/system_settings.py").read_text()
