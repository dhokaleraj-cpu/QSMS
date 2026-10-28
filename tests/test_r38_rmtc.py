"""R38 (agent A): RMTC approval QR (login-protected app deep link - no secret in the QR - PNG attachment, 100 x 60 mm
label, RMTC print, Quality e-mail), horizontal chemistry / Jominy grids (core/chem_grid.py) and Sections Applicable."""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261028100000_qcms_r38_rmtc_qr_chem.sql"
RID = "22222222-2222-2222-2222-222222222222"


# ----------------------------------------------------------------------------- payload / URL
def test_app_url_and_query_param(monkeypatch):
    from core import rmtc_qr as r

    assert r.rmtc_app_url("RMTC-D9-0001", base="https://qcms.example.app/") == "https://qcms.example.app/rmtc-records?rmtc=RMTC-D9-0001"
    assert r.rmtc_app_url("A/B 1", base="http://localhost:8510") == f"{r.DEFAULT_APP_URL}/rmtc-records?rmtc=A%2FB%201"
    assert r.requested_rmtc({"rmtc": " RMTC-1 "}) == "RMTC-1" and r.requested_rmtc({}) == ""

    class _Settings:
        qsms_url = "http://localhost:8510"

    import core.config as config
    monkeypatch.setattr(config, "get_settings", lambda: _Settings())

    class _Repo:
        def select(self, table, **kwargs):
            assert table == "qcms_whatsapp_settings"
            return [{"app_link": "https://fsi-qcms.streamlit.app/"}]
    assert r.app_base_url(_Repo()) == "https://fsi-qcms.streamlit.app"

    class _Empty:
        def select(self, *a, **k):
            return []
    assert r.app_base_url(_Empty()) == r.DEFAULT_APP_URL
    # default "APP": the QR always carries the login-protected app link, never a token (no secret in the QR)
    assert r.QR_CONTENT == "APP"
    assert r.qr_target_url("https://a/rmtc-records?rmtc=1", "") == "https://a/rmtc-records?rmtc=1"
    assert r.qr_target_url("https://a/x", "https://p.supabase.co/functions/v1/qcms-rmtc-certificate?t=" + "A" * 32) == "https://a/x"
    monkeypatch.setattr(r, "QR_CONTENT", "TOKEN")  # legacy opt-in only
    assert r.qr_target_url("https://a/x", "https://token") == "https://token"
    # the deep link survives the login screen (stashed in the session, consumed once)
    state = {}
    assert r.remember_qr_request({"rmtc": "RMTC-9"}, state) == "RMTC-9" and state[r.SESSION_KEY] == "RMTC-9"
    assert r.pending_qr_request({}, state) == "RMTC-9" and r.pending_qr_request({}, state) == ""


def test_label_png_decodes_back_to_the_url():
    from core import rmtc_qr as r

    url = r.rmtc_app_url("RMTC-D9-0042", base="https://qcms.example.app")
    lines = r.label_lines({"rmtc_number": "RMTC-D9-0042", "heat_number": "H42", "heat_code": "SM-01", "rm_section": "65 RCS",
                           "decision_at": "2026-10-28T06:00:00Z", "storage_location": "Rack B-3", "certificate_quantity": 12500},
                          grade="20MnCr5", supplier="ABC Steels", parts=["P-100", "P-200"])
    assert lines == ["RMTC RMTC-D9-0042", "Heat: H42 (SM-01)", "Grade: 20MnCr5", "Size / Section: 65 RCS", "Parts: P-100, P-200",
                     "Qty: 12,500 kg", "Supplier: ABC Steels", "Approved: 28-10-2026", "Location: Rack B-3"]
    png = r.label_png_bytes(url, lines)
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 2000
    plain = r.qr_png_bytes(url)
    assert plain[:8] == b"\x89PNG\r\n\x1a\n"
    try:
        import cv2
        import numpy as np
        from PIL import Image
    except Exception:
        return  # no decoder here: header + size checked above
    for data in (png, plain):
        image = np.array(Image.open(io.BytesIO(data)).convert("L"))
        assert cv2.QRCodeDetector().detectAndDecode(image)[0] == url


