package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.Iterator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Masters write rules ported from the QCMS website:
 * core/master_service.py (MasterService.save: normalise, auto code, required, duplicate check incl. the fuzzy
 * name rule and stop-words, _IDENTITY_DUPLICATE_FIELDS), core/part_identity.py (find_part_conflicts) and
 * app_pages/part_master.py::_save_rows (R28: grid rows are always scoped to their own Part).
 * Every method that touches the network must run inside Api.async.
 */
public final class MstSave {
    private MstSave() { }

    // ------------------------------------------------------------------ master definition
    /** Same information as core/master_definitions.py MasterDef (only what the save path needs). */
    public static final class Def {
        public final String key, label, table;
        public final List<Field> fields = new ArrayList<>();
        public String[] natural = new String[0];
        /** _IDENTITY_DUPLICATE_FIELDS[key] (+ extra_unique_fields). */
        public String[] identity = new String[0];
        public JSONObject fixed = new JSONObject();
        /** PostgREST filter that mirrors MasterDef.array_filter (e.g. "&party_types=cs.%7BCUSTOMER%7D"). */
        public String listFilter = "";
        /** auto_code_field: filled from qsms_next_master_code(p_master_key = key) on a new record when blank. */
        public String autoField = "";

        public Def(String key, String label, String table) { this.key = key; this.label = label; this.table = table; }
        public Def fields(Field... f) { fields.addAll(Arrays.asList(f)); return this; }
        public Def natural(String... n) { natural = n; return this; }
        public Def identity(String... n) { identity = n; return this; }
        public Def fixed(JSONObject f) { fixed = f; return this; }
        public Def list(String filter) { listFilter = filter; return this; }
        public Def auto(String field) { autoField = field; return this; }
    }

    // ------------------------------------------------------------------ small value helpers
    static boolean isNull(Object v) { return v == null || v == JSONObject.NULL; }

    static String s(Object v) { return isNull(v) ? "" : String.valueOf(v); }

    static boolean empty(Object v) {
        if (isNull(v)) return true;
        if (v instanceof JSONArray) return ((JSONArray) v).length() == 0;
        if (v instanceof JSONObject) return ((JSONObject) v).length() == 0;
        return String.valueOf(v).isEmpty();
    }

    static Object orNull(String text) {
        String t = text == null ? "" : text.trim();
        return t.isEmpty() ? JSONObject.NULL : t;
    }

    static Double dbl(Object v) {
        if (isNull(v)) return null;
        if (v instanceof Number) return ((Number) v).doubleValue();
        String t = String.valueOf(v).trim().replace(",", "");
        if (t.isEmpty()) return null;
        try { return Double.parseDouble(t); } catch (NumberFormatException e) { return null; }
    }

    static Long lng(Object v) {
        Double d = dbl(v);
        return d == null ? null : Math.round(d);
    }

    static JSONObject copy(JSONObject o) {
        try { return new JSONObject(o == null ? "{}" : o.toString()); } catch (Exception e) { return new JSONObject(); }
    }

    static JSONObject first(JSONArray rows) { return rows == null || rows.length() == 0 ? null : rows.optJSONObject(0); }

    static String sha256(byte[] data) throws Exception {
        byte[] d = MessageDigest.getInstance("SHA-256").digest(data);
        StringBuilder b = new StringBuilder();
        for (byte x : d) b.append(String.format(Locale.ROOT, "%02x", x));
        return b.toString();
    }

    static String sha256(String text) throws Exception { return sha256(text.getBytes(StandardCharsets.UTF_8)); }

    static JSONObject get(Api api, String table, String id) throws Exception {
        if (id == null || id.isEmpty()) return null;
        return first(api.rows(table + "?select=*&id=eq." + Api.enc(id)));
    }

    // ------------------------------------------------------------------ auto codes
    /** MasterService.next_master_code: qsms_next_master_code(p_master_key) → plain text or {code}. */
    public static String nextMasterCode(Api api, String masterKey) throws Exception {
        Object v = api.rpcValue("qsms_next_master_code", new JSONObject().put("p_master_key", masterKey));
        if (v instanceof JSONObject) {
            JSONObject o = (JSONObject) v;
            String c = Lookups.j(o, "code");
            return (c.isEmpty() ? Lookups.j(o, "qsms_next_master_code") : c).trim();
        }
        if (v instanceof JSONArray) {
            JSONObject o = ((JSONArray) v).optJSONObject(0);
            if (o != null) { String c = Lookups.j(o, "code"); return (c.isEmpty() ? Lookups.j(o, "qsms_next_master_code") : c).trim(); }
            return s(((JSONArray) v).opt(0)).trim();
        }
        return s(v).trim();
    }

