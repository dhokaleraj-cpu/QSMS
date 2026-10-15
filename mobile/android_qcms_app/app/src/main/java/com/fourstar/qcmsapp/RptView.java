package com.fourstar.qcmsapp;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * R33 · Shows an RptDoc on the phone: every section, result table, conclusion and photograph of the report,
 * in the same order as the printed PDF. Result tables are spreadsheet grids (slide in every direction).
 */
final class RptView {
    private RptView() { }

    static View build(MainActivity a, RptDoc d) {
        LinearLayout box = Ui.vbox(a);
        String heading = d.title;
        if (!d.heatNumber.isEmpty()) heading = "HEAT NUMBER: " + d.heatNumber + (d.recordNumber.isEmpty() ? "" : " · " + d.recordNumber);
        TextView t = Ui.text(a, heading, 15, Ui.TEXT, true);
        box.addView(t);
        String lastBar = d.title;
        LinearLayout card = null;
        for (RptDoc.Block b : d.blocks) {
            if (b instanceof RptDoc.Bar) {
                RptDoc.Bar bar = (RptDoc.Bar) b;
                String text = bar.fixedFill ? bar.text : d.relabel(bar.text);
                lastBar = text;
                TextView v = Ui.text(a, bar.light ? text : text.toUpperCase(java.util.Locale.ROOT), bar.light ? 13 : 13.5f, bar.light ? d.accent : Color.WHITE, true);
                int p = Ui.dp(a, 8);
                v.setPadding(bar.light ? 2 : p, p / 2 + 2, p, p / 2 + 2);
                if (!bar.light) v.setBackgroundColor(d.accent);
                box.addView(v, Ui.matchWrap(a, bar.light ? 10 : 14));
                card = null;
            } else if (b instanceof RptDoc.Labeled) {
                RptDoc.Labeled g = (RptDoc.Labeled) b;
                LinearLayout c = Ui.card(a);
                for (String[] row : g.rows) {
                    for (int i = 0; i < row.length; i++) {
                        if (!g.labelCols.contains(i)) continue;
                        String label = row[i] == null ? "" : row[i];
                        String value = i + 1 < row.length && row[i + 1] != null ? row[i + 1] : "";
                        if (label.isEmpty() && value.isEmpty()) continue;
                        LinearLayout pair = Ui.pair(a, label, value.isEmpty() ? "-" : value);
                        colour(pair, label, value, d, g.valueColor);
                        c.addView(pair);
                    }
                }
                box.addView(c, Ui.matchWrap(a, 4));
            } else if (b instanceof RptDoc.Grid) {
                RptDoc.Grid g = (RptDoc.Grid) b;
                if (g.rows.length == 0) continue;
                List<String> cols = new ArrayList<>(Arrays.asList(g.rows[Math.max(0, g.headerRows - 1)]));
                for (int i = 0; i < cols.size(); i++) if (cols.get(i) == null || cols.get(i).isEmpty()) cols.set(i, " ");
                List<List<String>> rows = new ArrayList<>();
                for (int r = g.headerRows; r < g.rows.length; r++) {
                    List<String> line = new ArrayList<>();
                    for (int i = 0; i < cols.size(); i++) line.add(i < g.rows[r].length && g.rows[r][i] != null ? g.rows[r][i] : "");
                    rows.add(line);
                }
                box.addView(new DataGrid(a, lastBar, cols, rows, 360, null), Ui.matchWrap(a, 4));
            } else if (b instanceof RptDoc.Conclusion) {
                RptDoc.Conclusion k = (RptDoc.Conclusion) b;
                LinearLayout c = Ui.card(a);
                c.addView(line(a, "Conclusion", RptDoc.v(k.conclusion), d.conclusionColor, true));
                if (k.remark != null && !k.remark.trim().isEmpty()) c.addView(line(a, "Conclusion Remark", k.remark, d.remarkColor, false));
                c.addView(line(a, "Final Decision", RptDoc.v(k.decision), RptDoc.statusColor(k.decision), true));
                c.addView(line(a, "Decision Reason", RptDoc.v(k.reason), d.remarkColor, false));
                box.addView(c, Ui.matchWrap(a, 8));
            } else if (b instanceof RptDoc.Photos) {
                RptDoc.Photos p = (RptDoc.Photos) b;
                for (RptDoc.Photo ph : p.items) box.addView(photo(a, ph), Ui.matchWrap(a, 6));
            } else if (b instanceof RptDoc.BendPanel) {
                RptDoc.BendPanel p = (RptDoc.BendPanel) b;
                TextView angle = Ui.text(a, "Bend angle " + p.angle, 22, Ui.TEXT, false);
                angle.setGravity(Gravity.CENTER);
                box.addView(angle, Ui.matchWrap(a, 8));
                for (RptDoc.Photo ph : new RptDoc.Photo[]{p.left, p.r1, p.r2, p.r3}) if (ph != null && ph.has()) box.addView(photo(a, ph), Ui.matchWrap(a, 6));
                if (p.surface != null && !p.surface.isEmpty()) box.addView(Ui.text(a, p.surface, 13, d.remarkColor, true), Ui.matchWrap(a, 6));
            } else if (b instanceof RptDoc.Chart) {
                RptDoc.Chart k = (RptDoc.Chart) b;
                int w = 1100, h = 520;
                try {
                    Bitmap bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
                    Canvas cv = new Canvas(bmp);
                    cv.drawColor(Color.WHITE);
                    cv.scale(w / 560f, h / 165f);
                    RptPdf.drawChart(cv, k, 0, 0, 560, 165);
                    ImageView iv = new ImageView(a);
                    iv.setAdjustViewBounds(true);
                    iv.setImageBitmap(bmp);
                    box.addView(iv, Ui.matchWrap(a, 6));
                } catch (Throwable ignored) { }
            } else if (b instanceof RptDoc.Text) {
                RptDoc.Text tx = (RptDoc.Text) b;
                int color = tx.style == RptDoc.CONCL ? d.conclusionColor : tx.style == RptDoc.REMARK ? d.remarkColor : tx.style == RptDoc.SUBTITLE ? Ui.MUTED : Ui.TEXT;
                box.addView(Ui.text(a, tx.text, tx.style == RptDoc.SMALL || tx.style == RptDoc.SUBTITLE ? 12 : 13, color, tx.style == RptDoc.HEADING || tx.style == RptDoc.CONCL), Ui.matchWrap(a, 4));
            } else if (b instanceof RptDoc.Signatures) {
                RptDoc.Signatures s = (RptDoc.Signatures) b;
                LinearLayout c = Ui.card(a);
                for (int i = 0; i < s.labels.length; i++) c.addView(Ui.pair(a, s.labels[i], i < s.values.length ? s.values[i] : ""));
                box.addView(c, Ui.matchWrap(a, 6));
            }
        }
        return box;
    }

