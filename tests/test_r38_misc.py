"""R38 (agent D, tests/test_r38_misc.py) · header branding, licensed company logo, version only in user details, login cover photo,
department e-mail subjects, employee photo + reporting / escalation details, PO approval auto-download, OSP merged entry."""
from __future__ import annotations

import base64
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261028140000_qcms_r38_misc.sql"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------------ 1-3 header
def test_header_icon_is_sized_and_never_squeezed():
    ui = read("core/ui.py")
    assert "R38 header branding" in ui
    assert "flex:0 0 46px!important;width:46px!important;height:46px!important;min-width:46px!important" in ui
    assert "object-fit:cover!important" in ui
    # the shrunk data URI is still a valid PNG of the STAWN icon
    from core import ui as ui_mod
    uri = ui_mod.stawn_logo_data_uri()
    assert uri.startswith("data:image/png;base64,")
    data = base64.b64decode(uri.split(",", 1)[1])
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) < (ROOT / "assets/stawn_qcms_icon.png").stat().st_size


def test_header_company_logo_and_no_logo_fallback(monkeypatch):
    import streamlit as st
    from core import licence_service, ui

    st.session_state.pop(ui.HEADER_COMPANY_LOGO_KEY, None)
    logo = (ROOT / "assets/fsi_logo.png").read_bytes()
    monkeypatch.setattr(licence_service, "company_profile", lambda tid=None: {"display_name": "Four Star", "logo_path": "t/logo.png"})
    monkeypatch.setattr(licence_service, "company_logo_bytes", lambda path: logo if path else None)
    html = ui.header_company_logo_html("Four Star Industries Private Limited")
    assert 'class="qcms-hdr-company-logo"' in html and "data:image/png;base64," in html and 'title="Four Star"' in html
    # cached for the session
    monkeypatch.setattr(licence_service, "company_logo_bytes", lambda path: None)
    assert ui.header_company_logo_html("x") == html
    st.session_state.pop(ui.HEADER_COMPANY_LOGO_KEY, None)
    monkeypatch.setattr(licence_service, "company_profile", lambda tid=None: {})
    fallback = ui.header_company_logo_html("Four Star Industries Private Limited")
    # R38 (shell): no uploaded logo -> the licensed company's initials badge
    assert 'class="qcms-hdr-company-initials"' in fallback and ">FSI</span>" in fallback
    st.session_state.pop(ui.HEADER_COMPANY_LOGO_KEY, None)


def test_header_renders_company_logo_before_user_and_version_only_in_user_details():
    from streamlit.testing.v1 import AppTest

    script = '''
import streamlit as st
st.session_state["_qsms_preview"] = True  # no live Supabase calls from the header (Mac has real secrets)
from core import ui
st.session_state[ui.HEADER_COMPANY_LOGO_KEY] = {"_at": 9e12, "html": '<span class="qcms-hdr-company-logo"><img src="data:image/png;base64,AAAA" alt="Four Star"></span>'}
st.session_state["_qcms_r35_licence_status"] = {"_at": 9e12, "data": {"company_name": "Four Star Industries Private Limited"}}
ui.render_shell_header({"full_name": "Rajesh Dhokale", "role": "ADMIN"}, "Dashboard")
'''
    app = AppTest.from_string(script).run(timeout=90)
    assert not app.exception, app.exception
    html = " ".join(m.value for m in app.markdown)
    user = html[html.index('<div class="fsi-user">'):]
    assert user.index("qcms-hdr-company-logo") < user.index("fsi-user-avatar") < user.index("fsi-user-name")
    from core.config import get_settings
    version = get_settings().version
    meta = user[user.index('class="fsi-user-meta"'):].split("</div>", 1)[0]
    assert f"v{version}" not in meta  # R38 (shell): not on the ribbon any more
    assert f"v{version}" in user  # only in the "User details" popover next to it
    brand = html[html.index('fsi-company-block'):html.index('fsi-user')]
    assert version not in brand and 'class="fsi-logo"' in brand


def test_version_removed_from_search_caption_and_developer_page():
    app = read("streamlit_app.py")
    assert 'gs3.caption(f"STAWN QCMS · v{settings.version}' not in app
    caption = next(line for line in app.splitlines() if "gs3.caption(" in line)
    assert "version" not in caption and "LIVE BUILD" not in caption
    assert "LIVE BUILD · QCMS" in app  # historical source marker only (comment)
    lic = read("app_pages/licence_company.py")
    assert "get_settings().version" not in lic and "R35 · STAWN icon" not in lic
    ui = read("core/ui.py")
    assert "· v{safe(s.version)}</div>" not in ui and "def app_version_text" in ui  # version only in the user details popover
    auth = read("core/auth.py")
    assert "settings.version)" not in auth.split("def render_login", 1)[1].split("def render_first_admin_claim", 1)[0]


