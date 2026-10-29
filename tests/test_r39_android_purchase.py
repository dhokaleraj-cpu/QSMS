"""R39: Android app - Purchase parity: R37b PO amendment + price history by row id, R38 approved PO auto-download
(supplier-safe), Indirect Purchase module (requisitions, POs, approval, PDF, e-mail). Static checks of the Java sources."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mobile/android_qcms_app/app/src/main/java/com/fourstar/qcmsapp"


def read(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def test_po_amendment_port():
    svc = read("SupSvc.java")
    for name in ("amendPurchaseOrder(", "amendmentPriceSuggestion(", "purchaseOrderAmendments(", "poDisplayNumber(", "samePriceUom("):
        assert name in svc, name
    assert '"supply_po_amendments"' in svc and '"supply_po_amendment_lines"' in svc
    assert '.put("refresh_master_data", false)' in svc
    assert '"PO " + poNumber + " Amd " + amendmentNo + ": " + reason' in svc
    assert "cannot be below the quantity already received" in svc
    assert '.put("amendment_effective_date", effective)' in svc
    screen = read("SupPoAmendScreen.java")
    assert "a.confirmPassword(" in screen and "amendPurchaseOrder(" in screen and "Effective Date" in screen
    assert "new SupPoAmendScreen(a, id)" in read("PoDetailScreen.java")
    assert "SupPoAmendScreen" in read("CatSupply.java")
    pdf = read("SndPoPdf.java")
    assert "amendmentCaption(" in pdf and "amendmentHistoryPages()" in pdf and "historyContinuationPages(" in pdf


def test_price_history_saved_by_row_id():
    plan = read("PriceHistoryPlan.java")
    assert "no longer exists for the selected Part / Supplier / Raw Material" in plan
    assert "Each price revision needs its own Start Date" in plan and "closed on" in plan
    assert "shrinking" in plan and "growing" in plan
    screen = read("MstPartPriceScreen.java")
    assert "PriceHistoryPlan.save(api, partId, supplierId, rawId, edited)" in screen
    assert 'p.put("id", Lookups.j(row, "id"))' in screen
    assert "MstSave.saveRows(api, \"part_supplier_price_history\"" not in screen


def test_approved_po_auto_download_supplier_safe():
    po = read("PoDetailScreen.java")
    assert "autoDownloadApproved(a, id)" in po
    assert "SndData.supplierSafe(po)" in po and "SndFiles.saveToDownloads(" in po and "SndFiles.open(" in po
    data = read("SndData.java")
    assert 'out.put("show_source_reference", false)' in data
    assert '"_Amd" + amd' in data
    send = read("SndPoSend.java")
    assert "SndData.supplierSafe(po)" in send and "SndData.supplierSafeOptions(sendOptions)" in send


def test_indirect_purchase_module_registered_and_wired():
    cat = read("CatSupply.java")
    for key in ('"indirect_purchase_orders"', '"indirect_po_approval"', '"indirect_requisitions"', '"indirect_grns"', '"indirect_items"'):
        assert key in cat, key
    scr = read("IndScreens.java")
    for name in ("class PoList", "class PoView", "class PoEdit", "class Approvals", "class Requisitions", "class PrEdit"):
        assert name in scr, name
    for call in ("svc.approvePo(", "svc.rejectPo(", ".submitPo(", "cancelPo(", "createPo(", "updatePo(", "requisitionPrefill(",
                 "decideRequisition(", "IndPdf.poById(", '"INDIRECT_PO_RELEASED"', '"INDIRECT_PO_APPROVAL_PENDING"', "qcms_notification_outbox"):
        assert call in scr, call
    svc = read("IndSvc.java")
    assert 'MODULE_KEY = "INDIRECT_PURCHASE"' in svc and "qcms_indirect_purchase_can" in svc
    for rpc in ("qcms_approve_indirect_po", "qcms_reject_indirect_po", "qcms_next_indirect_number"):
        assert rpc in svc, rpc


def test_no_service_role_or_customer_data_on_supplier_documents():
    for name in ("IndScreens.java", "IndSvc.java", "IndPdf.java", "SupPoAmendScreen.java", "PriceHistoryPlan.java", "SupPdfKit.java"):
        assert "service_role" not in read(name), name
    assert "customer" not in read("IndPdf.java").lower().replace("no customer data", "").replace("nothing customer-related", "")