def test_quality_department_normalisation():
    from core.rmtc_qr import is_quality_department

    for value in ("Quality", "QUALITY", "QA", "QC", "Q.A.", "Quality Assurance", "Quality Control", "QA / QC", "Supplier Quality"):
        assert is_quality_department(value), value
    for value in ("Production", "MetLAB", "Supply Chain", "", None, "Accounts"):
        assert not is_quality_department(value), value


# ----------------------------------------------------------------------------- approval hook
class _FakeRepo:
    tenant_id = "11111111-1111-1111-1111-111111111111"

    def __init__(self):
        self.tables = {
            "rmtc_approvals": [{"id": RID, "rmtc_number": "RMTC-77", "status": "APPROVED", "disposition": "ACCEPTED", "heat_number": "H77",
                                "material_grade_id": "g1", "supplier_id": "s1", "rm_section": "60 RCS", "decision_at": "2026-10-28T06:00:00Z",
                                "part_id": "p1", "certificate_quantity": 5000}],
            "rmtc_part_approvals": [{"id": "pa1", "rmtc_approval_id": RID, "part_id": "p1"}, {"id": "pa2", "rmtc_approval_id": RID, "part_id": "p2"}],
            "parts": [{"id": "p1", "part_number": "FSI-100"}, {"id": "p2", "part_number": "FSI-200"}],
            "material_grades": [{"id": "g1", "grade_code": "20MnCr5"}],
            "parties": [{"id": "s1", "party_name": "Steel Supplier"}],
            "employees": [
                {"id": "e1", "status": "ACTIVE", "department": "Quality", "email": "q1@fsi.example", "first_name": "Q", "last_name": "One"},
                {"id": "e2", "status": "ACTIVE", "department": "QA", "email": "q2@fsi.example"},
                {"id": "e3", "status": "ACTIVE", "department": "Quality Control", "email": "Q1@fsi.example"},  # duplicate address
                {"id": "e4", "status": "ACTIVE", "department": "Production", "email": "p@fsi.example"},
                {"id": "e5", "status": "INACTIVE", "department": "Quality", "email": "old@fsi.example"},
                {"id": "e6", "status": "ACTIVE", "department": "QC", "email": ""},
            ],
            "rmtc_qr_tokens": [], "document_attachments": [], "qcms_whatsapp_settings": [],
        }

    def select(self, table, *, eq=None, **kwargs):
        rows = [dict(r) for r in self.tables.get(table, [])]
        for key, value in (eq or {}).items():
            rows = [r for r in rows if r.get(key) == value]
        return rows

    def find_one(self, table, *, eq=None, **kwargs):
        rows = self.select(table, eq=eq)
        return rows[0] if rows else None

    def get(self, table, record_id):
        return next((dict(r) for r in self.tables.get(table, []) if str(r.get("id")) == str(record_id)), None)

    def insert(self, table, payload):
        row = {"id": f"id{len(self.tables.setdefault(table, [])) + 1}", "revoked": False, **payload}
        self.tables[table].append(row)
        return dict(row)

    def update(self, table, record_id, payload):
        for row in self.tables.get(table, []):
            if str(row.get("id")) == str(record_id):
                row.update(payload)
                return dict(row)
        return {}


class _Client:
    def __init__(self):
        self.store = {}
        outer = self

        class _Bucket:
            def upload(self, path, content, options):
                outer.store[path] = (bytes(content), options.get("content-type"))

        class _Storage:
            def from_(self, bucket):
                assert bucket == "quality-documents"
                return _Bucket()
        self.storage = _Storage()


