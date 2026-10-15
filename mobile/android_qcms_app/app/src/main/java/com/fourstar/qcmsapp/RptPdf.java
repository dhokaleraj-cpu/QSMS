package com.fourstar.qcmsapp;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.graphics.pdf.PdfDocument;
import android.text.TextPaint;

import java.io.ByteArrayOutputStream;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/**
 * R33 · Draws an RptDoc as the website's controlled A4 PDF (core/reporting.py _PageNumberCanvas + Design B):
 * FSI logo and company under it, centred report title (or HEAT NUMBER / RMTC NUMBER), plant, printed time and
 * app version on the right, teal rule, footer "Version … | Page i of N" on every page. Tables repeat their header
 * rows on a new page and never split a row. Two passes: the first only counts pages.
 */
final class RptPdf {
    static final String WEB_VERSION = "4.14.49";
    static final String FOOTER = "QUALITY CONTROL MONITORING SYSTEM | Developed by Rajesh Dhokale | dhokaleraj@icloud.com | Copyrights by STAWN";
    static final float MM = 72f / 25.4f;
    private static final int BORDER = Color.parseColor("#AFC3D4");
    private static final int MUTED = Color.parseColor("#617386");
    private static final int LABEL = Color.parseColor("#333333");
    private static final int INK = RptDoc.INK;
    private static final float PAD_LR = 2.6f, PAD_TB = 3.6f, FRAME_PAD = 6f;

    private final RptDoc d;
    private final float pw, ph;
    private final float x0, top, bottom, frameW;
    private final TextPaint regular = new TextPaint(Paint.ANTI_ALIAS_FLAG);
    private final TextPaint bold = new TextPaint(Paint.ANTI_ALIAS_FLAG);
    private final TextPaint italic = new TextPaint(Paint.ANTI_ALIAS_FLAG);
    private final TextPaint boldItalic = new TextPaint(Paint.ANTI_ALIAS_FLAG);
    private final Paint fill = new Paint();
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final String printed;

    private boolean dry;
    private int pageNo, totalPages;
    private PdfDocument pdf;
    private PdfDocument.Page page;
    private Canvas c;
    private float y;

