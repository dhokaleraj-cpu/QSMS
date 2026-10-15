package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Detailed Complaint Analysis & CAPA (complaints.py render_analysis, sections B-E): problem definition,
 * containment, 5-Why / root cause and effectiveness verification. Status is calculated exactly like the website.
 */
final class CalComplaintAnalysis extends CalEditScreen {
    private JSONArray actions = new JSONArray();

    CalComplaintAnalysis(MainActivity a, String complaintId) { super(a, complaintId, null); }

    @Override public String title() { return "Detailed Analysis · " + (existing == null ? "Complaint" : Lookups.j(existing, "complaint_number")); }
    @Override public String subtitle() { return "Problem definition · containment · root cause · effectiveness"; }
    @Override protected String table() { return "quality_complaints"; }
    @Override protected String saveLabel() { return "Save Detailed Complaint Analysis"; }
    @Override protected String savedMessage() { return "Detailed Complaint Analysis saved successfully."; }

    @Override
    protected void load() throws Exception {
        actions = api.rows("quality_complaint_actions?select=id,action_no,status,target_date&complaint_id=eq." + id + "&order=action_no.asc&limit=5000");
    }

    @Override
    protected void buildForm(CalSections f) {
        JSONObject c = existing;
        int open = 0, overdue = 0;
        for (int i = 0; i < actions.length(); i++) {
            JSONObject r = actions.optJSONObject(i);
            if (r != null && !CalComplaints.done(r)) { open++; if (CalComplaints.actionOverdue(r)) overdue++; }
        }
        f.note(CalUtil.infoCard(a, Lookups.join(Lookups.j(c, "complaint_number"), Lookups.j(c, "subject")),
            "Status " + Ui.pretty(Lookups.j(c, "status").isEmpty() ? "OPEN" : Lookups.j(c, "status"))
                + " · Root cause " + (CalUtil.isTrue(c, "root_cause_confirmed") ? "CONFIRMED" : "PENDING")
                + " · Open actions " + open + " (" + overdue + " overdue)"
                + " · Effectiveness " + (CalUtil.isTrue(c, "effectiveness_verified") ? "VERIFIED" : "PENDING")));
        f.note(CalComplaints.progressView(a, c, actions));
        f.section("B · Problem definition & impact",
            Field.lookup("process_id", "Related Process", Lookups.processes()).hint("Blank = process not linked"),
            Field.text("defect_mode", "Defect / Failure Mode"),
            Field.text("lot_batch_number", "Lot / Batch Number"),
            Field.text("heat_number", "Heat Number"),
            Field.text("detection_point", "Detection Point / Inspection Stage"),
            Field.area("problem_what", "What exactly happened?"),
            Field.area("problem_where", "Where did it occur / where was it detected?"),
            Field.area("problem_when", "When / under what operating or inspection condition?"),
            Field.area("occurrence_pattern", "Occurrence Pattern / Frequency"),
            Field.area("impact_summary", "Customer / Supplier / Production Impact & Risk"));
        f.section("C · Immediate correction & containment",
            Field.area("immediate_correction", "Immediate Correction / Disposition"),
            Field.area("containment_action", "Containment Action"),
            Field.lookup("containment_responsible_employee_id", "Containment Responsible", Lookups.employees()),
            Field.date("containment_due_date", "Containment Due Date"),
            Field.date("containment_completed_date", "Containment Completed Date").hint("Saved only when a containment action is recorded"),
            Field.area("containment_effectiveness", "Containment Effectiveness / Evidence"));
        f.section("D · Root cause analysis",
            Field.select("analysis_method", "Analysis Method", CalComplaints.ANALYSIS_METHODS).labels(CalComplaints.ANALYSIS_LABELS).req().def("5_WHY"),
            Field.lookup("root_cause_responsible_employee_id", "Root Cause Analysis Responsible", Lookups.employees()),
            Field.bool("root_cause_confirmed", "Root Cause Confirmed"),
            Field.area("why_1", "Why 1"), Field.area("why_2", "Why 2"), Field.area("why_3", "Why 3"),
            Field.area("why_4", "Why 4"), Field.area("why_5", "Why 5"),
            Field.area("occurrence_root_cause", "Occurrence Root Cause - Why defect happened"),
            Field.area("escape_root_cause", "Escape / Detection Root Cause - Why it was not detected"),
            Field.area("systemic_root_cause", "Systemic Root Cause - Why system allowed recurrence"),
            Field.area("root_cause_evidence", "Root Cause Evidence / Validation"),
            Field.date("root_cause_confirmed_date", "Root Cause Confirmation Date"));
        f.section("E · Effectiveness verification",
            Field.area("verification_plan", "Verification Plan"),
            Field.area("effectiveness_criteria", "Acceptance / Effectiveness Criteria"),
            Field.area("verification_result", "Verification Result / Evidence"),
            Field.bool("effectiveness_verified", "Effectiveness Verified"),
            Field.date("effectiveness_verified_date", "Effectiveness Verified Date"),
            Field.lookup("effectiveness_verified_by_employee_id", "Verified By", Lookups.employees()),
            Field.area("recurrence_check_result", "Recurrence Check / Similar-Part Review"));
    }

