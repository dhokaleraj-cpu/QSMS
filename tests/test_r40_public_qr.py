"""R40 (agent W): public RMTC QR (no login) - token URL, customer-safe certificate stored on approval, RMTC QR Codes
page below the RMTC navigation, public Edge Function qcms-rmtc-certificate (index / f=zip / f=pdf / d=<id>)."""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUNCTION = ROOT / "supabase/functions/qcms-rmtc-certificate/index.ts"
PAGE = ROOT / "app_pages/rmtc_qr.py"
APP = ROOT / "streamlit_app.py"
TENANT = "11111111-1111-1111-1111-111111111111"
RID = "22222222-2222-2222-2222-222222222222"
URL_RE = r"https://xxrxopzxzyjnzumrwuwy\.supabase\.co/functions/v1/qcms-rmtc-certificate\?t=[A-Za-z0-9]{32}"


class _Repo:
    tenant_id = TENANT

    def __init__(self):
        self.tables = {
            "rmtc_approvals": [{"id": RID, "tenant_id": TENANT, "rmtc_number": "RMTC-40", "status": "APPROVED", "disposition": "ACCEPTED",
                                "heat_number": "H40", "material_grade_id": "g1", "supplier_id": "s1", "part_id": "p1",
                                "decision_at": "2026-10-29T06:00:00Z", "rmtc_copy_path": f"{TENANT}/rmtc/{RID}/legacy_copy.pdf"}],
            "rmtc_part_approvals": [{"id": "pa1", "rmtc_approval_id": RID, "part_id": "p1"}],
            "parts": [{"id": "p1", "part_number": "CUST-PN-1", "fsi_part_number": "FSI-1"}],
            "material_grades": [{"id": "g1", "grade_code": "20MnCr5"}],
            "parties": [{"id": "s1", "party_name": "Steel Supplier"}],
            "employees": [{"id": "e1", "status": "ACTIVE", "department": "Quality", "email": "q1@fsi.example", "first_name": "Q"}],
            "rmtc_qr_tokens": [], "qcms_whatsapp_settings": [],
            "document_attachments": [
                {"id": "a1", "tenant_id": TENANT, "entity_type": "RMTC", "entity_id": RID, "document_type": "RMTC_ATTACHMENT_2", "status": "ACTIVE",
                 "file_name": "report.pdf", "object_path": f"{TENANT}/rmtc/{RID}/a2", "mime_type": "application/pdf"},
                {"id": "a2", "tenant_id": TENANT, "entity_type": "RMTC", "entity_id": RID, "document_type": "RMTC_COPY", "status": "ACTIVE",
                 "file_name": "mill_tc.pdf", "object_path": f"{TENANT}/rmtc/{RID}/copy", "mime_type": "application/pdf"},
                {"id": "a3", "tenant_id": TENANT, "entity_type": "RMTC", "entity_id": RID, "document_type": "RMTC_ATTACHMENT_3", "status": "INACTIVE",
                 "file_name": "old.pdf", "object_path": f"{TENANT}/rmtc/{RID}/old"},
                {"id": "a4", "tenant_id": "other-tenant", "entity_type": "RMTC", "entity_id": RID, "document_type": "RMTC_ATTACHMENT_3", "status": "ACTIVE",
                 "file_name": "foreign.pdf", "object_path": f"other-tenant/rmtc/{RID}/x"},
            ],
        }
        self.updates = []

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
        row = {"id": f"{table}-{len(self.tables.setdefault(table, [])) + 1}", "revoked": False, **payload}
        self.tables[table].append(row)
        return dict(row)

    def update(self, table, record_id, payload):
        self.updates.append((table, record_id, dict(payload)))
        for row in self.tables.get(table, []):
            if str(row.get("id")) == str(record_id):
                row.update(payload)
                return dict(row)
        return {}


class _Client:
    def __init__(self):
        self.store: dict[str, tuple[bytes, str]] = {}
        outer = self

        class _Bucket:
            def upload(self, path, content, options):
                outer.store[path] = (bytes(content), options.get("content-type"))

            def download(self, path):
                return outer.store.get(path, (b"%PDF-1.4 dummy", ""))[0]

        class _Storage:
            def from_(self, bucket):
                assert bucket == "quality-documents"
                return _Bucket()
        self.storage = _Storage()


class _Notify:
    def __init__(self):
        self.calls = []

    def attachment_manifest(self, *a, **k):
        return []

    def enqueue(self, event_key, **kwargs):
        self.calls.append({"event": event_key, **kwargs})
        return {"id": "out1"}

    def dispatch(self, rows):
        pass


