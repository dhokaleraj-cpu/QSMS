package com.fourstar.qcmsapp;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.graphics.pdf.PdfDocument;
import android.text.TextPaint;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.math.BigDecimal;
import java.math.MathContext;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Native controlled Purchase Order PDF (A4 portrait, android.graphics.pdf.PdfDocument).
 * Port of core/purchase_order_reporting.py (Design B family, B5 "Teal Bands" default, Print Layout
 * Designer colours / headings / title / company / footer, per-PO print_options, line numbers, TOTAL QTY,
 * GRAND TOTAL row, approval stamp, price history continuation pages, approval watermark) followed by the
 * standard terms pages (FSI/703/F04, text from SndTerms).
 *
 * All drawing coordinates are the website's ReportLab coordinates (points, origin bottom-left); the
 * page helper flips them to the Android canvas, so every number below matches the Python source.
 */
final class SndPoPdf {
    static final int PAGE_W = 595, PAGE_H = 842;
    private static final float W = 595.2756f, H = 841.8898f;

    private static final int TEXT = Color.parseColor("#202124");
    private static final int GREY = Color.parseColor("#6B7280");
    private static final int DARK = Color.parseColor("#111827");
    private static final int WHITE = Color.WHITE;

    private static final String[] PLANT = {"Four Star Industries Private Limited D9", "Plot No.D9, Chakan MIDC PH II", "Bhamboli, Khed", "Pune 410501",
        "27AAGCF3769A1ZP", "022 40104412", "orders@fourstarindustries.com"};
    static final String DEFAULT_SPECIAL_INSTRUCTIONS = "1. PO number should be mentioned on your Invoice.\n"
        + "2. Material must be packed properly to avoid water damage and free from dent, damages & rust.\n"
        + "3. All QC related reports & TCs to be attached with the Invoices.\n"
        + "4. All reports to be sent to quality@fourstarindustries.com\n"
        + "5. Refer STANDARD PURCHASE ORDER TERMS AND CONDITIONS no FSI/703/F04.";

    private static final int FIRST_HISTORY_ROWS = 3, CONT_HISTORY_ROWS = 28, HISTORY_ONLY_ROWS = 42;
    private static final float FIRST_PAGE_ITEM_BOTTOM = 245, ITEM_GAP = 6, GRAND_TOTAL_HEIGHT = 40;

    private final JSONObject header;
    private final List<JSONObject> items;
    private final JSONObject layout;
    private final PdfDocument doc = new PdfDocument();
    private PdfDocument.Page page;
    private Pg g;
    private int pageNo = 0;
    private final String watermark;

    private SndPoPdf(JSONObject header, List<JSONObject> items, JSONObject layout) {
        this.header = header == null ? new JSONObject() : header;
        this.items = items == null ? new ArrayList<>() : items;
        this.layout = layout == null ? SndData.defaultLayout() : layout;
        this.watermark = "APPROVED".equalsIgnoreCase(SndData.s(this.header, "approval_status")) ? "APPROVED" : "PENDING APPROVAL";
    }

    /** purchase_order_pdf_bytes(header, items): options = sections for THIS print (null = the PO's saved print_options). */
    static byte[] build(SndData.Po po, JSONObject options) throws Exception {
        if (po.items.isEmpty()) throw new IllegalStateException("At least one Purchase Order line is required.");
        JSONObject own = options != null ? options : SndData.obj(po.header, "print_options");
        JSONObject layout = SndData.printLayout(po.layout, own);
        List<JSONObject> copy = new ArrayList<>();
        int total = po.items.size();
        for (int i = 0; i < total; i++) {
            JSONObject it = new JSONObject(po.items.get(i).toString());
            it.put("_line_no", i + 1);
            it.put("_line_count", total);
            copy.add(it);
        }
        SndPoPdf r = new SndPoPdf(po.header, copy, layout);
        try {
            return r.render();
        } finally {
            r.doc.close();
        }
    }

    // ================================================================== layout helpers (_ACTIVE)
    private int color(String key, int fallback) {
        String v = SndData.s(layout, key);
        if (v.isEmpty()) return fallback;
        try { return Color.parseColor(v); } catch (Exception e) { return fallback; }
    }
    private int accent() { return color("accent", Color.parseColor("#0B6E70")); }
    private int ruleColor() { return color("rule", Color.parseColor("#C9D6D6")); }
    private int fillOrWhite(String key) { return color(key, WHITE); }
    // R36b: customer PO references are internal - the source reference prints only when explicitly ticked (internal copy).
    private boolean show(String flag) {
        if ("show_source_reference".equals(flag)) return layout.has(flag) && SndData.truthy(layout.opt(flag));
        return !layout.has(flag) || SndData.truthy(layout.opt(flag));
    }
    private void rules() { g.stroke = ruleColor(); g.lw = 0.5f; }

