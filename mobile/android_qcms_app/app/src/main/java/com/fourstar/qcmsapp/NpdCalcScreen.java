package com.fourstar.qcmsapp;

import android.graphics.Color;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/**
 * QC Calculation Tools (app_pages/qc_calculation_tools.py): Jominy curve, DI value and ASTM E140 hardness
 * conversion calculated natively (NpdCalc = exact ports) and saved to qc_calculation_records like the website.
 */
public final class NpdCalcScreen extends Screen {
    private static final String[] TOOLS = {"Jominy Calculator", "DI Value Calculator", "Hardness Conversion"};
    private int tool = 0;
    private FormView context, inputs;
    private LinearLayout result;
    private final Field.Lookup parts = Lookups.parts();
    private final Field.Lookup employees = NpdUtil.employees();
    // last calculation (saved by the Save button)
    private JSONObject lastInputs, lastResults;
    private Object lastPrimaryUnit = JSONObject.NULL, lastPrimaryValue = JSONObject.NULL, lastConversionUnit = JSONObject.NULL, lastResultValue = JSONObject.NULL;

    public NpdCalcScreen(MainActivity a) { super(a); }

    @Override public String title() { return "QC Calculation Tools"; }
    @Override public String subtitle() { return "Jominy, DI and hardness conversion with stored records"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        LinearLayout tabs = Ui.hbox(a);
        for (int i = 0; i < TOOLS.length; i++) {
            final int k = i;
            TextView t = Ui.text(a, TOOLS[i].replace(" Calculator", "").replace("Hardness ", "Hardness\n"), 12.5f, k == tool ? Color.WHITE : Ui.TEXT, true);
            t.setGravity(android.view.Gravity.CENTER);
            t.setPadding(dp(6), dp(10), dp(6), dp(10));
            t.setBackground(k == tool ? Ui.round(Ui.TEAL, 0, 0, 12, a) : Ui.round(Color.WHITE, Ui.LINE_STRONG, 1, 12, a));
            t.setOnClickListener(v -> { tool = k; a.rebuild(); });
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1);
            if (i > 0) lp.leftMargin = dp(6);
            tabs.addView(t, lp);
        }
        add(tabs, 2);
        Button records = Ui.outline(a, "Calculation records (register)", Ui.TEAL);
        records.setOnClickListener(v -> {
            Module m = Catalog.get("qc_calculations");
            if (m != null) a.push(new RegisterScreen(a, m));
        });
        add(records, 8);

        add(Ui.label(a, TOOLS[tool]), 12);
        String note = tool == 0 ? "Calculated from the entered chemical composition using the QCMS Jominy calculation logic."
            : tool == 1 ? "Ideal diameter calculation using the QCMS DI factor table and chemical composition."
            : "ASTM E 140-02 Table 1 - non-austenitic steels, Rockwell C hardness range. Conversions are approximate and material-specific; QCMS does not extrapolate outside the table.";
        add(Ui.text(a, note, 11.5f, tool == 2 ? Ui.AMBER_FG : Ui.MUTED, false), 2);

