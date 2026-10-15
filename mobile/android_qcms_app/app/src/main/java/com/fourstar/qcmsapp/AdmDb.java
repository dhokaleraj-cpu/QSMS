package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;

/**
 * Database helpers for the Administration screens, written like core/repository.py and
 * core/system_settings.py so the app stores exactly what the website stores.
 * Every method that touches the network must run inside Api.async.
 */
final class AdmDb {
    private AdmDb() { }

    static final String ADMIN_ONLY = "Administrator access is required.";

    /** Repository.select with eq filters (None -> is.null), order and limit. */
    static JSONArray select(Api api, String table, JSONObject eq, String order, int limit) throws Exception {
        StringBuilder q = new StringBuilder(table).append("?select=*");
        if (eq != null) {
            Iterator<String> it = eq.keys();
            while (it.hasNext()) {
                String k = it.next();
                Object v = eq.opt(k);
                q.append('&').append(k).append(AdmPy.isNull(v) ? "=is.null" : "=eq." + Api.enc(String.valueOf(v)));
            }
        }
        if (order != null && !order.isEmpty()) q.append("&order=").append(order);
        if (limit > 0) q.append("&limit=").append(limit);
        return new JSONArray(api.get(q.toString(), false).body);
    }

    static JSONObject eq(Object... kv) {
        JSONObject o = new JSONObject();
        try { for (int i = 0; i + 1 < kv.length; i += 2) o.put(String.valueOf(kv[i]), kv[i + 1] == null ? JSONObject.NULL : kv[i + 1]); } catch (Exception ignored) { }
        return o;
    }

    static JSONObject first(JSONArray rows) { return rows == null || rows.length() == 0 ? null : rows.optJSONObject(0); }

    static List<JSONObject> list(JSONArray rows) {
        List<JSONObject> out = new ArrayList<>();
        for (int i = 0; rows != null && i < rows.length(); i++) { JSONObject r = rows.optJSONObject(i); if (r != null) out.add(r); }
        return out;
    }

    /** Repository.upsert_by: find one row by the natural key, update it with the payload, else insert the payload. */
    static JSONObject upsertBy(Api api, String table, JSONObject payload, JSONObject natural) throws Exception {
        JSONObject existing = first(select(api, table, natural, null, 1));
        if (existing != null && !AdmPy.j(existing, "id").isEmpty()) return api.update(table, AdmPy.j(existing, "id"), payload);
        return api.insert(table, payload);
    }

    /** Natural key {"tenant_id": repo.tenant_id, ...} used by the email pages. */
    static JSONObject tenantKey(Api api, Object... more) {
        JSONObject k = eq(more);
        try { k.put("tenant_id", api.tenantId == null || api.tenantId.isEmpty() ? JSONObject.NULL : api.tenantId); } catch (Exception ignored) { }
        return k;
    }

    static Object orNull(String text) {
        String t = text == null ? "" : text.trim();
        return t.isEmpty() ? JSONObject.NULL : t;
    }

    // ------------------------------------------------------------------ core/system_settings.py
    static final String AI_MODE_KEY = "qcms.system.ai_assistant_mode";
    static final String[][] AI_MODES = {
        {"ALL", "Enabled for all users (module View permissions still apply)"},
        {"ADMIN_ONLY", "Enabled for System Administrators only"},
        {"DISABLED", "Disabled for everyone"}};
    static final String EMAIL_FROM_MODE_KEY = "qcms.system.email_from_mode";
    static final String[][] EMAIL_FROM_MODES = {
        {"COMPANY", "Company mailbox shows the user's name — replies go to the user (works without extra Microsoft 365 rights)"},
        {"USER", "User's own email address as From (needs Microsoft 365 'Send As' permission for the company mailbox on every user)"}};

    static boolean inModes(String[][] modes, String v) {
        for (String[] m : modes) if (m[0].equals(v)) return true;
        return false;
    }

    static String modeLabel(String[][] modes, String v) {
        for (String[] m : modes) if (m[0].equals(v)) return m[1];
        return v;
    }

    /** ai_mode_record: newest ACTIVE row with a valid mode (null when none). */
    static JSONObject aiModeRecord(Api api) {
        try {
            JSONArray rows = select(api, "master_value_catalog", eq("field_key", AI_MODE_KEY, "status", "ACTIVE"), "last_used_at.desc", 5);
            for (JSONObject r : list(rows)) if (inModes(AI_MODES, AdmPy.j(r, "value_text").trim().toUpperCase(Locale.ROOT))) return r;
        } catch (Exception ignored) { }
        return null;
    }

