package com.fourstar.qcmsapp;

import android.content.Context;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/**
 * Spreadsheet grid block: toolbar (rows × columns, full-screen button) + SheetView
 * (slide in every direction, fling, pinch-zoom, frozen header and first column).
 */
public final class DataGrid extends LinearLayout {
    public interface RowClick { void onRow(int index); }

    private final SheetView sheet;

    public DataGrid(Context c, List<String> columns, List<List<String>> rows, int maxHeightDp, RowClick click) {
        this(c, "", columns, rows, maxHeightDp, click);
    }

    public DataGrid(Context c, String title, List<String> columns, List<List<String>> rows, int maxHeightDp, RowClick click) {
        super(c);
        setOrientation(VERTICAL);
        LinearLayout bar = Ui.hbox(c);
        TextView info = Ui.text(c, rows.size() + " row(s) × " + columns.size() + " column(s) · slide ↔ ↕ · pinch to zoom", 11, Ui.MUTED, false);
        bar.addView(info, Ui.weight(1));
        TextView full = Ui.text(c, "⤢ Full screen", 12, Ui.TEAL_DARK, true);
        full.setPadding(Ui.dp(c, 10), Ui.dp(c, 6), Ui.dp(c, 4), Ui.dp(c, 6));
        bar.addView(full);
        addView(bar, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        List<String[]> data = new ArrayList<>();
        for (List<String> row : rows) data.add(row.toArray(new String[0]));
        sheet = new SheetView(c);
        sheet.setData(columns, data);
        sheet.setMaxHeightDp(maxHeightDp);
        if (click != null) sheet.setOnRowClick(click::onRow);
        LinearLayout frame = Ui.vbox(c);
        frame.setBackground(Ui.round(android.graphics.Color.WHITE, Ui.LINE_STRONG, 1, 10, c));
        frame.setPadding(1, 1, 1, 1);
        frame.setClipToOutline(true);
        frame.addView(sheet, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        addView(frame, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        full.setOnClickListener(v -> {
            if (c instanceof MainActivity) ((MainActivity) c).push(new SheetScreen((MainActivity) c, title.isEmpty() ? "Grid" : title, columns, data, click));
        });
    }

    public SheetView sheet() { return sheet; }

    /** Full-screen spreadsheet view of the same rows. */
    static final class SheetScreen extends Screen {
        private final String title;
        private final List<String> columns;
        private final List<String[]> rows;
        private final RowClick click;

        SheetScreen(MainActivity a, String title, List<String> columns, List<String[]> rows, RowClick click) {
            super(a);
            this.title = title; this.columns = columns; this.rows = rows; this.click = click;
        }

        @Override public String title() { return title; }
        @Override public String subtitle() { return rows.size() + " row(s) · slide in any direction · pinch to zoom"; }
        @Override public int tab() { return -1; }

        @Override
        public View build() {
            SheetView s = new SheetView(a);
            s.setData(columns, rows);
            if (click != null) s.setOnRowClick(click::onRow);
            return s;
        }
    }
}
