package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Native port of app_pages/email_settings.py (Email Server, Templates & Automatic Notifications).
 * The SMTP password is write-only exactly like the website: it is never read into the app or shown;
 * the app only knows whether one is saved. A new password is written to qcms_email_settings.smtp_password
 * the same way the website writes it (Repository.upsert_by on the tenant row).
 */
public final class AdmEmailScreen extends Screen {
    /** Every column except smtp_password. */
    static final String SERVER_COLS = "id,enabled,smtp_host,smtp_port,smtp_username,sender_email,sender_name,reply_to,use_tls,use_ssl,timeout_seconds,last_test_at,last_test_status,last_test_message";

    private static String routeEvent = AdmMail.EVENTS[0][0];
    private static String templateEvent = AdmMail.EVENTS[0][0];

    JSONObject server;
    boolean passwordSaved;
    List<String> departments = new ArrayList<>();
    List<JSONObject> employees = new ArrayList<>();
    final Map<String, String> employeeOptions = new java.util.LinkedHashMap<>();
    Map<String, JSONObject> routes = new HashMap<>();
    Map<String, JSONObject> templates = new HashMap<>();
    List<JSONObject> schedules = new ArrayList<>();
    List<JSONObject> outbox = new ArrayList<>();

    public AdmEmailScreen(MainActivity a) { super(a); }

    @Override public String title() { return "Email Settings"; }
    @Override public String subtitle() { return "Server, next-stage routing, templates and automatic open / overdue reports"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        if (!api.isAdmin()) {
            add(AdmUi.adminOnly(a, AdmDb.ADMIN_ONLY), 4);
            return scroll;
        }
        page.addView(loading());
        Api.async(() -> {
            Object[] r = new Object[8];
            r[0] = AdmDb.first(new JSONArray(api.get("qcms_email_settings?select=" + SERVER_COLS + "&limit=1", false).body));
            r[1] = new JSONArray(api.get("qcms_email_settings?select=id&smtp_password=not.is.null&limit=1", false).body).length() > 0;
            r[2] = AdmDb.activeDepartments(api);
            r[3] = AdmDb.list(AdmDb.select(api, "employees", null, "first_name.asc", 5000));
            r[4] = AdmDb.select(api, "qcms_notification_routes", null, null, 500);
            r[5] = AdmDb.select(api, "qcms_email_templates", null, "template_key.asc", 500);
            JSONArray sch;
            try { sch = AdmDb.select(api, "qcms_notification_schedules", null, "schedule_key.asc", 100); } catch (Exception e) { sch = new JSONArray(); }
            r[6] = sch;
            r[7] = AdmDb.select(api, "qcms_notification_outbox", null, "created_at.desc", 300);
            return r;
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { add(error(err, this::reload)); return; }
            server = (JSONObject) res[0];
            passwordSaved = (Boolean) res[1];
            @SuppressWarnings("unchecked") List<String> d = (List<String>) res[2];
            departments = d;
            employees.clear();
            employeeOptions.clear();
            @SuppressWarnings("unchecked") List<JSONObject> all = (List<JSONObject>) res[3];
            for (JSONObject e : all) {
                String st = AdmPy.j(e, "status");
                if (!(st.isEmpty() ? "ACTIVE" : st).equals("ACTIVE")) continue;
                employees.add(e);
                String email = AdmPy.j(e, "email");
                employeeOptions.put(AdmPy.j(e, "id"), AdmPy.j(e, "employee_code") + " · " + AdmPy.j(e, "first_name") + " " + AdmPy.j(e, "last_name")
                    + " · " + AdmPy.j(e, "department") + " · " + (email.isEmpty() ? "NO EMAIL" : email));
            }
            routes.clear();
            for (JSONObject r : AdmDb.list((JSONArray) res[4])) routes.put(AdmPy.j(r, "event_key"), r);
            templates.clear();
            for (JSONObject t : AdmDb.list((JSONArray) res[5])) templates.put(AdmPy.j(t, "template_key"), t);
            schedules = AdmDb.list((JSONArray) res[6]);
            outbox = AdmDb.list((JSONArray) res[7]);
            renderServer();
            renderRoutes();
            renderTemplates();
            AdmEmailAuto.renderSchedules(this, page);
            AdmEmailAuto.renderOutbox(this, page);
        });
        return scroll;
    }

    void saved(Button b, String message, Exception err) {
        AdmUi.enable(b, true);
        if (err != null) { a.toast(Api.message(err)); return; }
        a.toast(message);
        a.rebuild();
    }

