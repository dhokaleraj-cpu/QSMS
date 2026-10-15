package com.fourstar.qcmsapp;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.text.TextPaint;
import android.text.TextUtils;
import android.view.MotionEvent;
import android.view.View;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Native chart drawn on a Canvas (no libraries): vertical bars, stacked bars, horizontal bars,
 * lines with markers and a "share" view for pie charts. Same colours as the website
 * (core/kpi_service.SERIES). Slide sideways when there are many categories; tap a category to
 * see its exact values.
 */
final class GenChart extends View {
    static final int[] SERIES = {Color.parseColor("#00968f"), Color.parseColor("#eb6834"), Color.parseColor("#4a3aa7"),
        Color.parseColor("#eda100"), Color.parseColor("#e87ba4"), Color.parseColor("#2a78d6")};
    private static final int GRID = Color.parseColor("#e1e0d9");
    private static final int AXIS = Color.parseColor("#c3c2b7");
    private static final int INK = Color.parseColor("#52514e");

    private final String kind;               // bar | stacked | hbar | line | pie
    private final List<String> cats = new ArrayList<>();
    private final List<String> names = new ArrayList<>();
    private final List<double[]> values = new ArrayList<>();
    private final float d;
    private final TextPaint text = new TextPaint(Paint.ANTI_ALIAS_FLAG);
    private final TextPaint small = new TextPaint(Paint.ANTI_ALIAS_FLAG);
    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint line = new Paint(Paint.ANTI_ALIAS_FLAG);
    private float scrollX = 0, downX, downY, downScroll;
    private boolean dragging = false;
    private int selected = -1;

    GenChart(Context c, GenKpi.Chart chart) {
        super(c);
        d = c.getResources().getDisplayMetrics().density;
        kind = chart.kind == null ? "bar" : chart.kind;
        cats.addAll(chart.cats);
        for (Map.Entry<String, double[]> e : chart.series.entrySet()) { names.add(e.getKey()); values.add(e.getValue()); }
        text.setColor(INK);
        text.setTextSize(11.5f * d);
        small.setColor(INK);
        small.setTextSize(10f * d);
        line.setStrokeWidth(2 * d);
        setClickable(true);
    }

    private boolean multi() { return names.size() > 1 || (names.size() == 1 && !names.get(0).isEmpty()); }
    private boolean horizontal() { return kind.equals("hbar") || kind.equals("pie"); }

    private static boolean ok(double v) { return !Double.isNaN(v) && !Double.isInfinite(v); }

    /** plotly ",.4~g" style: 4 significant digits, k / M / G for large numbers. */
    static String fmt(double v) {
        if (!ok(v)) return "";
        double a = Math.abs(v);
        String suffix = "";
        if (a >= 1e9) { v /= 1e9; suffix = "G"; } else if (a >= 1e6) { v /= 1e6; suffix = "M"; } else if (a >= 1e4) { v /= 1e3; suffix = "k"; }
        String s = new java.math.BigDecimal(v).round(new java.math.MathContext(4)).stripTrailingZeros().toPlainString();
        if (s.equals("-0")) s = "0";
        return s + suffix;
    }

    private float legendHeight(int width) {
        if (!multi() && !kind.equals("pie")) return 0;
        if (kind.equals("pie")) return 0;
        int lines = 1; float x = 0;
        for (String n : names) {
            float w = 18 * d + small.measureText(n) + 12 * d;
            if (x + w > width && x > 0) { lines++; x = 0; }
            x += w;
        }
        return lines * 18 * d + 4 * d;
    }

    @Override
    protected void onMeasure(int widthSpec, int heightSpec) {
        int w = MeasureSpec.getSize(widthSpec);
        int h;
        if (horizontal()) h = Math.round(Math.max(1, cats.size()) * 28 * d + 16 * d);
        else h = Math.round(250 * d + legendHeight(w));
        setMeasuredDimension(w, Math.max(h, Math.round(80 * d)));
    }

