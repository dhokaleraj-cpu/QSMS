package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Native RMTC Part Worksheet (rmtc_pages.render_part + RMTCService.save_part_worksheet): production plan with the
 * global heat balance, chemistry against the material grade, actual / calculated Jominy, DI (factor table) and the
 * heat-treatment requirements of one covered part. Writes the same rows with the same on_conflict keys, then
 * rpc qsms_evaluate_rmtc.
 */
final class IncRmtcWorksheet extends Screen {
    private final String rid;
    private final String partId;

    private JSONObject header, partApproval, part, grade, heatSummary;
    private List<JSONObject> covered;
    private Map<String, JSONObject> parts;
    private double inputWeight, currentPartInward, currentExistingRemaining, globalHeat, currentCommit, heatInward;

    private FormView plan, di;
    private RowsEditor chem, jom, req;
    private TextView planNote, diNote;
    private Button save;
    private boolean planExceeds = false;
    private boolean saving = false;

    IncRmtcWorksheet(MainActivity a, String rmtcId, String partId) {
        super(a);
        this.rid = rmtcId;
        this.partId = partId;
    }

    @Override public String title() { return "RMTC · Part Worksheet"; }
    @Override public String subtitle() { return header == null ? "Step 2" : Lookups.j(header, "rmtc_number") + " · Heat " + Lookups.j(header, "heat_number"); }
    @Override public int tab() { return Catalog.QUALITY; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(this::load, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            render(res);
        });
        return scroll;
    }

    private Object[] load() throws Exception {
        JSONObject h = IncRmtcData.rmtc(api, rid);
        List<JSONObject> cov = IncRmtcData.coveredParts(api, rid);
        Map<String, JSONObject> p = IncRmtcData.parts(api);
        List<String> ids = new ArrayList<>();
        for (JSONObject r : cov) ids.add(Lookups.j(r, "part_id"));
        IncRmtcData.addMissingParts(api, p, ids);
        JSONObject pa = null;
        for (JSONObject r : cov) if (partId.equals(Lookups.j(r, "part_id"))) pa = r;
        if (pa == null) throw new Api.ApiException(404, "This Part Number is not covered by the RMTC.");
        JSONObject pt = p.get(partId);
        if (pt == null) pt = new JSONObject();
        String gradeId = Lookups.j(pt, "material_grade_id");
        JSONObject g = gradeId.isEmpty() ? null : IncCalc.one(api, "material_grades?select=*&id=eq." + gradeId + "&limit=1");
        String eq = "rmtc_approval_id=eq." + Api.enc(rid) + "&part_id=eq." + Api.enc(partId);
        JSONArray exChem = api.rows("rmtc_chemistry_results?select=*&" + eq + "&order=element.asc&limit=300");
        JSONArray exJom = api.rows("rmtc_jominy_results?select=*&" + eq + "&order=distance_mm.asc&limit=300");
        JSONArray exReq = api.rows("rmtc_requirement_results?select=*&" + eq + "&order=sequence_no.asc&limit=300");
        JSONArray chemT = gradeId.isEmpty() ? new JSONArray() : api.rows("material_grade_elements?select=*&material_grade_id=eq." + gradeId + "&order=element.asc&limit=200");
        List<JSONObject> jomT = IncRmtcData.jominyTemplate(api, partId);
        JSONArray reqT = api.rows("part_heat_treatment_details?select=*&part_id=eq." + Api.enc(partId) + "&status=eq.ACTIVE&order=sequence_no.asc&limit=200");
        JSONArray src = IncRmtcData.sourceDetails(api, partId);
        JSONObject hs = IncRmtcData.heatSummary(api, Lookups.j(h, "heat_number"));
        List<JSONObject> usage = IncRmtcData.heatUsage(api, Lookups.j(h, "heat_number"));
        return new Object[]{h, cov, p, pa, pt, g, exChem, exJom, exReq, chemT, jomT, reqT, src, hs, usage};
    }

    private static Map<String, JSONObject> by(JSONArray rows, String key) {
        Map<String, JSONObject> m = new LinkedHashMap<>();
        for (JSONObject r : IncCalc.list(rows)) m.put(Lookups.j(r, key), r);
        return m;
    }

    private static List<String[]> cols(String[][] c) { return new ArrayList<>(Arrays.asList(c)); }

    @SuppressWarnings("unchecked")
    private void render(Object[] r) {
        header = (JSONObject) r[0];
        covered = (List<JSONObject>) r[1];
        parts = (Map<String, JSONObject>) r[2];
        partApproval = (JSONObject) r[3];
        part = (JSONObject) r[4];
        grade = r[5] == null ? new JSONObject() : (JSONObject) r[5];
        Map<String, JSONObject> exChem = by((JSONArray) r[6], "material_grade_element_id");
        Map<String, JSONObject> exJom = by((JSONArray) r[7], "jominy_distance_id");
        Map<String, JSONObject> exReq = by((JSONArray) r[8], "source_requirement_id");
        JSONArray chemT = (JSONArray) r[9];
        List<JSONObject> jomT = (List<JSONObject>) r[10];
        JSONArray reqT = (JSONArray) r[11];
        JSONArray src = (JSONArray) r[12];
        heatSummary = (JSONObject) r[13];
        List<JSONObject> usage = (List<JSONObject>) r[14];
        a.rebuildTitle(this);

        // ---- part selector
        if (covered.size() > 1) {
            int done = 0;
            for (JSONObject c : covered) if (!Lookups.j(c, "worksheet_completed_at").isEmpty()) done++;
            Button pick = Ui.outline(a, "Part Worksheet: " + IncRmtcData.partLabel(parts, partId) + "  ▾  (" + done + "/" + covered.size() + " done)", Ui.TEAL);
            pick.setOnClickListener(v -> {
                List<String> ids = new ArrayList<>(), names = new ArrayList<>();
                for (JSONObject c : covered) {
                    String pid = Lookups.j(c, "part_id");
                    ids.add(pid);
                    names.add(IncRmtcData.partLabel(parts, pid) + (Lookups.j(c, "worksheet_completed_at").isEmpty() ? " · PENDING" : " · COMPLETED"));
                }
                plan.choose("Part Worksheet", ids, names, pid -> { if (!pid.equals(partId)) a.replaceTop(new IncRmtcWorksheet(a, rid, pid)); });
            });
            add(pick, 0);
        }

        // ---- A part & material
        add(Ui.label(a, "A · PART & MATERIAL"), 10);
        LinearLayout card = Ui.card(a);
        card.addView(Ui.pair(a, "RMTC", Lookups.j(header, "rmtc_number")));
        card.addView(Ui.pair(a, "Heat Number", Lookups.j(header, "heat_number")));
        card.addView(Ui.pair(a, "Internal Heat Code", Lookups.j(header, "heat_code")));
        card.addView(Ui.pair(a, "Part Number", Lookups.j(part, "part_number")));
        card.addView(Ui.pair(a, "FSI Part Number", Lookups.j(part, "fsi_part_number")));
        card.addView(Ui.pair(a, "Part Description", Lookups.j(part, "part_name")));
        card.addView(Ui.pair(a, "Material Grade", Lookups.j(grade, "grade_code")));
        card.addView(Ui.pair(a, "Status", Ui.pretty(Lookups.j(header, "status"))));
        card.addView(Ui.pair(a, "Worksheet", Lookups.j(partApproval, "worksheet_completed_at").isEmpty() ? "Pending" : "Completed " + Ui.date(Lookups.j(partApproval, "worksheet_completed_at"))));
        add(card, 2);

        // ---- B production plan
        JSONObject production = new JSONObject();
        for (JSONObject s : IncCalc.list(src)) if (Lookups.j(s, "supplier_id").equals(Lookups.j(header, "supplier_id"))) { production = s; break; }
        double w = IncCalc.f(partApproval.opt("input_weight_kg"));
        inputWeight = w != 0 ? w : IncCalc.first(production, "input_weight_kg", "gross_weight_kg", "forging_weight_kg");
        JSONObject currentUsage = new JSONObject();
        for (JSONObject u : usage) if (Lookups.j(u, "rmtc_part_approval_id").equals(Lookups.j(partApproval, "id"))) { currentUsage = u; break; }
        currentPartInward = IncCalc.f(currentUsage.opt("inward_steel_quantity_kg"));
        currentExistingRemaining = IncCalc.remainingPlanned(partApproval.opt("planned_steel_quantity_kg"), currentPartInward);
        globalHeat = IncCalc.first(heatSummary, "global_steel_quantity_kg");
        if (globalHeat == 0) globalHeat = IncCalc.f(header.opt("certificate_quantity"));
        currentCommit = IncCalc.f(heatSummary.opt("committed_steel_quantity_kg"));
        heatInward = IncCalc.f(heatSummary.opt("inward_steel_quantity_kg"));

        add(Ui.label(a, "B · PRODUCTION PLAN"), 14);
        add(Ui.text(a, "Committed Heat steel equals inward steel already used plus the still-unconsumed portion of every active part plan.", 11.5f, Ui.MUTED, false), 2);
        plan = new FormView(a, Arrays.asList(
            Field.number("planned_production_quantity_pcs", "Part Production Quantity (pcs)").req().range(0, Double.MAX_VALUE),
            Field.info("input_weight", "Input Weight (kg/part)"),
            Field.info("planned_steel", "Planned Steel Quantity (kg)"),
            Field.info("heat_balance", "Heat Steel Balance after Plan (kg)")));
        add(plan, 4);
        planNote = Ui.text(a, "", 12, Ui.MUTED, false);
        add(planNote, 4);
        double plannedExisting = IncCalc.f(partApproval.opt("planned_production_quantity_pcs"));
        plan.set("planned_production_quantity_pcs", plannedExisting == 0 ? "" : Ui.num(plannedExisting, 3).replace(",", ""));
        plan.set("input_weight", Ui.num(inputWeight, 3));
        plan.onChange((k, v) -> { if ("planned_production_quantity_pcs".equals(k)) updatePlan(); });
        updatePlan();

        // ---- C chemistry
        add(Ui.label(a, "C · CHEMICAL COMPOSITION"), 14);
        add(Ui.text(a, "Limits come from this Part Master material grade. Actual values are entered from the RMTC. Tap a row to enter the actual value.", 11.5f, Ui.MUTED, false), 2);
        List<JSONObject> chemRows = new ArrayList<>();
        for (JSONObject t : IncCalc.list(chemT)) {
            JSONObject old = exChem.get(Lookups.j(t, "id"));
            JSONObject row = new JSONObject();
            try {
                row.put("material_grade_element_id", t.opt("id"));
                row.put("element", IncCalc.jo(t, "element"));
                row.put("minimum_value", IncCalc.jo(t, "minimum"));
                row.put("maximum_value", IncCalc.jo(t, "maximum"));
                row.put("unit", IncCalc.firstText(Lookups.j(t, "unit"), "%"));
                row.put("actual_value", old == null ? JSONObject.NULL : IncCalc.jo(old, "actual_value"));
                row.put("applicable", old == null || !Rules.NOT_APPLICABLE.equals(Lookups.j(old, "result")));
                if (old != null) row.put("_existing_id", old.opt("id"));
            } catch (Exception ignored) { }
            chemRows.add(row);
        }
        chem = new RowsEditor(a, "Chemistry", Arrays.asList(
            Field.info("element", "Element"), Field.info("minimum_value", "Minimum %"), Field.info("maximum_value", "Maximum %"),
            Field.number("actual_value", "Actual %"), Field.bool("applicable", "Applicable")),
            cols(new String[][]{{"element", "Element"}, {"minimum_value", "Minimum %"}, {"maximum_value", "Maximum %"}, {"actual_value", "Actual %"},
                {"applicable", "Applicable"}, {"result", "Status"}})).fixedRows();
        chem.setRows(chemRows);
        add(chem, 4);
        if (chemRows.isEmpty()) add(Ui.text(a, "No chemistry limits exist for this material grade in Masters.", 12, Ui.AMBER_FG, false), 2);

        // ---- D jominy
        add(Ui.label(a, "D · JOMINY RESULTS"), 14);
        add(Ui.text(a, "Actual Jominy, Actual Status, Calculated Jominy (JUST.xls formulas from the chemistry) and Calculated Status.", 11.5f, Ui.MUTED, false), 2);
        List<JSONObject> jomRows = new ArrayList<>();
        for (JSONObject t : jomT) {
            JSONObject old = exJom.get(Lookups.j(t, "jominy_distance_id"));
            JSONObject row = new JSONObject();
            try {
                row.put("jominy_distance_id", IncCalc.jo(t, "jominy_distance_id"));
                row.put("distance_label", IncCalc.jo(t, "distance_label"));
                row.put("distance_mm", IncCalc.jo(t, "distance_mm"));
                row.put("distance_16th", t.optInt("distance_16th", 0));
                row.put("minimum_hrc", IncCalc.jo(t, "minimum_hrc"));
                row.put("maximum_hrc", IncCalc.jo(t, "maximum_hrc"));
                row.put("actual_hrc", old == null ? JSONObject.NULL : IncCalc.jo(old, "actual_hrc"));
                row.put("applicable", old == null || !"NOT_APPLICABLE".equals(IncCalc.firstText(Lookups.j(old, "applicability"), "APPLICABLE")));
                if (old != null) row.put("_existing_id", old.opt("id"));
            } catch (Exception ignored) { }
            jomRows.add(row);
        }
        jom = new RowsEditor(a, "Jominy", Arrays.asList(
            Field.info("distance_label", "Distance"), Field.info("distance_mm", "MM"), Field.info("minimum_hrc", "Min HRC"), Field.info("maximum_hrc", "Max HRC"),
            Field.number("actual_hrc", "Actual Jominy (HRC)"), Field.bool("applicable", "Applicable")),
            cols(new String[][]{{"distance_label", "Distance"}, {"distance_mm", "MM"}, {"minimum_hrc", "Min HRC"}, {"maximum_hrc", "Max HRC"},
                {"actual_hrc", "Actual Jominy"}, {"result", "Actual Jominy Status"}, {"calculated_hrc", "Calculated Jominy"},
                {"calculated_result", "Calculated Jominy Status"}, {"applicable", "Applicable"}})).fixedRows();
        jom.setRows(jomRows);
        add(jom, 4);
        if (jomRows.isEmpty()) add(Ui.text(a, "No Jominy requirements exist for this Part in Part Master.", 12, Ui.MUTED, false), 2);

        // ---- E DI
        add(Ui.label(a, "E · DI VALUE"), 14);
        add(Ui.text(a, "Actual and calculated DI use the supplied DI Hardenability workbook factor table.", 11.5f, Ui.MUTED, false), 2);
        di = new FormView(a, Arrays.asList(
            Field.select("grain_size", "Grain Size (ASTM E-112)", "4", "5", "6", "7", "8").req(),
            Field.bool("di_applicable", "DI Applicable"),
            Field.number("actual_di", "Actual DI").range(0, Double.MAX_VALUE)));
        add(di, 4);
        int grain = (int) IncCalc.f(partApproval.opt("grain_size"));
        di.set("grain_size", String.valueOf(grain >= 4 && grain <= 8 ? grain : 6));
        di.set("di_applicable", !"NOT_APPLICABLE".equals(Lookups.j(partApproval, "calculated_di_status")));
        di.set("actual_di", Ui.num(IncCalc.f(partApproval.opt("actual_di")), 4).replace(",", ""));
        diNote = Ui.text(a, "", 12.5f, Ui.TEXT, true);
        add(diNote, 4);
        di.onChange((k, v) -> recalc());

        // ---- F requirements
        add(Ui.label(a, "F · HEAT TREATMENT & OTHER REQUIREMENTS"), 14);
        add(Ui.text(a, "Not Applicable is available and does not block Draft saving.", 11.5f, Ui.MUTED, false), 2);
        List<JSONObject> reqRows = new ArrayList<>();
        for (JSONObject t : IncCalc.list(reqT)) {
            JSONObject old = exReq.get(Lookups.j(t, "id"));
            JSONObject row = new JSONObject();
            try {
                row.put("source_requirement_id", t.opt("id"));
                row.put("requirement_name", IncCalc.jo(t, "parameter_name"));
                row.put("requirement_value", IncCalc.jo(t, "requirement_value"));
                row.put("actual_value", old == null ? "" : Lookups.j(old, "actual_value"));
                row.put("applicable", old == null || !Rules.NOT_APPLICABLE.equals(Lookups.j(old, "result")));
                row.put("sequence_no", IncCalc.jo(t, "sequence_no"));
            } catch (Exception ignored) { }
            reqRows.add(row);
        }
        req = new RowsEditor(a, "Requirements", Arrays.asList(
            Field.info("requirement_name", "Property / Requirement"), Field.info("requirement_value", "Part Master Value"),
            Field.text("actual_value", "RMTC Actual / Observation"), Field.bool("applicable", "Applicable")),
            cols(new String[][]{{"requirement_name", "Property / Requirement"}, {"requirement_value", "Part Master Value"},
                {"actual_value", "RMTC Actual / Observation"}, {"applicable", "Applicable"}, {"result", "Status"}})).fixedRows();
        req.setRows(reqRows);
        add(req, 4);

        chem.onChanged(this::recalc);
        jom.onChanged(this::recalc);
        req.onChanged(this::recalc);
        recalc();

        save = Ui.primary(a, "Save Part Worksheet");
        add(save, 18);
        save.setOnClickListener(v -> save());
    }

    private void updatePlan() {
        double pcs = IncCalc.f(plan.num("planned_production_quantity_pcs"));
        double plannedSteel = IncCalc.round(pcs * inputWeight, 3);
        double projectedCurrent = IncCalc.remainingPlanned(plannedSteel, currentPartInward);
        double projected = IncCalc.round(Math.max(currentCommit - currentExistingRemaining, 0.0) + projectedCurrent, 3);
        double heatRemaining = Math.max(globalHeat - projected, 0.0);
        plan.set("planned_steel", Ui.num(plannedSteel, 3));
        plan.set("heat_balance", Ui.num(heatRemaining, 3));
        planExceeds = projected > globalHeat + 0.001;
        String text = "Projected committed Heat steel: " + IncCalc.kg(projected) + " = Inward " + IncCalc.kg(heatInward)
            + " + Remaining active plans " + IncCalc.kg(Math.max(projected - heatInward, 0.0)) + ".";
        if (inputWeight <= 0) {
            text = "Input Weight is missing in Part Master supplier forging parameters.\n" + text;
            planNote.setTextColor(Ui.RED_FG);
        } else if (planExceeds) {
            text = "Committed Heat steel " + IncCalc.kg(projected) + " exceeds the Global Heat steel quantity " + IncCalc.kg(globalHeat) + ".\n" + text;
            planNote.setTextColor(Ui.RED_FG);
        } else {
            planNote.setTextColor(Ui.MUTED);
        }
        planNote.setText(text);
    }

    /** Chemistry map of the website page/service: element -> actual for rows that are not "Not Applicable". */
    private Map<String, Object> chemistryMap() {
        Map<String, Object> m = new LinkedHashMap<>();
        for (JSONObject row : chem.rows()) {
            if (!row.optBoolean("applicable", true)) continue;
            Object v = row.opt("actual_value");
            m.put(Lookups.j(row, "element").trim(), v == null || v == JSONObject.NULL ? null : v);
        }
        return m;
    }

    private int grain() {
        try { return Integer.parseInt(di.str("grain_size")); } catch (Exception e) { return 6; }
    }

    private void recalc() {
        try {
            for (JSONObject row : chem.rows()) {
                row.put("result", IncCalc.band(row.opt("actual_value"), row.opt("minimum_value"), row.opt("maximum_value"), row.optBoolean("applicable", true)));
            }
            Map<String, Object> cm = chemistryMap();
            Map<Integer, Double> curve = IncCalc.jominyCurve(cm);
            for (JSONObject row : jom.rows()) {
                boolean app = row.optBoolean("applicable", true);
                int d = row.optInt("distance_16th", 0);
                Double calc = app ? curve.get(d) : null;
                row.put("calculated_hrc", IncCalc.jn(calc));
                row.put("result", IncCalc.band(row.opt("actual_hrc"), row.opt("minimum_hrc"), row.opt("maximum_hrc"), app));
                row.put("calculated_result", IncCalc.band(calc, row.opt("minimum_hrc"), row.opt("maximum_hrc"), app));
            }
            for (JSONObject row : req.rows()) {
                row.put("result", IncCalc.requirement(Lookups.j(row, "actual_value"), Lookups.j(row, "requirement_value"), row.optBoolean("applicable", true)));
            }
            chem.refresh();
            jom.refresh();
            req.refresh();
            boolean diApp = di.bool("di_applicable");
            if (diApp) {
                IncCalc.Di d = IncCalc.calculateDi(cm, grain());
                diNote.setText("Grain Size " + grain() + " · Actual DI " + Ui.num(IncCalc.f(di.num("actual_di")), 4) + " · Calculated DI "
                    + (d.value == null ? "-" : Ui.num(d.value, 4)) + "\n" + (d.error != null ? d.error : "DI Hardenability.XLSX factor product"));
                diNote.setTextColor(d.error != null ? Ui.AMBER_FG : Ui.TEXT);
            } else {
                diNote.setText("DI not applicable for this Part Worksheet.");
                diNote.setTextColor(Ui.MUTED);
            }
        } catch (Exception e) {
            diNote.setText(Api.message(e));
        }
    }

    // ------------------------------------------------------------------ save (RMTCService.save_part_worksheet)
    private void save() {
        if (saving) return;
        String problem = plan.validate();
        if (problem == null) problem = di.validate();
        double pcs = IncCalc.f(plan.num("planned_production_quantity_pcs"));
        if (problem == null && pcs <= 0) problem = "Part Production Quantity is mandatory and must be greater than zero.";
        if (problem == null && inputWeight <= 0) problem = "Input Weight is missing in Part Master supplier forging parameters.";
        if (problem == null && planExceeds) problem = "The planned steel exceeds the Global Heat steel quantity. Reduce the Part Production Quantity.";
        if (problem != null) { a.toast(problem); return; }
        recalc();
        final int grain = grain();
        final boolean diApp = di.bool("di_applicable");
        final Double actualDi = diApp ? Double.valueOf(IncCalc.f(di.num("actual_di"))) : null;
        final List<JSONObject> chemRows = new ArrayList<>(chem.rows());
        final List<JSONObject> jomRows = new ArrayList<>(jom.rows());
        final List<JSONObject> reqRows = new ArrayList<>(req.rows());
        final double weightIn = inputWeight;
        saving = true;
        save.setEnabled(false);
        save.setText("Saving Part Worksheet…");
        Api.async(() -> {
            Map<String, Object> cm = new LinkedHashMap<>();
            for (JSONObject row : chemRows) if (!Rules.NOT_APPLICABLE.equals(Lookups.j(row, "result"))) {
                Object v = row.opt("actual_value");
                cm.put(Lookups.j(row, "element").trim(), v == JSONObject.NULL ? null : v);
            }
            Map<Integer, Double> curve = IncCalc.jominyCurve(cm);
            IncCalc.Di diRes = IncCalc.calculateDi(cm, grain);

            JSONArray chemPayload = new JSONArray();
            for (JSONObject row : chemRows) {
                JSONObject o = new JSONObject();
                if (row.has("_existing_id") && !row.isNull("_existing_id")) o.put("id", row.get("_existing_id"));
                o.put("rmtc_approval_id", rid);
                o.put("part_id", partId);
                o.put("material_grade_element_id", IncCalc.jo(row, "material_grade_element_id"));
                o.put("element", IncCalc.jo(row, "element"));
                o.put("minimum_value", IncCalc.jo(row, "minimum_value"));
                o.put("maximum_value", IncCalc.jo(row, "maximum_value"));
                o.put("actual_value", IncCalc.jo(row, "actual_value"));
                o.put("unit", IncCalc.firstText(Lookups.j(row, "unit"), "%"));
                o.put("result", IncCalc.firstText(Lookups.j(row, "result"), Rules.NOT_EVALUATED));
                o.put("remarks", JSONObject.NULL);
                chemPayload.put(o);
            }
            normaliseIds(chemPayload);
            api.upsert("rmtc_chemistry_results", chemPayload, "tenant_id,rmtc_approval_id,part_id,material_grade_element_id");

            JSONArray jomPayload = new JSONArray();
            for (JSONObject row : jomRows) {
                boolean app = row.optBoolean("applicable", true);
                int d = row.optInt("distance_16th", 0);
                Double calc = app ? curve.get(d) : null;
                JSONObject o = new JSONObject();
                if (row.has("_existing_id") && !row.isNull("_existing_id")) o.put("id", row.get("_existing_id"));
                o.put("rmtc_approval_id", rid);
                o.put("part_id", partId);
                o.put("jominy_distance_id", IncCalc.jo(row, "jominy_distance_id"));
                o.put("distance_label", IncCalc.jo(row, "distance_label"));
                o.put("distance_mm", d != 0 ? IncCalc.round(d * 25.4 / 16, 2) : 0);
                o.put("actual_hrc", IncCalc.jo(row, "actual_hrc"));
                o.put("result", IncCalc.band(row.opt("actual_hrc"), row.opt("minimum_hrc"), row.opt("maximum_hrc"), app));
                o.put("calculated_hrc", IncCalc.jn(calc));
                o.put("calculated_result", IncCalc.band(calc, row.opt("minimum_hrc"), row.opt("maximum_hrc"), app));
                o.put("applicability", app ? "APPLICABLE" : "NOT_APPLICABLE");
                o.put("remarks", JSONObject.NULL);
                jomPayload.put(o);
            }
            normaliseIds(jomPayload);
            api.upsert("rmtc_jominy_results", jomPayload, "tenant_id,rmtc_approval_id,part_id,jominy_distance_id");

            Map<String, JSONObject> existingReq = new LinkedHashMap<>();
            for (JSONObject e : IncCalc.list(api.rows("rmtc_requirement_results?select=id,source_requirement_id&rmtc_approval_id=eq." + Api.enc(rid) + "&part_id=eq." + Api.enc(partId) + "&limit=500")))
                existingReq.put(Lookups.j(e, "source_requirement_id"), e);
            JSONArray reqPayload = new JSONArray();
            for (JSONObject row : reqRows) {
                JSONObject ex = existingReq.get(Lookups.j(row, "source_requirement_id"));
                JSONObject o = new JSONObject();
                o.put("id", ex != null ? ex.optString("id") : java.util.UUID.randomUUID().toString());
                o.put("rmtc_approval_id", rid);
                o.put("part_id", partId);
                o.put("requirement_source", "PART_HEAT_TREATMENT");
                o.put("source_requirement_id", IncCalc.jo(row, "source_requirement_id"));
                o.put("requirement_code", IncCalc.jo(row, "requirement_name"));
                o.put("requirement_name", IncCalc.jo(row, "requirement_name"));
                o.put("requirement_value", IncCalc.jo(row, "requirement_value"));
                o.put("actual_value", Lookups.j(row, "actual_value"));
                o.put("unit", JSONObject.NULL);
                o.put("result", IncCalc.firstText(Lookups.j(row, "result"), Rules.NOT_EVALUATED));
                Double seq = IncCalc.num(row.opt("sequence_no"));
                o.put("sequence_no", seq == null || seq == 0 ? 10 : (Object) seq.intValue());
                o.put("remarks", JSONObject.NULL);
                reqPayload.put(o);
            }
            api.upsert("rmtc_requirement_results", reqPayload, "id");

            JSONObject diReq = null;
            for (JSONObject row : reqRows) if (Lookups.j(row, "requirement_name").toUpperCase(java.util.Locale.ROOT).contains("DI")) { diReq = row; break; }
            Double[] range = IncCalc.range(diReq == null ? "" : Lookups.j(diReq, "requirement_value"));
            Double calculatedDi = diApp ? diRes.value : null;
            String actualStatus = IncCalc.band(actualDi, range[0], range[1], diApp);
            String calculatedStatus = IncCalc.band(calculatedDi, range[0], range[1], diApp);
            JSONObject partRow = IncCalc.one(api, "rmtc_part_approvals?select=id,input_weight_kg&rmtc_approval_id=eq." + Api.enc(rid) + "&part_id=eq." + Api.enc(partId) + "&limit=1");
            double weight = weightIn != 0 ? weightIn : IncCalc.f(partRow == null ? null : partRow.opt("input_weight_kg"));
            double plannedSteel = IncCalc.round(pcs * weight, 3);
            JSONObject updates = new JSONObject();
            updates.put("grain_size", grain);
            updates.put("actual_di", IncCalc.jn(actualDi));
            updates.put("calculated_di", IncCalc.jn(calculatedDi));
            updates.put("actual_di_status", actualStatus);
            updates.put("calculated_di_status", calculatedStatus);
            updates.put("planned_production_quantity_pcs", pcs);
            updates.put("input_weight_kg", weight != 0 ? (Object) weight : JSONObject.NULL);
            updates.put("planned_steel_quantity_kg", plannedSteel);
            updates.put("worksheet_completed_at", OffsetDateTime.now(ZoneOffset.UTC).toString());
            updates.put("worksheet_completed_by", api.userId.isEmpty() ? JSONObject.NULL : api.userId);
            if (partRow != null) api.update("rmtc_part_approvals", partRow.getString("id"), updates);
            api.rpc("qsms_evaluate_rmtc", new JSONObject().put("p_rmtc_id", rid));
            List<String> pending = new ArrayList<>();
            for (JSONObject c : IncRmtcData.coveredParts(api, rid)) if (Lookups.j(c, "worksheet_completed_at").isEmpty()) pending.add(Lookups.j(c, "part_id"));
            return new Object[]{diRes.value, pending};
        }, (res, err) -> {
            saving = false;
            save.setEnabled(true);
            save.setText("Save Part Worksheet");
            if (err != null) { a.toast("Part Worksheet not saved: " + Api.message(err)); return; }
            @SuppressWarnings("unchecked") List<String> pending = (List<String>) res[1];
            String diText = res[0] == null ? "None" : String.valueOf(res[0]);
            if (!pending.isEmpty()) {
                a.toast("Part Worksheet saved. Calculated DI: " + diText + ". Continue with the next Part Number.");
                a.replaceTop(new IncRmtcWorksheet(a, rid, pending.get(0)));
            } else {
                a.toast("All Part Worksheets are saved. Calculated DI: " + diText + ". Next: Validation & Decision on the RMTC record.");
                a.back();
            }
        });
    }

    /** Every row of one bulk upsert must carry the same keys (PostgREST): give new rows a fresh id. */
    private static void normaliseIds(JSONArray rows) throws Exception {
        for (int i = 0; i < rows.length(); i++) {
            JSONObject o = rows.getJSONObject(i);
            if (!o.has("id")) o.put("id", java.util.UUID.randomUUID().toString());
        }
    }

    @Override public boolean onBack() {
        if (save == null) return false;
        a.confirm("Leave the worksheet?", "Values entered on this Part Worksheet are not saved.", "Leave", () -> a.back());
        return true;
    }
}