    /** RPC returning a code as text or {code} / {<function name>} (qcms_next_material_number, qsms_next_employee_code). */
    public static String codeRpc(Api api, String fn) throws Exception {
        Object v = api.rpcValue(fn, new JSONObject());
        if (v instanceof JSONObject) {
            JSONObject o = (JSONObject) v;
            String c = Lookups.j(o, "code");
            return (c.isEmpty() ? Lookups.j(o, fn) : c).trim();
        }
        if (v instanceof JSONArray) {
            JSONObject o = ((JSONArray) v).optJSONObject(0);
            if (o != null) { String c = Lookups.j(o, "code"); return (c.isEmpty() ? Lookups.j(o, fn) : c).trim(); }
            return s(((JSONArray) v).opt(0)).trim();
        }
        return s(v).trim();
    }

    // ------------------------------------------------------------------ MasterService.normalize_payload
    public static JSONObject normalize(Def def, JSONObject raw, JSONObject existing) throws Exception {
        JSONObject p = new JSONObject();
        for (Field f : def.fields) {
            if (Field.INFO.equals(f.type)) continue;
            Object v = raw != null && raw.has(f.key) ? raw.opt(f.key) : f.def;
            switch (f.type) {
                case Field.NUM: { Double d = dbl(v); p.put(f.key, d == null ? JSONObject.NULL : d); break; }
                case Field.INT: { Long l = lng(v); p.put(f.key, l == null ? JSONObject.NULL : l); break; }
                case Field.DATE: { String t = s(v).trim(); p.put(f.key, t.isEmpty() ? JSONObject.NULL : (t.length() >= 10 ? t.substring(0, 10) : t)); break; }
                case Field.BOOL: p.put(f.key, v instanceof Boolean ? v : "true".equalsIgnoreCase(s(v))); break;
                case Field.TEXT: case Field.AREA: p.put(f.key, orNull(s(v))); break;
                case Field.MULTI: p.put(f.key, v instanceof JSONArray ? v : new JSONArray()); break;
                default: p.put(f.key, empty(v) ? JSONObject.NULL : v);
            }
        }
        Iterator<String> it = def.fixed.keys();
        while (it.hasNext()) {
            String k = it.next();
            Object val = def.fixed.opt(k);
            if ("party_types".equals(k)) {
                TreeSet<String> merged = new TreeSet<>();
                JSONArray prior = existing == null ? null : existing.optJSONArray("party_types");
                for (int i = 0; prior != null && i < prior.length(); i++) if (!prior.isNull(i)) merged.add(prior.optString(i));
                JSONArray add = val instanceof JSONArray ? (JSONArray) val : new JSONArray();
                for (int i = 0; i < add.length(); i++) merged.add(add.optString(i));
                JSONArray out = new JSONArray();
                for (String m : merged) out.put(m);
                p.put(k, out);
            } else {
                p.put(k, val);
            }
        }
        return p;
    }

    /** MasterService.validate_payload. */
    public static List<String> validate(Def def, JSONObject payload) {
        List<String> errors = new ArrayList<>();
        for (Field f : def.fields) if (f.required && empty(payload.opt(f.key))) errors.add(f.label + " is mandatory.");
        if ("quality_assets".equals(def.key)) {
            Long freq = lng(payload.opt("calibration_frequency_days"));
            if (freq != null && freq <= 0) errors.add("Calibration frequency must be greater than zero.");
        }
        return errors;
    }

    // ------------------------------------------------------------------ duplicate rules
    private static final Pattern WS = Pattern.compile("\\s+");
    private static final Pattern WORD = Pattern.compile("[a-z0-9]+");
    static final Set<String> STOP_WORDS = new HashSet<>(Arrays.asList(
        "the", "and", "for", "with", "from", "of", "to", "a", "an", "in", "on",
        "pvt", "private", "ltd", "limited", "inc", "incorporated", "company", "co",
        "gmbh", "kg", "llc", "llp", "india", "active", "approved", "master"));

