package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Complaint constants and rules shared by the complaint screens (exact ports from app_pages/complaints.py). */
final class CalComplaints {
    private CalComplaints() { }

    static final String[] STATUSES = {"OPEN", "CONTAINMENT", "ROOT_CAUSE", "CORRECTIVE_ACTION", "VERIFICATION", "CLOSED", "CANCELLED"};
    static final String[] ENTRY_STATUSES = {"OPEN", "CONTAINMENT", "ROOT_CAUSE", "CORRECTIVE_ACTION", "VERIFICATION", "CANCELLED"};
    static final String[] SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"};
    static final String[] DEBIT_STATUSES = {"NOT_REQUIRED", "PENDING", "RELEASED", "PARTIALLY_SETTLED", "SETTLED", "WAIVED"};
    static final String[] CURRENCIES = {"INR", "EUR", "USD", "GBP", "JPY"};
    static final String[] FOLLOWUP_TYPES = {"FOLLOW_UP", "CUSTOMER_UPDATE", "SUPPLIER_UPDATE", "INTERNAL_REVIEW", "COMMERCIAL", "CLOSURE_REVIEW"};
    static final String[] ANALYSIS_METHODS = {"5_WHY", "FISHBONE", "8D", "PARETO", "OTHER"};
    static final String[] ANALYSIS_LABELS = {"5 Why", "Fishbone", "8D", "Pareto", "Other"};
    static final String[] ACTION_TYPES = {"CORRECTION", "CONTAINMENT", "OCCURRENCE_CORRECTIVE", "ESCAPE_CORRECTIVE", "SYSTEMIC_PREVENTIVE", "VERIFICATION"};
    static final String[] ACTION_STATUSES = {"OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED"};

    static final String ENTITY = "QUALITY_COMPLAINT";
    static final String FOLDER = "complaints";
    static final String[] FIXED_SLOTS = {"COMPLAINT_SOURCE", "ANALYSIS_EVIDENCE", "CLOSURE_REPORT"};
    static final String[] FIXED_LABELS = {"Complaint / Claim Document", "Analysis Evidence", "8D / Closure Report"};

    static String partyWord(String type) { return "CUSTOMER".equals(type) ? "Customer" : "Supplier"; }

    static boolean done(JSONObject action) {
        String s = Lookups.j(action, "status");
        return "COMPLETED".equals(s) || "CANCELLED".equals(s);
    }

    static boolean actionOverdue(JSONObject action) {
        String s = Lookups.j(action, "status");
        if (s.isEmpty()) s = "OPEN";
        if ("COMPLETED".equals(s) || "CANCELLED".equals(s)) return false;
        String t = Lookups.j(action, "target_date");
        if (t.length() < 10) return false;
        try { return LocalDate.parse(t.substring(0, 10)).isBefore(LocalDate.now()); } catch (Exception e) { return false; }
    }

    /** _closure_readiness: list of gaps (empty = ready). */
    static List<String> closureGaps(JSONObject complaint, JSONArray actions) {
        List<String> gaps = new ArrayList<>();
        if (!CalUtil.isTrue(complaint, "root_cause_confirmed")) gaps.add("Root cause confirmation is pending");
        if (!CalUtil.isTrue(complaint, "effectiveness_verified")) gaps.add("Corrective-action effectiveness verification is pending");
        int open = 0;
        for (int i = 0; actions != null && i < actions.length(); i++) {
            JSONObject r = actions.optJSONObject(i);
            if (r != null && !done(r)) open++;
        }
        if (open > 0) gaps.add(open + " action-plan item(s) are still open");
        if (Lookups.j(complaint, "closure_date").isEmpty()) gaps.add("Actual Closure Date is not recorded");
        return gaps;
    }

