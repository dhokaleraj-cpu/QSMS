package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * R39 · Part "Sections applicable" (port of core/part_process_service.py PART_SECTION_REGISTRY / part_applicable_sections /
 * sections_storage): parts.applicable_sections text[] (NULL = every section applicable) and the legacy jsonb
 * parts.section_applicability (core/part_sections.py keys, missing key = applicable) are written together. Part Master
 * record actions / child tables / native editors of Not Applicable sections are hidden in the app.
 */
public final class MstPartSections extends Screen {
    /** key, label, group, legacy core.part_sections key ("" = new key). */
    static final String[][] REGISTRY = {
        {"DRAWINGS", "Controlled Drawings (Finish / Forging / Heat Treatment)", "PART", "controlled_drawings"},
        {"STANDARDS", "Customer Standards & Specifications", "PART", "customer_standards"},
        {"APPROVED_SOURCES", "Approved Sources (Suppliers / Steel Mills)", "PART", "approved_sources"},
        {"RAW_MATERIAL", "Raw Material Details / Forging Parameters", "PART", "raw_material"},
        {"SUPPLIER_TECHNICAL_DATA", "Supplier Technical Data (RM technical rows)", "PART", "supplier_technical_data"},
        {"PRICE_HISTORY", "Supplier / FSI Part Price History", "PART", "price_history"},
        {"PROCESS_SPECIFICATIONS", "OSP / Process Inspection Requirements (MetLAB)", "PART", "osp_metlab"},
        {"FINAL_METALLURGICAL", "Final Dispatch Metallurgical Requirements", "PART", "final_metallurgical"},
        {"PROCESSES", "Part Processes & Drawings (routing, process drawings / specs)", "PART", "process_routing"},
        {"CHEMISTRY", "Chemical Composition", "METALLURGICAL", "chemistry"},
        {"MECHANICAL", "Mechanical Properties (tensile / yield / elongation / impact)", "METALLURGICAL", ""},
        {"JOMINY", "Jominy / Hardenability", "METALLURGICAL", "jominy"},
        {"DI_VALUE", "DI Value", "METALLURGICAL", "di_value"},
        {"GRAIN_SIZE", "Grain Size", "METALLURGICAL", ""},
        {"INCLUSION", "Inclusion Rating", "METALLURGICAL", ""},
        {"MICROSTRUCTURE", "Microstructure", "METALLURGICAL", "microstructure"},
        {"HARDNESS", "Hardness", "METALLURGICAL", ""},
        {"CASE_DEPTH", "Case Depth", "METALLURGICAL", ""},
        {"HEAT_TREATMENT", "Heat Treatment", "METALLURGICAL", "heat_treatment"},
        {"ULTRASONIC", "Ultrasonic Testing", "METALLURGICAL", ""},
        {"MACRO", "Macro Etch / Macro Structure", "METALLURGICAL", ""},
    };
    /** core/part_sections.py SECTION_KEYS (legacy jsonb keys). */
    static final String[] LEGACY_KEYS = {"controlled_drawings", "customer_standards", "approved_sources", "raw_material", "supplier_technical_data",
        "price_history", "jominy", "osp_metlab", "final_metallurgical", "process_routing", "chemistry", "di_value", "heat_treatment", "microstructure"};
    /** Part child table -> section key (CHILD_TABLE_SECTION + controlled drawings). */
    static final Map<String, String> CHILD_TABLE = new HashMap<>();
    /** Part Master record action label -> section key. */
    static final Map<String, String> ACTION = new HashMap<>();
    static {
        CHILD_TABLE.put("part_raw_material_details", "RAW_MATERIAL");
        CHILD_TABLE.put("part_raw_material_technical_data", "SUPPLIER_TECHNICAL_DATA");
        CHILD_TABLE.put("part_supplier_links", "APPROVED_SOURCES");
        CHILD_TABLE.put("part_supplier_price_history", "PRICE_HISTORY");
        CHILD_TABLE.put("part_process_specifications", "PROCESSES");
        CHILD_TABLE.put("part_process_parameter_specifications", "PROCESS_SPECIFICATIONS");
        CHILD_TABLE.put("part_metallurgical_requirements", "FINAL_METALLURGICAL");
        CHILD_TABLE.put("part_heat_treatment_details", "HEAT_TREATMENT");
        CHILD_TABLE.put("part_jominy_requirements", "JOMINY");
        CHILD_TABLE.put("part_standard_links", "STANDARDS");
        CHILD_TABLE.put("part_process_routes", "PROCESSES");
        CHILD_TABLE.put("document_attachments", "DRAWINGS");
        ACTION.put("Raw material details", "RAW_MATERIAL");
        ACTION.put("Supplier technical data", "SUPPLIER_TECHNICAL_DATA");
        ACTION.put("Price history", "PRICE_HISTORY");
        ACTION.put("Approved sources", "APPROVED_SOURCES");
        ACTION.put("Jominy requirements", "JOMINY");
        ACTION.put("Metallurgical requirements", "FINAL_METALLURGICAL");
        ACTION.put("Standards", "STANDARDS");
        ACTION.put("Controlled drawings", "DRAWINGS");
        ACTION.put("Part processes & drawings", "PROCESSES");
    }

