package com.fourstar.qcmsapp;

import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Users & Access → "Role & Department Defaults" tab (role / department module defaults and module approval routes). */
final class AdmUserDefaults {
    private AdmUserDefaults() { }

    private static String roleScope = AdmPerm.ROLES[0];
    private static String deptScope = "";

    static void render(AdmUsersScreen s, LinearLayout body) {
        MainActivity a = s.a;
        LinearLayout ra = AdmUi.section(a, body, "A", "ROLE → MODULE DEFAULTS", "Assign permissions once to a Role. Users inherit these rights unless an explicit User override exists.");
        LinearLayout roleGrid = Ui.vbox(a);
        AdmUi.choice(a, ra, "Role", AdmUsersScreen.roles(), roleScope, v -> { roleScope = v; loadDefaults(s, roleGrid, "role_module_defaults", "role", v, "Role defaults"); });
        ra.addView(roleGrid, Ui.matchWrap(a, 6));
        loadDefaults(s, roleGrid, "role_module_defaults", "role", roleScope, "Role defaults");

        LinearLayout rb = AdmUi.section(a, body, "B", "DEPARTMENT → MODULE DEFAULTS", "Department permissions apply when no explicit User or Role permission row exists.");
        LinearLayout depGrid = Ui.vbox(a);
        if (!s.departments.contains(deptScope)) deptScope = s.departments.isEmpty() ? "" : s.departments.get(0);
        AdmUi.choice(a, rb, "Department", s.departments, deptScope, v -> { deptScope = v; loadDefaults(s, depGrid, "department_module_defaults", "department", v, "Department defaults"); });
        rb.addView(depGrid, Ui.matchWrap(a, 6));
        loadDefaults(s, depGrid, "department_module_defaults", "department", deptScope, "Department defaults");

        renderRoutes(s, body);
    }

    /** _permission_editor_rows(table, eq={scope: value, status: ACTIVE}) without a selected profile + Save. */
    private static void loadDefaults(AdmUsersScreen s, LinearLayout box, String table, String scopeCol, String scope, String what) {
        MainActivity a = s.a;
        Api api = s.api;
        box.removeAllViews();
        if (scope == null || scope.isEmpty()) { box.addView(Ui.empty(a, "Select a value first.")); return; }
        box.addView(Ui.text(a, "Loading…", 12, Ui.MUTED, false));
        Api.async(() -> AdmDb.select(api, table, AdmDb.eq(scopeCol, scope, "status", "ACTIVE"), null, 200), (rows, err) -> {
            box.removeAllViews();
            if (err != null) { box.addView(AdmUi.note(a, Api.message(err), "red")); return; }
            Map<String, JSONObject> existing = new HashMap<>();
            for (JSONObject r : AdmDb.list(rows)) existing.put(AdmPy.j(r, "module_key"), r);
            List<AdmGrid.Row> list = new ArrayList<>();
            for (String[] m : AdmPerm.MODULES) {
                JSONObject configured = existing.get(m[0]);
                JSONObject values = configured == null ? new JSONObject() : configured;
                boolean[] v = new boolean[AdmGrid.MODULE_KEYS.length];
                for (int i = 0; i < v.length; i++) v[i] = AdmPy.bool(values, AdmGrid.MODULE_KEYS[i], i == 0);
                list.add(new AdmGrid.Row(m[0], "", m[1], configured != null ? "EXPLICIT" : "INHERIT", configured, configured != null, v));
            }
            LinearLayout grid = Ui.vbox(a);
            box.addView(grid);
            AdmGrid.render(a, grid, list, AdmGrid.MODULE_COLS, null, true);
            AdmUi.primary(a, box, "Save " + what, v -> s.saveGrid((Button) v, () -> {
                for (AdmGrid.Row r : list) {
                    if (r.override) {
                        JSONObject p = new JSONObject().put(scopeCol, scope).put("module_key", r.module);
                        for (int i = 0; i < AdmGrid.MODULE_KEYS.length; i++) p.put(AdmGrid.MODULE_KEYS[i], r.values[i]);
                        p.put("status", "ACTIVE");
                        AdmDb.upsertBy(api, table, p, AdmDb.eq(scopeCol, scope, "module_key", r.module));
                    } else if (r.configured != null && !AdmPy.j(r.configured, "id").isEmpty()) {
                        api.delete(table, AdmPy.j(r.configured, "id"));
                    }
                }
            }, "role".equals(scopeCol) ? "Role module defaults saved." : "Department module defaults saved."));
        });
    }

