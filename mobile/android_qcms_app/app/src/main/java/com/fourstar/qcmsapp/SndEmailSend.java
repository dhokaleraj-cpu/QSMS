package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.TreeSet;

/**
 * Email → Send Email (app_pages/email_center.render_send), native. Recipients from employees, departments,
 * email groups and typed addresses; sent through the COMPANY mailbox exactly like the website: attachments
 * uploaded to notification_exports, one qcms_notification_outbox row per message (event USER_EMAIL,
 * context.to_emails / sender_name / sender_email / from_mode), qcms-send-email, then qcms_mail_sent_log.
 * Personal mailbox passwords / "My Email Settings" are intentionally not handled in the app.
 */
public final class SndEmailSend extends Screen {
    private static final String SIGNATURE_PREF = "qcms_mail_signature";

    private List<JSONObject> employees;
    private List<JSONObject> groups = new ArrayList<>();
    private boolean groupsReady = true;
    private List<String> departments = new ArrayList<>();
    private String fromMode = "COMPANY", company = "";
    private Exception loadError;

    // form state
    private String fromName = "", fromEmail = "", toExtra = "", ccExtra = "", bccExtra = "", subject = "", body = "", signature = "";
    private final Set<String> toEmp = new LinkedHashSet<>(), toDep = new LinkedHashSet<>(), toGrp = new LinkedHashSet<>(), ccEmp = new LinkedHashSet<>();
    private boolean hide = true;
    private final List<Attachments.FileData> files = new ArrayList<>();
    private boolean sending;
    private String resultStatus, resultMessage;

    private EditText fromNameIn, fromEmailIn, toExtraIn, ccExtraIn, bccExtraIn, subjectIn, bodyIn, signatureIn;
    private CheckBox hideBox;

    public SndEmailSend(MainActivity a) { super(a); }

    @Override public String title() { return "Send Email"; }
    @Override public String subtitle() { return "Company mailbox · shows your name & email"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        if (employees != null) { render(); return scroll; }
        if (loadError != null) { page.addView(error(loadError, () -> { loadError = null; a.rebuild(); })); return scroll; }
        page.addView(loading());
        Api.async(() -> {
            List<JSONObject> emps = SndMail.employees(api);
            List<JSONObject> grp = new ArrayList<>();
            boolean ready = true;
            try {
                JSONArray g = api.rows("qcms_mail_groups?select=*&status=eq.ACTIVE&order=group_name.asc&limit=1000");
                for (int i = 0; i < g.length(); i++) grp.add(g.getJSONObject(i));
            } catch (Exception e) { ready = false; }
            String[] who = SndMail.senderIdentity(api);
            String mode = SndMail.fromMode(api);
            String mailbox = SndMail.companyMailbox(api);
            return new Object[]{emps, grp, ready, who, mode, mailbox};
        }, (r, err) -> {
            if (err != null) { loadError = err; a.rebuild(); return; }
            @SuppressWarnings("unchecked") List<JSONObject> emps = (List<JSONObject>) r[0];
            @SuppressWarnings("unchecked") List<JSONObject> grp = (List<JSONObject>) r[1];
            groups = grp;
            groupsReady = (Boolean) r[2];
            String[] who = (String[]) r[3];
            if (fromName.isEmpty()) fromName = who[0];
            if (fromEmail.isEmpty()) fromEmail = who[1];
            fromMode = (String) r[4];
            company = (String) r[5];
            TreeSet<String> deps = new TreeSet<>();
            for (JSONObject e : emps) if (!SndData.s(e, "department").isEmpty()) deps.add(SndData.s(e, "department"));
            departments = new ArrayList<>(deps);
            try { signature = api.prefs().getString(SIGNATURE_PREF, ""); } catch (Exception ignored) { }
            employees = emps;
            a.rebuild();
        });
        return scroll;
    }

    @Override public void reload() { sync(); employees = null; a.rebuild(); }

    private String empLabel(JSONObject e) {
        String mail = SndMail.employeeEmail(e);
        return SndMail.employeeName(e) + " · " + (SndData.s(e, "department").isEmpty() ? "-" : SndData.s(e, "department")) + " · " + (mail.isEmpty() ? "no email" : mail);
    }

