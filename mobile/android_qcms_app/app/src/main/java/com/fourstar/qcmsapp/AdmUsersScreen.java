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
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Native port of app_pages/user_access.py (Users & Access). User create / update / password reset go through the
 * same qsms-user-admin edge function calls as the website; permission overrides, role / department defaults and
 * approval routes are written to the same tables with Repository.upsert_by / delete semantics.
 */
public final class AdmUsersScreen extends Screen {
    static final String[] TABS = {"Create User", "User Permissions", "Role & Department Defaults", "Audit & Activity", "My Password"};
    private static int lastTab = 1;
    private static String selectedUid = "";
    /** R35 / R39: employee picked in "Create login for an Employee without login" (prefills the Create User form). */
    private static String prefillEmployee = "";

    private LinearLayout tabsHolder, body;
    List<JSONObject> employees = new ArrayList<>();
    final Map<String, String> emp = new LinkedHashMap<>();
    final Map<String, JSONObject> empById = new HashMap<>();
    List<String> departments = new ArrayList<>();
    private List<JSONObject> users = new ArrayList<>();
    private String usersError = "";

    public AdmUsersScreen(MainActivity a) { super(a); }

    @Override public String title() { return "Users & Access"; }
    @Override public String subtitle() { return "Role + Department access, user overrides, section visibility, approvals and audit"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        if (!api.isAdmin()) {
            add(AdmUi.adminOnly(a, AdmDb.ADMIN_ONLY), 4);
            return scroll;
        }
        tabsHolder = Ui.vbox(a);
        add(tabsHolder, 0);
        body = Ui.vbox(a);
        add(body, 4);
        body.addView(loading());
        Api.async(() -> {
            List<JSONObject> e = AdmDb.employees(api);
            List<JSONObject> u = new ArrayList<>();
            String err = "";
            try {
                JSONObject payload = AdmDb.userAdmin(api, new JSONObject().put("action", "list_users"));
                JSONArray list = payload.optJSONArray("users");
                for (int i = 0; list != null && i < list.length(); i++) {
                    JSONObject r = list.optJSONObject(i);
                    if (r != null) u.add(normalizeUser(r));
                }
            } catch (Exception ex) {
                err = "Could not load QCMS users: " + Api.message(ex);
            }
            return new Object[]{e, u, err};
        }, (res, err) -> {
            body.removeAllViews();
            if (err != null) { body.addView(error(err, this::reload)); return; }
            @SuppressWarnings("unchecked") List<JSONObject> e = (List<JSONObject>) res[0];
            @SuppressWarnings("unchecked") List<JSONObject> u = (List<JSONObject>) res[1];
            employees = e; users = u; usersError = (String) res[2];
            emp.clear(); empById.clear();
            for (JSONObject r : employees) { String id = AdmPy.j(r, "id"); emp.put(id, AdmDb.employeeLabel(r)); empById.put(id, r); }
            departments = AdmDb.accessDepartments(employees);
            if (!users.isEmpty()) {
                boolean found = false;
                for (JSONObject x : users) if (AdmPy.j(x, "id").equals(selectedUid)) found = true;
                if (!found) selectedUid = AdmPy.j(users.get(0), "id");
            }
            renderTabs();
        });
        return scroll;
    }

    private void renderTabs() {
        tabsHolder.removeAllViews();
        tabsHolder.addView(AdmUi.tabs(a, TABS, lastTab, i -> { lastTab = i; renderTabs(); }));
        body.removeAllViews();
        switch (lastTab) {
            case 0: renderCreate(); break;
            case 1: renderAccess(); break;
            case 2: AdmUserDefaults.render(this, body); break;
            case 3: AdmUserAudit.render(this, body); break;
            default: renderPassword();
        }
    }

