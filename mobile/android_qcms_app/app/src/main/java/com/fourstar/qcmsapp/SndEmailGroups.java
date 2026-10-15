package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Email → Email Groups (app_pages/email_center.render_groups): saved distribution lists in qcms_mail_groups.
 * Everyone can use them; the creator or an administrator can edit / delete.
 */
public final class SndEmailGroups extends Screen {
    static final String SETUP_SQL_NOTE = "The Email module's secure tables are not installed yet. Ask the System Administrator to run "
        + "supabase/migrations/20261009100000_qcms_r14_personal_mail.sql in Supabase → SQL Editor.";

    private JSONArray groups;
    private List<JSONObject> employees;
    private Exception loadError;

    public SndEmailGroups(MainActivity a) { super(a); }

    @Override public String title() { return "Email Groups"; }
    @Override public String subtitle() { return "Saved distribution lists"; }
    @Override public int tab() { return Catalog.MORE; }
    @Override public void reload() { groups = null; loadError = null; a.rebuild(); }

    @Override
    public View build() {
        newPage();
        if (loadError != null) { page.addView(error(loadError, this::reload)); return scroll; }
        if (groups == null) {
            page.addView(loading());
            Api.async(() -> {
                JSONArray g;
                try {
                    g = new JSONArray(api.get("qcms_mail_groups?select=*&order=group_name.asc&limit=1000", true).body);
                } catch (Api.ApiException e) {
                    if (e.status == 0) throw e;
                    throw new Api.ApiException(e.status, SETUP_SQL_NOTE);
                }
                return new Object[]{g, SndMail.employees(api)};
            }, (r, err) -> {
                if (err != null) loadError = err;
                else {
                    groups = (JSONArray) r[0];
                    @SuppressWarnings("unchecked") List<JSONObject> e = (List<JSONObject>) r[1];
                    employees = e;
                }
                a.rebuild();
            });
            return scroll;
        }
        offlineNote();
        Button create = Ui.primary(a, "＋ New group");
        create.setOnClickListener(v -> a.push(new Edit(a, this, null, employees)));
        add(create, 2);
        add(Ui.text(a, "Everyone can use the groups in Send Email. Only the creator of a group or an administrator can change it.", 11.5f, Ui.MUTED, false), 6);
        if (groups.length() == 0) add(Ui.empty(a, "No email groups yet."), 8);
        for (int i = 0; i < groups.length(); i++) {
            JSONObject g = groups.optJSONObject(i);
            if (g == null) continue;
            LinearLayout c = Ui.card(a);
            LinearLayout top = Ui.hbox(a);
            top.addView(Ui.text(a, SndData.s(g, "group_name"), 14, Ui.TEXT, true), Ui.weight(1));
            String st = SndData.s(g, "status").isEmpty() ? "ACTIVE" : SndData.s(g, "status");
            top.addView(Ui.chip(a, st, Ui.tone(st)));
            c.addView(top);
            if (!SndData.s(g, "description").isEmpty()) c.addView(Ui.text(a, SndData.s(g, "description"), 12, Ui.MUTED, false));
            int members = SndData.arr(g, "member_employee_ids").length(), extra = SndData.arr(g, "extra_emails").length();
            c.addView(Ui.text(a, members + " employee(s) · " + extra + " other address(es)", 11.5f, Ui.MUTED, false));
            c.setOnClickListener(v -> a.push(new Edit(a, this, g, employees)));
            add(c, 8);
        }
        return scroll;
    }

    /** Create / edit one group. */
    static final class Edit extends Screen {
        private final SndEmailGroups parent;
        private final JSONObject row;
        private final List<JSONObject> employees;
        private final Set<String> members = new LinkedHashSet<>();
        private String name, description, extra, status;
        private EditText nameIn, descIn, extraIn;
        private CheckBox activeBox;
        private boolean saving;

        Edit(MainActivity a, SndEmailGroups parent, JSONObject row, List<JSONObject> employees) {
            super(a);
            this.parent = parent;
            this.row = row;
            this.employees = employees == null ? new ArrayList<>() : employees;
            name = row == null ? "" : SndData.s(row, "group_name");
            description = row == null ? "" : Lookups.j(row, "description");
            status = row == null || SndData.s(row, "status").isEmpty() ? "ACTIVE" : SndData.s(row, "status");
            List<String> mails = new ArrayList<>();
            JSONArray ex = SndData.arr(row, "extra_emails");
            for (int i = 0; i < ex.length(); i++) mails.add(ex.optString(i));
            extra = String.join("\n", mails);
            JSONArray m = SndData.arr(row, "member_employee_ids");
            Set<String> known = new LinkedHashSet<>();
            for (JSONObject e : this.employees) known.add(SndData.s(e, "id"));
            for (int i = 0; i < m.length(); i++) if (known.contains(m.optString(i))) members.add(m.optString(i));
        }

        private boolean canEdit() {
            return row == null || SndData.s(row, "created_by").equals(api.userId) || api.isAdmin();
        }

        @Override public String title() { return row == null ? "New email group" : SndData.s(row, "group_name"); }
        @Override public String subtitle() { return canEdit() ? "Email group" : "Read only · created by another user"; }
        @Override public int tab() { return Catalog.MORE; }

