package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * R33 · One controlled QCMS report in the website's print layout (core/reporting.py, Design B):
 * a list of blocks (section bars, label/value grids, result tables, conclusion, photographs, charts).
 * The same document is drawn as the PDF (RptPdf) and shown on the record screen (RptView), so the
 * phone shows every entry of a MetLAB / Bend Test / Dimensional / RMTC / Inward report exactly as printed.
 */
final class RptDoc {
    // ------------------------------------------------------------------ blocks
    interface Block { }

    static final class Bar implements Block {
        final String text; final boolean light; boolean keepCase; boolean fixedFill;
        Bar(String t, boolean l) { text = t; light = l; }
    }

    /** Label / value grid (_rmtc_labeled_grid): label columns bold grey, values coloured by their label. */
    static final class Labeled implements Block {
        final String[][] rows; final float[] w; final Set<Integer> labelCols; final boolean center; final float size;
        boolean ruled;              // 1.0 ink line above and below (bend test conclusion row)
        int valueColor = 0;         // fixed value colour (0 = by label)
        boolean valueBold;
        float labelSize = 0;
        Labeled(String[][] rows, float[] w, int[] labelCols, boolean center, float size) {
            this.rows = rows; this.w = w; this.labelCols = set(labelCols); this.center = center; this.size = size;
        }
    }

    /** Result table (_rmtc_grid): header lines, rules, status / remark / conclusion colours, word-based alignment. */
    static final class Grid implements Block {
        final String[][] rows; final float[] w; final Set<Integer> statusCols; final int headerRows; final float headSize, cellSize;
        boolean noAlign;        // bend-test tables keep plain left alignment
        boolean allCenter;      // every data cell centred (bend test tables)
        boolean firstColBold;   // first column printed as a bold label
        boolean noTopLine;      // no 1.0 line above the header
        boolean plainHeader;    // header in the cell font (not bold)
        Grid(String[][] rows, float[] w, int[] statusCols, int headerRows, float headSize, float cellSize) {
            this.rows = rows; this.w = w; this.statusCols = set(statusCols); this.headerRows = headerRows; this.headSize = headSize; this.cellSize = cellSize;
        }
    }

    static final class Conclusion implements Block {
        final String conclusion, remark, decision, reason;
        Conclusion(String c, String r, String d, String why) { conclusion = c; remark = r; decision = d; reason = why; }
    }

    static final class Photo {
        final String caption; final byte[] bytes;
        Photo(String caption, byte[] bytes) { this.caption = caption == null ? "" : caption; this.bytes = bytes; }
        boolean has() { return bytes != null && bytes.length > 0; }
    }

    static final class Photos implements Block {
        final List<Photo> items; final int cols; final float maxHmm; final boolean slots;
        Photos(List<Photo> items, int cols, float maxHmm, boolean slots) { this.items = items; this.cols = cols; this.maxHmm = maxHmm; this.slots = slots; }
    }

    /** Case depth traverse: Distance (mm) vs Hardness (HV), one line per location. */
    static final class Chart implements Block {
        final List<String> names = new ArrayList<>();
        final List<List<double[]>> series = new ArrayList<>();
    }

    static final int NORMAL = 0, SMALL = 1, CENTER = 2, BIG = 3, REMARK = 4, HEADING = 5, CONCL = 6, SUBTITLE = 7;

    static final class Text implements Block { final String text; final int style; Text(String t, int s) { text = t; style = s; } }

    static final class Space implements Block { final float mm; Space(float mm) { this.mm = mm; } }

    static final class Keep implements Block { final float mm; Keep(float mm) { this.mm = mm; } }

    /** Bend test photograph panel: Load vs CHT graph left, bend angle + part photos + surface remark right. */
    static final class BendPanel implements Block {
        final Photo left, r1, r2, r3; final String angle, surface;
        BendPanel(Photo left, String angle, Photo r1, Photo r2, Photo r3, String surface) {
            this.left = left; this.angle = angle; this.r1 = r1; this.r2 = r2; this.r3 = r3; this.surface = surface;
        }
    }

