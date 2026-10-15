package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/** OSP register actions (app_pages/osp_transactions.py, osp_inspections.py, core/osp_service.py) - all writes are the website RPCs. */
final class InspOsp {
    private InspOsp() { }

    static final List<String> FINAL_ACCEPTED = Arrays.asList("ACCEPTED", "ACCEPTED_UNDER_RESERVE");

    static String jobLabel(JSONObject r) {
        return InspUtil.j(r, "osp_job_number") + " · Part " + InspUtil.j(r, "part_number") + " · FSI Batch " + (InspUtil.j(r, "osp_batch_code").isEmpty() ? "-" : InspUtil.j(r, "osp_batch_code"))
            + " · Heat " + InspUtil.j(r, "heat_number") + " · " + InspUtil.j(r, "process_name") + " · " + InspUtil.j(r, "vendor_name");
    }

    private static void done(MainActivity a, Exception err, String ok, Runnable refresh) {
        if (err != null) { a.toast(Api.message(err)); return; }
        a.toast(ok);
        refresh.run();
    }

    /** Pre-inward sample receipt: qsms_record_osp_sample. */
    static void sampleReceipt(MainActivity a, JSONObject job, Runnable refresh) {
        if (InspUtil.dbl(job, "quantity_received") > 0 || Arrays.asList("REJECTED", "CANCELLED").contains(InspUtil.j(job, "status"))) {
            a.toast("Sample receipt is possible only before any OSP inward and while the job is not Rejected / Cancelled.");
            return;
        }
        int dispatched = (int) Math.max(1, Math.round(InspUtil.dbl(job, "quantity_dispatched")));
        List<Field> f = new ArrayList<>();
        f.add(Field.date("sample_received_date", "Sample Received Date").req());
        f.add(Field.text("sample_reference", "Sample Reference"));
        f.add(Field.text("vendor_batch_number", "OSP Vendor Batch Number"));
        f.add(Field.integer("sample_quantity", "Sample Quantity (pcs)").range(1, dispatched).req());
        JSONObject v = new JSONObject();
        try {
            v.put("sample_received_date", InspUtil.j(job, "sample_received_date").isEmpty() ? Ui.today() : InspUtil.j(job, "sample_received_date").substring(0, 10));
            v.put("sample_reference", InspUtil.j(job, "sample_reference"));
            v.put("vendor_batch_number", InspUtil.j(job, "vendor_batch_number"));
            v.put("sample_quantity", String.valueOf(Math.max(1, (int) Math.round(InspUtil.dbl(job, "sample_quantity")))));
        } catch (Exception ignored) { }
        Api api = Api.get(a);
        InspUtil.formDialog(a, "OSP Pre-inward Sample Receipt", f, v, "Save Sample Receipt", (form, values) -> Api.async(() -> {
            JSONObject args = new JSONObject();
            args.put("p_osp_job_id", InspUtil.j(job, "id"));
            args.put("p_sample_received_date", form.str("sample_received_date"));
            args.put("p_sample_reference", form.str("sample_reference"));
            args.put("p_vendor_batch_number", form.str("vendor_batch_number"));
            args.put("p_sample_quantity", (long) Math.round(form.num("sample_quantity")));
            return api.rpc("qsms_record_osp_sample", args);
        }, (r, err) -> done(a, err, "OSP sample receipt saved successfully. Required OSP inspection queues are now available.", refresh)));
    }

    static void clearSample(MainActivity a, JSONObject job, Runnable refresh) {
        Api api = Api.get(a);
        a.confirm("Delete Sample Receipt?", "Allowed only before linked Sample Dimensional / MetLAB records exist. You will be asked for your password.", "Continue", () ->
            a.confirmPassword("Confirm with your QCMS password", () -> Api.async(() -> api.rpc("qcms_clear_osp_sample", new JSONObject().put("p_osp_job_id", InspUtil.j(job, "id"))),
                (r, err) -> done(a, err, "OSP Sample Receipt cleared successfully.", refresh))));
    }

