package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** Checkpoints / bullet points of one process-flow step (npd_process_flow_points), saved like "Save Checkpoints - OP n". */
public final class NpdPointsScreen extends Screen {
    private final JSONObject step;
    private final Field.Lookup employees = NpdUtil.employees();
    private RowsEditor grid;
    private final Set<String> existingIds = new HashSet<>();
    private Button save;

    public NpdPointsScreen(MainActivity a, JSONObject step) { super(a); this.step = step; }

    private String op() { return NpdUtil.s(step, "operation_no"); }

    @Override public String title() { return "Checkpoints · OP " + op(); }
    @Override public String subtitle() { return NpdUtil.s(step, "process_name_snapshot"); }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            Lookups.rows(api, employees);
            return api.rows("npd_process_flow_points?select=*&flow_step_id=eq." + Api.enc(step.optString("id")) + "&order=sequence_no.asc&limit=300");
        }, (rows, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            render(rows);
        });
        return scroll;
    }

    private void render(JSONArray rows) {
        offlineNote();
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, "OP " + op() + " - " + NpdUtil.s(step, "process_name_snapshot"), 15, Ui.TEXT, true));
        card.addView(Ui.text(a, "Points that must be closed under this process. They are copied to every new NPD Order (ACTIVE points only).", 11.5f, Ui.MUTED, false));
        List<Field> fields = Arrays.asList(
            Field.integer("sequence_no", "Seq").req().range(0, 999999),
            Field.area("point_text", "Checkpoint / Bullet Point").req(),
            Field.lookup("responsible_employee_id", "Responsible Employee", employees),
            Field.select("status", "Status", "ACTIVE", "INACTIVE").req().def("ACTIVE"),
            Field.text("remarks", "Remarks"));
        List<String[]> cols = Arrays.asList(new String[]{"sequence_no", "Seq"}, new String[]{"point_text", "Checkpoint / Bullet Point"},
            new String[]{"_resp", "Responsible"}, new String[]{"status", "Status"}, new String[]{"remarks", "Remarks"});
        grid = new RowsEditor(a, "Checkpoints", fields, cols);
        List<JSONObject> list = new ArrayList<>();
        for (JSONObject p : NpdUtil.list(rows)) {
            JSONObject r = new JSONObject();
            try {
                r.put("id", p.optString("id"));
                existingIds.add(p.optString("id"));
                r.put("sequence_no", p.isNull("sequence_no") ? 10 : NpdUtil.intOf(p.opt("sequence_no"), 10));
                r.put("point_text", NpdUtil.s(p, "point_text"));
                String emp = NpdUtil.s(p, "responsible_employee_id");
                r.put("responsible_employee_id", emp.isEmpty() ? JSONObject.NULL : emp);
                if (emp.isEmpty() && !NpdUtil.s(p, "responsible_snapshot").isEmpty()) r.put("_legacy", NpdUtil.s(p, "responsible_snapshot"));
                r.put("status", NpdUtil.s(p, "status").isEmpty() ? "ACTIVE" : NpdUtil.s(p, "status"));
                r.put("remarks", NpdUtil.s(p, "remarks"));
            } catch (Exception ignored) { }
            list.add(r);
        }
        grid.setRows(list);
        grid.onChanged(this::recompute);
        recompute();
        card.addView(grid, Ui.matchWrap(a, 10));
        add(card, 4);
        save = Ui.primary(a, "Save Checkpoints - OP " + op());
        save.setOnClickListener(v -> save());
        add(save, 12);
    }

    private void recompute() {
        int max = 0;
        for (JSONObject r : grid.rows()) {
            max = Math.max(max, NpdUtil.intOf(r.opt("sequence_no"), 0));
            String emp = NpdUtil.s(r, "responsible_employee_id");
            try {
                r.put("_resp", !emp.isEmpty() ? Lookups.labelOf(employees, emp) : (NpdUtil.s(r, "_legacy").isEmpty() ? "— Not assigned —" : "Legacy · " + NpdUtil.s(r, "_legacy")));
            } catch (Exception ignored) { }
        }
        try { grid.template(new JSONObject().put("sequence_no", max + 10).put("status", "ACTIVE")); } catch (Exception ignored) { }
        grid.refresh();
    }

    private void save() {
        Set<Integer> seen = new HashSet<>();
        List<JSONObject> keep = new ArrayList<>();
        for (JSONObject r : grid.rows()) {
            if (NpdUtil.s(r, "point_text").trim().isEmpty()) continue;
            int seq = NpdUtil.intOf(r.opt("sequence_no"), 0);
            if (seen.contains(seq)) { a.toast("Checkpoint sequence " + seq + " is duplicated in OP " + op() + "."); return; }
            seen.add(seq);
            keep.add(r);
        }
        save.setEnabled(false);
        save.setText("Saving…");
        Api.async(() -> {
            Set<String> retained = new HashSet<>();
            for (JSONObject r : keep) {
                String emp = NpdUtil.s(r, "responsible_employee_id");
                JSONObject payload = new JSONObject();
                payload.put("flow_step_id", step.optString("id"));
                payload.put("sequence_no", NpdUtil.intOf(r.opt("sequence_no"), 0));
                payload.put("point_text", NpdUtil.s(r, "point_text").trim());
                payload.put("responsible_employee_id", emp.isEmpty() ? JSONObject.NULL : emp);
                payload.put("responsible_snapshot", NpdUtil.snapshot(employees, emp, r.opt("_legacy")));
                payload.put("status", NpdUtil.s(r, "status").isEmpty() ? "ACTIVE" : NpdUtil.s(r, "status"));
                payload.put("remarks", NpdUtil.orNull(NpdUtil.s(r, "remarks")));
                String id = NpdUtil.s(r, "id");
                if (existingIds.contains(id)) { api.update("npd_process_flow_points", id, payload); retained.add(id); }
                else retained.add(api.insert("npd_process_flow_points", payload).optString("id"));
            }
            for (String id : existingIds) if (!retained.contains(id)) NpdUtil.deleteRow(api, "npd_process_flow_points", id);
            return true;
        }, (ok, err) -> {
            save.setEnabled(true);
            save.setText("Save Checkpoints - OP " + op());
            if (err != null) { a.toast(Api.message(err)); return; }
            a.toast("Checkpoints saved for OP " + op() + ".");
            a.back();
        });
    }

    @Override public boolean onBack() {
        a.confirm("Leave without saving?", "Changes to the checkpoints are not saved.", "Leave", () -> a.back());
        return true;
    }
}
