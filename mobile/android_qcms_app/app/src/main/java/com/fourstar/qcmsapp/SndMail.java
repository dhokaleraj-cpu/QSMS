package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;

/**
 * Email helpers ported from core/notification_service.py (routes, templates, recipients, outbox, dispatch)
 * and core/mail_service.py (Email module: recipients, company mailbox outbox rows, HTML body).
 */
final class SndMail {
    private SndMail() { }

    static final String BUCKET = Api.BUCKET;
    static final String COMPANY_EVENT_KEY = "USER_EMAIL";
    static final int COMPANY_MAX_RECIPIENTS = 90;
    static final long COMPANY_MAX_ATTACHMENT_BYTES = 10L * 1024 * 1024;
    private static final Pattern EMAIL_RE = Pattern.compile("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$");

    // ------------------------------------------------------------------ small helpers
    static String valid(String email) {
        String t = email == null ? "" : email.trim();
        return EMAIL_RE.matcher(t).matches() ? t : "";
    }

    /** notification_ui._split_emails: ; , or new line separated, '@' required, unique (case-insensitive). */
    static List<String> splitEmails(String value) {
        List<String> out = new ArrayList<>();
        for (String token : (value == null ? "" : value).split("[;,\\n]+")) {
            String e = token.trim();
            if (!e.isEmpty() && e.contains("@") && !containsIgnoreCase(out, e)) out.add(e);
        }
        return out;
    }

    static boolean containsIgnoreCase(List<String> list, String v) {
        for (String s : list) if (s.equalsIgnoreCase(v)) return true;
        return false;
    }

