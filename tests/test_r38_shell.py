"""R38 (agent C, shell & admin) · header branding, version only in the user details popover, employee photo in the header
avatar, PO approval auto-download (supplier-safe, <PO no>[_Amd n].pdf), department e-mail subjects, login cover."""
from __future__ import annotations

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------------ 1 header logos
def test_company_initials_ignore_legal_suffixes():
    from core.ui import company_initials

    assert company_initials("Four Star Industries Private Limited") == "FSI"
    assert company_initials("STAWN Precision Pvt. Ltd.") == "SP"
    assert company_initials("") == ""


def test_company_logo_falls_back_to_initials_badge(monkeypatch):
    import streamlit as st
    from core import licence_service, ui

    st.session_state.pop(ui.HEADER_COMPANY_LOGO_KEY, None)
    monkeypatch.setattr(licence_service, "company_profile", lambda tid=None: {"display_name": "Four Star Industries", "logo_path": None})
    monkeypatch.setattr(licence_service, "company_logo_bytes", lambda path: None)
    html = ui.header_company_logo_html("Four Star Industries Private Limited")
    assert html == '<span class="qcms-hdr-company-initials" title="Four Star Industries">FSI</span>'
    st.session_state.pop(ui.HEADER_COMPANY_LOGO_KEY, None)


def test_header_avatar_uses_employee_photo_else_initials():
    from core.ui import header_avatar_html

    assert header_avatar_html("RD") == '<div class="fsi-user-avatar">RD</div>'
    photo = header_avatar_html("RD", "data:image/png;base64,AAAA")
    assert 'fsi-user-avatar-photo' in photo and '<img src="data:image/png;base64,AAAA"' in photo


def test_header_user_details_without_employee_never_queries():
    import streamlit as st
    from core import ui

    st.session_state.pop(ui.HEADER_USER_KEY, None)
    info = ui.header_user_details({"full_name": "X"})
    assert info["employee_id"] == "" and info["photo_uri"] == ""
    st.session_state.pop(ui.HEADER_USER_KEY, None)


def test_header_css_icon_and_badges():
    ui = read("core/ui.py")
    assert "html body .qcms-hdr-company-initials{" in ui and "html body .fsi-user-avatar-photo img{width:100%%;" in ui
    assert 'st-key-qcms_header_user_details' in ui


# ------------------------------------------------------------------------------------------------ 2 version only in user details
def test_ribbon_has_no_version_but_user_details_popover_has_it():
    from streamlit.testing.v1 import AppTest

    script = '''
import streamlit as st
from core import ui
st.session_state[ui.HEADER_COMPANY_LOGO_KEY] = {"_at": 9e12, "html": '<span class="qcms-hdr-company-initials">FSI</span>'}
st.session_state[ui.HEADER_USER_KEY] = {"employee_id": "e1", "_at": 9e12, "employee_code": "FSI-007", "department": "Purchase", "photo_uri": ""}
st.session_state["_qcms_r35_licence_status"] = {"_at": 9e12, "data": {"company_name": "Four Star Industries Private Limited"}}
ui.render_shell_header({"full_name": "Rajesh Dhokale", "role": "ADMIN", "employee_id": "e1"}, "Dashboard")
'''
    app = AppTest.from_string(script).run(timeout=30)
    assert not app.exception, app.exception
    from core.config import get_settings

    version = get_settings().version
    texts = [m.value for m in app.markdown]
    ribbon = next(t for t in texts if 'class="fsi-user"' in t)
    assert "qcms-hdr-company-initials" in ribbon and f"v{version}" not in ribbon
    assert not any(f"v{version}" in t for t in texts if "fsi-company-block" in t)
    details = " ".join(texts)
    assert "About this app" in details and f"website v{version}" in details and "FSI-007" in details


def test_no_version_on_search_caption_footer_or_page_header():
    app = read("streamlit_app.py")
    caption = next(line for line in app.splitlines() if "gs3.caption(" in line)
    assert "version" not in caption and "LIVE BUILD" not in caption
    assert "LIVE BUILD · QCMS" in app  # historical source marker only (comment)
    ui = read("core/ui.py")
    footer = ui.split("def app_footer", 1)[1]
    assert "version" not in footer
    header = ui.split("def page_header", 1)[1].split("\ndef ", 1)[0]
    assert "version" not in header
    shell = ui.split("def render_shell_header", 1)[1].split("def render_left_navigation", 1)[0]
    assert "s.version" not in shell and "render_user_details(" in shell


