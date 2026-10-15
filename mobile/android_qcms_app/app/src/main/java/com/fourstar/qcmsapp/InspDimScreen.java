package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
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

/**
 * Native Dimensional Inspection Report entry (app_pages/dimensional_report.py + osp_inspections.py):
 * linked to a Material Inward, standalone stage report, or OSP sample / receipt inspection.
 * Save = header insert/update in inspection_reports + upsert of inspection_results (ids re-used by
 * inspection_plan_characteristic_id), exactly like InspectionService.save_dimensional.
 */
final class InspDimScreen extends Screen {
    static final int LINKED = 0, STANDALONE = 1, OSP = 2;

    private final String id;
    private final JSONObject prefill;
    private JSONObject existing;
    private int mode = -1;
    private boolean loaded = false;

    // selections
    private String inwardId = "", partId = "", scope = "RAW_MATERIAL_STAGE", groupId = "", manualPlanId = "";
    // context
    private JSONObject inward, part, plan, job, group, process, stage, sourceSupplier;
    private List<JSONObject> planOptions = new ArrayList<>();
    private List<JSONObject> groups = new ArrayList<>();
    private List<JSONObject> chars = new ArrayList<>();
    private List<JSONObject> savedResults = new ArrayList<>();
    private List<String> supplierIds = new ArrayList<>();
    private String contextProblem = "";
    private Map<String, JSONObject> employeeRows = new HashMap<>();

    private FormView form;
    private final List<String> formKeys = new ArrayList<>();
    private Map<String, String> formCache;
    private List<JSONObject> rowsCache;
    private InspReadings readings;
    private Attachments.FileData reportCopy;
    private TextView copyLabel;

    InspDimScreen(MainActivity a, String id, JSONObject prefill) {
        super(a);
        this.id = id;
        this.prefill = prefill;
    }

    /** OSP sample / receipt inspection for one OSP job (row of v_qsms_osp_register). */
    static InspDimScreen forOsp(MainActivity a, String reportId, JSONObject job, String scope) {
        JSONObject p = new JSONObject();
        try { p.put("_osp_job", job); p.put("_scope", scope); } catch (Exception ignored) { }
        return new InspDimScreen(a, reportId, p);
    }

    @Override public String title() {
        if (existing != null) return "Edit · " + InspUtil.j(existing, "report_number");
        return mode == OSP ? "OSP Dimensional Inspection" : "New · Dimensional Report";
    }
    @Override public String subtitle() {
        if (mode == OSP) return "OSP_SAMPLE".equals(scope) ? "Pre-inward Sample" : "Post-receipt Full Batch";
        if (mode == STANDALONE) return "Standalone Stage Report · " + InspUtil.scopeLabel(scope);
        if (mode == LINKED) return "QCMS Linked Flow · Material Inward";
        return "Automatic part / process / stage layout";
    }
    @Override public int tab() { return Catalog.QUALITY; }

