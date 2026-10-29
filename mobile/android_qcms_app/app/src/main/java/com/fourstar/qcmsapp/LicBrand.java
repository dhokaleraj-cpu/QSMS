package com.fourstar.qcmsapp;

import android.content.Context;
import android.graphics.Bitmap;

import org.json.JSONArray;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;

/**
 * R39 shell branding (website R38 header: core/ui.py header_company_logo_html / header_avatar_html, core/auth.py LOGIN_COVER_*):
 * - licensed company logo (qcms_company_profiles.logo_path in quality-documents) for the right of the top bar,
 * - the signed-in user's Employee Master photo (employees.photo_storage_path) for the top-bar avatar,
 * - the developer-set login cover photo (public bucket qcms-public/login/cover.{jpg|png}).
 * Images are cached in memory and in the app cache folder so the top bar and the login page also show them offline.
 * Every network call runs on a background thread; nothing here holds a secret.
 */
final class LicBrand {
    private LicBrand() { }

    private static Bitmap logo, avatar, cover;
    private static String logoTenant = "", avatarKey = "";
    private static boolean coverLoaded = false;

    // ------------------------------------------------------------------ file cache
    private static File cacheFile(Context c, String name) {
        try {
            File dir = c.getCacheDir();
            return dir == null ? null : new File(dir, "qcms_brand_" + name.replaceAll("[^A-Za-z0-9_.-]", "_"));
        } catch (Exception e) {
            return null;
        }
    }

    static byte[] readCache(Context c, String name) {
        File f = cacheFile(c, name);
        if (f == null || !f.exists() || f.length() == 0 || f.length() > LicService.LOGIN_COVER_MAX_BYTES) return null;
        try (InputStream in = new FileInputStream(f); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[16384]; int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            return out.toByteArray();
        } catch (Exception e) {
            return null;
        }
    }

    static void writeCache(Context c, String name, byte[] data) {
        File f = cacheFile(c, name);
        if (f == null) return;
        if (data == null || data.length == 0) { try { f.delete(); } catch (Exception ignored) { } return; }
        try (FileOutputStream out = new FileOutputStream(f)) { out.write(data); } catch (Exception ignored) { }
    }

    // ------------------------------------------------------------------ company logo
    /** Cached company logo (memory) or null; call companyLogo() on a background thread to load it. */
    static synchronized Bitmap cachedLogo(Api api) { return api.tenantId.equals(logoTenant) ? logo : null; }

    /** Background thread: company logo of the signed-in user's company (online, else the cached copy). */
    static Bitmap companyLogo(Context c, Api api) {
        synchronized (LicBrand.class) { if (logo != null && api.tenantId.equals(logoTenant)) return logo; }
        String tid = api.tenantId;
        String cacheName = "logo_" + (tid.isEmpty() ? "default" : tid);
        byte[] data = null;
        try {
            if (!tid.isEmpty()) {
                JSONArray rows = new JSONArray(api.get("qcms_company_profiles?select=logo_path&tenant_id=eq." + Api.enc(tid) + "&limit=1", false).body);
                String path = rows.length() == 0 ? "" : LicService.s(rows.getJSONObject(0), "logo_path");
                data = path.isEmpty() ? null : api.download(path);
                writeCache(c, cacheName, data);
            }
        } catch (Exception offline) {
            data = readCache(c, cacheName);
        }
        Bitmap b = data == null ? null : Photos.thumbnail(data, 240);
        synchronized (LicBrand.class) { logo = b; logoTenant = tid; }
        return b;
    }

    // ------------------------------------------------------------------ user avatar (Employee Master photo)
    static synchronized Bitmap cachedAvatar(Api api) { return (api.userId + "/" + api.employeeId).equals(avatarKey) ? avatar : null; }

    /** Background thread: the signed-in user's employee photo (employees.photo_storage_path) or null (initials avatar). */
    static Bitmap userPhoto(Context c, Api api) {
        String key = api.userId + "/" + api.employeeId;
        synchronized (LicBrand.class) { if (avatar != null && key.equals(avatarKey)) return avatar; }
        String cacheName = "avatar_" + (api.userId.isEmpty() ? "user" : api.userId);
        byte[] data = null;
        try {
            if (!api.employeeId.isEmpty()) {
                JSONArray rows = new JSONArray(api.get("employees?select=photo_storage_path&id=eq." + Api.enc(api.employeeId) + "&limit=1", false).body);
                String path = rows.length() == 0 ? "" : LicService.s(rows.getJSONObject(0), "photo_storage_path");
                data = path.isEmpty() ? null : api.download(path);
                writeCache(c, cacheName, data);
            }
        } catch (Exception offline) {
            data = readCache(c, cacheName);
        }
        Bitmap b = data == null ? null : Photos.thumbnail(data, 160);
        synchronized (LicBrand.class) { avatar = b; avatarKey = key; }
        return b;
    }

    /** "Rajesh Dhokale" -> "RD" (e-mail when no name). */
    static String initials(Api api) {
        String n = api.fullName == null || api.fullName.trim().isEmpty() ? api.email : api.fullName;
        StringBuilder b = new StringBuilder();
        for (String w : (n == null ? "" : n).split("[\\s._@-]+")) {
            if (w.isEmpty()) continue;
            b.append(Character.toUpperCase(w.charAt(0)));
            if (b.length() >= 2) break;
        }
        return b.length() == 0 ? "U" : b.toString();
    }

    // ------------------------------------------------------------------ login cover photo
    static synchronized Bitmap cachedCover() { return coverLoaded ? cover : null; }

    /** Background thread: developer-set login cover (public URL, no session needed); cached copy offline; null = none. */
    static Bitmap loginCover(Context c) {
        byte[] data = LicService.loginCoverBytes();
        if (data != null) writeCache(c, "login_cover", data);
        else if (!onlineCheck()) data = readCache(c, "login_cover");
        else writeCache(c, "login_cover", null);
        Bitmap b = data == null ? null : Photos.thumbnail(data, 1400);
        synchronized (LicBrand.class) { cover = b; coverLoaded = true; }
        return b;
    }

    /** True when the public storage answers (so "no cover" really means none was uploaded). */
    private static boolean onlineCheck() {
        try {
            java.net.HttpURLConnection h = (java.net.HttpURLConnection) new java.net.URL(BuildConfig.SUPABASE_URL + "/storage/v1/version").openConnection();
            h.setConnectTimeout(4000);
            h.setReadTimeout(4000);
            int code = h.getResponseCode();
            h.disconnect();
            return code > 0;
        } catch (Exception e) {
            return false;
        }
    }

    // ------------------------------------------------------------------ refresh
    /** Forget the cached images (logo / photo / cover changed) and redraw the top bar. Main thread. */
    static void refresh(MainActivity a) {
        synchronized (LicBrand.class) { logo = null; logoTenant = ""; avatar = null; avatarKey = ""; coverLoaded = false; cover = null; }
        LicService.clearImages();
        try { a.refreshBrand(); } catch (Exception ignored) { }
    }

    /** Sign-out: drop the in-memory images of the previous user (the file cache keeps only the public cover offline). */
    static synchronized void clear(Context c) {
        logo = null; logoTenant = ""; avatar = null; avatarKey = "";
        File dir = null;
        try { dir = c.getCacheDir(); } catch (Exception ignored) { }
        File[] files = dir == null ? null : dir.listFiles();
        if (files == null) return;
        for (File f : files) if (f.getName().startsWith("qcms_brand_avatar_") || f.getName().startsWith("qcms_brand_logo_")) { try { f.delete(); } catch (Exception ignored) { } }
    }
}