    static String fold(String v) { return v.toLowerCase(Locale.ROOT); }

    /** _normalized_key_value: arrays sorted + joined, text trimmed, inner spaces collapsed, case-folded. */
    static String normKey(Object v) {
        if (isNull(v)) return "";
        if (v instanceof JSONArray) {
            JSONArray a = (JSONArray) v;
            List<String> items = new ArrayList<>();
            for (int i = 0; i < a.length(); i++) items.add(fold(s(a.opt(i)).trim()));
            Collections.sort(items);
            return String.join("|", items);
        }
        return fold(WS.matcher(String.valueOf(v).trim()).replaceAll(" "));
    }

    /** Punctuation-insensitive word signature ("Kessler + Co. GmbH" == "KESSLER CO GMBH"). */
    static String words(Object v) {
        Matcher m = WORD.matcher(fold(s(v)));
        StringBuilder b = new StringBuilder();
        while (m.find()) { if (b.length() > 0) b.append(' '); b.append(m.group()); }
        return b.toString();
    }

    static List<String> significant(Object v) {
        Matcher m = WORD.matcher(fold(s(v)));
        List<String> out = new ArrayList<>();
        while (m.find()) {
            String w = m.group();
            if (w.length() >= 2 && !STOP_WORDS.contains(w)) out.add(w);
        }
        return out;
    }

    /** _fuzzy_word_duplicate: 2 shared words when the shorter value has ≤2 words, else 3; and ≥67 % overlap. */
    static boolean fuzzyDuplicate(Object left, Object right) {
        List<String> a = significant(left), b = significant(right);
        if (a.size() < 2 || b.size() < 2) return false;
        Set<String> sa = new HashSet<>(a), sb = new HashSet<>(b);
        Set<String> both = new HashSet<>(sa);
        both.retainAll(sb);
        int shared = both.size();
        int shorter = Math.max(1, Math.min(sa.size(), sb.size()));
        int needed = shorter <= 2 ? 2 : 3;
        return shared >= needed && ((double) shared / shorter) >= 0.67;
    }

    static String pretty(String field) { return field.replace('_', ' '); }

    /** MasterService.duplicate_match. */
    static String duplicateMatch(Api api, Def def, JSONObject payload, String recordId, String... extraUnique) throws Exception {
        LinkedHashSet<String> cols = new LinkedHashSet<>();
        cols.add("id");
        cols.addAll(Arrays.asList(def.natural));
        LinkedHashSet<String> fuzzy = new LinkedHashSet<>(Arrays.asList(def.identity));
        fuzzy.addAll(Arrays.asList(extraUnique));
        cols.addAll(fuzzy);
        JSONArray rows = api.rows(def.table + "?select=" + String.join(",", cols) + def.listFilter + "&limit=5000");
        String[] expected = new String[def.natural.length];
        boolean allExpected = def.natural.length > 0;
        for (int i = 0; i < def.natural.length; i++) {
            expected[i] = normKey(payload.opt(def.natural[i]));
            if (expected[i].isEmpty()) allExpected = false;
        }
        for (int r = 0; r < rows.length(); r++) {
            JSONObject row = rows.optJSONObject(r);
            if (row == null) continue;
            if (recordId != null && !recordId.isEmpty() && recordId.equals(Lookups.j(row, "id"))) continue;
            if (allExpected) {
                boolean same = true;
                for (int i = 0; i < def.natural.length; i++) if (!expected[i].equals(normKey(row.opt(def.natural[i])))) { same = false; break; }
                if (same) return "matching controlled key " + String.join(" + ", def.natural);
            }
            for (String field : fuzzy) {
                Object candidate = payload.opt(field);
                Object existing = row.opt(field);
                String nc = normKey(candidate);
                if (nc.isEmpty()) continue;
                if (nc.equals(normKey(existing))) return "matching " + pretty(field);
                boolean descriptive = field.contains("name") || field.contains("description");
                if (descriptive && fuzzyDuplicate(candidate, existing)) return "2–3 matching words in " + pretty(field) + " (" + s(existing) + ")";
            }
        }
        return null;
    }

