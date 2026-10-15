package com.fourstar.qcmsapp;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Exact ports of the website's QC calculations (pure Java, no Android types):
 *  - core/calculations.py   calculate_jominy_curve, calculate_di (+ _approx_lookup on the DI factor table)
 *  - core/hardness_conversion.py   convert_hardness (ASTM E 140-02 Table 1, linear interpolation, no extrapolation)
 * Results are LinkedHashMaps with the same keys / key order as the Python dicts (saved as jsonb payloads).
 */
final class NpdCalc {
    private NpdCalc() { }

    /** SCALE_LABELS of core/hardness_conversion.py (same order). */
    static final String[][] SCALES = {
        {"HRC", "Rockwell C (HRC)"},
        {"HV", "Vickers (HV)"},
        {"HBS", "Brinell - standard ball 3000 kgf (HBS)"},
        {"HBW", "Brinell - carbide ball 3000 kgf (HBW)"},
        {"HK", "Knoop 500 gf and over (HK)"},
        {"HRA", "Rockwell A (HRA)"},
        {"HRD", "Rockwell D (HRD)"},
        {"HR15N", "Rockwell 15-N (HR15N)"},
        {"HR30N", "Rockwell 30-N (HR30N)"},
        {"HR45N", "Rockwell 45-N (HR45N)"},
        {"HSc", "Scleroscope hardness (HSc)"},
    };

    static String scaleLabel(String scale) {
        for (String[] s : SCALES) if (s[0].equals(scale)) return s[1];
        return null;
    }

    /** Python round(value, digits): exact binary value, half-even. */
    static double round(double value, int digits) {
        if (Double.isNaN(value) || Double.isInfinite(value)) return value;
        return new BigDecimal(value).setScale(digits, RoundingMode.HALF_EVEN).doubleValue();
    }

    // ------------------------------------------------------------------ chemistry
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

    /** chemistry_value(): first alias with a numeric value, else default 0.0. */
    static double chemistryValue(Map<String, ?> chemistry, String symbol) {
        Map<String, Object> normalized = new LinkedHashMap<>();
        for (Map.Entry<String, ?> e : chemistry.entrySet()) normalized.put(e.getKey().trim().toUpperCase(Locale.ROOT), e.getValue());
        String[] keys = ALIASES.get(symbol.toUpperCase(Locale.ROOT));
        if (keys == null) keys = new String[]{symbol.toUpperCase(Locale.ROOT)};
        for (String k : keys) {
            Double v = num(normalized.get(k));
            if (v != null) return v;
        }
        return 0.0;
    }

    private static Double num(Object value) {
        if (value == null) return null;
        if (value instanceof Number) return ((Number) value).doubleValue();
        String s = String.valueOf(value).trim();
        if (s.isEmpty()) return null;
        try { return Double.parseDouble(s); } catch (NumberFormatException e) { return null; }
    }

    // ------------------------------------------------------------------ Jominy
    /** calculate_jominy_curve(): J1..J16 HRC, rounded to 3 decimals. */
    static LinkedHashMap<Integer, Double> jominyCurve(Map<String, ?> chemistry) {
        double c = chemistryValue(chemistry, "C");
        double mn = chemistryValue(chemistry, "MN");
        double cr = chemistryValue(chemistry, "CR");
        double ni = chemistryValue(chemistry, "NI");
        double mo = chemistryValue(chemistry, "MO");

        double j1 = 37.0 + (c - 0.08) * 60.0;
        double j4 = 87.0 * c + 16.0 * mn + 13.25 * cr + 5.3 * ni + 28.5 * mo + 22.0 - (21.2 * Math.sqrt(4.0) - 2.21 * 4.0);
        double j2 = j1 - (j1 - j4) * 0.1;
        double j3 = j1 - (j1 - j4) * 0.5;
        LinkedHashMap<Integer, Double> curve = new LinkedHashMap<>();
        curve.put(1, j1); curve.put(2, j2); curve.put(3, j3); curve.put(4, j4);
        for (int distance = 5; distance < 17; distance++) {
            curve.put(distance, 87.0 * c + 16.0 * mn + 14.0 * cr + 5.3 * ni + 29.0 * mo + 22.0
                - (21.2 * Math.sqrt((double) distance) - 2.21 * (double) distance));
        }
        LinkedHashMap<Integer, Double> out = new LinkedHashMap<>();
        for (Map.Entry<Integer, Double> e : curve.entrySet()) out.put(e.getKey(), round(e.getValue(), 3));
        return out;
    }