class _FakeNotify:
    def __init__(self):
        self.calls, self.dispatched = [], []

    def attachment_manifest(self, related_table, related_id, *, include_generated_pdf, include_record_attachments):
        return [{"bucket": "quality-documents", "object_path": "t/notification_reports/RMTC.pdf", "file_name": "RMTC-77.pdf",
                 "mime_type": "application/pdf", "generated": True}] if include_generated_pdf else []

    def enqueue(self, event_key, **kwargs):
        manifest = self.attachment_manifest(kwargs.get("related_table"), kwargs.get("related_id"),
                                            include_generated_pdf=kwargs.get("include_generated_pdf"), include_record_attachments=False)
        self.calls.append({"event": event_key, "manifest": manifest, **kwargs})
        return {"id": "out1"}

    def dispatch(self, rows):
        self.dispatched.append(rows)


def test_approval_stores_png_attachment_and_emails_quality(monkeypatch):
    from core import qr_codes, rmtc_qr

    repo, client, notify = _FakeRepo(), _Client(), _FakeNotify()
    monkeypatch.setattr(qr_codes.RMTCQRService, "certificate_pdf", lambda self, rid: ("RMTC_RMTC-77.pdf", b"%PDF-1.4"))
    monkeypatch.setattr(rmtc_qr, "app_base_url", lambda repo=None: "https://qcms.example.app")
    import core.notification_service as ns
    monkeypatch.setattr(ns, "NotificationService", lambda repo=None: notify)
    result = rmtc_qr.RMTCQRLabelService(repo, storage_client=lambda: client).on_rmtc_approved(RID)
    assert result["ok"] and not result["warnings"], result
    assert result["app_url"] == "https://qcms.example.app/rmtc-records?rmtc=RMTC-77"
    assert result["url"] == result["app_url"] and not repo.tables["rmtc_qr_tokens"]  # no token / secret is created
    attachment = repo.tables["document_attachments"][0]
    assert (attachment["entity_type"], attachment["entity_id"], attachment["document_type"]) == ("RMTC", RID, "RMTC_QR_LABEL")
    assert attachment["file_name"] == "RMTC_RMTC-77_QR_Label.png" and attachment["mime_type"] == "image/png"
    assert client.store[attachment["object_path"]][0][:8] == b"\x89PNG\r\n\x1a\n"
    call = notify.calls[0]
    assert call["event"] == "RMTC_APPROVED_QR"
    assert call["subject"].startswith("Quality ·") and "QCMS" not in call["subject"].split("·")[0]
    assert [call["recipient_email"], *call["cc_emails"]] == ["q1@fsi.example", "q2@fsi.example"]
    assert call["manifest"][0]["object_path"] == attachment["object_path"] and call["manifest"][0]["mime_type"] == "image/png"
    assert any(m["file_name"] == "RMTC-77.pdf" for m in call["manifest"])  # the RMTC record PDF rides along
    assert "Size / Section: 60 RCS" in call["body_text"] and result["app_url"] in call["body_text"]
    assert "Parts: FSI-100, FSI-200" in call["body_text"] and "Qty: 5,000 kg" in call["body_text"]
    assert call["include_supplier"] is False and call["automatic"] is True
    assert notify.dispatched and result["emailed"] == 2
    # refresh keeps ONE label attachment row
    rmtc_qr.RMTCQRLabelService(repo, storage_client=lambda: client).on_rmtc_approved(RID, send_email=False)
    assert len(repo.tables["document_attachments"]) == 1 and len(notify.calls) == 1


def test_approval_hook_never_raises(monkeypatch):
    from core import rmtc_qr

    repo = _FakeRepo()
    import core.notification_service as ns

    def boom(repo=None):
        raise RuntimeError("smtp down")
    monkeypatch.setattr(ns, "NotificationService", boom)
    result = rmtc_qr.RMTCQRLabelService(repo, storage_client=lambda: None).on_rmtc_approved(RID)
    assert result["ok"] and result["warnings"]  # storage / mail warnings only
    repo.tables["rmtc_approvals"][0]["disposition"] = "REJECTED"
    assert rmtc_qr.RMTCQRLabelService(repo).on_rmtc_approved(RID)["ok"] is False
    assert rmtc_qr.print_qr(repo.tables["rmtc_approvals"][0], repo) == ("", [], "")


