package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Corrective / preventive action plan item (quality_complaint_actions): next action number = max + 1,
 * description + Four Star owner required, evidence required before COMPLETED, completion date only when COMPLETED.
 */
final class CalComplaintAction extends CalEditScreen {
    private final JSONObject complaint;
    private int nextNo = 1;

    CalComplaintAction(MainActivity a, JSONObject complaint, String actionId) {
        super(a, actionId, null);
        this.complaint = complaint;
    }

    @Override public String title() { return (id == null ? "New action · " : "Edit action · ") + Lookups.j(complaint, "complaint_number"); }
    @Override public String subtitle() { return "Corrective / preventive action plan & responsibility"; }
    @Override protected String table() { return "quality_complaint_actions"; }
    @Override protected String saveLabel() { return id == null ? "Add Action to Plan" : "Update Action"; }
    @Override protected String savedMessage() { return "Complaint Action Plan item saved successfully."; }

    @Override
    protected void load() throws Exception {
        JSONArray rows = api.rows("quality_complaint_actions?select=action_no&complaint_id=eq." + Lookups.j(complaint, "id") + "&limit=5000");
        int max = 0;
        for (int i = 0; i < rows.length(); i++) max = Math.max(max, CalUtil.intOr(rows.optJSONObject(i), "action_no", 0));
        nextNo = max + 1;
    }

    @Override
    protected void buildForm(CalSections f) {
        Field no = Field.integer("action_no", "Action No.").req().range(1, 100000).def(nextNo);
        if (id != null) no.ro();
        f.section("Action plan item",
            no,
            Field.select("action_type", "Action Type", CalComplaints.ACTION_TYPES).req().def("OCCURRENCE_CORRECTIVE"),
            Field.select("status", "Action Status", CalComplaints.ACTION_STATUSES).req().def("OPEN"),
            Field.area("action_description", "Action Description").req(),
            Field.lookup("owner_employee_id", "Four Star Responsible Person", Lookups.employees()).req(),
            Field.text("external_owner_name", "Customer / Supplier Responsible").def(Lookups.j(complaint, "external_responsible_name")),
            Field.date("target_date", "Target Date").req().def(Ui.today()),
            Field.date("completion_date", "Completion Date").def(Ui.today()),
            Field.area("evidence", "Implementation Evidence / Reference").hint("Required before the action can be marked Completed"),
            Field.area("effectiveness_result", "Action Effectiveness Result"));
    }

    @Override
    protected void afterFill() {
        quiet = true;
        if (form.str("completion_date").isEmpty()) form.set("completion_date", Ui.today());
        if (form.str("target_date").isEmpty()) form.set("target_date", Ui.today());
        if (form.str("external_owner_name").isEmpty()) form.set("external_owner_name", Lookups.j(complaint, "external_responsible_name"));
        quiet = false;
        visibility();
        form.onChange((k, v) -> { if (!quiet) visibility(); });
    }

    private void visibility() { form.setVisible("completion_date", "COMPLETED".equals(form.str("status"))); }

    @Override
    protected String check() {
        if (form.str("action_description").isEmpty() || form.str("owner_employee_id").isEmpty())
            return "Action Description and Four Star Responsible Person are mandatory.";
        if ("COMPLETED".equals(form.str("status")) && form.str("evidence").isEmpty())
            return "Implementation Evidence / Reference is required before an action can be marked Completed.";
        return null;
    }

    @Override
    protected JSONObject collect() throws Exception {
        String status = form.str("status");
        JSONObject p = new JSONObject();
        p.put("complaint_id", Lookups.j(complaint, "id"));
        p.put("action_no", Math.round(CalUtil.dbl(form.num("action_no"))));
        p.put("action_type", form.str("action_type"));
        p.put("action_description", form.str("action_description"));
        p.put("owner_employee_id", form.str("owner_employee_id"));
        p.put("external_owner_name", CalUtil.v(form.str("external_owner_name")));
        p.put("target_date", CalUtil.id(form.str("target_date")));
        p.put("completion_date", "COMPLETED".equals(status) ? CalUtil.id(form.str("completion_date")) : JSONObject.NULL);
        p.put("status", status);
        p.put("evidence", CalUtil.v(form.str("evidence")));
        p.put("effectiveness_result", CalUtil.v(form.str("effectiveness_result")));
        return p;
    }

    @Override
    protected JSONObject persist(JSONObject p) throws Exception {
        return api.save("quality_complaint_actions", id, p);
    }
}
