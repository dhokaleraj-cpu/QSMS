"""QCMS R38 · RMTC approval QR label (PNG attachment, print, Quality-department e-mail).

Builds on ``core.qr_codes`` (token table ``rmtc_qr_tokens`` + public Edge Function ``qcms-rmtc-certificate`` that
downloads the stored certificate PDF without a QCMS login; the Android / iOS apps show the same token QR).

* QR content (``QR_CONTENT``):
    "APP" (default, R38 final) - the login-protected app deep link ``<website>/rmtc-records?rmtc=<RMTC number>``.
                                 No secret / token is encoded; RMTC Records honours ``?rmtc=`` after login and offers
                                 the RMTC print PDF + the supplier test certificate attachment for download.
    "TOKEN"                    - legacy opt-in: the no-login certificate URL (Edge Function + rmtc_qr_tokens). Only when
                                 the user explicitly wants a public download; no new tokens are created in "APP" mode.
  RMTC no / heat / grade / parts / qty / supplier / approval date are printed as text so the label is useful offline.
* Label PDF: 100 x 60 mm sticker (QR + RMTC no + heat + grade + part numbers + qty + hand-written Location field).
* Website base URL: QSMS_APP_URL (when not localhost) -> WhatsApp settings ``app_link`` -> ``DEFAULT_APP_URL``.
* Label PNG = QR + caption (RMTC no, heat, grade, size / section, supplier, approval date, location when present).
  QR matrix: ``qrcode`` library when installed, else reportlab's built-in encoder (always available). PNG writer: Pillow
  (ships with Streamlit) for the caption, pure-zlib PNG otherwise.
* On approval: PNG stored as ``document_attachments`` (entity RMTC, document_type RMTC_QR_LABEL) and e-mailed to every
  ACTIVE employee of the Quality department (Quality / QA / QC / Quality Assurance / Quality Control ...) through
  ``NotificationService`` event ``RMTC_APPROVED_QR`` (subject starts with "Quality"). Never raises / never blocks approval.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from io import BytesIO
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote

from core import qr_codes

LOGGER = logging.getLogger(__name__)

DEFAULT_APP_URL = "https://vf6fa9hrhxquqxmfgyy4wf.streamlit.app"
RECORDS_ROUTE = "rmtc-records"
QUERY_PARAM = "rmtc"
EVENT_KEY = "RMTC_APPROVED_QR"
DOCUMENT_TYPE = "RMTC_QR_LABEL"
ENTITY_TYPE = "RMTC"
BUCKET = qr_codes.BUCKET
QR_CONTENT = "APP"  # "APP" (login required, no secret) | "TOKEN" (legacy public token URL, opt-in only)
LABEL_WIDTH_MM = 100.0
LABEL_HEIGHT_MM = 60.0

_QUALITY_KEYS = {"quality", "qa", "qc", "qad", "qcd", "qualityassurance", "qualitycontrol", "qualitydepartment",
                 "qaqc", "qcqa", "qualityqa", "qualityqc", "quality&assurance", "sqa", "supplierquality"}


# ----------------------------------------------------------------------------- URLs
def _clean_base(value: Any) -> str:
    text = str(value or "").strip().rstrip("/")
    if not text.lower().startswith(("http://", "https://")):
        return ""
    if re.search(r"//(localhost|127\.0\.0\.1|0\.0\.0\.0)(:|/|$)", text, re.I):
        return ""
    return text


def app_base_url(repo: Any = None) -> str:
    """Public QCMS website base URL used in QR / e-mail links."""
    try:
        from core.config import get_settings
        base = _clean_base(get_settings().qsms_url)
        if base:
            return base
    except Exception:
        pass
    try:
        if repo is None:
            from core.repository import Repository
            repo = Repository()
        rows = repo.select("qcms_whatsapp_settings", limit=1)
        base = _clean_base((rows[0] if rows else {}).get("app_link"))
        if base:
            return base
    except Exception:
        pass
    return DEFAULT_APP_URL


def rmtc_app_url(rmtc_number: Any, base: str | None = None) -> str:
    """``<base>/rmtc-records?rmtc=<RMTC number>`` (opens that RMTC with its certificate download after login)."""
    root = (_clean_base(base) or DEFAULT_APP_URL) if base is not None else app_base_url()
    return f"{root}/{RECORDS_ROUTE}?{QUERY_PARAM}={quote(str(rmtc_number or '').strip(), safe='')}"


def qr_target_url(app_url: str, token_url: str = "") -> str:
    if QR_CONTENT.upper() == "APP" or not str(token_url or "").strip():
        return app_url
    return token_url


def requested_rmtc(query_params: Any) -> str:
    """RMTC number from ``?rmtc=`` (st.query_params or a dict)."""
    try:
        value = query_params.get(QUERY_PARAM)
    except Exception:
        return ""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "").strip()[:80]


SESSION_KEY = "_qcms_qr_rmtc"


def remember_qr_request(query_params: Any, session_state: Any) -> str:
    """Stash ``?rmtc=`` in the session before the login screen so the RMTC still opens after login."""
    number = requested_rmtc(query_params)
    if number:
        try:
            session_state[SESSION_KEY] = number
        except Exception:
            pass
    return number


def pending_qr_request(query_params: Any, session_state: Any) -> str:
    """``?rmtc=`` from the URL, else the value stashed before login (consumed once)."""
    number = requested_rmtc(query_params)
    try:
        stashed = str(session_state.pop(SESSION_KEY, "") or "")
    except Exception:
        stashed = ""
    return number or stashed


# ----------------------------------------------------------------------------- QR / PNG
def qr_matrix(text: str) -> list[list[bool]]:
    """Module matrix (True = dark): ``qrcode`` when installed, else reportlab's encoder."""
    try:
        import qrcode  # type: ignore
        code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=0)
        code.add_data(str(text)); code.make(fit=True)
        return [[bool(v) for v in row] for row in code.get_matrix()]
    except Exception:
        return qr_codes.qr_matrix(str(text))


