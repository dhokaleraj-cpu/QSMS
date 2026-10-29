"""R38 · QR codes for approved RMTC certificates (material-location label).

The QR encodes a stable public URL (R40 default; anyone with the QR opens all RMTC documents, no login)::

    https://<project>.supabase.co/functions/v1/qcms-rmtc-certificate?t=<32-char token>

The public Edge Function ``qcms-rmtc-certificate`` resolves the token (table ``rmtc_qr_tokens``) with the
service role and serves the document index / ZIP / combined PDF / 10-minute signed download URLs of the stored
customer-safe certificate PDF (``quality-documents/{tenant}/rmtc_certificates/{rmtc_id}/RMTC_<number>.pdf``) and every
RMTC attachment.

No extra dependency: the QR matrix comes from reportlab's built-in encoder (reportlab is already required)
and the PNG is written with zlib (pure Python). Pillow, when installed (it ships with Streamlit), is only
used to add the text caption to the label PNG.
"""
from __future__ import annotations

import logging
import re
import secrets
import string
import struct
import zlib
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Callable, Mapping, Sequence

LOGGER = logging.getLogger(__name__)

FUNCTION_SLUG = "qcms-rmtc-certificate"
DEFAULT_PROJECT_REF = "xxrxopzxzyjnzumrwuwy"
TOKEN_LENGTH = 32
TOKEN_ALPHABET = string.ascii_letters + string.digits
BUCKET = "quality-documents"
EVENT_KEY = "RMTC_QR_APPROVED"
APPROVED_STATUSES = ("APPROVED", "PARTIALLY_APPROVED")
APPROVED_DISPOSITIONS = ("ACCEPTED", "ACCEPTED_UNDER_RESERVE")
LABEL_WIDTH_MM = 70.0
LABEL_HEIGHT_MM = 50.0


