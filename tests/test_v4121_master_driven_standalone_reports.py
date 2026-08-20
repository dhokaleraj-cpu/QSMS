from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_version_and_migration():
    assert (ROOT / "VERSION").read_text().strip() in {"4.12.1", "4.12.2", "4.12.3", "4.12.4"}
    migration = ROOT / "supabase/migrations/20260819170000_qcms_master_driven_standalone_reports_v4121.sql"
    assert migration.exists()
    sql = migration.read_text()
    for token in ("customer_id", "material_grade_id", "batch_number", "supplier_reference_number", "supply_condition", "reference_text", "qcms_fill_report_part_master_context"):
        assert token in sql


def test_standalone_reports_are_master_driven_and_auto_layout():
    met = (ROOT / "app_pages/metlab_report.py").read_text()
    dim = (ROOT / "app_pages/dimensional_report.py").read_text()
    service = (ROOT / "core/inspection_service.py").read_text()
    for source in (met, dim):
        for token in ("Customer", "Material Grade", "Batch Number", "Supplier Invoice / Reference", "Auto Layout from Part Master", "OSP Process", "Process Specification"):
            assert token in source
        assert '"customer_id": part.get("customer_id")' in source
        assert '"material_grade_id": part.get("material_grade_id")' in source
    assert "def standalone_part_context" in service
    assert "def standalone_osp_process_groups" in service
    assert "def auto_standalone_plan" in service
    assert 'scope == "FINAL_DISPATCH_STAGE" and layout_type.upper() == "METLAB"' in service


def test_controlled_pdfs_include_lab_report_header_context():
    report = (ROOT / "core/reporting.py").read_text()
    for token in ("Customer", "Supplier / OSP Vendor", "Material Used", "Supplier Invoice / Reference", "Quantity (pcs)", "Heat Number", "Heat Code", "Supplier / HT / OSP Batch", "Internal / FSI Batch", "Drawing / Revision", "Sample / Reference"):
        assert token in report
    assert "FINAL METALLURGICAL TEST REPORT" in report
    assert "RAW MATERIAL DIMENSIONAL INSPECTION REPORT" in report


def test_supplier_and_internal_batch_are_distinct_in_standalone_reports():
    for rel in ("app_pages/metlab_report.py", "app_pages/dimensional_report.py"):
        text = (ROOT / rel).read_text()
        assert "Supplier / HT / OSP Batch Number" in text
        assert "Internal / FSI Batch Number" in text
        assert '"vendor_batch_number_snapshot": vendor_batch_number.strip() or None' in text
    reporting = (ROOT / "core/reporting.py").read_text()
    assert "Supplier / HT / OSP Batch" in reporting
    assert "Internal / FSI Batch" in reporting
