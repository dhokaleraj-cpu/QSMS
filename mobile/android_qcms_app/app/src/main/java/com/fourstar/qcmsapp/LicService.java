package com.fourstar.qcmsapp;

import android.graphics.Bitmap;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * R39 port of core/licence_service.py (licence, company profile + logo, STAWN developer console RPCs, WhatsApp settings)
 * and the R38 login cover photo (app_pages/licence_company.py section H, core/auth.py LOGIN_COVER_*).
 * Every check runs in the database (security definer RPCs / RLS); nothing here holds a secret. The WhatsApp access
 * token is an Edge Function secret and is never read, stored or shown by the app.
 */
final class LicService {
    private LicService() { }

    static final String LOGO_BUCKET = Api.BUCKET;                 // quality-documents/{tenant}/company_profile/company_logo.{ext}
    static final int LOGO_MAX_BYTES = 2 * 1024 * 1024;
    static final String LOGIN_COVER_BUCKET = "qcms-public";      // public bucket, STAWN developer-only write
    static final String LOGIN_COVER_PREFIX = "login/cover";
    static final String[] LOGIN_COVER_EXTENSIONS = {"jpg", "png"};
    static final int LOGIN_COVER_MAX_BYTES = 5 * 1024 * 1024;

    /** licence_service.COMPANY_FIELDS (field, label; * = required). */
    static final String[][] COMPANY_FIELDS = {
        {"legal_name", "Registered company name *"}, {"display_name", "Short name shown in the app"},
        {"address_line1", "Address line 1 *"}, {"address_line2", "Address line 2"}, {"city", "City *"}, {"state", "State *"},
        {"country", "Country"}, {"pincode", "PIN code"}, {"gstin", "GSTIN"}, {"pan", "PAN"}, {"cin", "CIN"},
        {"contact_person", "Contact person *"}, {"contact_email", "Contact e-mail *"}, {"contact_phone", "Contact phone *"},
        {"website", "Website"}, {"industry", "Industry"}};
    static final String[] REQUIRED_COMPANY_FIELDS = {"legal_name", "address_line1", "city", "state", "contact_person", "contact_email", "contact_phone"};

    static final String[] PLANS = {"STANDARD", "PROFESSIONAL", "ENTERPRISE", "TRIAL"};
    static final String[] ASSIGN_ROLES = {"ADMIN", "MANAGEMENT", "QUALITY_MANAGER", "QUALITY_ENGINEER", "SUPPLY_CHAIN", "VIEWER"};
    static final String[] WHATSAPP_CATEGORIES = {"APPROVAL", "TASK", "UPDATE", "ALERT"};

    static String s(JSONObject o, String k) { return o == null || o.isNull(k) ? "" : o.optString(k, "").trim(); }

    static boolean isDeveloper() { JSONObject st = Licence.status; return st != null && st.optBoolean("is_stawn_developer", false); }

    static boolean isCompanyAdmin(Api api) {
        JSONObject st = Licence.status;
        return (st != null && st.optBoolean("is_company_admin", false)) || api.isAdmin();
    }

    // ------------------------------------------------------------------ licence
    static JSONObject validateKey(Api api, String key) throws Exception {
        return api.rpcObject("qcms_validate_licence", new JSONObject().put("p_key", key.trim()));
    }

    static JSONObject activateKey(Api api, String key) throws Exception {
        JSONObject r = Licence.activate(api, key);
        try { Licence.load(api); } catch (Exception ignored) { }
        return r;
    }

    // ------------------------------------------------------------------ company profile
    static JSONObject companyProfile(Api api, String tenantId) throws Exception {
        String tid = tenantId == null || tenantId.isEmpty() ? api.tenantId : tenantId;
        JSONArray rows = new JSONArray(api.get("qcms_company_profiles?select=*&tenant_id=eq." + Api.enc(tid) + "&limit=1", false).body);
        return rows.length() > 0 ? rows.getJSONObject(0) : new JSONObject().put("tenant_id", tid);
    }

    static String label(String field) {
        for (String[] f : COMPANY_FIELDS) if (f[0].equals(field)) return f[1].replace(" *", "");
        return field;
    }

