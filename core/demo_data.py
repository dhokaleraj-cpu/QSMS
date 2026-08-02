from __future__ import annotations

from copy import deepcopy

DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000001"

IDS = {
    "customer": "00000000-0000-0000-0000-000000000101",
    "supplier": "00000000-0000-0000-0000-000000000102",
    "steel_mill": "00000000-0000-0000-0000-000000000103",
    "osp_vendor": "00000000-0000-0000-0000-000000000104",
    "grade_16": "00000000-0000-0000-0000-000000000201",
    "grade_20": "00000000-0000-0000-0000-000000000202",
    "part": "00000000-0000-0000-0000-000000000301",
    "part_2": "00000000-0000-0000-0000-000000000302",
    "process_forging": "00000000-0000-0000-0000-000000000401",
    "process_broaching": "00000000-0000-0000-0000-000000000402",
    "process_carburizing": "00000000-0000-0000-0000-000000000403",
    "process_qt": "00000000-0000-0000-0000-000000000404",
    "process_gear": "00000000-0000-0000-0000-000000000405",
    "process_final": "00000000-0000-0000-0000-000000000406",
    "stage_inward": "00000000-0000-0000-0000-000000000501",
    "stage_setup": "00000000-0000-0000-0000-000000000502",
    "stage_stage": "00000000-0000-0000-0000-000000000503",
    "stage_osp": "00000000-0000-0000-0000-000000000504",
    "stage_final": "00000000-0000-0000-0000-000000000505",
    "asset_cmm": "00000000-0000-0000-0000-000000000601",
    "asset_fixture": "00000000-0000-0000-0000-000000000602",
    "asset_gauge": "00000000-0000-0000-0000-000000000603",
    "inspection_plan": "00000000-0000-0000-0000-000000000701",
    "characteristic": "00000000-0000-0000-0000-000000000702",
    "test_plan": "00000000-0000-0000-0000-000000000703",
    "rmtc": "00000000-0000-0000-0000-000000000801",
    "inward": "00000000-0000-0000-0000-000000000802",
    "batch": "00000000-0000-0000-0000-000000000803",
    "osp_batch": "00000000-0000-0000-0000-000000000804",
    "osp_job": "00000000-0000-0000-0000-000000000805",
    "inspection": "00000000-0000-0000-0000-000000000806",
    "lab": "00000000-0000-0000-0000-000000000807",
    "dispatch": "00000000-0000-0000-0000-000000000808",
    "dispatch_batch": "00000000-0000-0000-0000-000000000809",
}


def _base(record_id: str) -> dict:
    return {
        "id": record_id,
        "tenant_id": DEMO_TENANT_ID,
        "created_at": "2026-07-01T09:00:00+05:30",
        "updated_at": "2026-07-30T18:00:00+05:30",
    }


