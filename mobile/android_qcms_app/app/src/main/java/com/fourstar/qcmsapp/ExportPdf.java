package com.fourstar.qcmsapp;

import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
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
 * Controlled QCMS print of an ExportDoc (A4, landscape when a table is wide): company header, title,
 * key-value sections in two columns, tables with wrapped cells and the header row repeated on every
 * page, footer "Page i of N". Two passes: the first only counts pages.
 */
final class ExportPdf {
    static final String COMPANY = "FOUR STAR INDUSTRIES PVT. LTD.";
    private static final int TEAL = Color.parseColor("#0F8B8D");
    private static final int TEAL_DARK = Color.parseColor("#0B6E70");
    private static final int TEAL_SOFT = Color.parseColor("#E3F2F2");
    private static final int TEXT = Color.parseColor("#1D2B2C");
    private static final int MUTED = Color.parseColor("#5C7778");
    private static final int LINE = Color.parseColor("#B5CFCF");
    private static final int ZEBRA = Color.parseColor("#F5F9F9");
    private static final float M = 28f;

    private final ExportDoc doc;
    private final String printedBy;
    private final boolean landscape;
    private final float pw, ph;
    private final TextPaint text = new TextPaint(Paint.ANTI_ALIAS_FLAG);
    private final TextPaint bold = new TextPaint(Paint.ANTI_ALIAS_FLAG);
    private final Paint fill = new Paint();
    private final Paint line = new Paint();

    // layout state
    private boolean dry;
    private int pageCount, totalPages;
    private PdfDocument pdf;
    private PdfDocument.Page page;
    private Canvas c;
    private float y;

    private ExportPdf(ExportDoc doc, String printedBy) {
        this.doc = doc;
        this.printedBy = printedBy == null ? "" : printedBy;
        int widest = 0;
        for (ExportDoc.Table t : doc.tables) widest = Math.max(widest, t.columns.size());
        landscape = widest > 7;
        pw = landscape ? 842f : 595f;
        ph = landscape ? 595f : 842f;
        text.setColor(TEXT);
        bold.setColor(TEXT);
        bold.setTypeface(Typeface.DEFAULT_BOLD);
        bold.setFakeBoldText(true);
        line.setColor(LINE);
        line.setStrokeWidth(0.6f);
    }

    static byte[] render(ExportDoc doc, String printedBy) throws Exception {
        ExportPdf r = new ExportPdf(doc, printedBy);
        r.dry = true;
        r.run();
        r.totalPages = r.pageCount;
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
        pageCount = 0;
        page = null;
        c = null;
        newPage();
        for (ExportDoc.Section s : doc.sections) if (!s.pairs.isEmpty()) section(s);
        for (ExportDoc.Table t : doc.tables) table(t);
        if (doc.isEmpty()) {
            text.setTextSize(10);
            draw("No data to print.", M, y + 14, text);
        }
        finishPage();
    }

    // ------------------------------------------------------------------ pages
    private void newPage() {
        finishPage();
        pageCount++;
        if (!dry) {
            page = pdf.startPage(new PdfDocument.PageInfo.Builder((int) pw, (int) ph, pageCount).create());
            c = page.getCanvas();
            c.drawColor(Color.WHITE);
        }
        header();
    }

    private void finishPage() {
        if (page == null && !(dry && pageCount > 0)) return;
        footer();
        if (!dry && page != null) pdf.finishPage(page);
        page = null;
        c = null;
    }

    private void header() {
        float top = M;
        bold.setTextSize(9);
        bold.setColor(TEAL_DARK);
        draw(COMPANY, M, top + 9, bold);
        text.setTextSize(7.5f);
        text.setColor(MUTED);
        String right = "QCMS · Quality Control Monitoring System";
        draw(right, pw - M - text.measureText(right), top + 9, text);
        bold.setTextSize(pageCount == 1 ? 15 : 11);
        bold.setColor(TEXT);
        float titleY = top + (pageCount == 1 ? 30 : 24);
        draw(fit(doc.title.toUpperCase(Locale.ROOT), pw - 2 * M, bold), M, titleY, bold);
        float after = titleY + 6;
        if (pageCount == 1) {
            text.setTextSize(8);
            text.setColor(MUTED);
            String printed = "Printed " + new SimpleDateFormat("dd-MM-yyyy HH:mm", Locale.ENGLISH).format(new Date())
                + (printedBy.isEmpty() ? "" : " by " + printedBy);
            String sub = doc.subtitle.isEmpty() ? printed : doc.subtitle + "   ·   " + printed;
            for (String l : wrap(sub, pw - 2 * M, text, 2)) { after += 11; draw(l, M, after, text); }
            after += 4;
        }
        fill.setColor(TEAL);
        rect(M, after, pw - M, after + 1.6f, fill);
        text.setColor(TEXT);
        bold.setColor(TEXT);
        y = after + 10;
    }