    /** _normalize_user: accepts flat and nested qsms-user-admin payloads. */
    static JSONObject normalizeUser(JSONObject row) {
        JSONObject profile = row.optJSONObject("profile");
        JSONObject employee = row.optJSONObject("employee");
        JSONObject o = new JSONObject();
        try {
            o.put("id", firstOf(AdmPy.j(row, "id"), AdmPy.j(profile, "id")));
            o.put("email", firstOf(AdmPy.j(row, "email"), AdmPy.j(profile, "email")));
            o.put("full_name", firstOf(AdmPy.j(profile, "full_name"), AdmPy.j(row, "full_name")));
            o.put("role", firstOf(AdmPy.j(profile, "role"), AdmPy.j(row, "role"), "VIEWER").toUpperCase(java.util.Locale.ROOT));
            o.put("status", firstOf(AdmPy.j(profile, "status"), AdmPy.j(row, "status"), "ACTIVE").toUpperCase(java.util.Locale.ROOT));
            o.put("employee_id", firstOf(AdmPy.j(employee, "id"), AdmPy.j(row, "employee_id")));
            o.put("employee_code", firstOf(AdmPy.j(employee, "employee_code"), AdmPy.j(row, "employee_code")));
            o.put("department", firstOf(AdmPy.j(employee, "department"), AdmPy.j(row, "department")));
            o.put("designation", firstOf(AdmPy.j(employee, "designation"), AdmPy.j(row, "designation")));
            o.put("last_sign_in_at", AdmPy.j(row, "last_sign_in_at"));
            o.put("created_at", firstOf(AdmPy.j(row, "created_at"), AdmPy.j(profile, "created_at")));
        } catch (Exception ignored) { }
        return o;
    }

    private static String firstOf(String... v) {
        for (String s : v) if (s != null && !s.isEmpty()) return s;
        return "";
    }

    List<String> employeeIds(boolean withBlank) {
        List<String> ids = new ArrayList<>();
        if (withBlank) ids.add("");
        ids.addAll(emp.keySet());
        return ids;
    }

    List<String> employeeLabels(List<String> ids, String blank) {
        List<String> out = new ArrayList<>();
        for (String id : ids) out.add(id.isEmpty() ? blank : (emp.containsKey(id) ? emp.get(id) : blank));
        return out;
    }

    static List<String> roles() { return AdmUi.listOf(AdmPerm.ROLES); }
    static List<String> statuses() { return AdmUi.listOf(AdmPerm.ACCESS_STATUSES); }