    /** Two columns of plain values over bold labels (bend test signatures). */
    static final class Signatures implements Block {
        final String[] values, labels; final float[] w;
        Signatures(String[] values, String[] labels, float[] w) { this.values = values; this.labels = labels; this.w = w; }
    }

    // ------------------------------------------------------------------ document
    final String title;
    String heatNumber = "", recordNumber = "", reportLabel = "", subtitle = "";
    String fileBase;
    String layoutDoc = "QUALITY_RECORD";
    boolean landscape = false;
    float edgeMm = 8f, topMm = 30f, bottomMm = 12f;
    final List<Block> blocks = new ArrayList<>();

    // Design B theme (overridden by the saved Print Layout Designer layout).
    int accent = 0xFF0B6E70, rule = 0xFF9AA5A5, conclusionColor = 0xFF166534, remarkColor = 0xFF9A3412;
    float bodyPt = 8.6f, headingPt = 10.5f;
    String company = "FOUR STAR INDUSTRIES", footer = "", barStyle = "fill";
    String plantCode = "D9";
    JSONObject labels = new JSONObject();

    RptDoc(String title) { this.title = title == null ? "" : title; this.fileBase = "QCMS_" + this.title; }

    RptDoc file(String base) { fileBase = base; return this; }

    float contentMm() { return (landscape ? 297f : 210f) - 2 * edgeMm; }

    /** applied_print_layout: theme of the saved layout (accent, rule, colours, type sizes, company, footer, labels). */
    void applyLayout(JSONObject l) {
        if (l == null) return;
        accent = color(l.optString("accent"), accent);
        rule = color(l.optString("rule"), rule);
        conclusionColor = color(l.optString("conclusion"), conclusionColor);
        remarkColor = color(l.optString("remark"), remarkColor);
        double b = l.optDouble("body_pt", Double.NaN), h = l.optDouble("heading_pt", Double.NaN);
        if (!Double.isNaN(b) && b > 0) bodyPt = (float) b;
        if (!Double.isNaN(h) && h > 0) headingPt = (float) h;
        String c = l.optString("company_name", "").trim();
        if (!c.isEmpty()) company = c;
        footer = l.optString("footer_text", "").trim();
        String bar = l.optString("bar", "fill");
        if (!bar.isEmpty()) barStyle = bar;
        JSONObject lab = l.optJSONObject("labels");
        if (lab != null) labels = lab;
    }

    /** core/print_designer.relabel (exact name, then prefix match). */
    String relabel(String t) {
        if (t == null) return "";
        if (labels.has(t)) return labels.optString(t, t);
        for (Iterator<String> it = labels.keys(); it.hasNext(); ) {
            String k = it.next();
            if (!k.isEmpty() && t.startsWith(k)) return labels.optString(k) + t.substring(k.length());
        }
        return t;
    }

    static int color(String hex, int def) {
        try { return hex != null && hex.matches("#[0-9A-Fa-f]{6}") ? (int) (0xFF000000L | Long.parseLong(hex.substring(1), 16)) : def; }
        catch (Exception e) { return def; }
    }

    // ------------------------------------------------------------------ builder helpers
    RptDoc bar(String t) { blocks.add(new Bar(t, false)); return this; }
    RptDoc sub(String t) { blocks.add(new Bar(t, true)); return this; }
    /** Bend test bar_row: always a filled teal band, text as written. */
    RptDoc band(String t) { Bar b = new Bar(t, false); b.keepCase = true; b.fixedFill = true; blocks.add(b); return this; }
    RptDoc space(float mm) { blocks.add(new Space(mm)); return this; }
    RptDoc keep(float mm) { blocks.add(new Keep(mm)); return this; }
    RptDoc text(String t, int style) { blocks.add(new Text(t, style)); return this; }

