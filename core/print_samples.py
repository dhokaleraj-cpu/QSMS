"""R21 · Sample data used by the Print Layout Designer live preview (no real records)."""
from __future__ import annotations

from typing import Any

EMP = {"e1": {"employee_code": "EMP-0031", "first_name": "Prepared", "last_name": "By"}, "e2": {"employee_code": "EMP-0012", "first_name": "Validated", "last_name": "By"}, "e3": {"employee_code": "E003", "first_name": "Approval", "last_name": "User"}}


def po_sample() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    header = {"po_number": "PD9121000090", "po_type": "RAW_MATERIAL", "order_date": "2026-10-12", "delivery_date": "2026-11-05",
              "requisitioner": "Requisitioner", "ship_via": "Road", "incoterm": "DAP, CHAKAN", "payment_term": "NET 30 DAYS AFTER GRN",
              "quotation_reference": "Q-STEEL-2026-114", "quotation_date": "2026-10-01", "old_po_reference": "",
              "vendor_snapshot": {"party_name": "Sample Steel Supplier Pvt Ltd", "address": "Plot 12, MIDC Bhosari", "city": "Pune", "state": "Maharashtra", "country": "India", "tax_identifier": "27ABCDE1234F1Z5", "phone": "020 0000 0000", "email": "sales@example.com"},
              "remarks": "PART WILL BE SUPPLIED AS PER DRAWING.", "subtotal": 296400, "cgst_amount": 26676, "sgst_amount": 26676, "igst_amount": 0, "other_amount": 0, "grand_total": 349752,
              "approval_status": "APPROVED", "approver_employee_name": "Approver Name", "approver_employee_code": "EMP001", "approved_at": "2026-10-12T06:30:00+00:00"}
    item = {"item_no": "RM-EN19-RD45", "item_description": "Round Bar · EN19 · 45 mm", "quantity": 3800, "uom": "KGS", "unit_price": 78, "gst_percent": 18, "gst_amount": 53352, "line_total": 296400,
            "hsn_sac_code": "72283029", "part_description_master": "Clubbed RM for FSI-1021, FSI-1044, FSI-1107",
            "customer_source_rows": [{"customer_po_number": "4500123456", "po_position": "10", "part_description": "Flange Yoke", "quantity": 1500, "uom": "KGS"},
                                     {"customer_po_number": "4500123499", "po_position": "20", "part_description": "Slip Yoke", "quantity": 1300, "uom": "KGS"},
                                     {"customer_po_number": "4500124011", "po_position": "10", "part_description": "Stub Shaft", "quantity": 1000, "uom": "KGS"}],
            "technical_data_snapshot": [{"heading": "Raw Material Type", "value": "Round Bar", "source": "STANDARD"}, {"heading": "Material Grade", "value": "EN19", "source": "STANDARD"},
                                        {"heading": "Section Size", "value": "45 mm", "source": "STANDARD"}, {"heading": "Supplier RM Item Code", "value": "RM-EN19-RD45", "source": "STANDARD"},
                                        {"heading": "Supplier Lead Time", "value": "21 days", "source": "STANDARD"}, {"heading": "Cutting Cost", "value": "INR 2 per kg", "source": "CUSTOM"}],
            "price_history_snapshot": [{"start_date": "2026-10-12", "end_date": None, "price": 78, "remarks": "Current"}, {"start_date": "2026-04-01", "end_date": "2026-10-11", "price": 81, "remarks": "Revision"}]}
    return header, [item]


def dimensional_sample() -> dict[str, Any]:
    rows = [{"characteristic_no": i, "characteristic": c, "specification": sp, "lower_spec": lo, "upper_spec": hi, "unit": "mm", "observations": obs, "result": "PASS", "remarks": rm}
            for i, (c, sp, lo, hi, obs, rm) in enumerate([("Overall Length", "120.00 ± 0.20", 119.8, 120.2, [120.05, 120.02, 119.98], ""), ("Bore Diameter", "35 +0.03/0", 35, 35.03, [35.01, 35.02], "Air gauge"), ("Bend", "0/0.1", 0, 0.1, [0.04], "")], 1)]
    return {"record": {"report_number": "D9-DIR-2026-00112", "inspection_date": "2026-10-07", "inspection_scope": "OSP_RECEIPT", "heat_number": "H-24578", "overall_result": "PASS", "disposition": "ACCEPTED", "remarks": "All characteristics within limits", "prepared_by_employee_id": "e1", "validated_by_employee_id": "e2", "approved_by_employee_id": "e2"},
            "part": {"part_number": "40256626", "part_name": "Yoke"}, "employees": EMP, "results": rows}


