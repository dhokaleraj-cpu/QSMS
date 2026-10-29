package com.fourstar.qcmsapp;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.graphics.pdf.PdfDocument;
import android.text.TextPaint;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;

/**
 * R39 · Shared print kit for the "PO look" documents that are not the Direct PO itself (OSP Returnable Delivery
 * Challan, Indirect PO / GRN): A4 portrait PdfDocument with the ReportLab coordinate system of
 * core/purchase_order_reporting.py (origin bottom-left), Print Layout Designer colours (saved PURCHASE_ORDER layout),
 * _bar / _block / _draw_text / _wrap / _party_lines helpers, company logo and the low-visibility status watermark.
 */
final class SupPdfKit {
    static final int PAGE_W = 595, PAGE_H = 842;
    static final float W = 595.2756f, H = 841.8898f;
    static final int TEXT = Color.parseColor("#202124");
    static final int GREY = Color.parseColor("#6B7280");
    static final int DARK = Color.parseColor("#111827");
    static final int WHITE = Color.WHITE;

    final JSONObject layout;
    private final String watermark;
    private final PdfDocument doc = new PdfDocument();
    private PdfDocument.Page page;
    private Canvas canvas;
    private int pageNo = 0;
    int fill = TEXT, stroke = Color.BLACK;
    float lw = 1f;
    private final Paint fp = new Paint(Paint.ANTI_ALIAS_FLAG), sp = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final TextPaint tp = new TextPaint(Paint.ANTI_ALIAS_FLAG);

    SupPdfKit(JSONObject layout, String watermark) {
        this.layout = layout == null ? SndData.defaultLayout() : layout;
        this.watermark = watermark == null ? "" : watermark;
        fp.setStyle(Paint.Style.FILL);
        sp.setStyle(Paint.Style.STROKE);
    }

    /** Saved Print Layout Designer theme (PURCHASE_ORDER) or the default; never throws. */
    static JSONObject layout(Api api) {
        try { return SndData.loadLayout(api); } catch (Exception e) { return SndData.defaultLayout(); }
    }

    // ------------------------------------------------------------------ pages
    void newPage() {
        pageNo++;
        page = doc.startPage(new PdfDocument.PageInfo.Builder(PAGE_W, PAGE_H, pageNo).create());
        canvas = page.getCanvas();
        drawWatermark();
        rules();
    }

    void showPage() {
        if (page != null) doc.finishPage(page);
        page = null;
    }

    int pageNumber() { return pageNo; }

    byte[] finish() throws Exception {
        if (page != null) showPage();
        try {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            doc.writeTo(out);
            return out.toByteArray();
        } finally {
            doc.close();
        }
    }

    /** _watermark_pdf_bytes: very light status text behind the content. */
    private void drawWatermark() {
        if (watermark.isEmpty()) return;
        float size = watermark.length() > 9 ? 27 : 36;
        TextPaint p = font(size, true);
        p.setColor(Color.parseColor("#F2F4F7"));
        float tw = p.measureText(watermark);
        canvas.save();
        canvas.translate(W / 2f, H / 2f);
        try { Canvas.class.getMethod("rotate", float.class).invoke(canvas, -36f); } catch (Throwable ignored) { }
        canvas.drawText(watermark, -tw / 2f, 8f, p);
        canvas.restore();
    }

    // ------------------------------------------------------------------ colours (_ACTIVE)
    int color(String key, int fallback) {
        String v = SndData.s(layout, key);
        if (v.isEmpty()) return fallback;
        try { return Color.parseColor(v); } catch (Exception e) { return fallback; }
    }
    int accent() { return color("accent", Color.parseColor("#0B6E70")); }
    int fillOrWhite(String key) { return color(key, WHITE); }
    void rules() { stroke = color("rule", Color.parseColor("#C9D6D6")); lw = 0.5f; }
    boolean show(String flag) { return !layout.has(flag) || SndData.truthy(layout.opt(flag)); }
    String footerText() { return SndData.s(layout, "footer_text").isEmpty() ? "FSI · connect@fourstarindustries.com" : SndData.s(layout, "footer_text"); }