    private static List<Field> receiptFields(double maxQty) {
        List<Field> f = new ArrayList<>();
        f.add(Field.date("receipt_date", "OSP Inward Date").req());
        f.add(Field.text("receipt_challan", "Vendor Delivery Challan"));
        f.add(Field.text("vendor_invoice_number", "Vendor Invoice Number"));
        f.add(Field.date("vendor_invoice_date", "Vendor Invoice Date").req());
        f.add(Field.text("tc_number", "TC Number"));
        f.add(Field.date("tc_date", "TC Date").req());
        f.add(Field.text("vendor_batch_number", "OSP Vendor Batch Number"));
        f.add(Field.number("quantity_received", "Receipt Batch Qty (pcs)").range(1, maxQty).req());
        f.add(Field.area("remarks", "Receipt Remarks"));
        return f;
    }

    private static JSONObject receiptArgs(FormView form) throws Exception {
        JSONObject args = new JSONObject();
        for (String k : new String[]{"receipt_date", "receipt_challan", "vendor_invoice_number", "vendor_invoice_date", "tc_number", "tc_date", "vendor_batch_number"}) args.put("p_" + k, form.str(k));
        args.put("p_quantity_received", form.num("quantity_received"));
        args.put("p_remarks", InspUtil.nz(form.str("remarks")));
        return args;
    }

    /** OSP inward (partial allowed): qsms_receive_osp_batch. */
    static void receive(MainActivity a, JSONObject job, Runnable refresh) {
        double dispatched = InspUtil.dbl(job, "quantity_dispatched"), received = InspUtil.dbl(job, "quantity_received");
        if (!FINAL_ACCEPTED.contains(InspUtil.j(job, "sample_gate_status")) || received >= dispatched || Arrays.asList("REJECTED", "CANCELLED").contains(InspUtil.j(job, "status"))) {
            a.toast("OSP inward is enabled after the pre-inward sample passes (sample gate Accepted / Accepted Under Reserve) and while quantity is still at the vendor.");
            return;
        }
        double remaining = Math.max(dispatched - received, 0);
        JSONObject v = new JSONObject();
        try {
            v.put("receipt_date", Ui.today()); v.put("vendor_invoice_date", Ui.today()); v.put("tc_date", Ui.today());
            v.put("vendor_batch_number", InspUtil.j(job, "vendor_batch_number"));
            v.put("quantity_received", InspUtil.fmt(Math.max(remaining, 1)));
        } catch (Exception ignored) { }
        Api api = Api.get(a);
        InspUtil.formDialog(a, "OSP Material Inward · balance " + Ui.num(remaining, 0) + " pcs", receiptFields(Math.max(remaining, 1)), v, "Create OSP Inward", (form, values) -> Api.async(() -> {
            JSONObject args = receiptArgs(form);
            args.put("p_osp_job_id", InspUtil.j(job, "id"));
            Object res = api.rpcValue("qsms_receive_osp_batch", args);
            return res instanceof JSONObject ? InspUtil.j((JSONObject) res, "receipt_number") : "";
        }, (no, err) -> done(a, err, "OSP Inward " + (no == null ? "" : no) + " saved successfully. Post-receipt inspections are now pending.", refresh)));
    }

    static void editReceipt(MainActivity a, JSONObject rec, Runnable refresh) {
        JSONObject v = new JSONObject();
        try {
            for (String k : new String[]{"receipt_challan", "vendor_invoice_number", "tc_number", "vendor_batch_number", "remarks"}) v.put(k, InspUtil.j(rec, k));
            for (String k : new String[]{"receipt_date", "vendor_invoice_date", "tc_date"}) v.put(k, InspUtil.j(rec, k).length() >= 10 ? InspUtil.j(rec, k).substring(0, 10) : Ui.today());
            v.put("quantity_received", InspUtil.fmt(rec.opt("quantity_received")));
        } catch (Exception ignored) { }
        Api api = Api.get(a);
        InspUtil.formDialog(a, "Edit OSP Inward " + InspUtil.j(rec, "receipt_number"), receiptFields(Double.MAX_VALUE), v, "Update", (form, values) -> Api.async(() -> {
            JSONObject args = receiptArgs(form);
            args.put("p_receipt_id", InspUtil.j(rec, "id"));
            return api.rpc("qcms_update_osp_receipt", args);
        }, (r, err) -> done(a, err, "OSP Inward receipt updated successfully.", refresh)));
    }