    // ------------------------------------------------------------------ A. Create user
    private void renderCreate() {
        LinearLayout s = AdmUi.section(a, body, "A", "CREATE USER", "Create the login and optionally link one Employee Master record. Employee email is never overwritten by login administration.");
        // R35 (user_access.py): one-tap prefill for an active employee that has no QCMS login yet
        Map<String, String> without = EmpLinks.withoutLogin(employees);
        if (!without.containsKey(prefillEmployee)) prefillEmployee = "";
        if (!without.isEmpty()) {
            List<String> wIds = new ArrayList<>();
            wIds.add("");
            wIds.addAll(without.keySet());
            List<String> wLabels = new ArrayList<>();
            for (String id : wIds) wLabels.add(id.isEmpty() ? "— Select employee —" : without.get(id));
            AdmUi.choice(a, s, "Create login for an Employee without login (prefills the form)", wIds, wLabels, prefillEmployee, v -> { prefillEmployee = v; renderTabs(); });
        }
        JSONObject pre = empById.get(prefillEmployee);
        String preName = pre == null ? "" : (AdmPy.j(pre, "first_name") + " " + AdmPy.j(pre, "last_name")).trim();
        EditText full = AdmUi.field(a, s, "Full Name", preName, "Full Name");
        EditText email = AdmUi.field(a, s, "Login / Company Email", pre == null ? "" : AdmPy.j(pre, "email"), "name@company.com");
        email.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        final String[] role = {AdmPerm.ROLES[0]};
        AdmUi.choice(a, s, "QCMS Role", roles(), role[0], v -> role[0] = v);
        final String[] employee = {pre == null ? "" : prefillEmployee};
        List<String> ids = employeeIds(true);
        TextView dept = Ui.text(a, "", 11.5f, Ui.MUTED, false);
        AdmUi.choice(a, s, "Employee Link", ids, employeeLabels(ids, "— Not linked —"), employee[0], v -> {
            employee[0] = v;
            dept.setText(deptCaption(v));
        });
        final String[] status = {AdmPerm.ACCESS_STATUSES[0]};
        AdmUi.choice(a, s, "Access Status", statuses(), status[0], v -> status[0] = v);
        EditText password = AdmUi.password(a, s, "Temporary Password", "At least 10 characters");
        dept.setText(deptCaption(employee[0]));
        dept.setPadding(0, dp(6), 0, 0);
        s.addView(dept);
        CheckBox mismatchOk = AdmUi.check(a, "Link even if the Employee Master email differs from the login email", false);
        s.addView(mismatchOk, Ui.matchWrap(a, 6));
        AdmUi.primary(a, s, "Create User", v -> {
            String problem = EmpLinks.linkProblem(empById.get(employee[0]), AdmUi.text(email), "");
            if (!problem.isEmpty() && !mismatchOk.isChecked()) {
                a.toast(problem + " Tick 'Link even if … differs' to confirm, or choose the correct employee.");
                return;
            }
            Button b = (Button) v;
            AdmUi.enable(b, false);
            Api.async(() -> {
                JSONObject p = new JSONObject();
                p.put("action", "create_user");
                p.put("email", AdmUi.text(email));
                p.put("password", AdmUi.text(password));
                p.put("full_name", AdmUi.text(full));
                p.put("role", role[0]);
                p.put("status", status[0]);
                p.put("employee_id", employee[0].isEmpty() ? JSONObject.NULL : employee[0]);
                return AdmDb.userAdmin(api, p);
            }, (res, err) -> {
                AdmUi.enable(b, true);
                if (err != null) { a.toast(Api.message(err)); return; }
                String msg = AdmPy.j(res, "message");
                a.toast(msg.isEmpty() ? "User created successfully." : msg);
                prefillEmployee = "";
                a.rebuild();
            });
        });
    }

    private String deptCaption(String employeeId) {
        JSONObject e = empById.get(employeeId);
        String d = e == null ? "" : AdmPy.j(e, "department");
        return "Department: " + (d.isEmpty() ? "Link an Employee Master record to derive Department access." : d);
    }

    // ------------------------------------------------------------------ User permissions (A identity, B modules, C sections, D password)
    private JSONObject selectedUser() {
        for (JSONObject u : users) if (AdmPy.j(u, "id").equals(selectedUid)) return u;
        return users.isEmpty() ? null : users.get(0);
    }