    @Override
    protected void afterFill() {
        JSONObject c = existing;
        String owner = Lookups.j(c, "fourstar_responsible_employee_id");
        quiet = true;
        if (form.str("problem_what").isEmpty()) form.set("problem_what", Lookups.j(c, "description"));
        if (form.str("containment_responsible_employee_id").isEmpty() && !owner.isEmpty()) form.set("containment_responsible_employee_id", owner);
        if (form.str("root_cause_responsible_employee_id").isEmpty() && !owner.isEmpty()) form.set("root_cause_responsible_employee_id", owner);
        if (form.str("occurrence_root_cause").isEmpty()) form.set("occurrence_root_cause", Lookups.j(c, "root_cause"));
        if (form.str("analysis_method").isEmpty()) form.set("analysis_method", "5_WHY");
        for (String k : new String[]{"containment_due_date", "containment_completed_date", "root_cause_confirmed_date", "effectiveness_verified_date"})
            if (form.str(k).isEmpty()) form.set(k, Ui.today());
        quiet = false;
        visibility();
        form.onChange((k, v) -> { if (!quiet) visibility(); });
    }

    private void visibility() {
        form.setVisible("root_cause_confirmed_date", form.bool("root_cause_confirmed"));
        boolean verified = form.bool("effectiveness_verified");
        form.setVisible("effectiveness_verified_date", verified);
        form.setVisible("effectiveness_verified_by_employee_id", verified);
    }

    @Override
    protected String check() {
        if (form.bool("root_cause_confirmed") && (form.str("occurrence_root_cause").isEmpty() || form.str("root_cause_evidence").isEmpty() || form.str("root_cause_responsible_employee_id").isEmpty()))
            return "Confirmed Root Cause requires Occurrence Root Cause, supporting evidence and a responsible employee.";
        if (form.bool("effectiveness_verified") && (form.str("verification_result").isEmpty() || form.str("effectiveness_criteria").isEmpty() || form.str("effectiveness_verified_by_employee_id").isEmpty()))
            return "Effectiveness verification requires criteria, result/evidence and the verifying employee.";
        return null;
    }

    @Override
    protected JSONObject collect() throws Exception {
        boolean rootConfirmed = form.bool("root_cause_confirmed");
        boolean verified = form.bool("effectiveness_verified");
        String containment = form.str("containment_action");
        String occurrence = form.str("occurrence_root_cause");
        // Status calculated exactly like the website (CLOSED / CANCELLED stay unchanged).
        String status = Lookups.j(existing, "status");
        if (status.isEmpty()) status = "OPEN";
        if (!"CLOSED".equals(status) && !"CANCELLED".equals(status)) {
            if (verified) status = "VERIFICATION";
            else if (rootConfirmed) status = "CORRECTIVE_ACTION";
            else if (!form.str("why_1").isEmpty() || !occurrence.isEmpty()) status = "ROOT_CAUSE";
            else if (!containment.isEmpty()) status = "CONTAINMENT";
        }
        JSONObject p = new JSONObject();
        p.put("process_id", CalUtil.id(form.str("process_id")));
        for (String k : new String[]{"defect_mode", "lot_batch_number", "heat_number", "problem_what", "problem_where", "problem_when",
            "detection_point", "occurrence_pattern", "impact_summary", "immediate_correction", "containment_action"}) p.put(k, CalUtil.v(form.str(k)));
        p.put("containment_responsible_employee_id", CalUtil.id(form.str("containment_responsible_employee_id")));
        p.put("containment_due_date", CalUtil.id(form.str("containment_due_date")));
        p.put("containment_completed_date", containment.isEmpty() ? JSONObject.NULL : CalUtil.id(form.str("containment_completed_date")));
        p.put("containment_effectiveness", CalUtil.v(form.str("containment_effectiveness")));
        p.put("analysis_method", form.str("analysis_method"));
        for (int i = 1; i <= 5; i++) p.put("why_" + i, CalUtil.v(form.str("why_" + i)));
        p.put("occurrence_root_cause", CalUtil.v(occurrence));
        p.put("root_cause", CalUtil.v(occurrence));
        p.put("escape_root_cause", CalUtil.v(form.str("escape_root_cause")));
        p.put("systemic_root_cause", CalUtil.v(form.str("systemic_root_cause")));
        p.put("root_cause_evidence", CalUtil.v(form.str("root_cause_evidence")));
        p.put("root_cause_confirmed", rootConfirmed);
        p.put("root_cause_confirmed_date", rootConfirmed ? CalUtil.id(form.str("root_cause_confirmed_date")) : JSONObject.NULL);
        p.put("root_cause_responsible_employee_id", CalUtil.id(form.str("root_cause_responsible_employee_id")));
        p.put("verification_plan", CalUtil.v(form.str("verification_plan")));
        p.put("effectiveness_criteria", CalUtil.v(form.str("effectiveness_criteria")));
        p.put("verification_result", CalUtil.v(form.str("verification_result")));
        p.put("effectiveness_verified", verified);
        p.put("effectiveness_verified_date", verified ? CalUtil.id(form.str("effectiveness_verified_date")) : JSONObject.NULL);
        p.put("effectiveness_verified_by_employee_id", CalUtil.id(form.str("effectiveness_verified_by_employee_id")));
        p.put("recurrence_check_result", CalUtil.v(form.str("recurrence_check_result")));
        p.put("status", status);
        return p;
    }

    @Override
    protected JSONObject persist(JSONObject p) throws Exception {
        return api.update("quality_complaints", id, p);
    }
}
