package com.fourstar.qcmsapp;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.net.Network;
import android.os.Handler;
import android.os.Looper;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.lang.reflect.Field;
import java.net.HttpURLConnection;
import java.net.ProtocolException;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Supabase REST / Auth client (framework only: HttpURLConnection + org.json).
 * Every call runs with the logged-in user's own access token, so the same Row Level
 * Security and module permissions as on the QCMS website apply.
 */
public final class Api {
    public interface Task<T> { T run() throws Exception; }
    public interface Callback<T> { void done(T result, Exception error); }

    public static final class ApiException extends Exception {
        public final int status;
        public ApiException(int status, String message) { super(message); this.status = status; }
    }

    public static final class Response {
        public final int code; public final String body; public final String contentRange; public final boolean fromCache;
        Response(int code, String body, String contentRange, boolean fromCache) { this.code = code; this.body = body; this.contentRange = contentRange; this.fromCache = fromCache; }
    }

    private static Api instance;
    private static final ExecutorService IO = Executors.newFixedThreadPool(4);
    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    private final Context context;
    private final SecureStore secure;
    private final SharedPreferences cache;
    private final SharedPreferences prefs;
    private String accessToken;
    private String refreshToken;
    private long expiresAtMs;
    public String userId = "";
    public String email = "";
    public String fullName = "";
    public String role = "";
    public String tenantId = "";
    public String employeeId = "";
    public String employeeLabel = "";
    public volatile boolean lastCallOffline = false;

    private Api(Context context) {
        this.context = context.getApplicationContext();
        this.secure = new SecureStore(this.context);
        this.cache = this.context.getSharedPreferences("qcms_cache", Context.MODE_PRIVATE);
        this.prefs = this.context.getSharedPreferences("qcms_app", Context.MODE_PRIVATE);
        this.email = prefs.getString("email", "");
        this.fullName = prefs.getString("full_name", "");
        this.role = prefs.getString("role", "");
        this.userId = prefs.getString("user_id", "");
    }

    public static synchronized Api get(Context context) {
        if (instance == null) instance = new Api(context);
        return instance;
    }

    public SharedPreferences prefs() { return prefs; }

    // ------------------------------------------------------------------ async
    public static <T> void async(Task<T> task, Callback<T> callback) {
        IO.execute(() -> {
            T result = null; Exception error = null;
            try { result = task.run(); } catch (Exception e) { error = e; }
            final T r = result; final Exception err = error;
            MAIN.post(() -> callback.done(r, err));
        });
    }

    public static void main(Runnable runnable) { MAIN.post(runnable); }

    public boolean online() {
        try {
            ConnectivityManager cm = (ConnectivityManager) context.getSystemService(Context.CONNECTIVITY_SERVICE);
            Network n = cm == null ? null : cm.getActiveNetwork();
            NetworkCapabilities caps = n == null ? null : cm.getNetworkCapabilities(n);
            return caps != null && caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
        } catch (Exception e) {
            return true;
        }
    }

    // ------------------------------------------------------------------ auth
    public boolean hasSavedSession() { return secure.get("refresh_token") != null; }

    public boolean isAdmin() { return "ADMIN".equalsIgnoreCase(role); }

    public synchronized void signIn(String mail, String password) throws Exception {
        JSONObject body = new JSONObject();
        body.put("email", mail.trim());
        body.put("password", password);
        Response r = http("POST", "/auth/v1/token?grant_type=password", body.toString(), false, null);
        storeTokens(new JSONObject(r.body));
        loadProfile();
    }

    /** Change the signed-in user's password (Supabase Auth PUT /auth/v1/user). */
    public void changePassword(String newPassword) throws Exception {
        Response r = authed("PUT", "/auth/v1/user", new JSONObject().put("password", newPassword).toString(), null);
        if (new JSONObject(r.body).optString("id", "").isEmpty()) throw new ApiException(500, "Supabase did not confirm the password change.");
    }

    /** Same as changePassword (name used by the Administration area). */
    public void updatePassword(String password) throws Exception { changePassword(password); }

    /** Re-check the password of the signed-in user (for sensitive actions). */
    public void verifyPassword(String password) throws Exception {
        signIn(email, password);
    }