    /** licence_service.missing_company_fields */
    static List<String> missingCompanyFields(JSONObject profile) {
        List<String> out = new ArrayList<>();
        for (String f : REQUIRED_COMPANY_FIELDS) if (s(profile, f).isEmpty()) out.add(label(f));
        return out;
    }

    /** licence_service.save_company_profile: update by tenant_id when the row exists, else insert. */
    static JSONObject saveCompanyProfile(Api api, String tenantId, Map<String, String> values, String logoPath, boolean complete) throws Exception {
        String tid = tenantId == null || tenantId.isEmpty() ? api.tenantId : tenantId;
        JSONObject p = new JSONObject();
        for (String[] f : COMPANY_FIELDS) {
            String v = values.get(f[0]) == null ? "" : values.get(f[0]).trim();
            p.put(f[0], v.isEmpty() ? JSONObject.NULL : v);
        }
        if (logoPath != null && !logoPath.isEmpty()) p.put("logo_path", logoPath);
        p.put("updated_by", api.userId.isEmpty() ? JSONObject.NULL : api.userId);
        String now = OffsetDateTime.now(ZoneOffset.UTC).toString();
        p.put("updated_at", now);
        if (complete) {
            List<String> missing = missingCompanyFields(p);
            if (!missing.isEmpty()) throw new Api.ApiException(422, "Fill these company details before finishing the setup: " + String.join(", ", missing));
            p.put("setup_complete", true).put("completed_by", api.userId.isEmpty() ? JSONObject.NULL : api.userId).put("completed_at", now);
        }
        JSONObject existing = companyProfile(api, tid);
        String body = existing.has("created_at")
            ? api.patchWhere("qcms_company_profiles", "tenant_id=eq." + Api.enc(tid), p)
            : api.insertRaw("qcms_company_profiles", new JSONObject(p.toString()).put("tenant_id", tid));
        JSONArray rows = new JSONArray(body.trim().startsWith("[") ? body : "[]");
        if (existing.has("created_at") && rows.length() == 0) throw new Api.ApiException(403, "The company profile was not saved - only the company administrator or STAWN can change it.");
        clearImages();
        return rows.length() > 0 ? rows.getJSONObject(0) : p;
    }

    /** licence_service.upload_company_logo: {tenant}/company_profile/company_logo.{png|jpg} (upsert). */
    static String uploadCompanyLogo(Api api, String tenantId, Attachments.FileData f) throws Exception {
        if (f == null || f.data == null || f.data.length == 0) throw new Api.ApiException(422, "The selected logo file is empty.");
        if (f.data.length > LOGO_MAX_BYTES) throw new Api.ApiException(422, "Use a logo smaller than 2 MB (PNG or JPG).");
        String tid = tenantId == null || tenantId.isEmpty() ? api.tenantId : tenantId;
        boolean png = f.mime != null && f.mime.toLowerCase(Locale.ROOT).endsWith("png");
        String path = tid + "/company_profile/company_logo." + (png ? "png" : "jpg");
        api.upload(path, f.data, png ? "image/png" : "image/jpeg", true);
        clearImages();
        return path;
    }

    // ------------------------------------------------------------------ STAWN developer console
    static JSONArray devOverview(Api api) throws Exception { return api.rpcRows("qcms_dev_licence_overview", new JSONObject()); }

    static JSONObject devIssueLicence(Api api, String tenantId, String plan, int maxUsers, String validTo, String notes) throws Exception {
        JSONObject args = new JSONObject().put("p_tenant_id", tenantId).put("p_plan", plan).put("p_max_users", maxUsers)
            .put("p_valid_to", validTo == null || validTo.isEmpty() ? JSONObject.NULL : validTo)
            .put("p_modules", new JSONArray().put("ALL")).put("p_notes", notes == null || notes.trim().isEmpty() ? JSONObject.NULL : notes.trim());
        return api.rpcObject("qcms_dev_issue_licence", args);
    }