    private void renderAccess() {
        if (!usersError.isEmpty()) body.addView(AdmUi.note(a, usersError, "red"), Ui.matchWrap(a, 4));
        if (users.isEmpty()) { body.addView(AdmUi.note(a, "No users are available.", "teal"), Ui.matchWrap(a, 6)); return; }
        JSONObject user = selectedUser();
        String uid = AdmPy.j(user, "id");
        selectedUid = uid;

        LinearLayout s = AdmUi.section(a, body, "A", "USER · ROLE · DEPARTMENT · EMPLOYEE LINK",
            "Role and Department are displayed together with the Employee Master link. Changing access never changes Employee Master email.");
        List<String> headers = AdmUi.listOf("Email", "Name", "Role", "Department", "Employee", "Status", "Last Sign In");
        List<List<String>> rows = new ArrayList<>();
        List<String> ids = new ArrayList<>(), labels = new ArrayList<>();
        for (JSONObject u : users) {
            String dep = AdmPy.j(u, "department"), code = AdmPy.j(u, "employee_code");
            rows.add(AdmUi.listOf(AdmPy.j(u, "email"), AdmPy.j(u, "full_name"), AdmPy.j(u, "role"), dep.isEmpty() ? "—" : dep,
                code.isEmpty() ? "—" : code, AdmPy.j(u, "status"), AdmUi.ts(AdmPy.j(u, "last_sign_in_at"))));
            ids.add(AdmPy.j(u, "id"));
            labels.add(AdmPy.j(u, "email") + " · " + AdmPy.j(u, "role"));
        }
        s.addView(new DataGrid(a, "QCMS users", headers, rows, 300, i -> { selectedUid = ids.get(i); renderTabs(); }), Ui.matchWrap(a, 8));
        AdmUi.choice(a, s, "Selected User", ids, labels, uid, v -> { selectedUid = v; renderTabs(); });

        String currentEmployee = AdmPy.j(user, "employee_id");
        String curRole = roles().contains(AdmPy.j(user, "role")) ? AdmPy.j(user, "role") : "VIEWER";
        String curStatus = statuses().contains(AdmPy.j(user, "status")) ? AdmPy.j(user, "status") : "ACTIVE";
        final String[] role = {curRole}, status = {curStatus};
        final String[] employee = {emp.containsKey(currentEmployee) ? currentEmployee : ""};
        final String[] department = {""};
        AdmUi.choice(a, s, "Role", roles(), role[0], v -> role[0] = v);
        AdmUi.choice(a, s, "Access Status", statuses(), status[0], v -> status[0] = v);
        List<String> empIds = employeeIds(true);
        LinearLayout deptBox = Ui.vbox(a);
        LinearLayout unlinkBox = Ui.vbox(a);
        final CheckBox[] unlink = {null};
        Runnable[] refreshDept = new Runnable[1];
        AdmUi.choice(a, s, "Employee", empIds, employeeLabels(empIds, "— Not linked —"), employee[0], v -> { employee[0] = v; refreshDept[0].run(); });
        s.addView(deptBox);
        s.addView(unlinkBox);
        refreshDept[0] = () -> {
            deptBox.removeAllViews();
            JSONObject e = empById.get(employee[0]);
            String linked = e != null && !AdmPy.j(e, "department").isEmpty() ? AdmPy.j(e, "department") : AdmPy.j(user, "department");
            List<String> opts = new ArrayList<>();
            opts.add("");
            for (String d : departments) if (!d.isEmpty()) opts.add(d);
            department[0] = opts.contains(linked) ? linked : "";
            List<String> optLabels = new ArrayList<>();
            for (String d : opts) optLabels.add(d.isEmpty() ? "— Link employee first —" : d);
            TextView dv = AdmUi.choice(a, deptBox, "Department", opts, optLabels, department[0], v -> department[0] = v);
            AdmUi.enableView(dv, !employee[0].isEmpty());
            if ("ADMIN".equals(AdmPy.j(user, "role")) && e != null && AdmPy.truthy(e, "is_top_level_authority"))
                deptBox.addView(AdmUi.note(a, "Top-level Super Admin: Reports-To is not required and remains blank in Employee Master.", "teal"), Ui.matchWrap(a, 6));
            unlinkBox.removeAllViews();
            unlink[0] = null;
            if (!currentEmployee.isEmpty() && employee[0].isEmpty()) {
                CheckBox c = AdmUi.check(a, "Confirm unlinking this QCMS User from the currently linked Employee Master record", false);
                unlinkBox.addView(c, Ui.matchWrap(a, 6));
                unlinkBox.addView(AdmUi.note(a, "The existing Employee link will be preserved unless this confirmation is selected.", "amber"), Ui.matchWrap(a, 4));
                unlink[0] = c;
            }
        };
        refreshDept[0].run();
        CheckBox mismatchOk = AdmUi.check(a, "I confirm this Employee belongs to this login (when the link check warns)", false);
        s.addView(mismatchOk, Ui.matchWrap(a, 6));
        AdmUi.primary(a, s, "Update User / Employee Link", v -> {
            String mismatch = EmpLinks.linkProblem(empById.get(employee[0]), AdmPy.j(user, "email"), uid);
            if (!mismatch.isEmpty() && !mismatchOk.isChecked()) { a.toast(mismatch + " Tick the confirmation to link anyway."); return; }
            Button b = (Button) v;
            AdmUi.enable(b, false);
            Api.async(() -> {
                JSONObject p = new JSONObject();
                p.put("action", "update_user");
                p.put("user_id", uid);
                p.put("role", role[0]);
                p.put("status", status[0]);
                p.put("employee_id", employee[0].isEmpty() ? JSONObject.NULL : employee[0]);
                p.put("allow_unlink_employee", unlink[0] != null && unlink[0].isChecked());
                p.put("department", employee[0].isEmpty() ? JSONObject.NULL : department[0]);
                return AdmDb.userAdmin(api, p);
            }, (res, err) -> {
                AdmUi.enable(b, true);
                if (err != null) { a.toast(Api.message(err)); return; }
                a.toast("User role, status, Department and Employee link updated successfully.");
                a.rebuild();
            });
        });
        // R35 (user_access.py): Employee ↔ Login link check
        List<List<String>> checks = EmpLinks.linkCheckRows(employees, users);
        if (checks.isEmpty()) s.addView(AdmUi.note(a, "Every Employee ↔ Login link matches by email.", "green"), Ui.matchWrap(a, 10));
        else {
            s.addView(AdmUi.note(a, checks.size() + " link(s) need attention. QCMS does not change them automatically – correct each one with 'Update User / Employee Link' above.", "amber"), Ui.matchWrap(a, 10));
            s.addView(new DataGrid(a, "Employee ↔ Login link check", AdmUi.listOf("Employee", "Employee Email", "Linked Login", "Issue"), checks, 260, null), Ui.matchWrap(a, 6));
        }

        JSONObject effective = new JSONObject();
        try {
            effective.put("id", uid).put("role", AdmPy.j(user, "role")).put("email", AdmPy.j(user, "email")).put("department", AdmPy.j(user, "department"));
        } catch (Exception ignored) { }
        LinearLayout b = AdmUi.section(a, body, "B", "EXPLICIT USER MODULE PERMISSIONS",
            "An enabled Override is authoritative. If Override is off, the user inherits Role → Department → legacy defaults. This same effective permission is enforced by the database/RLS and the UI.");
        LinearLayout c = AdmUi.section(a, body, "C", "SECTION VIEW / CREATE / EDIT",
            "Default: all sections remain visible according to module View permission. Create an Override only when you need to hide or restrict a section such as Part Master Price History.");
        b.addView(loading());
        c.addView(loading());
        renderReset(uid);
        Api.async(() -> {
            JSONArray modRows = AdmDb.select(api, "user_module_permissions", AdmDb.eq("profile_id", uid), null, 200);
            JSONArray secRows = AdmDb.select(api, "user_section_permissions", AdmDb.eq("profile_id", uid), null, 1000);
            Map<String, AdmPerm.Effective> eff = AdmPerm.effectiveAll(api, effective);
            return new Object[]{modRows, secRows, eff};
        }, (res, err) -> {
            if (!uid.equals(selectedUid) || lastTab != 1) return;
            b.removeViewAt(b.getChildCount() - 1);
            c.removeViewAt(c.getChildCount() - 1);
            if (err != null) { b.addView(AdmUi.note(a, Api.message(err), "red")); return; }
            @SuppressWarnings("unchecked") Map<String, AdmPerm.Effective> eff = (Map<String, AdmPerm.Effective>) res[2];
            renderModuleGrid(b, uid, (JSONArray) res[0], eff);
            renderSectionGrid(c, uid, (JSONArray) res[1], eff);
        });
    }