    // ------------------------------------------------------------------ drawing
    @Override
    protected void onDraw(Canvas canvas) {
        canvas.drawColor(Color.parseColor("#fcfcfb"));
        if (getWidth() < 40 * d) return;
        if (cats.isEmpty() || values.isEmpty()) {
            canvas.drawText("No data", 12 * d, 24 * d, text);
            return;
        }
        if (horizontal()) drawHorizontal(canvas);
        else drawVertical(canvas);
    }

    private void drawHorizontal(Canvas canvas) {
        int width = getWidth();
        double[] v = values.get(0);
        boolean pie = kind.equals("pie");
        double total = 0, max = 0, min = 0;
        for (int i = 0; i < cats.size(); i++) if (ok(v[i])) { total += Math.max(v[i], 0); max = Math.max(max, v[i]); min = Math.min(min, v[i]); }
        String[] labels = new String[cats.size()];
        float valueW = 0;
        for (int i = 0; i < cats.size(); i++) {
            labels[i] = ok(v[i]) ? fmt(v[i]) + (pie && total > 0 ? String.format(Locale.US, " (%.1f%%)", 100 * Math.max(v[i], 0) / total) : "") : "";
            valueW = Math.max(valueW, small.measureText(labels[i]));
        }
        valueW += 8 * d;
        float labelW = 0;
        for (String c : cats) labelW = Math.max(labelW, text.measureText(c == null ? "" : c));
        labelW = Math.min(labelW + 10 * d, width * 0.42f);
        float x0 = labelW, x1 = Math.max(x0 + 20 * d, width - valueW);
        double span = max - min;
        if (span <= 0) span = 1;
        float zero = (float) (x0 + (0 - min) / span * (x1 - x0));
        float rowH = 28 * d, top = 8 * d;
        // vertical grid (website: grid on the value axis for hbar)
        line.setColor(GRID); line.setStrokeWidth(Math.max(1, d * 0.75f));
        for (int g = 0; g <= 4; g++) { float gx = x0 + (x1 - x0) * g / 4f; canvas.drawLine(gx, top, gx, top + cats.size() * rowH, line); }
        // plotly draws the first row at the bottom: last category on top
        for (int i = 0; i < cats.size(); i++) {
            int row = cats.size() - 1 - i;
            float y = top + row * rowH;
            String label = TextUtils.ellipsize(cats.get(i) == null ? "" : cats.get(i), text, Math.max(0, labelW - 10 * d), TextUtils.TruncateAt.END).toString();
            text.setColor(i == selected ? Ui.TEAL_DARK : INK);
            canvas.drawText(label, labelW - 6 * d - text.measureText(label), y + rowH / 2 + text.getTextSize() * 0.35f, text);
            if (!ok(v[i])) continue;
            float xv = (float) (x0 + (v[i] - min) / span * (x1 - x0));
            fill.setColor(pie ? SERIES[i % SERIES.length] : SERIES[0]);
            RectF r = new RectF(Math.min(zero, xv), y + rowH * 0.2f, Math.max(zero, xv), y + rowH * 0.8f);
            if (r.right - r.left < 1) r.right = r.left + 1;
            canvas.drawRect(r.left, r.top, r.right, r.bottom, fill);
            canvas.drawText(labels[i], Math.max(zero, xv) + 4 * d, y + rowH / 2 + small.getTextSize() * 0.35f, small);
        }
        text.setColor(INK);
        line.setColor(AXIS);
        canvas.drawLine(zero, top, zero, top + cats.size() * rowH, line);
    }

    private float slot, plotLeft, plotRight, plotTop, plotBottom;

    private float contentWidth() { return slot * cats.size(); }
    private float maxScroll() { return Math.max(0, contentWidth() - (plotRight - plotLeft)); }