    // ------------------------------------------------------------------ DI
    private static int column(String header) {
        for (int i = 1; i < NpdTables.DI_HEADERS.length; i++) if (NpdTables.DI_HEADERS[i].equals(header)) return i;
        throw new IllegalArgumentException(header);
    }

    /** _approx_lookup(): bisect_right on the Alloy% column, minus one (Excel approximate VLOOKUP). Null = blank factor. */
    static Double approxLookup(double value, String header) {
        double[][] rows = NpdTables.DI_ROWS;
        int col = column(header);
        int lo = 0, hi = rows.length;
        while (lo < hi) {   // bisect_right
            int mid = (lo + hi) >>> 1;
            if (value < rows[mid][0]) hi = mid; else lo = mid + 1;
        }
        int pos = lo - 1;
        if (pos < 0) pos = 0;
        double v = rows[Math.min(pos, rows.length - 1)][col];
        return Double.isNaN(v) ? null : v;
    }

    /** calculate_di(): {value, factors, error}. */
    static LinkedHashMap<String, Object> di(Map<String, ?> chemistry, int grainSize) {
        LinkedHashMap<String, Object> out = new LinkedHashMap<>();
        if (grainSize < 4 || grainSize > 8) {
            out.put("value", null);
            out.put("factors", new LinkedHashMap<String, Double>());
            out.put("error", "Grain size must be between 4 and 8.");
            return out;
        }
        String grainHeader = "C(GS " + grainSize + ")";
        LinkedHashMap<String, Double> inputs = new LinkedHashMap<>();
        inputs.put(grainHeader, chemistryValue(chemistry, "C"));
        inputs.put("Mn", chemistryValue(chemistry, "MN"));
        inputs.put("Si", chemistryValue(chemistry, "SI"));
        inputs.put("Ni", chemistryValue(chemistry, "NI"));
        inputs.put("Cr", chemistryValue(chemistry, "CR"));
        inputs.put("Mo", chemistryValue(chemistry, "MO"));
        inputs.put("Cu", chemistryValue(chemistry, "CU"));
        inputs.put("V", chemistryValue(chemistry, "V"));
        LinkedHashMap<String, Double> factors = new LinkedHashMap<>();
        List<String> missing = new ArrayList<>();
        for (Map.Entry<String, Double> e : inputs.entrySet()) {
            Double f = approxLookup(e.getValue(), e.getKey());
            factors.put(e.getKey(), f);
            if (f == null) missing.add(e.getKey());
        }
        if (!missing.isEmpty()) {
            out.put("value", null);
            out.put("factors", factors);
            out.put("error", "Factor unavailable for: " + String.join(", ", missing));
            return out;
        }
        double result = 1.0;   // math.prod start value
        for (Double f : factors.values()) result *= f;
        out.put("value", round(result, 4));
        out.put("factors", factors);
        out.put("error", null);
        return out;
    }

    // ------------------------------------------------------------------ hardness conversion
    private static int scaleIndex(String scale) {
        for (int i = 0; i < NpdTables.E140_SCALES.length; i++) if (NpdTables.E140_SCALES[i].equals(scale)) return i;
        return -1;
    }

    private static Set<String> outside(int row) {
        String s = NpdTables.E140_OUTSIDE[row];
        return s.isEmpty() ? new HashSet<>() : new HashSet<>(Arrays.asList(s.split(",")));
    }

    /** Python f"{x:g}". */
    static String g(double x) {
        if (x == 0) return (1 / x < 0) ? "-0" : "0";
        if (Double.isNaN(x)) return "nan";
        if (Double.isInfinite(x)) return x > 0 ? "inf" : "-inf";
        BigDecimal r = new BigDecimal(x).round(new MathContext(6, RoundingMode.HALF_EVEN));
        int exp = r.precision() - r.scale() - 1;
        if (exp < -4 || exp >= 6) {
            BigDecimal mant = r.movePointLeft(exp);
            String m = strip(mant.toPlainString());
            String e = String.valueOf(Math.abs(exp));
            if (e.length() < 2) e = "0" + e;
            return m + "e" + (exp < 0 ? "-" : "+") + e;
        }
        return strip(r.toPlainString());
    }

    private static String strip(String s) {
        if (s.contains(".")) {
            s = s.replaceAll("0+$", "");
            if (s.endsWith(".")) s = s.substring(0, s.length() - 1);
        }
        return s;
    }

