package com.fourstar.qcmsapp;

import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Switch;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.TreeSet;

/** Email Settings sections E (automatic open / overdue report schedules) and the test & notification outbox. */
final class AdmEmailAuto {
    private AdmEmailAuto() { }

    private static String scheduleId = "";

    static void renderSchedules(AdmEmailScreen s, LinearLayout page) {
        MainActivity a = s.a;
        LinearLayout box = AdmUi.section(a, page, "E", "AUTOMATIC OPEN / OVERDUE REPORT EMAILS", "Supabase Cron checks every hour. Each schedule follows its configured cadence (for example every 2 days), local hour, recipient departments and PDF/Excel export format. Supplier/vendor copies are sent only when Party Master contains an email address.");
        if (s.schedules.isEmpty()) {
            box.addView(AdmUi.note(a, "Automatic notification schedules are not available. Apply the QCMS v4.14.7 database migration.", "amber"), Ui.matchWrap(a, 6));
            return;
        }
        List<String> ids = new ArrayList<>(), labels = new ArrayList<>();
        for (JSONObject r : s.schedules) { ids.add(AdmPy.j(r, "id")); labels.add(AdmPy.j(r, "schedule_label") + " · " + AdmPy.j(r, "module_key")); }
        if (!ids.contains(scheduleId)) scheduleId = ids.get(0);
        LinearLayout form = Ui.vbox(a);
        AdmUi.choice(a, box, "Automatic Schedule", ids, labels, scheduleId, v -> { scheduleId = v; scheduleForm(s, form); });
        box.addView(form);
        scheduleForm(s, form);
        List<List<String>> rows = new ArrayList<>();
        for (JSONObject r : s.schedules) {
            JSONArray deps = r.optJSONArray("recipient_departments");
            List<String> dl = new ArrayList<>();
            for (int i = 0; deps != null && i < deps.length(); i++) if (!deps.isNull(i)) dl.add(deps.optString(i));
            String every = AdmPy.j(r, "run_every_days");
            String exp = AdmPy.j(r, "export_format");
            rows.add(AdmUi.listOf(AdmPy.j(r, "schedule_label"), AdmPy.j(r, "module_key"), AdmPy.j(r, "hour_local"), every.isEmpty() || "0".equals(every) ? "1" : every,
                AdmPy.j(r, "timezone"), AdmPy.j(r, "days_ahead"), dl.isEmpty() ? AdmPy.j(r, "recipient_department") : String.join(", ", dl),
                exp.isEmpty() ? "PDF" : exp, AdmEmailScreen.yes(AdmPy.truthy(r, "include_suppliers")), AdmEmailScreen.yes(AdmPy.truthy(r, "enabled")), AdmUi.ts(AdmPy.j(r, "last_run_at"))));
        }
        box.addView(new DataGrid(a, "Automatic schedules", AdmUi.listOf("Schedule", "Module", "Hour", "Every Days", "Time Zone", "Days Ahead", "Departments", "Export", "Supplier Copy", "Enabled", "Last Run"), rows, 300, null), Ui.matchWrap(a, 10));
    }

    /** Python int(value or default). */
    private static int intOr(JSONObject r, String key, int def) {
        Object v = r.opt(key);
        if (AdmPy.isNull(v)) return def;
        try { int i = (int) Math.round(Double.parseDouble(String.valueOf(v))); return i == 0 ? def : i; } catch (Exception e) { return def; }
    }

