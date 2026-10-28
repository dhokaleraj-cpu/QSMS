package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * R38 · Horizontal chemistry / Jominy grids for record views and prints (website core/chem_grid.py).
 * Elements and Jominy distances are COLUMNS; Jominy shows the inch label (J5/16") and a Distance (mm) row
 * (n / 16 x 25.4 mm, two decimals half-up: J5/16" = 7.94 mm). Stored rows are never changed.
 */
final class ChemGrid {
    private ChemGrid() { }

    static final int PDF_BAND_COLUMNS = 14;
    private static final Pattern MM_LABEL = Pattern.compile("^\\s*J?\\s*(\\d+(?:\\.\\d+)?)\\s*mm\\s*$", Pattern.CASE_INSENSITIVE);
    private static final Pattern FRACTION = Pattern.compile("(\\d+(?:\\.\\d+)?)\\s*/\\s*16");
    private static final Pattern J_NUMBER = Pattern.compile("^\\s*J\\s*(\\d+(?:\\.\\d+)?)\\s*(?:\"|in|inch)?\\s*$", Pattern.CASE_INSENSITIVE);
    private static final Pattern PLAIN = Pattern.compile("^\\s*(\\d+(?:\\.\\d+)?)\\s*$");

    /** Sixteenths of an inch from J-notation: J5/16", 5/16", J 5, J3, 5 -> n; blank / mm label -> 0. */
    static double sixteenths(Object v) {
        if (v == null || v == JSONObject.NULL || v instanceof Boolean) return 0;
        if (v instanceof Number) { double d = ((Number) v).doubleValue(); return d > 0 ? d : 0; }
        String t = String.valueOf(v).trim().replace("″", "\"");
        if (t.isEmpty() || MM_LABEL.matcher(t).matches()) return 0;
        Matcher m = FRACTION.matcher(t);
        if (m.find()) return Double.parseDouble(m.group(1));
        m = J_NUMBER.matcher(t);
        if (m.matches()) return Double.parseDouble(m.group(1));
        m = PLAIN.matcher(t);
        if (m.matches()) return Double.parseDouble(m.group(1));
        return 0;
    }

    /** J-notation -> millimetres text with two decimals ("7.94"), "" when unknown. */
    static String inchToMm(Object v) {
        double s = sixteenths(v);
        if (s <= 0) return "";
        return new BigDecimal(String.valueOf(s)).multiply(new BigDecimal("1.5875")).setScale(2, RoundingMode.HALF_UP).toPlainString();
    }

    /** Millimetres -> decimal inches text (7.9375 -> "0.3125"). */
    static String mmToInch(double mm) {
        if (mm <= 0) return "";
        return new BigDecimal(String.valueOf(mm)).divide(new BigDecimal("25.4"), 4, RoundingMode.HALF_UP).stripTrailingZeros().toPlainString();
    }

    /** Sixteenths of a stored Jominy row: distance_16th, then the label, then distance_mm. */
    static int sixteenthOf(JSONObject r) {
        double s = sixteenths(r.opt("distance_16th"));
        if (s <= 0) s = sixteenths(r.opt("distance_label"));
        if (s <= 0) {
            double mm = r.optDouble("distance_mm", 0);
            if (mm > 0) s = mm / 1.5875;
        }
        return (int) Math.round(s);
    }

    static boolean handles(String table) {
        return "material_grade_elements".equals(table) || "part_jominy_requirements".equals(table)
            || "rmtc_chemistry_results".equals(table) || "rmtc_jominy_results".equals(table);
    }

    /** One horizontal table per part ("" key when the child has no part split). partLabels may be null. */
    static LinkedHashMap<String, List<String[]>> horizontal(String table, JSONArray rows, Map<String, String> partLabels) {
        LinkedHashMap<String, List<JSONObject>> groups = new LinkedHashMap<>();
        boolean byPart = "rmtc_chemistry_results".equals(table) || "rmtc_jominy_results".equals(table);
        for (int i = 0; rows != null && i < rows.length(); i++) {
            JSONObject r = rows.optJSONObject(i);
            if (r == null) continue;
            String status = RptReports.str(r.opt("status"));
            if ("part_jominy_requirements".equals(table) && !status.isEmpty() && !"ACTIVE".equals(status)) continue;
            String key = byPart ? RptReports.str(r.opt("part_id")) : "";
            if (!groups.containsKey(key)) groups.put(key, new ArrayList<>());
            groups.get(key).add(r);
        }
        LinkedHashMap<String, List<String[]>> out = new LinkedHashMap<>();
        for (Map.Entry<String, List<JSONObject>> e : groups.entrySet()) {
            String label = e.getKey();
            if (partLabels != null && partLabels.containsKey(label)) label = partLabels.get(label);
            if (groups.size() == 1) label = "";
            out.put(label, table(table, e.getValue()));
        }
        return out;
    }

    static List<String[]> table(String table, List<JSONObject> rows) {
        switch (table) {
            case "material_grade_elements":
                return RptReports.chemHorizontal(rows, new String[][]{{"Minimum", "minimum"}, {"Maximum", "maximum"}, {"Unit", "unit"}, {"Test Method", "test_method"}});
            case "rmtc_chemistry_results":
                return RptReports.chemHorizontal(rows, new String[][]{{"Minimum", "minimum_value"}, {"Maximum", "maximum_value"}, {"Actual", "actual_value"}, {"Status", "result"}});
            case "part_jominy_requirements":
                return RptReports.jominyHorizontal(rows, new String[][]{{"Min HRC", "minimum_hrc"}, {"Max HRC", "maximum_hrc"}});
            default:
                return RptReports.jominyHorizontal(rows, new String[][]{{"Actual HRC", "actual_hrc"}, {"Actual Status", "result"},
                    {"Calculated HRC", "calculated_hrc"}, {"Calc. Status", "calculated_result"}, {"Applicable", "__na"}});
        }
    }

    /** Wide grids are cut into bands of PDF_BAND_COLUMNS value columns (row titles repeated) to fit A4. */
    static List<List<String[]>> bands(List<String[]> t, int per) {
        List<List<String[]>> out = new ArrayList<>();
        if (t == null || t.isEmpty()) return out;
        int values = 0;
        for (String[] r : t) values = Math.max(values, r.length - 1);
        if (values <= per) { out.add(t); return out; }
        for (int start = 1; start <= values; start += per) {
            List<String[]> band = new ArrayList<>();
            for (String[] r : t) {
                int end = Math.min(r.length, start + per);
                String[] line = new String[Math.max(1, end - start + 1)];
                line[0] = r.length > 0 ? r[0] : "";
                for (int i = start; i < end; i++) line[i - start + 1] = r[i];
                for (int i = 1; i < line.length; i++) if (line[i] == null) line[i] = "";
                band.add(line);
            }
            out.add(band);
        }
        return out;
    }

    /** Header + data lists for DataGrid / RptReports.Table. */
    static List<String> headers(List<String[]> t) {
        List<String> h = new ArrayList<>();
        if (t.isEmpty()) return h;
        for (String s : t.get(0)) h.add(s == null || s.isEmpty() ? " " : s);
        return h;
    }

    static List<List<String>> data(List<String[]> t) {
        List<List<String>> d = new ArrayList<>();
        int width = t.isEmpty() ? 0 : t.get(0).length;
        for (int r = 1; r < t.size(); r++) {
            List<String> line = new ArrayList<>();
            for (int i = 0; i < width; i++) line.add(i < t.get(r).length && t.get(r)[i] != null ? t.get(r)[i] : "");
            d.add(line);
        }
        return d;
    }
}
