package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * R33 · Builds the website's controlled reports (core/reporting.py) for the app, from the same Supabase rows the
 * website reads (InspectionService.metlab_report_payload, dimensional_report_payload, RmtcService.report_payload,
 * MaterialInwardService.report_payload, complaints / calibration / standard room / QC calculation PDFs).
 * Every other record prints as the website's Universal Record PDF (controlled_record_pdf_bytes).
 */
final class RptReports {
    private RptReports() { }

    // ------------------------------------------------------------------ entry points
    /** True when the table has a dedicated website print layout. */
    static boolean dedicated(String table) {
        switch (table) {
            case "lab_tests": case "inspection_reports": case "rmtc_approvals": case "inward_lots":
            case "quality_complaints": case "quality_asset_calibration_records": case "standard_room_inspection_records":
            case "qc_calculation_records":
                return true;
            default: return false;
        }
    }

    /** Report of one record in the website's print layout (dedicated layout, else Universal Record PDF). Runs off the UI thread. */
    static RptDoc forRecord(Api api, Module m, String id) throws Exception {
        switch (m.table) {
            case "lab_tests": return metlab(api, id);
            case "inspection_reports": return dimensional(api, id);
            case "rmtc_approvals": return rmtc(api, id);
            case "inward_lots": return inward(api, id);
            case "quality_complaints": return complaint(api, id);
            case "quality_asset_calibration_records": return calibration(api, id);
            case "standard_room_inspection_records": return standardRoom(api, id);
            case "qc_calculation_records": return qcCalculation(api, id);
            default: return universal(api, m, id);
        }
    }

    // ------------------------------------------------------------------ data helpers
    static JSONObject one(Api api, String table, Object id) {
        String s = str(id);
        if (s.isEmpty()) return new JSONObject();
        try {
            JSONArray r = api.rows(table + "?select=*&id=eq." + Api.enc(s) + "&limit=1");
            return r.length() > 0 ? r.getJSONObject(0) : new JSONObject();
        } catch (Exception e) {
            return new JSONObject();
        }
    }

    static List<JSONObject> list(Api api, String path) {
        List<JSONObject> out = new ArrayList<>();
        try {
            JSONArray r = api.rows(path);
            for (int i = 0; i < r.length(); i++) { JSONObject o = r.optJSONObject(i); if (o != null) out.add(o); }
        } catch (Exception ignored) { }
        return out;
    }

    static List<JSONObject> list(JSONArray a) {
        List<JSONObject> out = new ArrayList<>();
        if (a != null) for (int i = 0; i < a.length(); i++) { JSONObject o = a.optJSONObject(i); if (o != null) out.add(o); }
        return out;
    }

    static Map<String, JSONObject> employees(Api api, Object... ids) {
        Map<String, JSONObject> out = new HashMap<>();
        List<String> want = new ArrayList<>();
        for (Object id : ids) { String s = str(id); if (!s.isEmpty() && !want.contains(s)) want.add(s); }
        if (want.isEmpty()) return out;
        for (JSONObject e : list(api, "employees?select=*&id=in.(" + String.join(",", want) + ")&limit=20")) out.put(str(e.opt("id")), e);
        return out;
    }

    /** _employee_name: "code - first last", else name / code, else "-". */
    static String emp(Map<String, JSONObject> emps, Object id) {
        JSONObject e = emps.get(str(id));
        if (e == null) return "-";
        String name = (str(e.opt("first_name")) + " " + str(e.opt("last_name"))).trim();
        String code = str(e.opt("employee_code"));
        if (!code.isEmpty() && !name.isEmpty()) return code + " - " + name;
        return !name.isEmpty() ? name : !code.isEmpty() ? code : "-";
    }

    static String str(Object o) { return o == null || o == JSONObject.NULL ? "" : String.valueOf(o).trim(); }

    /** Python truthiness (None, "", 0, False, empty list / dict are false). */
    static boolean truthy(Object o) {
        if (o == null || o == JSONObject.NULL) return false;
        if (o instanceof Boolean) return (Boolean) o;
        if (o instanceof Number) return ((Number) o).doubleValue() != 0;
        if (o instanceof JSONArray) return ((JSONArray) o).length() > 0;
        if (o instanceof JSONObject) return ((JSONObject) o).length() > 0;
        return !String.valueOf(o).isEmpty();
    }

    /** a or b or c … */
    static Object or(Object... values) {
        for (Object v : values) if (truthy(v)) return v;
        return values.length == 0 ? null : values[values.length - 1];
    }

    static Object g(JSONObject o, String k) { return o == null ? null : o.opt(k); }

    static String v(Object o) { return RptDoc.v(o); }
    static String raw(Object o) { return RptDoc.raw(o); }
    static String dash(Object o) { String s = raw(o); return s.isEmpty() ? "-" : s; }

    private static String plant;

    static void theme(Api api, RptDoc d, String doc) {
        d.layoutDoc = doc;
        try { d.applyLayout(AdmPrint.read(api, doc)); } catch (Exception ignored) { }
        if (plant == null) {
            plant = "D9";
            JSONObject t = list(api, "tenants?select=plant_code&limit=1").stream().findFirst().orElse(null);
            if (t != null && !str(t.opt("plant_code")).isEmpty()) plant = str(t.opt("plant_code"));
        }
        d.plantCode = plant;
    }

    /** Microstructure / evidence photographs of a report (one per slot, newest file of each type). */
    static List<RptDoc.Photo> slotPhotos(Api api, String entity, String id, String typePrefix, JSONObject record, int slots) {
        Map<String, JSONObject> byType = new HashMap<>();
        for (JSONObject a : list(api, "document_attachments?select=*&entity_type=eq." + entity + "&entity_id=eq." + Api.enc(id)
            + "&status=eq.ACTIVE&order=created_at.asc&limit=250")) byType.put(str(a.opt("document_type")), a);
        List<RptDoc.Photo> out = new ArrayList<>();
        for (int s = 1; s <= slots; s++) {
            JSONObject a = byType.get(typePrefix + s);
            byte[] data = null;
            if (a != null) { try { data = api.download(str(a.opt("object_path"))); } catch (Exception ignored) { } }
            String cap = str(record.opt("microstructure_caption_" + s));
            out.add(new RptDoc.Photo(cap.isEmpty() ? "Microstructure Photo " + s : cap, data));
        }
        return out;
    }

    static float[] f(float... v) { return v; }

    static String[] row(Object... cells) {
        String[] r = new String[cells.length];
        for (int i = 0; i < cells.length; i++) r[i] = cells[i] instanceof String ? (String) cells[i] : raw(cells[i]);
        return r;
    }

    /** Label / value rows: values through _display_value like _rmtc_labeled_grid. */
    static String[] vrow(Object... cells) {
        String[] r = new String[cells.length];
        for (int i = 0; i < cells.length; i++) r[i] = v(cells[i]);
        return r;
    }

    static String[][] rows(List<String[]> l) { return l.toArray(new String[0][]); }

    // ================================================================== MetLAB (metlab_record_pdf_bytes)
    static RptDoc metlab(Api api, String id) throws Exception {
        JSONObject record = one(api, "lab_tests", id);
        if (record.length() == 0) throw new Api.ApiException(404, "MetLAB report not found.");
        JSONObject results = record.optJSONObject("results");
        if (results == null) results = new JSONObject();
        if (rawMaterial(record)) results = rawMaterialResults(api, record, results);
        JSONObject part = one(api, "parts", record.opt("part_id"));
        JSONObject inward = one(api, "inward_lots", record.opt("inward_lot_id"));
        JSONObject supplier = one(api, "parties", or(record.opt("supplier_id"), inward.opt("supplier_id")));
        JSONObject grade = one(api, "material_grades", or(record.opt("material_grade_id"), part.opt("material_grade_id")));
        JSONObject customer = one(api, "parties", or(record.opt("customer_id"), part.opt("customer_id")));
        JSONObject process = one(api, "processes", record.opt("process_id"));
        JSONObject stage = one(api, "inspection_stages", record.opt("inspection_stage_id"));
        JSONObject osp = new JSONObject();
        if (truthy(record.opt("osp_job_id"))) {
            List<JSONObject> o = list(api, "v_qsms_osp_register?select=*&id=eq." + Api.enc(str(record.opt("osp_job_id"))) + "&limit=1");
            if (!o.isEmpty()) osp = o.get(0);
        }
        JSONObject ospVendor = one(api, "parties", or(record.opt("osp_vendor_id"), osp.opt("vendor_id")));
        Map<String, JSONObject> emps = employees(api, record.opt("prepared_by_employee_id"), record.opt("validated_by_employee_id"), record.opt("approved_by_employee_id"));
        List<RptDoc.Photo> photos = slotPhotos(api, "METLAB_REPORT", id, "MICROSTRUCTURE_", record, 4);
        String method = str(or(results.opt("inspection_method"), "GENERAL_METLAB")).toUpperCase(Locale.ROOT);
        if ("BEND_TEST".equals(method)) return bend(api, record, part, customer, grade, inward, osp, emps, results, photos);

        String scope = str(or(record.opt("inspection_scope"), "MATERIAL_INWARD"));
        boolean isOsp = scope.startsWith("OSP_") || truthy(record.opt("osp_job_id"));
        String title = isOsp ? "OSP METALLURGICAL TEST REPORT" : "FINAL_DISPATCH_STAGE".equals(scope) ? "FINAL METALLURGICAL TEST REPORT" : "RAW MATERIAL METALLURGICAL TEST REPORT";
        RptDoc d = new RptDoc(title).file("QCMS_MetLAB_" + str(record.opt("report_number")));
        theme(api, d, "METLAB");
        d.recordNumber = "";
        d.bar(title);
        Object ospVendorName = or(ospVendor.opt("party_name"), osp.opt("vendor_name"), "-");
        Object supplyCondition = or(osp.opt("process_name"), process.opt("process_name"), record.opt("layout_name_snapshot"));
        Object qty = "OSP_SAMPLE".equals(scope) ? osp.opt("sample_quantity") : isOsp ? osp.opt("quantity_received") : record.opt("production_quantity_pcs");
        Object processName = or(process.opt("process_name"), record.opt("process_specification_snapshot"));
        List<String[]> meta = new ArrayList<>();
        meta.add(vrow("Report No.", record.opt("report_number"), "Date", record.opt("test_date")));
        meta.add(vrow("Part Name", part.opt("part_name"), "Part No.", part.opt("part_number")));
        meta.add(vrow("Customer", customer.opt("party_name"), "Supplier", supplier.opt("party_name")));
        meta.add(vrow("OSP Vendor", ospVendorName, "Material Used", or(grade.opt("grade_code"), grade.opt("grade_name"))));
        meta.add(vrow("Supply / Process Condition", or(record.opt("supply_condition"), supplyCondition), "Process", processName));
        meta.add(vrow("Supplier Invoice / Reference", record.opt("supplier_reference_number"), "Quantity (pcs)", or(record.opt("production_quantity_pcs"), qty)));
        meta.add(vrow("Heat Number", or(record.opt("heat_number"), inward.opt("heat_number"), osp.opt("heat_number")), "Heat Code", or(record.opt("heat_code"), inward.opt("heat_code"))));
        meta.add(vrow("Supplier / HT / OSP Batch", or(record.opt("vendor_batch_number_snapshot"), osp.opt("vendor_batch_number")), "Internal / FSI Batch", record.opt("batch_number")));
        meta.add(vrow("Inspection Stage", or(stage.opt("stage_name"), RptDoc.title(scope.replace("_", " "))), "Process", processName));
        meta.add(vrow("Drawing / Revision", dash(part.opt("drawing_number")) + " / " + dash(part.opt("drawing_revision")), "Specification Reference", record.opt("specification_reference")));
        meta.add(vrow("Sample / Reference", or(record.opt("reference_text"), record.opt("sample_reference"), inward.opt("inward_number"), osp.opt("sample_reference")), "Report Layout", record.opt("layout_name_snapshot")));
        d.labeled(rows(meta), f(32, 65, 32, 65), 0, 2);

        List<String[]> test = new ArrayList<>();
        test.add(row("Sr.", "Parameter", "Specification", "Observations", "Unit", "Result"));
        int seq = 1;
        for (JSONObject r : list(results.optJSONArray("rows"))) {
            Object spec = r.opt("specification");
            if (!truthy(spec)) {
                Object lo = r.opt("lower_spec"), hi = r.opt("upper_spec");
                if (present(lo) || present(hi)) spec = strip((present(lo) ? raw(lo) : "") + " - " + (present(hi) ? raw(hi) : ""), " -");
            }
            test.add(row(or(r.opt("sequence_no"), seq), r.opt("parameter"), spec, r.opt("actual_value"), r.opt("unit"), r.opt("result")));
            seq++;
        }
        for (JSONObject r : list(results.optJSONArray("requirement_rows"))) {
            test.add(row(seq, r.opt("requirement_name"), r.opt("requirement_value"), r.opt("actual_value"), r.opt("unit"), r.opt("result")));
            seq++;
        }
        if (test.size() == 1) test.add(row(1, "Metallurgical requirements", "As approved inspection layout", "No result rows recorded", "", "NOT_EVALUATED"));
        d.space(1.4f);
        d.bar("METALLURGICAL TEST RESULTS");
        d.grid(rows(test), f(12, 54, 50, 46, 14, 18), 5);

        caseDepth(d, results);

        List<JSONObject> chem = list(results.optJSONArray("chemistry_rows"));
        if (!chem.isEmpty()) {
            d.sub("CHEMICAL ANALYSIS · ASTM E 415 / IS 8811");
            chemistryTable(d, chem);
        }
        List<JSONObject> jom = list(results.optJSONArray("jominy_rows"));
        if (!jom.isEmpty()) {
            d.sub("HARDNESS / JOMINY TRAVERSE");
            List<String[]> jr = new ArrayList<>();
            jr.add(row("Distance", "mm", "Min HRC", "Max HRC", "RMTC HRC", "MetLAB HRC", "Result", "Remark"));
            for (JSONObject r : jom) jr.add(row(r.opt("distance_label"), r.opt("distance_mm"), r.opt("minimum_hrc"), r.opt("maximum_hrc"), r.opt("rmtc_actual_hrc"), r.opt("actual_value"), r.opt("result"), r.opt("remarks")));
            d.grid(rows(jr), f(20, 17, 22, 22, 25, 28, 22, 38), 6);
        }
        d.keep(70);
        d.bar("MICROSTRUCTURE PHOTOGRAPHS");
        d.photos(photos, 2, 46);
        references(d, results, "REFERENCE DOCUMENTS / STATEMENTS");

        Object overall = or(record.opt("disposition"), record.opt("overall_result"), "NOT_EVALUATED");
        Object conclusion = or(record.opt("remarks"), "Overall result: " + raw(or(record.opt("overall_result"), overall)));
        d.space(1.5f);
        d.conclusion(raw(conclusion), raw(results.opt("conclusion_remark")), raw(overall), raw(or(record.opt("disposition_reason"), "-")));
        d.labeledCenter(new String[][]{
            vrow("Prepared By", emp(emps, record.opt("prepared_by_employee_id")), "Validated By", emp(emps, record.opt("validated_by_employee_id")), "Verified & Approved By", emp(emps, record.opt("approved_by_employee_id"))),
            vrow("Prepared / Test Date", record.opt("test_date"), "Validated At", record.opt("validated_at"), "Decision At", record.opt("decision_at"))},
            f(25, 37, 25, 37, 34, 36), 0, 2, 4);
        return d;
    }