    /** qcms_dev_update_licence: status ACTIVE (renew / re-activate) | SUSPENDED | REVOKED; users / valid-to changes. */
    static JSONObject devUpdateLicence(Api api, String licenceId, String status, Integer maxUsers, String validTo, boolean clearValidTo, String plan) throws Exception {
        JSONObject args = new JSONObject().put("p_licence_id", licenceId)
            .put("p_status", status == null ? JSONObject.NULL : status)
            .put("p_max_users", maxUsers == null ? JSONObject.NULL : maxUsers)
            .put("p_valid_to", validTo == null || validTo.isEmpty() ? JSONObject.NULL : validTo)
            .put("p_clear_valid_to", clearValidTo)
            .put("p_plan", plan == null || plan.isEmpty() ? JSONObject.NULL : plan);
        return api.rpcObject("qcms_dev_update_licence", args);
    }

    static String devCreateCompany(Api api, String code, String name, String plant) throws Exception {
        Object v = api.rpcValue("qcms_dev_create_company", new JSONObject().put("p_tenant_code", code.trim()).put("p_tenant_name", name.trim())
            .put("p_plant_code", plant == null || plant.trim().isEmpty() ? JSONObject.NULL : plant.trim()));
        return v == null ? "" : String.valueOf(v);
    }

    static JSONObject devAssignProfile(Api api, String email, String tenantId, String role) throws Exception {
        return api.rpcObject("qcms_dev_assign_profile", new JSONObject().put("p_email", email.trim()).put("p_tenant_id", tenantId).put("p_role", role));
    }

    // ------------------------------------------------------------------ WhatsApp (no access token here - Edge Function secret)
    static final String[] WHATSAPP_FIELDS = {"enabled", "phone_number_id", "business_account_id", "api_version", "approval_template", "task_template",
        "update_template", "template_language", "send_categories", "default_country_code", "app_link"};

    static JSONObject whatsappSettings(Api api) throws Exception {
        JSONArray rows = new JSONArray(api.get("qcms_whatsapp_settings?select=" + String.join(",", WHATSAPP_FIELDS) + ",tenant_id&tenant_id=eq." + Api.enc(api.tenantId) + "&limit=1", false).body);
        return rows.length() > 0 ? rows.getJSONObject(0) : new JSONObject();
    }

    static void saveWhatsappSettings(Api api, JSONObject values) throws Exception {
        JSONObject p = new JSONObject();
        for (String k : WHATSAPP_FIELDS) if (values.has(k)) p.put(k, values.get(k));
        p.put("updated_by", api.userId.isEmpty() ? JSONObject.NULL : api.userId);
        if (whatsappSettings(api).length() > 0) api.patchWhere("qcms_whatsapp_settings", "tenant_id=eq." + Api.enc(api.tenantId), p);
        else api.insertRaw("qcms_whatsapp_settings", new JSONObject(p.toString()).put("tenant_id", api.tenantId));
    }

    static JSONObject whatsappTest(Api api, String to) throws Exception {
        String body = api.invokeFunction("qcms-whatsapp-dispatch", new JSONObject().put("action", "test").put("to", to.trim()).put("template", "hello_world"));
        try { return new JSONObject(body); } catch (Exception e) { return new JSONObject().put("ok", false).put("error", body.length() > 300 ? body.substring(0, 300) : body); }
    }

    // ------------------------------------------------------------------ R38 login cover photo (qcms-public/login/cover.{jpg|png})
    static String loginCoverPublicUrl(String ext) {
        return BuildConfig.SUPABASE_URL + "/storage/v1/object/public/" + LOGIN_COVER_BUCKET + "/" + LOGIN_COVER_PREFIX + "." + ext;
    }

    /** Current uploaded cover (public URL, no session needed) or null = default factory photo. Background thread. */
    static byte[] loginCoverBytes() {
        for (String ext : LOGIN_COVER_EXTENSIONS) {
            byte[] b = fetchPublic(loginCoverPublicUrl(ext) + "?t=" + System.currentTimeMillis() / 60000L);
            if (b != null) return b;
        }
        return null;
    }

