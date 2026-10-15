package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Native Inspection Layout editor (app_pages/inspection_layouts.py + InspectionService.save_plan): plan header,
 * auto plan number, one-current-layout-per-scope check, characteristics grid with the website checks and the
 * bulk upsert of inspection_plan_characteristics matched by sequence_no.
 */
final class InspLayoutScreen extends Screen {
    static final String[] STATUSES = {"DRAFT", "APPROVAL_PENDING", "APPROVED", "SUPERSEDED"};
    static final Object[][] BEND_DEFAULTS = {
        {10, "1", "Baking Temperature", "400°C / as approved process", null, null, "°C", "NUMBER", "Baking / ageing process record", 1},
        {20, "2", "Baking Time", "60 Minutes Minimum", 60.0, null, "Minutes", "NUMBER", "Baking / ageing process record", 1},
        {30, "3", "Base Metal Hardness below plating", "446-544 HV (45-52 HRC) · average of three observations", 45.0, 52.0, "HRC", "NUMBER", "Hardness tester", 3},
        {40, "4", "Load", "Record achieved test load", null, null, "kN", "NUMBER", "Compression / bend test machine", 1},
        {50, "5", "CHT", "Record cross head travel", null, null, "mm", "NUMBER", "Compression / bend test machine", 1},
        {60, "6", "Bend Angle", "Record achieved bend angle", null, null, "Degree", "NUMBER", "Bend test fixture / angle measurement", 1},
        {70, "7", "Bend Test Status", "Passed", null, null, "", "TEXT", "Visual / test report review", 1},
        {80, "8", "Plating Surface Condition", "No Peeling, Flaking on the plating surface.", null, null, "", "TEXT", "Visual inspection after bend test", 1}};

    private final String id;
    private final boolean bendStart;
    private JSONObject existing;
    private List<JSONObject> sourceRows = new ArrayList<>();
    private String existingMethod = InspUtil.GENERAL_METLAB;
    private boolean loaded = false;
    private FormView form;
    private RowsEditor grid;
    private TextView planNo;
    private Map<String, String> cache;
    private List<JSONObject> rowsCache;

    InspLayoutScreen(MainActivity a, String id, boolean bendStart) {
        super(a);
        this.id = id;
        this.bendStart = bendStart;
    }

    @Override public String title() { return existing != null ? "Edit · " + InspUtil.j(existing, "plan_number") : bendStart ? "New · Bend Test Layout" : "New · Inspection Layout"; }
    @Override public String subtitle() { return "Part · Process · Stage · one current layout per scope"; }
    @Override public int tab() { return Catalog.QUALITY; }

    @Override
    public View build() {
        newPage();
        if (loaded) { snapshot(); render(); return scroll; }
        page.addView(loading());
        Api.async(() -> {
            if (id != null) {
                existing = InspUtil.get(api, "inspection_plans", id);
                if (existing == null) throw new Api.ApiException(404, "Layout not found.");
                sourceRows = InspUtil.planChars(api, id);
                existingMethod = InspUtil.methodFromRows(sourceRows, InspUtil.planText(existing));
            }
            Lookups.rows(api, Lookups.parts());
            Lookups.rows(api, Lookups.processes());
            Lookups.rows(api, Lookups.stages());
            return true;
        }, (ok, err) -> {
            loaded = true;
            if (err != null) { page.removeAllViews(); page.addView(error(err, () -> { loaded = false; a.rebuild(); })); return; }
            a.rebuildTitle(this);
            render();
        });
        return scroll;
    }

    private void snapshot() {
        if (form != null) {
            cache = new HashMap<>();
            for (String k : new String[]{"layout_type", "inspection_method", "part_id", "inward_type", "process_id", "inspection_stage_id", "status", "layout_name", "revision", "default_sample_size", "report_title", "format_number", "format_revision", "effective_date"}) cache.put(k, form.str(k));
        }
        if (grid != null) rowsCache = new ArrayList<>(grid.rows());
    }

    private String type() { return form.str("layout_type").isEmpty() ? "DIMENSIONAL" : form.str("layout_type"); }
    private String method() { return "METLAB".equals(type()) && InspUtil.BEND_TEST.equals(form.str("inspection_method")) ? InspUtil.BEND_TEST : InspUtil.GENERAL_METLAB; }

