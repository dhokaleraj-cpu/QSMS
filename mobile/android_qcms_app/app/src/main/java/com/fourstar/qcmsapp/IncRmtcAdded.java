package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

/**
 * Approved RMTC · Add Part Number and Added Part validation / decision (rmtc_pages "ADD PART NUMBER TO APPROVED
 * RMTC" and the incremental review): qsms_add_part_to_approved_rmtc → worksheet → qsms_validate_added_rmtc_part →
 * qsms_decide_added_rmtc_part. Existing accepted parts stay released.
 */
final class IncRmtcAdded extends Screen {
    private final String rid;
    private JSONObject record, heat;
    private List<JSONObject> covered;
    private Map<String, JSONObject> parts;

    IncRmtcAdded(MainActivity a, String rmtcId) { super(a); this.rid = rmtcId; }

    @Override public String title() { return "Approved RMTC · Add Part"; }
    @Override public String subtitle() { return record == null ? "Add Part Worksheet" : Lookups.j(record, "rmtc_number") + " · Heat " + Lookups.j(record, "heat_number"); }
    @Override public int tab() { return Catalog.QUALITY; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONObject r = IncRmtcData.rmtc(api, rid);
            List<JSONObject> cov = IncRmtcData.coveredParts(api, rid);
            Map<String, JSONObject> p = IncRmtcData.parts(api);
            List<String> ids = new ArrayList<>();
            for (JSONObject c : cov) ids.add(Lookups.j(c, "part_id"));
            IncRmtcData.addMissingParts(api, p, ids);
            JSONObject h = IncRmtcData.heatSummary(api, Lookups.j(r, "heat_number"));
            Lookups.rows(api, IncCalc.employeeLookup("RMTC_VALIDATE"));
            Lookups.rows(api, IncCalc.employeeLookup("RMTC_APPROVE"));
            return new Object[]{r, cov, p, h};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            record = (JSONObject) res[0];
            @SuppressWarnings("unchecked") List<JSONObject> c = (List<JSONObject>) res[1];
            @SuppressWarnings("unchecked") Map<String, JSONObject> p = (Map<String, JSONObject>) res[2];
            covered = c; parts = p; heat = (JSONObject) res[3];
            a.rebuildTitle(this);
            render();
        });
        return scroll;
    }

    private void render() {
        String status = Lookups.j(record, "status"), disp = Lookups.j(record, "disposition");
        boolean approved = status.equals("APPROVED") || status.equals("PARTIALLY_APPROVED");
        LinearLayout head = Ui.card(a);
        head.addView(Ui.pair(a, "RMTC", Lookups.j(record, "rmtc_number")));
        head.addView(Ui.pair(a, "Heat Number", Lookups.j(record, "heat_number")));
        head.addView(Ui.pair(a, "RMTC Steel Qty", IncCalc.kg(IncCalc.f(record.opt("certificate_quantity")))));
        head.addView(Ui.pair(a, "Inward Used", IncCalc.kg(IncCalc.f(heat.opt("inward_steel_quantity_kg")))));
        head.addView(Ui.pair(a, "Available / Unallocated", IncCalc.kg(IncCalc.first(heat, "available_unallocated_steel_quantity_kg", "available_steel_quantity_kg"))));
        head.addView(Ui.pair(a, "Covered Parts", String.valueOf(covered.size())));
        head.addView(Ui.pair(a, "Status", Ui.pretty(status) + " · " + Ui.pretty(disp)));
        add(head, 0);
        if (!approved) { add(Ui.text(a, "Parts can be added only to an Approved / Partially Approved RMTC.", 12.5f, Ui.AMBER_FG, false), 8); return; }

        // ---- C: add a compatible part
        add(Ui.label(a, "C · ADD PART NUMBER TO APPROVED RMTC"), 14);
        if (!(disp.equals("ACCEPTED") || disp.equals("ACCEPTED_UNDER_RESERVE"))) {
            add(Ui.text(a, "Only an Accepted / Accepted Under Reserve RMTC can be extended to another Part Number.", 12, Ui.MUTED, false), 2);
        } else {
            List<String> coveredIds = new ArrayList<>();
            for (JSONObject c : covered) coveredIds.add(Lookups.j(c, "part_id"));
            List<String> ids = new ArrayList<>(), names = new ArrayList<>();
            String grade = Lookups.j(record, "material_grade_id");
            for (Map.Entry<String, JSONObject> e : parts.entrySet()) {
                if (coveredIds.contains(e.getKey()) || !grade.equals(Lookups.j(e.getValue(), "material_grade_id"))) continue;
                if (!"ACTIVE".equalsIgnoreCase(IncCalc.firstText(Lookups.j(e.getValue(), "status"), "ACTIVE"))) continue;
                ids.add(e.getKey()); names.add(Lookups.PART.of(e.getValue()));
            }
            if (ids.isEmpty()) {
                add(Ui.text(a, "No additional active Part with the same Material Grade is available to add to this RMTC.", 12, Ui.MUTED, false), 2);
            } else {
                Field pf = Field.select("part_id", "New Part Number for this RMTC", ids.toArray(new String[0])).req().labels(names.toArray(new String[0]));
                FormView f = new FormView(a, Arrays.asList(pf));
                add(f, 2);
                Button addBtn = Ui.primary(a, "Add Part Number to Approved RMTC");
                add(addBtn, 8);
                addBtn.setOnClickListener(v -> {
                    String pid = f.str("part_id");
                    if (pid.isEmpty()) { a.toast("Select the new Part Number."); return; }
                    addBtn.setEnabled(false);
                    Api.async(() -> api.rpc("qsms_add_part_to_approved_rmtc", new JSONObject().put("p_rmtc_id", rid).put("p_part_id", pid)), (ok, err) -> {
                        addBtn.setEnabled(true);
                        if (err != null) { a.toast(Api.message(err)); return; }
                        a.toast("Part Number added to the approved RMTC. Complete the new Part Worksheet and validation; previously accepted Parts remain released.");
                        a.replaceTop(new IncRmtcAdded(a, rid));
                        a.push(new IncRmtcWorksheet(a, rid, pid));
                    });
                });
            }
        }

        // ---- D: validate & decide added part
        add(Ui.label(a, "D · VALIDATE & DECIDE ADDED PART WORKSHEET"), 16);
        List<JSONObject> pending = new ArrayList<>();
        for (JSONObject c : covered) {
            String d = IncCalc.firstText(Lookups.j(c, "disposition"), "PENDING");
            if (d.equals("PENDING") || d.equals("ON_HOLD")) pending.add(c);
        }
        if (pending.isEmpty()) { add(Ui.text(a, "All covered Part Worksheets already have a released final decision.", 12.5f, Ui.GREEN_FG, false), 2); return; }
        List<String> ids = new ArrayList<>(), names = new ArrayList<>();
        for (JSONObject c : pending) { ids.add(Lookups.j(c, "part_id")); names.add(IncRmtcData.partLabel(parts, Lookups.j(c, "part_id"))); }
        FormView f = new FormView(a, Arrays.asList(
            Field.select("part_id", "Pending Added Part Number", ids.toArray(new String[0])).req().labels(names.toArray(new String[0])),
            Field.lookup("validated_by_employee_id", "Added Part · Validated By", IncCalc.employeeLookup("RMTC_VALIDATE")),
            Field.lookup("approved_by_employee_id", "Added Part · Approved / Decided By", IncCalc.employeeLookup("RMTC_APPROVE")),
            Field.select("disposition", "Added Part Final Decision", IncCalc.DISPOSITIONS).req(),
            Field.area("reason", "Added Part Decision / Reserve / Hold / Rejection Reason")));
        LinearLayout statusBox = Ui.card(a);
        add(statusBox, 4);
        add(f, 6);
        f.onChange((k, v) -> { if ("part_id".equals(k)) showPending(statusBox, pending, String.valueOf(v)); });
        f.set("part_id", ids.get(0));
        f.set("disposition", "PENDING");
        if (!Lookups.j(record, "validated_by_employee_id").isEmpty()) f.set("validated_by_employee_id", Lookups.j(record, "validated_by_employee_id"));
        String ap = IncCalc.firstText(Lookups.j(record, "approved_by_employee_id"), Lookups.j(record, "decision_by_employee_id"));
        if (!ap.isEmpty()) f.set("approved_by_employee_id", ap);

        Button open = Ui.outline(a, "Open Part Worksheet", Ui.TEAL);
        Button validate = Ui.primary(a, "1 · Validate Added Part Against Masters");
        Button decide = Ui.primary(a, "2 · Save Added Part Final Decision");
        add(open, 10);
        add(validate, 8);
        add(decide, 8);
        open.setOnClickListener(v -> a.push(new IncRmtcWorksheet(a, rid, f.str("part_id"))));
        validate.setOnClickListener(v -> {
            JSONObject row = find(pending, f.str("part_id"));
            if (row == null || Lookups.j(row, "worksheet_completed_at").isEmpty()) { a.toast("Complete and save this Part Worksheet before automated validation."); return; }
            String val = f.str("validated_by_employee_id"), appr = f.str("approved_by_employee_id"), pid = f.str("part_id");
            if (val.isEmpty()) { a.toast("Select Added Part · Validated By."); return; }
            IncRmtcFlow.run(a, "Validating added Part…", () -> {
                api.update("rmtc_approvals", rid, new JSONObject().put("validated_by_employee_id", val).put("approved_by_employee_id", appr.isEmpty() ? JSONObject.NULL : appr));
                api.rpc("qsms_validate_added_rmtc_part", new JSONObject().put("p_rmtc_id", rid).put("p_part_id", pid));
                return "Added Part validation completed. Existing accepted Part releases were not changed.";
            }, this::reload);
        });
        decide.setOnClickListener(v -> {
            JSONObject row = find(pending, f.str("part_id"));
            String appr = f.str("approved_by_employee_id"), d = f.str("disposition"), reason = f.str("reason"), pid = f.str("part_id");
            if (row == null || Lookups.j(row, "worksheet_completed_at").isEmpty()) { a.toast("Complete and save this Part Worksheet first."); return; }
            if (appr.isEmpty()) { a.toast("Select Added Part · Approved / Decided By."); return; }
            if (d.isEmpty() || d.equals("PENDING")) { a.toast("Select the final decision (not Pending)."); return; }
            IncRmtcFlow.run(a, "Saving added Part decision…", () -> {
                api.rpc("qsms_decide_added_rmtc_part", new JSONObject().put("p_rmtc_id", rid).put("p_part_id", pid).put("p_disposition", d)
                    .put("p_reason", reason.isEmpty() ? JSONObject.NULL : reason).put("p_approved_by_employee_id", appr));
                IncQrLabel.onApproved(api, rid, false);  // R39 (web _run_qr_hook send_email=False): refresh the stored QR label (parts line)
                return "Added Part final decision saved. Existing accepted Parts remain released.";
            }, this::reload);
        });
    }

    private static JSONObject find(List<JSONObject> rows, String partId) {
        for (JSONObject r : rows) if (partId.equals(Lookups.j(r, "part_id"))) return r;
        return null;
    }

    private void showPending(LinearLayout box, List<JSONObject> pending, String partId) {
        box.removeAllViews();
        JSONObject r = find(pending, partId);
        if (r == null) return;
        String[][] info = {{"approval_status", "Automated Validation"}, {"source_status", "Source"}, {"material_grade_status", "Material Grade"},
            {"raw_material_status", "Raw Material"}, {"chemistry_status", "Chemistry"}, {"jominy_status", "Jominy"}, {"requirement_status", "Requirements"},
            {"disposition", "Current Decision"}};
        box.addView(Ui.pair(a, "Worksheet", Lookups.j(r, "worksheet_completed_at").isEmpty() ? "PENDING" : "COMPLETED"));
        for (String[] i : info) box.addView(Ui.pair(a, i[1], Ui.pretty(Lookups.j(r, i[0]))));
    }
}
