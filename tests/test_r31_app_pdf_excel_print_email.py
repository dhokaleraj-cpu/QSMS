"""R31: every app screen can Download PDF, Download Excel (.xlsx), Print, Email and Share."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mobile/android_qcms_app/app/src/main/java/com/fourstar/qcmsapp"


def read(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def test_export_kit_actions():
    kit = read("ExportKit.java")
    for label in ("Download PDF", "Download Excel (.xlsx)", "View PDF", "Print", "Email from QCMS (PDF + Excel attached)", "Share PDF", "Share Excel"):
        assert label in kit, label
    assert "PrintManager" in kit and "PrintDocumentAdapter" in kit and "onWriteFinished" in kit
    assert "SndEmailSend.openWith" in kit and "SndFiles.saveToDownloads" in kit


def test_every_screen_has_the_export_button():
    main = read("MainActivity.java")
    assert 'barButton("⇩")' in main and "ExportKit.show(this, s, shown)" in main
    assert "implements ExportDoc.Source" in read("RegisterScreen.java")
    assert "ExportKit.showData(a, this, scroll)" in read("RecordScreen.java")  # R33: data export; print layout via printLayout()
    assert "exportPairs()" in read("FormView.java") and "rowsData()" in read("SheetView.java")


def test_real_xlsx_and_pdf_writers():
    x = read("ExportXlsx.java")
    assert "ZipOutputStream" in x and "xl/worksheets/sheet" in x and 'state=\\"frozen\\"' in x and "autoFilter" in x
    p = read("ExportPdf.java")
    assert "PdfDocument" in p and "Page \" + pageCount + \" of \"" in p and "headerRow(t, w, pad, lh, false)" in p


def test_email_attachments_prefill():
    assert "static void openWith(MainActivity a, String subject, String body, List<Attachments.FileData> attachments)" in read("SndEmailSend.java")
