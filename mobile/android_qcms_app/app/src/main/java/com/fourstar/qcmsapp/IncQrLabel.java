package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.graphics.pdf.PdfDocument;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.security.MessageDigest;
import java.text.DecimalFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * R39 · Approved RMTC material-location QR (website core/rmtc_qr.py, R38/R39):
 *  - QR content = login-protected website link (QR_CONTENT "APP"): <website>/rmtc-records?rmtc=<RMTC number>
 *    (RptReports.rmtcQrUrl); matrix from the pure-Java encoder IncQrCode (same choices as the website encoder).
 *  - Caption lines = label_lines (RMTC no, heat, grade, size / section, parts, qty, supplier, approval date[, location]).
 *  - Downloads: QR PNG (QR + caption), QR JPEG (white background, RGB), QR PDF (A6 page, QR + caption) and the
 *    100 x 60 mm print label PDF. File names RMTC_<no>_QR.png / .jpg / .pdf, RMTC_<no>_QR_Label.pdf.
 *  - Stored label = document_attachments (entity RMTC, document_type RMTC_QR_LABEL, bucket quality-documents).
 *  - onApproved(): store the label PNG + queue the RMTC_APPROVED_QR e-mail to every active Quality department employee
 *    (outbox row with attachment_manifest = label PNG + generated RMTC record PDF) and dispatch through qcms-send-email,
 *    exactly as RMTCQRLabelService.on_rmtc_approved does on the website.
 */
final class IncQrLabel {
    private IncQrLabel() { }

    static final String EVENT_KEY = "RMTC_APPROVED_QR";
    static final String DOCUMENT_TYPE = "RMTC_QR_LABEL";
    static final String ENTITY_TYPE = "RMTC";
    static final String MODULE_KEY = "RMTC_ENTRY";
    static final float LABEL_WIDTH_MM = 100f, LABEL_HEIGHT_MM = 60f, A6_WIDTH_MM = 105f, A6_HEIGHT_MM = 148f;
    static final String PNG = "image/png", JPEG = "image/jpeg", PDF = "application/pdf";
    private static final Set<String> QUALITY_KEYS = new HashSet<>(Arrays.asList("quality", "qa", "qc", "qad", "qcd", "qualityassurance",
        "qualitycontrol", "qualitydepartment", "qaqc", "qcqa", "qualityqa", "qualityqc", "quality&assurance", "sqa", "supplierquality"));

    // ================================================================== data
    static boolean approved(JSONObject r) {
        String st = Lookups.j(r, "status").toUpperCase(Locale.ROOT), disp = Lookups.j(r, "disposition").toUpperCase(Locale.ROOT);
        return (st.equals("APPROVED") || st.equals("PARTIALLY_APPROVED")) && (disp.equals("ACCEPTED") || disp.equals("ACCEPTED_UNDER_RESERVE"));
    }

    /** qr_codes.safe_file_token */
    static String safeToken(String value) {
        String v = value == null || value.trim().isEmpty() ? "RMTC" : value;
        String t = v.replaceAll("[^A-Za-z0-9_.-]+", "_").replaceAll("^_+|_+$", "");
        return t.isEmpty() ? "RMTC" : t;
    }

    static String fileStem(JSONObject r) { return "RMTC_" + safeToken(Lookups.j(r, "rmtc_number")); }

    static final class Assets {
        String url = "";
        List<String> lines = new ArrayList<>();
        String stem = "RMTC";
        String number = "";
        boolean[][] matrix;
    }

    /** _date_text: dd-MM-yyyy */
    static String dateText(String v) {
        String t = v == null ? "" : v.trim();
        if (t.isEmpty()) return "-";
        if (t.length() >= 10 && t.charAt(4) == '-' && t.charAt(7) == '-') return t.substring(8, 10) + "-" + t.substring(5, 7) + "-" + t.substring(0, 4);
        return t.length() > 10 ? t.substring(0, 10) : t;
    }

    /** qty_text: "1,234.5 kg" */
    static String qtyText(Object v) {
        if (v == null || v == JSONObject.NULL || String.valueOf(v).isEmpty()) return "-";
        try {
            double d = Double.parseDouble(String.valueOf(v));
            String s = new DecimalFormat("#,##0.00", java.text.DecimalFormatSymbols.getInstance(Locale.ENGLISH)).format(new BigDecimal(d).setScale(2, RoundingMode.HALF_EVEN));
            s = s.replaceAll("0+$", "").replaceAll("\\.$", "");
            return s + " kg";
        } catch (Exception e) {
            return String.valueOf(v);
        }
    }

