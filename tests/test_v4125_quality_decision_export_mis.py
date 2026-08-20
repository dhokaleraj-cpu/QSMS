from pathlib import Path

from core.reporting import quality_record_excel_bytes

ROOT = Path(__file__).resolve().parents[1]


def test_release_and_visible_build_marker():
    assert (ROOT / "VERSION").read_text().strip() in {"4.12.5", "4.12.6", "4.12.7", "4.12.8"}
    assert "4125-QUALITY-DECISION-EXPORT-MIS" in (ROOT / "core/ui.py").read_text()
    assert "4125-QUALITY-DECISION-EXPORT-MIS" in (ROOT / "core/auth.py").read_text()


def test_monthly_order_dispatch_summary_keeps_customer_and_part_identity():
    service = (ROOT / "core/supply_chain_service.py").read_text()
    assert '"Customer Name": customer' in service
    assert '"Part Number": part_number' in service
    assert '"Part Description": part_description' in service
    assert 'str(row.get("Customer") or "-")' in service
    assert 'str(row.get("Part Number") or "-")' in service
    assert '"Pending Dispatch pcs": max(ordered - dispatched, 0)' in service


def test_metlab_and_dimensional_have_conclusion_final_decision_and_exports():
    for rel in ("app_pages/metlab_report.py", "app_pages/dimensional_report.py"):
        text = (ROOT / rel).read_text()
        for token in ("Conclusion", "Final Decision", "Decision Reason", "Download / Print PDF", "Download Excel Report", "PDF / EXCEL / PRINT EXPORT"):
            assert token in text
    reporting = (ROOT / "core/reporting.py").read_text()
    assert '"Conclusion", conclusion' in reporting
    assert '"Final Decision", overall' in reporting
    assert '"Decision Reason", decision_reason' in reporting


def test_standalone_final_decision_does_not_require_inward_gate_rpc():
    service = (ROOT / "core/inspection_service.py").read_text()
    assert "not record.get(\"inward_lot_id\") and not record.get(\"osp_job_id\")" in service
    assert "_standalone_final_payload" in service
    assert 'return self.repo.update("inspection_reports", report_id, payload)' in service
    assert 'return self.repo.update("lab_tests", report_id, payload)' in service


def test_quality_record_excel_contains_controlled_summary_and_decision_sheet():
    payload = {
        "record": {
            "report_number": "QC-001", "inspection_date": "2026-08-20", "remarks": "All dimensions conform.",
            "disposition": "ACCEPTED", "disposition_reason": "", "status": "FINAL", "overall_result": "PASS",
        },
        "part": {"part_number": "40256626", "part_name": "Diff Shaft"},
        "customer": {"party_name": "Customer A"},
        "supplier": {"party_name": "Supplier A"},
        "material_grade": {"grade_code": "20MnCr5"},
        "results": [{"sequence_no": 1, "characteristic": "Diameter", "specification": "10 ±0.1", "observations": [10.01, 10.02], "result": "PASS"}],
    }
    data = quality_record_excel_bytes(payload, "DIMENSIONAL")
    assert data[:2] == b"PK"
    assert len(data) > 3000


def test_v4125_requires_no_manual_supabase_sql():
    assert list((ROOT / "supabase/migrations").glob("*v4125*.sql")) == []
