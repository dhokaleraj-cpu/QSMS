package com.fourstar.qcmsapp;

import android.graphics.Bitmap;
import android.view.Gravity;
import android.view.View;
import android.widget.ImageView;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

/**
 * R38 Employee Master view (app_pages/employee_master._employee_details_panel + core/employee_service.employee_details):
 * photo (upload / replace), reporting to, escalation chain (manager's manager … up to 4 levels), direct reports,
 * approval-route levels (qcms_module_approval_routes) and overdue escalations (qcms_notification_schedules) where the
 * employee is responsible, and the departments involved.
 */
final class EmpDetailsScreen extends Screen {
    static final int ESCALATION_MAX_LEVELS = 4;

    private final String employeeId;
    private String name = "";

    EmpDetailsScreen(MainActivity a, String employeeId) { super(a); this.employeeId = employeeId; }

    @Override public String title() { return name.isEmpty() ? "Employee details" : name; }
    @Override public String subtitle() { return "Photo · reporting line · approval routes"; }
    @Override public int tab() { return Catalog.MASTERS; }

    static String s(JSONObject o, String k) { return o == null || o.isNull(k) ? "" : o.optString(k, "").trim(); }

    /** employee_service.employee_name */
    static String employeeName(JSONObject r) {
        String n = (s(r, "first_name") + " " + s(r, "last_name")).trim();
        return n.isEmpty() ? s(r, "employee_code") : n;
    }

    /** employee_service.escalation_chain: reports_to → their reports_to … (cycle-safe), each with "level" 1..n. */
    static List<JSONObject> escalationChain(Map<String, JSONObject> byId, String employeeId, int maxLevels) {
        List<JSONObject> chain = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        seen.add(employeeId);
        JSONObject current = byId.get(employeeId);
        while (current != null && chain.size() < maxLevels) {
            String manager = s(current, "reports_to_employee_id");
            if (manager.isEmpty() || seen.contains(manager) || !byId.containsKey(manager)) break;
            seen.add(manager);
            current = byId.get(manager);
            try { chain.add(new JSONObject(current.toString()).put("level", chain.size() + 1)); } catch (Exception e) { break; }
        }
        return chain;
    }