        @Override
        public View build() {
            newPage();
            boolean edit = canEdit();
            LinearLayout c = Ui.card(a);
            c.addView(Ui.text(a, "Group name *", 11.5f, Ui.MUTED, true));
            nameIn = Ui.input(a, "e.g. Quality Team", false);
            nameIn.setText(name);
            nameIn.setEnabled(edit);
            c.addView(nameIn, Ui.matchWrap(a, 4));
            c.addView(Ui.text(a, "Description", 11.5f, Ui.MUTED, true), Ui.matchWrap(a, 10));
            descIn = Ui.input(a, "Description", false);
            descIn.setText(description);
            descIn.setEnabled(edit);
            c.addView(descIn, Ui.matchWrap(a, 4));
            activeBox = SndUi.check(a, "Active (offered in Send Email)", "ACTIVE".equals(status));
            activeBox.setEnabled(edit);
            c.addView(activeBox, Ui.matchWrap(a, 8));
            add(c, 2);

            add(Ui.label(a, "Members (employees) · " + members.size()), 10);
            LinearLayout mc = Ui.card(a);
            if (members.isEmpty()) mc.addView(Ui.text(a, "No employees selected.", 12, Ui.MUTED, false));
            for (String id : members) {
                for (JSONObject e : employees) {
                    if (!id.equals(SndData.s(e, "id"))) continue;
                    String mail = SndMail.employeeEmail(e);
                    mc.addView(Ui.pair(a, SndMail.employeeName(e), (SndData.s(e, "department").isEmpty() ? "-" : SndData.s(e, "department")) + " · " + (mail.isEmpty() ? "no email" : mail)));
                }
            }
            if (edit) {
                Button choose = Ui.outline(a, "Choose employees", Ui.TEAL);
                choose.setOnClickListener(v -> {
                    sync();
                    List<String> ids = new ArrayList<>(), labels = new ArrayList<>();
                    for (JSONObject e : employees) {
                        String mail = SndMail.employeeEmail(e);
                        ids.add(SndData.s(e, "id"));
                        labels.add(SndMail.employeeName(e) + " · " + (SndData.s(e, "department").isEmpty() ? "-" : SndData.s(e, "department")) + " · " + (mail.isEmpty() ? "no email" : mail));
                    }
                    SndUi.multiPick(a, "Group members", ids, labels, members, chosen -> { members.clear(); members.addAll(chosen); a.rebuild(); });
                });
                mc.addView(choose, Ui.matchWrap(a, 8));
            }
            add(mc, 2);

            add(Ui.label(a, "Other email addresses (one per line)"), 10);
            extraIn = SndUi.area(a, "name@company.com", 3);
            extraIn.setText(extra);
            extraIn.setEnabled(edit);
            add(extraIn, 2);

            if (edit) {
                Button save = Ui.primary(a, saving ? "Saving…" : "Save group");
                save.setEnabled(!saving);
                save.setOnClickListener(v -> save());
                add(save, 14);
                if (row != null) {
                    Button del = Ui.outline(a, "Delete this group", Ui.ORANGE);
                    del.setOnClickListener(v -> a.confirm("Delete " + SndData.s(row, "group_name") + "?", "The group is removed for everyone.", "Delete", this::delete));
                    add(del, 10);
                }
            } else {
                TextView t = Ui.text(a, "Only the creator of this group or an administrator can change it.", 12, Ui.MUTED, false);
                add(t, 12);
            }
            return scroll;
        }

        private void sync() {
            if (nameIn != null) name = SndUi.text(nameIn);
            if (descIn != null) description = SndUi.text(descIn);
            if (extraIn != null) extra = SndUi.text(extraIn);
            if (activeBox != null) status = activeBox.isChecked() ? "ACTIVE" : "INACTIVE";
        }

        private void save() {
            sync();
            if (name.trim().isEmpty()) { a.toast("Enter a group name."); return; }
            List<String> emails = new ArrayList<>(), bad = new ArrayList<>();
            for (String line : extra.split("\\r?\\n")) {
                for (String piece : line.replace(";", ",").split(",")) {
                    if (piece.trim().isEmpty()) continue;
                    if (!SndMail.valid(piece).isEmpty()) emails.add(piece.trim()); else bad.add(piece.trim());
                }
            }
            if (!bad.isEmpty()) { a.toast("Invalid email address(es): " + String.join(", ", bad)); return; }
            saving = true;
            a.rebuild();
            Api.async(() -> {
                JSONObject p = new JSONObject();
                p.put("group_name", name.trim());
                p.put("description", description.trim().isEmpty() ? JSONObject.NULL : description.trim());
                p.put("member_employee_ids", SndMail.toArray(new ArrayList<>(members)));
                p.put("extra_emails", SndMail.toArray(emails));
                p.put("status", status);
                p.put("updated_at", OffsetDateTime.now(ZoneOffset.UTC).toString());
                return row == null ? api.insert("qcms_mail_groups", p) : api.update("qcms_mail_groups", SndData.s(row, "id"), p);
            }, (saved, err) -> {
                saving = false;
                if (err != null) {
                    String m = Api.message(err);
                    a.toast(m.toLowerCase(Locale.ROOT).contains("duplicate") ? "Duplicate group name — choose another name." : m);
                    a.rebuild();
                    return;
                }
                a.toast("Email group saved with " + (members.size() + emails.size()) + " recipient(s).");
                if (parent != null) parent.groups = null;
                a.back();
            });
        }

        private void delete() {
            Api.async(() -> { api.delete("qcms_mail_groups", SndData.s(row, "id")); return true; }, (ok, err) -> {
                if (err != null) { a.toast(Api.message(err)); return; }
                a.toast("Email group deleted.");
                if (parent != null) parent.groups = null;
                a.back();
            });
        }
    }
}
