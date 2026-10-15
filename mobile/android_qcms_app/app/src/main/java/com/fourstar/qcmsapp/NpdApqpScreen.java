package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * APQP project (npd_apqp.py render_apqp): project header (ppap_projects) and the APQP gates / deliverables
 * (ppap_documents) with the standard 8 gates, removed gates deleted and completion % recomputed after saving.
 */
public final class NpdApqpScreen extends Screen {
    static final String[] PROJECT_STATUSES = {"IN_PROGRESS", "ON_HOLD", "COMPLETED", "CANCELLED"};
    static final String[] GATE_STATUSES = {"NOT_STARTED", "IN_PROGRESS", "ON_HOLD", "COMPLETED", "APPROVED", "NOT_APPLICABLE"};
    static final String[] LEVELS = {"Level 1", "Level 2", "Level 3", "Level 4", "Level 5"};
    /** _default_apqp_tasks(). */
    static final Object[][] DEFAULT_GATES = {
        {10, "Phase 1 - Plan & Define", "Customer Requirements / Feasibility Review"},
        {20, "Phase 2 - Product Design", "Drawing / Technical Specification Review"},
        {30, "Phase 3 - Process Design", "Process Flow Diagram"},
        {40, "Phase 3 - Process Design", "PFMEA"},
        {50, "Phase 3 - Process Design", "Control Plan"},
        {60, "Phase 4 - Validation", "Tooling / Gauge / Process Validation"},
        {70, "Phase 4 - Validation", "MSA / Capability / Dimensional / Material Validation"},
        {80, "Phase 5 - Launch & Feedback", "PPAP Submission / Customer Approval"},
    };

    private final String id;
    private JSONObject existing;
    private FormView form;
    private RowsEditor gates;
    private Button loadStd, save;
    private TextView kpi;
    private final Set<String> existingGateIds = new HashSet<>();
    private final Field.Lookup parts = Lookups.parts();
    private final Field.Lookup customers = NpdUtil.customers();
    private final Field.Lookup employees = NpdUtil.employees();

    public NpdApqpScreen(MainActivity a, String id) { super(a); this.id = id; }

