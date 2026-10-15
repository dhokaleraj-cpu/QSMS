package com.fourstar.qcmsapp;

import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.List;

/**
 * Phone version of the website's permission data editors (user_access.py): one card per module or section
 * with the Override switch and the permission ticks. Rows keep their state while the grid is filtered.
 */
final class AdmGrid {
    private AdmGrid() { }

    /** One editor row (Override + rights). */
    static final class Row {
        final String module, section, label, source;
        final JSONObject configured;
        boolean override;
        final boolean[] values;

        Row(String module, String section, String label, String source, JSONObject configured, boolean override, boolean[] values) {
            this.module = module; this.section = section; this.label = label; this.source = source;
            this.configured = configured; this.override = override; this.values = values;
        }
    }

    /** Module rows: View, Entry/Create, Edit, Validate/Review, Approve, Delete/Archive. */
    static final String[] MODULE_COLS = {"View", "Entry/Create", "Edit", "Validate/Review", "Approve", "Delete/Archive"};
    static final String[] MODULE_KEYS = {"can_view", "can_create", "can_edit", "can_validate", "can_approve", "can_archive"};
    /** Section rows: View, Create, Edit. */
    static final String[] SECTION_COLS = {"View", "Create", "Edit"};
    static final String[] SECTION_KEYS = {"can_view", "can_create", "can_edit"};

    /** Cards for the rows (only rows accepted by the filter). Ticking a right switches Override on. */
    static void render(MainActivity a, LinearLayout box, List<Row> rows, String[] cols, String moduleFilter, boolean editable) {
        box.removeAllViews();
        int shown = 0;
        for (Row r : rows) {
            if (moduleFilter != null && !moduleFilter.isEmpty() && !moduleFilter.equals(r.module)) continue;
            shown++;
            LinearLayout card = Ui.vbox(a);
            card.setBackground(Ui.round(r.override ? Ui.TEAL_SOFT : android.graphics.Color.WHITE, Ui.LINE, 1, 10, a));
            card.setPadding(Ui.dp(a, 10), Ui.dp(a, 8), Ui.dp(a, 10), Ui.dp(a, 6));
            LinearLayout head = Ui.hbox(a);
            head.addView(Ui.text(a, r.label, 13, Ui.TEXT, true), Ui.weight(1));
            card.addView(head);
            String detail = r.section.isEmpty() ? r.module : r.module + " · " + r.section;
            TextView sub = Ui.text(a, detail + (r.source.isEmpty() ? "" : "  ·  Source: " + r.source), 10.5f, Ui.MUTED, false);
            card.addView(sub);
            Switch ov = new Switch(a);
            ov.setText("Override");
            ov.setTextColor(Ui.TEXT);
            ov.setChecked(r.override);
            ov.setEnabled(editable);
            card.addView(ov, Ui.matchWrap(a, 2));
            CheckBox[] boxes = new CheckBox[cols.length];
            LinearLayout line = null;
            for (int i = 0; i < cols.length; i++) {
                if (i % 3 == 0) { line = Ui.hbox(a); card.addView(line); }
                CheckBox c = AdmUi.check(a, cols[i], r.values[i]);
                c.setTextSize(12);
                c.setEnabled(editable);
                final int index = i;
                c.setOnCheckedChangeListener((b, on) -> {
                    r.values[index] = on;
                    if (!r.override) { r.override = true; ov.setChecked(true); }
                });
                boxes[i] = c;
                line.addView(c, Ui.weight(1));
            }
            ov.setOnCheckedChangeListener((b, on) -> {
                r.override = on;
                card.setBackground(Ui.round(on ? Ui.TEAL_SOFT : android.graphics.Color.WHITE, Ui.LINE, 1, 10, a));
            });
            box.addView(card, Ui.matchWrap(a, 6));
        }
        if (shown == 0) box.addView(Ui.empty(a, "No rows."));
    }

    static int overrides(List<Row> rows) {
        int n = 0;
        for (Row r : rows) if (r.override) n++;
        return n;
    }
}
