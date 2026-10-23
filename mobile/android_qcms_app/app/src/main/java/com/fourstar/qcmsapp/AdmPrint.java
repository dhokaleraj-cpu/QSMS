package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * Port of core/print_designer.py: layouts are JSON in master_value_catalog (field_key qcms.print.layout.&lt;DOC&gt;),
 * saved through set_system_value with json.dumps(sort_keys=True, ensure_ascii=False) so every earlier version
 * stays as an INACTIVE row that can be restored. Network methods must run inside Api.async.
 */
final class AdmPrint {
    private AdmPrint() { }

    static final String LAYOUT_KEY_PREFIX = "qcms.print.layout.";

    static final String[][] DOCUMENTS = {
        {"PURCHASE_ORDER", "Purchase Order"}, {"RMTC", "RMTC Report"}, {"METLAB", "MetLAB Report"}, {"BEND_TEST", "Bend Test Report"},
        {"DIMENSIONAL", "Dimensional Report"}, {"MATERIAL_INWARD", "Material Inward Report"}, {"QUALITY_RECORD", "Other Quality Records / Registers"}};

    static final String[][] BAR_STYLES = {{"fill", "Filled heading bar"}, {"underline", "Heading text + underline"}, {"outline", "Outlined heading bar"}};

    /** PO_SECTIONS (heading -> flag). */
    static final String[][] PO_SECTIONS = {
        {"PLANT / COMPANY BRANCH", "show_plant"}, {"VENDOR", "show_vendor"}, {"REFERENCE DETAILS", "show_reference"},
        {"OLD PO DETAILS", "show_old_po"}, {"SHIP TO", "show_ship_to"}, {"PO SOURCE REFERENCE", "show_source_reference"},
        {"RAW MATERIAL DETAILS & SUPPLIER TECHNICAL DATA", "show_technical"}, {"PRICE REVISION HISTORY", "show_price_history"},
        {"COMMENTS OR SPECIAL INSTRUCTIONS", "show_special_instructions"}};

    /** core/po_print_ui.SECTION_OPTIONS (flag, label). */
    static final String[][] SECTION_OPTIONS = {
        {"show_plant", "Plant / Company Branch"}, {"show_vendor", "Vendor"}, {"show_reference", "Reference Details"},
        {"show_old_po", "Old PO Details"}, {"show_ship_to", "Ship To"}, {"show_source_reference", "PO Source Ref (internal only)"},
        {"show_technical", "RM Details & Technical Data"}, {"show_price_history", "Price Revision History"},
        {"show_special_instructions", "Comments / Special Instructions"}, {"show_approval_stamp", "Approval Stamp"}};

    static final String[] PRESET_KEYS = {"B1", "B2", "B3", "B4", "B5"};
    static final String[][] PRESET_NAMES = {
        {"B1", "B1 · Open Lines Teal"}, {"B2", "B2 · Teal Underline"}, {"B3", "B3 · Teal Outline"},
        {"B4", "B4 · Graphite & Teal"}, {"B5", "B5 · Teal Bands (approved)"}};
    static final String DEFAULT_PRESET = "B5";
    static final String[] PRESET_FIELDS = {"accent", "bar", "rule", "head_fill", "label_fill", "remark", "remark_fill", "conclusion"};

    /** Website print_designer REPORT_HEADINGS (headings that can be renamed per report family). */
    static final Map<String, String[]> REPORT_HEADINGS = new LinkedHashMap<>();
    static {
        REPORT_HEADINGS.put("RMTC", new String[]{"RMTC HEADER & TRACEABILITY", "GLOBAL HEAT QUANTITY BALANCE & RECORD LIST", "COVERED PART WORKSHEET REGISTER", "SUPPLIER RMTC MECHANICAL PROPERTIES", "Chemical Composition", "Jominy Results", "DI / Hardenability", "Mechanical Properties"});
        REPORT_HEADINGS.put("METLAB", new String[]{"RAW MATERIAL METALLURGICAL TEST", "METALLURGICAL TEST RESULTS", "MICROSTRUCTURE PHOTOGRAPHS"});
        REPORT_HEADINGS.put("DIMENSIONAL", new String[]{"OSP DIMENSIONAL INSPECTION REPORT", "INSPECTION RESULTS"});
        REPORT_HEADINGS.put("BEND_TEST", new String[]{});
        REPORT_HEADINGS.put("MATERIAL_INWARD", new String[]{"MATERIAL INWARD DETAILS"});
        REPORT_HEADINGS.put("QUALITY_RECORD", new String[]{"RECORD DETAILS", "PHOTOGRAPHS"});
    }