    public synchronized boolean restoreSession() {
        String saved = secure.get("refresh_token");
        if (saved == null) return false;
        refreshToken = saved;
        try {
            refresh();
            loadProfile();
            return true;
        } catch (ApiException e) {
            if (e.status == 400 || e.status == 401 || e.status == 403) secure.put("refresh_token", null);
            return false;
        } catch (Exception e) {
            return false;
        }
    }

    /**
     * Background use (NotifJob): make sure a usable session exists without touching the UI.
     * Uses the in-memory token while it is valid, otherwise the encrypted saved refresh token.
     * Returns false (quietly) when nobody is signed in on this phone.
     */
    public synchronized boolean ensureSession() {
        if (accessToken != null && System.currentTimeMillis() < expiresAtMs - 60_000L) return true;
        if (refreshToken == null) {
            String saved = secure.get("refresh_token");
            if (saved == null) return false;
            refreshToken = saved;
        }
        try {
            refresh();
            return accessToken != null;
        } catch (Exception e) {
            return false;
        }
    }

    public boolean signedIn() { return accessToken != null || hasSavedSession(); }

    private synchronized void refresh() throws Exception {
        if (refreshToken == null) throw new ApiException(401, "Please sign in again.");
        JSONObject body = new JSONObject();
        body.put("refresh_token", refreshToken);
        Response r = http("POST", "/auth/v1/token?grant_type=refresh_token", body.toString(), false, null);
        storeTokens(new JSONObject(r.body));
    }

    private void storeTokens(JSONObject json) throws JSONException {
        accessToken = json.getString("access_token");
        refreshToken = json.optString("refresh_token", refreshToken);
        expiresAtMs = System.currentTimeMillis() + json.optLong("expires_in", 3600) * 1000L;
        JSONObject user = json.optJSONObject("user");
        if (user != null) {
            userId = user.optString("id", userId);
            email = user.optString("email", email);
        }
        secure.put("refresh_token", prefs.getBoolean("keep_signed_in", true) ? refreshToken : null);
        prefs.edit().putString("email", email).putString("user_id", userId).apply();
    }

    private void loadProfile() {
        try {
            JSONArray rows = new JSONArray(get("profiles?select=full_name,role,email,tenant_id&id=eq." + userId, false).body);
            if (rows.length() > 0) {
                JSONObject p = rows.getJSONObject(0);
                fullName = p.optString("full_name", "");
                role = p.optString("role", "");
                tenantId = p.optString("tenant_id", "");
                prefs.edit().putString("full_name", fullName).putString("role", role).apply();
            }
            try {
                String emp = authed("POST", "/rest/v1/rpc/qcms_current_login_employee_id", "{}", null).body.trim().replace("\"", "");
                employeeId = emp.equals("null") ? "" : emp;
                if (!employeeId.isEmpty()) {
                    JSONArray e = new JSONArray(get("employees?select=employee_code,first_name,last_name&id=eq." + employeeId, false).body);
                    if (e.length() > 0) {
                        JSONObject r = e.getJSONObject(0);
                        employeeLabel = (r.optString("employee_code") + " · " + r.optString("first_name") + " " + r.optString("last_name")).trim();
                    }
                }
            } catch (Exception ignored) { employeeId = ""; }
        } catch (Exception ignored) { }
    }

    public void signOut() {
        final String token = accessToken;
        accessToken = null; refreshToken = null; expiresAtMs = 0;
        secure.put("refresh_token", null);
        cache.edit().clear().apply();
        prefs.edit().remove("full_name").remove("role").apply();
        if (token != null) {
            IO.execute(() -> {
                try { http("POST", "/auth/v1/logout", "{}", false, token); } catch (Exception ignored) { }
            });
        }
    }

    private synchronized String token() throws Exception {
        if (accessToken == null || System.currentTimeMillis() > expiresAtMs - 60_000L) refresh();
        return accessToken;
    }

    // ------------------------------------------------------------------ REST
    public static String enc(String value) {
        try { return URLEncoder.encode(value, "UTF-8"); } catch (Exception e) { return value; }
    }