    // ------------------------------------------------------------------ C. Module approval routes
    private static void renderRoutes(AdmUsersScreen s, LinearLayout body) {
        MainActivity a = s.a;
        Api api = s.api;
        LinearLayout c = AdmUi.section(a, body, "C", "MODULE APPROVAL ROUTES", "Configured employee route first → Reports-To manager → controlled Approve-permission fallback.");
        List<String> mods = new ArrayList<>(), modLabels = new ArrayList<>();
        for (String[] m : AdmPerm.MODULES) { mods.add(m[0]); modLabels.add(m[1]); }
        final String[] module = {"SUPPLY_CHAIN"};
        AdmUi.choice(a, c, "Approval Module", mods, modLabels, module[0], v -> module[0] = v);
        List<String> deps = new ArrayList<>();
        deps.add("ALL DEPARTMENTS");
        deps.addAll(s.departments);
        final String[] dept = {"ALL DEPARTMENTS"};
        AdmUi.choice(a, c, "Department Scope", deps, dept[0], v -> dept[0] = v);
        final int[] level = {1};
        EditText name = Ui.input(a, "Level Name", false);
        EditText hours = Ui.input(a, "Overdue after hours", false);
        hours.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);
        AdmUi.choice(a, c, "Approval Level", AdmUi.listOf("1", "2", "3"), "1", v -> {
            level[0] = Integer.parseInt(v);
            name.setText(level[0] == 1 ? "Manager Approval" : "Approval Level " + level[0]);
            hours.setText(String.valueOf(level[0] == 1 ? 24 : level[0] == 2 ? 48 : 72));
        });
        List<String> empIds = s.employeeIds(true);
        final String[] approver = {""};
        Button[] save = new Button[1];
        AdmUi.choice(a, c, "Approver Employee", empIds, s.employeeLabels(empIds, "— Select approver —"), "", v -> {
            approver[0] = v;
            if (save[0] != null) AdmUi.enable(save[0], !v.isEmpty());
        });
        c.addView(Ui.label(a, "Level Name"));
        name.setText("Manager Approval");
        c.addView(name, Ui.matchWrap(a, 0));
        final String[] status = {"ACTIVE"};
        AdmUi.choice(a, c, "Route Status", AdmUi.listOf("ACTIVE", "INACTIVE"), "ACTIVE", v -> status[0] = v);
        CheckBox required = AdmUi.check(a, "Required approval route", true);
        c.addView(required, Ui.matchWrap(a, 6));
        CheckBox notify = AdmUi.check(a, "Send automatic overdue approval reminder", true);
        c.addView(notify, Ui.matchWrap(a, 2));
        c.addView(Ui.label(a, "Overdue after hours"));
        hours.setText("24");
        c.addView(hours, Ui.matchWrap(a, 0));
        c.addView(Ui.text(a, "Set a responsible employee for each level. The server checks hourly and sends at most one reminder per PO, level and email each day.", 11, Ui.MUTED, false), Ui.matchWrap(a, 6));
        save[0] = AdmUi.primary(a, c, "Save Approval Route", v -> {
            if (approver[0].isEmpty()) { a.toast("Select the approver employee."); return; }
            int h;
            try { h = Integer.parseInt(AdmUi.text(hours).trim()); } catch (NumberFormatException e) { h = -1; }
            if (h < 1 || h > 8760) { a.toast("Overdue after hours must be between 1 and 8760."); return; }
            final int overdue = h;
            final int lvl = level[0];
            Object department = "ALL DEPARTMENTS".equals(dept[0]) ? JSONObject.NULL : dept[0];
            String levelName = AdmUi.text(name).trim();
            s.saveGrid((Button) v, () -> {
                JSONObject p = new JSONObject();
                p.put("module_key", module[0]);
                p.put("department", department);
                p.put("level_no", lvl);
                p.put("level_name", levelName.isEmpty() ? "Approval Level " + lvl : levelName);
                p.put("employee_id", approver[0]);
                p.put("required", required.isChecked());
                p.put("status", status[0]);
                p.put("notify_overdue", notify.isChecked());
                p.put("overdue_after_hours", overdue);
                AdmDb.upsertBy(api, "qcms_module_approval_routes", p, AdmDb.eq("module_key", module[0], "department", department, "level_no", lvl));
            }, "Approval route saved successfully.");
        });
        AdmUi.enable(save[0], false);

        LinearLayout list = Ui.vbox(a);
        c.addView(list, Ui.matchWrap(a, 10));
        list.addView(Ui.text(a, "Loading routes…", 12, Ui.MUTED, false));
        Api.async(() -> AdmDb.select(api, "qcms_module_approval_routes", null, "module_key.asc", 500), (rows, err) -> {
            list.removeAllViews();
            if (err != null) { list.addView(AdmUi.note(a, Api.message(err), "red")); return; }
            List<JSONObject> routes = AdmDb.list(rows);
            if (routes.isEmpty()) {
                list.addView(AdmUi.note(a, "No configured approval routes. QCMS will use Reports-To manager and then controlled approval-permission fallback.", "teal"));
                return;
            }
            List<List<String>> grid = new ArrayList<>();
            List<String> ids = new ArrayList<>(), labels = new ArrayList<>();
            for (JSONObject r : routes) {
                String mod = AdmPerm.moduleLabel(AdmPy.j(r, "module_key"));
                String dep = AdmPy.j(r, "department").isEmpty() ? "ALL DEPARTMENTS" : AdmPy.j(r, "department");
                String eid = AdmPy.j(r, "employee_id");
                String appr = s.emp.containsKey(eid) ? s.emp.get(eid) : (eid.isEmpty() ? "-" : eid);
                grid.add(AdmUi.listOf(mod, dep, AdmPy.j(r, "level_no"), AdmPy.j(r, "level_name"), appr,
                    AdmPy.truthy(r, "required") ? "Yes" : "No", AdmPy.j(r, "overdue_after_hours"),
                    AdmPy.bool(r, "notify_overdue", true) ? "Yes" : "No", AdmPy.j(r, "status")));
                if (!AdmPy.j(r, "id").isEmpty()) {
                    ids.add(AdmPy.j(r, "id"));
                    labels.add(mod + " · " + dep + " · Level " + AdmPy.j(r, "level_no") + " · " + appr);
                }
            }
            list.addView(new DataGrid(a, "Approval routes", AdmUi.listOf("Module", "Department", "Level", "Level Name", "Approver", "Required", "Overdue Hours", "Overdue Reminder", "Status"), grid, 300, null));
            if (ids.isEmpty()) return;
            final String[] sel = {ids.get(0)};
            AdmUi.choice(a, list, "Selected Approval Route", ids, labels, sel[0], v -> sel[0] = v);
            AdmUi.outline(a, list, "Deactivate Selected Route", v -> s.saveGrid((Button) v,
                () -> api.update("qcms_module_approval_routes", sel[0], new JSONObject().put("status", "INACTIVE")), "Approval route deactivated."));
        });
    }
}
