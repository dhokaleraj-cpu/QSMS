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
        List<Field> fields = receiptFields(Math.max(remaining, 1));
        // R37: one entry updates both - the receipt is the vendor return on the Material Out challan (osp_challan.link_receipt)
        fields.add(fields.size() - 1, Field.text("return_vehicle", "Return Vehicle No").hint("Printed in 'Supplier Details for Returnable Challan' on the Material Out challan."));
        fields.add(fields.size() - 1, Field.number("return_rejected", "Rejected / not returned at vendor (pcs)").range(0, Double.MAX_VALUE)
            .hint("Reduces the challan balance; the receipt quantity is the returned quantity."));
        InspUtil.formDialog(a, "OSP Material Inward · balance " + Ui.num(remaining, 0) + " pcs", fields, v, "Create OSP Inward", (form, values) -> Api.async(() -> {
            JSONObject args = receiptArgs(form);
            args.put("p_osp_job_id", InspUtil.j(job, "id"));
            Object res = api.rpcValue("qsms_receive_osp_batch", args);
            JSONObject saved = res instanceof JSONObject ? (JSONObject) res : new JSONObject();
            String note;
            try {
                JSONObject current = saved.optJSONObject("current_receipt");
                String receiptId = InspUtil.j(current, "id");
                if (receiptId.isEmpty()) {
                    JSONArray latest = api.rows("osp_receipts?select=id&osp_job_id=eq." + Api.enc(InspUtil.j(job, "id")) + "&order=created_at.desc&limit=1");
                    if (latest.length() > 0) receiptId = latest.getJSONObject(0).optString("id");
                }
                JSONObject raw = InspUtil.get(api, "osp_jobs", InspUtil.j(job, "id"));
                Double rej = form.num("return_rejected");
                JSONObject linked = OspChallan.linkReceipt(api, InspUtil.j(job, "id"), InspUtil.j(raw, "material_out_id"), receiptId, form.str("return_vehicle"), rej == null ? 0 : rej, "");
                note = linked != null ? " · Vendor return added to the Material Out challan." : " · Shown as a vendor return on the Material Out challan.";
            } catch (Exception linkError) {
                note = " · Challan return details not saved (" + Api.message(linkError) + "); add them in OSP Material Out.";
            }
            return InspUtil.j(saved, "receipt_number") + "|" + note;
        }, (res, err) -> {
            String[] parts = res == null ? new String[]{"", ""} : res.split("\\|", 2);
            done(a, err, "OSP Inward " + parts[0] + " saved successfully. Post-receipt inspections are now pending." + (parts.length > 1 ? parts[1] : ""), refresh);
        }));
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

    // ================================================================== R39 (web R35 / R37 OSP queue + layout fixes)
    /** OSPService.name_matched_layouts: approved OSP layouts whose layout name contains the job's process name. */
    static List<JSONObject> nameMatchedLayouts(List<JSONObject> layouts, String processName) {
        String name = processName == null ? "" : processName.trim().replaceAll("\\s+", " ").toLowerCase(Locale.ROOT);
        List<JSONObject> out = new ArrayList<>();
        if (name.length() < 3) return out;
        for (JSONObject l : layouts) if (InspUtil.j(l, "layout_name").replaceAll("\\s+", " ").toLowerCase(Locale.ROOT).contains(name)) out.add(l);
        return out;
    }

    /** OSPService.fallback_layouts (mirror of DB qcms_osp_layout_acceptable): name match, else the only OSP layout of the Part at an
     *  OSP stage whose Process is not one of the Part's own OSP processes. */
    static List<JSONObject> fallbackLayouts(List<JSONObject> layouts, JSONObject job, java.util.Set<String> partOspProcessIds, java.util.Set<String> ospStageIds) {
        List<JSONObject> named = nameMatchedLayouts(layouts, InspUtil.j(job, "process_name"));
        if (!named.isEmpty()) return named;
        List<JSONObject> out = new ArrayList<>();
        if (layouts.size() == 1) {
            JSONObject only = layouts.get(0);
            boolean stageOk = ospStageIds == null || ospStageIds.contains(InspUtil.j(only, "inspection_stage_id"));
            boolean processOk = partOspProcessIds == null || !partOspProcessIds.contains(InspUtil.j(only, "process_id"));
            if (stageOk && processOk) out.add(only);
        }
        return out;
    }

    /**
     * Approved OSP layouts offered for an OSP job (osp_inspections section A, R35/R37): Part + Process first; else an approved OSP
     * layout of the Part registered under another Process (name match / only layout) - the DB save trigger accepts the same
     * fallback, so the draft save of e.g. "CASE CARBURIZING 9265" no longer fails.
     */
    static List<JSONObject> ospPlans(Api api, String reportType, JSONObject job) throws Exception {
        String partId = InspUtil.j(job, "part_id");
        List<JSONObject> plans = InspUtil.plans(api, reportType, partId, true, InspUtil.j(job, "process_id"), null, "OSP_PROCESS");
        if (!plans.isEmpty()) return plans;
        List<JSONObject> partLayouts = InspUtil.plans(api, reportType, partId, true, null, null, "OSP_PROCESS");
        if (partLayouts.isEmpty()) return plans;
        java.util.Set<String> processes = new java.util.HashSet<>(), stages = new java.util.HashSet<>();
        for (JSONObject s : InspUtil.list(api.rows("part_process_specifications?select=process_id&part_id=eq." + Api.enc(partId) + "&inward_type=eq.OSP_PROCESS&limit=500")))
            processes.add(InspUtil.j(s, "process_id"));
        for (JSONObject s : InspUtil.list(api.rows("inspection_stages?select=id,stage_code,stage_name&limit=500")))
            if ((InspUtil.j(s, "stage_code") + " " + InspUtil.j(s, "stage_name")).toUpperCase(Locale.ROOT).contains("OSP")) stages.add(InspUtil.j(s, "id"));
        return fallbackLayouts(partLayouts, job, processes, stages);
    }

    /** OSPService.inspection_gate_closed (R37): the stage gate is decided - the batch leaves the Pending / New queue. */
    static boolean inspectionGateClosed(JSONObject row, String scope) {
        String status = InspUtil.j(row, "status").toUpperCase(Locale.ROOT);
        if ("CANCELLED".equals(status) || "REJECTED".equals(status)) return true;
        List<String> decided = Arrays.asList("ACCEPTED", "ACCEPTED_UNDER_RESERVE", "REJECTED");
        if ("OSP_SAMPLE".equals(scope)) return decided.contains(InspUtil.j(row, "sample_gate_status").toUpperCase(Locale.ROOT));
        return "COMPLETED".equals(status) || "CLOSED".equals(status) || decided.contains(InspUtil.j(row, "receipt_quality_disposition").toUpperCase(Locale.ROOT));
    }

    /** OSPService._inspection_candidates: required (flag / approved layout / part layout) + ready + stage decision still pending. */
    static List<JSONObject> inspectionCandidates(Api api, String scope, String reportType) throws Exception {
        boolean dim = "DIMENSIONAL".equals(reportType);
        String dispositionKey = ("OSP_SAMPLE".equals(scope) ? "sample_" : "receipt_") + (dim ? "dimensional" : "metlab") + "_disposition";
        List<JSONObject> register = InspUtil.list(api.rows("v_qsms_osp_register?select=*&order=created_at.desc&limit=5000"));
        java.util.Set<String> layoutSpecs = new java.util.HashSet<>();
        java.util.Map<String, List<JSONObject>> partLayouts = new java.util.HashMap<>();
        for (JSONObject l : InspUtil.list(api.rows("inspection_plans?select=id,part_id,process_id,layout_name,source_process_specification_id,inward_type&status=eq.APPROVED&layout_type=eq."
            + reportType + "&limit=5000"))) {
            if (!InspUtil.j(l, "source_process_specification_id").isEmpty()) layoutSpecs.add(InspUtil.j(l, "source_process_specification_id"));
            if ("OSP_PROCESS".equals(InspUtil.j(l, "inward_type"))) partLayouts.computeIfAbsent(InspUtil.j(l, "part_id"), k -> new ArrayList<>()).add(l);
        }
        List<JSONObject> rows = new ArrayList<>();
        List<String> decided = Arrays.asList("ACCEPTED", "ACCEPTED_UNDER_RESERVE", "REJECTED");
        for (JSONObject row : register) {
            boolean byFlag = row.optBoolean(dim ? "dimensional_required" : "metlab_required", false);
            boolean byLayout = layoutSpecs.contains(InspUtil.j(row, "process_specification_id"));
            String status = InspUtil.j(row, "status").toUpperCase(Locale.ROOT);
            if (!byFlag && !byLayout && !"COMPLETED".equals(status) && !"CLOSED".equals(status)) {
                List<JSONObject> cands = partLayouts.getOrDefault(InspUtil.j(row, "part_id"), new ArrayList<>());
                for (JSONObject l : cands) if (InspUtil.j(l, "process_id").equals(InspUtil.j(row, "process_id"))) byLayout = true;
                if (!byLayout) byLayout = !nameMatchedLayouts(cands, InspUtil.j(row, "process_name")).isEmpty();
            }
            if (!byFlag && !byLayout) continue;
            boolean ready = "OSP_SAMPLE".equals(scope) ? !InspUtil.j(row, "sample_received_date").isEmpty()
                : InspUtil.dbl(row, "quantity_received") >= InspUtil.dbl(row, "quantity_dispatched") && InspUtil.dbl(row, "quantity_dispatched") > 0;
            String disp = InspUtil.j(row, dispositionKey).isEmpty() ? "PENDING" : InspUtil.j(row, dispositionKey).toUpperCase(Locale.ROOT);
            if (ready && !decided.contains(disp) && !"CANCELLED".equals(status)) rows.add(row);
        }
        return rows;
    }

    /** jobs_for_inspection: candidates whose stage gate is still open (R37 - released batches leave the Pending list). */
    static List<JSONObject> jobsForInspection(List<JSONObject> candidates, String scope) {
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject r : candidates) if (!inspectionGateClosed(r, scope)) out.add(r);
        return out;
    }

    /** released_without_report: gate decided but no report of this stage (e.g. a draft deleted after release). */
    static List<JSONObject> releasedWithoutReport(Api api, List<JSONObject> candidates, String scope, String reportType) throws Exception {
        List<JSONObject> closed = new ArrayList<>();
        for (JSONObject r : candidates) if (inspectionGateClosed(r, scope)) closed.add(r);
        if (closed.isEmpty()) return closed;
        java.util.Set<String> reported = new java.util.HashSet<>();
        List<String> ids = new ArrayList<>();
        for (JSONObject r : closed) ids.add(InspUtil.j(r, "id"));
        String table = "DIMENSIONAL".equals(reportType) ? "inspection_reports" : "lab_tests";
        for (int i = 0; i < ids.size(); i += 80)
            for (JSONObject r : InspUtil.list(api.rows(table + "?select=osp_job_id&inspection_scope=eq." + scope + "&osp_job_id=in.(" + String.join(",", ids.subList(i, Math.min(ids.size(), i + 80))) + ")&limit=2000")))
                reported.add(InspUtil.j(r, "osp_job_id"));
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject r : closed) if (!reported.contains(InspUtil.j(r, "id"))) out.add(r);
        return out;
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
            // R37: a batch released without a report of this stage (draft deleted after release) may still record it
            if (Arrays.asList("ACCEPTED", "ACCEPTED_UNDER_RESERVE", "REJECTED").contains(disp) && !inspectionGateClosed(job, scope)) throw new Api.ApiException(422, "This OSP inspection step is already decided (" + Ui.pretty(disp) + ").");
            return "";
        }, (rid, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            String reportId = rid == null || rid.isEmpty() ? null : rid;
            a.push(dim ? InspDimScreen.forOsp(a, reportId, job, scope) : InspLabScreen.forOsp(a, reportId, job, scope));
        });
    }
}
