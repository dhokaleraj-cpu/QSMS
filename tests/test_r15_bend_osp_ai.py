"""R15: Bend Test module + report layout, separate bend layout scope, OSP finalize guidance, free AI providers, Android 1.1.0."""
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from app_pages.osp_inspections import osp_finalize_blockers, osp_gate_checklist
from core import ai_assistant as ai
from core.reporting import bend_test_report_pdf_bytes

ROOT = Path(__file__).resolve().parents[1]


def _text(pdf: bytes) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)


def test_bend_pdf_follows_customer_report_layout():
    payload = {
        "record": {"report_number": "1006/2026/7237", "test_date": "2026-10-09", "part_number": "40256626", "heat_number": "H123"},
        "results": {"inspection_method": "BEND_TEST", "bend_angle_degrees": 171,
                    "bend_report": {"customer_name": "ACME", "baking_batch_no": "BK-7", "conclusion": "Part accepted"}},
    }
    text = _text(bend_test_report_pdf_bytes(payload))
    for token in ("BEND TEST REPORT", "Baking", "Bend Test Results", "Load Vs CHT", "Bend Test Part", "171", "Conclusion", "Prepared By", "BK-7", "ACME"):
        assert token in text, token
    assert len(PdfReader(BytesIO(bend_test_report_pdf_bytes(payload))).pages) == 1


def test_bend_module_and_layout_master_routes():
    app = (ROOT / "streamlit_app.py").read_text()
    assert '"bend-layout-entry"' in app and "Bend Test Layout Master" in app
    assert '"Bend Test": (' in app
    assert "render_bend_layout_entry" in (ROOT / "app_pages/inspection_layouts.py").read_text()


class _Repo:
    def __init__(self, rows): self.rows = rows
    def select(self, table, **_): return list(self.rows)


def test_bend_layout_does_not_collide_with_general_metlab_layout():
    from core.inspection_service import InspectionService
    svc = InspectionService.__new__(InspectionService)
    general = {"id": "p1", "part_id": "A", "process_id": "", "inspection_stage_id": "S", "layout_type": "METLAB", "inward_type": "MATERIAL_INWARD", "status": "APPROVED"}
    svc.repo = _Repo([general])
    svc.plan_inspection_method = lambda plan_id: "GENERAL"
    payload = {"part_id": "A", "inspection_stage_id": "S", "layout_type": "METLAB"}
    assert svc.scope_plan(payload, inspection_method="BEND_TEST") is None
    assert svc.scope_plan(payload, inspection_method="GENERAL")["id"] == "p1"


def test_osp_finalize_explains_why_disabled():
    emps = {"e12": "EMP-0012 · Nitin Nanavare", "e1": "EMP-0001 · Raj"}
    final = osp_finalize_blockers(existing={"status": "FINAL", "approved_by_employee_id": "e12", "approved_at": "2026-10-08T10:00:00"}, can_approve=True, disposition="ACCEPTED", validator="e1", approver="e12", login_employee_id="e12", employees=emps)
    assert "already FINAL" in final[0] and "Nitin" in final[0] and "2026-10-08" in final[0]
    other = osp_finalize_blockers(existing={"status": "DRAFT"}, can_approve=True, disposition="ACCEPTED", validator="e1", approver="e1", login_employee_id="e12", employees=emps)
    assert any("must be your own login employee" in r for r in other)
    assert osp_finalize_blockers(existing={"status": "DRAFT"}, can_approve=True, disposition="ACCEPTED", validator="e1", approver="e12", login_employee_id="e12", employees=emps) == []
    pending = osp_finalize_blockers(existing={"status": "DRAFT"}, can_approve=False, disposition="PENDING", validator="", approver="", login_employee_id="e12", employees=emps)
    assert len(pending) >= 3


def test_osp_gate_checklist_shows_missing_receipt_metlab():
    rows = osp_gate_checklist({"sample_dimensional_disposition": "ACCEPTED", "sample_metlab_disposition": "ACCEPTED", "receipt_dimensional_disposition": "ACCEPTED", "receipt_metlab_disposition": None})
    status = {r["Gate Report"]: r["Status"] for r in rows}
    assert status["Receipt MetLAB"] == "Report not created"
    assert status["Receipt Dimensional"].startswith("Finalized")
    assert len(osp_gate_checklist({"metlab_required": False})) == 2


def test_free_ai_provider_resolution_and_openai_tool_loop():
    secrets = {"GEMINI_API_KEY": "AIzaTEST"}
    assert ai.resolve_provider(lambda k, d="": secrets.get(k, d)) == ("gemini", "AIzaTEST", "gemini-flash-latest")
    secrets = {"ANTHROPIC_API_KEY": "sk-ant-x", "GROQ_API_KEY": "gsk_x", "QCMS_AI_PROVIDER": "claude", "QCMS_AI_MODEL": "claude-sonnet-5-5"}
    assert ai.resolve_provider(lambda k, d="": secrets.get(k, d))[0] == "claude"
    secrets = {"GROQ_API_KEY": "gsk_x", "QCMS_AI_MODEL": "claude-sonnet-5-5"}
    assert ai.resolve_provider(lambda k, d="": secrets.get(k, d)) == ("groq", "gsk_x", "openai/gpt-oss-120b")

    replies = [
        {"choices": [{"message": {"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "describe_dataset", "arguments": "{\"dataset\": \"parts\"}"}}]}}]},
        {"choices": [{"message": {"content": "There are 2 parts."}}]},
    ]
    sent = []
    def post(payload):
        sent.append(payload); return replies[len(sent) - 1]
    assistant = ai.QCMSAIAssistant(_Repo([{"id": 1, "part_number": "X"}]), [{"table": "parts", "module_key": "PARTS", "columns": ("part_number",)}], lambda m: True, api_key="AIza", provider="gemini", post=post)
    answer = assistant.ask("how many parts")
    assert not answer.error and answer.text == "There are 2 parts."
    assert sent[0]["tools"][0]["type"] == "function" and sent[0]["messages"][0]["role"] == "system"
    assert sent[1]["messages"][-1]["role"] == "tool" and sent[1]["messages"][-1]["tool_call_id"] == "c1"


def test_ai_key_script_offers_free_engines():
    script = (ROOT / "scripts/set_ai_key.sh").read_text()
    for token in ("Google Gemini  - FREE", "Groq", "GEMINI_API_KEY", "QCMS_AI_PROVIDER", "chmod 600"):
        assert token in script


def test_android_app_1_1_0_camera_progress_offline():
    java = (ROOT / "mobile/android_first_app/app/src/main/java/com/fourstar/qcms/MainActivity.java").read_text()
    gradle = (ROOT / "mobile/android_first_app/app/build.gradle").read_text()
    assert "versionName '1.1.0'" in gradle and "versionCode 19" in gradle
    for token in ("MediaStore.ACTION_IMAGE_CAPTURE", "onProgressChanged", "onReceivedError", "Clear cache & reload", "QCMSClassicShell/1.0.2"):
        assert token in java
    assert "__qcmsNativeNavigate" not in java
