package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * R39 · One Part process (part_process_routes row; core/part_process_service.part_process_payloads validation): Op No.
 * (positive, unique among ACTIVE processes of the Part), Process (Process Master), Mandatory, Source IN_HOUSE / OSP
 * (default from the process type), Remarks, Status ACTIVE / INACTIVE.
 */
public final class MstPartProcessEditScreen extends Screen {
    private final JSONObject part, route;
    private final List<JSONObject> routes;
    private final Map<String, JSONObject> processes;
    private FormView form;
    private TextView problem;
    private Button save;

    public MstPartProcessEditScreen(MainActivity a, JSONObject part, JSONObject route, List<JSONObject> routes, Map<String, JSONObject> processes) {
        super(a);
        this.part = part;
        this.route = route;
        this.routes = routes == null ? new ArrayList<>() : routes;
        this.processes = processes;
    }

    @Override public String title() { return route == null ? "Add part process" : "Op " + MstPartProcessScreen.op(route); }
    @Override public String subtitle() { return MstPartGrid.partLabel(part); }
    @Override public int tab() { return Catalog.MASTERS; }

    private int nextOp() {
        int max = 0;
        for (JSONObject r : routes) max = Math.max(max, MstPartProcessScreen.op(r));
        return (max / 10 + 1) * 10;
    }

    @Override
    public View build() {
        newPage();
        List<Field> f = new ArrayList<>();
        f.add(Field.integer("operation_no", "Op No.").req().range(1, 1e6).hint("Operation / sequence number, e.g. 10, 20, 30."));
        f.add(Field.lookup("process_id", "Process", Lookups.processes()).req());
        f.add(Field.bool("is_mandatory", "Mandatory").def(true).hint("Ticked = Yes, the process is mandatory for this Part."));
        f.add(Field.select("source_type", "Source", "IN_HOUSE", "OSP").labels("In-house", "OSP (outside processing)").req().def("IN_HOUSE"));
        f.add(Field.area("remarks", "Remarks").hint("Remarks, e.g. OSP vendor."));
        f.add(Field.select("status", "Status", "ACTIVE", "INACTIVE").req().def("ACTIVE"));
        form = new FormView(a, f);
        form.onChange((k, v) -> {
            if (!"process_id".equals(k)) return;
            JSONObject p = processes.get(String.valueOf(v));
            if (p != null) form.set("source_type", "OUTSOURCED".equalsIgnoreCase(Lookups.j(p, "process_type")) ? "OSP" : "IN_HOUSE");
        });
        add(form, 0);
        if (route != null) {
            form.setAll(route);
            form.set("is_mandatory", MstPartProcessScreen.mandatory(route));
        } else {
            form.set("operation_no", nextOp());
            form.set("is_mandatory", true);
            form.set("status", "ACTIVE");
            form.set("source_type", "IN_HOUSE");
        }
        problem = Ui.text(a, "", 13, Ui.RED_FG, false);
        problem.setVisibility(View.GONE);
        add(problem, 8);
        save = Ui.primary(a, "Save Part process");
        save.setOnClickListener(v -> save());
        add(save, 10);
        add(Ui.text(a, "After a change of the process list you can raise a PCN from the Part processes screen.", 11.5f, Ui.MUTED, false), 6);
        return scroll;
    }

    private void fail(String m) { problem.setText(m); problem.setVisibility(View.VISIBLE); a.toast(m); }

    private void save() {
        String p0 = form.validate();
        if (p0 != null) { fail(p0); return; }
        int opNo;
        try { opNo = (int) Math.round(Double.parseDouble(form.str("operation_no"))); } catch (Exception e) { fail("Op No. must be a positive number."); return; }
        if (opNo <= 0) { fail("Op No. must be a positive number."); return; }
        String processId = form.str("process_id");
        JSONObject proc = processes.get(processId);
        if (processId.isEmpty()) { fail("Select a valid Process from Process Master."); return; }
        String status = MstPartProcessScreen.upper(form.str("status"));
        if (!"INACTIVE".equals(status)) status = "ACTIVE";
        if ("ACTIVE".equals(status)) {
            for (JSONObject r : routes) {
                if (route != null && Lookups.j(r, "id").equals(Lookups.j(route, "id"))) continue;
                if (MstPartProcessScreen.active(r) && MstPartProcessScreen.op(r) == opNo) {
                    fail("Duplicate Op No. " + opNo + ". Each ACTIVE process needs its own operation number.");
                    return;
                }
            }
        }
        String source = MstPartProcessScreen.upper(form.str("source_type")).replace('-', '_');
        if (!"OSP".equals(source) && !"IN_HOUSE".equals(source))
            source = proc != null && "OUTSOURCED".equalsIgnoreCase(Lookups.j(proc, "process_type")) ? "OSP" : "IN_HOUSE";
        final JSONObject p = new JSONObject();
        try {
            p.put("part_id", Lookups.j(part, "id"));
            p.put("operation_no", opNo);
            p.put("process_id", processId);
            p.put("process_name_snapshot", proc == null ? JSONObject.NULL : Lookups.j(proc, "process_name"));
            p.put("is_mandatory", form.bool("is_mandatory"));
            p.put("source_type", source);
            String remarks = form.str("remarks").trim();
            p.put("remarks", remarks.isEmpty() ? JSONObject.NULL : remarks);
            p.put("sequence_no", opNo);
            p.put("status", status.toUpperCase(Locale.ROOT));
        } catch (Exception e) { fail(Api.message(e)); return; }
        save.setEnabled(false);
        Api.async(() -> route == null ? api.insert(MstPartProcessScreen.TABLE, p) : api.update(MstPartProcessScreen.TABLE, Lookups.j(route, "id"), p), (r, err) -> {
            save.setEnabled(true);
            if (err != null) { fail(Api.message(err)); return; }
            a.toast("Part process Op " + p.optInt("operation_no") + " saved.");
            a.back();
        });
    }

    @Override public boolean onBack() {
        a.confirm("Leave without saving?", "Changes on this form are not saved.", "Leave", () -> a.back());
        return true;
    }
}