    // ------------------------------------------------------------------ A. server
    private void renderServer() {
        JSONObject ex = server == null ? new JSONObject() : server;
        LinearLayout s = AdmUi.section(a, page, "A", "EMAIL SERVER SETTINGS", "SMTP password is write-only in the UI. Leave Password blank to keep the saved password.");
        String host0 = AdmPy.fold(AdmPy.j(ex, "smtp_host"));
        if (host0.equals("smtp.office365.com") || host0.equals("smtp-mail.outlook.com"))
            s.addView(AdmUi.note(a, "Microsoft 365 email is configured in QCMS. TENANT SMTP AUTH BLOCK CHECK: if a future 535 5.7.139 occurs, verify Authenticated SMTP / tenant policy before changing QCMS credentials. QCMS cannot override this from application code.", "green"), Ui.matchWrap(a, 6));
        Switch enabled = AdmUi.toggle(a, s, "Enable Email Notifications", AdmPy.bool(ex, "enabled", false));
        EditText host = AdmUi.field(a, s, "SMTP Host", AdmPy.j(ex, "smtp_host"), "smtp.office365.com");
        int port0 = ex.optInt("smtp_port", 0);
        EditText port = AdmUi.number(a, s, "SMTP Port", port0 == 0 ? 587 : port0);
        String sn = AdmPy.j(ex, "sender_name");
        EditText senderName = AdmUi.field(a, s, "Sender Name", sn.isEmpty() ? "QCMS" : sn, "QCMS");
        EditText username = AdmUi.field(a, s, "SMTP Username", AdmPy.j(ex, "smtp_username"), "SMTP Username");
        EditText password = AdmUi.password(a, s, "SMTP Password / App Password", "Leave blank to keep saved password");
        s.addView(Ui.text(a, passwordSaved ? "A password is saved (never shown)." : "No password saved yet.", 11, passwordSaved ? Ui.GREEN_FG : Ui.AMBER_FG, false), Ui.matchWrap(a, 2));
        EditText sender = AdmUi.field(a, s, "Sender Email", AdmPy.j(ex, "sender_email"), "qcms@company.com");
        EditText reply = AdmUi.field(a, s, "Reply-To", AdmPy.j(ex, "reply_to"), "Reply-To");
        Switch tls = AdmUi.toggle(a, s, "STARTTLS", AdmPy.bool(ex, "use_tls", true));
        Switch ssl = AdmUi.toggle(a, s, "SMTP SSL", AdmPy.bool(ex, "use_ssl", false));
        int to0 = ex.optInt("timeout_seconds", 0);
        EditText timeout = AdmUi.number(a, s, "Timeout seconds", to0 == 0 ? 20 : to0);
        AdmUi.primary(a, s, "Save Email Server Settings", v -> {
            Integer p = AdmUi.intIn(port, 1, 65535);
            if (p == null) { a.toast("SMTP Port must be between 1 and 65535."); return; }
            Integer t = AdmUi.intIn(timeout, 5, 120);
            if (t == null) { a.toast("Timeout seconds must be between 5 and 120."); return; }
            Button b = (Button) v;
            AdmUi.enable(b, false);
            String pw = AdmUi.text(password);
            Api.async(() -> {
                JSONObject payload = new JSONObject();
                payload.put("enabled", enabled.isChecked());
                payload.put("smtp_host", AdmDb.orNull(AdmUi.text(host)));
                payload.put("smtp_port", p.intValue());
                payload.put("smtp_username", AdmDb.orNull(AdmUi.text(username)));
                payload.put("sender_email", AdmDb.orNull(AdmUi.text(sender)));
                String nm = AdmUi.text(senderName).trim();
                payload.put("sender_name", nm.isEmpty() ? "QCMS" : nm);
                payload.put("reply_to", AdmDb.orNull(AdmUi.text(reply)));
                payload.put("use_tls", tls.isChecked());
                payload.put("use_ssl", ssl.isChecked());
                payload.put("timeout_seconds", t.intValue());
                // Blank password keeps the saved one (the website re-sends the stored value; omitting it leaves it unchanged).
                if (!pw.trim().isEmpty()) payload.put("smtp_password", pw);
                return AdmDb.upsertBy(api, "qcms_email_settings", payload, AdmDb.tenantKey(api));
            }, (r, e) -> saved(b, "Email server settings saved.", e));
        });
    }

