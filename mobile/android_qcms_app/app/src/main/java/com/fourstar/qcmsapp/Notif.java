package com.fourstar.qcmsapp;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * R35 notifications: in-app inbox data, Android system notifications (JobScheduler, no Firebase SDK)
 * and opening the record / module / website page a notification or search result points to.
 * Live RPCs: qcms_my_notifications, qcms_unread_notification_count, qcms_mark_notifications_read,
 * qcms_set_my_whatsapp.
 */
final class Notif {
    private Notif() { }

    static final String CHANNEL = "qcms_alerts";
    static final String CHANNEL_APPROVAL = "qcms_alerts_approval";
    static final int JOB_PERIODIC = 3401;
    static final int JOB_NOW = 3402;
    static final long PERIOD_MS = 15L * 60L * 1000L;
    static final String EXTRA_OPEN = "qcms_open";
    static final String OPEN_NOTIFICATIONS = "notifications";
    private static final String PREFS = "qcms_notif";
    private static final int MAX_POST_PER_RUN = 5;

    static final String[] CATEGORIES = {"APPROVAL", "TASK", "UPDATE", "INFO", "ALERT"};

    // ------------------------------------------------------------------ look
    static String icon(String category) {
        switch (category == null ? "" : category.toUpperCase(Locale.ROOT)) {
            case "APPROVAL": return "✔";
            case "TASK": return "☑";
            case "UPDATE": return "↻";
            case "ALERT": return "⚠";
            default: return "ℹ";
        }
    }

    static String tone(String category) {
        switch (category == null ? "" : category.toUpperCase(Locale.ROOT)) {
            case "APPROVAL": return "amber";
            case "TASK": return "teal";
            case "ALERT": return "red";
            case "UPDATE": return "green";
            default: return "grey";
        }
    }

    // ------------------------------------------------------------------ data (background thread)
    static JSONArray list(Api api, boolean unreadOnly, int limit) throws Exception {
        JSONObject args = new JSONObject();
        args.put("p_limit", limit);
        args.put("p_unread_only", unreadOnly);
        return api.rpcRows("qcms_my_notifications", args);
    }

    static int unreadCount(Api api) throws Exception {
        Object v = api.rpcValue("qcms_unread_notification_count", new JSONObject());
        if (v == null) return 0;
        try { return (int) Math.round(Double.parseDouble(String.valueOf(v).trim())); } catch (NumberFormatException e) { return 0; }
    }

    /** ids == null marks all of the user's notifications read. */
    static int markRead(Api api, List<String> ids) throws Exception {
        JSONObject args = new JSONObject();
        if (ids == null) args.put("p_ids", JSONObject.NULL);
        else {
            JSONArray arr = new JSONArray();
            for (String id : ids) arr.put(id);
            args.put("p_ids", arr);
        }
        Object v = api.rpcValue("qcms_mark_notifications_read", args);
        try { return v == null ? 0 : Integer.parseInt(String.valueOf(v).trim()); } catch (NumberFormatException e) { return 0; }
    }

    static JSONObject setWhatsapp(Api api, boolean optIn, String mobile) throws Exception {
        JSONObject args = new JSONObject();
        args.put("p_opt_in", optIn);
        args.put("p_mobile_number", mobile == null || mobile.trim().isEmpty() ? JSONObject.NULL : mobile.trim());
        return api.rpcObject("qcms_set_my_whatsapp", args);
    }

