package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Shared helpers of the General area (Global Search, KPI dashboards, Report Builder,
 * Master Lists, Traceability, My Account): Python-like value semantics, the website's
 * module View-permission engine (core/access.py), CSV export and simple pickers.
 */
final class GenUtil {
    private GenUtil() { }

    // ------------------------------------------------------------------ Python-like values
    /** Python truthiness of a JSON value (None, "", 0, False, empty list/dict are falsy). */
    static boolean truthy(Object v) {
        if (v == null || v == JSONObject.NULL) return false;
        if (v instanceof Boolean) return (Boolean) v;
        if (v instanceof Number) { double d = ((Number) v).doubleValue(); return d != 0 && !Double.isNaN(d); }
        if (v instanceof String) return !((String) v).isEmpty();
        if (v instanceof JSONArray) return ((JSONArray) v).length() > 0;
        if (v instanceof JSONObject) return ((JSONObject) v).length() > 0;
        return true;
    }

    /** {@code row.get(k1) or row.get(k2) or ...} - first truthy value, else the last one. */
    static Object or(JSONObject r, String... keys) {
        Object last = null;
        for (String k : keys) {
            Object v = r == null ? null : r.opt(k);
            if (v == JSONObject.NULL) v = null;
            if (truthy(v)) return v;
            last = v;
        }
        return last;
    }

    /** str(value or "") */
    static String str(Object v) {
        if (!truthy(v)) return "";
        if (v instanceof Double) {
            double d = (Double) v;
            if (d == Math.rint(d) && Math.abs(d) < 1e15) return String.valueOf((long) d) + ".0";
        }
        return String.valueOf(v);
    }

    /** str(value or "").strip().upper() (kpi_service._s). */
    static String up(Object v) { return str(v).trim().toUpperCase(Locale.ROOT); }

    static String j(JSONObject r, String k) { return r == null ? "" : Lookups.j(r, k); }

    /** float(value) with 0 for anything not numeric (kpi_service._n). */
    static double n(Object v) {
        if (v == null || v == JSONObject.NULL) return 0;
        if (v instanceof Boolean) return ((Boolean) v) ? 1 : 0;
        if (v instanceof Number) { double d = ((Number) v).doubleValue(); return Double.isNaN(d) ? 0 : d; }
        try { double d = Double.parseDouble(String.valueOf(v).trim()); return Double.isNaN(d) || Double.isInfinite(d) ? 0 : d; } catch (Exception e) { return 0; }
    }

    static double n(JSONObject r, String k) { return r == null ? 0 : n(r.opt(k)); }

    /** pandas to_datetime(..., utc=True).date() for ISO dates / timestamps; null when empty or invalid. */
    static LocalDate d(Object value) {
        if (value == null || value == JSONObject.NULL) return null;
        String s = String.valueOf(value).trim();
        if (s.isEmpty() || "null".equals(s)) return null;
        try {
            if (s.length() > 10) {
                String t = s.replace(' ', 'T');
                try { return OffsetDateTime.parse(t).withOffsetSameInstant(ZoneOffset.UTC).toLocalDate(); } catch (Exception ignored) { }
                try { return OffsetDateTime.parse(t.replaceAll("([+-]\\d\\d)$", "$1:00")).withOffsetSameInstant(ZoneOffset.UTC).toLocalDate(); } catch (Exception ignored) { }
                try { return LocalDateTime.parse(t).toLocalDate(); } catch (Exception ignored) { }
            }
            return LocalDate.parse(s.length() >= 10 ? s.substring(0, 10) : s);
        } catch (Exception e) {
            return null;
        }
    }

    /** Python str.title(): capital after every non-letter. */
    static String title(String s) {
        if (s == null) return "";
        StringBuilder b = new StringBuilder();
        boolean prevLetter = false;
        for (char ch : s.toCharArray()) {
            boolean letter = Character.isLetter(ch);
            b.append(letter ? (prevLetter ? Character.toLowerCase(ch) : Character.toUpperCase(ch)) : ch);
            prevLetter = letter;
        }
        return b.toString();
    }

