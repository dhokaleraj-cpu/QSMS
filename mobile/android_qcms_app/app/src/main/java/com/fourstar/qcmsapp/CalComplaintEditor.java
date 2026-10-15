package com.fourstar.qcmsapp;

import android.widget.TextView;

import org.json.JSONObject;

import java.util.Arrays;

/**
 * Customer / Supplier complaint entry (complaints.py _render_entry): number from qcms_next_complaint_number on the
 * first save, debit-note rules, and every status except CLOSED (closure is controlled by "Close complaint").
 */
final class CalComplaintEditor extends CalEditScreen {
    private final String type;
    private final String word;
    private TextView balance;

    CalComplaintEditor(MainActivity a, String type, String id, JSONObject prefill) {
        super(a, id, prefill);
        this.type = type;
        this.word = CalComplaints.partyWord(type);
    }

    @Override public String title() { return (id == null ? "New · " : "Edit · ") + word + " Complaint"; }
    @Override protected String table() { return "quality_complaints"; }
    @Override protected Module module() { return Catalog.get("CUSTOMER".equals(type) ? "customer_complaints" : "supplier_complaints"); }
    @Override protected String saveLabel() { return id == null ? "Save Complaint" : "Update Complaint"; }

    private boolean closed() { return existing != null && "CLOSED".equals(Lookups.j(existing, "status")); }

    @Override
    protected void buildForm(CalSections f) {
        Field status = closed()
            ? Field.info("status", "Complaint Status").hint("Closed from Close complaint")
            : Field.select("status", "Complaint Status", CalComplaints.ENTRY_STATUSES).req().def("OPEN")
                .hint("Final CLOSED status is controlled from Close complaint after RCA, actions and effectiveness verification.");
        f.section("A · Complaint details",
            Field.info("complaint_number", "Complaint Number"),
            Field.date("complaint_date", "Complaint Date").req().def(Ui.today()),
            Field.select("severity", "Severity", CalComplaints.SEVERITIES).req().def("MEDIUM"),
            status,
            Field.lookup("party_id", word, Lookups.parties(type)).req(),
            Field.lookup("part_id", "Part Number", Lookups.parts()).hint("Blank = not linked to a Part"),
            Field.text("external_reference", word + " Complaint / Reference No."),
            Field.text("subject", "Complaint Subject").req(),
            Field.area("description", "Complaint Description").req(),
            Field.number("affected_quantity", "Affected Quantity").def(0).range(0, Double.MAX_VALUE),
            Field.date("target_closure_date", "Target Closure Date").req().def(Ui.today()),
            Field.text("heat_number", "Heat Number"),
            Field.text("lot_batch_number", "Batch Code / Lot Number"));
        f.section("B · Responsibility",
            Field.lookup("fourstar_responsible_employee_id", "Four Star Responsible Person", Lookups.employees()).req()
                .def(api.employeeId == null || api.employeeId.isEmpty() ? null : api.employeeId),
            Field.text("external_responsible_name", word + " Responsible Person"),
            Field.text("external_responsible_email", word + " Responsible Email"),
            Field.text("external_responsible_phone", word + " Responsible Phone"));
        f.section("D · Containment / root cause / corrective action",
            Field.area("containment_action", "Containment Action"),
            Field.area("root_cause", "Root Cause"),
            Field.area("corrective_action", "Corrective Action"),
            Field.area("verification_result", "Effectiveness / Verification Result"),
            Field.date("closure_date", "Actual Closure Date"),
            Field.area("closure_remarks", "Closure Remarks"));
        f.section("E · Debit note / commercial settlement",
            Field.bool("debit_note_required", "Debit Note Required"),
            Field.select("debit_note_status", "Debit Note Status", CalComplaints.DEBIT_STATUSES).req().def("PENDING"),
            Field.text("debit_note_number", "Debit Note Number"),
            Field.date("debit_note_date", "Debit Note Date").def(Ui.today()),
            Field.select("currency", "Currency", CalComplaints.CURRENCIES).req().def("INR"),
            Field.number("debit_note_amount", "Debit Note Amount").def(0).range(0, Double.MAX_VALUE),
            Field.number("debit_note_settled_amount", "Settled Amount").def(0).range(0, Double.MAX_VALUE),
            Field.date("debit_note_settled_date", "Settled Date").def(Ui.today()),
            Field.area("commercial_remarks", "Commercial / Debit Note Remarks"));
        balance = Ui.text(a, "", 12, Ui.MUTED, true);
        f.note(balance);
        if (id == null) f.note(CalUtil.infoCard(a, "Photographs & attachments",
            "After the complaint is saved, add titled photographs and supporting documents on the complaint record."));
    }