    /** _permission_editor_rows for user_module_permissions (selected profile given). */
    private void renderModuleGrid(LinearLayout box, String uid, JSONArray existingRows, Map<String, AdmPerm.Effective> eff) {
        Map<String, JSONObject> existing = new HashMap<>();
        for (JSONObject r : AdmDb.list(existingRows)) existing.put(AdmPy.j(r, "module_key"), r);
        List<AdmGrid.Row> rows = new ArrayList<>();
        for (String[] m : AdmPerm.MODULES) {
            JSONObject configured = existing.get(m[0]);
            JSONObject values;
            String source;
            if (configured != null) { values = configured; source = "EXPLICIT"; }
            else { AdmPerm.Effective e = eff.get(m[0]); values = e == null ? new JSONObject() : e.values; source = e == null ? "" : e.source; }
            boolean[] v = new boolean[AdmGrid.MODULE_KEYS.length];
            for (int i = 0; i < v.length; i++) v[i] = AdmPy.bool(values, AdmGrid.MODULE_KEYS[i], false);
            rows.add(new AdmGrid.Row(m[0], "", m[1], source, configured, configured != null, v));
        }
        LinearLayout grid = Ui.vbox(a);
        box.addView(Ui.text(a, "Ticking a right switches its Override on. Rows with Override off are removed when you save.", 11, Ui.MUTED, false), Ui.matchWrap(a, 6));
        box.addView(grid, Ui.matchWrap(a, 4));
        AdmGrid.render(a, grid, rows, AdmGrid.MODULE_COLS, null, true);
        AdmUi.primary(a, box, "Save User Permission Overrides", v -> saveGrid((Button) v, () -> {
            for (AdmGrid.Row r : rows) {
                if (r.override) {
                    JSONObject p = new JSONObject().put("profile_id", uid).put("module_key", r.module);
                    for (int i = 0; i < AdmGrid.MODULE_KEYS.length; i++) p.put(AdmGrid.MODULE_KEYS[i], r.values[i]);
                    AdmDb.upsertBy(api, "user_module_permissions", p, AdmDb.eq("profile_id", uid, "module_key", r.module));
                } else if (r.configured != null && !AdmPy.j(r.configured, "id").isEmpty()) {
                    api.delete("user_module_permissions", AdmPy.j(r.configured, "id"));
                }
            }
        }, "User permission overrides saved. Effective module authorization is synchronized with database workflows."));
        AdmUi.outline(a, box, "Clear All User Overrides", v -> a.confirm("Clear all user overrides?", "Role / Department defaults will apply to this user.", "Clear", () ->
            saveGrid((Button) v, () -> {
                for (JSONObject r : existing.values()) if (!AdmPy.j(r, "id").isEmpty()) api.delete("user_module_permissions", AdmPy.j(r, "id"));
            }, "User overrides cleared. Role / Department defaults now apply.")));
    }