# ----------------------------------------------------------------------------- QR matrix / PNG / PDF
def qr_matrix(text: str, *, level: str = "M") -> list[list[bool]]:
    """Return the QR module matrix (True = dark) for ``text`` using reportlab's encoder."""
    from reportlab.graphics.barcode import qrencoder

    levels = {"L": qrencoder.QRErrorCorrectLevel.L, "M": qrencoder.QRErrorCorrectLevel.M,
              "Q": qrencoder.QRErrorCorrectLevel.Q, "H": qrencoder.QRErrorCorrectLevel.H}
    code = qrencoder.QRCode(None, levels.get(str(level).upper(), qrencoder.QRErrorCorrectLevel.M))
    code.addData(str(text))
    code.make()
    count = code.getModuleCount()
    return [[bool(code.isDark(row, col)) for col in range(count)] for row in range(count)]


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def png_from_matrix(matrix: Sequence[Sequence[bool]], *, scale: int = 10, border: int = 4) -> bytes:
    """Encode a module matrix as an 8-bit greyscale PNG (pure Python, zlib)."""
    scale = max(1, int(scale)); border = max(0, int(border))
    modules = len(matrix)
    size = (modules + 2 * border) * scale
    white_row = b"\x00" + b"\xff" * size
    raw = bytearray()
    for _ in range(border * scale):
        raw += white_row
    for row in matrix:
        line = bytearray(b"\xff" * (border * scale))
        for dark in row:
            line += (b"\x00" if dark else b"\xff") * scale
        line += b"\xff" * (border * scale)
        packed = b"\x00" + bytes(line)
        for _ in range(scale):
            raw += packed
    for _ in range(border * scale):
        raw += white_row
    header = struct.pack(">IIBBBBB", size, size, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", header) + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _png_chunk(b"IEND", b"")


def qr_png_bytes(text: str, *, scale: int = 10, border: int = 4) -> bytes:
    return png_from_matrix(qr_matrix(text), scale=scale, border=border)


def qr_label_png_bytes(text: str, lines: Sequence[str], *, scale: int = 10) -> bytes:
    """QR PNG with the label text underneath (Pillow); falls back to the plain QR PNG."""
    plain = qr_png_bytes(text, scale=scale)
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return plain
    try:
        qr_img = Image.open(BytesIO(plain)).convert("L")
        font = None
        for name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "Arial.ttf", "Helvetica.ttc"):
            try:
                font = ImageFont.truetype(name, 22); break
            except Exception:
                continue
        if font is None:
            try:
                font = ImageFont.load_default(size=22)
            except Exception:
                font = ImageFont.load_default()
        line_h = 30
        width = max(qr_img.width, 520)
        canvas = Image.new("L", (width, qr_img.height + line_h * len(lines) + 16), 255)
        canvas.paste(qr_img, ((width - qr_img.width) // 2, 0))
        draw = ImageDraw.Draw(canvas)
        y = qr_img.height
        for line in lines:
            text_line = str(line)[:60]
            try:
                w = draw.textlength(text_line, font=font)
            except Exception:
                w = len(text_line) * 11
            draw.text(((width - w) / 2, y), text_line, fill=0, font=font)
            y += line_h
        out = BytesIO(); canvas.save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return plain


def qr_drawing(text: str, size: float):
    """reportlab Drawing (vector QR) of ``size`` points for PDF prints."""
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing

    widget = QrCodeWidget(str(text))
    widget.barLevel = "M"
    x1, y1, x2, y2 = widget.getBounds()
    w, h = (x2 - x1) or 1.0, (y2 - y1) or 1.0
    drawing = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
    drawing.add(widget)
    return drawing


def label_pdf_bytes(text: str, lines: Sequence[str], *, width_mm: float = LABEL_WIDTH_MM, height_mm: float = LABEL_HEIGHT_MM) -> bytes:
    """Sticker-size PDF (default 70 x 50 mm): QR on the left, RMTC text on the right."""
    from reportlab.graphics import renderPDF
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas

    buffer = BytesIO()
    page_w, page_h = width_mm * mm, height_mm * mm
    pdf = rl_canvas.Canvas(buffer, pagesize=(page_w, page_h))
    pdf.setTitle("RMTC material location label")
    pad = 2.5 * mm
    qr_size = min(page_h - 2 * pad, page_w * 0.52)
    renderPDF.draw(qr_drawing(text, qr_size), pdf, pad, (page_h - qr_size) / 2)
    pdf.setLineWidth(0.6); pdf.rect(0.8 * mm, 0.8 * mm, page_w - 1.6 * mm, page_h - 1.6 * mm)
    x = pad + qr_size + 1.5 * mm
    avail = page_w - x - pad
    y = page_h - pad - 3.2 * mm
    for index, line in enumerate(lines):
        font, size = ("Helvetica-Bold", 7.4) if index == 0 else ("Helvetica", 6.3)
        pdf.setFont(font, size)
        value = str(line)
        while value and pdf.stringWidth(value, font, size) > avail:
            value = value[:-1]
        pdf.drawString(x, y, value)
        y -= size + 2.6
    pdf.setFont("Helvetica-Oblique", 5.2)
    pdf.drawString(x, pad, "Scan to download certificate")
    pdf.showPage(); pdf.save()
    return buffer.getvalue()


# ----------------------------------------------------------------------------- tokens / URLs / labels
def new_token() -> str:
    return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(TOKEN_LENGTH))


def valid_token(value: Any) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9]{32}", str(value or "")))


def functions_base_url() -> str:
    base = ""
    try:
        from core.config import get_settings
        settings = get_settings()
        base = str(settings.supabase_url or "").strip() or f"https://{settings.supabase_project_ref or DEFAULT_PROJECT_REF}.supabase.co"
    except Exception:
        base = f"https://{DEFAULT_PROJECT_REF}.supabase.co"
    return base.rstrip("/") + "/functions/v1"


def certificate_url(token: str) -> str:
    return f"{functions_base_url()}/{FUNCTION_SLUG}?t={token}"


def is_rmtc_approved(record: Mapping[str, Any] | None) -> bool:
    record = record or {}
    return str(record.get("status") or "").upper() in APPROVED_STATUSES and str(record.get("disposition") or "").upper() in APPROVED_DISPOSITIONS


def _date_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%d-%m-%Y")
    except Exception:
        return text[:10]


