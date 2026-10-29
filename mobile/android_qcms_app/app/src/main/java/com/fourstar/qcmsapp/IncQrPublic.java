package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * R40 · Public RMTC QR (shared contract with the website core/qr_codes.RMTCQRService and the public Edge Function
 * qcms-rmtc-certificate):
 *  - QR text = PUBLIC_BASE + "?t=" + token; token = 32 chars [A-Za-z0-9] from java.security.SecureRandom, one active
 *    (revoked = false) row per RMTC in public.rmtc_qr_tokens, created with a normal insert (tenant_id filled by the
 *    column default / RLS insert policy). No login is needed to open the link; the random token is the only key.
 *  - Certificate = the app's customer-safe RMTC print PDF (RptReports.rmtc - no customer name / code / PO / customer
 *    part no) stored at <tenant>/rmtc_certificates/<rmtc_id>/RMTC_<no>.pdf in bucket quality-documents; its path is
 *    written to rmtc_qr_tokens.certificate_path + certificate_refreshed_at.
 *  - &f=zip = all documents as one ZIP, &f=pdf = all documents as one PDF, &d=<attachment id | certificate> = one file.
 *  - Falls back to the old login-protected website link only when the token cannot be created (note shown).
 * No elevated key; only the signed-in user's own rights (RLS) are used.
 */
final class IncQrPublic {
    private IncQrPublic() { }

    static final String PROJECT_URL = "https://xxrxopzxzyjnzumrwuwy.supabase.co";
    static final String FUNCTION_SLUG = "qcms-rmtc-certificate";
    static final String PUBLIC_BASE = PROJECT_URL + "/functions/v1/" + FUNCTION_SLUG;
    static final String TABLE = "rmtc_qr_tokens";
    static final String CERT_FOLDER = "rmtc_certificates";
    static final int TOKEN_LENGTH = 32;
    private static final String ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    private static final SecureRandom RANDOM = new SecureRandom();

    // ================================================================== token + links
    /** new_token: 32 chars [A-Za-z0-9], cryptographically random. */
    static String newToken() {
        StringBuilder sb = new StringBuilder(TOKEN_LENGTH);
        for (int i = 0; i < TOKEN_LENGTH; i++) sb.append(ALPHABET.charAt(RANDOM.nextInt(ALPHABET.length())));
        return sb.toString();
    }

    static boolean validToken(String t) { return t != null && t.matches("[A-Za-z0-9]{32}"); }

    static String publicUrl(String token) { return PUBLIC_BASE + "?t=" + token; }
    static String zipUrl(String token) { return publicUrl(token) + "&f=zip"; }
    static String pdfUrl(String token) { return publicUrl(token) + "&f=pdf"; }
    /** One document: attachment uuid or "certificate". */
    static String docUrl(String token, String doc) { return publicUrl(token) + "&d=" + Api.enc(doc); }

    /** Old R38 / R39 login-protected website link (fallback only). */
    static String websiteUrl(JSONObject r) {
        return RptReports.QCMS_WEBSITE + "/rmtc-records?rmtc=" + Api.enc(Lookups.j(r, "rmtc_number")).replace("+", "%20");
    }

    /** Active (not revoked) token row of the RMTC, or null. Read only. */
    static JSONObject activeToken(Api api, String rid) {
        if (rid == null || rid.isEmpty()) return null;
        try {
            JSONArray rows = api.rows(TABLE + "?select=*&rmtc_approval_id=eq." + Api.enc(rid) + "&revoked=eq.false&order=created_at.desc&limit=1");
            JSONObject row = rows.length() > 0 ? rows.getJSONObject(0) : null;
            return row != null && validToken(Lookups.j(row, "token")) ? row : null;
        } catch (Exception e) {
            return null;
        }
    }

    /** Public URL of the active token, "" when none (read only - used by the RMTC print). */
    static String activeUrl(Api api, String rid) {
        JSONObject t = activeToken(api, rid);
        return t == null ? "" : publicUrl(Lookups.j(t, "token"));
    }