    private void renderSectionGrid(LinearLayout box, String uid, JSONArray existingRows, Map<String, AdmPerm.Effective> eff) {
        Map<String, JSONObject> existing = new HashMap<>();
        for (JSONObject r : AdmDb.list(existingRows)) existing.put(AdmPy.j(r, "module_key") + "|" + AdmPy.j(r, "section_key"), r);
        List<AdmGrid.Row> rows = new ArrayList<>();
        for (String[] s : AdmPerm.SECTIONS) {
            JSONObject configured = existing.get(s[0] + "|" + s[1]);
            boolean[] v = new boolean[3];
            if (configured != null) {
                for (int i = 0; i < 3; i++) v[i] = AdmPy.truthy(configured, AdmGrid.SECTION_KEYS[i]);
            } else {
                AdmPerm.Effective e = eff.get(s[0]);
                for (int i = 0; i < 3; i++) v[i] = e != null && e.has(AdmGrid.SECTION_KEYS[i]);
            }
            rows.add(new AdmGrid.Row(s[0], s[1], s[2], "", configured, configured != null, v));
        }
        box.addView(Ui.text(a, "Section rights are available for all " + AdmPerm.MODULES.length + " QCMS modules. Unticked Override rows inherit the effective module permission.", 11, Ui.MUTED, false), Ui.matchWrap(a, 6));
        List<String> mods = new ArrayList<>(), modLabels = new ArrayList<>();
        mods.add(""); modLabels.add("All modules (" + rows.size() + " sections)");
        for (String[] m : AdmPerm.MODULES) { mods.add(m[0]); modLabels.add(m[1]); }
        LinearLayout grid = Ui.vbox(a);
        final String[] filter = {AdmPerm.MODULES[0][0]};
        AdmUi.choice(a, box, "Show sections of", mods, modLabels, filter[0], v -> { filter[0] = v; AdmGrid.render(a, grid, rows, AdmGrid.SECTION_COLS, v, true); });
        box.addView(grid, Ui.matchWrap(a, 6));
        AdmGrid.render(a, grid, rows, AdmGrid.SECTION_COLS, filter[0], true);
        AdmUi.primary(a, box, "Save Section Overrides", v -> saveGrid((Button) v, () -> {
            for (AdmGrid.Row r : rows) {
                if (r.override) {
                    JSONObject natural = AdmDb.eq("profile_id", uid, "module_key", r.module, "section_key", r.section);
                    JSONObject p = new JSONObject(natural.toString());
                    for (int i = 0; i < 3; i++) p.put(AdmGrid.SECTION_KEYS[i], r.values[i]);
                    AdmDb.upsertBy(api, "user_section_permissions", p, natural);
                } else if (r.configured != null && !AdmPy.j(r.configured, "id").isEmpty()) {
                    api.delete("user_section_permissions", AdmPy.j(r.configured, "id"));
                }
            }
        }, "Section overrides saved. Sections without overrides remain visible by default."));
        AdmUi.outline(a, box, "Reset Sections to Default Visible", v -> a.confirm("Reset all section overrides?", "Module-level default visibility will apply.", "Reset", () ->
            saveGrid((Button) v, () -> {
                for (JSONObject r : existing.values()) if (!AdmPy.j(r, "id").isEmpty()) api.delete("user_section_permissions", AdmPy.j(r, "id"));
            }, "All section overrides removed. Module-level default visibility applies.")));
    }

