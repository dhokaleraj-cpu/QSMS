"""R39 (agent Q): RMTC QR download as PNG / JPEG / PDF on the website (core/rmtc_qr.py + app_pages/rmtc_pages.py)."""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from core import rmtc_qr

ROOT = Path(__file__).resolve().parents[1]
URL = "https://vf6fa9hrhxquqxmfgyy4wf.streamlit.app/rmtc-records?rmtc=RMTC-2026-0001"
LINES = ["RMTC RMTC-2026-0001", "Heat: H123 (HC1)", "Grade: 20MnCr5", "Size / Section: 60 RCS", "Parts: P-1, P-2",
         "Qty: 1,250.5 kg", "Supplier: Steel Co", "Approved: 29-10-2026"]


def test_download_formats_and_file_names():
    files = rmtc_qr.qr_download_files(URL, LINES, "RMTC_RMTC-2026-0001")
    assert [f["format"] for f in files] == ["PNG", "JPEG", "PDF"] == list(rmtc_qr.QR_DOWNLOAD_FORMATS)
    assert [f["file_name"] for f in files] == ["RMTC_RMTC-2026-0001_QR.png", "RMTC_RMTC-2026-0001_QR.jpg", "RMTC_RMTC-2026-0001_QR.pdf"]
    assert [f["mime"] for f in files] == ["image/png", "image/jpeg", "application/pdf"]
    png, jpg, pdf = (f["data"] for f in files)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert jpg[:3] == b"\xff\xd8\xff"
    assert pdf[:5] == b"%PDF-"


def test_jpeg_is_rgb_on_white_background():
    Image = pytest.importorskip("PIL.Image")
    image = Image.open(io.BytesIO(rmtc_qr.qr_jpeg_bytes(URL, LINES)))
    assert image.format == "JPEG" and image.mode == "RGB"
    r, g, b = image.getpixel((5, image.height - 5))  # caption area corner inside the frame -> white
    assert min(r, g, b) > 230
    plain = Image.open(io.BytesIO(rmtc_qr.qr_jpeg(URL)))
    assert plain.mode == "RGB" and plain.getpixel((0, 0))[0] > 230  # quiet zone is white


def test_pdf_contains_caption_text_and_label_pdf_size():
    pdf = rmtc_qr.qr_pdf(URL, LINES, title="RMTC RMTC-2026-0001 QR")
    assert pdf.startswith(b"%PDF-")
    assert b"297.6378" in pdf and b"419.5276" in pdf  # A6 portrait page
    label = rmtc_qr.label_pdf_bytes(URL, LINES)
    assert label.startswith(b"%PDF-")
    # 100 x 60 mm sticker = 283.46 x 170.08 pt
    assert b"283.4646" in label and b"170.0787" in label


def test_download_files_never_raise(monkeypatch):
    monkeypatch.setattr(rmtc_qr, "qr_jpeg_bytes", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no pillow")))
    files = rmtc_qr.qr_download_files(URL, LINES, "RMTC/26 01")
    assert [f["format"] for f in files] == ["PNG", "PDF"]
    assert files[0]["file_name"] == "RMTC_26_01_QR.png"


def test_exports_listed():
    for name in ("QR_DOWNLOAD_FORMATS", "qr_jpeg_bytes", "qr_pdf_bytes", "qr_download_files", "qr_png", "qr_jpeg", "qr_pdf"):
        assert name in rmtc_qr.__all__, name


def test_rmtc_page_offers_png_jpeg_pdf_and_label():
    page = (ROOT / "app_pages/rmtc_pages.py").read_text(encoding="utf-8")
    panel = page[page.index("def _render_rmtc_qr_panel"):page.index("def render_approval")]
    for text in ("Download QR PNG", "Download QR JPEG", "Download QR PDF", "Print Label PDF (100 x 60 mm)",
                 "_QR.png", "_QR.jpg", "_QR.pdf", "_QR_Label.pdf", "image/jpeg", "application/pdf"):
        assert text in panel, text
    # the panel is shown on the RMTC records page and on the approval page
    assert "_render_rmtc_qr_panel(svc.repo,selected_row" in page and "key='approval')" in page