    private static void scheduleForm(AdmEmailScreen s, LinearLayout form) {
        MainActivity a = s.a;
        Api api = s.api;
        form.removeAllViews();
        JSONObject sc = null;
        for (JSONObject r : s.schedules) if (AdmPy.j(r, "id").equals(scheduleId)) sc = r;
        if (sc == null) return;
        final JSONObject schedule = sc;
        final String sid = scheduleId;
        Switch enabled = AdmUi.toggle(a, form, "Enabled", AdmPy.bool(schedule, "enabled", true));
        EditText hour = AdmUi.number(a, form, "Local send hour", intOr(schedule, "hour_local", 8));
        EditText every = AdmUi.number(a, form, "Run every (days)", Math.max(intOr(schedule, "run_every_days", 1), 1));
        EditText ahead = AdmUi.number(a, form, "Include due within days", intOr(schedule, "days_ahead", 7));
        Switch suppliers = AdmUi.toggle(a, form, "Send supplier/vendor copies", AdmPy.bool(schedule, "include_suppliers", false));
        String tz0 = AdmPy.j(schedule, "timezone");
        EditText tz = AdmUi.field(a, form, "Time Zone", tz0.isEmpty() ? "Asia/Kolkata" : tz0, "Asia/Kolkata");
        List<String> deptValues = new ArrayList<>();
        deptValues.add("");
        deptValues.addAll(s.departments);
        List<String> deptLabels = new ArrayList<>();
        for (String d : deptValues) deptLabels.add(d.isEmpty() ? "— None —" : d);
        String cd = AdmPy.j(schedule, "recipient_department");
        final String[] primary = {deptValues.contains(cd) ? cd : ""};
        AdmUi.choice(a, form, "Primary Department", deptValues, deptLabels, primary[0], v -> primary[0] = v);
        TreeSet<String> opts = new TreeSet<>(s.departments);
        opts.add("Marketing"); opts.add("Procurement"); opts.add("Business Development");
        List<String> multiOptions = new ArrayList<>(opts);
        List<String> selected = new ArrayList<>();
        JSONArray existing = schedule.optJSONArray("recipient_departments");
        for (int i = 0; existing != null && i < existing.length(); i++) {
            String x = existing.isNull(i) ? "" : existing.optString(i);
            if (!x.isEmpty() && multiOptions.contains(x) && !selected.contains(x)) selected.add(x);
        }
        AdmUi.multi(a, form, "Recipient Departments", multiOptions, selected, null);
        form.addView(Ui.text(a, "Every active employee in these departments receives the digest. Marketing and Procurement also match the equivalent QCMS user roles when configured.", 10.5f, Ui.MUTED, false));
        String ef = AdmPy.j(schedule, "export_format").toUpperCase(Locale.ROOT);
        final String[] export = {ef.equals("PDF") || ef.equals("XLSX") || ef.equals("BOTH") ? ef : "PDF"};
        AdmUi.choice(a, form, "Attachment Format", AdmUi.listOf("PDF", "XLSX", "BOTH"), export[0], v -> export[0] = v);
        List<String> empIds = new ArrayList<>();
        empIds.add("");
        empIds.addAll(s.employeeOptions.keySet());
        String ce = AdmPy.j(schedule, "employee_id");
        final String[] employee = {empIds.contains(ce) ? ce : ""};
        AdmUi.choice(a, form, "Specific Employee (optional)", empIds, labels(s, empIds, "— Department / record responsibility —"), employee[0], v -> employee[0] = v);
        String tk = AdmPy.j(schedule, "template_key").isEmpty() ? AdmPy.j(schedule, "event_key") : AdmPy.j(schedule, "template_key");
        final String[] template = {AdmMail.keys().contains(tk) ? tk : AdmMail.EVENTS[0][0]};
        AdmUi.choice(a, form, "Template", AdmMail.keys(), AdmMail.keyLabels(false), template[0], v -> template[0] = v);
        Switch overdue = AdmUi.toggle(a, form, "Include overdue", AdmPy.bool(schedule, "include_overdue", true));
        Switch open = AdmUi.toggle(a, form, "Include open / due-soon", AdmPy.bool(schedule, "include_open", true));
        boolean escalation = "PO_PENDING_APPROVAL".equals(AdmPy.j(schedule, "schedule_key"));
        final String[][] escEmp = {{""}, {""}};
        final EditText[] escHours = new EditText[2];
        if (escalation) {
            form.addView(Ui.text(a, "Approver reminders follow Module Approval Routes. Add responsible employees for overdue escalation below. Thresholds are evaluated in whole calendar days.", 11, Ui.MUTED, false), Ui.matchWrap(a, 8));
            for (int level = 1; level <= 2; level++) {
                final int i = level - 1;
                String cur = AdmPy.j(schedule, "overdue_level" + level + "_employee_id");
                escEmp[i][0] = empIds.contains(cur) ? cur : "";
                AdmUi.choice(a, form, "Overdue Level " + level + " Responsible Employee", empIds, labels(s, empIds, "— Not assigned —"), escEmp[i][0], v -> escEmp[i][0] = v);
                escHours[i] = AdmUi.number(a, form, "Overdue Level " + level + " after hours", Math.max(24, intOr(schedule, "overdue_level" + level + "_after_hours", level == 1 ? 24 : 48)));
            }
        }
        AdmUi.primary(a, form, "Save Automatic Email Schedule", v -> {
            Integer h = AdmUi.intIn(hour, 0, 23), ev = AdmUi.intIn(every, 1, 30), da = AdmUi.intIn(ahead, 0, 365);
            if (h == null) { a.toast("Local send hour must be between 0 and 23."); return; }
            if (ev == null) { a.toast("Run every (days) must be between 1 and 30."); return; }
            if (da == null) { a.toast("Include due within days must be between 0 and 365."); return; }
            Integer[] eh = new Integer[2];
            if (escalation) for (int i = 0; i < 2; i++) {
                eh[i] = AdmUi.intIn(escHours[i], 24, 8760);
                if (eh[i] == null) { a.toast("Overdue Level " + (i + 1) + " after hours must be between 24 and 8760."); return; }
            }
            Button b = (Button) v;
            AdmUi.enable(b, false);
            Api.async(() -> {
                JSONObject p = new JSONObject();
                p.put("enabled", enabled.isChecked());
                p.put("hour_local", h.intValue());
                p.put("run_every_days", ev.intValue());
                p.put("days_ahead", da.intValue());
                p.put("include_suppliers", suppliers.isChecked());
                String zone = AdmUi.text(tz).trim();
                p.put("timezone", zone.isEmpty() ? "Asia/Kolkata" : zone);
                p.put("recipient_department", primary[0].isEmpty() ? JSONObject.NULL : primary[0]);
                JSONArray deps = new JSONArray();
                for (String d : selected) deps.put(d);
                p.put("recipient_departments", deps);
                p.put("employee_id", employee[0].isEmpty() ? JSONObject.NULL : employee[0]);
                p.put("template_key", template[0]);
                p.put("export_format", export[0]);
                p.put("include_overdue", overdue.isChecked());
                p.put("include_open", open.isChecked());
                if (escalation) for (int i = 0; i < 2; i++) {
                    p.put("overdue_level" + (i + 1) + "_employee_id", escEmp[i][0].isEmpty() ? JSONObject.NULL : escEmp[i][0]);
                    p.put("overdue_level" + (i + 1) + "_after_hours", eh[i].intValue());
                }
                return api.update("qcms_notification_schedules", sid, p);
            }, (r, e) -> s.saved(b, "Automatic email schedule saved.", e));
        });
    }