    /** label_lines */
    static List<String> labelLines(JSONObject r, String grade, String supplier, List<String> parts) {
        String heat = Lookups.j(r, "heat_number");
        if (heat.isEmpty()) heat = "-";
        if (!Lookups.j(r, "heat_code").isEmpty()) heat += " (" + Lookups.j(r, "heat_code") + ")";
        String section = Lookups.j(r, "rm_section");
        String location = IncCalc.firstText(Lookups.j(r, "storage_location"), IncCalc.firstText(Lookups.j(r, "material_location"), Lookups.j(r, "location")));
        List<String> p = new ArrayList<>();
        if (parts != null) for (String s : parts) if (s != null && !s.isEmpty()) p.add(s);
        List<String> out = new ArrayList<>();
        out.add("RMTC " + (Lookups.j(r, "rmtc_number").isEmpty() ? "-" : Lookups.j(r, "rmtc_number")));
        out.add("Heat: " + heat);
        out.add("Grade: " + (grade == null || grade.isEmpty() ? "-" : grade));
        out.add("Size / Section: " + (section.isEmpty() ? "-" : section));
        out.add("Parts: " + (p.isEmpty() ? "-" : String.join(", ", p)));
        out.add("Qty: " + qtyText(r.opt("certificate_quantity")));
        out.add("Supplier: " + (supplier == null || supplier.isEmpty() ? "-" : supplier));
        out.add("Approved: " + dateText(IncCalc.firstText(Lookups.j(r, "decision_at"), Lookups.j(r, "approved_at"))));
        if (!location.trim().isEmpty()) out.add("Location: " + location.trim());
        return out;
    }

    /** Background: grade / supplier names + covered part numbers -> QR assets. */
    static Assets assets(Api api, JSONObject r) throws Exception {
        Assets s = new Assets();
        s.url = RptReports.rmtcQrUrl(api, Lookups.j(r, "id"), r);
        if (s.url.isEmpty()) s.url = RptReports.QCMS_WEBSITE + "/rmtc-records?rmtc=" + Api.enc(Lookups.j(r, "rmtc_number")).replace("+", "%20");
        String grade = "", supplier = "";
        try {
            JSONObject g = IncCalc.one(api, "material_grades?select=grade_code,grade_name&id=eq." + Api.enc(Lookups.j(r, "material_grade_id")) + "&limit=1");
            if (g != null) grade = IncCalc.firstText(Lookups.j(g, "grade_code"), Lookups.j(g, "grade_name"));
        } catch (Exception ignored) { }
        try {
            JSONObject p = IncCalc.one(api, "parties?select=party_name&id=eq." + Api.enc(Lookups.j(r, "supplier_id")) + "&limit=1");
            if (p != null) supplier = Lookups.j(p, "party_name");
        } catch (Exception ignored) { }
        List<String> ids = new ArrayList<>();
        if (!Lookups.j(r, "part_id").isEmpty()) ids.add(Lookups.j(r, "part_id"));
        try {
            JSONArray cov = api.rows("rmtc_part_approvals?select=part_id&rmtc_approval_id=eq." + Api.enc(Lookups.j(r, "id")) + "&order=created_at.asc&limit=100");
            for (int i = 0; i < cov.length(); i++) {
                String pid = Lookups.j(cov.optJSONObject(i), "part_id");
                if (!pid.isEmpty() && !ids.contains(pid)) ids.add(pid);
            }
        } catch (Exception ignored) { }
        List<String> numbers = new ArrayList<>();
        if (!ids.isEmpty()) {
            LinkedHashMap<String, String> byId = new LinkedHashMap<>();
            try {
                JSONArray ps = api.rows("parts?select=id,part_number&id=in.(" + String.join(",", ids) + ")&limit=100");
                for (int i = 0; i < ps.length(); i++) byId.put(Lookups.j(ps.optJSONObject(i), "id"), Lookups.j(ps.optJSONObject(i), "part_number").trim());
            } catch (Exception ignored) { }
            for (String id : ids) {
                String n = byId.get(id);
                if (n != null && !n.isEmpty() && !numbers.contains(n)) numbers.add(n);
            }
        }
        s.lines = labelLines(r, grade, supplier, numbers);
        s.stem = fileStem(r);
        s.number = Lookups.j(r, "rmtc_number");
        s.matrix = IncQrCode.encode(s.url);
        return s;
    }

