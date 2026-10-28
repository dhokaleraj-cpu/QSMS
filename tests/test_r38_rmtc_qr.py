"""R38 (agent A): RMTC approval QR (token, public certificate function, Quality e-mail) + horizontal
chemistry / Jominy grids with the Jominy mm row."""
from __future__ import annotations

import io
import json
import re
import struct
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261028100000_qcms_r38_rmtc_qr_chem.sql"
FUNCTION = ROOT / "supabase/functions/qcms-rmtc-certificate/index.ts"


# ----------------------------------------------------------------------------- QR generation
def _png_pixels(png: bytes) -> tuple[int, int, list[bytes]]:
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, width, height = 8, b"", 0, 0
    while pos < len(png):
        length = struct.unpack(">I", png[pos:pos + 4])[0]
        kind = png[pos + 4:pos + 8]
        data = png[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, colour = struct.unpack(">IIBB", data[:10])
            assert (depth, colour) == (8, 0)
        elif kind == b"IDAT":
            idat += data
        pos += 12 + length
    raw = zlib.decompress(idat)
    rows = [raw[i * (width + 1) + 1:(i + 1) * (width + 1)] for i in range(height)]
    return width, height, rows


def test_qr_png_encodes_the_certificate_url_matrix():
    from core import qr_codes as q

    token = q.new_token()
    assert q.valid_token(token) and len(token) == 32 and token.isalnum()
    url = q.certificate_url(token)
    assert re.fullmatch(r"https://[a-z0-9]+\.supabase\.co/functions/v1/qcms-rmtc-certificate\?t=[A-Za-z0-9]{32}", url)
    matrix = q.qr_matrix(url)
    n = len(matrix)
    assert n >= 21 and (n - 17) % 4 == 0  # a valid QR version size
    # three finder patterns (7x7 dark ring + centre)
    for r0, c0 in ((0, 0), (0, n - 7), (n - 7, 0)):
        assert all(matrix[r0][c0 + i] and matrix[r0 + 6][c0 + i] for i in range(7))
        assert all(matrix[r0 + 2 + i][c0 + 2 + j] for i in range(3) for j in range(3))
    png = q.png_from_matrix(matrix, scale=4, border=4)
    width, height, rows = _png_pixels(png)
    assert width == height == (n + 8) * 4
    # every module of the PNG matches the matrix
    for r in range(n):
        for c in range(n):
            pixel = rows[(r + 4) * 4 + 1][(c + 4) * 4 + 1]
            assert (pixel == 0) == matrix[r][c]
    # decode back when a decoder exists on this machine
    try:
        from pyzbar.pyzbar import decode  # type: ignore
        from PIL import Image
    except Exception:
        decode = None
    if decode is not None:
        assert decode(Image.open(io.BytesIO(png)))[0].data.decode() == url


def test_label_pdf_and_label_png():
    from core import qr_codes as q

    lines = q.label_lines({"rmtc_number": "RMTC-1", "heat_number": "H123", "heat_code": "SM-0001", "decision_at": "2026-10-28T08:00:00+00:00"},
                          grade="20MnCr5", supplier="ABC Steels")
    assert lines == ["RMTC RMTC-1", "Heat: H123 (SM-0001)", "Grade: 20MnCr5", "Supplier: ABC Steels", "Approved: 28-10-2026"]
    pdf = q.label_pdf_bytes(q.certificate_url("A" * 32), lines)
    assert pdf.startswith(b"%PDF")
    from pypdf import PdfReader
    page = PdfReader(io.BytesIO(pdf)).pages[0]
    width_mm = float(page.mediabox.width) / 72 * 25.4
    height_mm = float(page.mediabox.height) / 72 * 25.4
    assert round(width_mm) == 70 and round(height_mm) == 50
    text = page.extract_text()
    assert "RMTC RMTC-1" in text and "20MnCr5" in text
    assert q.qr_label_png_bytes(q.certificate_url("A" * 32), lines)[:8] == b"\x89PNG\r\n\x1a\n"


# ----------------------------------------------------------------------------- DB + public function
def test_token_table_migration_and_public_function():
    sql = MIGRATION.read_text()
    for token in ("create table if not exists public.rmtc_qr_tokens", "tenant_id uuid not null default public.current_tenant_id()",
                  "enable row level security", "revoke all on public.rmtc_qr_tokens from anon", "uq_rmtc_qr_tokens_active",
                  "'^[A-Za-z0-9]{32}$'", "certificate_path"):
        assert token in sql
    for word in ("delete", "update", "drop"):
        assert not re.search(rf"\b{word}\b", sql, re.I), word  # MCP-safe additive migration
    assert "supabase/migrations/20261028100000_qcms_r38_rmtc_qr_chem.sql" in json.loads((ROOT / "supabase/auto_apply.json").read_text())["files"]
    fn = FUNCTION.read_text()
    for token in ("rmtc_qr_tokens", "SUPABASE_SERVICE_ROLE_KEY", "createSignedUrl", "SIGNED_URL_SECONDS = 600", "status: 302", "revoked", "[A-Za-z0-9]{32}"):
        assert token in fn
    assert (FUNCTION.parent / "deno.json").exists()


# ----------------------------------------------------------------------------- approval hook
class _FakeRepo:
    tenant_id = "11111111-1111-1111-1111-111111111111"

    def __init__(self):
        self.tables = {
            "rmtc_approvals": [{"id": "22222222-2222-2222-2222-222222222222", "rmtc_number": "RMTC-77", "status": "APPROVED", "disposition": "ACCEPTED",
                                "heat_number": "H77", "material_grade_id": "g1", "supplier_id": "s1", "decision_at": "2026-10-28T06:00:00Z"}],
            "material_grades": [{"id": "g1", "grade_code": "20MnCr5"}],
            "parties": [{"id": "s1", "party_name": "Steel Supplier"}],
            "employees": [
                {"id": "e1", "status": "ACTIVE", "department": "Quality", "email": "q1@fsi.example", "first_name": "Q", "last_name": "One"},
                {"id": "e2", "status": "ACTIVE", "department": "QUALITY ASSURANCE", "email": "q2@fsi.example", "first_name": "Q", "last_name": "Two"},
                {"id": "e3", "status": "ACTIVE", "department": "Production", "email": "p@fsi.example"},
                {"id": "e4", "status": "ACTIVE", "department": "quality", "email": ""},
                {"id": "e5", "status": "INACTIVE", "department": "Quality", "email": "old@fsi.example"},
            ],
            "rmtc_qr_tokens": [],
        }
        self.updates = []

    def select(self, table, *, eq=None, **kwargs):
        rows = [dict(r) for r in self.tables.get(table, [])]
        for key, value in (eq or {}).items():
            rows = [r for r in rows if r.get(key) == value]
        return rows

    def get(self, table, record_id):
        return next((dict(r) for r in self.tables.get(table, []) if str(r.get("id")) == str(record_id)), None)

    def insert(self, table, payload):
        row = {"id": f"id{len(self.tables.setdefault(table, [])) + 1}", "revoked": False, **payload}
        self.tables[table].append(row)
        return dict(row)

    def update(self, table, record_id, payload):
        self.updates.append((table, record_id, dict(payload)))
        for row in self.tables.get(table, []):
            if str(row.get("id")) == str(record_id):
                row.update(payload)
        return {}


class _Bucket:
    def __init__(self, store):
        self.store = store

    def upload(self, path, content, options):
        self.store[path] = (bytes(content), options.get("content-type"))


class _Storage:
    def __init__(self):
        self.store = {}

    def from_(self, bucket):
        assert bucket == "quality-documents"
        return _Bucket(self.store)


class _Client:
    def __init__(self):
        self.storage = _Storage()


class _FakeNotify:
    def __init__(self):
        self.calls = []
        self.dispatched = []

    def enqueue(self, event_key, **kwargs):
        manifest = self.attachment_manifest(kwargs.get("related_table"), kwargs.get("related_id"), include_generated_pdf=False, include_record_attachments=False)
        self.calls.append({"event": event_key, "manifest": manifest, **kwargs})
        return {"id": "out1"}

    def dispatch(self, rows):
        self.dispatched.append(rows)
        return {"processed": len(rows)}


def test_approval_hook_creates_token_certificate_and_emails_quality(monkeypatch):
    from core import qr_codes as q

    repo, client, notify = _FakeRepo(), _Client(), _FakeNotify()
    service = q.RMTCQRService(repo, storage_client=lambda: client)
    monkeypatch.setattr(q.RMTCQRService, "certificate_pdf", lambda self, rid: ("RMTC_RMTC-77.pdf", b"%PDF-1.4 certificate"))
    import core.notification_service as ns
    monkeypatch.setattr(ns, "NotificationService", lambda repo=None: notify)
    rid = "22222222-2222-2222-2222-222222222222"
    result = service.on_rmtc_approved(rid)
    assert result["ok"] and result["created"] and not result["warnings"], result
    token = repo.tables["rmtc_qr_tokens"][0]
    assert q.valid_token(token["token"]) and result["url"].endswith("?t=" + token["token"])
    folder = f"{repo.tenant_id}/rmtc_certificates/{rid}"
    assert client.storage.store[f"{folder}/RMTC_RMTC-77.pdf"][1] == "application/pdf"
    assert token["certificate_path"] == f"{folder}/RMTC_RMTC-77.pdf"
    png_path = f"{folder}/RMTC_RMTC-77_QR.png"
    assert client.storage.store[png_path][0][:8] == b"\x89PNG\r\n\x1a\n"
    call = notify.calls[0]
    assert call["subject"] == "Quality · RMTC RMTC-77 approved · QR for material location"
    recipients = [call["recipient_email"], *call["cc_emails"]]
    assert recipients == ["q1@fsi.example", "q2@fsi.example"]  # ACTIVE, department contains 'quality', has e-mail
    assert [m["file_name"] for m in call["manifest"]] == ["RMTC_RMTC-77_QR.png", "RMTC_RMTC-77_QR_Label.pdf"]
    assert all(m["generated"] is False for m in call["manifest"])
    assert notify.dispatched and result["emailed"] == 2
    # a second approval run re-uses the token (stable QR)
    again = service.on_rmtc_approved(rid, send_email=False)
    assert not again["created"] and len(repo.tables["rmtc_qr_tokens"]) == 1 and again["url"] == result["url"]


def test_approval_hook_never_raises(monkeypatch):
    from core import qr_codes as q

    repo = _FakeRepo()
    service = q.RMTCQRService(repo, storage_client=lambda: None)  # no live session: uploads fail
    result = service.on_rmtc_approved("22222222-2222-2222-2222-222222222222")
    assert result["ok"] and result["warnings"]  # certificate / e-mail warnings, but no exception
    repo.tables["rmtc_approvals"][0]["status"] = "APPROVAL_PENDING"
    assert q.RMTCQRService(repo).on_rmtc_approved("22222222-2222-2222-2222-222222222222")["ok"] is False

    class Broken(_FakeRepo):
        def get(self, *a, **k):
            raise RuntimeError("db down")
    assert q.RMTCQRService(Broken()).on_rmtc_approved("x")["warnings"]


def test_rmtc_pages_call_qr_hook_after_approval_and_show_panel():
    page = (ROOT / "app_pages/rmtc_pages.py").read_text()
    decide = page.index("repo.rpc('qsms_decide_rmtc'")
    hook = page.index("_run_qr_hook(repo,rid,send_email=True)", decide)
    assert hook - decide < 600
    assert "is_rmtc_approved(svc.get(rid) or {})" in page
    for token in ("Download QR PNG", "Print Label PDF (100 x 60 mm)", "Refresh QR Label", "Re-send QR to Quality",
                  "Generate QR & e-mail Quality department", "_render_rmtc_qr_panel(repo,record", "_render_rmtc_qr_panel(svc.repo,selected_row"):
        assert token in page
    assert page.count("_run_qr_hook(svc.repo,rid,send_email=False)") == 2  # added-part decisions refresh the certificate
    service = (ROOT / "core/rmtc_service.py").read_text()
    assert "'qr_url': qr_url" in service and "print_qr(record, self.repo)" in service


# ----------------------------------------------------------------------------- horizontal grids
def test_jominy_mm_conversion():
    from core.analysis_grids import jominy_inch_to_mm, jominy_mm, sixteenth_from

    assert jominy_mm(1) == 1.59 and jominy_mm(2) == 3.18 and jominy_mm(5) == 7.94 and jominy_mm(6) == 9.53 and jominy_mm(16) == 25.4
    assert jominy_inch_to_mm('J5/16"') == 7.94 and jominy_inch_to_mm('5/16"') == 7.94 and jominy_inch_to_mm(5) == 7.94
    assert sixteenth_from(None, label="J 9/16") == 9 and sixteenth_from(None, mm=7.94) == 5


def test_chemistry_and_jominy_tables_are_horizontal():
    from core.analysis_grids import chemistry_table, jominy_table

    chem = [{"element": "Ni", "minimum_value": 0, "maximum_value": 0.4, "actual_value": 0.1},
            {"element": "C", "minimum_value": 0.17, "maximum_value": 0.22, "actual_value": 0.19},
            {"element": "Mn%", "minimum_value": 1.1, "maximum_value": 1.4, "actual_value": 1.2},
            {"element": "Al/N2 Ratio", "actual_value": 2.1}, {"element": "B", "actual_value": 0.002}]
    table = chemistry_table(chem, [("Min", "minimum_value"), ("Max", "maximum_value"), ("Actual", "actual_value")])
    assert table[0] == ["Element", "C%", "Mn%", "Ni%", "B%", "Al/N2 Ratio"]
    assert [row[0] for row in table[1:]] == ["Min", "Max", "Actual"]
    assert table[3][1:3] == [0.19, 1.2]
    jom = [{"distance_label": '5/16"', "distance_16th": 5, "minimum_hrc": 30, "maximum_hrc": 45, "actual_hrc": 40},
           {"distance_label": '1/16"', "distance_16th": 1, "minimum_hrc": 40, "maximum_hrc": 50, "actual_hrc": 47}]
    jt = jominy_table(jom, [("Min HRC", "minimum_hrc"), ("Max HRC", "maximum_hrc"), ("Actual HRC", "actual_hrc")])
    assert jt[0] == ["Distance (inch)", 'J1/16"', 'J5/16"']
    assert jt[1] == ["Distance (mm)", "1.59", "7.94"]
    assert jt[4] == ["Actual HRC", 47, 40]


def _rmtc_sample_pdf_text() -> str:
    from pypdf import PdfReader
    from core import print_samples, reporting
    from core.qr_codes import certificate_url

    payload = print_samples.rmtc_sample()
    payload["qr_url"] = certificate_url("B" * 32)
    payload["qr_lines"] = ["RMTC SAMPLE", "Heat: H1"]
    payload["record"] = {**dict(payload.get("record") or {}), "status": "APPROVED", "disposition": "ACCEPTED"}  # QR prints only when approved
    pdf = reporting.rmtc_record_pdf_bytes.__wrapped_uncached__(payload)
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


def test_rmtc_pdf_grids_horizontal_and_qr_printed():
    text = _rmtc_sample_pdf_text()
    words = [w.strip() for w in text.split("\n") if w.strip()]
    chem = words.index("Chemical Composition")
    assert words[chem + 1:chem + 4] == ["Element", "C%", "Mn%"]  # elements across, not down
    assert words.index("Minimum", chem) > words.index("Mn%", chem)
    jom = words.index("Jominy Results")
    assert words[jom + 1:jom + 3] == ["Distance (inch)", 'J1/16"']
    mm_row = words.index("Distance (mm)", jom)
    assert words[mm_row + 1:mm_row + 3] == ["1.59", "3.18"]
    assert "7.94" in words[mm_row:mm_row + 12]
    assert "MATERIAL LOCATION QR · scan to open / download this approved RMTC certificate" in " ".join(text.split())
    assert "qcms-rmtc-certificate?t=" in text.replace("\n", "")


def test_pages_and_prints_use_horizontal_grids():
    rmtc = (ROOT / "app_pages/rmtc_pages.py").read_text()
    assert "chem_part_h_" in rmtc and "jom_part_h_" in rmtc and "ordered_elements(svc.chemistry_template(grade_id))" in rmtc
    assert "'Element':t.get('element'),'Minimum %'" not in rmtc  # the vertical worksheet grid is gone
    grade = (ROOT / "app_pages/material_grade.py").read_text()
    assert "_horizontal_composition(composition)" in grade and 'key=f"chem_h_{grade_id}_{columns_token}"' in grade
    assert '{"Element": r.get("element"), "Minimum %"' not in grade
    part = (ROOT / "app_pages/part_master.py").read_text()
    assert "_horizontal_jominy_print(jominy_rows)" in part and 'key=f"jom_h_{part_id}"' in part
    metlab = (ROOT / "app_pages/metlab_report.py").read_text()
    assert "_jominy_horizontal_frame(list(snapshot[key]))" in metlab
    reporting = (ROOT / "core/reporting.py").read_text()
    assert '["Element", "Minimum", "Maximum", "Actual", "Unit", "Status"]' not in reporting
    assert '["Distance", "mm", "Min HRC", "Max HRC", "RMTC HRC"' not in reporting
    android = next((ROOT / "mobile").rglob("RptReports.java")).read_text()
    assert "jominyHorizontal(pjom" in android and "chemHorizontal(pchem" in android and "1.5875" in android and "/rmtc-records?rmtc=" in android and "rmtc_qr_tokens" not in android
    ios = next((ROOT / "mobile").rglob("RptReports.swift")).read_text()
    assert "jominyHorizontal(pjom" in ios and "chemHorizontal(pchem" in ios and "CIQRCodeGenerator" in ios


def test_excel_and_generic_print_horizontal():
    from openpyxl import load_workbook
    from core.reporting import quality_record_excel_bytes
    from core.record_print import _analysis_frame

    payload = {"record": {"report_number": "ML-1"}, "results": {
        "chemistry_rows": [{"element": "Mn", "minimum_value": 1.1, "actual_value": 1.2}, {"element": "C", "minimum_value": 0.17, "actual_value": 0.2}],
        "jominy_rows": [{"distance_label": '2/16"', "distance_16th": 2, "minimum_hrc": 40, "actual_value": 44}]}}
    book = load_workbook(io.BytesIO(quality_record_excel_bytes(payload, "METLAB")))
    chem = [[c.value for c in row] for row in book["Chemistry"].iter_rows()]
    assert chem[0][:3] == ["Element", "C%", "Mn%"] and chem[1][0] == "Spec. Min"
    jom = [[c.value for c in row] for row in book["Jominy"].iter_rows()]
    assert jom[0] == ["Distance (inch)", 'J2/16"'] and jom[1] == ["Distance (mm)", "3.18"]

    class _Resolver:
        def label(self, *a):
            return "P-1"
    frame = _analysis_frame("part_jominy_requirements", [
        {"distance_label": '5/16"', "minimum_hrc": 30, "maximum_hrc": 40, "status": "ACTIVE"},
        {"distance_label": '6/16"', "minimum_hrc": 28, "maximum_hrc": 38, "status": "INACTIVE"}], _Resolver())
    assert list(frame.columns) == ["Distance (inch)", 'J5/16"'] and frame.iloc[0].tolist() == ["Distance (mm)", "7.94"]
    grade = _analysis_frame("material_grade_elements", [{"element": "Si", "minimum": 0.1}, {"element": "C", "minimum": 0.2}], _Resolver())
    assert list(grade.columns) == ["Element", "C%", "Si%"]