    /** f"{v:,.Nf}" - Python rounds the exact binary value half-to-even (52618.5 -> 52,618). */
    static String fmt(double v, int decimals) {
        if (Double.isNaN(v) || Double.isInfinite(v)) return String.valueOf(v);
        java.math.BigDecimal b = new java.math.BigDecimal(v).setScale(decimals, java.math.RoundingMode.HALF_EVEN);
        return String.format(Locale.US, "%,." + decimals + "f", b);
    }

    /** f"{v:.Nf}" (no thousands separator), Python rounding. */
    static String fixed(double v, int decimals) {
        if (Double.isNaN(v) || Double.isInfinite(v)) return String.valueOf(v);
        return new java.math.BigDecimal(v).setScale(decimals, java.math.RoundingMode.HALF_EVEN).toPlainString();
    }

    /** Python round(v, n) (half-even on the decimal text like the website's numbers). */
    static double round(double v, int n) {
        if (Double.isNaN(v) || Double.isInfinite(v)) return v;
        return new java.math.BigDecimal(v).setScale(n, java.math.RoundingMode.HALF_EVEN).doubleValue();   // exact binary value, like Python round()
    }

    /** Number shown in a grid cell: integers without decimals, else up to 4 decimals. */
    static String cell(double v) {
        if (Double.isNaN(v)) return "";
        if (v == Math.rint(v) && Math.abs(v) < 1e15) return String.valueOf((long) v);
        String s = String.format(Locale.US, "%.4f", v);
        while (s.contains(".") && (s.endsWith("0") || s.endsWith("."))) s = s.substring(0, s.length() - 1);
        return s;
    }

    /** Python str(value) of a JSON scalar (None, True/False, 5, 5.0). */
    static String py(Object v) {
        if (v == null || v == JSONObject.NULL) return "None";
        if (v instanceof Boolean) return ((Boolean) v) ? "True" : "False";
        if (v instanceof Double || v instanceof Float) {
            double d = ((Number) v).doubleValue();
            if (Double.isNaN(d)) return "nan";
            if (d == Math.rint(d) && Math.abs(d) < 1e16) return String.valueOf((long) d) + ".0";
            return String.valueOf(d);
        }
        return String.valueOf(v);
    }

    /** Large live read (not kept in the offline cache - KPI / report tables can be several MB). Background thread. */
    static List<JSONObject> big(Api api, String path) throws Exception {
        return list(new JSONArray(api.get(path, false).body));
    }

    static List<JSONObject> list(JSONArray a) {
        List<JSONObject> out = new ArrayList<>();
        if (a == null) return out;
        for (int i = 0; i < a.length(); i++) { JSONObject o = a.optJSONObject(i); if (o != null) out.add(o); }
        return out;
    }

    static List<String> keys(JSONObject o) {
        List<String> out = new ArrayList<>();
        if (o == null) return out;
        Iterator<String> it = o.keys();
        while (it.hasNext()) out.add(it.next());
        return out;
    }

    /** Text of any JSON value for searching (global_search._text). */
    static String text(Object v) {
        if (v == null || v == JSONObject.NULL) return "";
        if (v instanceof JSONObject) {
            StringBuilder b = new StringBuilder();
            JSONObject o = (JSONObject) v;
            for (String k : keys(o)) { if (b.length() > 0) b.append(' '); b.append(k).append(' ').append(text(o.opt(k))); }
            return b.toString();
        }
        if (v instanceof JSONArray) {
            StringBuilder b = new StringBuilder();
            JSONArray a = (JSONArray) v;
            for (int i = 0; i < a.length(); i++) { if (b.length() > 0) b.append(' '); b.append(text(a.opt(i))); }
            return b.toString();
        }
        return str(v);
    }

    // ------------------------------------------------------------------ module permissions (core/access.py)
    static final String[] PERMISSION_KEYS = {"can_view", "can_create", "can_edit", "can_archive", "can_validate", "can_approve"};
    private static final Map<String, Boolean> VIEW_CACHE = new HashMap<>();
    private static String cacheUser = "";
    private static long cacheAt = 0;

    /** Effective "can_view" of a module like core.access.module_permissions (call on a background thread). */
    static synchronized boolean canView(Api api, String moduleKey) {
        if (api.isAdmin()) return true;
        String key = moduleKey == null ? "" : moduleKey.toUpperCase(Locale.ROOT);
        if (!api.userId.equals(cacheUser) || System.currentTimeMillis() - cacheAt > 300_000L) {
            VIEW_CACHE.clear(); cacheUser = api.userId; cacheAt = System.currentTimeMillis();
        }
        Boolean hit = VIEW_CACHE.get(key);
        if (hit != null) return hit;
        boolean v = permissions(api, key).optBoolean("can_view", false);
        VIEW_CACHE.put(key, v);
        return v;
    }