# ----------------------------------------------------------------------------- PDF
def _pdf_text(payload) -> str:
    from pypdf import PdfReader
    from core import reporting

    render = getattr(reporting.rmtc_record_pdf_bytes, "__wrapped_uncached__", reporting.rmtc_record_pdf_bytes)
    pdf = render(payload)
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


def _sample(status: str, disposition: str, sections=None):
    from core import print_samples

    payload = print_samples.rmtc_sample()
    payload["record"] = {**dict(payload.get("record") or {}), "status": status, "disposition": disposition}
    payload["qr_url"] = "https://qcms.example.app/rmtc-records?rmtc=RMTC-SAMPLE"
    payload["qr_lines"] = ["RMTC RMTC-SAMPLE", "Heat: H1"]
    if sections is not None:
        payload["applicable_sections"] = sections
    return payload


def test_pdf_has_qr_only_when_approved():
    approved = _pdf_text(_sample("APPROVED", "ACCEPTED"))
    assert "MATERIAL LOCATION QR" in approved and "rmtc-records?rmtc=RMTC-SAMPLE" in approved.replace("\n", "")
    for status, disposition in (("DRAFT", "PENDING"), ("REJECTED", "REJECTED"), ("APPROVAL_PENDING", "ON_HOLD")):
        assert "MATERIAL LOCATION QR" not in _pdf_text(_sample(status, disposition)), status


def test_pdf_omits_not_applicable_sections():
    full = _pdf_text(_sample("DRAFT", "PENDING"))
    full_lines = {line.strip() for line in full.splitlines()}
    for title in ("Jominy Results", "DI / Hardenability", "RMTC MICROSTRUCTURE PHOTOGRAPHS", "SUPPLIER RMTC MECHANICAL PROPERTIES"):
        assert title in full_lines, title
    assert "Sections Not Applicable" not in full
    text = _pdf_text(_sample("DRAFT", "PENDING", {"jominy": False, "di_value": False, "microstructure": False, "supplier_mechanical": False}))
    lines = {line.strip() for line in text.splitlines()}  # section bars are lines of their own; the N/A note lists labels
    for title in ("Jominy Results", "DI / Hardenability", "RMTC MICROSTRUCTURE PHOTOGRAPHS", "SUPPLIER RMTC MECHANICAL PROPERTIES"):
        assert title not in lines, title
    flat = " ".join(text.split())
    assert "Chemical Composition" in flat and "Sections Not Applicable" in flat


# ----------------------------------------------------------------------------- applicability model
def test_rmtc_sections_default_from_parts_and_stored_choice():
    from core.section_applicability import (RMTC_SECTION_KEYS, default_rmtc_sections, na_chemistry_rows, na_jominy_rows,
                                            na_requirement_rows, normalize_rmtc_sections, rmtc_not_applicable_labels,
                                            rmtc_sections, split_requirement_templates)

    assert normalize_rmtc_sections(None) == {k: True for k in RMTC_SECTION_KEYS}
    assert normalize_rmtc_sections("not json") == {k: True for k in RMTC_SECTION_KEYS}
    parts = [{"section_applicability": {"jominy": False, "chemistry": False}}, {"section_applicability": {"jominy": "no"}}]
    defaults = default_rmtc_sections(parts)
    assert defaults["jominy"] is False and defaults["chemistry"] is True and defaults["mechanical"] is True
    assert rmtc_sections({"applicable_sections": None}, parts) == defaults
    assert rmtc_sections({"applicable_sections": {}}, parts) == defaults
    assert rmtc_sections({"applicable_sections": json.dumps({"jominy": True, "heat_treatment": False})}, parts)["jominy"] is True
    assert rmtc_not_applicable_labels({"heat_treatment": False}) == ["Heat Treatment & Other Requirements"]
    shown, hidden = split_requirement_templates(
        [{"id": "r1", "parameter_name": "Tensile Strength"}, {"id": "r2", "parameter_name": "Hardness"}], {"mechanical": False})
    assert [t["id"] for t in shown] == ["r2"] and [t["id"] for t in hidden] == ["r1"]
    assert na_requirement_rows(hidden)[0]["result"] == "NOT_APPLICABLE"
    assert na_chemistry_rows([{"id": "e1", "element": "C", "minimum": 0.1}])[0]["result"] == "NOT_APPLICABLE"
    assert na_jominy_rows([{"jominy_distance_id": "j1", "distance_16th": 5}])[0]["applicability"] == "NOT_APPLICABLE"