    private void drawVertical(Canvas canvas) {
        int width = getWidth(), height = getHeight();
        boolean stacked = kind.equals("stacked");
        boolean isLine = kind.equals("line");
        // value range
        double max = 0, min = 0;
        for (int i = 0; i < cats.size(); i++) {
            double pos = 0, neg = 0;
            for (double[] s : values) {
                if (!ok(s[i])) continue;
                if (stacked) { if (s[i] >= 0) pos += s[i]; else neg += s[i]; }
                else { max = Math.max(max, s[i]); min = Math.min(min, s[i]); }
            }
            if (stacked) { max = Math.max(max, pos); min = Math.min(min, neg); }
        }
        if (isLine) {
            // lines zoom to the data like plotly (no forced zero when all values are well above it)
            double lo = Double.MAX_VALUE, hi = -Double.MAX_VALUE;
            for (double[] s : values) for (double x : s) if (ok(x)) { lo = Math.min(lo, x); hi = Math.max(hi, x); }
            if (lo != Double.MAX_VALUE) {
                double pad = (hi - lo) * 0.12;
                if (pad == 0) pad = Math.max(1, Math.abs(hi) * 0.1);
                min = lo - pad < 0 && lo >= 0 ? 0 : lo - pad; max = hi + pad;
            }
        }
        if (!isLine && max > 0) max *= 1.1;   // room for the value labels above the bars
        if (max == min) max = min + 1;
        double step = nice((max - min) / 4);
        double lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step;
        float legend = legendHeight(width);
        float axisW = 0;
        for (double t = lo; t <= hi + step / 2; t += step) axisW = Math.max(axisW, small.measureText(fmt(t)));
        plotLeft = axisW + 8 * d;
        plotRight = width - 8 * d;
        plotTop = legend + (isLine ? 10 : 18) * d;
        plotBottom = height - 30 * d;
        float plotW = plotRight - plotLeft;
        slot = Math.max(plotW / cats.size(), 42 * d);
        scrollX = Math.max(0, Math.min(scrollX, maxScroll()));

        // legend
        if (legend > 0) {
            float x = 0, y = 12 * d;
            for (int sIdx = 0; sIdx < names.size(); sIdx++) {
                String n = names.get(sIdx).isEmpty() ? "Value" : names.get(sIdx);
                float w = 18 * d + small.measureText(n) + 12 * d;
                if (x + w > width && x > 0) { x = 0; y += 18 * d; }
                fill.setColor(SERIES[sIdx % SERIES.length]);
                canvas.drawCircle(x + 6 * d, y - 4 * d, 5 * d, fill);
                canvas.drawText(n, x + 16 * d, y, small);
                x += w;
            }
        }

        // grid + y labels
        line.setStrokeWidth(Math.max(1, d * 0.75f));
        for (double t = lo; t <= hi + step / 2; t += step) {
            float y = yOf(t, lo, hi);
            line.setColor(GRID);
            canvas.drawLine(plotLeft, y, plotRight, y, line);
            String label = fmt(t);
            canvas.drawText(label, plotLeft - 6 * d - small.measureText(label), y + small.getTextSize() * 0.35f, small);
        }
        float zeroY = yOf(Math.max(lo, Math.min(0, hi)), lo, hi);

        canvas.save();
        canvas.clipRect(plotLeft, 0, plotRight, height);
        // x labels: skip some when they would overlap
        float widest = 0;
        for (String c : cats) widest = Math.max(widest, small.measureText(c == null ? "" : c));
        int every = Math.max(1, (int) Math.ceil((Math.min(widest, 110 * d) + 6 * d) / slot));
        for (int i = 0; i < cats.size(); i++) {
            float cx = plotLeft + slot * i + slot / 2 - scrollX;
            if (cx < plotLeft - slot || cx > plotRight + slot) continue;
            if (i % every == 0) {
                String lab = TextUtils.ellipsize(cats.get(i) == null ? "" : cats.get(i), small, Math.max(slot * every - 4 * d, 20 * d), TextUtils.TruncateAt.END).toString();
                small.setColor(i == selected ? Ui.TEAL_DARK : INK);
                canvas.drawText(lab, cx - small.measureText(lab) / 2, plotBottom + 16 * d, small);
                small.setColor(INK);
            }
            if (i == selected) {
                fill.setColor(Color.parseColor("#1A0F8B8D"));
                canvas.drawRect(cx - slot / 2, plotTop, cx + slot / 2, plotBottom, fill);
            }
        }
        if (isLine) drawLines(canvas, lo, hi);
        else drawBars(canvas, lo, hi, stacked, zeroY);
        canvas.restore();
        line.setColor(AXIS);
        canvas.drawLine(plotLeft, zeroY, plotRight, zeroY, line);
        if (maxScroll() > 0) {
            fill.setColor(Color.parseColor("#8A949C"));
            float viewW = plotRight - plotLeft;
            float barW = Math.max(30 * d, viewW * viewW / contentWidth());
            float barX = plotLeft + (viewW - barW) * (scrollX / maxScroll());
            canvas.drawRoundRect(new RectF(barX, height - 5 * d, barX + barW, height - 2 * d), 2 * d, 2 * d, fill);
        }
        if (selected >= 0 && selected < cats.size()) drawTip(canvas, width);
    }

