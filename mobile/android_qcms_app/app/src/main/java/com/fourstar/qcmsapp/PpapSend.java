package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * R39 · Send the PPAP package to the customer from the Android app - port of core/ppap_service.PpapService.send_to_customer
 * and the website's section E "Send the PPAP package to the customer":
 * - only documents of THIS package (current revisions, user selection) - never documents of another package / customer;
 * - recipients that belong to another customer / supplier in the party master are refused (foreign_party_recipients):
 *   a PPAP package is confidential to its own customer;
 * - up to 10 MB / 18 files the documents are e-mail attachments (attachment_manifest), above that the phone builds the
 *   ZIP ("NN Element name/file"), stores it under &lt;tenant&gt;/ppap/&lt;package&gt;/submissions/ and mails a 7-day signed link;
 * - outbox row PPAP_PACKAGE_SUBMISSION -> qcms-send-email, logged in ppap_customer_submissions; an IN_PROGRESS package
 *   becomes SUBMITTED.
 */
final class PpapSend {
    private PpapSend() { }

    static final long MAX_EMAIL_BYTES = 10L * 1024 * 1024;
    static final int MAX_EMAIL_FILES = 18;
    static final int SIGNED_LINK_SECONDS = 7 * 24 * 3600;
    static final String EVENT = "PPAP_PACKAGE_SUBMISSION";

    /** submission_method: EMAIL_ATTACHMENTS when the files fit in one e-mail, else SECURE_LINK. */
    static String method(List<JSONObject> docs) {
        long total = 0;
        for (JSONObject d : docs) total += d.optLong("size_bytes", 0);
        return total > MAX_EMAIL_BYTES || docs.size() > MAX_EMAIL_FILES ? "SECURE_LINK" : "EMAIL_ATTACHMENTS";
    }

    static long totalBytes(List<JSONObject> docs) {
        long total = 0;
        for (JSONObject d : docs) total += d.optLong("size_bytes", 0);
        return total;
    }

    /** split_emails: valid, de-duplicated (case-insensitive) addresses from ; , newline or space separated text. */
    static List<String> splitEmails(String text) {
        List<String> out = new ArrayList<>();
        for (String token : (text == null ? "" : text).split("[;,\\n\\s]+")) {
            String t = token.trim().replaceAll("^<|>$", "");
            if (!t.isEmpty() && t.matches("[^@\\s]+@[^@\\s]+\\.[^@\\s]+") && !SndMail.containsIgnoreCase(out, t)) out.add(t);
        }
        return out;
    }

    static List<String> partyEmails(JSONObject party) {
        if (party == null) return new ArrayList<>();
        return splitEmails(PpapData.s(party, "email") + ";" + PpapData.s(party, "notification_emails"));
    }

    /** foreign_party_recipients: addresses that belong to another party (supplier / other customer). */
    static List<String> foreignRecipients(List<String> addresses, List<JSONObject> parties, String customerId) {
        Map<String, Set<String>> byEmail = new HashMap<>();
        for (JSONObject p : parties) for (String e : partyEmails(p)) {
            byEmail.computeIfAbsent(e.toLowerCase(Locale.ROOT), k -> new HashSet<>()).add(PpapData.s(p, "id"));
        }
        List<String> bad = new ArrayList<>();
        for (String a : addresses) {
            Set<String> owners = byEmail.get(a.toLowerCase(Locale.ROOT));
            if (owners != null && !owners.contains(customerId == null ? "" : customerId)) bad.add(a);
        }
        return bad;
    }