def _service(monkeypatch, repo, client, notify=None):
    from core import qr_codes, rmtc_qr
    import core.notification_service as ns

    captured = {}

    def fake_pdf(self, rid):
        captured["rid"] = rid
        return "RMTC_RMTC-40.pdf", b"%PDF-1.4 certificate"
    monkeypatch.setattr(qr_codes.RMTCQRService, "certificate_pdf", fake_pdf)
    monkeypatch.setattr(rmtc_qr, "app_base_url", lambda repo=None: "https://qcms.example.app")
    monkeypatch.setattr(ns, "NotificationService", lambda repo=None: notify or _Notify())
    return rmtc_qr.RMTCQRLabelService(repo, storage_client=lambda: client), captured


# ----------------------------------------------------------------------------- QR = public URL with a valid token
def test_qr_encodes_public_function_url_with_valid_token():
    from core import qr_codes as q, rmtc_qr as r

    assert r.QR_CONTENT == "TOKEN"
    token = q.new_token()
    assert q.valid_token(token) and not q.valid_token("RMTC-40") and not q.valid_token(token[:-1] + "-")
    url = q.certificate_url(token)
    assert re.fullmatch(URL_RE, url) and url.endswith(token)
    assert r.qr_target_url("https://app/rmtc-records?rmtc=1", url) == url
    assert r.is_public_url(url) and not r.is_public_url("https://app/rmtc-records?rmtc=1")
    assert r.scan_hint(url) == r.PUBLIC_SCAN_HINT and "no login" in r.PUBLIC_NOTICE
    matrix = r.qr_matrix(url)
    assert len(matrix) >= 25
    try:
        import cv2
        import numpy as np
        from PIL import Image
    except Exception:
        return
    image = np.array(Image.open(io.BytesIO(r.qr_png_bytes(url))).convert("L"))
    assert cv2.QRCodeDetector().detectAndDecode(image)[0] == url


# ----------------------------------------------------------------------------- approval flow
def test_approval_creates_token_stores_certificate_and_label(monkeypatch):
    repo, client, notify = _Repo(), _Client(), _Notify()
    service, captured = _service(monkeypatch, repo, client, notify)
    result = service.on_rmtc_approved(RID)
    assert result["ok"] and result["public"] and not result["warnings"], result
    tokens = repo.tables["rmtc_qr_tokens"]
    assert len(tokens) == 1 and re.fullmatch(r"[A-Za-z0-9]{32}", tokens[0]["token"]) and tokens[0]["rmtc_approval_id"] == RID
    assert re.fullmatch(URL_RE, result["url"]) and result["url"].endswith(tokens[0]["token"])
    cert_path = f"{TENANT}/rmtc_certificates/{RID}/RMTC_RMTC-40.pdf"
    assert result["certificate_path"] == cert_path and client.store[cert_path] == (b"%PDF-1.4 certificate", "application/pdf")
    assert tokens[0]["certificate_path"] == cert_path and tokens[0]["certificate_refreshed_at"]
    label = next(a for a in repo.tables["document_attachments"] if a["document_type"] == "RMTC_QR_LABEL")
    assert client.store[label["object_path"]][0][:8] == b"\x89PNG\r\n\x1a\n"
    body = notify.calls[0]["body_text"]
    assert result["url"] in body and "no login" in body
    # refresh keeps the same token; revoke issues a new one and marks the old revoked
    again = service.refresh_public(RID)
    assert again["url"] == result["url"] and len(repo.tables["rmtc_qr_tokens"]) == 1
    renewed = service.revoke_and_renew(RID)
    assert renewed["ok"] and renewed["revoked"] == 1 and renewed["url"] != result["url"]
    active = [t for t in repo.tables["rmtc_qr_tokens"] if not t.get("revoked")]
    assert len(active) == 1 and repo.tables["rmtc_qr_tokens"][0]["revoked"] is True and repo.tables["rmtc_qr_tokens"][0]["revoked_at"]
    assert active[0]["certificate_path"] == cert_path
    # QR assets (PNG / JPEG / PDF / label) all encode the current public URL
    assets = service.assets(repo.get("rmtc_approvals", RID))
    assert assets["url"] == renewed["url"] and assets["label_pdf"][:4] == b"%PDF"


def test_not_approved_creates_nothing_and_falls_back_without_session(monkeypatch):
    repo, client = _Repo(), _Client()
    repo.tables["rmtc_approvals"][0]["status"] = "APPROVAL_PENDING"
    service, _ = _service(monkeypatch, repo, client)
    assert service.on_rmtc_approved(RID)["ok"] is False and not repo.tables["rmtc_qr_tokens"]

    class NoInsert(_Repo):
        def insert(self, table, payload):
            if table == "rmtc_qr_tokens":
                raise RuntimeError("no session")
            return super().insert(table, payload)
    repo2 = NoInsert()
    service2, _ = _service(monkeypatch, repo2, _Client())
    result = service2.on_rmtc_approved(RID, send_email=False)
    assert result["ok"] and not result["public"] and result["url"].startswith("https://qcms.example.app/rmtc-records?rmtc=")