    // ================================================================== renderers
    private static Paint paint(float size, boolean bold) {
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        p.setColor(Color.BLACK);
        p.setTextSize(size);
        p.setTypeface(bold ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
        return p;
    }

    private static void drawQr(Canvas c, boolean[][] m, float x, float y, float size) {
        int n = m.length + 8;  // 4-module quiet zone each side
        float mod = size / n;
        Paint black = new Paint();
        black.setColor(Color.BLACK);
        black.setStyle(Paint.Style.FILL);
        for (int r = 0; r < m.length; r++)
            for (int col = 0; col < m.length; col++)
                if (m[r][col]) c.drawRect(x + (col + 4) * mod, y + (r + 4) * mod, x + (col + 5) * mod + 0.01f, y + (r + 5) * mod + 0.01f, black);
    }

    private static String fit(String s, float width, Paint p) {
        String v = s == null ? "" : s;
        while (!v.isEmpty() && p.measureText(v) > width) v = v.substring(0, v.length() - 1);
        return v;
    }

    /** label_png_bytes layout: QR (scale 10, border 4) centred, caption lines underneath, 2 px frame; white background. */
    static Bitmap labelBitmap(Assets s) {
        int scale = 10;
        int qr = (s.matrix.length + 8) * scale;
        int lineH = 31;
        int width = Math.max(qr, 560);
        int height = qr + lineH * s.lines.size() + 20;
        Bitmap b = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(b);
        c.drawColor(Color.WHITE);
        drawQr(c, s.matrix, (width - qr) / 2f, 0, qr);
        float y = qr;
        for (int i = 0; i < s.lines.size(); i++) {
            Paint p = paint(i == 0 ? 24 : 21, i == 0);
            String v = s.lines.get(i);
            if (v.length() > 64) v = v.substring(0, 64);
            v = fit(v, width - 8, p);
            float w = p.measureText(v);
            c.drawText(v, Math.max((width - w) / 2f, 4), y + 24, p);
            y += lineH;
        }
        Paint frame = new Paint();
        frame.setColor(Color.BLACK);
        frame.setStyle(Paint.Style.STROKE);
        frame.setStrokeWidth(2);
        c.drawRect(1, 1, width - 2, height - 2, frame);
        return b;
    }

    private static byte[] compress(Bitmap b, Bitmap.CompressFormat f, int q) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        b.compress(f, q, out);
        return out.toByteArray();
    }

    /** QR + caption as PNG. */
    static byte[] png(Assets s) {
        Bitmap b = labelBitmap(s);
        try { return compress(b, Bitmap.CompressFormat.PNG, 100); } finally { b.recycle(); }
    }

    /** QR + caption as JPEG (white background, RGB - qr_jpeg_bytes). */
    static byte[] jpeg(Assets s) {
        Bitmap b = labelBitmap(s);
        try { return compress(b, Bitmap.CompressFormat.JPEG, 95); } finally { b.recycle(); }
    }

    private static float pt(float mm) { return mm * 72f / 25.4f; }

