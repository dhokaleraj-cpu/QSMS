"""R39: Android app - OSP parity with the web R37 / R38 OSP page (one Material Out + Returnable Delivery Challan form,
challan register, record Details / Print / Vendor returns, customer-safe challan, inspection queues + layout fallback).
Static checks of the Java sources."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mobile/android_qcms_app/app/src/main/java/com/fourstar/qcmsapp"


def read(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def test_osp_files_exist():
    for name in ("InspOsp.java", "InspOspOutScreen.java", "OspChallan.java", "OspChallanEdit.java", "OspChallanPdf.java",
                 "OspRecordScreen.java", "OspRecordView.java", "OspMoRegister.java", "OspQueueScreen.java"):
        assert (SRC / name).exists(), name


def test_one_form_saves_material_out_then_challan_with_recovery():
    out = read("InspOspOutScreen.java")
    # challan validated BEFORE the stock-allocating RPC (unchanged contract)
    assert out.index("OspChallan.cleanHeader(challanHeader)") < out.index('"qcms_create_osp_material_out"')
    assert out.index("OspChallan.duplicateNumber(") < out.index('"qcms_create_osp_material_out"')
    assert '.put("p_request_id", req).put("p_header", header).put("p_lines", clean)' in out
    assert "OspChallan.saveWithRetry(" in out and "OspChallan.PENDING.put(" in out
    assert "Do NOT create the Material Out again" in out
    ch = read("OspChallan.java")
    assert "qcms_next_osp_challan_number" in ch and '"JWC" + code' in ch
    assert '"osp_challans"' in ch and '"osp_challan_lines"' in ch and '"osp_challan_returns"' in ch
    assert "existing == null ? null : s(existing, \"id\")" in ch   # retry re-uses an inserted header


def test_register_one_row_per_material_out_with_challan_number():
    reg = read("OspMoRegister.java")
    for col in ("Challan No", "Material Out", "OSP Vendor", "FSI Part", "Heat Numbers", "Returned pcs", "Rejected pcs", "Balance pcs", "E-mailed"):
        assert f'"{col}"' in reg, col
    assert "osp_challan_returns" in reg and "osp_challans" in reg
    for f in ("Open at vendor", "Fully returned", "Challan not created"):
        assert f in reg
    cat = read("CatInspection.java")
    assert ".custom(OspMoRegister::new)" in cat and '"osp_inspection_queues"' in cat and "OspQueueScreen::new" in cat


def test_record_view_details_print_returns_and_draft():
    view = read("OspRecordView.java")
    assert '{"Details", "Print", "Vendor returns"}' in view
    assert "payloadForDocument" in view and "DRAFT" in view
    assert "OspChallan.saveReturn(" in view and "OspChallan.deleteReturn(" in view
    rec = read("RecordScreen.java")
    assert 'if ("osp_material_outs".equals(m.table)) add(OspRecordView.build(' in rec


def test_challan_is_customer_safe():
    ch = read("OspChallan.java")
    assert "return vendorSafe(p);" in ch
    for key in ('"customer_name"', '"customer_part_number"', '"customer_po_number"', '"customer_delivery_date"'):
        assert key in ch
    assert 'low.startsWith("customer_")' in ch
    view = read("OspRecordView.java")
    assert "OspChallan.payloadForChallan(api, d.challan)" in view   # every print goes through the vendor-safe payload


def test_osp_queues_follow_web_r37_rules():
    osp = read("InspOsp.java")
    for name in ("inspectionGateClosed", "jobsForInspection", "releasedWithoutReport", "nameMatchedLayouts", "fallbackLayouts", "ospPlans"):
        assert f" {name}(" in osp, name
    assert '"sample_gate_status"' in osp and '"receipt_quality_disposition"' in osp
    for screen in ("InspDimScreen.java", "InspLabScreen.java"):
        assert "InspOsp.ospPlans(api," in read(screen), screen


def test_no_service_role_in_osp_sources():
    for name in ("OspChallan.java", "OspRecordView.java", "OspMoRegister.java", "OspQueueScreen.java", "InspOspOutScreen.java", "OspChallanEdit.java"):
        assert "service_role" not in read(name), name