def qr_png_bytes(text: str, *, scale: int = 10, border: int = 4) -> bytes:
    return qr_codes.png_from_matrix(qr_matrix(text), scale=scale, border=border)


def _font(size: int):
    from PIL import ImageFont
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "Arial Bold.ttf", "Arial.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def label_png_bytes(text: str, lines: Sequence[str], *, scale: int = 10) -> bytes:
    """QR with the caption lines underneath (Pillow). Falls back to the plain QR PNG."""
    plain = qr_png_bytes(text, scale=scale)
    try:
        from PIL import Image, ImageDraw
        qr_img = Image.open(BytesIO(plain)).convert("L")
        bold, regular = _font(24), _font(21)
        line_h = 31
        width = max(qr_img.width, 560)
        canvas = Image.new("L", (width, qr_img.height + line_h * len(lines) + 20), 255)
        canvas.paste(qr_img, ((width - qr_img.width) // 2, 0))
        draw = ImageDraw.Draw(canvas)
        y = qr_img.height
        for index, line in enumerate(lines):
            font = bold if index == 0 else regular
            value = str(line)[:64]
            try:
                w = draw.textlength(value, font=font)
            except Exception:
                w = len(value) * 11
            draw.text((max((width - w) / 2, 4), y), value, fill=0, font=font)
            y += line_h
        draw.rectangle([1, 1, width - 2, canvas.height - 2], outline=0, width=2)
        out = BytesIO(); canvas.save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return plain


# ----------------------------------------------------------------------------- caption / recipients
def _date_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%d-%m-%Y")
    except Exception:
        return text[:10]


def label_lines(record: Mapping[str, Any], *, grade: str = "", supplier: str = "", section: str = "", location: str = "",
                parts: Sequence[str] = ()) -> list[str]:
    heat = str(record.get("heat_number") or "-")
    if record.get("heat_code"):
        heat += f" ({record.get('heat_code')})"
    section = section or str(record.get("rm_section") or "")
    location = location or str(record.get("storage_location") or record.get("material_location") or record.get("location") or "")
    lines = [
        f"RMTC {record.get('rmtc_number') or '-'}",
        f"Heat: {heat}",
        f"Grade: {grade or '-'}",
        f"Size / Section: {section or '-'}",
        f"Parts: {', '.join(p for p in parts if p) or '-'}",
        f"Qty: {qty_text(record)}",
        f"Supplier: {supplier or '-'}",
        f"Approved: {_date_text(record.get('decision_at') or record.get('approved_at'))}",
    ]
    if location.strip():
        lines.append(f"Location: {location.strip()}")
    return lines


def qty_text(record: Mapping[str, Any]) -> str:
    value = record.get("certificate_quantity")
    if value in (None, ""):
        return "-"
    try:
        return f"{float(value):,.2f}".rstrip("0").rstrip(".") + " kg"
    except (TypeError, ValueError):
        return str(value)


def label_pdf_bytes(text: str, lines: Sequence[str], *, width_mm: float = LABEL_WIDTH_MM, height_mm: float = LABEL_HEIGHT_MM) -> bytes:
    """100 x 60 mm sticker PDF: QR left, RMTC text right, blank "Location" write-in box at the bottom."""
    from reportlab.graphics import renderPDF
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas

    buffer = BytesIO()
    page_w, page_h = width_mm * mm, height_mm * mm
    pdf = rl_canvas.Canvas(buffer, pagesize=(page_w, page_h))
    pdf.setTitle("RMTC material location label")
    pad = 3 * mm
    loc_h = 9 * mm
    qr_size = min(page_h - 2 * pad - loc_h - 1.5 * mm, page_w * 0.45)
    renderPDF.draw(qr_codes.qr_drawing(text, qr_size), pdf, pad, page_h - pad - qr_size)
    pdf.setLineWidth(0.7); pdf.rect(1 * mm, 1 * mm, page_w - 2 * mm, page_h - 2 * mm)
    x = pad + qr_size + 2 * mm
    avail = page_w - x - pad
    y = page_h - pad - 3.4 * mm
    body = [line for line in lines if not str(line).startswith("Location:")]
    for index, line in enumerate(body):
        font, size = ("Helvetica-Bold", 9.5) if index == 0 else ("Helvetica", 7.2)
        pdf.setFont(font, size)
        value = str(line)
        while value and pdf.stringWidth(value, font, size) > avail:
            value = value[:-1]
        pdf.drawString(x, y, value)
        y -= size + 2.4
    location = next((str(line).split(":", 1)[1].strip() for line in lines if str(line).startswith("Location:")), "")
    pdf.setLineWidth(0.5); pdf.rect(pad, pad, page_w - 2 * pad, loc_h)
    pdf.setFont("Helvetica-Bold", 8); pdf.drawString(pad + 1.5 * mm, pad + loc_h - 3.6 * mm, "Location:")
    if location:
        pdf.setFont("Helvetica", 8); pdf.drawString(pad + 17 * mm, pad + loc_h - 3.6 * mm, location[:60])
    pdf.setFont("Helvetica-Oblique", 5.4)
    pdf.drawString(pad + 1.5 * mm, pad + 1.4 * mm, "Scan with a phone: QCMS login opens this RMTC and its certificate downloads.")
    pdf.showPage(); pdf.save()
    return buffer.getvalue()


# ----------------------------------------------------------------------------- R39 · QR download formats (PNG / JPEG / PDF)
A6_WIDTH_MM = 105.0
A6_HEIGHT_MM = 148.0
QR_DOWNLOAD_FORMATS = ("PNG", "JPEG", "PDF")


def qr_jpeg_bytes(text: str, lines: Sequence[str] = (), *, scale: int = 10, quality: int = 95) -> bytes:
    """QR (+ caption lines when given) as a JPEG (white background, RGB). Uses Pillow (ships with Streamlit)."""
    from PIL import Image
    png = label_png_bytes(text, lines, scale=scale) if lines else qr_png_bytes(text, scale=scale)
    image = Image.open(BytesIO(png))
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        image = background
    else:
        image = image.convert("RGB")
    out = BytesIO()
    image.save(out, format="JPEG", quality=quality, subsampling=0, optimize=True)
    return out.getvalue()


def qr_pdf_bytes(text: str, lines: Sequence[str] = (), *, width_mm: float = A6_WIDTH_MM, height_mm: float = A6_HEIGHT_MM,
                 title: str = "RMTC QR code") -> bytes:
    """One A6 page (portrait): large QR centred at the top, caption text underneath (vector QR, prints sharp)."""
    from reportlab.graphics import renderPDF
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas

    buffer = BytesIO()
    page_w, page_h = width_mm * mm, height_mm * mm
    pdf = rl_canvas.Canvas(buffer, pagesize=(page_w, page_h))
    pdf.setTitle(title)
    pad = 6 * mm
    qr_size = min(page_w - 2 * pad, page_h * 0.55)
    renderPDF.draw(qr_codes.qr_drawing(text, qr_size), pdf, (page_w - qr_size) / 2, page_h - pad - qr_size)
    pdf.setLineWidth(0.7); pdf.rect(2 * mm, 2 * mm, page_w - 4 * mm, page_h - 4 * mm)
    y = page_h - pad - qr_size - 6 * mm
    avail = page_w - 2 * pad
    for index, line in enumerate(lines):
        font, size = ("Helvetica-Bold", 12) if index == 0 else ("Helvetica", 9)
        pdf.setFont(font, size)
        value = str(line)
        while value and pdf.stringWidth(value, font, size) > avail:
            value = value[:-1]
        pdf.drawCentredString(page_w / 2, y, value)
        y -= size + 4
        if y < pad + 6 * mm:
            break
    pdf.setFont("Helvetica-Oblique", 6.5)
    pdf.drawCentredString(page_w / 2, pad, "Scan with a phone: QCMS login opens this record.")
    pdf.showPage(); pdf.save()
    return buffer.getvalue()


def qr_download_files(text: str, lines: Sequence[str], file_stem: str) -> list[dict[str, Any]]:
    """Download buttons for the QR: PNG (QR + caption), JPEG (QR + caption), PDF (A6 page). Never raises; a format that
    cannot be rendered is skipped."""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", str(file_stem or "QR")).strip("_") or "QR"
    builders = (
        ("PNG", f"{stem}_QR.png", "image/png", lambda: label_png_bytes(text, lines)),
        ("JPEG", f"{stem}_QR.jpg", "image/jpeg", lambda: qr_jpeg_bytes(text, lines)),
        ("PDF", f"{stem}_QR.pdf", "application/pdf", lambda: qr_pdf_bytes(text, lines)),
    )
    out: list[dict[str, Any]] = []
    for fmt, name, mime, build in builders:
        try:
            out.append({"format": fmt, "file_name": name, "mime": mime, "data": build()})
        except Exception:
            LOGGER.warning("QR %s download could not be rendered", fmt, exc_info=True)
    return out


def qr_png(text: str, lines: Sequence[str] = ()) -> bytes:
    """R39: QR (+ caption lines) as PNG."""
    return label_png_bytes(text, lines) if lines else qr_png_bytes(text)


def qr_jpeg(text: str, lines: Sequence[str] = ()) -> bytes:
    """R39: QR (+ caption lines) as JPEG."""
    return qr_jpeg_bytes(text, lines)


def qr_pdf(text: str, lines: Sequence[str] = (), *, title: str = "RMTC QR code") -> bytes:
    """R39: QR + caption on one A6 PDF page."""
    return qr_pdf_bytes(text, lines, title=title)


def is_quality_department(value: Any) -> bool:
    raw = str(value or "").casefold()
    key = re.sub(r"[^a-z0-9&]+", "", raw)
    if key in _QUALITY_KEYS or "quality" in key:
        return True
    tokens = set(re.split(r"[^a-z0-9]+", raw))
    return bool(tokens & {"qa", "qc"})


def quality_recipients(repo: Any) -> list[dict]:
    rows = repo.select("employees", eq={"status": "ACTIVE"}, order_by="first_name", limit=5000)
    seen: set[str] = set(); result: list[dict] = []
    for row in rows:
        email = str(row.get("email") or "").strip()
        if str(row.get("status") or "ACTIVE").upper() != "ACTIVE" or not email or "@" not in email:
            continue
        if not is_quality_department(row.get("department")) or email.casefold() in seen:
            continue
        seen.add(email.casefold())
        name = " ".join(v for v in (str(row.get("first_name") or "").strip(), str(row.get("last_name") or "").strip()) if v)
        result.append({"email": email, "name": name})
    return result


# ----------------------------------------------------------------------------- service
class RMTCQRLabelService:
    def __init__(self, repo: Any = None, *, storage_client: Callable[[], Any] | None = None) -> None:
        if repo is None:
            from core.repository import Repository
            repo = Repository()
        self.repo = repo
        self._storage_client = storage_client
        self.tokens = qr_codes.RMTCQRService(repo, storage_client=storage_client)

    # ------------------------------------------------------------ data
    def _names(self, record: Mapping[str, Any]) -> tuple[str, str]:
        grade = supplier = ""
        try:
            row = self.repo.get("material_grades", str(record.get("material_grade_id") or "")) or {}
            grade = str(row.get("grade_code") or row.get("grade_name") or "")
        except Exception:
            pass
        try:
            party = self.repo.get("parties", str(record.get("supplier_id") or "")) or {}
            supplier = str(party.get("party_name") or "")
        except Exception:
            pass
        return grade, supplier

    def part_numbers(self, record: Mapping[str, Any]) -> list[str]:
        ids: list[str] = []
        if record.get("part_id"):
            ids.append(str(record.get("part_id")))
        try:
            for row in self.repo.select("rmtc_part_approvals", eq={"rmtc_approval_id": str(record.get("id"))}, order_by="created_at", limit=100) or []:
                if row.get("part_id") and str(row.get("part_id")) not in ids:
                    ids.append(str(row.get("part_id")))
        except Exception:
            pass
        numbers: list[str] = []
        for pid in ids:
            try:
                number = str((self.repo.get("parts", pid) or {}).get("part_number") or "").strip()
            except Exception:
                number = ""
            if number and number not in numbers:
                numbers.append(number)
        return numbers

    def lines(self, record: Mapping[str, Any]) -> list[str]:
        grade, supplier = self._names(record)
        return label_lines(record, grade=grade, supplier=supplier, parts=self.part_numbers(record))

    def urls(self, record: Mapping[str, Any]) -> dict[str, str]:
        app_url = rmtc_app_url(record.get("rmtc_number"), app_base_url(self.repo))
        token_url = ""
        if QR_CONTENT.upper() == "TOKEN":
            try:
                token_url = self.tokens.url_for(str(record.get("id") or ""))
            except Exception:
                token_url = ""
        return {"app_url": app_url, "token_url": token_url, "qr_url": qr_target_url(app_url, token_url)}

    def assets(self, record: Mapping[str, Any]) -> dict[str, Any]:
        urls = self.urls(record)
        lines = self.lines(record)
        target = urls["qr_url"]
        return {
            **urls, "url": target, "lines": lines,
            "png": label_png_bytes(target, lines),
            "qr_png": qr_png_bytes(target),
            "label_pdf": label_pdf_bytes(target, lines),
            "file_stem": f"RMTC_{qr_codes.safe_file_token(record.get('rmtc_number'))}",
        }

    # ------------------------------------------------------------ attachment
    def _client(self):
        if self._storage_client is not None:
            return self._storage_client()
        from core.database import get_session_client
        return get_session_client()

    def stored_label(self, rmtc_id: str) -> dict | None:
        try:
            rows = self.repo.select("document_attachments", eq={"entity_type": ENTITY_TYPE, "entity_id": str(rmtc_id), "document_type": DOCUMENT_TYPE, "status": "ACTIVE"}, order_by="created_at", desc=True, limit=1)
        except Exception:
            return None
        return dict(rows[0]) if rows else None

    def store_label(self, record: Mapping[str, Any], png: bytes, file_stem: str) -> dict:
        client = self._client()
        if client is None:
            raise RuntimeError("Live Supabase session is required to store the RMTC QR label.")
        rid = str(record.get("id"))
        file_name = f"{file_stem}_QR_Label.png"
        path = f"{getattr(self.repo, 'tenant_id', '') or 'tenant'}/rmtc/{rid}/{file_name}"
        client.storage.from_(BUCKET).upload(path, bytes(png), {"content-type": "image/png", "upsert": "true"})
        payload = {"entity_type": ENTITY_TYPE, "entity_id": rid, "document_type": DOCUMENT_TYPE, "file_name": file_name,
                   "object_path": path, "mime_type": "image/png", "size_bytes": len(png),
                   "checksum": hashlib.sha256(bytes(png)).hexdigest(), "status": "ACTIVE",
                   "document_title": f"QR label · RMTC {record.get('rmtc_number') or ''}".strip()}
        existing = None
        try:
            existing = self.repo.find_one("document_attachments", eq={"entity_type": ENTITY_TYPE, "entity_id": rid, "document_type": DOCUMENT_TYPE})
        except Exception:
            existing = None
        if existing:
            row = self.repo.update("document_attachments", str(existing["id"]), payload)
        else:
            row = self.repo.insert("document_attachments", payload)
        return dict(row or payload)

    # ------------------------------------------------------------ e-mail
    def email_quality(self, record: Mapping[str, Any], assets: Mapping[str, Any], attachment: Mapping[str, Any], *, notification_service: Any = None) -> tuple[dict | None, int]:
        recipients = quality_recipients(self.repo)
        if not recipients:
            return None, 0
        if notification_service is None:
            from core.notification_service import NotificationService
            notification_service = NotificationService(self.repo)
        png_entry = {"bucket": BUCKET, "object_path": attachment.get("object_path"), "file_name": attachment.get("file_name"),
                     "mime_type": "image/png", "generated": False}
        original = notification_service.attachment_manifest

        def manifest(*args: Any, **kwargs: Any) -> list[dict]:
            rows: list[dict] = []
            try:
                rows = [dict(r) for r in (original(*args, **kwargs) or [])]  # the RMTC record PDF (generated)
            except Exception as exc:
                LOGGER.warning("RMTC QR e-mail: RMTC PDF not attached: %s", exc)
            return [png_entry, *[r for r in rows if r.get("object_path") != png_entry["object_path"]]]

        notification_service.attachment_manifest = manifest
        lines = list(assets.get("lines") or [])
        number = record.get("rmtc_number") or "-"
        body = (
            f"RMTC {number} has been approved ({str(record.get('disposition') or '').replace('_', ' ').title()}).\n\n"
            + "\n".join(lines[1:])
            + "\n\nAttached: the QR label (PNG) and the RMTC record PDF. Print the QR label and stick it at the location where this material is stored."
            + f"\nScan the QR (QCMS login required) to open / download the approved RMTC certificate: {assets.get('url')}"
            + (f"\nQCMS (after login): {assets.get('app_url')}" if assets.get("app_url") and assets.get("app_url") != assets.get("url") else "")
            + "\n"
        )
        row = notification_service.enqueue(
            EVENT_KEY,
            subject=f"Quality · RMTC {number} approved · QR label for material location",
            body_text=body,
            related_table="rmtc_approvals", related_id=str(record.get("id")),
            context={"rmtc_id": str(record.get("id")), "rmtc_number": number, "department": "Quality", "next_task": "Stick QR label at material location"},
            recipient_email=recipients[0]["email"], recipient_name=recipients[0]["name"],
            cc_emails=[r["email"] for r in recipients[1:]],
            include_generated_pdf=True, include_record_attachments=False, include_supplier=False,
            automatic=True,
        )
        if row:
            try:
                notification_service.dispatch([row])
            except Exception as exc:
                LOGGER.warning("RMTC QR e-mail dispatch failed: %s", exc)
        return row, (len(recipients) if row else 0)

    # ------------------------------------------------------------ approval hook
    def on_rmtc_approved(self, rmtc_id: str, *, send_email: bool = True) -> dict[str, Any]:
        """Token + certificate snapshot (core.qr_codes), QR label PNG attachment, Quality e-mail. Never raises."""
        result: dict[str, Any] = {"ok": False, "warnings": [], "url": "", "app_url": "", "emailed": 0, "attachment": None}
        try:
            record = self.repo.get("rmtc_approvals", str(rmtc_id)) or {}
            if not qr_codes.is_rmtc_approved(record):
                result["warnings"].append("RMTC is not approved; QR not generated.")
                return result
            if QR_CONTENT.upper() == "TOKEN":  # legacy public-token mode only; "APP" encodes no secret
                snapshot = self.tokens.on_rmtc_approved(str(rmtc_id), send_email=False)
                result["warnings"].extend(w for w in snapshot.get("warnings") or [] if "not approved" not in w)
            assets = self.assets(record)
            result.update({"ok": True, "url": assets["url"], "app_url": assets["app_url"]})
            attachment: dict | None = None
            try:
                attachment = self.store_label(record, assets["png"], assets["file_stem"])
                result["attachment"] = attachment
            except Exception as exc:
                result["warnings"].append(f"QR label PNG could not be stored: {exc}")
            if send_email:
                if not attachment:
                    result["warnings"].append("QR e-mail not sent because the QR label PNG is not stored.")
                else:
                    try:
                        row, count = self.email_quality(record, assets, attachment)
                        result["emailed"] = count
                        if not row:
                            result["warnings"].append("No active Quality department employee with an e-mail address; QR e-mail not queued.")
                    except Exception as exc:
                        result["warnings"].append(f"QR e-mail could not be queued: {exc}")
        except Exception as exc:
            LOGGER.warning("RMTC QR label failed for %s: %s", rmtc_id, exc)
            result["warnings"].append(f"QR could not be generated: {exc}")
        return result


def print_qr(record: Mapping[str, Any], repo: Any) -> tuple[str, list[str], str]:
    """(qr_url, caption lines, app_url) for the RMTC print PDF - empty when the RMTC is not approved."""
    if not qr_codes.is_rmtc_approved(record):
        return "", [], ""
    service = RMTCQRLabelService(repo)
    urls = service.urls(record)
    return urls["qr_url"], service.lines(record), urls["app_url"]


__all__ = [
    "DEFAULT_APP_URL", "EVENT_KEY", "DOCUMENT_TYPE", "QR_CONTENT", "app_base_url", "rmtc_app_url", "qr_target_url",
    "requested_rmtc", "remember_qr_request", "pending_qr_request", "qr_matrix", "qr_png_bytes", "label_png_bytes", "label_pdf_bytes", "label_lines", "qty_text", "is_quality_department",
    "quality_recipients", "RMTCQRLabelService", "print_qr",
    "QR_DOWNLOAD_FORMATS", "qr_jpeg_bytes", "qr_pdf_bytes", "qr_download_files", "qr_png", "qr_jpeg", "qr_pdf",
]