    private String groupLabel(JSONObject g) {
        int n = SndData.arr(g, "member_employee_ids").length() + SndData.arr(g, "extra_emails").length();
        return SndData.s(g, "group_name") + " (" + n + ")";
    }

    private void render() {
        if (resultStatus != null) add(SndUi.resultCard(a, resultStatus, resultMessage), 2);
        if (!groupsReady) add(Ui.chip(a, "Email Groups need the R14/R15 database step; sending works now.", "amber"), 4);

        // ---- From
        LinearLayout from = Ui.card(a);
        from.addView(Ui.text(a, "From name", 11.5f, Ui.MUTED, true));
        fromNameIn = Ui.input(a, "From name", false);
        fromNameIn.setText(fromName);
        from.addView(fromNameIn, Ui.matchWrap(a, 4));
        from.addView(Ui.text(a, "From / reply-to email", 11.5f, Ui.MUTED, true), Ui.matchWrap(a, 8));
        fromEmailIn = SndUi.emails(a, "you@fourstarindustries.com");
        fromEmailIn.setSingleLine(true);
        fromEmailIn.setText(fromEmail);
        from.addView(fromEmailIn, Ui.matchWrap(a, 4));
        String shown = "USER".equals(fromMode)
            ? "Recipients see " + fromName + " <" + fromEmail + "> as the sender."
            : "Recipients see " + fromName + " via QCMS <" + (company.isEmpty() ? "company mailbox" : company) + "> and replies go to " + fromEmail + ".";
        TextView cap = Ui.text(a, shown, 11.5f, Ui.MUTED, false);
        cap.setPadding(0, dp(6), 0, 0);
        from.addView(cap);
        add(from, 6);

        // ---- To
        add(Ui.label(a, "To · people, departments, groups"), 10);
        LinearLayout toCard = Ui.card(a);
        toCard.addView(pickRow("Employees", toEmp, () -> pickEmployees("To · employees", toEmp)));
        toCard.addView(pickRow("Departments", toDep, () -> pickDepartments()));
        toCard.addView(pickRow("Email groups", toGrp, () -> pickGroups()));
        toCard.addView(Ui.text(a, "Other addresses (To) · separate with ; or ,", 11.5f, Ui.MUTED, true), Ui.matchWrap(a, 8));
        toExtraIn = SndUi.emails(a, "name@company.com; …");
        toExtraIn.setText(toExtra);
        toCard.addView(toExtraIn, Ui.matchWrap(a, 4));
        add(toCard, 2);

        // ---- CC / BCC
        add(Ui.label(a, "CC / BCC"), 10);
        LinearLayout ccCard = Ui.card(a);
        ccCard.addView(pickRow("CC employees", ccEmp, () -> pickEmployees("CC · employees", ccEmp)));
        ccCard.addView(Ui.text(a, "CC other addresses", 11.5f, Ui.MUTED, true), Ui.matchWrap(a, 8));
        ccExtraIn = SndUi.emails(a, "name@company.com; …");
        ccExtraIn.setText(ccExtra);
        ccCard.addView(ccExtraIn, Ui.matchWrap(a, 4));
        ccCard.addView(Ui.text(a, "BCC other addresses", 11.5f, Ui.MUTED, true), Ui.matchWrap(a, 8));
        bccExtraIn = SndUi.emails(a, "name@company.com; …");
        bccExtraIn.setText(bccExtra);
        ccCard.addView(bccExtraIn, Ui.matchWrap(a, 4));
        hideBox = SndUi.check(a, "Send department / group recipients as BCC (recipients do not see each other)", hide);
        ccCard.addView(hideBox, Ui.matchWrap(a, 6));
        add(ccCard, 2);

        // ---- message
        add(Ui.label(a, "Message"), 10);
        LinearLayout msg = Ui.card(a);
        subjectIn = Ui.input(a, "Subject", false);
        subjectIn.setText(subject);
        msg.addView(subjectIn);
        bodyIn = SndUi.area(a, "Message", 8);
        bodyIn.setText(body);
        msg.addView(bodyIn, Ui.matchWrap(a, 8));
        signatureIn = SndUi.area(a, "Signature (optional, saved on this phone)", 2);
        signatureIn.setText(signature);
        msg.addView(signatureIn, Ui.matchWrap(a, 8));
        add(msg, 2);

        // ---- attachments
        add(Ui.label(a, "Attachments (max 10 MB in total)"), 10);
        LinearLayout att = Ui.card(a);
        long total = 0;
        for (int i = 0; i < files.size(); i++) {
            Attachments.FileData f = files.get(i);
            total += f.data.length;
            LinearLayout row = Ui.hbox(a);
            row.addView(Ui.text(a, f.name + " · " + Ui.num(f.data.length / 1024.0, 0) + " KB", 12.5f, Ui.TEXT, false), Ui.weight(1));
            TextView rm = Ui.text(a, "Remove", 12.5f, Ui.RED_FG, true);
            rm.setPadding(dp(10), dp(8), dp(4), dp(8));
            final int index = i;
            rm.setOnClickListener(v -> { sync(); files.remove(index); a.rebuild(); });
            row.addView(rm);
            att.addView(row);
        }
        if (files.isEmpty()) att.addView(Ui.text(a, "No attachments.", 12, Ui.MUTED, false));
        else att.addView(Ui.text(a, "Total " + Ui.num(total / 1048576.0, 1) + " MB", 11.5f, total > SndMail.COMPANY_MAX_ATTACHMENT_BYTES ? Ui.RED_FG : Ui.MUTED, false));
        Button addFile = Ui.outline(a, "Add attachment (camera / gallery / file)", Ui.TEAL);
        addFile.setOnClickListener(v -> { sync(); a.pickFile("Attach to email", false, f -> { if (f != null) { files.add(f); a.rebuild(); } }); });
        att.addView(addFile, Ui.matchWrap(a, 8));
        add(att, 2);

        Button review = Ui.primary(a, sending ? "Sending…" : "Review recipients & send");
        review.setEnabled(!sending);
        review.setOnClickListener(v -> review());
        add(review, 14);
        add(Ui.text(a, "Your Office 365 / personal mailbox password is never stored in the app. Emails go through the company email server (Admin → Email Settings).", 11, Ui.MUTED, false), 6);
    }