    private float yOf(double v, double lo, double hi) {
        return (float) (plotBottom - (v - lo) / (hi - lo) * (plotBottom - plotTop));
    }

    private void drawBars(Canvas canvas, double lo, double hi, boolean stacked, float zeroY) {
        int n = values.size();
        boolean grouped = !stacked && n > 1;
        float barW = slot * (1 - 0.35f);
        for (int i = 0; i < cats.size(); i++) {
            float left = plotLeft + slot * i + (slot - barW) / 2 - scrollX;
            if (left > plotRight || left + barW < plotLeft) continue;
            double pos = 0, neg = 0;
            for (int s = 0; s < n; s++) {
                double v = values.get(s)[i];
                if (!ok(v)) continue;
                fill.setColor(SERIES[s % SERIES.length]);
                float l = grouped ? left + barW * s / n : left, r = grouped ? left + barW * (s + 1) / n : left + barW;
                float y0, y1;
                if (stacked) {
                    double base = v >= 0 ? pos : neg;
                    y0 = yOf(base, lo, hi); y1 = yOf(base + v, lo, hi);
                    if (v >= 0) pos += v; else neg += v;
                } else { y0 = zeroY; y1 = yOf(v, lo, hi); }
                canvas.drawRect(l, Math.min(y0, y1), r, Math.max(y0, y1), fill);
                if (!stacked && n == 1) {
                    String t = fmt(v);
                    float tw = small.measureText(t);
                    canvas.drawText(t, (l + r) / 2 - tw / 2, Math.min(y0, y1) - 4 * d, small);
                }
            }
        }
    }

    private void drawLines(Canvas canvas, double lo, double hi) {
        line.setStrokeWidth(2 * d);
        for (int s = 0; s < values.size(); s++) {
            double[] v = values.get(s);
            int color = SERIES[s % SERIES.length];
            line.setColor(color);
            float px = 0, py = 0; boolean has = false;
            for (int i = 0; i < cats.size(); i++) {
                if (!ok(v[i])) { continue; }   // plotly connects the points of the same series across gaps
                float x = plotLeft + slot * i + slot / 2 - scrollX, y = yOf(v[i], lo, hi);
                if (has) canvas.drawLine(px, py, x, y, line);
                px = x; py = y; has = true;
            }
            for (int i = 0; i < cats.size(); i++) {
                if (!ok(v[i])) continue;
                float x = plotLeft + slot * i + slot / 2 - scrollX, y = yOf(v[i], lo, hi);
                fill.setColor(Color.parseColor("#fcfcfb"));
                canvas.drawCircle(x, y, 5.5f * d, fill);
                fill.setColor(color);
                canvas.drawCircle(x, y, 3.8f * d, fill);
            }
        }
        line.setStrokeWidth(Math.max(1, d * 0.75f));
    }