    /** ensure_token: existing active row or a new one (normal insert; tenant from the column default). */
    static JSONObject ensureToken(Api api, JSONObject r) throws Exception {
        String rid = Lookups.j(r, "id");
        JSONObject existing = activeToken(api, rid);
        if (existing != null) return existing;
        JSONObject row = new JSONObject()
            .put("rmtc_approval_id", rid)
            .put("token", newToken())
            .put("rmtc_number", Lookups.j(r, "rmtc_number").isEmpty() ? JSONObject.NULL : Lookups.j(r, "rmtc_number"))
            .put("certificate_bucket", Api.BUCKET);
        JSONObject saved = api.insert(TABLE, row);
        if (!validToken(Lookups.j(saved, "token"))) {
            JSONObject again = activeToken(api, rid);
            if (again == null) throw new Api.ApiException(500, "The public QR code could not be created.");
            return again;
        }
        return saved;
    }

    // ================================================================== certificate (customer-safe RMTC print)
    static String certificateName(JSONObject r) { return "RMTC_" + IncQrLabel.safeToken(Lookups.j(r, "rmtc_number")) + ".pdf"; }

    /** <tenant>/rmtc_certificates/<rmtc_id>/RMTC_<no>.pdf - tenant of the token row (= the file's tenant). */
    static String certificatePath(Api api, JSONObject tokenRow, JSONObject r) {
        String tenant = Lookups.j(tokenRow, "tenant_id");
        if (tenant.isEmpty()) tenant = api.tenantId == null ? "" : api.tenantId;
        if (tenant.isEmpty()) tenant = "tenant";
        return tenant + "/" + CERT_FOLDER + "/" + Lookups.j(r, "id") + "/" + certificateName(r);
    }

    /**
     * The approved RMTC print layout (RptReports.rmtc) as PDF. That print has no customer fields (customer name / code /
     * customer PO / customer part no are never read by it) - safe for anyone holding the public QR.
     */
    static byte[] certificatePdf(Api api, String rid) throws Exception {
        return RptPdf.render(RptReports.rmtc(api, rid));
    }

    /** store_certificate: upload (upsert) + certificate_path / certificate_refreshed_at on the token row. */
    static String storeCertificate(Api api, JSONObject r, JSONObject tokenRow) throws Exception {
        String path = certificatePath(api, tokenRow, r);
        api.upload(path, certificatePdf(api, Lookups.j(r, "id")), IncQrLabel.PDF, true);
        String now = java.time.OffsetDateTime.now(java.time.ZoneOffset.UTC).toString();
        if (!Lookups.j(tokenRow, "id").isEmpty()) {
            JSONObject saved = api.update(TABLE, Lookups.j(tokenRow, "id"),
                new JSONObject().put("certificate_path", path).put("certificate_refreshed_at", now).put("updated_at", now));
            tokenRow.put("certificate_path", Lookups.j(saved, "certificate_path").isEmpty() ? path : Lookups.j(saved, "certificate_path"));
            tokenRow.put("certificate_refreshed_at", now);
        }
        return path;
    }

    // ================================================================== ensure (QR panel / label / e-mail / approval)
    static final class Link {
        String url = "";
        String token = "";
        JSONObject row;
        boolean isPublic;
        boolean created;
        String note = "";
    }

    /** Active / new token + certificate when missing. Never throws: falls back to the website link with a note. */
    static Link ensure(Api api, JSONObject r) {
        Link l = new Link();
        try {
            JSONObject before = activeToken(api, Lookups.j(r, "id"));
            l.row = before != null ? before : ensureToken(api, r);
            l.created = before == null;
            l.token = Lookups.j(l.row, "token");
            l.url = publicUrl(l.token);
            l.isPublic = true;
        } catch (Exception e) {
            l.url = websiteUrl(r);
            l.note = "Public QR code could not be created (" + Api.message(e) + "); the QR uses the QCMS website link (login required).";
            return l;
        }
        if (Lookups.j(l.row, "certificate_path").isEmpty()) {
            try {
                storeCertificate(api, r, l.row);
            } catch (Exception e) {
                l.note = "RMTC certificate PDF could not be stored for the public page: " + Api.message(e);
            }
        }
        return l;
    }

