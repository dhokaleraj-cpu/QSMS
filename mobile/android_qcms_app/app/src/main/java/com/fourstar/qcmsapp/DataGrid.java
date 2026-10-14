package com.fourstar.qcmsapp;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.List;

/**
 * Data grid that scrolls left / right and up / down, with a fixed header row and a fixed
 * first column (like a frozen-pane spreadsheet). Column widths are measured from the content.
 */
public final class DataGrid extends LinearLayout {
    public interface RowClick { void onRow(int index); }

    private final HorizontalScrollView headScroll;
    private final HorizontalScrollView bodyScroll;
    private final ScrollView leftScroll;
    private final ScrollView bodyVScroll;
    private boolean syncing = false;

    public DataGrid(Context c, List<String> columns, List<List<String>> rows, int maxHeightDp, RowClick click) {
        super(c);
        setOrientation(VERTICAL);
        setBackground(Ui.round(Color.WHITE, Ui.LINE_STRONG, 1, 10, c));
        setPadding(1, 1, 1, 1);
        setClipToOutline(true);

        int n = columns.size();
        int[] widths = new int[n];
        Paint paint = new Paint();
        paint.setTextSize(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, 12.5f, c.getResources().getDisplayMetrics()));
        int pad = Ui.dp(c, 20);
        for (int i = 0; i < n; i++) {
            float w = paint.measureText(columns.get(i)) * 1.08f;
            for (List<String> row : rows) {
                String v = i < row.size() ? row.get(i) : "";
                w = Math.max(w, paint.measureText(v == null ? "" : v));
            }
            widths[i] = Math.min(Math.max((int) w + pad, Ui.dp(c, 64)), Ui.dp(c, 260));
        }
        int rowH = Ui.dp(c, 38);

        // ---- header: fixed corner + horizontally scrolling header cells
        LinearLayout head = new LinearLayout(c);
        head.setOrientation(HORIZONTAL);
        head.setBackgroundColor(Ui.TEAL_SOFT);
        head.addView(cell(c, columns.get(0), widths[0], rowH, true, false), new LayoutParams(widths[0], rowH));
        headScroll = new HorizontalScrollView(c);
        headScroll.setHorizontalScrollBarEnabled(false);
        LinearLayout headCells = new LinearLayout(c);
        headCells.setOrientation(HORIZONTAL);
        for (int i = 1; i < n; i++) headCells.addView(cell(c, columns.get(i), widths[i], rowH, true, false), new LayoutParams(widths[i], rowH));
        headScroll.addView(headCells);
        head.addView(headScroll, new LayoutParams(0, rowH, 1));
        addView(head, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, rowH));

        // ---- body: fixed first column + 2-D scrolling cells
        LinearLayout body = new LinearLayout(c);
        body.setOrientation(HORIZONTAL);
        leftScroll = new ScrollView(c);
        leftScroll.setVerticalScrollBarEnabled(false);
        LinearLayout leftCol = new LinearLayout(c);
        leftCol.setOrientation(VERTICAL);
        bodyVScroll = new ScrollView(c);
        bodyVScroll.setScrollbarFadingEnabled(false);
        bodyScroll = new HorizontalScrollView(c);
        bodyScroll.setScrollbarFadingEnabled(false);
        LinearLayout cells = new LinearLayout(c);
        cells.setOrientation(VERTICAL);
        for (int r = 0; r < rows.size(); r++) {
            List<String> row = rows.get(r);
            boolean even = r % 2 == 1;
            final int index = r;
            TextView first = cell(c, row.isEmpty() ? "" : row.get(0), widths[0], rowH, false, even);
            first.setTypeface(Typeface.DEFAULT_BOLD);
            leftCol.addView(first, new LayoutParams(widths[0], rowH));
            LinearLayout line = new LinearLayout(c);
            line.setOrientation(HORIZONTAL);
            for (int i = 1; i < n; i++) line.addView(cell(c, i < row.size() ? row.get(i) : "", widths[i], rowH, false, even), new LayoutParams(widths[i], rowH));
            cells.addView(line);
            if (click != null) {
                first.setOnClickListener(v -> click.onRow(index));
                line.setOnClickListener(v -> click.onRow(index));
            }
        }
        if (rows.isEmpty()) {
            TextView none = Ui.text(c, "No rows", 12, Ui.MUTED, false);
            none.setPadding(Ui.dp(c, 12), Ui.dp(c, 12), Ui.dp(c, 12), Ui.dp(c, 12));
            leftCol.addView(none);
        }
        leftScroll.addView(leftCol);
        bodyScroll.addView(cells);
        bodyVScroll.addView(bodyScroll);
        body.addView(leftScroll, new LayoutParams(widths[0], ViewGroup.LayoutParams.MATCH_PARENT));
        View shadow = new View(c);
        shadow.setBackgroundColor(Ui.LINE_STRONG);
        body.addView(shadow, new LayoutParams(Math.max(1, Ui.dp(c, 1)), ViewGroup.LayoutParams.MATCH_PARENT));
        body.addView(bodyVScroll, new LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1));
        int height = Math.min(rowH * Math.max(rows.size(), 1) + Ui.dp(c, 4), Ui.dp(c, maxHeightDp));
        FrameLayout bodyFrame = new FrameLayout(c);
        bodyFrame.addView(body, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, height));
        addView(bodyFrame, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, height));

        // inside a scrolling page the grid keeps the finger while it can still scroll itself
        if (rowH * rows.size() + Ui.dp(c, 4) > height) {
            View.OnTouchListener hold = (v, e) -> {
                int action = e.getActionMasked();
                if (action == MotionEvent.ACTION_DOWN || action == MotionEvent.ACTION_MOVE) {
                    if (getParent() != null) getParent().requestDisallowInterceptTouchEvent(true);
                }
                return false;
            };
            bodyVScroll.setOnTouchListener(hold);
            leftScroll.setOnTouchListener(hold);
        }

        // keep the frozen header / first column aligned with the scrolling cells
        bodyScroll.setOnScrollChangeListener((v, x, y, ox, oy) -> sync(() -> headScroll.scrollTo(x, 0)));
        headScroll.setOnScrollChangeListener((v, x, y, ox, oy) -> sync(() -> bodyScroll.scrollTo(x, bodyScroll.getScrollY())));
        bodyVScroll.setOnScrollChangeListener((v, x, y, ox, oy) -> sync(() -> leftScroll.scrollTo(0, y)));
        leftScroll.setOnScrollChangeListener((v, x, y, ox, oy) -> sync(() -> bodyVScroll.scrollTo(0, y)));
    }

    private void sync(Runnable r) {
        if (syncing) return;
        syncing = true;
        try { r.run(); } finally { syncing = false; }
    }

    private static TextView cell(Context c, String value, int width, int height, boolean header, boolean even) {
        TextView t = Ui.text(c, value == null ? "" : value, header ? 11.5f : 12.5f, header ? Ui.TEAL_DARK : Ui.TEXT, header);
        t.setSingleLine(true);
        t.setEllipsize(TextUtils.TruncateAt.END);
        t.setGravity(Gravity.CENTER_VERTICAL);
        t.setPadding(Ui.dp(c, 9), 0, Ui.dp(c, 9), 0);
        t.setWidth(width);
        t.setHeight(height);
        if (!header) t.setBackgroundColor(even ? Color.parseColor("#F7FAFA") : Color.WHITE);
        return t;
    }
}
