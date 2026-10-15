package com.fourstar.qcmsapp;

import android.graphics.Color;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * NPD Process Flow Designer (app_pages/npd_apqp.py render_process_flow): one flow per part with header,
 * operational sequence (auto OP numbers: forging / casting = 0, then 10, 20 …) and checkpoints per process.
 * Saves exactly like the website: steps reused by OP + process (else process), unused steps deleted,
 * renumbered steps first parked at OP 900000+i to avoid unique clashes.
 */
public final class NpdFlowScreen extends Screen {
    private String flowId;
    private String partId;
    private JSONObject flow;
    private JSONObject part;
    private FormView header;
    private RowsEditor steps;
    private Switch auto;
    private TextView designationInfo;
    private LinearLayout checkpointsBox;
    private Button save;
    private final Field.Lookup employees = NpdUtil.employees();
    private final Field.Lookup processes = Lookups.processes();
    private final Field.Lookup parts = Lookups.parts();

    public NpdFlowScreen(MainActivity a, String flowId) { super(a); this.flowId = flowId; }

    @Override public String title() { return "Process Flow Designer"; }
    @Override public String subtitle() { return part == null ? "One process flow per part" : NpdUtil.s(part, "part_number") + " · " + NpdUtil.s(part, "part_name"); }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            Lookups.rows(api, processes);
            Lookups.rows(api, employees);
            Lookups.rows(api, parts);
            if (flowId != null) {
                JSONArray r = api.rows("npd_process_flows?select=*&id=eq." + Api.enc(flowId));
                if (r.length() == 0) throw new Api.ApiException(404, "Process flow not found.");
                return r.getJSONObject(0);
            }
            return null;
        }, (f, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            render(f);
        });
        return scroll;
    }

    private void render(JSONObject existing) {
        offlineNote();
        add(Ui.label(a, "A · Process flow header"), 4);
        LinearLayout card = Ui.card(a);
        List<Field> fields = new ArrayList<>(Arrays.asList(
            Field.lookup("part_id", "Select Part Number", parts).req(),
            Field.text("revision", "Revision").def("A"),
            Field.date("effective_date", "Effective Date").def(Ui.today()).req(),
            Field.select("status", "Flow Status", "ACTIVE", "DRAFT", "INACTIVE").def("ACTIVE").req(),
            Field.area("remarks", "Flow Remarks")));
        if (existing != null) fields.get(0).ro();
        header = new FormView(a, fields);
        card.addView(header);
        add(card, 2);

        add(Ui.label(a, "B · Operational sequence"), 12);
        LinearLayout seq = Ui.card(a);
        auto = new Switch(a);
        auto.setText("Auto-number operations and Part Designations (Forging / Casting = 0, then 10, 20, 30 … in row order)");
        auto.setTextColor(Ui.TEXT);
        auto.setChecked(true);
        seq.addView(auto);
        designationInfo = Ui.text(a, "", 11.5f, Ui.MUTED, false);
        seq.addView(designationInfo, Ui.matchWrap(a, 4));
        List<Field> stepFields = Arrays.asList(
            Field.integer("operation_no", "Operation No.").range(0, 999999).hint("Leave blank when auto-numbering is on"),
            Field.lookup("process_id", "Process", processes).req(),
            Field.integer("target_lead_days", "Target Lead Days").range(0, 100000).hint("Optional default lead-time allocation for this process"),
            Field.lookup("responsible_employee_id", "Responsible Employee", employees),
            Field.text("remarks", "Remarks"));
        List<String[]> cols = Arrays.asList(new String[]{"operation_no", "OP"}, new String[]{"part_designation", "Part Designation"},
            new String[]{"process_id", "Process"}, new String[]{"target_lead_days", "Lead days"}, new String[]{"_resp", "Responsible"},
            new String[]{"remarks", "Remarks"});
        steps = new RowsEditor(a, "Processes", stepFields, cols);
        steps.onChanged(this::recompute);
        seq.addView(steps, Ui.matchWrap(a, 8));
        add(seq, 2);
        auto.setOnCheckedChangeListener((b, on) -> recompute());

        save = Ui.primary(a, "Save Process Flow");
        save.setOnClickListener(v -> save());
        add(save, 12);

        add(Ui.label(a, "C · Process checkpoints / bullet points"), 16);
        checkpointsBox = Ui.vbox(a);
        add(checkpointsBox, 2);

        header.onChange((key, value) -> {
            if ("part_id".equals(key) && existing == null && value != null && !String.valueOf(value).isEmpty()) loadPart(String.valueOf(value));
        });
        if (existing != null) {
            header.setAll(existing);
            loadPart(NpdUtil.s(existing, "part_id"));
        } else {
            checkpointsBox.addView(Ui.text(a, "Select the part. Save the Process Flow first; checkpoints can then be added under each process.", 12.5f, Ui.MUTED, false));
        }
    }

    /** Part chosen: load its flow (one per part) and saved steps. */
    private void loadPart(String pid) {
        partId = pid;
        part = Lookups.rowOf(parts, pid);
        a.rebuildTitle(this);
        designationInfo.setText("Loading the process flow of this part…");
        Api.async(() -> {
            JSONArray f = api.rows("npd_process_flows?select=*&part_id=eq." + Api.enc(pid) + "&limit=1");
            JSONObject fl = f.length() > 0 ? f.getJSONObject(0) : null;
            JSONArray st = fl == null ? new JSONArray() : api.rows("npd_process_flow_steps?select=*&flow_id=eq." + fl.optString("id") + "&order=operation_no.asc&limit=500");
            return new Object[]{fl, st, Lookups.rows(api, processes)};
        }, (res, err) -> {
            if (err != null) { designationInfo.setText(Api.message(err)); designationInfo.setTextColor(Ui.RED_FG); return; }
            flow = (JSONObject) res[0];
            if (flow != null) {
                flowId = flow.optString("id");
                header.set("revision", NpdUtil.s(flow, "revision").isEmpty() ? "A" : NpdUtil.s(flow, "revision"));
                header.set("effective_date", NpdUtil.s(flow, "effective_date").isEmpty() ? Ui.today() : NpdUtil.s(flow, "effective_date"));
                String st = NpdUtil.s(flow, "status");
                header.set("status", Arrays.asList("ACTIVE", "DRAFT", "INACTIVE").contains(st) ? st : "ACTIVE");
                header.set("remarks", NpdUtil.s(flow, "remarks"));
            }
            List<JSONObject> rows = new ArrayList<>();
            for (JSONObject s : NpdUtil.list((JSONArray) res[1])) {
                JSONObject r = new JSONObject();
                try {
                    r.put("operation_no", NpdUtil.intOf(s.opt("operation_no"), 0));
                    r.put("process_id", NpdUtil.s(s, "process_id"));
                    r.put("target_lead_days", NpdUtil.intOf(s.opt("target_lead_days"), 0));
                    String emp = NpdUtil.s(s, "responsible_employee_id");
                    r.put("responsible_employee_id", emp.isEmpty() ? JSONObject.NULL : emp);
                    if (emp.isEmpty() && !NpdUtil.s(s, "responsible").isEmpty()) r.put("_legacy", NpdUtil.s(s, "responsible"));
                    r.put("remarks", NpdUtil.s(s, "remarks"));
                } catch (Exception ignored) { }
                rows.add(r);
            }
            if (rows.isEmpty()) {
                JSONArray procs = (JSONArray) res[2];
                if (procs.length() > 0) {
                    JSONObject r = new JSONObject();
                    try {
                        r.put("operation_no", 0);
                        r.put("process_id", procs.getJSONObject(0).optString("id"));
                        r.put("target_lead_days", 0);
                        r.put("responsible_employee_id", JSONObject.NULL);
                    } catch (Exception ignored) { }
                    rows.add(r);
                }
            }
            steps.setRows(rows);
            recompute();
            renderCheckpoints((JSONArray) res[1]);
        });
    }

    private String designationBase() {
        if (part == null) return "";
        String raw = NpdUtil.s(part, "fsi_part_number").trim();
        if (raw.isEmpty()) raw = NpdUtil.s(part, "part_number").trim();
        return raw.replaceAll("\\s+", "").toUpperCase(Locale.ROOT);
    }

    /** _is_primary_process(): code / name / type contains "forg" or "cast". */
    private boolean primary(String processId) {
        JSONObject p = Lookups.rowOf(processes, processId);
        if (p == null) return false;
        String text = (NpdUtil.s(p, "process_code") + " " + NpdUtil.s(p, "process_name") + " " + NpdUtil.s(p, "process_type")).toLowerCase(Locale.ROOT);
        return text.contains("forg") || text.contains("cast");
    }

    /** auto_operation_numbers() + Part Designation + responsible column, applied in place. */
    private void recompute() {
        List<JSONObject> rows = steps.rows();
        String base = designationBase();
        try {
            if (auto.isChecked()) {
                int next = 10;
                boolean zero = false;
                for (JSONObject r : rows) {
                    String pid = NpdUtil.s(r, "process_id");
                    if (pid.isEmpty()) continue;
                    if (!zero && primary(pid)) { r.put("operation_no", 0); zero = true; }
                    else { r.put("operation_no", next); next += 10; }
                }
            }
            for (JSONObject r : rows) {
                r.put("part_designation", base.isEmpty() ? "Set FSI Part Number in Part Master" : base + "-" + NpdUtil.intOf(r.opt("operation_no"), 0));
                String emp = NpdUtil.s(r, "responsible_employee_id");
                r.put("_resp", !emp.isEmpty() ? Lookups.labelOf(employees, emp) : (NpdUtil.s(r, "_legacy").isEmpty() ? "— Not assigned —" : "Legacy · " + NpdUtil.s(r, "_legacy")));
            }
        } catch (Exception ignored) { }
        steps.refresh();
        designationInfo.setText("Part Designation = FSI Part No - Operation No (" + (base.isEmpty() ? "FSI Part Number not set" : base + "-0, " + base + "-10 …") + "). Tap a row to edit; + Add row adds a process.");
        designationInfo.setTextColor(Ui.MUTED);
    }

    private void save() {
        String problem = header.validate();
        if (problem != null) { a.toast(problem); return; }
        recompute();
        // ---- validation exactly like the website
        List<JSONObject> clean = new ArrayList<>();
        Set<Integer> seen = new HashSet<>();
        for (JSONObject r : steps.rows()) {
            String pid = NpdUtil.s(r, "process_id");
            if (pid.isEmpty()) continue;
            int op = NpdUtil.intOf(r.opt("operation_no"), 0);
            if (seen.contains(op)) { a.toast("Operation Number " + op + " is duplicated. Each operation number must be unique."); return; }
            seen.add(op);
            if (Lookups.rowOf(processes, pid) == null) { a.toast("Process '" + Lookups.labelOf(processes, pid) + "' is not an active Process Master record."); return; }
            clean.add(r);
        }
        if (clean.isEmpty()) { a.toast("Add at least one process step before saving the Process Flow."); return; }
        clean.sort((x, y) -> Integer.compare(NpdUtil.intOf(x.opt("operation_no"), 0), NpdUtil.intOf(y.opt("operation_no"), 0)));
        save.setEnabled(false);
        save.setText("Saving…");
        final String pid = header.str("part_id");
        Api.async(() -> {
            JSONObject payload = new JSONObject();
            payload.put("part_id", pid);
            payload.put("revision", header.str("revision").isEmpty() ? "A" : header.str("revision"));
            payload.put("effective_date", header.str("effective_date").substring(0, 10));
            payload.put("status", header.str("status"));
            payload.put("remarks", NpdUtil.orNull(header.str("remarks")));
            // one flow per part: re-check on the server copy before inserting
            String fid = flowId;
            if (fid == null) {
                JSONArray f = api.rows("npd_process_flows?select=id&part_id=eq." + Api.enc(pid) + "&limit=1");
                if (f.length() > 0) fid = f.getJSONObject(0).optString("id");
            }
            JSONObject saved = fid != null ? api.update("npd_process_flows", fid, payload) : api.insert("npd_process_flows", payload);
            String savedId = saved.optString("id");
            List<JSONObject> oldSteps = NpdUtil.list(api.rows("npd_process_flow_steps?select=*&flow_id=eq." + savedId + "&order=operation_no.asc&limit=500"));
            Map<Integer, JSONObject> oldByOp = new HashMap<>();
            for (JSONObject o : oldSteps) oldByOp.put(NpdUtil.intOf(o.opt("operation_no"), 0), o);
            Set<String> used = new HashSet<>();
            List<JSONObject> matches = new ArrayList<>();
            for (JSONObject src : clean) {
                int op = NpdUtil.intOf(src.opt("operation_no"), 0);
                String procId = NpdUtil.s(src, "process_id");
                JSONObject match = oldByOp.get(op);
                if (match == null || !NpdUtil.s(match, "process_id").equals(procId) || used.contains(match.optString("id"))) {
                    match = null;
                    for (JSONObject o : oldSteps) {
                        if (NpdUtil.s(o, "process_id").equals(procId) && !used.contains(o.optString("id"))) { match = o; break; }
                    }
                }
                if (match == null && oldByOp.get(op) != null && !used.contains(oldByOp.get(op).optString("id"))) match = oldByOp.get(op);
                if (match != null) used.add(match.optString("id"));
                matches.add(match);
            }
            for (JSONObject o : oldSteps) {
                if (!used.contains(o.optString("id"))) NpdUtil.deleteRow(api, "npd_process_flow_steps", o.optString("id"));
            }
            for (int i = 0; i < clean.size(); i++) {
                JSONObject match = matches.get(i);
                int op = NpdUtil.intOf(clean.get(i).opt("operation_no"), 0);
                if (match != null && NpdUtil.intOf(match.opt("operation_no"), 0) != op) {
                    api.update("npd_process_flow_steps", match.optString("id"), new JSONObject().put("operation_no", 900000 + i));
                }
            }
            for (int i = 0; i < clean.size(); i++) {
                JSONObject src = clean.get(i);
                JSONObject match = matches.get(i);
                String procId = NpdUtil.s(src, "process_id");
                JSONObject proc = Lookups.rowOf(processes, procId);
                String emp = NpdUtil.s(src, "responsible_employee_id");
                JSONObject step = new JSONObject();
                step.put("flow_id", savedId);
                step.put("process_id", procId);
                step.put("operation_no", NpdUtil.intOf(src.opt("operation_no"), 0));
                step.put("process_name_snapshot", proc == null ? "" : NpdUtil.s(proc, "process_name"));
                step.put("target_lead_days", NpdUtil.intOf(src.opt("target_lead_days"), 0));
                step.put("responsible_employee_id", emp.isEmpty() ? JSONObject.NULL : emp);
                step.put("responsible", NpdUtil.snapshot(employees, emp, src.opt("_legacy")));
                step.put("remarks", NpdUtil.orNull(NpdUtil.s(src, "remarks")));
                if (match != null) api.update("npd_process_flow_steps", match.optString("id"), step);
                else api.insert("npd_process_flow_steps", step);
            }
            return savedId;
        }, (savedId, err) -> {
            save.setEnabled(true);
            save.setText("Save Process Flow");
            if (err != null) { a.toast(Api.message(err)); return; }
            a.toast("Part Process Flow saved in operational sequence.");
            a.replaceTop(new NpdFlowScreen(a, savedId));
        });
    }

    /** Saved steps with their checkpoint counts; tap one to edit its checkpoints. */
    private void renderCheckpoints(JSONArray savedSteps) {
        checkpointsBox.removeAllViews();
        if (flow == null || savedSteps.length() == 0) {
            checkpointsBox.addView(Ui.text(a, "Save the Process Flow first. Checkpoints / bullet points can then be added under each process.", 12.5f, Ui.MUTED, false));
            return;
        }
        checkpointsBox.addView(Ui.text(a, "Add the quality, development or completion points that must be closed under each process. Save the flow before editing checkpoints of changed steps.", 11.5f, Ui.MUTED, false));
        List<String> ids = new ArrayList<>();
        for (JSONObject s : NpdUtil.list(savedSteps)) ids.add(s.optString("id"));
        LinearLayout list = Ui.vbox(a);
        checkpointsBox.addView(list, Ui.matchWrap(a, 6));
        Api.async(() -> api.rows("npd_process_flow_points?select=id,flow_step_id&flow_step_id=in.(" + String.join(",", ids) + ")&limit=5000"), (pts, err) -> {
            Map<String, Integer> counts = new HashMap<>();
            for (JSONObject p : NpdUtil.list(pts)) counts.merge(NpdUtil.s(p, "flow_step_id"), 1, Integer::sum);
            for (JSONObject s : NpdUtil.list(savedSteps)) {
                LinearLayout card = Ui.card(a);
                LinearLayout row = Ui.hbox(a);
                LinearLayout text = Ui.vbox(a);
                text.addView(Ui.text(a, "OP " + NpdUtil.s(s, "operation_no") + " - " + NpdUtil.s(s, "process_name_snapshot"), 14, Ui.TEXT, true));
                int n = counts.getOrDefault(s.optString("id"), 0);
                text.addView(Ui.text(a, n + " checkpoint(s)" + (NpdUtil.s(s, "responsible").isEmpty() ? "" : " · " + NpdUtil.s(s, "responsible")), 11.5f, Ui.MUTED, false));
                row.addView(text, Ui.weight(1));
                row.addView(Ui.text(a, "›", 24, Ui.TEAL, true));
                card.addView(row);
                Ui.clickable(card, Color.WHITE, Ui.LINE, 14);
                card.setOnClickListener(v -> a.push(new NpdPointsScreen(a, s)));
                list.addView(card, Ui.matchWrap(a, 6));
            }
        });
    }

    @Override public boolean onBack() {
        a.confirm("Leave the Process Flow?", "Unsaved changes of the header and operational sequence are lost.", "Leave", () -> a.back());
        return true;
    }
}
