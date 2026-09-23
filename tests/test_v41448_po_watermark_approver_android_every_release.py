from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from core import purchase_order_reporting as por
from core.supply_chain_service import SupplyChainService

ROOT = Path(__file__).resolve().parents[1]


class _Repo:
    def __init__(self, legacy: bool = False):
        self.legacy = legacy
        self.po = {
            "id": "po-1", "po_number": "PD9010100009", "approval_status": "APPROVED",
            "approved_at": "2026-09-22T08:00:00+00:00", "updated_by": "profile-1",
        }
        if not legacy:
            self.po["approver_employee_id"] = "emp-1"

    def get(self, table, row_id):
        if table == "supply_purchase_orders" and row_id == "po-1":
            return dict(self.po)
        if table == "employees" and row_id == "emp-1":
            return {
                "id": "emp-1", "employee_code": "E001", "first_name": "Rajesh",
                "last_name": "Dhokale", "department": "Management", "designation": "CEO",
                "profile_id": "profile-1", "status": "ACTIVE",
            }
        return None

    def select(self, table, *, eq=None, limit=None, **kwargs):
        if table == "employees" and eq == {"profile_id": "profile-1", "status": "ACTIVE"}:
            return [{
                "id": "emp-1", "employee_code": "E001", "first_name": "Rajesh",
                "last_name": "Dhokale", "department": "Management", "designation": "CEO",
                "profile_id": "profile-1", "status": "ACTIVE",
            }]
        return []


def _fill_opacities(page) -> list[float]:
    ext = (page.get("/Resources") or {}).get("/ExtGState") or {}
    values = []
    for state in ext.values():
        obj = state.get_object() if hasattr(state, "get_object") else state
        if "/ca" in obj:
            values.append(float(obj["/ca"]))
    return values


def test_watermark_is_exactly_five_percent_background_and_unobtrusive():
    source = Path(por.__file__).read_text()
    assert 'setFillAlpha(0.05)' in source
    assert 'HexColor("#F2F4F7")' in source
    assert 'page.merge_page(watermark_page, over=False)' in source

    header = {
        "po_number": "PD9010100009", "order_date": "2026-09-22", "approval_status": "APPROVED",
        "approver_employee_name": "Rajesh Dhokale", "approver_employee_code": "E001",
        "approved_at": "2026-09-22T08:00:00+00:00", "subtotal": 100, "grand_total": 100,
    }
    item = {"item_no":"P-001","item_description":"Test Part","quantity":1,"uom":"PCS","unit_price":100,"gst_percent":0,"line_total":100}
    pdf = por.purchase_order_pdf_bytes(header, [item], terms_path="/__qcms_missing_terms__.pdf")
    page = PdfReader(BytesIO(pdf)).pages[0]
    assert any(abs(v - 0.05) < 1e-9 for v in _fill_opacities(page))


def test_single_purchase_order_lookup_enriches_real_approver_employee_name():
    service = SupplyChainService(_Repo())
    po = service.purchase_order("po-1")
    assert po["approver_employee_name"] == "Rajesh Dhokale"
    assert po["approver_employee_code"] == "E001"
    assert po["approver_designation"] == "CEO"


def test_legacy_approved_po_recovers_approver_from_profile_link():
    service = SupplyChainService(_Repo(legacy=True))
    po = service.purchase_order("po-1")
    assert po["approver_employee_id"] == "emp-1"
    assert po["approver_employee_name"] == "Rajesh Dhokale"


def test_approved_pdf_uses_employee_name_not_generic_authorised_approver():
    header = {
        "po_number": "PD9010100009", "order_date": "2026-09-22", "approval_status": "APPROVED",
        "approver_employee_name": "Rajesh Dhokale", "approver_employee_code": "E001",
        "approved_at": "2026-09-22T08:00:00+00:00", "subtotal": 100, "grand_total": 100,
    }
    item = {"item_no":"P-001","item_description":"Test Part","quantity":1,"uom":"PCS","unit_price":100,"gst_percent":0,"line_total":100}
    pdf = por.purchase_order_pdf_bytes(header, [item], terms_path="/__qcms_missing_terms__.pdf")
    page_text = PdfReader(BytesIO(pdf)).pages[0].extract_text()
    assert "Approver: Rajesh Dhokale" in page_text
    assert "Date / Time:" in page_text
    assert "Authorised Approver" not in page_text


def test_persistent_auth_bridge_does_not_rerun_or_reserve_page_height():
    auth = (ROOT / "core" / "auth.py").read_text()
    ui = (ROOT / "core" / "ui.py").read_text()
    assert '"saved_at"' not in auth
    assert 'setTriggerValue("done"' not in auth
    assert '"height": 0' in auth
    assert 'if (action === "write")' in auth
    write = auth.split('if (action === "write")', 1)[1].split('const payload = window.localStorage.getItem', 1)[0]
    assert 'setStateValue(' not in write
    assert 'st-key-qcms_auth_read' in ui
    assert 'max-height:0!important' in ui
    assert 'visibility:hidden!important' in ui


def test_android_workflow_builds_every_main_release_and_is_manually_runnable():
    workflow = (ROOT / '.github/workflows/qcms-android-test-apk.yml').read_text()
    gradle = (ROOT / 'mobile/android_qcms/app/build.gradle').read_text()
    java = (ROOT / 'mobile/android_qcms/app/src/main/java/com/fourstar/qcms/MainActivity.java').read_text()
    assert 'workflow_dispatch:' in workflow
    assert 'branches:' in workflow and '- main' in workflow
    assert 'paths:' not in workflow.split('permissions:')[0]
    assert 'QCMS_SERVER_RELEASE' in workflow
    assert "versionCode 15" in gradle
    assert "versionName '0.2.4'" in gradle
    assert 'QCMSMobile/0.2.4' in java
    assert 'Verify native navigation source before compile' in workflow