    // ------------------------------------------------------------------ B. routes
    private void renderRoutes() {
        LinearLayout s = AdmUi.section(a, page, "B", "NEXT-STAGE RESPONSIBILITY ROUTING", "Each event can target one responsible employee, a responsible department, CC the department and optionally copy the linked Supplier / OSP Vendor. Supplier email is taken from Party Master Primary Email + Notification Email(s).");
        LinearLayout form = Ui.vbox(a);
        AdmUi.choice(a, s, "Workflow Event", AdmMail.keys(), AdmMail.keyLabels(true), routeEvent, v -> { routeEvent = v; routeForm(form); });
        s.addView(form);
        routeForm(form);
        List<List<String>> rows = new ArrayList<>();
        for (String[] e : AdmMail.EVENTS) {
            JSONObject r = routes.containsKey(e[0]) ? routes.get(e[0]) : new JSONObject();
            JSONObject emp = null;
            for (JSONObject x : employees) if (AdmPy.j(x, "id").equals(AdmPy.j(r, "employee_id")) && !AdmPy.j(x, "id").isEmpty()) emp = x;
            String name = emp == null ? "" : (AdmPy.j(emp, "first_name") + " " + AdmPy.j(emp, "last_name")).trim();
            String email = emp != null && !AdmPy.j(emp, "email").isEmpty() ? AdmPy.j(emp, "email") : AdmPy.j(r, "fallback_email");
            rows.add(AdmUi.listOf(e[2], e[1], AdmPy.j(r, "department"), name, email, yes(AdmPy.bool(r, "department_cc", false)),
                yes(AdmPy.bool(r, "send_to_supplier", false)), yes(AdmPy.bool(r, "enabled", false))));
        }
        s.addView(new DataGrid(a, "Notification routes", AdmUi.listOf("Module", "Event", "Department", "Employee", "Email", "Department CC", "Supplier Copy", "Enabled"), rows, 390, null), Ui.matchWrap(a, 10));
    }

    static String yes(boolean b) { return b ? "Yes" : "No"; }

    private void routeForm(LinearLayout form) {
        form.removeAllViews();
        String event = routeEvent;
        JSONObject row = routes.containsKey(event) ? routes.get(event) : new JSONObject();
        List<String> deptValues = new ArrayList<>();
        deptValues.add("");
        deptValues.addAll(departments);
        String curDept = AdmPy.j(row, "department");
        final String[] department = {deptValues.contains(curDept) ? curDept : ""};
        List<String> deptLabels = new ArrayList<>();
        for (String d : deptValues) deptLabels.add(d.isEmpty() ? "— Not assigned —" : d);
        final String[] employee = {""};
        LinearLayout empBox = Ui.vbox(a);
        String curEmp = AdmPy.j(row, "employee_id");
        Runnable[] fillEmp = new Runnable[1];
        fillEmp[0] = () -> {
            empBox.removeAllViews();
            List<String> ids = new ArrayList<>();
            ids.add("");
            for (JSONObject e : employees)
                if (department[0].isEmpty() || AdmPy.fold(AdmPy.j(e, "department")).equals(AdmPy.fold(department[0]))) ids.add(AdmPy.j(e, "id"));
            String cur = employee[0].isEmpty() ? curEmp : employee[0];
            employee[0] = ids.contains(cur) ? cur : "";
            List<String> labels = new ArrayList<>();
            for (String id : ids) labels.add(employeeOptions.containsKey(id) ? employeeOptions.get(id) : "— Department fallback —");
            AdmUi.choice(a, empBox, "Responsible Employee", ids, labels, employee[0], v -> employee[0] = v);
        };
        AdmUi.choice(a, form, "Responsible Department", deptValues, deptLabels, department[0], v -> { department[0] = v; employee[0] = ""; fillEmp[0].run(); });
        form.addView(empBox);
        fillEmp[0].run();
        Switch cc = AdmUi.toggle(a, form, "CC Responsible Department", AdmPy.bool(row, "department_cc", false));
        Switch supplier = AdmUi.toggle(a, form, "Copy linked Supplier / Vendor", AdmPy.bool(row, "send_to_supplier", false));
        EditText fallback = AdmUi.field(a, form, "Fallback Email", AdmPy.j(row, "fallback_email"), "Fallback Email");
        EditText next = AdmUi.field(a, form, "Next Stage / Action", AdmPy.j(row, "next_stage"), "Next Stage / Action");
        Switch enabled = AdmUi.toggle(a, form, "Route Enabled", AdmPy.bool(row, "enabled", false));
        String tk = AdmPy.j(row, "template_key").isEmpty() ? event : AdmPy.j(row, "template_key");
        final String[] template = {AdmMail.keys().contains(tk) ? tk : AdmMail.EVENTS[0][0]};
        AdmUi.choice(a, form, "Email Template", AdmMail.keys(), AdmMail.keyLabels(false), template[0], v -> template[0] = v);
        AdmUi.primary(a, form, "Save Responsibility Route", v -> {
            Button b = (Button) v;
            AdmUi.enable(b, false);
            Api.async(() -> {
                JSONObject p = new JSONObject();
                p.put("event_key", event);
                p.put("route_label", AdmMail.label(event));
                p.put("employee_id", employee[0].isEmpty() ? JSONObject.NULL : employee[0]);
                p.put("department", department[0].isEmpty() ? JSONObject.NULL : department[0]);
                p.put("department_cc", cc.isChecked());
                p.put("send_to_supplier", supplier.isChecked());
                p.put("fallback_email", AdmDb.orNull(AdmUi.text(fallback)));
                p.put("template_key", template[0]);
                p.put("next_stage", AdmDb.orNull(AdmUi.text(next)));
                p.put("subject_template", JSONObject.NULL);
                p.put("enabled", enabled.isChecked());
                return AdmDb.upsertBy(api, "qcms_notification_routes", p, AdmDb.tenantKey(api, "event_key", event));
            }, (r, e) -> saved(b, "Next-stage notification route saved.", e));
        });
    }