    static byte[] fetchPublic(String url) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(url).openConnection();
            c.setConnectTimeout(6000);
            c.setReadTimeout(10000);
            if (c.getResponseCode() != 200) return null;
            try (InputStream in = c.getInputStream(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] buf = new byte[16384]; int n;
                while ((n = in.read(buf)) > 0) { out.write(buf, 0, n); if (out.size() > LOGIN_COVER_MAX_BYTES) return null; }
                return out.size() == 0 ? null : out.toByteArray();
            }
        } catch (Exception e) {
            return null;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    /** licence_company.upload_login_cover: store login/cover.{ext} (upsert, cache 60 s) and remove the other format. */
    static String uploadLoginCover(Api api, Attachments.FileData f) throws Exception {
        if (!isDeveloper()) throw new Api.ApiException(403, "Only the STAWN developer login can change the login cover photo.");
        if (f == null || f.data == null || f.data.length == 0) throw new Api.ApiException(422, "The selected photo is empty.");
        if (f.data.length > LOGIN_COVER_MAX_BYTES) throw new Api.ApiException(422, "Use a cover photo smaller than 5 MB (JPG or PNG).");
        String mime = f.mime == null ? "" : f.mime.toLowerCase(Locale.ROOT);
        String name = f.name == null ? "" : f.name.toLowerCase(Locale.ROOT);
        String ext;
        if (mime.endsWith("png") || name.endsWith(".png")) ext = "png";
        else if (mime.endsWith("jpeg") || mime.endsWith("jpg") || name.endsWith(".jpg") || name.endsWith(".jpeg")) ext = "jpg";
        else throw new Api.ApiException(422, "Use a JPG or PNG photo for the login cover.");
        String path = LOGIN_COVER_PREFIX + "." + ext;
        api.uploadTo(LOGIN_COVER_BUCKET, path, f.data, "png".equals(ext) ? "image/png" : "image/jpeg", true, "60");
        for (String e : LOGIN_COVER_EXTENSIONS) if (!e.equals(ext)) api.removeFrom(LOGIN_COVER_BUCKET, LOGIN_COVER_PREFIX + "." + e);
        return path;
    }

    /** licence_company.reset_login_cover: remove the uploaded cover -> the default factory photo shows again. */
    static void resetLoginCover(Api api) throws Exception {
        if (!isDeveloper()) throw new Api.ApiException(403, "Only the STAWN developer login can change the login cover photo.");
        for (String e : LOGIN_COVER_EXTENSIONS) api.removeFrom(LOGIN_COVER_BUCKET, LOGIN_COVER_PREFIX + "." + e);
    }

    // ------------------------------------------------------------------ images (company logo / employee photos) with a small cache
    private static final Map<String, Bitmap> IMAGES = new HashMap<>();

    static synchronized void clearImages() { IMAGES.clear(); }

    /** quality-documents object as a thumbnail (null when missing / not visible). Background thread. */
    static Bitmap image(Api api, String path, int maxSide) {
        if (path == null || path.trim().isEmpty()) return null;
        String key = path + "@" + maxSide;
        synchronized (LicService.class) { if (IMAGES.containsKey(key)) return IMAGES.get(key); }
        Bitmap b = null;
        try {
            byte[] data = api.download(path);
            if (data != null && data.length > 0) b = Photos.thumbnail(data, maxSide);
        } catch (Exception ignored) { }
        synchronized (LicService.class) { IMAGES.put(key, b); }
        return b;
    }

    /** ui.company_initials: "Four Star Industries Private Limited" -> "FSI" (legal suffixes ignored). */
    static String initials(String name, int max) {
        java.util.Set<String> skip = new java.util.HashSet<>(java.util.Arrays.asList("private", "pvt", "pvt.", "limited", "ltd", "ltd.", "llp", "inc", "inc.", "the", "and", "&", "co", "co.", "company"));
        StringBuilder b = new StringBuilder();
        for (String w : (name == null ? "" : name).trim().split("\\s+")) {
            if (w.isEmpty() || skip.contains(w.toLowerCase(Locale.ROOT))) continue;
            char c = w.charAt(0);
            if (Character.isLetterOrDigit(c)) b.append(Character.toUpperCase(c));
            if (b.length() >= max) break;
        }
        return b.toString();
    }
}