def demo_store() -> dict[str, list[dict]]:
    parties = [
        {
            **_base(IDS["customer"]),
            "party_code": "C000100",
            "party_name": "Kessler + Co. GmbH & Co. KG",
            "party_types": ["CUSTOMER"],
            "country": "Germany",
            "state": "Baden-Württemberg",
            "city": "Abtsgmünd",
            "address": "Germany",
            "contact_person": "Quality Team",
            "email": "quality@example.com",
            "phone": "",
            "tax_identifier": "",
            "approval_status": "APPROVED",
            "status": "ACTIVE",
            "remarks": "Reference customer from the uploaded Customer Master.",
        },
        {
            **_base(IDS["supplier"]),
            "party_code": "S000104",
            "party_name": "Om Forge",
            "party_types": ["SUPPLIER"],
            "country": "India",
            "state": "Maharashtra",
            "city": "Ahmednagar",
            "address": "Ahmednagar",
            "contact_person": "",
            "email": "",
            "phone": "",
            "tax_identifier": "",
            "approval_status": "APPROVED",
            "status": "ACTIVE",
            "remarks": "Forging supplier from the uploaded Vendor Supplier Master.",
        },
        {
            **_base(IDS["steel_mill"]),
            "party_code": "MILL001",
            "party_name": "Approved Steel Mill",
            "party_types": ["STEEL_MILL"],
            "country": "India",
            "state": "Maharashtra",
            "city": "Pune",
            "address": "",
            "contact_person": "Metallurgy Team",
            "email": "",
            "phone": "",
            "tax_identifier": "",
            "approval_status": "APPROVED",
            "status": "ACTIVE",
            "remarks": "Representative approved steel source.",
        },
        {
            **_base(IDS["osp_vendor"]),
            "party_code": "OSP001",
            "party_name": "Unitherm Engineers Limited",
            "party_types": ["OSP_VENDOR", "SUPPLIER"],
            "country": "India",
            "state": "Maharashtra",
            "city": "Pune",
            "address": "",
            "contact_person": "Heat Treatment Quality",
            "email": "",
            "phone": "",
            "tax_identifier": "",
            "approval_status": "APPROVED",
            "status": "ACTIVE",
            "remarks": "Representative case carburizing source.",
        },
    ]

    grades = [
        {**_base(IDS["grade_16"]), "grade_code": "16MnCr5", "standard": "EN 10084", "revision": "Current", "effective_date": "2026-01-01", "status": "ACTIVE", "remarks": "Controlled part material grade."},
        {**_base(IDS["grade_20"]), "grade_code": "20MnCr5", "standard": "EN 10084", "revision": "Current", "effective_date": "2026-01-01", "status": "ACTIVE", "remarks": "Composition taken from the uploaded Material Grade Master."},
    ]

    elements = []
    chemistry = [
        ("C", 0.17, 0.21), ("Mn", 1.10, 1.30), ("Cr", 0.50, 0.90),
        ("P", 0.00, 0.025), ("S", 0.00, 0.025), ("Mo", 0.10, 0.25),
        ("Ni", 0.05, 0.15), ("Al", 0.02, 0.05), ("Cu", 0.02, 0.05),
    ]
    for idx, (element, minimum, maximum) in enumerate(chemistry, start=1):
        elements.append({
            **_base(f"00000000-0000-0000-0000-{900+idx:012d}"),
            "material_grade_id": IDS["grade_20"],
            "element": element,
            "minimum": minimum,
            "maximum": maximum,
            "unit": "%",
            "test_method": "Optical emission spectroscopy",
        })

    parts = [
        {
            **_base(IDS["part"]),
            "part_number": "71.784.3",
            "part_name": "Differential Spider",
            "customer_id": IDS["customer"],
            "material_grade_id": IDS["grade_16"],
            "drawing_number": "Finish drawing reference",
            "drawing_revision": "Current",
            "finished_weight_kg": 1.8,
            "forging_weight_kg": 2.35,
            "gross_weight_kg": 3.05,
            "section_size": "65 mm",
            "manufacturing_route": "Forging → Machining → Broaching → Case Carburizing → Final Inspection",
            "special_characteristics": [
                {"type": "JOMINY", "position": "4/16 in", "requirement": "28-32 HRC"},
                {"type": "JOMINY", "position": "5/16 in", "requirement": "27-30 HRC"},
                {"type": "JOMINY", "position": "6/16 in", "requirement": "25-28 HRC"},
                {"type": "HEAT_TREATMENT", "process": "Case Carburizing", "case_depth": "0.9-1.3 mm @ 513 HV1", "core_strength": "1100-1300 MPa"},
            ],
            "status": "ACTIVE",
            "remarks": "Reference part from the uploaded Part Master.",
        },
        {
            **_base(IDS["part_2"]),
            "part_number": "40286128",
            "part_name": "Differential Shaft",
            "customer_id": IDS["customer"],
            "material_grade_id": IDS["grade_20"],
            "drawing_number": "40286128",
            "drawing_revision": "N",
            "finished_weight_kg": 0.74,
            "forging_weight_kg": 0.92,
            "gross_weight_kg": 1.05,
            "section_size": "Round bar",
            "manufacturing_route": "Turning → Broaching → Heat Treatment → Grinding → Final Inspection",
            "special_characteristics": [],
            "status": "ACTIVE",
            "remarks": "Representative traceability part.",
        },
    ]

    processes = [
        {**_base(IDS["process_forging"]), "process_code": "P010", "process_name": "Forging", "process_type": "OUTSOURCED", "special_process": False, "cqi_standard": "", "status": "ACTIVE", "remarks": ""},
        {**_base(IDS["process_broaching"]), "process_code": "P020", "process_name": "Broaching", "process_type": "IN_HOUSE", "special_process": False, "cqi_standard": "", "status": "ACTIVE", "remarks": ""},
        {**_base(IDS["process_carburizing"]), "process_code": "P030", "process_name": "Case Carburizing", "process_type": "OUTSOURCED", "special_process": True, "cqi_standard": "CQI-9", "status": "ACTIVE", "remarks": ""},
        {**_base(IDS["process_qt"]), "process_code": "P040", "process_name": "Quench & Tempering", "process_type": "OUTSOURCED", "special_process": True, "cqi_standard": "CQI-9", "status": "ACTIVE", "remarks": ""},
        {**_base(IDS["process_gear"]), "process_code": "P050", "process_name": "Gear Shaping", "process_type": "OUTSOURCED", "special_process": False, "cqi_standard": "", "status": "ACTIVE", "remarks": ""},
        {**_base(IDS["process_final"]), "process_code": "P090", "process_name": "Final Inspection", "process_type": "IN_HOUSE", "special_process": False, "cqi_standard": "", "status": "ACTIVE", "remarks": ""},
    ]

    stages = [
        {**_base(IDS["stage_inward"]), "stage_code": "INWARD", "stage_name": "Raw Material Inward", "sequence_no": 10, "status": "ACTIVE"},
        {**_base(IDS["stage_setup"]), "stage_code": "SETUP", "stage_name": "Setup Approval", "sequence_no": 20, "status": "ACTIVE"},
        {**_base(IDS["stage_stage"]), "stage_code": "STAGE", "stage_name": "Stage Inspection", "sequence_no": 30, "status": "ACTIVE"},
        {**_base(IDS["stage_osp"]), "stage_code": "OSP", "stage_name": "OSP Receipt Inspection", "sequence_no": 40, "status": "ACTIVE"},
        {**_base(IDS["stage_final"]), "stage_code": "FINAL", "stage_name": "Final Inspection", "sequence_no": 50, "status": "ACTIVE"},
    ]

    assets = [
        {**_base(IDS["asset_cmm"]), "asset_code": "CMM-D9-01", "asset_name": "Coordinate Measuring Machine", "asset_type": "EQUIPMENT", "manufacturer": "Zeiss", "model": "CMM", "serial_number": "D9-CMM-01", "range_text": "900 x 1200 x 700 mm", "least_count": "0.001 mm", "location": "Metrology Lab", "calibration_frequency_days": 365, "last_calibration_date": "2026-01-15", "next_due_date": "2027-01-15", "status": "ACTIVE", "remarks": ""},
        {**_base(IDS["asset_fixture"]), "asset_code": "FIX-717843-01", "asset_name": "Spider Inspection Fixture", "asset_type": "FIXTURE", "manufacturer": "In-house", "model": "", "serial_number": "", "range_text": "", "least_count": "", "location": "Final Inspection", "calibration_frequency_days": 180, "last_calibration_date": "2026-06-01", "next_due_date": "2026-11-28", "status": "ACTIVE", "remarks": ""},
        {**_base(IDS["asset_gauge"]), "asset_code": "PG-40286128-01", "asset_name": "Plug Gauge", "asset_type": "GAUGE", "manufacturer": "Baker", "model": "GO / NO-GO", "serial_number": "PG-001", "range_text": "Drawing controlled", "least_count": "Attribute", "location": "Stage Inspection", "calibration_frequency_days": 90, "last_calibration_date": "2026-07-01", "next_due_date": "2026-09-29", "status": "ACTIVE", "remarks": ""},
    ]

    store = {
        "parties": parties,
        "material_grades": grades,
        "material_grade_elements": elements,
        "parts": parts,
        "part_supplier_links": [{
            **_base("00000000-0000-0000-0000-000000000901"),
            "part_id": IDS["part"], "supplier_id": IDS["supplier"], "steel_mill_id": IDS["steel_mill"],
            "supplier_part_number": "71.784.3", "approval_reference": "Approved source", "approved": True,
            "valid_from": "2026-01-01", "valid_to": None,
        }],
        "processes": processes,
        "inspection_stages": stages,
        "quality_assets": assets,
        "inspection_plans": [{
            **_base(IDS["inspection_plan"]), "part_id": IDS["part_2"], "process_id": IDS["process_final"],
            "inspection_stage_id": IDS["stage_final"], "plan_number": "IP-40286128-FINAL", "revision": "N",
            "effective_date": "2026-01-01", "sample_plan": "5 pieces per batch", "status": "APPROVED",
        }],
        "inspection_plan_characteristics": [{
            **_base(IDS["characteristic"]), "inspection_plan_id": IDS["inspection_plan"], "sequence_no": 10,
            "characteristic_no": "1", "characteristic": "Critical diameter", "specification": "As drawing",
            "lower_spec": 24.98, "upper_spec": 25.02, "unit": "mm", "characteristic_type": "VARIABLE",
            "special_class": "CC", "checking_aid_id": IDS["asset_cmm"], "checking_method": "CMM",
            "sample_size": 5, "frequency": "Every batch", "reaction_plan": "Stop, segregate and inform Quality Manager",
        }],
        "test_plans": [{
            **_base(IDS["test_plan"]), "part_id": IDS["part_2"], "process_id": IDS["process_carburizing"],
            "inspection_stage_id": IDS["stage_osp"], "plan_number": "TP-40286128-HT", "revision": "N",
            "test_type": "METLAB", "specification_reference": "Drawing and heat treatment specification",
            "frequency": "Every OSP batch", "sample_size": 1,
            "acceptance_criteria": {"case_depth": "As drawing", "hardness": "As drawing", "microstructure": "Acceptable"},
            "status": "APPROVED",
        }],
        "rmtc_approvals": [{
            **_base(IDS["rmtc"]), "rmtc_number": "RMTC-D9-2026-1478", "certificate_date": "2026-07-24",
            "certificate_reference": "MLAB_D9_2026_1478", "part_id": IDS["part_2"], "supplier_id": IDS["supplier"],
            "steel_mill_id": IDS["steel_mill"], "material_grade_id": IDS["grade_20"], "heat_number": "9346",
            "heat_code": "H9346-D9", "certificate_quantity": 8500, "chemistry_results": {"C": 0.19, "Mn": 1.20, "Cr": 0.74},
            "chemistry_compliance": "PASS", "chemistry_failures": [], "mechanical_results": {"tensile_mpa": 1180},
            "status": "APPROVED", "approved_at": "2026-07-24T16:00:00+05:30", "approved_by": None, "remarks": "Reference trace.",
        }],
        "inward_lots": [{
            **_base(IDS["inward"]), "inward_number": "INW-D9-2026-0714", "inward_date": "2026-07-25", "grn_number": "GRN-D9-260725-18",
            "invoice_number": "OF-260724-31", "part_id": IDS["part_2"], "supplier_id": IDS["supplier"], "rmtc_approval_id": IDS["rmtc"],
            "heat_number": "9346", "heat_code": "H9346-D9", "quantity_received": 8000, "quantity_accepted": 7950, "quantity_rejected": 50,
            "metallurgical_status": "PASS", "dimensional_status": "PASS", "status": "RELEASED", "remarks": "Released after inward inspection.",
        }],
        "production_batches": [
            {**_base(IDS["batch"]), "batch_code": "B-D9-9346-001", "part_id": IDS["part_2"], "inward_lot_id": IDS["inward"], "parent_batch_id": None,
             "heat_number": "9346", "heat_code": "H9346-D9", "vendor_batch_number": None, "current_process_id": IDS["process_broaching"],
             "work_order": "WO-D9-260726-04", "quantity_started": 4000, "quantity_available": 3680, "status": "IN_PROCESS", "remarks": "Main production batch."},
            {**_base(IDS["osp_batch"]), "batch_code": "OSP-B-D9-9346-01", "part_id": IDS["part_2"], "inward_lot_id": IDS["inward"], "parent_batch_id": IDS["batch"],
             "heat_number": "9346", "heat_code": "H9346-D9", "vendor_batch_number": "UTH-301-94", "current_process_id": IDS["process_carburizing"],
             "work_order": "WO-D9-260726-04", "quantity_started": 2000, "quantity_available": 1950, "status": "RELEASED", "remarks": "OSP child batch."},
        ],
        "batch_movements": [
            {**_base("00000000-0000-0000-0000-000000000910"), "batch_id": IDS["batch"], "movement_type": "PROCESS_TRANSFER", "from_process_id": IDS["process_broaching"], "to_process_id": IDS["process_carburizing"], "quantity": 2000, "movement_date": "2026-07-27", "reference": "OSP-D9-2026-032", "remarks": "Sent for case carburizing."},
        ],
        "osp_jobs": [{
            **_base(IDS["osp_job"]), "osp_job_number": "OSP-D9-2026-032", "source_batch_id": IDS["batch"], "osp_batch_id": IDS["osp_batch"],
            "part_id": IDS["part_2"], "vendor_id": IDS["osp_vendor"], "process_id": IDS["process_carburizing"], "dispatch_date": "2026-07-27",
            "dispatch_challan": "DC-D9-260727-18", "quantity_dispatched": 2000, "expected_return_date": "2026-07-30",
            "process_specification": "Case carburizing as drawing", "required_tests": ["METLAB", "HARDNESS"], "receipt_date": "2026-07-30",
            "receipt_challan": "RCV-UTH-260730", "vendor_batch_number": "UTH-301-94", "quantity_received": 2000,
            "quantity_rejected_at_receipt": 0, "receipt_status": "COMPLETE", "inspection_status": "PASS", "status": "COMPLETED", "receipt_remarks": "Released.",
        }],
        "inspection_reports": [{
            **_base(IDS["inspection"]), "report_number": "FIR-D9-2026-011", "report_type": "FINAL_INSPECTION", "inspection_plan_id": IDS["inspection_plan"],
            "inspection_stage_id": IDS["stage_final"], "part_id": IDS["part_2"], "batch_id": IDS["osp_batch"], "inward_lot_id": None,
            "osp_job_id": IDS["osp_job"], "inspection_date": "2026-07-31", "sample_size": 5, "accepted_quantity": 1950,
            "rejected_quantity": 0, "inspector": "Quality Engineer", "overall_result": "PASS", "status": "APPROVED", "remarks": "Final release inspection.",
        }],
        "inspection_results": [{
            **_base("00000000-0000-0000-0000-000000000920"), "inspection_report_id": IDS["inspection"], "inspection_plan_characteristic_id": IDS["characteristic"],
            "characteristic_no": "1", "characteristic": "Critical diameter", "specification": "25.00 ± 0.02", "lower_spec": 24.98,
            "upper_spec": 25.02, "checking_aid": "CMM-D9-01", "checking_aid_id": IDS["asset_cmm"], "observations": [25.001, 25.003, 25.000, 24.999, 25.002],
            "attribute_result": None, "result": "PASS", "remarks": "",
        }],
        "lab_tests": [{
            **_base(IDS["lab"]), "report_number": "MLAB-D9-2026-1478", "test_type": "METLAB", "test_plan_id": IDS["test_plan"], "part_id": IDS["part_2"],
            "batch_id": IDS["osp_batch"], "inward_lot_id": None, "osp_job_id": IDS["osp_job"], "test_date": "2026-07-30", "sample_reference": "UTH-301-94-S1",
            "specification_reference": "Heat treatment drawing", "results": {"surface_hardness_hrc": 60, "case_depth_mm": 1.1, "microstructure": "Acceptable"},
            "overall_result": "PASS", "status": "APPROVED", "remarks": "OSP quality release evidence.",
        }],
        "dispatches": [{
            **_base(IDS["dispatch"]), "dispatch_number": "DISP-D9-2026-118", "dispatch_date": "2026-08-01", "customer_id": IDS["customer"],
            "invoice_number": "INV-D9-260801-04", "destination": "Germany", "quality_release_reference": "FIR-D9-2026-011",
            "quality_release_approved_by": "Quality Manager", "status": "DISPATCHED", "remarks": "Customer shipment.",
        }],
        "dispatch_batches": [{
            **_base(IDS["dispatch_batch"]), "dispatch_id": IDS["dispatch"], "batch_id": IDS["osp_batch"], "release_inspection_id": IDS["inspection"], "quantity": 1200,
        }],
    }
    return deepcopy(store)