        LinearLayout card = Ui.card(a);
        context = new FormView(a, Arrays.asList(
            Field.lookup("part_id", "Part Number (optional)", parts),
            Field.text("heat_number", "Heat Number (optional)"),
            Field.lookup("performed_by_employee_id", "Calculated / Performed By", employees).req()));
        if (!api.employeeId.isEmpty()) context.set("performed_by_employee_id", api.employeeId);
        card.addView(context);
        List<Field> f = new ArrayList<>();
        if (tool == 0) for (String s : new String[]{"C", "MN", "CR", "NI", "MO"}) f.add(Field.number(s, s + " %").range(0, 100).def("0"));
        else if (tool == 1) {
            for (String s : new String[]{"C", "MN", "SI", "NI", "CR", "MO", "CU", "V"}) f.add(Field.number(s, s + " %").range(0, 100).def("0"));
            f.add(Field.select("grain_size", "ASTM Grain Size", "4", "5", "6", "7", "8").req().def("7"));
        } else {
            String[] codes = new String[NpdCalc.SCALES.length], labels = new String[NpdCalc.SCALES.length];
            for (int i = 0; i < codes.length; i++) { codes[i] = NpdCalc.SCALES[i][0]; labels[i] = NpdCalc.SCALES[i][1]; }
            f.add(Field.select("source_scale", "Primary Hardness Unit", codes).labels(labels).req().def("HRC"));
            f.add(Field.number("source_value", "Primary Hardness Value").req().def("50.0"));
            f.add(Field.select("target_scale", "Conversion Unit", codes).labels(labels).req().def("HV"));
        }
        f.add(Field.area("remarks", "Calculation Remarks"));
        inputs = new FormView(a, f);
        card.addView(inputs, Ui.matchWrap(a, 4));
        add(card, 4);
        Button calc = Ui.primary(a, tool == 0 ? "Calculate Jominy Curve" : tool == 1 ? "Calculate DI Value" : "Convert Hardness");
        calc.setOnClickListener(v -> calculate());
        add(calc, 12);
        result = Ui.vbox(a);
        add(result, 10);
        Api.async(() -> { Lookups.rows(api, parts); Lookups.rows(api, employees); return true; }, (ok, err) -> { });
        return scroll;
    }

    private double chem(String key) {
        Double d = inputs.num(key);
        return d == null ? 0.0 : d;
    }

    private void calculate() {
        String problem = inputs.validate();
        if (problem != null) { a.toast(problem); return; }
        result.removeAllViews();
        lastInputs = null; lastResults = null;
        lastPrimaryUnit = JSONObject.NULL; lastPrimaryValue = JSONObject.NULL; lastConversionUnit = JSONObject.NULL; lastResultValue = JSONObject.NULL;
        LinearLayout card = Ui.card(a);
        try {
            if (tool == 0) {
                Map<String, Object> chemistry = new LinkedHashMap<>();
                for (String s : new String[]{"C", "MN", "CR", "NI", "MO"}) chemistry.put(s, chem(s));
                LinkedHashMap<Integer, Double> curve = NpdCalc.jominyCurve(chemistry);
                JSONObject c = new JSONObject();
                List<List<String>> rows = new ArrayList<>();
                for (Map.Entry<Integer, Double> e : curve.entrySet()) {
                    c.put(String.valueOf(e.getKey()), e.getValue());
                    rows.add(Arrays.asList(String.valueOf(e.getKey()), Ui.num(e.getValue(), 3)));
                }
                lastInputs = new JSONObject(chemistry);
                lastResults = new JSONObject().put("curve", c);
                card.addView(new DataGrid(a, "Jominy curve", Arrays.asList("Distance (1/16 in.)", "Calculated HRC"), rows, 420, null));
            } else if (tool == 1) {
                Map<String, Object> chemistry = new LinkedHashMap<>();
                for (String s : new String[]{"C", "MN", "SI", "NI", "CR", "MO", "CU", "V"}) chemistry.put(s, chem(s));
                int gs = Integer.parseInt(inputs.str("grain_size"));
                LinkedHashMap<String, Object> di = NpdCalc.di(chemistry, gs);
                if (di.get("error") != null) {
                    card.addView(Ui.text(a, String.valueOf(di.get("error")), 13, Ui.RED_FG, true));
                    result.addView(card);
                    return;
                }
                JSONObject in = new JSONObject(chemistry);
                in.put("grain_size", gs);
                lastInputs = in;
                lastResults = toJson(di);
                lastResultValue = di.get("value");
                card.addView(Ui.text(a, "Calculated DI", 12, Ui.MUTED, false));
                card.addView(Ui.text(a, String.valueOf(di.get("value")), 26, Ui.TEAL_DARK, true));
                List<List<String>> rows = new ArrayList<>();
                @SuppressWarnings("unchecked") Map<String, Double> factors = (Map<String, Double>) di.get("factors");
                for (Map.Entry<String, Double> e : factors.entrySet()) rows.add(Arrays.asList(e.getKey(), String.valueOf(e.getValue())));
                card.addView(new DataGrid(a, "DI factors", Arrays.asList("Factor", "Value"), rows, 360, null), Ui.matchWrap(a, 8));
            } else {
                String src = inputs.str("source_scale"), tgt = inputs.str("target_scale");
                if (src.equals(tgt)) { a.toast("Choose a Conversion Unit different from the Primary Hardness Unit."); return; }
                double value = inputs.num("source_value");
                LinkedHashMap<String, Object> r = NpdCalc.convertHardness(value, src, tgt);
                lastInputs = new JSONObject().put("primary_unit", src).put("primary_value", value).put("conversion_unit", tgt);
                lastResults = toJson(r);
                lastPrimaryUnit = src; lastPrimaryValue = value; lastConversionUnit = tgt; lastResultValue = r.get("target_value");
                card.addView(Ui.text(a, "Converted Hardness", 12, Ui.MUTED, false));
                card.addView(Ui.text(a, String.format(Locale.ROOT, "%.3f %s", (Double) r.get("target_value"), tgt), 26, Ui.TEAL_DARK, true));
                card.addView(Ui.text(a, String.valueOf(r.get("method")), 12, Ui.MUTED, false));
                TextView w = Ui.text(a, String.valueOf(r.get("warning")), 12, Ui.AMBER_FG, false);
                w.setPadding(dp(10), dp(8), dp(10), dp(8));
                w.setBackground(Ui.round(Ui.AMBER_BG, 0, 0, 10, a));
                card.addView(w, Ui.matchWrap(a, 8));
            }
        } catch (IllegalArgumentException e) {
            card.addView(Ui.text(a, e.getMessage(), 13, Ui.RED_FG, true));
            result.addView(card);
            return;
        } catch (Exception e) {
            a.toast(Api.message(e));
            return;
        }
        Button save = Ui.outline(a, tool == 0 ? "Save Jominy Calculation Record" : tool == 1 ? "Save DI Calculation Record" : "Save Hardness Conversion Record", Ui.TEAL);
        save.setOnClickListener(v -> save(save));
        card.addView(save, Ui.matchWrap(a, 10));
        result.addView(card);
    }

    @SuppressWarnings("unchecked")
    private static Object jsonValue(Object v) throws Exception {
        if (v == null) return JSONObject.NULL;
        if (v instanceof double[]) {
            JSONArray arr = new JSONArray();
            for (double d : (double[]) v) arr.put(d);
            return arr;
        }
        if (v instanceof Map) {
            JSONObject o = new JSONObject();
            for (Map.Entry<Object, Object> e : ((Map<Object, Object>) v).entrySet()) o.put(String.valueOf(e.getKey()), jsonValue(e.getValue()));
            return o;
        }
        return v;
    }

    private static JSONObject toJson(Map<String, Object> m) throws Exception { return (JSONObject) jsonValue(m); }

    /** _calc_number(): QCT-{JOM|DI|HCV}-{yyyyMMddHHmmss}-{4 hex upper}. */
    static String calcNumber(String type) {
        String prefix = "JOMINY".equals(type) ? "JOM" : "DI_VALUE".equals(type) ? "DI" : "HARDNESS_CONVERSION".equals(type) ? "HCV" : "QCT";
        String hex = UUID.randomUUID().toString().replace("-", "").substring(0, 4).toUpperCase(Locale.ROOT);
        return "QCT-" + prefix + "-" + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMddHHmmss", Locale.ROOT)) + "-" + hex;
    }

    private void save(Button button) {
        if (lastInputs == null) { a.toast("Calculate first."); return; }
        String problem = context.validate();
        if (problem != null) { a.toast(problem); return; }
        String type = tool == 0 ? "JOMINY" : tool == 1 ? "DI_VALUE" : "HARDNESS_CONVERSION";
        String standard = tool == 0 ? "QCMS controlled Jominy calculation logic" : tool == 1 ? "QCMS DI Hardenability factor table" : "ASTM E 140-02 Table 1";
        button.setEnabled(false);
        Api.async(() -> {
            String partId = context.str("part_id");
            JSONObject part = partId.isEmpty() ? null : Lookups.rowOf(parts, partId);
            String grade = part == null ? "" : NpdUtil.s(part, "material_grade_id");
            JSONObject p = new JSONObject();
            p.put("calculation_number", calcNumber(type));
            p.put("calculation_type", type);
            p.put("calculation_date", Ui.today());
            p.put("part_id", partId.isEmpty() ? JSONObject.NULL : partId);
            p.put("material_grade_id", grade.isEmpty() ? JSONObject.NULL : grade);
            p.put("heat_number", NpdUtil.orNull(context.str("heat_number")));
            p.put("primary_unit", lastPrimaryUnit);
            p.put("primary_value", lastPrimaryValue);
            p.put("conversion_unit", lastConversionUnit);
            p.put("result_value", lastResultValue == null ? JSONObject.NULL : lastResultValue);
            p.put("input_payload", lastInputs);
            p.put("result_payload", lastResults);
            p.put("standard_reference", standard);
            p.put("performed_by_employee_id", context.str("performed_by_employee_id"));
            p.put("remarks", NpdUtil.orNull(inputs.str("remarks")));
            p.put("status", "ACTIVE");
            return api.insert("qc_calculation_records", p);
        }, (saved, err) -> {
            button.setEnabled(true);
            if (err != null) { a.toast(Api.message(err)); return; }
            a.toast("Calculation saved as " + saved.optString("calculation_number") + ".");
            Module m = Catalog.get("qc_calculations");
            if (m != null) a.push(new RecordScreen(a, m, saved.optString("id")));
        });
    }

    /** "Show calculation details" action on a saved record: inputs and results in readable form. */
    static void showDetails(MainActivity a, JSONObject row) {
        StringBuilder b = new StringBuilder();
        b.append(Ui.pretty(Lookups.j(row, "calculation_type"))).append(" · ").append(Ui.date(Lookups.j(row, "calculation_date"))).append('\n');
        b.append("Standard: ").append(Lookups.j(row, "standard_reference")).append("\n\nINPUTS\n");
        JSONObject in = row.optJSONObject("input_payload");
        if (in != null) for (java.util.Iterator<String> it = in.keys(); it.hasNext(); ) { String k = it.next(); b.append(k).append(": ").append(in.opt(k)).append('\n'); }
        b.append("\nRESULT\n");
        JSONObject res = row.optJSONObject("result_payload");
        if (res != null) {
            JSONObject curve = res.optJSONObject("curve");
            if (curve != null) {
                for (int d = 1; d <= 16; d++) if (curve.has(String.valueOf(d))) b.append("J").append(d).append(": ").append(curve.opt(String.valueOf(d))).append(" HRC\n");
            } else {
                for (java.util.Iterator<String> it = res.keys(); it.hasNext(); ) {
                    String k = it.next();
                    Object v = res.opt(k);
                    if (v == null || v == JSONObject.NULL) continue;
                    b.append(Labels.header(k)).append(": ").append(v).append('\n');
                }
            }
        }
        new android.app.AlertDialog.Builder(a).setTitle(Lookups.j(row, "calculation_number")).setMessage(b.toString()).setPositiveButton("OK", null).show();
    }
}