    private void footer() {
        float fy = ph - M + 10;
        line.setColor(LINE);
        lineAt(M, fy - 10, pw - M, fy - 10);
        text.setTextSize(7);
        text.setColor(MUTED);
        draw(fit(doc.title, pw / 2, text), M, fy, text);
        String p = "Page " + pageCount + " of " + Math.max(totalPages, pageCount);
        draw(p, pw - M - text.measureText(p), fy, text);
        text.setColor(TEXT);
    }

    private float bottom() { return ph - M - 16; }

    private void ensure(float need) {
        if (y + need > bottom()) newPage();
    }

    // ------------------------------------------------------------------ sections
    private void bar(String title) {
        ensure(40);
        fill.setColor(TEAL_SOFT);
        rect(M, y, pw - M, y + 16, fill);
        fill.setColor(TEAL);
        rect(M, y, M + 3, y + 16, fill);
        bold.setTextSize(8.5f);
        bold.setColor(TEAL_DARK);
        draw(fit(title.toUpperCase(Locale.ROOT), pw - 2 * M - 12, bold), M + 8, y + 11.5f, bold);
        bold.setColor(TEXT);
        y += 20;
    }

    private void section(ExportDoc.Section s) {
        bar(s.title.isEmpty() ? "Details" : s.title);
        float colW = (pw - 2 * M - 12) / 2f;
        float labelW = colW * 0.38f, valueW = colW - labelW - 4;
        text.setTextSize(8);
        bold.setTextSize(8);
        for (int i = 0; i < s.pairs.size(); i += 2) {
            List<String[]> pair = new ArrayList<>();
            pair.add(s.pairs.get(i));
            if (i + 1 < s.pairs.size()) pair.add(s.pairs.get(i + 1));
            int lines = 1;
            List<List<String>> values = new ArrayList<>();
            List<List<String>> labels = new ArrayList<>();
            for (String[] p : pair) {
                List<String> l = wrap(p[0], labelW, text, 2);
                List<String> v = wrap(p[1].isEmpty() ? "-" : p[1], valueW, bold, 4);
                labels.add(l);
                values.add(v);
                lines = Math.max(lines, Math.max(l.size(), v.size()));
            }
            float h = 4 + lines * 10.5f;
            ensure(h + 2);
            text.setTextSize(8);
            bold.setTextSize(8);
            bold.setColor(TEXT);
            for (int k = 0; k < pair.size(); k++) {
                float x = M + k * (colW + 12);
                text.setColor(MUTED);
                for (int li = 0; li < labels.get(k).size(); li++) draw(labels.get(k).get(li), x, y + 9 + li * 10.5f, text);
                text.setColor(TEXT);
                for (int li = 0; li < values.get(k).size(); li++) draw(values.get(k).get(li), x + labelW + 4, y + 9 + li * 10.5f, bold);
            }
            line.setColor(Color.parseColor("#E3EAEA"));
            lineAt(M, y + h, pw - M, y + h);
            y += h + 1;
        }
        y += 8;
    }

    // ------------------------------------------------------------------ tables
    private void table(ExportDoc.Table t) {
        bar((t.title.isEmpty() ? "Table" : t.title) + "  (" + t.rows.size() + " row" + (t.rows.size() == 1 ? "" : "s") + ")");
        int n = t.columns.size();
        if (n == 0) return;
        float avail = pw - 2 * M;
        float font = n > 14 ? 6.2f : n > 10 ? 6.8f : n > 7 ? 7.2f : 7.8f;
        text.setTextSize(font);
        bold.setTextSize(font);
        float pad = 3f;
        float[] w = new float[n];
        float total = 0;
        for (int i = 0; i < n; i++) {
            float best = bold.measureText(t.columns.get(i));
            int sample = Math.min(t.rows.size(), 300);
            for (int r = 0; r < sample; r++) {
                List<String> row = t.rows.get(r);
                String v = i < row.size() && row.get(i) != null ? row.get(i) : "";
                best = Math.max(best, text.measureText(v));
            }
            w[i] = Math.min(best, 200f) + 2 * pad;
            total += w[i];
        }
        // fit the page width: shrink wide columns (cells wrap), or stretch when there is room
        float scale = avail / total;
        if (scale < 1f) {
            float min = Math.max(26f, avail / n * 0.55f);
            float fixed = 0, flexible = 0;
            for (float x : w) { if (x * scale < min) fixed += min; else flexible += x; }
            float k = flexible > 0 ? (avail - fixed) / flexible : scale;
            for (int i = 0; i < n; i++) w[i] = w[i] * scale < min ? min : w[i] * k;
        } else {
            for (int i = 0; i < n; i++) w[i] *= scale;
        }
        float lh = font + 3f;
        headerRow(t, w, pad, lh, true);
        for (int r = 0; r < t.rows.size(); r++) {
            List<String> row = t.rows.get(r);
            List<List<String>> cells = new ArrayList<>();
            int lines = 1;
            for (int i = 0; i < n; i++) {
                String v = i < row.size() && row.get(i) != null ? row.get(i) : "";
                List<String> l = wrap(v, w[i] - 2 * pad - 1, i == 0 ? bold : text, 3);
                cells.add(l);
                lines = Math.max(lines, l.size());
            }
            float h = lines * lh + 4;
            if (y + h > bottom()) {
                newPage();
                text.setTextSize(font);
                bold.setTextSize(font);
                text.setColor(TEXT);
                bold.setColor(TEXT);
                headerRow(t, w, pad, lh, false);
            }
            if (r % 2 == 1) {
                fill.setColor(ZEBRA);
                rect(M, y, M + avail, y + h, fill);
            }
            float x = M;
            for (int i = 0; i < n; i++) {
                List<String> l = cells.get(i);
                boolean num = isNumber(i < row.size() ? row.get(i) : "");
                for (int li = 0; li < l.size(); li++) {
                    TextPaint p = i == 0 ? bold : text;
                    float tx = num ? x + w[i] - pad - 1 - p.measureText(l.get(li)) : x + pad;
                    draw(l.get(li), tx, y + 2 + font + li * lh, p);
                }
                x += w[i];
                line.setColor(Color.parseColor("#DCE6E6"));
                lineAt(x, y, x, y + h);
            }
            lineAt(M, y + h, M + avail, y + h);
            lineAt(M, y, M, y + h);
            y += h;
        }
        if (t.rows.isEmpty()) {
            text.setColor(MUTED);
            draw("No rows.", M + 4, y + 10, text);
            text.setColor(TEXT);
            y += 14;
        }
        y += 10;
    }

