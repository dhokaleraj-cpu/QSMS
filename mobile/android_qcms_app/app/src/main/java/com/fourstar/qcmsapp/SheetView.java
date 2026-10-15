package com.fourstar.qcmsapp;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.text.TextUtils;
import android.text.TextPaint;
import android.view.GestureDetector;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.view.View;
import android.widget.OverScroller;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Spreadsheet grid drawn on a canvas: slide freely in every direction with one finger (diagonal
 * too), fling, pinch to zoom, frozen header row and frozen first column, visible scroll bars,
 * tap a row to open it. Works the same for 10 or 10,000 rows (only visible cells are drawn).
 */
public final class SheetView extends View {
    public interface RowClick { void onRow(int index); }

    private final List<String> columns = new ArrayList<>();
    private final List<String[]> rows = new ArrayList<>();
    private float[] widths = new float[0];
    private int statusColumn = -1;
    private final TextPaint text = new TextPaint(Paint.ANTI_ALIAS_FLAG);
    private final TextPaint bold = new TextPaint(Paint.ANTI_ALIAS_FLAG);
    private final Paint fill = new Paint();
    private final Paint line = new Paint();
    private final OverScroller scroller;
    private final GestureDetector gestures;
    private final ScaleGestureDetector scaler;
    private float scrollX, scrollY, scale = 1f;
    private int maxHeightPx;
    private RowClick click;
    private int selected = -1;
    private final float density;

    public SheetView(Context c) {
        super(c);
        density = c.getResources().getDisplayMetrics().density;
        scroller = new OverScroller(c);
        maxHeightPx = Math.round(420 * density);
        text.setColor(Ui.TEXT);
        bold.setColor(Ui.TEAL_DARK);
        bold.setTypeface(Typeface.DEFAULT_BOLD);
        line.setColor(Color.parseColor("#DDE7E7"));
        line.setStrokeWidth(Math.max(1f, density * 0.75f));
        setFocusable(true);
        setClickable(true);
        gestures = new GestureDetector(c, new GestureDetector.SimpleOnGestureListener() {
            @Override public boolean onDown(MotionEvent e) {
                scroller.forceFinished(true);
                return true;
            }
            @Override public boolean onScroll(MotionEvent e1, MotionEvent e2, float dx, float dy) {
                scrollBy(dx, dy);
                return true;
            }
            @Override public boolean onFling(MotionEvent e1, MotionEvent e2, float vx, float vy) {
                scroller.fling((int) scrollX, (int) scrollY, (int) -vx, (int) -vy, 0, (int) maxScrollX(), 0, (int) maxScrollY());
                postInvalidateOnAnimation();
                return true;
            }
            @Override public boolean onSingleTapUp(MotionEvent e) {
                int row = rowAt(e.getY());
                if (row >= 0) {
                    selected = row;
                    invalidate();
                    if (click != null) click.onRow(row);
                }
                return true;
            }
        });
        scaler = new ScaleGestureDetector(c, new ScaleGestureDetector.SimpleOnScaleGestureListener() {
            @Override public boolean onScale(ScaleGestureDetector d) {
                scale = Math.max(0.6f, Math.min(2.2f, scale * d.getScaleFactor()));
                measureColumns();
                clamp();
                invalidate();
                return true;
            }
        });
        measureColumns();
    }

    public void setData(List<String> cols, List<String[]> data) {
        columns.clear();
        columns.addAll(cols);
        rows.clear();
        rows.addAll(data);
        statusColumn = -1;
        for (int i = 0; i < columns.size(); i++) {
            String k = columns.get(i).toLowerCase(Locale.ROOT);
            if (k.contains("status") || k.contains("result") || k.contains("disposition")) { statusColumn = i; break; }
        }
        scrollX = 0; scrollY = 0; selected = -1;
        measureColumns();
        requestLayout();
        invalidate();
    }

    public void setOnRowClick(RowClick c) { click = c; }
    /** Copies of the grid content (for PDF / Excel export). */
    public List<String> columnsData() { return new ArrayList<>(columns); }
    public List<String[]> rowsData() { return new ArrayList<>(rows); }
    public void setMaxHeightDp(int dp) { maxHeightPx = Math.round(dp * density); requestLayout(); }
    public int rowCount() { return rows.size(); }

    private float rowH() { return 36 * density * scale; }
    private float headH() { return 40 * density * scale; }
    private float pad() { return 9 * density * scale; }