    // ------------------------------------------------------------------ primitives (ReportLab coordinates)
    private float y(float rl) { return H - rl; }

    void rect(float x, float yb, float w, float h, boolean doStroke, boolean doFill) {
        if (w <= 0 || h <= 0 || canvas == null) return;
        float top = y(yb + h), bottom = y(yb);
        if (doFill) { fp.setColor(fill); canvas.drawRect(x, top, x + w, bottom, fp); }
        if (doStroke) { sp.setColor(stroke); sp.setStrokeWidth(lw); canvas.drawRect(x, top, x + w, bottom, sp); }
    }

    void roundRect(float x, float yb, float w, float h, float r) {
        if (canvas == null) return;
        sp.setColor(stroke); sp.setStrokeWidth(lw);
        canvas.drawRoundRect(new RectF(x, y(yb + h), x + w, y(yb)), r, r, sp);
    }

    void line(float x1, float y1, float x2, float y2) {
        if (canvas == null) return;
        sp.setColor(stroke); sp.setStrokeWidth(lw);
        canvas.drawLine(x1, y(y1), x2, y(y2), sp);
    }

    TextPaint font(float size, boolean bold) {
        tp.setTypeface(bold ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
        tp.setTextSize(size);
        tp.setTextAlign(Paint.Align.LEFT);
        return tp;
    }

    float width(String s, float size, boolean bold) { return s == null || s.isEmpty() ? 0 : font(size, bold).measureText(s); }

    void string(float x, float yb, String s, float size, boolean bold, int color) {
        if (s == null || s.isEmpty() || canvas == null) return;
        TextPaint p = font(size, bold);
        p.setColor(color);
        canvas.drawText(s, x, y(yb), p);
    }

    void right(float x, float yb, String s, float size, boolean bold, int color) { string(x - width(s, size, bold), yb, s, size, bold, color); }
    void centre(float x, float yb, String s, float size, boolean bold, int color) { string(x - width(s, size, bold) / 2f, yb, s, size, bold, color); }

    void bitmap(Bitmap b, float x, float yb, float w, float h) {
        if (b == null || canvas == null || b.getWidth() <= 0 || b.getHeight() <= 0) return;
        float scale = Math.min(w / b.getWidth(), h / b.getHeight());
        float dw = b.getWidth() * scale, dh = b.getHeight() * scale;
        float left = x + (w - dw) / 2f, bottomRl = yb + (h - dh) / 2f;
        canvas.save();
        canvas.translate(left, y(bottomRl + dh));
        canvas.scale(scale, scale);
        canvas.drawBitmap(b, 0f, 0f, (Paint) null);
        canvas.restore();
    }

    void logo() { bitmap(SndLogo.bitmap(), 28, H - 58, 105, 39); }

    /** _draw_text: one line, shortened with "..." to max width. */
    void text(float x, float y, Object value, float size, boolean bold, int color, float maxWidth) {
        String v = SndData.clean(value);
        if (maxWidth > 0 && !v.isEmpty() && width(v, size, bold) > maxWidth) {
            while (v.length() > 3 && width(v + "...", size, bold) > maxWidth) v = v.substring(0, v.length() - 1);
            v = v.replaceAll("\\s+$", "") + "...";
        }
        string(x, y, v, size, bold, color);
    }

    void text(float x, float y, Object value, float size, boolean bold, int color) { text(x, y, value, size, bold, color, 0); }

    /** Value in a fixed box: shrink the font (down to 70 %) before shortening. */
    void fit(float x, float y, Object value, float size, boolean bold, int color, float maxWidth) {
        String v = SndData.clean(value);
        float s = size;
        while (s > size * 0.7f && width(v, s, bold) > maxWidth) s -= 0.2f;
        text(x, y, v, s, bold, color, maxWidth);
    }

    /** Right-aligned number in a column, shortened from the right like the website. */
    void rightFit(float xRight, float y, String value, float size, boolean bold, int color, float maxWidth) {
        String v = value == null ? "" : value;
        while (v.length() > 1 && width(v, size, bold) > maxWidth) v = v.substring(0, v.length() - 1);
        right(xRight, y, v, size, bold, color);
    }

    List<String> wrapLines(String value, float width, float size, boolean bold, int maxLines) {
        List<String> lines = new ArrayList<>();
        for (String para : (value == null ? "" : value).split("\\r?\\n")) {
            String clean = SndData.clean(para);
            if (clean.isEmpty()) continue;
            String line = "";
            for (String word : clean.split(" ")) {
                String test = (line + " " + word).trim();
                if (width(test, size, bold) <= width) line = test;
                else {
                    if (!line.isEmpty()) lines.add(line);
                    line = word;
                }
            }
            if (!line.isEmpty()) lines.add(line);
        }
        if (lines.size() > maxLines) {
            List<String> cut = new ArrayList<>(lines.subList(0, maxLines));
            String last = cut.get(maxLines - 1);
            cut.set(maxLines - 1, last.substring(0, Math.max(last.length() - 3, 1)) + "...");
            return cut;
        }
        return lines;
    }

    /** _wrap: returns the y below the last line. */
    float wrap(float x, float y, Object text, float width, float size, float leading, boolean bold, int maxLines) {
        List<String> lines = wrapLines(SndData.clean(text), width, size, bold, maxLines);
        for (int i = 0; i < lines.size(); i++) text(x, y - i * leading, lines.get(i), size, bold, TEXT, width);
        return y - lines.size() * leading;
    }

    String relabel(String title) {
        JSONObject labels = layout.optJSONObject("labels");
        if (labels == null || labels.length() == 0) return title;
        if (labels.has(title)) return labels.optString(title, title);
        Iterator<String> it = labels.keys();
        while (it.hasNext()) {
            String original = it.next();
            if (title.startsWith(original)) return labels.optString(original, original) + title.substring(original.length());
        }
        return title;
    }

    /** _bar: section heading band (solid / underline / outline style of the saved layout). */
    void bar(float x, float y, float width, String title, float height) {
        title = relabel(title);
        rules();
        String style = SndData.s(layout, "bar");
        int accent = accent();
        if ("underline".equals(style)) {
            fill = WHITE; rect(x, y - height, width, height, false, true);
            stroke = accent; lw = 1.1f; line(x, y - height, x + width, y - height); rules();
            text(x + 3, y - height + 3.1f, title, 7.2f, true, accent, width - 6);
        } else if ("outline".equals(style)) {
            fill = WHITE; stroke = accent; lw = 0.8f;
            rect(x, y - height, width, height, true, true); rules();
            text(x + 4, y - height + 3.1f, title, 7.2f, true, accent, width - 8);
        } else {
            fill = accent;
            rect(x, y - height, width, height, false, true);
            text(x + 4, y - height + 3.1f, title, 7.2f, true, WHITE, width - 8);
        }
    }

    /** _block: bar + up to maxLines non-empty lines (each may wrap to two). */
    float block(float x, float yTop, float width, String title, List<String> lines, int maxLines) {
        bar(x, yTop, width, title, 13);
        float y = yTop - 24;
        int shown = 0;
        for (String line : lines) {
            if (SndData.clean(line).isEmpty()) continue;
            if (shown++ >= maxLines) break;
            y = wrap(x + 4, y, line, width - 8, 7.0f, 8.2f, false, 2);
        }
        return y;
    }

    /** _special_lines: each numbered instruction on its own line. */
    float specialLines(float x, float y, String text, float width, float bottom) {
        for (String raw : (text == null ? "" : text).split("\\r?\\n")) {
            String line = raw.trim();
            if (line.isEmpty()) continue;
            if (y < bottom) break;
            y = wrap(x, y, line, width, 6.2f, 9.6f, false, 2);
        }
        return y;
    }

    /** _party_lines of a party / branch snapshot (name, address, locality, GSTIN, contact, phone, e-mail). */
    static List<String> partyLines(JSONObject snap) {
        List<String> out = new ArrayList<>();
        if (snap == null) snap = new JSONObject();
        String name = first(SndData.s(snap, "party_name"), SndData.s(snap, "name"), SndData.s(snap, "branch_name"));
        String address = first(SndData.s(snap, "address"), SndData.s(snap, "address1"), SndData.s(snap, "address_line1"));
        String locality = join(", ", SndData.s(snap, "city"), SndData.s(snap, "state"), SndData.s(snap, "country"));
        String legacy = join(", ", SndData.s(snap, "address2"), SndData.s(snap, "address3"));
        out.add(name);
        out.add(address);
        out.add(locality.isEmpty() ? legacy : locality);
        out.add(first(SndData.s(snap, "tax_identifier"), SndData.s(snap, "gstin")));
        out.add(SndData.s(snap, "contact_person"));
        out.add(SndData.s(snap, "phone"));
        out.add(SndData.s(snap, "email"));
        return out;
    }

    /** Digital approval stamp (_draw_approver_stamp). */
    void approverStamp(JSONObject header, float pageWidth) {
        String approver = first(SndData.s(header, "approver_employee_name"), SndData.s(header, "approver_name"));
        String code = SndData.s(header, "approver_employee_code");
        String approvedAt = SndPoPdf.approvalDateTime(SndData.s(header, "approved_at"));
        if (approver.isEmpty()) approver = code.isEmpty() ? "Approver record unavailable" : code;
        String identity = "Approver: " + approver + (!code.isEmpty() && !approver.toLowerCase(Locale.ROOT).contains(code.toLowerCase(Locale.ROOT)) ? " · " + code : "");
        float x = pageWidth - 185, y = 55, bw = 155, bh = 62;
        int green = Color.parseColor("#2E7D32");
        stroke = green; lw = 1.15f;
        roundRect(x, y, bw, bh, 6);
        centre(x + bw / 2, y + 45, "APPROVED", 10.5f, true, green);
        fit(x + 8, y + 30, identity, 6.4f, true, Color.parseColor("#1F2937"), bw - 16);
        if (!approvedAt.isEmpty()) text(x + 8, y + 17, "Date / Time: " + approvedAt, 5.7f, false, Color.parseColor("#374151"), bw - 16);
        text(x + 8, y + 7, "QCMS DIGITAL APPROVAL", 5.2f, true, GREY, bw - 16);
        rules();
    }

    // ------------------------------------------------------------------ R39: standard PO terms pages (_compact_terms_portrait)
    private static final float T_SIZE = 6.9f, T_LEAD = 8.3f, T_GAP = 3.2f, T_LEFT = 24f, T_RIGHT = 24f, T_BOTTOM = 34f;

    /** FSI standard PO terms (SndTerms) appended as portrait pages with this order's DATE / PO # (and amendment caption). */
    void termsPages(String poNumber, String orderDate, String plantName, String caption) {
        float width = W - T_LEFT - T_RIGHT;
        java.util.regex.Pattern heading = java.util.regex.Pattern.compile("^((?:\\d+\\.|\\([a-z]\\))\\s+([^:]{1,90}):)");
        float space = width(" x", T_SIZE, false) - width("x", T_SIZE, false);
        List<List<String>> words = new ArrayList<>();
        List<List<Boolean>> bolds = new ArrayList<>();
        List<Boolean> ends = new ArrayList<>();
        for (String para : SndTerms.PARAGRAPHS) {
            java.util.regex.Matcher m = heading.matcher(para);
            int boldChars = m.find() && m.group(2).equals(m.group(2).toUpperCase(Locale.ROOT)) ? m.group(1).length() : 0;
            int pos = 0;
            List<String> lw = new ArrayList<>(); List<Boolean> lb = new ArrayList<>();
            float lineW = 0;
            for (String word : para.split(" ")) {
                if (word.isEmpty()) { pos++; continue; }
                boolean b = pos < boldChars;
                pos += word.length() + 1;
                float ww = width(word, T_SIZE, b);
                float add = lw.isEmpty() ? ww : space + ww;
                if (!lw.isEmpty() && lineW + add > width) {
                    words.add(lw); bolds.add(lb); ends.add(false);
                    lw = new ArrayList<>(); lb = new ArrayList<>(); lineW = 0; add = ww;
                }
                lw.add(word); lb.add(b); lineW += add;
            }
            if (!lw.isEmpty()) { words.add(lw); bolds.add(lb); ends.add(true); }
        }
        List<int[]> pages = new ArrayList<>();
        int i = 0;
        boolean first = true;
        while (i < words.size()) {
            float y = first ? H - 150 : H - 96;
            int start = i;
            while (i < words.size()) {
                if (y < T_BOTTOM && i > start) break;
                y -= T_LEAD + (ends.get(i) ? T_GAP : 0);
                i++;
            }
            pages.add(new int[]{start, i});
            first = false;
        }
        for (int p = 0; p < pages.size(); p++) {
            newPage();
            logo();
            right(W - 28, H - 34, "PURCHASE ORDER", 20, true, TEXT);
            fill = accent(); rect(28, H - 74, 230, 10, false, true);
            text(32, H - 71.6f, "PLANT", 6.6f, true, WHITE);
            text(32, H - 83, plantName, 6.6f, false, TEXT, 222);
            rules();
            text(W - 137, H - 58, "DATE", 7.0f, false, TEXT);
            rect(W - 91, H - 61, 62, 11, true, false);
            fit(W - 86, H - 58, date(orderDate), 6.8f, false, TEXT, 54);
            text(W - 137, H - 72, "PO #", 7.0f, false, TEXT);
            rect(W - 91, H - 75, 62, 11, true, false);
            fit(W - 86, H - 72, poNumber, 6.8f, false, TEXT, 54);
            if (caption != null && !caption.isEmpty()) text(18, H - 12, "PO # " + poNumber + " - " + caption, 5.6f, false, TEXT, W - 36);
            if (p == 0) {
                centre(W / 2, H - 104, SndTerms.COMPANY, 12.5f, true, TEXT);
                centre(W / 2, H - 120, SndTerms.TITLE, 12.5f, true, TEXT);
                text(80, H - 135, SndTerms.FORMAT, 10f, true, TEXT);
                centre(W / 2 + 40, H - 135, SndTerms.REVISION, 10f, true, TEXT);
                right(W - 60, H - 135, SndTerms.DATE, 10f, true, TEXT);
            }
            float y = p == 0 ? H - 150 : H - 96;
            for (int k = pages.get(p)[0]; k < pages.get(p)[1]; k++) {
                float x = T_LEFT;
                List<String> lw = words.get(k); List<Boolean> lb = bolds.get(k);
                for (int wi = 0; wi < lw.size(); wi++) {
                    string(x, y, lw.get(wi), T_SIZE, lb.get(wi), TEXT);
                    x += width(lw.get(wi), T_SIZE, lb.get(wi)) + space;
                }
                y -= T_LEAD + (ends.get(k) ? T_GAP : 0);
            }
            string(18, 12, "STANDARD PURCHASE ORDER TERMS AND CONDITIONS", 6.3f, false, TEXT);
            string(237, 12, "FSI/703/F04", 6.3f, false, TEXT);
            string(315, 12, SndTerms.DATE, 6.3f, false, TEXT);
            string(500, 12, "Terms " + (p + 1) + " of " + pages.size(), 6.3f, false, TEXT);
            showPage();
        }
    }

    // ------------------------------------------------------------------ formatting (_date / _money / _qty)
    static String date(String value) { return SndPoPdf.date(value); }
    static String money(double v) { return SndPoPdf.money(v); }
    static String qty(double v) {
        if (v == Math.rint(v)) return String.format(Locale.US, "%,.0f", v);
        return SndPoPdf.strip(String.format(Locale.US, "%,.3f", v));
    }
    static String g(double v) { return SndPoPdf.g(v); }

    static String first(String... values) {
        for (String v : values) if (v != null && !v.trim().isEmpty()) return v.trim();
        return "";
    }

    static String join(String sep, String... parts) {
        StringBuilder b = new StringBuilder();
        for (String p : parts) {
            if (p == null || p.trim().isEmpty()) continue;
            if (b.length() > 0) b.append(sep);
            b.append(p.trim());
        }
        return b.toString();
    }
}
