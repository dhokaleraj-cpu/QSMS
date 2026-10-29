"""R39 (agent Q): Android RMTC parity - material-location QR (PNG / JPEG / PDF / 100x60 mm label), Quality QR e-mail on
approval, sections applicable per RMTC, horizontal chemistry / Jominy grids (entry, approval view, Part Master, print)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mobile/android_qcms_app/app/src/main/java/com/fourstar/qcmsapp"


def read(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def test_files_exist_and_record_screen_wires_the_panel():
    for name in ("IncQrCode.java", "IncQrLabel.java", "IncRmtcSections.java", "IncRmtcHGrid.java", "ChemGrid.java"):
        assert (SRC / name).exists(), name
    rec = read("RecordScreen.java")
    assert '"rmtc_approvals".equals(m.table)' in rec and "IncQrLabel.panel(a, rec, this::reload)" in rec


def test_qr_label_downloads_and_file_names():
    q = read("IncQrLabel.java")
    for text in ('s.stem + "_QR.png"', 's.stem + "_QR.jpg"', 's.stem + "_QR.pdf"', 's.stem + "_QR_Label.pdf"',
                 "Bitmap.CompressFormat.PNG", "Bitmap.CompressFormat.JPEG", "c.drawColor(Color.WHITE)", "new PdfDocument()",
                 "LABEL_WIDTH_MM = 100f, LABEL_HEIGHT_MM = 60f", "A6_WIDTH_MM = 105f, A6_HEIGHT_MM = 148f",
                 "SndFiles.saveToDownloads", "SndFiles.share", "ExportKit.printPdf", "SndPdfView.show"):
        assert text in q, text
    # same QR content as the website (QR_CONTENT = "APP"): login-protected rmtc-records link, no token / secret
    assert "RptReports.rmtcQrUrl(api" in q and "IncQrCode.encode(s.url)" in q
    rpt = read("RptReports.java")
    assert 'QCMS_WEBSITE = "https://vf6fa9hrhxquqxmfgyy4wf.streamlit.app"' in rpt and '"/rmtc-records?rmtc="' in rpt
    # caption = label_lines
    for text in ('"RMTC "', '"Heat: "', '"Grade: "', '"Size / Section: "', '"Parts: "', '"Qty: "', '"Supplier: "', '"Approved: "', '"Location: "'):
        assert text in q, text
    # stored RMTC_QR_LABEL attachment offered too
    assert 'DOCUMENT_TYPE = "RMTC_QR_LABEL"' in q and "storedLabel(api, rid)" in q and "api.download(path)" in q


def test_approval_triggers_quality_qr_email_like_the_web():
    q = read("IncQrLabel.java")
    assert 'EVENT_KEY = "RMTC_APPROVED_QR"' in q
    for text in ('"qcms_notification_outbox"', '"attachment_manifest"', "SndMail.dispatch(api, ids)", "isQualityDepartment",
                 '"/rmtc/" + rid + "/" + fileName', '"document_attachments"', "RptPdf.render(RptReports.rmtc(api"):
        assert text in q, text
    assert "service_role" not in q
    decide = read("IncRmtcDecide.java")
    assert "IncQrLabel.onApproved(api, rid, true)" in decide and "qsms_decide_rmtc" in decide
    added = read("IncRmtcAdded.java")
    assert "IncQrLabel.onApproved(api, rid, false)" in added


def test_sections_applicable_port():
    s = read("IncRmtcSections.java")
    for key in ("heat_balance", "supplier_mechanical", "chemistry", "jominy", "di_value", "mechanical", "heat_treatment", "microstructure"):
        assert f'"{key}"' in s, key
    assert '"applicable_sections"' in s and '"section_applicability"' in s
    assert 'PART_DEFAULT_KEYS = Arrays.asList("chemistry", "jominy", "di_value", "heat_treatment", "microstructure")' in s
    ws = read("IncRmtcWorksheet.java")
    assert "IncRmtcSections.load(api, rid, h)" in ws and "IncRmtcSections.requirementApplicable" in ws
    assert 'Section not applicable for this RMTC' in ws and "naRequirements" in ws
    rpt = read("RptReports.java")
    assert "IncRmtcSections.resolve(record, parts.values())" in rpt and '"Sections Not Applicable"' in rpt
    for key in ("heat_balance", "supplier_mechanical", "chemistry", "jominy", "di_value", "mechanical", "heat_treatment", "microstructure"):
        assert f'IncRmtcSections.on(secs, "{key}")' in rpt, key


def test_horizontal_grids_everywhere():
    ws = read("IncRmtcWorksheet.java")
    assert "new IncRmtcHGrid(a)" in ws and "RptReports.orderedChem" in ws and '"Distance (mm)"' in ws
    assert 'RowsEditor(a, "Chemistry"' not in ws and 'RowsEditor(a, "Jominy"' not in ws
    decide = read("IncRmtcDecide.java")
    assert "RptReports.chemHorizontal" in decide and "RptReports.jominyHorizontal" in decide
    assert "RptReports.jominyHorizontal" in read("MstPartJominyScreen.java")
    met = read("MstPartMetScreen.java")
    assert "RptReports.chemHorizontal" in met and "RptReports.jominyHorizontal" in met
    rpt = read("RptReports.java")
    assert 'CHEM_ORDER = {"C", "Mn", "Si", "S", "P"' in rpt
    assert 'multiply(new BigDecimal("1.5875"))' in read("ChemGrid.java")
    assert "IncQrCode.png(IncQrCode.encode(qrUrl)" in rpt  # QR printed on the approved RMTC record PDF


def _jdk_works() -> bool:
    """True only for a real JDK. On macOS /usr/bin/javac and /usr/bin/java are Apple launchers that exit 1 with
    "Unable to locate a Java Runtime" when no JDK is installed - those must skip this test, not fail it."""
    for tool in ("javac", "java"):
        if not shutil.which(tool):
            return False
        try:
            if subprocess.run([tool, "-version"], capture_output=True, timeout=30).returncode != 0:
                return False
        except Exception:
            return False
    return True


@pytest.mark.skipif(not _jdk_works(), reason="JDK not available (no javac / java, or only the macOS launcher stub)")
def test_java_qr_matrix_equals_website_matrix(tmp_path):
    from core.rmtc_qr import qr_matrix
    pkg = tmp_path / "com/fourstar/qcmsapp"
    pkg.mkdir(parents=True)
    shutil.copy(SRC / "IncQrCode.java", pkg / "IncQrCode.java")
    (pkg / "QrDump.java").write_text(
        "package com.fourstar.qcmsapp;\npublic class QrDump { public static void main(String[] a) { for (String t : a) {"
        " for (boolean[] r : IncQrCode.encode(t)) { StringBuilder s = new StringBuilder(); for (boolean b : r) s.append(b ? '1' : '0');"
        " System.out.println(s); } System.out.println(\"--\"); } } }\n", encoding="utf-8")
    built = subprocess.run(["javac", "-d", str(tmp_path / "out"), str(pkg / "IncQrCode.java"), str(pkg / "QrDump.java")], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr[-2000:]
    texts = ["https://vf6fa9hrhxquqxmfgyy4wf.streamlit.app/rmtc-records?rmtc=RMTC-2026-0001", "HELLO WORLD", "0123456789",
             "https://vf6fa9hrhxquqxmfgyy4wf.streamlit.app/rmtc-records?rmtc=RMTC%2F26%20" + "X" * 160]
    out = subprocess.run(["java", "-cp", str(tmp_path / "out"), "com.fourstar.qcmsapp.QrDump", *texts], check=True, capture_output=True, text=True).stdout
    blocks = [b.strip().splitlines() for b in out.split("--") if b.strip()]
    for text, block in zip(texts, blocks):
        assert block == ["".join("1" if v else "0" for v in row) for row in qr_matrix(text)], text