    static void deleteReceipt(MainActivity a, JSONObject rec, Runnable refresh) {
        Api api = Api.get(a);
        a.confirm("Delete OSP Inward " + InspUtil.j(rec, "receipt_number") + "?", "Receipt-level Dimensional / MetLAB records must be deleted first. You will be asked for your password.", "Continue", () ->
            a.confirmPassword("Confirm delete with your password", () -> Api.async(() -> api.rpc("qcms_delete_osp_receipt", new JSONObject().put("p_receipt_id", InspUtil.j(rec, "id"))),
                (r, err) -> { if (err != null) { a.toast(Api.message(err)); return; } a.toast("OSP inward receipt deleted and quantity / status recalculated."); a.back(); })));
    }

    static void deleteTransaction(MainActivity a, JSONObject job, Runnable refresh) {
        Api api = Api.get(a);
        a.confirm("Delete OSP transaction " + InspUtil.j(job, "osp_job_number") + "?", "QCMS restores the Material Out allocation. Linked quality / downstream records block deletion. You will be asked for your password.", "Continue", () ->
            a.confirmPassword("Confirm delete with your password", () -> Api.async(() -> api.rpc("qcms_delete_osp_transaction", new JSONObject().put("p_osp_job_id", InspUtil.j(job, "id"))),
                (r, err) -> { if (err != null) { a.toast("Deletion blocked: " + Api.message(err)); return; } a.toast("OSP transaction deleted and source quantity restored."); a.back(); })));
    }

    static void deleteMaterialOut(MainActivity a, JSONObject doc, Runnable refresh) {
        Api api = Api.get(a);
        a.confirm("Delete Material Out " + InspUtil.j(doc, "material_out_number") + "?", "Deletes all heat lines together only when downstream genealogy checks permit it; restores each source balance. You will be asked for your password.", "Continue", () ->
            a.confirmPassword("Confirm delete with your password", () -> Api.async(() -> api.rpc("qcms_delete_osp_material_out_group", new JSONObject().put("p_material_out_id", InspUtil.j(doc, "id"))),
                (r, err) -> { if (err != null) { a.toast("Deletion blocked: " + Api.message(err)); return; } a.toast("Material Out deleted and heat balances restored."); a.back(); })));
    }

    /** Single-line (legacy) Material Out edit: qcms_update_osp_material_out. Multi-heat documents are edited on the Material Out record. */
    static void editLegacyMaterialOut(MainActivity a, JSONObject job, Runnable refresh) {
        Api api = Api.get(a);
        Api.async(() -> InspUtil.get(api, "osp_jobs", InspUtil.j(job, "id")), (raw, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            if (raw != null && !InspUtil.j(raw, "material_out_id").isEmpty()) {
                a.toast("This heat line belongs to a multi-heat Material Out document. Edit it from OSP Material Out.");
                return;
            }
            List<Field> f = new ArrayList<>();
            f.add(Field.date("dispatch_date", "Material Out Date").req());
            f.add(Field.date("expected_return_date", "Expected Return Date").req());
            f.add(Field.text("dispatch_challan", "Material Out Challan Number"));
            f.add(Field.number("quantity_dispatched", "Material Out Quantity (pcs)").range(1, Double.MAX_VALUE).req());
            f.add(Field.area("remarks", "Dispatch Remarks"));
            JSONObject v = new JSONObject();
            try {
                v.put("dispatch_date", InspUtil.j(job, "dispatch_date").length() >= 10 ? InspUtil.j(job, "dispatch_date").substring(0, 10) : Ui.today());
                v.put("expected_return_date", InspUtil.j(job, "expected_return_date").length() >= 10 ? InspUtil.j(job, "expected_return_date").substring(0, 10) : LocalDate.now().plusDays(7).toString());
                v.put("dispatch_challan", InspUtil.j(job, "dispatch_challan"));
                v.put("quantity_dispatched", InspUtil.fmt(job.opt("quantity_dispatched")));
                v.put("remarks", InspUtil.j(job, "dispatch_remarks"));
            } catch (Exception ignored) { }
            InspUtil.formDialog(a, "Edit Material Out " + InspUtil.j(job, "osp_job_number"), f, v, "Update Material Out", (form, values) -> Api.async(() -> {
                JSONObject args = new JSONObject();
                args.put("p_osp_job_id", InspUtil.j(job, "id"));
                args.put("p_dispatch_date", form.str("dispatch_date"));
                args.put("p_dispatch_challan", form.str("dispatch_challan"));
                args.put("p_quantity_dispatched", form.num("quantity_dispatched"));
                args.put("p_expected_return_date", form.str("expected_return_date"));
                args.put("p_remarks", form.str("remarks"));
                return api.rpc("qcms_update_osp_material_out", args);
            }, (r, e2) -> done(a, e2, "OSP Material Out updated successfully.", refresh)));
        });
    }