def test_pages_and_service_wiring():
    page = (ROOT / "app_pages/rmtc_pages.py").read_text()
    for token in ("pending_qr_request(st.query_params,st.session_state)", "_render_rmtc_sections(svc,header,part_rows,parts", "_rmtc_stage(rmtc_app,'chemistry'",
                  "_rmtc_stage(rmtc_app,'jominy'", "_rmtc_stage(rmtc_app,'di_value'", "split_requirement_templates(templates,rmtc_app)",
                  "RMTCQRLabelService(repo).on_rmtc_approved", "Download QR PNG", "Print Label PDF (100 x 60 mm)",
                  "if qr_match==selected:_render_qr_certificate_downloads(svc.repo,selected_row)", "Download Supplier Test Certificate"):
        assert token in page, token
    assert "st.dataframe" not in page
    service = (ROOT / "core/rmtc_service.py").read_text()
    assert "'applicable_sections': applicable_sections" in service and "def save_applicable_sections" in service
    assert "qrcode[pil]" in (ROOT / "requirements.txt").read_text()
    app = (ROOT / "streamlit_app.py").read_text()
    assert app.index("_remember_qr_request(st.query_params, st.session_state)") < app.index("render_login(); st.stop()")


def test_migration_is_additive_and_listed():
    sql = MIGRATION.read_text()
    for token in ("alter table public.rmtc_approvals add column if not exists applicable_sections jsonb",
                  "add column if not exists section_applicability", "create index if not exists"):
        assert token in sql
    code = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    for word in ("delete", "update", "drop", "truncate"):
        assert not re.search(rf"\b{word}\b", code, re.I), word
    assert "supabase/migrations/20261028100000_qcms_r38_rmtc_qr_chem.sql" in json.loads((ROOT / "supabase/auto_apply.json").read_text())["files"]


# ----------------------------------------------------------------------------- R38 final additions
def test_label_pdf_is_100_by_60_mm_with_qr_and_fields():
    from pypdf import PdfReader
    from core import rmtc_qr as r

    url = r.rmtc_app_url("RMTC-55", base="https://qcms.example.app")
    lines = r.label_lines({"rmtc_number": "RMTC-55", "heat_number": "H55", "certificate_quantity": 900}, grade="EN353",
                          supplier="ABC", parts=["P-1"])
    pdf = r.label_pdf_bytes(url, lines)
    page = PdfReader(io.BytesIO(pdf)).pages[0]
    width_mm, height_mm = float(page.mediabox.width) / 72 * 25.4, float(page.mediabox.height) / 72 * 25.4
    assert round(width_mm) == 100 and round(height_mm) == 60
    text = " ".join(page.extract_text().split())
    for token in ("RMTC RMTC-55", "Heat: H55", "Grade: EN353", "Parts: P-1", "Qty: 900 kg", "Location:"):
        assert token in text, token
    content = page.get_contents().get_data().decode("latin-1")
    assert content.count(" re") > 100  # the vector QR modules


def test_rmtc_pdf_contains_qr_drawing_and_text():
    from pypdf import PdfReader
    from core import print_samples, reporting

    payload = _sample("APPROVED", "ACCEPTED")
    render = getattr(reporting.rmtc_record_pdf_bytes, "__wrapped_uncached__", reporting.rmtc_record_pdf_bytes)
    reader = PdfReader(io.BytesIO(render(payload)))
    text = " ".join(" ".join(p.extract_text() for p in reader.pages).split())
    assert "MATERIAL LOCATION QR" in text and "QCMS login required" in text and "RMTC RMTC-SAMPLE" in text
    def rects(pdf_reader) -> int:
        return sum(p.get_contents().get_data().decode("latin-1").count(" re") for p in pdf_reader.pages)
    draft = PdfReader(io.BytesIO(render(_sample("DRAFT", "PENDING"))))
    assert rects(reader) - rects(draft) > 100  # QR modules drawn only on the approved certificate