    static String label(String key) {
        for (String[] r : REGISTRY) if (r[0].equals(key)) return r[1];
        return Ui.pretty(key);
    }

    private static Boolean bool(Object v) {
        if (v instanceof Boolean) return (Boolean) v;
        if (v == null || v == JSONObject.NULL) return null;
        if (v instanceof Number) return ((Number) v).doubleValue() != 0;
        String t = String.valueOf(v).trim().toLowerCase(Locale.ROOT);
        switch (t) {
            case "1": case "true": case "yes": case "y": case "on": case "applicable": case "t": return true;
            case "0": case "false": case "no": case "n": case "off": case "na": case "n/a": case "not applicable": case "f": return false;
            default: return null;
        }
    }

    /** Stored text[] (JSON array / "{A,B}" literal) -> keys; null = never chosen. */
    static List<String> stored(Object v) {
        if (v == null || v == JSONObject.NULL) return null;
        List<String> out = new ArrayList<>();
        if (v instanceof JSONArray) {
            JSONArray a = (JSONArray) v;
            for (int i = 0; i < a.length(); i++) { String s = a.optString(i, "").trim(); if (!s.isEmpty()) out.add(s.toUpperCase(Locale.ROOT)); }
            return out;
        }
        String t = String.valueOf(v).trim();
        if (t.isEmpty()) return null;
        if (t.startsWith("[")) {
            try { return stored(new JSONArray(t)); } catch (Exception e) { return out; }
        }
        for (String s : t.replaceAll("^\\{|\\}$", "").split(",")) { s = s.trim().replace("\"", ""); if (!s.isEmpty()) out.add(s.toUpperCase(Locale.ROOT)); }
        return out;
    }

    /** part_applicable_sections: applicable keys of a parts row. */
    static Set<String> applicable(JSONObject part) {
        Set<String> out = new LinkedHashSet<>();
        List<String> s = part == null ? null : stored(part.opt("applicable_sections"));
        if (s != null) {
            for (String[] r : REGISTRY) if (s.contains(r[0])) out.add(r[0]);
            return out;
        }
        JSONObject legacy = null;
        Object lv = part == null ? null : part.opt("section_applicability");
        if (lv instanceof JSONObject) legacy = (JSONObject) lv;
        else if (lv instanceof String) { try { legacy = new JSONObject((String) lv); } catch (Exception ignored) { } }
        for (String[] r : REGISTRY) {
            Boolean b = legacy == null || r[3].isEmpty() ? null : bool(legacy.opt(r[3]));
            if (b == null || b) out.add(r[0]);
        }
        return out;
    }

    static boolean isApplicable(JSONObject part, String key) {
        if (key == null || key.isEmpty()) return true;
        boolean known = false;
        for (String[] r : REGISTRY) if (r[0].equals(key)) known = true;
        return !known || applicable(part).contains(key);
    }

    /** RecordScreen (Part Master): show this record action? */
    static boolean showAction(JSONObject part, String actionLabel) { return isApplicable(part, ACTION.get(actionLabel)); }

    /** RecordScreen (Part Master): show this child table? */
    static boolean showChild(JSONObject part, String table) { return isApplicable(part, CHILD_TABLE.get(table)); }