    /**
     * OSP Dimensional / MetLAB inspection for one job and scope (OSP_SAMPLE / OSP_RECEIPT). One report per job + scope:
     * an existing report is opened, otherwise the queue rule of OSPService.jobs_for_inspection must hold.
     */
    static void openInspection(MainActivity a, JSONObject job, String reportType, String scope) {
        Api api = Api.get(a);
        boolean dim = "DIMENSIONAL".equals(reportType);
        String table = dim ? "inspection_reports" : "lab_tests";
        a.toast("Opening OSP " + Ui.pretty(reportType) + "…");
        Api.async(() -> {
            JSONArray ex = api.rows(table + "?select=id&osp_job_id=eq." + Api.enc(InspUtil.j(job, "id")) + "&inspection_scope=eq." + scope + "&order=updated_at.desc&limit=1");
            if (ex.length() > 0) return ex.getJSONObject(0).optString("id");
            boolean required = job.optBoolean(dim ? "dimensional_required" : "metlab_required", false);
            if (!required && !InspUtil.j(job, "process_specification_id").isEmpty()) {
                required = api.rows("inspection_plans?select=id&status=eq.APPROVED&layout_type=eq." + reportType + "&source_process_specification_id=eq."
                    + Api.enc(InspUtil.j(job, "process_specification_id")) + "&limit=1").length() > 0;
            }
            if (!required) throw new Api.ApiException(422, "OSP " + Ui.pretty(reportType) + " is not required for this OSP process (Part Master flag off and no approved OSP layout).");
            boolean ready = "OSP_SAMPLE".equals(scope) ? !InspUtil.j(job, "sample_received_date").isEmpty()
                : InspUtil.dbl(job, "quantity_received") >= InspUtil.dbl(job, "quantity_dispatched") && InspUtil.dbl(job, "quantity_dispatched") > 0;
            if (!ready) throw new Api.ApiException(422, "OSP_SAMPLE".equals(scope) ? "Record the Sample Receipt first." : "The full dispatched quantity must be received (OSP inward) before the receipt inspection.");
            if ("CANCELLED".equals(InspUtil.j(job, "status"))) throw new Api.ApiException(422, "This OSP job is cancelled.");
            String key = ("OSP_SAMPLE".equals(scope) ? "sample_" : "receipt_") + (dim ? "dimensional" : "metlab") + "_disposition";
            String disp = InspUtil.j(job, key).toUpperCase(Locale.ROOT);
            if (Arrays.asList("ACCEPTED", "ACCEPTED_UNDER_RESERVE", "REJECTED").contains(disp)) throw new Api.ApiException(422, "This OSP inspection step is already decided (" + Ui.pretty(disp) + ").");
            return "";
        }, (rid, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            String reportId = rid == null || rid.isEmpty() ? null : rid;
            a.push(dim ? InspDimScreen.forOsp(a, reportId, job, scope) : InspLabScreen.forOsp(a, reportId, job, scope));
        });
    }
}