    /** Result of a send: method, status (SENT / QUEUED / FAILED), link (secure link or ""). */
    static String[] send(Api api, JSONObject pkg, List<JSONObject> docs, List<JSONObject> elements, List<String> to, List<String> cc,
                         String subject, String message, String customerName) throws Exception {
        List<String> recipients = new ArrayList<>();
        for (String t : to) if (t != null && !t.trim().isEmpty()) recipients.add(t.trim());
        if (recipients.isEmpty()) throw new Api.ApiException(422, "Send to - enter at least one customer e-mail address.");
        if (docs.isEmpty()) throw new Api.ApiException(422, "Documents - select at least one document for the package.");
        String packageId = PpapData.s(pkg, "id");
        for (JSONObject d : docs) {
            String owner = PpapData.s(d, "package_id");
            if (!owner.isEmpty() && !owner.equals(packageId)) throw new Api.ApiException(422, "Documents - only documents of this PPAP package can be sent to its customer.");
        }
        // confidentiality: re-check the recipients against the party master on the server data
        List<JSONObject> parties = PpapData.list(api.rows("parties?select=id,email,notification_emails&limit=5000"));
        List<String> all = new ArrayList<>(recipients);
        all.addAll(cc);
        List<String> foreign = foreignRecipients(all, parties, PpapData.s(pkg, "customer_id"));
        if (!foreign.isEmpty()) throw new Api.ApiException(422, "Recipients - " + String.join(", ", foreign)
            + " belong(s) to another customer / supplier. A PPAP package is confidential to its customer.");

        String method = method(docs);
        JSONArray manifest = new JSONArray();
        String zipPath = null, link = "", expires = null;
        if (method.equals("SECURE_LINK")) {
            byte[] zip = PpapData.zip(api, docs, elements);
            String stamp = new SimpleDateFormat("yyyyMMddHHmmss", Locale.ROOT).format(new Date());
            zipPath = api.tenantId + "/ppap/" + packageId + "/submissions/" + stamp + "_" + PpapData.safeName(PpapData.s(pkg, "package_no"), false) + ".zip";
            api.upload(zipPath, zip, "application/zip", true);
            link = api.signedUrl(zipPath, SIGNED_LINK_SECONDS);
            if (link == null || link.isEmpty()) throw new Api.ApiException(500, "The secure download link could not be created.");
            expires = Instant.now().plusSeconds(SIGNED_LINK_SECONDS).toString();
        } else {
            for (JSONObject d : docs) manifest.put(new JSONObject().put("bucket", Api.BUCKET).put("object_path", PpapData.s(d, "object_path"))
                .put("file_name", PpapData.s(d, "file_name")).put("mime_type", PpapData.s(d, "mime_type").isEmpty() ? "application/octet-stream" : PpapData.s(d, "mime_type"))
                .put("generated", false));
        }
        String sender = api.fullName == null || api.fullName.isEmpty() ? "Quality Department" : api.fullName;
        StringBuilder body = new StringBuilder();
        body.append(message == null || message.trim().isEmpty()
            ? "Dear " + (customerName == null || customerName.isEmpty() ? "Customer" : customerName) + ",\n\nPlease find the PPAP submission package below."
            : message.trim());
        body.append("\n\nPPAP package: ").append(dash(PpapData.s(pkg, "package_no")))
            .append("\nPPAP no.: ").append(dash(PpapData.s(pkg, "customer_ppap_no")))
            .append("\nPart no.: ").append(dash(PpapData.s(pkg, "customer_part_no")))
            .append("\nSubmission level: ").append(PpapData.s(pkg, "submission_level").isEmpty() ? "3" : PpapData.s(pkg, "submission_level"))
            .append("\nDocuments: ").append(docs.size());
        if (!link.isEmpty()) body.append("\n\nThe package is larger than an e-mail allows. Download it (ZIP, valid for 7 days):\n").append(link);
        else {
            body.append("\n\nDocuments attached:");
            for (JSONObject d : docs) body.append("\n- ").append(PpapData.s(d, "file_name")).append(" (Rev. ").append(dash(PpapData.s(d, "revision"))).append(")");
        }
        body.append("\n\nRegards,\n").append(sender);
        String subj = subject == null || subject.trim().isEmpty()
            ? ("PPAP Submission · " + (PpapData.s(pkg, "customer_ppap_no").isEmpty() ? PpapData.s(pkg, "package_no") : PpapData.s(pkg, "customer_ppap_no"))
               + " · Part " + PpapData.s(pkg, "customer_part_no")).trim()
            : subject.trim();
        subj = SndMail.departmentSubject(subj, "Quality", EVENT);

        JSONObject row = new JSONObject();
        row.put("tenant_id", api.tenantId);
        row.put("event_key", EVENT);
        row.put("recipient_email", recipients.get(0));
        row.put("recipient_name", customerName == null || customerName.isEmpty() ? JSONObject.NULL : customerName);
        row.put("cc_emails", SndMail.toArray(cc));
        row.put("subject", subj);
        row.put("body_text", body.toString());
        row.put("body_html", SndMail.userHtml(body.toString(), ""));
        row.put("related_table", "ppap_packages");
        row.put("related_id", packageId);
        row.put("context", new JSONObject().put("to_emails", SndMail.toArray(recipients)).put("package_no", PpapData.s(pkg, "package_no"))
            .put("ppap_no", PpapData.s(pkg, "customer_ppap_no")).put("document_count", docs.size()).put("method", method)
            .put("module_key", PpapData.MODULE_KEY).put("department", "Quality").put("source", "android_ppap_send"));
        row.put("template_key", JSONObject.NULL);
        row.put("attachment_manifest", manifest);
        row.put("is_automatic", false);
        row.put("status", "PENDING");
        JSONObject saved = api.insert("qcms_notification_outbox", row);
        String outboxId = PpapData.s(saved, "id");
        List<String> ids = new ArrayList<>();
        ids.add(outboxId);
        JSONObject res = SndMail.dispatch(api, ids);
        String err = res.optString("error", "");
        String status = res.optInt("sent", 0) > 0 ? "SENT" : (res.optInt("failed", 0) > 0 || (!err.isEmpty() && !"null".equals(err)) ? "FAILED" : "QUEUED");

        // log_submission
        Map<String, JSONObject> byId = new HashMap<>();
        for (JSONObject e : elements) byId.put(PpapData.s(e, "id"), e);
        JSONArray list = new JSONArray();
        for (JSONObject d : docs) {
            JSONObject e = byId.get(PpapData.s(d, "package_element_id"));
            list.put(new JSONObject().put("element_no", e == null ? JSONObject.NULL : (Object) PpapData.num(e, "element_no"))
                .put("element_name", e == null ? JSONObject.NULL : PpapData.s(e, "element_name")).put("file_name", PpapData.s(d, "file_name"))
                .put("revision", PpapData.s(d, "revision")).put("document_id", PpapData.s(d, "id")).put("size_bytes", d.optLong("size_bytes", 0)));
        }
        JSONObject sub = new JSONObject();
        sub.put("package_id", packageId);
        sub.put("sent_to", String.join("; ", recipients));
        sub.put("cc_emails", cc.isEmpty() ? JSONObject.NULL : String.join("; ", cc));
        sub.put("method", method);
        sub.put("documents", list);
        sub.put("document_count", docs.size());
        sub.put("total_bytes", totalBytes(docs));
        sub.put("zip_object_path", zipPath == null ? JSONObject.NULL : zipPath);
        sub.put("link_expires_at", expires == null ? JSONObject.NULL : expires);
        sub.put("outbox_id", outboxId.isEmpty() ? JSONObject.NULL : outboxId);
        sub.put("status", status);
        sub.put("message", !link.isEmpty() ? link : (message == null || message.trim().isEmpty() ? JSONObject.NULL : message.trim()));
        sub.put("sent_by_name", sender);
        try { api.insert("ppap_customer_submissions", sub); } catch (Exception ignored) { }
        if (!status.equals("FAILED") && "IN_PROGRESS".equalsIgnoreCase(PpapData.s(pkg, "status"))) {
            try { api.update("ppap_packages", packageId, new JSONObject().put("status", "SUBMITTED")); } catch (Exception ignored) { }
        }
        return new String[]{method, status, link};
    }