    // ------------------------------------------------------------------ C. templates + D. test
    private void renderTemplates() {
        LinearLayout s = AdmUi.section(a, page, "C", "MODULE EMAIL TEMPLATES", "Maintain the controlled subject/body format for every QCMS workflow and digest. Generated PDFs and controlled record documents may be attached automatically.");
        LinearLayout form = Ui.vbox(a);
        LinearLayout test = Ui.vbox(a);
        AdmUi.choice(a, s, "Template", AdmMail.keys(), AdmMail.keyLabels(true), templateEvent, v -> { templateEvent = v; templateForm(form, test); });
        s.addView(form);
        LinearLayout d = AdmUi.section(a, page, "D", "TEST EMAIL TEMPLATE", "Select the template above, enter any manual To / CC recipient and send a controlled test. QCMS shows the confirmation popup before releasing the email.");
        d.addView(test);
        templateForm(form, test);
    }

    private void templateForm(LinearLayout form, LinearLayout test) {
        form.removeAllViews();
        String event = templateEvent;
        JSONObject t = templates.containsKey(event) ? templates.get(event) : new JSONObject();
        form.addView(Ui.text(a, "Available placeholders: " + AdmMail.TEMPLATE_VARIABLES, 11, Ui.MUTED, false), Ui.matchWrap(a, 6));
        String subj0 = AdmPy.j(t, "subject_template");
        String body0 = AdmPy.j(t, "body_template");
        String name0 = AdmPy.j(t, "template_name");
        List<String[]> catalog = AdmMail.fieldCatalog(event);
        List<String> fields = new ArrayList<>(), fieldLabels = new ArrayList<>();
        for (String[] f : catalog) { fields.add(f[0]); fieldLabels.add(f[1] + " · " + f[2] + " · {{" + f[0] + "}}"); }
        final String[] field = {fields.get(0)};
        AdmUi.choice(a, form, "Add Database Field to Template", fields, fieldLabels, field[0], v -> field[0] = v);
        LinearLayout btns = Ui.hbox(a);
        form.addView(btns, Ui.matchWrap(a, 6));
        form.addView(Ui.text(a, "The field picker is limited to database fields/context related to the selected QCMS section. Unknown or empty values render as '-'.", 11, Ui.MUTED, false), Ui.matchWrap(a, 4));
        EditText subject = AdmUi.field(a, form, "Subject Template", subj0.isEmpty() ? "QCMS · " + AdmMail.label(event) + " · {{document_no}}" : subj0, "Subject Template");
        EditText name = AdmUi.field(a, form, "Template Name", name0.isEmpty() ? AdmMail.label(event) : name0, "Template Name");
        EditText body = AdmUi.field(a, form, "Email Body Template",
            body0.isEmpty() ? "Dear {{department}},\n\nQCMS action is pending for {{document_no}}.\nNext Stage: {{next_stage}}\n\nRegards,\nQCMS" : body0, "Email Body Template");
        body.setSingleLine(false);
        body.setMinLines(8);
        Button toSubject = Ui.outline(a, "+ Field to Subject", Ui.TEAL);
        Button toBody = Ui.outline(a, "+ Field to Body", Ui.TEAL);
        btns.addView(toSubject, Ui.weight(1));
        btns.addView(toBody, Ui.weight(1));
        toSubject.setOnClickListener(v -> subject.setText(AdmMail.appendPlaceholder(AdmUi.text(subject), field[0], false)));
        toBody.setOnClickListener(v -> body.setText(AdmMail.appendPlaceholder(AdmUi.text(body), field[0], true)));
        Switch pdf = AdmUi.toggle(a, form, "Attach generated QCMS PDF", AdmPy.bool(t, "include_generated_pdf", true));
        Switch docs = AdmUi.toggle(a, form, "Attach controlled documents", AdmPy.bool(t, "include_record_attachments", true));
        Switch supplier = AdmUi.toggle(a, form, "Allow Supplier / Vendor copy", AdmPy.bool(t, "include_supplier", false));
        Switch enabled = AdmUi.toggle(a, form, "Template Enabled", AdmPy.bool(t, "enabled", true));
        AdmUi.primary(a, form, "Save Email Template", v -> {
            Button b = (Button) v;
            AdmUi.enable(b, false);
            Api.async(() -> {
                JSONObject p = new JSONObject();
                p.put("template_key", event);
                String mod = AdmMail.module(event);
                p.put("module_key", mod.isEmpty() ? "QCMS" : mod);
                String nm = AdmUi.text(name).trim();
                p.put("template_name", nm.isEmpty() ? AdmMail.label(event) : nm);
                p.put("subject_template", AdmUi.text(subject).trim());
                p.put("body_template", AdmUi.text(body).trim());
                p.put("include_generated_pdf", pdf.isChecked());
                p.put("include_record_attachments", docs.isChecked());
                p.put("include_supplier", supplier.isChecked());
                p.put("enabled", enabled.isChecked());
                return AdmDb.upsertBy(api, "qcms_email_templates", p, AdmDb.tenantKey(api, "template_key", event));
            }, (r, e) -> saved(b, "Email template saved.", e));
        });
        renderTest(test, event);
    }