    static SharedPreferences prefs(Context c) { return c.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE); }

    // ------------------------------------------------------------------ scheduling
    /** Periodic 15-minute check (kept across reboots) - called on app start / resume and after boot. */
    static void schedule(Context context) {
        try {
            Context c = context.getApplicationContext();
            JobScheduler js = (JobScheduler) c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
            if (js == null) return;
            if (js.getPendingJob(JOB_PERIODIC) == null) {
                JobInfo job = new JobInfo.Builder(JOB_PERIODIC, new ComponentName(c, NotifJob.class))
                    .setPeriodic(PERIOD_MS)
                    .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                    .setPersisted(true)
                    .build();
                js.schedule(job);
            }
        } catch (Exception ignored) { }
    }

    /** One check as soon as the network allows (app start / resume). */
    static void checkSoon(Context context) {
        try {
            Context c = context.getApplicationContext();
            JobScheduler js = (JobScheduler) c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
            if (js == null) return;
            JobInfo job = new JobInfo.Builder(JOB_NOW, new ComponentName(c, NotifJob.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setOverrideDeadline(30_000L)
                .build();
            js.schedule(job);
        } catch (Exception ignored) { }
    }

    static void cancelAll(Context context) {
        try {
            JobScheduler js = (JobScheduler) context.getApplicationContext().getSystemService(Context.JOB_SCHEDULER_SERVICE);
            if (js != null) { js.cancel(JOB_PERIODIC); js.cancel(JOB_NOW); }
            NotificationManager nm = (NotificationManager) context.getApplicationContext().getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm != null) nm.cancelAll();
        } catch (Exception ignored) { }
        prefs(context).edit().clear().apply();
    }

    // ------------------------------------------------------------------ system notifications
    static void ensureChannels(Context c) {
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;
        NotificationChannel normal = new NotificationChannel(CHANNEL, "QCMS alerts", NotificationManager.IMPORTANCE_DEFAULT);
        normal.setDescription("Tasks, updates and information from STAWN QCMS");
        nm.createNotificationChannel(normal);
        NotificationChannel high = new NotificationChannel(CHANNEL_APPROVAL, "QCMS approvals", NotificationManager.IMPORTANCE_HIGH);
        high.setDescription("Approval requests and decisions from STAWN QCMS");
        nm.createNotificationChannel(high);
    }

    static boolean mayPost(Context c) {
        if (Build.VERSION.SDK_INT >= 33
            && c.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) return false;
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        return nm != null && nm.areNotificationsEnabled();
    }

    /**
     * NotifJob body (background thread): fetch unread notifications with the stored session and show
     * the ones not shown before. Does nothing when nobody is signed in. Returns how many were shown.
     */
    static int check(Context context) {
        Context c = context.getApplicationContext();
        Api api = Api.get(c);
        if (!api.ensureSession()) return 0;
        JSONArray rows;
        try { rows = list(api, true, 50); } catch (Exception e) { return 0; }
        SharedPreferences p = prefs(c);
        String lastAt = p.getString("last_shown_at", "");
        String lastId = p.getString("last_shown_id", "");
        Set<String> shown = new LinkedHashSet<>();
        for (String s : p.getString("shown_ids", "").split(",")) if (!s.isEmpty()) shown.add(s);
        boolean firstRun = lastAt.isEmpty();

        List<JSONObject> fresh = new ArrayList<>();
        String newest = lastAt, newestId = lastId;
        for (int i = 0; i < rows.length(); i++) {
            JSONObject r = rows.optJSONObject(i);
            if (r == null) continue;
            String id = r.optString("id", "");
            String at = r.optString("created_at", "");
            if (id.isEmpty() || shown.contains(id)) continue;
            if (!lastAt.isEmpty() && at.compareTo(lastAt) < 0) continue;
            fresh.add(r);
            if (at.compareTo(newest) > 0) { newest = at; newestId = id; }
        }
        // newest first; on the very first run only the newest few, so an old backlog does not flood the phone
        fresh.sort((x, y) -> y.optString("created_at", "").compareTo(x.optString("created_at", "")));
        int limit = firstRun ? 3 : MAX_POST_PER_RUN;
        int posted = 0;
        boolean allowed = mayPost(c);
        if (allowed) ensureChannels(c);
        for (JSONObject r : fresh) {
            shown.add(r.optString("id"));
            if (!allowed || posted >= limit) continue;
            post(c, r);
            posted++;
        }
        if (allowed && fresh.size() > posted && posted > 0) postSummary(c, fresh.size());
        List<String> keep = new ArrayList<>(shown);
        if (keep.size() > 300) keep = keep.subList(keep.size() - 300, keep.size());
        p.edit().putString("last_shown_at", newest).putString("last_shown_id", newestId)
            .putString("shown_ids", String.join(",", keep)).putInt("unread", rows.length()).apply();
        return posted;
    }

    private static PendingIntent openIntent(Context c, String notificationId, int request) {
        Intent i = new Intent(c, MainActivity.class);
        i.putExtra(EXTRA_OPEN, OPEN_NOTIFICATIONS);
        i.putExtra("notification_id", notificationId == null ? "" : notificationId);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        return PendingIntent.getActivity(c, request, i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private static void post(Context c, JSONObject r) {
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;
        String id = r.optString("id");
        String category = r.optString("category", "INFO").toUpperCase(Locale.ROOT);
        boolean approval = "APPROVAL".equals(category);
        String title = r.optString("title", "STAWN QCMS");
        String body = r.isNull("body") ? "" : r.optString("body", "");
        int code = id.hashCode() & 0x7fffffff;
        Notification.Builder b = new Notification.Builder(c, approval ? CHANNEL_APPROVAL : CHANNEL)
            .setSmallIcon(R.drawable.ic_launcher_monochrome)
            .setContentTitle(icon(category) + " " + title)
            .setContentText(body)
            .setStyle(new Notification.BigTextStyle().bigText(body))
            .setSubText(GenUtil.title(category.toLowerCase(Locale.ROOT)))
            .setAutoCancel(true)
            .setGroup("qcms")
            .setCategory(approval ? Notification.CATEGORY_REMINDER : Notification.CATEGORY_MESSAGE)
            .setContentIntent(openIntent(c, id, code));
        nm.notify(code, b.build());
    }

    private static void postSummary(Context c, int total) {
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;
        Notification.Builder b = new Notification.Builder(c, CHANNEL)
            .setSmallIcon(R.drawable.ic_launcher_monochrome)
            .setContentTitle("STAWN QCMS")
            .setContentText(total + " new notification(s)")
            .setAutoCancel(true)
            .setGroup("qcms")
            .setGroupSummary(true)
            .setContentIntent(openIntent(c, "", 3400));
        nm.notify(3400, b.build());
    }

    // ------------------------------------------------------------------ open the target
    /** Website route -> app module key (opened natively when the app has the module). */
    static final Map<String, String> ROUTE_MODULES = new HashMap<>();
    static {
        String[][] m = {
            {"supply-po-approval", "po_approval"}, {"supply-purchase-orders", "purchase_orders"}, {"supply-po-order-list", "purchase_orders"},
            {"supply-po-edit", "purchase_orders"}, {"supply-po-pdf", "purchase_orders"}, {"supply-customer-orders", "customer_orders"},
            {"supply-rm-procurement", "rm_po_stages"}, {"supply-rm-receipt", "rm_receipts"}, {"supply-rm-dispatch", "rm_dispatches"},
            {"supply-forging", "forging_orders"}, {"supply-downstream", "downstream_events"}, {"supply-opening-stock", "opening_stock"},
            {"supply-traceability", "traceability"}, {"traceability-report", "traceability"},
            {"rmtc-entry", "rmtc"}, {"rmtc-records", "rmtc"}, {"rmtc-report", "rmtc"}, {"rmtc-approval", "rmtc"}, {"rmtc-part", "rmtc"},
            {"rmtc-approved-worksheet", "accepted_rmtc_parts"},
            {"inward-entry", "inward"}, {"inward-records", "inward"}, {"inward-report", "inward"}, {"heat-ledger", "heat_ledger"},
            {"dimensional-entry", "dimensional_reports"}, {"dimensional-records", "dimensional_reports"}, {"dimensional-report", "dimensional_reports"},
            {"metlab-entry", "metlab_reports"}, {"metlab-records", "metlab_reports"}, {"metlab-report", "metlab_reports"},
            {"bend-test-entry", "bend_tests"}, {"bend-test-records", "bend_tests"}, {"bend-test-report", "bend_tests"},
            {"inspection-layout-entry", "inspection_layouts"}, {"inspection-layout-records", "inspection_layouts"}, {"inspection-layout-report", "inspection_layouts"},
            {"bend-layout-entry", "inspection_layouts"},
            {"osp-material-out", "osp_material_out"}, {"osp-inward", "osp_receipts"}, {"osp-records", "osp_register"}, {"osp-home", "osp_register"},
            {"customer-complaint", "customer_complaints"}, {"customer-complaint-register", "customer_complaints"},
            {"supplier-complaint", "supplier_complaints"}, {"supplier-complaint-register", "supplier_complaints"},
            {"complaint-analysis", "customer_complaints"}, {"complaint-records", "customer_complaints"}, {"complaints-report", "customer_complaints"},
            {"complaints-home", "customer_complaints"},
            {"calibration-validation", "calibration_records"}, {"standard-room-inspection", "standard_room"},
            {"part-entry", "parts"}, {"part-records", "parts"}, {"grade-entry", "material_grades"}, {"grade-records", "material_grades"},
            {"process-entry", "processes"}, {"process-records", "processes"}, {"employee-entry", "employees"}, {"employee-records", "employees"},
            {"standards-entry", "customer_standards"}, {"standards-records", "customer_standards"}, {"standards-report", "customer_standards"},
            {"company-branch-entry", "company_branches"}, {"company-branch-records", "company_branches"},
            {"npd-status", "npd_orders"}, {"npd-report", "npd_orders"}, {"npd-process-flow", "npd_flows"}, {"apqp", "apqp_projects"}, {"apqp-report", "apqp_projects"},
            {"qc-tools", "qc_calculations"}, {"qc-calculation-records", "qc_calculations"}, {"qc-report", "qc_calculations"},
            {"global-search", "global_search"}, {"kpi-dashboards", "kpi_dashboards"}, {"report-builder", "report_builder"},
            {"master-lists", "master_lists"}, {"records-center", "records_centre"}, {"reports-home", "reports_centre"},
            {"my-account", "my_account"}, {"about", "about"}, {"user-access", "user_access"}, {"system-settings", "system_settings"},
            {"email-send", "email_send"}, {"email-sent", "email_sent"}, {"email-groups", "email_groups"}, {"email-settings", "email_server"},
            {"print-designer", "print_designer"}, {"master-import", "master_import"}};
        for (String[] r : m) ROUTE_MODULES.put(r[0], r[1]);
    }

    static String cleanRoute(String route) {
        String r = route == null ? "" : route.trim();
        if (r.startsWith("/")) r = r.substring(1);
        int q = r.indexOf('?');
        String base = q >= 0 ? r.substring(0, q) : r;
        return base.toLowerCase(Locale.ROOT);
    }

    /** Native module for a table (+ route hint for tables shown by several modules, e.g. lab_tests). */
    static Module moduleForTable(String table, String route) {
        if (table == null || table.isEmpty()) return null;
        List<Module> candidates = new ArrayList<>();
        for (Module m : Catalog.all()) if (m.table.equals(table) && !m.idField.isEmpty()) candidates.add(m);
        if (candidates.isEmpty()) return null;
        String key = ROUTE_MODULES.get(cleanRoute(route));
        if (key != null) for (Module m : candidates) if (m.key.equals(key)) return m;
        return candidates.get(0);
    }

    /**
     * Opens what a notification / search result / pending task points to: the record natively when the
     * app has a module for its table, else the app module for the website route, else the website page.
     */
    static void open(MainActivity a, String table, String id, String route, String title) {
        String r = cleanRoute(route);
        boolean hasId = id != null && !id.isEmpty() && !"null".equals(id);
        if (r.equals("notifications")) { a.push(new NotifScreen(a)); return; }
        if (r.equals("licence-company") || r.equals("stawn-developer")) { a.openWeb(title == null || title.isEmpty() ? "Licence & Company" : title, route); return; }
        if (hasId && ("supply_purchase_orders".equals(table) || (table == null || table.isEmpty()) && r.startsWith("supply-po"))) {
            a.push(new PoDetailScreen(a, id));
            return;
        }
        Module m = moduleForTable(table, route);
        if (m != null && hasId) { a.push(new RecordScreen(a, m, id)); return; }
        String key = ROUTE_MODULES.get(r);
        Module byRoute = key == null ? null : Catalog.get(key);
        if (byRoute != null) {
            if (hasId && (table == null || table.isEmpty()) && !byRoute.table.isEmpty() && !byRoute.idField.isEmpty() && byRoute.custom == null) {
                a.push(new RecordScreen(a, byRoute, id));
            } else {
                a.openModule(key);
            }
            return;
        }
        if (m != null) { a.openModule(m.key); return; }
        if (!r.isEmpty()) { a.openWeb(title == null || title.isEmpty() ? "QCMS" : title, route.startsWith("/") ? route.substring(1) : route); return; }
        a.toast("Nothing to open for this item.");
    }
}
