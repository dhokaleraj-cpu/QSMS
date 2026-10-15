package com.fourstar.qcmsapp;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Pass / fail rules ported 1:1 from the website (core/inspection_service.py evaluate_characteristic,
 * core/calculations.py band_status, rmtc_pages._requirement_result) so the app gives the same result.
 */
public final class Rules {
    private Rules() { }

    public static final String PASS = "PASS", FAIL = "FAIL", NOT_EVALUATED = "NOT_EVALUATED", NOT_APPLICABLE = "NOT_APPLICABLE";
    private static final String[] ATTRIBUTE_OK = {"OK", "PASS", "ACCEPTED", "FOUND OK", "YES", "CONFORM", "SATISFACTORY", "FOR REF"};

    public static Double number(Object v) {
        if (v == null || v == JSONObject.NULL) return null;
        String s = String.valueOf(v).trim().replace(",", "");
        if (s.isEmpty() || "null".equals(s)) return null;
        try { return Double.parseDouble(s); } catch (NumberFormatException e) { return null; }
    }

    static String text(Object v) {
        if (v == null || v == JSONObject.NULL) return "";
        String s = String.valueOf(v).trim();
        return "null".equals(s) ? "" : s;
    }

    static boolean attributePass(String value) {
        String t = text(value).toUpperCase(Locale.ROOT);
        if (t.isEmpty()) return false;
        for (String ok : ATTRIBUTE_OK) if (t.contains(ok)) return true;
        return false;
    }

    static String normalized(String value) {
        Matcher m = Pattern.compile("[a-z0-9]+").matcher(text(value).toLowerCase(Locale.ROOT));
        StringBuilder b = new StringBuilder();
        while (m.find()) { if (b.length() > 0) b.append(' '); b.append(m.group()); }
        return b.toString();
    }

    /** Python difflib.SequenceMatcher(None, a, b).ratio() (Ratcliff-Obershelp). */
    public static double ratio(String a, String b) {
        int total = a.length() + b.length();
        if (total == 0) return 1.0;
        return 2.0 * matches(a, 0, a.length(), b, 0, b.length()) / total;
    }

    private static int matches(String a, int alo, int ahi, String b, int blo, int bhi) {
        int bestI = alo, bestJ = blo, bestSize = 0;
        int[] prev = new int[bhi - blo + 1];
        for (int i = alo; i < ahi; i++) {
            int[] cur = new int[bhi - blo + 1];
            for (int j = blo; j < bhi; j++) {
                if (a.charAt(i) == b.charAt(j)) {
                    int k = prev[j - blo] + 1;
                    cur[j - blo + 1] = k;
                    if (k > bestSize) { bestI = i - k + 1; bestJ = j - k + 1; bestSize = k; }
                }
            }
            prev = cur;
        }
        if (bestSize == 0) return 0;
        return bestSize + matches(a, alo, bestI, b, blo, bestJ) + matches(a, bestI + bestSize, ahi, b, bestJ + bestSize, bhi);
    }

    /** True when the text reading matches the text specification (score >= 0.75). */
    public static boolean textMatches(String specification, String reading) {
        String expected = normalized(specification);
        String actual = normalized(reading);
        Set<String> exp = new HashSet<>();
        for (String t : expected.split(" ")) if (!t.isEmpty()) exp.add(t);
        Set<String> act = new HashSet<>();
        for (String t : actual.split(" ")) if (!t.isEmpty()) act.add(t);
        double seq = !expected.isEmpty() && !actual.isEmpty() ? ratio(expected, actual) : 0.0;
        int common = 0;
        for (String t : exp) if (act.contains(t)) common++;
        double tok = exp.isEmpty() ? 0.0 : common / (double) exp.size();
        return Math.max(seq, tok) >= 0.75;
    }

    /**
     * InspectionService.evaluate_characteristic: characteristicType NUMBER/VARIABLE (numeric) or TEXT/ATTRIBUTE,
     * readings = observations of the samples.
     */
    public static String evaluate(String characteristicType, String specification, Double lower, Double upper, List<String> readings, boolean notApplicable) {
        if (notApplicable) return NOT_APPLICABLE;
        List<String> values = new ArrayList<>();
        for (String r : readings) if (!text(r).isEmpty()) values.add(text(r));
        if (values.isEmpty()) return NOT_EVALUATED;
        String type = text(characteristicType).isEmpty() ? "NUMBER" : text(characteristicType).toUpperCase(Locale.ROOT);
        if (type.equals("TEXT") || type.equals("ATTRIBUTE")) {
            String spec = text(specification);
            if (spec.isEmpty() && type.equals("ATTRIBUTE")) {
                for (String v : values) if (!attributePass(v)) return FAIL;
                return PASS;
            }
            if (spec.isEmpty()) return FAIL;
            for (String v : values) if (!textMatches(spec, v)) return FAIL;
            return PASS;
        }
        for (String v : values) {
            Double n = number(v);
            if (n == null) return FAIL;
            if (lower != null && n < lower) return FAIL;
            if (upper != null && n > upper) return FAIL;
        }
        return PASS;
    }

    /** Characteristic row (inspection_plan_characteristics or a saved result row) + readings. */
    public static String evaluate(JSONObject characteristic, List<String> readings, boolean notApplicable) {
        return evaluate(text(characteristic.opt("characteristic_type")), text(characteristic.opt("specification")),
            number(characteristic.opt("lower_spec")), number(characteristic.opt("upper_spec")), readings, notApplicable);
    }

    /** core/calculations.band_status. */
    public static String band(Object value, Object minimum, Object maximum, boolean applicable) {
        if (!applicable) return NOT_APPLICABLE;
        Double n = number(value);
        if (n == null) return NOT_EVALUATED;
        Double lo = number(minimum), hi = number(maximum);
        if (lo != null && n < lo) return FAIL;
        if (hi != null && n > hi) return FAIL;
        return PASS;
    }

    /**
     * rmtc_pages._requirement_result: two numbers in the requirement = range, one number (no colon) =
     * exact value, otherwise text match.
     */
    public static String requirement(String requirement, String actual) {
        String req = text(requirement), act = text(actual);
        if (act.isEmpty()) return NOT_EVALUATED;
        Matcher m = Pattern.compile("-?\\d+(?:\\.\\d+)?").matcher(req);
        List<Double> nums = new ArrayList<>();
        while (m.find()) nums.add(Double.parseDouble(m.group()));
        Double value = null;
        Matcher am = Pattern.compile("-?\\d+(?:\\.\\d+)?").matcher(act);
        if (am.find()) value = Double.parseDouble(am.group());
        if (nums.size() >= 2 && value != null) {
            double lo = Math.min(nums.get(0), nums.get(1)), hi = Math.max(nums.get(0), nums.get(1));
            return value >= lo && value <= hi ? PASS : FAIL;
        }
        if (nums.size() == 1 && !req.contains(":") && value != null) return Math.abs(value - nums.get(0)) < 1e-9 ? PASS : FAIL;
        return textMatches(req, act) ? PASS : FAIL;
    }

    /** Tone for a result word. */
    public static String tone(String result) {
        if (PASS.equals(result)) return "green";
        if (FAIL.equals(result)) return "red";
        if (NOT_APPLICABLE.equals(result)) return "grey";
        return "amber";
    }

    /** OK / NG / NA / — label used on reading grids. */
    public static String shortLabel(String result) {
        if (PASS.equals(result)) return "OK";
        if (FAIL.equals(result)) return "NG";
        if (NOT_APPLICABLE.equals(result)) return "NA";
        return "—";
    }
}