    private float headerRow(ExportDoc.Table t, float[] w, float pad, float lh, boolean first) {
        int n = w.length;
        List<List<String>> heads = new ArrayList<>();
        int lines = 1;
        for (int i = 0; i < n; i++) {
            List<String> l = wrap(t.columns.get(i), w[i] - 2 * pad - 1, bold, 3);
            heads.add(l);
            lines = Math.max(lines, l.size());
        }
        float h = lines * lh + 5;
        if (first && y + h + lh * 2 + 8 > bottom()) {
            float size = text.getTextSize();
            newPage();
            text.setTextSize(size);
            bold.setTextSize(size);
            text.setColor(TEXT);
        }
        float avail = 0;
        for (float x : w) avail += x;
        fill.setColor(TEAL_SOFT);
        rect(M, y, M + avail, y + h, fill);
        float x = M;
        bold.setColor(TEAL_DARK);
        for (int i = 0; i < n; i++) {
            for (int li = 0; li < heads.get(i).size(); li++) draw(heads.get(i).get(li), x + pad, y + 2.5f + bold.getTextSize() + li * lh, bold);
            x += w[i];
            line.setColor(LINE);
            lineAt(x, y, x, y + h);
        }
        bold.setColor(TEXT);
        line.setColor(LINE);
        lineAt(M, y, M + avail, y);
        lineAt(M, y + h, M + avail, y + h);
        lineAt(M, y, M, y + h);
        y += h;
        return h;
    }

    // ------------------------------------------------------------------ helpers
    static boolean isNumber(String v) { return ExportXlsx.number(v) != null; }

    private void draw(String s, float x, float yy, Paint p) {
        if (!dry && c != null && s != null && !s.isEmpty()) c.drawText(s, x, yy, p);
    }

    private void rect(float l, float t, float r, float b, Paint p) {
        if (!dry && c != null) c.drawRect(l, t, r, b, p);
    }

    private void lineAt(float x1, float y1, float x2, float y2) {
        if (!dry && c != null) c.drawLine(x1, y1, x2, y2, line);
    }

    static String fit(String s, float width, Paint p) {
        if (s == null) return "";
        if (p.measureText(s) <= width) return s;
        String dots = "…";
        int end = s.length();
        while (end > 0 && p.measureText(s.substring(0, end) + dots) > width) end--;
        return s.substring(0, end) + dots;
    }

    /** Word wrap to at most maxLines lines; the last line is shortened with "…". */
    static List<String> wrap(String s, float width, Paint p, int maxLines) {
        List<String> out = new ArrayList<>();
        String rest = s == null ? "" : s.replace("\r", "").trim();
        if (rest.isEmpty()) { out.add(""); return out; }
        for (String para : rest.split("\n")) {
            String line = "";
            for (String word : para.trim().split("\\s+")) {
                String candidate = line.isEmpty() ? word : line + " " + word;
                if (p.measureText(candidate) <= width) { line = candidate; continue; }
                if (!line.isEmpty()) out.add(line);
                // a single word longer than the column: hard-break it
                while (p.measureText(word) > width && word.length() > 1) {
                    int cut = word.length();
                    while (cut > 1 && p.measureText(word.substring(0, cut)) > width) cut--;
                    out.add(word.substring(0, cut));
                    word = word.substring(cut);
                }
                line = word;
            }
            out.add(line);
        }
        if (out.size() > maxLines) {
            List<String> cut = new ArrayList<>(out.subList(0, maxLines));
            String last = cut.get(maxLines - 1) + " " + out.get(maxLines);
            cut.set(maxLines - 1, p.measureText(cut.get(maxLines - 1) + "…") <= width ? cut.get(maxLines - 1) + "…" : fit(last, width, p));
            return cut;
        }
        return out;
    }
}
