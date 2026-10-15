package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Python-compatible helpers used by the Administration screens (same text / JSON as the website). */
final class AdmPy {
    private AdmPy() { }

    static boolean isNull(Object v) { return v == null || v == JSONObject.NULL; }

    static String s(Object v) { return isNull(v) ? "" : String.valueOf(v); }

    /** Null-safe string of a JSON field (JSON null -> ""). */
    static String j(JSONObject o, String key) { return o == null ? "" : Lookups.j(o, key); }

    static boolean truthy(JSONObject o, String key) {
        if (o == null) return false;
        Object v = o.opt(key);
        if (isNull(v)) return false;
        if (v instanceof Boolean) return (Boolean) v;
        String t = String.valueOf(v);
        return !t.isEmpty() && !"false".equalsIgnoreCase(t) && !"0".equals(t);
    }

    /** bool(row.get(key, default)) - the default applies only when the key is missing. */
    static boolean bool(JSONObject o, String key, boolean def) {
        if (o == null || !o.has(key)) return def;
        return truthy(o, key);
    }

    static String fold(String v) { return v == null ? "" : v.toLowerCase(Locale.ROOT); }

    /** datetime.now(timezone.utc).isoformat(). */
    static String nowUtc() { return OffsetDateTime.now(ZoneOffset.UTC).toString(); }

    /** str.strip(chars). */
    static String strip(String text, String chars) {
        if (text == null) return "";
        int b = 0, e = text.length();
        while (b < e && chars.indexOf(text.charAt(b)) >= 0) b++;
        while (e > b && chars.indexOf(text.charAt(e - 1)) >= 0) e--;
        return text.substring(b, e);
    }

    /** Python str.title(). */
    static String title(String text) {
        StringBuilder b = new StringBuilder();
        boolean prevCased = false;
        for (char ch : text.toCharArray()) {
            if (Character.isLetter(ch)) {
                b.append(prevCased ? Character.toLowerCase(ch) : Character.toUpperCase(ch));
                prevCased = true;
            } else {
                b.append(ch);
                prevCased = false;
            }
        }
        return b.toString();
    }

    // ------------------------------------------------------------------ json.dumps(sort_keys=True, ensure_ascii=False)
    static String dumps(Object v) {
        StringBuilder b = new StringBuilder();
        write(b, v);
        return b.toString();
    }

    private static void write(StringBuilder b, Object v) {
        if (isNull(v)) { b.append("null"); return; }
        if (v instanceof Boolean) { b.append(((Boolean) v) ? "true" : "false"); return; }
        if (v instanceof Integer || v instanceof Long || v instanceof Short) { b.append(v); return; }
        if (v instanceof Number) {
            double d = ((Number) v).doubleValue();
            if (d == Math.rint(d) && Math.abs(d) < 1e16) b.append(String.format(Locale.ROOT, "%.1f", d));
            else b.append(Double.toString(d));
            return;
        }
        if (v instanceof JSONObject) {
            JSONObject o = (JSONObject) v;
            List<String> keys = new ArrayList<>();
            Iterator<String> it = o.keys();
            while (it.hasNext()) keys.add(it.next());
            Collections.sort(keys);
            b.append('{');
            for (int i = 0; i < keys.size(); i++) {
                if (i > 0) b.append(", ");
                quote(b, keys.get(i));
                b.append(": ");
                write(b, o.opt(keys.get(i)));
            }
            b.append('}');
            return;
        }
        if (v instanceof JSONArray) {
            JSONArray a = (JSONArray) v;
            b.append('[');
            for (int i = 0; i < a.length(); i++) {
                if (i > 0) b.append(", ");
                write(b, a.opt(i));
            }
            b.append(']');
            return;
        }
        quote(b, String.valueOf(v));
    }

    private static void quote(StringBuilder b, String s) {
        b.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                case '\b': b.append("\\b"); break;
                case '\f': b.append("\\f"); break;
                default:
                    if (c < 0x20) b.append(String.format(Locale.ROOT, "\\u%04x", (int) c));
                    else b.append(c);
            }
        }
        b.append('"');
    }

    // ------------------------------------------------------------------ notification_service._template_text
    private static final Pattern PLACEHOLDER = Pattern.compile("\\{\\{\\s*([a-zA-Z0-9_]+)\\s*\\}\\}");

    /** {{ field }} placeholders -> values; unknown / empty values render as '-' (format_map with _SafeTemplate). */
    static String templateText(Object value, Map<String, Object> context) {
        String text = s(value);
        String converted = PLACEHOLDER.matcher(text).replaceAll("{$1}");
        StringBuilder out = new StringBuilder();
        int i = 0, n = converted.length();
        while (i < n) {
            char c = converted.charAt(i);
            if (c == '{') {
                if (i + 1 < n && converted.charAt(i + 1) == '{') { out.append('{'); i += 2; continue; }
                int close = converted.indexOf('}', i);
                if (close < 0) return converted;
                String field = converted.substring(i + 1, close);
                if (field.isEmpty() || Character.isDigit(field.charAt(0)) || field.contains("{") || field.contains(":") || field.contains("!") || field.contains("[") || field.contains(".")) return converted;
                Object v = context.get(field);
                out.append(isNull(v) || "".equals(v) || !context.containsKey(field) ? "-" : pyStr(v));
                i = close + 1;
            } else if (c == '}') {
                if (i + 1 < n && converted.charAt(i + 1) == '}') { out.append('}'); i += 2; continue; }
                return converted;
            } else {
                out.append(c);
                i++;
            }
        }
        return out.toString();
    }

    static String pyStr(Object v) {
        if (v instanceof Boolean) return ((Boolean) v) ? "True" : "False";
        if (v instanceof Double || v instanceof Float) {
            double d = ((Number) v).doubleValue();
            if (d == Math.rint(d) && Math.abs(d) < 1e16) return String.format(Locale.ROOT, "%.1f", d);
            return Double.toString(d);
        }
        return String.valueOf(v);
    }

    /** _split_emails: unique addresses containing @ separated by ; , or newline. */
    static List<String> splitEmails(String value) {
        List<String> out = new ArrayList<>();
        for (String token : s(value).split("[;,\\n]+")) {
            String e = token.trim();
            if (e.isEmpty() || !e.contains("@")) continue;
            boolean dup = false;
            for (String x : out) if (fold(x).equals(fold(e))) { dup = true; break; }
            if (!dup) out.add(e);
        }
        return out;
    }

    /** _normalize_department. */
    static String normDept(Object v) { return fold(s(v)).replaceAll("[^a-z0-9]+", ""); }

    /** master_import._norm. */
    static String norm(Object v) {
        String t = fold(s(v).trim()).replaceAll("[^a-z0-9]+", " ");
        return t.trim();
    }

    static Matcher match(String regex, String text) { return Pattern.compile(regex).matcher(text); }
}