    /** PostgREST GET. With cache=true the last good answer is kept for offline viewing. */
    public Response get(String path, boolean useCache) throws Exception {
        try {
            Response r = authed("GET", "/rest/v1/" + path, null, null);
            if (useCache) cache.edit().putString(path, r.body).apply();
            lastCallOffline = false;
            return r;
        } catch (IOException offline) {
            lastCallOffline = true;
            String saved = useCache ? cache.getString(path, null) : null;
            if (saved != null) return new Response(200, saved, null, true);
            throw new ApiException(0, "No internet connection. Connect and tap refresh.");
        }
    }

    public JSONArray rows(String path) throws Exception {
        return new JSONArray(get(path, true).body);
    }

    /** Row count using PostgREST exact count (Content-Range: 0-0/123). */
    public int count(String path) throws Exception {
        String sep = path.contains("?") ? "&" : "?";
        try {
            Response r = authed("GET", "/rest/v1/" + path + sep + "limit=1", null, "count=exact");
            int n = parseCount(r.contentRange);
            cache.edit().putInt("count:" + path, n).apply();
            lastCallOffline = false;
            return n;
        } catch (IOException offline) {
            lastCallOffline = true;
            return cache.getInt("count:" + path, 0);
        }
    }

    static int parseCount(String contentRange) {
        if (contentRange == null || !contentRange.contains("/")) return 0;
        String total = contentRange.substring(contentRange.indexOf('/') + 1).trim();
        try { return Integer.parseInt(total); } catch (NumberFormatException e) { return 0; }
    }

    public String rpc(String function, JSONObject args) throws Exception {
        return authed("POST", "/rest/v1/rpc/" + function, args.toString(), null).body;
    }

    // ------------------------------------------------------------------ writes (same as the website's Repository)
    /** Insert one row; id and tenant_id are added like core/repository.py does. Returns the saved row. */
    public JSONObject insert(String table, JSONObject values) throws Exception {
        JSONObject v = new JSONObject(values.toString());
        if (!v.has("id") || v.isNull("id")) v.put("id", java.util.UUID.randomUUID().toString());
        if (!tenantId.isEmpty() && Tables.TENANT.contains(table) && (!v.has("tenant_id") || v.isNull("tenant_id"))) v.put("tenant_id", tenantId);
        String body = authed("POST", "/rest/v1/" + table, v.toString(), "return=representation").body;
        JSONArray rows = new JSONArray(body);
        JSONObject saved = rows.length() > 0 ? rows.getJSONObject(0) : v;
        logActivity("CREATE", table, saved.optString("id"));
        return saved;
    }

    /** Update one row by id. Returns the saved row. */
    public JSONObject update(String table, String id, JSONObject values) throws Exception {
        JSONArray rows = new JSONArray(patch(table, id, values));
        if (rows.length() == 0) throw new ApiException(403, "The record was not saved - it is not visible / editable for your role.");
        logActivity("UPDATE", table, id);
        return rows.getJSONObject(0);
    }

    /** Insert or update (by id) - one call for a row from a form. */
    public JSONObject save(String table, String id, JSONObject values) throws Exception {
        return id == null || id.isEmpty() ? insert(table, values) : update(table, id, values);
    }

    /** Bulk upsert like Repository.bulk_upsert (on_conflict, merge duplicates). */
    public JSONArray upsert(String table, JSONArray rows, String onConflict) throws Exception {
        JSONArray out = new JSONArray();
        for (int i = 0; i < rows.length(); i++) {
            JSONObject v = new JSONObject(rows.getJSONObject(i).toString());
            if (!v.has("id") || v.isNull("id")) v.put("id", java.util.UUID.randomUUID().toString());
            if (!tenantId.isEmpty() && Tables.TENANT.contains(table) && (!v.has("tenant_id") || v.isNull("tenant_id"))) v.put("tenant_id", tenantId);
            out.put(v);
        }
        if (out.length() == 0) return out;
        String q = onConflict == null || onConflict.isEmpty() ? "" : "?on_conflict=" + enc(onConflict);
        String body = authed("POST", "/rest/v1/" + table + q, out.toString(), "resolution=merge-duplicates,return=representation").body;
        return new JSONArray(body);
    }

