package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;

/**
 * Incoming-material calculations ported 1:1 from the website: core/calculations.py (Jominy curve, DI factor
 * product, band status), core/steel_balance.py and the small helpers of rmtc_service.py / material_inward.py.
 */
final class IncCalc {
    private IncCalc() { }

    /** Python round(value, n): exact binary value rounded half-even. */
    static double round(double value, int decimals) {
        if (Double.isNaN(value) || Double.isInfinite(value)) return value;
        return new BigDecimal(value).setScale(decimals, RoundingMode.HALF_EVEN).doubleValue();
    }

    /** _num(): None / "" -> null, else float(value). */
    static Double num(Object v) { return Rules.number(v); }

    /** float(value or 0). */
    static double f(Object v) {
        Double d = num(v);
        return d == null ? 0.0 : d;
    }

    /** Python "row.get(a) or row.get(b) or …" for numbers: first value that is not null / zero, else 0. */
    static double first(JSONObject row, String... keys) {
        if (row == null) return 0.0;
        for (String k : keys) {
            Double d = num(row.opt(k));
            if (d != null && d != 0.0) return d;
        }
        return 0.0;
    }

    /** Python "a or b": first non-empty text. */
    static String firstText(String... values) {
        for (String v : values) if (v != null && !v.trim().isEmpty() && !"null".equals(v)) return v;
        return "";
    }

    // ---------------------------------------------------------------- chemistry
    private static final Map<String, String[]> ALIASES = new LinkedHashMap<>();
    static {
        ALIASES.put("C", new String[]{"C", "C%", "CARBON"});
        ALIASES.put("MN", new String[]{"MN", "MN%", "MANGANESE"});
        ALIASES.put("CR", new String[]{"CR", "CR%", "CHROMIUM"});
        ALIASES.put("NI", new String[]{"NI", "NI%", "NICKEL"});
        ALIASES.put("MO", new String[]{"MO", "MO%", "MOLYBDENUM"});
        ALIASES.put("SI", new String[]{"SI", "SI%", "SILICON"});
        ALIASES.put("CU", new String[]{"CU", "CU%", "COPPER"});
        ALIASES.put("V", new String[]{"V", "V%", "VANADIUM"});
    }

    /** chemistry_value(chemistry, symbol, default 0). Map values may be null (missing actual). */
    static double chemistryValue(Map<String, Object> chemistry, String symbol) {
        Map<String, Object> normalized = new LinkedHashMap<>();
        for (Map.Entry<String, Object> e : chemistry.entrySet()) normalized.put(String.valueOf(e.getKey()).trim().toUpperCase(Locale.ROOT), e.getValue());
        String sym = symbol.toUpperCase(Locale.ROOT);
        String[] keys = ALIASES.containsKey(sym) ? ALIASES.get(sym) : new String[]{sym};
        for (String k : keys) {
            Double v = num(normalized.get(k));
            if (v != null) return v;
        }
        return 0.0;
    }

    /** calculate_jominy_curve: J1..J16 HRC (JUST.xls formulas), rounded to 3 decimals. */
    static Map<Integer, Double> jominyCurve(Map<String, Object> chem) {
        double c = chemistryValue(chem, "C"), mn = chemistryValue(chem, "MN"), cr = chemistryValue(chem, "CR"),
            ni = chemistryValue(chem, "NI"), mo = chemistryValue(chem, "MO");
        double j1 = 37.0 + (c - 0.08) * 60.0;
        double j4 = 87.0 * c + 16.0 * mn + 13.25 * cr + 5.3 * ni + 28.5 * mo + 22.0 - (21.2 * Math.sqrt(4.0) - 2.21 * 4.0);
        double j2 = j1 - (j1 - j4) * 0.1;
        double j3 = j1 - (j1 - j4) * 0.5;
        Map<Integer, Double> curve = new TreeMap<>();
        curve.put(1, round(j1, 3));
        curve.put(2, round(j2, 3));
        curve.put(3, round(j3, 3));
        curve.put(4, round(j4, 3));
        for (int d = 5; d <= 16; d++) {
            double v = 87.0 * c + 16.0 * mn + 14.0 * cr + 5.3 * ni + 29.0 * mo + 22.0 - (21.2 * Math.sqrt((double) d) - 2.21 * (double) d);
            curve.put(d, round(v, 3));
        }
        return curve;
    }

    /** Result of calculate_di. */
    static final class Di {
        Double value; String error; final Map<String, Double> factors = new LinkedHashMap<>();
    }

    private static Double approxLookup(double value, String header) {
        int col = -1;
        for (int i = 0; i < IncDiTable.HEADERS.length; i++) if (IncDiTable.HEADERS[i].equals(header)) col = i;
        double[][] rows = IncDiTable.ROWS;
        // bisect.bisect_right(alloy, value) - 1
        int lo = 0, hi = rows.length;
        while (lo < hi) {
            int mid = (lo + hi) >>> 1;
            if (value < rows[mid][0]) hi = mid; else lo = mid + 1;
        }
        int pos = lo - 1;
        if (pos < 0) pos = 0;
        double v = rows[Math.min(pos, rows.length - 1)][col];
        return Double.isNaN(v) ? null : v;
    }

