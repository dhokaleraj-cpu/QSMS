package com.fourstar.qcmsapp;

import android.graphics.Color;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Collections;
import java.util.Locale;

/**
 * R35 notification inbox (website page "notifications"): Unread / All, category icons, tap = mark read
 * and open the matching record / module (or the website page), Mark all read, WhatsApp alerts opt-in.
 */
final class NotifScreen extends Screen {
    private static boolean unreadOnly = true;
    private LinearLayout listBox;
    private TextView countView;

    NotifScreen(MainActivity a) { super(a); }

    @Override public String title() { return "Notifications"; }
    @Override public String subtitle() { return "Approvals, tasks and updates for you"; }
    @Override public int tab() { return Catalog.HOME; }

    @Override
    public View build() {
        newPage();
        add(GenUtil.chips(a, GenUtil.listOf("Unread", "All"), unreadOnly ? 0 : 1, i -> { unreadOnly = i == 0; a.rebuild(); }), 0);

        LinearLayout actions = Ui.hbox(a);
        actions.setGravity(Gravity.CENTER_VERTICAL);
        countView = Ui.text(a, "", 12, Ui.MUTED, false);
        actions.addView(countView, Ui.weight(1));
        Button all = Ui.outline(a, "✓ Mark all read", Ui.TEAL);
        all.setOnClickListener(v -> Api.async(() -> Notif.markRead(api, null), (n, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            a.toast("All notifications marked as read.");
            a.refreshBell();
            a.rebuild();
        }));
        actions.addView(all);
        add(actions, 8);

        listBox = Ui.vbox(a);
        listBox.addView(loading());
        add(listBox, 4);
        addWhatsapp();
        load();
        return scroll;
    }

    private void load() {
        final boolean only = unreadOnly;
        Api.async(() -> Notif.list(api, only, 100), (rows, err) -> {
            listBox.removeAllViews();
            if (err != null) { listBox.addView(error(err, a::rebuild)); return; }
            render(rows);
        });
    }

    private void render(JSONArray rows) {
        int unread = 0;
        for (int i = 0; i < rows.length(); i++) { JSONObject r = rows.optJSONObject(i); if (r != null && !r.optBoolean("is_read", false)) unread++; }
        countView.setText(rows.length() + (unreadOnly ? " unread" : " notification(s) · " + unread + " unread"));
        if (rows.length() == 0) {
            listBox.addView(Ui.empty(a, unreadOnly ? "No unread notifications. ✓" : "No notifications yet."));
            return;
        }
        for (int i = 0; i < rows.length(); i++) {
            JSONObject r = rows.optJSONObject(i);
            if (r != null) listBox.addView(row(r), Ui.matchWrap(a, i == 0 ? 0 : 8));
        }
    }

    private View row(JSONObject r) {
        boolean read = r.optBoolean("is_read", false);
        String category = r.optString("category", "INFO").toUpperCase(Locale.ROOT);
        LinearLayout card = Ui.hbox(a);
        card.setGravity(Gravity.TOP);
        card.setPadding(dp(12), dp(12), dp(12), dp(12));
        Ui.clickable(card, read ? Color.WHITE : Ui.TEAL_SOFT, Ui.LINE, 14);

        TextView icon = Ui.text(a, Notif.icon(category), 18, Color.WHITE, true);
        icon.setGravity(Gravity.CENTER);
        int fill = "APPROVAL".equals(category) ? Ui.ORANGE : "ALERT".equals(category) ? Ui.RED_FG : "TASK".equals(category) ? Ui.TEAL : "UPDATE".equals(category) ? Ui.GREEN_FG : Ui.GREY_FG;
        icon.setBackground(Ui.round(fill, 0, 0, 18, a));
        LinearLayout.LayoutParams ilp = new LinearLayout.LayoutParams(dp(36), dp(36));
        ilp.rightMargin = dp(10);
        card.addView(icon, ilp);

        LinearLayout text = Ui.vbox(a);
        LinearLayout head = Ui.hbox(a);
        TextView title = Ui.text(a, r.optString("title", "Notification"), 14, Ui.TEXT, !read);
        head.addView(title, Ui.weight(1));
        head.addView(Ui.chip(a, GenUtil.title(category.toLowerCase(Locale.ROOT)), Notif.tone(category)));
        text.addView(head);
        String body = r.isNull("body") ? "" : r.optString("body", "");
        if (!body.isEmpty()) {
            TextView b = Ui.text(a, body, 12.5f, Ui.TEXT, false);
            b.setMaxLines(4);
            text.addView(b, Ui.matchWrap(a, 3));
        }
        String when = when(r.optString("created_at", ""));
        String route = r.isNull("web_route") ? "" : r.optString("web_route", "");
        TextView meta = Ui.text(a, when + (read ? "" : " · unread") + (route.isEmpty() ? "" : " · tap to open"), 11, Ui.MUTED, false);
        text.addView(meta, Ui.matchWrap(a, 4));
        card.addView(text, Ui.weight(1));

        card.setOnClickListener(v -> openItem(r));
        return card;
    }

