package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;

import org.json.JSONObject;

import java.lang.reflect.Method;
import java.util.Locale;

/**
 * My Account (website app_pages/my_account.py): login account information and change of the own
 * login password (current password verified first, at least 10 characters, Supabase Auth
 * PUT /auth/v1/user).
 */
final class GenAccountScreen extends Screen {
    GenAccountScreen(MainActivity a) { super(a); }

    @Override public String title() { return "My Account"; }
    @Override public String subtitle() { return "Your QCMS login and password"; }
    @Override public int tab() { return Catalog.MORE; }

    /** core.permissions.role_label */
    static String roleLabel(String role) {
        String r = (role == null || role.trim().isEmpty() ? "VIEWER" : role).trim().toUpperCase(Locale.ROOT).replace(' ', '_');
        return GenUtil.title(r.replace('_', ' '));
    }

    @Override
    public View build() {
        newPage();
        add(Ui.label(a, "A · Login account"), 0);
        LinearLayout info = Ui.card(a);
        info.addView(Ui.pair(a, "Name", api.fullName));
        info.addView(Ui.pair(a, "Email / Username", api.email));
        info.addView(Ui.pair(a, "QCMS Role", roleLabel(api.role)));
        if (!api.employeeLabel.isEmpty()) info.addView(Ui.pair(a, "Employee", api.employeeLabel));
        add(info, 2);

        add(Ui.label(a, "B · Change login password"), 14);
        add(Ui.text(a, "Available to every signed-in QCMS user. Your current password is verified before the change is accepted.", 12, Ui.MUTED, false), 0);
        LinearLayout form = Ui.card(a);
        EditText current = Ui.input(a, "Current Password", true);
        EditText next = Ui.input(a, "New Password", true);
        EditText confirm = Ui.input(a, "Confirm New Password", true);
        form.addView(current, Ui.matchWrap(a, 0));
        form.addView(next, Ui.matchWrap(a, 8));
        form.addView(confirm, Ui.matchWrap(a, 8));
        form.addView(Ui.text(a, "Use at least 10 characters. The new password applies to your QCMS login immediately.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 6));
        Button change = Ui.primary(a, "Change My Login Password");
        form.addView(change, Ui.matchWrap(a, 10));
        add(form, 4);
        change.setOnClickListener(v -> {
            String cur = current.getText().toString(), pw = next.getText().toString(), pw2 = confirm.getText().toString();
            String problem = null;
            if (pw.length() < 10) problem = "Use a new password with at least 10 characters.";
            else if (!pw.equals(pw2)) problem = "New Password and Confirm New Password do not match.";
            else if (cur.isEmpty()) problem = "Enter your current password.";
            if (problem != null) { alert("Password not changed", problem); return; }
            change.setEnabled(false);
            change.setText("Changing…");
            Api.async(() -> {
                try { api.verifyPassword(cur); }
                catch (Api.ApiException e) {
                    if (e.status == 400 || e.status == 401) throw new Exception("Current password is not correct.");
                    throw e;
                }
                changePassword(api, pw);
                return true;
            }, (ok, err) -> {
                change.setEnabled(true);
                change.setText("Change My Login Password");
                if (err != null) { alert("Password not changed", Api.message(err)); return; }
                current.setText(""); next.setText(""); confirm.setText("");
                alert("Password changed", "Your QCMS login password was changed successfully.");
            });
        });

        Button out = Ui.outline(a, "Sign out", Ui.ORANGE);
        out.setOnClickListener(v -> a.confirm("Sign out?", "You will need your email and password to sign in again.", "Sign out", a::signOut));
        add(out, 18);
        return scroll;
    }

    private void alert(String title, String msg) {
        new android.app.AlertDialog.Builder(a).setTitle(title).setMessage(msg).setPositiveButton("OK", null).show();
    }

    /**
     * Calls {@code Api.changePassword(String)} (to be added to Api by the framework owner). Until it
     * exists, the same request (PUT /auth/v1/user {"password": ...} with the user's session) is sent
     * through Api's own HTTP helper so the change works today. Background thread.
     */
    static void changePassword(Api api, String newPassword) throws Exception {
        Method m = null;
        try { m = Api.class.getMethod("changePassword", String.class); } catch (NoSuchMethodException ignored) { }
        try {
            if (m != null) { m.invoke(api, newPassword); return; }
            Method token = Api.class.getDeclaredMethod("token");
            token.setAccessible(true);
            String bearer = (String) token.invoke(api);
            Method http = Api.class.getDeclaredMethod("http", String.class, String.class, String.class, boolean.class, String.class);
            http.setAccessible(true);
            Object res = http.invoke(api, "PUT", "/auth/v1/user", new JSONObject().put("password", newPassword).toString(), false, bearer);
            String body = res == null ? "" : String.valueOf(res.getClass().getField("body").get(res));
            JSONObject user = new JSONObject(body.isEmpty() ? "{}" : body);
            if (user.optString("id", "").isEmpty()) throw new Exception("Supabase did not confirm the password change.");
        } catch (java.lang.reflect.InvocationTargetException e) {
            Throwable c = e.getCause();
            if (c instanceof Exception) throw (Exception) c;
            throw new Exception(String.valueOf(c));
        } catch (NoSuchMethodException e) {
            throw new Exception("Password change needs a newer version of the QCMS app.");
        }
    }
}