    static boolean present(Object o) { return o != null && o != JSONObject.NULL; }

    static String strip(String s, String chars) {
        int a = 0, b = s.length();
        while (a < b && chars.indexOf(s.charAt(a)) >= 0) a++;
        while (b > a && chars.indexOf(s.charAt(b - 1)) >= 0) b--;
        return s.substring(a, b);
    }

    static boolean rawMaterial(JSONObject record) {
        String scope = str(record.opt("inspection_scope")).toUpperCase(Locale.ROOT);
        return "RAW_MATERIAL_STAGE".equals(scope) || "MATERIAL_INWARD".equals(scope) || truthy(record.opt("inward_lot_id"));
    }

    /** InspectionService.raw_material_results: only the selected Layout Master characteristics; RMTC values are reference data. */
    static JSONObject rawMaterialResults(Api api, JSONObject record, JSONObject results) {
        try {
            JSONObject clean = new JSONObject(results.toString());
            JSONObject plan = one(api, "inspection_plans", record.opt("layout_plan_id"));
            if (plan.length() > 0) {
                List<JSONObject> chars = list(api, "inspection_plan_characteristics?select=*&inspection_plan_id=eq." + Api.enc(str(plan.opt("id"))) + "&order=sequence_no.asc&limit=2000");
                java.util.Set<String> allowed = new java.util.HashSet<>();
                boolean caseDepth = false;
                for (JSONObject c : chars) {
                    allowed.add(str(c.opt("id")));
                    JSONObject meta = c.optJSONObject("layout_metadata");
                    if ((meta != null && truthy(meta.opt("case_depth_traverse"))) || truthy(c.opt("case_depth_traverse_enabled"))
                        || str(c.opt("characteristic")).toLowerCase(Locale.ROOT).matches(".*\\bcase\\s+depth\\b.*")) caseDepth = true;
                }
                JSONArray kept = new JSONArray();
                for (JSONObject r : list(results.optJSONArray("rows"))) if (allowed.contains(str(r.opt("inspection_plan_characteristic_id")))) kept.put(r);
                clean.put("rows", kept);
                if (!caseDepth) {
                    clean.put("case_depth_applicable", false);
                    clean.put("case_depth_locations", new JSONArray());
                    clean.put("case_depth_traverse", new JSONArray());
                    clean.put("case_depth_na_reason", "Not applicable for this approved layout.");
                }
            }
            clean.put("chemistry_rows", new JSONArray());
            clean.put("jominy_rows", new JSONArray());
            clean.put("requirement_rows", new JSONArray());
            return clean;
        } catch (Exception e) {
            return results;
        }
    }

    static void caseDepth(RptDoc d, JSONObject results) {
        List<JSONObject> locs = list(results.optJSONArray("case_depth_locations"));
        List<JSONObject> trav = list(results.optJSONArray("case_depth_traverse"));
        if (truthy(results.opt("case_depth_applicable")) && !locs.isEmpty() && !trav.isEmpty()) {
            List<String> names = new ArrayList<>();
            for (JSONObject l : locs) { String n = str(or(l.opt("location"), l.opt("name"))); if (!n.isEmpty()) names.add(n); }
            d.space(1.4f);
            d.bar("CASE DEPTH / MICROHARDNESS TRAVERSE");
            List<String[]> specs = new ArrayList<>();
            specs.add(row("Location", "Controlled Parameter", "Specification", "Unit"));
            for (JSONObject l : locs) specs.add(row(or(l.opt("location"), l.opt("name")), or(l.opt("parameter"), "Case Depth"), or(l.opt("specification"), "-"), or(l.opt("unit"), "")));
            d.grid(rows(specs), f(34, 66, 72, 22));
            d.space(1.0f);
            List<String[]> t = new ArrayList<>();
            String[] head = new String[names.size() + 1];
            head[0] = "Distance (mm)";
            for (int i = 0; i < names.size(); i++) head[i + 1] = names.get(i);
            t.add(head);
            RptDoc.Chart chart = new RptDoc.Chart();
            Map<String, List<double[]>> pts = new LinkedHashMap<>();
            for (String n : names) pts.put(n, new ArrayList<>());
            for (JSONObject r : trav) {
                JSONObject readings = r.optJSONObject("readings");
                if (readings == null) readings = new JSONObject();
                String[] line = new String[names.size() + 1];
                line[0] = raw(r.opt("distance_mm"));
                for (int i = 0; i < names.size(); i++) {
                    Object val = readings.opt(names.get(i));
                    line[i + 1] = raw(val);
                    try {
                        double dist = Double.parseDouble(raw(r.opt("distance_mm")));
                        double hv = Double.parseDouble(raw(val));
                        pts.get(names.get(i)).add(new double[]{dist, hv});
                    } catch (Exception ignored) { }
                }
                t.add(line);
            }
            float rest = (d.contentMm() - 28) / Math.max(1, names.size());
            float[] w = new float[names.size() + 1];
            w[0] = 28;
            for (int i = 1; i < w.length; i++) w[i] = rest;
            d.grid(rows(t), w);
            for (Map.Entry<String, List<double[]>> e : pts.entrySet()) if (!e.getValue().isEmpty()) { chart.names.add(e.getKey()); chart.series.add(e.getValue()); }
            if (!chart.series.isEmpty()) {
                d.space(1.2f);
                d.sub("CASE DEPTH TRAVERSE · Distance (mm) vs Hardness (HV)");
                d.blocks.add(chart);
            }
        } else if (truthy(results.opt("case_depth_na_reason"))) {
            d.sub("CASE DEPTH / MICROHARDNESS TRAVERSE");
            d.text("Not Applicable: " + raw(results.opt("case_depth_na_reason")), RptDoc.NORMAL);
        }
    }

    // _chemical_horizontal_report_table
    private static final String[] CHEM_ORDER = {"C", "Mn", "Si", "S", "P", "Cr", "Ni", "Mo", "V", "Al", "Cu", "Nb", "Ti"};
    private static final String RATIO = "aln2ratio";

    static String chemKey(Object value) {
        String t = str(value).replaceAll("[^A-Za-z0-9]", "").toLowerCase(Locale.ROOT);
        Map<String, String> alias = new HashMap<>();
        String[][] a = {{"carbon", "c"}, {"manganese", "mn"}, {"silicon", "si"}, {"sulphur", "s"}, {"sulfur", "s"}, {"phosphorus", "p"}, {"chromium", "cr"},
            {"nickel", "ni"}, {"molybdenum", "mo"}, {"vanadium", "v"}, {"aluminium", "al"}, {"aluminum", "al"}, {"copper", "cu"}, {"niobium", "nb"},
            {"titanium", "ti"}, {"alnratio", RATIO}, {"aln2ratio", RATIO}, {"alnitrogenratio", RATIO}};
        for (String[] p : a) alias.put(p[0], p[1]);
        return alias.containsKey(t) ? alias.get(t) : t;
    }

    static void chemistryTable(RptDoc d, List<JSONObject> chem) {
        Map<String, Integer> rank = new HashMap<>();
        for (int i = 0; i < CHEM_ORDER.length; i++) rank.put(chemKey(CHEM_ORDER[i]), i);
        List<JSONObject> normal = new ArrayList<>(), extras = new ArrayList<>(), ratio = new ArrayList<>();
        for (JSONObject r : chem) {
            String k = chemKey(r.opt("element"));
            if (RATIO.equals(k)) ratio.add(r); else if (rank.containsKey(k)) normal.add(r); else extras.add(r);
        }
        Collections.sort(normal, (x, y) -> {
            int c = Integer.compare(rank.get(chemKey(x.opt("element"))), rank.get(chemKey(y.opt("element"))));
            return c != 0 ? c : str(x.opt("element")).compareTo(str(y.opt("element")));
        });
        Collections.sort(extras, (x, y) -> str(x.opt("element")).compareTo(str(y.opt("element"))));
        List<JSONObject> ordered = new ArrayList<>(normal);
        ordered.addAll(extras);
        ordered.addAll(ratio);
        String[] head = new String[ordered.size() + 1];
        head[0] = "Element";
        for (int i = 0; i < ordered.size(); i++) {
            String e = str(ordered.get(i).opt("element"));
            head[i + 1] = RATIO.equals(chemKey(e)) ? "Al/N2 Ratio" : e.contains("%") ? e : e + "%";
        }
        List<String[]> t = new ArrayList<>();
        t.add(head);
        String[][] lines = {{"Spec. Min", "minimum_value"}, {"Spec. Max", "maximum_value"}, {"RMTC Achieved", "rmtc_actual_value"}, {"MetLAB Achieved", "actual_value"}};
        for (String[] l : lines) {
            String[] r = new String[ordered.size() + 1];
            r[0] = l[0];
            for (int i = 0; i < ordered.size(); i++) {
                Object val = ordered.get(i).opt(l[1]);
                if ("RMTC Achieved".equals(l[0]) && (!present(val) || "".equals(val))) val = ordered.get(i).opt("source_actual_value");
                r[i + 1] = !present(val) || "".equals(val) ? "-" : raw(val);
            }
            t.add(r);
        }
        float rest = (d.contentMm() - 26) / Math.max(1, head.length - 1);
        float[] w = new float[head.length];
        w[0] = 26;
        for (int i = 1; i < w.length; i++) w[i] = rest;
        d.grid(rows(t), w);
    }