    /** calculate_di: approximate VLOOKUP factor product of DI Hardenability.XLSX. */
    static Di calculateDi(Map<String, Object> chem, int grainSize) {
        Di out = new Di();
        if (grainSize < 4 || grainSize > 8) { out.error = "Grain size must be between 4 and 8."; return out; }
        String grainHeader = "C(GS " + grainSize + ")";
        LinkedHashMap<String, Double> inputs = new LinkedHashMap<>();
        inputs.put(grainHeader, chemistryValue(chem, "C"));
        inputs.put("Mn", chemistryValue(chem, "MN"));
        inputs.put("Si", chemistryValue(chem, "SI"));
        inputs.put("Ni", chemistryValue(chem, "NI"));
        inputs.put("Cr", chemistryValue(chem, "CR"));
        inputs.put("Mo", chemistryValue(chem, "MO"));
        inputs.put("Cu", chemistryValue(chem, "CU"));
        inputs.put("V", chemistryValue(chem, "V"));
        List<String> missing = new ArrayList<>();
        for (Map.Entry<String, Double> e : inputs.entrySet()) {
            Double fct = approxLookup(e.getValue(), e.getKey());
            out.factors.put(e.getKey(), fct);
            if (fct == null) missing.add(e.getKey());
        }
        if (!missing.isEmpty()) { out.error = "Factor unavailable for: " + String.join(", ", missing); return out; }
        double result = 1.0;
        for (Double fct : out.factors.values()) result = result * fct;
        out.value = round(result, 4);
        return out;
    }

    /** core/calculations.band_status (also Rules.band). */
    static String band(Object value, Object min, Object max, boolean applicable) { return Rules.band(value, min, max, applicable); }

    /** rmtc_pages._requirement_result. */
    static String requirement(String actual, String requirement, boolean applicable) {
        if (!applicable) return Rules.NOT_APPLICABLE;
        return Rules.requirement(requirement, actual);
    }

    /** RMTCService._range: two numbers = (min, max), one number = (n, n). */
    static Double[] range(String text) {
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("-?\\d+(?:\\.\\d+)?").matcher(text == null ? "" : text);
        List<Double> nums = new ArrayList<>();
        while (m.find()) nums.add(Double.parseDouble(m.group()));
        if (nums.size() >= 2) return new Double[]{Math.min(nums.get(0), nums.get(1)), Math.max(nums.get(0), nums.get(1))};
        if (nums.size() == 1) return new Double[]{nums.get(0), nums.get(0)};
        return new Double[]{null, null};
    }

    /** core/steel_balance.remaining_planned_steel. */
    static double remainingPlanned(Object planned, Object inward) {
        return round(Math.max(f(planned) - f(inward), 0.0), 3);
    }

    /** normalize_heat_number / normalize_supplier_rmtc_number: upper-case alphanumerics only. */
    static String normalize(String value) {
        return (value == null ? "" : value).replaceAll("[^A-Za-z0-9]", "").toUpperCase(Locale.ROOT);
    }

    // ---------------------------------------------------------------- shared loaders
    /** Active employees holding one approval authority (RMTCService.employees). */
    static JSONArray employeesWith(Api api, String authority, boolean fallbackAll) throws Exception {
        JSONArray all = Lookups.rows(api, Lookups.employees());
        JSONArray out = new JSONArray();
        for (int i = 0; i < all.length(); i++) {
            JSONObject r = all.optJSONObject(i);
            if (r == null) continue;
            JSONArray auth = r.optJSONArray("approval_authorities");
            boolean has = false;
            if (auth != null) for (int k = 0; k < auth.length(); k++) if (authority.equals(auth.optString(k))) has = true;
            if (has) out.put(r);
        }
        return out.length() == 0 && fallbackAll ? all : out;
    }

    /** Lookup with only the employees holding an authority (dropdown on forms). */
    static Field.Lookup employeeLookup(String authority) {
        return new Field.Lookup("employees", "id,employee_code,first_name,last_name,designation,department,approval_authorities",
            "&status=eq.ACTIVE&approval_authorities=cs.%7B" + authority + "%7D", "employee_code.asc", Lookups.EMPLOYEE);
    }

    static JSONObject one(Api api, String path) throws Exception {
        JSONArray r = api.rows(path);
        return r.length() == 0 ? null : r.getJSONObject(0);
    }

    static List<JSONObject> list(JSONArray rows) {
        List<JSONObject> out = new ArrayList<>();
        for (int i = 0; rows != null && i < rows.length(); i++) { JSONObject r = rows.optJSONObject(i); if (r != null) out.add(r); }
        return out;
    }

    /** JSON value for a nullable number. */
    static Object jn(Double d) { return d == null ? JSONObject.NULL : (Object) d; }
    static Object jt(String s) { return s == null || s.trim().isEmpty() ? JSONObject.NULL : s.trim(); }
    static Object jo(JSONObject row, String key) {
        if (row == null || !row.has(key) || row.isNull(key)) return JSONObject.NULL;
        return row.opt(key);
    }

    static String kg(double v) { return Ui.num(v, 3) + " kg"; }

    /** Website disposition labels (core/ui.DISPOSITION_LABELS without the colour dots). */
    static final String[] DISPOSITIONS = {"PENDING", "ON_HOLD", "ACCEPTED", "ACCEPTED_UNDER_RESERVE", "REJECTED"};
}
