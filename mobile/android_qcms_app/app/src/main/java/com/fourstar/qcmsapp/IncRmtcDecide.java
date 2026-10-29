package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

/**
 * RMTC · Validation & Decision step 3 (rmtc_pages.render_approval "3 · Save Decisions"): automated results per
 * covered part are read-only, the final disposition and reason are chosen per part, then rpc qsms_decide_rmtc.
 */
final class IncRmtcDecide extends Screen {
    private final String rid;
    private JSONObject record;
    private List<JSONObject> covered;
    private Map<String, JSONObject> parts;
    private final List<FormView> forms = new ArrayList<>();
    private FormView approverForm;
    private Button save;
    private List<JSONObject> chemistry = new ArrayList<>(), jominy = new ArrayList<>();
    private java.util.LinkedHashMap<String, Boolean> sections;

    IncRmtcDecide(MainActivity a, String rmtcId) { super(a); this.rid = rmtcId; }

    @Override public String title() { return "RMTC · Final Decision"; }
    @Override public String subtitle() { return record == null ? "Validation & Decision" : Lookups.j(record, "rmtc_number") + " · Heat " + Lookups.j(record, "heat_number"); }
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
            Lookups.rows(api, IncCalc.employeeLookup("RMTC_APPROVE"));
            // R39: entered chemistry / Jominy for the horizontal review grids + sections applicable
            List<JSONObject> ch = IncCalc.list(api.rows("rmtc_chemistry_results?select=*&rmtc_approval_id=eq." + Api.enc(rid) + "&limit=500"));
            List<JSONObject> jo = IncCalc.list(api.rows("rmtc_jominy_results?select=*&rmtc_approval_id=eq." + Api.enc(rid) + "&limit=500"));
            java.util.LinkedHashMap<String, Boolean> sec = IncRmtcSections.load(api, rid, r);
            return new Object[]{r, cov, p, ch, jo, sec};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            record = (JSONObject) res[0];
            @SuppressWarnings("unchecked") List<JSONObject> c = (List<JSONObject>) res[1];
            @SuppressWarnings("unchecked") Map<String, JSONObject> p = (Map<String, JSONObject>) res[2];
            covered = c; parts = p;
            @SuppressWarnings("unchecked") List<JSONObject> ch = (List<JSONObject>) res[3];
            @SuppressWarnings("unchecked") List<JSONObject> jo = (List<JSONObject>) res[4];
            @SuppressWarnings("unchecked") java.util.LinkedHashMap<String, Boolean> sec = (java.util.LinkedHashMap<String, Boolean>) res[5];
            chemistry = ch; jominy = jo; sections = sec;
            a.rebuildTitle(this);
            render();
        });
        return scroll;
    }

    private void render() {
        LinearLayout head = Ui.card(a);
        head.addView(Ui.pair(a, "Workflow", Ui.pretty(IncCalc.firstText(Lookups.j(record, "status"), "DRAFT"))));
        head.addView(Ui.pair(a, "Validation", Ui.pretty(IncCalc.firstText(Lookups.j(record, "validation_result"), "NOT_EVALUATED"))));
        head.addView(Ui.pair(a, "Final Disposition", Ui.pretty(IncCalc.firstText(Lookups.j(record, "disposition"), "PENDING"))));
        head.addView(Ui.pair(a, "Covered Parts", String.valueOf(covered.size())));
        add(head, 0);
        reviewGrids();
        boolean open = "APPROVAL_PENDING".equals(Lookups.j(record, "status"));
        if (!open) add(Ui.text(a, "Decisions can be saved only while the RMTC is Approval Pending (current: " + Ui.pretty(Lookups.j(record, "status")) + ").", 12.5f, Ui.AMBER_FG, false), 8);
        add(Ui.text(a, "Reason is mandatory for On Hold, Accepted Under Reserve and Rejected, and for Accepted when the automated recommendation is not Approved.", 11.5f, Ui.MUTED, false), 8);
        forms.clear();
        for (JSONObject c : covered) {
            add(Ui.label(a, IncRmtcData.partLabel(parts, Lookups.j(c, "part_id"))), 12);
            LinearLayout card = Ui.card(a);
            String[][] info = {{"approval_status", "Automated Recommendation"}, {"source_status", "Source"}, {"material_grade_status", "Material Grade"},
                {"raw_material_status", "Raw Material"}, {"chemistry_status", "Chemistry"}, {"jominy_status", "Jominy"}, {"requirement_status", "Requirements"},
                {"actual_di_status", "Actual DI Status"}, {"calculated_di_status", "Calculated DI Status"}};
            for (String[] i : info) card.addView(Ui.pair(a, i[1], Ui.pretty(Lookups.j(c, i[0]))));
            card.addView(Ui.pair(a, "Worksheet", Lookups.j(c, "worksheet_completed_at").isEmpty() ? "Pending" : "Completed"));
            FormView f = new FormView(a, Arrays.asList(
                Field.select("disposition", "Final Decision", IncCalc.DISPOSITIONS).req(),
                Field.area("reason", "Decision / Reserve Reason")));
            f.set("disposition", IncCalc.firstText(Lookups.j(c, "disposition"), "PENDING"));
            f.set("reason", Lookups.j(c, "decision_reason"));
            card.addView(f, Ui.matchWrap(a, 6));
            add(card, 2);
            forms.add(f);
        }
        approverForm = new FormView(a, Arrays.asList(Field.lookup("approved_by_employee_id", "Approved / Decided By", IncCalc.employeeLookup("RMTC_APPROVE")).req()));
        String cur = IncCalc.firstText(Lookups.j(record, "approved_by_employee_id"), Lookups.j(record, "decision_by_employee_id"));
        if (!cur.isEmpty()) approverForm.set("approved_by_employee_id", cur);
        add(approverForm, 14);
        save = Ui.primary(a, "3 · Save Decisions");
        save.setEnabled(open);
        add(save, 14);
        save.setOnClickListener(v -> save());
    }

    private void save() {
        if (!"APPROVAL_PENDING".equals(Lookups.j(record, "status"))) { a.toast("The RMTC is not Approval Pending."); return; }
        if (Lookups.j(record, "validated_at").isEmpty()) { a.toast("Validate the RMTC against masters first."); return; }
        String approver = approverForm.str("approved_by_employee_id");
        if (approver.isEmpty()) { a.toast("Select Approved / Decided By."); return; }
        JSONArray decisions = new JSONArray();
        try {
            for (int i = 0; i < covered.size(); i++) {
                JSONObject c = covered.get(i);
                String disp = IncCalc.firstText(forms.get(i).str("disposition"), "PENDING");
                String reason = forms.get(i).str("reason");
                String partNo = Lookups.j(parts.containsKey(Lookups.j(c, "part_id")) ? parts.get(Lookups.j(c, "part_id")) : new JSONObject(), "part_number");
                String automated = Lookups.j(c, "approval_status").toUpperCase(java.util.Locale.ROOT);
                if ((disp.equals("ON_HOLD") || disp.equals("ACCEPTED_UNDER_RESERVE") || disp.equals("REJECTED")) && reason.isEmpty()) {
                    a.toast("Reason is mandatory for " + partNo + ": " + Ui.pretty(disp) + "."); return;
                }
                if (disp.equals("ACCEPTED") && !automated.equals("APPROVED") && reason.isEmpty()) {
                    a.toast("Manual acceptance reason is mandatory for " + partNo + "."); return;
                }
                decisions.put(new JSONObject().put("part_id", Lookups.j(c, "part_id")).put("disposition", disp).put("reason", reason.isEmpty() ? JSONObject.NULL : reason));
            }
        } catch (Exception e) { a.toast(Api.message(e)); return; }
        save.setEnabled(false);
        Api.async(() -> api.rpcValue("qsms_decide_rmtc", new JSONObject().put("p_rmtc_id", rid).put("p_decisions", decisions).put("p_approved_by_employee_id", approver)),
            (res, err) -> {
                save.setEnabled(true);
                if (err != null) { a.toast(Api.message(err)); return; }
                String d = res instanceof JSONObject ? Lookups.j((JSONObject) res, "disposition") : "";
                a.toast("RMTC decision saved" + (d.isEmpty() ? "." : " as " + Ui.pretty(d) + "."));
                // R39: same as the website (_run_qr_hook): approved -> QR label PNG attachment + Quality-department e-mail
                Api.async(() -> IncQrLabel.approved(IncRmtcData.rmtc(api, rid)) ? IncQrLabel.onApproved(api, rid, true) : null, (qr, qerr) -> {
                    if (qr != null) a.toast(IncQrLabel.summary(qr));
                });
                a.back();
            });
    }

    /** R39 · rmtc_pages._render_approval_grids: entered chemistry / Jominy per Part as HORIZONTAL grids; not-applicable sections hidden. */
    private void reviewGrids() {
        boolean showChem = IncRmtcSections.on(sections, "chemistry"), showJom = IncRmtcSections.on(sections, "jominy");
        List<String> off = IncRmtcSections.notApplicableLabels(sections);
        if (!off.isEmpty()) add(Ui.text(a, "Sections not applicable for this RMTC: " + String.join(", ", off), 12, Ui.AMBER_FG, false), 6);
        boolean any = false;
        for (JSONObject c : covered) {
            String pid = Lookups.j(c, "part_id");
            List<JSONObject> ch = new ArrayList<>(), jo = new ArrayList<>();
            if (showChem) for (JSONObject r : chemistry) if (pid.equals(Lookups.j(r, "part_id")) && !"NOT_APPLICABLE".equalsIgnoreCase(Lookups.j(r, "result"))) ch.add(r);
            if (showJom) for (JSONObject r : jominy) if (pid.equals(Lookups.j(r, "part_id")) && !"NOT_APPLICABLE".equalsIgnoreCase(Lookups.j(r, "applicability"))) jo.add(r);
            if (ch.isEmpty() && jo.isEmpty()) continue;
            if (!any) add(Ui.label(a, "CHEMISTRY & JOMINY REVIEW"), 12);
            any = true;
            String number = Lookups.j(parts.containsKey(pid) ? parts.get(pid) : new JSONObject(), "part_number");
            if (number.isEmpty()) number = pid;
            if (!ch.isEmpty()) {
                List<String[]> t = RptReports.chemHorizontal(ch, new String[][]{{"Minimum", "minimum_value"}, {"Maximum", "maximum_value"}, {"Actual", "actual_value"}, {"Status", "result"}});
                add(new DataGrid(a, number + " · Chemical Composition", ChemGrid.headers(t), ChemGrid.data(t), 260, null), 4);
            }
            if (!jo.isEmpty()) {
                List<String[]> t = RptReports.jominyHorizontal(jo, new String[][]{{"Min HRC", "minimum_hrc"}, {"Max HRC", "maximum_hrc"}, {"Actual HRC", "actual_hrc"}, {"Result", "result"}});
                add(new DataGrid(a, number + " · Jominy (inch / mm)", ChemGrid.headers(t), ChemGrid.data(t), 300, null), 4);
            }
        }
    }
}