def label_lines(record: Mapping[str, Any], *, grade: str = "", supplier: str = "") -> list[str]:
    heat = str(record.get("heat_number") or "-")
    if record.get("heat_code"):
        heat += f" ({record.get('heat_code')})"
    return [
        f"RMTC {record.get('rmtc_number') or '-'}",
        f"Heat: {heat}",
        f"Grade: {grade or '-'}",
        f"Supplier: {supplier or '-'}",
        f"Approved: {_date_text(record.get('decision_at') or record.get('approved_at'))}",
    ]


def safe_file_token(value: Any, default: str = "RMTC") -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or default)).strip("_") or default


def quality_department(value: Any) -> bool:
    return "quality" in str(value or "").casefold()


# ----------------------------------------------------------------------------- R40 · customer-safe public certificate
def public_certificate_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """RMTC print payload for the PUBLIC certificate (anyone with the QR can download it).

    core.customer_privacy.strip_customer blanks every customer key; in addition the original (customer) part number
    is replaced by the FSI part number (``-`` when none), the drawing number / customer link of the parts are
    removed and the heat-usage rows show FSI part numbers only.
    """
    from core.customer_privacy import strip_customer

    clean = dict(strip_customer(dict(payload or {})))
    parts = {str(k): dict(v or {}) for k, v in dict(clean.get("parts") or {}).items()}
    fsi_by_number: dict[str, str] = {}
    for key, part in parts.items():
        fsi = str(part.get("fsi_part_number") or "").strip()
        if part.get("part_number"):
            fsi_by_number[str(part.get("part_number")).strip()] = fsi
        part["part_number"] = fsi or "-"
        for field in ("customer_id", "drawing_number", "drawing_revision"):
            if field in part:
                part[field] = None
        parts[key] = part
    clean["parts"] = parts
    usage = []
    for row in clean.get("heat_usage") or []:
        row = dict(row or {})
        original = str(row.get("part_number") or "").strip()
        row["part_number"] = str(row.get("fsi_part_number") or "").strip() or fsi_by_number.get(original, "") or "-"
        usage.append(row)
    if "heat_usage" in clean:
        clean["heat_usage"] = usage
    fsi_numbers = [str(p.get("part_number")) for p in parts.values() if str(p.get("part_number") or "-") != "-"]
    clean["qr_lines"] = [(f"Parts: {', '.join(dict.fromkeys(fsi_numbers)) or '-'}" if str(line).startswith("Parts:") else line)
                         for line in (clean.get("qr_lines") or [])]
    clean["qr_app_url"] = ""
    clean["customer_safe"] = True
    return clean