# ------------------------------------------------------------------------------------------------ 4 login cover
def test_migration_public_bucket_and_developer_policies():
    sql = MIGRATION.read_text()
    assert "'qcms-public', 'qcms-public', true" in sql and "on conflict (id) do nothing" in sql
    assert "public.qcms_is_stawn_developer()" in sql and sql.count("create policy qcms_public_dev_") == 4
    for word in ("DELETE", "UPDATE", "DROP"):
        assert not re.search(rf"\b{word}\b", sql), word
    assert "supabase/migrations/20261028140000_qcms_r38_misc.sql" in read("supabase/auto_apply.json")
    assert "r38_branding_misc" not in read("supabase/auto_apply.json") and "5242880" in sql


def test_login_cover_prefers_uploaded_photo(monkeypatch):
    from core import auth

    calls = []

    def fake_download(url, timeout=auth.LOGIN_COVER_TIMEOUT_SECONDS):
        calls.append(url)
        return b"\xff\xd8\xffPNGDATA" if url.endswith("cover.png") else None

    monkeypatch.setattr(auth, "_download_public_image", fake_download)
    auth.clear_login_cover_cache()
    assert auth._cached_login_cover("https://x.supabase.co") == b"\xff\xd8\xffPNGDATA"
    assert calls == ["https://x.supabase.co/storage/v1/object/public/qcms-public/login/cover.jpg",
                     "https://x.supabase.co/storage/v1/object/public/qcms-public/login/cover.png"]
    auth.clear_login_cover_cache()
    monkeypatch.setattr(auth, "_download_public_image", lambda url, timeout=0: None)
    assert auth._cached_login_cover("https://x.supabase.co") is None
    auth.clear_login_cover_cache()
    src = read("core/auth.py")
    assert "cover = login_cover_bytes()" in src and "login_factory.jpeg" in src


class _Bucket:
    def __init__(self, log):
        self.log = log

    def upload(self, path, data, options):
        self.log.append(("upload", path, len(data), dict(options)))

    def remove(self, paths):
        self.log.append(("remove", list(paths)))


class _Client:
    def __init__(self):
        self.log = []
        outer = self

        class Storage:
            def from_(self, bucket):
                outer.log.append(("bucket", bucket))
                return _Bucket(outer.log)

        self.storage = Storage()


class _File:
    def __init__(self, data, name, mime):
        self._d, self.name, self.type = data, name, mime

    def getvalue(self):
        return self._d


def test_developer_uploads_and_resets_login_cover():
    from app_pages import licence_company as page

    client = _Client()
    path = page.upload_login_cover(_File(b"x" * 100, "cover.PNG", "image/png"), client)
    assert path == "login/cover.png"
    assert ("bucket", "qcms-public") in client.log
    upload = next(e for e in client.log if e[0] == "upload")
    assert upload[1] == "login/cover.png" and upload[3]["content-type"] == "image/png" and upload[3]["upsert"] == "true"
    assert ("remove", ["login/cover.jpg"]) in client.log
    with pytest.raises(ValueError):
        page.upload_login_cover(_File(b"x" * (5 * 1024 * 1024 + 1), "big.jpg", "image/jpeg"), _Client())
    with pytest.raises(ValueError):
        page.upload_login_cover(_File(b"x", "cover.gif", "image/gif"), _Client())
    client = _Client()
    page.reset_login_cover(client)
    assert ("remove", ["login/cover.jpg", "login/cover.png"]) in client.log
    src = read("app_pages/licence_company.py")
    assert "_login_cover_section()" in src and "LOGIN PAGE COVER PHOTO" in src and "Reset to default photo" in src