    static void references(RptDoc d, JSONObject results, String title) {
        List<String> refs = new ArrayList<>();
        JSONArray a = results.optJSONArray("reference_documents");
        if (a != null) for (int i = 0; i < a.length(); i++) { String s = str(a.opt(i)); if (!s.isEmpty()) refs.add(s); }
        if (refs.isEmpty()) return;
        d.space(1.2f);
        d.sub(title);
        List<String[]> r = new ArrayList<>();
        r.add(row("Sr.", "Reference"));
        for (int i = 0; i < refs.size(); i++) r.add(row(i + 1, refs.get(i)));
        d.grid(rows(r), f(14, d.contentMm() - 14));
    }

    // ================================================================== Bend test (bend_test_report_pdf_bytes)
    static JSONObject bendFind(List<JSONObject> rows, String[] units, String[] words, boolean textOnly) {
        for (JSONObject r : rows) {
            String unit = str(r.opt("unit")).toLowerCase(Locale.ROOT);
            String name = (str(r.opt("parameter")) + " " + str(r.opt("characteristic")) + " " + str(r.opt("specification"))).toLowerCase(Locale.ROOT);
            String ctype = str(r.opt("characteristic_type")).toUpperCase(Locale.ROOT);
            if (textOnly && !("TEXT".equals(ctype) || "ATTRIBUTE".equals(ctype))) continue;
            if (Arrays.asList(units).contains(unit)) return r;
            for (String w : words) if (name.contains(w)) return r;
        }
        return new JSONObject();
    }

    static String bendActual(JSONObject r) {
        Object val = r.opt("actual_value");
        if (!present(val) || "".equals(val)) {
            JSONArray obs = r.optJSONArray("observations");
            List<String> o = new ArrayList<>();
            if (obs != null) for (int i = 0; i < obs.length(); i++) { String s = str(obs.opt(i)); if (!s.isEmpty() && !"null".equals(s)) o.add(s); }
            val = String.join(", ", o);
        }
        String s = raw(val);
        return "None".equals(s) ? "" : s;
    }

    static String bendSpec(JSONObject r) { return str(r.opt("specification")); }

    static String pv(Object o) { String s = raw(o); return s.isEmpty() ? "-" : s; }

    static RptDoc bend(Api api, JSONObject record, JSONObject part, JSONObject customer, JSONObject grade, JSONObject inward, JSONObject osp,
                       Map<String, JSONObject> emps, JSONObject results, List<RptDoc.Photo> photos) {
        JSONObject det = results.optJSONObject("bend_report");
        if (det == null) det = new JSONObject();
        List<JSONObject> rows = list(results.optJSONArray("rows"));
        RptDoc d = new RptDoc("METALLURGICAL LABORATORY - BEND TEST REPORT").file("QCMS_Bend_Test_" + str(record.opt("report_number")));
        theme(api, d, "BEND_TEST");
        d.edgeMm = 9;
        d.topMm = 28;
        d.band("BEND TEST REPORT");
        Object batch = or(det.opt("fsi_batch_no"), record.opt("batch_number"));
        String[][] info = {
            {"Report No.", pv(record.opt("report_number")), "Date", pv(record.opt("test_date"))},
            {"Part #", pv(part.opt("part_number")), "Part Name", pv(part.opt("part_name"))},
            {"Customer Name", pv(or(det.opt("customer_name"), customer.opt("party_name"))), "Material Used", pv(or(det.opt("material_used"), grade.opt("grade_code"), grade.opt("grade_name")))},
            {"Baking Batch No.", pv(or(det.opt("baking_batch_no"), record.opt("vendor_batch_number_snapshot"))), "Batch Quantity (Pcs)", pv(or(det.opt("batch_quantity_pcs"), record.opt("production_quantity_pcs")))},
            {"Steel Heat Code", pv(or(det.opt("steel_heat_code"), record.opt("heat_code"), inward.opt("heat_code"), record.opt("heat_number"))), "Part Diameter", pv(det.opt("part_diameter"))},
            {"FSI Batch No.", pv(batch), "HT Batch No.", pv(or(det.opt("ht_batch_no"), osp.opt("vendor_batch_number")))},
        };
        RptDoc.Labeled infoGrid = new RptDoc.Labeled(info, f(.19f, .31f, .19f, .31f), new int[]{0, 2}, false, 8.6f);
        infoGrid.valueColor = RptDoc.INK;
        d.blocks.add(infoGrid);

        JSONObject temp = bendFind(rows, new String[]{"°c", "c", "deg c", "degc"}, new String[]{"°c", "baking temp"}, false);
        JSONObject btime = bendFind(rows, new String[]{"minutes", "minute", "min", "mins"}, new String[]{"minutes", "baking time"}, false);
        JSONObject hard = bendFind(rows, new String[]{"hrc", "hv", "hrc/hv"}, new String[]{"hrc", "hardness"}, false);
        d.band("Baking / Aging");
        String tA = bendActual(temp), timeA = bendActual(btime), hA = bendActual(hard);
        String[][] bk = {
            {"", "Baking Temp.", "Baking Time (Minutes)", str(or(det.opt("hardness_title"), "Base Metal Hardness below plating in HV0.5kgs at 0.1mm & (HRC) Avg reading of Three observations"))},
            {"Specification", pv(or(det.opt("baking_temp_spec"), bendSpec(temp))), pv(or(det.opt("baking_time_spec"), bendSpec(btime))), pv(or(det.opt("hardness_spec"), bendSpec(hard)))},
            {"Actual", pv(or(det.opt("baking_temp_actual"), tA + (!tA.isEmpty() && !tA.contains("°") ? "°C" : ""))),
                pv(or(det.opt("baking_time_actual"), timeA.isEmpty() ? "" : timeA + " Minutes")),
                pv(or(det.opt("hardness_actual"), (hA + " " + str(hard.opt("unit"))).trim()))},
        };
        RptDoc.Grid bkg = new RptDoc.Grid(bk, f(.19f, .22f, .24f, .35f), new int[0], 1, 8.6f, 8.6f);
        bkg.allCenter = true; bkg.firstColBold = true; bkg.noTopLine = true;
        d.blocks.add(bkg);

        JSONObject load = bendFind(rows, new String[]{"kn"}, new String[]{"load"}, false);
        JSONObject cht = bendFind(rows, new String[]{"mm"}, new String[]{"cross head", "cht"}, false);
        Object angleValue = results.opt("bend_angle_degrees");
        if (!present(angleValue) || "".equals(angleValue)) angleValue = bendActual(bendFind(rows, new String[]{"degree", "degrees", "deg", "°"}, new String[]{"angle"}, false));
        String angle;
        try {
            double a = Double.parseDouble(raw(angleValue));
            angle = (a == Math.rint(a) ? String.valueOf((long) a) : String.valueOf(a)) + "°";
        } catch (Exception e) {
            angle = raw(angleValue).isEmpty() ? "-" : raw(angleValue);
        }
        String disp = str(or(record.opt("disposition"), record.opt("overall_result"))).toUpperCase(Locale.ROOT);
        String status = str(or(det.opt("bend_status"),
            "ACCEPTED".equals(disp) || "PASS".equals(disp) ? "Passed" : "REJECTED".equals(disp) || "FAIL".equals(disp) ? "Failed"
                : (disp.isEmpty() ? "Pending" : RptDoc.title(disp.replace("_", " ")))));
        d.band("Bend Test Results");
        String[][] rs = {
            {"Load Vs CHT", "CHT (mm)", "Bend Angle (Degree)", "Bend Test Status"},
            {pv(or(det.opt("load_kn"), bendActual(load))), pv(or(det.opt("cht_mm"), bendActual(cht))), "-".equals(angle) ? "-" : "Including angle   " + angle, pv(status)},
        };
        RptDoc.Grid rsg = new RptDoc.Grid(rs, f(.25f, .25f, .25f, .25f), status.toLowerCase(Locale.ROOT).startsWith("pass") ? new int[]{3} : new int[0], 1, 8.6f, 8.6f);
        rsg.allCenter = true; rsg.noTopLine = true;
        d.blocks.add(rsg);

        RptDoc.Photo[] slot = new RptDoc.Photo[5];
        for (int i = 0; i < photos.size() && i < 4; i++) slot[i + 1] = photos.get(i);
        JSONObject surfRow = bendFind(rows, new String[0], new String[]{"peeling", "flaking", "plating"}, true);
        String surface = str(or(det.opt("surface_remark"), bendActual(surfRow), bendSpec(surfRow)));
        d.blocks.add(new RptDoc.BendPanel(slot[1], angle, slot[2], slot[3], slot[4], surface));
        d.text("Part Bend Angle: " + angle, RptDoc.SMALL);
        List<String> caps = new ArrayList<>();
        for (int s = 1; s <= 4; s++) if (slot[s] != null && slot[s].has()) caps.add(slot[s].caption);
        d.text("BEND TEST PART PHOTOGRAPHS: " + String.join(" · ", caps), RptDoc.SMALL);

        String conclusion = str(or(results.opt("conclusion_remark"), record.opt("remarks")));
        d.space(3);
        RptDoc.Labeled cl = new RptDoc.Labeled(new String[][]{{"Conclusion:-", conclusion.isEmpty() ? "-" : conclusion}}, f(.2f, .8f), new int[]{0}, false, 9.6f);
        cl.ruled = true; cl.valueColor = d.conclusionColor; cl.valueBold = true; cl.labelSize = 10f;
        d.blocks.add(cl);
        String prepared = emp(emps, record.opt("prepared_by_employee_id"));
        String approved = emp(emps, record.opt("approved_by_employee_id"));
        if ("-".equals(approved)) approved = emp(emps, record.opt("validated_by_employee_id"));
        d.space(4);
        d.blocks.add(new RptDoc.Signatures(new String[]{prepared, approved}, new String[]{"Prepared By", "Verified & Approved By"}, f(.6f, .4f)));
        JSONArray refs = results.optJSONArray("reference_documents");
        List<String> refList = new ArrayList<>();
        if (refs != null) for (int i = 0; i < refs.length(); i++) { String s = str(refs.opt(i)); if (!s.isEmpty()) refList.add(s); }
        if (!refList.isEmpty()) {
            d.space(3);
            d.text("Referance Documents:", RptDoc.HEADING);
            for (String r : refList) d.text("- " + r, RptDoc.SMALL);
        }
        List<String[]> unmapped = new ArrayList<>();
        unmapped.add(row("Parameter / Specification", "Actual", "Unit", "Result"));
        for (JSONObject r : rows) {
            if (r == temp || r == btime || r == hard || r == load || r == cht) continue;
            String unit = str(r.opt("unit")).toLowerCase(Locale.ROOT);
            if (Arrays.asList("degree", "degrees", "deg", "°").contains(unit)) continue;
            String ctype = str(or(r.opt("characteristic_type"), "NUMBER")).toUpperCase(Locale.ROOT);
            if ("TEXT".equals(ctype) || "ATTRIBUTE".equals(ctype)) continue;
            unmapped.add(row(or(r.opt("specification"), r.opt("parameter"), r.opt("characteristic")), bendActual(r), or(r.opt("unit"), ""), or(r.opt("result"), "")));
        }
        if (unmapped.size() > 1) {
            d.space(3);
            d.band("Layout Parameters");
            RptDoc.Grid ug = new RptDoc.Grid(rows(unmapped), f(.55f, .2f, .1f, .15f), new int[0], 1, 7.4f, 7.4f);
            ug.noAlign = true; ug.plainHeader = true;
            d.blocks.add(ug);
        }
        return d;
    }