    static String normDept(String value) {
        return (value == null ? "" : value).toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]+", "");
    }

    static String employeeName(JSONObject e) {
        String n = (SndData.s(e, "first_name") + " " + SndData.s(e, "last_name")).trim();
        return n.isEmpty() ? SndData.s(e, "employee_code") : n;
    }

    static String employeeEmail(JSONObject e) {
        return valid(SndData.s(e, "email"));
    }

    static String join(List<String> list, String sep) { return String.join(sep, list); }

    static JSONArray toArray(List<String> list) {
        JSONArray a = new JSONArray();
        for (String s : list) a.put(s);
        return a;
    }

    // ------------------------------------------------------------------ templates (NotificationService._template_text)
    private static final Pattern DOUBLE = Pattern.compile("\\{\\{\\s*([a-zA-Z0-9_]+)\\s*\\}\\}");

    /** '{{ field }}' / '{field}' placeholders; empty values and unknown names print '-'. */
    static String fill(String template, JSONObject ctx) {
        String text = template == null ? "" : template;
        String converted = DOUBLE.matcher(text).replaceAll("{$1}");
        StringBuilder out = new StringBuilder();
        int i = 0, n = converted.length();
        try {
            while (i < n) {
                char c = converted.charAt(i);
                if (c == '{') {
                    if (i + 1 < n && converted.charAt(i + 1) == '{') { out.append('{'); i += 2; continue; }
                    int end = converted.indexOf('}', i);
                    if (end < 0) return converted;
                    String field = converted.substring(i + 1, end);
                    int cut = field.length();
                    for (char stop : new char[]{':', '!'}) { int k = field.indexOf(stop); if (k >= 0) cut = Math.min(cut, k); }
                    String name = field.substring(0, cut).trim();
                    if (name.isEmpty() || !name.matches("[A-Za-z0-9_]+")) return converted;
                    out.append(value(ctx, name));
                    i = end + 1;
                } else if (c == '}') {
                    if (i + 1 < n && converted.charAt(i + 1) == '}') { out.append('}'); i += 2; continue; }
                    return converted;
                } else {
                    out.append(c);
                    i++;
                }
            }
        } catch (Exception e) {
            return converted;
        }
        return out.toString();
    }

    private static String value(JSONObject ctx, String key) {
        if (ctx == null || !ctx.has(key)) return "-";
        Object v = ctx.opt(key);
        if (v == null || v == JSONObject.NULL) return "-";
        if (v instanceof Boolean) return ((Boolean) v) ? "True" : "False";
        if (v instanceof Double || v instanceof Float) {
            double d = ((Number) v).doubleValue();
            return String.valueOf(d);
        }
        String s = String.valueOf(v);
        return s.isEmpty() ? "-" : s;
    }

    /** Body of a workflow notification as HTML (NotificationService.enqueue). */
    static String notificationHtml(String body) {
        String esc = (body == null ? "" : body).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
        String[] lines = esc.split("\\r?\\n", -1);
        // Python splitlines() drops a trailing empty line
        int count = lines.length;
        if (count > 0 && lines[count - 1].isEmpty() && esc.endsWith("\n")) count--;
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < count; i++) { if (i > 0) b.append("<br>"); b.append(lines[i]); }
        return b.toString();
    }

    /** mail_service.body_html: plain text -> safe HTML (paragraphs, line breaks, optional signature). */
    static String userHtml(String text, String signature) {
        String esc = htmlEscape(text == null ? "" : text).replace("\r\n", "\n");
        String[] paragraphs = esc.split("\n\n", -1);
        StringBuilder content = new StringBuilder();
        for (String p : paragraphs) {
            if (!p.trim().isEmpty() || paragraphs.length == 1) content.append("<p>").append(p.replace("\n", "<br>")).append("</p>");
        }
        if (signature != null && !signature.trim().isEmpty()) {
            content.append("<p style='color:#5C7778'>").append(htmlEscape(signature).replace("\n", "<br>")).append("</p>");
        }
        return "<div style=\"font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#173233\">" + content + "</div>";
    }

    static String htmlEscape(String s) {
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;").replace("'", "&#x27;");
    }

    // ------------------------------------------------------------------ routes / templates / recipients
    static JSONObject route(Api api, String event) {
        try {
            JSONArray r = api.rows("qcms_notification_routes?select=*&event_key=eq." + Api.enc(event.toUpperCase(Locale.ROOT)) + "&enabled=eq.true&limit=1");
            return r.length() > 0 ? r.getJSONObject(0) : null;
        } catch (Exception e) {
            return null;
        }
    }

    static JSONObject template(Api api, String templateKey, String event) {
        String key = (templateKey == null || templateKey.trim().isEmpty() ? (event == null ? "" : event) : templateKey).trim().toUpperCase(Locale.ROOT);
        if (key.isEmpty()) return null;
        try {
            JSONArray r = api.rows("qcms_email_templates?select=*&template_key=eq." + Api.enc(key) + "&enabled=eq.true&limit=1");
            return r.length() > 0 ? r.getJSONObject(0) : null;
        } catch (Exception e) {
            return null;
        }
    }

    /** Active employees (id, code, name, email, department) for routing and the Email module. */
    static List<JSONObject> employees(Api api) throws Exception {
        JSONArray r = api.rows("employees?select=id,employee_code,first_name,last_name,email,department,designation,status&order=first_name.asc&limit=5000");
        List<JSONObject> out = new ArrayList<>();
        for (int i = 0; i < r.length(); i++) {
            JSONObject e = r.getJSONObject(i);
            String st = SndData.s(e, "status");
            if (st.isEmpty() || st.equalsIgnoreCase("ACTIVE")) out.add(e);
        }
        return out;
    }

    /** NotificationService.department_emails. */
    static List<String> departmentEmails(List<JSONObject> employees, String department, List<String> exclude) {
        String target = normDept(department);
        List<String> result = new ArrayList<>();
        if (target.isEmpty()) return result;
        for (JSONObject row : employees) {
            if (!normDept(SndData.s(row, "department")).equals(target)) continue;
            String email = SndData.s(row, "email");
            if (!email.isEmpty() && !containsIgnoreCase(exclude, email) && !containsIgnoreCase(result, email)) result.add(email);
        }
        return result;
    }

    /** NotificationService.recipient_for_route -> {email, name}. */
    static String[] recipientForRoute(List<JSONObject> employees, JSONObject route) {
        String empId = SndData.s(route, "employee_id");
        if (!empId.isEmpty()) {
            for (JSONObject e : employees) {
                if (empId.equals(SndData.s(e, "id")) && !SndData.s(e, "email").isEmpty()) return new String[]{SndData.s(e, "email"), employeeName(e)};
            }
        }
        String dept = SndData.s(route, "department");
        if (!dept.isEmpty()) {
            for (JSONObject e : employees) {
                if (normDept(SndData.s(e, "department")).equals(normDept(dept)) && !SndData.s(e, "email").isEmpty()) return new String[]{SndData.s(e, "email"), employeeName(e)};
            }
        }
        return new String[]{SndData.s(route, "fallback_email"), SndData.s(route, "route_label")};
    }

    /** NotificationService._party_notification_emails. */
    static List<String> partyEmails(JSONObject party) {
        List<String> values = new ArrayList<>();
        for (String source : new String[]{SndData.s(party, "email"), party == null ? "" : Lookups.j(party, "notification_emails")}) {
            for (String token : source.split("[;,\\n]+")) {
                String e = token.trim();
                if (!e.isEmpty() && e.contains("@") && !containsIgnoreCase(values, e)) values.add(e);
            }
        }
        return values;
    }

    // ------------------------------------------------------------------ storage + outbox
    /** NotificationService._persist_generated_pdf / email_center._upload_company_attachments path. */
    static JSONObject uploadExport(Api api, String folder, String fileName, byte[] data, String mime, boolean generated) throws Exception {
        String safe = (fileName == null ? "" : fileName).replaceAll("[^A-Za-z0-9_.-]+", "_").replaceAll("^_+|_+$", "");
        if (safe.isEmpty()) safe = generated ? "QCMS_Report.pdf" : "attachment";
        String path = folder + "/" + safe;
        String type = mime == null || mime.isEmpty() ? "application/octet-stream" : mime;
        api.upload(path, data, type, false);
        JSONObject m = new JSONObject();
        m.put("bucket", BUCKET);
        m.put("object_path", path);
        m.put("file_name", safe);
        m.put("mime_type", type);
        m.put("generated", generated);
        return m;
    }

    static String exportFolder(Api api) {
        return api.tenantId + "/notification_exports/" + UUID.randomUUID().toString().replace("-", "");
    }

    /** Edge function qcms-send-email with {"outbox_ids": [...]} (NotificationService.dispatch). Never throws. */
    static JSONObject dispatch(Api api, List<String> ids) {
        JSONObject result = new JSONObject();
        try {
            if (ids.isEmpty()) return result.put("processed", 0);
            String body = api.invokeFunction("qcms-send-email", new JSONObject().put("outbox_ids", toArray(ids)));
            try { return new JSONObject(body); } catch (Exception e) { return result.put("result", body); }
        } catch (Exception e) {
            try { result.put("processed", 0); result.put("error", Api.message(e)); } catch (Exception ignored) { }
            return result;
        }
    }

    /** email_center._wait_for_outbox: poll until every row is SENT / FAILED (or timeout). */
    static List<JSONObject> waitForOutbox(Api api, List<String> ids, long timeoutMs) {
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (true) {
            List<JSONObject> rows = new ArrayList<>();
            boolean done = true;
            for (String id : ids) {
                JSONObject row;
                try {
                    JSONArray r = new JSONArray(api.get("qcms_notification_outbox?select=id,status,last_error,attempts,sent_at,subject,recipient_email&id=eq." + Api.enc(id), false).body);
                    row = r.length() > 0 ? r.getJSONObject(0) : null;
                } catch (Exception e) {
                    row = null;
                }
                if (row == null) {
                    row = new JSONObject();
                    try { row.put("id", id); row.put("status", "UNKNOWN"); } catch (Exception ignored) { }
                }
                String st = SndData.s(row, "status");
                if (!st.equals("SENT") && !st.equals("FAILED") && !st.equals("UNKNOWN")) done = false;
                rows.add(row);
            }
            if (done || System.currentTimeMillis() >= deadline) return rows;
            try { Thread.sleep(1500); } catch (InterruptedException e) { return rows; }
        }
    }

    /** email_center._outbox_outcome -> {status, error}. status SENT / PARTIAL / FAILED / QUEUED. */
    static String[] outcome(List<JSONObject> rows, JSONObject result) {
        boolean allSent = !rows.isEmpty();
        boolean anyFailed = false, anySent = false;
        List<String> errors = new ArrayList<>();
        for (JSONObject r : rows) {
            String st = SndData.s(r, "status");
            if (!st.equals("SENT")) allSent = false;
            if (st.equals("SENT")) anySent = true;
            if (st.equals("FAILED")) { anyFailed = true; if (!SndData.s(r, "last_error").isEmpty()) errors.add(Lookups.j(r, "last_error")); }
        }
        if (allSent) return new String[]{"SENT", null};
        if (anyFailed) {
            String err = String.join("; ", errors);
            if (err.isEmpty()) err = result == null ? "" : SndData.s(result, "error");
            if (err.isEmpty()) err = "The email server did not accept the email.";
            if (err.length() > 900) err = err.substring(0, 900);
            return new String[]{anySent ? "PARTIAL" : "FAILED", err};
        }
        return new String[]{"QUEUED", "The email server is still sending - it will be delivered in a moment. Check My Sent Emails."};
    }

    // ------------------------------------------------------------------ Email module (core/mail_service.py)
    /** mail_service.Recipient. */
    static final class Recipient {
        final String email, name, source;
        Recipient(String email, String name, String source) { this.email = email; this.name = name; this.source = source; }
    }

    /** mail_service.resolve_recipients -> recipients; warnings are appended to the given list. */
    static List<Recipient> resolve(List<JSONObject> employees, List<JSONObject> groups, List<String> employeeIds, List<String> departments,
                                   List<String> groupIds, List<String> extra, List<String> exclude, List<String> warnings) {
        java.util.LinkedHashMap<String, Recipient> out = new java.util.LinkedHashMap<>();
        Set<String> skip = new LinkedHashSet<>();
        for (String x : exclude) if (x != null && !x.trim().isEmpty()) skip.add(x.trim().toLowerCase(Locale.ROOT));
        java.util.Map<String, JSONObject> active = new java.util.LinkedHashMap<>();
        for (JSONObject e : employees) active.put(SndData.s(e, "id"), e);
        for (String eid : employeeIds) {
            JSONObject row = active.get(eid);
            if (row == null) continue;
            String email = employeeEmail(row);
            if (!email.isEmpty()) add(out, skip, email, employeeName(row), "Employee");
            else warnings.add(employeeName(row) + " has no email address in Employee Master.");
        }
        Set<String> wanted = new LinkedHashSet<>();
        for (String d : departments) if (d != null && !d.trim().isEmpty()) wanted.add(d.trim().toLowerCase(Locale.ROOT));
        if (!wanted.isEmpty()) {
            int found = 0;
            for (JSONObject row : active.values()) {
                if (wanted.contains(SndData.s(row, "department").toLowerCase(Locale.ROOT))) {
                    String email = employeeEmail(row);
                    if (!email.isEmpty()) { add(out, skip, email, employeeName(row), "Department " + SndData.s(row, "department")); found++; }
                }
            }
            if (found == 0) warnings.add("No employee with an email address was found in the selected department(s).");
        }
        for (String gid : groupIds) {
            JSONObject group = null;
            for (JSONObject g : groups) if (gid.equals(SndData.s(g, "id")) && (SndData.s(g, "status").isEmpty() || SndData.s(g, "status").equalsIgnoreCase("ACTIVE"))) group = g;
            if (group == null) continue;
            String gname = "Group " + SndData.s(group, "group_name");
            JSONArray members = SndData.arr(group, "member_employee_ids");
            for (int i = 0; i < members.length(); i++) {
                JSONObject row = active.get(members.optString(i));
                if (row != null && !employeeEmail(row).isEmpty()) add(out, skip, employeeEmail(row), employeeName(row), gname);
            }
            JSONArray extraMails = SndData.arr(group, "extra_emails");
            for (int i = 0; i < extraMails.length(); i++) {
                String v = valid(extraMails.optString(i));
                if (!v.isEmpty()) add(out, skip, v, "", gname);
            }
        }
        for (String raw : extra) {
            for (String piece : (raw == null ? "" : raw).split("[;,\\s]+")) {
                if (piece.isEmpty()) continue;
                String email = valid(piece);
                if (!email.isEmpty()) add(out, skip, email, "", "Typed");
                else warnings.add("Ignored invalid email address: " + piece);
            }
        }
        return new ArrayList<>(out.values());
    }

    private static void add(java.util.Map<String, Recipient> out, Set<String> skip, String email, String name, String source) {
        String key = email.toLowerCase(Locale.ROOT);
        if (!key.isEmpty() && !skip.contains(key) && !out.containsKey(key)) out.put(key, new Recipient(email, name, source));
    }

    static List<String> emails(List<Recipient> list) {
        List<String> out = new ArrayList<>();
        for (Recipient r : list) out.add(r.email);
        return out;
    }

    /** mail_service.company_outbox_rows: one qcms_notification_outbox row per message (BCC split at 90). */
    static List<JSONObject> companyOutboxRows(String subject, String htmlBody, String textBody, List<Recipient> to, List<Recipient> cc, List<Recipient> bcc,
                                              String senderName, String senderEmail, JSONArray manifest, String fromMode) throws Exception {
        if (subject == null || subject.trim().isEmpty()) throw new IllegalArgumentException("Enter a subject.");
        if (to.isEmpty() && cc.isEmpty() && bcc.isEmpty()) throw new IllegalArgumentException("Select at least one recipient.");
        String sender = valid(senderEmail);
        if (sender.isEmpty()) throw new IllegalArgumentException("Your QCMS login has no valid email address, so the email cannot show you as the sender.");
        int fixed = to.size() + cc.size();
        if (fixed > COMPANY_MAX_RECIPIENTS) throw new IllegalArgumentException("To + CC has " + fixed + " addresses. Put large lists in BCC (limit " + COMPANY_MAX_RECIPIENTS + " per message).");
        int room = COMPANY_MAX_RECIPIENTS - fixed;
        List<List<Recipient>> batches = new ArrayList<>();
        if (bcc.size() > room) {
            batches.add(new ArrayList<>(bcc.subList(0, room)));
            for (int i = room; i < bcc.size(); i += COMPANY_MAX_RECIPIENTS) batches.add(new ArrayList<>(bcc.subList(i, Math.min(bcc.size(), i + COMPANY_MAX_RECIPIENTS))));
        } else batches.add(new ArrayList<>(bcc));
        List<List<Recipient>> clean = new ArrayList<>();
        for (List<Recipient> b : batches) if (!b.isEmpty()) clean.add(b);
        if (clean.isEmpty()) clean.add(new ArrayList<>());
        List<JSONObject> rows = new ArrayList<>();
        for (int index = 0; index < clean.size(); index++) {
            List<String> toList = index == 0 ? emails(to) : new ArrayList<>();
            List<String> ccList = index == 0 ? emails(cc) : new ArrayList<>();
            String primary = toList.isEmpty() ? sender : toList.get(0);
            String rname = index == 0 && !to.isEmpty() ? to.get(0).name : senderName;
            JSONObject row = new JSONObject();
            row.put("event_key", COMPANY_EVENT_KEY);
            row.put("recipient_email", primary);
            row.put("recipient_name", rname == null || rname.isEmpty() ? JSONObject.NULL : rname);
            row.put("cc_emails", toArray(ccList));
            row.put("bcc_emails", toArray(emails(clean.get(index))));
            row.put("subject", subject.trim());
            row.put("body_text", textBody == null ? "" : textBody);
            row.put("body_html", htmlBody);
            row.put("template_key", COMPANY_EVENT_KEY);
            row.put("attachment_manifest", manifest == null ? new JSONArray() : new JSONArray(manifest.toString()));
            row.put("is_automatic", false);
            row.put("status", "PENDING");
            JSONObject ctx = new JSONObject();
            ctx.put("to_emails", toArray(toList));
            ctx.put("sender_name", senderName);
            ctx.put("sender_email", sender);
            ctx.put("from_mode", "USER".equalsIgnoreCase(fromMode) ? "USER" : "COMPANY");
            ctx.put("message_index", index + 1);
            ctx.put("message_count", clean.size());
            row.put("context", ctx);
            rows.add(row);
        }
        return rows;
    }

    /** system_settings.get_email_from_mode (admin value in master_value_catalog; default COMPANY). */
    static String fromMode(Api api) {
        try {
            JSONArray r = api.rows("master_value_catalog?select=value_text&field_key=eq." + Api.enc("qcms.system.email_from_mode") + "&status=eq.ACTIVE&order=last_used_at.desc&limit=1");
            if (r.length() > 0) {
                String v = Lookups.j(r.getJSONObject(0), "value_text").trim().toUpperCase(Locale.ROOT);
                if (v.equals("USER") || v.equals("COMPANY")) return v;
            }
        } catch (Exception ignored) { }
        return "COMPANY";
    }

    /** email_center._sender_identity: saved My Email Settings value, then Employee Master, then login. */
    static String[] senderIdentity(Api api) {
        try {
            JSONArray r = api.rows("master_value_catalog?select=value_text&field_key=eq." + Api.enc("qcms.email.from." + api.userId) + "&status=eq.ACTIVE&order=last_used_at.desc&limit=1");
            if (r.length() > 0) {
                JSONObject saved = new JSONObject(Lookups.j(r.getJSONObject(0), "value_text"));
                if (!SndData.s(saved, "name").isEmpty() && !SndData.s(saved, "email").isEmpty()) return new String[]{SndData.s(saved, "name"), SndData.s(saved, "email")};
            }
        } catch (Exception ignored) { }
        String name = api.fullName == null ? "" : api.fullName.trim();
        String email = api.email == null ? "" : api.email.trim();
        try {
            if (!api.employeeId.isEmpty()) {
                JSONArray e = api.rows("employees?select=first_name,last_name,employee_code,email&id=eq." + Api.enc(api.employeeId));
                if (e.length() > 0) {
                    String en = employeeName(e.getJSONObject(0));
                    String ee = employeeEmail(e.getJSONObject(0));
                    if (!en.isEmpty()) name = en;
                    if (!ee.isEmpty()) email = ee;
                }
            }
        } catch (Exception ignored) { }
        if (name.isEmpty()) name = email.contains("@") ? email.substring(0, email.indexOf('@')) : email;
        return new String[]{name, email};
    }

    static String companyMailbox(Api api) {
        try {
            JSONArray r = api.rows("qcms_email_settings?select=sender_email&limit=1");
            if (r.length() > 0) return SndData.s(r.getJSONObject(0), "sender_email");
        } catch (Exception ignored) { }
        return "";
    }

    /** Keys of a JSONObject (for context copies). */
    static List<String> keys(JSONObject o) {
        List<String> out = new ArrayList<>();
        if (o == null) return out;
        Iterator<String> it = o.keys();
        while (it.hasNext()) out.add(it.next());
        return out;
    }
}