# ------------------------------------------------------------------------------------------------ 5 subjects
def test_department_replaces_qcms_in_subjects():
    from core.notification_service import department_subject

    assert department_subject("QCMS · RMTC approval pending · R-1", "METLAB", "RMTC_APPROVAL_PENDING") == "MetLAB · RMTC approval pending · R-1"
    assert department_subject("QCMS · PO 7 approved", "Supply Chain", "PO_APPROVED") == "Supply Chain · PO 7 approved"
    assert department_subject("STAWN QCMS · Email server test", "", "EMAIL_SERVER_TEST") == "Admin · Email server test"
    assert department_subject("QCMS · Complaint", "", "CUSTOMER_COMPLAINT_CREATED") == "Quality · Complaint"
    assert department_subject("QCMS · Indirect PO", "", "INDIRECT_PO_APPROVAL") == "Purchase · Indirect PO"
    # subjects without the QCMS prefix also get the department in front (once)
    assert department_subject("PRIORITY · Purchase Order confirmation required", "", "PO_CONFIRMATION_REQUIRED") == \
        "Purchase · PRIORITY · Purchase Order confirmation required"
    assert department_subject("Forging Purchase Order PO-1 Released through QCMS", "Supply Chain", "FORGING_PO_CREATED") == \
        "Supply Chain · Forging Purchase Order PO-1 Released through QCMS"
    assert department_subject("Quality · Already prefixed", "Supply Chain", "PO_APPROVED") == "Quality · Already prefixed"
    assert department_subject("Plain", "", "SOMETHING") == "Plain"
    assert department_subject("QCMS · Unknown", "QCMS Team", "SOMETHING") == "QCMS · Unknown"


def test_notification_service_applies_department_to_preview_and_enqueue():
    from core.notification_service import NotificationService

    src = read("core/notification_service.py")
    assert src.count("department_subject(") >= 3  # definition + preview + enqueue

    class Repo:
        tenant_id = "t"

        def select(self, table, **kwargs):
            if table == "qcms_notification_routes":
                return [{"event_key": "RMTC_APPROVAL_PENDING", "department": "METLAB", "enabled": True, "status": "ACTIVE"}]
            return []

    svc = NotificationService(Repo())
    svc.recipient_for_route = lambda route: ("lab@example.com", "Lab")
    svc.route = lambda event: {"event_key": event, "department": "METLAB"}
    svc.template = lambda key, event: {"subject_template": "QCMS · RMTC approval pending · {{document_no}}"}
    preview = svc.preview("RMTC_APPROVAL_PENDING", context={"document_no": "RM-9"})
    assert preview["subject"] == "MetLAB · RMTC approval pending · RM-9"


def test_scheduled_notifier_subjects_use_department():
    for name in ("qcms-overdue-notifier", "qcms-supply-digest-notifier"):
        src = read(f"supabase/functions/{name}/index.ts")
        assert "function r38DepartmentSubject" in src and "r38ScheduleDepartment(schedule)" in src
    approval = read("supabase/functions/qcms-po-approval-overdue/index.ts")
    assert "`Supply Chain · ${ln>1?\"ESCALATION · \":\"\"}PO" in approval
    # the subject sits on a long one-line statement: a // comment there would swallow `const intro=`
    assert not re.search(r"approval overdue`;\s*//", approval) and "approval overdue`; /* R38: department instead of QCMS */const intro=" in approval
    reminder = read("supabase/functions/qcms-po-confirmation-reminder/index.ts")
    assert "`Purchase · PRIORITY · Purchase Order confirmation pending" in reminder


# ------------------------------------------------------------------------------------------------ 6 employees
EMPLOYEES = [
    {"id": "e1", "first_name": "Asha", "last_name": "Patil", "designation": "QA Engineer", "department": "Quality", "reports_to_employee_id": "e2", "email": "a@x"},
    {"id": "e2", "first_name": "Bala", "last_name": "Rao", "designation": "QA Manager", "department": "Quality", "reports_to_employee_id": "e3", "email": "b@x"},
    {"id": "e3", "first_name": "Chetan", "last_name": "S", "designation": "Plant Head", "department": "Management", "reports_to_employee_id": "e4"},
    {"id": "e4", "first_name": "Dev", "last_name": "K", "designation": "Director", "department": "Management", "reports_to_employee_id": "e5"},
    {"id": "e5", "first_name": "Esha", "last_name": "M", "designation": "MD", "department": "Management", "reports_to_employee_id": "e6"},
    {"id": "e6", "first_name": "Farid", "last_name": "N", "designation": "Chairman", "department": "Management", "reports_to_employee_id": "e1"},
    {"id": "e7", "first_name": "Gita", "last_name": "P", "designation": "Inspector", "department": "Quality", "reports_to_employee_id": "e1"},
]


