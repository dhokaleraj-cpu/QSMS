package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

/**
 * A form made of several titled FormView sections (like the website's stage sections A, B, C …).
 * Every call is routed to the FormView that owns the field key.
 */
final class CalSections extends LinearLayout {
    private final MainActivity a;
    private final List<FormView> forms = new ArrayList<>();
    private final Map<String, FormView> owner = new HashMap<>();
    private FormView.Change change;

    CalSections(MainActivity a) {
        super(a);
        this.a = a;
        setOrientation(VERTICAL);
    }

    /** Adds a titled section with its fields (title may be null). */
    FormView section(String title, Field... fields) {
        if (title != null && !title.isEmpty()) {
            TextView t = Ui.text(a, title, 13.5f, Ui.TEAL_DARK, true);
            t.setPadding(0, Ui.dp(a, forms.isEmpty() ? 2 : 18), 0, Ui.dp(a, 2));
            addView(t);
        }
        FormView f = new FormView(a, Arrays.asList(fields));
        f.onChange((k, v) -> { if (change != null) change.changed(k, v); });
        for (Field x : fields) owner.put(x.key, f);
        forms.add(f);
        addView(f, Ui.matchWrap(a, 0));
        return f;
    }

    /** Extra view (note, hint card) placed after the current sections. */
    void note(View v) { addView(v, Ui.matchWrap(a, 8)); }

    void onChange(FormView.Change c) { change = c; }

    boolean has(String key) { return owner.containsKey(key); }
    Field field(String key) { FormView f = owner.get(key); return f == null ? null : f.field(key); }
    void set(String key, Object v) { FormView f = owner.get(key); if (f != null) f.set(key, v); }
    String str(String key) { FormView f = owner.get(key); return f == null ? "" : f.str(key); }
    Double num(String key) { FormView f = owner.get(key); return f == null ? null : f.num(key); }
    boolean bool(String key) { FormView f = owner.get(key); return f != null && f.bool(key); }
    void setVisible(String key, boolean on) { FormView f = owner.get(key); if (f != null) f.setVisible(key, on); }

    void setAll(JSONObject row) { if (row != null) for (FormView f : forms) f.setAll(row); }

    String validate() {
        for (FormView f : forms) { String p = f.validate(); if (p != null) return p; }
        return null;
    }

    JSONObject json() throws Exception {
        JSONObject out = new JSONObject();
        for (FormView f : forms) {
            JSONObject o = f.json();
            Iterator<String> it = o.keys();
            while (it.hasNext()) { String k = it.next(); out.put(k, o.opt(k)); }
        }
        return out;
    }
}
