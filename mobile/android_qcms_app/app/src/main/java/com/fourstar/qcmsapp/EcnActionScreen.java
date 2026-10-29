package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * R39 · One ECN / PCN implementation action (part_ecn_actions; app_pages/ecn.py _render_ecn_actions + core/ecn_service
 * normalize_action_rows): affected document, action, responsible (employee or text), target date, status OPEN /
 * IN_PROGRESS / DONE / NOT_REQUIRED, completed date (today when DONE), remarks. Actions of a COMPLETED / CANCELLED ECN
 * cannot change; removing an action is ADMIN only (RLS tenant_admin_remove).
 */
public final class EcnActionScreen extends Screen {
    private final JSONObject ecn;
    private final JSONObject row;
    private FormView form;
    private TextView problem;
    private Button save;

    /** row = existing action (null = new action). */
    public EcnActionScreen(MainActivity a, JSONObject ecn, JSONObject row) { super(a); this.ecn = ecn; this.row = row; }

    @Override public String title() { return row == null ? "New implementation action" : "Implementation action"; }
    @Override public String subtitle() { return EcnData.s(ecn, "ecn_number") + " · " + EcnData.s(ecn, "part_number"); }
    @Override public int tab() { return Catalog.MASTERS; }

    @Override
    public View build() {
        newPage();
        String st = EcnData.status(ecn);
        if (st.equals("COMPLETED") || st.equals("CANCELLED")) {
            add(MstForm.noteCard(a, "Actions of a COMPLETED / CANCELLED ECN cannot be changed."), 0);
            return scroll;
        }
        List<Field> f = new ArrayList<>();
        f.add(Field.integer("sequence_no", "Sequence").def(10));
        f.add(Field.text("affected_document", "Affected Document").hint("e.g. Drawing, PFD, Control Plan, PFMEA, PPAP, Purchase Orders"));
        f.add(Field.area("action_text", "Action").req());
        f.add(Field.lookup("responsible_employee_id", "Responsible (employee)", Lookups.employees()));
        f.add(Field.text("responsible_text", "Responsible (other / text)"));
        f.add(Field.date("target_date", "Target Date"));
        f.add(Field.select("status", "Status", EcnData.ACTION_STATUSES).labels(EcnData.pretty(EcnData.ACTION_STATUSES)).req().def("OPEN"));
        f.add(Field.date("completed_date", "Completed Date").hint("Set to today automatically when the status is DONE."));
        f.add(Field.area("remarks", "Remarks"));
        form = new FormView(a, f);
        add(form, 0);
        if (row != null) form.setAll(row);
        else {
            form.set("status", "OPEN");
            if (!EcnData.s(ecn, "response_by").isEmpty()) form.set("target_date", EcnData.iso(EcnData.s(ecn, "response_by")));
        }
        problem = Ui.text(a, "", 13, Ui.RED_FG, false);
        problem.setVisibility(View.GONE);
        add(problem, 8);
        LinearLayout box = Ui.vbox(a);
        save = Ui.primary(a, "Save action");
        save.setOnClickListener(v -> save());
        box.addView(save, Ui.matchWrap(a, 0));
        if (row != null && api.isAdmin()) {
            Button del = Ui.outline(a, "Delete action", Ui.ORANGE);
            del.setOnClickListener(v -> a.confirm("Delete this action?", EcnData.s(row, "action_text"), "Delete", () ->
                Api.async(() -> { api.delete(EcnData.ACTIONS, EcnData.s(row, "id")); return true; }, (ok, err) -> {
                    if (err != null) a.toast(Api.message(err)); else { a.toast("Action deleted."); a.back(); }
                })));
            box.addView(del, Ui.matchWrap(a, 8));
        }
        add(box, 10);
        add(Ui.text(a, "The ECN can be marked COMPLETED only when every action is DONE or NOT REQUIRED.", 11.5f, Ui.MUTED, false), 6);
        return scroll;
    }

    private static Object val(JSONObject v, String k) {
        Object o = v.opt(k);
        if (o == null || o == JSONObject.NULL) return JSONObject.NULL;
        String t = String.valueOf(o).trim();
        return t.isEmpty() || "null".equals(t) ? JSONObject.NULL : t;
    }

    private void save() {
        String p0 = form.validate();
        if (p0 != null) { problem.setText(p0); problem.setVisibility(View.VISIBLE); return; }
        final JSONObject p = new JSONObject();
        try {
            JSONObject v = form.json();
            String status = String.valueOf(v.opt("status")).trim().toUpperCase(Locale.ROOT).replace(' ', '_');
            boolean ok = false;
            for (String s : EcnData.ACTION_STATUSES) if (s.equals(status)) ok = true;
            if (!ok) status = "OPEN";
            Object seq = v.opt("sequence_no");
            int sequence = 10;
            try { sequence = (int) Double.parseDouble(String.valueOf(seq)); } catch (Exception ignored) { }
            p.put("ecn_id", EcnData.s(ecn, "id"));
            p.put("sequence_no", sequence);
            p.put("affected_document", val(v, "affected_document"));
            p.put("action_text", String.valueOf(v.opt("action_text")).trim());
            p.put("responsible_employee_id", val(v, "responsible_employee_id"));
            p.put("responsible_text", val(v, "responsible_text"));
            Object target = val(v, "target_date");
            p.put("target_date", target == JSONObject.NULL ? target : EcnData.iso(String.valueOf(target)));
            Object done = val(v, "completed_date");
            if (done == JSONObject.NULL && "DONE".equals(status)) done = LocalDate.now().toString();
            p.put("completed_date", done == JSONObject.NULL ? done : EcnData.iso(String.valueOf(done)));
            p.put("status", status);
            p.put("remarks", val(v, "remarks"));
        } catch (Exception e) { a.toast(Api.message(e)); return; }
        save.setEnabled(false);
        Api.async(() -> row == null ? api.insert(EcnData.ACTIONS, p) : api.update(EcnData.ACTIONS, EcnData.s(row, "id"), p), (r, err) -> {
            save.setEnabled(true);
            if (err != null) { problem.setText(Api.message(err)); problem.setVisibility(View.VISIBLE); return; }
            a.toast("Implementation action saved.");
            a.back();
        });
    }
}
