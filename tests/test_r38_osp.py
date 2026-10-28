"""R38 · OSP: ONE Material Out / Returnable Delivery Challan workflow.

The separate "B · Returnable Delivery Challan" entry section is gone: one entry form saves the Material Out (existing RPC
qcms_create_osp_material_out, unchanged) AND its challan in the same Save; every Material Out opens as one record with
tabs Details · Print · Vendor returns (Material Out page and OSP Records). Older Material Outs without a challan still open
and print (DRAFT) and can be completed once."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "app_pages/osp_transactions.py").read_text(encoding="utf-8")
PERMS = '{"can_edit": True, "can_create": True, "can_archive": True}'

ENTRY_SCRIPT = '''
import streamlit as st
st.data_editor = lambda frame, **kwargs: frame
from tests.test_r37_osp import FakeRepo, TABLES
from core.osp_challan import OSPChallanService
from core.osp_service import OSPService
import app_pages.osp_transactions as page
repo = st.session_state.setdefault("challan_repo", FakeRepo({**TABLES, "osp_challans": [], "osp_challan_lines": []}))
class Challans(OSPChallanService):
    def save(self, *a, **k):
        if st.session_state.get("fail_challan", 0) > 0:
            st.session_state["fail_challan"] -= 1
            raise RuntimeError("network down")
        return super().save(*a, **k)
page.OSPChallanService = lambda *a, **k: Challans(repo)
class Rpc:
    def rpc(self, name, args):
        if name == "qcms_next_osp_challan_number": return "JWCD9TEST"
        st.session_state.setdefault("rpc_calls", []).append(name)
        st.session_state["submitted_rpc"] = {"name": name, "args": args}
        return {"id": "doc", "material_out_number": "OUT-TEST", "lines": [{"id": f"job{i}", **r} for i, r in enumerate(args["p_lines"])]}
class Service(OSPService):
    def __init__(self): self.repo = Rpc()
    def dispatch_candidates(self): return [{"candidate_key": "INWARD:a", "inward_lot_id": "a", "part_id": "part", "part_number": "PN", "heat_number": "HA", "inward_number": "IN-A", "osp_available_quantity_pcs": 10},
                                           {"candidate_key": "INWARD:b", "inward_lot_id": "b", "part_id": "part", "part_number": "PN", "heat_number": "HB", "inward_number": "IN-B", "osp_available_quantity_pcs": 20}]
    def specifications(self, part): return [{"id": "spec", "process_id": "process", "sample_quantity": 1}]
    def processes(self): return {"process": {"id": "process", "process_name": "Case Carburizing"}}
    def vendors(self): return [{"id": "vendor", "party_name": "OSP Vendor"}]
page._render_material_out_entry(Service(), {"can_create": True})
'''


def _body(name: str) -> str:
    return PAGE.split(f"def {name}", 1)[1].split("\ndef ", 1)[0]


def _entry_app(fail: int = 0):
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string(ENTRY_SCRIPT)
    app.session_state["fail_challan"] = fail
    app.run(timeout=30)
    assert not app.exception, app.exception
    app.multiselect[0].select("INWARD:a").select("INWARD:b").run(timeout=30)
    assert not app.exception, app.exception
    return app


# ------------------------------------------------------------------------------------------- one section only
def test_material_out_page_has_one_entry_and_one_record_view():
    page = _body("render_material_out()")
    assert page.count("_render_material_out_entry(") == 1 and "_render_challan_module(" in page
    assert "stage_section(" not in page  # no separate challan / edit / multi-heat sections on the page body
    assert "def _render_grouped_material_outs" not in PAGE and "def _render_record_challan" not in PAGE
    assert '"EDIT / DELETE MATERIAL OUT"' not in PAGE and '"MULTI-HEAT MATERIAL OUT DOCUMENTS"' not in PAGE
    assert not re.search(r'stage_section\("[A-Z]", "RETURNABLE DELIVERY CHALLAN"', PAGE)
    record = _body("render_material_out_record")
    assert 'st.tabs(["Details", "Print", "Vendor returns"])' in record
    assert "_render_challan_print(" in record and "_render_returns_section(" in record and "_render_challan_section(" in record
    # the returns block is a tab of the record, not another expander section
    assert "stage_section(" not in _body("_render_returns_section")
    # every challan field is entered exactly once in the entry form
    entry = _body("_render_material_out_entry")
    for label in ("Material Out Challan Number", "OSP Vendor", "Ship To", "Ship Via", "Incoterm", "Payment Term", "Vehicle No", "Transporter",
                  "E-way Bill No", "Reference Details", "Old PO Details", "Process To Be Done", "Shipping (INR)", "Other (INR)", "Expected Return / Delivery Date",
                  "Plant / Company Branch (challan series)", "Dispatch Remarks"):
        assert entry.count(f'"{label}"') == 1, label
    assert '"Delivery Date"' not in entry  # merged into "Expected Return / Delivery Date"
    # OSP Records opens the same record view
    records = _body("render_records")
    assert "render_material_out_record(service, challans, doc, challan, perms, allow_delete=False)" in records


def test_full_material_out_page_renders_single_create_button():
    from streamlit.testing.v1 import AppTest
    script = '''
import streamlit as st
st.data_editor = lambda frame, **kwargs: frame
import sys
if "core.osp_challan_pdf" in sys.modules and sys.modules["core.osp_challan_pdf"] is None:
    del sys.modules["core.osp_challan_pdf"]  # another test's AppTest script blocks this module process-wide
from tests.test_r37_osp import FakeRepo, TABLES, JOB
from core.osp_challan import OSPChallanService
from core.osp_service import OSPService
import app_pages.osp_transactions as page
repo = FakeRepo(TABLES)
_saved = {name: getattr(page, name) for name in ("OSPChallanService", "selectable_table", "current_permissions", "subpage_navigation", "OSPService")}
page.OSPChallanService = lambda *a, **k: OSPChallanService(repo)
page.selectable_table = lambda frame, **k: None
page.current_permissions = lambda module: ''' + PERMS + '''
page.subpage_navigation = lambda *a, **k: None
class Svc(OSPService):
    def __init__(self): self.repo = repo
    def register(self): return [dict(JOB, vendor_name="PMT", status="AT_VENDOR", material_out_number="OUT-1", dispatch_date="2026-10-19")]
    def dispatch_candidates(self): return [{"candidate_key": "INWARD:a", "inward_lot_id": "a", "part_id": "part", "part_number": "PN", "heat_number": "HA", "inward_number": "IN-A", "osp_available_quantity_pcs": 10}]
    def specifications(self, part): return [{"id": "spec", "process_id": "process", "sample_quantity": 1}]
    def processes(self): return {"process": {"id": "process", "process_name": "Case Carburizing"}}
    def vendors(self): return [{"id": "vendor", "party_name": "OSP Vendor"}]
page.OSPService = Svc
try:
    page.render_material_out()
finally:  # the page module is shared by the whole pytest process - leave it unpatched
    for name, value in _saved.items():
        setattr(page, name, value)
'''
    app = AppTest.from_string(script).run(timeout=30)
    assert not app.exception, app.exception
    app.multiselect[0].select("INWARD:a").run(timeout=30)
    assert not app.exception, app.exception
    buttons = [b.label for b in app.button]
    assert buttons.count("Create OSP Material Out") == 1
    assert "Update Challan" not in buttons and "Save Challan" not in buttons  # no second challan entry form
    assert [t.label for t in app.tabs] == ["Details", "Print", "Vendor returns"]
    assert "Save Return" in buttons and "Send Challan E-mail" in buttons, [e.value for e in app.error]
    assert any(b.label == "Download Challan PDF" for b in app.get("download_button"))


# ------------------------------------------------------------------------------------------- save creates both
def test_save_creates_material_out_and_challan_in_one_action():
    app = _entry_app()
    next(x for x in app.text_input if x.label == "Material Out Challan Number").set_value("JWCD901099")
    next(x for x in app.text_input if x.label == "Vehicle No").set_value("MH12AB1234")
    next(x for x in app.text_input if x.label == "Reference Details").set_value("REF-7")
    next(x for x in app.button if x.label == "Create OSP Material Out").click().run(timeout=30)
    assert not app.exception, app.exception
    assert app.session_state["rpc_calls"] == ["qcms_create_osp_material_out"]  # existing RPC, unchanged semantics
    args = app.session_state["submitted_rpc"]["args"]
    assert args["p_header"]["dispatch_challan"] == "JWCD901099" and len(args["p_lines"]) == 2
    repo = app.session_state["challan_repo"]
    assert len(repo.tables["osp_challans"]) == 1
    header = repo.tables["osp_challans"][0]
    assert header["challan_number"] == "JWCD901099" and header["material_out_id"] == "doc" and header["vehicle_number"] == "MH12AB1234"
    assert header["reference_details"] == "REF-7" and header["delivery_date"] == args["p_header"]["expected_return_date"]
    assert header["challan_date"] == args["p_header"]["dispatch_date"]
    assert sorted(l["osp_job_id"] for l in repo.tables["osp_challan_lines"]) == ["job0", "job1"]
    assert app.session_state["osp_mo_open"] == "doc"


def test_duplicate_challan_number_blocks_before_material_out_rpc():
    app = _entry_app()
    next(x for x in app.text_input if x.label == "Material Out Challan Number").set_value("JWCD901026")
    repo = app.session_state["challan_repo"]
    repo.tables["osp_challans"].append({"id": "old", "challan_number": "JWCD901026", "material_out_id": "other"})
    next(x for x in app.button if x.label == "Create OSP Material Out").click().run(timeout=30)
    assert not app.exception, app.exception
    assert "rpc_calls" not in app.session_state  # nothing allocated
    assert any("already used" in e.value for e in app.error)


def test_challan_failure_retries_once_then_keeps_entries_for_retry():
    app = _entry_app(fail=1)  # first attempt fails, automatic retry succeeds
    next(x for x in app.button if x.label == "Create OSP Material Out").click().run(timeout=30)
    assert not app.exception, app.exception
    assert len(app.session_state["challan_repo"].tables["osp_challans"]) == 1

    app = _entry_app(fail=5)  # both attempts fail -> Material Out kept (never re-created), entries kept for one-click retry
    next(x for x in app.text_input if x.label == "Material Out Challan Number").set_value("JWCD901200")
    next(x for x in app.button if x.label == "Create OSP Material Out").click().run(timeout=30)
    assert not app.exception, app.exception
    assert app.session_state["rpc_calls"] == ["qcms_create_osp_material_out"]
    assert app.session_state["challan_repo"].tables["osp_challans"] == []
    pending = app.session_state["osp_challan_pending_doc"]
    assert pending["header"]["challan_number"] == "JWCD901200" and set(pending["lines"]) == {"job0", "job1"}
    assert "Do NOT create the Material Out again" in app.session_state["osp_mo_flash_doc"]


def test_retry_reuses_partially_saved_header():
    from tests.test_r37_osp import FakeRepo, TABLES
    from core.osp_challan import OSPChallanService
    from app_pages.osp_transactions import save_material_out_challan

    repo = FakeRepo({**TABLES, "osp_challans": [], "osp_challan_lines": []})
    calls = {"n": 0}
    original = repo.insert

    def flaky(table, payload):
        if table == "osp_challan_lines" and calls["n"] == 0:
            calls["n"] += 1
            raise RuntimeError("timeout")
        return original(table, payload)
    repo.insert = flaky
    ok, error = save_material_out_challan(OSPChallanService(repo), {"is_group": True, "material_out_id": "g9", "id": "g9"},
                                          {"challan_number": "JWCD901300"}, [{"osp_job_id": "j1", "unit_price": 5}])
    assert ok and error is None
    assert len(repo.tables["osp_challans"]) == 1 and len(repo.tables["osp_challan_lines"]) == 1


# ------------------------------------------------------------------------------------------- existing material outs
def test_existing_material_out_without_challan_opens_prints_draft_and_completes():
    from streamlit.testing.v1 import AppTest
    script = '''
import streamlit as st
st.data_editor = lambda frame, **kwargs: frame
import sys
if "core.osp_challan_pdf" in sys.modules and sys.modules["core.osp_challan_pdf"] is None:
    del sys.modules["core.osp_challan_pdf"]  # another test's AppTest script blocks this module process-wide
from tests.test_r37_osp import FakeRepo, TABLES, JOB
from core.osp_challan import OSPChallanService
from core.osp_service import OSPService
import app_pages.osp_transactions as page
repo = st.session_state.setdefault("repo", FakeRepo({**TABLES, "osp_challans": [], "osp_challan_lines": [], "osp_challan_returns": []}))
class Svc(OSPService):
    def __init__(self): self.repo = repo
challans = OSPChallanService(repo)
doc = OSPService.material_out_documents([dict(JOB, material_out_number="OUT-OLD", vendor_name="PMT", dispatch_date="2026-10-19", expected_return_date="2026-10-26")])[0]
page.render_material_out_record(Svc(), challans, doc, challans.challan_for(doc), ''' + PERMS + ''')
'''
    app = AppTest.from_string(script).run(timeout=30)
    assert not app.exception, app.exception
    assert any(t.label == "Complete challan details" for t in app.toggle)
    assert any(b.label == "Download DRAFT Challan PDF" for b in app.get("download_button"))
    assert any(b.label.startswith("Internal Material Out record PDF") for b in app.get("download_button"))
    assert any("Complete the challan details first" in i.value for i in app.info)
    next(x for x in app.button if x.label == "Save Challan").click().run(timeout=30)
    assert not app.exception, app.exception
    header = app.session_state["repo"].tables["osp_challans"][0]
    assert header["challan_number"] == "JWCD901026" and header["material_out_id"] == "g1" and header["delivery_date"] == "2026-10-26"


def test_correction_updates_material_out_quantities_through_existing_rpc():
    from app_pages.osp_transactions import _sync_material_out

    class Svc:
        def __init__(self): self.calls = []
        def update_material_out_group(self, gid, header, lines): self.calls.append(("group", gid, header, lines))
        def update_material_out(self, payload): self.calls.append(("single", payload))

    line = {"id": "j1", "dispatch_challan": "JWC1", "dispatch_date": "2026-10-19", "expected_return_date": "2026-10-26", "dispatch_remarks": "", "quantity_dispatched": 10}
    doc = {"id": "g1", "is_group": True, "lines": [line]}
    svc = Svc()
    assert _sync_material_out(svc, doc, number="jwc1", dispatch_date="2026-10-19", expected_date="2026-10-26", remarks="", quantities={"j1": 10}) == ""
    assert svc.calls == []
    _sync_material_out(svc, doc, number="JWC1", dispatch_date="2026-10-19", expected_date="2026-10-26", remarks="", quantities={"j1": 8})
    assert svc.calls == [("group", "g1", {"dispatch_date": "2026-10-19", "expected_return_date": "2026-10-26", "dispatch_challan": "JWC1", "remarks": ""}, [{"id": "j1", "quantity_dispatched": 8.0}])]

    class Blocked(Svc):
        def update_material_out(self, payload): raise RuntimeError("downstream receipt exists")
    single = dict(line, id="j1")
    single_doc = {**single, "is_group": False, "lines": [single]}
    # challan-number-only change: reported, challan still saved
    assert "could not be updated" in _sync_material_out(Blocked(), single_doc, number="JWC2", dispatch_date="2026-10-19", expected_date="2026-10-26", remarks="", quantities={})
    # quantity change blocked by genealogy: the whole save stops
    try:
        _sync_material_out(Blocked(), single_doc, number="JWC1", dispatch_date="2026-10-19", expected_date="2026-10-26", remarks="", quantities={"j1": 5})
    except RuntimeError:
        pass
    else:
        raise AssertionError("quantity change must not be silently ignored")


def test_challan_print_stays_vendor_safe():
    page = _body("_render_challan_print")
    assert "customer" not in page.lower()
    entry = _body("_render_material_out_entry")
    assert "customer_name" not in entry and "customer_po" not in entry


def test_osp_records_opens_the_same_record_view():
    from streamlit.testing.v1 import AppTest
    script = '''
import streamlit as st
st.data_editor = lambda frame, **kwargs: frame
import sys
if "core.osp_challan_pdf" in sys.modules and sys.modules["core.osp_challan_pdf"] is None:
    del sys.modules["core.osp_challan_pdf"]
from tests.test_r37_osp import FakeRepo, TABLES, JOB
from core.osp_challan import OSPChallanService
from core.osp_service import OSPService
import app_pages.osp_transactions as page
repo = FakeRepo({**TABLES, "lab_tests": [], "inspection_reports": []})
names = ("OSPChallanService", "current_permissions", "subpage_navigation", "OSPService", "InspectionService", "record_email_sender", "NotificationService")
_saved = {name: getattr(page, name) for name in names}
page.OSPChallanService = lambda *a, **k: OSPChallanService(repo)
page.current_permissions = lambda module: ''' + PERMS + '''
page.subpage_navigation = lambda *a, **k: None
page.record_email_sender = lambda *a, **k: None
page.NotificationService = lambda *a, **k: None
class Insp:
    def __init__(self): self.repo = repo
page.InspectionService = Insp
class Svc(OSPService):
    def __init__(self): self.repo = repo
    def register(self): return [dict(JOB, vendor_name="PMT", status="AT_VENDOR", material_out_number="OUT-1", osp_job_number="OSP-1", dispatch_date="2026-10-19")]
    def receipts(self, job_id): return []
page.OSPService = Svc
try:
    page.render_records()
finally:
    for name, value in _saved.items():
        setattr(page, name, value)
'''
    app = AppTest.from_string(script).run(timeout=30)
    assert not app.exception, app.exception
    assert [t.label for t in app.tabs] == ["Details", "Print", "Vendor returns"]
    assert any(e.label.startswith("B - MATERIAL OUT OUT-1 · CHALLAN JWCD901026") for e in app.expander)
    assert any(b.label == "Download Challan PDF" for b in app.get("download_button"))
    assert "Delete Material Out" not in [e.label for e in app.expander]  # deletes stay in OSP Records C / Material Out record