    private void measureColumns() {
        text.setTextSize(12.5f * density * scale);
        bold.setTextSize(12f * density * scale);
        widths = new float[columns.size()];
        for (int i = 0; i < columns.size(); i++) {
            float w = bold.measureText(columns.get(i));
            int sample = Math.min(rows.size(), 400);
            for (int r = 0; r < sample; r++) {
                String[] row = rows.get(r);
                if (i < row.length && row[i] != null) w = Math.max(w, text.measureText(row[i]));
            }
            widths[i] = Math.min(Math.max(w + 2 * pad(), 60 * density * scale), 280 * density * scale);
        }
    }

    private float contentWidth() {
        float w = 0;
        for (float x : widths) w += x;
        return w;
    }

    private float contentHeight() { return headH() + rows.size() * rowH(); }
    private float maxScrollX() { return Math.max(0, contentWidth() - getWidth()); }
    private float maxScrollY() { return Math.max(0, contentHeight() - getHeight()); }

    private void clamp() {
        scrollX = Math.max(0, Math.min(scrollX, maxScrollX()));
        scrollY = Math.max(0, Math.min(scrollY, maxScrollY()));
    }

    public void scrollBy(float dx, float dy) {
        scrollX += dx;
        scrollY += dy;
        clamp();
        invalidate();
    }

    private int rowAt(float y) {
        if (y < headH()) return -1;
        int r = (int) ((y - headH() + scrollY) / rowH());
        return r >= 0 && r < rows.size() ? r : -1;
    }

    @Override
    protected void onMeasure(int widthSpec, int heightSpec) {
        int w = MeasureSpec.getSize(widthSpec);
        int wanted = (int) Math.ceil(contentHeight()) + Math.round(8 * density);
        int mode = MeasureSpec.getMode(heightSpec);
        int h;
        if (mode == MeasureSpec.EXACTLY) h = MeasureSpec.getSize(heightSpec);
        else h = Math.min(wanted, maxHeightPx);
        setMeasuredDimension(w, Math.max(h, Math.round(80 * density)));
    }

    @Override
    public boolean onTouchEvent(MotionEvent e) {
        if (e.getActionMasked() == MotionEvent.ACTION_DOWN && getParent() != null
            && (maxScrollX() > 0 || maxScrollY() > 0)) {
            getParent().requestDisallowInterceptTouchEvent(true);   // the grid owns the finger, like Excel
        }
        scaler.onTouchEvent(e);
        if (!scaler.isInProgress()) gestures.onTouchEvent(e);
        if ((e.getActionMasked() == MotionEvent.ACTION_UP || e.getActionMasked() == MotionEvent.ACTION_CANCEL) && getParent() != null) {
            getParent().requestDisallowInterceptTouchEvent(false);
        }
        return true;
    }

    @Override
    public void computeScroll() {
        if (scroller.computeScrollOffset()) {
            scrollX = scroller.getCurrX();
            scrollY = scroller.getCurrY();
            clamp();
            postInvalidateOnAnimation();
        }
    }