    /** notification_ui.template_test_sender. */
    private void renderTest(LinearLayout box, String event) {
        box.removeAllViews();
        box.addView(AdmUi.note(a, "Testing template: " + AdmMail.label(event) + " · " + AdmMail.module(event), "teal"), Ui.matchWrap(a, 6));
        box.addView(Ui.text(a, "Test this template with a manual recipient", 12.5f, Ui.TEXT, true), Ui.matchWrap(a, 8));
        EditText to = AdmUi.field(a, box, "Manual Test Recipient", api.email, "name@company.com");
        EditText cc = AdmUi.field(a, box, "Manual Test CC", "", "Separate several with ; or ,");
        TextView msg = Ui.text(a, "", 12, Ui.TEAL_DARK, false);
        AdmUi.outline(a, box, "Review & Send Template Test", v -> {
            String toEmail = AdmUi.text(to).trim();
            if (toEmail.isEmpty() || !toEmail.contains("@")) { a.toast("Enter a valid test recipient."); return; }
            List<String> ccEmails = AdmPy.splitEmails(AdmUi.text(cc));
            JSONObject sample = AdmMail.sampleContext();
            Api.async(() -> AdmMail.previewSubject(api, event, sample), (subject, err) -> {
                String subj = err != null || subject == null || subject.isEmpty() ? AdmMail.defaultSubject(event) : subject;
                a.confirm("Confirm Template Test Email", "To: " + toEmail + "\nCC: " + (ccEmails.isEmpty() ? "-" : String.join("; ", ccEmails)) + "\nSubject: " + subj,
                    "Send", () -> Api.async(() -> {
                        JSONObject row = AdmMail.enqueue(api, event, null, null, toEmail, "QCMS Template Test", ccEmails, event, sample);
                        if (row == null) return "Template test could not be queued.";
                        List<String> ids = new ArrayList<>();
                        ids.add(AdmPy.j(row, "id"));
                        JSONObject result = AdmMail.dispatch(api, ids);
                        if (!AdmPy.j(result, "error").isEmpty()) return "Template test queued; delivery returned: " + AdmPy.j(result, "error");
                        return "Template test email queued / delivery requested successfully.";
                    }, (text, e2) -> {
                        String t = e2 != null ? Api.message(e2) : text;
                        msg.setText(t);
                        a.toast(t);
                    }));
            });
        });
        box.addView(msg, Ui.matchWrap(a, 6));
    }
}
