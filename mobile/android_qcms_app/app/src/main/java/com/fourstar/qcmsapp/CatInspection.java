package com.fourstar.qcmsapp;

import java.util.List;

/** Quality tab · Inspection (Dimensional, MetLAB, Bend Test, Inspection Layouts) and OSP (outside processing). */
public final class CatInspection {
    private CatInspection() { }

    static final String INSPECTION = "Inspection";
    static final String OSP = "OSP (outside processing)";

    private static final String[][] RESULT_COLS = {
        {"sequence_no", "Seq"}, {"characteristic_no", "Sr No"}, {"characteristic", "Parameter"}, {"specification", "Specification"},
        {"lower_spec", "Min"}, {"upper_spec", "Max"}, {"unit", "Unit"}, {"checking_aid", "Checking Aid"}, {"observations", "Actual Values"},
        {"applicability", "Applicability"}, {"result", "Result"}, {"remarks", "Remark"}};

    public static void register(List<Module> list) {
        // ---------------------------------------------------------------- Dimensional
        list.add(new Module("dimensional_reports", "Dimensional Reports", Catalog.QUALITY, INSPECTION, "inspection_reports")
            .desc("Dimensional inspection · linked Material Inward, standalone stage or OSP")
            .filter("&report_type=eq.DIMENSIONAL")
            .titleField("report_number")
            .col("report_number", "Report Number").col("inspection_date", "Date").col("part_id", "Part Number").col("supplier_id", "Supplier")
            .col("heat_number", "Heat Number").col("batch_number", "Batch Number").col("layout_name_snapshot", "Layout")
            .col("inspection_scope", "Report Stage").col("production_quantity_pcs", "Production pcs").col("remarks", "Conclusion")
            .col("overall_result", "Result").col("disposition", "Final Decision").col("disposition_reason", "Decision Reason").col("status", "Status")
            .statuses("DRAFT", "ON_HOLD", "FINAL")
            .editor((a, id, prefill) -> new InspDimScreen(a, id, prefill))
            .action("Finalize Dimensional Decision", "status!=FINAL", (a, row, refresh) -> InspUtil.finalizeAction(a, "inspection_reports", row, refresh))
            .action("Controlled amendment (reopen to Draft with password)", "status!=DRAFT|EMPTY", (a, row, refresh) -> {
                boolean osp = !Lookups.j(row, "osp_job_id").isEmpty();
                if (osp && !"FINAL".equalsIgnoreCase(Lookups.j(row, "status"))) { a.toast("OSP reports that are not FINAL stay editable - use Edit."); return; }
                InspUtil.amendAction(a, "inspection_reports", osp ? "OSP DIMENSIONAL" : "DIMENSIONAL_REPORT", row, refresh);
            })
            .action("Attach report copy", "status=DRAFT|EMPTY", InspUtil::dimensionalUploadAction)
            .child("Inspection results", "inspection_results", "inspection_report_id", "sequence_no.asc", RESULT_COLS)
            .attach("DIMENSIONAL_REPORT", "dimensional-report"));

        // ---------------------------------------------------------------- MetLAB (without bend tests)
        list.add(new Module("metlab_reports", "MetLAB Reports", Catalog.QUALITY, INSPECTION, "lab_tests")
            .desc("Metallurgical laboratory reports · raw material inward, standalone stage or OSP")
            .filter("&test_type=eq.METLAB&or=(results->>inspection_method.is.null,results->>inspection_method.neq.BEND_TEST)")
            .titleField("report_number")
            .col("report_number", "Report Number").col("test_date", "Date").col("part_id", "Part Number").col("supplier_id", "Supplier")
            .col("osp_vendor_id", "OSP Vendor").col("heat_number", "Heat Number").col("batch_number", "Batch Number")
            .col("layout_name_snapshot", "Layout").col("inspection_scope", "Report Stage").col("sample_reference", "Sample Reference")
            .col("remarks", "Conclusion").col("overall_result", "Result").col("disposition", "Final Decision").col("status", "Status")
            .statuses("DRAFT", "ON_HOLD", "FINAL")
            .editor((a, id, prefill) -> new InspLabScreen(a, id, prefill, false))
            .action("Finalize MetLAB Decision", "status!=FINAL", (a, row, refresh) -> InspUtil.finalizeAction(a, "lab_tests", row, refresh))
            .action("Controlled amendment (reopen to Draft with password)", "status!=DRAFT|EMPTY", (a, row, refresh) -> amendLab(a, row, refresh))
            .action("Upload report copy / photo", "status=DRAFT|EMPTY", InspUtil::metlabUploadAction)
            .attach("METLAB_REPORT", "metlab-report"));

        // ---------------------------------------------------------------- Bend test (lab_tests, inspection_method BEND_TEST)
        list.add(new Module("bend_tests", "Bend Test Reports", Catalog.QUALITY, INSPECTION, "lab_tests")
            .desc("Controlled Bend Test reports (MetLAB engine, Bend Test layouts)")
            .filter("&test_type=eq.METLAB&results->>inspection_method=eq.BEND_TEST")
            .titleField("report_number")
            .col("report_number", "Report Number").col("test_date", "Date").col("part_id", "Part Number").col("supplier_id", "Supplier")
            .col("heat_number", "Heat Number").col("batch_number", "Batch Number").col("layout_name_snapshot", "Layout")
            .col("inspection_scope", "Report Stage").col("sample_reference", "Sample Reference").col("remarks", "Conclusion")
            .col("overall_result", "Result").col("disposition", "Final Decision").col("status", "Status")
            .statuses("DRAFT", "ON_HOLD", "FINAL")
            .editor((a, id, prefill) -> new InspLabScreen(a, id, prefill, true))
            .action("Finalize Bend Test Decision", "status!=FINAL", (a, row, refresh) -> InspUtil.finalizeAction(a, "lab_tests", row, refresh))
            .action("Controlled amendment (reopen to Draft with password)", "status!=DRAFT|EMPTY", (a, row, refresh) -> amendLab(a, row, refresh))
            .action("Upload report copy / photo", "status=DRAFT|EMPTY", InspUtil::metlabUploadAction)
            .attach("METLAB_REPORT", "metlab-report"));

        // ---------------------------------------------------------------- Inspection layouts
        list.add(new Module("inspection_layouts", "Inspection Layouts", Catalog.QUALITY, INSPECTION, "inspection_plans")
            .desc("Layout Master · Part + Process + Stage characteristics for Dimensional / MetLAB / Bend Test")
            .titleField("plan_number").order("plan_number.asc")
            .col("plan_number", "Plan Number").col("revision", "Revision").col("layout_type", "Layout Type").col("inward_type", "Inward Type")
            .col("layout_name", "Layout Name").col("part_id", "Part Number").col("process_id", "Process").col("inspection_stage_id", "Stage")
            .col("inspection_method", "Inspection Method").col("default_sample_size", "Samples").col("format_number", "Format").col("status", "Status")
            .statuses("DRAFT", "APPROVAL_PENDING", "APPROVED", "SUPERSEDED")
            .editor((a, id, prefill) -> new InspLayoutScreen(a, id, prefill != null && prefill.optBoolean("bend", false)))
            .action("Submit for approval", "status=DRAFT|EMPTY", (a, row, refresh) -> InspLayoutScreen.setStatus(a, row, "APPROVAL_PENDING", refresh))
            .action("Approve layout", "status=DRAFT|APPROVAL_PENDING|EMPTY", (a, row, refresh) -> InspLayoutScreen.setStatus(a, row, "APPROVED", refresh))
            .action("Supersede layout", "status=APPROVED|APPROVAL_PENDING", (a, row, refresh) -> InspLayoutScreen.setStatus(a, row, "SUPERSEDED", refresh))
            .action("Return to Draft", "status=APPROVAL_PENDING|SUPERSEDED", (a, row, refresh) -> InspLayoutScreen.setStatus(a, row, "DRAFT", refresh))
            .action("New Bend Test layout", "", (a, row, refresh) -> a.push(new InspLayoutScreen(a, null, true)))
            .child("Characteristics", "inspection_plan_characteristics", "inspection_plan_id", "sequence_no.asc", new String[][]{
                {"sequence_no", "Seq"}, {"characteristic_no", "No"}, {"characteristic", "Parameter"}, {"specification", "Specification"},
                {"lower_spec", "Min"}, {"upper_spec", "Max"}, {"unit", "Unit"}, {"characteristic_type", "Type"}, {"checking_aid_text", "Checking Aid"},
                {"sample_size", "Samples"}, {"allow_na", "Allow NA"}, {"is_mandatory", "Mandatory"}, {"status", "Status"}}));

        // ---------------------------------------------------------------- OSP material out
        list.add(new Module("osp_material_out", "OSP Material Out", Catalog.QUALITY, OSP, "osp_material_outs")
            .desc("Material Out = Returnable Delivery Challan (one form) · record: Details · Print · Vendor returns")
            .titleField("material_out_number").status("")
            .col("material_out_number", "Material Out").col("created_at", "Created")
            // R39: new = one Material Out + challan form; Edit = "Correct challan details" (Material Out + challan together)
            .editor((a, id, prefill) -> id == null ? new InspOspOutScreen(a, null) : new OspChallanEdit(a, id, null))
            // R39 (web R38 section B): register = one row per Material Out with its challan number, balances and challan state
            .custom(OspMoRegister::new)
            .readOnly()
            .action("Delete Material Out document", "", InspOsp::deleteMaterialOut)
            .child("Heat lines (OSP jobs)", "osp_jobs", "material_out_id", "material_out_line_no.asc", new String[][]{
                {"material_out_line_no", "Line"}, {"osp_job_number", "OSP Job"}, {"part_id", "Part"}, {"vendor_id", "OSP Vendor"},
                {"dispatch_date", "Material Out Date"}, {"dispatch_challan", "Challan"}, {"quantity_dispatched", "Out Qty pcs"},
                {"sample_gate_status", "Sample Gate"}, {"quantity_received", "Received pcs"}, {"receipt_quality_disposition", "Receipt Decision"}, {"status", "Status"}}));

        // ---------------------------------------------------------------- OSP register (one heat line = one OSP job)
        list.add(new Module("osp_register", "OSP Register", Catalog.QUALITY, OSP, "v_qsms_osp_register")
            .desc("Heat-wise OSP jobs · sample receipt, OSP inward and the OSP quality gate")
            .titleField("osp_job_number")
            .col("osp_job_number", "OSP Job").col("dispatch_date", "Material Out Date").col("part_number", "Part Number").col("heat_number", "Heat Number")
            .col("osp_batch_code", "FSI Batch Number").col("vendor_name", "OSP Vendor").col("process_name", "Process")
            .col("quantity_dispatched", "Out Qty pcs").col("vendor_batch_number", "Vendor Batch").col("sample_gate_status", "Sample Gate")
            .col("receipt_number", "OSP Inward").col("quantity_received", "Inward Qty pcs").col("receipt_quality_disposition", "Receipt Decision")
            .col("production_available_quantity", "Production Qty Available").col("status", "Status")
            .statuses("AT_VENDOR", "COMPLETED", "REJECTED", "CANCELLED")
            .noEdit().readOnly()
            .action("Material Out / Challan record (Details · Print · Vendor returns)", "", OspRecordScreen::open)
            .action("Sample Receipt", "status!=REJECTED|CANCELLED", InspOsp::sampleReceipt)
            .action("Sample Dimensional inspection", "sample_received_date!=EMPTY", (a, row, refresh) -> InspOsp.openInspection(a, row, "DIMENSIONAL", "OSP_SAMPLE"))
            .action("Sample MetLAB inspection", "sample_received_date!=EMPTY", (a, row, refresh) -> InspOsp.openInspection(a, row, "METLAB", "OSP_SAMPLE"))
            .action("Clear Sample Receipt", "sample_received_date!=EMPTY", InspOsp::clearSample)
            .action("OSP Inward (receive batch)", "sample_gate_status=ACCEPTED|ACCEPTED_UNDER_RESERVE;status!=REJECTED|CANCELLED", InspOsp::receive)
            .action("Receipt Dimensional inspection", "", (a, row, refresh) -> InspOsp.openInspection(a, row, "DIMENSIONAL", "OSP_RECEIPT"))
            .action("Receipt MetLAB inspection", "", (a, row, refresh) -> InspOsp.openInspection(a, row, "METLAB", "OSP_RECEIPT"))
            .action("Edit Material Out (single-heat job)", "", InspOsp::editLegacyMaterialOut)
            .action("Delete OSP transaction", "", InspOsp::deleteTransaction)
            .child("OSP inward receipts", "osp_receipts", "osp_job_id", "created_at.desc", new String[][]{
                {"receipt_number", "Receipt No."}, {"receipt_date", "Receipt Date"}, {"receipt_challan", "Vendor Challan"},
                {"vendor_invoice_number", "Vendor Invoice"}, {"tc_number", "TC Number"}, {"vendor_batch_number", "OSP Vendor Batch"},
                {"quantity_received", "Receipt Qty pcs"}, {"remarks", "Remarks"}})
            .child("OSP Dimensional reports", "inspection_reports", "osp_job_id", "updated_at.desc", new String[][]{
                {"report_number", "Report"}, {"inspection_scope", "Stage"}, {"inspection_date", "Date"}, {"disposition", "Decision"}, {"status", "Status"}})
            .child("OSP MetLAB reports", "lab_tests", "osp_job_id", "updated_at.desc", new String[][]{
                {"report_number", "Report"}, {"inspection_scope", "Stage"}, {"test_date", "Date"}, {"disposition", "Decision"}, {"status", "Status"}}));

        // ---------------------------------------------------------------- R39: OSP inspection queues (web osp_inspections · R37 fixes)
        list.add(new Module("osp_inspection_queues", "OSP Inspection Queues", Catalog.QUALITY, OSP, "v_qsms_osp_register")
            .desc("Sample / Receipt × Dimensional / MetLAB · pending and released-without-report batches")
            .custom(OspQueueScreen::new).readOnly().noEdit());

        // ---------------------------------------------------------------- OSP receipts (read-only register)
        list.add(new Module("osp_receipts", "OSP Inward Receipts", Catalog.QUALITY, OSP, "osp_receipts")
            .desc("Partial / full OSP vendor receipts")
            .titleField("receipt_number")
            .col("receipt_number", "Receipt No.").col("receipt_date", "Receipt Date").col("osp_job_id", "OSP Job").col("receipt_challan", "Vendor Challan")
            .col("vendor_invoice_number", "Vendor Invoice").col("vendor_invoice_date", "Invoice Date").col("tc_number", "TC Number")
            .col("vendor_batch_number", "OSP Vendor Batch").col("quantity_received", "Receipt Qty pcs").col("remarks", "Remarks")
            .status("")
            .noEdit().readOnly()
            .action("Edit OSP inward receipt", "", InspOsp::editReceipt)
            .action("Delete OSP inward receipt", "", InspOsp::deleteReceipt));
    }

    private static void amendLab(MainActivity a, org.json.JSONObject row, Runnable refresh) {
        boolean osp = !Lookups.j(row, "osp_job_id").isEmpty();
        if (osp && !"FINAL".equalsIgnoreCase(Lookups.j(row, "status"))) { a.toast("OSP reports that are not FINAL stay editable - use Edit."); return; }
        InspUtil.amendAction(a, "lab_tests", osp ? "OSP METLAB" : "METLAB_REPORT", row, refresh);
    }
}