    @Override public String title() { return (id == null ? "New · " : "Edit · ") + "APQP Project"; }
    @Override public String subtitle() { return "Project header and APQP phase gates"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            Lookups.rows(api, parts);
            Lookups.rows(api, customers);
            Lookups.rows(api, employees);
            if (id == null) return new Object[]{null, new JSONArray()};
            JSONArray r = api.rows("ppap_projects?select=*&id=eq." + Api.enc(id));
            if (r.length() == 0) throw new Api.ApiException(404, "APQP project not found.");
            JSONArray g = api.rows("ppap_documents?select=*&ppap_project_id=eq." + Api.enc(id) + "&order=sequence_no.asc&limit=500");
            return new Object[]{r.getJSONObject(0), g};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            existing = (JSONObject) res[0];
            render((JSONArray) res[1]);
        });
        return scroll;
    }

    private void render(JSONArray tasks) {
        offlineNote();
        add(Ui.label(a, "A · APQP project header"), 4);
        form = new FormView(a, Arrays.asList(
            Field.text("project_code", "Project / NPD Number").req(),
            Field.lookup("part_id", "Part Number", parts).req(),
            Field.lookup("customer_id", "Customer", customers).req(),
            Field.select("submission_level", "PPAP Submission Level", LEVELS).req().def("Level 3"),
            Field.date("target_submission_date", "Target PPAP Submission").req().def(LocalDate.now().plusDays(60).toString()),
            Field.lookup("coordinator_employee_id", "APQP Coordinator", employees),
            Field.text("reason", "Reason / Program").def("New Product Development"),
            Field.select("status", "Project Status", PROJECT_STATUSES).req().def("IN_PROGRESS"),
            Field.area("remarks", "APQP Remarks")));
        LinearLayout card = Ui.card(a);
        card.addView(form);
        add(card, 2);
        if (existing != null) {
            form.setAll(existing);
            if (!Arrays.asList(LEVELS).contains(NpdUtil.s(existing, "submission_level"))) form.set("submission_level", "Level 3");
            if (!Arrays.asList(PROJECT_STATUSES).contains(NpdUtil.s(existing, "status"))) form.set("status", "IN_PROGRESS");
            if (NpdUtil.s(existing, "target_submission_date").isEmpty()) form.set("target_submission_date", LocalDate.now().plusDays(60).toString());
            String legacy = NpdUtil.s(existing, "coordinator");
            if (NpdUtil.s(existing, "coordinator_employee_id").isEmpty() && !legacy.isEmpty()) {
                card.addView(Ui.text(a, "Saved coordinator (legacy text): " + legacy + " - kept unless you choose an employee.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 6));
            }
        } else {
            form.onChange((key, value) -> {
                if (!"part_id".equals(key) || value == null) return;
                JSONObject p = Lookups.rowOf(parts, String.valueOf(value));
                String cust = p == null ? "" : NpdUtil.s(p, "customer_id");
                if (!cust.isEmpty() && Lookups.rowOf(customers, cust) != null) form.set("customer_id", cust);
            });
        }

        add(Ui.label(a, "B · APQP phase status"), 14);
        LinearLayout gcard = Ui.card(a);
        kpi = Ui.text(a, "", 12, Ui.TEXT, false);
        gcard.addView(kpi);
        List<Field> fields = Arrays.asList(
            Field.integer("sequence_no", "Seq").req().range(0, 999999),
            Field.text("apqp_phase", "APQP Phase").req(),
            Field.text("document_type", "Activity / Deliverable").req(),
            Field.text("document_number", "Evidence / Document No."),
            Field.text("revision", "Revision"),
            Field.lookup("owner_employee_id", "Owner", employees),
            Field.date("due_date", "Due Date"),
            Field.select("status", "Status", GATE_STATUSES).req().def("NOT_STARTED"),
            Field.date("approved_date", "Approved Date"),
            Field.text("remarks", "Remarks"));
        List<String[]> cols = Arrays.asList(new String[]{"sequence_no", "Seq"}, new String[]{"apqp_phase", "APQP Phase"},
            new String[]{"document_type", "Activity / Deliverable"}, new String[]{"document_number", "Evidence / Doc No."},
            new String[]{"revision", "Rev"}, new String[]{"_owner", "Owner"}, new String[]{"due_date", "Due Date"},
            new String[]{"status", "Status"}, new String[]{"approved_date", "Approved"}, new String[]{"remarks", "Remarks"});
        gates = new RowsEditor(a, "Gates", fields, cols);
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject t : NpdUtil.list(tasks)) {
            JSONObject r = NpdUtil.copy(t);
            existingGateIds.add(t.optString("id"));
            try {
                if (NpdUtil.s(r, "status").isEmpty()) r.put("status", "NOT_STARTED");
                if (r.isNull("sequence_no")) r.put("sequence_no", 0);
                if (NpdUtil.s(t, "owner_employee_id").isEmpty() && !NpdUtil.s(t, "owner").isEmpty()) r.put("_legacy", NpdUtil.s(t, "owner"));
            } catch (Exception ignored) { }
            rows.add(r);
        }
        gates.setRows(rows);
        gates.onChanged(this::recompute);
        gcard.addView(gates, Ui.matchWrap(a, 8));
        loadStd = Ui.outline(a, "Load Standard APQP Gates", Ui.TEAL);
        loadStd.setOnClickListener(v -> loadStandard());
        gcard.addView(loadStd, Ui.matchWrap(a, 8));
        add(gcard, 2);
        recompute();

        save = Ui.primary(a, existing == null ? "Save APQP Project" : "Save APQP Project & Gates");
        save.setOnClickListener(v -> save());
        add(save, 14);
    }

    private static boolean closed(JSONObject g) {
        String s = NpdUtil.s(g, "status");
        return "COMPLETED".equals(s) || "APPROVED".equals(s) || "NOT_APPLICABLE".equals(s);
    }

    private void recompute() {
        List<JSONObject> rows = gates.rows();
        int done = 0, overdue = 0;
        LocalDate today = LocalDate.now();
        for (JSONObject g : rows) {
            String emp = NpdUtil.s(g, "owner_employee_id");
            try {
                g.put("_owner", !emp.isEmpty() ? Lookups.labelOf(employees, emp) : (NpdUtil.s(g, "_legacy").isEmpty() ? "— Not assigned —" : "Legacy · " + NpdUtil.s(g, "_legacy")));
            } catch (Exception ignored) { }
            if (closed(g)) { done++; continue; }
            LocalDate due = NpdUtil.date(g.opt("due_date"));
            if (due != null && due.isBefore(today)) overdue++;
        }
        int max = 0;
        for (JSONObject g : rows) max = Math.max(max, NpdUtil.intOf(g.opt("sequence_no"), 0));
        try { gates.template(new JSONObject().put("sequence_no", max + 10).put("status", "NOT_STARTED")); } catch (Exception ignored) { }
        gates.refresh();
        if (rows.isEmpty()) {
            kpi.setText("No gates yet. Load the standard APQP gates or add rows.");
        } else {
            int pct = (int) Math.rint(done * 100.0 / rows.size());
            LocalDate target = NpdUtil.date(form.str("target_submission_date"));
            kpi.setText("APQP Completion " + pct + "% (" + done + "/" + rows.size() + " gates closed) · Open gates " + (rows.size() - done)
                + " · Overdue gates " + overdue + (target == null ? "" : " · PPAP target " + Ui.date(target.toString()) + " (" + ChronoUnit.DAYS.between(today, target) + " day(s))"));
        }
        loadStd.setVisibility(rows.isEmpty() ? View.VISIBLE : View.GONE);
    }

    private void loadStandard() {
        List<JSONObject> rows = new ArrayList<>();
        for (Object[] g : DEFAULT_GATES) {
            try { rows.add(new JSONObject().put("sequence_no", g[0]).put("apqp_phase", g[1]).put("document_type", g[2]).put("status", "NOT_STARTED")); } catch (Exception ignored) { }
        }
        List<JSONObject> removed = new ArrayList<>(gates.removedRows());
        gates.setRows(rows);
        gates.removedRows().addAll(removed);
        recompute();
        a.toast("Standard APQP gates loaded. Save to store them.");
    }

    private void save() {
        String problem = form.validate();
        if (problem != null) { a.toast(problem); return; }
        if (form.str("project_code").trim().isEmpty()) { a.toast("Project / NPD Number is required."); return; }
        save.setEnabled(false);
        save.setText("Saving…");
        final String legacyCoordinator = existing == null ? "" : NpdUtil.s(existing, "coordinator");
        final List<JSONObject> rows = new ArrayList<>(gates.rows());
        Api.async(() -> {
            String coord = form.str("coordinator_employee_id");
            JSONObject payload = new JSONObject();
            payload.put("project_code", form.str("project_code").trim());
            payload.put("part_id", form.str("part_id"));
            payload.put("customer_id", form.str("customer_id"));
            payload.put("submission_level", form.str("submission_level"));
            payload.put("reason", NpdUtil.orNull(form.str("reason")));
            payload.put("target_submission_date", form.str("target_submission_date").substring(0, 10));
            payload.put("coordinator_employee_id", coord.isEmpty() ? JSONObject.NULL : coord);
            payload.put("coordinator", NpdUtil.snapshot(employees, coord, NpdUtil.s(existing, "coordinator_employee_id").isEmpty() ? legacyCoordinator : ""));
            payload.put("status", form.str("status"));
            payload.put("remarks", NpdUtil.orNull(form.str("remarks")));
            JSONObject saved;
            if (existing != null) saved = api.update("ppap_projects", existing.optString("id"), payload);
            else { payload.put("completion_percent", 0); saved = api.insert("ppap_projects", payload); }
            String projectId = saved.optString("id");
            if (rows.isEmpty() && existingGateIds.isEmpty()) return saved;
            try {
                Set<String> retained = new HashSet<>();
                for (JSONObject r : rows) {
                    String activity = NpdUtil.s(r, "document_type").trim();
                    if (activity.isEmpty()) continue;
                    String owner = NpdUtil.s(r, "owner_employee_id");
                    JSONObject g = new JSONObject();
                    g.put("ppap_project_id", projectId);
                    g.put("sequence_no", NpdUtil.intOf(r.opt("sequence_no"), 0));
                    g.put("apqp_phase", NpdUtil.orNull(NpdUtil.s(r, "apqp_phase")));
                    g.put("document_type", activity);
                    g.put("document_number", NpdUtil.orNull(NpdUtil.s(r, "document_number")));
                    g.put("revision", NpdUtil.orNull(NpdUtil.s(r, "revision")));
                    g.put("owner_employee_id", owner.isEmpty() ? JSONObject.NULL : owner);
                    g.put("owner", NpdUtil.snapshot(employees, owner, r.opt("_legacy")));
                    String due = NpdUtil.s(r, "due_date"), appr = NpdUtil.s(r, "approved_date");
                    g.put("due_date", due.isEmpty() ? JSONObject.NULL : due.substring(0, 10));
                    g.put("status", NpdUtil.s(r, "status").isEmpty() ? "NOT_STARTED" : NpdUtil.s(r, "status"));
                    g.put("approved_date", appr.isEmpty() ? JSONObject.NULL : appr.substring(0, 10));
                    g.put("remarks", NpdUtil.orNull(NpdUtil.s(r, "remarks")));
                    String gid = NpdUtil.s(r, "id");
                    if (existingGateIds.contains(gid)) { api.update("ppap_documents", gid, g); retained.add(gid); }
                    else retained.add(api.insert("ppap_documents", g).optString("id"));
                }
                for (String gid : existingGateIds) if (!retained.contains(gid)) NpdUtil.deleteRow(api, "ppap_documents", gid);
                List<JSONObject> refreshed = NpdUtil.list(api.rows("ppap_documents?select=id,status&ppap_project_id=eq." + projectId + "&limit=500"));
                int closedCount = 0;
                for (JSONObject g : refreshed) if (closed(g)) closedCount++;
                int percent = refreshed.isEmpty() ? 0 : (int) Math.rint(closedCount * 100.0 / refreshed.size());
                api.update("ppap_projects", projectId, new JSONObject().put("completion_percent", percent));
            } catch (Exception e) {
                throw new Exception("The APQP project header was saved, but saving the gates stopped: " + Api.message(e) + ". Open the project and save the gates again.");
            }
            return saved;
        }, (saved, err) -> {
            save.setEnabled(true);
            save.setText(existing == null ? "Save APQP Project" : "Save APQP Project & Gates");
            if (err != null) { a.toast(Api.message(err)); return; }
            a.toast("APQP Project saved successfully.");
            Module m = Catalog.get("apqp_projects");
            if (existing == null && m != null) a.replaceTop(new RecordScreen(a, m, saved.optString("id")));
            else a.back();
        });
    }

    @Override public boolean onBack() {
        a.confirm("Leave without saving?", "Changes on this form are not saved.", "Leave", () -> a.back());
        return true;
    }
}
