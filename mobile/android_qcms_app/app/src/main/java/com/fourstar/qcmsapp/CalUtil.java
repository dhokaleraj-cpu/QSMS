package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.util.Locale;

/** Small helpers shared by the calibration / standard room / complaint screens. */
final class CalUtil {
    private CalUtil() { }

    /** Trimmed text or JSON null (the website's `value.strip() or None`). */
    static Object v(String s) {
        return s == null || s.trim().isEmpty() ? JSONObject.NULL : s.trim();
    }

    /** Id / date or JSON null. */
    static Object id(String s) { return v(s); }

    static String plusDays(String iso, long days) {
        try { return LocalDate.parse(iso.substring(0, 10)).plusDays(days).toString(); }
        catch (Exception e) { return LocalDate.now().plusDays(days).toString(); }
    }

    /** Positive integer column, else the default (Python `int(x or default)`). */
    static int intOr(JSONObject r, String key, int def) {
        if (r == null) return def;
        String s = Lookups.j(r, key);
        try {
            int n = (int) Math.round(Double.parseDouble(s));
            return n != 0 ? n : def;
        } catch (Exception e) {
            return def;
        }
    }

    static double dbl(Double d) { return d == null ? 0.0 : d; }

    /** MasterService._normalized_key_value: trim, collapse spaces, ignore case. */
    static String norm(String s) {
        return s == null ? "" : s.trim().replaceAll("\\s+", " ").toLowerCase(Locale.ROOT);
    }

    static boolean isTrue(JSONObject r, String key) {
        return r != null && "true".equalsIgnoreCase(Lookups.j(r, key));
    }

    /** Small explanatory card. */
    static LinearLayout infoCard(MainActivity a, String title, String body) {
        LinearLayout card = Ui.card(a);
        if (title != null && !title.isEmpty()) card.addView(Ui.text(a, title, 13.5f, Ui.TEXT, true));
        if (body != null && !body.isEmpty()) {
            TextView t = Ui.text(a, body, 12, Ui.MUTED, false);
            t.setPadding(0, Ui.dp(a, 3), 0, 0);
            card.addView(t);
        }
        return card;
    }

    /**
     * Fixed attachment slots (AttachmentService.upload): pick slot → file → upload. Replacing an existing file
     * asks for the password again, like the website.
     */
    static void uploadFixedSlot(MainActivity a, Api api, String entity, String entityId, String folder,
                                String[] slots, String[] labels, Runnable done) {
        new AlertDialog.Builder(a).setTitle("Controlled document").setItems(labels, (d, which) -> {
            String slot = slots[which];
            boolean imagesOnly = slot.contains("PHOTO");
            a.pickFile(labels[which], imagesOnly, file -> Api.async(() -> {
                JSONArray rows = api.rows("document_attachments?select=id&entity_type=eq." + entity + "&entity_id=eq." + entityId
                    + "&document_type=eq." + slot + "&status=eq.ACTIVE&limit=1");
                return rows.length() > 0;
            }, (exists, err) -> {
                Runnable upload = () -> {
                    a.toast("Uploading " + file.name + " (" + (file.data.length / 1024) + " KB)…");
                    Api.async(() -> Attachments.uploadSlot(api, entity, entityId, folder, slot, file, null, null), (path, e2) -> {
                        if (e2 != null) { a.toast("Upload failed: " + Api.message(e2)); return; }
                        a.toast(labels[which] + " uploaded.");
                        if (done != null) done.run();
                    });
                };
                if (err == null && Boolean.TRUE.equals(exists)) {
                    a.confirmPassword("Replace " + labels[which] + " - confirm with your password", upload);
                } else {
                    upload.run();
                }
            }));
        }).setNegativeButton("Back", null).show();
    }
}
