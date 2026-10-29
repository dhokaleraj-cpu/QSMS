package com.fourstar.qcmsapp;

import android.graphics.Typeface;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * R39 · Horizontal entry grid for the RMTC Part Worksheet (web rmtc_pages.render_part, R38): one COLUMN per stored row
 * (chemistry element / Jominy distance), one LINE per field - Minimum / Maximum (spec), Actual (entry), Applicable
 * (tick), Status (calculated). Edits are written straight into the row JSONObjects, so the save payload keeps exactly
 * the stored row shape. Scrolls sideways on a phone.
 */
final class IncRmtcHGrid {
    static final int INFO = 0, NUMBER = 1, BOOL = 2, STATUS = 3;

    static final class Line {
        final String title, field; final int kind;
        Line(String title, String field, int kind) { this.title = title; this.field = field; this.kind = kind; }
    }

    interface Header { String of(JSONObject row); }

    private final MainActivity a;
    private final List<Line> lines = new ArrayList<>();
    private final List<JSONObject> rows = new ArrayList<>();
    private final List<TextView[]> infoCells = new ArrayList<>();
    private Header header = r -> Lookups.j(r, "element");
    private Runnable changed;
    private final LinearLayout table;
    private final HorizontalScrollView root;

    IncRmtcHGrid(MainActivity a) {
        this.a = a;
        root = new HorizontalScrollView(a);
        table = Ui.vbox(a);
        root.addView(table);
    }

    IncRmtcHGrid header(Header h) { header = h; return this; }
    IncRmtcHGrid line(String title, String field, int kind) { lines.add(new Line(title, field, kind)); return this; }
    IncRmtcHGrid onChanged(Runnable r) { changed = r; return this; }
    View view() { return root; }
    List<JSONObject> rows() { return rows; }

    void setRows(List<JSONObject> list) {
        rows.clear();
        if (list != null) rows.addAll(list);
        build();
    }

    private int w(int dp) { return Ui.dp(a, dp); }

    private TextView cell(String text, boolean head, int width) {
        TextView t = Ui.text(a, text, 12, head ? Ui.TEXT : Ui.TEXT, head);
        t.setGravity(Gravity.CENTER);
        t.setPadding(w(4), w(6), w(4), w(6));
        t.setBackgroundColor(head ? Ui.TEAL_SOFT : Ui.PANEL);
        t.setLayoutParams(new LinearLayout.LayoutParams(width, LinearLayout.LayoutParams.WRAP_CONTENT));
        return t;
    }

    private void build() {
        table.removeAllViews();
        infoCells.clear();
        int first = w(118), col = w(78);
        LinearLayout head = Ui.hbox(a);
        TextView corner = cell(lines.isEmpty() ? "" : "", true, first);
        head.addView(corner);
        for (JSONObject r : rows) head.addView(cell(header.of(r), true, col));
        table.addView(head);
        for (Line l : lines) {
            LinearLayout line = Ui.hbox(a);
            TextView title = cell(l.title, true, first);
            title.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
            line.addView(title);
            TextView[] infos = new TextView[rows.size()];
            for (int i = 0; i < rows.size(); i++) {
                JSONObject r = rows.get(i);
                if (l.kind == NUMBER) {
                    EditText e = new EditText(a);
                    e.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL | InputType.TYPE_NUMBER_FLAG_SIGNED);
                    e.setTextSize(13);
                    e.setGravity(Gravity.CENTER);
                    e.setSingleLine(true);
                    e.setText(text(r.opt(l.field)));
                    e.setLayoutParams(new LinearLayout.LayoutParams(col, LinearLayout.LayoutParams.WRAP_CONTENT));
                    e.addTextChangedListener(new TextWatcher() {
                        @Override public void beforeTextChanged(CharSequence s, int x, int y, int z) { }
                        @Override public void onTextChanged(CharSequence s, int x, int y, int z) { }
                        @Override public void afterTextChanged(Editable s) {
                            Double v = parse(s == null ? "" : s.toString());
                            try { r.put(l.field, v == null ? JSONObject.NULL : (Object) v); } catch (Exception ignored) { }
                            fire();
                        }
                    });
                    line.addView(e);
                } else if (l.kind == BOOL) {
                    CheckBox c = new CheckBox(a);
                    c.setChecked(r.optBoolean(l.field, true));
                    c.setLayoutParams(new LinearLayout.LayoutParams(col, LinearLayout.LayoutParams.WRAP_CONTENT));
                    c.setOnCheckedChangeListener((b, on) -> {
                        try { r.put(l.field, on); } catch (Exception ignored) { }
                        fire();
                    });
                    line.addView(c);
                } else {
                    TextView t = cell(l.kind == STATUS ? Ui.pretty(text(r.opt(l.field))) : dash(r.opt(l.field)), false, col);
                    if (l.kind == STATUS) t.setTypeface(Typeface.DEFAULT_BOLD);
                    infos[i] = t;
                    line.addView(t);
                }
            }
            infoCells.add(infos);
            table.addView(line);
        }
        refresh();
    }

    /** Re-reads the INFO / STATUS lines (calculated values) from the rows. */
    void refresh() {
        for (int li = 0; li < lines.size() && li < infoCells.size(); li++) {
            Line l = lines.get(li);
            TextView[] cells = infoCells.get(li);
            for (int i = 0; i < cells.length && i < rows.size(); i++) {
                if (cells[i] == null) continue;
                Object v = rows.get(i).opt(l.field);
                if (l.kind == STATUS) {
                    String s = text(v);
                    cells[i].setText(s.isEmpty() ? "-" : Ui.pretty(s));
                    String tone = Ui.tone(s);
                    String u = s.toUpperCase(Locale.ROOT);
                    cells[i].setTextColor(u.contains("NOT_APPLICABLE") ? Ui.MUTED : u.contains("FAIL") || u.contains("REJECT") ? Ui.RED_FG
                        : u.contains("PASS") || u.equals("OK") || "green".equals(tone) ? Ui.GREEN_FG : Ui.TEXT);
                } else cells[i].setText(dash(v));
            }
        }
    }

    private void fire() { if (changed != null) changed.run(); }

    static Double parse(String s) {
        String t = s == null ? "" : s.trim().replace(",", "");
        if (t.isEmpty() || t.equals("-") || t.equals(".")) return null;
        try { return Double.parseDouble(t); } catch (NumberFormatException e) { return null; }
    }

    static String text(Object v) {
        if (v == null || v == JSONObject.NULL) return "";
        if (v instanceof Double || v instanceof Float) {
            double d = ((Number) v).doubleValue();
            if (d == Math.rint(d) && Math.abs(d) < 1e12) return String.valueOf((long) d);
            return new java.math.BigDecimal(String.valueOf(d)).stripTrailingZeros().toPlainString();
        }
        return String.valueOf(v);
    }

    static String dash(Object v) { String t = text(v); return t.isEmpty() ? "-" : t; }
}
