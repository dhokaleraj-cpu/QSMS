package com.fourstar.qcmsapp;

import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.List;

/**
 * Final closure & approval (complaints.py render_analysis section G): "Save Closure Details" and "Close Complaint".
 * Closing needs a confirmed root cause, verified effectiveness, every action COMPLETED / CANCELLED, a closure date
 * and the closure approver.
 */
final class CalComplaintClose extends CalEditScreen {
    private JSONArray actions = new JSONArray();
    private TextView readiness;
    private Button close;

    CalComplaintClose(MainActivity a, String complaintId) { super(a, complaintId, null); }

    @Override public String title() { return "Closure · " + (existing == null ? "Complaint" : Lookups.j(existing, "complaint_number")); }
    @Override public String subtitle() { return "Final closure & approval"; }
    @Override protected String table() { return "quality_complaints"; }
    @Override protected String saveLabel() { return "Save Closure Details"; }
    @Override protected String savedMessage() { return "Complaint closure details saved."; }

    @Override
    protected void load() throws Exception {
        actions = api.rows("quality_complaint_actions?select=id,action_no,status,target_date&complaint_id=eq." + id + "&order=action_no.asc&limit=5000");
    }

    private boolean closed() { return "CLOSED".equals(Lookups.j(existing, "status")); }

    @Override
    protected void buildForm(CalSections f) {
        f.note(CalComplaints.progressView(a, existing, actions));
        f.section("G · Final closure & approval",
            Field.date("closure_date", "Actual Closure Date").req(),
            Field.area("closure_remarks", "Final Closure Remarks"),
            Field.lookup("closure_approved_by_employee_id", "Closure Approved By", Lookups.employees()),
            Field.date("closure_approved_date", "Closure Approval Date").req());
        readiness = Ui.text(a, "", 12.5f, Ui.TEXT, true);
        LinearLayout card = Ui.card(a);
        card.addView(readiness);
        f.note(card);
    }

    @Override
    protected void afterFill() {
        quiet = true;
        if (form.str("closure_date").isEmpty()) form.set("closure_date", Ui.today());
        if (form.str("closure_approved_date").isEmpty()) form.set("closure_approved_date", Ui.today());
        quiet = false;
        form.onChange((k, v) -> { if (!quiet) refreshReadiness(); });
    }

    @Override
    protected void addButtons(LinearLayout b) {
        close = Ui.primary(a, closed() ? "Complaint is closed" : "Close Complaint");
        close.setOnClickListener(v -> closeComplaint());
        b.addView(close, Ui.matchWrap(a, 10));
        refreshReadiness();
    }

    private List<String> gaps() {
        JSONObject candidate;
        try { candidate = new JSONObject(existing.toString()); candidate.put("closure_date", form.str("closure_date").isEmpty() ? JSONObject.NULL : form.str("closure_date")); }
        catch (Exception e) { candidate = existing; }
        return CalComplaints.closureGaps(candidate, actions);
    }

    private void refreshReadiness() {
        if (readiness == null) return;
        List<String> g = gaps();
        if (closed()) {
            readiness.setText("Complaint is CLOSED. Closure details can still be corrected with Save Closure Details.");
            readiness.setTextColor(Ui.GREEN_FG);
        } else if (g.isEmpty()) {
            readiness.setText("Complaint is ready for final quality closure. Commercial Debit Note settlement may continue independently if still pending.");
            readiness.setTextColor(Ui.GREEN_FG);
        } else {
            readiness.setText("Closure pending: " + String.join(" · ", g));
            readiness.setTextColor(Ui.AMBER_FG);
        }
        if (close != null) close.setEnabled(!closed() && g.isEmpty());
    }

    @Override
    protected JSONObject collect() throws Exception {
        JSONObject p = new JSONObject();
        p.put("closure_date", CalUtil.id(form.str("closure_date")));
        p.put("closure_remarks", CalUtil.v(form.str("closure_remarks")));
        p.put("closure_approved_by_employee_id", CalUtil.id(form.str("closure_approved_by_employee_id")));
        p.put("closure_approved_date", CalUtil.id(form.str("closure_approved_date")));
        return p;
    }

    @Override
    protected JSONObject persist(JSONObject p) throws Exception {
        return api.update("quality_complaints", id, p);
    }

    private void closeComplaint() {
        String problem = form.validate();
        if (problem != null) { a.toast(problem); return; }
        if (closed()) return;
        List<String> g = gaps();
        if (!g.isEmpty()) { a.toast("Closure pending: " + String.join(" · ", g)); return; }
        if (form.str("closure_approved_by_employee_id").isEmpty()) { a.toast("Closure Approved By is mandatory."); return; }
        JSONObject p;
        try { p = collect().put("status", "CLOSED"); } catch (Exception e) { a.toast(Api.message(e)); return; }
        a.confirm("Close complaint " + Lookups.j(existing, "complaint_number") + "?", "Final CLOSED status after RCA, action and effectiveness verification.", "Close complaint", () -> {
            close.setEnabled(false);
            Api.async(() -> {
                // Re-check open actions on the server copy just before closing.
                JSONArray fresh = api.rows("quality_complaint_actions?select=id,status&complaint_id=eq." + id + "&limit=5000");
                JSONObject cur = api.rows("quality_complaints?select=*&id=eq." + id).optJSONObject(0);
                if (cur == null) throw new Api.ApiException(404, "Complaint not found.");
                cur.put("closure_date", p.opt("closure_date"));
                List<String> latest = CalComplaints.closureGaps(cur, fresh);
                if (!latest.isEmpty()) throw new Exception("Closure pending: " + String.join(" · ", latest));
                return api.update("quality_complaints", id, p);
            }, (saved, err) -> {
                close.setEnabled(true);
                if (err != null) { a.toast(Api.message(err)); return; }
                a.toast("Complaint closed successfully after RCA, action and effectiveness verification.");
                a.back();
            });
        });
    }
}
