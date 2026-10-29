package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * R39 · "Sections applicable" per RMTC - port of core/section_applicability.py (R38 web).
 * RMTC level: rmtc_approvals.applicable_sections jsonb {key: bool}; NULL / {} = not chosen -> defaults from the covered
 * Parts (parts.section_applicability jsonb, missing key = applicable; parts.applicable_sections text[] = APPLICABLE keys).
 * A Part-default section is applicable by default when it is applicable for at least one covered Part.
 * Not-applicable sections are hidden in the Part Worksheet, saved as NOT_APPLICABLE rows and omitted from the print.
 */
final class IncRmtcSections {
    private IncRmtcSections() { }

    /** key, user label, print title (core.section_applicability.RMTC_SECTIONS). */
    static final String[][] SECTIONS = {
        {"heat_balance", "Global Heat Quantity Balance & Record List", "GLOBAL HEAT QUANTITY BALANCE & RECORD LIST"},
        {"supplier_mechanical", "Supplier RMTC Mechanical Properties", "SUPPLIER RMTC MECHANICAL PROPERTIES"},
        {"chemistry", "Chemical Composition", "Chemical Composition"},
        {"jominy", "Jominy Results", "Jominy Results"},
        {"di_value", "DI / Hardenability", "DI / Hardenability"},
        {"mechanical", "Mechanical Properties (Part requirements)", "Mechanical Properties"},
        {"heat_treatment", "Heat Treatment & Other Requirements", "Heat Treatment & Other Requirements"},
        {"microstructure", "Microstructure Photographs", "RMTC MICROSTRUCTURE PHOTOGRAPHS"},
    };
    static final List<String> PART_DEFAULT_KEYS = Arrays.asList("chemistry", "jominy", "di_value", "heat_treatment", "microstructure");
    static final String[] MECHANICAL_TOKENS = {"tensile", "yield", "elongation", "reduction", "impact", "proof", "mechanical", "uts"};
    private static final Set<String> TRUE = new HashSet<>(Arrays.asList("1", "true", "yes", "y", "on", "applicable", "t"));
    private static final Set<String> FALSE = new HashSet<>(Arrays.asList("0", "false", "no", "n", "off", "na", "n/a", "not applicable", "f"));
    private static final Map<String, String> ALIASES = new LinkedHashMap<>();
    static {
        String[][] a = {{"chemical", "chemistry"}, {"chemicalcomposition", "chemistry"}, {"chemicalanalysis", "chemistry"},
            {"jominyhardenability", "jominy"}, {"hardenability", "di_value"}, {"di", "di_value"}, {"dihardenability", "di_value"},
            {"mechanicalproperties", "mechanical"}, {"suppliermechanicalproperties", "supplier_mechanical"},
            {"heattreatment", "heat_treatment"}, {"otherrequirements", "heat_treatment"}, {"hardness", "heat_treatment"},
            {"grainsize", "heat_treatment"}, {"inclusionrating", "heat_treatment"}, {"ultrasonictest", "heat_treatment"},
            {"macroetch", "heat_treatment"}, {"microstructurephotographs", "microstructure"}, {"heatbalance", "heat_balance"}};
        for (String[] p : a) ALIASES.put(p[0], p[1]);
    }

    static List<String> keys() {
        List<String> k = new ArrayList<>();
        for (String[] s : SECTIONS) k.add(s[0]);
        return k;
    }

    static String label(String key) {
        for (String[] s : SECTIONS) if (s[0].equals(key)) return s[1];
        return key;
    }

    static boolean bool(Object v, boolean def) {
        if (v == null || v == JSONObject.NULL) return def;
        if (v instanceof Boolean) return (Boolean) v;
        if (v instanceof Number) return ((Number) v).doubleValue() != 0;
        String t = String.valueOf(v).trim().toLowerCase(Locale.ROOT);
        if (TRUE.contains(t)) return true;
        if (FALSE.contains(t)) return false;
        return def;
    }

    static JSONObject mapping(Object value) {
        if (value instanceof JSONObject) return (JSONObject) value;
        if (value instanceof String) {
            try { return new JSONObject((String) value); } catch (Exception e) { return null; }
        }
        return null;
    }

