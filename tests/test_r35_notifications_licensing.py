"""R35: in-app notifications, WhatsApp, STAWN licence + company setup + developer console, STAWN branding."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261021120000_qcms_r35_notifications_licensing.sql"

NOTE = {"id": "11111111-1111-1111-1111-111111111111", "title": "PO PD9131000096 waiting for your approval", "body": "Kessler · 2 lines",
        "category": "APPROVAL", "module_key": "SUPPLY_CHAIN", "web_route": "supply-po-approval", "is_read": False,
        "created_at": "2026-10-22T05:00:00+00:00"}
STATUS = {"valid": True, "status": "ACTIVE", "plan": "ENTERPRISE", "max_users": 50, "used_users": 18, "company_name": "Four Star Industries Pvt. Ltd.",
          "licence_key_masked": "STAWN-QCMS-•••••-•••••-•••••-AB12C", "is_stawn_developer": True, "is_company_admin": True,
          "setup_complete": False, "reason": "Licence valid"}


def _fake_rpc(self, name, params=None):
    if name == "qcms_my_notifications":
        return [NOTE]
    if name == "qcms_unread_notification_count":
        return 1
    if name == "qcms_licence_status":
        return dict(STATUS)
    if name == "qcms_dev_licence_overview":
        return [{"tenant_id": "00000000-0000-0000-0000-000000000001", "tenant_code": "FSI", "company_name": "Four Star Industries Pvt. Ltd.",
                 "licence_id": "22222222-2222-2222-2222-222222222222", "licence_key": "STAWN-QCMS-AAAAA-BBBBB-CCCCC-DDDDD",
                 "plan": "ENTERPRISE", "status": "ACTIVE", "evaluated_status": "ACTIVE", "valid_to": None, "max_users": 50,
                 "used_users": 18, "last_validated_at": None, "setup_complete": False}]
    raise RuntimeError("RPC functions are unavailable in controlled preview mode.")


def test_migration_contracts_and_safety():
    sql = MIGRATION.read_text()
    for token in ("create table if not exists public.qcms_user_notifications", "qcms_my_notifications", "qcms_unread_notification_count",
                  "qcms_mark_notifications_read", "qcms_register_push_device", "public.qcms_notify(", "qcms_whatsapp_settings",
                  "qcms_licence_status", "qcms_validate_licence", "qcms_activate_licence", "qcms_dev_issue_licence",
                  "qcms_dev_licence_overview", "qcms_dev_create_company", "qcms_dev_assign_profile", "qcms_company_profiles",
                  "qcms_stawn_developers", "qcms_r35_licence_seat_limit", "R35 seed: Four Star Industries"):
        assert token in sql, token
    low = sql.lower()
    assert "drop table" not in low and "truncate" not in low and "drop column" not in low
    # licence signing secret never readable through the API
    assert "revoke all on public.qcms_licence_secret from public, anon, authenticated" in sql
    # WhatsApp access token is an Edge Function secret, never a column
    assert "access_token" not in low.split("create table if not exists public.qcms_whatsapp_settings")[1].split(");")[0]


def test_edge_functions_have_no_secrets():
    for fn in ("qcms-push-dispatch", "qcms-whatsapp-dispatch"):
        src = (ROOT / "supabase/functions" / fn / "index.ts").read_text()
        assert "Deno.env.get" in src and "X-QCMS-Scheduler" in src
        assert "EAA" not in src and "BEGIN PRIVATE KEY-----M" not in src


def test_routes_registered_and_gate_is_safe():
    app = (ROOT / "streamlit_app.py").read_text()
    for route in ("notifications", "licence-company", "stawn-developer"):
        assert f'url_path="{route}"' in app
    assert "licence_blocks_use(_licence)" in app and "_LICENCE_FREE_ROUTES" in app and "qcms_notification_bell" in app
    from core import licence_service as lic
    assert lic.licence_blocks_use({"valid": False, "status": "EXPIRED"}) is True
    assert lic.licence_blocks_use({"valid": False, "status": "EXPIRED", "is_stawn_developer": True}) is False
    assert lic.licence_blocks_use({"valid": True, "status": "UNCHECKED", "unchecked": True}) is False
    assert lic.licence_blocks_use({"valid": True, "status": "GRACE"}) is False
    assert lic.missing_company_fields({"legal_name": "X"})  # required fields enforced
    ui = (ROOT / "core/ui.py").read_text()
    assert "STAWN QCMS</div>" in ui and "stawn_logo_data_uri" in ui


def test_notifications_page_renders(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from core.repository import Repository
    monkeypatch.setattr(Repository, "rpc", _fake_rpc)
    app = AppTest.from_string('''
import streamlit as st
from core.auth import PREVIEW_PROFILE
st.session_state["_qsms_preview"] = True
st.session_state["profile"] = PREVIEW_PROFILE.copy()
from app_pages import notifications
notifications.render()
''').run(timeout=60)
    assert not app.exception
    text = " ".join(str(m.value) for m in app.markdown)
    assert "waiting for your approval" in text


def test_licence_and_developer_pages_render(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from core.repository import Repository
    monkeypatch.setattr(Repository, "rpc", _fake_rpc)
    for fn in ("render", "render_developer"):
        app = AppTest.from_string(f'''
import streamlit as st
from core.auth import PREVIEW_PROFILE
st.session_state["_qsms_preview"] = True
st.session_state["profile"] = PREVIEW_PROFILE.copy()
from app_pages import licence_company
licence_company.{fn}()
''').run(timeout=60)
        assert not app.exception, fn
        text = " ".join(str(m.value) for m in app.markdown)
        assert ("ENTERPRISE" in text) if fn == "render" else ("STAWN DEVELOPER RIGHTS" in text or "LICENSED COMPANIES" in text), fn