    /** ADMIN -> explicit user override -> role defaults -> department defaults -> legacy role fallback. */
    static JSONObject permissions(Api api, String moduleKey) {
        JSONObject out = new JSONObject();
        try {
            if (api.isAdmin()) { for (String k : PERMISSION_KEYS) out.put(k, true); return out; }
            String pid = api.userId;
            try {
                JSONArray rows = api.rows("user_module_permissions?select=*&profile_id=eq." + Api.enc(pid) + "&module_key=eq." + Api.enc(moduleKey) + "&limit=1");
                if (rows.length() > 0) return permissionRow(rows.getJSONObject(0), false);
            } catch (Exception ignored) { }
            String role = (api.role == null || api.role.isEmpty() ? "VIEWER" : api.role).toUpperCase(Locale.ROOT).replace(' ', '_');
            try {
                JSONArray rows = api.rows("role_module_defaults?select=*&role=eq." + Api.enc(role) + "&module_key=eq." + Api.enc(moduleKey) + "&status=eq.ACTIVE&limit=1");
                if (rows.length() > 0) return permissionRow(rows.getJSONObject(0), false);
            } catch (Exception ignored) { }
            String department = department(api);
            if (!department.isEmpty()) {
                try {
                    JSONArray rows = api.rows("department_module_defaults?select=*&department=eq." + Api.enc(department) + "&module_key=eq." + Api.enc(moduleKey) + "&status=eq.ACTIVE&limit=1");
                    if (rows.length() > 0) return permissionRow(rows.getJSONObject(0), false);
                } catch (Exception ignored) { }
            }
            return legacy(role, moduleKey);
        } catch (Exception e) {
            return out;
        }
    }

    private static String departmentCache;
    private static String departmentUser = "";

    static synchronized String department(Api api) {
        if (departmentCache != null && api.userId.equals(departmentUser)) return departmentCache;
        String dept = "";
        try {
            List<JSONObject> rows = list(api.rows("employees?select=profile_id,email,department&status=eq.ACTIVE&limit=5000"));
            for (JSONObject r : rows) if (!api.userId.isEmpty() && api.userId.equals(j(r, "profile_id"))) { dept = j(r, "department").trim(); break; }
            if (dept.isEmpty()) {
                String mail = api.email == null ? "" : api.email.trim().toLowerCase(Locale.ROOT);
                for (JSONObject r : rows) if (!mail.isEmpty() && mail.equals(j(r, "email").trim().toLowerCase(Locale.ROOT))) { dept = j(r, "department").trim(); break; }
            }
        } catch (Exception ignored) { }
        departmentCache = dept; departmentUser = api.userId;
        return dept;
    }

    private static JSONObject permissionRow(JSONObject r, boolean archiveDefault) throws Exception {
        JSONObject o = new JSONObject();
        for (String k : PERMISSION_KEYS) o.put(k, r.has(k) ? truthy(r.opt(k)) : (k.equals("can_archive") && archiveDefault));
        return o;
    }