    /** normalize_rmtc_sections: every key -> bool (missing / bad = true). */
    static LinkedHashMap<String, Boolean> normalize(Object value) {
        JSONObject m = mapping(value);
        LinkedHashMap<String, Boolean> out = new LinkedHashMap<>();
        for (String k : keys()) out.put(k, bool(m == null ? null : m.opt(k), true));
        return out;
    }

    /** section_key: key / label / alias -> RMTC key. */
    static String sectionKey(Object value) {
        String text = value == null || value == JSONObject.NULL ? "" : String.valueOf(value).trim();
        for (String[] s : SECTIONS) if (s[0].equals(text)) return text;
        for (String[] s : SECTIONS) if (text.equalsIgnoreCase(s[1]) || text.equalsIgnoreCase(s[2])) return s[0];
        String compact = text.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
        return ALIASES.containsKey(compact) ? ALIASES.get(compact) : compact;
    }

    /** part_values: parts.section_applicability (jsonb) + parts.applicable_sections (text[] of APPLICABLE keys) when non-empty. */
    static Map<String, Boolean> partValues(JSONObject part) {
        Map<String, Boolean> values = new LinkedHashMap<>();
        JSONObject legacy = part == null ? null : mapping(part.opt("section_applicability"));
        for (String k : PART_DEFAULT_KEYS) values.put(k, bool(legacy == null ? null : legacy.opt(k), true));
        Object listed = part == null ? null : part.opt("applicable_sections");
        List<String> items = new ArrayList<>();
        if (listed instanceof JSONArray) {
            for (int i = 0; i < ((JSONArray) listed).length(); i++) items.add(((JSONArray) listed).optString(i));
        } else if (listed instanceof String && !((String) listed).trim().isEmpty()) {
            String s = ((String) listed).trim();
            try {
                JSONArray arr = new JSONArray(s);
                for (int i = 0; i < arr.length(); i++) items.add(arr.optString(i));
            } catch (Exception e) {
                for (String p : s.replaceAll("^\\{|\\}$", "").split(",")) if (!p.trim().isEmpty()) items.add(p.trim().replace("\"", ""));
            }
        }
        if (!items.isEmpty()) {
            Set<String> wanted = new HashSet<>();
            for (String it : items) wanted.add(sectionKey(it));
            for (String k : PART_DEFAULT_KEYS) values.put(k, wanted.contains(k));
        }
        return values;
    }

    /** default_rmtc_sections: all true, except a Part section Not Applicable for EVERY covered Part. */
    static LinkedHashMap<String, Boolean> defaults(Collection<JSONObject> parts) {
        LinkedHashMap<String, Boolean> out = normalize(null);
        List<Map<String, Boolean>> per = new ArrayList<>();
        if (parts != null) for (JSONObject p : parts) if (p != null && p.length() > 0) per.add(partValues(p));
        if (per.isEmpty()) return out;
        for (String k : PART_DEFAULT_KEYS) {
            boolean any = false;
            for (Map<String, Boolean> v : per) if (!Boolean.FALSE.equals(v.get(k))) any = true;
            out.put(k, any);
        }
        return out;
    }

    /** rmtc_sections: stored choice when present (NULL / {} = not chosen), else defaults from the covered Parts. */
    static LinkedHashMap<String, Boolean> resolve(JSONObject record, Collection<JSONObject> parts) {
        JSONObject stored = record == null ? null : mapping(record.opt("applicable_sections"));
        if (stored != null && stored.length() > 0) return normalize(stored);
        return defaults(parts);
    }

    static JSONObject stored(Map<String, Boolean> m) {
        JSONObject o = new JSONObject();
        for (String k : keys()) {
            try { o.put(k, m == null || !Boolean.FALSE.equals(m.get(k))); } catch (Exception ignored) { }
        }
        return o;
    }

    static List<String> notApplicableLabels(Map<String, Boolean> m) {
        List<String> out = new ArrayList<>();
        for (String[] s : SECTIONS) if (m != null && Boolean.FALSE.equals(m.get(s[0]))) out.add(s[1]);
        return out;
    }

    static boolean on(Map<String, Boolean> m, String key) { return m == null || !Boolean.FALSE.equals(m.get(key)); }

    static boolean isMechanical(Object name) {
        String t = name == null ? "" : String.valueOf(name).toLowerCase(Locale.ROOT);
        for (String tok : MECHANICAL_TOKENS) if (t.contains(tok)) return true;
        return false;
    }