    static final String[] PO_EXTRA_HEADINGS = {"ITEM #", "REQUISITIONER", "SHIP VIA", "INCOTERM", "DELIVERY DATE", "PAYMENT TERM"};

    static String docLabel(String doc) {
        for (String[] d : DOCUMENTS) if (d[0].equals(doc)) return d[1];
        return doc;
    }

    static boolean isPreset(String p) {
        for (String k : PRESET_KEYS) if (k.equals(p)) return true;
        return false;
    }

    static JSONObject preset(String key) {
        JSONObject o = new JSONObject();
        try {
            switch (key) {
                case "B1": o.put("accent", "#0B6E70").put("bar", "fill").put("rule", "#C9D6D6").put("head_fill", "").put("label_fill", "").put("remark", "#9A3412").put("remark_fill", "").put("conclusion", "#166534"); break;
                case "B2": o.put("accent", "#0B6E70").put("bar", "underline").put("rule", "#C9D6D6").put("head_fill", "").put("label_fill", "").put("remark", "#9A3412").put("remark_fill", "").put("conclusion", "#166534"); break;
                case "B3": o.put("accent", "#0B6E70").put("bar", "outline").put("rule", "#C9D6D6").put("head_fill", "").put("label_fill", "").put("remark", "#9A3412").put("remark_fill", "").put("conclusion", "#166534"); break;
                case "B4": o.put("accent", "#334155").put("bar", "fill").put("rule", "#CBD5E1").put("head_fill", "").put("label_fill", "#F1F5F9").put("remark", "#0B6E70").put("remark_fill", "").put("conclusion", "#166534"); break;
                default: o.put("accent", "#0B6E70").put("bar", "fill").put("rule", "#C9D6D6").put("head_fill", "#EAF4F4").put("label_fill", "#F3F8F8").put("remark", "#9A3412").put("remark_fill", "#FFF7ED").put("conclusion", "#166534");
            }
        } catch (Exception ignored) { }
        return o;
    }

    private static void merge(JSONObject into, JSONObject from) {
        for (Iterator<String> it = from.keys(); it.hasNext(); ) {
            String k = it.next();
            try { into.put(k, from.opt(k)); } catch (Exception ignored) { }
        }
    }

    /** default_layout. */
    static JSONObject defaultLayout(String doc) {
        doc = doc == null ? "" : doc.toUpperCase(Locale.ROOT);
        JSONObject l = new JSONObject();
        try {
            l.put("preset", DEFAULT_PRESET);
            merge(l, preset(DEFAULT_PRESET));
            l.put("labels", new JSONObject()).put("company_name", "").put("footer_text", "");
            if (doc.equals("PURCHASE_ORDER")) {
                l.put("title", "PURCHASE ORDER").put("show_approval_stamp", true);
                for (String[] s : PO_SECTIONS) l.put(s[1], true);
            } else {
                l.put("preset", "B1");
                merge(l, preset("B1"));
                l.put("rule", "#9AA5A5").put("body_pt", 8.6).put("heading_pt", 10.5);
            }
        } catch (Exception ignored) { }
        return l;
    }

    private static final Pattern HEX = Pattern.compile("^#[0-9A-Fa-f]{6}$");

    static boolean hex(Object v) { return v instanceof String && HEX.matcher((String) v).matches(); }

    private static boolean barStyle(Object v) {
        for (String[] b : BAR_STYLES) if (b[0].equals(v)) return true;
        return false;
    }