    private static List<String> labels(AdmEmailScreen s, List<String> ids, String blank) {
        List<String> out = new ArrayList<>();
        for (String id : ids) out.add(s.employeeOptions.containsKey(id) ? s.employeeOptions.get(id) : blank);
        return out;
    }

    // ------------------------------------------------------------------ test & outbox
    static void renderOutbox(AdmEmailScreen s, LinearLayout page) {
        MainActivity a = s.a;
        Api api = s.api;
        LinearLayout box = AdmUi.section(a, page, "E", "TEST & NOTIFICATION OUTBOX", "Send a test message or retry failed/pending notifications. Business transactions are never rolled back if email delivery fails.");
        EditText to = AdmUi.field(a, box, "Test Recipient Email", api.email, "name@company.com");
        AdmUi.primary(a, box, "Send Test Email", v -> {
            Button b = (Button) v;
            AdmUi.enable(b, false);
            String recipient = AdmUi.text(to);
            Api.async(() -> {
                JSONObject row = AdmMail.enqueue(api, "EMAIL_SERVER_TEST", "QCMS · Email server test",
                    "QCMS email server test completed successfully from Email Server, Templates & Automatic Notifications.",
                    recipient, "QCMS Administrator", null, null, new JSONObject().put("test", true));
                List<String> ids = new ArrayList<>();
                if (row != null) ids.add(AdmPy.j(row, "id"));
                return AdmMail.dispatch(api, ids);
            }, (res, err) -> {
                AdmUi.enable(b, true);
                if (err != null) { a.toast(Api.message(err)); return; }
                if (!AdmPy.j(res, "error").isEmpty()) { a.toast("Test queued but delivery returned: " + AdmPy.j(res, "error")); return; }
                a.toast("Test email queued/delivery requested.");
                a.rebuild();
            });
        });
        AdmUi.outline(a, box, "Retry Pending / Failed Email", v -> {
            Button b = (Button) v;
            AdmUi.enable(b, false);
            Api.async(() -> AdmMail.retryPending(api), (res, err) -> {
                AdmUi.enable(b, true);
                if (err != null) { a.toast(Api.message(err)); return; }
                if (!AdmPy.j(res, "error").isEmpty()) { a.toast(AdmPy.j(res, "error")); return; }
                a.toast("Retry requested for " + res.optInt("processed", 0) + " notification(s).");
                a.rebuild();
            });
        });
        if (s.outbox.isEmpty()) { box.addView(AdmUi.note(a, "No notification outbox records yet.", "teal"), Ui.matchWrap(a, 8)); return; }
        List<List<String>> rows = new ArrayList<>();
        for (JSONObject r : s.outbox) {
            JSONArray cc = r.optJSONArray("cc_emails");
            List<String> ccl = new ArrayList<>();
            for (int i = 0; cc != null && i < cc.length(); i++) if (!cc.isNull(i)) ccl.add(cc.optString(i));
            JSONArray man = r.optJSONArray("attachment_manifest");
            rows.add(AdmUi.listOf(AdmUi.ts(AdmPy.j(r, "created_at")), AdmPy.j(r, "event_key"), AdmPy.j(r, "recipient_email"), String.join("; ", ccl),
                AdmPy.j(r, "subject"), String.valueOf(man == null ? 0 : man.length()), AdmEmailScreen.yes(AdmPy.bool(r, "is_automatic", false)),
                AdmPy.j(r, "status"), AdmPy.j(r, "attempts"), AdmUi.ts(AdmPy.j(r, "sent_at")), AdmPy.j(r, "last_error")));
        }
        box.addView(new DataGrid(a, "Notification outbox", AdmUi.listOf("Created", "Event", "Recipient", "CC", "Subject", "Attachments", "Automatic", "Status", "Attempts", "Sent", "Last Error"), rows, 460, null), Ui.matchWrap(a, 10));
    }
}