    @Override
    protected void onSizeChanged(int w, int h, int ow, int oh) {
        clamp();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        int width = getWidth(), height = getHeight();
        canvas.drawColor(Color.WHITE);
        if (columns.isEmpty()) return;
        float rh = rowH(), hh = headH(), pad = pad();
        float firstW = widths[0];
        int firstRow = Math.max(0, (int) (scrollY / rh));
        int lastRow = Math.min(rows.size() - 1, (int) ((scrollY + height - hh) / rh) + 1);
        float baseline = rh / 2f + text.getTextSize() * 0.35f;

        // body cells (scrolling part)
        canvas.save();
        canvas.clipRect(firstW, hh, width, height);
        for (int r = firstRow; r <= lastRow; r++) {
            float top = hh + r * rh - scrollY;
            fill.setColor(r == selected ? Color.parseColor("#D5EEEE") : (r % 2 == 1 ? Color.parseColor("#F7FAFA") : Color.WHITE));
            canvas.drawRect(firstW, top, width, top + rh, fill);
            float x = firstW - scrollX;
            String[] row = rows.get(r);
            for (int c = 1; c < widths.length; c++) {
                float w = widths[c];
                if (x + w >= firstW && x <= width) {
                    String v = c < row.length && row[c] != null ? row[c] : "";
                    if (c == statusColumn && !v.isEmpty()) drawChip(canvas, v, x + pad, top, rh);
                    else canvas.drawText(fit(v, w - 2 * pad, text), x + pad, top + baseline, text);
                    canvas.drawLine(x + w, top, x + w, top + rh, line);
                }
                x += w;
            }
            canvas.drawLine(firstW, top + rh, width, top + rh, line);
        }
        canvas.restore();

        // frozen first column
        canvas.save();
        canvas.clipRect(0, hh, firstW, height);
        for (int r = firstRow; r <= lastRow; r++) {
            float top = hh + r * rh - scrollY;
            fill.setColor(r == selected ? Color.parseColor("#C8E8E8") : (r % 2 == 1 ? Color.parseColor("#F1F7F7") : Color.parseColor("#FBFDFD")));
            canvas.drawRect(0, top, firstW, top + rh, fill);
            String[] row = rows.get(r);
            String v = row.length > 0 && row[0] != null ? row[0] : "";
            bold.setColor(Ui.TEXT);
            canvas.drawText(fit(v, firstW - 2 * pad, bold), pad, top + baseline, bold);
            canvas.drawLine(0, top + rh, firstW, top + rh, line);
        }
        canvas.restore();

        // frozen header row
        fill.setColor(Ui.TEAL_SOFT);
        canvas.drawRect(0, 0, width, hh, fill);
        bold.setColor(Ui.TEAL_DARK);
        float hb = hh / 2f + bold.getTextSize() * 0.35f;
        canvas.save();
        canvas.clipRect(firstW, 0, width, hh);
        float x = firstW - scrollX;
        for (int c = 1; c < widths.length; c++) {
            if (x + widths[c] >= firstW && x <= width) {
                canvas.drawText(fit(columns.get(c), widths[c] - 2 * pad, bold), x + pad, hb, bold);
                canvas.drawLine(x + widths[c], 0, x + widths[c], hh, line);
            }
            x += widths[c];
        }
        canvas.restore();
        canvas.drawText(fit(columns.get(0), firstW - 2 * pad, bold), pad, hb, bold);
        line.setColor(Ui.LINE_STRONG);
        canvas.drawLine(0, hh, width, hh, line);
        canvas.drawLine(firstW, 0, firstW, height, line);
        line.setColor(Color.parseColor("#DDE7E7"));

        if (rows.isEmpty()) {
            text.setColor(Ui.MUTED);
            canvas.drawText("No rows", pad, hh + baseline, text);
            text.setColor(Ui.TEXT);
        }

        // scroll bars (always visible when there is more to see)
        fill.setColor(Color.parseColor("#8A949C"));
        float t = 4 * density;
        if (maxScrollX() > 0) {
            float viewW = width - firstW, total = contentWidth() - firstW;
            float barW = Math.max(30 * density, viewW * viewW / total);
            float barX = firstW + (viewW - barW) * (scrollX / maxScrollX());
            canvas.drawRoundRect(new RectF(barX, height - t - 2, barX + barW, height - 2), t, t, fill);
        }
        if (maxScrollY() > 0) {
            float viewH = height - hh, total = contentHeight() - hh;
            float barH = Math.max(30 * density, viewH * viewH / total);
            float barY = hh + (viewH - barH) * (scrollY / maxScrollY());
            canvas.drawRoundRect(new RectF(width - t - 2, barY, width - 2, barY + barH), t, t, fill);
        }
    }

    private void drawChip(Canvas canvas, String v, float x, float top, float rh) {
        String tone = Ui.tone(v);
        int fg = "green".equals(tone) ? Ui.GREEN_FG : "red".equals(tone) ? Ui.RED_FG : "amber".equals(tone) ? Ui.AMBER_FG : "teal".equals(tone) ? Ui.TEAL_DARK : Ui.GREY_FG;
        int bg = "green".equals(tone) ? Ui.GREEN_BG : "red".equals(tone) ? Ui.RED_BG : "amber".equals(tone) ? Ui.AMBER_BG : "teal".equals(tone) ? Ui.TEAL_SOFT : Ui.GREY_BG;
        String label = Ui.pretty(v);
        float w = bold.measureText(label) + 16 * density * scale;
        float h = rh * 0.62f;
        fill.setColor(bg);
        canvas.drawRoundRect(new RectF(x, top + (rh - h) / 2, x + w, top + (rh + h) / 2), h / 2, h / 2, fill);
        bold.setColor(fg);
        canvas.drawText(label, x + 8 * density * scale, top + rh / 2f + bold.getTextSize() * 0.35f, bold);
        bold.setColor(Ui.TEAL_DARK);
    }

    private static String fit(String value, float width, TextPaint paint) {
        if (value == null) return "";
        return TextUtils.ellipsize(value, paint, Math.max(0, width), TextUtils.TruncateAt.END).toString();
    }
}