    private String relabel(String title) {
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

    // ================================================================== formatting (_s / _n / _date / _money)
    static String date(String value) {
        String t = value == null ? "" : value.trim();
        if (t.isEmpty() || "null".equals(t)) return "";
        try {
            String[] p = t.substring(0, Math.min(10, t.length())).split("-");
            if (p.length == 3) return p[2] + "-" + p[1] + "-" + p[0];
        } catch (Exception ignored) { }
        return t.length() > 10 ? t.substring(0, 10) : t;
    }

    static String money(double v) { return String.format(Locale.US, "%,.2f", v); }

    static String strip(String s) {
        if (!s.contains(".")) return s;
        s = s.replaceAll("0+$", "");
        if (s.endsWith(".")) s = s.substring(0, s.length() - 1);
        return s;
    }

    static String qty3(double v) { return strip(String.format(Locale.US, "%,.3f", v)); }
    static String qty2(double v) { return strip(String.format(Locale.US, "%,.2f", v)); }

    /** Python format(v, "g"). */
    static String g(double v) {
        if (v == 0) return "0";
        try {
            BigDecimal b = new BigDecimal(v).round(new MathContext(6)).stripTrailingZeros();
            return b.toPlainString();
        } catch (Exception e) { return String.valueOf(v); }
    }

    /** po_quantity_totals: combined quantity per UOM, e.g. '12,012 KGS'. */
    static String quantityTotals(List<JSONObject> items) {
        Map<String, Double> totals = new LinkedHashMap<>();
        for (JSONObject it : items) {
            String uom = SndData.s(it, "uom").toUpperCase(Locale.ROOT);
            if (uom.isEmpty()) uom = "-";
            Double prev = totals.get(uom);
            totals.put(uom, (prev == null ? 0 : prev) + SndData.n(it, "quantity"));
        }
        StringBuilder b = new StringBuilder();
        for (Map.Entry<String, Double> e : totals.entrySet()) {
            if (b.length() > 0) b.append(" + ");
            b.append(qty3(e.getValue())).append(' ').append(e.getKey());
        }
        return b.length() == 0 ? "-" : b.toString();
    }

    static String approvalDateTime(String value) {
        String t = value == null ? "" : value.trim();
        if (t.isEmpty() || "null".equals(t)) return "";
        DateTimeFormatter out = DateTimeFormatter.ofPattern("dd-MM-yyyy hh:mm a", Locale.ENGLISH);
        try {
            OffsetDateTime dt = OffsetDateTime.parse(t.replace("Z", "+00:00").replace(' ', 'T'));
            return dt.atZoneSameInstant(ZoneId.of("Asia/Kolkata")).format(out) + " IST";
        } catch (Exception ignored) { }
        try {
            LocalDateTime dt = LocalDateTime.parse(t.replace(' ', 'T'));
            return dt.atOffset(ZoneOffset.UTC).atZoneSameInstant(ZoneId.of("Asia/Kolkata")).format(out) + " IST";
        } catch (Exception ignored) { }
        return t.length() > 25 ? t.substring(0, 25) : t;
    }

    private String lineSuffix(JSONObject item) {
        int count = Math.max(1, item.optInt("_line_count", 1));
        return count > 1 ? " · LINE " + Math.max(1, item.optInt("_line_no", 1)) + " OF " + count : "";
    }

    // ================================================================== page helper (ReportLab coordinates)
    private static final class Pg {
        final Canvas c;
        int fill = TEXT, stroke = Color.BLACK;
        float lw = 1f;
        private final Paint fp = new Paint(Paint.ANTI_ALIAS_FLAG), sp = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final TextPaint tp = new TextPaint(Paint.ANTI_ALIAS_FLAG);

        Pg(Canvas c) {
            this.c = c;
            fp.setStyle(Paint.Style.FILL);
            sp.setStyle(Paint.Style.STROKE);
        }

        float y(float rl) { return H - rl; }

        void rect(float x, float yb, float w, float h, boolean doStroke, boolean doFill) {
            if (w <= 0 || h <= 0) return;
            float top = y(yb + h), bottom = y(yb);
            if (doFill) { fp.setColor(fill); c.drawRect(x, top, x + w, bottom, fp); }
            if (doStroke) { sp.setColor(stroke); sp.setStrokeWidth(lw); c.drawRect(x, top, x + w, bottom, sp); }
        }

        void roundRect(float x, float yb, float w, float h, float r) {
            sp.setColor(stroke); sp.setStrokeWidth(lw);
            c.drawRoundRect(new RectF(x, y(yb + h), x + w, y(yb)), r, r, sp);
        }

        void line(float x1, float y1, float x2, float y2) {
            sp.setColor(stroke); sp.setStrokeWidth(lw);
            c.drawLine(x1, y(y1), x2, y(y2), sp);
        }

        TextPaint font(float size, boolean bold) {
            tp.setTypeface(bold ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
            tp.setTextSize(size);
            tp.setTextAlign(Paint.Align.LEFT);
            return tp;
        }

        float width(String s, float size, boolean bold) { return s == null || s.isEmpty() ? 0 : font(size, bold).measureText(s); }

        void string(float x, float yb, String s, float size, boolean bold, int color) {
            if (s == null || s.isEmpty()) return;
            TextPaint p = font(size, bold);
            p.setColor(color);
            c.drawText(s, x, y(yb), p);
        }

        void right(float x, float yb, String s, float size, boolean bold, int color) { string(x - width(s, size, bold), yb, s, size, bold, color); }
        void centre(float x, float yb, String s, float size, boolean bold, int color) { string(x - width(s, size, bold) / 2f, yb, s, size, bold, color); }

        void bitmap(Bitmap b, float x, float yb, float w, float h) {
            if (b == null || b.getWidth() <= 0 || b.getHeight() <= 0) return;
            // preserveAspectRatio, anchored in the centre like ReportLab drawImage
            float scale = Math.min(w / b.getWidth(), h / b.getHeight());
            float dw = b.getWidth() * scale, dh = b.getHeight() * scale;
            float left = x + (w - dw) / 2f, bottomRl = yb + (h - dh) / 2f;
            c.save();
            c.translate(left, y(bottomRl + dh));
            c.scale(scale, scale);
            c.drawBitmap(b, 0f, 0f, (Paint) null);
            c.restore();
        }
    }

    /** _draw_text: one line, shortened with "..." to max width. */
    private void text(float x, float y, Object value, float size, boolean bold, int color, float maxWidth) {
        String v = SndData.clean(value);
        if (maxWidth > 0 && !v.isEmpty() && g.width(v, size, bold) > maxWidth) {
            while (v.length() > 3 && g.width(v + "...", size, bold) > maxWidth) v = v.substring(0, v.length() - 1);
            v = v.replaceAll("\\s+$", "") + "...";
        }
        g.fill = color;
        g.string(x, y, v, size, bold, color);
    }

    private void text(float x, float y, Object value, float size, boolean bold, int color) { text(x, y, value, size, bold, color, 0); }

    /** Value in a fixed box: shrink the font (down to 70 %) before shortening, so numbers stay complete. */
    private void fit(float x, float y, Object value, float size, boolean bold, int color, float maxWidth) {
        String v = SndData.clean(value);
        float s = size;
        while (s > size * 0.7f && g.width(v, s, bold) > maxWidth) s -= 0.2f;
        text(x, y, v, s, bold, color, maxWidth);
    }

    /** Word wrap (reportlab stringWidth based). */
    private List<String> wrapLines(String value, float width, float size, boolean bold, int maxLines) {
        List<String> lines = new ArrayList<>();
        String line = "";
        String clean = SndData.clean(value);
        if (clean.isEmpty()) return lines;
        for (String word : clean.split(" ")) {
            String test = (line + " " + word).trim();
            if (g.width(test, size, bold) <= width) line = test;
            else {
                if (!line.isEmpty()) lines.add(line);
                line = word;
                if (lines.size() >= maxLines) break;
            }
        }
        if (!line.isEmpty() && lines.size() < maxLines) lines.add(line);
        return lines;
    }

    /** _wrap: returns the y below the last line. */
    private float wrap(float x, float y, Object text, float width, float size, float leading, boolean bold, int maxLines) {
        List<String> lines = wrapLines(SndData.clean(text), width, size, bold, maxLines);
        for (int i = 0; i < lines.size(); i++) {
            String l = lines.get(i);
            // a single word wider than the column is shortened instead of running over the border
            if (g.width(l, size, bold) > width) text(x, y - i * leading, l, size, bold, TEXT, width);
            else g.string(x, y - i * leading, l, size, bold, TEXT);
        }
        return y - lines.size() * leading;
    }

    // ================================================================== pages
    private void newPage() {
        pageNo++;
        page = doc.startPage(new PdfDocument.PageInfo.Builder(PAGE_W, PAGE_H, pageNo).create());
        g = new Pg(page.getCanvas());
        drawWatermark();
        rules();
    }

    private void showPage() {
        if (page != null) doc.finishPage(page);
        page = null;
    }

    /** _watermark_pdf_bytes: very light approval watermark BEHIND the content (drawn first). */
    private void drawWatermark() {
        float size = "APPROVED".equals(watermark) ? 36 : 27;
        TextPaint p = g.font(size, true);
        p.setColor(Color.parseColor("#F2F4F7"));
        float tw = p.measureText(watermark);
        Canvas c = g.c;
        c.save();
        c.translate(W / 2f, H / 2f);
        try {
            Canvas.class.getMethod("rotate", float.class).invoke(c, -36f);
        } catch (Throwable ignored) { }
        c.drawText(watermark, -tw / 2f, 8f, p);
        c.restore();
    }

    private byte[] render() throws Exception {
        List<Object[]> overflow = new ArrayList<>();
        boolean[] firstGrand = {false};
        int drawn = firstPage(overflow, firstGrand);
        for (Object[] o : overflow) historyContinuationPages((JSONObject) o[0], castList(o[1]));
        if (drawn < items.size()) continuationItems(items.subList(drawn, items.size()), !firstGrand[0]);
        termsPages();
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        doc.writeTo(out);
        return out.toByteArray();
    }

    @SuppressWarnings("unchecked")
    private static List<JSONObject> castList(Object o) { return (List<JSONObject>) o; }

    private void logo() { g.bitmap(SndLogo.bitmap(), 28, H - 58, 105, 39); }

    // ------------------------------------------------------------------ _bar / _block
    private void bar(float x, float y, float width, String title, float height) {
        title = relabel(title);
        rules();
        String style = SndData.s(layout, "bar");
        int accent = accent();
        if ("underline".equals(style)) {
            g.fill = WHITE; g.rect(x, y - height, width, height, false, true);
            g.stroke = accent; g.lw = 1.1f; g.line(x, y - height, x + width, y - height); rules();
            text(x + 3, y - height + 3.1f, title, 7.2f, true, accent, width - 6);
        } else if ("outline".equals(style)) {
            g.fill = WHITE; g.stroke = accent; g.lw = 0.8f;
            g.rect(x, y - height, width, height, true, true); rules();
            text(x + 4, y - height + 3.1f, title, 7.2f, true, accent, width - 8);
        } else {
            g.fill = accent;
            g.rect(x, y - height, width, height, false, true);
            text(x + 4, y - height + 3.1f, title, 7.2f, true, WHITE, width - 8);
        }
    }

    private float block(float x, float yTop, float width, String title, List<String> lines, int maxLines) {
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

    private static List<String> partyLines(JSONObject snap) {
        List<String> out = new ArrayList<>();
        String name = SndData.s(snap, "party_name").isEmpty() ? SndData.s(snap, "name") : SndData.s(snap, "party_name");
        String address = SndData.s(snap, "address").isEmpty() ? SndData.s(snap, "address1") : SndData.s(snap, "address");
        String locality = joinNonEmpty(", ", SndData.s(snap, "city"), SndData.s(snap, "state"), SndData.s(snap, "country"));
        String legacy = joinNonEmpty(", ", SndData.s(snap, "address2"), SndData.s(snap, "address3"));
        out.add(name);
        out.add(address);
        out.add(locality.isEmpty() ? legacy : locality);
        out.add(SndData.s(snap, "tax_identifier"));
        out.add(SndData.s(snap, "contact_person"));
        out.add(SndData.s(snap, "phone"));
        out.add(SndData.s(snap, "email"));
        return out;
    }

    private static String joinNonEmpty(String sep, String... parts) {
        StringBuilder b = new StringBuilder();
        for (String p : parts) {
            if (p == null || p.isEmpty()) continue;
            if (b.length() > 0) b.append(sep);
            b.append(p);
        }
        return b.toString();
    }

    private JSONObject plantSnapshot() {
        JSONObject p = SndData.obj(header, "plant_snapshot");
        if (p != null && p.length() > 0) return p;
        return defaultPlant();
    }

    static JSONObject defaultPlant() {
        JSONObject p = new JSONObject();
        try {
            p.put("name", PLANT[0]); p.put("address1", PLANT[1]); p.put("address2", PLANT[2]); p.put("address3", PLANT[3]);
            p.put("tax_identifier", PLANT[4]); p.put("phone", PLANT[5]); p.put("email", PLANT[6]);
        } catch (Exception ignored) { }
        return p;
    }

    // ------------------------------------------------------------------ first page
    private int firstPage(List<Object[]> overflow, boolean[] grandOut) {
        newPage();
        float w = W, h = H, left = 28, right = 28;
        logo();
        String title = SndData.s(layout, "title").isEmpty() ? "PURCHASE ORDER" : SndData.s(layout, "title");
        g.right(w - right, h - 34, title, 24, true, accent());
        rules();
        text(w - 137, h - 51, "DATE", 7.4f, false, TEXT);
        g.rect(w - 91, h - 58, 62, 12, true, false);
        fit(w - 86, h - 55, date(SndData.s(header, "order_date")), 7.2f, false, TEXT, 54);
        text(w - 137, h - 65, "PO #", 7.4f, false, TEXT);
        g.rect(w - 91, h - 72, 62, 12, true, false);
        fit(w - 86, h - 69, SndData.s(header, "po_number"), 7.2f, false, TEXT, 54);
        String amendment = amendmentCaption(header);
        if (!amendment.isEmpty()) g.right(w - right - 1, h - 81, amendment, 6.3f, true, accent());   // R37b

        float colW = 230, leftX = left, rightX = w - right - 184, y0 = h - 62;
        JSONObject plant = plantSnapshot();
        if (show("show_plant")) {
            List<String> pl = new ArrayList<>();
            pl.add(SndData.s(plant, "name").isEmpty() ? SndData.s(plant, "branch_name") : SndData.s(plant, "name"));
            pl.add(SndData.s(plant, "address1")); pl.add(SndData.s(plant, "address2")); pl.add(SndData.s(plant, "address3"));
            pl.add(SndData.s(plant, "tax_identifier").isEmpty() ? SndData.s(plant, "gstin") : SndData.s(plant, "tax_identifier"));
            pl.add(SndData.s(plant, "phone")); pl.add(SndData.s(plant, "email"));
            block(leftX, y0, colW, "PLANT / COMPANY BRANCH", pl, 7);
        }
        JSONObject vendor = SndData.obj(header, "vendor_snapshot");
        if (show("show_vendor")) block(leftX, h - 154, colW, "VENDOR", partyLines(vendor == null ? new JSONObject() : vendor), 7);
        if (show("show_reference")) {
            List<String> ref = new ArrayList<>();
            ref.add("QUOTATION DATE: " + date(SndData.s(header, "quotation_date")));
            ref.add(SndData.s(header, "quotation_reference"));
            block(rightX, h - 86, 184, "REFERENCE DETAILS", ref, 3);
        }
        if (show("show_old_po")) {
            List<String> old = new ArrayList<>();
            old.add(SndData.s(header, "old_po_reference"));
            block(rightX, h - 136, 184, "OLD PO DETAILS", old, 2);
        }
        JSONObject ship = SndData.obj(header, "ship_to_snapshot");
        if (ship == null || ship.length() == 0) ship = defaultPlant();
        if (show("show_ship_to")) block(rightX, h - 174, 184, "SHIP TO", partyLines(ship), 7);

        float yStrip = h - 284;
        float[] sw = {78, 106, 82, 93, w - left - right - 359};
        String[] st = {"REQUISITIONER", "SHIP VIA", "INCOTERM", "DELIVERY DATE", "PAYMENT TERM"};
        String[] sv = {SndData.s(header, "requisitioner"), SndData.s(header, "ship_via"), SndData.s(header, "incoterm"),
            date(SndData.s(header, "delivery_date")), SndData.s(header, "payment_term")};
        float x = left;
        for (int i = 0; i < sw.length; i++) {
            bar(x, yStrip, sw[i], st[i], 14);
            g.rect(x, yStrip - 34, sw[i], 20, true, false);
            List<String> two = wrapLines(sv[i], sw[i] - 8, 6.6f, false, 3);
            if (two.size() <= 1) text(x + 4, yStrip - 27, sv[i], 6.6f, false, TEXT, sw[i] - 8);
            else {
                // long requisitioner / payment term: two lines inside the 20 pt cell instead of cutting the text
                text(x + 4, yStrip - 22.5f, two.get(0), 6.0f, false, TEXT, sw[i] - 8);
                String rest = two.size() > 2 ? two.get(1) + " " + two.get(2) : two.get(1);
                text(x + 4, yStrip - 30.5f, rest, 6.0f, false, TEXT, sw[i] - 8);
            }
            x += sw[i];
        }

        float yItem = yStrip - 45;
        int drawn = 0, total = items.size();
        for (int index = 0; index < total; index++) {
            JSONObject item = items.get(index);
            float need = itemBlockHeight(item, FIRST_HISTORY_ROWS);
            boolean isLast = index == total - 1;
            float reserve = isLast && total > 1 ? GRAND_TOTAL_HEIGHT : 0;
            if (index > 0 && yItem - need - reserve < FIRST_PAGE_ITEM_BOTTOM) break;
            float rowBottom = itemRow(item, yItem, left, right, w);
            List<JSONObject> history = new ArrayList<>();
            int rendered = itemSections(item, rowBottom, left, right, w, 4, Math.max(FIRST_PAGE_ITEM_BOTTOM, yItem - need), FIRST_HISTORY_ROWS, history);
            if (rendered < history.size()) overflow.add(new Object[]{item, new ArrayList<>(history.subList(rendered, history.size()))});
            yItem = yItem - need - ITEM_GAP;
            drawn++;
        }
        if (drawn == total && total > 1 && yItem - GRAND_TOTAL_HEIGHT + ITEM_GAP >= FIRST_PAGE_ITEM_BOTTOM - 2) {
            grandTotal(yItem + ITEM_GAP - 2, left, right, w);
            grandOut[0] = true;
        }

        int remarkColor = color("remark", Color.parseColor("#9A3412"));
        text(left + 2, 236, "Remarks:", 7.6f, true, accent());
        rules();
        g.fill = fillOrWhite("remark_fill");
        g.rect(left, 211, 386, 21, true, true);
        String remarks = SndData.s(header, "remarks").isEmpty() ? "PART WILL BE SUPPLIED AS PER DRAWING." : SndData.s(header, "remarks");
        if (g.width(remarks, 7.4f, true) <= 378) text(left + 4, 220, remarks, 7.4f, true, remarkColor, 378);
        else {
            List<String> rl = wrapLines(remarks, 378, 6.4f, true, 3);
            text(left + 4, 224.5f, rl.isEmpty() ? "" : rl.get(0), 6.4f, true, remarkColor, 378);
            String rest = rl.size() > 2 ? rl.get(1) + " " + rl.get(2) : rl.size() > 1 ? rl.get(1) : "";
            text(left + 4, 215.5f, rest, 6.4f, true, remarkColor, 378);
        }
        if (show("show_special_instructions")) {
            bar(left, 206, 386, "COMMENTS OR SPECIAL INSTRUCTIONS", 14);
            String si = SndData.has(header, "special_instructions") ? header.optString("special_instructions") : DEFAULT_SPECIAL_INSTRUCTIONS;
            specialLines(left + 2, 181, si, 374, 100);
        }
        float tx = 417, ytot = 205;
        rules();
        text(tx, 237, "PO LINES", 6.9f, true, TEXT);
        g.rect(tx + 55, 232, 95, 13, true, false);
        text(tx + 61, 236, String.valueOf(items.size()), 6.8f, true, TEXT);
        text(tx, 221, "TOTAL QTY", 6.9f, true, TEXT);
        g.rect(tx + 55, 216, 95, 13, true, false);
        fit(tx + 61, 220, quantityTotals(items), 6.8f, true, TEXT, 88);
        String[][] rows = {{"SUBTOTAL", "subtotal"}, {"CGST 9%", "cgst_amount"}, {"SGST 9%", "sgst_amount"}, {"IGST", "igst_amount"}, {"OTHER", "other_amount"}};
        for (String[] r : rows) {
            text(tx, ytot, r[0], 6.9f, false, TEXT);
            g.rect(tx + 55, ytot - 5, 95, 13, true, false);
            fit(tx + 61, ytot - 1, money(SndData.n(header, r[1])), 6.8f, false, TEXT, 88);
            ytot -= 16;
        }
        String cur = SndData.s(header, "currency").isEmpty() ? "INR" : SndData.s(header, "currency").toUpperCase(Locale.ROOT);
        text(tx, ytot, "TOTAL", 8.0f, true, TEXT);
        fit(tx + 61, ytot, cur + " " + money(SndData.n(header, "grand_total")), 8.0f, true, TEXT, w - right - tx - 61);

        String signatory = SndData.s(layout, "company_name");
        if (signatory.isEmpty()) signatory = SndData.s(plant, "name");
        if (signatory.isEmpty()) signatory = SndData.s(plant, "branch_name");
        if (signatory.isEmpty()) signatory = PLANT[0];
        if ("APPROVED".equalsIgnoreCase(SndData.s(header, "approval_status")) && show("show_approval_stamp")) approverStamp(w);
        else {
            text(w - 143, 81, "Authorised Signatory", 7.0f, true, TEXT);
            text(w - 174, 67, signatory, 6.2f, false, TEXT, 170);
        }
        g.centre(w / 2, 47, "If you have any questions about this purchase order, please contact", 6.0f, false, GREY);
        String footer = SndData.s(layout, "footer_text").isEmpty() ? "FSI · connect@fourstarindustries.com" : SndData.s(layout, "footer_text");
        g.centre(w / 2, 36, footer, 6.0f, false, GREY);
        showPage();
        return Math.max(drawn, 1);
    }

    /** _special_lines: each numbered instruction on its own line (wrapping long ones). */
    private float specialLines(float x, float y, String text, float width, float bottom) {
        for (String raw : (text == null ? "" : text).split("\\r?\\n")) {
            String line = raw.trim();
            if (line.isEmpty()) continue;
            if (y < bottom) break;
            y = wrap(x, y, line, width, 6.2f, 9.6f, false, 2);
        }
        return y;
    }

    private void approverStamp(float pageWidth) {
        String approver = SndData.s(header, "approver_employee_name");
        if (approver.isEmpty()) approver = SndData.s(header, "approver_name");
        if (approver.isEmpty()) approver = SndData.s(header, "approved_by_name");
        String code = SndData.s(header, "approver_employee_code");
        String approvedAt = approvalDateTime(SndData.s(header, "approved_at"));
        if (approver.isEmpty()) approver = code.isEmpty() ? "Approver record unavailable" : code;
        String identity = "Approver: " + approver + (!code.isEmpty() && !approver.toLowerCase(Locale.ROOT).contains(code.toLowerCase(Locale.ROOT)) ? " · " + code : "");
        float x = pageWidth - 185, y = 55, bw = 155, bh = 62;
        int green = Color.parseColor("#2E7D32");
        g.stroke = green; g.lw = 1.15f;
        g.roundRect(x, y, bw, bh, 6);
        g.centre(x + bw / 2, y + 45, "APPROVED", 10.5f, true, green);
        fit(x + 8, y + 30, identity, 6.4f, true, Color.parseColor("#1F2937"), bw - 16);
        if (!approvedAt.isEmpty()) text(x + 8, y + 17, "Date / Time: " + approvedAt, 5.7f, false, Color.parseColor("#374151"), bw - 16);
        text(x + 8, y + 7, "QCMS DIGITAL APPROVAL", 5.2f, true, GREY, bw - 16);
        rules();
    }

    // ------------------------------------------------------------------ item blocks
    private float itemRow(JSONObject item, float yTop, float left, float right, float pageWidth) {
        float[] widths = {34, 184, 44, 62, 42, 40, 70, 63};
        String[] titles = {"LINE", "ITEM #", "QTY", "UNIT PRICE", "UNIT", "GST%", "GST AMOUNT", "TOTAL"};
        float x = left;
        for (int i = 0; i < widths.length; i++) { bar(x, yTop, widths[i], titles[i], 14); x += widths[i]; }
        float rowTop = yTop - 14, rowBottom = rowTop - 42;
        rules();
        g.fill = WHITE;
        g.rect(left, rowBottom, pageWidth - left - right, 42, true, true);
        String itemNo = SndData.s(item, "item_no").isEmpty() ? SndData.s(item, "fsi_part_number_snapshot") : SndData.s(item, "item_no");
        String display = joinNonEmpty(" ", itemNo, SndData.s(item, "item_description"));
        String[] vals = {item.optInt("_line_no", 1) + "/" + item.optInt("_line_count", 1), display,
            qty2(SndData.n(item, "quantity")), money(SndData.n(item, "unit_price")), SndData.s(item, "uom"),
            g(SndData.n(item, "gst_percent")) + "%", money(SndData.n(item, "gst_amount")), money(SndData.n(item, "line_total"))};
        x = left;
        for (int idx = 0; idx < widths.length; idx++) {
            float sw = widths[idx];
            if (idx == 0) {
                text(x + 5, rowTop - 20, vals[0], 7.6f, true, accent(), sw - 8);
            } else if (idx == 1) {
                float max = sw - 10;
                List<String> lines = wrapLines(display, max, 6.7f, true, 2);
                boolean two = lines.size() > 1 || g.width(display, 6.7f, true) > max;
                if (!two) text(x + 5, rowTop - 10, display, 6.7f, true, TEXT, max);
                else {
                    // R30 app: long item text wraps to a second line instead of being cut
                    text(x + 5, rowTop - 9, lines.get(0), 6.4f, true, TEXT, max);
                    String rest = display.substring(Math.min(display.length(), lines.get(0).length())).trim();
                    text(x + 5, rowTop - 16.6f, rest, 6.4f, true, TEXT, max);
                }
                String partDesc = SndData.s(item, "part_description_master");
                if (!partDesc.isEmpty()) text(x + 5, two ? rowTop - 25.5f : rowTop - 21, "Part Description: " + partDesc, 5.7f, false, Color.parseColor("#374151"), max);
                String hsn = SndData.s(item, "hsn_sac_code");
                String rm = SndData.s(item, "rm_section");
                String code = joinNonEmpty(" · ", hsn.isEmpty() ? "" : "HSN / SAC: " + hsn, rm.isEmpty() ? "" : "RM Section: " + rm);
                if (!code.isEmpty()) text(x + 5, rowTop - 35, code, 5.6f, true, Color.parseColor("#4B5563"), max);
            } else {
                fit(x + 4, rowTop - 20, vals[idx], 6.7f, false, TEXT, sw - 8);
            }
            x += sw;
        }
        return rowBottom;
    }

    private static List<JSONObject> sourceRows(JSONObject item) {
        List<JSONObject> out = new ArrayList<>();
        JSONArray raw = SndData.arr(item, "customer_source_rows");
        for (int i = 0; i < raw.length(); i++) if (raw.optJSONObject(i) != null) out.add(raw.optJSONObject(i));
        return out;
    }

    private float customerReferenceHeight(JSONObject item) {
        int shown = Math.min(Math.max(sourceRows(item).size(), 1), 4);
        return 30f + shown * 14f;
    }

    private float customerReference(JSONObject item, float top, float left, float right, float pageWidth) {
        float totalW = pageWidth - left - right;
        List<JSONObject> rows = sourceRows(item);
        List<JSONObject> shown = rows.subList(0, Math.min(4, rows.size()));
        float height = customerReferenceHeight(item);
        float bottom = top - height;
        bar(left, top, totalW, "PO SOURCE REFERENCE · INTERNAL COPY - CUSTOMER DETAILS - NOT FOR SUPPLIER" + lineSuffix(item), 15);
        float y = top - 15;
        float[] widths = {130, 55, 245, 72, totalW - 502};
        String[] titles = {"CUSTOMER PO NO.", "POS", "PART DESCRIPTION", "QTY", "UOM"};
        float x = left;
        for (int i = 0; i < widths.length; i++) {
            rules(); g.fill = fillOrWhite("head_fill"); g.rect(x, y - 14, widths[i], 14, true, true);
            text(x + 3, y - 9.8f, titles[i], 5.0f, true, DARK, widths[i] - 6);
            x += widths[i];
        }
        y -= 14;
        if (shown.isEmpty()) {
            g.fill = WHITE; g.rect(left, y - 14, totalW, 14, true, true);
            text(left + 4, y - 9.8f, "No linked order / schedule source stored for this historical PO line.", 5.3f, false, GREY, totalW - 8);
        } else {
            for (JSONObject row : shown) {
                x = left;
                String[] values = {SndData.s(row, "customer_po_number"), SndData.s(row, "po_position"), SndData.s(row, "part_description"),
                    qty3(SndData.n(row, "quantity")), SndData.s(row, "uom")};
                for (int i = 0; i < widths.length; i++) {
                    g.fill = WHITE; g.rect(x, y - 14, widths[i], 14, true, true);
                    text(x + 3, y - 9.8f, values[i], 5.0f, false, TEXT, widths[i] - 6);
                    x += widths[i];
                }
                y -= 14;
            }
            if (rows.size() > shown.size()) {
                text(left + 4, bottom + 3, "+ " + (rows.size() - shown.size()) + " additional linked source(s) retained in QCMS genealogy.", 5.0f, true, accent(), totalW - 8);
            }
        }
        return bottom;
    }

    /** _technical_pairs: supplier-facing technical data in display order. */
    static List<String[]> technicalPairs(JSONObject item, String poType, int limit) {
        List<String[]> out = new ArrayList<>();
        JSONArray raw = SndData.arr(item, "technical_data_snapshot");
        String kind = poType == null ? "" : poType.toUpperCase(Locale.ROOT);
        List<String> rmAllowed = java.util.Arrays.asList("raw material type", "raw material section", "material grade", "section size", "supplier rm item code", "supplier lead time");
        List<String> rmForgingOnly = java.util.Arrays.asList("supplier forging part no.", "supplier forging part no", "forge wt", "gross wt", "input wt", "forging route");
        String[] priorityNames = {"Raw Material Type", "Raw Material Section", "Material Grade", "Section Size", "Supplier RM Item Code", "Supplier Lead Time", "Forge wt", "Gross wt", "Input wt", "Forging Route"};
        List<Object[]> prepared = new ArrayList<>();
        for (int idx = 0; idx < raw.length(); idx++) {
            JSONObject row = raw.optJSONObject(idx);
            if (row == null) continue;
            String heading = SndData.s(row, "heading"), value = SndData.s(row, "value");
            if (heading.isEmpty() || value.isEmpty()) continue;
            String key = heading.toLowerCase(Locale.ROOT);
            String source = SndData.s(row, "source").toUpperCase(Locale.ROOT);
            if (kind.equals("RAW_MATERIAL")) {
                if (source.equals("STANDARD") && !rmAllowed.contains(key)) continue;
                if (!source.equals("CUSTOM") && rmForgingOnly.contains(key)) continue;
            }
            if (key.equals("raw material section")) { heading = "Raw Material Type"; key = "raw material type"; }
            int pr = 100 + idx;
            for (int i = 0; i < priorityNames.length; i++) if (priorityNames[i].toLowerCase(Locale.ROOT).equals(key)) { pr = i; break; }
            prepared.add(new Object[]{pr, heading, value});
        }
        prepared.sort((a, b) -> Integer.compare((Integer) a[0], (Integer) b[0]));
        for (int i = 0; i < prepared.size() && i < limit; i++) out.add(new String[]{(String) prepared.get(i)[1], (String) prepared.get(i)[2]});
        return out;
    }

    private String poType() { return SndData.s(header, "po_type").isEmpty() ? "FORGING" : SndData.s(header, "po_type").toUpperCase(Locale.ROOT); }

    private float technicalHeight(JSONObject item) {
        int pairs = technicalPairs(item, poType(), 12).size();
        int rows = Math.max(1, (pairs + 2) / 3);
        return Math.max(42f, 22f + rows * 13f);
    }

    private void technical(JSONObject item, float top, float bottom, float left, float right, float pageWidth) {
        float totalW = pageWidth - left - right;
        boolean isRm = "RAW_MATERIAL".equals(poType());
        String title = isRm ? "RAW MATERIAL DETAILS & SUPPLIER TECHNICAL DATA" : "RAW MATERIAL / FORGING PARAMETERS & SUPPLIER TECHNICAL DATA";
        rules(); g.fill = WHITE; g.rect(left, bottom, totalW, Math.max(top - bottom, 0), true, true);
        bar(left, top, totalW, title + lineSuffix(item), 15);
        List<String[]> pairs = technicalPairs(item, poType(), 12);
        if (pairs.isEmpty()) {
            text(left + 5, top - 29, "No controlled supplier technical data configured", 5.8f, false, GREY, 310);
            return;
        }
        float rowH = 13f, innerLeft = left + 3, innerW = totalW - 6, pairW = innerW / 3f, labelW = pairW * 0.43f, firstRowTop = top - 17;
        rules();
        for (int r = 0; r < (pairs.size() + 2) / 3; r++) {
            float yTop = firstRowTop - r * rowH, yBottom = yTop - rowH;
            if (yBottom < bottom + 2) break;
            for (int col = 0; col < 3; col++) {
                int pi = r * 3 + col;
                float px = innerLeft + col * pairW;
                if (pi >= pairs.size()) { g.fill = WHITE; g.rect(px, yBottom, pairW, rowH, true, true); continue; }
                g.fill = fillOrWhite("label_fill"); g.rect(px, yBottom, labelW, rowH, true, true);
                g.fill = WHITE; g.rect(px + labelW, yBottom, pairW - labelW, rowH, true, true);
                text(px + 3, yBottom + 4.1f, pairs.get(pi)[0], 5.2f, true, Color.parseColor("#30363B"), labelW - 6);
                fit(px + labelW + 3, yBottom + 4.1f, pairs.get(pi)[1], 5.2f, false, TEXT, pairW - labelW - 6);
            }
        }
    }

    static List<JSONObject> priceHistoryRows(JSONObject item) {
        List<JSONObject> rows = new ArrayList<>();
        JSONArray raw = SndData.arr(item, "price_history_snapshot");
        for (int i = 0; i < raw.length(); i++) if (raw.optJSONObject(i) != null) rows.add(raw.optJSONObject(i));
        rows.sort((a, b) -> {
            int c = SndData.s(a, "start_date").compareTo(SndData.s(b, "start_date"));
            if (c != 0) return c;
            String ea = SndData.s(a, "end_date").isEmpty() ? "9999-12-31" : SndData.s(a, "end_date");
            String eb = SndData.s(b, "end_date").isEmpty() ? "9999-12-31" : SndData.s(b, "end_date");
            return ea.compareTo(eb);
        });
        return rows;
    }

    private int priceHistory(JSONObject item, List<JSONObject> history, float top, float bottom, float left, float right, float pageWidth, int maxRows) {
        String itemNo = SndData.s(item, "item_no").isEmpty() ? SndData.s(item, "fsi_part_number_snapshot") : SndData.s(item, "item_no");
        float totalW = pageWidth - left - right;
        bar(left, top, totalW, "PRICE REVISION HISTORY · FSI PART " + itemNo + lineSuffix(item), 15);
        float y = top - 15;
        float[] widths = {92, 92, 100, totalW - 284};
        String[] headers = {"START DATE", "END DATE", "PRICE", "REMARK"};
        float x = left;
        for (int i = 0; i < widths.length; i++) {
            rules(); g.fill = fillOrWhite("head_fill"); g.rect(x, y - 15, widths[i], 15, true, true);
            text(x + 3, y - 10.4f, headers[i], 5.4f, true, DARK, widths[i] - 6);
            x += widths[i];
        }
        y -= 15;
        int available = Math.max((int) Math.floor((y - bottom) / 15f), 0);
        int count = Math.min(history.size(), Math.min(maxRows, available));
        if (count == 0 && history.isEmpty() && y - 15 >= bottom) {
            g.fill = WHITE; g.rect(left, y - 15, totalW, 15, true, true);
            text(left + 4, y - 10.5f, "No controlled price revision history is recorded for this Supplier / FSI Part.", 5.8f, false, GREY, totalW - 8);
            return 0;
        }
        for (int r = 0; r < count; r++) {
            JSONObject row = history.get(r);
            x = left;
            String price = SndData.has(row, "price") ? money(SndData.n(row, "price")) : "-";
            String[] vals = {date(SndData.s(row, "start_date")), SndData.s(row, "end_date").isEmpty() ? "CURRENT" : date(SndData.s(row, "end_date")),
                price, SndData.s(row, "remarks").isEmpty() ? SndData.s(row, "remark") : SndData.s(row, "remarks")};
            for (int i = 0; i < widths.length; i++) {
                g.fill = WHITE; g.rect(x, y - 15, widths[i], 15, true, true);
                text(x + 3, y - 10.5f, vals[i], 5.35f, false, TEXT, widths[i] - 6);
                x += widths[i];
            }
            y -= 15;
        }
        int remaining = history.size() - count;
        if (remaining > 0 && y - 12 >= bottom) {
            text(left + 4, y - 9, "Continued on next controlled item page · " + remaining + " more revision(s)", 5.6f, true, accent(), totalW - 8);
        }
        return count;
    }

    private float historyBlockHeight(JSONObject item, int rows) {
        if (!show("show_price_history")) return 0f;
        List<JSONObject> history = priceHistoryRows(item);
        int shown = history.isEmpty() ? 1 : Math.min(history.size(), rows);
        return 4 + 15 + 15 + 15f * shown;
    }

    private float itemBlockHeight(JSONObject item, int historyRows) {
        float height = 56f;
        if (show("show_source_reference")) height += customerReferenceHeight(item);
        if (show("show_technical")) height += technicalHeight(item);
        return height + historyBlockHeight(item, historyRows);
    }

    /** _item_sections: source reference, technical data and price history (each optional). Fills history; returns rows drawn. */
    private int itemSections(JSONObject item, float top, float left, float right, float w, float gap, float historyBottom, int maxRows, List<JSONObject> historyOut) {
        float y = top;
        if (show("show_source_reference")) y = customerReference(item, y, left, right, w);
        if (show("show_technical")) {
            float bottom = y - technicalHeight(item);
            technical(item, y, bottom, left, right, w);
            y = bottom;
        }
        if (!show("show_price_history")) return 0;
        historyOut.addAll(priceHistoryRows(item));
        return priceHistory(item, historyOut, y - gap, historyBottom, left, right, w, maxRows);
    }

    private void grandTotal(float yTop, float left, float right, float pageWidth) {
        float totalW = pageWidth - left - right;
        float[] widths = {70, 150, 100, 90, totalW - 410};
        String[] titles = {"PO LINES", "TOTAL QTY", "SUBTOTAL", "GST", "GRAND TOTAL"};
        double subtotal = SndData.n(header, "subtotal");
        if (subtotal == 0) for (JSONObject i : items) subtotal += SndData.n(i, "line_total");
        double gst = SndData.n(header, "cgst_amount") + SndData.n(header, "sgst_amount") + SndData.n(header, "igst_amount");
        if (gst == 0) for (JSONObject i : items) gst += SndData.n(i, "gst_amount");
        double grand = SndData.n(header, "grand_total");
        if (grand == 0) grand = subtotal + gst + SndData.n(header, "other_amount");
        String cur = SndData.s(header, "currency").isEmpty() ? "INR" : SndData.s(header, "currency");
        String[] values = {String.valueOf(items.size()), quantityTotals(items), money(subtotal), money(gst), cur + " " + money(grand)};
        bar(left, yTop, totalW, "GRAND TOTAL · ALL PO LINES", 14);
        float y = yTop - 14, x = left;
        for (int i = 0; i < widths.length; i++) {
            rules(); g.fill = fillOrWhite("head_fill"); g.rect(x, y - 12, widths[i], 12, true, true);
            text(x + 3, y - 8.6f, titles[i], 5.6f, true, DARK, widths[i] - 6);
            g.fill = WHITE; g.rect(x, y - 26, widths[i], 14, true, true);
            fit(x + 3, y - 21.5f, values[i], 7.2f, true, accent(), widths[i] - 6);
            x += widths[i];
        }
    }

    // ------------------------------------------------------------------ continuation pages
    private void continuationHeader(String title) {
        newPage();
        logo();
        g.right(W - 28, H - 33, title, 16.5f, true, accent());
        rules();
        text(W - 176, H - 51, "PO # " + SndData.s(header, "po_number"), 7.2f, true, TEXT, 148);
        text(W - 176, H - 64, "DATE " + date(SndData.s(header, "order_date")), 7.2f, false, TEXT);
        String amendment = amendmentCaption(header);
        if (!amendment.isEmpty()) g.right(W - 28, H - 76, amendment, 6.0f, true, accent());   // R37b
    }

    /** R37b: "Amendment No. N  ·  Amendment Date dd-mm-yyyy  ·  Effective Date dd-mm-yyyy" or "" when not amended. */
    static String amendmentCaption(JSONObject header) {
        int no = (int) Math.round(SndData.n(header, "amendment_no"));
        if (no <= 0) return "";
        StringBuilder out = new StringBuilder("Amendment No. ").append(no);
        if (!SndData.s(header, "amendment_date").isEmpty()) out.append("  \u00b7  Amendment Date ").append(date(SndData.s(header, "amendment_date")));
        if (!SndData.s(header, "amendment_effective_date").isEmpty()) out.append("  \u00b7  Effective Date ").append(date(SndData.s(header, "amendment_effective_date")));
        return out.toString();
    }

    private void footer(String text) { g.centre(W / 2, 27, text, 5.8f, false, GREY); }

    private void historyContinuationPages(JSONObject item, List<JSONObject> history) {
        List<JSONObject> remaining = new ArrayList<>(history);
        while (!remaining.isEmpty()) {
            continuationHeader("PURCHASE ORDER · PRICE HISTORY CONTINUED");
            String itemNo = SndData.s(item, "item_no").isEmpty() ? SndData.s(item, "fsi_part_number_snapshot") : SndData.s(item, "item_no");
            text(28, H - 88, "FSI PART: " + itemNo + " · " + SndData.s(item, "item_description"), 7.2f, true, accent(), W - 56);
            int rendered = priceHistory(item, remaining, H - 102, 50, 28, 28, W, HISTORY_ONLY_ROWS);
            footer("QCMS controlled Purchase Order · Price revision history is item-specific and supplier-specific.");
            showPage();
            if (rendered <= 0) break;
            remaining = new ArrayList<>(remaining.subList(rendered, remaining.size()));
        }
    }

    private void continuationItems(List<JSONObject> rest, boolean grandTotal) {
        String foot = "QCMS controlled continuation · Technical data and Price Revision History are item-specific and supplier-specific.";
        boolean open = false;
        float y = 0, left = 28, right = 28;
        List<Object[]> pending = new ArrayList<>();
        for (JSONObject item : rest) {
            float need = itemBlockHeight(item, CONT_HISTORY_ROWS);
            if (open && y - need < 60) {
                footer(foot); showPage(); open = false;
                for (Object[] p : pending) historyContinuationPages((JSONObject) p[0], castList(p[1]));
                pending.clear();
            }
            if (!open) { continuationHeader("PURCHASE ORDER · ITEMS CONTINUED"); y = H - 92; open = true; }
            float rowBottom = itemRow(item, y, left, right, W);
            List<JSONObject> history = new ArrayList<>();
            int rendered = itemSections(item, rowBottom, left, right, W, 4, Math.max(50, y - need), CONT_HISTORY_ROWS, history);
            if (rendered < history.size()) pending.add(new Object[]{item, new ArrayList<>(history.subList(rendered, history.size()))});
            y = y - need - ITEM_GAP;
        }
        if (open) {
            if (grandTotal && items.size() > 1) {
                if (y - GRAND_TOTAL_HEIGHT < 50) {
                    footer(foot); showPage();
                    continuationHeader("PURCHASE ORDER · ITEMS CONTINUED"); y = H - 92;
                }
                grandTotal(y + ITEM_GAP - 2, left, right, W);
            }
            footer(foot); showPage();
        }
        for (Object[] p : pending) historyContinuationPages((JSONObject) p[0], castList(p[1]));
    }

    // ------------------------------------------------------------------ standard terms (FSI/703/F04), portrait A4
    private static final float T_SIZE = 6.9f, T_LEAD = 8.3f, T_GAP = 3.2f, T_LEFT = 24f, T_RIGHT = 24f, T_BOTTOM = 34f;

    /** One wrapped terms line: words with a bold flag (clause headings print bold). */
    private static final class TLine { final List<String> words = new ArrayList<>(); final List<Boolean> bold = new ArrayList<>(); boolean paragraphEnd; }

    private List<TLine> termLines(float width) {
        List<TLine> lines = new ArrayList<>();
        java.util.regex.Pattern heading = java.util.regex.Pattern.compile("^((?:\\d+\\.|\\([a-z]\\))\\s+([^:]{1,90}):)");
        float space = g.width(" ", T_SIZE, false);
        for (String para : SndTerms.PARAGRAPHS) {
            java.util.regex.Matcher m = heading.matcher(para);
            int boldChars = m.find() && m.group(2).equals(m.group(2).toUpperCase(Locale.ROOT)) ? m.group(1).length() : 0;
            String[] words = para.split(" ");
            int pos = 0;
            TLine line = new TLine();
            float lineW = 0;
            for (String word : words) {
                if (word.isEmpty()) { pos++; continue; }
                boolean b = pos < boldChars;
                pos += word.length() + 1;
                float ww = g.width(word, T_SIZE, b);
                float add = line.words.isEmpty() ? ww : space + ww;
                if (!line.words.isEmpty() && lineW + add > width) {
                    lines.add(line);
                    line = new TLine();
                    lineW = 0;
                    add = ww;
                }
                line.words.add(word);
                line.bold.add(b);
                lineW += add;
            }
            if (!line.words.isEmpty()) { line.paragraphEnd = true; lines.add(line); }
        }
        return lines;
    }

    private void termsHeader(boolean first) {
        newPage();
        logo();
        String plantName = SndData.s(plantSnapshot(), "name");
        if (plantName.isEmpty()) plantName = SndData.s(plantSnapshot(), "branch_name");
        if (plantName.isEmpty()) plantName = PLANT[0];
        g.right(W - 28, H - 34, "PURCHASE ORDER", 20, true, TEXT);
        // PLANT bar + name (left) and the live DATE / PO # cells (right), like the controlled template
        g.fill = accent(); g.rect(28, H - 74, 230, 10, false, true);
        text(32, H - 71.6f, "PLANT", 6.6f, true, WHITE);
        text(32, H - 83, plantName, 6.6f, false, TEXT, 222);
        rules();
        text(W - 137, H - 58, "DATE", 7.0f, false, TEXT);
        g.rect(W - 91, H - 61, 62, 11, true, false);
        fit(W - 86, H - 58, date(SndData.s(header, "order_date")), 6.8f, false, TEXT, 54);
        text(W - 137, H - 72, "PO #", 7.0f, false, TEXT);
        g.rect(W - 91, H - 75, 62, 11, true, false);
        fit(W - 86, H - 72, SndData.s(header, "po_number"), 6.8f, false, TEXT, 54);
        if (first) {
            g.centre(W / 2, H - 104, SndTerms.COMPANY, 12.5f, true, TEXT);
            g.centre(W / 2, H - 120, SndTerms.TITLE, 12.5f, true, TEXT);
            text(80, H - 135, SndTerms.FORMAT, 10f, true, TEXT);
            g.centre(W / 2 + 40, H - 135, SndTerms.REVISION, 10f, true, TEXT);
            g.right(W - 60, H - 135, SndTerms.DATE, 10f, true, TEXT);
        }
    }

    private void termsPages() {
        float width = W - T_LEFT - T_RIGHT;
        g = new Pg(new Canvas()); // measuring only (no page open)
        List<TLine> lines = termLines(width);
        // paginate: first page body starts below the big title block
        List<int[]> pages = new ArrayList<>();
        int i = 0;
        boolean first = true;
        while (i < lines.size()) {
            float y = first ? H - 150 : H - 96;
            int start = i;
            while (i < lines.size()) {
                float need = T_LEAD + (lines.get(i).paragraphEnd ? T_GAP : 0);
                if (y < T_BOTTOM && i > start) break;
                y -= need;
                i++;
            }
            pages.add(new int[]{start, i});
            first = false;
        }
        int total = pages.size();
        for (int p = 0; p < total; p++) {
            termsHeader(p == 0);
            float y = p == 0 ? H - 150 : H - 96;
            for (int k = pages.get(p)[0]; k < pages.get(p)[1]; k++) {
                TLine line = lines.get(k);
                float x = T_LEFT;
                float space = g.width(" ", T_SIZE, false);
                for (int wi = 0; wi < line.words.size(); wi++) {
                    String word = line.words.get(wi);
                    boolean b = line.bold.get(wi);
                    g.string(x, y, word, T_SIZE, b, TEXT);
                    x += g.width(word, T_SIZE, b) + space;
                }
                y -= T_LEAD + (line.paragraphEnd ? T_GAP : 0);
            }
            float fy = 12;
            g.string(18, fy, "STANDARD PURCHASE ORDER TERMS AND CONDITIONS", 6.3f, false, TEXT);
            g.string(237, fy, "FSI/703/F04", 6.3f, false, TEXT);
            g.string(315, fy, SndTerms.DATE, 6.3f, false, TEXT);
            g.string(500, fy, "Terms " + (p + 1) + " of " + total, 6.3f, false, TEXT);
            showPage();
        }
    }
}