    interface Pick { void run(); }

    private LinearLayout pickRow(String label, Set<String> chosen, Pick pick) {
        LinearLayout row = Ui.hbox(a);
        row.setPadding(0, dp(6), 0, dp(6));
        LinearLayout texts = Ui.vbox(a);
        texts.addView(Ui.text(a, label, 12.5f, Ui.TEXT, true));
        String summary = chosen.isEmpty() ? "None selected" : chosen.size() + " selected · " + shortNames(chosen);
        texts.addView(Ui.text(a, summary, 11.5f, Ui.MUTED, false));
        row.addView(texts, Ui.weight(1));
        Button b = Ui.outline(a, "Choose", Ui.TEAL);
        b.setOnClickListener(v -> { sync(); pick.run(); });
        row.addView(b);
        return row;
    }

    private String shortNames(Set<String> ids) {
        List<String> names = new ArrayList<>();
        for (String id : ids) {
            String n = id;
            for (JSONObject e : employees) if (id.equals(SndData.s(e, "id"))) n = SndMail.employeeName(e);
            for (JSONObject g : groups) if (id.equals(SndData.s(g, "id"))) n = SndData.s(g, "group_name");
            names.add(n);
            if (names.size() >= 4) break;
        }
        return String.join(", ", names) + (ids.size() > 4 ? " …" : "");
    }

    private void pickEmployees(String title, Set<String> target) {
        List<String> ids = new ArrayList<>(), labels = new ArrayList<>();
        for (JSONObject e : employees) { ids.add(SndData.s(e, "id")); labels.add(empLabel(e)); }
        SndUi.multiPick(a, title, ids, labels, target, chosen -> { target.clear(); target.addAll(chosen); a.rebuild(); });
    }

    private void pickDepartments() {
        SndUi.multiPick(a, "To · departments", departments, departments, toDep, chosen -> { toDep.clear(); toDep.addAll(chosen); a.rebuild(); });
    }