    /** MasterService.assert_no_duplicate (legacy duplicates stay editable while their natural key is unchanged). */
    public static void assertNoDuplicate(Api api, Def def, JSONObject payload, String recordId, JSONObject current, String... extraUnique) throws Exception {
        String reason;
        boolean keyUnchanged = current != null;
        if (current != null) {
            for (String f : def.natural) if (!normKey(payload.opt(f)).equals(normKey(current.opt(f)))) { keyUnchanged = false; break; }
        }
        if (keyUnchanged) {
            JSONObject natural = copy(payload);
            for (String f : def.natural) natural.put(f, JSONObject.NULL);
            reason = duplicateMatch(api, def, natural, recordId, extraUnique);
        } else {
            reason = duplicateMatch(api, def, payload, recordId, extraUnique);
        }
        if (reason != null) throw new Api.ApiException(409, "Duplicate " + def.label + " is not allowed. Matching words already exist: " + reason + ".");
    }

    /** MasterService.save: load → normalise → auto code → required → duplicate → update / insert. */
    public static JSONObject save(Api api, Def def, JSONObject raw, String recordId) throws Exception {
        JSONObject existing = get(api, def.table, recordId);
        JSONObject payload = normalize(def, raw, existing);
        if (existing == null && !def.autoField.isEmpty() && empty(payload.opt(def.autoField))) {
            payload.put(def.autoField, nextMasterCode(api, def.key));
        }
        List<String> errors = validate(def, payload);
        if (!errors.isEmpty()) throw new Api.ApiException(422, String.join("\n", errors));
        String id = existing != null ? Lookups.j(existing, "id") : recordId;
        assertNoDuplicate(api, def, payload, id, existing);
        return existing != null ? api.update(def.table, id, payload) : api.insert(def.table, payload);
    }

    // ------------------------------------------------------------------ part grids (_save_rows, R28)
    /**
     * part_master._save_rows: every payload gets part_id; a row with id is updated after checking that the stored
     * row belongs to THIS part; a row without id is upserted by {part_id, key fields} (never another Part's row).
     */
    public static int saveRows(Api api, String table, String partId, List<JSONObject> payloads, String... keyFields) throws Exception {
        int n = 0;
        for (JSONObject source : payloads) {
            if (source == null || source.length() == 0) continue;
            JSONObject payload = copy(source);
            payload.put("part_id", partId);
            if (payload.has("id") && !payload.isNull("id") && !payload.optString("id").isEmpty()) {
                String rowId = payload.optString("id");
                payload.remove("id");
                JSONObject current = first(api.rows(table + "?select=id,part_id&id=eq." + Api.enc(rowId)));
                if (current != null && !Lookups.j(current, "part_id").isEmpty() && !partId.equals(Lookups.j(current, "part_id"))) {
                    throw new Api.ApiException(409, "This grid row belongs to another Part. Refresh the page and save again.");
                }
                api.update(table, rowId, payload);
            } else {
                payload.remove("id");
                LinkedHashSet<String> keys = new LinkedHashSet<>();
                keys.add("part_id");
                keys.addAll(Arrays.asList(keyFields));
                for (String k : keys) if (!payload.has(k)) payload.put(k, JSONObject.NULL);
                api.upsertBy(table, payload, keys.toArray(new String[0]));
            }
            n++;
        }
        return n;
    }

    /** Permanent delete of rows removed from a grid (same RPC as the website's password delete panel). */
    public static int deleteRows(Api api, String table, List<JSONObject> removed) throws Exception {
        int n = 0;
        for (JSONObject r : removed) {
            String id = Lookups.j(r, "id");
            if (id.isEmpty()) continue;
            api.rpc("qsms_delete_master_row", new JSONObject().put("p_table_name", table).put("p_record_id", id));
            n++;
        }
        return n;
    }

    // ------------------------------------------------------------------ part identity (core/part_identity.py)
    static String normPart(Object v) { return fold(s(v)).replaceAll("[^0-9a-z]", ""); }

    static String digits(Object v) { return s(v).replaceAll("\\D", ""); }