    /** requirement_applicable: mechanical rows follow 'mechanical', the others 'heat_treatment'. */
    static boolean requirementApplicable(Object name, Map<String, Boolean> m) {
        return on(m, isMechanical(name) ? "mechanical" : "heat_treatment");
    }

    /** Covered part rows (id, section_applicability, applicable_sections) of one RMTC. */
    static List<JSONObject> coveredPartRows(Api api, String rmtcId, JSONObject record) throws Exception {
        List<String> ids = new ArrayList<>();
        if (record != null && !Lookups.j(record, "part_id").isEmpty()) ids.add(Lookups.j(record, "part_id"));
        JSONArray cov = api.rows("rmtc_part_approvals?select=part_id&rmtc_approval_id=eq." + Api.enc(rmtcId) + "&limit=200");
        for (int i = 0; i < cov.length(); i++) {
            String pid = Lookups.j(cov.optJSONObject(i), "part_id");
            if (!pid.isEmpty() && !ids.contains(pid)) ids.add(pid);
        }
        List<JSONObject> out = new ArrayList<>();
        if (ids.isEmpty()) return out;
        JSONArray rows = api.rows("parts?select=id,part_number,section_applicability,applicable_sections&id=in.(" + String.join(",", ids) + ")&limit=200");
        for (int i = 0; i < rows.length(); i++) out.add(rows.optJSONObject(i));
        return out;
    }

    /** Applicability of one RMTC (background thread). */
    static LinkedHashMap<String, Boolean> load(Api api, String rmtcId, JSONObject record) throws Exception {
        return resolve(record, coveredPartRows(api, rmtcId, record));
    }

    // ------------------------------------------------------------------ UI (rmtc_pages._render_rmtc_sections)
    interface Saved { void saved(LinkedHashMap<String, Boolean> m); }

    /** "SECTIONS APPLICABLE (THIS RMTC)" card: ticks + Save (writable) or a read-only summary. */
    static View card(MainActivity a, String rmtcId, LinkedHashMap<String, Boolean> current, boolean writable, Saved saved) {
        LinearLayout box = Ui.card(a);
        box.addView(Ui.text(a, "SECTIONS APPLICABLE (THIS RMTC)", 13, Ui.TEXT, true));
        box.addView(Ui.text(a, "Defaults come from the covered Parts (Part Master · Sections Applicable). Untick a section that does not apply "
            + "to this certificate - it is hidden in the Part Worksheet, saved Not Applicable and omitted from the print.", 11.5f, Ui.MUTED, false));
        List<Field> fields = new ArrayList<>();
        for (String[] s : SECTIONS) fields.add(writable ? Field.bool(s[0], s[1]) : Field.info(s[0], s[1]));
        FormView f = new FormView(a, fields);
        for (String[] s : SECTIONS) f.set(s[0], writable ? (Object) on(current, s[0]) : (on(current, s[0]) ? "Applicable" : "Not applicable"));
        box.addView(f, Ui.matchWrap(a, 4));
        List<String> off = notApplicableLabels(current);
        if (!off.isEmpty()) box.addView(Ui.text(a, "Not applicable for this RMTC: " + String.join(", ", off), 12, Ui.AMBER_FG, false));
        if (writable) {
            Button save = Ui.outline(a, "Save Sections Applicable", Ui.TEAL);
            box.addView(save, Ui.matchWrap(a, 6));
            save.setOnClickListener(v -> {
                LinkedHashMap<String, Boolean> chosen = new LinkedHashMap<>();
                for (String[] s : SECTIONS) chosen.put(s[0], f.bool(s[0]));
                save.setEnabled(false);
                Api api = Api.get(a);
                Api.async(() -> api.update("rmtc_approvals", rmtcId, new JSONObject().put("applicable_sections", stored(chosen))), (res, err) -> {
                    save.setEnabled(true);
                    if (err != null) { a.toast("Sections not saved: " + Api.message(err)); return; }
                    List<String> na = notApplicableLabels(chosen);
                    a.toast("RMTC sections applicable saved." + (na.isEmpty() ? " All sections are applicable." : " Not applicable: " + String.join(", ", na) + "."));
                    if (saved != null) saved.saved(chosen);
                });
            });
        }
        return box;
    }
}
