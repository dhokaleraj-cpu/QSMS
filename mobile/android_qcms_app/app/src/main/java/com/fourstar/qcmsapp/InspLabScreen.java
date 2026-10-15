package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.text.InputType;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Native MetLAB / Bend Test report entry (app_pages/metlab_report.py + osp_inspections.py): linked raw-material
 * inward, standalone stage report or OSP sample / receipt. Writes lab_tests with the results JSON exactly like
 * InspectionService.save_metlab (raw-material cleaning included), learned reference values, report copy and the
 * four MICROSTRUCTURE photo slots.
 */
final class InspLabScreen extends Screen {
    static final int LINKED = 0, STANDALONE = 1, OSP = 2;
    static final double[] DEFAULT_DISTANCES = {0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00};
    static final String[][] BEND_FIELDS = {
        {"baking_batch_no", "Baking Batch No."}, {"batch_quantity_pcs", "Batch Quantity (Pcs)"}, {"part_diameter", "Part Diameter"},
        {"ht_batch_no", "HT Batch No."}, {"fsi_batch_no", "FSI Batch No."}, {"steel_heat_code", "Steel Heat Code"},
        {"customer_name", "Customer Name (print)"}, {"material_used", "Material Used (print)"},
        {"baking_temp_spec", "Baking Temp. · Specification"}, {"baking_time_spec", "Baking Time · Specification"},
        {"hardness_spec", "Base Metal Hardness · Specification"}, {"baking_temp_actual", "Baking Temp. · Actual"},
        {"baking_time_actual", "Baking Time · Actual"}, {"hardness_actual", "Base Metal Hardness · Actual"},
        {"load_kn", "Load Vs CHT (kN at peak)"}, {"cht_mm", "CHT (mm)"}};

    private final String id;
    private final JSONObject prefill;
    private final boolean bendMode;
    private JSONObject existing;
    private int mode = -1;
    private boolean loaded = false;

    private String inwardId = "", partId = "", scope = "RAW_MATERIAL_STAGE", groupId = "", manualPlanId = "";
    private JSONObject inward, part, plan, job, group, process, stage, rmtc, grade, supplier, steelMill, sourceSupplier;
    private List<JSONObject> planOptions = new ArrayList<>();
    private boolean planSelectable = false;
    private List<JSONObject> groups = new ArrayList<>();
    private List<JSONObject> chars = new ArrayList<>();
    private List<String> supplierIds = new ArrayList<>();
    private String method = InspUtil.GENERAL_METLAB;
    private String contextProblem = "";

    private FormView form, bendForm, captionForm;
    private final List<String> formKeys = new ArrayList<>();
    private Map<String, String> formCache;
    private List<JSONObject> rowsCache;
    private InspReadings readings;
    private final Attachments.FileData[] photos = new Attachments.FileData[5];   // 0 = report copy, 1..4 photos
    private final TextView[] photoLabels = new TextView[5];
    // case depth traverse
    private List<JSONObject> locations = new ArrayList<>();
    private List<JSONObject> traverse;
    private SheetView traverseSheet;

    InspLabScreen(MainActivity a, String id, JSONObject prefill, boolean bendMode) {
        super(a);
        this.id = id; this.prefill = prefill; this.bendMode = bendMode;
    }

    static InspLabScreen forOsp(MainActivity a, String reportId, JSONObject job, String scope) {
        JSONObject p = new JSONObject();
        try { p.put("_osp_job", job); p.put("_scope", scope); } catch (Exception ignored) { }
        return new InspLabScreen(a, reportId, p, false);
    }

    private String kind() { return bendMode || InspUtil.BEND_TEST.equals(method) ? "Bend Test" : "MetLAB"; }

    @Override public String title() {
        if (existing != null) return "Edit · " + InspUtil.j(existing, "report_number");
        return mode == OSP ? "OSP MetLAB Inspection" : bendMode ? "New · Bend Test Report" : "New · MetLAB Report";
    }
    @Override public String subtitle() {
        if (mode == OSP) return "OSP_SAMPLE".equals(scope) ? "Pre-inward Sample" : "Post-receipt Full Batch";
        if (mode == STANDALONE) return "Standalone Stage Report · " + InspUtil.scopeLabel(scope);
        if (mode == LINKED) return "QCMS Linked Flow · Raw Material Inward";
        return bendMode ? "Controlled Bend Test · linked or standalone stage" : "Linked or standalone Raw Material / OSP / Final Dispatch stage";
    }
    @Override public int tab() { return Catalog.QUALITY; }

    @Override
    public View build() {
        newPage();
        if (loaded) { snapshot(); render(); return scroll; }
        page.addView(loading());
        Api.async(() -> {
            if (id != null) {
                existing = InspUtil.get(api, "lab_tests", id);
                if (existing == null) throw new Api.ApiException(404, "MetLAB report not found or not visible for your role.");
            }
            JSONObject ospJob = prefill == null ? null : prefill.optJSONObject("_osp_job");
            if (existing != null) {
                partId = InspUtil.j(existing, "part_id");
                if (!InspUtil.j(existing, "osp_job_id").isEmpty()) {
                    mode = OSP;
                    scope = InspUtil.j(existing, "inspection_scope");
                    JSONArray jr = api.rows("v_qsms_osp_register?select=*&id=eq." + Api.enc(InspUtil.j(existing, "osp_job_id")));
                    job = jr.length() > 0 ? jr.getJSONObject(0) : null;
                } else if (InspUtil.isStandaloneScope(InspUtil.j(existing, "inspection_scope"))) {
                    mode = STANDALONE;
                    scope = InspUtil.j(existing, "inspection_scope");
                } else {
                    mode = LINKED;
                    inwardId = InspUtil.j(existing, "inward_lot_id");
                }
            } else if (ospJob != null) {
                mode = OSP;
                job = ospJob;
                scope = prefill.optString("_scope", "OSP_SAMPLE");
                partId = InspUtil.j(job, "part_id");
            } else if (prefill != null && !InspUtil.j(prefill, "inward_lot_id").isEmpty()) {
                mode = LINKED;
                inwardId = InspUtil.j(prefill, "inward_lot_id");
            }
            if (mode >= 0) loadContextNow();
            return true;
        }, (ok, err) -> {
            loaded = true;
            if (err != null) { page.removeAllViews(); page.addView(error(err, () -> { loaded = false; a.rebuild(); })); return; }
            render();
        });
        return scroll;
    }

    // ------------------------------------------------------------------ context
    private static JSONObject byId(List<JSONObject> l, String id) {
        for (JSONObject r : l) if (InspUtil.j(r, "id").equals(id)) return r;
        return null;
    }