    static String longestDigitRun(Object left, Object right) {
        String a = digits(left), b = digits(right);
        if (a.isEmpty() || b.isEmpty()) return "";
        int bestLen = 0, bestEnd = 0;
        int[] prev = new int[b.length() + 1];
        for (int i = 1; i <= a.length(); i++) {
            int[] cur = new int[b.length() + 1];
            char ai = a.charAt(i - 1);
            for (int j = 1; j <= b.length(); j++) {
                if (ai == b.charAt(j - 1)) {
                    cur[j] = prev[j - 1] + 1;
                    if (cur[j] > bestLen) { bestLen = cur[j]; bestEnd = i; }
                }
            }
            prev = cur;
        }
        return a.substring(bestEnd - bestLen, bestEnd);
    }

    /** find_part_conflicts → {"exact": [...], "similar": [...]} (rows: Part Number, FSI Part Number, Description, Status, Reason). */
    public static JSONObject partConflicts(Api api, String partNumber, String fsiNumber, String excludeId) throws Exception {
        // live read (require_live=True on the website): never decide identity from the offline copy
        JSONArray parts = new JSONArray(api.get("parts?select=id,part_number,fsi_part_number,part_name,status&limit=10000", false).body);
        String[][] mine = {{"Part Number", partNumber == null ? "" : partNumber.trim()}, {"FSI Part Number", fsiNumber == null ? "" : fsiNumber.trim()}};
        JSONArray exact = new JSONArray();
        List<JSONObject> similar = new ArrayList<>();
        for (int r = 0; r < parts.length(); r++) {
            JSONObject row = parts.optJSONObject(r);
            if (row == null) continue;
            if (excludeId != null && !excludeId.isEmpty() && excludeId.equals(Lookups.j(row, "id"))) continue;
            String[][] old = {{"Part Number", Lookups.j(row, "part_number").trim()}, {"FSI Part Number", Lookups.j(row, "fsi_part_number").trim()}};
            List<String> rowExact = new ArrayList<>();
            String bestRun = "";
            String[] bestPair = {"", ""};
            for (String[] n : mine) {
                if (n[1].isEmpty()) continue;
                String normNew = normPart(n[1]);
                for (String[] o : old) {
                    if (o[1].isEmpty()) continue;
                    if (!normNew.isEmpty() && normNew.equals(normPart(o[1]))) {
                        rowExact.add(n[0] + " " + n[1] + " = existing " + o[0] + " " + o[1]);
                        continue;
                    }
                    String run = longestDigitRun(n[1], o[1]);
                    if (run.length() > bestRun.length()) { bestRun = run; bestPair = new String[]{n[0], o[0]}; }
                }
            }
            JSONObject base = new JSONObject();
            base.put("id", Lookups.j(row, "id"));
            base.put("Part Number", old[0][1]);
            base.put("FSI Part Number", old[1][1]);
            base.put("Part Description", Lookups.j(row, "part_name"));
            base.put("Status", Lookups.j(row, "status"));
            if (!rowExact.isEmpty()) {
                base.put("Reason", String.join("; ", rowExact));
                exact.put(base);
            } else if (bestRun.length() >= 4) {
                base.put("Matching Digits", bestRun);
                base.put("Reason", bestPair[0] + " shares " + bestRun.length() + " digits '" + bestRun + "' with existing " + bestPair[1]);
                similar.add(base);
            }
        }
        similar.sort((x, y) -> {
            int c = Integer.compare(y.optString("Matching Digits").length(), x.optString("Matching Digits").length());
            return c != 0 ? c : x.optString("Part Number").compareTo(y.optString("Part Number"));
        });
        JSONArray sim = new JSONArray();
        for (JSONObject o : similar) sim.put(o);
        return new JSONObject().put("exact", exact).put("similar", sim);
    }

    /** Text block for a conflict list (shown in a dialog). */
    static String conflictText(JSONArray list) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < list.length() && i < 25; i++) {
            JSONObject r = list.optJSONObject(i);
            if (b.length() > 0) b.append("\n\n");
            b.append("• ").append(Lookups.join(r.optString("Part Number"), r.optString("FSI Part Number").isEmpty() ? "" : "FSI " + r.optString("FSI Part Number"),
                r.optString("Part Description"), Ui.pretty(r.optString("Status"))));
            b.append("\n  ").append(r.optString("Reason"));
        }
        if (list.length() > 25) b.append("\n\n… and ").append(list.length() - 25).append(" more");
        return b.toString();
    }
}