    private void pickGroups() {
        if (!groupsReady) { a.toast("Email Groups are not installed yet (R14/R15 database step)."); return; }
        List<String> ids = new ArrayList<>(), labels = new ArrayList<>();
        for (JSONObject g : groups) { ids.add(SndData.s(g, "id")); labels.add(groupLabel(g)); }
        SndUi.multiPick(a, "To · email groups", ids, labels, toGrp, chosen -> { toGrp.clear(); toGrp.addAll(chosen); a.rebuild(); });
    }

    private void sync() {
        if (fromNameIn != null) fromName = SndUi.text(fromNameIn).trim();
        if (fromEmailIn != null) fromEmail = SndUi.text(fromEmailIn).trim();
        if (toExtraIn != null) toExtra = SndUi.text(toExtraIn);
        if (ccExtraIn != null) ccExtra = SndUi.text(ccExtraIn);
        if (bccExtraIn != null) bccExtra = SndUi.text(bccExtraIn);
        if (subjectIn != null) subject = SndUi.text(subjectIn);
        if (bodyIn != null) body = SndUi.text(bodyIn);
        if (signatureIn != null) signature = SndUi.text(signatureIn);
        if (hideBox != null) hide = hideBox.isChecked();
    }

    private static List<String> list(String s) { List<String> l = new ArrayList<>(); l.add(s); return l; }

    // ------------------------------------------------------------------ review + send (render_send)
    private void review() {
        sync();
        List<String> warnings = new ArrayList<>();
        List<String> none = Collections.emptyList();
        List<SndMail.Recipient> direct = SndMail.resolve(employees, groups, new ArrayList<>(toEmp), none, none, list(toExtra), none, warnings);
        List<SndMail.Recipient> bulk = SndMail.resolve(employees, groups, none, new ArrayList<>(toDep), new ArrayList<>(toGrp), none, SndMail.emails(direct), warnings);
        List<String> ex2 = SndMail.emails(direct); ex2.addAll(SndMail.emails(bulk));
        List<SndMail.Recipient> ccR = SndMail.resolve(employees, groups, new ArrayList<>(ccEmp), none, none, list(ccExtra), ex2, warnings);
        List<String> ex3 = new ArrayList<>(ex2); ex3.addAll(SndMail.emails(ccR));
        List<SndMail.Recipient> bccTyped = SndMail.resolve(employees, groups, none, none, none, list(bccExtra), ex3, warnings);
        List<SndMail.Recipient> toR = new ArrayList<>(direct);
        if (!hide) toR.addAll(bulk);
        List<SndMail.Recipient> bccR = new ArrayList<>();
        if (hide) bccR.addAll(bulk);
        bccR.addAll(bccTyped);
        int count = toR.size() + ccR.size() + bccR.size();
        String problem = null;
        if (count == 0) problem = "Select at least one recipient.";
        else if (subject.trim().isEmpty()) problem = "Enter a subject.";
        else if (SndMail.valid(fromEmail).isEmpty()) problem = "Enter a valid From / reply-to email address.";
        long total = 0;
        for (Attachments.FileData f : files) total += f.data.length;
        if (problem == null && total > SndMail.COMPANY_MAX_ATTACHMENT_BYTES) problem = String.format(Locale.US, "Attachments are %.1f MB. The limit is 10 MB per email.", total / 1048576.0);
        StringBuilder m = new StringBuilder();
        for (String w : warnings) m.append("⚠ ").append(w).append('\n');
        if (problem != null) {
            if (m.length() > 0) problem = m + "\n" + problem;
            a.confirm("Cannot send yet", problem, "OK", () -> { });
            return;
        }
        String shownFrom = "USER".equals(fromMode) ? fromName + " <" + fromEmail + ">" : fromName + " via QCMS <" + (company.isEmpty() ? "company mailbox" : company) + "> · reply-to " + fromEmail;
        m.append("From: ").append(shownFrom).append('\n');
        m.append("To: ").append(shortList(toR)).append('\n');
        m.append("CC: ").append(shortList(ccR)).append('\n');
        m.append("BCC: ").append(shortList(bccR)).append('\n');
        m.append("Subject: ").append(subject.trim()).append('\n');
        List<String> names = new ArrayList<>();
        for (Attachments.FileData f : files) names.add(f.name);
        m.append("Attachments: ").append(names.isEmpty() ? "None" : String.join(", ", names)).append("\n\n");
        m.append(count).append(" recipient(s).");
        a.confirm("Send email to " + count + " recipient(s)?", m.toString(), "Send", () -> send(toR, ccR, bccR, count));
    }