    // ================================================================== Dimensional (dimensional_record_pdf_bytes)
    static RptDoc dimensional(Api api, String id) throws Exception {
        JSONObject record = one(api, "inspection_reports", id);
        if (record.length() == 0) throw new Api.ApiException(404, "Dimensional report not found.");
        JSONObject part = one(api, "parts", record.opt("part_id"));
        JSONObject inward = one(api, "inward_lots", record.opt("inward_lot_id"));
        JSONObject supplier = one(api, "parties", or(record.opt("supplier_id"), inward.opt("supplier_id")));
        JSONObject customer = one(api, "parties", or(record.opt("customer_id"), part.opt("customer_id")));
        JSONObject grade = one(api, "material_grades", or(record.opt("material_grade_id"), part.opt("material_grade_id")));
        JSONObject process = one(api, "processes", record.opt("process_id"));
        JSONObject stage = one(api, "inspection_stages", record.opt("inspection_stage_id"));
        JSONObject osp = new JSONObject();
        if (truthy(record.opt("osp_job_id"))) {
            List<JSONObject> o = list(api, "v_qsms_osp_register?select=*&id=eq." + Api.enc(str(record.opt("osp_job_id"))) + "&limit=1");
            if (!o.isEmpty()) osp = o.get(0);
        }
        Map<String, JSONObject> emps = employees(api, record.opt("prepared_by_employee_id"), record.opt("validated_by_employee_id"), record.opt("approved_by_employee_id"));
        List<JSONObject> results = list(api, "inspection_results?select=*&inspection_report_id=eq." + Api.enc(id) + "&order=sequence_no.asc&limit=2000");
        String scope = str(or(record.opt("inspection_scope"), "MATERIAL_INWARD"));
        boolean isOsp = scope.startsWith("OSP_") || truthy(record.opt("osp_job_id"));
        String title = isOsp ? "OSP DIMENSIONAL INSPECTION REPORT" : "RAW_MATERIAL_STAGE".equals(scope) ? "RAW MATERIAL DIMENSIONAL INSPECTION REPORT" : "FINAL INSPECTION / DIMENSIONAL REPORT";
        RptDoc d = new RptDoc(title).file("QCMS_Dimensional_" + str(record.opt("report_number")));
        theme(api, d, "DIMENSIONAL");
        d.bar(title);
        List<String[]> meta = new ArrayList<>();
        meta.add(vrow("Report No.", record.opt("report_number"), "Date", record.opt("inspection_date")));
        meta.add(vrow("Part Name", part.opt("part_name"), "Part No.", part.opt("part_number")));
        meta.add(vrow("Customer", customer.opt("party_name"), "Supplier / OSP Vendor", or(osp.opt("vendor_name"), supplier.opt("party_name"))));
        meta.add(vrow("Material Grade", or(grade.opt("grade_code"), grade.opt("grade_name")), "Supply / Process Condition", or(record.opt("supply_condition"), osp.opt("process_name"), process.opt("process_name"))));
        meta.add(vrow("Heat Number", or(record.opt("heat_number"), inward.opt("heat_number"), osp.opt("heat_number")), "Heat Code", or(record.opt("heat_code"), inward.opt("heat_code"))));
        meta.add(vrow("Supplier / HT / OSP Batch", or(record.opt("vendor_batch_number_snapshot"), osp.opt("vendor_batch_number")), "Internal / FSI Batch", record.opt("batch_number")));
        meta.add(vrow("Supplier Invoice / Reference", record.opt("supplier_reference_number"), "Inspection Stage", or(stage.opt("stage_name"), record.opt("layout_type_name"))));
        meta.add(vrow("Drawing", or(record.opt("drawing_number"), part.opt("drawing_number")), "Revision", or(record.opt("drawing_revision"), part.opt("drawing_revision"))));
        meta.add(vrow("Process", or(osp.opt("process_name"), process.opt("process_name"), record.opt("process_specification_snapshot")), "Layout", record.opt("layout_name_snapshot")));
        meta.add(vrow("Lot / Production Qty", or(record.opt("production_quantity_pcs"), record.opt("lot_quantity")), "Sample Size", record.opt("sample_size")));
        meta.add(vrow("Sample / Lot Reference", record.opt("reference_text"), "Report Scope", RptDoc.title(scope.replace("_", " "))));
        d.labeled(rows(meta), f(32, 65, 32, 65), 0, 2);
        d.space(1.5f);
        d.bar("INSPECTION RESULTS");
        List<String[]> t = new ArrayList<>();
        t.add(row("Sr.", "Parameter / Characteristic", "Specification", "Observations", "Method / Aid", "Result"));
        int i = 1;
        for (JSONObject r : results) {
            Object obs = r.opt("observations");
            String observations = obs instanceof JSONArray ? RptDoc.joinList((JSONArray) obs) : raw(obs);
            Object spec = r.opt("specification");
            if (!truthy(spec) && (present(r.opt("lower_spec")) || present(r.opt("upper_spec"))))
                spec = (raw(r.opt("lower_spec")) + " - " + raw(r.opt("upper_spec")) + " " + raw(r.opt("unit"))).trim();
            t.add(row(or(r.opt("sequence_no"), r.opt("characteristic_no"), i), r.opt("characteristic"), spec,
                observations.isEmpty() ? r.opt("attribute_result") : observations, r.opt("checking_aid"), r.opt("result")));
            i++;
        }
        if (t.size() == 1) t.add(row(1, "Inspection characteristic", "As approved layout", "No results recorded", "", "NOT_EVALUATED"));
        d.grid(rows(t), f(12, 54, 48, 42, 22, 16), 5);
        Object overall = or(record.opt("disposition"), record.opt("overall_result"), "NOT_EVALUATED");
        Object conclusion = or(record.opt("remarks"), "Overall result: " + raw(or(record.opt("overall_result"), overall)));
        d.space(1.5f);
        d.conclusion(raw(conclusion), "", raw(overall), raw(or(record.opt("disposition_reason"), "-")));
        d.labeledCenter(new String[][]{vrow("Prepared By", emp(emps, record.opt("prepared_by_employee_id")), "Validated By", emp(emps, record.opt("validated_by_employee_id")),
            "Approved By", emp(emps, record.opt("approved_by_employee_id")))}, f(25, 39, 25, 39, 25, 41), 0, 2, 4);
        return d;
    }

    // ================================================================== Material inward (material_inward_record_pdf_bytes)
    static RptDoc inward(Api api, String id) throws Exception {
        JSONObject record = one(api, "inward_lots", id);
        if (record.length() == 0) throw new Api.ApiException(404, "Material Inward record not found.");
        List<JSONObject> reg = list(api, "v_qsms_inward_register?select=*&id=eq." + Api.enc(id) + "&limit=1");
        JSONObject register = reg.isEmpty() ? new JSONObject() : reg.get(0);
        JSONObject part = one(api, "parts", record.opt("part_id"));
        JSONObject supplier = one(api, "parties", record.opt("supplier_id"));
        JSONObject rmtc = one(api, "rmtc_approvals", record.opt("rmtc_approval_id"));
        Map<String, JSONObject> emps = employees(api, record.opt("prepared_by_employee_id"), record.opt("validated_by_employee_id"));
        List<JSONObject> ml = list(api, "lab_tests?select=*&inward_lot_id=eq." + Api.enc(id) + "&test_type=eq.METLAB&order=updated_at.desc&limit=1");
        List<JSONObject> dl = list(api, "inspection_reports?select=*&inward_lot_id=eq." + Api.enc(id) + "&report_type=eq.DIMENSIONAL&order=updated_at.desc&limit=1");
        JSONObject metlab = ml.isEmpty() ? new JSONObject() : ml.get(0), dim = dl.isEmpty() ? new JSONObject() : dl.get(0);
        String title = "MATERIAL INWARD INSPECTION RECORD";
        RptDoc d = new RptDoc(title).file("QCMS_Material_Inward_" + str(record.opt("inward_number")));
        theme(api, d, "MATERIAL_INWARD");
        d.bar(title);
        String[][] meta = {
            vrow("Inward No.", record.opt("inward_number"), "Date", record.opt("inward_date")),
            vrow("GRN Number", record.opt("grn_number"), "Supplier Invoice", record.opt("invoice_number")),
            vrow("Part Name", or(part.opt("part_name"), register.opt("part_name")), "Part No.", or(part.opt("part_number"), register.opt("part_number"))),
            vrow("Supplier", or(supplier.opt("party_name"), register.opt("supplier_name")), "Heat Number", record.opt("heat_number")),
            vrow("Heat Code", record.opt("heat_code"), "RMTC Number", or(rmtc.opt("rmtc_number"), register.opt("rmtc_number"))),
            vrow("Supplier RMTC", or(rmtc.opt("certificate_reference"), register.opt("supplier_rmtc_number")), "Input Weight kg/part", record.opt("input_weight_kg")),
        };
        d.labeled(meta, f(32, 65, 32, 65), 0, 2);
        d.space(1.5f);
        d.bar("QUANTITY & STEEL ALLOCATION");
        String[][] qty = {
            row("Quantity", "Production pcs", "Steel kg", "Disposition / Status"),
            row("Total", record.opt("production_quantity_pcs"), or(record.opt("required_steel_quantity_kg"), record.opt("steel_quantity_kg")), record.opt("receipt_disposition")),
            row("Accepted", record.opt("accepted_production_quantity_pcs"), record.opt("accepted_steel_quantity_kg"), "ACCEPTED"),
            row("Rejected", record.opt("rejected_production_quantity_pcs"), record.opt("rejected_steel_quantity_kg"), "REJECTED"),
            row("On Hold", record.opt("hold_production_quantity_pcs"), record.opt("hold_steel_quantity_kg"), "ON_HOLD"),
        };
        RptDoc.Grid q = d.grid(qty, f(44, 45, 45, 60), 3);
        d.bar("QUALITY GATE & LINKED INSPECTIONS");
        String[][] gate = {
            row("Quality Gate", "Status", "Linked Report", "Report / Decision"),
            row("RMTC Validation", or(rmtc.opt("disposition"), register.opt("rmtc_disposition")), rmtc.opt("rmtc_number"), rmtc.opt("validation_result")),
            row("MetLAB", record.opt("metallurgical_status"), or(metlab.opt("report_number"), "-"), or(metlab.opt("disposition"), metlab.opt("overall_result"))),
            row("Dimensional / Final Inspection", record.opt("dimensional_status"), or(dim.opt("report_number"), "-"), or(dim.opt("disposition"), dim.opt("overall_result"))),
            row("Final Quality Decision", record.opt("quality_disposition"), "Material Inward", record.opt("status")),
        };
        d.grid(gate, f(50, 42, 47, 55), 1, 3);
        if (truthy(record.opt("reserve_reason")) || truthy(record.opt("remarks")))
            d.labeled(new String[][]{vrow("Hold / Reserve / Rejection Reason", or(record.opt("reserve_reason"), "-")), vrow("Remarks", or(record.opt("remarks"), "-"))}, f(48, 146), 0);
        d.space(1.5f);
        d.labeledCenter(new String[][]{vrow("Prepared By", emp(emps, record.opt("prepared_by_employee_id")), "Validated By", emp(emps, record.opt("validated_by_employee_id")))}, f(32, 65, 32, 65), 0, 2);
        return d;
    }

