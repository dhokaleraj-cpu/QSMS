import re
from pathlib import Path
from io import BytesIO

from PIL import Image
from reportlab.lib.pagesizes import A4

from core.reporting import (
    dimensional_record_pdf_bytes,
    material_inward_record_pdf_bytes,
    metlab_record_pdf_bytes,
    rmtc_record_pdf_bytes,
)
from tests.test_v495_rmtc_portrait_compact_pdf import _payload

ROOT = Path(__file__).resolve().parents[1]


def _jpg() -> bytes:
    image = Image.new("RGB", (320, 180), "white")
    out = BytesIO(); image.save(out, "JPEG"); return out.getvalue()


def test_release_branding_and_footer_contract():
    assert (ROOT / "VERSION").read_text().strip() in {"4.9.6", "4.9.7", "4.9.8", "4.9.9", "4.10.0", "4.10.1", "4.10.2", "4.10.3", "4.10.5", "4.10.6", "4.10.7", "4.10.8", "4.10.9", "4.11.0", "4.11.1", "4.11.2", "4.11.3", "4.11.4", "4.11.5", "4.11.6", "4.11.7", "4.11.8","4.12.0", "4.12.1", "4.12.2", "4.12.3", "4.12.4", "4.12.5", "4.12.6", "4.12.7", "4.12.8", "4.12.9", "4.13.0", "4.13.1", "4.13.2", "4.13.3", "4.13.4", "4.13.5", "4.13.6", "4.13.7", "4.13.8", "4.13.9", "4.14.0", "4.14.2", "4.14.3", "4.14.4", "4.14.5", "4.14.6", "4.14.7", "4.14.8", "4.14.9", "4.14.10", "4.14.11", "4.14.12", "4.14.13", "4.14.14", "4.14.15", "4.14.16", "4.14.17", "4.14.18", "4.14.19", "4.14.20", "4.14.21", "4.14.22", "4.14.23", "4.14.24"}
    assert (ROOT / "docs" / "RELEASE_4_9_6.md").exists()
    ui = (ROOT / "core" / "ui.py").read_text()
    reporting = (ROOT / "core" / "reporting.py").read_text()
    assert "QUALITY CONTROL MONITORING SYSTEM" in ui
    assert "QUALITY CONTROL MONITORING SYSTEM" in reporting
    assert "QUALITY SYSTEM MONITORING SYSTEM" not in ui
    assert "QUALITY SYSTEM MONITORING SYSTEM" not in reporting
    for token in ("Developed by Rajesh Dhokale", "dhokaleraj@icloud.com", "Copyrights by STAWN"):
        assert token in ui
        assert token in reporting
    assert "App Version" in reporting


def test_rmtc_global_heat_header_and_three_microstructure_contract():
    reporting = (ROOT / "core" / "reporting.py").read_text()
    rmtc_page = (ROOT / "app_pages" / "rmtc_pages.py").read_text()
    assert "GLOBAL HEAT QUANTITY BALANCE & RECORD LIST" in reporting
    assert "GLOBAL HEAT QUANTITY BALANCE & RECORD LIST" in rmtc_page
    assert "HEAT NUMBER:" in reporting and "RMTC NUMBER:" in reporting
    assert reporting.index("HEAT NUMBER:") < reporting.index("RMTC NUMBER:")
    assert "10.5 if portrait_page" in reporting and "7.0 if portrait_page" in reporting
    assert "range(1, 4)" in rmtc_page
    for n in range(1, 4):
        assert f"RMTC_MICROSTRUCTURE_{{slot}}" in rmtc_page or f"RMTC_MICROSTRUCTURE_{n}" in rmtc_page
    assert "RMTC MICROSTRUCTURE PHOTOGRAPHS" in reporting


def test_controlled_pdf_downloads_are_wired():
    metlab = (ROOT / "app_pages" / "metlab_report.py").read_text()
    dimensional = (ROOT / "app_pages" / "dimensional_report.py").read_text()
    inward = (ROOT / "app_pages" / "material_inward.py").read_text()
    osp = (ROOT / "app_pages" / "osp_transactions.py").read_text()
    assert "Download MetLAB Report PDF" in metlab
    assert "Download Final / Dimensional PDF" in dimensional
    assert "Download Inward PDF" in inward
    assert "OSP CONTROLLED PDF REPORTS" in osp
    assert "metlab_record_pdf_bytes" in osp and "dimensional_record_pdf_bytes" in osp


def test_generated_controlled_pdfs_are_a4_portrait():
    employees = {"e1": {"employee_code":"E1","first_name":"One","last_name":"User"}, "e2": {"employee_code":"E2","first_name":"Two","last_name":"User"}, "e3": {"employee_code":"E3","first_name":"Three","last_name":"User"}}
    image = _jpg()
    metlab = metlab_record_pdf_bytes({
        "record":{"report_number":"MLAB-1","test_date":"2026-08-11","inspection_scope":"OSP_SAMPLE","osp_job_id":"o1","heat_number":"H1","overall_result":"PASS","disposition":"ACCEPTED","prepared_by_employee_id":"e1","validated_by_employee_id":"e2","approved_by_employee_id":"e3"},
        "part":{"part_number":"P1","part_name":"Part"},"material_grade":{"grade_code":"20MnCr5"},"process":{"process_name":"Carburizing"},"stage":{"stage_name":"OSP Sample"},"osp_job":{"vendor_name":"Vendor","sample_quantity":3},"employees":employees,
        "results":{"rows":[{"parameter":"Hardness","specification":"59-63 HRC","actual_value":"61","unit":"HRC","result":"PASS"}]},
        "microstructure_images":[{"bytes":image,"caption":f"Photo {i}"} for i in range(1,4)],
    })
    dim = dimensional_record_pdf_bytes({"record":{"report_number":"DIM-1","inspection_date":"2026-08-11","inspection_scope":"FINAL_INSPECTION","heat_number":"H1","overall_result":"PASS","disposition":"ACCEPTED"},"part":{"part_number":"P1","part_name":"Part"},"employees":employees,"results":[]})
    inward = material_inward_record_pdf_bytes({"record":{"inward_number":"INW-1","inward_date":"2026-08-11","heat_number":"H1","status":"RELEASED"},"part":{"part_number":"P1","part_name":"Part"},"employees":employees})
    payload = _payload(); payload["heat_summary"]={"global_steel_quantity_kg":2250,"committed_steel_quantity_kg":610,"available_unallocated_steel_quantity_kg":1640,"inward_steel_quantity_kg":300,"remaining_planned_steel_quantity_kg":310,"active_rmtc_count":1}; payload["heat_usage"]=[{"rmtc_number":"RMTC-1","supplier_rmtc_number":"SUP-1","supplier_name":"Supplier","part_number":"P1","planned_steel_quantity_kg":610,"inward_steel_quantity_kg":300,"remaining_planned_steel_quantity_kg":310,"part_disposition":"ACCEPTED"}]; payload["microstructure_images"]=[{"bytes":image,"caption":f"Photo {i}"} for i in range(1,4)]
    rmtc = rmtc_record_pdf_bytes(payload)
    for pdf in (metlab, dim, inward, rmtc):
        assert pdf.startswith(b"%PDF")
        match=re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*\]", pdf); assert match
        w,h=map(float,match.groups()); assert w<h and abs(w-A4[0])<1 and abs(h-A4[1])<1