    private static JSONObject legacy(String role, String moduleKey) throws Exception {
        if (role.equals("VIEWER") || role.equals("AUDITOR")) {
            JSONObject o = new JSONObject();
            for (String k : PERMISSION_KEYS) o.put(k, k.equals("can_view"));
            return o;
        }
        Set<String> supply = new HashSet<>(Arrays.asList("SUPPLY_CHAIN", "PROCUREMENT", "PRODUCTION", "MANAGEMENT"));
        Set<String> quality = new HashSet<>(Arrays.asList("QUALITY_MANAGER", "QUALITY_ENGINEER", "METLAB_APPROVER", "SQA"));
        boolean write;
        if (moduleKey.equals("SUPPLY_CHAIN")) write = supply.contains(role) || role.equals("QUALITY_MANAGER") || role.equals("MASTER_DATA");
        else if (Arrays.asList("RMTC_ENTRY", "MATERIAL_INWARD", "DIMENSIONAL_REPORT", "METLAB_REPORT", "OSP_TRANSACTIONS").contains(moduleKey)) write = quality.contains(role) || role.equals("PRODUCTION") || role.equals("MANAGEMENT");
        else if (moduleKey.equals("NPD_APQP")) write = quality.contains(role) || Arrays.asList("PRODUCTION", "BUSINESS_DEVELOPMENT", "MANAGEMENT", "MASTER_DATA").contains(role);
        else if (moduleKey.equals("CALIBRATION_VALIDATION")) write = quality.contains(role) || role.equals("MANAGEMENT") || role.equals("MASTER_DATA");
        else write = quality.contains(role) || role.equals("MASTER_DATA") || role.equals("MANAGEMENT");
        boolean validate = Arrays.asList("QUALITY_MANAGER", "QUALITY_ENGINEER", "METLAB_APPROVER", "SQA", "SUPPLY_CHAIN", "PROCUREMENT", "MANAGEMENT").contains(role);
        boolean approve;
        if (moduleKey.equals("DIMENSIONAL_REPORT")) approve = Arrays.asList("QUALITY_MANAGER", "QUALITY_ENGINEER", "SQA", "MANAGEMENT").contains(role);
        else if (moduleKey.equals("METLAB_REPORT")) approve = Arrays.asList("QUALITY_MANAGER", "METLAB_APPROVER", "MANAGEMENT").contains(role);
        else approve = role.equals("MANAGEMENT");
        JSONObject o = new JSONObject();
        o.put("can_view", true); o.put("can_create", write); o.put("can_edit", write); o.put("can_archive", false);
        o.put("can_validate", validate); o.put("can_approve", approve);
        return o;
    }

    // ------------------------------------------------------------------ open a record natively
    /** Catalogue module that shows this table and row (bend tests / party types picked like the website routing). */
    static Module moduleFor(String table, JSONObject row) {
        List<Module> candidates = new ArrayList<>();
        for (Module m : Catalog.all()) if (m.table.equals(table) && !m.idField.isEmpty()) candidates.add(m);
        if (candidates.isEmpty()) return Catalog.adhoc(table);
        if (candidates.size() == 1 || row == null) return candidates.get(0);
        if (table.equals("lab_tests")) {
            JSONObject res = row.optJSONObject("results");
            String method = res == null ? "" : up(res.opt("inspection_method"));
            String fallback = (j(row, "test_type") + " " + j(row, "remarks") + " " + j(row, "layout_name_snapshot")).toUpperCase(Locale.ROOT);
            boolean bend = method.equals("BEND_TEST") || fallback.contains("BEND TEST") || "BEND".equalsIgnoreCase(j(row, "test_type"));
            for (Module m : candidates) {
                boolean isBend = m.key.toLowerCase(Locale.ROOT).contains("bend");
                if (bend == isBend && filterMatches(m, row)) return m;
            }
        }
        for (Module m : candidates) if (!m.filter.isEmpty() && filterMatches(m, row)) return m;
        for (Module m : candidates) if (m.filter.isEmpty()) return m;
        return candidates.get(0);
    }

    /** Best-effort check of simple PostgREST filters (&col=eq.X, &col=cs.{X}, &col=in.(..)) on one row. */
    static boolean filterMatches(Module m, JSONObject row) {
        if (m.filter == null || m.filter.isEmpty()) return true;
        for (String part : m.filter.split("&")) {
            if (part.isEmpty() || !part.contains("=")) continue;
            String col = part.substring(0, part.indexOf('='));
            String rest = part.substring(part.indexOf('=') + 1);
            String value;
            try { value = java.net.URLDecoder.decode(rest, "UTF-8"); } catch (Exception e) { value = rest; }
            if (!row.has(col)) continue;
            Object v = row.opt(col);
            if (value.startsWith("eq.")) { if (!value.substring(3).equalsIgnoreCase(str(v))) return false; }
            else if (value.startsWith("neq.")) { if (value.substring(4).equalsIgnoreCase(str(v))) return false; }
            else if (value.startsWith("cs.{")) {
                String want = value.substring(4).replace("}", "");
                if (!text(v).toUpperCase(Locale.ROOT).contains(want.toUpperCase(Locale.ROOT))) return false;
            } else if (value.startsWith("in.(")) {
                List<String> opts = Arrays.asList(value.substring(4).replace(")", "").toUpperCase(Locale.ROOT).split(","));
                if (!opts.contains(up(v))) return false;
            }
        }
        return true;
    }