    /** _analysis_progress: six stages with state complete / current / pending. */
    static String[] progress(JSONObject c, JSONArray actions) {
        boolean containmentDone = !Lookups.j(c, "containment_completed_date").isEmpty() || !Lookups.j(c, "containment_effectiveness").isEmpty();
        boolean rcaDone = CalUtil.isTrue(c, "root_cause_confirmed");
        int live = 0, completed = 0;
        for (int i = 0; actions != null && i < actions.length(); i++) {
            JSONObject r = actions.optJSONObject(i);
            if (r == null || "CANCELLED".equals(Lookups.j(r, "status"))) continue;
            live++;
            if ("COMPLETED".equals(Lookups.j(r, "status"))) completed++;
        }
        boolean actionsDone = live > 0 && completed == live;
        boolean verified = CalUtil.isTrue(c, "effectiveness_verified");
        if ("CLOSED".equals(Lookups.j(c, "status"))) return new String[]{"complete", "complete", "complete", "complete", "complete", "complete"};
        if (verified) return new String[]{"complete", "complete", "complete", actionsDone ? "complete" : "current", "current", "pending"};
        if (rcaDone) return new String[]{"complete", containmentDone ? "complete" : "current", "complete", "current", "pending", "pending"};
        if (containmentDone || !Lookups.j(c, "why_1").isEmpty() || !Lookups.j(c, "occurrence_root_cause").isEmpty())
            return new String[]{"complete", containmentDone ? "complete" : "current", "current", "pending", "pending", "pending"};
        return new String[]{"complete", "current", "pending", "pending", "pending", "pending"};
    }

    static final String[] STAGES = {"Complaint", "Containment", "Root Cause", "Corrective Action", "Verification", "Closure"};

    /** Workflow progress strip (two rows of three chips). */
    static LinearLayout progressView(MainActivity a, JSONObject c, JSONArray actions) {
        String[] states = progress(c, actions);
        LinearLayout box = Ui.vbox(a);
        for (int row = 0; row < 2; row++) {
            LinearLayout line = Ui.hbox(a);
            for (int i = row * 3; i < row * 3 + 3; i++) {
                String tone = "complete".equals(states[i]) ? "green" : ("current".equals(states[i]) ? "teal" : "grey");
                TextView chip = Ui.chip(a, STAGES[i], tone);
                chip.setGravity(Gravity.CENTER);
                LinearLayout.LayoutParams lp = Ui.weight(1);
                lp.rightMargin = i % 3 < 2 ? Ui.dp(a, 5) : 0;
                line.addView(chip, lp);
            }
            box.addView(line, Ui.matchWrap(a, row == 0 ? 0 : 5));
        }
        return box;
    }

    /** Pick one existing action (for "Update corrective action"). */
    static void pickAction(MainActivity a, Api api, JSONObject complaint, Runnable refresh) {
        String cid = Lookups.j(complaint, "id");
        Api.async(() -> api.rows("quality_complaint_actions?select=id,action_no,action_type,action_description,status&complaint_id=eq." + cid + "&order=action_no.asc&limit=5000"),
            (rows, err) -> {
                if (err != null) { a.toast(Api.message(err)); return; }
                if (rows.length() == 0) { a.toast("No action-plan items yet - use Add corrective action."); return; }
                String[] names = new String[rows.length()];
                for (int i = 0; i < rows.length(); i++) {
                    JSONObject r = rows.optJSONObject(i);
                    String desc = Lookups.j(r, "action_description");
                    if (desc.length() > 70) desc = desc.substring(0, 70);
                    names[i] = String.format(Locale.ROOT, "A%02d · %s · %s · %s", CalUtil.intOr(r, "action_no", 0), Ui.pretty(Lookups.j(r, "action_type")), desc, Ui.pretty(Lookups.j(r, "status")));
                }
                new AlertDialog.Builder(a).setTitle("Action plan item").setItems(names, (d, w) ->
                    a.push(new CalComplaintAction(a, complaint, Lookups.j(rows.optJSONObject(w), "id"))))
                    .setNegativeButton("Back", null).show();
            });
    }
}