def test_bulk_create_skips_existing(monkeypatch):
    repo, client = _Repo(), _Client()
    service, _ = _service(monkeypatch, repo, client)
    seen = []
    first = service.bulk_create_missing(repo.select("rmtc_approvals"), progress=lambda i, n, no: seen.append((i, n, no)))
    assert first["created"] == 1 and first["skipped"] == 0 and seen == [(1, 1, "RMTC-40")]
    second = service.bulk_create_missing(repo.select("rmtc_approvals"))
    assert second["created"] == 0 and second["skipped"] == 1


def test_public_documents_order_tenant_and_bundles(monkeypatch):
    repo, client = _Repo(), _Client()
    service, _ = _service(monkeypatch, repo, client)
    service.on_rmtc_approved(RID, send_email=False)
    record = repo.get("rmtc_approvals", RID)
    docs = service.public_documents(record)
    assert [d["id"] for d in docs] == ["certificate", "a2", "a1", "copy"]  # certificate first, QR label / inactive / foreign excluded
    assert all(d["object_path"].startswith(f"{TENANT}/") for d in docs)
    data, skipped = service.documents_zip(record, docs)
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert names[0] == "RMTC_RMTC-40.pdf" and len(names) == len(set(n.casefold() for n in names)) == 4 and not skipped
    from core.rmtc_qr import unique_file_names, labels_pdf_bytes
    assert unique_file_names(["a.pdf", "A.pdf", "a.pdf"]) == ["a.pdf", "A (2).pdf", "a (3).pdf"]
    pdf, not_merged = service.documents_combined_pdf(record, docs)
    assert pdf[:4] == b"%PDF" and len(not_merged) == 4  # dummy bytes are not valid PDFs -> listed on the final page
    from pypdf import PdfReader
    labels = PdfReader(io.BytesIO(labels_pdf_bytes([("https://x", ["RMTC A"]), ("https://y", ["RMTC B"])])))
    assert len(labels.pages) == 2 and round(float(labels.pages[0].mediabox.width) / 72 * 25.4) == 100


def test_certificate_payload_is_customer_safe():
    from core.qr_codes import public_certificate_payload

    payload = {
        "record": {"rmtc_number": "RMTC-40", "customer_name": "Big OEM"},
        "parts": {"p1": {"part_number": "CUST-PN-1", "fsi_part_number": "FSI-1", "customer_id": "c1", "drawing_number": "D-9"},
                  "p2": {"part_number": "CUST-PN-2", "fsi_part_number": None}},
        "heat_usage": [{"part_number": "CUST-PN-1", "rmtc_number": "RMTC-40"}, {"part_number": "UNKNOWN"}],
        "customer": {"party_name": "Big OEM"},
        "qr_lines": ["RMTC RMTC-40", "Parts: CUST-PN-1, CUST-PN-2"], "qr_app_url": "https://app/rmtc-records?rmtc=RMTC-40",
    }
    clean = public_certificate_payload(payload)
    text = json.dumps(clean)
    for secret in ("CUST-PN-1", "CUST-PN-2", "Big OEM", "D-9", "rmtc-records"):
        assert secret not in text, secret
    assert clean["parts"]["p1"]["part_number"] == "FSI-1" and clean["parts"]["p2"]["part_number"] == "-"
    assert clean["heat_usage"][0]["part_number"] == "FSI-1" and clean["qr_lines"][1] == "Parts: FSI-1"
    src = (ROOT / "core/qr_codes.py").read_text(encoding="utf-8")
    assert "payload = public_certificate_payload(service.report_payload(rmtc_id))" in src