    /** Find one row by exact column values (Repository.upsert_by) and update it, else insert. */
    public JSONObject upsertBy(String table, JSONObject values, String... keys) throws Exception {
        StringBuilder q = new StringBuilder(table + "?select=id&limit=1");
        for (String k : keys) {
            Object v = values.opt(k);
            q.append('&').append(k).append(v == null || v == JSONObject.NULL ? "=is.null" : "=eq." + enc(String.valueOf(v)));
        }
        JSONArray found = new JSONArray(get(q.toString(), false).body);
        if (found.length() > 0) return update(table, found.getJSONObject(0).getString("id"), values);
        return insert(table, values);
    }

    /** Delete one row by id (DELETE /rest/v1/table?id=eq.x) and log the activity like the website. */
    public void delete(String table, String id) throws Exception {
        authed("DELETE", "/rest/v1/" + table + "?id=eq." + enc(id), null, "return=minimal");
        logActivity("DELETE", table, id);
    }

    /** Call a Supabase Edge Function with the user's session (e.g. qcms-send-email). Returns the body. */
    public String invokeFunction(String name, JSONObject body) throws Exception {
        byte[] data = raw("POST", "/functions/v1/" + name, (body == null ? "{}" : body.toString()).getBytes(StandardCharsets.UTF_8), "application/json", null);
        return new String(data, StandardCharsets.UTF_8);
    }

    /** RPC returning a set of rows (PostgREST JSON array). Null / scalar answers become an empty array. */
    public JSONArray rpcRows(String function, JSONObject args) throws Exception {
        String body = rpc(function, args == null ? new JSONObject() : args).trim();
        if (body.startsWith("[")) return new JSONArray(body);
        if (body.startsWith("{")) return new JSONArray().put(new JSONObject(body));
        return new JSONArray();
    }

    /** RPC returning jsonb (one object). Null answers become an empty object. */
    public JSONObject rpcObject(String function, JSONObject args) throws Exception {
        String body = rpc(function, args == null ? new JSONObject() : args).trim();
        if (body.startsWith("{")) return new JSONObject(body);
        if (body.startsWith("[")) {
            JSONArray arr = new JSONArray(body);
            if (arr.length() > 0 && arr.opt(0) instanceof JSONObject) return arr.getJSONObject(0);
        }
        return new JSONObject();
    }

    public Object rpcValue(String function, JSONObject args) throws Exception {
        String body = rpc(function, args).trim();
        if (body.isEmpty() || body.equals("null")) return null;
        if (body.startsWith("{")) return new JSONObject(body);
        if (body.startsWith("[")) return new JSONArray(body);
        if (body.startsWith("\"")) return body.substring(1, body.length() - 1);
        return body;
    }

    /** Next document / master number from the same server sequences as the website. */
    public String nextNumber(String function, JSONObject args) throws Exception {
        Object v = rpcValue(function, args == null ? new JSONObject() : args);
        if (v instanceof JSONObject) {
            JSONObject o = (JSONObject) v;
            for (String k : new String[]{"code", "number", "document_number", "value"}) if (o.has(k)) return o.optString(k);
        }
        if (v instanceof JSONArray && ((JSONArray) v).length() > 0) {
            Object first = ((JSONArray) v).get(0);
            if (first instanceof JSONObject) {
                JSONObject o = (JSONObject) first;
                java.util.Iterator<String> it = o.keys();
                if (it.hasNext()) return o.optString(it.next());
            }
            return String.valueOf(first);
        }
        return v == null ? "" : String.valueOf(v);
    }

    private void logActivity(String action, String table, String rowId) {
        try {
            JSONObject a = new JSONObject();
            a.put("p_action", action);
            a.put("p_module_key", Tables.moduleFor(table));
            a.put("p_section_key", JSONObject.NULL);
            a.put("p_table_name", table);
            a.put("p_row_id", rowId == null || rowId.isEmpty() ? JSONObject.NULL : rowId);
            a.put("p_details", new JSONObject().put("source", "android_app"));
            authed("POST", "/rest/v1/rpc/qcms_log_user_activity", a.toString(), null);
        } catch (Exception ignored) { }
    }

    // ------------------------------------------------------------------ storage (bucket quality-documents)
    public static final String BUCKET = "quality-documents";