    private static byte[] pdfBytes(PdfDocument doc) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        try { doc.writeTo(out); } finally { doc.close(); }
        return out.toByteArray();
    }

    /** qr_pdf_bytes: one A6 portrait page, large QR centred at the top, caption underneath. */
    static byte[] pdf(Assets s) throws Exception {
        float w = pt(A6_WIDTH_MM), h = pt(A6_HEIGHT_MM), pad = pt(6);
        PdfDocument doc = new PdfDocument();
        PdfDocument.Page page = doc.startPage(new PdfDocument.PageInfo.Builder(Math.round(w), Math.round(h), 1).create());
        Canvas c = page.getCanvas();
        float qr = Math.min(w - 2 * pad, h * 0.55f);
        drawQr(c, s.matrix, (w - qr) / 2f, pad, qr);
        Paint frame = new Paint();
        frame.setColor(Color.BLACK);
        frame.setStyle(Paint.Style.STROKE);
        frame.setStrokeWidth(0.7f);
        c.drawRect(pt(2), pt(2), w - pt(2), h - pt(2), frame);
        float y = pad + qr + pt(6);
        for (int i = 0; i < s.lines.size(); i++) {
            float size = i == 0 ? 12 : 9;
            Paint p = paint(size, i == 0);
            String v = fit(s.lines.get(i), w - 2 * pad, p);
            c.drawText(v, (w - p.measureText(v)) / 2f, y, p);
            y += size + 4;
            if (y > h - pad - pt(6)) break;
        }
        Paint note = paint(6.5f, false);
        String n = "Scan with a phone: QCMS login opens this record.";
        c.drawText(n, (w - note.measureText(n)) / 2f, h - pad, note);
        doc.finishPage(page);
        return pdfBytes(doc);
    }

    /** label_pdf_bytes: 100 x 60 mm sticker - QR left, RMTC text right, "Location" write-in box at the bottom. */
    static byte[] labelPdf(Assets s) throws Exception {
        float w = pt(LABEL_WIDTH_MM), h = pt(LABEL_HEIGHT_MM), pad = pt(3), locH = pt(9);
        PdfDocument doc = new PdfDocument();
        PdfDocument.Page page = doc.startPage(new PdfDocument.PageInfo.Builder(Math.round(w), Math.round(h), 1).create());
        Canvas c = page.getCanvas();
        float qr = Math.min(h - 2 * pad - locH - pt(1.5f), w * 0.45f);
        drawQr(c, s.matrix, pad, pad, qr);
        Paint frame = new Paint();
        frame.setColor(Color.BLACK);
        frame.setStyle(Paint.Style.STROKE);
        frame.setStrokeWidth(0.7f);
        c.drawRect(pt(1), pt(1), w - pt(1), h - pt(1), frame);
        float x = pad + qr + pt(2), avail = w - x - pad, y = pad + pt(3.4f);
        String location = "";
        int index = 0;
        for (String line : s.lines) {
            if (line.startsWith("Location:")) { location = line.substring(9).trim(); continue; }
            float size = index == 0 ? 9.5f : 7.2f;
            Paint p = paint(size, index == 0);
            c.drawText(fit(line, avail, p), x, y, p);
            y += size + 2.4f;
            index++;
        }
        frame.setStrokeWidth(0.5f);
        c.drawRect(pad, h - pad - locH, w - pad, h - pad, frame);
        Paint lb = paint(8, true);
        c.drawText("Location:", pad + pt(1.5f), h - pad - locH + pt(3.6f), lb);
        if (!location.isEmpty()) c.drawText(location.length() > 60 ? location.substring(0, 60) : location, pad + pt(17), h - pad - locH + pt(3.6f), paint(8, false));
        c.drawText("Scan with a phone: QCMS login opens this RMTC and its certificate downloads.", pad + pt(1.5f), h - pad - pt(1.4f), paint(5.4f, false));
        doc.finishPage(page);
        return pdfBytes(doc);
    }

    // ================================================================== attachment + e-mail (RMTCQRLabelService)
    static JSONObject storedLabel(Api api, String rid) {
        try {
            JSONArray r = api.rows("document_attachments?select=*&entity_type=eq." + ENTITY_TYPE + "&entity_id=eq." + Api.enc(rid)
                + "&document_type=eq." + DOCUMENT_TYPE + "&status=eq.ACTIVE&order=created_at.desc&limit=1");
            return r.length() > 0 ? r.getJSONObject(0) : null;
        } catch (Exception e) {
            return null;
        }
    }

    static String sha256(byte[] data) {
        try {
            StringBuilder sb = new StringBuilder();
            for (byte b : MessageDigest.getInstance("SHA-256").digest(data)) sb.append(String.format(Locale.ROOT, "%02x", b));
            return sb.toString();
        } catch (Exception e) {
            return "";
        }
    }

    /** store_label: upload <tenant>/rmtc/<id>/<stem>_QR_Label.png (upsert) and insert / update the attachment row. */
    static JSONObject storeLabel(Api api, JSONObject r, byte[] png, String stem) throws Exception {
        String rid = Lookups.j(r, "id");
        String fileName = stem + "_QR_Label.png";
        String path = (api.tenantId == null || api.tenantId.isEmpty() ? "tenant" : api.tenantId) + "/rmtc/" + rid + "/" + fileName;
        api.upload(path, png, PNG, true);
        JSONObject payload = new JSONObject().put("entity_type", ENTITY_TYPE).put("entity_id", rid).put("document_type", DOCUMENT_TYPE)
            .put("file_name", fileName).put("object_path", path).put("mime_type", PNG).put("size_bytes", png.length)
            .put("checksum", sha256(png)).put("status", "ACTIVE").put("document_title", ("QR label · RMTC " + Lookups.j(r, "rmtc_number")).trim());
        JSONObject existing = null;
        try {
            JSONArray ex = api.rows("document_attachments?select=id&entity_type=eq." + ENTITY_TYPE + "&entity_id=eq." + Api.enc(rid) + "&document_type=eq." + DOCUMENT_TYPE + "&limit=1");
            if (ex.length() > 0) existing = ex.getJSONObject(0);
        } catch (Exception ignored) { }
        JSONObject row = existing != null ? api.update("document_attachments", Lookups.j(existing, "id"), payload) : api.insert("document_attachments", payload);
        return row == null || row.length() == 0 ? payload : row;
    }

    static boolean isQualityDepartment(String value) {
        String raw = value == null ? "" : value.toLowerCase(Locale.ROOT);
        String key = raw.replaceAll("[^a-z0-9&]+", "");
        if (QUALITY_KEYS.contains(key) || key.contains("quality")) return true;
        for (String t : raw.split("[^a-z0-9]+")) if (t.equals("qa") || t.equals("qc")) return true;
        return false;
    }

    /** quality_recipients: active employees of the Quality department with an e-mail (unique, by first name). */
    static List<String[]> qualityRecipients(Api api) throws Exception {
        List<String[]> out = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        for (JSONObject e : SndMail.employees(api)) {
            String email = Lookups.j(e, "email").trim();
            if (email.isEmpty() || !email.contains("@") || !isQualityDepartment(Lookups.j(e, "department"))) continue;
            if (!seen.add(email.toLowerCase(Locale.ROOT))) continue;
            out.add(new String[]{email, SndMail.employeeName(e)});
        }
        return out;
    }

    /** email_quality: one outbox row (To = first Quality employee, CC = the rest), label PNG + RMTC record PDF attached, dispatched. */
    static int emailQuality(Api api, JSONObject r, Assets s, JSONObject attachment) throws Exception {
        List<String[]> rec = qualityRecipients(api);
        if (rec.isEmpty()) return 0;
        JSONArray manifest = new JSONArray();
        manifest.put(new JSONObject().put("bucket", Api.BUCKET).put("object_path", Lookups.j(attachment, "object_path"))
            .put("file_name", Lookups.j(attachment, "file_name")).put("mime_type", PNG).put("generated", false));
        try {  // include_generated_pdf=True: the RMTC record PDF (print layout)
            byte[] pdf = RptPdf.render(RptReports.rmtc(api, Lookups.j(r, "id")));
            manifest.put(SndMail.uploadExport(api, SndMail.exportFolder(api), "QCMS_RMTC_" + safeToken(s.number) + ".pdf", pdf, PDF, true));
        } catch (Exception ignored) { }
        String number = s.number.isEmpty() ? "-" : s.number;
        StringBuilder body = new StringBuilder();
        body.append("RMTC ").append(number).append(" has been approved (").append(Ui.pretty(Lookups.j(r, "disposition"))).append(").\n\n");
        body.append(String.join("\n", s.lines.subList(1, s.lines.size())));
        body.append("\n\nAttached: the QR label (PNG) and the RMTC record PDF. Print the QR label and stick it at the location where this material is stored.");
        body.append("\nScan the QR (QCMS login required) to open / download the approved RMTC certificate: ").append(s.url).append("\n");
        String subject = "Quality · RMTC " + number + " approved · QR label for material location";
        JSONObject ctx = new JSONObject().put("rmtc_id", Lookups.j(r, "id")).put("rmtc_number", number).put("department", "Quality")
            .put("next_task", "Stick QR label at material location").put("event_key", EVENT_KEY).put("document_no", number);
        String text = body.toString();
        JSONObject tpl = SndMail.template(api, null, EVENT_KEY);
        if (tpl != null) {
            if (!Lookups.j(tpl, "subject_template").isEmpty()) subject = SndMail.fill(Lookups.j(tpl, "subject_template"), ctx);
            if (!Lookups.j(tpl, "body_template").isEmpty()) text = SndMail.fill(Lookups.j(tpl, "body_template"), ctx);
        }
        subject = SndMail.departmentSubject(subject, "Quality", EVENT_KEY);
        JSONArray cc = new JSONArray();
        for (int i = 1; i < rec.size(); i++) cc.put(rec.get(i)[0]);
        JSONObject row = new JSONObject();
        row.put("event_key", EVENT_KEY);
        row.put("recipient_email", rec.get(0)[0]);
        row.put("recipient_name", rec.get(0)[1].isEmpty() ? JSONObject.NULL : rec.get(0)[1]);
        row.put("cc_emails", cc);
        row.put("subject", subject);
        row.put("body_text", text);
        row.put("body_html", SndMail.notificationHtml(text));
        row.put("related_table", "rmtc_approvals");
        row.put("related_id", Lookups.j(r, "id"));
        row.put("context", ctx);
        row.put("template_key", EVENT_KEY);
        row.put("attachment_manifest", manifest);
        row.put("is_automatic", true);
        row.put("status", "PENDING");
        JSONObject saved = api.insert("qcms_notification_outbox", row);
        List<String> ids = new ArrayList<>();
        if (!Lookups.j(saved, "id").isEmpty()) ids.add(Lookups.j(saved, "id"));
        SndMail.dispatch(api, ids);
        return rec.size();
    }

    /**
     * on_rmtc_approved (background, never throws): label PNG stored as the RMTC attachment and, when sendEmail, the
     * Quality-department e-mail. Returns {ok, emailed, warnings[]}.
     */
    static JSONObject onApproved(Api api, String rid, boolean sendEmail) {
        JSONObject result = new JSONObject();
        JSONArray warnings = new JSONArray();
        try {
            result.put("ok", false).put("emailed", 0).put("warnings", warnings);
            JSONObject r = IncRmtcData.rmtc(api, rid);
            if (!approved(r)) { warnings.put("RMTC is not approved; QR not generated."); return result; }
            Assets s = assets(api, r);
            result.put("ok", true).put("url", s.url);
            JSONObject attachment = null;
            try {
                attachment = storeLabel(api, r, png(s), s.stem);
            } catch (Exception e) {
                warnings.put("QR label PNG could not be stored: " + Api.message(e));
            }
            if (sendEmail) {
                if (attachment == null) warnings.put("QR e-mail not sent because the QR label PNG is not stored.");
                else {
                    try {
                        int n = emailQuality(api, r, s, attachment);
                        result.put("emailed", n);
                        if (n == 0) warnings.put("No active Quality department employee with an e-mail address; QR e-mail not queued.");
                    } catch (Exception e) {
                        warnings.put("QR e-mail could not be queued: " + Api.message(e));
                    }
                }
            }
        } catch (Exception e) {
            warnings.put("QR could not be generated: " + Api.message(e));
        }
        return result;
    }

    /** Toast text for an onApproved result. */
    static String summary(JSONObject res) {
        if (res == null) return "";
        StringBuilder sb = new StringBuilder();
        int n = res.optInt("emailed", 0);
        if (n > 0) sb.append("Material-location QR label generated and e-mailed to ").append(n).append(" Quality department employee(s).");
        else if (res.optBoolean("ok")) sb.append("Material-location QR label generated.");
        JSONArray w = res.optJSONArray("warnings");
        for (int i = 0; w != null && i < w.length(); i++) sb.append(sb.length() > 0 ? " " : "").append(w.optString(i));
        return sb.toString();
    }

    // ================================================================== record panel (RecordScreen, rmtc_approvals)
    /** Sections applicable + (approved RMTC) material-location QR with PNG / JPEG / PDF / label downloads. */
    static View panel(MainActivity a, JSONObject rec, Runnable reload) {
        LinearLayout box = Ui.vbox(a);
        Api api = Api.get(a);
        String rid = Lookups.j(rec, "id");
        if (rid.isEmpty()) return box;
        box.addView(Ui.text(a, "Loading sections applicable / QR…", 12, Ui.MUTED, false));
        Api.async(() -> {
            LinkedHashMap<String, Boolean> sec = IncRmtcSections.load(api, rid, rec);
            boolean manage = AdmPerm.current(api, MODULE_KEY, "can_edit") || AdmPerm.current(api, MODULE_KEY, "can_approve");
            Assets s = null;
            Bitmap bmp = null;
            JSONObject stored = null;
            if (approved(rec)) {
                s = assets(api, rec);
                bmp = labelBitmap(s);
                stored = storedLabel(api, rid);
            }
            return new Object[]{sec, manage, s, bmp, stored};
        }, (res, err) -> {
            box.removeAllViews();
            if (err != null || res == null) { box.addView(Ui.text(a, "QR / sections could not be loaded: " + Api.message(err), 12, Ui.AMBER_FG, false)); return; }
            @SuppressWarnings("unchecked") LinkedHashMap<String, Boolean> sec = (LinkedHashMap<String, Boolean>) res[0];
            boolean manage = (Boolean) res[1];
            String st = Lookups.j(rec, "status").toUpperCase(Locale.ROOT);
            boolean editable = manage && (st.isEmpty() || st.equals("DRAFT") || st.equals("APPROVAL_PENDING"));
            box.addView(IncRmtcSections.card(a, rid, sec, editable, m -> { if (reload != null) reload.run(); }));
            if (res[2] == null) return;
            renderQr(a, box, rec, (Assets) res[2], (Bitmap) res[3], (JSONObject) res[4], manage, reload);
        });
        return box;
    }

    private static void renderQr(MainActivity a, LinearLayout box, JSONObject rec, Assets s, Bitmap bmp, JSONObject stored, boolean manage, Runnable reload) {
        Api api = Api.get(a);
        String rid = Lookups.j(rec, "id");
        LinearLayout card = Ui.card(a);
        card.addView(Ui.text(a, "MATERIAL LOCATION QR", 13, Ui.TEXT, true));
        card.addView(Ui.text(a, "Stick this QR label where the material is stored. Scanning it opens this RMTC in QCMS (login required) with the certificate downloads.", 11.5f, Ui.MUTED, false));
        ImageView img = new ImageView(a);
        img.setAdjustViewBounds(true);
        img.setScaleType(ImageView.ScaleType.FIT_CENTER);
        if (bmp != null) img.setImageBitmap(bmp);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(Ui.dp(a, 240), LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = Ui.dp(a, 6);
        card.addView(img, lp);
        card.addView(Ui.text(a, s.url, 11, Ui.MUTED, false), Ui.matchWrap(a, 4));
        if (stored != null) card.addView(Ui.text(a, "QR label stored as RMTC attachment: " + Lookups.j(stored, "file_name") + " · "
            + Ui.date(IncCalc.firstText(Lookups.j(stored, "updated_at"), Lookups.j(stored, "created_at"))), 11, Ui.MUTED, false), Ui.matchWrap(a, 2));
        else card.addView(Ui.text(a, "No QR label has been generated for this approved RMTC yet (approved before R38 / R39 or from an older app).", 11.5f, Ui.AMBER_FG, false), Ui.matchWrap(a, 2));

        addFileButton(a, card, "⇩ QR PNG · Save / Share", s.stem + "_QR.png", PNG, () -> png(s));
        addFileButton(a, card, "⇩ QR JPEG · Save / Share", s.stem + "_QR.jpg", JPEG, () -> jpeg(s));
        addFileButton(a, card, "⇩ QR PDF (A6, QR + RMTC text) · View / Save / Share / Print", s.stem + "_QR.pdf", PDF, () -> pdf(s));
        addFileButton(a, card, "🖨 Print Label PDF (100 x 60 mm)", s.stem + "_QR_Label.pdf", PDF, () -> labelPdf(s));
        if (stored != null) {
            Button open = Ui.outline(a, "📎 Stored QR label attachment (" + Lookups.j(stored, "file_name") + ")", Ui.TEAL_DARK);
            card.addView(open, Ui.matchWrap(a, 6));
            String path = Lookups.j(stored, "object_path"), name = IncCalc.firstText(Lookups.j(stored, "file_name"), s.stem + "_QR_Label.png");
            String mime = IncCalc.firstText(Lookups.j(stored, "mime_type"), PNG);
            open.setOnClickListener(v -> Api.async(() -> api.download(path), (bytes, err) -> {
                if (err != null || bytes == null) { a.toast("Could not download the attachment: " + Api.message(err)); return; }
                fileActions(a, name, mime, bytes);
            }));
        }
        if (manage) {
            Button refresh = Ui.outline(a, stored == null ? "Generate QR & e-mail Quality department" : "Refresh QR Label", Ui.TEAL);
            card.addView(refresh, Ui.matchWrap(a, 10));
            boolean send = stored == null;
            refresh.setOnClickListener(v -> runHook(a, rid, send, refresh, reload));
            if (stored != null) {
                Button resend = Ui.outline(a, "Re-send QR to Quality", Ui.TEAL);
                card.addView(resend, Ui.matchWrap(a, 6));
                resend.setOnClickListener(v -> runHook(a, rid, true, resend, reload));
            }
        }
        box.addView(card, Ui.matchWrap(a, 8));
    }

    private static void runHook(MainActivity a, String rid, boolean send, Button b, Runnable reload) {
        b.setEnabled(false);
        a.toast(send ? "Generating QR label and e-mailing the Quality department…" : "Refreshing the QR label…");
        Api api = Api.get(a);
        Api.async(() -> onApproved(api, rid, send), (res, err) -> {
            b.setEnabled(true);
            a.toast(err != null ? Api.message(err) : summary(res));
            if (reload != null) reload.run();
        });
    }

    private static void addFileButton(MainActivity a, LinearLayout card, String label, String name, String mime, Api.Task<byte[]> build) {
        Button b = Ui.outline(a, label, Ui.TEAL);
        card.addView(b, Ui.matchWrap(a, 6));
        b.setOnClickListener(v -> Api.async(build, (bytes, err) -> {
            if (err != null || bytes == null || bytes.length == 0) { a.toast("Could not create " + name + ": " + Api.message(err)); return; }
            fileActions(a, name, mime, bytes);
        }));
    }

    /** View (PDF) · Save to Downloads · Share · Print (PDF) · Email from QCMS. */
    static void fileActions(MainActivity a, String name, String mime, byte[] data) {
        boolean pdf = PDF.equals(mime);
        List<String> items = new ArrayList<>();
        if (pdf) items.add("View PDF");
        items.add("Save to Downloads");
        items.add("Share (WhatsApp, Gmail…)");
        if (pdf) items.add("Print");
        items.add("Email from QCMS (attached)");
        new AlertDialog.Builder(a)
            .setTitle(name)
            .setItems(items.toArray(new String[0]), (d, which) -> {
                String item = items.get(which);
                if (item.startsWith("View")) SndPdfView.show(a, name, name, data);
                else if (item.startsWith("Print")) ExportKit.printPdf(a, name, data);
                else if (item.startsWith("Email")) {
                    List<Attachments.FileData> files = new ArrayList<>();
                    files.add(new Attachments.FileData(data, name, mime));
                    SndEmailSend.openWith(a, "QCMS · " + name, "Dear Sir / Madam,\n\nPlease find attached " + name + " from QCMS.\n\nRegards,\n" + ExportKit.printedBy(a), files);
                } else {
                    boolean share = item.startsWith("Share");
                    Api.async(() -> SndFiles.saveToDownloads(a, name, data, mime), (saved, err) -> {
                        if (err != null || saved == null) { a.toast("Could not save: " + Api.message(err)); return; }
                        if (saved.uri == null) { a.toast("Saved: " + saved.where + (share ? " (sharing needs Android 10 or newer)" : "")); return; }
                        if (share) { SndFiles.share(a, saved.uri, mime, name); return; }
                        new AlertDialog.Builder(a).setTitle("Saved").setMessage(saved.where)
                            .setPositiveButton("Open", (x, y) -> SndFiles.open(a, saved.uri, mime))
                            .setNeutralButton("Share", (x, y) -> SndFiles.share(a, saved.uri, mime, name))
                            .setNegativeButton("Done", null).show();
                    });
                }
            })
            .setNegativeButton("Close", null)
            .show();
    }
}