    private static String dash(String v) { return v == null || v.isEmpty() ? "-" : v; }

    // ------------------------------------------------------------------ dialog (website section E)
    static void dialog(MainActivity a, Api api, JSONObject pkg, List<JSONObject> current, List<JSONObject> elements, Runnable done) {
        if (current.isEmpty()) { a.toast("Upload documents to the elements first."); return; }
        a.toast("Loading customer contacts…");
        Api.async(() -> {
            String cid = PpapData.s(pkg, "customer_id");
            if (cid.isEmpty()) return null;
            List<JSONObject> r = PpapData.list(api.rows("parties?select=id,party_name,contact_person,email,notification_emails&id=eq." + Api.enc(cid) + "&limit=1"));
            return r.isEmpty() ? null : r.get(0);
        }, (customer, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            chooseDocs(a, api, pkg, current, elements, customer, done);
        });
    }

    private static void chooseDocs(MainActivity a, Api api, JSONObject pkg, List<JSONObject> current, List<JSONObject> elements, JSONObject customer, Runnable done) {
        Map<String, JSONObject> byId = new HashMap<>();
        for (JSONObject e : elements) byId.put(PpapData.s(e, "id"), e);
        List<JSONObject> sorted = new ArrayList<>(current);
        sorted.sort((x, y) -> Integer.compare(no(byId, x), no(byId, y)));
        String[] labels = new String[sorted.size()];
        boolean[] checked = new boolean[sorted.size()];
        for (int i = 0; i < sorted.size(); i++) {
            JSONObject d = sorted.get(i);
            JSONObject e = byId.get(PpapData.s(d, "package_element_id"));
            labels[i] = String.format(Locale.ROOT, "%02d · %s · %s · Rev. %s", no(byId, d), e == null ? "" : PpapData.s(e, "element_name"),
                PpapData.s(d, "file_name"), dash(PpapData.s(d, "revision")));
            checked[i] = true;
        }
        new AlertDialog.Builder(a).setTitle("Documents to send (current revisions)").setMultiChoiceItems(labels, checked, (d, w, on) -> checked[w] = on)
            .setPositiveButton("Next", (d, w) -> {
                List<JSONObject> chosen = new ArrayList<>();
                for (int i = 0; i < sorted.size(); i++) if (checked[i]) chosen.add(sorted.get(i));
                if (chosen.isEmpty()) { a.toast("Select at least one document."); return; }
                compose(a, api, pkg, chosen, elements, customer, done);
            }).setNegativeButton("Cancel", null).show();
    }