    public void upload(String path, byte[] data, String mime, boolean upsert) throws Exception {
        java.util.Map<String, String> h = new java.util.HashMap<>();
        h.put("x-upsert", upsert ? "true" : "false");
        h.put("cache-control", "3600");
        raw("POST", "/storage/v1/object/" + BUCKET + "/" + encPath(path), data, mime, h);
    }

    public void removeObject(String path) {
        try { raw("DELETE", "/storage/v1/object/" + BUCKET + "/" + encPath(path), null, null, null); } catch (Exception ignored) { }
    }

    // R39 (Licence & Company / STAWN Developer Console): tables keyed by tenant_id and the public bucket qcms-public
    /** PATCH rows matching a PostgREST filter (e.g. "tenant_id=eq.x"); returns the JSON array body. */
    public String patchWhere(String table, String filter, JSONObject values) throws Exception {
        return authed("PATCH", "/rest/v1/" + table + "?" + filter, values.toString(), "return=representation").body;
    }

    /** INSERT one row exactly as given (no id / tenant_id added - for tables keyed by tenant_id). */
    public String insertRaw(String table, JSONObject values) throws Exception {
        return authed("POST", "/rest/v1/" + table, values.toString(), "return=representation").body;
    }

    /** Upload to another storage bucket (e.g. qcms-public, developer-only write). */
    public void uploadTo(String bucket, String path, byte[] data, String mime, boolean upsert, String cacheControl) throws Exception {
        java.util.Map<String, String> h = new java.util.HashMap<>();
        h.put("x-upsert", upsert ? "true" : "false");
        h.put("cache-control", cacheControl == null ? "3600" : cacheControl);
        raw("POST", "/storage/v1/object/" + bucket + "/" + encPath(path), data, mime, h);
    }

    /** Remove one object from a bucket; false when it was not there / not allowed. */
    public boolean removeFrom(String bucket, String path) {
        try { raw("DELETE", "/storage/v1/object/" + bucket + "/" + encPath(path), null, null, null); return true; } catch (Exception e) { return false; }
    }

    public String signedUrl(String path, int seconds) throws Exception {
        byte[] body = new JSONObject().put("expiresIn", seconds).toString().getBytes(StandardCharsets.UTF_8);
        JSONObject r = new JSONObject(new String(raw("POST", "/storage/v1/object/sign/" + BUCKET + "/" + encPath(path), body, "application/json", null), StandardCharsets.UTF_8));
        String rel = r.optString("signedURL", r.optString("signedUrl", ""));
        if (rel.isEmpty()) throw new ApiException(404, "File link not available.");
        return rel.startsWith("http") ? rel : BuildConfig.SUPABASE_URL + "/storage/v1" + (rel.startsWith("/") ? rel : "/" + rel);
    }

    public byte[] download(String path) throws Exception {
        return raw("GET", "/storage/v1/object/authenticated/" + BUCKET + "/" + encPath(path), null, null, null);
    }

    private static String encPath(String path) {
        StringBuilder b = new StringBuilder();
        for (String part : path.split("/")) {
            if (b.length() > 0) b.append('/');
            b.append(enc(part).replace("+", "%20"));
        }
        return b.toString();
    }

    private byte[] raw(String method, String path, byte[] body, String mime, java.util.Map<String, String> headers) throws Exception {
        for (int attempt = 0; attempt < 2; attempt++) {
            HttpURLConnection c = (HttpURLConnection) new URL(BuildConfig.SUPABASE_URL + path).openConnection();
            try {
                setMethod(c, method);
                c.setConnectTimeout(20000);
                c.setReadTimeout(90000);
                c.setRequestProperty("apikey", BuildConfig.SUPABASE_KEY);
                c.setRequestProperty("Authorization", "Bearer " + token());
                if (headers != null) for (java.util.Map.Entry<String, String> e : headers.entrySet()) c.setRequestProperty(e.getKey(), e.getValue());
                if (body != null) {
                    c.setDoOutput(true);
                    c.setRequestProperty("Content-Type", mime == null ? "application/octet-stream" : mime);
                    c.setFixedLengthStreamingMode(body.length);
                    try (OutputStream out = c.getOutputStream()) { out.write(body); }
                }
                int code = c.getResponseCode();
                if (code == 401 && attempt == 0) { refresh(); continue; }
                InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
                byte[] data = readBytes(in);
                if (code >= 400) throw new ApiException(code, friendly(code, new String(data, StandardCharsets.UTF_8)));
                return data;
            } finally {
                c.disconnect();
            }
        }
        throw new ApiException(401, "Session expired - please sign in again.");
    }