# ----------------------------------------------------------------------------- service
class RMTCQRService:
    """Token, certificate snapshot, QR assets and Quality-department e-mail for an approved RMTC."""

    def __init__(self, repo: Any = None, *, storage_client: Callable[[], Any] | None = None) -> None:
        if repo is None:
            from core.repository import Repository
            repo = Repository()
        self.repo = repo
        self._storage_client = storage_client

    # ---------------------------------------------------------------- storage
    def _client(self):
        if self._storage_client is not None:
            return self._storage_client()
        from core.database import get_session_client
        return get_session_client()

    def _upload(self, path: str, content: bytes, mime: str) -> str:
        client = self._client()
        if client is None:
            raise RuntimeError("Live Supabase session is required to store the RMTC certificate / QR.")
        client.storage.from_(BUCKET).upload(path, content, {"content-type": mime, "upsert": "true"})
        return path

    def folder(self, rmtc_id: str) -> str:
        return f"{getattr(self.repo, 'tenant_id', '') or 'tenant'}/rmtc_certificates/{rmtc_id}"

    # ---------------------------------------------------------------- tokens
    def active_token(self, rmtc_id: str) -> dict | None:
        try:
            rows = self.repo.select("rmtc_qr_tokens", eq={"rmtc_approval_id": str(rmtc_id), "revoked": False}, order_by="created_at", desc=True, limit=1)
        except Exception:
            return None
        return dict(rows[0]) if rows else None

    def ensure_token(self, record: Mapping[str, Any]) -> tuple[dict, bool]:
        existing = self.active_token(str(record.get("id")))
        if existing and valid_token(existing.get("token")):
            return existing, False
        row = self.repo.insert("rmtc_qr_tokens", {
            "rmtc_approval_id": str(record.get("id")),
            "token": new_token(),
            "rmtc_number": record.get("rmtc_number"),
            "certificate_bucket": BUCKET,
        })
        return dict(row), True

    def revoke_active(self, rmtc_id: str) -> int:
        """R40: mark every active token of this RMTC revoked (printed labels with the old code stop working)."""
        count = 0
        now = datetime.now(timezone.utc).isoformat()
        try:
            rows = self.repo.select("rmtc_qr_tokens", eq={"rmtc_approval_id": str(rmtc_id), "revoked": False}, limit=20) or []
        except Exception:
            rows = []
        for row in rows:
            if row.get("id"):
                self.repo.update("rmtc_qr_tokens", str(row["id"]), {"revoked": True, "revoked_at": now, "updated_at": now})
                count += 1
        return count

    def url_for(self, rmtc_id: str) -> str:
        token = self.active_token(rmtc_id)
        return certificate_url(str(token["token"])) if token and valid_token(token.get("token")) else ""

    # ---------------------------------------------------------------- labels
    def _names(self, record: Mapping[str, Any]) -> tuple[str, str]:
        grade = supplier = ""
        try:
            grade_row = self.repo.get("material_grades", str(record.get("material_grade_id") or "")) or {}
            grade = str(grade_row.get("grade_code") or grade_row.get("grade_name") or "")
        except Exception:
            pass
        try:
            party = self.repo.get("parties", str(record.get("supplier_id") or "")) or {}
            supplier = str(party.get("party_name") or "")
        except Exception:
            pass
        return grade, supplier

    def label_for(self, record: Mapping[str, Any]) -> list[str]:
        grade, supplier = self._names(record)
        return label_lines(record, grade=grade, supplier=supplier)

    def assets(self, record: Mapping[str, Any], token_row: Mapping[str, Any]) -> dict[str, Any]:
        url = certificate_url(str(token_row.get("token")))
        lines = self.label_for(record)
        return {
            "url": url, "lines": lines,
            "png": qr_label_png_bytes(url, lines),
            "qr_png": qr_png_bytes(url),
            "label_pdf": label_pdf_bytes(url, lines),
            "file_stem": f"RMTC_{safe_file_token(record.get('rmtc_number'))}",
        }

    # ---------------------------------------------------------------- certificate snapshot
    def certificate_pdf(self, rmtc_id: str) -> tuple[str, bytes]:
        from core.reporting import rmtc_record_pdf_bytes
        from core.rmtc_service import RMTCService

        service = RMTCService.__new__(RMTCService)
        service.repo = self.repo
        payload = public_certificate_payload(service.report_payload(rmtc_id))
        record = dict(payload.get("record") or {})
        return f"RMTC_{safe_file_token(record.get('rmtc_number'))}.pdf", rmtc_record_pdf_bytes(payload)

    def store_certificate(self, rmtc_id: str, token_row: Mapping[str, Any]) -> str:
        file_name, content = self.certificate_pdf(rmtc_id)
        path = self._upload(f"{self.folder(rmtc_id)}/{file_name}", content, "application/pdf")
        self._touch(token_row, {"certificate_path": path, "certificate_refreshed_at": datetime.now(timezone.utc).isoformat()})
        return path

    def _touch(self, token_row: Mapping[str, Any], changes: Mapping[str, Any]) -> None:
        if token_row.get("id"):
            try:
                self.repo.update("rmtc_qr_tokens", str(token_row["id"]), {**changes, "updated_at": datetime.now(timezone.utc).isoformat()})
            except Exception as exc:  # never block
                LOGGER.warning("rmtc_qr_tokens refresh failed: %s", exc)

    # ---------------------------------------------------------------- e-mail
    def quality_recipients(self) -> list[dict]:
        rows = self.repo.select("employees", eq={"status": "ACTIVE"}, order_by="first_name", limit=5000)
        seen: set[str] = set(); result: list[dict] = []
        for row in rows:
            email = str(row.get("email") or "").strip()
            if not quality_department(row.get("department")) or not email or email.casefold() in seen:
                continue
            seen.add(email.casefold())
            result.append({"email": email, "name": " ".join(v for v in (str(row.get("first_name") or "").strip(), str(row.get("last_name") or "").strip()) if v)})
        return result

    def email_quality(self, record: Mapping[str, Any], token_row: Mapping[str, Any], assets: Mapping[str, Any], *, notification_service: Any = None) -> dict | None:
        recipients = self.quality_recipients()
        if not recipients:
            return None
        stem = str(assets.get("file_stem") or "RMTC")
        png_path = self._upload(f"{self.folder(str(record.get('id')))}/{stem}_QR.png", bytes(assets["png"]), "image/png")
        pdf_path = self._upload(f"{self.folder(str(record.get('id')))}/{stem}_QR_Label.pdf", bytes(assets["label_pdf"]), "application/pdf")
        manifest = [
            {"bucket": BUCKET, "object_path": png_path, "file_name": f"{stem}_QR.png", "mime_type": "image/png", "generated": False},
            {"bucket": BUCKET, "object_path": pdf_path, "file_name": f"{stem}_QR_Label.pdf", "mime_type": "application/pdf", "generated": False},
        ]
        if notification_service is None:
            from core.notification_service import NotificationService
            notification_service = NotificationService(self.repo)
        # This e-mail carries exactly the QR PNG + sticker label (not the generic record bundle).
        notification_service.attachment_manifest = lambda *args, **kwargs: list(manifest)
        lines = list(assets.get("lines") or [])
        body = (
            f"RMTC {record.get('rmtc_number') or '-'} has been approved ({str(record.get('disposition') or '').replace('_', ' ').title()}).\n\n"
            + "\n".join(lines[1:]) +
            "\n\nAttached: QR code (PNG) and a 70 x 50 mm label (PDF). Print the label and stick it at the location where this material is stored."
            f"\nScanning the QR downloads the approved RMTC certificate:\n{assets.get('url')}\n"
        )
        row = notification_service.enqueue(
            EVENT_KEY,
            subject=f"Quality · RMTC {record.get('rmtc_number') or '-'} approved · QR for material location",
            body_text=body,
            related_table="rmtc_approvals", related_id=str(record.get("id")),
            context={"rmtc_id": str(record.get("id")), "rmtc_number": record.get("rmtc_number"), "next_task": "Stick QR at material location"},
            recipient_email=recipients[0]["email"], recipient_name=recipients[0]["name"],
            cc_emails=[r["email"] for r in recipients[1:]],
            include_generated_pdf=False, include_record_attachments=False, include_supplier=False,
            automatic=True,
        )
        if row:
            try:
                notification_service.dispatch([row])
            except Exception as exc:
                LOGGER.warning("RMTC QR e-mail dispatch failed: %s", exc)
            self._touch(token_row, {"qr_png_path": png_path, "label_pdf_path": pdf_path, "emailed_at": datetime.now(timezone.utc).isoformat(), "email_recipient_count": len(recipients)})
        return row

    # ---------------------------------------------------------------- approval hook
    def on_rmtc_approved(self, rmtc_id: str, *, send_email: bool = True) -> dict[str, Any]:
        """Create token + certificate snapshot + QR, then e-mail Quality. Never raises."""
        result: dict[str, Any] = {"ok": False, "warnings": [], "url": "", "emailed": 0, "created": False}
        try:
            record = self.repo.get("rmtc_approvals", str(rmtc_id)) or {}
            if not is_rmtc_approved(record):
                result["warnings"].append("RMTC is not approved; QR not generated.")
                return result
            token_row, created = self.ensure_token(record)
            result.update({"created": created, "url": certificate_url(str(token_row.get("token")))})
            try:
                result["certificate_path"] = self.store_certificate(str(rmtc_id), token_row)
            except Exception as exc:
                result["warnings"].append(f"Certificate PDF could not be stored: {exc}")
            assets = self.assets(record, token_row)
            result["ok"] = True
            if send_email:
                try:
                    row = self.email_quality(record, token_row, assets)
                    result["emailed"] = len(self.quality_recipients()) if row else 0
                    if not row:
                        result["warnings"].append("No active Quality department employee with an e-mail address; QR e-mail not queued.")
                except Exception as exc:
                    result["warnings"].append(f"QR e-mail could not be queued: {exc}")
        except Exception as exc:
            LOGGER.warning("RMTC QR generation failed for %s: %s", rmtc_id, exc)
            result["warnings"].append(f"QR could not be generated: {exc}")
        return result