    RptDoc labeled(String[][] rows, float[] w, int... labelCols) { blocks.add(new Labeled(rows, w, labelCols, false, bodyPt)); return this; }
    RptDoc labeledCenter(String[][] rows, float[] w, int... labelCols) { blocks.add(new Labeled(rows, w, labelCols, true, bodyPt)); return this; }
    Grid grid(String[][] rows, float[] w, int... statusCols) { Grid g = new Grid(rows, w, statusCols, 1, 8.2f, 8.2f); blocks.add(g); return g; }
    RptDoc conclusion(String c, String r, String d, String why) { blocks.add(new Conclusion(c, r, d, why)); return this; }
    RptDoc photos(List<Photo> items, int cols, float maxHmm) { blocks.add(new Photos(items, cols, maxHmm, false)); return this; }

    boolean isEmpty() { return blocks.isEmpty(); }

    // ------------------------------------------------------------------ value formatting (reporting.py)
    private static final Set<String> STATUS_WORDS = new HashSet<>(Arrays.asList(
        "DRAFT", "APPROVAL_PENDING", "APPROVED", "PARTIALLY_APPROVED", "REJECTED", "PENDING", "ON_HOLD", "ACCEPTED",
        "ACCEPTED_UNDER_RESERVE", "PASS", "FAIL", "NOT_EVALUATED", "NOT_APPLICABLE"));

    /** _display_value: dates dd-mm-yyyy, floats with thousands separators, workflow words in title case. */
    static String v(Object value) {
        if (value == null || value == JSONObject.NULL) return "";
        if (value instanceof Double || value instanceof Float) {
            String s = String.format(Locale.ENGLISH, "%,.3f", ((Number) value).doubleValue());
            if (s.contains(".")) { s = s.replaceAll("0+$", ""); if (s.endsWith(".")) s = s.substring(0, s.length() - 1); }
            return s;
        }
        if (value instanceof JSONArray) return joinList((JSONArray) value);
        if (value instanceof JSONObject) return joinMap((JSONObject) value);
        String text = String.valueOf(value).trim();
        if (text.isEmpty()) return "";
        if (text.contains("T") && text.length() >= 16 && text.charAt(4) == '-' && text.charAt(7) == '-' && text.charAt(10) == 'T') {
            try {
                java.util.Date d = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm", Locale.ENGLISH).parse(text.substring(0, 16));
                return new SimpleDateFormat("dd-MM-yyyy HH:mm", Locale.ENGLISH).format(d);
            } catch (Exception ignored) { }
        }
        if (text.length() >= 10 && text.charAt(4) == '-' && text.charAt(7) == '-') {
            try {
                java.util.Date d = new SimpleDateFormat("yyyy-MM-dd", Locale.ENGLISH).parse(text.substring(0, 10));
                if (text.length() == 10) return new SimpleDateFormat("dd-MM-yyyy", Locale.ENGLISH).format(d);
            } catch (Exception ignored) { }
        }
        if (STATUS_WORDS.contains(text.toUpperCase(Locale.ROOT))) return title(text.replace("_", " "));
        return text;
    }

    /** str(value) as the website's tables print it (no date / status reformatting). */
    static String raw(Object value) {
        if (value == null || value == JSONObject.NULL) return "";
        if (value instanceof Boolean) return ((Boolean) value) ? "True" : "False";
        if (value instanceof Double) {
            double d = (Double) value;
            if (d == Math.rint(d) && Math.abs(d) < 1e15) return String.valueOf((long) d) + ".0";
            String s = String.valueOf(d);
            return s.contains("E") ? new java.math.BigDecimal(d).stripTrailingZeros().toPlainString() : s;
        }
        if (value instanceof JSONArray) return joinList((JSONArray) value);
        if (value instanceof JSONObject) return joinMap((JSONObject) value);
        return String.valueOf(value);
    }