    /** normalize_layout: merge a saved / edited layout over the defaults and drop invalid values. */
    static JSONObject normalize(String doc, JSONObject data) {
        JSONObject base = defaultLayout(doc);
        if (data == null) data = new JSONObject();
        try {
            String p = AdmPy.s(data.opt("preset")).toUpperCase(Locale.ROOT);
            if (isPreset(p) && !p.equals(base.optString("preset"))) { merge(base, preset(p)); base.put("preset", p); }
            for (Iterator<String> it = data.keys(); it.hasNext(); ) {
                String key = it.next();
                Object value = data.opt(key);
                if (key.equals("accent") || key.equals("rule") || key.equals("remark") || key.equals("conclusion")) {
                    if (hex(value)) base.put(key, ((String) value).toUpperCase(Locale.ROOT));
                } else if (key.equals("head_fill") || key.equals("label_fill") || key.equals("remark_fill")) {
                    if (AdmPy.isNull(value) || "".equals(value) || hex(value)) base.put(key, AdmPy.s(value).toUpperCase(Locale.ROOT));
                } else if (key.equals("bar")) {
                    if (barStyle(value)) base.put(key, value);
                } else if (key.equals("body_pt") || key.equals("heading_pt")) {
                    Double d = toFloat(value);
                    if (d != null) base.put(key, Math.max(6.0, Math.min(14.0, d)));
                } else if (key.startsWith("show_")) {
                    base.put(key, pyBool(value));
                } else if (key.equals("labels") && value instanceof JSONObject) {
                    JSONObject in = (JSONObject) value, out = new JSONObject();
                    for (Iterator<String> li = in.keys(); li.hasNext(); ) {
                        String k = li.next();
                        String kk = k.trim(), vv = AdmPy.pyStr(in.opt(k)).trim();
                        if (AdmPy.isNull(in.opt(k))) vv = "None";
                        if (!kk.isEmpty() && !vv.isEmpty()) out.put(kk, vv);
                    }
                    base.put("labels", out);
                } else if (key.equals("title") || key.equals("company_name") || key.equals("footer_text")) {
                    String t = AdmPy.isNull(value) || Boolean.FALSE.equals(value) || "".equals(value) ? "" : AdmPy.pyStr(value);
                    t = t.trim();
                    base.put(key, t.length() > 120 ? t.substring(0, 120) : t);
                }
            }
        } catch (Exception ignored) { }
        return base;
    }

    private static Double toFloat(Object v) {
        if (AdmPy.isNull(v) || v instanceof Boolean) return v instanceof Boolean ? (((Boolean) v) ? 1.0 : 0.0) : null;
        if (v instanceof Number) return ((Number) v).doubleValue();
        try { return Double.parseDouble(String.valueOf(v).trim()); } catch (NumberFormatException e) { return null; }
    }

    /** Python bool() of a JSON value. */
    private static boolean pyBool(Object v) {
        if (AdmPy.isNull(v)) return false;
        if (v instanceof Boolean) return (Boolean) v;
        if (v instanceof Number) return ((Number) v).doubleValue() != 0;
        if (v instanceof String) return !((String) v).isEmpty();
        if (v instanceof JSONArray) return ((JSONArray) v).length() > 0;
        if (v instanceof JSONObject) return ((JSONObject) v).length() > 0;
        return true;
    }

    static String layoutKey(String doc) { return LAYOUT_KEY_PREFIX + (doc == null ? "" : doc.toUpperCase(Locale.ROOT)); }

    static JSONObject parse(String text) {
        try { return new JSONObject(text == null || text.trim().isEmpty() ? "{}" : text); } catch (Exception e) { return new JSONObject(); }
    }

    /** read_layout. */
    static JSONObject read(Api api, String doc) {
        JSONObject saved;
        try {
            JSONObject row = AdmDb.first(AdmDb.select(api, "master_value_catalog", AdmDb.eq("field_key", layoutKey(doc), "status", "ACTIVE"), "last_used_at.desc", 1));
            saved = row == null ? new JSONObject() : parse(AdmPy.j(row, "value_text"));
        } catch (Exception e) {
            saved = new JSONObject();
        }
        return normalize(doc, saved);
    }

    /** save_layout (admin only, through set_system_value). */
    static JSONObject save(Api api, String doc, JSONObject layout) throws Exception {
        JSONObject clean = normalize(doc, layout);
        AdmDb.setSystemValue(api, layoutKey(doc), AdmPy.dumps(clean));
        return clean;
    }

    /** layout_history (newest first, 20 rows). */
    static List<JSONObject> history(Api api, String doc) {
        try { return AdmDb.list(AdmDb.select(api, "master_value_catalog", AdmDb.eq("field_key", layoutKey(doc)), "updated_at.desc", 20)); }
        catch (Exception e) { return new java.util.ArrayList<>(); }
    }

    /** Layout with the preset switched like the designer does (preset fields dropped, then normalized). */
    static JSONObject withPreset(String doc, JSONObject layout, String preset) {
        JSONObject copy = new JSONObject();
        try {
            for (Iterator<String> it = layout.keys(); it.hasNext(); ) {
                String k = it.next();
                boolean presetField = false;
                for (String f : PRESET_FIELDS) if (f.equals(k)) presetField = true;
                if (!presetField) copy.put(k, layout.opt(k));
            }
            copy.put("preset", preset);
        } catch (Exception ignored) { }
        return normalize(doc, copy);
    }
}