# ------------------------------------------------------------------------------------------------ 3 login cover
def test_developer_console_has_login_cover_upload_preview_reset():
    lic = read("app_pages/licence_company.py")
    for text in ("LOGIN PAGE COVER PHOTO (STAWN ONLY)", "def upload_login_cover", "def reset_login_cover", "Preview of the new cover"):
        assert text in lic
    auth = read("core/auth.py")
    login = auth.split("def render_login", 1)[1].split("def render_first_admin_claim", 1)[0]
    assert "login_cover_bytes()" in login and "login_factory.jpeg" in login


# ------------------------------------------------------------------------------------------------ 4 department subjects
def test_department_subject_replaces_qcms():
    from core.notification_service import department_subject

    assert department_subject("QCMS · PO PD9131000096 approval overdue", "Supply Chain") == "Supply Chain · PO PD9131000096 approval overdue"
    assert department_subject("QCMS - RMTC approval pending", "quality").startswith("Quality · ")
    for name in ("qcms-po-approval-overdue", "qcms-po-confirmation-reminder"):
        src = read(f"supabase/functions/{name}/index.ts")
        assert "subject=`QCMS" not in src.replace(" ", "")


# ------------------------------------------------------------------------------------------------ 5 PO auto-download
def test_po_download_file_name():
    from app_pages.supply_chain import po_download_file_name

    assert po_download_file_name({"po_number": "PD9131000096"}) == "PD9131000096.pdf"
    assert po_download_file_name({"po_number": "PD9131000096", "amendment_no": 2}) == "PD9131000096_Amd2.pdf"
    assert po_download_file_name({"po_number": "PD/91"}) == "PD-91.pdf"
    assert po_download_file_name({}) == "Purchase_Order.pdf"


def test_po_auto_download_is_supplier_safe_and_once(monkeypatch):
    import streamlit as st
    from app_pages import supply_chain as page

    seen = {}

    def fake_pdf(header, items):
        seen["header"], seen["items"] = header, items
        return b"%PDF-1.4 approved"

    monkeypatch.setattr(page, "purchase_order_pdf_bytes", fake_pdf)
    html_calls = []
    import streamlit.components.v1 as components

    monkeypatch.setattr(components, "html", lambda body, height=0: html_calls.append(body))
    monkeypatch.setattr(st, "success", lambda *a, **k: None)
    monkeypatch.setattr(st, "download_button", lambda *a, **k: None)

    class Svc:
        def purchase_order(self, i):
            return {"id": i, "po_number": "PD9131000096", "amendment_no": 1, "approval_status": "APPROVED"}

        def purchase_order_items_for_print(self, i):
            return [{"part_number": "P1", "customer_name": "SECRET CUSTOMER", "customer_po_number": "CPO-1"}]

    page.queue_po_approved_download("po1")
    page._po_approved_auto_download(Svc())
    assert seen["header"]["print_options"]["show_source_reference"] is False
    assert "SECRET CUSTOMER" not in str(seen["items"]) and "CPO-1" not in str(seen["items"])
    assert len(html_calls) == 1 and '"PD9131000096_Amd1.pdf"' in html_calls[0]
    assert base64.b64encode(b"%PDF-1.4 approved").decode() in html_calls[0]
    page._po_approved_auto_download(Svc())  # queue consumed -> no second download
    assert len(html_calls) == 1


# ------------------------------------------------------------------------------------------------ 6 employee photo / escalation
def test_employee_details_reporting_and_escalation():
    from core.employee_service import employee_details

    rows = [{"id": "a", "first_name": "Top", "reports_to_employee_id": None},
            {"id": "b", "first_name": "Mid", "reports_to_employee_id": "a"},
            {"id": "c", "first_name": "Low", "reports_to_employee_id": "b"}]
    routes = [{"employee_id": "b", "module_key": "SUPPLY_CHAIN", "level_no": 1, "status": "ACTIVE"}]
    info = employee_details(rows, routes, "c")
    assert info["reporting_to"]["id"] == "b" and [r["id"] for r in info["escalation"]] == ["b", "a"]
    mid = employee_details(rows, routes, "b")
    assert [r["id"] for r in mid["direct_reports"]] == ["c"] and len(mid["approval_routes"]) == 1
    page = read("app_pages/employee_master.py")
    assert "Employee Photo (JPG / PNG, max 3 MB)" in page and "upload_employee_photo(" in page