    private static String shortList(List<SndMail.Recipient> l) {
        if (l.isEmpty()) return "—";
        List<String> e = SndMail.emails(l);
        return String.join(", ", e.subList(0, Math.min(6, e.size()))) + (e.size() > 6 ? " … +" + (e.size() - 6) : "");
    }

    private void send(List<SndMail.Recipient> toR, List<SndMail.Recipient> ccR, List<SndMail.Recipient> bccR, int count) {
        sending = true;
        resultStatus = null;
        try { api.prefs().edit().putString(SIGNATURE_PREF, signature).apply(); } catch (Exception ignored) { }
        a.rebuild();
        final String subj = subject, text = body, sig = signature, name = fromName.isEmpty() ? fromEmail : fromName, mail = fromEmail, mode = fromMode;
        final List<Attachments.FileData> atts = new ArrayList<>(files);
        Api.async(() -> {
            String status, error = null;
            int messages = 1;
            try {
                JSONArray manifest = new JSONArray();
                if (!atts.isEmpty()) {
                    String folder = SndMail.exportFolder(api);
                    for (Attachments.FileData f : atts) manifest.put(SndMail.uploadExport(api, folder, f.name, f.data, f.mime, false));
                }
                List<JSONObject> rows = SndMail.companyOutboxRows(subj, SndMail.userHtml(text, sig), text, toR, ccR, bccR, name, mail, manifest, mode);
                messages = rows.size();
                List<String> ids = new ArrayList<>();
                for (JSONObject r : rows) ids.add(SndData.s(api.insert("qcms_notification_outbox", r), "id"));
                JSONObject result = SndMail.dispatch(api, ids);
                // the edge function keeps sending when this call times out, so the outbox rows are the truth
                List<JSONObject> now = SndMail.waitForOutbox(api, ids, 15000);
                List<String> pending = new ArrayList<>();
                for (JSONObject r : now) if ("PENDING".equals(SndData.s(r, "status"))) pending.add(SndData.s(r, "id"));
                if (!pending.isEmpty()) {
                    SndMail.dispatch(api, pending);
                    now = SndMail.waitForOutbox(api, ids, 45000);
                }
                String[] out = SndMail.outcome(now, result);
                status = out[0];
                error = out[1];
            } catch (Exception e) {
                status = "FAILED";
                error = Api.message(e);
                if (error != null && error.length() > 900) error = error.substring(0, 900);
            }
            try {
                List<String> all = new ArrayList<>(SndMail.emails(toR));
                all.addAll(SndMail.emails(ccR));
                all.addAll(SndMail.emails(bccR));
                String summary = String.join(", ", all.subList(0, Math.min(40, all.size()))) + (all.size() > 40 ? " …" : "");
                JSONObject log = new JSONObject();
                log.put("sender_email", mail);
                log.put("subject", subj);
                log.put("recipient_count", count);
                log.put("recipient_summary", summary);
                log.put("message_count", messages);
                log.put("status", status);
                log.put("error_text", error == null ? JSONObject.NULL : error);
                api.insert("qcms_mail_sent_log", log);
            } catch (Exception ignored) { }
            return new String[]{status, error};
        }, (out, err) -> {
            sending = false;
            String st = err != null ? "FAILED" : out[0];
            String msg = err != null ? Api.message(err) : out[1];
            resultStatus = st;
            if ("SENT".equals(st) || "QUEUED".equals(st)) {
                resultMessage = ("SENT".equals(st) ? "Your email \"" + subj.trim() + "\" was sent" : "Your email \"" + subj.trim() + "\" is queued")
                    + " to " + count + " recipient(s). Replies go to " + mail + "." + (msg != null && "QUEUED".equals(st) ? "\n" + msg : "");
                subject = ""; body = ""; toExtra = ""; ccExtra = ""; bccExtra = "";
                files.clear();
                a.toast("SENT".equals(st) ? "Email sent." : "Email queued.");
            } else {
                resultMessage = "Email not fully sent: " + (msg == null ? "" : msg);
            }
            a.rebuild();
            if (scroll != null) scroll.post(() -> scroll.scrollTo(0, 0));
        });
    }
}