    private void openItem(JSONObject r) {
        String id = r.optString("id", "");
        String table = r.isNull("related_table") ? "" : r.optString("related_table", "");
        String related = r.isNull("related_id") ? "" : r.optString("related_id", "");
        String route = r.isNull("web_route") ? "" : r.optString("web_route", "");
        String title = r.optString("title", "QCMS");
        if (!r.optBoolean("is_read", false) && !id.isEmpty()) {
            Api.async(() -> Notif.markRead(api, Collections.singletonList(id)), (n, err) -> a.refreshBell());
            try { r.put("is_read", true); } catch (Exception ignored) { }
        }
        if (route.isEmpty() && table.isEmpty()) {
            a.toast(title);
            a.rebuild();
            return;
        }
        Notif.open(a, table, related, route, title);
    }

    static String when(String iso) {
        if (iso == null || iso.isEmpty()) return "";
        try {
            OffsetDateTime t = OffsetDateTime.parse(iso.replace(' ', 'T'));
            return t.atZoneSameInstant(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("dd MMM yyyy, HH:mm", Locale.ENGLISH));
        } catch (Exception e) {
            return Ui.date(iso);
        }
    }

    // ------------------------------------------------------------------ WhatsApp alerts (qcms_set_my_whatsapp)
    private void addWhatsapp() {
        add(Ui.label(a, "WhatsApp alerts"), 18);
        LinearLayout card = Ui.card(a);
        Switch on = new Switch(a);
        on.setText("Send my QCMS alerts on WhatsApp too");
        on.setTextColor(Ui.TEXT);
        on.setChecked(api.prefs().getBoolean("whatsapp_opt_in", false));
        card.addView(on);
        EditText number = Ui.input(a, "WhatsApp number with country code, e.g. +91 98xxxxxxxx", false);
        number.setInputType(InputType.TYPE_CLASS_PHONE);
        number.setText(api.prefs().getString("whatsapp_number", ""));
        card.addView(number, Ui.matchWrap(a, 8));
        TextView note = Ui.text(a, "Messages are sent by STAWN QCMS once WhatsApp sending is set up for your company. You can switch this off at any time.", 11.5f, Ui.MUTED, false);
        card.addView(note, Ui.matchWrap(a, 6));
        Button save = Ui.primary(a, "Save WhatsApp setting");
        card.addView(save, Ui.matchWrap(a, 10));
        save.setOnClickListener(v -> {
            boolean opt = on.isChecked();
            String mobile = number.getText().toString().trim();
            if (opt && mobile.replaceAll("[^0-9]", "").length() < 8) { number.setError("Enter the WhatsApp number"); return; }
            save.setEnabled(false);
            Api.async(() -> Notif.setWhatsapp(api, opt, mobile), (res, err) -> {
                save.setEnabled(true);
                if (err != null) { a.toast(Api.message(err)); return; }
                api.prefs().edit().putBoolean("whatsapp_opt_in", opt).putString("whatsapp_number", mobile).apply();
                String msg = res == null ? "" : res.optString("message", "");
                a.toast(msg.isEmpty() ? (opt ? "WhatsApp alerts switched on." : "WhatsApp alerts switched off.") : msg);
            });
        });
        add(card, 4);
    }

    @Override public void reload() { a.refreshBell(); a.rebuild(); }
}
