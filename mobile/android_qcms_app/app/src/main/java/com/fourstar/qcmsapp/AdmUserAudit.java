package com.fourstar.qcmsapp;

import android.text.Editable;
import android.text.TextWatcher;
import android.widget.EditText;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeSet;

/** Users & Access → "Audit & Activity" tab: user activity register and database record-change audit (read only). */
final class AdmUserAudit {
    private AdmUserAudit() { }

    /** Website reads 3000 audit rows; the phone reads the newest 1000 (old / new data of each row is large). */
    static final int AUDIT_LIMIT = 1000;

    static void render(AdmUsersScreen s, LinearLayout body) {
        MainActivity a = s.a;
        Api api = s.api;
        LinearLayout act = AdmUi.section(a, body, "A", "USER ACTIVITY", "Navigation and application actions by user, module, section and record.");
        LinearLayout aud = AdmUi.section(a, body, "B", "RECORD CHANGE AUDIT", "Database-level CREATE / UPDATE / DELETE history with the user and changed fields for tenant records.");
        act.addView(Ui.text(a, "Loading…", 12, Ui.MUTED, false));
        aud.addView(Ui.text(a, "Loading…", 12, Ui.MUTED, false));
        Api.async(() -> AdmDb.select(api, "qcms_user_activity_log", null, "occurred_at.desc", 2000), (rows, err) -> {
            act.removeViewAt(act.getChildCount() - 1);
            if (err != null) { act.addView(AdmUi.note(a, Api.message(err), "red")); return; }
            List<String> headers = AdmUi.listOf("Date / Time", "User", "Role", "Department", "Module", "Section", "Action", "Table", "Record ID");
            List<List<String>> all = new ArrayList<>();
            for (JSONObject r : AdmDb.list(rows)) all.add(AdmUi.listOf(AdmUi.ts(AdmPy.j(r, "occurred_at")), AdmPy.j(r, "user_email_snapshot"), AdmPy.j(r, "role_snapshot"),
                AdmPy.j(r, "department_snapshot"), AdmPy.j(r, "module_key"), AdmPy.j(r, "section_key"), AdmPy.j(r, "action"), AdmPy.j(r, "table_name"), AdmPy.j(r, "row_id")));
            searchable(a, act, "Activity search", "user, module, section, action, record", headers, all, "No user activity is recorded yet.", "QCMS User Activity");
        });
        Api.async(() -> {
            JSONArray audits = new JSONArray(api.get("audit_log?select=changed_at,changed_by,operation,table_name,row_id,old_data,new_data&order=changed_at.desc&limit=" + AUDIT_LIMIT, false).body);
            JSONArray profiles = AdmDb.select(api, "profiles", null, null, 2000);
            return new JSONArray[]{audits, profiles};
        }, (res, err) -> {
            aud.removeViewAt(aud.getChildCount() - 1);
            if (err != null) { aud.addView(AdmUi.note(a, Api.message(err), "red")); return; }
            Map<String, String> emails = new HashMap<>();
            for (JSONObject p : AdmDb.list(res[1])) emails.put(AdmPy.j(p, "id"), AdmPy.j(p, "email"));
            List<String> headers = AdmUi.listOf("Date / Time", "User", "Operation", "Table / Section", "Record ID", "Changed Fields");
            List<List<String>> all = new ArrayList<>();
            for (JSONObject r : AdmDb.list(res[0])) {
                String by = AdmPy.j(r, "changed_by");
                String user = emails.containsKey(by) && !emails.get(by).isEmpty() ? emails.get(by) : (by.isEmpty() ? "SYSTEM" : by);
                all.add(AdmUi.listOf(AdmUi.ts(AdmPy.j(r, "changed_at")), user, AdmPy.j(r, "operation"), AdmPy.j(r, "table_name"), AdmPy.j(r, "row_id"),
                    changedFields(r.opt("old_data"), r.opt("new_data"))));
            }
            aud.addView(Ui.text(a, "Newest " + AUDIT_LIMIT + " record changes (the website PDF covers 3000).", 11, Ui.MUTED, false), Ui.matchWrap(a, 4));
            searchable(a, aud, "Audit search", "table, operation, user, record", headers, all, "No matching record changes are available.", "QCMS Record Change Audit");
        });
    }

    /** _changed_fields: sorted keys whose value changed (updated_at / updated_by ignored), max 12. */
    static String changedFields(Object oldData, Object newData) {
        JSONObject o = oldData instanceof JSONObject ? (JSONObject) oldData : new JSONObject();
        JSONObject n = newData instanceof JSONObject ? (JSONObject) newData : new JSONObject();
        TreeSet<String> keys = new TreeSet<>();
        for (Iterator<String> it = o.keys(); it.hasNext(); ) keys.add(it.next());
        for (Iterator<String> it = n.keys(); it.hasNext(); ) keys.add(it.next());
        List<String> changed = new ArrayList<>();
        for (String k : keys) {
            if (k.equals("updated_at") || k.equals("updated_by")) continue;
            if (!same(o.opt(k), n.opt(k))) changed.add(k);
        }
        String text = String.join(", ", changed.subList(0, Math.min(12, changed.size())));
        return text + (changed.size() > 12 ? " …" : "");
    }

    private static boolean same(Object x, Object y) {
        if (AdmPy.isNull(x) && AdmPy.isNull(y)) return true;
        if (AdmPy.isNull(x) || AdmPy.isNull(y)) return false;
        if (x instanceof Number && y instanceof Number) return ((Number) x).doubleValue() == ((Number) y).doubleValue();
        return AdmPy.dumps(x).equals(AdmPy.dumps(y));
    }

    /** Search box + grid + "Share CSV" (the website offers a PDF download). */
    private static void searchable(MainActivity a, LinearLayout box, String label, String hint, List<String> headers, List<List<String>> all, String emptyText, String subject) {
        box.addView(Ui.label(a, label));
        EditText search = Ui.input(a, hint, false);
        box.addView(search, Ui.matchWrap(a, 0));
        LinearLayout holder = Ui.vbox(a);
        box.addView(holder, Ui.matchWrap(a, 6));
        List<List<String>> shown = new ArrayList<>();
        Runnable draw = () -> {
            holder.removeAllViews();
            String q = AdmUi.text(search).toLowerCase(Locale.ROOT);
            shown.clear();
            for (List<String> r : all) if (q.isEmpty() || String.join(" ", r).toLowerCase(Locale.ROOT).contains(q)) shown.add(r);
            if (shown.isEmpty()) { holder.addView(AdmUi.note(a, emptyText, "teal")); return; }
            holder.addView(new DataGrid(a, subject, headers, new ArrayList<>(shown), 420, null));
        };
        draw.run();
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence c, int st, int n, int af) { }
            @Override public void onTextChanged(CharSequence c, int st, int b, int n) { }
            @Override public void afterTextChanged(Editable e) { draw.run(); }
        });
        AdmUi.outline(a, box, "Share as CSV", v -> {
            if (shown.isEmpty()) { a.toast("Nothing to share."); return; }
            AdmUi.share(a, subject, AdmUi.csv(headers, shown));
        });
    }
}