def metlab_sample() -> dict[str, Any]:
    return {"record": {"report_number": "MLAB-D9-26-00145", "test_date": "2026-10-07", "heat_number": "H-24578", "disposition": "ACCEPTED", "remarks": "Material meets 20MnCr5 requirements", "prepared_by_employee_id": "e1"},
            "part": {"part_number": "40256626", "part_name": "Yoke"}, "employees": EMP,
            "results": {"inspection_method": "GENERAL_METLAB", "conclusion_remark": "Retest not required", "rows": [
                {"characteristic_no": 1, "characteristic": "Surface Hardness", "specification": "58-62 HRC", "unit": "HRC", "actual_value": "60", "result": "PASS", "remarks": "3 readings"},
                {"characteristic_no": 2, "characteristic": "Core Hardness", "specification": "30-42 HRC", "unit": "HRC", "actual_value": "36", "result": "PASS"}]}}


def bend_sample() -> dict[str, Any]:
    return {"record": {"report_number": "1006/2026/7237", "test_date": "2026-08-25", "disposition": "ACCEPTED", "remarks": "Part accepted"},
            "part": {"part_number": "D9OV-1167", "part_name": "U-Bolt"},
            "results": {"inspection_method": "BEND_TEST", "bend_angle_degrees": 171, "bend_report": {"customer_name": "Customer", "surface_remark": "No peeling or flaking on the plating surface.", "baking_temp_spec": "400 °C", "baking_temp_actual": "405 °C", "load_kn": "38.6 kN", "cht_mm": "42"}}}


def inward_sample() -> dict[str, Any]:
    return {"record": {"inward_number": "INW-D9-26-0451", "inward_date": "2026-10-07", "heat_number": "H-24578", "heat_code": "A-0007", "invoice_number": "INV-7781", "grn_number": "GRN-5512",
                       "steel_quantity_kg": 2250, "production_quantity_pcs": 700, "receipt_disposition": "ACCEPTED", "metallurgical_status": "ACCEPTED", "dimensional_status": "ACCEPTED", "quality_disposition": "ACCEPTED", "status": "RELEASED", "remarks": "Released to production"},
            "register": {"part_number": "40256626", "part_name": "Yoke", "supplier_name": "Sample Steel Supplier", "rmtc_number": "RMTC-D9-0001", "rmtc_disposition": "ACCEPTED"},
            "part": {"part_number": "40256626", "part_name": "Yoke"}, "employees": EMP}