    /** set_ai_mode (admin only). */
    static JSONObject setAiMode(Api api, String mode) throws Exception {
        mode = mode == null ? "" : mode.trim().toUpperCase(Locale.ROOT);
        if (!inModes(AI_MODES, mode)) throw new Api.ApiException(400, "Select a valid AI Assistant mode.");
        if (!api.isAdmin()) throw new Api.ApiException(403, "Only the QCMS System Administrator can change the AI Assistant setting.");
        String now = AdmPy.nowUtc();
        JSONObject target = null;
        for (JSONObject row : list(select(api, "master_value_catalog", eq("field_key", AI_MODE_KEY), null, 20))) {
            String value = AdmPy.j(row, "value_text").trim().toUpperCase(Locale.ROOT);
            if (value.equals(mode)) target = row;
            else if ("ACTIVE".equals(AdmPy.j(row, "status"))) api.update("master_value_catalog", AdmPy.j(row, "id"), new JSONObject().put("status", "INACTIVE").put("updated_at", now));
        }
        if (target != null) {
            long usage = target.optLong("usage_count", 0);
            return api.update("master_value_catalog", AdmPy.j(target, "id"), new JSONObject().put("status", "ACTIVE").put("last_used_at", now).put("updated_at", now).put("usage_count", usage + 1));
        }
        return api.insert("master_value_catalog", new JSONObject().put("field_key", AI_MODE_KEY).put("value_text", mode).put("status", "ACTIVE").put("last_used_at", now));
    }

    /** get_system_value without the Streamlit secret override (secrets are not visible to the app). */
    static String getSystemValue(Api api, String fieldKey) {
        try {
            JSONObject r = first(select(api, "master_value_catalog", eq("field_key", fieldKey, "status", "ACTIVE"), "last_used_at.desc", 1));
            return r == null ? "" : AdmPy.j(r, "value_text").trim();
        } catch (Exception e) {
            return "";
        }
    }

    /** set_system_value (admin only): older ACTIVE rows -> INACTIVE, the same value is re-activated, else inserted. */
    static JSONObject setSystemValue(Api api, String fieldKey, String value) throws Exception {
        if (!api.isAdmin()) throw new Api.ApiException(403, "Only the QCMS System Administrator can change system settings.");
        value = value == null ? "" : value.trim();
        String now = AdmPy.nowUtc();
        JSONObject target = null;
        String fold = AdmPy.fold(value);
        for (JSONObject row : list(select(api, "master_value_catalog", eq("field_key", fieldKey), null, 50))) {
            if (!value.isEmpty() && AdmPy.fold(AdmPy.j(row, "value_text").trim()).equals(fold)) target = row;
            else if ("ACTIVE".equals(AdmPy.j(row, "status"))) api.update("master_value_catalog", AdmPy.j(row, "id"), new JSONObject().put("status", "INACTIVE").put("updated_at", now));
        }
        if (value.isEmpty()) return null;
        if (target != null) return api.update("master_value_catalog", AdmPy.j(target, "id"), new JSONObject().put("status", "ACTIVE").put("last_used_at", now).put("updated_at", now));
        return api.insert("master_value_catalog", new JSONObject().put("field_key", fieldKey).put("value_text", value).put("status", "ACTIVE").put("last_used_at", now));
    }

    static String emailFromMode(Api api) {
        String v = getSystemValue(api, EMAIL_FROM_MODE_KEY).toUpperCase(Locale.ROOT);
        return inModes(EMAIL_FROM_MODES, v) ? v : "COMPANY";
    }

    // ------------------------------------------------------------------ qsms-user-admin edge function
    /** user_access._invoke: same payload, error field -> exception. */
    static JSONObject userAdmin(Api api, JSONObject payload) throws Exception {
        String body = api.invokeFunction("qsms-user-admin", payload);
        JSONObject data;
        try { data = new JSONObject(body == null || body.trim().isEmpty() ? "{}" : body); }
        catch (Exception e) { throw new Api.ApiException(500, "User administration service returned an invalid response."); }
        String err = AdmPy.j(data, "error");
        if (!err.isEmpty()) throw new Api.ApiException(400, err);
        return data;
    }

    // ------------------------------------------------------------------ employees / departments
    /** user_access._employee_label. */
    static String employeeLabel(JSONObject r) {
        String code = AdmPy.j(r, "employee_code");
        return ((code.isEmpty() ? "-" : code) + " · " + AdmPy.j(r, "first_name") + " " + AdmPy.j(r, "last_name")).trim();
    }

    /** All employees ordered by first name (Repository.select("employees", order_by="first_name", limit=5000)). */
    static List<JSONObject> employees(Api api) throws Exception {
        return list(select(api, "employees", null, "first_name.asc", 5000));
    }

    /** user_access departments: employee departments + the fixed list, sorted. */
    static List<String> accessDepartments(List<JSONObject> employees) {
        java.util.TreeSet<String> set = new java.util.TreeSet<>();
        for (JSONObject e : employees) { String d = AdmPy.j(e, "department").trim(); if (!d.isEmpty()) set.add(d); }
        for (String d : AdmPerm.FIXED_DEPARTMENTS) set.add(d);
        return new ArrayList<>(set);
    }

    /** email_settings._departments: ACTIVE employees ordered by department, unique case-insensitively. */
    static List<String> activeDepartments(Api api) throws Exception {
        List<String> values = new ArrayList<>();
        for (JSONObject r : list(select(api, "employees", eq("status", "ACTIVE"), "department.asc", 5000))) {
            String v = AdmPy.j(r, "department").trim();
            if (v.isEmpty()) continue;
            boolean dup = false;
            for (String x : values) if (AdmPy.fold(x).equals(AdmPy.fold(v))) { dup = true; break; }
            if (!dup) values.add(v);
        }
        return values;
    }

    static boolean has(JSONArray a, String v) {
        for (int i = 0; a != null && i < a.length(); i++) if (v.equals(a.optString(i))) return true;
        return false;
    }
}