    @Override
    protected void afterFill() {
        quiet = true;
        if (existing == null || Lookups.j(existing, "complaint_number").isEmpty()) form.set("complaint_number", "Auto on Save");
        if (closed()) form.set("status", "Closed");
        else if (!Arrays.asList(CalComplaints.ENTRY_STATUSES).contains(form.str("status"))) form.set("status", "OPEN");
        // Website defaults: dates fall back to today, debit status follows "Debit Note Required".
        boolean req = form.bool("debit_note_required");
        String ds = existing == null ? "" : Lookups.j(existing, "debit_note_status");
        if (!Arrays.asList(CalComplaints.DEBIT_STATUSES).contains(ds)) form.set("debit_note_status", req ? "PENDING" : "NOT_REQUIRED");
        for (String k : new String[]{"complaint_date", "target_closure_date", "debit_note_date", "debit_note_settled_date", "closure_date"})
            if (form.str(k).isEmpty()) form.set(k, Ui.today());
        if (form.str("currency").isEmpty()) form.set("currency", "INR");
        if (form.str("severity").isEmpty()) form.set("severity", "MEDIUM");
        quiet = false;
        visibility();
        form.onChange((k, v) -> {
            if (quiet) return;
            if ("debit_note_required".equals(k)) {
                quiet = true;
                form.set("debit_note_status", form.bool("debit_note_required") ? "PENDING" : "NOT_REQUIRED");
                quiet = false;
            }
            visibility();
        });
    }

    private String status() { return closed() ? "CLOSED" : form.str("status"); }

    private void visibility() {
        boolean debit = form.bool("debit_note_required");
        for (String k : new String[]{"debit_note_status", "debit_note_number", "debit_note_date", "currency", "debit_note_amount", "debit_note_settled_amount"})
            form.setVisible(k, debit);
        form.setVisible("debit_note_settled_date", debit && "SETTLED".equals(form.str("debit_note_status")));
        form.setVisible("closure_date", "CLOSED".equals(status()));
        if (debit) {
            double bal = Math.max(CalUtil.dbl(form.num("debit_note_amount")) - CalUtil.dbl(form.num("debit_note_settled_amount")), 0.0);
            balance.setText("Debit Note Settlement Balance: " + form.str("currency") + " " + Ui.num(bal, 2));
        } else {
            balance.setText("");
        }
    }

    @Override
    protected String check() {
        boolean debit = form.bool("debit_note_required");
        double amount = CalUtil.dbl(form.num("debit_note_amount")), settled = CalUtil.dbl(form.num("debit_note_settled_amount"));
        String ds = form.str("debit_note_status");
        if (form.str("party_id").isEmpty() || form.str("subject").isEmpty() || form.str("description").isEmpty() || form.str("fourstar_responsible_employee_id").isEmpty())
            return word + ", Complaint Subject, Complaint Description and Four Star Responsible Person are mandatory.";
        if (debit && settled > amount + 0.001) return "Settled Amount cannot be greater than the Debit Note Amount.";
        if (debit && "SETTLED".equals(ds) && amount > 0 && settled + 0.001 < amount) return "Debit Note Status cannot be SETTLED until the full Debit Note Amount is settled.";
        if (debit && ("RELEASED".equals(ds) || "PARTIALLY_SETTLED".equals(ds) || "SETTLED".equals(ds)) && form.str("debit_note_number").isEmpty())
            return "Debit Note Number is required when the Debit Note has been released or settled.";
        return null;
    }