    @Override
    public View build() {
        newPage();
        if (loaded) { snapshot(); render(); return scroll; }
        page.addView(loading());
        Api.async(() -> {
            if (id != null) {
                existing = InspUtil.get(api, "inspection_reports", id);
                if (existing == null) throw new Api.ApiException(404, "Dimensional report not found or not visible for your role.");
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
            a.rebuildTitle(this);
            render();
        });
        return scroll;
    }

    // ------------------------------------------------------------------ context (background)
    private void loadContextNow() throws Exception {
        contextProblem = "";
        plan = null; chars = new ArrayList<>(); planOptions = new ArrayList<>(); savedResults = new ArrayList<>();
        group = null; process = null; stage = null;
        if (mode == LINKED) {
            if (inwardId.isEmpty()) return;
            inward = InspUtil.get(api, "inward_lots", inwardId);
            if (inward == null) { contextProblem = "The Material Inward could not be loaded."; return; }
            partId = InspUtil.j(inward, "part_id");
            part = InspUtil.get(api, "parts", partId);
            planOptions = InspUtil.plans(api, "DIMENSIONAL", partId, true, null, null, null);
            String saved = InspUtil.j(existing, "inspection_plan_id");
            if (!saved.isEmpty() && !containsId(planOptions, saved)) {
                JSONObject hist = InspUtil.get(api, "inspection_plans", saved);
                if (hist != null && InspUtil.j(hist, "part_id").equals(partId)) planOptions.add(0, hist);
            }
            if (planOptions.isEmpty()) { contextProblem = "No Approved Dimensional Layout is configured for this Part Number. Create / approve it in Inspection Layouts."; return; }
            List<JSONObject> ranked = InspUtil.rankedPlans(api, "DIMENSIONAL", partId, null, null, null);
            JSONObject recommended = ranked.isEmpty() ? planOptions.get(0) : ranked.get(0);
            if (existing != null) plan = !saved.isEmpty() && containsId(planOptions, saved) ? byId(planOptions, saved) : recommended;
            else plan = !manualPlanId.isEmpty() && containsId(planOptions, manualPlanId) ? byId(planOptions, manualPlanId) : recommended;
            sourceSupplier = InspUtil.get(api, "parties", InspUtil.j(inward, "supplier_id"));
        } else if (mode == STANDALONE) {
            if (partId.isEmpty()) return;
            part = InspUtil.get(api, "parts", partId);
            String processId = null;
            if ("OSP_STAGE".equals(scope)) {
                groups = InspUtil.ospProcessGroups(api, partId, "DIMENSIONAL");
                if (groups.isEmpty()) { contextProblem = "No active OSP Dimensional Process requirements are configured in Part Master for this Part Number."; return; }
                String existingProcess = InspUtil.j(existing, "process_id");
                if (groupId.isEmpty() || !containsId(groups, groupId)) {
                    groupId = InspUtil.j(groups.get(0), "id");
                    for (JSONObject g : groups) if (InspUtil.j(g, "process_id").equals(existingProcess)) groupId = InspUtil.j(g, "id");
                }
                group = byId(groups, groupId);
                processId = InspUtil.j(group, "process_id").isEmpty() ? null : InspUtil.j(group, "process_id");
            }
            String saved = InspUtil.j(existing, "inspection_plan_id");
            JSONObject p = saved.isEmpty() ? null : InspUtil.get(api, "inspection_plans", saved);
            if (p != null && !InspUtil.j(p, "part_id").equals(partId)) p = null;
            if (p == null) {
                List<JSONObject> cands = InspUtil.standalonePlans(api, "DIMENSIONAL", partId, scope, processId);
                p = cands.isEmpty() ? null : cands.get(0);
            }
            if (p == null) {
                contextProblem = "OSP_STAGE".equals(scope)
                    ? "The Part Master OSP Dimensional requirements exist, but the controlled OSP Dimensional layout has not been generated / approved. Create / update the OSP inspection layout from the Part Master process section."
                    : "No approved Dimensional layout is configured for this Part Number.";
                return;
            }
            plan = p;
            if (processId == null && !InspUtil.j(plan, "process_id").isEmpty()) processId = InspUtil.j(plan, "process_id");
            process = processId == null ? null : InspUtil.get(api, "processes", processId);
            if ("OSP_STAGE".equals(scope)) supplierIds = new ArrayList<>();
            else supplierIds = InspUtil.partSupplierIds(api, partId);
        } else if (mode == OSP) {
            if (job == null) { contextProblem = "The OSP job could not be loaded."; return; }
            partId = InspUtil.j(job, "part_id");
            part = InspUtil.get(api, "parts", partId);
            planOptions = InspUtil.plans(api, "DIMENSIONAL", partId, true, InspUtil.j(job, "process_id"), null, "OSP_PROCESS");
            if (planOptions.isEmpty()) { contextProblem = "No Approved OSP Dimensional layout matches Part " + InspUtil.j(job, "part_number") + " and Process " + InspUtil.j(job, "process_name") + ". Create / approve the OSP inspection layout."; return; }
            String saved = InspUtil.j(existing, "inspection_plan_id");
            String want = !saved.isEmpty() ? saved : manualPlanId;
            plan = !want.isEmpty() && containsId(planOptions, want) ? byId(planOptions, want) : planOptions.get(0);
            JSONObject src = InspUtil.get(api, "inward_lots", InspUtil.j(job, "source_inward_lot_id"));
            JSONObject open = InspUtil.get(api, "supply_opening_stock", InspUtil.j(job, "opening_stock_id"));
            String sup = InspUtil.j(src, "supplier_id").isEmpty() ? InspUtil.j(open, "supplier_id") : InspUtil.j(src, "supplier_id");
            sourceSupplier = sup.isEmpty() ? null : new JSONObject().put("id", sup);
        }
        if (plan != null) {
            chars = InspUtil.planChars(api, InspUtil.j(plan, "id"));
            if (process == null && !InspUtil.j(plan, "process_id").isEmpty()) process = InspUtil.get(api, "processes", InspUtil.j(plan, "process_id"));
            stage = InspUtil.get(api, "inspection_stages", InspUtil.j(plan, "inspection_stage_id"));
        }
        if (existing != null) {
            savedResults = InspUtil.list(api.rows("inspection_results?select=*&inspection_report_id=eq." + Api.enc(InspUtil.j(existing, "id")) + "&order=sequence_no.asc&limit=2000"));
        }
    }

    private static boolean containsId(List<JSONObject> l, String id) { return byId(l, id) != null; }
    private static JSONObject byId(List<JSONObject> l, String id) {
        for (JSONObject r : l) if (InspUtil.j(r, "id").equals(id)) return r;
        return null;
    }

    private void reloadContext() {
        page.removeAllViews();
        page.addView(loading());
        Api.async(() -> { loadContextNow(); return true; }, (ok, err) -> {
            if (err != null) { page.removeAllViews(); page.addView(error(err, this::reloadContext)); return; }
            reportCopy = null;
            formCache = null;
            rowsCache = null;
            render();
        });
    }

    // ------------------------------------------------------------------ UI
    private boolean writable() {
        if (existing == null) return true;
        String st = InspUtil.j(existing, "status").isEmpty() ? "DRAFT" : InspUtil.j(existing, "status").toUpperCase(Locale.ROOT);
        return mode == OSP ? !st.equals("FINAL") : st.equals("DRAFT");
    }

    private String sectionName() {
        if (mode == STANDALONE) return InspUtil.scopeLabel(scope);
        if (mode == OSP) return "DIMENSIONAL";
        return InspUtil.j(plan, "layout_type").isEmpty() ? "DIMENSIONAL" : InspUtil.j(plan, "layout_type");
    }

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

    private void render() {
        page.removeAllViews();
        a.rebuildTitle(this);
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
        renderInfo();
        renderForm();
        add(Ui.label(a, "B · Layout characteristics"), 14);
        readings = new InspReadings(a, "Dimensional characteristics", "Checking Aid");
        readings.setEditable(writable());
        int samples = mode == OSP ? 1 : clampSamples(form.num("sample_size"));
        readings.setRows(rowsCache != null ? rowsCache : buildRows(), samples);
        add(readings, 4);
        form.onChange((key, v) -> {
            if ("sample_size".equals(key) && readings != null && mode != OSP) readings.setSamples(clampSamples(form.num("sample_size")));
        });
        renderTail();
    }

    /** Keep typed values and readings when the screen is rebuilt (e.g. back from a full-screen grid). */
    private void snapshot() {
        if (form != null) {
            formCache = new HashMap<>();
            for (String k : formKeys) formCache.put(k, form.str(k));
        }
        if (readings != null) rowsCache = new ArrayList<>(readings.rows());
    }

    private static int clampSamples(Double d) {
        int n = d == null ? 1 : (int) Math.round(d);
        return Math.min(10, Math.max(1, n));
    }

    private void renderModeChoice() {
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, "Report Linkage", 15, Ui.TEXT, true));
        card.addView(Ui.text(a, "Standalone Stage Report does not require RMTC, Material Inward or Production linkage. OSP sample / receipt reports are opened from OSP Register.", 12, Ui.MUTED, false));
        Button linked = Ui.primary(a, "QCMS Linked Flow · Material Inward");
        linked.setOnClickListener(v -> { mode = LINKED; render(); });
        card.addView(linked, Ui.matchWrap(a, 10));
        Button standalone = Ui.outline(a, "Standalone Stage Report", Ui.TEAL);
        standalone.setOnClickListener(v -> { mode = STANDALONE; render(); });
        card.addView(standalone, Ui.matchWrap(a, 8));
        add(card, 4);
    }

    private void renderContext() {
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, mode == OSP ? "A · OSP batch & approved OSP layout" : mode == STANDALONE ? "A · Standalone report context" : "A · Material Inward & layout", 14, Ui.TEXT, true));
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
            if (plan != null) {
                card.addView(selector("Approved Layout Plan" + (fresh ? (manualPlanId.isEmpty() ? " (Automatic)" : " (Manual)") : ""), InspUtil.planLabel(plan),
                    fresh && planOptions.size() > 1 ? this::pickPlan : null), Ui.matchWrap(a, 8));
                if (!"APPROVED".equals(InspUtil.j(plan, "status"))) card.addView(Ui.text(a, "This report uses a historical / no-longer-approved Dimensional layout. QCMS loaded that saved layout for controlled editing.", 12, Ui.AMBER_FG, false));
            }
        } else if (mode == STANDALONE) {
            card.addView(selector("Report Stage", InspUtil.scopeLabel(scope), fresh ? this::pickScope : null), Ui.matchWrap(a, 8));
            card.addView(selector("Part Number", part == null ? "" : Lookups.PART.of(part), fresh ? this::pickPart : null), Ui.matchWrap(a, 8));
            if ("OSP_STAGE".equals(scope) && group != null) {
                card.addView(selector("OSP Process", groupLabel(group), fresh && groups.size() > 1 ? this::pickGroup : null), Ui.matchWrap(a, 8));
            }
            if (plan != null) card.addView(Ui.text(a, "Auto Layout from Part Master: " + (InspUtil.j(plan, "layout_name").isEmpty() ? InspUtil.j(plan, "plan_number") : InspUtil.j(plan, "layout_name")) + " · Rev " + InspUtil.j(plan, "revision"), 12.5f, Ui.TEAL_DARK, true));
        } else if (mode == OSP && job != null) {
            card.addView(Ui.pair(a, "OSP Job", InspUtil.j(job, "osp_job_number")));
            card.addView(Ui.pair(a, "Inspection Stage", "OSP_SAMPLE".equals(scope) ? "Pre-inward Sample" : "Post-receipt Full Batch"));
            if (plan != null) card.addView(selector("Approved OSP Layout", InspUtil.planLabel(plan), fresh && planOptions.size() > 1 ? this::pickPlan : null), Ui.matchWrap(a, 8));
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
        card.addView(Ui.pair(a, "Drawing / Revision", (InspUtil.j(part, "drawing_number").isEmpty() ? "-" : InspUtil.j(part, "drawing_number")) + " / " + (InspUtil.j(part, "drawing_revision").isEmpty() ? "-" : InspUtil.j(part, "drawing_revision"))));
        card.addView(Ui.pair(a, "Layout Name", InspUtil.j(plan, "layout_name")));
        card.addView(Ui.pair(a, "Section / Layout Type", sectionName()));
        card.addView(Ui.pair(a, "Process", process == null ? "Not assigned" : InspUtil.j(process, "process_name")));
        card.addView(Ui.pair(a, "Inspection Stage", stage == null ? "Not assigned" : InspUtil.j(stage, "stage_name")));
        if (mode == LINKED && inward != null) {
            card.addView(Ui.pair(a, "Heat Number / Code", InspUtil.j(inward, "heat_number") + " / " + InspUtil.j(inward, "heat_code")));
            card.addView(Ui.pair(a, "Supplier", InspUtil.j(sourceSupplier, "party_name")));
            double steel = InspUtil.dbl(inward, "steel_quantity_kg") != 0 ? InspUtil.dbl(inward, "steel_quantity_kg") : InspUtil.dbl(inward, "quantity_received");
            card.addView(Ui.pair(a, "Steel Quantity (kg)", Ui.num(steel, 3)));
            card.addView(Ui.pair(a, "Production Quantity (pcs)", Ui.num(InspUtil.dbl(inward, "production_quantity_pcs"), 0)));
        }
        if (mode == STANDALONE && "OSP_STAGE".equals(scope) && group != null) {
            card.addView(Ui.pair(a, "Process Specification", InspUtil.j(group, "process_specification")));
            card.addView(Ui.pair(a, "Process Drawing / Rev", InspUtil.j(group, "drawing_number") + " / " + InspUtil.j(group, "drawing_revision")));
        }
        if (mode == OSP && job != null) {
            card.addView(Ui.pair(a, "Heat Number", InspUtil.j(job, "heat_number")));
            card.addView(Ui.pair(a, "FSI Batch Number", InspUtil.j(job, "osp_batch_code")));
            card.addView(Ui.pair(a, "OSP Vendor", InspUtil.j(job, "vendor_name")));
            card.addView(Ui.pair(a, "OSP Process", InspUtil.j(job, "process_name")));
            card.addView(Ui.pair(a, "Vendor Batch", InspUtil.j(job, "vendor_batch_number")));
            card.addView(Ui.pair(a, "Process Specification", InspUtil.j(job, "process_specification")));
            card.addView(Ui.pair(a, "Material Out Remarks", InspUtil.j(job, "dispatch_remarks")));
        }
        add(card, 8);
    }

    private void renderForm() {
        List<Field> f = new ArrayList<>();
        boolean ro = !writable();
        f.add(Field.text("report_number", "Report Number").hint(existing == null ? "Auto on first save" : "").ro().def(InspUtil.j(existing, "report_number")));
        if (existing == null) f.get(0).readOnly = false;
        if (mode == OSP && existing != null) f.get(0).readOnly = true;
        f.add(Field.date("inspection_date", "Inspection Date").req());
        if (mode == STANDALONE) {
            f.add(Field.text("heat_number", "Heat Number"));
            f.add(Field.text("heat_code", "Heat Code"));
            f.add(Field.text("vendor_batch_number_snapshot", "Supplier / HT / OSP Batch Number"));
            f.add(Field.text("batch_number", "Internal / FSI Batch Number"));
            f.add(Field.text("supplier_reference_number", "Supplier Invoice / Reference"));
            f.add(Field.number("lot_quantity", "Lot / Production Quantity pcs").range(0, Double.MAX_VALUE));
            f.add(Field.text("reference_text", "Lot / Sample Reference"));
            f.add(Field.text("supply_condition", "Supply / Process Condition"));
            Field.Lookup sup = Lookups.parties(null).where(supplierFilter());
            f.add(Field.lookup("supplier_id", "Supplier / OSP Vendor", sup));
        }
        if (mode == LINKED) f.add(Field.number("lot_quantity", "Lot Quantity (pcs)").range(0, Double.MAX_VALUE));
        if (mode != OSP) f.add(Field.integer("sample_size", "Sample Size").range(1, 10).req());
        f.add(Field.area("remarks", mode == OSP ? "Report Remarks" : "Conclusion").hint(mode == OSP ? "" : "Controlled report conclusion. Separate from the Final Decision and Decision Reason."));
        f.add(Field.lookup("prepared_by_employee_id", mode == OSP ? "Prepared By" : "Inspected / Prepared By", Lookups.employees()).req());
        f.add(Field.select("disposition", mode == OSP ? "Validation Decision" : "Final Decision", InspUtil.DRAFT_DISPOSITIONS).labels(InspUtil.DISPOSITION_LABELS).req());
        if (mode != OSP) f.add(Field.text("disposition_reason", "Decision Reason").hint("Required for On Hold, Accepted Under Reserve and Rejected decisions."));
        if (ro) for (Field x : f) x.readOnly = true;
        form = new FormView(a, f);
        formKeys.clear();
        for (Field x : f) formKeys.add(x.key);
        // defaults
        JSONObject e = existing;
        form.set("inspection_date", e != null && !InspUtil.j(e, "inspection_date").isEmpty() ? InspUtil.j(e, "inspection_date").substring(0, 10) : Ui.today());
        String prepared = InspUtil.j(e, "prepared_by_employee_id");
        if (prepared.isEmpty() && e == null) prepared = api.employeeId;
        if (prepared != null && !prepared.isEmpty()) form.set("prepared_by_employee_id", prepared);
        form.set("disposition", InspUtil.j(e, "disposition").isEmpty() ? "PENDING" : InspUtil.j(e, "disposition"));
        form.set("remarks", InspUtil.j(e, "remarks"));
        if (mode != OSP) {
            form.set("disposition_reason", InspUtil.j(e, "disposition_reason"));
            double ss = InspUtil.dbl(e, "sample_size") > 0 ? InspUtil.dbl(e, "sample_size") : InspUtil.dbl(plan, "default_sample_size") > 0 ? InspUtil.dbl(plan, "default_sample_size") : 1;
            form.set("sample_size", String.valueOf(Math.min(10, Math.max(1, (int) Math.round(ss)))));
        }
        if (mode == LINKED) {
            double lot = e != null && InspUtil.dbl(e, "lot_quantity") != 0 ? InspUtil.dbl(e, "lot_quantity") : InspUtil.dbl(inward, "production_quantity_pcs");
            form.set("lot_quantity", InspUtil.fmt(lot));
        }
        if (mode == STANDALONE) {
            for (String k : new String[]{"heat_number", "heat_code", "vendor_batch_number_snapshot", "batch_number", "supplier_reference_number", "reference_text"}) form.set(k, InspUtil.j(e, k));
            double lot = InspUtil.dbl(e, "production_quantity_pcs") != 0 ? InspUtil.dbl(e, "production_quantity_pcs") : InspUtil.dbl(e, "lot_quantity");
            form.set("lot_quantity", InspUtil.fmt(lot));
            String def = group != null && !InspUtil.j(group, "process_specification").isEmpty() ? InspUtil.j(group, "process_specification")
                : process != null && !InspUtil.j(process, "process_name").isEmpty() ? InspUtil.j(process, "process_name") : InspUtil.scopeLabel(scope);
            form.set("supply_condition", e != null && !InspUtil.j(e, "supply_condition").isEmpty() ? InspUtil.j(e, "supply_condition") : def);
            if (!InspUtil.j(e, "supplier_id").isEmpty()) form.set("supplier_id", InspUtil.j(e, "supplier_id"));
        }
        if (formCache != null) for (Map.Entry<String, String> en : formCache.entrySet()) form.set(en.getKey(), en.getValue().isEmpty() ? null : en.getValue());
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, "Report header", 14, Ui.TEXT, true));
        card.addView(form, Ui.matchWrap(a, 4));
        add(card, 10);
    }

    /** Supplier choices like _render_standalone_entry (part context suppliers, OSP vendors / suppliers for OSP stage). */
    private String supplierFilter() {
        if ("OSP_STAGE".equals(scope)) return "&or=(party_types.cs.%7BOSP_VENDOR%7D,party_types.cs.%7BSUPPLIER%7D)";
        if (!supplierIds.isEmpty()) return "&id=in.(" + String.join(",", supplierIds) + ")";
        return "&party_types=cs.%7BSUPPLIER%7D";
    }

    private void renderTail() {
        boolean w = writable();
        if (mode != OSP && w) {
            LinearLayout card = Ui.card(a);
            card.addView(Ui.text(a, "Attach Report (optional)", 14, Ui.TEXT, true));
            card.addView(Ui.text(a, "PDF, Excel or photo · uploaded with the save as the report copy.", 12, Ui.MUTED, false));
            copyLabel = Ui.text(a, existing != null && !InspUtil.j(existing, "attachment_path").isEmpty() ? "A report copy is already uploaded · pick a file to replace it" : "No file selected", 12.5f, Ui.TEXT, false);
            card.addView(copyLabel, Ui.matchWrap(a, 6));
            Button pick = Ui.outline(a, "Choose report file (camera or file)", Ui.TEAL);
            pick.setOnClickListener(v -> a.pickFile("Attach Report", false, file -> { reportCopy = file; copyLabel.setText("Selected: " + file.name + " (" + (file.data.length / 1024) + " KB)"); }));
            card.addView(pick, Ui.matchWrap(a, 6));
            add(card, 10);
        }
        if (w) {
            Button save = Ui.primary(a, mode == STANDALONE ? "Save Standalone Dimensional Report" : mode == OSP ? "Save OSP Dimensional Draft" : "Save Dimensional Report Draft");
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
        Module m = Catalog.get("dimensional_reports");
        if (m == null) m = Catalog.adhoc("inspection_reports");
        a.replaceTop(new RecordScreen(a, m, reportId));
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
        InspUtil.pick(a, "Approved Layout Plan", ids, names, picked -> { manualPlanId = picked; reloadContext(); });
    }

    private void pickScope() {
        List<String> ids = new ArrayList<>(), names = new ArrayList<>();
        for (int i = 0; i < InspUtil.STANDALONE_SCOPES.length; i++) { ids.add(InspUtil.STANDALONE_SCOPES[i]); names.add(InspUtil.STANDALONE_LABELS[i]); }
        InspUtil.pick(a, "Report Stage", ids, names, picked -> { scope = picked; groupId = ""; if (!partId.isEmpty()) reloadContext(); else render(); });
    }

    private void pickPart() {
        Api.async(() -> Lookups.rows(api, Lookups.parts()), (rows, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            List<String> ids = new ArrayList<>(), names = new ArrayList<>();
            for (JSONObject r : InspUtil.list(rows)) { ids.add(InspUtil.j(r, "id")); names.add(Lookups.PART.of(r)); }
            if (ids.isEmpty()) { a.toast("No active Parts are available."); return; }
            InspUtil.pick(a, "Part Number", ids, names, picked -> { partId = picked; groupId = ""; reloadContext(); });
        });
    }

    private void pickGroup() {
        List<String> ids = new ArrayList<>(), names = new ArrayList<>();
        for (JSONObject g : groups) { ids.add(InspUtil.j(g, "id")); names.add(groupLabel(g)); }
        InspUtil.pick(a, "OSP Process", ids, names, picked -> { groupId = picked; reloadContext(); });
    }

    // ------------------------------------------------------------------ rows
    private List<JSONObject> buildRows() {
        List<JSONObject> out = new ArrayList<>();
        Map<String, JSONObject> charById = new HashMap<>();
        for (JSONObject c : chars) charById.put(InspUtil.j(c, "id"), c);
        try {
            if (mode == OSP) {
                Map<String, JSONObject> saved = new HashMap<>();
                for (JSONObject s : savedResults) saved.put(InspUtil.j(s, "inspection_plan_characteristic_id"), s);
                int pos = 0;
                for (JSONObject c : chars) {
                    pos++;
                    JSONObject s = saved.get(InspUtil.j(c, "id"));
                    JSONObject r = new JSONObject();
                    String sr = !InspUtil.j(c, "characteristic_no").isEmpty() ? InspUtil.j(c, "characteristic_no") : !InspUtil.j(c, "sequence_no").isEmpty() ? InspUtil.j(c, "sequence_no") : String.valueOf(pos);
                    r.put("characteristic_no", sr);
                    r.put("sequence_no", InspUtil.j(c, "sequence_no").isEmpty() ? String.valueOf(pos) : InspUtil.j(c, "sequence_no"));
                    r.put("inspection_plan_characteristic_id", InspUtil.j(c, "id"));
                    r.put("characteristic", InspUtil.j(c, "characteristic"));
                    r.put("specification", InspUtil.j(c, "specification"));
                    r.put("lower_spec", c.opt("lower_spec"));
                    r.put("upper_spec", c.opt("upper_spec"));
                    r.put("unit", InspUtil.j(c, "unit"));
                    r.put("checking_aid", !InspUtil.j(c, "checking_aid_text").isEmpty() ? InspUtil.j(c, "checking_aid_text") : InspUtil.j(c, "checking_method"));
                    r.put("characteristic_type", InspUtil.j(c, "characteristic_type").isEmpty() ? "VARIABLE" : InspUtil.j(c, "characteristic_type"));
                    JSONArray obs = s == null ? null : s.optJSONArray("observations");
                    r.put("observations", new JSONArray().put(obs != null && obs.length() > 0 ? InspReadings.text(obs.opt(0)) : ""));
                    r.put("applicability", s != null && "NOT_APPLICABLE".equals(InspUtil.j(s, "applicability")) ? "NOT_APPLICABLE" : "APPLICABLE");
                    r.put("remarks", InspUtil.j(s, "remarks"));
                    out.add(r);
                }
                return out;
            }
            if (!savedResults.isEmpty()) {
                int pos = 0;
                for (JSONObject s : savedResults) {
                    pos++;
                    JSONObject r = new JSONObject();
                    r.put("sequence_no", InspUtil.j(s, "sequence_no").isEmpty() ? String.valueOf(pos) : InspUtil.j(s, "sequence_no"));
                    r.put("inspection_plan_characteristic_id", InspUtil.j(s, "inspection_plan_characteristic_id"));
                    r.put("characteristic_no", InspUtil.j(s, "characteristic_no"));
                    r.put("characteristic", InspUtil.j(s, "characteristic"));
                    r.put("specification", InspUtil.j(s, "specification"));
                    r.put("lower_spec", s.opt("lower_spec"));
                    r.put("upper_spec", s.opt("upper_spec"));
                    r.put("unit", InspUtil.j(s, "unit"));
                    r.put("checking_aid", InspUtil.j(s, "checking_aid"));
                    r.put("observations", s.optJSONArray("observations") == null ? new JSONArray() : s.optJSONArray("observations"));
                    r.put("remarks", InspUtil.j(s, "remarks"));
                    r.put("applicability", InspUtil.j(s, "applicability"));
                    JSONObject c = charById.get(InspUtil.j(s, "inspection_plan_characteristic_id"));
                    r.put("characteristic_type", c == null || InspUtil.j(c, "characteristic_type").isEmpty() ? "VARIABLE" : InspUtil.j(c, "characteristic_type"));
                    out.add(r);
                }
                return out;
            }
            int pos = 0;
            for (JSONObject c : chars) {
                pos++;
                JSONObject r = new JSONObject();
                r.put("sequence_no", InspUtil.j(c, "sequence_no").isEmpty() ? String.valueOf(pos) : InspUtil.j(c, "sequence_no"));
                r.put("inspection_plan_characteristic_id", InspUtil.j(c, "id"));
                r.put("characteristic_no", InspUtil.j(c, "characteristic_no"));
                r.put("characteristic", InspUtil.j(c, "characteristic"));
                r.put("specification", InspUtil.j(c, "specification"));
                r.put("lower_spec", c.opt("lower_spec"));
                r.put("upper_spec", c.opt("upper_spec"));
                r.put("unit", InspUtil.j(c, "unit"));
                r.put("checking_aid", !InspUtil.j(c, "checking_aid_text").isEmpty() ? InspUtil.j(c, "checking_aid_text") : InspUtil.j(c, "checking_method"));
                r.put("observations", new JSONArray());
                r.put("remarks", "");
                r.put("applicability", "APPLICABLE");
                r.put("characteristic_type", InspUtil.j(c, "characteristic_type").isEmpty() ? "VARIABLE" : InspUtil.j(c, "characteristic_type"));
                out.add(r);
            }
        } catch (Exception e) {
            a.toast(Api.message(e));
        }
        return out;
    }

    // ------------------------------------------------------------------ save
    private void save(Button button) {
        String problem = form.validate();
        if (problem != null) { a.toast(problem); return; }
        if (form.str("prepared_by_employee_id").isEmpty()) { a.toast("Inspected / Prepared By is required."); return; }
        String label = button.getText().toString();
        button.setEnabled(false);
        button.setText("Saving report and layout characteristics…");
        final Attachments.FileData copy = reportCopy;
        Api.async(this::saveNow, (saved, err) -> {
            button.setEnabled(true);
            button.setText(label);
            if (err != null) { a.toast(Api.message(err)); return; }
            String number = InspUtil.j(saved, "report_number");
            String savedId = InspUtil.j(saved, "id");
            if (copy != null) {
                a.toast("Report " + number + " saved · uploading the report copy…");
                Api.async(() -> Attachments.uploadReport(api, "DIMENSIONAL_REPORT", savedId, "REPORT_COPY", copy, "inspection_reports", "attachment_path"), (p, e2) -> {
                    a.toast(e2 != null ? "Report saved, but the report copy upload failed: " + Api.message(e2) : (mode == STANDALONE ? "Standalone " : mode == OSP ? "OSP " : "") + "Dimensional Report " + number + " saved successfully.");
                    openRecord(savedId);
                });
                return;
            }
            a.toast((mode == STANDALONE ? "Standalone " : mode == OSP ? "OSP " : "") + "Dimensional Report " + number + " saved successfully.");
            openRecord(savedId);
        });
    }

    private JSONObject saveNow() throws Exception {
        String number = form.str("report_number");
        if (number.isEmpty()) number = api.nextNumber("qsms_next_document_number", new JSONObject().put("p_sequence_code", "DIMENSIONAL_REPORT"));
        if (number == null || number.isEmpty()) throw new Api.ApiException(500, "QCMS could not generate the Dimensional report number.");
        String prepared = form.str("prepared_by_employee_id");
        JSONObject emp = InspUtil.get(api, "employees", prepared);
        String status = existing == null || InspUtil.j(existing, "status").isEmpty() ? "DRAFT" : InspUtil.j(existing, "status");
        String planId = InspUtil.j(plan, "id");
        JSONObject p = new JSONObject();
        p.put("report_number", number);
        p.put("report_type", "DIMENSIONAL");
        p.put("inspection_plan_id", planId);
        p.put("inspection_stage_id", InspUtil.nzObj(plan.opt("inspection_stage_id")));
        p.put("part_id", partId);
        p.put("inspection_date", form.str("inspection_date"));
        p.put("accepted_quantity", 0);
        p.put("rejected_quantity", 0);
        p.put("overall_result", "NOT_EVALUATED");
        p.put("status", status);
        p.put("remarks", InspUtil.nz(form.str("remarks")));
        p.put("disposition", form.str("disposition").isEmpty() ? "PENDING" : form.str("disposition"));
        p.put("prepared_by_employee_id", prepared);
        p.put("source_layout_revision", InspUtil.nzObj(plan.opt("revision")));
        p.put("layout_name_snapshot", InspUtil.nzObj(plan.opt("layout_name")));
        int samples;
        if (mode == LINKED) {
            samples = clampSamples(form.num("sample_size"));
            p.put("process_id", InspUtil.nzObj(plan.opt("process_id")));
            p.put("inward_lot_id", inwardId);
            p.put("sample_size", samples);
            p.put("inspector", InspUtil.nz(InspUtil.employeeLabel(emp)));
            p.put("disposition_reason", InspUtil.nz(form.str("disposition_reason")));
            p.put("heat_number", InspUtil.nzObj(inward.opt("heat_number")));
            p.put("heat_code", InspUtil.nzObj(inward.opt("heat_code")));
            Double lot = form.num("lot_quantity");
            p.put("lot_quantity", lot == null ? 0.0 : lot);
            p.put("supplier_id", InspUtil.nzObj(inward.opt("supplier_id")));
            p.put("drawing_number", InspUtil.nzObj(part == null ? null : part.opt("drawing_number")));
            p.put("drawing_revision", InspUtil.nzObj(part == null ? null : part.opt("drawing_revision")));
            p.put("layout_type_name", sectionName());
            Object steel = InspUtil.dbl(inward, "steel_quantity_kg") != 0 ? inward.opt("steel_quantity_kg") : inward.opt("quantity_received");
            p.put("steel_quantity_kg", InspUtil.numOrNull(steel));
            p.put("production_quantity_pcs", InspUtil.numOrNull(inward.opt("production_quantity_pcs")));
        } else if (mode == STANDALONE) {
            samples = clampSamples(form.num("sample_size"));
            String processId = group != null && !InspUtil.j(group, "process_id").isEmpty() ? InspUtil.j(group, "process_id") : InspUtil.j(plan, "process_id");
            p.put("process_id", InspUtil.nz(processId));
            p.put("inward_lot_id", JSONObject.NULL);
            p.put("batch_id", JSONObject.NULL);
            p.put("osp_job_id", JSONObject.NULL);
            p.put("sample_size", samples);
            p.put("inspector", InspUtil.nz(InspUtil.employeeLabel(emp)));
            p.put("disposition_reason", InspUtil.nz(form.str("disposition_reason")));
            for (String k : new String[]{"heat_number", "heat_code", "batch_number", "supplier_reference_number", "supply_condition", "reference_text"}) p.put(k, InspUtil.nz(form.str(k)));
            Double lot = form.num("lot_quantity");
            Object lotV = lot == null || lot == 0 ? JSONObject.NULL : (Object) lot;
            p.put("lot_quantity", lotV);
            p.put("production_quantity_pcs", lotV);
            p.put("supplier_id", InspUtil.nz(form.str("supplier_id")));
            p.put("customer_id", InspUtil.nzObj(part == null ? null : part.opt("customer_id")));
            p.put("material_grade_id", InspUtil.nzObj(part == null ? null : part.opt("material_grade_id")));
            p.put("drawing_number", InspUtil.nzObj(part == null ? null : part.opt("drawing_number")));
            p.put("drawing_revision", InspUtil.nzObj(part == null ? null : part.opt("drawing_revision")));
            p.put("layout_type_name", InspUtil.scopeLabel(scope));
            p.put("steel_quantity_kg", JSONObject.NULL);
            p.put("inspection_scope", scope);
            String spec = group != null && !InspUtil.j(group, "process_specification").isEmpty() ? InspUtil.j(group, "process_specification") : InspUtil.j(plan, "remarks");
            p.put("process_specification_snapshot", InspUtil.nz(spec));
            p.put("vendor_batch_number_snapshot", InspUtil.nz(form.str("vendor_batch_number_snapshot")));
        } else {
            samples = 1;
            double qty = "OSP_SAMPLE".equals(scope) ? InspUtil.dbl(job, "sample_quantity") : InspUtil.dbl(job, "quantity_received");
            p.put("osp_job_id", InspUtil.j(job, "id"));
            p.put("batch_id", InspUtil.nzObj(job.opt("osp_batch_id")));
            p.put("process_id", InspUtil.nzObj(job.opt("process_id")));
            p.put("part_id", InspUtil.j(job, "part_id"));
            p.put("inspection_scope", scope);
            p.put("heat_number", InspUtil.nzObj(job.opt("heat_number")));
            p.put("heat_code", InspUtil.nzObj(job.opt("heat_code")));
            p.put("batch_number", InspUtil.nzObj(job.opt("osp_batch_code")));
            p.put("supplier_id", sourceSupplier == null ? JSONObject.NULL : sourceSupplier.opt("id"));
            p.put("layout_type_name", "DIMENSIONAL");
            p.put("production_quantity_pcs", qty);
            p.put("process_specification_snapshot", InspUtil.nzObj(job.opt("process_specification")));
            p.put("vendor_batch_number_snapshot", InspUtil.nzObj(job.opt("vendor_batch_number")));
            p.put("sample_size", 1);
            p.put("lot_quantity", qty);
            p.put("inspector", InspUtil.nz(InspUtil.ospEmployeeLabel(emp)));
        }
        String existingId = existing == null ? null : InspUtil.j(existing, "id");
        JSONObject report = api.save("inspection_reports", existingId, p);
        String rid = InspUtil.j(report, "id");
        if (rid.isEmpty()) throw new Api.ApiException(500, "QCMS did not receive a saved report ID from the database.");
        // rows -> inspection_results (InspectionService.save_dimensional)
        Map<String, String> existingIds = new HashMap<>();
        for (JSONObject r : InspUtil.list(api.rows("inspection_results?select=id,inspection_plan_characteristic_id,sequence_no&inspection_report_id=eq." + Api.enc(rid) + "&limit=2000"))) {
            String key = !InspUtil.j(r, "inspection_plan_characteristic_id").isEmpty() ? InspUtil.j(r, "inspection_plan_characteristic_id") : InspUtil.j(r, "sequence_no");
            existingIds.put(key, InspUtil.j(r, "id"));
        }
        JSONArray resultRows = new JSONArray();
        int pos = 0;
        String section = sectionName();
        for (JSONObject r : readings.rows()) {
            pos++;
            List<String> obs = InspReadings.readings(r);
            JSONArray observations = new JSONArray();
            for (int i = 0; i < samples; i++) observations.put(i < obs.size() ? obs.get(i) : "");
            boolean na = InspReadings.na(r);
            String result = Rules.evaluate(InspUtil.j(r, "characteristic_type").isEmpty() ? "VARIABLE" : InspUtil.j(r, "characteristic_type"),
                InspUtil.j(r, "specification"), Rules.number(r.opt("lower_spec")), Rules.number(r.opt("upper_spec")), obs, na);
            Double seqD = Rules.number(r.opt("sequence_no"));
            int seq = seqD == null || seqD == 0 ? pos : (int) Math.round(seqD);
            String charId = InspUtil.j(r, "inspection_plan_characteristic_id");
            String key = !charId.isEmpty() ? charId : String.valueOf(seq);
            String charNo = InspUtil.j(r, "characteristic_no").isEmpty() ? String.valueOf(seq) : InspUtil.j(r, "characteristic_no");
            JSONObject row = new JSONObject();
            String rowId = existingIds.get(key);
            if (rowId != null && !rowId.isEmpty()) row.put("id", rowId);
            row.put("inspection_report_id", rid);
            row.put("inspection_plan_characteristic_id", InspUtil.nz(charId));
            row.put("sequence_no", seq);
            row.put("characteristic_no", InspUtil.nz(charNo));
            row.put("characteristic", InspUtil.j(r, "characteristic"));
            row.put("specification", InspUtil.nz(InspUtil.j(r, "specification")));
            row.put("lower_spec", InspUtil.numOrNull(r.opt("lower_spec")));
            row.put("upper_spec", InspUtil.numOrNull(r.opt("upper_spec")));
            row.put("unit", InspUtil.nz(InspUtil.j(r, "unit")));
            row.put("checking_aid", InspUtil.nz(InspUtil.j(r, "checking_aid")));
            row.put("observations", observations);
            row.put("attribute_result", JSONObject.NULL);
            row.put("result", result);
            row.put("remarks", InspUtil.nz(InspUtil.j(r, "remarks")));
            row.put("applicability", na ? "NOT_APPLICABLE" : "APPLICABLE");
            row.put("report_section", InspUtil.nz(section));
            row.put("observation_count", Math.max(1, observations.length()));
            resultRows.put(row);
        }
        try {
            api.upsert("inspection_results", resultRows, "id");
        } catch (Exception e) {
            throw new Api.ApiException(500, "Report header " + number + " was saved, but the characteristic readings were not: " + Api.message(e) + " Open the report and save again.");
        }
        Lookups.invalidate();
        return report;
    }

    @Override public boolean onBack() {
        if (form == null || !writable()) return false;
        a.confirm("Leave without saving?", "Readings and changes on this report are not saved.", "Leave", () -> a.back());
        return true;
    }
}