    static void openRecord(MainActivity a, String table, JSONObject row) {
        String id = j(row, "id");
        if (id.isEmpty()) { a.toast("This record has no id to open."); return; }
        Module m = moduleFor(table, row);
        a.push(new RecordScreen(a, m, id));
    }

    // ------------------------------------------------------------------ CSV
    static String q(String s) {
        String v = s == null ? "" : s;
        return v.contains(",") || v.contains("\"") || v.contains("\n") || v.contains("\r") ? "\"" + v.replace("\"", "\"\"") + "\"" : v;
    }

    static String csv(List<String> headers, List<String[]> rows) {
        StringBuilder b = new StringBuilder();
        appendCsv(b, headers, rows);
        return b.toString();
    }

    static void appendCsv(StringBuilder b, List<String> headers, List<String[]> rows) {
        for (int c = 0; c < headers.size(); c++) { if (c > 0) b.append(','); b.append(q(headers.get(c))); }
        b.append('\n');
        for (String[] r : rows) {
            for (int c = 0; c < r.length; c++) { if (c > 0) b.append(','); b.append(q(r[c])); }
            b.append('\n');
        }
    }

    static String safeName(String title) {
        StringBuilder b = new StringBuilder();
        for (char ch : (title == null ? "" : title).toCharArray()) b.append(Character.isLetterOrDigit(ch) ? ch : '_');
        String s = b.length() > 60 ? b.substring(0, 60) : b.toString();
        return s.isEmpty() ? "QCMS_Report" : s;
    }

    /**
     * Save the CSV to Downloads (MediaStore, Android 10+) and offer to share it as text/csv.
     * Older Android versions share the CSV text directly.
     */
    static void exportCsv(MainActivity a, String title, String fileName, String csv) {
        String name = fileName.toLowerCase(Locale.ROOT).endsWith(".csv") ? fileName : fileName + ".csv";
        Api.async(() -> saveToDownloads(a, name, csv), (uri, err) -> {
            Intent send = new Intent(Intent.ACTION_SEND);
            send.setType("text/csv");
            send.putExtra(Intent.EXTRA_SUBJECT, "QCMS " + title);
            if (uri != null) {
                send.putExtra(Intent.EXTRA_STREAM, uri);
                send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                a.toast("Saved to Downloads: " + name);
            } else {
                send.putExtra(Intent.EXTRA_TEXT, csv);
            }
            try { a.startActivity(Intent.createChooser(send, "Share " + title)); } catch (Exception e) { a.toast(uri != null ? "Saved to Downloads: " + name : "No app to share with."); }
        });
    }

    /** MediaStore.Downloads insert (API 29+, via reflection so older stubs / devices stay safe). Null when not possible. */
    static Uri saveToDownloads(MainActivity a, String name, String csv) {
        if (Build.VERSION.SDK_INT < 29) return null;
        try {
            Class<?> downloads = Class.forName("android.provider.MediaStore$Downloads");
            Uri collection = (Uri) downloads.getField("EXTERNAL_CONTENT_URI").get(null);
            ContentValues values = new ContentValues();
            values.put("_display_name", name);
            values.put("mime_type", "text/csv");
            values.put("relative_path", "Download/QCMS");
            ContentResolver resolver = a.getContentResolver();
            Uri uri = resolver.insert(collection, values);
            if (uri == null) return null;
            OutputStream out = (OutputStream) ContentResolver.class.getMethod("openOutputStream", Uri.class).invoke(resolver, uri);
            if (out == null) return null;
            try (OutputStream o = out) { o.write(csv.getBytes(StandardCharsets.UTF_8)); }
            return uri;
        } catch (Throwable e) {
            return null;
        }
    }

    // ------------------------------------------------------------------ small UI helpers
    interface Picked { void picked(int index); }
    interface MultiPicked { void picked(boolean[] checked); }