    /** employee_service.direct_reports */
    static List<JSONObject> directReports(List<JSONObject> rows, String employeeId) {
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject r : rows) if (employeeId.equals(s(r, "reports_to_employee_id")) && !employeeId.equals(s(r, "id"))) out.add(r);
        out.sort(Comparator.comparing(EmpDetailsScreen::employeeName));
        return out;
    }

    /** employee_service.approver_routes: active route levels where this employee is the approver. */
    static List<JSONObject> approverRoutes(JSONArray routes, String employeeId) {
        List<JSONObject> out = new ArrayList<>();
        for (int i = 0; routes != null && i < routes.length(); i++) {
            JSONObject r = routes.optJSONObject(i);
            String st = s(r, "status").isEmpty() ? "ACTIVE" : s(r, "status").toUpperCase(java.util.Locale.ROOT);
            if (employeeId.equals(s(r, "employee_id")) && !st.equals("INACTIVE") && !st.equals("ARCHIVED")) out.add(r);
        }
        out.sort(Comparator.comparing((JSONObject r) -> s(r, "module_key")).thenComparing(r -> s(r, "department")).thenComparingInt(r -> r.optInt("level_no", 0)));
        return out;
    }

    /** employee_service.schedule_escalations: schedules where this employee is the overdue Level-1 / Level-2 escalation. */
    static List<String[]> scheduleEscalations(JSONArray schedules, String employeeId) {
        List<String[]> out = new ArrayList<>();
        for (int i = 0; schedules != null && i < schedules.length(); i++) {
            JSONObject sch = schedules.optJSONObject(i);
            for (int level = 1; level <= 2; level++) {
                if (!employeeId.isEmpty() && employeeId.equals(s(sch, "overdue_level" + level + "_employee_id"))) {
                    String label = s(sch, "schedule_label").isEmpty() ? s(sch, "schedule_key") : s(sch, "schedule_label");
                    out.add(new String[]{label, s(sch, "module_key"), s(sch, "recipient_department"), "Level " + level,
                        s(sch, "overdue_level" + level + "_after_hours"), sch.optBoolean("enabled", true) ? "YES" : "NO"});
                }
            }
        }
        out.sort(Comparator.comparing((String[] r) -> r[0]).thenComparing(r -> r[3]));
        return out;
    }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONArray emps = new JSONArray(api.get("employees?select=id,employee_code,first_name,last_name,email,mobile_number,department,designation,plant,status,"
                + "reports_to_employee_id,is_top_level_authority,photo_storage_path&order=first_name.asc&limit=5000", false).body);
            JSONArray routes = new JSONArray();
            try { routes = new JSONArray(api.get("qcms_module_approval_routes?select=*&order=module_key.asc&limit=3000", false).body); } catch (Exception ignored) { }
            JSONArray schedules = new JSONArray();
            try { schedules = new JSONArray(api.get("qcms_notification_schedules?select=*&order=schedule_label.asc&limit=500", false).body); } catch (Exception ignored) { }
            List<JSONObject> rows = new ArrayList<>();
            Map<String, JSONObject> byId = new HashMap<>();
            for (int i = 0; i < emps.length(); i++) { JSONObject r = emps.getJSONObject(i); rows.add(r); byId.put(s(r, "id"), r); }
            JSONObject me = byId.get(employeeId);
            if (me == null) throw new Api.ApiException(404, "Employee not found or not visible for your role.");
            List<JSONObject> chain = escalationChain(byId, employeeId, ESCALATION_MAX_LEVELS);
            Bitmap photo = LicService.image(api, s(me, "photo_storage_path"), 400);
            Bitmap bossPhoto = chain.isEmpty() ? null : LicService.image(api, s(chain.get(0), "photo_storage_path"), 160);
            return new Object[]{rows, me, chain, approverRoutes(routes, employeeId), scheduleEscalations(schedules, employeeId), photo, bossPhoto};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { add(error(err, this::reload)); return; }
            @SuppressWarnings("unchecked") List<JSONObject> rows = (List<JSONObject>) res[0];
            @SuppressWarnings("unchecked") List<JSONObject> chain = (List<JSONObject>) res[2];
            @SuppressWarnings("unchecked") List<JSONObject> mine = (List<JSONObject>) res[3];
            @SuppressWarnings("unchecked") List<String[]> esc = (List<String[]>) res[4];
            render(rows, (JSONObject) res[1], chain, mine, esc, (Bitmap) res[5], (Bitmap) res[6]);
        });
        return scroll;
    }

    private ImageView image(Bitmap b, int sizeDp) {
        ImageView iv = new ImageView(a);
        iv.setScaleType(ImageView.ScaleType.CENTER_CROP);
        iv.setBackground(Ui.round(Ui.BG, Ui.LINE, 1, sizeDp / 2f, a));
        iv.setClipToOutline(true);
        if (b != null) iv.setImageBitmap(b); else iv.setImageResource(R.drawable.stawn_qcms_logo);
        return iv;
    }

    private void render(List<JSONObject> rows, JSONObject me, List<JSONObject> chain, List<JSONObject> mine, List<String[]> esc, Bitmap photo, Bitmap bossPhoto) {
        name = employeeName(me);
        a.rebuildTitle(this);

        // ---- photo + identity
        LinearLayout head = Ui.card(a);
        LinearLayout row = Ui.hbox(a);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.addView(image(photo, 96), new LinearLayout.LayoutParams(dp(96), dp(96)));
        LinearLayout id = Ui.vbox(a);
        id.setPadding(dp(12), 0, 0, 0);
        id.addView(Ui.text(a, name, 17, Ui.TEXT, true));
        id.addView(Ui.text(a, s(me, "employee_code") + " · " + s(me, "designation"), 12.5f, Ui.MUTED, false));
        id.addView(Ui.text(a, s(me, "department") + (s(me, "plant").isEmpty() ? "" : " · Plant " + s(me, "plant")), 12.5f, Ui.MUTED, false));
        if (!s(me, "email").isEmpty()) id.addView(Ui.text(a, s(me, "email") + (s(me, "mobile_number").isEmpty() ? "" : " · " + s(me, "mobile_number")), 12, Ui.TEXT, false));
        if (!s(me, "status").isEmpty()) id.addView(Ui.chip(a, s(me, "status"), Ui.tone(s(me, "status"))));
        row.addView(id, Ui.weight(1));
        head.addView(row);
        if (photo == null) head.addView(Ui.text(a, "No photo yet - add it with the button below.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 6));
        android.widget.Button up = Ui.outline(a, photo == null ? "Upload employee photo" : "Replace employee photo", Ui.TEAL);
        up.setOnClickListener(v -> MstPeople.uploadPhoto(a, me, this::reload));
        head.addView(up, Ui.matchWrap(a, 8));
        add(head, 0);

        // ---- reporting to + escalation
        add(Ui.label(a, "Reporting to"), 12);
        LinearLayout rep = Ui.card(a);
        if (chain.isEmpty()) {
            rep.addView(Ui.text(a, me.optBoolean("is_top_level_authority", false) ? "Top-level authority - no Reports-To." : "No Reports-To set in Employee Master.", 12.5f, Ui.MUTED, false));
        } else {
            JSONObject boss = chain.get(0);
            LinearLayout br = Ui.hbox(a);
            br.setGravity(Gravity.CENTER_VERTICAL);
            br.addView(image(bossPhoto, 56), new LinearLayout.LayoutParams(dp(56), dp(56)));
            LinearLayout bt = Ui.vbox(a);
            bt.setPadding(dp(10), 0, 0, 0);
            bt.addView(Ui.text(a, employeeName(boss), 14.5f, Ui.TEXT, true));
            bt.addView(Ui.text(a, s(boss, "employee_code") + " · " + s(boss, "designation") + " · " + s(boss, "department"), 12, Ui.MUTED, false));
            if (!s(boss, "email").isEmpty()) bt.addView(Ui.text(a, s(boss, "email"), 12, Ui.TEXT, false));
            br.addView(bt, Ui.weight(1));
            br.setOnClickListener(v -> a.push(new EmpDetailsScreen(a, s(boss, "id"))));
            rep.addView(br);
        }
        add(rep, 2);
        add(Ui.label(a, "Escalation (manager's manager …)"), 12);
        if (chain.size() <= 1) add(Ui.empty(a, chain.isEmpty() ? "No escalation line." : "No level above the direct manager."), 2);
        else {
            List<List<String>> data = new ArrayList<>();
            for (JSONObject c : chain) data.add(AdmUi.listOf("Level " + c.optInt("level"), employeeName(c), s(c, "employee_code"), s(c, "designation"), s(c, "department"), s(c, "email")));
            add(new DataGrid(a, "Escalation", AdmUi.listOf("Level", "Name", "Code", "Designation", "Department", "Email"), data, 240, i -> a.push(new EmpDetailsScreen(a, s(chain.get(i), "id")))), 2);
        }

        // ---- direct reports
        List<JSONObject> reports = directReports(rows, employeeId);
        add(Ui.label(a, "Direct reports (" + reports.size() + ")"), 12);
        if (reports.isEmpty()) add(Ui.empty(a, "Nobody reports to this employee."), 2);
        else {
            List<List<String>> data = new ArrayList<>();
            for (JSONObject r : reports) data.add(AdmUi.listOf(employeeName(r), s(r, "employee_code"), s(r, "designation"), s(r, "department"), s(r, "status")));
            add(new DataGrid(a, "Direct reports", AdmUi.listOf("Name", "Code", "Designation", "Department", "Status"), data, 260, i -> a.push(new EmpDetailsScreen(a, s(reports.get(i), "id")))), 2);
        }

        // ---- approval routes
        add(Ui.label(a, "Approver in approval routes (" + mine.size() + ")"), 12);
        if (mine.isEmpty()) add(Ui.empty(a, "Not an approver in any approval route."), 2);
        else {
            List<List<String>> data = new ArrayList<>();
            for (JSONObject r : mine) data.add(AdmUi.listOf(s(r, "module_key"), s(r, "department"), s(r, "level_no"), s(r, "level_name"),
                r.optBoolean("required", false) ? "YES" : "NO", s(r, "overdue_after_hours")));
            add(new DataGrid(a, "Approval routes", AdmUi.listOf("Module", "Department", "Level", "Level Name", "Required", "Overdue after (h)"), data, 260, null), 2);
        }

        // ---- notification schedule escalations
        add(Ui.label(a, "Overdue escalation in notification schedules (" + esc.size() + ")"), 12);
        if (esc.isEmpty()) add(Ui.empty(a, "Not an overdue escalation contact."), 2);
        else {
            List<List<String>> data = new ArrayList<>();
            for (String[] e : esc) data.add(AdmUi.listOf(e));
            add(new DataGrid(a, "Schedule escalations", AdmUi.listOf("Schedule", "Module", "Department", "Escalation", "After (h)", "Enabled"), data, 240, null), 2);
        }

        // ---- departments
        TreeSet<String> deps = new TreeSet<>();
        if (!s(me, "department").isEmpty()) deps.add(s(me, "department"));
        for (JSONObject r : mine) if (!s(r, "department").isEmpty()) deps.add(s(r, "department"));
        add(Ui.label(a, "Departments"), 12);
        add(Ui.text(a, deps.isEmpty() ? "-" : String.join(", ", deps), 13, Ui.TEXT, false), 2);
    }
}