    private static byte[] readBytes(InputStream in) throws IOException {
        if (in == null) return new byte[0];
        try (InputStream s = in; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[16384]; int n;
            while ((n = s.read(buf)) > 0) out.write(buf, 0, n);
            return out.toByteArray();
        }
    }

    public String patch(String table, String id, JSONObject values) throws Exception {
        return authed("PATCH", "/rest/v1/" + table + "?id=eq." + enc(id), values.toString(), "return=representation").body;
    }

    private Response authed(String method, String path, String body, String prefer) throws Exception {
        try {
            return http(method, path, body, true, token(), prefer);
        } catch (ApiException e) {
            if (e.status == 401) {
                refresh();
                return http(method, path, body, true, accessToken, prefer);
            }
            throw e;
        }
    }

    private Response http(String method, String path, String body, boolean rest, String bearer) throws Exception {
        return http(method, path, body, rest, bearer, null);
    }

    private Response http(String method, String path, String body, boolean rest, String bearer, String prefer) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(BuildConfig.SUPABASE_URL + path).openConnection();
        try {
            setMethod(c, method);
            c.setConnectTimeout(15000);
            c.setReadTimeout(30000);
            c.setRequestProperty("apikey", BuildConfig.SUPABASE_KEY);
            c.setRequestProperty("Accept", "application/json");
            c.setRequestProperty("X-Client-Info", "qcms-android/" + BuildConfig.VERSION_NAME);
            if (bearer != null) c.setRequestProperty("Authorization", "Bearer " + bearer);
            if (prefer != null) c.setRequestProperty("Prefer", prefer);
            if (body != null) {
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                try (OutputStream out = c.getOutputStream()) { out.write(body.getBytes(StandardCharsets.UTF_8)); }
            }
            int code = c.getResponseCode();
            InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
            String text = read(in);
            if (code >= 400) throw new ApiException(code, friendly(code, text));
            return new Response(code, text, c.getHeaderField("Content-Range"), false);
        } finally {
            c.disconnect();
        }
    }

    /** Android's HttpURLConnection accepts PATCH; the reflection path is only a safety net. */
    private static void setMethod(HttpURLConnection c, String method) throws ProtocolException {
        try {
            c.setRequestMethod(method);
        } catch (ProtocolException e) {
            try {
                Field f = HttpURLConnection.class.getDeclaredField("method");
                f.setAccessible(true);
                f.set(c, method);
            } catch (Exception ignored) {
                throw e;
            }
        }
    }

    private static String read(InputStream in) throws IOException {
        if (in == null) return "";
        try (InputStream s = in; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[8192]; int n;
            while ((n = s.read(buf)) > 0) out.write(buf, 0, n);
            return out.toString("UTF-8");
        }
    }

    static String friendly(int code, String body) {
        String message = body == null ? "" : body;
        try {
            JSONObject json = new JSONObject(body);
            message = json.optString("message", json.optString("msg", json.optString("error_description", json.optString("error", body))));
        } catch (Exception ignored) { }
        String low = message.toLowerCase(Locale.ROOT);
        if (low.contains("invalid login credentials")) return "Email or password is not correct.";
        if (low.contains("email not confirmed")) return "This login is not confirmed yet. Ask the QCMS administrator.";
        if (low.contains("jwt expired")) return "Session expired - please sign in again.";
        if (low.contains("permission denied") || low.contains("row-level security")) return "Your QCMS role does not have permission for this action.";
        if (code == 429) return "Too many attempts. Wait a minute and try again.";
        if (message.length() > 300) message = message.substring(0, 300) + "...";
        return message.isEmpty() ? ("Server error " + code) : message;
    }

    public static String message(Exception e) {
        if (e == null) return "";
        if (e instanceof ApiException) return e.getMessage();
        if (e instanceof IOException) return "No internet connection or QCMS server not reachable. Try again.";
        return e.getMessage() == null ? e.toString() : e.getMessage();
    }
}