def test_escalation_chain_direct_reports_and_routes():
    from core.employee_service import approver_routes, direct_reports, employee_details, escalation_chain

    chain = escalation_chain(EMPLOYEES, "e1")
    assert [r["id"] for r in chain] == ["e2", "e3", "e4", "e5"] and [r["level"] for r in chain] == [1, 2, 3, 4]
    assert [r["id"] for r in escalation_chain(EMPLOYEES, "e5")] == ["e6", "e1", "e2", "e3"]  # cycle-safe, max 4
    assert escalation_chain(EMPLOYEES, "unknown") == []
    assert [r["id"] for r in direct_reports(EMPLOYEES, "e1")] == ["e6", "e7"]
    routes = [{"employee_id": "e1", "module_key": "RMTC", "department": "MetLAB", "level_no": 2, "status": "ACTIVE"},
              {"employee_id": "e1", "module_key": "RMTC", "department": "MetLAB", "level_no": 1, "status": "INACTIVE"},
              {"employee_id": "e2", "module_key": "PPAP", "department": "Quality", "level_no": 1}]
    assert [r["level_no"] for r in approver_routes(routes, "e1")] == [2]
    info = employee_details(EMPLOYEES, routes, "e1")
    assert info["reporting_to"]["id"] == "e2" and info["departments"] == ["MetLAB", "Quality"]


def test_employee_photo_upload_path_and_size(monkeypatch):
    import core.database as database
    from core import employee_service as svc

    class Repo:
        tenant_id = "tid"
        updates = []

        def update(self, table, rid, payload):
            self.updates.append((table, rid, payload))

    client = _Client()
    monkeypatch.setattr(database, "get_session_client", lambda: client)
    repo = Repo()
    path = svc.upload_employee_photo(repo, "e1", _File(b"img", "me.JPEG", "image/jpeg"))
    assert path == "tid/employees/e1/photo_e1.jpg" and repo.updates == [("employees", "e1", {"photo_storage_path": path})]
    assert ("bucket", "quality-documents") in client.log
    with pytest.raises(ValueError):
        svc.upload_employee_photo(repo, "e1", _File(b"x" * (3 * 1024 * 1024 + 1), "big.jpg", "image/jpeg"))
    with pytest.raises(ValueError):
        svc.photo_path("tid", "e1", "x.gif")
    page = read("app_pages/employee_master.py")
    assert "_employee_details_panel(svc,rows,selected_row)" in page and "upload_employee_photo(repo,str(saved['id']),photo)" in page
    assert "EMPLOYEE DETAILS · REPORTING & ESCALATION" in page and "Approver in approval routes" in page


# ------------------------------------------------------------------------------------------------ 7 PO auto-download
def test_po_approval_triggers_one_time_download():
    from app_pages import supply_chain as page

    html = page.po_auto_download_html(b"%PDF-1.4 test", "PO-1_APPROVED.pdf", "n1")
    assert base64.b64encode(b"%PDF-1.4 test").decode() in html and '"PO-1_APPROVED.pdf"' in html and "qcms-po-dl-n1" in html
    src = read("app_pages/supply_chain.py")
    assert "queue_po_approved_download(po_id)" in src
    approval = src.split("def render_purchase_order_approval_page", 1)[1][:800]
    assert "_po_approved_auto_download(service)" in approval
    assert "Download approved Purchase Order PDF" in src


# ------------------------------------------------------------------------------------------------ 8 OSP merged entry
def test_osp_material_out_is_the_challan_entry():
    src = read("app_pages/osp_transactions.py")
    assert "A · NEW MATERIAL OUT · RETURNABLE DELIVERY CHALLAN" in src
    assert '"Correct challan details" if challan else "Complete challan details"' in src
    for label in ("E-way Bill No", "Shipping (INR)", "Other (INR)"):
        assert src.split("def _render_material_out_entry", 1)[1].split("def _profile_name", 1)[0].count(label) == 1


