package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Email → My Sent Emails: the qcms_notification_outbox rows created by the signed-in user (Email module and
 * workflow emails such as "PO to supplier") with delivery status / server error, detail and Retry for
 * FAILED / PENDING rows through the qcms-send-email function. The website's send log (qcms_mail_sent_log)
 * is shown on the second tab.
 */
public final class SndEmailSent extends Screen {
    private static final String[] FILTERS = {"ALL", "SENT", "FAILED", "PENDING"};
    private String filter = "ALL";
    private boolean showLog = false;
    private JSONArray rows, log;
    private Exception loadError;

    public SndEmailSent(MainActivity a) { super(a); }

    @Override public String title() { return "My Sent Emails"; }
    @Override public String subtitle() { return "Visible only to you · status from the email server"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override public void reload() { rows = null; log = null; loadError = null; a.rebuild(); }

    @Override
    public View build() {
        newPage();
        LinearLayout seg = Ui.hbox(a);
        seg.addView(segment("Emails (outbox)", !showLog, () -> { showLog = false; a.rebuild(); }), lp(true));
        seg.addView(segment("Send log", showLog, () -> { showLog = true; a.rebuild(); }), lp(false));
        add(seg, 2);
        if (loadError != null) { add(error(loadError, this::reload), 8); return scroll; }
        if (rows == null || log == null) {
            add(loading(), 8);
            Api.async(() -> {
                String uid = api.userId == null ? "" : api.userId;
                JSONArray r = api.rows("qcms_notification_outbox?select=id,created_at,event_key,recipient_email,recipient_name,cc_emails,bcc_emails,subject,body_text,status,attempts,last_error,sent_at,related_table,attachment_manifest,context"
                    + (uid.isEmpty() ? "" : "&created_by=eq." + Api.enc(uid)) + "&order=created_at.desc&limit=300");
                JSONArray l;
                try { l = api.rows("qcms_mail_sent_log?select=*&order=sent_at.desc&limit=500"); } catch (Exception e) { l = new JSONArray(); }
                return new JSONArray[]{r, l};
            }, (res, err) -> {
                if (err != null) loadError = err;
                else { rows = res[0]; log = res[1]; }
                a.rebuild();
            });
            return scroll;
        }
        offlineNote();
        if (showLog) renderLog(); else renderOutbox();
        return scroll;
    }

    private LinearLayout.LayoutParams lp(boolean first) {
        LinearLayout.LayoutParams l = Ui.weight(1);
        if (first) l.rightMargin = dp(6);
        return l;
    }

    private TextView segment(String text, boolean on, Runnable click) {
        TextView t = Ui.text(a, text, 12.5f, on ? android.graphics.Color.WHITE : Ui.TEXT, true);
        t.setGravity(Gravity.CENTER);
        t.setPadding(dp(6), dp(10), dp(6), dp(10));
        t.setBackground(on ? Ui.round(Ui.TEAL, 0, 0, 10, a) : Ui.round(android.graphics.Color.WHITE, Ui.LINE_STRONG, 1, 10, a));
        t.setOnClickListener(v -> click.run());
        return t;
    }

    private void renderOutbox() {
        LinearLayout chips = Ui.hbox(a);
        for (String f : FILTERS) {
            int n = 0;
            for (int i = 0; i < rows.length(); i++) if (f.equals("ALL") || f.equals(status(rows.optJSONObject(i)))) n++;
            TextView c = Ui.chip(a, Ui.pretty(f) + " " + n, f.equals(filter) ? "teal" : "grey");
            c.setPadding(dp(10), dp(6), dp(10), dp(6));
            c.setOnClickListener(v -> { filter = f; a.rebuild(); });
            LinearLayout.LayoutParams l = new LinearLayout.LayoutParams(-2, -2);
            l.rightMargin = dp(6);
            chips.addView(c, l);
        }
        add(chips, 10);
        int shown = 0;
        for (int i = 0; i < rows.length(); i++) {
            JSONObject r = rows.optJSONObject(i);
            if (r == null || !(filter.equals("ALL") || filter.equals(status(r)))) continue;
            add(card(r), 8);
            shown++;
        }
        if (shown == 0) add(Ui.empty(a, rows.length() == 0 ? "No emails sent from QCMS yet." : "No emails with this status."), 8);
    }

    private static String status(JSONObject r) {
        String s = SndData.s(r, "status").toUpperCase(Locale.ROOT);
        return s.equals("SENDING") ? "PENDING" : s.isEmpty() ? "PENDING" : s;
    }

    private LinearLayout card(JSONObject r) {
        LinearLayout c = Ui.card(a);
        LinearLayout top = Ui.hbox(a);
        String subj = SndData.s(r, "subject");
        top.addView(Ui.text(a, subj.isEmpty() ? "(no subject)" : subj, 13.5f, Ui.TEXT, true), Ui.weight(1));
        String st = SndData.s(r, "status");
        top.addView(Ui.chip(a, st.isEmpty() ? "PENDING" : st, Ui.tone(st.equals("SENT") ? "COMPLETE" : st.equals("FAILED") ? "FAILED" : "PENDING")));
        c.addView(top);
        c.addView(Ui.text(a, "To " + toText(r), 12, Ui.MUTED, false));
        c.addView(Ui.text(a, when(r) + " · " + Ui.pretty(SndData.s(r, "event_key")) + attachText(r), 11.5f, Ui.MUTED, false));
        if (st.equals("FAILED") && !SndData.s(r, "last_error").isEmpty()) {
            TextView e = Ui.text(a, Lookups.j(r, "last_error"), 11.5f, Ui.RED_FG, false);
            e.setMaxLines(3);
            c.addView(e);
        }
        c.setOnClickListener(v -> detail(r));
        return c;
    }

    private static String toText(JSONObject r) {
        JSONObject ctx = SndData.obj(r, "context");
        JSONArray to = ctx == null ? null : ctx.optJSONArray("to_emails");
        List<String> list = new ArrayList<>();
        if (to != null) for (int i = 0; i < to.length(); i++) list.add(to.optString(i));
        if (list.isEmpty()) list.add(SndData.s(r, "recipient_email"));
        int cc = SndData.arr(r, "cc_emails").length(), bcc = SndData.arr(r, "bcc_emails").length();
        return String.join(", ", list) + (cc > 0 ? " · CC " + cc : "") + (bcc > 0 ? " · BCC " + bcc : "");
    }

    private static String attachText(JSONObject r) {
        int n = SndData.arr(r, "attachment_manifest").length();
        return n > 0 ? " · " + n + " attachment(s)" : "";
    }

    private static String when(JSONObject r) {
        String t = SndData.s(r, "sent_at").isEmpty() ? SndData.s(r, "created_at") : SndData.s(r, "sent_at");
        if (t.length() >= 16) return Ui.date(t) + " " + t.substring(11, 16) + " UTC";
        return Ui.date(t);
    }

    private void detail(JSONObject r) {
        LinearLayout box = Ui.vbox(a);
        int p = dp(18);
        box.setPadding(p, dp(8), p, dp(8));
        box.addView(Ui.pair(a, "Status", SndData.s(r, "status")));
        box.addView(Ui.pair(a, "To", toText(r)));
        JSONArray cc = SndData.arr(r, "cc_emails"), bcc = SndData.arr(r, "bcc_emails");
        if (cc.length() > 0) box.addView(Ui.pair(a, "CC", join(cc)));
        if (bcc.length() > 0) box.addView(Ui.pair(a, "BCC", join(bcc)));
        box.addView(Ui.pair(a, "Created", when(r)));
        box.addView(Ui.pair(a, "Attempts", SndData.s(r, "attempts").isEmpty() ? "0" : SndData.s(r, "attempts")));
        box.addView(Ui.pair(a, "Event", SndData.s(r, "event_key")));
        JSONArray m = SndData.arr(r, "attachment_manifest");
        for (int i = 0; i < m.length(); i++) {
            JSONObject f = m.optJSONObject(i);
            if (f != null) box.addView(Ui.pair(a, i == 0 ? "Attachments" : "", SndData.s(f, "file_name")));
        }
        if (!SndData.s(r, "last_error").isEmpty()) {
            TextView e = Ui.text(a, Lookups.j(r, "last_error"), 12, Ui.RED_FG, false);
            e.setTextIsSelectable(true);
            e.setPadding(0, dp(6), 0, dp(6));
            box.addView(e);
        }
        TextView body = Ui.text(a, Lookups.j(r, "body_text"), 12.5f, Ui.TEXT, false);
        body.setTextIsSelectable(true);
        body.setPadding(0, dp(8), 0, 0);
        box.addView(body);
        ScrollView sv = new ScrollView(a);
        sv.addView(box);
        String st = status(r);
        AlertDialog.Builder b = new AlertDialog.Builder(a).setTitle(SndData.s(r, "subject").isEmpty() ? "Email" : SndData.s(r, "subject")).setView(sv)
            .setNegativeButton("Close", null);
        if (st.equals("FAILED") || (st.equals("PENDING") && "PENDING".equals(SndData.s(r, "status")))) {
            b.setPositiveButton("Retry sending", (d, w) -> retry(SndData.s(r, "id")));
        }
        b.show();
    }

    private static String join(JSONArray a) {
        List<String> l = new ArrayList<>();
        for (int i = 0; i < a.length(); i++) l.add(a.optString(i));
        return String.join(", ", l);
    }

    /** NotificationService.dispatch for one FAILED / PENDING row, then wait for the result. */
    private void retry(String id) {
        if (id.isEmpty()) return;
        a.toast("Sending again…");
        Api.async(() -> {
            List<String> ids = new ArrayList<>();
            ids.add(id);
            JSONObject result = SndMail.dispatch(api, ids);
            List<JSONObject> now = SndMail.waitForOutbox(api, ids, 20000);
            return SndMail.outcome(now, result);
        }, (out, err) -> {
            if (err != null) a.toast(Api.message(err));
            else if ("SENT".equals(out[0])) a.toast("Email sent.");
            else a.confirm("Email not sent", out[1] == null ? "The email server did not accept the email." : out[1], "OK", () -> { });
            reload();
        });
    }

    private void renderLog() {
        if (log.length() == 0) { add(Ui.empty(a, "No emails sent from the Email module yet."), 8); return; }
        for (int i = 0; i < log.length(); i++) {
            JSONObject r = log.optJSONObject(i);
            if (r == null) continue;
            LinearLayout c = Ui.card(a);
            LinearLayout top = Ui.hbox(a);
            String subj = SndData.s(r, "subject");
            top.addView(Ui.text(a, subj.isEmpty() ? "(no subject)" : subj, 13.5f, Ui.TEXT, true), Ui.weight(1));
            String st = SndData.s(r, "status");
            top.addView(Ui.chip(a, st, Ui.tone(st.equals("SENT") ? "COMPLETE" : st.equals("QUEUED") ? "PENDING" : "FAILED")));
            c.addView(top);
            String t = SndData.s(r, "sent_at");
            c.addView(Ui.text(a, (t.length() >= 16 ? Ui.date(t) + " " + t.substring(11, 16) + " UTC" : Ui.date(t)) + " · " + SndData.s(r, "recipient_count") + " recipient(s)", 11.5f, Ui.MUTED, false));
            String detail = SndData.s(r, "error_text").isEmpty() ? SndData.s(r, "recipient_summary") : Lookups.j(r, "error_text");
            TextView d = Ui.text(a, detail, 11.5f, SndData.s(r, "error_text").isEmpty() ? Ui.MUTED : Ui.RED_FG, false);
            d.setMaxLines(4);
            c.addView(d);
            add(c, 8);
        }
    }
}