    /** sections_storage: {"applicable_sections": [...registry order], "section_applicability": {legacy: bool}}. */
    static JSONObject storage(Set<String> chosen) throws Exception {
        JSONArray keys = new JSONArray();
        for (String[] r : REGISTRY) if (chosen.contains(r[0])) keys.put(r[0]);
        JSONObject legacy = new JSONObject();
        for (String lk : LEGACY_KEYS) {
            String nk = null;
            for (String[] r : REGISTRY) if (r[3].equals(lk)) nk = r[0];
            legacy.put(lk, nk == null || chosen.contains(nk));
        }
        return new JSONObject().put("applicable_sections", keys).put("section_applicability", legacy);
    }

    static List<String> notApplicableLabels(Set<String> applicable) {
        List<String> out = new ArrayList<>();
        for (String[] r : REGISTRY) if (!applicable.contains(r[0])) out.add(r[1]);
        return out;
    }

    // ============================================================== screen: Sections applicable checklist
    private final String partId;
    private JSONObject part;
    private final Map<String, CheckBox> boxes = new HashMap<>();
    private boolean writable;

    public MstPartSections(MainActivity a, JSONObject part) { super(a); this.part = part; this.partId = Lookups.j(part, "id"); }

    @Override public String title() { return "Sections applicable"; }
    @Override public String subtitle() { return MstPartGrid.partLabel(part); }
    @Override public int tab() { return Catalog.MASTERS; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            boolean[] p = EcnData.permissions(api);
            JSONArray r = api.rows("parts?select=*&id=eq." + Api.enc(partId) + "&limit=1");
            if (r.length() == 0) throw new Api.ApiException(404, "Part not found or not visible for your role.");
            return new Object[]{p, r.getJSONObject(0)};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            boolean[] p = (boolean[]) res[0];
            writable = p[0] || p[1];
            part = (JSONObject) res[1];
            render();
        });
        return scroll;
    }

    private void render() {
        offlineNote();
        Set<String> app = applicable(part);
        add(MstForm.noteCard(a, "Tick the sections that apply to this Part. Not applicable sections are hidden in Part Master, skipped by RMTC / "
            + "MetLAB checks and omitted from the Part print. A Part where nothing was chosen yet has every section applicable."), 0);
        String group = "";
        LinearLayout card = null;
        for (String[] r : REGISTRY) {
            if (!r[2].equals(group)) {
                group = r[2];
                add(Ui.label(a, "PART".equals(group) ? "Part Master sections" : "Metallurgical sections (RMTC / MetLAB)"), 12);
                card = Ui.card(a);
                add(card, 2);
            }
            CheckBox cb = new CheckBox(a);
            cb.setText(r[1]);
            cb.setTextColor(Ui.TEXT);
            cb.setChecked(app.contains(r[0]));
            cb.setEnabled(writable);
            boxes.put(r[0], cb);
            card.addView(cb);
        }
        if (!writable) { add(Ui.text(a, "Part Master create / edit permission is required to change the sections.", 12, Ui.MUTED, false), 10); return; }
        LinearLayout row = Ui.hbox(a);
        Button all = Ui.outline(a, "Tick all", Ui.TEAL);
        all.setOnClickListener(v -> { for (CheckBox cb : boxes.values()) cb.setChecked(true); });
        row.addView(all, Ui.weight(1));
        add(row, 10);
        Button save = Ui.primary(a, "Save sections applicable");
        save.setOnClickListener(v -> save(save));
        add(save, 10);
        TextView note = Ui.text(a, "", 12, Ui.MUTED, false);
        List<String> na = notApplicableLabels(app);
        note.setText(na.isEmpty() ? "Every section is applicable." : "Not applicable now: " + String.join(", ", na));
        add(note, 8);
    }

    private void save(Button b) {
        Set<String> chosen = new LinkedHashSet<>();
        for (Map.Entry<String, CheckBox> e : boxes.entrySet()) if (e.getValue().isChecked()) chosen.add(e.getKey());
        b.setEnabled(false);
        Api.async(() -> api.update("parts", partId, storage(chosen)), (r, err) -> {
            b.setEnabled(true);
            if (err != null) { a.toast(Api.message(err)); return; }
            a.toast("Sections applicable saved (" + chosen.size() + " of " + REGISTRY.length + ").");
            Lookups.invalidate();
            a.back();
        });
    }
}