def rmtc_sample():
    chemistry = []
    for element, minimum, maximum, actual in [
        ("C", 0.17, 0.22, 0.19), ("Si", 0.15, 0.40, 0.25), ("Mn", 1.10, 1.40, 1.25),
        ("P", 0, 0.025, 0.012), ("S", 0, 0.035, 0.015), ("Cr", 1.0, 1.3, 1.12),
        ("Mo", 0, 0.1, 0.03), ("Ni", 0, 0.4, 0.18), ("Al", 0.02, 0.05, 0.03),
    ]:
        chemistry.append({"part_id": "p1", "element": element, "minimum_value": minimum, "maximum_value": maximum, "actual_value": actual, "unit": "%", "result": "ACCEPTED"})
    jominy = []
    for index in range(10):
        jominy.append({
            "part_id": "p1", "distance_label": f"J{index + 1}", "distance_mm": 1.5 * (index + 1),
            "minimum_hrc": 35, "maximum_hrc": 58, "actual_hrc": 52 - index, "result": "ACCEPTED",
            "calculated_hrc": 51 - index, "calculated_result": "ACCEPTED", "applicability": "APPLICABLE",
        })
    return {
        "record": {
            "rmtc_number": "RMTC-D9-20260802195348", "entry_date": "2026-08-11", "certificate_reference": "SUP-1543",
            "certificate_date": "2026-08-10", "heat_number": "b12345", "heat_code": "A-0007",
            "certificate_quantity": 2250, "rm_section": "60 mm Bar", "forging_route": "Bar + Forging",
            "status": "APPROVAL_PENDING", "validation_result": "APPROVED", "disposition": "ACCEPTED",
            "decision_at": "2026-08-11 10:00", "mechanical_results": {"tensile_strength_mpa": 910},
            "prepared_by_employee_id": "e1", "validated_by_employee_id": "e2", "approved_by_employee_id": "e3",
        },
        "supplier": {"party_name": "Steel Supplier"}, "steel_mill": {"party_name": "Steel Mill"},
        "employees": {
            "e1": {"employee_code": "E001", "first_name": "Prepared", "last_name": "User"},
            "e2": {"employee_code": "E002", "first_name": "Validation", "last_name": "User"},
            "e3": {"employee_code": "E003", "first_name": "Approval", "last_name": "User"},
        },
        "parts": {"p1": {"id": "p1", "part_number": "71.784.3", "part_name": "Differential Spider", "material_grade_id": "g1"}},
        "material_grades": {"g1": {"id": "g1", "grade_code": "20MnCr5"}},
        "part_approvals": [{
            "part_id": "p1", "planned_production_quantity_pcs": 200, "input_weight_kg": 3.05,
            "planned_steel_quantity_kg": 610, "worksheet_completed_at": "2026-08-11", "grain_size": "7-8",
            "actual_di": 2.1, "actual_di_status": "ACCEPTED", "calculated_di": 2.0, "calculated_di_status": "ACCEPTED",
            "source_status": "ACCEPTED", "material_grade_status": "ACCEPTED", "raw_material_status": "ACCEPTED",
            "chemistry_status": "ACCEPTED", "jominy_status": "ACCEPTED", "requirement_status": "ACCEPTED",
            "approval_status": "ACCEPTED", "disposition": "ACCEPTED", "decision_reason": "PASS",
        }],
        "chemistry": chemistry,
        "jominy": jominy,
        "requirements": [
            {"part_id": "p1", "requirement_name": "Tensile Strength", "requirement_value": "850 MPa Min", "actual_value": "910", "unit": "MPa", "result": "ACCEPTED", "remarks": ""},
            {"part_id": "p1", "requirement_name": "Case Depth", "requirement_value": "0.95-1.35 mm", "actual_value": "1.236", "unit": "mm", "result": "ACCEPTED", "remarks": ""},
        ],
    }


def sample_pdf(doc: str, layout: dict[str, Any] | None) -> bytes:
    """Render the sample document of *doc* with an (unsaved) layout."""
    doc = str(doc or "").upper()
    if doc == "PURCHASE_ORDER":
        from core.purchase_order_reporting import purchase_order_pdf_bytes
        header, items = po_sample()
        return purchase_order_pdf_bytes(header, items, terms_path="/__qcms_no_terms__.pdf", layout=layout or {})
    from core import reporting as r
    if doc == "RMTC":
        return r.rmtc_record_pdf_bytes(rmtc_sample(), layout=layout or {})
    if doc == "METLAB":
        return r.metlab_record_pdf_bytes(metlab_sample(), layout=layout or {})
    if doc == "BEND_TEST":
        return r.bend_test_report_pdf_bytes(bend_sample(), layout=layout or {})
    if doc == "DIMENSIONAL":
        return r.dimensional_record_pdf_bytes(dimensional_sample(), layout=layout or {})
    if doc == "MATERIAL_INWARD":
        return r.material_inward_record_pdf_bytes(inward_sample(), layout=layout or {})
    return r.controlled_record_pdf_bytes("CONTROLLED QUALITY RECORD", {"Record Number": "QR-0001", "Date": "12-10-2026", "Status": "APPROVED", "Owner": "Quality"},
                                         {"DETAILS": [{"Item": "Check 1", "Result": "PASS", "Remarks": "OK"}, {"Item": "Check 2", "Result": "PASS", "Remarks": "OK"}]},
                                         record_number="QR-0001", layout=layout or {})
