package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.ViewGroup;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/** Small view helpers for the Snd (PO send / Email) screens. */
final class SndUi {
    private SndUi() { }

    static EditText area(MainActivity a, String hint, int minLines) {
        EditText e = Ui.input(a, hint, false);
        e.setSingleLine(false);
        e.setMinLines(minLines);
        e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        return e;
    }

    static EditText emails(MainActivity a, String hint) {
        EditText e = Ui.input(a, hint, false);
        e.setSingleLine(false);
        e.setMinLines(1);
        e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        return e;
    }

    static CheckBox check(MainActivity a, String text, boolean checked) {
        CheckBox cb = new CheckBox(a);
        cb.setText(text);
        cb.setTextSize(12.5f);
        cb.setTextColor(Ui.TEXT);
        cb.setChecked(checked);
        return cb;
    }

    static String text(EditText e) {
        CharSequence t = e == null ? null : e.getText();
        return t == null ? "" : t.toString();
    }

    interface Multi { void picked(Set<String> ids); }

    /** Searchable multi-select dialog (ids / labels), returns the ticked ids. */
    static void multiPick(MainActivity a, String title, List<String> ids, List<String> labels, Set<String> selected, Multi done) {
        LinearLayout box = Ui.vbox(a);
        int p = Ui.dp(a, 16);
        box.setPadding(p, Ui.dp(a, 8), p, 0);
        EditText search = Ui.input(a, "Search…", false);
        box.addView(search, Ui.matchWrap(a, 0));
        ScrollView sv = new ScrollView(a);
        LinearLayout list = Ui.vbox(a);
        sv.addView(list);
        box.addView(sv, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(a, 360)));
        Set<String> chosen = new LinkedHashSet<>(selected);
        List<CheckBox> boxes = new ArrayList<>();
        for (int i = 0; i < ids.size(); i++) {
            String id = ids.get(i);
            CheckBox cb = check(a, labels.get(i), chosen.contains(id));
            cb.setTag(labels.get(i).toLowerCase(Locale.ROOT));
            cb.setOnCheckedChangeListener((b, on) -> { if (on) chosen.add(id); else chosen.remove(id); });
            boxes.add(cb);
            list.addView(cb, Ui.matchWrap(a, 0));
        }
        if (ids.isEmpty()) list.addView(Ui.empty(a, "Nothing to choose."));
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int x, int y, int z) { }
            @Override public void onTextChanged(CharSequence s, int x, int y, int z) { }
            @Override public void afterTextChanged(Editable e) {
                String q = e == null ? "" : e.toString().trim().toLowerCase(Locale.ROOT);
                for (CheckBox cb : boxes) {
                    Object tag = cb.getTag();
                    cb.setVisibility(q.isEmpty() || (tag != null && tag.toString().contains(q)) ? android.view.View.VISIBLE : android.view.View.GONE);
                }
            }
        });
        new AlertDialog.Builder(a).setTitle(title).setView(box)
            .setPositiveButton("Done", (d, w) -> done.picked(chosen))
            .setNegativeButton("Back", null)
            .show();
    }

    /** Status card after a send: SENT (green) / QUEUED (amber) / FAILED (red) with the server message. */
    static LinearLayout resultCard(MainActivity a, String status, String message) {
        LinearLayout card = Ui.card(a);
        String tone = "SENT".equals(status) ? "green" : "QUEUED".equals(status) ? "amber" : "red";
        String head = "SENT".equals(status) ? "Email sent" : "QUEUED".equals(status) ? "Email queued" : "PARTIAL".equals(status) ? "Email partly sent" : "Email not sent";
        LinearLayout row = Ui.hbox(a);
        row.addView(Ui.text(a, head, 15, Ui.TEXT, true), Ui.weight(1));
        row.addView(Ui.chip(a, status, tone));
        card.addView(row);
        if (message != null && !message.isEmpty()) {
            TextView m = Ui.text(a, message, 12.5f, "red".equals(tone) ? Ui.RED_FG : Ui.TEXT, false);
            m.setPadding(0, Ui.dp(a, 6), 0, 0);
            m.setTextIsSelectable(true);
            card.addView(m);
        }
        return card;
    }
}
