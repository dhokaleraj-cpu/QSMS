package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.UUID;

/**
 * Photos and documents in Supabase Storage (bucket quality-documents) + document_attachments rows,
 * with exactly the object paths the website uses (core/attachments.py, InspectionService.upload_attachment).
 */
public final class Attachments {
    private Attachments() { }

    /** A picked / captured file. */
    public static final class FileData {
        public final byte[] data; public final String name; public final String mime;
        public FileData(byte[] data, String name, String mime) { this.data = data; this.name = name; this.mime = mime; }
        public String ext() {
            int i = name.lastIndexOf('.');
            return i >= 0 ? name.substring(i).toLowerCase(Locale.ROOT) : (mime != null && mime.contains("png") ? ".png" : mime != null && mime.contains("pdf") ? ".pdf" : ".jpg");
        }
        public String stem() {
            int i = name.lastIndexOf('.');
            return i > 0 ? name.substring(0, i) : name;
        }
    }

    static String safe(String v) {
        String s = (v == null ? "" : v).toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]+", "_");
        s = s.replaceAll("^_+|_+$", "");
        return s.isEmpty() ? "file" : s;
    }

    static String hex(byte[] b) {
        StringBuilder s = new StringBuilder();
        for (byte x : b) s.append(String.format(Locale.ROOT, "%02x", x));
        return s.toString();
    }

    static String sha256(byte[] data) throws Exception { return hex(MessageDigest.getInstance("SHA-256").digest(data)); }
    static String sha1(String text) throws Exception { return hex(MessageDigest.getInstance("SHA-1").digest(text.getBytes(StandardCharsets.UTF_8))); }

    private static JSONObject row(String entityType, String entityId, String docType, FileData f, String path) throws Exception {
        JSONObject r = new JSONObject();
        r.put("entity_type", entityType);
        r.put("entity_id", entityId);
        r.put("document_type", docType);
        r.put("file_name", f.name);
        r.put("object_path", path);
        r.put("mime_type", f.mime == null ? "application/octet-stream" : f.mime);
        r.put("size_bytes", f.data.length);
        r.put("checksum", sha256(f.data));
        r.put("status", "ACTIVE");
        return r;
    }

    private static void saveRow(Api api, JSONObject r) throws Exception {
        api.upsertBy("document_attachments", r, "entity_type", "entity_id", "document_type");
    }

    private static void linkParent(Api api, String parentTable, String parentField, String entityId, String path) {
        if (parentTable == null || parentField == null) return;
        try { api.update(parentTable, entityId, new JSONObject().put(parentField, path)); } catch (Exception ignored) { }
    }

    /** Fixed slot (AttachmentService.upload): {tenant}/{folder}/{entity}/{doctype}, replaced on re-upload. */
    public static String uploadSlot(Api api, String entityType, String entityId, String folder, String docType, FileData f,
                                    String parentTable, String parentField) throws Exception {
        String path = api.tenantId + "/" + safe(folder) + "/" + entityId + "/" + safe(docType);
        api.upload(path, f.data, f.mime, true);
        saveRow(api, row(entityType, entityId, docType, f, path));
        linkParent(api, parentTable, parentField, entityId, path);
        return path;
    }

    /** Several files with a title (AttachmentService.upload_additional, e.g. complaint photos). */
    public static String uploadAdditional(Api api, String entityType, String entityId, String folder, String docType, FileData f, String title) throws Exception {
        String path = api.tenantId + "/" + safe(folder) + "/" + entityId + "/" + safe(docType) + "/"
            + UUID.randomUUID().toString().replace("-", "").substring(0, 12) + "_" + safe(f.stem()) + f.ext();
        api.upload(path, f.data, f.mime, false);
        JSONObject r = row(entityType, entityId, docType, f, path);
        r.put("document_title", title);
        try {
            api.insert("document_attachments", r);
        } catch (Exception e) {
            api.removeObject(path);
            throw e;
        }
        return path;
    }

    /** Report copies / microstructure photos (InspectionService.upload_attachment path). */
    public static String uploadReport(Api api, String entityType, String entityId, String docType, FileData f,
                                      String parentTable, String parentField) throws Exception {
        String path = api.tenantId + "/" + entityType.toLowerCase(Locale.ROOT).replace('_', '-') + "/" + entityId + "/"
            + docType.toLowerCase(Locale.ROOT) + "_" + sha1(f.name).substring(0, 8) + f.ext();
        api.upload(path, f.data, f.mime, true);
        saveRow(api, row(entityType, entityId, docType, f, path));
        linkParent(api, parentTable, parentField, entityId, path);
        return path;
    }

    public static JSONArray list(Api api, String entityType, String entityId) throws Exception {
        return api.rows("document_attachments?select=id,document_type,document_title,file_name,object_path,mime_type,size_bytes,created_at"
            + "&entity_type=eq." + entityType + "&entity_id=eq." + entityId + "&status=eq.ACTIVE&order=created_at.asc");
    }

    /** Short-lived link to open a document in the phone's viewer / browser. */
    public static String signedUrl(Api api, String path) throws Exception {
        return api.signedUrl(path, 900);
    }
}
