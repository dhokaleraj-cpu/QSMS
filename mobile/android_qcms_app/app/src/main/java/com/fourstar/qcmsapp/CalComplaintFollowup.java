package com.fourstar.qcmsapp;

import org.json.JSONObject;

/** Complaint follow-up (quality_complaint_followups) with the optional status update of the complaint. */
final class CalComplaintFollowup extends CalEditScreen {
    private final JSONObject complaint;

    CalComplaintFollowup(MainActivity a, JSONObject complaint) {
        super(a, null, null);
        this.complaint = complaint;
    }

    @Override public String title() { return "Follow-up · " + Lookups.j(complaint, "complaint_number"); }
    @Override public String subtitle() { return "Complaint follow-up & closure tracking"; }
    @Override protected String table() { return null; }
    @Override protected String saveLabel() { return "Add Follow-up"; }
    @Override protected String savedMessage() { return "Complaint follow-up saved successfully."; }

    @Override
    protected void buildForm(CalSections f) {
        String[] after = new String[CalComplaints.STATUSES.length + 1];
        after[0] = "NO_CHANGE";
        System.arraycopy(CalComplaints.STATUSES, 0, after, 1, CalComplaints.STATUSES.length);
        String owner = Lookups.j(complaint, "fourstar_responsible_employee_id");
        f.section("Follow-up",
            Field.date("followup_date", "Follow-up Date").req().def(Ui.today()),
            Field.select("followup_type", "Follow-up Type", CalComplaints.FOLLOWUP_TYPES).req().def("FOLLOW_UP"),
            Field.lookup("responsible_employee_id", "Responsible Employee", Lookups.employees()).req().def(owner.isEmpty() ? null : owner),
            Field.date("next_followup_date", "Next Follow-up Date").def(Ui.today()),
            Field.select("_status_after", "Status after Follow-up", after).req().def("NO_CHANGE"),
            Field.area("remarks", "Follow-up Remarks / Action Update").req());
    }

    @Override
    protected String check() {
        if (form.str("remarks").isEmpty() || form.str("responsible_employee_id").isEmpty()) return "Follow-up Remarks and Responsible Employee are mandatory.";
        return null;
    }

    @Override
    protected JSONObject collect() throws Exception {
        String after = form.str("_status_after");
        JSONObject p = new JSONObject();
        p.put("complaint_id", Lookups.j(complaint, "id"));
        p.put("followup_date", CalUtil.id(form.str("followup_date")));
        p.put("followup_type", form.str("followup_type"));
        p.put("remarks", form.str("remarks"));
        p.put("next_followup_date", CalUtil.id(form.str("next_followup_date")));
        p.put("responsible_employee_id", form.str("responsible_employee_id"));
        p.put("status_after_followup", after.isEmpty() || "NO_CHANGE".equals(after) ? JSONObject.NULL : after);
        return p;
    }

    @Override
    protected JSONObject persist(JSONObject p) throws Exception {
        JSONObject saved = api.insert("quality_complaint_followups", p);
        if (!p.isNull("status_after_followup")) {
            String status = p.optString("status_after_followup");
            JSONObject changes = new JSONObject().put("status", status);
            if ("CLOSED".equals(status)) changes.put("closure_date", p.opt("followup_date"));
            try {
                api.update("quality_complaints", Lookups.j(complaint, "id"), changes);
            } catch (Exception e) {
                warning = "The follow-up was saved, but the complaint status could not be updated: " + Api.message(e);
            }
        }
        return saved;
    }
}