    private static void colour(LinearLayout pair, String label, String value, RptDoc d, int fixed) {
        if (pair.getChildCount() < 2 || !(pair.getChildAt(1) instanceof TextView)) return;
        TextView v = (TextView) pair.getChildAt(1);
        String lu = label.toUpperCase(java.util.Locale.ROOT);
        if (fixed != 0) v.setTextColor(fixed);
        else if (RptDoc.isRemark(label)) v.setTextColor(d.remarkColor);
        else if (RptDoc.isConclusion(label)) v.setTextColor(d.conclusionColor);
        else if ((lu.contains("DISPOSITION") || lu.contains("DECISION") || lu.contains("RESULT") || lu.contains("STATUS")) && !lu.contains("REASON")) {
            int c = RptDoc.statusColor(value.replace(" ", "_"));
            if (c != RptDoc.INK) v.setTextColor(c);
        }
    }

    private static View line(MainActivity a, String label, String value, int color, boolean bold) {
        LinearLayout l = Ui.vbox(a);
        l.addView(Ui.text(a, label, 12, Ui.MUTED, true));
        l.addView(Ui.text(a, value == null || value.isEmpty() ? "-" : value, bold ? 15 : 13.5f, color, bold));
        l.setPadding(0, Ui.dp(a, 4), 0, Ui.dp(a, 4));
        return l;
    }

    private static View photo(MainActivity a, RptDoc.Photo ph) {
        LinearLayout l = Ui.vbox(a);
        if (ph.has()) {
            Bitmap bmp = RptPdf.decode(ph.bytes);
            if (bmp != null) {
                ImageView iv = new ImageView(a);
                iv.setAdjustViewBounds(true);
                iv.setImageBitmap(bmp);
                l.addView(iv, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
            }
        } else {
            TextView none = Ui.text(a, "No photograph uploaded", 12, Ui.MUTED, false);
            none.setGravity(Gravity.CENTER);
            none.setPadding(0, Ui.dp(a, 18), 0, Ui.dp(a, 18));
            none.setBackground(Ui.round(Color.WHITE, Ui.LINE_STRONG, 1, 8, a));
            l.addView(none, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        }
        TextView cap = Ui.text(a, ph.caption, 12, Ui.MUTED, false);
        cap.setGravity(Gravity.CENTER);
        l.addView(cap);
        return l;
    }
}