    /** Revoke the active code (old QR stops working) and create a new one with a fresh certificate. */
    static Link revoke(Api api, JSONObject r) throws Exception {
        JSONObject cur = activeToken(api, Lookups.j(r, "id"));
        if (cur != null) {
            String now = java.time.OffsetDateTime.now(java.time.ZoneOffset.UTC).toString();
            api.update(TABLE, Lookups.j(cur, "id"), new JSONObject().put("revoked", true).put("revoked_at", now).put("updated_at", now));
        }
        Link l = ensure(api, r);
        if (!l.isPublic) throw new Api.ApiException(500, l.note);
        return l;
    }

    /** Refresh certificate: regenerate the print PDF for the active token (creates the token when missing). */
    static Link refreshCertificate(Api api, JSONObject r) throws Exception {
        Link l = ensure(api, r);
        if (!l.isPublic) throw new Api.ApiException(500, l.note);
        storeCertificate(api, r, l.row);
        l.note = "";
        return l;
    }

    // ================================================================== documents (same rules as the public page)
    static final class Doc {
        String id, name, path, mime, title;
        long size;
        boolean certificate;
    }

    /** Certificate first, then every ACTIVE RMTC attachment (not the QR label itself, not customer-only entities). */
    static List<Doc> documents(Api api, String rid, JSONObject tokenRow, JSONObject r) {
        List<Doc> out = new ArrayList<>();
        if (tokenRow != null && !Lookups.j(tokenRow, "certificate_path").isEmpty()) {
            Doc d = new Doc();
            d.id = "certificate";
            d.certificate = true;
            d.path = Lookups.j(tokenRow, "certificate_path");
            d.name = r == null ? "RMTC_certificate.pdf" : certificateName(r);
            d.mime = IncQrLabel.PDF;
            d.title = "Approved RMTC certificate (QCMS print)";
            out.add(d);
        }
        try {
            JSONArray rows = api.rows("document_attachments?select=id,document_type,document_title,file_name,object_path,mime_type,size_bytes,status,created_at"
                + "&entity_type=eq." + IncQrLabel.ENTITY_TYPE + "&entity_id=eq." + Api.enc(rid) + "&status=eq.ACTIVE"
                + "&document_type=neq." + IncQrLabel.DOCUMENT_TYPE + "&order=created_at.asc&limit=200");
            for (int i = 0; i < rows.length(); i++) {
                JSONObject a = rows.getJSONObject(i);
                if (Lookups.j(a, "object_path").isEmpty()) continue;
                Doc d = new Doc();
                d.id = Lookups.j(a, "id");
                d.path = Lookups.j(a, "object_path");
                d.name = IncCalc.firstText(Lookups.j(a, "file_name"), d.path.substring(d.path.lastIndexOf('/') + 1));
                d.mime = IncCalc.firstText(Lookups.j(a, "mime_type"), "application/octet-stream");
                d.title = IncCalc.firstText(Lookups.j(a, "document_title"), Ui.pretty(Lookups.j(a, "document_type")));
                d.size = a.optLong("size_bytes", 0);
                out.add(d);
            }
        } catch (Exception ignored) { }
        return out;
    }

    // ================================================================== bulk
    static String approvedFilter() {
        return "status=in.(APPROVED,PARTIALLY_APPROVED)&disposition=in.(ACCEPTED,ACCEPTED_UNDER_RESERVE)";
    }

    /** Bulk: create a public QR (token + certificate) for every approved RMTC without an active one. Returns {done, failed}. */
    static int[] bulkCreate(Api api) throws Exception {
        JSONArray rmtcs = api.rows("rmtc_approvals?select=*&" + approvedFilter() + "&order=decision_at.desc.nullslast&limit=2000");
        java.util.Set<String> have = new java.util.HashSet<>();
        JSONArray tokens = api.rows(TABLE + "?select=rmtc_approval_id&revoked=eq.false&limit=10000");
        for (int i = 0; i < tokens.length(); i++) have.add(Lookups.j(tokens.optJSONObject(i), "rmtc_approval_id"));
        int done = 0, failed = 0;
        for (int i = 0; i < rmtcs.length(); i++) {
            JSONObject r = rmtcs.getJSONObject(i);
            if (have.contains(Lookups.j(r, "id")) || !IncQrLabel.approved(r)) continue;
            Link l = ensure(api, r);
            if (l.isPublic && l.note.isEmpty()) done++;
            else failed++;
        }
        return new int[]{done, failed};
    }

    static String lower(String s) { return s == null ? "" : s.toLowerCase(Locale.ROOT); }
}
