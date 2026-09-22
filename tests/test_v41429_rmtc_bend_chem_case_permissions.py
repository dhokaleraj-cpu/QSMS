from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_v41429_release_identity_source_only_schema_contract():
    assert tuple(map(int, text("VERSION").strip().split("."))) >= (4, 14, 29)
    assert "metlab_bend_test_subcategory" in text("DEPLOYMENT_MANIFEST.json")
    manifest = json.loads(text("DEPLOYMENT_MANIFEST.json"))
    assert tuple(map(int, manifest["version"].split("."))) >= (4, 14, 29)
    assert "metlab_bend_test_subcategory" in manifest["features"]
    if manifest["version"] in {"4.14.35", "4.14.36", "4.14.37", "4.14.38", "4.14.39"}:
        expected_schema = "4.14.36" if manifest["version"] in {"4.14.37", "4.14.38", "4.14.39"} else manifest["version"]
        assert manifest["database_schema_required"] == expected_schema
        assert manifest["database_migration_required"] is True
        assert manifest["source_only_updater"] is False
    else:
        assert manifest["database_schema_required"] == "4.14.28"
        assert manifest["database_migration_required"] is False
        assert manifest["source_only_updater"] is True


def test_rmtc_approved_source_selector_joins_part_approval_and_rm_detail():
    service = text("core/rmtc_service.py")
    page = text("app_pages/rmtc_pages.py")
    assert "def approved_source_options" in service
    assert "part_supplier_links" in service
    assert "part_raw_material_details" in service
    assert "source_ready" in service
    assert "svc.approved_source_options(primary_id)" in page
    assert "Approved Raw Material Source" in page
    assert "source.get('raw_material_detail_id')" in page
    assert "Complete the Raw Material Details row in Part Master first" in page


def test_section_rights_catalog_covers_every_module():
    access = text("core/access.py")
    page = text("app_pages/user_access.py")
    module_keys = [
        "PART_MASTER", "MATERIAL_GRADE", "REFERENCE_MASTERS", "EMPLOYEE_MASTER",
        "RMTC_ENTRY", "MATERIAL_INWARD", "OSP_TRANSACTIONS", "INSPECTION_LAYOUTS",
        "DIMENSIONAL_REPORT", "METLAB_REPORT", "NPD_APQP", "QC_CALCULATION_TOOLS",
        "COMPLAINT_MANAGEMENT", "CALIBRATION_VALIDATION", "SUPPLY_CHAIN", "USER_ACCESS",
    ]
    for key in module_keys:
        assert f'("{key}",' in access
        assert f'("{key}",' in page
    assert "Section rights are available for all" in page
    assert '"Module": MODULE_LABELS.get(mod, mod)' in page


def test_bend_test_is_metlab_subcategory_with_controlled_starter_format():
    metadata = text("core/inspection_layout_metadata.py")
    layout = text("app_pages/inspection_layouts.py")
    reporting = text("core/reporting.py")
    for token in (
        'BEND_TEST = "BEND_TEST"', "BEND_TEST_DEFAULT_CHARACTERISTICS", "Baking Temperature",
        "Baking Time", "Base Metal Hardness below plating", '"Load"', '"CHT"',
        "Bend Angle", "Bend Test Status", "Plating Surface Condition",
    ):
        assert token in metadata
    assert "Inspection Method / Sub Category" in layout
    assert "BEND TEST REPORT" in layout
    assert 'title = (' in reporting and '"BEND TEST REPORT" if is_bend_test' in reporting
    assert '"BAKING / AGING"' in reporting
    assert '"BEND TEST RESULTS"' in reporting
    assert '"BEND TEST EVIDENCE / PART PHOTOGRAPHS"' in reporting


def test_case_depth_explicit_checkbox_supports_multiple_controlled_locations():
    layout = text("app_pages/inspection_layouts.py")
    metlab = text("app_pages/metlab_report.py")
    metadata = text("core/inspection_layout_metadata.py")
    assert "Case Depth Traverse" in layout
    assert "Traverse Location" in layout
    assert 'data["case_depth_traverse"]' in metadata
    assert 'data["case_depth_location"]' in metadata
    assert 'bool(row.get("case_depth_traverse"))' in metlab
    assert 'row.get("case_depth_location")' in metlab
    assert "Multiple rows create multiple traverse locations" in layout


def test_metlab_reference_picker_is_reusable_and_persisted_in_report_results():
    metlab = text("app_pages/metlab_report.py")
    catalog = text("core/catalog.py")
    assert "def _reference_controls" in metlab
    assert "Specification Reference" in metlab
    assert "Reference Documents / Statements" in metlab
    assert 'catalog.suggestions("metlab.reference_document")' in metlab
    assert 'catalog.remember_many("metlab.reference_document", reference_documents)' in metlab
    assert '"reference_documents": reference_documents' in metlab
    assert "qsms_remember_master_value" in catalog


def test_chemical_analysis_is_horizontal_and_attached_order_is_enforced():
    metlab = text("app_pages/metlab_report.py")
    reporting = text("core/reporting.py")
    exact_order = '("C", "Mn", "Si", "S", "P", "Cr", "Ni", "Mo", "V", "Al", "Cu", "Nb", "Ti")'
    assert exact_order in metlab
    assert exact_order in reporting
    assert "_chemical_horizontal_models" in metlab
    assert "MetLAB Achieved · enter results horizontally" in metlab
    assert "_chemical_horizontal_report_table" in reporting
    assert '"Spec. Min"' in reporting and '"Spec. Max"' in reporting
    assert '"RMTC Achieved"' in reporting and '"MetLAB Achieved"' in reporting
    assert "Al/N2 Ratio" in metlab and "Al/N2 Ratio" in reporting


def test_conclusion_remark_and_color_font_highlighting_are_in_outputs():
    metlab = text("app_pages/metlab_report.py")
    reporting = text("core/reporting.py")
    assert "Conclusion Remark (optional)" in metlab
    assert '"conclusion_remark": conclusion_remark.strip() or None' in metlab
    assert "def _quality_conclusion_table" in reporting
    assert "Helvetica-Bold" in reporting
    assert "Helvetica-Oblique" in reporting
    assert 'colors.HexColor("#E0F2FE")' in reporting
    assert 'colors.HexColor("#FFF7ED")' in reporting
    assert "PatternFill" in reporting


def test_osp_selectors_expose_batch_identity_including_source_batch_lot():
    osp = text("app_pages/osp_transactions.py")
    for token in ("FSI Batch Number", "Vendor Batch Number", "Source Batch / Lot", "SRC-"):
        assert token in osp
    assert '"FSI Batch Number": r.get("osp_batch_code")' in osp