    // ================================================================== RMTC (rmtc_record_pdf_bytes)
    static RptDoc rmtc(Api api, String id) throws Exception {
        JSONObject record = one(api, "rmtc_approvals", id);
        if (record.length() == 0) throw new Api.ApiException(404, "RMTC record not found.");
        List<JSONObject> approvals = list(api, "rmtc_part_approvals?select=*&rmtc_approval_id=eq." + Api.enc(id) + "&order=created_at.asc&limit=100");
        List<JSONObject> chemistry = list(api, "rmtc_chemistry_results?select=*&rmtc_approval_id=eq." + Api.enc(id) + "&order=element.asc&limit=300");
        List<JSONObject> jominy = list(api, "rmtc_jominy_results?select=*&rmtc_approval_id=eq." + Api.enc(id) + "&order=distance_mm.asc&limit=300");
        List<JSONObject> requirements = list(api, "rmtc_requirement_results?select=*&rmtc_approval_id=eq." + Api.enc(id) + "&order=sequence_no.asc&limit=300");
        Map<String, JSONObject> parts = new HashMap<>(), grades = new HashMap<>();
        List<String> partIds = new ArrayList<>();
        for (JSONObject a : approvals) if (truthy(a.opt("part_id"))) partIds.add(str(a.opt("part_id")));
        if (!partIds.isEmpty()) for (JSONObject p : list(api, "parts?select=*&id=in.(" + String.join(",", partIds) + ")&limit=200")) parts.put(str(p.opt("id")), p);
        List<String> gradeIds = new ArrayList<>();
        for (JSONObject p : parts.values()) if (truthy(p.opt("material_grade_id"))) gradeIds.add(str(p.opt("material_grade_id")));
        if (!gradeIds.isEmpty()) for (JSONObject gr : list(api, "material_grades?select=*&id=in.(" + String.join(",", gradeIds) + ")&limit=200")) grades.put(str(gr.opt("id")), gr);
        JSONObject supplier = one(api, "parties", record.opt("supplier_id"));
        JSONObject mill = one(api, "parties", record.opt("steel_mill_id"));
        Map<String, JSONObject> emps = employees(api, record.opt("prepared_by_employee_id"), record.opt("validated_by_employee_id"), record.opt("approved_by_employee_id"), record.opt("decision_by_employee_id"));
        String norm = str(record.opt("heat_number")).replaceAll("[^A-Za-z0-9]", "").toUpperCase(Locale.ROOT);
        JSONObject heat = new JSONObject();
        List<JSONObject> usage = new ArrayList<>();
        if (!norm.isEmpty()) {
            List<JSONObject> hs = list(api, "v_qsms_heat_summary?select=*&normalized_heat_number=eq." + Api.enc(norm) + "&limit=1");
            if (!hs.isEmpty()) heat = hs.get(0);
            usage = list(api, "v_qsms_heat_steel_ledger?select=*&normalized_heat_number=eq." + Api.enc(norm) + "&order=created_at.desc&limit=500");
        }
        List<RptDoc.Photo> photos = slotPhotos(api, "RMTC", id, "RMTC_MICROSTRUCTURE_", record, 3);

        RptDoc d = new RptDoc("RMTC RECORD - " + str(or(record.opt("rmtc_number"), "QUALITY RECORD"))).file("QCMS_RMTC_" + str(record.opt("rmtc_number")));
        theme(api, d, "RMTC");
        d.heatNumber = str(record.opt("heat_number"));
        d.recordNumber = str(record.opt("rmtc_number"));
        d.reportLabel = "RMTC RECORD";
        float body = 8.0f;
        d.bar("RMTC HEADER & TRACEABILITY");
        String[][] header = {
            vrow("QCMS RMTC Number", record.opt("rmtc_number"), "Entry Date", record.opt("entry_date")),
            vrow("Supplier RMTC Number", record.opt("certificate_reference"), "RMTC Date", record.opt("certificate_date")),
            vrow("Supplier", supplier.opt("party_name"), "Steel Mill", mill.opt("party_name")),
            vrow("Heat Number", record.opt("heat_number"), "Internal Heat Code", record.opt("heat_code")),
            vrow("Global Heat Steel Qty kg", record.opt("certificate_quantity"), "RM Section", record.opt("rm_section")),
            vrow("Forging Route / Root", record.opt("forging_route"), "Prepared By", emp(emps, record.opt("prepared_by_employee_id"))),
            vrow("Workflow Status", record.opt("status"), "Validation Result", record.opt("validation_result")),
            vrow("Final Disposition", record.opt("disposition"), "Decision Date", record.opt("decision_at")),
        };
        d.blocks.add(new RptDoc.Labeled(header, f(29, 68, 29, 68), new int[]{0, 2}, false, body));
        if (truthy(record.opt("remarks")))
            d.blocks.add(new RptDoc.Labeled(new String[][]{vrow("RMTC Remarks", record.opt("remarks"))}, f(29, d.contentMm() - 29), new int[]{0}, false, body));
        d.space(1.6f);
        d.bar("GLOBAL HEAT QUANTITY BALANCE & RECORD LIST");
        String[][] bal = {
            vrow("Global Heat Qty kg", or(heat.opt("global_steel_quantity_kg"), record.opt("certificate_quantity")), "Committed kg", heat.opt("committed_steel_quantity_kg"),
                "Unallocated Balance kg", or(heat.opt("available_unallocated_steel_quantity_kg"), heat.opt("available_steel_quantity_kg"))),
            vrow("Inward Steel Used kg", heat.opt("inward_steel_quantity_kg"), "Remaining Planned kg", heat.opt("remaining_planned_steel_quantity_kg"), "Active RMTC Records", heat.opt("active_rmtc_count")),
        };
        d.blocks.add(new RptDoc.Labeled(bal, f(31, 33, 31, 33, 34, 32), new int[]{0, 2, 4}, false, body));
        List<String[]> hr = new ArrayList<>();
        hr.add(row("RMTC No.", "Supplier RMTC", "Supplier", "Part", "Planned kg", "Inward kg", "Balance Plan kg", "Decision"));
        for (JSONObject r : usage) hr.add(row(r.opt("rmtc_number"), r.opt("supplier_rmtc_number"), r.opt("supplier_name"), r.opt("part_number"), r.opt("planned_steel_quantity_kg"),
            r.opt("inward_steel_quantity_kg"), r.opt("remaining_planned_steel_quantity_kg"), or(r.opt("part_disposition"), r.opt("rmtc_disposition"), r.opt("rmtc_status"))));
        if (hr.size() == 1) hr.add(row(record.opt("rmtc_number"), record.opt("certificate_reference"), supplier.opt("party_name"), "-", "-", "-", "-", or(record.opt("disposition"), record.opt("status"))));
        rmtcGrid(d, hr, f(24, 27, 34, 21, 21, 21, 25, 21), 7.6f, 7);

        d.space(1.6f);
        d.bar("COVERED PART WORKSHEET REGISTER");
        List<String[]> ps = new ArrayList<>();
        ps.add(row("Part No.", "FSI Part No.", "Description", "Grade", "Planned Qty", "Input kg", "Steel kg", "Worksheet", "Auto Validation", "Final Decision"));
        for (JSONObject a : approvals) {
            JSONObject p = parts.getOrDefault(str(a.opt("part_id")), new JSONObject());
            JSONObject gr = grades.getOrDefault(str(p.opt("material_grade_id")), new JSONObject());
            ps.add(row(p.opt("part_number"), p.opt("fsi_part_number"), p.opt("part_name"), or(gr.opt("grade_code"), gr.opt("grade_name")), a.opt("planned_production_quantity_pcs"),
                a.opt("input_weight_kg"), a.opt("planned_steel_quantity_kg"), truthy(a.opt("worksheet_completed_at")) ? "Completed" : "Pending",
                or(a.opt("approval_status"), "NOT_EVALUATED"), or(a.opt("disposition"), "PENDING")));
        }
        if (ps.size() == 1) ps.add(row("-", "-", "No covered part worksheets found", "", "", "", "", "Pending", "NOT_EVALUATED", "PENDING"));
        rmtcGrid(d, ps, f(17, 20, 27, 17, 16, 17, 18, 20, 21, 21), 7.6f, 7, 8, 9);

        d.space(1.6f);
        d.bar("SUPPLIER RMTC MECHANICAL PROPERTIES");
        List<String[]> mech = new ArrayList<>();
        mech.add(row("Property", "Actual / Result", "Source"));
        JSONObject mr = record.optJSONObject("mechanical_results");
        if (mr != null && mr.length() > 0) {
            for (Iterator<String> it = mr.keys(); it.hasNext(); ) { String k = it.next(); mech.add(row(RptDoc.title(k.replace("_", " ")), mr.opt(k), "Supplier RMTC")); }
        } else mech.add(row("Mechanical Properties", "No dedicated mechanical property values recorded", "Supplier RMTC"));
        rmtcGrid(d, mech, f(55, 94, 45), body);

        int wi = 0;
        for (JSONObject a : approvals) {
            wi++;
            d.keep(42);
            String pid = str(a.opt("part_id"));
            JSONObject p = parts.getOrDefault(pid, new JSONObject());
            JSONObject gr = grades.getOrDefault(str(p.opt("material_grade_id")), new JSONObject());
            d.bar("PART WORKSHEET " + wi + " - " + dash(p.opt("part_number")) + " - " + raw(p.opt("part_name")));
            String[][] ident = {
                vrow("Part Number", p.opt("part_number"), "FSI Part Number", p.opt("fsi_part_number"), "Part Description", p.opt("part_name")),
                vrow("Material Grade", or(gr.opt("grade_code"), gr.opt("grade_name")), "Heat Number", record.opt("heat_number"), "Heat Code", record.opt("heat_code")),
                vrow("Worksheet Status", truthy(a.opt("worksheet_completed_at")) ? "Completed" : "Pending", "", "", "", ""),
                vrow("Planned Production Qty pcs", a.opt("planned_production_quantity_pcs"), "Input Weight kg", a.opt("input_weight_kg"), "Planned Steel kg", a.opt("planned_steel_quantity_kg")),
            };
            d.blocks.add(new RptDoc.Labeled(ident, f(25, 37, 27, 43, 27, 35), new int[]{0, 2, 4}, false, body));
            d.sub("Chemical Composition");
            List<String[]> cr = new ArrayList<>();
            cr.add(row("Element", "Minimum", "Maximum", "Actual", "Unit", "Status"));
            for (JSONObject r : chemistry) if (pid.equals(str(r.opt("part_id"))))
                cr.add(row(r.opt("element"), r.opt("minimum_value"), r.opt("maximum_value"), r.opt("actual_value"), or(r.opt("unit"), "%"), r.opt("result")));
            if (cr.size() == 1) cr.add(row("-", "", "", "No chemistry values recorded", "", "NOT_EVALUATED"));
            rmtcGrid(d, cr, f(24, 31, 31, 39, 19, 50), body, 5);
            d.sub("Jominy Results");
            List<String[]> jr = new ArrayList<>();
            jr.add(row("Distance", "mm", "Min HRC", "Max HRC", "Actual", "Actual Status", "Calculated", "Calc. Status", "Applicable"));
            for (JSONObject r : jominy) if (pid.equals(str(r.opt("part_id"))))
                jr.add(row(r.opt("distance_label"), r.opt("distance_mm"), r.opt("minimum_hrc"), r.opt("maximum_hrc"), r.opt("actual_hrc"), r.opt("result"),
                    r.opt("calculated_hrc"), r.opt("calculated_result"), "NOT_APPLICABLE".equals(str(r.opt("applicability"))) ? "No" : "Yes"));
            if (jr.size() == 1) jr.add(row("-", "", "", "", "", "NOT_EVALUATED", "", "NOT_EVALUATED", "No"));
            rmtcGrid(d, jr, f(20, 14, 18, 18, 20, 24, 22, 28, 30), 7.6f, 5, 7);
            d.sub("DI / Hardenability");
            String[][] di = {row("Grain Size ASTM E-112", "Actual DI", "Actual DI Status", "Calculated DI", "Calculated DI Status"),
                row(a.opt("grain_size"), a.opt("actual_di"), a.opt("actual_di_status"), a.opt("calculated_di"), a.opt("calculated_di_status"))};
            rmtcGrid(d, Arrays.asList(di), f(42, 32, 42, 32, 46), body, 2, 4);
            List<JSONObject> preq = new ArrayList<>(), mreq = new ArrayList<>(), oreq = new ArrayList<>();
            for (JSONObject r : requirements) if (pid.equals(str(r.opt("part_id")))) preq.add(r);
            String[] tokens = {"tensile", "yield", "elongation", "reduction", "impact", "proof", "mechanical", "uts"};
            for (JSONObject r : preq) {
                String n = str(or(r.opt("requirement_name"), r.opt("requirement_code"))).toLowerCase(Locale.ROOT);
                boolean isMech = false;
                for (String t : tokens) if (n.contains(t)) isMech = true;
                (isMech ? mreq : oreq).add(r);
            }
            d.sub("Mechanical Properties");
            List<String[]> mp = new ArrayList<>();
            mp.add(row("Property", "Specification", "Actual / Observation", "Unit", "Status", "Remarks"));
            for (JSONObject r : mreq) mp.add(row(or(r.opt("requirement_name"), r.opt("requirement_code")), r.opt("requirement_value"), r.opt("actual_value"), r.opt("unit"), r.opt("result"), r.opt("remarks")));
            if (mp.size() == 1) mp.add(row("Mechanical Properties", "As supplier RMTC / Part requirement", "No separate part-level mechanical property row", "", "NOT_EVALUATED", ""));
            rmtcGrid(d, mp, f(38, 42, 40, 18, 24, 32), 7.6f, 4);
            d.sub("Heat Treatment & Other Requirements");
            List<String[]> orq = new ArrayList<>();
            orq.add(row("Requirement", "Specification / Part Master", "RMTC Actual / Observation", "Unit", "Status", "Remarks"));
            for (JSONObject r : oreq) orq.add(row(or(r.opt("requirement_name"), r.opt("requirement_code")), r.opt("requirement_value"), r.opt("actual_value"), r.opt("unit"), r.opt("result"), r.opt("remarks")));
            if (orq.size() == 1) orq.add(row("-", "No additional requirements recorded", "", "", "NOT_EVALUATED", ""));
            rmtcGrid(d, orq, f(38, 45, 39, 18, 24, 30), 7.6f, 4);
        }
        d.keep(55);
        d.bar("RMTC MICROSTRUCTURE PHOTOGRAPHS");
        d.blocks.add(new RptDoc.Photos(photos, 3, 40, true));
        d.keep(44);
        d.bar("RMTC VALIDATION STATUS & FINAL DECISION");
        if (approvals.isEmpty()) {
            rmtcGrid(d, Arrays.asList(row("Validation Check", "Status", "Validation Check", "Status"), row("Record", "NOT_EVALUATED", "Final Decision", "PENDING")), f(42, 55, 42, 55), body, 1, 3);
        } else {
            int ai = 0;
            for (JSONObject a : approvals) {
                ai++;
                JSONObject p = parts.getOrDefault(str(a.opt("part_id")), new JSONObject());
                JSONObject gr = grades.getOrDefault(str(p.opt("material_grade_id")), new JSONObject());
                if (ai > 1) d.space(1.2f);
                d.sub(dash(p.opt("part_number")) + " - " + raw(p.opt("part_name")) + " - " + raw(or(gr.opt("grade_code"), gr.opt("grade_name"), "")));
                List<String[]> vr = Arrays.asList(
                    row("Validation Check", "Status", "Validation Check", "Status"),
                    row("Source", a.opt("source_status"), "Material Grade", a.opt("material_grade_status")),
                    row("Raw Material", a.opt("raw_material_status"), "Chemistry", a.opt("chemistry_status")),
                    row("Jominy", a.opt("jominy_status"), "Requirements", a.opt("requirement_status")),
                    row("Actual DI", a.opt("actual_di_status"), "Calculated DI", a.opt("calculated_di_status")),
                    row("Automated Recommendation", a.opt("approval_status"), "Final Decision", a.opt("disposition")));
                rmtcGrid(d, vr, f(42, 55, 42, 55), body, 1, 3);
                Object reason = or(a.opt("decision_reason"), record.opt("decision_reason"), "");
                d.blocks.add(new RptDoc.Labeled(new String[][]{vrow("Decision / Reserve Reason", or(reason, "-"))}, f(42, 152), new int[]{0}, false, body));
            }
        }
        d.space(1.6f);
        String[][] sign = {
            {"Prepared By", emp(emps, record.opt("prepared_by_employee_id")), "Validated By", emp(emps, record.opt("validated_by_employee_id")),
                "Approved / Decided By", emp(emps, or(record.opt("approved_by_employee_id"), record.opt("decision_by_employee_id")))},
            {"Prepared At", v(record.opt("prepared_at")), "Validated At", v(record.opt("validated_at")), "Decision At", v(or(record.opt("decision_at"), record.opt("approved_at")))},
        };
        d.blocks.add(new RptDoc.Labeled(sign, f(24, 41, 24, 41, 30, 34), new int[]{0, 2, 4}, true, body));
        return d;
    }