# ----------------------------------------------------------------------------- navigation
def test_page_route_registered_below_rmtc():
    app = APP.read_text(encoding="utf-8")
    items = app[app.index("PAGE_ITEMS = ("):app.index("PAGES = tuple")]
    assert '("rmtc-qr", st.Page(rmtc_qr_page.render, title="RMTC QR Codes"' in items
    assert items.index('("rmtc-approval",') < items.index('("rmtc-qr",')
    rmtc_menu = app[app.index('    "RMTC": ('):app.index('    "Inward": (')]
    assert '("rmtc-qr", "RMTC QR Codes"' in rmtc_menu and rmtc_menu.index('"rmtc-report"') < rmtc_menu.index('"rmtc-qr"')
    rail = app[app.index("RAIL_NAV = ("):]
    assert rail.index('PAGE_BY_PATH["rmtc-entry"]') < rail.index('PAGE_BY_PATH["rmtc-qr"]') < rail.index('PAGE_BY_PATH["inward-entry"]')
    for token in ('"rmtc-qr": "RMTC"', '"RMTC QR Codes": "rmtc-qr"', '"rmtc-qr":"RMTC_ENTRY"'):
        assert token in app, token
    verify = (ROOT / "scripts/verify_phase1.py").read_text(encoding="utf-8")
    assert '"rmtc-qr"' in verify and '"app_pages/rmtc_qr.py"' in verify
    page = PAGE.read_text(encoding="utf-8")
    assert "st.dataframe" not in page and "portal_table" in page and 'current_permissions("RMTC_ENTRY")' in page
    for token in ("Create public QR + certificate for all approved RMTCs without one", "Print labels for selected",
                  "Refresh public QR / certificate", "Revoke QR (new code)", "&f=zip", "&f=pdf", "public_documents"):
        assert token in page, token
    records = (ROOT / "app_pages/rmtc_pages.py").read_text(encoding="utf-8")
    assert "Refresh public QR / certificate" in records and "Revoke QR (new code)" in records and "PUBLIC_NOTICE" in records
    from core.rmtc_qr import PUBLIC_NOTICE
    assert PUBLIC_NOTICE == "Anyone with this QR can open and download all RMTC documents - no login."


# ----------------------------------------------------------------------------- public Edge Function
def test_edge_function_contract():
    fn = FUNCTION.read_text(encoding="utf-8")
    # default ?t= = combined PDF inline (index page 1 + all documents); f=pdf same as download; f=index index only
    assert 'return await pdfResponse(admin, ctx, token, "inline")' in fn and 'pdfResponse(admin, ctx, token, "attachment")' in fn
    assert "_All_Documents.pdf" in fn and 'format === "index"' in fn and "await drawIndexPage(out, ctx, token" in fn
    assert "if (overCap) return await out.save();" in fn  # above 50 MB: index page only with a note
    for token in ['url.searchParams.get("f")', 'url.searchParams.get("d")', 'format === "zip"', 'format === "pdf"', "zipSync",
                  "npm:pdf-lib@1.17.1", "npm:fflate@0.8.2", "copyPages", "embedJpg", "embedPng", "createSignedUrl",
                  "SIGNED_URL_SECONDS = 600", "status: 302", "MAX_BUNDLE_BYTES = 50 * 1024 * 1024", "uniqueNames",
                  "Download all (ZIP)", "Download all as one PDF", '"certificate"']:
        assert token in fn, token
    # revoked tokens -> "not active"; tenant of every file must match the token tenant
    assert "tok.revoked" in fn and "not active" in fn
    assert 'eq("tenant_id", tenant)' in fn and "path.startsWith(`${tenant}/`)" in fn and "String(a.tenant_id) === tenant" in fn
    assert '"RMTC_QR_LABEL"' in fn and '"SUPPLY_CUSTOMER_ORDER", "CUSTOMER_STANDARD"' in fn and 'eq("status", "ACTIVE")' in fn
    # customer-safe: FSI part numbers only, never part_number / customer columns
    code = "\n".join(line for line in fn.splitlines() if not line.strip().startswith("//"))
    selects = " ".join(re.findall(r"\.select\(\"([^\"]*)\"\)", code))
    assert "fsi_part_number" in selects and not re.search(r"(?<!fsi_)\bpart_number\b", selects) and "customer" not in selects
    assert "verify" not in json.loads((FUNCTION.parent / "deno.json").read_text())
    deploy = json.loads((ROOT / "supabase/auto_deploy_functions.json").read_text())
    assert {"slug": "qcms-rmtc-certificate", "verify_jwt": False} in deploy["functions"]
    assert "supabase/migrations/20261029120000_qcms_r40_public_qr.sql" in json.loads((ROOT / "supabase/auto_apply.json").read_text())["files"]
    sql = (ROOT / "supabase/migrations/20261029120000_qcms_r40_public_qr.sql").read_text()
    for word in ("delete", "update", "drop"):
        assert not re.search(rf"\b{word}\b", sql, re.I), word


def test_no_service_role_key_in_client_code():
    for rel in ("core/rmtc_qr.py", "core/qr_codes.py", "app_pages/rmtc_qr.py", "app_pages/rmtc_pages.py"):
        src = (ROOT / rel).read_text(encoding="utf-8").lower()
        assert "service_role" not in src and "service-role" not in src, rel
    assert "SUPABASE_SERVICE_ROLE_KEY" in FUNCTION.read_text(encoding="utf-8")  # only server-side, inside the function
