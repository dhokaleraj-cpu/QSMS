package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.widget.LinearLayout;
import android.widget.ScrollView;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * RMTC record actions with the website's workflow rules (rmtc_pages.render_entry / render_approval):
 * part worksheets, submit, validate, decide, add part to an approved RMTC, admin reopen, attachments and the
 * heat ledger of the record's heat.
 */
final class IncRmtcFlow {
    private IncRmtcFlow() { }

    interface Values { void ok(JSONObject values); }

    /** Small form in a dialog (validated before OK closes it). */
    static void formDialog(MainActivity a, String title, List<Field> fields, JSONObject initial, String okLabel, Values done) {
        FormView form = new FormView(a, fields);
        if (initial != null) form.setAll(initial);
        ScrollView sv = new ScrollView(a);
        LinearLayout pad = Ui.vbox(a);
        pad.setPadding(Ui.dp(a, 18), Ui.dp(a, 4), Ui.dp(a, 18), Ui.dp(a, 8));
        pad.addView(form);
        sv.addView(pad);
        AlertDialog dialog = new AlertDialog.Builder(a).setTitle(title).setView(sv)
            .setPositiveButton(okLabel, null).setNegativeButton("Back", null).create();
        dialog.setOnShowListener(d -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            String problem = form.validate();
            if (problem != null) { a.toast(problem); return; }
            try {
                JSONObject values = form.json();
                dialog.dismiss();
                done.ok(values);
            } catch (Exception e) {
                a.toast(Api.message(e));
            }
        }));
        dialog.show();
    }

    static void run(MainActivity a, String doing, Api.Task<String> task, Runnable refresh) {
        a.toast(doing);
        Api.async(task, (msg, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            a.toast(msg);
            if (refresh != null) refresh.run();
        });
    }

    // ------------------------------------------------------------------ actions
    static void worksheets(MainActivity a, JSONObject row) {
        Api api = Api.get(a);
        String rid = Lookups.j(row, "id");
        Api.async(() -> {
            List<JSONObject> cov = IncRmtcData.coveredParts(api, rid);
            java.util.Map<String, JSONObject> parts = IncRmtcData.parts(api);
            List<String> ids = new ArrayList<>();
            for (JSONObject c : cov) ids.add(Lookups.j(c, "part_id"));
            IncRmtcData.addMissingParts(api, parts, ids);
            List<String> names = new ArrayList<>();
            for (JSONObject c : cov) names.add(IncRmtcData.partLabel(parts, Lookups.j(c, "part_id")) + (Lookups.j(c, "worksheet_completed_at").isEmpty() ? " · PENDING" : " · COMPLETED"));
            return new Object[]{ids, names};
        }, (res, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            @SuppressWarnings("unchecked") List<String> ids = (List<String>) res[0];
            @SuppressWarnings("unchecked") List<String> names = (List<String>) res[1];
            if (ids.isEmpty()) { a.toast("No covered parts exist."); return; }
            if (ids.size() == 1) { a.push(new IncRmtcWorksheet(a, rid, ids.get(0))); return; }
            new FormView(a, new ArrayList<>()).choose("Part Worksheet", ids, names, pid -> a.push(new IncRmtcWorksheet(a, rid, pid)));
        });
    }

    static void submit(MainActivity a, JSONObject row, Runnable refresh) {
        Api api = Api.get(a);
        String rid = Lookups.j(row, "id");
        List<Field> f = Arrays.asList(
            Field.lookup("validated_by_employee_id", "Validator", IncCalc.employeeLookup("RMTC_VALIDATE")).req(),
            Field.lookup("approved_by_employee_id", "Approver", IncCalc.employeeLookup("RMTC_APPROVE")).req());
        formDialog(a, "Submit Draft → Approval Pending", f, row, "Submit", v -> run(a, "Submitting RMTC…", () -> {
            api.update("rmtc_approvals", rid, new JSONObject().put("validated_by_employee_id", v.opt("validated_by_employee_id")).put("approved_by_employee_id", v.opt("approved_by_employee_id")));
            api.rpc("qsms_submit_rmtc", new JSONObject().put("p_rmtc_id", rid));
            return "RMTC submitted and moved to Approval Pending.";
        }, refresh));
    }

    static void validate(MainActivity a, JSONObject row, Runnable refresh) {
        Api api = Api.get(a);
        String rid = Lookups.j(row, "id");
        JSONObject init = new JSONObject();
        try {
            init.put("validated_by_employee_id", IncCalc.jo(row, "validated_by_employee_id"));
            init.put("approved_by_employee_id", Lookups.j(row, "approved_by_employee_id").isEmpty() ? IncCalc.jo(row, "decision_by_employee_id") : row.opt("approved_by_employee_id"));
        } catch (Exception ignored) { }
        List<Field> f = Arrays.asList(
            Field.lookup("validated_by_employee_id", "Validated By", IncCalc.employeeLookup("RMTC_VALIDATE")).req(),
            Field.lookup("approved_by_employee_id", "Approved / Decided By", IncCalc.employeeLookup("RMTC_APPROVE")));
        formDialog(a, "2 · Validate Against Masters", f, init, "Validate", v -> run(a, "Validating RMTC against masters…", () -> {
            api.update("rmtc_approvals", rid, new JSONObject().put("validated_by_employee_id", v.opt("validated_by_employee_id")).put("approved_by_employee_id", v.opt("approved_by_employee_id")));
            api.rpc("qsms_validate_rmtc", new JSONObject().put("p_rmtc_id", rid));
            return "RMTC validation completed. Select the final decision for every Part Number.";
        }, refresh));
    }

    static void decide(MainActivity a, JSONObject row) {
        if (Lookups.j(row, "validated_at").isEmpty()) { a.toast("Validate the RMTC against masters first (2 · Validate Against Masters)."); return; }
        a.push(new IncRmtcDecide(a, Lookups.j(row, "id")));
    }

    static void adminReopen(MainActivity a, JSONObject row, Runnable refresh) {
        Api api = Api.get(a);
        if (!api.isAdmin()) { a.toast("Only the Administrator can reopen a final RMTC decision."); return; }
        String rid = Lookups.j(row, "id");
        a.askText("Admin · Reopen Decision for Change", "Mandatory: explain why the approved/rejected decision must be changed.", "Reopen", true, reason ->
            run(a, "Reopening RMTC decision…", () -> {
                if ("PARTIALLY_APPROVED".equals(Lookups.j(row, "status"))) {
                    for (JSONObject c : IncRmtcData.coveredParts(api, rid)) {
                        String d = IncCalc.firstText(Lookups.j(c, "disposition"), "PENDING");
                        if (d.equals("PENDING") || d.equals("ON_HOLD"))
                            throw new IllegalArgumentException("An added Part Worksheet is still pending its decision. Complete it with 'Add Part / Added Part Decision' first.");
                    }
                }
                api.rpc("qsms_admin_reopen_rmtc", new JSONObject().put("p_rmtc_id", rid).put("p_reason", reason));
                return "RMTC reopened to Approval Pending. The administrator may now change and save the decisions.";
            }, refresh));
    }

    static final String[] DOC_SLOTS = {"RMTC_COPY", "RMTC_ATTACHMENT_2", "RMTC_ATTACHMENT_3"};
    static final String[] DOC_LABELS = {"Attachment 1 · RMTC Certificate / Copy", "Attachment 2 · Supporting Document", "Attachment 3 · Additional Document"};

    static void uploadDocument(MainActivity a, JSONObject row, Runnable refresh) {
        String rid = Lookups.j(row, "id");
        new AlertDialog.Builder(a).setTitle("RMTC attachment").setItems(DOC_LABELS, (d, which) -> {
            String slot = DOC_SLOTS[which];
            a.pickFile(DOC_LABELS[which], false, file -> upload(a, rid, "rmtc", slot, file,
                "RMTC_COPY".equals(slot) ? "rmtc_approvals" : null, "RMTC_COPY".equals(slot) ? "rmtc_copy_path" : null, refresh));
        }).setNegativeButton("Back", null).show();
    }

    static void uploadMicrostructure(MainActivity a, JSONObject row, Runnable refresh) {
        String rid = Lookups.j(row, "id");
        String[] labels = new String[3];
        for (int s = 1; s <= 3; s++) {
            String cap = Lookups.j(row, "microstructure_caption_" + s);
            labels[s - 1] = "Microstructure Photo " + s + (cap.isEmpty() || cap.equals("Microstructure Photo " + s) ? "" : " · " + cap);
        }
        new AlertDialog.Builder(a).setTitle("Microstructure photo").setItems(labels, (d, which) ->
            a.pickFile(labels[which], true, file -> upload(a, rid, "rmtc-microstructure", "RMTC_MICROSTRUCTURE_" + (which + 1), file, null, null, refresh)))
            .setNegativeButton("Back", null).show();
    }

    private static void upload(MainActivity a, String rid, String folder, String slot, Attachments.FileData file, String parentTable, String parentField, Runnable refresh) {
        Api api = Api.get(a);
        run(a, "Uploading " + file.name + " (" + (file.data.length / 1024) + " KB)…", () -> {
            Attachments.uploadSlot(api, "RMTC", rid, folder, slot, file, parentTable, parentField);
            return "Uploaded " + Ui.pretty(slot) + ".";
        }, refresh);
    }

    /** Heat Steel Ledger register filtered to this record's heat. */
    static void heatLedger(MainActivity a, String heat) {
        String n = IncCalc.normalize(heat);
        if (n.isEmpty()) { a.toast("No Heat Number on this record."); return; }
        Module base = Catalog.get("heat_ledger");
        Module m = new Module("heat_ledger_" + n, "Heat Steel Ledger · " + heat, Catalog.QUALITY, "Incoming material", "v_qsms_heat_steel_ledger")
            .filter("&normalized_heat_number=eq." + Api.enc(n)).order("updated_at.desc").status("heat_balance_status").id("");
        if (base != null) for (String[] c : base.cols) m.cols.add(c);
        a.push(new RegisterScreen(a, m));
    }
}