    private static void rmtcGrid(RptDoc d, List<String[]> rows, float[] w, float cell, int... status) {
        RptDoc.Grid g = new RptDoc.Grid(rows(rows), w, status, 1, 7.6f, cell);
        d.blocks.add(g);
    }

    // ================================================================== controlled records (controlled_record_pdf_bytes)
    static final int MAX_COLUMNS = 9, CELL_LIMIT = 160;

    /** header fields in pairs (RECORD DETAILS), then each section as a table (dict -> Field / Value). */
    static RptDoc controlled(String title, LinkedHashMap<String, Object> header, LinkedHashMap<String, Object> sections, String recordNumber, String subtitle,
                             List<RptDoc.Photo> images, String imagesTitle) {
        RptDoc d = new RptDoc(title);
        d.topMm = 32;
        d.bottomMm = 14;
        d.recordNumber = recordNumber == null ? "" : recordNumber;
        d.reportLabel = subtitle == null ? "" : subtitle;
        if (subtitle != null && !subtitle.isEmpty()) d.text(subtitle, RptDoc.SUBTITLE);
        if (header != null && !header.isEmpty()) {
            d.bar("RECORD DETAILS");
            List<String[]> rows = new ArrayList<>();
            List<Map.Entry<String, Object>> items = new ArrayList<>(header.entrySet());
            for (int i = 0; i < items.size(); i += 2) {
                Map.Entry<String, Object> l = items.get(i);
                Map.Entry<String, Object> r = i + 1 < items.size() ? items.get(i + 1) : null;
                rows.add(new String[]{l.getKey(), v(l.getValue()), r == null ? "" : r.getKey(), r == null ? "" : v(r.getValue())});
            }
            d.labeled(rows(rows), f(33, 61, 33, d.contentMm() - 127), 0, 2);
        }
        if (sections != null) for (Map.Entry<String, Object> s : sections.entrySet()) section(d, s.getKey(), s.getValue());
        if (images != null) {
            List<RptDoc.Photo> imgs = new ArrayList<>();
            for (RptDoc.Photo p : images) if (p.has()) imgs.add(p);
            if (!imgs.isEmpty()) {
                d.space(2.4f);
                d.bar(imagesTitle == null ? "PHOTOGRAPHS" : imagesTitle);
                d.photos(imgs, 2, 52);
            }
        }
        return d;
    }

    /** One section: Map -> Field / Value table; List<Map> -> table; split into groups of 9 columns (first column repeated). */
    @SuppressWarnings("unchecked")
    static void section(RptDoc d, String name, Object raw) {
        d.space(2.4f);
        d.bar(name);
        List<String> cols = new ArrayList<>();
        List<List<String>> data = new ArrayList<>();
        if (raw instanceof Map) {
            cols.add("Field"); cols.add("Value");
            for (Map.Entry<String, Object> e : ((Map<String, Object>) raw).entrySet()) data.add(Arrays.asList(e.getKey(), cell(e.getValue())));
        } else if (raw instanceof List) {
            for (Object o : (List<Object>) raw) {
                if (o instanceof Map) {
                    Map<String, Object> m = (Map<String, Object>) o;
                    for (String k : m.keySet()) if (!cols.contains(k)) cols.add(k);
                }
            }
            for (Object o : (List<Object>) raw) {
                if (!(o instanceof Map)) continue;
                Map<String, Object> m = (Map<String, Object>) o;
                List<String> line = new ArrayList<>();
                for (String c : cols) line.add(cell(m.get(c)));
                data.add(line);
            }
        } else if (raw instanceof Table) {
            cols.addAll(((Table) raw).columns);
            for (List<String> r : ((Table) raw).rows) { List<String> line = new ArrayList<>(); for (String c : r) line.add(cut(c)); data.add(line); }
        } else if (raw != null) {
            cols.add("Information");
            data.add(Collections.singletonList(cell(raw)));
        }
        if (data.isEmpty()) { cols.clear(); cols.add("Information"); data.add(Collections.singletonList("No records available.")); }
        List<List<Integer>> groups = new ArrayList<>();
        if (cols.size() <= MAX_COLUMNS) {
            List<Integer> all = new ArrayList<>();
            for (int i = 0; i < cols.size(); i++) all.add(i);
            groups.add(all);
        } else {
            for (int i = 1; i < cols.size(); i += MAX_COLUMNS - 1) {
                List<Integer> gr = new ArrayList<>();
                gr.add(0);
                for (int j = i; j < Math.min(cols.size(), i + MAX_COLUMNS - 1); j++) gr.add(j);
                groups.add(gr);
            }
        }
        for (int gi = 0; gi < groups.size(); gi++) {
            List<Integer> gr = groups.get(gi);
            if (groups.size() > 1) { d.space(1.6f); d.sub(name + " · columns " + (gi + 1) + " of " + groups.size()); }
            List<String[]> t = new ArrayList<>();
            String[] head = new String[gr.size()];
            List<Integer> status = new ArrayList<>();
            for (int i = 0; i < gr.size(); i++) {
                head[i] = cols.get(gr.get(i));
                String lc = head[i].toLowerCase(Locale.ROOT);
                if (lc.contains("status") || lc.contains("result")) status.add(i);
            }
            t.add(head);
            for (List<String> r : data) {
                String[] line = new String[gr.size()];
                for (int i = 0; i < gr.size(); i++) line[i] = gr.get(i) < r.size() ? r.get(gr.get(i)) : "";
                t.add(line);
            }
            float[] w = new float[gr.size()];
            Arrays.fill(w, d.contentMm() / Math.max(1, gr.size()));
            int[] st = new int[status.size()];
            for (int i = 0; i < st.length; i++) st[i] = status.get(i);
            RptDoc.Grid g = new RptDoc.Grid(rows(t), w, st, 1, 8.2f, d.bodyPt);
            d.blocks.add(g);
        }
    }

    static String cell(Object o) { return cut(raw(o)); }

    static String cut(String s) { return s != null && s.length() > CELL_LIMIT ? s.substring(0, CELL_LIMIT - 1) + "…" : (s == null ? "" : s); }

