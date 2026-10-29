package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * R39 · Part Master section I "Part Processes & Drawings" (app_pages/ecn.py render_part_processes +
 * core/part_process_service.py): ordered process list of a Part (part_process_routes: Op No., Process, Mandatory Yes / No,
 * In-house / OSP, Remarks, ACTIVE / INACTIVE), copy from the NPD Process Flow when the Part has none, a PCN after a
 * process list change (process_change_defaults - previous / new process flow), and per process the revision-controlled
 * process drawings / specifications (MstPartProcessDocsScreen).
 */
public final class MstPartProcessScreen extends Screen {
    static final String TABLE = "part_process_routes";
    /** Process list text before the last save of each Part (web session PCN_BEFORE_KEY). */
    static final Map<String, String> BEFORE = new HashMap<>();

    private final String partId;
    private JSONObject part;
    private List<JSONObject> routes = new ArrayList<>();
    private Map<String, JSONObject> processes = new HashMap<>();
    private JSONObject npdFlow;
    private Map<String, Integer> docCount = new HashMap<>();
    private boolean[] perms = {false, false, false};

    public MstPartProcessScreen(MainActivity a, JSONObject part) { super(a); this.part = part; this.partId = Lookups.j(part, "id"); }

    @Override public String title() { return "Part processes & drawings"; }
    @Override public String subtitle() { return MstPartGrid.partLabel(part); }
    @Override public int tab() { return Catalog.MASTERS; }

    static boolean active(JSONObject r) { String s = Lookups.j(r, "status"); return s.isEmpty() || "ACTIVE".equalsIgnoreCase(s); }
    static boolean mandatory(JSONObject r) { return r.isNull("is_mandatory") || r.optBoolean("is_mandatory", true); }
    static int op(JSONObject r) { try { return (int) Double.parseDouble(Lookups.j(r, "operation_no")); } catch (Exception e) { return 0; } }

    /** process_display: "CODE · Name" (Process Master) or the name snapshot. */
    static String processName(JSONObject route, Map<String, JSONObject> processes) {
        JSONObject p = processes.get(Lookups.j(route, "process_id"));
        String code = p == null ? "" : Lookups.j(p, "process_code");
        String name = p == null || Lookups.j(p, "process_name").isEmpty() ? Lookups.j(route, "process_name_snapshot") : Lookups.j(p, "process_name");
        if (name.isEmpty()) name = "-";
        return code.isEmpty() ? name : code + " · " + name;
    }

    /** route_text: numbered process list (PCN previous description / revision requested). */
    static String routeText(List<JSONObject> routes, Map<String, JSONObject> processes) {
        List<JSONObject> list = new ArrayList<>();
        for (JSONObject r : routes) if (active(r)) list.add(r);
        Collections.sort(list, (x, y) -> Integer.compare(op(x), op(y)));
        StringBuilder b = new StringBuilder();
        int i = 0;
        for (JSONObject r : list) {
            if (i++ > 0) b.append('\n');
            String remarks = Lookups.j(r, "remarks");
            b.append(i).append(") Op ").append(op(r)).append(' ').append(processName(r, processes)).append(" (")
                .append(mandatory(r) ? "Mandatory" : "Optional").append(", ").append("OSP".equalsIgnoreCase(Lookups.j(r, "source_type")) ? "OSP" : "In-house").append(')')
                .append(remarks.isEmpty() ? "" : " - " + remarks);
        }
        return b.length() == 0 ? "-" : b.toString();
    }

    static Map<String, JSONObject> processMap(Api api) throws Exception {
        Map<String, JSONObject> out = new HashMap<>();
        JSONArray r = api.rows("processes?select=id,process_code,process_name,process_type,status&order=process_name.asc&limit=3000");
        for (int i = 0; i < r.length(); i++) out.put(Lookups.j(r.getJSONObject(i), "id"), r.getJSONObject(i));
        return out;
    }