    @Override
    protected JSONObject collect() throws Exception {
        boolean debit = form.bool("debit_note_required");
        String status = status();
        String ds = form.str("debit_note_status");
        JSONObject p = new JSONObject();
        p.put("complaint_type", type);
        p.put("complaint_date", form.str("complaint_date"));
        p.put("party_id", form.str("party_id"));
        p.put("part_id", CalUtil.id(form.str("part_id")));
        p.put("external_reference", CalUtil.v(form.str("external_reference")));
        p.put("heat_number", CalUtil.v(form.str("heat_number")));
        p.put("lot_batch_number", CalUtil.v(form.str("lot_batch_number")));
        p.put("subject", form.str("subject"));
        p.put("description", form.str("description"));
        p.put("affected_quantity", CalUtil.dbl(form.num("affected_quantity")));
        p.put("severity", form.str("severity"));
        p.put("fourstar_responsible_employee_id", form.str("fourstar_responsible_employee_id"));
        p.put("external_responsible_name", CalUtil.v(form.str("external_responsible_name")));
        p.put("external_responsible_email", CalUtil.v(form.str("external_responsible_email")));
        p.put("external_responsible_phone", CalUtil.v(form.str("external_responsible_phone")));
        p.put("target_closure_date", form.str("target_closure_date"));
        p.put("status", status);
        p.put("containment_action", CalUtil.v(form.str("containment_action")));
        p.put("root_cause", CalUtil.v(form.str("root_cause")));
        p.put("corrective_action", CalUtil.v(form.str("corrective_action")));
        p.put("verification_result", CalUtil.v(form.str("verification_result")));
        p.put("closure_date", "CLOSED".equals(status) ? CalUtil.id(form.str("closure_date")) : JSONObject.NULL);
        p.put("closure_remarks", CalUtil.v(form.str("closure_remarks")));
        p.put("debit_note_required", debit);
        p.put("debit_note_status", debit ? ds : "NOT_REQUIRED");
        p.put("debit_note_number", debit ? CalUtil.v(form.str("debit_note_number")) : JSONObject.NULL);
        p.put("debit_note_date", debit ? CalUtil.id(form.str("debit_note_date")) : JSONObject.NULL);
        p.put("debit_note_amount", debit ? CalUtil.dbl(form.num("debit_note_amount")) : 0.0);
        p.put("currency", form.str("currency").isEmpty() ? "INR" : form.str("currency"));
        p.put("debit_note_settled_amount", debit ? CalUtil.dbl(form.num("debit_note_settled_amount")) : 0.0);
        p.put("debit_note_settled_date", debit && "SETTLED".equals(ds) ? CalUtil.id(form.str("debit_note_settled_date")) : JSONObject.NULL);
        p.put("commercial_remarks", CalUtil.v(form.str("commercial_remarks")));
        return p;
    }

    @Override
    protected JSONObject persist(JSONObject p) throws Exception {
        String number = existing == null ? "" : Lookups.j(existing, "complaint_number");
        if (number.isEmpty()) number = api.nextNumber("qcms_next_complaint_number", new JSONObject().put("p_complaint_type", type));
        if (number == null || number.trim().isEmpty()) throw new Exception("The complaint number could not be generated. Try again.");
        JSONObject payload = new JSONObject().put("complaint_number", number);
        java.util.Iterator<String> it = p.keys();
        while (it.hasNext()) { String k = it.next(); payload.put(k, p.opt(k)); }
        return api.save("quality_complaints", id, payload);
    }

    @Override
    protected void done(JSONObject saved) {
        a.toast(word + " complaint " + Lookups.j(saved, "complaint_number") + " saved successfully.");
        Module m = module();
        if (id == null && m != null) a.replaceTop(new RecordScreen(a, m, Lookups.j(saved, "id")));
        else a.back();
    }
}