    /** A ready table (register) for a controlled section. */
    static final class Table {
        final List<String> columns; final List<List<String>> rows;
        Table(List<String> columns, List<List<String>> rows) { this.columns = columns; this.rows = rows; }
    }

    static LinkedHashMap<String, Object> map(Object... kv) {
        LinkedHashMap<String, Object> m = new LinkedHashMap<>();
        for (int i = 0; i + 1 < kv.length; i += 2) m.put(String.valueOf(kv[i]), kv[i + 1]);
        return m;
    }

    static String label(JSONObject r, String... keys) {
        List<String> parts = new ArrayList<>();
        for (String k : keys) { String s = str(r.opt(k)); if (!s.isEmpty()) parts.add(s); }
        if (keys.length >= 3 && keys[1].equals("first_name")) {
            String name = (str(r.opt("first_name")) + " " + str(r.opt("last_name"))).trim();
            String code = str(r.opt(keys[0]));
            return String.join(" · ", Arrays.asList(code, name)).replaceAll("^ · | · $", "");
        }
        return String.join(" · ", parts);
    }

    static String pretty(Object o) { return RptDoc.title(str(o).replace("_", " ")); }

    // ---------------------------------------------------------------- calibration (_calibration_pdf)
    static RptDoc calibration(Api api, String id) throws Exception {
        JSONObject r = one(api, "quality_asset_calibration_records", id);
        if (r.length() == 0) throw new Api.ApiException(404, "Calibration record not found.");
        JSONObject asset = one(api, "quality_assets", r.opt("asset_id"));
        JSONObject link = one(api, "quality_asset_part_process_links", r.opt("link_id"));
        JSONObject part = one(api, "parts", link.opt("part_id"));
        JSONObject process = one(api, "processes", link.opt("process_id"));
        JSONObject emp = one(api, "employees", r.opt("performed_by_employee_id"));
        LinkedHashMap<String, Object> header = map("Asset Code", asset.opt("asset_code"), "Asset Number", asset.opt("asset_number"), "Asset", asset.opt("asset_name"),
            "Asset Type", asset.opt("asset_type"), "Part Number", part.opt("part_number"), "Process", process.opt("process_name"), "Record Type", r.opt("record_type"),
            "Service Date", r.opt("service_date"), "Next Due Date", r.opt("next_due_date"), "Result", r.opt("result"), "Status", r.opt("status"));
        LinkedHashMap<String, Object> sections = new LinkedHashMap<>();
        sections.put("CALIBRATION / VALIDATION DETAILS", map("Report Number", r.opt("report_number"), "Certificate Number", r.opt("certificate_number"),
            "Calibration / Validation Agency", r.opt("calibration_agency"), "Performed By", label(emp, "employee_code", "first_name", "last_name"), "Remarks", r.opt("remarks")));
        sections.put("ASSET MASTER CONTEXT", map("Manufacturer", asset.opt("manufacturer"), "Model", asset.opt("model"), "Serial Number", asset.opt("serial_number"),
            "Range", asset.opt("range_text"), "Least Count", asset.opt("least_count"), "Location", asset.opt("location")));
        RptDoc d = controlled("GAUGE / FIXTURE CALIBRATION & VALIDATION RECORD", header, sections,
            str(or(r.opt("report_number"), r.opt("certificate_number"), r.opt("id"))), "Part-wise · Process-wise controlled calibration / validation genealogy", null, null);
        d.file("QCMS_Calibration_" + str(or(r.opt("report_number"), r.opt("certificate_number"), "Record")));
        theme(api, d, "QUALITY_RECORD");
        return d;
    }

    // ---------------------------------------------------------------- standard room (_standard_room_pdf)
    static RptDoc standardRoom(Api api, String id) throws Exception {
        JSONObject r = one(api, "standard_room_inspection_records", id);
        if (r.length() == 0) throw new Api.ApiException(404, "Standard room record not found.");
        JSONObject asset = one(api, "quality_assets", r.opt("instrument_asset_id"));
        JSONObject part = one(api, "parts", r.opt("part_id"));
        JSONObject process = one(api, "processes", r.opt("process_id"));
        JSONObject emp = one(api, "employees", r.opt("operator_employee_id"));
        LinkedHashMap<String, Object> header = map("Inspection Date", r.opt("inspection_date"), "Report Number", r.opt("report_number"),
            "Instrument", or(asset.opt("asset_name"), r.opt("instrument_type")), "Instrument Code", asset.opt("asset_code"), "Asset Number", asset.opt("asset_number"),
            "Part Number", part.opt("part_number"), "Part Name", part.opt("part_name"), "Process", process.opt("process_name"), "Heat Number", r.opt("heat_number"),
            "Batch Code", r.opt("batch_code"), "Status", r.opt("inspection_status"));
        LinkedHashMap<String, Object> sections = new LinkedHashMap<>();
        sections.put("STANDARD ROOM INSPECTION", map("Instrument Type", r.opt("instrument_type"), "Program / Method Reference", r.opt("program_reference"),
            "Quantity Inspected", r.opt("quantity_inspected"), "Operator", label(emp, "employee_code", "first_name", "last_name"), "Remarks", r.opt("remarks"), "Record Status", r.opt("status")));
        RptDoc d = controlled("STANDARD ROOM PART INSPECTION RECORD", header, sections, str(or(r.opt("report_number"), r.opt("id"))),
            "CMM · VMM · Roughness · Counter · Standard Room Instrument Inspection", null, null);
        d.file("QCMS_Standard_Room_" + str(or(r.opt("report_number"), "Record")));
        theme(api, d, "QUALITY_RECORD");
        return d;
    }

    // ---------------------------------------------------------------- complaint (_complaint_pdf)
    static String yn(Object o) { return truthy(o) ? "Yes" : "No"; }

    static RptDoc complaint(Api api, String id) throws Exception {
        JSONObject c = one(api, "quality_complaints", id);
        if (c.length() == 0) throw new Api.ApiException(404, "Complaint not found.");
        JSONObject party = one(api, "parties", c.opt("party_id"));
        JSONObject part = one(api, "parts", c.opt("part_id"));
        JSONObject process = one(api, "processes", c.opt("process_id"));
        Map<String, JSONObject> emps = new HashMap<>();
        List<String> ids = new ArrayList<>();
        for (String k : new String[]{"fourstar_responsible_employee_id", "containment_responsible_employee_id", "root_cause_responsible_employee_id",
            "effectiveness_verified_by_employee_id", "closure_approved_by_employee_id"}) if (truthy(c.opt(k))) ids.add(str(c.opt(k)));
        List<JSONObject> followups = list(api, "quality_complaint_followups?select=*&complaint_id=eq." + Api.enc(id) + "&order=followup_date.asc&limit=5000");
        List<JSONObject> actions = list(api, "quality_complaint_actions?select=*&complaint_id=eq." + Api.enc(id) + "&order=action_no.asc&limit=5000");
        for (JSONObject a : actions) if (truthy(a.opt("owner_employee_id"))) ids.add(str(a.opt("owner_employee_id")));
        for (JSONObject a : followups) if (truthy(a.opt("responsible_employee_id"))) ids.add(str(a.opt("responsible_employee_id")));
        if (!ids.isEmpty()) for (JSONObject e : list(api, "employees?select=*&id=in.(" + String.join(",", new java.util.LinkedHashSet<>(ids)) + ")&limit=200")) emps.put(str(e.opt("id")), e);
        List<JSONObject> media = list(api, "document_attachments?select=*&entity_type=eq.QUALITY_COMPLAINT&entity_id=eq." + Api.enc(id) + "&status=eq.ACTIVE&order=created_at.desc&limit=250");
        media.removeIf(m -> !"COMPLAINT_PHOTO".equals(str(m.opt("document_type"))) && !"COMPLAINT_ATTACHMENT".equals(str(m.opt("document_type"))));

        LinkedHashMap<String, Object> header = map("Complaint No.", c.opt("complaint_number"), "Complaint Type", RptDoc.title(str(c.opt("complaint_type"))),
            "Complaint Date", c.opt("complaint_date"), "Status", pretty(c.opt("status")), "Party", Lookups.PARTY.of(party),
            "Part", part.length() > 0 ? Lookups.PART.of(part) : "Not linked", "Process", process.length() > 0 ? Lookups.PROCESS.of(process) : "Not linked",
            "External Reference", or(c.opt("external_reference"), "-"), "Severity", c.opt("severity"), "Target Closure", or(c.opt("target_closure_date"), "-"),
            "Actual Closure", or(c.opt("closure_date"), "-"));
        LinkedHashMap<String, Object> s = new LinkedHashMap<>();
        s.put("PROBLEM DEFINITION / COMPLAINT ANALYSIS", map("Subject", c.opt("subject"), "Complaint Description", c.opt("description"),
            "Defect / Failure Mode", or(c.opt("defect_mode"), "-"), "What happened?", or(c.opt("problem_what"), "-"), "Where detected / occurred?", or(c.opt("problem_where"), "-"),
            "When / under what condition?", or(c.opt("problem_when"), "-"), "Detection Point", or(c.opt("detection_point"), "-"),
            "Occurrence Pattern / Frequency", or(c.opt("occurrence_pattern"), "-"), "Lot / Batch", or(c.opt("lot_batch_number"), "-"), "Heat Number", or(c.opt("heat_number"), "-"),
            "Affected Quantity", c.opt("affected_quantity"), "Impact / Risk Summary", or(c.opt("impact_summary"), "-")));
        s.put("RESPONSIBILITY MATRIX", map("Complaint Coordinator", empLabel(emps, c.opt("fourstar_responsible_employee_id")),
            "Containment Owner", empLabel(emps, c.opt("containment_responsible_employee_id")), "Root Cause Analysis Owner", empLabel(emps, c.opt("root_cause_responsible_employee_id")),
            "Effectiveness Verified By", empLabel(emps, c.opt("effectiveness_verified_by_employee_id")), "Closure Approved By", empLabel(emps, c.opt("closure_approved_by_employee_id")),
            "Customer / Supplier Responsible", or(c.opt("external_responsible_name"), "-"), "External Email", or(c.opt("external_responsible_email"), "-"),
            "External Phone", or(c.opt("external_responsible_phone"), "-")));
        s.put("IMMEDIATE CORRECTION & CONTAINMENT", map("Immediate Correction", or(c.opt("immediate_correction"), "-"), "Containment Action", or(c.opt("containment_action"), "-"),
            "Containment Due Date", or(c.opt("containment_due_date"), "-"), "Containment Completed Date", or(c.opt("containment_completed_date"), "-"),
            "Containment Effectiveness", or(c.opt("containment_effectiveness"), "-")));
        s.put("ROOT CAUSE ANALYSIS", map("Analysis Method", RptDoc.title(str(or(c.opt("analysis_method"), "-")).replace("_", " ")), "Why 1", or(c.opt("why_1"), "-"),
            "Why 2", or(c.opt("why_2"), "-"), "Why 3", or(c.opt("why_3"), "-"), "Why 4", or(c.opt("why_4"), "-"), "Why 5", or(c.opt("why_5"), "-"),
            "Occurrence Root Cause", or(c.opt("occurrence_root_cause"), c.opt("root_cause"), "-"), "Escape / Detection Root Cause", or(c.opt("escape_root_cause"), "-"),
            "Systemic Root Cause", or(c.opt("systemic_root_cause"), "-"), "Evidence / Validation", or(c.opt("root_cause_evidence"), "-"),
            "Root Cause Confirmed", yn(c.opt("root_cause_confirmed")), "Confirmed Date", or(c.opt("root_cause_confirmed_date"), "-")));
        List<Object> acts = new ArrayList<>();
        String today = new java.text.SimpleDateFormat("yyyy-MM-dd", Locale.ENGLISH).format(new java.util.Date());
        for (JSONObject a : actions) {
            boolean overdue = !str(a.opt("target_date")).isEmpty() && str(a.opt("target_date")).compareTo(today) < 0
                && !Arrays.asList("COMPLETED", "CLOSED", "VERIFIED", "CANCELLED").contains(str(a.opt("status")).toUpperCase(Locale.ROOT));
            acts.add(map("Action No.", a.opt("action_no"), "Action Type", pretty(a.opt("action_type")), "Action", a.opt("action_description"),
                "Four Star Owner", empLabel(emps, a.opt("owner_employee_id")), "External Owner", or(a.opt("external_owner_name"), "-"),
                "Target Date", or(a.opt("target_date"), "-"), "Completion Date", or(a.opt("completion_date"), "-"), "Status", overdue ? "Overdue" : pretty(a.opt("status")),
                "Evidence", or(a.opt("evidence"), "-"), "Effectiveness", or(a.opt("effectiveness_result"), "-")));
        }
        s.put("CORRECTIVE / PREVENTIVE ACTION PLAN", acts);
        s.put("EFFECTIVENESS VERIFICATION & CLOSURE", map("Verification Plan", or(c.opt("verification_plan"), "-"), "Effectiveness Criteria", or(c.opt("effectiveness_criteria"), "-"),
            "Verification Result", or(c.opt("verification_result"), "-"), "Effectiveness Verified", yn(c.opt("effectiveness_verified")),
            "Verified Date", or(c.opt("effectiveness_verified_date"), "-"), "Recurrence Check", or(c.opt("recurrence_check_result"), "-"),
            "Closure Remarks", or(c.opt("closure_remarks"), "-"), "Closure Approval Date", or(c.opt("closure_approved_date"), "-")));
        String cur = str(or(c.opt("currency"), "INR"));
        s.put("DEBIT NOTE / COMMERCIAL STATUS", map("Debit Note Required", yn(c.opt("debit_note_required")), "Debit Note Status", pretty(c.opt("debit_note_status")),
            "Debit Note Number", or(c.opt("debit_note_number"), "-"), "Debit Note Date", or(c.opt("debit_note_date"), "-"),
            "Debit Note Amount", cur + " " + String.format(Locale.ENGLISH, "%,.2f", num(c.opt("debit_note_amount"))),
            "Settled Amount", cur + " " + String.format(Locale.ENGLISH, "%,.2f", num(c.opt("debit_note_settled_amount"))),
            "Settled Date", or(c.opt("debit_note_settled_date"), "-"), "Commercial Remarks", or(c.opt("commercial_remarks"), "-")));
        List<Object> reg = new ArrayList<>();
        List<RptDoc.Photo> photos = new ArrayList<>();
        for (JSONObject m : media) {
            String t = str(or(m.opt("document_title"), m.opt("file_name"), "Attachment"));
            boolean photo = "COMPLAINT_PHOTO".equals(str(m.opt("document_type")));
            String at = str(m.opt("created_at"));
            reg.add(map("Type", photo ? "Photograph" : "Attachment", "Title", t, "File Name", or(m.opt("file_name"), "-"), "Uploaded At", at.isEmpty() ? "-" : at.substring(0, Math.min(16, at.length()))));
            if (photo) { try { photos.add(new RptDoc.Photo(t, api.download(str(m.opt("object_path"))))); } catch (Exception ignored) { } }
        }
        s.put("PHOTOGRAPHS & ATTACHMENTS REGISTER", reg);
        List<Object> fol = new ArrayList<>();
        for (JSONObject f : followups) fol.add(map("Date", f.opt("followup_date"), "Type", pretty(f.opt("followup_type")), "Follow-up / Remarks", f.opt("remarks"),
            "Next Follow-up", or(f.opt("next_followup_date"), "-"), "Status", str(or(pretty(f.opt("status_after_followup")), "-")), "Responsible", empLabel(emps, f.opt("responsible_employee_id"))));
        s.put("FOLLOW-UP HISTORY", fol);
        RptDoc d = controlled("DETAILED COMPLAINT ANALYSIS RECORD", header, s, str(c.opt("complaint_number")),
            "Problem Definition · Root Cause · Corrective Action · Responsibility · Verification · Commercial Closure", photos, "COMPLAINT PHOTOGRAPHS");
        d.file("QCMS_Complaint_" + str(c.opt("complaint_number")));
        theme(api, d, "QUALITY_RECORD");
        return d;
    }