    static List<JSONObject> routes(Api api, String partId) throws Exception {
        List<JSONObject> out = EcnData.list(api.rows(TABLE + "?select=*&part_id=eq." + Api.enc(partId) + "&order=operation_no.asc&limit=500"));
        Collections.sort(out, (x, y) -> x == y ? 0 : op(x) != op(y) ? Integer.compare(op(x), op(y)) : Lookups.j(x, "status").compareTo(Lookups.j(y, "status")));
        return out;
    }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            boolean[] p = EcnData.permissions(api);
            JSONArray pr = api.rows("parts?select=*&id=eq." + Api.enc(partId) + "&limit=1");
            JSONObject partRow = pr.length() > 0 ? pr.getJSONObject(0) : part;
            List<JSONObject> rs = routes(api, partId);
            Map<String, JSONObject> procs = processMap(api);
            JSONObject flow = null;
            if (rs.isEmpty()) {
                JSONArray f = api.rows("npd_process_flows?select=id,revision,effective_date&part_id=eq." + Api.enc(partId) + "&order=effective_date.desc&limit=1");
                if (f.length() > 0) flow = f.getJSONObject(0);
            }
            Map<String, Integer> counts = new HashMap<>();
            if (!rs.isEmpty()) {
                StringBuilder ids = new StringBuilder();
                for (JSONObject r : rs) { if (ids.length() > 0) ids.append(','); ids.append(Lookups.j(r, "id")); }
                JSONArray d = api.rows("document_attachments?select=entity_id,status&entity_type=eq.PART_PROCESS&status=eq.ACTIVE&entity_id=in.(" + ids + ")&limit=2000");
                for (int i = 0; i < d.length(); i++) {
                    String k = Lookups.j(d.getJSONObject(i), "entity_id");
                    counts.put(k, counts.containsKey(k) ? counts.get(k) + 1 : 1);
                }
            }
            return new Object[]{p, partRow, rs, procs, flow, counts};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            perms = (boolean[]) res[0];
            part = (JSONObject) res[1];
            routes = EcnData.cast(res[2]);
            @SuppressWarnings("unchecked") Map<String, JSONObject> procs = (Map<String, JSONObject>) res[3];
            processes = procs;
            npdFlow = (JSONObject) res[4];
            @SuppressWarnings("unchecked") Map<String, Integer> counts = (Map<String, Integer>) res[5];
            docCount = counts;
            render();
        });
        return scroll;
    }

    private boolean writable() { return perms[0] || perms[1]; }

    private void render() {
        offlineNote();
        if (!MstPartSections.isApplicable(part, "PROCESSES"))
            add(MstForm.noteCard(a, "Part Processes & Drawings is marked NOT APPLICABLE for this Part (Sections applicable)."), 0);
        int act = 0, mand = 0;
        for (JSONObject r : routes) if (active(r)) { act++; if (mandatory(r)) mand++; }
        add(Ui.text(a, act + " active process(es) · " + mand + " mandatory · " + (act - mand) + " optional", 12.5f, Ui.MUTED, false), 0);
        add(Ui.text(a, "Op No. orders the processes. Mandatory = the process must be completed for this Part. Source = In-house or OSP (note the OSP "
            + "vendor in Remarks). Drawings and specifications per process are optional. Set Status INACTIVE to retire a process; a process list "
            + "change can raise a PCN.", 11.5f, Ui.MUTED, false), 4);

        // ---- PCN after a process list change
        String now = routeText(routes, processes);
        String before = BEFORE.get(partId);
        if (before != null && !before.equals(now))
            add(MstForm.noteCard(a, "The process list of this Part was changed. Raise a Process Change Note (PCN) for the customer / internal approval if required."), 8);

        if (routes.isEmpty() && npdFlow != null && writable()) {
            Button copy = Ui.outline(a, "Copy processes from NPD Process Flow Rev " + (Lookups.j(npdFlow, "revision").isEmpty() ? "-" : Lookups.j(npdFlow, "revision")), Ui.TEAL);
            copy.setOnClickListener(v -> copyFromNpd(copy));
            add(copy, 10);
        }
        if (processes.isEmpty()) add(MstForm.noteCard(a, "Create active Processes in Process Master first."), 8);

        add(Ui.label(a, "Part processes (tap to edit · drawings / specs)"), 12);
        LinearLayout card = Ui.card(a);
        if (routes.isEmpty()) card.addView(Ui.text(a, "No processes defined for this Part yet.", 12, Ui.MUTED, false));
        int i = 0;
        for (JSONObject r : routes) {
            if (i++ > 0) card.addView(Ui.divider(a));
            LinearLayout line = Ui.vbox(a);
            line.setPadding(0, dp(7), 0, dp(7));
            LinearLayout top = Ui.hbox(a);
            top.addView(Ui.text(a, "Op " + op(r) + " · " + processName(r, processes), 13.5f, active(r) ? Ui.TEXT : Ui.MUTED, true), Ui.weight(1));
            top.addView(Ui.chip(a, active(r) ? (mandatory(r) ? "Mandatory" : "Optional") : "Inactive", active(r) ? (mandatory(r) ? "green" : "teal") : "grey"));
            line.addView(top);
            Integer n = docCount.get(Lookups.j(r, "id"));
            line.addView(Ui.text(a, Lookups.join("OSP".equalsIgnoreCase(Lookups.j(r, "source_type")) ? "OSP" : "In-house",
                (n == null ? 0 : n) + " current drawing(s) / spec(s)", Lookups.j(r, "remarks")), 11.5f, Ui.MUTED, false));
            LinearLayout btns = Ui.hbox(a);
            Button docs = Ui.outline(a, "Drawings / specs", Ui.TEAL);
            docs.setOnClickListener(v -> a.push(new MstPartProcessDocsScreen(a, part, r, processName(r, processes))));
            btns.addView(docs, Ui.weight(1));
            if (writable()) {
                Button edit = Ui.outline(a, "Edit", Ui.TEAL);
                edit.setOnClickListener(v -> openEditor(r));
                LinearLayout.LayoutParams lp = Ui.weight(1);
                lp.leftMargin = dp(8);
                btns.addView(edit, lp);
            }
            line.addView(btns, Ui.matchWrap(a, 6));
            card.addView(line);
        }
        add(card, 2);
        if (writable()) {
            Button add = Ui.primary(a, "+ Add process");
            add.setOnClickListener(v -> openEditor(null));
            add(add, 10);
            if (act > 0) {
                Button pcn = Ui.outline(a, "Raise PCN (Process Change Note)", Ui.TEAL);
                pcn.setOnClickListener(v -> raisePcn());
                add(pcn, 8);
                if (before != null) {
                    Button dismiss = Ui.outline(a, "Dismiss process change", Ui.TEAL_DARK);
                    dismiss.setOnClickListener(v -> { BEFORE.remove(partId); reload(); });
                    add(dismiss, 8);
                }
            }
        } else add(Ui.text(a, "Part Master create / edit permission is required to change the processes.", 12, Ui.MUTED, false), 10);

        Button ecn = Ui.outline(a, "ECN / PCN of this Part", Ui.TEAL_DARK);
        ecn.setOnClickListener(v -> a.push(new EcnRegisterScreen(a, partId)));
        add(ecn, 12);
    }

    private void openEditor(JSONObject route) {
        // remember the process list before the change (web: PCN_BEFORE_KEY) - only when the Part already had processes
        boolean any = false;
        for (JSONObject r : routes) if (active(r)) any = true;
        if (any && !BEFORE.containsKey(partId)) BEFORE.put(partId, routeText(routes, processes));
        a.push(new MstPartProcessEditScreen(a, part, route, routes, processes));
    }

    private void raisePcn() {
        String now = routeText(routes, processes);
        String before = BEFORE.containsKey(partId) ? BEFORE.get(partId) : now;
        try {
            JSONObject d = EcnData.processChangeDefaults(part, before, now);
            BEFORE.remove(partId);
            a.push(new EcnFormScreen(a, d, null, null, null));
        } catch (Exception e) { a.toast(Api.message(e)); }
    }

    /** PartProcessService.copy_from_npd. */
    private void copyFromNpd(Button b) {
        b.setEnabled(false);
        Api.async(() -> {
            JSONArray steps = api.rows("npd_process_flow_steps?select=*&flow_id=eq." + Api.enc(Lookups.j(npdFlow, "id")) + "&order=operation_no.asc&limit=500");
            for (int i = 0; i < steps.length(); i++) {
                JSONObject st = steps.getJSONObject(i);
                JSONObject proc = processes.get(Lookups.j(st, "process_id"));
                int opNo = op(st) > 0 ? op(st) : (i + 1) * 10;
                JSONObject p = new JSONObject().put("part_id", partId).put("operation_no", opNo)
                    .put("process_id", Lookups.j(st, "process_id").isEmpty() ? JSONObject.NULL : Lookups.j(st, "process_id"))
                    .put("process_name_snapshot", proc != null ? Lookups.j(proc, "process_name") : Lookups.j(st, "process_name_snapshot"))
                    .put("is_mandatory", true)
                    .put("source_type", proc != null && "OUTSOURCED".equalsIgnoreCase(Lookups.j(proc, "process_type")) ? "OSP" : "IN_HOUSE")
                    .put("remarks", Lookups.j(st, "remarks").isEmpty() ? JSONObject.NULL : Lookups.j(st, "remarks"))
                    .put("sequence_no", (i + 1) * 10).put("status", "ACTIVE");
                api.insert(TABLE, p);
            }
            return steps.length();
        }, (n, err) -> {
            b.setEnabled(true);
            if (err != null) { a.toast(Api.message(err)); return; }
            a.toast(n + " process(es) copied from the NPD Process Flow.");
            reload();
        });
    }

    static String upper(String s) { return s == null ? "" : s.trim().toUpperCase(Locale.ROOT); }
}