    interface Work { void run() throws Exception; }

    /** Run a sequence of writes like the website (stops at the first error) and reload. */
    void saveGrid(Button b, Work work, String success) {
        AdmUi.enable(b, false);
        Api.async(() -> { work.run(); return true; }, (ok, err) -> {
            AdmUi.enable(b, true);
            if (err != null) { a.toast(Api.message(err) + " (rows before the error were saved)"); a.rebuild(); return; }
            a.toast(success);
            a.rebuild();
        });
    }

    private void renderReset(String uid) {
        LinearLayout d = AdmUi.section(a, body, "D", "RESET SELECTED USER PASSWORD", "");
        EditText temp = AdmUi.password(a, d, "New Temporary Password", "At least 10 characters");
        AdmUi.outline(a, d, "Reset Selected User Password", v -> {
            Button b = (Button) v;
            AdmUi.enable(b, false);
            Api.async(() -> AdmDb.userAdmin(api, new JSONObject().put("action", "reset_password").put("user_id", uid).put("password", AdmUi.text(temp))),
                (res, err) -> {
                    AdmUi.enable(b, true);
                    if (err != null) { a.toast(Api.message(err)); return; }
                    temp.setText("");
                    a.toast("Temporary password updated successfully.");
                });
        });
    }

    // ------------------------------------------------------------------ My password
    private void renderPassword() {
        LinearLayout s = AdmUi.section(a, body, "A", "CHANGE MY PASSWORD", "");
        EditText p1 = AdmUi.password(a, s, "New Password", "At least 10 characters");
        EditText p2 = AdmUi.password(a, s, "Confirm New Password", "Repeat the new password");
        AdmUi.primary(a, s, "Change My Password", v -> {
            String n1 = AdmUi.text(p1), n2 = AdmUi.text(p2);
            if (n1.length() < 10) { a.toast("Use at least 10 characters."); return; }
            if (!n1.equals(n2)) { a.toast("Passwords do not match."); return; }
            Button b = (Button) v;
            AdmUi.enable(b, false);
            Api.async(() -> { changeOwnPassword(api, n1); return true; }, (ok, err) -> {
                AdmUi.enable(b, true);
                if (err != null) { a.toast(Api.message(err)); return; }
                p1.setText(""); p2.setText("");
                a.toast("Password changed successfully.");
            });
        });
    }

    /** auth.update_user({"password": p}) of the signed-in user (PUT /auth/v1/user). */
    static void changeOwnPassword(Api api, String password) throws Exception {
        api.updatePassword(password);
    }
}