    private void drawTip(Canvas canvas, int width) {
        List<String> lines = new ArrayList<>();
        lines.add(cats.get(selected) == null ? "" : cats.get(selected));
        for (int s = 0; s < names.size(); s++) {
            double v = values.get(s)[selected];
            if (!ok(v)) continue;
            String n = names.get(s).isEmpty() ? "Value" : names.get(s);
            lines.add(n + ": " + GenUtil.fmt(v, v == Math.rint(v) ? 0 : 2));
        }
        float w = 0;
        for (String l : lines) w = Math.min(Math.max(w, small.measureText(l)), width - 24 * d);
        float h = lines.size() * 15 * d + 8 * d;
        float cx = plotLeft + slot * selected + slot / 2 - scrollX;
        float x = Math.max(4 * d, Math.min(cx - w / 2 - 6 * d, width - w - 16 * d));
        float y = plotTop;
        fill.setColor(Color.parseColor("#F2173233"));
        canvas.drawRoundRect(new RectF(x, y, x + w + 12 * d, y + h), 6 * d, 6 * d, fill);
        small.setColor(Color.WHITE);
        for (int i = 0; i < lines.size(); i++) {
            String l = TextUtils.ellipsize(lines.get(i), small, w, TextUtils.TruncateAt.END).toString();
            canvas.drawText(l, x + 6 * d, y + 15 * d * (i + 1), small);
        }
        small.setColor(INK);
    }

    static double nice(double raw) {
        if (raw <= 0 || !ok(raw)) return 1;
        double exp = Math.pow(10, Math.floor(Math.log10(raw)));
        double f = raw / exp;
        double n = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
        return n * exp;
    }

    // ------------------------------------------------------------------ touch: slide sideways, tap for values
    @Override
    public boolean onTouchEvent(MotionEvent e) {
        switch (e.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                downX = e.getX(); downY = e.getY(); downScroll = scrollX; dragging = false;
                return true;
            case MotionEvent.ACTION_MOVE: {
                float dx = e.getX() - downX, dy = e.getY() - downY;
                if (!horizontal() && maxScroll() > 0 && (dragging || (Math.abs(dx) > 8 * d && Math.abs(dx) > Math.abs(dy)))) {
                    if (!dragging && getParent() != null) getParent().requestDisallowInterceptTouchEvent(true);
                    dragging = true;
                    scrollX = Math.max(0, Math.min(downScroll - dx, maxScroll()));
                    invalidate();
                }
                return true;
            }
            case MotionEvent.ACTION_UP:
                if (!dragging) {
                    int hit = hit(e.getX(), e.getY());
                    selected = hit == selected ? -1 : hit;
                    invalidate();
                    performClick();
                }
                if (getParent() != null) getParent().requestDisallowInterceptTouchEvent(false);
                dragging = false;
                return true;
            case MotionEvent.ACTION_CANCEL:
                if (getParent() != null) getParent().requestDisallowInterceptTouchEvent(false);
                dragging = false;
                return true;
            default:
                return true;
        }
    }

    @Override public boolean performClick() { return super.performClick(); }

    private int hit(float x, float y) {
        if (cats.isEmpty()) return -1;
        if (horizontal()) {
            int row = (int) ((y - 8 * d) / (28 * d));
            int i = cats.size() - 1 - row;
            return i >= 0 && i < cats.size() ? i : -1;
        }
        if (x < plotLeft || x > plotRight || slot <= 0) return -1;
        int i = (int) ((x - plotLeft + scrollX) / slot);
        return i >= 0 && i < cats.size() ? i : -1;
    }
}
