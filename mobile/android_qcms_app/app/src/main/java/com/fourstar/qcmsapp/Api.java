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
            JSONArray rows = new JSONArray(get("profiles?select=full_name,role,email&id=eq." + userId, false).body);
            if (rows.length() > 0) {
                JSONObject p = rows.getJSONObject(0);
                fullName = p.optString("full_name", "");
                role = p.optString("role", "");
                prefs.edit().putString("full_name", fullName).putString("role", role).apply();
            }
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