    static double num(Object o) { try { return Double.parseDouble(raw(o)); } catch (Exception e) { return 0; } }

    static String empLabel(Map<String, JSONObject> emps, Object id) {
        JSONObject e = emps.get(str(id));
        if (e == null) return "-";
        String s = Lookups.EMPLOYEE.of(e);
        return s.isEmpty() ? "-" : s;
    }

    // ---------------------------------------------------------------- QC calculation (qc_calculation_pdf_bytes)
    static RptDoc qcCalculation(Api api, String id) throws Exception {
        JSONObject r = one(api, "qc_calculation_records", id);
        if (r.length() == 0) throw new Api.ApiException(404, "Calculation not found.");
        JSONObject emp = one(api, "employees", r.opt("performed_by_employee_id"));
        JSONObject part = one(api, "parts", r.opt("part_id"));
        JSONObject grade = one(api, "material_grades", r.opt("material_grade_id"));
        JSONObject in = r.optJSONObject("input_payload"), res = r.optJSONObject("result_payload");
        if (in == null) in = new JSONObject();
        if (res == null) res = new JSONObject();
        String nameEmp = (str(emp.opt("first_name")) + " " + str(emp.opt("last_name"))).trim();
        String code = str(emp.opt("employee_code"));
        String performed = !code.isEmpty() && !nameEmp.isEmpty() ? code + " - " + nameEmp : !nameEmp.isEmpty() ? nameEmp : !code.isEmpty() ? code : "-";
        LinkedHashMap<String, Object> header = map("Calculation No.", r.opt("calculation_number"), "Calculation Type", pretty(r.opt("calculation_type")),
            "Calculation Date", r.opt("calculation_date"), "Performed By", performed, "Part Number", part.opt("part_number"), "FSI Part Number", part.opt("fsi_part_number"),
            "Material Grade", grade.opt("grade_code"), "Heat Number", r.opt("heat_number"), "Standard / Basis", r.opt("standard_reference"), "Status", r.opt("status"), "Remarks", r.opt("remarks"));
        LinkedHashMap<String, Object> s = new LinkedHashMap<>();
        LinkedHashMap<String, Object> inputs = new LinkedHashMap<>();
        for (Iterator<String> it = in.keys(); it.hasNext(); ) { String k = it.next(); inputs.put(k, in.opt(k)); }
        s.put("Calculation Inputs", inputs);
        String type = str(r.opt("calculation_type"));
        if ("JOMINY".equals(type)) {
            JSONObject curve = res.optJSONObject("curve");
            List<Object> l = new ArrayList<>();
            if (curve != null) {
                List<Integer> keys = new ArrayList<>();
                for (Iterator<String> it = curve.keys(); it.hasNext(); ) { try { keys.add(Integer.parseInt(it.next())); } catch (Exception ignored) { } }
                Collections.sort(keys);
                for (int k : keys) l.add(map("Distance (1/16 in.)", k, "Calculated HRC", curve.opt(String.valueOf(k))));
            }
            s.put("Calculated Jominy Curve", l);
        } else if ("DI_VALUE".equals(type)) {
            JSONObject fac = res.optJSONObject("factors");
            List<Object> l = new ArrayList<>();
            if (fac != null) for (Iterator<String> it = fac.keys(); it.hasNext(); ) { String k = it.next(); l.add(map("Factor", k, "Value", fac.opt(k))); }
            s.put("DI Factor Details", l);
            s.put("Calculated Result", map("Calculated DI", res.opt("value"), "Error", or(res.opt("error"), "")));
        } else if ("HARDNESS_CONVERSION".equals(type)) {
            s.put("Hardness Conversion Result", map("Primary Value", (raw(r.opt("primary_value")) + " " + raw(r.opt("primary_unit"))).trim(),
                "Converted Value", (raw(r.opt("result_value")) + " " + raw(r.opt("conversion_unit"))).trim(), "Method", res.opt("method"), "Warning", res.opt("warning"),
                "Interpolation Bracket", res.opt("bracket")));
        }
        RptDoc d = controlled("QC CALCULATION RECORD", header, s, str(r.opt("calculation_number")), "Stored quality calculation result", null, null);
        d.file("QCMS_QC_Calculation_" + str(r.opt("calculation_number")));
        theme(api, d, "QUALITY_RECORD");
        return d;
    }

    // ---------------------------------------------------------------- Universal record PDF (records_center.render_universal_pdf_center)
    static RptDoc universal(Api api, Module m, String id) throws Exception {
        JSONArray r = api.rows(m.table + "?select=*&" + (m.idField.isEmpty() ? "id" : m.idField) + "=eq." + Api.enc(id) + "&limit=1");
        if (r.length() == 0) throw new Api.ApiException(404, "Record not found or not visible for your role.");
        JSONObject rec = r.getJSONObject(0);
        List<String> keys = new ArrayList<>();
        for (Iterator<String> it = rec.keys(); it.hasNext(); ) keys.add(it.next());
        Map<String, Map<String, String>> fk = Labels.resolve(api, m.table, r, keys);
        LinkedHashMap<String, Object> header = new LinkedHashMap<>();
        for (String k : keys) {
            if ("tenant_id".equals(k) || "id".equals(k) || k.endsWith("_path")) continue;
            Object val = rec.opt(k);
            if (!truthy(val) && !(val instanceof Number) && !(val instanceof Boolean)) continue;
            String text = val instanceof JSONObject || val instanceof JSONArray ? raw(val) : Labels.cell(k, val, fk.get(k));
            if (text.isEmpty()) continue;
            header.put(Labels.header(k), text.length() > 400 ? text.substring(0, 399) + "…" : text);
        }
        LinkedHashMap<String, Object> sections = new LinkedHashMap<>();
        for (Module.Child child : m.children) {
            try {
                String order = child.order == null || child.order.isEmpty() ? "" : "&order=" + child.order;
                JSONArray rows = api.rows(child.table + "?select=*&" + child.fk + "=eq." + Api.enc(id) + order + "&limit=2000");
                List<String> cols = new ArrayList<>();
                for (String[] c : child.cols) cols.add(c[0]);
                Map<String, Map<String, String>> cfk = Labels.resolve(api, child.table, rows, cols);
                List<String> heads = new ArrayList<>();
                for (String[] c : child.cols) heads.add(c[1]);
                List<List<String>> data = new ArrayList<>();
                for (int i = 0; i < rows.length(); i++) {
                    JSONObject row = rows.getJSONObject(i);
                    List<String> line = new ArrayList<>();
                    for (String[] c : child.cols) line.add(Labels.cell(c[0], row.opt(c[0]), cfk.get(c[0])));
                    data.add(line);
                }
                sections.put(child.title.toUpperCase(Locale.ROOT), new Table(heads, data));
            } catch (Exception ignored) { }
        }
        String number = m.recordTitle(rec);
        RptDoc d = controlled(m.title.toUpperCase(Locale.ROOT) + " RECORD", header, sections, number, "", null, null);
        d.file("QCMS_" + m.title + "_" + number);
        theme(api, d, "QUALITY_RECORD");
        return d;
    }

    /** Full register PDF ("<TYPE> REGISTER", Record Count, one table). */
    static RptDoc register(Api api, String title, List<String> columns, List<List<String>> rows) {
        LinkedHashMap<String, Object> sections = new LinkedHashMap<>();
        sections.put(title, new Table(columns, rows));
        RptDoc d = controlled(title.toUpperCase(Locale.ROOT) + " REGISTER", map("Record Count", rows.size()), sections, "", "", null, null);
        d.file("QCMS_" + title + "_Register");
        theme(api, d, "QUALITY_RECORD");
        return d;
    }
}