def test_print_qr_uses_app_link_without_token():
    from core import rmtc_qr

    repo = _FakeRepo()
    url, lines, app_url = rmtc_qr.print_qr(repo.tables["rmtc_approvals"][0], repo)
    assert url == app_url and url.endswith("/rmtc-records?rmtc=RMTC-77") and "?t=" not in url
    assert "Parts: FSI-100, FSI-200" in lines and not repo.tables["rmtc_qr_tokens"]


@pytest.mark.parametrize("value, mm", [('J5/16"', 7.94), ("J 5/16", 7.94), ('5/16"', 7.94), ("J5", 7.94), ("J1", 1.59),
                                       ("J20", 31.75), (20, 31.75), ("7.9 mm", 7.9)])
def test_jominy_distance_mm(value, mm):
    from core.chem_grid import jominy_distance_mm

    assert jominy_distance_mm(value) == mm


def test_horizontal_chemistry_pivot_round_trip():
    from core.chem_grid import ROW_TITLE, from_horizontal, ordered_elements, to_horizontal

    rows = ordered_elements([{"id": "2", "element": "Mn", "minimum_value": 0.6, "maximum_value": 0.9, "actual_value": None},
                             {"id": "1", "element": "C", "minimum_value": 0.17, "maximum_value": 0.23, "actual_value": 0.2}])
    fields = [("Min", "minimum_value"), ("Max", "maximum_value"), ("Actual", "actual_value")]
    frame = to_horizontal(rows, fields)
    assert list(frame.columns) == [ROW_TITLE, "C", "Mn"] and list(frame[ROW_TITLE]) == ["Min", "Max", "Actual"]
    frame.loc[frame[ROW_TITLE] == "Actual", "Mn"] = 0.75
    back = from_horizontal(frame, rows, fields)
    assert [r["id"] for r in back] == ["1", "2"] and back[1]["actual_value"] == 0.75 and back[0] == rows[0]


def test_part_text_array_applicability_hides_sections():
    from core.section_applicability import default_rmtc_sections, rmtc_sections, section_key

    assert section_key("Chemical Composition") == "chemistry" and section_key("Jominy Results") == "jominy"
    parts = [{"applicable_sections": ["chemistry", "Mechanical Properties"]}]
    values = rmtc_sections({"applicable_sections": None}, parts)
    assert values["chemistry"] and not values["jominy"] and not values["microstructure"] and values["heat_balance"]
    assert default_rmtc_sections([{"applicable_sections": "{chemistry,jominy}"}])["jominy"] is True
    assert default_rmtc_sections([{"applicable_sections": []}])["jominy"] is True  # empty list = not chosen = all


def test_reportlab_grid_and_approval_view_wiring():
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate
    from pypdf import PdfReader
    from core.chem_grid import jominy_table, reportlab_grid

    rows = [{"distance_16th": n, "minimum_hrc": 30, "maximum_hrc": 45} for n in range(1, 21)]
    flow = reportlab_grid(jominy_table(rows, [("Min HRC", "minimum_hrc"), ("Max HRC", "maximum_hrc")]), 180 * 2.8346)
    assert len(flow) == 4  # 20 distances -> 2 bands of <= 14 columns (+ spacers)
    buf = BytesIO(); SimpleDocTemplate(buf, pagesize=A4).build(flow)
    text = " ".join(PdfReader(BytesIO(buf.getvalue())).pages[0].extract_text().split())
    assert "Distance (mm)" in text and "31.75" in text and 'J5/16"' in text and "7.94" in text
    page = (ROOT / "app_pages/rmtc_pages.py").read_text()
    assert "_render_approval_grids(record,details,parts)" in page and "CHEMISTRY & JOMINY REVIEW" in page