    /** convert_hardness(): throws IllegalArgumentException with the website's message when not convertible. */
    static LinkedHashMap<String, Object> convertHardness(double number, String sourceScale, String targetScale) {
        sourceScale = sourceScale == null ? "" : sourceScale.trim();
        targetScale = targetScale == null ? "" : targetScale.trim();
        if (scaleLabel(sourceScale) == null || scaleLabel(targetScale) == null) {
            throw new IllegalArgumentException("Select a supported ASTM E140 Table 1 hardness scale.");
        }
        LinkedHashMap<String, Object> out = new LinkedHashMap<>();
        if (sourceScale.equals(targetScale)) {
            out.put("source_value", number);
            out.put("source_scale", sourceScale);
            out.put("target_value", number);
            out.put("target_scale", targetScale);
            out.put("method", "No conversion - identical scale");
            out.put("standard", "ASTM E 140-02 Table 1");
            out.put("warning", "Hardness conversion values are approximate and material-specific.");
            out.put("bracket", null);
            out.put("outside_recommended", false);
            return out;
        }
        int si = scaleIndex(sourceScale), ti = scaleIndex(targetScale);
        double[][] rows = NpdTables.E140_ROWS;
        List<Integer> candidates = new ArrayList<>();
        for (int i = 0; i < rows.length; i++) if (!Double.isNaN(rows[i][si]) && !Double.isNaN(rows[i][ti])) candidates.add(i);
        if (candidates.isEmpty()) {
            throw new IllegalArgumentException("No Table 1 conversion relationship is available from " + sourceScale + " to " + targetScale + ".");
        }
        for (int i : candidates) {
            if (Math.abs(rows[i][si] - number) < 1e-9) {
                Set<String> o = outside(i);
                boolean restricted = o.contains(targetScale) || o.contains(sourceScale);
                double target = rows[i][ti];
                out.put("source_value", number);
                out.put("source_scale", sourceScale);
                out.put("target_value", target);
                out.put("target_scale", targetScale);
                out.put("method", "ASTM E140 Table 1 direct lookup");
                out.put("standard", "ASTM E 140-02 Table 1");
                out.put("warning", restricted
                    ? "Approximate conversion. A parenthesized Brinell value is outside the recommended Brinell testing range."
                    : "Approximate conversion; use only for the material scope of ASTM E140 Table 1.");
                LinkedHashMap<String, double[]> bracket = new LinkedHashMap<>();
                bracket.put(sourceScale, new double[]{number, number});
                bracket.put(targetScale, new double[]{target, target});
                out.put("bracket", bracket);
                out.put("outside_recommended", restricted);
                return out;
            }
        }
        List<Integer> ordered = new ArrayList<>(candidates);
        ordered.sort((x, y) -> Double.compare(rows[x][si], rows[y][si]));   // stable, like sorted()
        double minimum = rows[ordered.get(0)][si];
        double maximum = rows[ordered.get(ordered.size() - 1)][si];
        if (number < minimum || number > maximum) {
            throw new IllegalArgumentException(g(number) + " " + sourceScale + " is outside the supported Table 1 range " + g(minimum) + " to " + g(maximum) + " "
                + sourceScale + ". Extrapolation is not permitted.");
        }
        Integer lower = null, upper = null;
        for (int k = 0; k + 1 < ordered.size(); k++) {
            double x1 = rows[ordered.get(k)][si], x2 = rows[ordered.get(k + 1)][si];
            if (x1 <= number && number <= x2) { lower = ordered.get(k); upper = ordered.get(k + 1); break; }
        }
        if (lower == null) throw new IllegalArgumentException("A valid ASTM E140 Table 1 interpolation bracket could not be found.");
        double x1 = rows[lower][si], x2 = rows[upper][si];
        double y1 = rows[lower][ti], y2 = rows[upper][ti];
        double ratio = x2 == x1 ? 0.0 : (number - x1) / (x2 - x1);
        double target = y1 + ratio * (y2 - y1);
        boolean restricted = false;
        for (int r : new int[]{lower, upper}) {
            Set<String> o = outside(r);
            if (o.contains(sourceScale) || o.contains(targetScale)) restricted = true;
        }
        out.put("source_value", number);
        out.put("source_scale", sourceScale);
        out.put("target_value", round(target, 3));
        out.put("target_scale", targetScale);
        out.put("method", "ASTM E140 Table 1 linear interpolation");
        out.put("standard", "ASTM E 140-02 Table 1");
        out.put("warning", restricted
            ? "Approximate interpolated conversion. The bracket includes a parenthesized Brinell value outside the recommended Brinell testing range."
            : "Approximate interpolated conversion; use only for the material scope of ASTM E140 Table 1.");
        LinkedHashMap<String, double[]> bracket = new LinkedHashMap<>();
        bracket.put(sourceScale, new double[]{x1, x2});
        bracket.put(targetScale, new double[]{y1, y2});
        out.put("bracket", bracket);
        out.put("outside_recommended", restricted);
        return out;
    }
}