    private void loadContextNow() throws Exception {
        contextProblem = "";
        plan = null; chars = new ArrayList<>(); planOptions = new ArrayList<>(); planSelectable = false;
        group = null; process = null; stage = null; method = InspUtil.GENERAL_METLAB;
        String required = bendMode ? InspUtil.BEND_TEST : null;
        String saved = InspUtil.j(existing, "layout_plan_id");
        if (mode == LINKED) {
            if (inwardId.isEmpty()) return;
            inward = InspUtil.get(api, "inward_lots", inwardId);
            if (inward == null) { contextProblem = "The Material Inward could not be loaded."; return; }
            partId = InspUtil.j(inward, "part_id");
            part = InspUtil.get(api, "parts", partId);
            rmtc = InspUtil.get(api, "rmtc_approvals", InspUtil.j(inward, "rmtc_approval_id"));
            grade = InspUtil.get(api, "material_grades", InspUtil.j(part, "material_grade_id"));
            supplier = InspUtil.get(api, "parties", InspUtil.j(inward, "supplier_id"));
            steelMill = InspUtil.get(api, "parties", InspUtil.j(rmtc, "steel_mill_id"));
            planOptions = InspUtil.filterByMethod(api, InspUtil.rawMetlabPlans(api, partId), required, partId);
            if (!saved.isEmpty() && byId(planOptions, saved) == null) {
                JSONObject hist = InspUtil.get(api, "inspection_plans", saved);
                if (hist != null && InspUtil.j(hist, "part_id").equals(partId) && InspUtil.isRawPlan(hist)) planOptions.add(0, hist);
            }
            if (planOptions.isEmpty()) {
                contextProblem = bendMode ? "No APPROVED Bend Test layout is available in Layout Master for this Part. Create / approve it in Inspection Layouts first."
                    : "No approved Raw Material Inward MetLAB layout is available in Layout Master for this Part. Create and approve a MetLAB layout before entering the Raw Material Inward report.";
                return;
            }
            if (existing != null && byId(planOptions, saved) != null) plan = byId(planOptions, saved);
            else { plan = !manualPlanId.isEmpty() && byId(planOptions, manualPlanId) != null ? byId(planOptions, manualPlanId) : planOptions.get(0); planSelectable = existing == null || byId(planOptions, saved) == null; }
        } else if (mode == STANDALONE) {
            if (partId.isEmpty()) return;
            part = InspUtil.get(api, "parts", partId);
            grade = InspUtil.get(api, "material_grades", InspUtil.j(part, "material_grade_id"));
            String processId = null;
            if ("OSP_STAGE".equals(scope)) {
                groups = InspUtil.ospProcessGroups(api, partId, "METLAB");
                if (groups.isEmpty()) { contextProblem = "No active OSP MetLAB Process requirements are configured in Part Master for this Part Number."; return; }
                String ep = InspUtil.j(existing, "process_id");
                if (groupId.isEmpty() || byId(groups, groupId) == null) {
                    groupId = InspUtil.j(groups.get(0), "id");
                    for (JSONObject g : groups) if (InspUtil.j(g, "process_id").equals(ep)) groupId = InspUtil.j(g, "id");
                }
                group = byId(groups, groupId);
                processId = InspUtil.j(group, "process_id").isEmpty() ? null : InspUtil.j(group, "process_id");
            }
            JSONObject p = saved.isEmpty() ? null : InspUtil.get(api, "inspection_plans", saved);
            if (p != null && !InspUtil.j(p, "part_id").equals(partId)) p = null;
            if (p != null && "RAW_MATERIAL_STAGE".equals(scope) && !InspUtil.isRawPlan(p)) p = null;
            if (p != null && bendMode && !InspUtil.BEND_TEST.equals(InspUtil.planMethod(api, p))) {
                contextProblem = "The selected saved report is not a Bend Test report. Open it from MetLAB Reports instead.";
                return;
            }
            if (p == null && "RAW_MATERIAL_STAGE".equals(scope)) {
                planOptions = InspUtil.filterByMethod(api, InspUtil.rawMetlabPlans(api, partId), required, partId);
                if (!planOptions.isEmpty()) {
                    p = !manualPlanId.isEmpty() && byId(planOptions, manualPlanId) != null ? byId(planOptions, manualPlanId) : planOptions.get(0);
                    planSelectable = true;
                }
            } else if (p == null) {
                planOptions = InspUtil.filterByMethod(api, InspUtil.standalonePlans(api, "METLAB", partId, scope, processId), required, partId);
                if (!planOptions.isEmpty()) {
                    p = !manualPlanId.isEmpty() && byId(planOptions, manualPlanId) != null ? byId(planOptions, manualPlanId) : planOptions.get(0);
                    planSelectable = bendMode && planOptions.size() > 1;
                }
            }
            if (p == null) {
                if (bendMode) contextProblem = "No APPROVED Bend Test layout is available for this Part and selected report stage. Create / approve it in Inspection Layouts, then return here.";
                else if ("OSP_STAGE".equals(scope)) contextProblem = "The Part Master OSP MetLAB requirements exist, but the controlled OSP MetLAB layout has not been generated / approved.";
                else if ("FINAL_DISPATCH_STAGE".equals(scope)) contextProblem = "No approved Final Metallurgical layout is available for this Part. Generate it from Part Master → Final Dispatch Metallurgical Requirements.";
                else contextProblem = "No approved Raw Material Inward MetLAB layout is configured in Layout Master for this Part Number.";
                return;
            }
            plan = p;
            if (processId == null && !InspUtil.j(plan, "process_id").isEmpty()) processId = InspUtil.j(plan, "process_id");
            process = processId == null ? null : InspUtil.get(api, "processes", processId);
            List<String> ids = InspUtil.partSupplierIds(api, partId);
            supplierIds = new ArrayList<>();
            if (!ids.isEmpty()) {
                Set<String> set = new HashSet<>(ids);
                for (JSONObject r : InspUtil.byId(api, "parties", "id,party_types,status", set).values()) {
                    JSONArray types = r.optJSONArray("party_types");
                    if (types != null && types.toString().contains("\"SUPPLIER\"") && "ACTIVE".equals(InspUtil.j(r, "status"))) supplierIds.add(InspUtil.j(r, "id"));
                }
            }
        } else if (mode == OSP) {
            if (job == null) { contextProblem = "The OSP job could not be loaded."; return; }
            partId = InspUtil.j(job, "part_id");
            part = InspUtil.get(api, "parts", partId);
            planOptions = InspUtil.plans(api, "METLAB", partId, true, InspUtil.j(job, "process_id"), null, "OSP_PROCESS");
            if (planOptions.isEmpty()) { contextProblem = "No Approved OSP MetLAB layout matches Part " + InspUtil.j(job, "part_number") + " and Process " + InspUtil.j(job, "process_name") + "."; return; }
            String want = !saved.isEmpty() ? saved : manualPlanId;
            plan = !want.isEmpty() && byId(planOptions, want) != null ? byId(planOptions, want) : planOptions.get(0);
            planSelectable = existing == null && planOptions.size() > 1;
            JSONObject src = InspUtil.get(api, "inward_lots", InspUtil.j(job, "source_inward_lot_id"));
            JSONObject open = InspUtil.get(api, "supply_opening_stock", InspUtil.j(job, "opening_stock_id"));
            String sup = InspUtil.j(src, "supplier_id").isEmpty() ? InspUtil.j(open, "supplier_id") : InspUtil.j(src, "supplier_id");
            sourceSupplier = sup.isEmpty() ? null : new JSONObject().put("id", sup);
        }
        if (plan != null) {
            chars = InspUtil.planChars(api, InspUtil.j(plan, "id"));
            method = mode == OSP ? InspUtil.GENERAL_METLAB : InspUtil.methodFromRows(chars, InspUtil.planText(plan));
            if (process == null && !InspUtil.j(plan, "process_id").isEmpty()) process = InspUtil.get(api, "processes", InspUtil.j(plan, "process_id"));
            stage = InspUtil.get(api, "inspection_stages", InspUtil.j(plan, "inspection_stage_id"));
        }
    }

    private void reloadContext() {
        page.removeAllViews();
        page.addView(loading());
        Api.async(() -> { loadContextNow(); return true; }, (ok, err) -> {
            if (err != null) { page.removeAllViews(); page.addView(error(err, this::reloadContext)); return; }
            formCache = null; rowsCache = null; traverse = null;
            for (int i = 0; i < photos.length; i++) photos[i] = null;
            render();
        });
    }

    private boolean writable() {
        if (existing == null) return true;
        String st = InspUtil.j(existing, "status").isEmpty() ? "DRAFT" : InspUtil.j(existing, "status").toUpperCase(Locale.ROOT);
        return mode == OSP ? !st.equals("FINAL") : st.equals("DRAFT");
    }

    private JSONObject results() {
        JSONObject r = existing == null ? null : existing.optJSONObject("results");
        return r == null ? new JSONObject() : r;
    }

    // ------------------------------------------------------------------ UI
    private View selector(String label, String value, Runnable onClick) {
        LinearLayout box = Ui.vbox(a);
        box.addView(Ui.label(a, label));
        TextView t = Ui.text(a, value == null || value.isEmpty() ? "Select…" : value, 14, value == null || value.isEmpty() ? Ui.MUTED : Ui.TEXT, false);
        t.setPadding(dp(12), dp(12), dp(12), dp(12));
        t.setBackground(Ui.round(onClick == null ? android.graphics.Color.parseColor("#F3F7F7") : android.graphics.Color.WHITE, Ui.LINE_STRONG, 1, 10, a));
        if (onClick != null) t.setOnClickListener(v -> onClick.run());
        box.addView(t, Ui.matchWrap(a, 0));
        return box;
    }

    private void snapshot() {
        formCache = new HashMap<>();
        for (String k : formKeys) {
            String[] parts = k.split(":", 2);
            FormView f = "b".equals(parts[0]) ? bendForm : "c".equals(parts[0]) ? captionForm : form;
            if (f != null) formCache.put(k, f.str(parts[1]));
        }
        if (readings != null) rowsCache = new ArrayList<>(readings.rows());
    }

    private void render() {
        page.removeAllViews();
        a.rebuildTitle(this);
        formKeys.clear();
        if (mode < 0) { renderModeChoice(); return; }
        if (existing != null) {
            String st = InspUtil.j(existing, "status");
            TextView note = Ui.chip(a, writable() ? "Editing " + InspUtil.j(existing, "report_number") + " · " + Ui.pretty(st.isEmpty() ? "DRAFT" : st)
                : "Report is " + Ui.pretty(st) + " · read only. Use 'Controlled amendment' on the record to reopen it for editing.", writable() ? "teal" : "amber");
            note.setSingleLine(false);
            add(note, 2);
        }
        renderContext();
        if (!contextProblem.isEmpty()) {
            LinearLayout card = Ui.card(a);
            card.addView(Ui.text(a, contextProblem, 13, Ui.AMBER_FG, false));
            add(card, 10);
            return;
        }
        if (plan == null) return;
        if (InspUtil.BEND_TEST.equals(method)) add(Ui.chip(a, "Bend Test inspection method selected from the controlled layout.", "green"), 8);
        renderInfo();
        renderForm();
        if (mode != OSP && InspUtil.BEND_TEST.equals(method)) renderBend();
        renderPhotos();
        add(Ui.label(a, mode == OSP ? "C · Process-specific inspection parameters" : "Layout Master inspection requirements"), 14);
        readings = new InspReadings(a, mode == OSP ? "OSP MetLAB parameters" : "MetLAB characteristics", "Method / Aid");
        readings.setEditable(writable());
        readings.setRows(rowsCache != null ? rowsCache : buildRows(), 1);
        add(readings, 4);
        if (mode != OSP) renderCaseDepth();
        renderTail();
        if (formCache != null) {
            for (Map.Entry<String, String> en : formCache.entrySet()) {
                String[] parts = en.getKey().split(":", 2);
                FormView f = "b".equals(parts[0]) ? bendForm : "c".equals(parts[0]) ? captionForm : form;
                if (f != null) f.set(parts[1], en.getValue().isEmpty() ? null : en.getValue());
            }
        }
    }