    private void render() {
        page.removeAllViews();
        List<Field> f = new ArrayList<>();
        f.add(Field.select("layout_type", "Layout Type", "DIMENSIONAL", "METLAB").labels("Dimensional", "MetLAB").req());
        if (existing != null) f.get(0).readOnly = true;
        f.add(Field.select("inspection_method", "Inspection Method / Sub Category", InspUtil.GENERAL_METLAB, InspUtil.BEND_TEST).labels("General MetLAB", "Bend Test").req());
        f.add(Field.lookup("part_id", "Part Number", Lookups.parts()).req());
        f.add(Field.select("inward_type", "Inward Type", "MATERIAL_INWARD", "OSP_PROCESS").labels("Material Inward", "OSP Process").req());
        f.add(Field.lookup("process_id", "Process", Lookups.processes()).hint("OSP Process layouts require an OUTSOURCED process"));
        f.add(Field.lookup("inspection_stage_id", "Inspection Stage", Lookups.stages()).req());
        f.add(Field.select("status", "Status", STATUSES).req());
        f.add(Field.text("layout_name", "Layout Name").req());
        f.add(Field.text("revision", "Revision"));
        f.add(Field.integer("default_sample_size", "Default Sample Size").range(1, 20).req());
        f.add(Field.text("report_title", "Report Title"));
        f.add(Field.text("format_number", "Format Number"));
        f.add(Field.text("format_revision", "Format Revision"));
        f.add(Field.date("effective_date", "Effective Date").req());
        form = new FormView(a, f);
        JSONObject e = existing;
        String lt = e != null ? (InspUtil.j(e, "layout_type").isEmpty() ? "DIMENSIONAL" : InspUtil.j(e, "layout_type")) : bendStart ? "METLAB" : "DIMENSIONAL";
        form.set("layout_type", lt);
        form.set("inspection_method", e != null ? existingMethod : bendStart ? InspUtil.BEND_TEST : InspUtil.GENERAL_METLAB);
        if (!InspUtil.j(e, "part_id").isEmpty()) form.set("part_id", InspUtil.j(e, "part_id"));
        form.set("inward_type", InspUtil.j(e, "inward_type").isEmpty() ? "MATERIAL_INWARD" : InspUtil.j(e, "inward_type"));
        if (!InspUtil.j(e, "process_id").isEmpty()) form.set("process_id", InspUtil.j(e, "process_id"));
        if (!InspUtil.j(e, "inspection_stage_id").isEmpty()) form.set("inspection_stage_id", InspUtil.j(e, "inspection_stage_id"));
        form.set("status", InspUtil.j(e, "status").isEmpty() ? "DRAFT" : InspUtil.j(e, "status"));
        form.set("layout_name", InspUtil.j(e, "layout_name"));
        form.set("revision", InspUtil.j(e, "revision").isEmpty() ? "00" : InspUtil.j(e, "revision"));
        form.set("default_sample_size", InspUtil.j(e, "default_sample_size").isEmpty() ? ("DIMENSIONAL".equals(lt) ? "6" : "1") : InspUtil.j(e, "default_sample_size"));
        String title = InspUtil.j(e, "report_title");
        if (title.isEmpty() && e == null) title = bendStart ? "BEND TEST REPORT" : "DIMENSIONAL".equals(lt) ? "DIMENSIONAL INSPECTION REPORT" : "METLAB REPORT";
        form.set("report_title", title);
        form.set("format_number", InspUtil.j(e, "format_number"));
        form.set("format_revision", InspUtil.j(e, "format_revision").isEmpty() ? "00" : InspUtil.j(e, "format_revision"));
        form.set("effective_date", InspUtil.j(e, "effective_date").isEmpty() ? Ui.today() : InspUtil.j(e, "effective_date").substring(0, 10));
        if (cache != null) for (Map.Entry<String, String> en : cache.entrySet()) form.set(en.getKey(), en.getValue().isEmpty() ? null : en.getValue());

        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, "Layout header", 14, Ui.TEXT, true));
        card.addView(form, Ui.matchWrap(a, 4));
        planNo = Ui.text(a, "", 12.5f, Ui.TEAL_DARK, true);
        card.addView(planNo, Ui.matchWrap(a, 8));
        card.addView(Ui.text(a, "Only one current layout is permitted for each Part + Inspection Stage + Process + Layout Type scope; older history may remain SUPERSEDED.", 11.5f, Ui.MUTED, false));
        add(card, 4);

        // characteristics
        List<Field> rf = new ArrayList<>();
        rf.add(Field.integer("sequence_no", "Sequence").req());
        rf.add(Field.text("characteristic_no", "Characteristic No"));
        rf.add(Field.text("characteristic", "Parameter").req());
        rf.add(Field.text("specification", "Specification").hint("Required for TEXT parameters"));
        rf.add(Field.number("lower_spec", "Minimum"));
        rf.add(Field.number("upper_spec", "Maximum"));
        rf.add(Field.text("unit", "Unit"));
        rf.add(Field.select("characteristic_type", "Type", "NUMBER", "TEXT").labels("Number", "Text").req());
        rf.add(Field.text("checking_aid_text", "Checking Aid"));
        rf.add(Field.integer("sample_size", "Sample Size").range(1, 1000));
        rf.add(Field.bool("allow_na", "Allow NA"));
        rf.add(Field.bool("is_mandatory", "Mandatory"));
        rf.add(Field.bool("case_depth_traverse", "Case Depth Traverse (MetLAB)").hint("Creates a Case Depth / Microhardness Traverse location"));
        rf.add(Field.text("case_depth_location", "Traverse Location").hint("Required when Case Depth Traverse is ticked, e.g. Ground Face, ID, OD"));
        rf.add(Field.select("status", "Status", "ACTIVE", "INACTIVE").req());
        List<String[]> cols = Arrays.asList(new String[]{"sequence_no", "Seq"}, new String[]{"characteristic_no", "No"}, new String[]{"characteristic", "Parameter"},
            new String[]{"specification", "Specification"}, new String[]{"lower_spec", "Min"}, new String[]{"upper_spec", "Max"}, new String[]{"unit", "Unit"},
            new String[]{"characteristic_type", "Type"}, new String[]{"checking_aid_text", "Checking Aid"}, new String[]{"sample_size", "Samples"},
            new String[]{"allow_na", "Allow NA"}, new String[]{"is_mandatory", "Mandatory"}, new String[]{"case_depth_traverse", "Case Depth"},
            new String[]{"case_depth_location", "Traverse Location"}, new String[]{"status", "Status"});
        grid = new RowsEditor(a, "Layout characteristics", rf, cols);
        try {
            grid.template(new JSONObject().put("characteristic_type", "NUMBER").put("status", "ACTIVE").put("is_mandatory", true).put("allow_na", false).put("case_depth_traverse", false));
        } catch (Exception ignored) { }
        grid.check(r -> {
            String ctype = r.optString("characteristic_type", "NUMBER");
            if ("TEXT".equals(ctype) && InspUtil.j(r, "specification").isEmpty()) return "Text Specification is mandatory for " + InspUtil.j(r, "characteristic") + ".";
            if (r.optBoolean("case_depth_traverse", false) && InspUtil.j(r, "case_depth_location").isEmpty()) return "Traverse Location is required when Case Depth Traverse is ticked for " + InspUtil.j(r, "characteristic") + ".";
            return null;
        });
        grid.onChanged(() -> grid.template(nextTemplate()));
        grid.setRows(rowsCache != null ? rowsCache : editorRows(sourceRows));
        grid.template(nextTemplate());
        add(Ui.label(a, "Layout characteristics"), 14);
        add(grid, 4);
        add(Ui.text(a, "Rows you remove from a saved layout are set to INACTIVE on save (history is kept).", 11.5f, Ui.MUTED, false), 4);

        LinearLayout tools = Ui.vbox(a);
        Button osp = Ui.outline(a, "Load parameters from Part Master OSP process", Ui.TEAL);
        osp.setOnClickListener(v -> loadOspParameters());
        tools.addView(osp, Ui.matchWrap(a, 0));
        Button bend = Ui.outline(a, "Load Bend Test starter parameters", Ui.TEAL);
        bend.setOnClickListener(v -> {
            if (!grid.rows().isEmpty()) { a.toast("Starter parameters load only into an empty layout grid."); return; }
            grid.setRows(bendRows(form.num("default_sample_size")));
            grid.template(nextTemplate());
            a.toast("Bend Test starter parameters loaded. Adjust specifications for this Part before approval.");
        });
        tools.addView(bend, Ui.matchWrap(a, 8));
        add(tools, 10);

        Button save = Ui.primary(a, "Save Inspection Layout");
        save.setOnClickListener(v -> save(save));
        add(save, 16);

        form.onChange((k, v) -> refreshHeader(k));
        refreshHeader("");
        if (existing == null && sourceRows.isEmpty() && rowsCache == null && bendStart && grid.rows().isEmpty()) {
            grid.setRows(bendRows(form.num("default_sample_size")));
            grid.template(nextTemplate());
        }
    }

    private JSONObject nextTemplate() {
        int max = 0;
        for (JSONObject r : grid.rows()) { Double s = Rules.number(r.opt("sequence_no")); if (s != null) max = Math.max(max, (int) Math.round(s)); }
        try {
            Double ds = form == null ? null : form.num("default_sample_size");
            return new JSONObject().put("sequence_no", max + 10).put("characteristic_type", "NUMBER").put("status", "ACTIVE").put("is_mandatory", true)
                .put("allow_na", false).put("case_depth_traverse", false).put("sample_size", ds == null ? 1 : (int) Math.round(ds));
        } catch (Exception e) { return new JSONObject(); }
    }

    private void refreshHeader(String key) {
        boolean metlab = "METLAB".equals(type());
        form.setVisible("inspection_method", metlab);
        if (("layout_type".equals(key) || "inspection_method".equals(key)) && existing == null) {
            String t = form.str("report_title").toUpperCase(Locale.ROOT);
            if (t.isEmpty() || t.equals("METLAB REPORT") || t.equals("DIMENSIONAL INSPECTION REPORT") || t.equals("BEND TEST REPORT")) {
                form.set("report_title", !metlab ? "DIMENSIONAL INSPECTION REPORT" : InspUtil.BEND_TEST.equals(method()) ? "BEND TEST REPORT" : "METLAB REPORT");
            }
        }
        JSONObject part = Lookups.rowOf(Lookups.parts(), form.str("part_id"));
        JSONObject process = Lookups.rowOf(Lookups.processes(), form.str("process_id"));
        JSONObject stage = Lookups.rowOf(Lookups.stages(), form.str("inspection_stage_id"));
        String no = autoPlanNumber(part, process, stage, form.str("layout_name"));
        planNo.setText("Plan Number (Auto): " + no + (metlab && InspUtil.BEND_TEST.equals(method()) && !no.toUpperCase(Locale.ROOT).contains("BEND") ? "-BEND" : ""));
    }

    /** InspectionService._layout_token. */
    static String token(String value, String fallback, int max) {
        String t = (value == null ? "" : value.trim()).toUpperCase(Locale.ROOT).replaceAll("[^A-Za-z0-9]+", "-").replaceAll("^-+|-+$", "");
        String s = t.isEmpty() ? fallback : t;
        s = s.substring(0, Math.min(max, s.length())).replaceAll("^-+|-+$", "");
        return s.isEmpty() ? fallback : s;
    }

    static String autoPlanNumber(JSONObject part, JSONObject process, JSONObject stage, String layoutName) {
        String st = InspUtil.j(stage, "stage_code").isEmpty() ? InspUtil.j(stage, "stage_name") : InspUtil.j(stage, "stage_code");
        String pr = InspUtil.j(process, "process_code").isEmpty() ? InspUtil.j(process, "process_name") : InspUtil.j(process, "process_code");
        String pa = InspUtil.j(part, "part_number").isEmpty() ? InspUtil.j(part, "fsi_part_number") : InspUtil.j(part, "part_number");
        return token(st, "STAGE", 20) + "-" + token(pr, "NOPROCESS", 24) + "-" + token(pa, "PART", 30) + "-" + token(layoutName, "LAYOUT", 36);
    }

    private List<JSONObject> editorRows(List<JSONObject> src) {
        List<JSONObject> out = new ArrayList<>();
        Double ds = form.num("default_sample_size");
        int pos = 0;
        for (JSONObject r : src) {
            pos++;
            try {
                JSONObject meta = InspUtil.metadata(r);
                JSONObject o = new JSONObject();
                if (!InspUtil.j(r, "id").isEmpty()) o.put("id", InspUtil.j(r, "id"));
                o.put("_meta", meta);
                Double seq = Rules.number(r.opt("sequence_no"));
                o.put("sequence_no", seq == null ? pos : (int) Math.round(seq));
                o.put("characteristic_no", InspUtil.j(r, "characteristic_no").isEmpty() ? String.valueOf(pos) : InspUtil.j(r, "characteristic_no"));
                o.put("characteristic", InspUtil.j(r, "characteristic"));
                o.put("specification", InspUtil.j(r, "specification"));
                o.put("lower_spec", InspUtil.numOrNull(r.opt("lower_spec")));
                o.put("upper_spec", InspUtil.numOrNull(r.opt("upper_spec")));
                o.put("unit", InspUtil.j(r, "unit"));
                String ct = InspUtil.j(r, "characteristic_type").toUpperCase(Locale.ROOT);
                o.put("characteristic_type", ct.equals("TEXT") || ct.equals("ATTRIBUTE") ? "TEXT" : "NUMBER");
                o.put("checking_aid_text", !InspUtil.j(r, "checking_aid_text").isEmpty() ? InspUtil.j(r, "checking_aid_text") : InspUtil.j(r, "checking_method"));
                Double ss = Rules.number(r.opt("sample_size"));
                o.put("sample_size", ss != null && ss > 0 ? (int) Math.round(ss) : ds == null ? 1 : (int) Math.round(ds));
                o.put("allow_na", r.optBoolean("allow_na", false));
                o.put("is_mandatory", r.isNull("is_mandatory") ? true : r.optBoolean("is_mandatory", true));
                o.put("case_depth_traverse", meta.optBoolean("case_depth_traverse", false));
                o.put("case_depth_location", InspUtil.j(meta, "case_depth_location"));
                o.put("status", InspUtil.j(r, "status").isEmpty() ? "ACTIVE" : InspUtil.j(r, "status"));
                out.add(o);
            } catch (Exception ignored) { }
        }
        return out;
    }

    private List<JSONObject> bendRows(Double defaultSample) {
        List<JSONObject> out = new ArrayList<>();
        for (Object[] b : BEND_DEFAULTS) {
            try {
                out.add(new JSONObject().put("sequence_no", b[0]).put("characteristic_no", b[1]).put("characteristic", b[2]).put("specification", b[3])
                    .put("lower_spec", b[4] == null ? JSONObject.NULL : b[4]).put("upper_spec", b[5] == null ? JSONObject.NULL : b[5]).put("unit", b[6])
                    .put("characteristic_type", b[7]).put("checking_aid_text", b[8]).put("sample_size", b[9]).put("allow_na", false).put("is_mandatory", true)
                    .put("case_depth_traverse", false).put("case_depth_location", "").put("status", "ACTIVE"));
            } catch (Exception ignored) { }
        }
        return out;
    }

    /** InspectionService.osp_parameter_characteristics. */
    static Object[] ospParameters(Api api, String partId, String processId, String layoutType) throws Exception {
        List<JSONObject> groups = InspUtil.list(api.rows("part_process_specifications?select=*&part_id=eq." + Api.enc(partId) + "&process_id=eq." + Api.enc(processId)
            + "&inward_type=eq.OSP_PROCESS&status=eq.ACTIVE&order=sequence_no.asc&limit=20"));
        if (groups.isEmpty()) return new Object[]{null, new ArrayList<JSONObject>()};
        JSONObject group = groups.get(0);
        List<JSONObject> params = InspUtil.list(api.rows("part_process_parameter_specifications?select=*&process_specification_id=eq." + Api.enc(InspUtil.j(group, "id"))
            + "&inspection_type=eq." + layoutType + "&status=eq.ACTIVE&order=sequence_no.asc&limit=1000"));
        List<JSONObject> out = new ArrayList<>();
        int i = 0;
        for (JSONObject r : params) {
            i++;
            String ct = InspUtil.j(r, "characteristic_type").isEmpty() ? "NUMBER" : InspUtil.j(r, "characteristic_type").toUpperCase(Locale.ROOT);
            Double ss = Rules.number(r.opt("sample_size"));
            if (ss == null || ss == 0) ss = Rules.number(group.opt("sample_quantity"));
            out.add(new JSONObject().put("sequence_no", InspUtil.nzObj(r.opt("sequence_no"))).put("characteristic_no", String.valueOf(i))
                .put("characteristic", InspUtil.j(r, "parameter_name")).put("specification", InspUtil.j(r, "specification_text"))
                .put("lower_spec", InspUtil.nzObj(r.opt("minimum_spec"))).put("upper_spec", InspUtil.nzObj(r.opt("maximum_spec"))).put("unit", InspUtil.j(r, "unit"))
                .put("characteristic_type", ct.equals("TEXT") || ct.equals("ATTRIBUTE") ? "TEXT" : "NUMBER")
                .put("checking_method", InspUtil.j(r, "checking_method")).put("checking_aid_text", InspUtil.j(r, "checking_method"))
                .put("sample_size", ss == null || ss == 0 ? 1 : (int) Math.round(ss))
                .put("is_mandatory", r.isNull("is_mandatory") || r.optBoolean("is_mandatory", true)).put("allow_na", r.optBoolean("allow_na", false))
                .put("status", InspUtil.j(r, "status").isEmpty() ? "ACTIVE" : InspUtil.j(r, "status")));
        }
        return new Object[]{group, out};
    }

    private void loadOspParameters() {
        if (!"OSP_PROCESS".equals(form.str("inward_type")) || form.str("process_id").isEmpty() || form.str("part_id").isEmpty()) {
            a.toast("Select Part, Inward Type 'OSP Process' and the outsourced Process first.");
            return;
        }
        if (!grid.rows().isEmpty()) { a.toast("Parameters load only into an empty layout grid."); return; }
        String part = form.str("part_id"), proc = form.str("process_id"), lt = type();
        Api.async(() -> ospParameters(api, part, proc, lt), (res, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            if (res[0] == null) { a.toast("No active Part Master OSP Process group and parameters match this Part and Process."); return; }
            @SuppressWarnings("unchecked") List<JSONObject> rows = (List<JSONObject>) res[1];
            grid.setRows(editorRows(rows));
            for (JSONObject r : grid.rows()) r.remove("_meta");
            grid.template(nextTemplate());
            a.toast(rows.size() + " " + Ui.pretty(lt) + " parameter(s) loaded from Part Master OSP group: " + InspUtil.j((JSONObject) res[0], "process_specification"));
        });
    }

    // ------------------------------------------------------------------ save (InspectionService.save_plan)
    private void save(Button button) {
        String problem = form.validate();
        if (problem != null) { a.toast(problem); return; }
        button.setEnabled(false);
        button.setText("Saving…");
        Api.async(this::saveNow, (saved, err) -> {
            button.setEnabled(true);
            button.setText("Save Inspection Layout");
            if (err != null) { a.toast(Api.message(err)); return; }
            a.toast("Inspection layout saved successfully.");
            Module m = Catalog.get("inspection_layouts");
            a.replaceTop(new RecordScreen(a, m == null ? Catalog.adhoc("inspection_plans") : m, InspUtil.j(saved, "id")));
        });
    }

    /** Another current layout in the same Part / Stage / Process / Type / Inward / requirement scope (+ method for METLAB). */
    static JSONObject scopePlan(Api api, JSONObject payload, String excludeId, String method) throws Exception {
        String partId = InspUtil.j(payload, "part_id");
        if (partId.isEmpty()) return null;
        List<JSONObject> rows = InspUtil.list(api.rows("inspection_plans?select=*&part_id=eq." + Api.enc(partId) + "&order=updated_at.desc&limit=3000"));
        String[] wanted = scopeOf(payload);
        List<JSONObject> matches = new ArrayList<>();
        for (JSONObject r : rows) {
            if (excludeId != null && InspUtil.j(r, "id").equals(excludeId)) continue;
            String st = InspUtil.j(r, "status").isEmpty() ? "DRAFT" : InspUtil.j(r, "status").toUpperCase(Locale.ROOT);
            if (!Arrays.asList("DRAFT", "APPROVAL_PENDING", "APPROVED").contains(st)) continue;
            if (Arrays.equals(scopeOf(r), wanted)) matches.add(r);
        }
        if (matches.isEmpty()) return null;
        if ("METLAB".equals(wanted[2]) && method != null) {
            Map<String, String> methods = InspUtil.planMethods(api, matches);
            for (JSONObject r : matches) if (method.equals(methods.get(InspUtil.j(r, "id")))) return r;
            return null;
        }
        return matches.get(0);
    }

    private static String[] scopeOf(JSONObject r) {
        return new String[]{InspUtil.j(r, "process_id"), InspUtil.j(r, "inspection_stage_id"),
            (InspUtil.j(r, "layout_type").isEmpty() ? "DIMENSIONAL" : InspUtil.j(r, "layout_type")).toUpperCase(Locale.ROOT),
            (InspUtil.j(r, "inward_type").isEmpty() ? "MATERIAL_INWARD" : InspUtil.j(r, "inward_type")).toUpperCase(Locale.ROOT),
            (InspUtil.j(r, "requirement_scope").isEmpty() ? "GENERAL" : InspUtil.j(r, "requirement_scope")).toUpperCase(Locale.ROOT)};
    }

    private JSONObject saveNow() throws Exception {
        String layoutName = form.str("layout_name"), stageId = form.str("inspection_stage_id"), inwardType = form.str("inward_type");
        String processId = form.str("process_id"), partId = form.str("part_id"), layoutType = type(), method = method();
        if (layoutName.isEmpty()) throw new Api.ApiException(422, "Layout Name is required. Plan Number is generated automatically.");
        if (stageId.isEmpty()) throw new Api.ApiException(422, "Inspection Stage is required so QCMS can enforce one layout per Part / Stage / Process scope.");
        JSONObject process = processId.isEmpty() ? null : InspUtil.get(api, "processes", processId);
        if ("OSP_PROCESS".equals(inwardType) && processId.isEmpty()) throw new Api.ApiException(422, "Select the outsourced Process for an OSP Process layout.");
        if ("OSP_PROCESS".equals(inwardType) && !"OUTSOURCED".equals(InspUtil.j(process, "process_type"))) throw new Api.ApiException(422, "OSP Process layouts can use only an OUTSOURCED Process Master.");
        JSONObject ospGroup = null;
        if ("OSP_PROCESS".equals(inwardType)) {
            if (!InspUtil.j(existing, "source_process_specification_id").isEmpty()) ospGroup = InspUtil.get(api, "part_process_specifications", InspUtil.j(existing, "source_process_specification_id"));
            if (ospGroup == null) ospGroup = (JSONObject) ospParameters(api, partId, processId, layoutType)[0];
        }
        JSONObject part = InspUtil.get(api, "parts", partId);
        JSONObject stage = InspUtil.get(api, "inspection_stages", stageId);
        Double ds = form.num("default_sample_size");
        int defaultSample = ds == null ? 1 : (int) Math.round(ds);
        String title = form.str("report_title");
        if ("METLAB".equals(layoutType) && InspUtil.BEND_TEST.equals(method) && (title.isEmpty() || title.equalsIgnoreCase("METLAB REPORT"))) title = "BEND TEST REPORT";
        JSONObject payload = new JSONObject();
        payload.put("part_id", partId);
        payload.put("process_id", InspUtil.nz(processId));
        payload.put("inspection_stage_id", InspUtil.nz(stageId));
        payload.put("inward_type", inwardType);
        payload.put("revision", form.str("revision").isEmpty() ? "00" : form.str("revision"));
        payload.put("effective_date", form.str("effective_date"));
        payload.put("sample_plan", defaultSample + " samples");
        payload.put("status", form.str("status"));
        payload.put("layout_type", layoutType);
        payload.put("layout_name", layoutName);
        payload.put("report_title", InspUtil.nz(title));
        payload.put("format_number", InspUtil.nz(form.str("format_number")));
        payload.put("format_revision", InspUtil.nz(form.str("format_revision")));
        payload.put("default_sample_size", defaultSample);
        String tmpl = InspUtil.j(existing, "source_template_name");
        payload.put("source_template_name", !tmpl.isEmpty() ? tmpl : ospGroup != null ? "PART_MASTER_OSP_PROCESS_GROUP" : JSONObject.NULL);
        payload.put("source_process_specification_id", ospGroup != null ? InspUtil.j(ospGroup, "id") : InspUtil.nz(InspUtil.j(existing, "source_process_specification_id")));
        // rows (inspection_layouts.render_entry checks)
        List<JSONObject> rows = new ArrayList<>();
        for (JSONObject r : grid.rows()) {
            String parameter = InspUtil.j(r, "characteristic").trim();
            if (parameter.isEmpty()) continue;
            String ctype = InspUtil.j(r, "characteristic_type").isEmpty() ? "NUMBER" : InspUtil.j(r, "characteristic_type").toUpperCase(Locale.ROOT);
            String spec = InspUtil.j(r, "specification").trim();
            Object lower = InspUtil.numOrNull(r.opt("lower_spec")), upper = InspUtil.numOrNull(r.opt("upper_spec"));
            if (ctype.equals("TEXT")) {
                if (spec.isEmpty()) throw new Api.ApiException(422, "Text Specification is mandatory for " + parameter + ".");
                lower = JSONObject.NULL; upper = JSONObject.NULL;
            } else if (lower == JSONObject.NULL && upper == JSONObject.NULL && !("METLAB".equals(layoutType) && InspUtil.BEND_TEST.equals(method) && !spec.isEmpty())) {
                throw new Api.ApiException(422, "Minimum or Maximum Specification is mandatory for numeric parameter " + parameter + ".");
            }
            boolean traverse = "METLAB".equals(layoutType) && r.optBoolean("case_depth_traverse", false);
            String location = "METLAB".equals(layoutType) ? InspUtil.j(r, "case_depth_location").trim() : "";
            if (traverse && location.isEmpty()) throw new Api.ApiException(422, "Traverse Location is required when Case Depth Traverse is ticked for " + parameter + ".");
            JSONObject meta = r.optJSONObject("_meta") == null ? new JSONObject() : InspUtil.copy(r.optJSONObject("_meta"));
            meta.put("inspection_method", method);
            meta.put("case_depth_traverse", traverse);
            if (!location.isEmpty()) meta.put("case_depth_location", location); else meta.remove("case_depth_location");
            Double seq = Rules.number(r.opt("sequence_no"));
            Double ss = Rules.number(r.opt("sample_size"));
            JSONObject row = new JSONObject();
            row.put("_id", InspUtil.j(r, "id"));
            row.put("sequence_no", seq == null || seq == 0 ? rows.size() + 1 : (int) Math.round(seq));
            row.put("characteristic_no", InspUtil.nz(InspUtil.j(r, "characteristic_no")));
            row.put("characteristic", parameter);
            row.put("specification", InspUtil.nz(spec));
            row.put("lower_spec", lower);
            row.put("upper_spec", upper);
            row.put("unit", InspUtil.nz(InspUtil.j(r, "unit")));
            row.put("characteristic_type", ctype);
            row.put("checking_aid_text", InspUtil.nz(InspUtil.j(r, "checking_aid_text")));
            row.put("sample_size", ss == null || ss == 0 ? defaultSample : (int) Math.round(ss));
            row.put("allow_na", r.optBoolean("allow_na", false));
            row.put("is_mandatory", r.optBoolean("is_mandatory", true));
            row.put("layout_metadata", meta);
            row.put("status", (InspUtil.j(r, "status").isEmpty() ? "ACTIVE" : InspUtil.j(r, "status")).toUpperCase(Locale.ROOT));
            rows.add(row);
        }
        // service.save_plan
        String planNumber = autoPlanNumber(part, process, stage, layoutName);
        boolean isBend = "METLAB".equals(layoutType) && InspUtil.methodFromRows(rows, layoutName + " " + title).equals(InspUtil.BEND_TEST);
        if (isBend && !planNumber.toUpperCase(Locale.ROOT).contains("BEND")) planNumber = planNumber + "-BEND";
        payload.put("plan_number", planNumber);
        payload.put("inspection_method", isBend ? InspUtil.BEND_TEST : "GENERAL");
        String existingId = existing == null ? null : InspUtil.j(existing, "id");
        if (Arrays.asList("DRAFT", "APPROVAL_PENDING", "APPROVED").contains(form.str("status"))) {
            String m = "METLAB".equals(layoutType) ? InspUtil.methodFromRows(rows, layoutName + " " + title) : null;
            JSONObject dup = scopePlan(api, payload, existingId, m);
            if (dup != null) {
                String label = !InspUtil.j(dup, "plan_number").isEmpty() ? InspUtil.j(dup, "plan_number") : !InspUtil.j(dup, "layout_name").isEmpty() ? InspUtil.j(dup, "layout_name") : InspUtil.j(dup, "id");
                throw new Api.ApiException(409, "Only one current inspection layout is allowed for the same Part + Inspection Stage + Process + Layout Type. Edit or supersede existing layout " + label + " instead of creating another one.");
            }
        }
        JSONObject plan;
        try {
            plan = api.save("inspection_plans", existingId, payload);
        } catch (Api.ApiException ex) {
            if (isBend && String.valueOf(ex.getMessage()).contains("uq_qcms_inspection_plan_current_scope")) {
                throw new Api.ApiException(409, "The database still uses the old one-layout rule, so the Bend Test layout cannot sit beside the MetLAB layout yet. Ask the administrator to run the R15 SQL (qcms_r15_bend_layout_scope) once in Supabase, then save again.");
            }
            throw ex;
        }
        String pid = InspUtil.j(plan, "id");
        Map<Integer, String> bySeq = new HashMap<>();
        for (JSONObject r : InspUtil.list(api.rows("inspection_plan_characteristics?select=id,sequence_no&inspection_plan_id=eq." + Api.enc(pid) + "&limit=2000"))) {
            Double s = Rules.number(r.opt("sequence_no"));
            bySeq.put(s == null ? 0 : (int) Math.round(s), InspUtil.j(r, "id"));
        }
        JSONArray prepared = new JSONArray();
        java.util.Set<String> usedIds = new java.util.HashSet<>();
        for (JSONObject r : rows) {
            int seq = r.getInt("sequence_no");
            String rid = bySeq.containsKey(seq) ? bySeq.get(seq) : InspUtil.j(r, "_id");
            JSONObject o = new JSONObject();
            if (!rid.isEmpty()) { o.put("id", rid); usedIds.add(rid); }
            o.put("inspection_plan_id", pid);
            o.put("sequence_no", seq);
            for (String k : new String[]{"characteristic_no", "characteristic", "specification", "lower_spec", "upper_spec", "unit", "characteristic_type", "checking_aid_text", "sample_size", "allow_na", "is_mandatory", "layout_metadata", "status"}) o.put(k, r.opt(k));
            o.put("special_class", JSONObject.NULL);
            o.put("checking_method", JSONObject.NULL);
            o.put("frequency", JSONObject.NULL);
            o.put("reaction_plan", JSONObject.NULL);
            o.put("report_section", layoutType);
            o.put("decimal_places", 3);
            o.put("source_row", JSONObject.NULL);
            prepared.put(o);
        }
        try {
            api.upsert("inspection_plan_characteristics", prepared, "id");
            for (JSONObject removed : grid.removedRows()) {
                String rid = InspUtil.j(removed, "id");
                if (!rid.isEmpty() && !usedIds.contains(rid)) api.update("inspection_plan_characteristics", rid, new JSONObject().put("status", "INACTIVE"));
            }
        } catch (Exception ex) {
            throw new Api.ApiException(500, "Layout header " + planNumber + " was saved, but its characteristics were not: " + Api.message(ex) + " Open the layout and save again.");
        }
        Lookups.invalidate();
        return plan;
    }

    /** Status change actions (DRAFT → APPROVAL_PENDING → APPROVED / SUPERSEDED) with the one-current-layout check. */
    static void setStatus(MainActivity a, JSONObject row, String target, Runnable refresh) {
        Api api = Api.get(a);
        a.confirm(Ui.pretty(target) + "?", "Layout " + InspUtil.j(row, "plan_number") + " will be set to " + Ui.pretty(target) + ".", "Continue", () -> Api.async(() -> {
            if (Arrays.asList("DRAFT", "APPROVAL_PENDING", "APPROVED").contains(target)) {
                JSONObject p = InspUtil.copy(row);
                String m = null;
                if ("METLAB".equalsIgnoreCase(InspUtil.j(row, "layout_type"))) m = InspUtil.planMethod(api, row);
                if (!"FINAL_METALLURGICAL".equalsIgnoreCase(InspUtil.j(row, "requirement_scope"))) {
                    JSONObject dup = scopePlan(api, p, InspUtil.j(row, "id"), m);
                    if (dup != null) throw new Api.ApiException(409, "Only one current inspection layout is allowed for the same Part + Inspection Stage + Process + Layout Type. Supersede existing layout " + InspUtil.j(dup, "plan_number") + " first.");
                }
            }
            api.update("inspection_plans", InspUtil.j(row, "id"), new JSONObject().put("status", target));
            return true;
        }, (ok, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            a.toast("Layout set to " + Ui.pretty(target) + ".");
            refresh.run();
        }));
    }

    @Override public boolean onBack() {
        a.confirm("Leave without saving?", "Changes on this layout are not saved.", "Leave", () -> a.back());
        return true;
    }
}