    private static int no(Map<String, JSONObject> byId, JSONObject doc) {
        JSONObject e = byId.get(PpapData.s(doc, "package_element_id"));
        return e == null ? 0 : PpapData.num(e, "element_no");
    }

    private static void compose(MainActivity a, Api api, JSONObject pkg, List<JSONObject> chosen, List<JSONObject> elements, JSONObject customer, Runnable done) {
        List<String> contacts = splitEmails(PpapData.s(pkg, "customer_contact_email"));
        if (contacts.isEmpty()) contacts = partyEmails(customer);
        String customerName = customer == null ? "" : PpapData.s(customer, "party_name");
        String method = method(chosen);
        LinearLayout box = Ui.vbox(a);
        box.setPadding(Ui.dp(a, 18), Ui.dp(a, 4), Ui.dp(a, 18), Ui.dp(a, 8));
        box.addView(Ui.text(a, String.format(Locale.ROOT, "%d document(s) · %.2f MB · %s", chosen.size(), totalBytes(chosen) / 1048576.0,
            method.equals("SECURE_LINK") ? "secure 7-day download link (ZIP)" : "e-mail attachments"), 12, Ui.MUTED, false));
        box.addView(Ui.label(a, "To"));
        EditText to = Ui.input(a, "name@customer.com; …", false);
        to.setText(contacts.isEmpty() ? "" : contacts.get(0));
        box.addView(to);
        if (contacts.size() > 1) box.addView(Ui.text(a, "Customer contacts: " + String.join("; ", contacts), 11, Ui.MUTED, false));
        box.addView(Ui.label(a, "CC"));
        EditText cc = Ui.input(a, "optional", false);
        box.addView(cc);
        box.addView(Ui.label(a, "Subject"));
        EditText subject = Ui.input(a, "Subject", false);
        subject.setText(("PPAP Submission · PPAP " + (PpapData.s(pkg, "customer_ppap_no").isEmpty() ? PpapData.s(pkg, "package_no") : PpapData.s(pkg, "customer_ppap_no"))
            + " · Part " + PpapData.s(pkg, "customer_part_no")).trim());
        box.addView(subject);
        box.addView(Ui.label(a, "Message"));
        EditText msg = Ui.input(a, "Message", true);
        String contact = customer == null ? "" : PpapData.s(customer, "contact_person");
        msg.setText("Dear " + (contact.isEmpty() ? "Sir / Madam" : contact) + ",\n\nPlease find our PPAP submission (Level "
            + (PpapData.s(pkg, "submission_level").isEmpty() ? "3" : PpapData.s(pkg, "submission_level")) + ") for part "
            + dash(PpapData.s(pkg, "customer_part_no")) + ".");
        box.addView(msg);
        TextView note = Ui.text(a, "Only this package's selected documents are sent - never documents of another customer. Recipients that belong to "
            + "another customer / supplier in the party master are refused.", 11, Ui.MUTED, false);
        box.addView(note);
        ScrollView sv = new ScrollView(a);
        sv.addView(box);
        new AlertDialog.Builder(a).setTitle("Send PPAP package to " + (customerName.isEmpty() ? "the customer" : customerName)).setView(sv)
            .setPositiveButton("Send", (d, w) -> {
                List<String> toList = splitEmails(to.getText().toString());
                List<String> ccList = splitEmails(cc.getText().toString());
                if (toList.isEmpty()) { a.toast("To - enter at least one valid customer e-mail address."); return; }
                a.toast("Sending the PPAP package…");
                Api.async(() -> send(api, pkg, chosen, elements, toList, ccList, subject.getText().toString(), msg.getText().toString(), customerName),
                    (res, err) -> {
                        if (err != null) { a.toast(Api.message(err)); return; }
                        String how = "SECURE_LINK".equals(res[0]) ? "with a secure 7-day download link" : "with attachments";
                        if ("FAILED".equals(res[1])) a.toast("The e-mail could not be sent (check Admin → Email Settings). The submission is logged as FAILED.");
                        else a.toast("PPAP package e-mailed to " + String.join(", ", toList) + " " + how + " (" + Ui.pretty(res[1]) + ").");
                        if (done != null) done.run();
                    });
            }).setNegativeButton("Cancel", null).show();
    }
}