    /** Searchable single choice list (dialog). */
    static void pick(MainActivity a, String title, List<String> names, Picked picked) {
        LinearLayout box = Ui.vbox(a);
        int p = Ui.dp(a, 16);
        box.setPadding(p, Ui.dp(a, 8), p, 0);
        EditText search = Ui.input(a, "Search…", false);
        box.addView(search, Ui.matchWrap(a, 0));
        ScrollView sv = new ScrollView(a);
        LinearLayout listBox = Ui.vbox(a);
        sv.addView(listBox);
        box.addView(sv, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(a, 380)));
        AlertDialog dialog = new AlertDialog.Builder(a).setTitle(title).setView(box).setNegativeButton("Back", null).create();
        Runnable[] fill = new Runnable[1];
        fill[0] = () -> {
            listBox.removeAllViews();
            String qx = search.getText().toString().trim().toLowerCase(Locale.ROOT);
            int shown = 0;
            for (int i = 0; i < names.size(); i++) {
                String n = names.get(i);
                if (!qx.isEmpty() && !n.toLowerCase(Locale.ROOT).contains(qx)) continue;
                if (++shown > 400) break;
                final int index = i;
                TextView t = Ui.text(a, n, 14, Ui.TEXT, false);
                t.setPadding(Ui.dp(a, 6), Ui.dp(a, 12), Ui.dp(a, 6), Ui.dp(a, 12));
                Ui.clickable(t, Color.WHITE, 0, 6);
                t.setOnClickListener(v -> { dialog.dismiss(); picked.picked(index); });
                listBox.addView(t, Ui.matchWrap(a, 0));
                listBox.addView(Ui.divider(a));
            }
            if (shown == 0) listBox.addView(Ui.empty(a, "No match"));
        };
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
            @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
            @Override public void afterTextChanged(Editable e) { fill[0].run(); }
        });
        fill[0].run();
        dialog.show();
    }

    static void pickMany(MainActivity a, String title, List<String> names, boolean[] checked, MultiPicked done) {
        boolean[] state = Arrays.copyOf(checked, checked.length);
        new AlertDialog.Builder(a)
            .setTitle(title)
            .setMultiChoiceItems(names.toArray(new CharSequence[0]), state, (d, which, on) -> state[which] = on)
            .setPositiveButton("OK", (d, w) -> done.picked(state))
            .setNeutralButton("None", (d, w) -> done.picked(new boolean[state.length]))
            .setNegativeButton("Back", null)
            .show();
    }

    /** Tappable "label: value ▾" selector row. */
    static TextView selector(MainActivity a, String text) {
        TextView t = Ui.text(a, text + "  ▾", 14, Ui.TEXT, true);
        t.setPadding(Ui.dp(a, 12), Ui.dp(a, 12), Ui.dp(a, 12), Ui.dp(a, 12));
        Ui.clickable(t, Color.WHITE, Ui.LINE_STRONG, 10);
        return t;
    }

    /** Horizontal row of chips; the chosen one is filled teal. */
    static HorizontalScrollView chips(MainActivity a, List<String> labels, int selected, Picked picked) {
        HorizontalScrollView hs = new HorizontalScrollView(a);
        hs.setHorizontalScrollBarEnabled(false);
        LinearLayout row = Ui.hbox(a);
        for (int i = 0; i < labels.size(); i++) {
            final int index = i;
            boolean on = i == selected;
            TextView chip = Ui.text(a, labels.get(i), 12.5f, on ? Color.WHITE : Ui.TEXT, on);
            chip.setPadding(Ui.dp(a, 12), Ui.dp(a, 8), Ui.dp(a, 12), Ui.dp(a, 8));
            chip.setBackground(on ? Ui.round(Ui.TEAL, 0, 0, 16, a) : Ui.round(Color.WHITE, Ui.LINE_STRONG, 1, 16, a));
            chip.setOnClickListener(v -> picked.picked(index));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            lp.rightMargin = Ui.dp(a, 6);
            row.addView(chip, lp);
        }
        hs.addView(row);
        return hs;
    }

    /** Number-first KPI tile (status colour bar on the left, like the website). */
    static View tile(MainActivity a, String head, String label, String value, String foot, String status) {
        int color = statusColor(status);
        LinearLayout outer = Ui.hbox(a);
        outer.setBackground(Ui.round(Color.WHITE, Ui.LINE, 1, 14, a));
        outer.setGravity(android.view.Gravity.TOP);
        View bar = new View(a);
        bar.setBackground(Ui.round(color, 0, 0, 3, a));
        outer.addView(bar, new LinearLayout.LayoutParams(Ui.dp(a, 5), ViewGroup.LayoutParams.MATCH_PARENT));
        LinearLayout box = Ui.vbox(a);
        box.setPadding(Ui.dp(a, 10), Ui.dp(a, 10), Ui.dp(a, 10), Ui.dp(a, 10));
        if (head != null && !head.isEmpty()) {
            TextView h = Ui.text(a, head, 11, Ui.TEAL_DARK, true);
            h.setSingleLine(true); h.setEllipsize(android.text.TextUtils.TruncateAt.END);
            box.addView(h);
        }
        LinearLayout top = Ui.hbox(a);
        TextView l = Ui.text(a, label.toUpperCase(Locale.ROOT), 10.5f, Ui.MUTED, true);
        l.setSingleLine(true); l.setEllipsize(android.text.TextUtils.TruncateAt.END);
        top.addView(l, Ui.weight(1));
        if (!"neutral".equals(status) && status != null && !status.isEmpty()) {
            View dot = new View(a);
            dot.setBackground(Ui.round(color, 0, 0, 5, a));
            top.addView(dot, new LinearLayout.LayoutParams(Ui.dp(a, 10), Ui.dp(a, 10)));
        }
        box.addView(top);
        TextView v = Ui.text(a, value, 24, Ui.TEXT, true);
        v.setSingleLine(true); v.setEllipsize(android.text.TextUtils.TruncateAt.END);
        box.addView(v);
        if (foot != null && !foot.isEmpty()) {
            TextView f = Ui.text(a, foot, 11, Ui.MUTED, false);
            f.setMaxLines(2); f.setEllipsize(android.text.TextUtils.TruncateAt.END);
            box.addView(f);
        }
        outer.addView(box, Ui.weight(1));
        return outer;
    }

    static int statusColor(String status) {
        switch (status == null ? "" : status) {
            case "good": return Color.parseColor("#0ca30c");
            case "warning": return Color.parseColor("#fab219");
            case "serious": return Color.parseColor("#ec835a");
            case "critical": return Color.parseColor("#d03b3b");
            default: return Color.parseColor("#898781");
        }
    }

    /** Lays views out two per row. */
    static void grid2(MainActivity a, LinearLayout parent, List<View> views, int topDp) {
        for (int i = 0; i < views.size(); i += 2) {
            LinearLayout row = Ui.hbox(a);
            row.setGravity(android.view.Gravity.TOP);
            LinearLayout.LayoutParams l = Ui.weight(1); l.rightMargin = Ui.dp(a, 5);
            row.addView(views.get(i), l);
            LinearLayout.LayoutParams r = Ui.weight(1); r.leftMargin = Ui.dp(a, 5);
            if (i + 1 < views.size()) row.addView(views.get(i + 1), r);
            else row.addView(new View(a), r);
            parent.addView(row, Ui.matchWrap(a, i == 0 ? topDp : 10));
        }
    }

    /** Collapsible section ("expander"). */
    static LinearLayout expander(MainActivity a, String title, boolean open, View content) {
        LinearLayout box = Ui.card(a);
        TextView head = Ui.text(a, (open ? "▾ " : "▸ ") + title, 13.5f, Ui.TEAL_DARK, true);
        head.setPadding(0, Ui.dp(a, 2), 0, Ui.dp(a, 2));
        box.addView(head);
        FrameLayout holder = new FrameLayout(a);
        holder.addView(content);
        holder.setVisibility(open ? View.VISIBLE : View.GONE);
        box.addView(holder, Ui.matchWrap(a, 6));
        head.setOnClickListener(v -> {
            boolean show = holder.getVisibility() != View.VISIBLE;
            holder.setVisibility(show ? View.VISIBLE : View.GONE);
            head.setText((show ? "▾ " : "▸ ") + title);
        });
        return box;
    }

    static List<String> listOf(String... v) { return new ArrayList<>(Arrays.asList(v)); }

    static String joinDot(Collection<String> parts) {
        StringBuilder b = new StringBuilder();
        for (String p : parts) { if (p == null || p.isEmpty()) continue; if (b.length() > 0) b.append(" · "); b.append(p); }
        return b.toString();
    }
}