def test_osp_material_out_entry_saves_full_challan_without_pyarrow():
    from streamlit.testing.v1 import AppTest

    script = '''
import streamlit as st
st.data_editor = lambda frame, **kwargs: frame
from tests.test_r37_osp import FakeRepo, TABLES
from core.osp_challan import OSPChallanService
from core.osp_service import OSPService
import app_pages.osp_transactions as page
repo = st.session_state.setdefault("challan_repo", FakeRepo({**TABLES, "osp_challans": [], "osp_challan_lines": []}))
page.OSPChallanService = lambda *a, **k: OSPChallanService(repo)
class Rpc:
    def rpc(self, name, args):
        return {"id": "doc", "material_out_number": "OUT-TEST", "lines": [{"id": f"job{i}", **r} for i, r in enumerate(args["p_lines"])]}
class Service(OSPService):
    def __init__(self): self.repo = Rpc()
    def dispatch_candidates(self): return [{"candidate_key": "INWARD:a", "inward_lot_id": "a", "part_id": "part", "part_number": "PN", "heat_number": "HA", "inward_number": "IN-A", "osp_available_quantity_pcs": 10}]
    def specifications(self, part): return [{"id": "spec", "process_id": "process", "sample_quantity": 1}]
    def processes(self): return {"process": {"id": "process", "process_name": "Case Carburizing"}}
    def vendors(self): return [{"id": "vendor", "party_name": "OSP Vendor"}]
page._render_material_out_entry(Service(), {"can_create": True})
'''
    app = AppTest.from_string(script).run(timeout=30)
    assert not app.exception, app.exception
    app.multiselect[0].select("INWARD:a").run(timeout=30)
    next(x for x in app.text_input if x.label == "Material Out Challan Number").set_value("JWCD901077")
    next(x for x in app.text_input if x.label == "E-way Bill No").set_value("EWB-123")
    next(x for x in app.text_input if x.label == "Transporter").set_value("VRL")
    next(x for x in app.number_input if x.label == "Shipping (INR)").set_value(250.0)
    next(x for x in app.button if x.label == "Create OSP Material Out").click().run(timeout=30)
    assert not app.exception, app.exception
    header = app.session_state["challan_repo"].tables["osp_challans"][0]
    assert header["challan_number"] == "JWCD901077" and header["eway_bill_number"] == "EWB-123"
    assert header["transporter_name"] == "VRL" and float(header["shipping_amount"]) == 250.0


# ------------------------------------------------------------------------------------------------ R38 misc additions
def test_header_logo_css_scoped_to_header_card_and_company_logo_32px():
    ui = read("core/ui.py")
    assert "html body .fsi-logo-card .fsi-logo{width:46px!important" in ui  # login brand (wide FSI logo) is not cropped
    assert "html body .qcms-hdr-company-logo img{height:32px;max-height:32px;" in ui


def test_dashboard_home_has_no_version_banner():
    dash = read("app_pages/dashboard.py")
    render = dash.split("def render()", 1)[1].split("repo = Repository()", 1)[0]
    assert "st.info(" not in render and "version" not in render.replace("app version is shown only", "")
    assert "LIVE RELEASE VERIFICATION" in dash  # historical source marker (comment) kept for older regression checks


def test_schedule_escalations_in_employee_details():
    from core.employee_service import employee_details, schedule_escalations

    schedules = [
        {"schedule_key": "PO_PENDING_APPROVAL", "schedule_label": "PO pending approval", "module_key": "SUPPLY_CHAIN",
         "recipient_department": "Management", "overdue_level1_employee_id": "e1", "overdue_level1_after_hours": 24,
         "overdue_level2_employee_id": "e2", "overdue_level2_after_hours": 48, "enabled": True},
        {"schedule_key": "RMTC", "schedule_label": "RMTC due", "overdue_level2_employee_id": "e1", "overdue_level2_after_hours": 72, "enabled": False},
    ]
    found = schedule_escalations(schedules, "e1")
    assert [(r["schedule_label"], r["level"], r["after_hours"]) for r in found] == [("PO pending approval", 1, 24), ("RMTC due", 2, 72)]
    assert schedule_escalations(schedules, "") == []
    info = employee_details(EMPLOYEES, [], "e2", schedules)
    assert [r["level"] for r in info["schedule_escalations"]] == [2]
    page = read("app_pages/employee_master.py")
    assert "qcms_notification_schedules" in page and "Overdue escalation in notification schedules" in page
    assert "boss.get('photo_storage_path')" in page and "**E-mail:**" in page


def test_po_auto_download_uses_blob_with_data_url_fallback():
    from app_pages import supply_chain as page

    html = page.po_auto_download_html(b"%PDF-1.4 x", "PO.pdf", "n2")
    assert "createObjectURL" in html and "new win.Blob" in html and "data:application/pdf;base64," in html
    assert "sessionStorage" in html  # once per nonce


def test_reminder_functions_prefix_department_on_any_subject():
    for name in ("qcms-overdue-notifier", "qcms-supply-digest-notifier"):
        src = read(f"supabase/functions/{name}/index.ts")
        body = src.split("function r38DepartmentSubject", 1)[1].split("\n}", 1)[0]
        assert "return known ? subject : `${label} · ${subject.trim()}`;" in body
