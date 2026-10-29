package com.fourstar.qcmsapp;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * R35 Employee ↔ Login link checks of app_pages/user_access.py (link_problem / link_check_rows and the
 * "Create login for an Employee without login" list). Pure functions over the rows the screen already loaded.
 */
final class EmpLinks {
    private EmpLinks() { }

    private static String s(JSONObject o, String k) { return o == null || o.isNull(k) ? "" : o.optString(k, "").trim(); }

    private static String fold(String v) { return v == null ? "" : v.trim().toLowerCase(Locale.ROOT); }

    static String name(JSONObject e) {
        String n = (s(e, "first_name") + " " + s(e, "last_name")).trim();
        return n;
    }

    /** user_access.link_problem: "" when fine, else the plain warning. */
    static String linkProblem(JSONObject employee, String loginEmail, String profileId) {
        if (employee == null || employee.length() == 0) return "";
        String name = name(employee).isEmpty() ? "this employee" : name(employee);
        String empEmail = fold(s(employee, "email")), login = fold(loginEmail);
        String other = s(employee, "profile_id");
        if (!other.isEmpty() && profileId != null && !profileId.isEmpty() && !other.equals(profileId))
            return name + " is already linked to another QCMS login. Linking here moves the link.";
        if (!empEmail.isEmpty() && !login.isEmpty() && !empEmail.equals(login))
            return "Email mismatch: Employee " + name + " has email " + s(employee, "email") + ", but the login is " + loginEmail + ".";
        return "";
    }

    /** Active employees with an e-mail and no QCMS login (id -> label · email), for the Create User prefill. */
    static Map<String, String> withoutLogin(List<JSONObject> employees) {
        Map<String, String> out = new java.util.LinkedHashMap<>();
        for (JSONObject e : employees) {
            String st = s(e, "status").isEmpty() ? "ACTIVE" : s(e, "status").toUpperCase(Locale.ROOT);
            if (!s(e, "profile_id").isEmpty() || !"ACTIVE".equals(st)) continue;
            out.put(s(e, "id"), AdmDb.employeeLabel(e) + (s(e, "email").isEmpty() ? "" : " · " + s(e, "email")));
        }
        return out;
    }

    /** user_access.link_check_rows: Employee, Employee Email, Linked Login, Issue. */
    static List<List<String>> linkCheckRows(List<JSONObject> employees, List<JSONObject> users) {
        Map<String, JSONObject> byId = new HashMap<>();
        for (JSONObject u : users) if (!s(u, "id").isEmpty()) byId.put(s(u, "id"), u);
        List<List<String>> rows = new ArrayList<>();
        for (JSONObject e : employees) {
            String pid = s(e, "profile_id");
            if (!pid.isEmpty()) {
                String login = s(byId.get(pid), "email");
                if (!login.isEmpty() && !fold(s(e, "email")).equals(fold(login)))
                    rows.add(AdmUi.listOf(name(e), s(e, "email"), login, "Email differs – check the employee is linked to the right login"));
            } else if ((s(e, "status").isEmpty() || "ACTIVE".equalsIgnoreCase(s(e, "status"))) && !s(e, "email").isEmpty()) {
                rows.add(AdmUi.listOf(name(e), s(e, "email"), "—", "No QCMS login – use Create User → 'Create login for an Employee without login'"));
            }
        }
        return rows;
    }
}