    static String joinList(JSONArray a) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < a.length(); i++) {
            Object o = a.opt(i);
            if (o == null || o == JSONObject.NULL || String.valueOf(o).isEmpty()) continue;
            if (b.length() > 0) b.append(", ");
            b.append(raw(o));
        }
        return b.toString();
    }

    static String joinMap(JSONObject o) {
        StringBuilder b = new StringBuilder();
        for (Iterator<String> it = o.keys(); it.hasNext(); ) {
            String k = it.next();
            if (b.length() > 0) b.append("; ");
            b.append(k).append(": ").append(raw(o.opt(k)));
        }
        return b.toString();
    }

    static String title(String s) {
        StringBuilder b = new StringBuilder();
        boolean up = true;
        for (char ch : s.toLowerCase(Locale.ROOT).toCharArray()) {
            b.append(up ? Character.toUpperCase(ch) : ch);
            up = !Character.isLetterOrDigit(ch);
        }
        return b.toString();
    }

    static Set<Integer> set(int[] a) {
        Set<Integer> s = new HashSet<>();
        if (a != null) for (int i : a) s.add(i);
        return s;
    }

    // ------------------------------------------------------------------ colours (reporting.py _status_text_color)
    static final int INK = 0xFF111111;

    static int statusColor(String value) {
        String k = value == null ? "" : value.trim().toUpperCase(Locale.ROOT).replace(" ", "_");
        switch (k) {
            case "PASS": case "APPROVED": case "ACCEPTED": case "RELEASED": case "COMPLETED": case "OK": case "PASSED": return 0xFF166534;
            case "FAIL": case "REJECTED": case "LOCKED": case "FAILED": case "NOT_OK": return 0xFFB91C1C;
            case "ON_HOLD": case "HOLD": case "APPROVAL_PENDING": case "ACCEPTED_UNDER_RESERVE": case "PARTIALLY_APPROVED": return 0xFFB45309;
            case "PENDING": case "DRAFT": case "NOT_EVALUATED": return 0xFF1D4ED8;
            case "NOT_APPLICABLE": case "INACTIVE": return 0xFF555555;
            default: return INK;
        }
    }

    static boolean isRemark(String t) { return t != null && t.toUpperCase(Locale.ROOT).contains("REMARK"); }

    static boolean isConclusion(String t) {
        String u = t == null ? "" : t.toUpperCase(Locale.ROOT);
        return u.contains("CONCLUSION") && !u.contains("REMARK");
    }

    static final int LEFT = 0, CENTER_A = 1, RIGHT = 2;
    private static final String[] RIGHT_WORDS = {"KG", "QTY", "QUANTITY", "WEIGHT", "AMOUNT", "VALUE", "RATE", "PRICE", "BALANCE", "PCS", "TOTAL"};
    private static final String[] CENTER_WORDS = {"SR", "NO.", "SR.", "UNIT", "MIN", "MAX", "RESULT", "STATUS", "DECISION", "DATE", "SPEC", "ACTUAL", "OBSERV",
        "READING", "HARDNESS", "HRC", "HV", "DEPTH", "DISTANCE", "GRADE", "HEAT", "%", "SAMPLE", "TOLERANCE", "LOCATION", "J", "DISPOSITION", "VALIDATION", "WORKSHEET"};
    private static final String[] LEFT_WORDS = {"PARAMETER", "CHARACTERISTIC", "DESCRIPTION", "REMARK", "NAME", "SUPPLIER", "METHOD", "AID", "PROPERTY", "SOURCE",
        "DOCUMENT", "TEST", "ELEMENT", "PART", "REQUIREMENT", "PROCESS"};

    /** _column_alignment: text columns left, measured / status columns centred, quantities right. */
    static int alignment(String header) {
        String t = header == null ? "" : header.replaceAll("<[^>]+>", "").toUpperCase(Locale.ROOT).trim();
        if (t.isEmpty()) return CENTER_A;
        if (any(t, LEFT_WORDS) && !any(t, new String[]{"RESULT", "STATUS", "DATE", "QTY", "KG"})) return LEFT;
        if (any(t, RIGHT_WORDS)) return RIGHT;
        Set<String> tokens = new HashSet<>(Arrays.asList(t.split("[^A-Z0-9%.]+")));
        for (String k : new String[]{"SR", "SR.", "NO", "NO.", "#", "S.NO"}) if (tokens.contains(k)) return CENTER_A;
        if (any(t, CENTER_WORDS)) return CENTER_A;
        return LEFT;
    }

    private static boolean any(String t, String[] words) { for (String w : words) if (t.contains(w)) return true; return false; }

    static boolean plainNumber(String v) { return v != null && v.trim().matches("[-+]?\\d+(?:[.,]\\d+)?(?:\\s*%)?"); }
}