    private void renderModeChoice() {
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, "Report Linkage", 15, Ui.TEXT, true));
        card.addView(Ui.text(a, "Standalone Stage Report does not require RMTC, Material Inward or Production linkage. OSP sample / receipt reports are opened from OSP Register.", 12, Ui.MUTED, false));
        Button linked = Ui.primary(a, "QCMS Linked Flow · Raw Material Inward");
        linked.setOnClickListener(v -> { mode = LINKED; render(); });
        card.addView(linked, Ui.matchWrap(a, 10));
        Button standalone = Ui.outline(a, "Standalone Stage Report", Ui.TEAL);
        standalone.setOnClickListener(v -> { mode = STANDALONE; render(); });
        card.addView(standalone, Ui.matchWrap(a, 8));
        add(card, 4);
    }

    private void renderContext() {
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, mode == OSP ? "A · OSP batch & approved OSP layout" : mode == STANDALONE ? "A · Standalone " + kind() + " context" : "A · Raw Material Inward & layout", 14, Ui.TEXT, true));
        boolean fresh = existing == null;
        if (fresh && mode != OSP) {
            TextView change = Ui.text(a, "Change report linkage", 12, Ui.TEAL_DARK, true);
            change.setPadding(0, dp(6), 0, dp(2));
            change.setOnClickListener(v -> { mode = -1; inwardId = ""; partId = ""; plan = null; contextProblem = ""; render(); });
            card.addView(change);
        }
        if (mode == LINKED) {
            String label = inward == null ? "" : InspUtil.j(inward, "inward_number") + " · " + InspUtil.j(part, "part_number") + " · Heat " + InspUtil.j(inward, "heat_number");
            card.addView(selector("Material Inward / Part / Supplier / Quantity", label, fresh ? this::pickInward : null), Ui.matchWrap(a, 8));
        } else if (mode == STANDALONE) {
            card.addView(selector("Report Stage", InspUtil.scopeLabel(scope), fresh ? this::pickScope : null), Ui.matchWrap(a, 8));
            card.addView(selector("Part Number", part == null ? "" : Lookups.PART.of(part), fresh ? this::pickPart : null), Ui.matchWrap(a, 8));
            if ("OSP_STAGE".equals(scope) && group != null) card.addView(selector("OSP Process", groupLabel(group), fresh && groups.size() > 1 ? this::pickGroup : null), Ui.matchWrap(a, 8));
        } else if (mode == OSP && job != null) {
            card.addView(Ui.pair(a, "OSP Job", InspUtil.j(job, "osp_job_number")));
            card.addView(Ui.pair(a, "Inspection Stage", "OSP_SAMPLE".equals(scope) ? "Pre-inward Sample" : "Post-receipt Full Batch"));
        }
        if (plan != null) {
            String title = mode == OSP ? "Approved OSP Layout" : mode == LINKED || "RAW_MATERIAL_STAGE".equals(scope) ? "Raw Material Inward MetLAB Layout · Layout Master" : bendMode ? "Bend Test Layout" : "Controlled Layout";
            card.addView(selector(title, InspUtil.planLabel(plan), fresh && planSelectable && planOptions.size() > 1 ? this::pickPlan : null), Ui.matchWrap(a, 8));
            if (!"APPROVED".equals(InspUtil.j(plan, "status"))) card.addView(Ui.text(a, "This saved report uses a historical MetLAB layout. QCMS loaded the original layout so the report can be edited without silently changing its specification basis.", 12, Ui.AMBER_FG, false));
        }
        add(card, 6);
    }

    private String groupLabel(JSONObject g) {
        JSONObject p = Lookups.rowOf(Lookups.processes(), InspUtil.j(g, "process_id"));
        return p == null ? InspUtil.j(g, "process_specification") : InspUtil.j(p, "process_code") + " · " + InspUtil.j(p, "process_name");
    }

    private void renderInfo() {
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, "Report context", 14, Ui.TEXT, true));
        card.addView(Ui.pair(a, "Part Number", InspUtil.j(part, "part_number")));
        card.addView(Ui.pair(a, "FSI Part Number", InspUtil.j(part, "fsi_part_number")));
        card.addView(Ui.pair(a, "Part Name", InspUtil.j(part, "part_name")));
        card.addView(Ui.pair(a, "Layout Name", InspUtil.j(plan, "layout_name")));
        card.addView(Ui.pair(a, "Process", process == null ? (mode == LINKED ? "Raw Material Inward" : "Not assigned") : InspUtil.j(process, "process_name")));
        card.addView(Ui.pair(a, "Inspection Stage", stage == null ? (mode == LINKED ? "Incoming Inspection" : "Not assigned") : InspUtil.j(stage, "stage_name")));
        if (mode == LINKED && inward != null) {
            card.addView(Ui.pair(a, "Heat Number / Code", InspUtil.j(inward, "heat_number") + " / " + InspUtil.j(inward, "heat_code")));
            card.addView(Ui.pair(a, "Supplier", InspUtil.j(supplier, "party_name")));
            card.addView(Ui.pair(a, "Steel Mill", InspUtil.j(steelMill, "party_name")));
            card.addView(Ui.pair(a, "Material Grade", InspUtil.j(grade, "grade_code")));
            card.addView(Ui.pair(a, "RMTC", InspUtil.j(rmtc, "rmtc_number")));
            double steel = InspUtil.dbl(inward, "steel_quantity_kg") != 0 ? InspUtil.dbl(inward, "steel_quantity_kg") : InspUtil.dbl(inward, "quantity_received");
            card.addView(Ui.pair(a, "Steel Quantity (kg)", Ui.num(steel, 3)));
            card.addView(Ui.pair(a, "Production Quantity (pcs)", Ui.num(InspUtil.dbl(inward, "production_quantity_pcs"), 0)));
            card.addView(Ui.text(a, "RMTC values are traceability references only. Acceptance limits come only from Layout Master.", 11.5f, Ui.MUTED, false));
        }
        if (mode == STANDALONE) {
            card.addView(Ui.pair(a, "Material Grade", InspUtil.j(grade, "grade_code")));
            card.addView(Ui.pair(a, "Drawing / Revision", InspUtil.j(part, "drawing_number") + " / " + InspUtil.j(part, "drawing_revision")));
            if (group != null) card.addView(Ui.pair(a, "Process Specification", InspUtil.j(group, "process_specification")));
        }
        if (mode == OSP && job != null) {
            card.addView(Ui.pair(a, "Heat Number", InspUtil.j(job, "heat_number")));
            card.addView(Ui.pair(a, "FSI Batch Number", InspUtil.j(job, "osp_batch_code")));
            card.addView(Ui.pair(a, "OSP Vendor", InspUtil.j(job, "vendor_name")));
            card.addView(Ui.pair(a, "OSP Process", InspUtil.j(job, "process_name")));
            card.addView(Ui.pair(a, "Vendor Batch", InspUtil.j(job, "vendor_batch_number")));
            card.addView(Ui.pair(a, "Process Specification", InspUtil.j(job, "process_specification")));
        }
        add(card, 8);
    }

    private void renderForm() {
        List<Field> f = new ArrayList<>();
        f.add(Field.text("report_number", "Report Number").hint("Auto on save"));
        if (existing != null) f.get(0).readOnly = true;
        f.add(Field.date("test_date", mode == OSP ? "Inspection Date" : "Test Date").req());
        if (mode == STANDALONE) {
            f.add(Field.lookup("supplier_id", "Supplier", Lookups.parties(null).where(supplierIds.isEmpty() ? "&party_types=cs.%7BSUPPLIER%7D" : "&id=in.(" + String.join(",", supplierIds) + ")")));
            f.add(Field.lookup("osp_vendor_id", "OSP Vendor", Lookups.ospVendors()));
            f.add(Field.text("heat_number", "Heat Number"));
            f.add(Field.text("heat_code", "Heat Code"));
            f.add(Field.text("vendor_batch_number_snapshot", "Supplier / HT / OSP Batch Number"));
            f.add(Field.text("batch_number", "Internal / FSI Batch Number"));
            f.add(Field.text("supplier_reference_number", "Supplier Invoice / Reference"));
            f.add(Field.number("production_quantity_pcs", "Quantity (pcs)").range(0, Double.MAX_VALUE));
            f.add(Field.text("supply_condition", "Supply / Process Condition"));
        }
        if (mode != OSP) {
            f.add(Field.text("sample_reference", mode == STANDALONE ? "Sample / Reference" : "Sample Reference").req());
            f.add(Field.text("specification_reference", "Specification Reference").hint("Type a reference or use 'Saved references' below"));
            f.add(Field.area("reference_documents", "Reference Documents / Statements").hint("One statement per line"));
        }
        if (mode != OSP && InspUtil.BEND_TEST.equals(method)) f.add(Field.number("bend_angle_degrees", "Part Bend Angle (degrees)").range(0, 360));
        f.add(Field.lookup("prepared_by_employee_id", "Prepared By", Lookups.employees()).req());
        f.add(Field.select("disposition", mode == OSP ? "Validation Decision" : "Final Decision", InspUtil.DRAFT_DISPOSITIONS).labels(InspUtil.DISPOSITION_LABELS).req());
        if (mode != OSP) f.add(Field.text("disposition_reason", "Decision Reason").hint("Required for On Hold, Accepted Under Reserve and Rejected decisions."));
        f.add(Field.area("remarks", mode == OSP ? "Report Remarks" : "Conclusion"));
        if (mode != OSP) f.add(Field.area("conclusion_remark", "Conclusion Remark (optional)").hint("Additional controlled remark shown in a separate highlighted row below the conclusion."));
        if (!writable()) for (Field x : f) x.readOnly = true;
        form = new FormView(a, f);
        for (Field x : f) formKeys.add("f:" + x.key);
        JSONObject e = existing;
        JSONObject res = results();
        form.set("report_number", InspUtil.j(e, "report_number"));
        form.set("test_date", e != null && !InspUtil.j(e, "test_date").isEmpty() ? InspUtil.j(e, "test_date").substring(0, 10) : Ui.today());
        String prepared = InspUtil.j(e, "prepared_by_employee_id");
        if (prepared.isEmpty() && e == null) prepared = api.employeeId;
        if (prepared != null && !prepared.isEmpty()) form.set("prepared_by_employee_id", prepared);
        form.set("disposition", InspUtil.j(e, "disposition").isEmpty() ? "PENDING" : InspUtil.j(e, "disposition"));
        form.set("remarks", InspUtil.j(e, "remarks"));
        if (mode != OSP) {
            form.set("disposition_reason", InspUtil.j(e, "disposition_reason"));
            String sref = InspUtil.j(e, "sample_reference");
            if (sref.isEmpty() && mode == LINKED) sref = InspUtil.j(inward, "inward_number");
            form.set("sample_reference", sref);
            String spec = InspUtil.j(e, "specification_reference");
            if (spec.isEmpty()) spec = InspUtil.j(plan, "format_number");
            if (spec.isEmpty()) spec = InspUtil.j(part, "drawing_number");
            form.set("specification_reference", spec);
            StringBuilder refs = new StringBuilder();
            JSONArray rd = res.optJSONArray("reference_documents");
            for (int i = 0; rd != null && i < rd.length(); i++) { String v = rd.optString(i, "").trim(); if (!v.isEmpty()) { if (refs.length() > 0) refs.append('\n'); refs.append(v); } }
            form.set("reference_documents", refs.toString());
            form.set("conclusion_remark", InspUtil.j(res, "conclusion_remark"));
            if (InspUtil.BEND_TEST.equals(method)) form.set("bend_angle_degrees", InspUtil.fmt(res.opt("bend_angle_degrees")));
        }
        if (mode == STANDALONE) {
            for (String k : new String[]{"supplier_id", "osp_vendor_id", "heat_number", "heat_code", "vendor_batch_number_snapshot", "batch_number", "supplier_reference_number"}) if (!InspUtil.j(e, k).isEmpty()) form.set(k, InspUtil.j(e, k));
            form.set("production_quantity_pcs", InspUtil.fmt(e == null ? null : e.opt("production_quantity_pcs")));
            String def = group != null && !InspUtil.j(group, "process_specification").isEmpty() ? InspUtil.j(group, "process_specification")
                : process != null && !InspUtil.j(process, "process_name").isEmpty() ? InspUtil.j(process, "process_name") : InspUtil.scopeLabel(scope);
            form.set("supply_condition", e != null && !InspUtil.j(e, "supply_condition").isEmpty() ? InspUtil.j(e, "supply_condition") : def);
        }
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, "Report header", 14, Ui.TEXT, true));
        card.addView(form, Ui.matchWrap(a, 4));
        if (mode != OSP && writable()) {
            LinearLayout row = Ui.hbox(a);
            Button specs = Ui.outline(a, "Saved references", Ui.TEAL);
            specs.setTextSize(12.5f);
            specs.setOnClickListener(v -> pickSuggestion("metlab.specification_reference", "Specification Reference", value -> form.set("specification_reference", value)));
            row.addView(specs, Ui.weight(1));
            Button docs = Ui.outline(a, "+ Saved statement", Ui.TEAL);
            docs.setTextSize(12.5f);
            docs.setOnClickListener(v -> pickSuggestion("metlab.reference_document", "Reference Documents / Statements", value -> {
                String cur = form.str("reference_documents");
                form.set("reference_documents", cur.isEmpty() ? value : cur + "\n" + value);
            }));
            LinearLayout.LayoutParams lp = Ui.weight(1);
            lp.leftMargin = dp(8);
            row.addView(docs, lp);
            card.addView(row, Ui.matchWrap(a, 8));
        }
        add(card, 10);
    }

    interface Value { void set(String v); }

    private void pickSuggestion(String key, String title, Value value) {
        Api.async(() -> InspUtil.suggestions(api, key), (list, err) -> {
            if (list == null || list.isEmpty()) { a.toast("No saved values yet. Type a new one; it is remembered when the report is saved."); return; }
            InspUtil.pick(a, title, list, list, value::set);
        });
    }

    private void renderBend() {
        JSONObject saved = results().optJSONObject("bend_report");
        if (saved == null) saved = new JSONObject();
        List<Field> f = new ArrayList<>();
        for (String[] b : BEND_FIELDS) f.add(Field.text(b[0], b[1]));
        f.add(Field.select("bend_status", "Bend Test Status", "Passed", "Failed").labels("Passed", "Failed").hint("Blank = from final decision"));
        f.add(Field.text("surface_remark", "Remark under part photo"));
        if (!writable()) for (Field x : f) x.readOnly = true;
        bendForm = new FormView(a, f);
        for (Field x : f) formKeys.add("b:" + x.key);
        for (String[] b : BEND_FIELDS) bendForm.set(b[0], InspUtil.j(saved, b[0]));
        String bs = InspUtil.j(saved, "bend_status");
        if (bs.equals("Passed") || bs.equals("Failed")) bendForm.set("bend_status", bs);
        bendForm.set("surface_remark", InspUtil.j(saved, "surface_remark").isEmpty() ? "No Peeling, Flaking on the plating surface." : InspUtil.j(saved, "surface_remark"));
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, "Bend Test report details", 14, Ui.TEXT, true));
        card.addView(Ui.text(a, "Printed exactly in the Bend Test Report layout. Leave blank to use the values from Part Master / layout readings.", 12, Ui.MUTED, false));
        card.addView(bendForm, Ui.matchWrap(a, 4));
        add(card, 10);
    }

    private void renderPhotos() {
        boolean bend = InspUtil.BEND_TEST.equals(method);
        List<Field> f = new ArrayList<>();
        for (int i = 1; i <= 4; i++) f.add(Field.text("microstructure_caption_" + i, "Photo " + i + " Title"));
        if (!writable()) for (Field x : f) x.readOnly = true;
        captionForm = new FormView(a, f);
        for (Field x : f) formKeys.add("c:" + x.key);
        for (int i = 1; i <= 4; i++) {
            String cap = InspUtil.j(existing, "microstructure_caption_" + i);
            if (cap.isEmpty() && bend) cap = InspUtil.BEND_CAPTIONS[i - 1];
            captionForm.set("microstructure_caption_" + i, cap);
        }
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, bend ? "B · Bend Test evidence / photographs" : "B · Microstructure photographs", 14, Ui.TEXT, true));
        card.addView(Ui.text(a, bend ? "Photo 1 can hold the machine / Load-vs-CHT test report; remaining photos can show bend angle and plating condition." : "Up to four report photographs with controlled titles.", 12, Ui.MUTED, false));
        card.addView(captionForm, Ui.matchWrap(a, 4));
        if (writable()) {
            for (int i = (mode == OSP ? 1 : 0); i <= 4; i++) {
                final int slot = i;
                String label = slot == 0 ? "Attach " + kind() + " Report (report copy)" : bend ? "Photo " + slot + " · " + InspUtil.BEND_PHOTO_LABELS[slot - 1] : (mode == OSP ? "Microstructure Photo " : "Photo ") + slot;
                String already = slot == 0 ? InspUtil.j(existing, "attachment_path") : InspUtil.j(existing, "microstructure_image_" + slot + "_path");
                photoLabels[slot] = Ui.text(a, photos[slot] != null ? "Selected: " + photos[slot].name : already.isEmpty() ? "No file selected" : "Already uploaded · pick a file to replace it", 12, Ui.MUTED, false);
                Button b = Ui.outline(a, label, Ui.TEAL);
                b.setTextSize(12.5f);
                b.setOnClickListener(v -> a.pickFile(label, slot != 0, file -> { photos[slot] = file; photoLabels[slot].setText("Selected: " + file.name + " (" + (file.data.length / 1024) + " KB)"); }));
                card.addView(b, Ui.matchWrap(a, 10));
                card.addView(photoLabels[slot]);
            }
        }
        add(card, 10);
    }

    // ------------------------------------------------------------------ rows
    private List<JSONObject> buildRows() {
        List<JSONObject> out = new ArrayList<>();
        try {
            JSONArray savedArr = results().optJSONArray("rows");
            List<JSONObject> saved = InspUtil.list(savedArr);
            if (mode == OSP) {
                Map<String, JSONObject> by = new HashMap<>();
                for (JSONObject s : saved) by.put(InspUtil.j(s, "inspection_plan_characteristic_id"), s);
                int pos = 0;
                for (JSONObject c : chars) {
                    pos++;
                    JSONObject s = by.get(InspUtil.j(c, "id"));
                    JSONObject r = charRow(c, pos);
                    String sr = !InspUtil.j(c, "characteristic_no").isEmpty() ? InspUtil.j(c, "characteristic_no") : InspUtil.j(r, "sequence_no");
                    r.put("characteristic_no", sr);
                    String actual = "";
                    if (s != null) {
                        JSONArray obs = s.optJSONArray("observations");
                        actual = obs != null && obs.length() > 0 ? InspReadings.text(obs.opt(0)) : InspReadings.text(s.opt("actual_value"));
                        r.put("applicability", "NOT_APPLICABLE".equals(InspUtil.j(s, "applicability")) ? "NOT_APPLICABLE" : "APPLICABLE");
                        r.put("remarks", InspUtil.j(s, "remarks"));
                    }
                    r.put("observations", new JSONArray().put(actual));
                    out.add(r);
                }
                return out;
            }
            boolean raw = existing != null && InspUtil.isRawRecord(existing);
            if (!saved.isEmpty() && !raw) {
                for (JSONObject s : saved) {
                    JSONObject r = new JSONObject();
                    r.put("sequence_no", InspUtil.j(s, "sequence_no"));
                    r.put("inspection_plan_characteristic_id", InspUtil.j(s, "inspection_plan_characteristic_id"));
                    r.put("characteristic", InspUtil.j(s, "parameter"));
                    r.put("specification", InspUtil.j(s, "specification"));
                    r.put("lower_spec", s.opt("lower_spec"));
                    r.put("upper_spec", s.opt("upper_spec"));
                    r.put("unit", InspUtil.j(s, "unit"));
                    r.put("checking_aid", InspUtil.j(s, "checking_method"));
                    r.put("characteristic_type", InspUtil.j(s, "characteristic_type").isEmpty() ? "VARIABLE" : InspUtil.j(s, "characteristic_type"));
                    r.put("layout_metadata", InspUtil.metadata(s));
                    r.put("observations", new JSONArray().put(InspReadings.text(s.opt("actual_value"))));
                    r.put("applicability", "NOT_APPLICABLE".equals(InspUtil.j(s, "applicability")) ? "NOT_APPLICABLE" : "APPLICABLE");
                    r.put("remarks", InspUtil.j(s, "remarks"));
                    if (s.has("case_depth_traverse")) r.put("case_depth_traverse", s.optBoolean("case_depth_traverse"));
                    if (s.has("case_depth_location")) r.put("case_depth_location", InspUtil.j(s, "case_depth_location"));
                    out.add(r);
                }
                return out;
            }
            Map<String, JSONObject> by = new HashMap<>();
            for (JSONObject s : saved) by.put(InspUtil.j(s, "inspection_plan_characteristic_id"), s);
            int pos = 0;
            for (JSONObject c : chars) {
                pos++;
                JSONObject r = charRow(c, pos);
                JSONObject meta = InspUtil.metadata(c);
                r.put("case_depth_traverse", meta.optBoolean("case_depth_traverse", false));
                r.put("case_depth_location", InspUtil.j(meta, "case_depth_location"));
                JSONObject prev = raw ? by.get(InspUtil.j(c, "id")) : null;
                r.put("observations", new JSONArray().put(prev != null ? InspReadings.text(prev.opt("actual_value")) : ""));
                if (prev != null && prev.has("remarks")) r.put("remarks", InspUtil.j(prev, "remarks"));
                if (prev != null && prev.has("applicability")) r.put("applicability", InspUtil.j(prev, "applicability"));
                out.add(r);
            }
        } catch (Exception e) {
            a.toast(Api.message(e));
        }
        return out;
    }

    private JSONObject charRow(JSONObject c, int pos) throws Exception {
        JSONObject r = new JSONObject();
        r.put("sequence_no", InspUtil.j(c, "sequence_no").isEmpty() ? String.valueOf(pos) : InspUtil.j(c, "sequence_no"));
        r.put("inspection_plan_characteristic_id", InspUtil.j(c, "id"));
        r.put("characteristic", InspUtil.j(c, "characteristic"));
        r.put("specification", InspUtil.j(c, "specification"));
        r.put("lower_spec", c.opt("lower_spec"));
        r.put("upper_spec", c.opt("upper_spec"));
        r.put("unit", InspUtil.j(c, "unit"));
        r.put("checking_aid", !InspUtil.j(c, "checking_aid_text").isEmpty() ? InspUtil.j(c, "checking_aid_text") : InspUtil.j(c, "checking_method"));
        r.put("characteristic_type", InspUtil.j(c, "characteristic_type").isEmpty() ? "VARIABLE" : InspUtil.j(c, "characteristic_type"));
        r.put("layout_metadata", InspUtil.metadata(c));
        r.put("applicability", "APPLICABLE");
        r.put("remarks", "");
        return r;
    }

    // ------------------------------------------------------------------ case depth traverse (_render_case_depth_traverse)
    static String locationFromParameter(String parameter) {
        String text = parameter == null ? "" : parameter.replaceAll("\\s+", " ").trim();
        if (text.isEmpty()) return "";
        String loc = Pattern.compile("^(?:effective\\s+)?case\\s+depth(?:\\s+(?:at|of|on)\\s+|\\s*[-:–—]\\s*|\\s+)?", Pattern.CASE_INSENSITIVE).matcher(text).replaceFirst("");
        loc = loc.replaceAll("^[\\s\\-:–—]+|[\\s\\-:–—]+$", "");
        return loc.isEmpty() ? text : loc;
    }

    static String caseDepthSpec(JSONObject r) {
        String spec = InspUtil.j(r, "specification").trim();
        if (!spec.isEmpty()) return spec;
        Double lo = Rules.number(r.opt("lower_spec")), hi = Rules.number(r.opt("upper_spec"));
        String unit = InspUtil.j(r, "unit").trim();
        if (lo == null && hi == null) return "";
        String t = lo != null && hi != null ? py(lo) + " - " + py(hi) : lo != null ? ">= " + py(lo) : "<= " + py(hi);
        return (t + " " + unit).trim();
    }

    private static String py(Double d) { return String.valueOf(d); }

    private List<JSONObject> computeLocations(List<JSONObject> rows) {
        List<JSONObject> out = new ArrayList<>();
        try {
            for (JSONObject r : rows) {
                String parameter = InspUtil.j(r, "characteristic").trim();
                boolean explicit = r.optBoolean("case_depth_traverse", false);
                if (!explicit && !InspUtil.CASE_DEPTH.matcher(parameter).find()) continue;
                String loc = explicit ? InspUtil.j(r, "case_depth_location").trim() : "";
                Double seq = Rules.number(r.opt("sequence_no"));
                JSONObject l = new JSONObject();
                l.put("sequence_no", seq == null || seq == 0 ? out.size() + 1 : (int) Math.round(seq));
                l.put("location", loc.isEmpty() ? locationFromParameter(parameter) : loc);
                l.put("parameter", parameter);
                l.put("specification", caseDepthSpec(r));
                l.put("unit", InspUtil.nz(InspUtil.j(r, "unit")));
                l.put("inspection_plan_characteristic_id", InspUtil.nz(InspUtil.j(r, "inspection_plan_characteristic_id")));
                out.add(l);
            }
            out.sort((x, y) -> {
                int c = Integer.compare(x.optInt("sequence_no"), y.optInt("sequence_no"));
                return c != 0 ? c : InspUtil.j(x, "location").compareTo(InspUtil.j(y, "location"));
            });
            for (int i = 0; i < out.size(); i++) out.get(i).put("sequence_no", i + 1);
        } catch (Exception ignored) { }
        return out;
    }

    private List<String> locationNames() {
        List<String> names = new ArrayList<>();
        for (JSONObject l : locations) names.add(InspUtil.j(l, "location").trim());
        return names;
    }

    private void renderCaseDepth() {
        locations = computeLocations(readings.rows());
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, "Case Depth / Microhardness Traverse", 14, Ui.TEXT, true));
        if (locations.isEmpty()) {
            card.addView(Ui.text(a, "Not applicable for this approved layout.", 12.5f, Ui.MUTED, false));
            add(card, 10);
            return;
        }
        card.addView(Ui.text(a, "Locations and specifications are controlled by Inspection Layout Master. Only distance-wise hardness readings (HV) are entered here.", 12, Ui.MUTED, false));
        List<List<String>> locRows = new ArrayList<>();
        for (JSONObject l : locations) {
            List<String> line = new ArrayList<>();
            line.add(InspUtil.j(l, "sequence_no")); line.add(InspUtil.j(l, "location")); line.add(InspUtil.j(l, "parameter")); line.add(InspUtil.j(l, "specification")); line.add(InspUtil.j(l, "unit"));
            locRows.add(line);
        }
        List<String> locHead = new ArrayList<>();
        for (String h : new String[]{"Sr No", "Case Depth Location", "Parameter", "Specification", "Unit"}) locHead.add(h);
        card.addView(new DataGrid(a, "Case Depth Locations", locHead, locRows, 200, null), Ui.matchWrap(a, 6));
        if (traverse == null) {
            traverse = new ArrayList<>();
            List<JSONObject> saved = InspUtil.list(results().optJSONArray("case_depth_traverse"));
            try {
                if (saved.isEmpty()) for (double d : DEFAULT_DISTANCES) traverse.add(new JSONObject().put("distance_mm", d).put("readings", new JSONObject()));
                else for (JSONObject s : saved) traverse.add(InspUtil.copy(s));
            } catch (Exception ignored) { }
        }
        traverseSheet = new SheetView(a);
        traverseSheet.setMaxHeightDp(320);
        traverseSheet.setOnRowClick(this::editDistance);
        LinearLayout frame = Ui.vbox(a);
        frame.setBackground(Ui.round(android.graphics.Color.WHITE, Ui.LINE_STRONG, 1, 10, a));
        frame.setPadding(1, 1, 1, 1);
        frame.addView(traverseSheet, Ui.matchWrap(a, 0));
        card.addView(Ui.text(a, "Traverse readings (HV) · tap a row to enter", 12, Ui.TEXT, true), Ui.matchWrap(a, 8));
        card.addView(frame, Ui.matchWrap(a, 4));
        if (writable()) {
            Button addRow = Ui.outline(a, "+ Add distance", Ui.TEAL);
            addRow.setOnClickListener(v -> editDistance(-1));
            card.addView(addRow, Ui.matchWrap(a, 8));
        }
        refreshTraverse();
        add(card, 10);
    }

    private void refreshTraverse() {
        if (traverseSheet == null) return;
        List<String> head = new ArrayList<>();
        head.add("Distance (mm)");
        List<String> names = locationNames();
        head.addAll(names);
        List<String[]> data = new ArrayList<>();
        for (JSONObject t : traverse) {
            String[] line = new String[names.size() + 1];
            line[0] = InspUtil.fmt(t.opt("distance_mm"));
            JSONObject rd = t.optJSONObject("readings");
            for (int i = 0; i < names.size(); i++) line[i + 1] = rd == null ? "" : InspUtil.fmt(rd.opt(names.get(i)));
            data.add(line);
        }
        traverseSheet.setData(head, data);
    }

    private void editDistance(int index) {
        if (!writable()) return;
        JSONObject cur = index >= 0 && index < traverse.size() ? traverse.get(index) : null;
        LinearLayout box = Ui.vbox(a);
        box.setPadding(dp(18), dp(4), dp(18), dp(8));
        box.addView(Ui.label(a, "Distance (mm)"));
        EditText dist = Ui.input(a, "e.g. 0.05", false);
        dist.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
        dist.setText(cur == null ? "" : InspUtil.fmt(cur.opt("distance_mm")));
        box.addView(dist, Ui.matchWrap(a, 0));
        List<String> names = locationNames();
        List<EditText> inputs = new ArrayList<>();
        for (String n : names) {
            box.addView(Ui.label(a, n + " (HV)"));
            EditText e = Ui.input(a, "HV", false);
            e.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
            JSONObject rd = cur == null ? null : cur.optJSONObject("readings");
            e.setText(rd == null ? "" : InspUtil.fmt(rd.opt(n)));
            inputs.add(e);
            box.addView(e, Ui.matchWrap(a, 0));
        }
        ScrollView sv = new ScrollView(a);
        sv.addView(box);
        AlertDialog.Builder b = new AlertDialog.Builder(a).setTitle(cur == null ? "New traverse distance" : "Traverse distance").setView(sv)
            .setNegativeButton("Back", null)
            .setPositiveButton("OK", (d, w) -> {
                try {
                    Double dv = Rules.number(dist.getText().toString());
                    JSONObject t = cur == null ? new JSONObject() : cur;
                    t.put("distance_mm", dv == null ? JSONObject.NULL : (Object) dv);
                    JSONObject rd = new JSONObject();
                    for (int i = 0; i < names.size(); i++) {
                        Double v = Rules.number(inputs.get(i).getText().toString());
                        rd.put(names.get(i), v == null ? JSONObject.NULL : (Object) v);
                    }
                    t.put("readings", rd);
                    if (cur == null) traverse.add(t);
                } catch (Exception e) { a.toast(Api.message(e)); }
                refreshTraverse();
            });
        if (cur != null) b.setNeutralButton("Remove row", (d, w) -> { traverse.remove(cur); refreshTraverse(); });
        b.show();
    }

    /** Case depth result keys + validity (website rules). */
    private JSONObject caseDepthResults() throws Exception {
        JSONObject out = new JSONObject();
        locations = computeLocations(readings.rows());
        if (locations.isEmpty()) {
            out.put("case_depth_applicable", false);
            out.put("case_depth_locations", new JSONArray());
            out.put("case_depth_traverse", new JSONArray());
            out.put("case_depth_na_reason", "No Inspection Layout characteristic is ticked for Case Depth Traverse.");
            return out;
        }
        List<String> names = locationNames();
        Set<String> uniq = new HashSet<>();
        int nonEmpty = 0;
        for (String n : names) if (!n.isEmpty()) { nonEmpty++; uniq.add(n.toLowerCase(Locale.ROOT)); }
        if (uniq.size() != nonEmpty) throw new Api.ApiException(422, "Case Depth layout locations must be unique. Correct the duplicate Case Depth Parameter names in Inspection Layout Master.");
        List<JSONObject> normalized = new ArrayList<>();
        Set<Double> seen = new HashSet<>();
        boolean dup = false;
        for (JSONObject t : traverse == null ? new ArrayList<JSONObject>() : traverse) {
            Double d = Rules.number(t.opt("distance_mm"));
            if (d == null) continue;
            double dd = Math.round(d * 10000.0) / 10000.0;
            if (!seen.add(dd)) dup = true;
            JSONObject rd = new JSONObject();
            JSONObject src = t.optJSONObject("readings");
            for (String n : names) { Double v = src == null ? null : Rules.number(src.opt(n)); rd.put(n, v == null ? JSONObject.NULL : (Object) v); }
            normalized.add(new JSONObject().put("distance_mm", dd).put("readings", rd));
        }
        normalized.sort((x, y) -> Double.compare(x.optDouble("distance_mm"), y.optDouble("distance_mm")));
        if (normalized.isEmpty()) throw new Api.ApiException(422, "Enter the Case Depth traverse readings (first distance 0.05 mm).");
        if (dup) throw new Api.ApiException(422, "Case Depth traverse distance values must be unique.");
        if (Math.abs(normalized.get(0).optDouble("distance_mm") - 0.05) >= 1e-9) throw new Api.ApiException(422, "The first Case Depth traverse reading must start at 0.05 mm.");
        List<String> missing = new ArrayList<>();
        for (String n : names) {
            boolean any = false;
            for (JSONObject t : normalized) if (!t.getJSONObject("readings").isNull(n)) any = true;
            if (!any) missing.add(n);
        }
        if (!missing.isEmpty()) throw new Api.ApiException(422, "Enter at least one Traverse hardness reading for: " + String.join(", ", missing));
        JSONArray locs = new JSONArray();
        for (JSONObject l : locations) locs.put(l);
        JSONArray tr = new JSONArray();
        for (JSONObject t : normalized) tr.put(t);
        out.put("case_depth_applicable", true);
        out.put("case_depth_locations", locs);
        out.put("case_depth_traverse", tr);
        out.put("case_depth_na_reason", JSONObject.NULL);
        return out;
    }

    // ------------------------------------------------------------------ pickers
    private void pickInward() {
        a.toast("Loading eligible Material Inward…");
        Api.async(() -> {
            List<JSONObject> rows = InspUtil.eligibleInwards(api);
            Set<String> partIds = new HashSet<>(), partyIds = new HashSet<>();
            for (JSONObject r : rows) { partIds.add(InspUtil.j(r, "part_id")); partyIds.add(InspUtil.j(r, "supplier_id")); }
            Map<String, JSONObject> parts = InspUtil.byId(api, "parts", "id,part_number,fsi_part_number,part_name", partIds);
            Map<String, JSONObject> parties = InspUtil.byId(api, "parties", "id,party_name", partyIds);
            List<String> ids = new ArrayList<>(), names = new ArrayList<>();
            for (JSONObject r : rows) { ids.add(InspUtil.j(r, "id")); names.add(InspUtil.inwardLabel(r, parts, parties)); }
            return new Object[]{ids, names};
        }, (res, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            @SuppressWarnings("unchecked") List<String> ids = (List<String>) res[0];
            @SuppressWarnings("unchecked") List<String> names = (List<String>) res[1];
            if (ids.isEmpty()) { a.toast("No Accepted or Accepted Under Reserve Material Inward is available."); return; }
            InspUtil.pick(a, "Material Inward", ids, names, picked -> { inwardId = picked; manualPlanId = ""; reloadContext(); });
        });
    }

    private void pickPlan() {
        List<String> ids = new ArrayList<>(), names = new ArrayList<>();
        for (JSONObject p : planOptions) { ids.add(InspUtil.j(p, "id")); names.add(InspUtil.planLabel(p)); }
        InspUtil.pick(a, "Layout", ids, names, picked -> { manualPlanId = picked; reloadContext(); });
    }

    private void pickScope() {
        List<String> ids = new ArrayList<>(), names = new ArrayList<>();
        for (int i = 0; i < InspUtil.STANDALONE_SCOPES.length; i++) { ids.add(InspUtil.STANDALONE_SCOPES[i]); names.add(InspUtil.STANDALONE_LABELS[i]); }
        InspUtil.pick(a, "Report Stage", ids, names, picked -> { scope = picked; groupId = ""; manualPlanId = ""; if (!partId.isEmpty()) reloadContext(); else render(); });
    }

    private void pickPart() {
        Api.async(() -> Lookups.rows(api, Lookups.parts()), (rows, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            List<String> ids = new ArrayList<>(), names = new ArrayList<>();
            for (JSONObject r : InspUtil.list(rows)) { ids.add(InspUtil.j(r, "id")); names.add(Lookups.PART.of(r)); }
            if (ids.isEmpty()) { a.toast("No active Parts are available."); return; }
            InspUtil.pick(a, "Part Number", ids, names, picked -> { partId = picked; groupId = ""; manualPlanId = ""; reloadContext(); });
        });
    }

    private void pickGroup() {
        List<String> ids = new ArrayList<>(), names = new ArrayList<>();
        for (JSONObject g : groups) { ids.add(InspUtil.j(g, "id")); names.add(groupLabel(g)); }
        InspUtil.pick(a, "OSP Process", ids, names, picked -> { groupId = picked; reloadContext(); });
    }

    // ------------------------------------------------------------------ save
    private void renderTail() {
        if (writable()) {
            Button save = Ui.primary(a, mode == OSP ? "Save OSP MetLAB Draft" : mode == STANDALONE ? "Save Standalone " + kind() + " Report" : "Save Raw Material " + kind() + " Draft");
            save.setOnClickListener(v -> save(save));
            add(save, 16);
        }
        if (existing != null) {
            Button open = Ui.outline(a, "Open record (finalize, amendment, attachments)", Ui.TEAL);
            open.setOnClickListener(v -> openRecord(InspUtil.j(existing, "id")));
            add(open, 8);
        }
    }

    private void openRecord(String reportId) {
        Module m = Catalog.get(bendMode || InspUtil.BEND_TEST.equals(method) ? "bend_tests" : "metlab_reports");
        if (m == null) m = Catalog.adhoc("lab_tests");
        a.replaceTop(new RecordScreen(a, m, reportId));
    }

    private void save(Button button) {
        String problem = form.validate();
        if (problem == null && bendForm != null) problem = bendForm.validate();
        if (problem != null) { a.toast(problem); return; }
        if (form.str("prepared_by_employee_id").isEmpty()) { a.toast("Prepared By is required."); return; }
        if (mode != OSP && form.str("sample_reference").isEmpty()) { a.toast("Sample Reference is required."); return; }
        String label = button.getText().toString();
        button.setEnabled(false);
        button.setText("Saving…");
        Attachments.FileData[] files = photos.clone();
        Api.async(this::saveNow, (saved, err) -> {
            button.setEnabled(true);
            button.setText(label);
            if (err != null) { a.toast(Api.message(err)); return; }
            String sid = InspUtil.j(saved, "id"), number = InspUtil.j(saved, "report_number");
            boolean any = false;
            for (Attachments.FileData f : files) if (f != null) any = true;
            if (!any) { a.toast(kind() + " Report " + number + " saved successfully."); openRecord(sid); return; }
            a.toast("Report " + number + " saved · uploading photos / report copy…");
            Api.async(() -> {
                List<String> failed = new ArrayList<>();
                for (int i = 0; i < files.length; i++) {
                    if (files[i] == null) continue;
                    try {
                        if (i == 0) Attachments.uploadReport(api, "METLAB_REPORT", sid, "REPORT_COPY", files[i], "lab_tests", "attachment_path");
                        else Attachments.uploadReport(api, "METLAB_REPORT", sid, "MICROSTRUCTURE_" + i, files[i], "lab_tests", "microstructure_image_" + i + "_path");
                    } catch (Exception e) { failed.add((i == 0 ? "report copy" : "photo " + i) + ": " + Api.message(e)); }
                }
                return failed;
            }, (failed, e2) -> {
                a.toast(failed != null && !failed.isEmpty() ? "Report saved, but some uploads failed – " + String.join("; ", failed) : kind() + " Report " + number + " saved successfully.");
                openRecord(sid);
            });
        });
    }

    private JSONObject saveNow() throws Exception {
        String number = form.str("report_number");
        if (number.isEmpty()) number = api.nextNumber("qsms_next_document_number", new JSONObject().put("p_sequence_code", "METLAB_REPORT"));
        if (number == null || number.isEmpty()) throw new Api.ApiException(500, "QCMS could not generate the MetLAB report number.");
        String status = existing == null || InspUtil.j(existing, "status").isEmpty() ? "DRAFT" : InspUtil.j(existing, "status");
        String planId = InspUtil.j(plan, "id");
        JSONObject p = new JSONObject();
        p.put("report_number", number);
        p.put("test_type", "METLAB");
        p.put("layout_plan_id", planId);
        p.put("inspection_stage_id", InspUtil.nzObj(plan.opt("inspection_stage_id")));
        p.put("part_id", partId);
        p.put("test_date", form.str("test_date"));
        p.put("overall_result", "NOT_EVALUATED");
        p.put("status", status);
        p.put("remarks", InspUtil.nz(form.str("remarks")));
        p.put("disposition", form.str("disposition").isEmpty() ? "PENDING" : form.str("disposition"));
        p.put("prepared_by_employee_id", form.str("prepared_by_employee_id"));
        p.put("layout_name_snapshot", InspUtil.nzObj(plan.opt("layout_name")));
        for (int i = 1; i <= 4; i++) p.put("microstructure_caption_" + i, InspUtil.nz(captionForm.str("microstructure_caption_" + i)));
        List<String> refDocs = new ArrayList<>();
        if (mode != OSP) for (String line : form.str("reference_documents").split("\n")) if (!line.trim().isEmpty() && !refDocs.contains(line.trim())) refDocs.add(line.trim());
        String specRef = mode == OSP ? "" : form.str("specification_reference");
        if (mode == LINKED) {
            p.put("process_id", InspUtil.nzObj(plan.opt("process_id")));
            p.put("inward_lot_id", inwardId);
            p.put("rmtc_approval_id", InspUtil.nzObj(inward.opt("rmtc_approval_id")));
            p.put("supplier_id", InspUtil.nzObj(inward.opt("supplier_id")));
            p.put("steel_mill_id", InspUtil.nzObj(rmtc == null ? null : rmtc.opt("steel_mill_id")));
            p.put("material_grade_id", InspUtil.nzObj(part == null ? null : part.opt("material_grade_id")));
            p.put("sample_reference", form.str("sample_reference"));
            p.put("specification_reference", InspUtil.nz(specRef));
            p.put("disposition_reason", InspUtil.nz(form.str("disposition_reason")));
            p.put("heat_number", InspUtil.nzObj(inward.opt("heat_number")));
            p.put("heat_code", InspUtil.nzObj(inward.opt("heat_code")));
            p.put("layout_type_name", InspUtil.j(plan, "layout_type").isEmpty() ? "METLAB" : InspUtil.j(plan, "layout_type"));
            if (InspUtil.j(plan, "layout_name").isEmpty()) p.put("layout_name_snapshot", "Raw Material Inward MetLAB");
            Object steel = InspUtil.dbl(inward, "steel_quantity_kg") != 0 ? inward.opt("steel_quantity_kg") : inward.opt("quantity_received");
            p.put("steel_quantity_kg", InspUtil.numOrNull(steel));
            p.put("production_quantity_pcs", InspUtil.numOrNull(inward.opt("production_quantity_pcs")));
        } else if (mode == STANDALONE) {
            String processId = group != null && !InspUtil.j(group, "process_id").isEmpty() ? InspUtil.j(group, "process_id") : InspUtil.j(plan, "process_id");
            p.put("process_id", InspUtil.nz(processId));
            p.put("inward_lot_id", JSONObject.NULL);
            p.put("osp_job_id", JSONObject.NULL);
            p.put("batch_id", JSONObject.NULL);
            p.put("rmtc_approval_id", JSONObject.NULL);
            p.put("supplier_id", InspUtil.nz(form.str("supplier_id")));
            p.put("osp_vendor_id", InspUtil.nz(form.str("osp_vendor_id")));
            p.put("customer_id", InspUtil.nzObj(part == null ? null : part.opt("customer_id")));
            p.put("material_grade_id", InspUtil.nzObj(part == null ? null : part.opt("material_grade_id")));
            p.put("sample_reference", form.str("sample_reference"));
            p.put("reference_text", form.str("sample_reference"));
            p.put("specification_reference", InspUtil.nz(specRef));
            p.put("disposition_reason", InspUtil.nz(form.str("disposition_reason")));
            for (String k : new String[]{"heat_number", "heat_code", "batch_number", "supplier_reference_number", "supply_condition"}) p.put(k, InspUtil.nz(form.str(k)));
            p.put("layout_type_name", InspUtil.scopeLabel(scope));
            p.put("steel_quantity_kg", JSONObject.NULL);
            Double q = form.num("production_quantity_pcs");
            p.put("production_quantity_pcs", q == null || q == 0 ? JSONObject.NULL : (Object) q);
            p.put("inspection_scope", scope);
            String spec = group != null && !InspUtil.j(group, "process_specification").isEmpty() ? InspUtil.j(group, "process_specification") : InspUtil.j(plan, "remarks");
            p.put("process_specification_snapshot", InspUtil.nz(spec));
            p.put("vendor_batch_number_snapshot", InspUtil.nz(form.str("vendor_batch_number_snapshot")));
        } else {
            double qty = "OSP_SAMPLE".equals(scope) ? InspUtil.dbl(job, "sample_quantity") : InspUtil.dbl(job, "quantity_received");
            p.put("part_id", InspUtil.j(job, "part_id"));
            p.put("osp_job_id", InspUtil.j(job, "id"));
            p.put("batch_id", InspUtil.nzObj(job.opt("osp_batch_id")));
            p.put("process_id", InspUtil.nzObj(job.opt("process_id")));
            p.put("inspection_scope", scope);
            p.put("heat_number", InspUtil.nzObj(job.opt("heat_number")));
            p.put("heat_code", InspUtil.nzObj(job.opt("heat_code")));
            p.put("batch_number", InspUtil.nzObj(job.opt("osp_batch_code")));
            p.put("supplier_id", sourceSupplier == null ? JSONObject.NULL : sourceSupplier.opt("id"));
            p.put("layout_type_name", "METLAB");
            p.put("production_quantity_pcs", qty);
            p.put("process_specification_snapshot", InspUtil.nzObj(job.opt("process_specification")));
            p.put("vendor_batch_number_snapshot", InspUtil.nzObj(job.opt("vendor_batch_number")));
            p.put("osp_vendor_id", InspUtil.nzObj(job.opt("vendor_id")));
            p.put("sample_reference", InspUtil.j(job, "osp_job_number") + " / " + (InspUtil.j(job, "vendor_batch_number").isEmpty() ? "None" : InspUtil.j(job, "vendor_batch_number")));
            p.put("specification_reference", InspUtil.nzObj(job.opt("process_specification")));
        }
        // ---- rows
        JSONArray rows = new JSONArray();
        int pos = 0;
        for (JSONObject r : readings.rows()) {
            pos++;
            List<String> obs = InspReadings.readings(r);
            String actual = obs.isEmpty() ? "" : obs.get(0);
            boolean na = InspReadings.na(r);
            String type = InspUtil.j(r, "characteristic_type");
            String result = Rules.evaluate(type.isEmpty() ? "VARIABLE" : type, InspUtil.j(r, "specification"), Rules.number(r.opt("lower_spec")), Rules.number(r.opt("upper_spec")), obs, na);
            Double seqD = Rules.number(r.opt("sequence_no"));
            int seq = seqD == null || seqD == 0 ? pos : (int) Math.round(seqD);
            JSONObject row = new JSONObject();
            row.put("sequence_no", seq);
            row.put("inspection_plan_characteristic_id", InspUtil.nz(InspUtil.j(r, "inspection_plan_characteristic_id")));
            row.put("specification", InspUtil.nz(InspUtil.j(r, "specification")));
            row.put("lower_spec", InspUtil.numOrNull(r.opt("lower_spec")));
            row.put("upper_spec", InspUtil.numOrNull(r.opt("upper_spec")));
            row.put("unit", InspUtil.nz(InspUtil.j(r, "unit")));
            row.put("actual_value", actual);
            row.put("applicability", na ? "NOT_APPLICABLE" : "APPLICABLE");
            row.put("result", result);
            row.put("remarks", InspUtil.j(r, "remarks"));
            row.put("characteristic_type", InspUtil.nz(type));
            row.put("parameter", InspUtil.j(r, "characteristic"));
            row.put("checking_method", InspUtil.nz(InspUtil.j(r, "checking_aid")));
            if (mode == OSP) {
                row.put("characteristic_no", InspUtil.nz(InspUtil.j(r, "characteristic_no")));
                row.put("characteristic", InspUtil.j(r, "characteristic"));
                row.put("checking_aid", InspUtil.nz(InspUtil.j(r, "checking_aid")));
                row.put("observations", new JSONArray().put(actual));
                row.put("report_section", "METLAB");
            } else {
                row.put("layout_metadata", InspUtil.metadata(r));
            }
            rows.put(row);
        }
        JSONObject results = new JSONObject();
        if (mode == OSP) {
            results.put("inspection_method", InspUtil.GENERAL_METLAB);
            results.put("bend_angle_degrees", JSONObject.NULL);
            results.put("reference_documents", new JSONArray());
            results.put("conclusion_remark", JSONObject.NULL);
            results.put("bend_report", new JSONObject());
            results.put("case_depth_locations", new JSONArray());
            results.put("case_depth_traverse", new JSONArray());
            results.put("case_depth_applicable", false);
            results.put("case_depth_na_reason", JSONObject.NULL);
        } else {
            boolean bend = InspUtil.BEND_TEST.equals(method);
            Object angle = JSONObject.NULL;
            if (bend && !form.str("bend_angle_degrees").isEmpty()) {
                Double ang = form.num("bend_angle_degrees");
                if (ang == null) throw new Api.ApiException(422, "Bend angle must be a number in degrees.");
                if (ang < 0 || ang > 360 || ang.isNaN() || ang.isInfinite()) throw new Api.ApiException(422, "Bend angle must be between 0 and 360 degrees.");
                angle = ang;
            }
            results.put("inspection_method", method);
            results.put("bend_angle_degrees", angle);
            JSONArray rd = new JSONArray();
            for (String s : refDocs) rd.put(s);
            results.put("reference_documents", rd);
            results.put("conclusion_remark", InspUtil.nz(form.str("conclusion_remark")));
            JSONObject bendReport = new JSONObject();
            if (bend && bendForm != null) {
                for (String[] b : BEND_FIELDS) if (!bendForm.str(b[0]).isEmpty()) bendReport.put(b[0], bendForm.str(b[0]));
                if (!bendForm.str("bend_status").isEmpty()) bendReport.put("bend_status", bendForm.str("bend_status"));
                if (!bendForm.str("surface_remark").isEmpty()) bendReport.put("surface_remark", bendForm.str("surface_remark"));
            }
            results.put("bend_report", bendReport);
            JSONObject cd = caseDepthResults();
            java.util.Iterator<String> it = cd.keys();
            while (it.hasNext()) { String k = it.next(); results.put(k, cd.get(k)); }
        }
        results.put("rows", rows);
        results.put("chemistry_rows", new JSONArray());
        results.put("jominy_rows", new JSONArray());
        results.put("requirement_rows", new JSONArray());
        // ---- InspectionService.save_metlab checks
        String existingId = existing == null ? null : InspUtil.j(existing, "id");
        if (existingId == null && InspUtil.isRawRecord(p) && !"APPROVED".equalsIgnoreCase(InspUtil.j(plan, "status"))) {
            throw new Api.ApiException(422, "New Raw Material MetLAB reports require an approved Layout Master layout.");
        }
        if ("FINAL_METALLURGICAL".equalsIgnoreCase(InspUtil.j(plan, "requirement_scope")) && !"FINAL_DISPATCH_STAGE".equalsIgnoreCase(InspUtil.j(p, "inspection_scope"))) {
            throw new Api.ApiException(422, "Part Master Section H is only applicable to Final Dispatch MetLAB.");
        }
        if (InspUtil.isRawRecord(p)) results = InspUtil.rawMaterialResults(api, p, results);
        p.put("results", results);
        if (mode != OSP) {
            InspUtil.remember(api, "metlab.specification_reference", specRef);
            for (String s : refDocs) InspUtil.remember(api, "metlab.reference_document", s);
        }
        JSONObject saved = api.save("lab_tests", existingId, p);
        if (InspUtil.j(saved, "id").isEmpty()) throw new Api.ApiException(500, "QCMS did not receive a saved report ID from the database.");
        Lookups.invalidate();
        return saved;
    }

    @Override public boolean onBack() {
        if (form == null || !writable()) return false;
        a.confirm("Leave without saving?", "Readings and changes on this report are not saved.", "Leave", () -> a.back());
        return true;
    }
}