    private RptPdf(RptDoc d) {
        this.d = d;
        pw = d.landscape ? 842f : 595f;
        ph = d.landscape ? 595f : 842f;
        x0 = d.edgeMm * MM + FRAME_PAD;
        top = d.topMm * MM + FRAME_PAD;
        bottom = ph - d.bottomMm * MM - FRAME_PAD;
        frameW = pw - 2 * x0;
        Typeface sans = Typeface.create(Typeface.SANS_SERIF, Typeface.NORMAL);
        regular.setTypeface(sans);
        bold.setTypeface(Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD));
        italic.setTypeface(Typeface.create(Typeface.SANS_SERIF, Typeface.ITALIC));
        boldItalic.setTypeface(Typeface.create(Typeface.SANS_SERIF, Typeface.BOLD_ITALIC));
        stroke.setStyle(Paint.Style.STROKE);
        printed = new SimpleDateFormat("dd-MM-yyyy hh:mm a", Locale.ENGLISH).format(new Date()).replace("am", "AM").replace("pm", "PM");
    }

    static byte[] render(RptDoc d) throws Exception {
        RptPdf r = new RptPdf(d);
        r.dry = true;
        r.run();
        r.totalPages = r.pageNo;
        r.dry = false;
        r.pdf = new PdfDocument();
        try {
            r.run();
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            r.pdf.writeTo(out);
            return out.toByteArray();
        } finally {
            r.pdf.close();
        }
    }

    private void run() {
        pageNo = 0;
        page = null;
        c = null;
        newPage();
        if (d.blocks.isEmpty()) { regular.setTextSize(9); regular.setColor(INK); text("No data recorded for this report.", x0, y + 10, regular); }
        for (RptDoc.Block b : d.blocks) draw(b);
        finishPage();
    }

    // ------------------------------------------------------------------ pages
    private void newPage() {
        finishPage();
        pageNo++;
        if (!dry) {
            page = pdf.startPage(new PdfDocument.PageInfo.Builder((int) pw, (int) ph, pageNo).create());
            c = page.getCanvas();
            c.drawColor(Color.WHITE);
        }
        y = top;
    }

    private void finishPage() {
        if (pageNo == 0) return;
        if (!dry && page != null) {
            headerFooter();
            pdf.finishPage(page);
        }
        page = null;
        c = null;
    }

    private float room() { return bottom - y; }

    private void need(float h) { if (h > room() && y > top + 1) newPage(); }

    /** _PageNumberCanvas._draw_header_footer. */
    private void headerFooter() {
        boolean portrait = ph >= pw;
        float edge = (portrait ? 8 : 10) * MM;
        float hy = (portrait ? 27 : 29) * MM;            // header_y measured from the top
        float rightPanel = (portrait ? 48 : 63) * MM;
        Bitmap logo = SndLogo.bitmap();
        if (logo != null) {
            float bw = (portrait ? 26 : 28) * MM, bh = 13 * MM;
            float boxTop = hy - 6 * MM - bh;
            float s = Math.min(bw / logo.getWidth(), bh / logo.getHeight());
            float w = logo.getWidth() * s, h = logo.getHeight() * s;
            float lx = edge + (bw - w) / 2, ly = boxTop + (bh - h) / 2;
            c.drawBitmap(logo, null, new RectF(lx, ly, lx + w, ly + h), null);
        }
        bold.setColor(INK);
        bold.setTextSize(portrait ? 6.6f : 7.2f);
        text(d.company.isEmpty() ? "FOUR STAR INDUSTRIES" : d.company, edge, hy - 2.6f * MM, bold);

        float cl = edge + (portrait ? 36 : 40) * MM, cr = pw - edge - rightPanel - 3 * MM, cx = (cl + cr) / 2;
        if (!d.heatNumber.isEmpty()) {
            bold.setTextSize(portrait ? 12.5f : 14.5f);
            centred(cut("HEAT NUMBER: " + d.heatNumber, 40), cx, hy - 12.2f * MM, bold);
            bold.setTextSize(portrait ? 8.6f : 10f);
            centred(cut(!d.recordNumber.isEmpty() ? "RMTC NUMBER: " + d.recordNumber : d.title, 50), cx, hy - 7.0f * MM, bold);
            if (!d.reportLabel.isEmpty()) {
                regular.setColor(Color.parseColor("#555555"));
                regular.setTextSize(portrait ? 6.6f : 7.4f);
                centred(cut(d.reportLabel, 55), cx, hy - 3.2f * MM, regular);
            }
        } else {
            String[] t = splitTitle(d.title);
            bold.setTextSize(portrait ? 11.2f : 14f);
            centred(cut(t[0], 44), cx, hy - (t[1].isEmpty() ? 10.0f : 12.4f) * MM, bold);
            if (!t[1].isEmpty()) {
                bold.setTextSize(portrait ? 9.0f : 10.5f);
                centred(cut(t[1], 50), cx, hy - 7.0f * MM, bold);
            }
        }
        bold.setColor(Color.parseColor("#333333"));
        bold.setTextSize(portrait ? 7.4f : 8f);
        right("Plant: " + d.plantCode, pw - edge, hy - 13.2f * MM, bold);
        regular.setColor(Color.parseColor("#333333"));
        regular.setTextSize(portrait ? 6.8f : 7.4f);
        right("Printed: " + printed, pw - edge, hy - 9.0f * MM, regular);
        right("App Version: " + WEB_VERSION, pw - edge, hy - 4.8f * MM, regular);
        line(edge, hy - 1.2f * MM, pw - edge, hy - 1.2f * MM, d.accent, 1.6f);

        float fy = ph - 9.2f * MM;
        line(edge, fy, pw - edge, fy, BORDER, 0.45f);
        regular.setColor(MUTED);
        regular.setTextSize(portrait ? 6.4f : 7.0f);
        String foot = d.footer.isEmpty() ? FOOTER : d.footer;
        String pageText = "Version " + WEB_VERSION + " | Page " + pageNo + " of " + Math.max(totalPages, pageNo);
        float maxFoot = pw - 2 * edge - regular.measureText(pageText) - 12;
        text(fit(foot, maxFoot, regular), edge + 1 * MM, ph - 5.6f * MM, regular);
        right(pageText, pw - edge - 1 * MM, ph - 5.6f * MM, regular);
    }

    static String[] splitTitle(String title) {
        String t = title == null ? "" : title.trim();
        int dash = t.indexOf(" - ");
        if (dash >= 0) return new String[]{t.substring(0, dash).trim(), t.substring(dash + 3).trim()};
        if (t.length() <= 34) return new String[]{t, ""};
        int at = t.lastIndexOf(' ', 33);
        if (at < 18) at = 34;
        return new String[]{t.substring(0, at).trim(), t.substring(at).trim()};
    }

    private static String cut(String s, int n) { return s.length() > n ? s.substring(0, n) : s; }

    // ------------------------------------------------------------------ blocks
    private void draw(RptDoc.Block b) {
        if (b instanceof RptDoc.Bar) bar((RptDoc.Bar) b);
        else if (b instanceof RptDoc.Labeled) labeled((RptDoc.Labeled) b);
        else if (b instanceof RptDoc.Grid) grid((RptDoc.Grid) b);
        else if (b instanceof RptDoc.Conclusion) conclusion((RptDoc.Conclusion) b);
        else if (b instanceof RptDoc.Photos) photos((RptDoc.Photos) b);
        else if (b instanceof RptDoc.Chart) chart((RptDoc.Chart) b);
        else if (b instanceof RptDoc.Text) paragraph((RptDoc.Text) b);
        else if (b instanceof RptDoc.Space) { y += ((RptDoc.Space) b).mm * MM; if (y > bottom) newPage(); }
        else if (b instanceof RptDoc.Keep) need(((RptDoc.Keep) b).mm * MM);
        else if (b instanceof RptDoc.BendPanel) bendPanel((RptDoc.BendPanel) b);
        else if (b instanceof RptDoc.Signatures) signatures((RptDoc.Signatures) b);
    }

    /** _rmtc_section_bar: teal band with white capitals; light = teal text over a teal rule. */
    private void bar(RptDoc.Bar b) {
        boolean light = b.light;
        String style = b.fixedFill ? "fill" : d.barStyle;
        boolean outline = !light && "outline".equals(style);
        String t = b.fixedFill ? b.text : d.relabel(b.text);
        if (!light && "underline".equals(style)) { light = true; t = t.toUpperCase(Locale.ROOT); }
        if (!b.light && !b.keepCase) t = t.toUpperCase(Locale.ROOT);
        float size = b.fixedFill ? 10.5f : light ? Math.max(8f, d.headingPt - 0.9f) : d.headingPt;
        bold.setTextSize(size);
        float lead = size + 2.1f;
        float padL = light ? 1f : 5f, padT = light ? 3f : b.fixedFill ? 3.5f : 4.2f, padB = light ? 2.4f : b.fixedFill ? 3.5f : 4.2f;
        float w = d.contentMm() * MM;
        List<String> lines = wrap(t, w - padL - 4, bold, 3);
        float h = padT + padB + lines.size() * lead;
        y += (b.fixedFill ? 2f : 2.2f) * MM;
        need(h + 34);   // keep the heading with at least two rows of what follows
        if (light) line(x0, y + h, x0 + w, y + h, d.accent, 0.9f);
        else if (outline) box(x0, y, x0 + w, y + h, d.accent, 0.9f);
        else rect(x0, y, x0 + w, y + h, d.accent);
        bold.setColor(light || outline ? d.accent : Color.WHITE);
        float ty = y + padT;
        for (String l : lines) { text(l, x0 + padL, ty + baseline(size, lead), bold); ty += lead; }
        y += h;
    }

    private static float baseline(float size, float lead) { return (lead - size) / 2f + size * 0.84f; }

    private float[] widths(float[] w) {
        float sum = 0;
        for (float v : w) sum += v;
        float[] out = new float[w.length];
        float content = d.contentMm() * MM;
        for (int i = 0; i < w.length; i++) out[i] = sum <= 1.01f ? w[i] * content : w[i] * MM;
        return out;
    }

    /** _rmtc_labeled_grid. */
    private void labeled(RptDoc.Labeled g) {
        float[] w = widths(g.w);
        float size = g.size, lead = size + 2f;
        for (String[] row : g.rows) {
            List<Cell> cells = new ArrayList<>();
            for (int i = 0; i < row.length && i < w.length; i++) {
                String v = row[i] == null ? "" : row[i];
                Cell cell;
                if (g.labelCols.contains(i)) {
                    cell = new Cell(v, bold, g.labelSize > 0 ? g.labelSize : size, LABEL, RptDoc.LEFT);
                } else {
                    String prev = i > 0 && g.labelCols.contains(i - 1) ? row[i - 1] : "";
                    prev = prev == null ? "" : prev;
                    String pu = prev.toUpperCase(Locale.ROOT);
                    TextPaint p = g.valueBold ? bold : regular;
                    int color = INK;
                    if (g.valueColor != 0) color = g.valueColor;
                    else if (RptDoc.isRemark(prev)) { p = italic; color = d.remarkColor; }
                    else if (RptDoc.isConclusion(prev)) { p = bold; color = d.conclusionColor; }
                    else if ((pu.contains("DISPOSITION") || pu.contains("DECISION") || pu.contains("RESULT") || pu.contains("STATUS")) && !pu.contains("REASON")) {
                        int sc = RptDoc.statusColor(v);
                        if (sc != INK) { p = bold; color = sc; }
                    }
                    cell = new Cell(v, p, size, color, g.center ? RptDoc.CENTER_A : RptDoc.LEFT);
                }
                cells.add(cell);
            }
            float h = rowHeight(cells, w, lead, PAD_TB);
            if (h > room()) newPage();
            if (g.ruled && row == g.rows[0]) line(x0, y, x0 + sum(w), y, INK, 1.0f);
            drawRow(cells, w, y, lead, PAD_TB);
            y += h;
            if (g.ruled) line(x0, y, x0 + sum(w), y, INK, 1.0f);
            else line(x0, y, x0 + sum(w), y, d.rule, 0.4f);
        }
    }

    /** _rmtc_grid with repeated header rows. */
    private void grid(RptDoc.Grid g) {
        if (g.rows.length == 0) return;
        float[] w = widths(g.w);
        int cols = w.length;
        float headLead = g.headSize + 1.8f, lead = g.cellSize + 2f;
        String[] header = g.rows[Math.max(0, g.headerRows - 1)];
        int[] align = new int[cols];
        java.util.Set<Integer> remark = new java.util.HashSet<>(), concl = new java.util.HashSet<>();
        for (int i = 0; i < cols; i++) {
            String h = i < header.length ? header[i] : "";
            align[i] = g.noAlign ? RptDoc.LEFT : RptDoc.alignment(h);
            if (RptDoc.isRemark(g.rows[0].length > i ? g.rows[0][i] : "")) remark.add(i);
            if (RptDoc.isConclusion(g.rows[0].length > i ? g.rows[0][i] : "")) concl.add(i);
        }
        List<List<Cell>> heads = new ArrayList<>();
        for (int r = 0; r < g.headerRows && r < g.rows.length; r++) {
            List<Cell> cells = new ArrayList<>();
            for (int i = 0; i < cols; i++) {
                String v = i < g.rows[r].length ? g.rows[r][i] : "";
                boolean labelCell = g.firstColBold && i == 0;
                cells.add(new Cell(v, g.plainHeader ? regular : bold, g.headSize, INK, labelCell || g.noAlign ? RptDoc.LEFT : RptDoc.CENTER_A));
            }
            heads.add(cells);
        }
        float headH = 0;
        for (List<Cell> h : heads) headH += rowHeight(h, w, headLead, PAD_TB);
        float total = sum(w);
        boolean drawn = false;
        for (int r = g.headerRows; r < g.rows.length; r++) {
            List<Cell> cells = new ArrayList<>();
            String[] row = g.rows[r];
            for (int i = 0; i < cols; i++) {
                String v = i < row.length && row[i] != null ? row[i] : "";
                TextPaint p = regular;
                int color = INK;
                if (g.firstColBold && i == 0) p = bold;
                else if (g.statusCols.contains(i)) { p = bold; color = RptDoc.statusColor(v); }
                else if (remark.contains(i)) { p = italic; color = d.remarkColor; }
                else if (concl.contains(i)) { p = bold; color = d.conclusionColor; }
                int a = g.allCenter && !(g.firstColBold && i == 0) ? RptDoc.CENTER_A : align[i];
                if (!g.allCenter && !g.noAlign && a == RptDoc.LEFT && RptDoc.plainNumber(v)) a = RptDoc.CENTER_A;
                cells.add(new Cell(v, p, g.cellSize, color, a));
            }
            float h = rowHeight(cells, w, lead, PAD_TB);
            float cap = bottom - top - headH - 4;
            if (h > cap) h = cap;
            if (!drawn) {
                if (headH + h > room()) newPage();
                gridHeader(g, heads, w, headLead, total);
                drawn = true;
            } else if (h > room()) {
                newPage();
                gridHeader(g, heads, w, headLead, total);
            }
            drawRow(cells, w, y, lead, PAD_TB, h);
            y += h;
            line(x0, y, x0 + total, y, d.rule, 0.4f);
        }
        if (!drawn) {
            need(headH);
            gridHeader(g, heads, w, headLead, total);
        }
    }

    private void gridHeader(RptDoc.Grid g, List<List<Cell>> heads, float[] w, float headLead, float total) {
        if (!g.noTopLine) line(x0, y, x0 + total, y, INK, 1.0f);
        for (List<Cell> hc : heads) {
            float hh = rowHeight(hc, w, headLead, PAD_TB);
            drawRow(hc, w, y, headLead, PAD_TB);
            y += hh;
        }
        line(x0, y, x0 + total, y, INK, 1.0f);
    }

    /** _quality_conclusion_table. */
    private void conclusion(RptDoc.Conclusion k) {
        float size = d.bodyPt;
        float[] w = {40 * MM, d.contentMm() * MM - 40 * MM};
        List<String[]> rows = new ArrayList<>();
        rows.add(new String[]{"Conclusion", k.conclusion, "C"});
        if (k.remark != null && !k.remark.trim().isEmpty()) rows.add(new String[]{"Conclusion Remark", k.remark, "R"});
        rows.add(new String[]{"Final Decision", k.decision, "D"});
        rows.add(new String[]{"Decision Reason", k.reason, "W"});
        float total = sum(w);
        need(60);
        line(x0, y, x0 + total, y, INK, 1.0f);
        for (int i = 0; i < rows.size(); i++) {
            String[] r = rows.get(i);
            String value = RptDoc.v(r[1]);
            Cell label = new Cell(r[0], bold, size, LABEL, RptDoc.LEFT);
            Cell val;
            switch (r[2]) {
                case "C": val = new Cell(value, bold, size + 1.4f, d.conclusionColor, RptDoc.LEFT); break;
                case "R": val = new Cell(value, italic, size + 0.6f, d.remarkColor, RptDoc.LEFT); break;
                case "D": val = new Cell(value, bold, size + 1.4f, RptDoc.statusColor(r[1]), RptDoc.LEFT); break;
                default: val = value.trim().isEmpty() ? new Cell(value, regular, size, INK, RptDoc.LEFT) : new Cell(value, italic, size, d.remarkColor, RptDoc.LEFT);
            }
            List<Cell> cells = new ArrayList<>();
            cells.add(label);
            cells.add(val);
            float lead = size + 3.6f;
            float h = rowHeight(cells, w, lead, 4f);
            if (h > room()) newPage();
            drawRow(cells, w, y, lead, 4f);
            y += h;
            boolean last = i == rows.size() - 1;
            line(x0, y, x0 + total, y, last ? INK : d.rule, last ? 1.0f : 0.4f);
        }
    }

    /** _photo_grid_table / _microstructure_photo_table. */
    private void photos(RptDoc.Photos p) {
        int cols = Math.max(1, p.cols);
        float total = d.contentMm() * MM;
        float colW = total / cols;
        float maxH = p.maxHmm * MM;
        TextPaint cap = regular;
        float capSize = d.bodyPt;
        List<RptDoc.Photo> items = p.items;
        if (items.isEmpty()) {
            regular.setTextSize(capSize);
            float h = capSize + 2 + 6;
            need(h);
            box(x0, y, x0 + total, y + h, BORDER, 0.55f);
            regular.setColor(INK);
            centred("No microstructure photographs recorded", x0 + total / 2, y + 3 + baseline(capSize, capSize + 2), regular);
            y += h;
            return;
        }
        for (int start = 0; start < items.size(); start += cols) {
            float rowH = 0;
            float[] imgH = new float[cols];
            Bitmap[] bmp = new Bitmap[cols];
            for (int i = 0; i < cols && start + i < items.size(); i++) {
                RptDoc.Photo ph = items.get(start + i);
                bmp[i] = ph.has() ? decode(ph.bytes) : null;
                float boxW = colW - 6 * MM;
                float hImg;
                if (bmp[i] != null) {
                    float s = Math.min(boxW / bmp[i].getWidth(), maxH / bmp[i].getHeight());
                    hImg = bmp[i].getHeight() * s;
                } else {
                    hImg = p.slots ? Math.min(maxH, 36 * MM) : maxH - 5 * MM;
                }
                imgH[i] = hImg;
                regular.setTextSize(capSize);
                int capLines = wrap(ph.caption, colW - 6, regular, 3).size();
                rowH = Math.max(rowH, 3 + hImg + 1 * MM + capLines * (capSize + 2) + 3);
            }
            need(rowH);
            box(x0, y, x0 + total, y + rowH, BORDER, 0.55f);
            for (int i = 1; i < cols; i++) line(x0 + i * colW, y, x0 + i * colW, y + rowH, BORDER, 0.35f);
            for (int i = 0; i < cols && start + i < items.size(); i++) {
                RptDoc.Photo ph = items.get(start + i);
                float cx = x0 + i * colW + colW / 2;
                float ty = y + 3;
                float boxW = colW - 6 * MM;
                if (bmp[i] != null) {
                    float s = Math.min(boxW / bmp[i].getWidth(), maxH / bmp[i].getHeight());
                    float w = bmp[i].getWidth() * s;
                    if (!dry) c.drawBitmap(bmp[i], null, new RectF(cx - w / 2, ty, cx + w / 2, ty + imgH[i]), null);
                } else {
                    float bw = p.slots ? colW - 6 * MM : colW - 8 * MM;
                    box(cx - bw / 2, ty, cx + bw / 2, ty + imgH[i], BORDER, 0.5f);
                    regular.setTextSize(capSize);
                    regular.setColor(INK);
                    centred("No photograph uploaded", cx, ty + imgH[i] / 2 + capSize / 3, regular);
                }
                ty += imgH[i] + 1 * MM;
                regular.setTextSize(capSize);
                regular.setColor(INK);
                for (String l : wrap(ph.caption, colW - 6, cap, 3)) { centred(l, cx, ty + baseline(capSize, capSize + 2), cap); ty += capSize + 2; }
            }
            y += rowH;
        }
    }

    static Bitmap decode(byte[] bytes) {
        try {
            BitmapFactory.Options o = new BitmapFactory.Options();
            o.inJustDecodeBounds = true;
            BitmapFactory.decodeByteArray(bytes, 0, bytes.length, o);
            int sample = 1;
            while (o.outWidth / sample > 1400 || o.outHeight / sample > 1400) sample *= 2;
            BitmapFactory.Options o2 = new BitmapFactory.Options();
            o2.inSampleSize = sample;
            return BitmapFactory.decodeByteArray(bytes, 0, bytes.length, o2);
        } catch (Throwable e) {
            return null;
        }
    }

    /** _case_depth_chart: Distance (mm) vs Hardness (HV). */
    private void chart(RptDoc.Chart k) {
        if (k.series.isEmpty()) return;
        float width = d.contentMm() * MM, height = 58 * MM;
        need(height);
        if (!dry) drawChart(c, k, x0, y, width, height);
        y += height;
    }

    static final int[] PALETTE = {0xFF083B6E, 0xFF0B76B7, 0xFF2E8B57, 0xFF7B3FB8, 0xFFC55A11, 0xFF5B6573};

    /** Shared with the on-screen report (RptView draws the same chart into a bitmap). */
    static void drawChart(Canvas c, RptDoc.Chart k, float left, float topY, float width, float height) {
        TextPaint t = new TextPaint(Paint.ANTI_ALIAS_FLAG);
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        double minX = Double.MAX_VALUE, maxX = -Double.MAX_VALUE, minY = Double.MAX_VALUE, maxY = -Double.MAX_VALUE;
        for (List<double[]> s : k.series) for (double[] pt : s) {
            minX = Math.min(minX, pt[0]); maxX = Math.max(maxX, pt[0]); minY = Math.min(minY, pt[1]); maxY = Math.max(maxY, pt[1]);
        }
        double xMin = Math.max(0, minX), xMax = maxX > minX ? maxX : minX + 0.1;
        double pad = Math.max(20.0, (maxY - minY) * 0.1);
        double yMin = Math.max(0, minY - pad), yMax = maxY + pad;
        float px = left + 36, plotW = Math.max(80, width - 128), plotH = Math.max(70, height - 38);
        float py = topY + height - 22 - plotH;   // plot top
        p.setColor(0xFF000000);
        p.setStrokeWidth(0.5f);
        c.drawLine(px, py + plotH, px + plotW, py + plotH, p);
        c.drawLine(px, py, px, py + plotH, p);
        t.setTextSize(5.5f);
        t.setColor(0xFF17212B);
        double xStep = nice((xMax - xMin) / 6), yStep = nice((yMax - yMin) / 6);
        for (double v = Math.ceil(xMin / xStep) * xStep; v <= xMax + 1e-9; v += xStep) {
            float x = (float) (px + (v - xMin) / (xMax - xMin) * plotW);
            c.drawLine(x, py + plotH, x, py + plotH + 3, p);
            String s = String.format(Locale.ENGLISH, "%.2f", v);
            c.drawText(s, x - t.measureText(s) / 2, py + plotH + 10, t);
        }
        for (double v = Math.ceil(yMin / yStep) * yStep; v <= yMax + 1e-9; v += yStep) {
            float yy = (float) (py + plotH - (v - yMin) / (yMax - yMin) * plotH);
            c.drawLine(px - 3, yy, px, yy, p);
            String s = String.valueOf((long) v);
            c.drawText(s, px - 5 - t.measureText(s), yy + 2, t);
        }
        for (int si = 0; si < k.series.size(); si++) {
            int col = PALETTE[si % PALETTE.length];
            p.setColor(col);
            p.setStrokeWidth(1.3f);
            List<double[]> s = k.series.get(si);
            float lx = 0, ly = 0;
            for (int i = 0; i < s.size(); i++) {
                float x = (float) (px + (s.get(i)[0] - xMin) / (xMax - xMin) * plotW);
                float yy = (float) (py + plotH - (s.get(i)[1] - yMin) / (yMax - yMin) * plotH);
                if (i > 0) c.drawLine(lx, ly, x, yy, p);
                c.drawCircle(x, yy, 1.75f, p);
                lx = x; ly = yy;
            }
        }
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setTextSize(6f);
        String xl = "Distance (mm)";
        c.drawText(xl, px + plotW / 2 - t.measureText(xl) / 2, topY + height - 2, t);
        c.drawText("Hardness (HV)", left + 2, topY + 12 - 6, t);
        t.setTypeface(Typeface.DEFAULT);
        t.setTextSize(5.5f);
        float lgx = left + width - 86, lgy = topY + 18;
        for (int i = 0; i < k.names.size(); i++) {
            p.setColor(PALETTE[i % PALETTE.length]);
            c.drawRect(lgx, lgy + i * 8 - 4, lgx + 5, lgy + i * 8 + 1, p);
            c.drawText(k.names.get(i), lgx + 8, lgy + i * 8 + 1, t);
        }
    }

    static double nice(double raw) {
        if (raw <= 0) return 1;
        double e = Math.pow(10, Math.floor(Math.log10(raw)));
        double f = raw / e;
        double n = f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10;
        return n * e;
    }

    private void paragraph(RptDoc.Text t) {
        float size;
        TextPaint p;
        int color = INK, align = RptDoc.LEFT;
        switch (t.style) {
            case RptDoc.SMALL: size = 7.4f; p = regular; break;
            case RptDoc.CENTER: size = d.bodyPt; p = regular; align = RptDoc.CENTER_A; break;
            case RptDoc.BIG: size = 20f; p = regular; align = RptDoc.CENTER_A; break;
            case RptDoc.REMARK: size = d.bodyPt; p = boldItalic; color = d.remarkColor; align = RptDoc.CENTER_A; break;
            case RptDoc.HEADING: size = d.bodyPt; p = bold; break;
            case RptDoc.CONCL: size = 9.6f; p = bold; color = d.conclusionColor; break;
            case RptDoc.SUBTITLE: size = 6.2f; p = regular; color = MUTED; align = RptDoc.CENTER_A; break;
            default: size = d.bodyPt; p = regular;
        }
        float lead = t.style == RptDoc.BIG ? 24f : t.style == RptDoc.SUBTITLE ? 7.4f : size + 2f;
        float w = d.contentMm() * MM;
        p.setTextSize(size);
        p.setColor(color);
        for (String l : wrap(t.text, w, p, 40)) {
            if (lead > room()) newPage();
            float base = y + baseline(size, lead);
            if (align == RptDoc.CENTER_A) centred(l, x0 + w / 2, base, p); else text(l, x0, base, p);
            if (t.style == RptDoc.HEADING) line(x0, base + 1.2f, x0 + p.measureText(l), base + 1.2f, color, 0.5f);
            y += lead;
        }
        if (t.style == RptDoc.SUBTITLE) y += 2 * MM;
    }

    private void bendPanel(RptDoc.BendPanel b) {
        float W = d.contentMm() * MM, half = W / 2;
        float imgW = half - 6 * MM;
        float leftH = photoHeight(b.left, imgW, 112 * MM, 30 * MM);
        float rightH = 24 + 2 * MM + photoHeight(b.r1, imgW, 48 * MM, 30 * MM) + 2 * MM + photoHeight(b.r2, imgW, 48 * MM, 30 * MM);
        if (b.r3 != null && b.r3.has()) rightH += 2 * MM + photoHeight(b.r3, imgW, 30 * MM, 30 * MM);
        regular.setTextSize(d.bodyPt);
        List<String> surface = wrap(b.surface == null ? "" : b.surface, half - 12, boldItalic, 6);
        rightH += 2 * MM + surface.size() * (d.bodyPt + 2);
        float h = Math.max(leftH, rightH) + 6;
        bold.setTextSize(10.5f);
        float bandH = 3.5f * 2 + 12.6f;
        y += 2 * MM;
        need(bandH + Math.min(h, 200));
        rect(x0, y, x0 + W, y + bandH, d.accent);
        bold.setColor(Color.WHITE);
        text("Load Vs CHT", x0 + 5, y + 3.5f + baseline(10.5f, 12.6f), bold);
        text("Bend Test Part", x0 + half + 5, y + 3.5f + baseline(10.5f, 12.6f), bold);
        y += bandH;
        need(h);
        float top0 = y + 3;
        drawPhoto(b.left, x0 + half / 2, top0, imgW, 112 * MM, 30 * MM);
        float ry = top0;
        regular.setTextSize(20f);
        regular.setColor(INK);
        centred(b.angle, x0 + half + half / 2, ry + baseline(20f, 24f), regular);
        ry += 24 + 2 * MM;
        ry += drawPhoto(b.r1, x0 + half + half / 2, ry, imgW, 48 * MM, 30 * MM) + 2 * MM;
        ry += drawPhoto(b.r2, x0 + half + half / 2, ry, imgW, 48 * MM, 30 * MM);
        if (b.r3 != null && b.r3.has()) { ry += 2 * MM; ry += drawPhoto(b.r3, x0 + half + half / 2, ry, imgW, 30 * MM, 30 * MM); }
        ry += 2 * MM;
        boldItalic.setTextSize(d.bodyPt);
        boldItalic.setColor(d.remarkColor);
        for (String l : surface) { centred(l, x0 + half + half / 2, ry + baseline(d.bodyPt, d.bodyPt + 2), boldItalic); ry += d.bodyPt + 2; }
        y += h;
    }

    private float photoHeight(RptDoc.Photo ph, float w, float h, float placeholder) {
        if (ph == null || !ph.has()) return Math.min(h, placeholder);
        Bitmap bm = decode(ph.bytes);
        if (bm == null) return Math.min(h, placeholder);
        return bm.getHeight() * Math.min(w / bm.getWidth(), h / bm.getHeight());
    }

    private float drawPhoto(RptDoc.Photo ph, float cx, float ty, float w, float h, float placeholder) {
        Bitmap bm = ph != null && ph.has() ? decode(ph.bytes) : null;
        if (bm == null) {
            float hh = Math.min(h, placeholder);
            box(cx - w / 2, ty, cx + w / 2, ty + hh, BORDER, 0.4f);
            regular.setTextSize(d.bodyPt);
            regular.setColor(INK);
            centred("No image uploaded", cx, ty + hh / 2 + 3, regular);
            return hh;
        }
        float s = Math.min(w / bm.getWidth(), h / bm.getHeight());
        float iw = bm.getWidth() * s, ih = bm.getHeight() * s;
        if (!dry) c.drawBitmap(bm, null, new RectF(cx - iw / 2, ty, cx + iw / 2, ty + ih), null);
        return ih;
    }

    private void signatures(RptDoc.Signatures s) {
        float[] w = widths(s.w);
        float size = d.bodyPt, lead = size + 1.8f;
        List<Cell> vals = new ArrayList<>(), labs = new ArrayList<>();
        for (String v : s.values) vals.add(new Cell(v, regular, size, INK, RptDoc.LEFT));
        for (String l : s.labels) labs.add(new Cell(l, bold, size, INK, RptDoc.LEFT));
        float h1 = rowHeight(vals, w, lead, 3f), h2 = rowHeight(labs, w, lead, 3f);
        need(h1 + h2);
        drawRow(vals, w, y, lead, 3f, h1, 6f);
        y += h1;
        drawRow(labs, w, y, lead, 3f, h2, 6f);
        y += h2;
    }

    // ------------------------------------------------------------------ cells
    private static final class Cell {
        final String text; final TextPaint paint; final float size; final int color; final int align;
        Cell(String text, TextPaint paint, float size, int color, int align) {
            this.text = text == null ? "" : text; this.paint = paint; this.size = size; this.color = color; this.align = align;
        }
    }

    private float rowHeight(List<Cell> cells, float[] w, float lead, float padTB) { return rowHeight(cells, w, lead, padTB, PAD_LR); }

    private float rowHeight(List<Cell> cells, float[] w, float lead, float padTB, float padLR) {
        float h = 0;
        for (int i = 0; i < cells.size() && i < w.length; i++) {
            Cell cell = cells.get(i);
            cell.paint.setTextSize(cell.size);
            int n = Math.max(1, wrap(cell.text, w[i] - 2 * padLR, cell.paint, 60).size());
            float cl = cell.size > lead - 1.5f ? cell.size + 2f : lead;
            h = Math.max(h, n * cl + 2 * padTB);
        }
        return h;
    }

    private void drawRow(List<Cell> cells, float[] w, float top, float lead, float padTB) { drawRow(cells, w, top, lead, padTB, rowHeight(cells, w, lead, padTB), PAD_LR); }

    private void drawRow(List<Cell> cells, float[] w, float top, float lead, float padTB, float h) { drawRow(cells, w, top, lead, padTB, h, PAD_LR); }

    /** Cells are vertically centred (VALIGN MIDDLE); text beyond the row height is cut. */
    private void drawRow(List<Cell> cells, float[] w, float top, float lead, float padTB, float h, float padLR) {
        if (dry) return;
        float x = x0;
        for (int i = 0; i < cells.size() && i < w.length; i++) {
            Cell cell = cells.get(i);
            cell.paint.setTextSize(cell.size);
            cell.paint.setColor(cell.color);
            float cl = cell.size > lead - 1.5f ? cell.size + 2f : lead;
            List<String> lines = wrap(cell.text, w[i] - 2 * padLR, cell.paint, 60);
            int max = Math.max(1, (int) Math.floor((h - 2 * padTB) / cl + 0.05f));
            if (lines.size() > max) lines = lines.subList(0, max);
            float textH = lines.size() * cl;
            float ty = top + (h - textH) / 2f;
            for (String l : lines) {
                float base = ty + baseline(cell.size, cl);
                float tw = cell.paint.measureText(l);
                float tx = cell.align == RptDoc.CENTER_A ? x + (w[i] - tw) / 2 : cell.align == RptDoc.RIGHT ? x + w[i] - padLR - tw : x + padLR;
                c.drawText(l, tx, base, cell.paint);
                ty += cl;
            }
            x += w[i];
        }
    }

    // ------------------------------------------------------------------ primitives
    static List<String> wrap(String s, float width, Paint p, int maxLines) {
        List<String> out = new ArrayList<>();
        if (s == null) s = "";
        for (String para : s.split("\n", -1)) {
            String[] words = para.split(" ");
            StringBuilder cur = new StringBuilder();
            for (String word : words) {
                String trial = cur.length() == 0 ? word : cur + " " + word;
                if (p.measureText(trial) <= width) { cur.setLength(0); cur.append(trial); continue; }
                if (cur.length() > 0) { out.add(cur.toString()); cur.setLength(0); }
                String rest = word;
                while (p.measureText(rest) > width && rest.length() > 1) {
                    int n = rest.length();
                    while (n > 1 && p.measureText(rest.substring(0, n)) > width) n--;
                    out.add(rest.substring(0, n));
                    rest = rest.substring(n);
                }
                cur.append(rest);
            }
            out.add(cur.toString());
        }
        while (out.size() > 1 && out.get(out.size() - 1).isEmpty()) out.remove(out.size() - 1);
        if (out.size() > maxLines) {
            List<String> cut = new ArrayList<>(out.subList(0, maxLines));
            cut.set(maxLines - 1, cut.get(maxLines - 1) + "…");
            return cut;
        }
        return out;
    }

    private static float sum(float[] w) { float s = 0; for (float v : w) s += v; return s; }

    static String fit(String s, float width, Paint p) {
        if (p.measureText(s) <= width) return s;
        String t = s;
        while (t.length() > 1 && p.measureText(t + "…") > width) t = t.substring(0, t.length() - 1);
        return t + "…";
    }

    private void text(String s, float x, float yy, Paint p) { if (!dry) c.drawText(s, x, yy, p); }
    private void centred(String s, float cx, float yy, Paint p) { if (!dry) c.drawText(s, cx - p.measureText(s) / 2, yy, p); }
    private void right(String s, float rx, float yy, Paint p) { if (!dry) c.drawText(s, rx - p.measureText(s), yy, p); }

    private void line(float ax, float ay, float bx, float by, int color, float width) {
        if (dry) return;
        stroke.setColor(color);
        stroke.setStrokeWidth(width);
        c.drawLine(ax, ay, bx, by, stroke);
    }

    private void rect(float l, float t, float r, float b, int color) {
        if (dry) return;
        fill.setColor(color);
        fill.setStyle(Paint.Style.FILL);
        c.drawRect(l, t, r, b, fill);
    }

    private void box(float l, float t, float r, float b, int color, float width) {
        line(l, t, r, t, color, width);
        line(r, t, r, b, color, width);
        line(r, b, l, b, color, width);
        line(l, b, l, t, color, width);
    }
}
