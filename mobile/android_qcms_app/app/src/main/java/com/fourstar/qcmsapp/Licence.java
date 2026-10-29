package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.Locale;

/**
 * R35 licence + company (live RPCs qcms_licence_status / qcms_activate_licence).
 * The app is blocked only when the server answers with a status and valid=false for a user who is not
 * a STAWN developer. When the RPC fails (offline, older database) the app is never blocked.
 */
final class Licence {
    private Licence() { }

    /** Last good answer of qcms_licence_status (null until loaded / when the RPC is not available). */
    static volatile JSONObject status;

    static JSONObject load(Api api) throws Exception {
        JSONObject s = api.rpcObject("qcms_licence_status", new JSONObject());
        status = s;
        String company = companyName(s);
        if (!company.isEmpty()) api.prefs().edit().putString("licence_company", company).apply();
        return s;
    }

    static JSONObject activate(Api api, String key) throws Exception {
        return api.rpcObject("qcms_activate_licence", new JSONObject().put("p_key", key.trim()));
    }

    static String companyName(JSONObject s) {
        if (s == null) return "";
        String n = s.isNull("company_name") ? "" : s.optString("company_name", "");
        if (n.isEmpty() && !s.isNull("company_legal_name")) n = s.optString("company_legal_name", "");
        return n.trim();
    }

    /** Company shown under "STAWN QCMS" (cached so it also shows offline). */
    static String company(Api api) {
        String n = companyName(status);
        return n.isEmpty() ? api.prefs().getString("licence_company", "") : n;
    }

    /** True when the app must show the blocking licence screen. */
    static boolean blocks(JSONObject s) {
        if (s == null || s.length() == 0) return false;
        String st = s.isNull("status") ? "" : s.optString("status", "").trim();
        if (st.isEmpty() || !s.has("valid")) return false;
        if (s.optBoolean("is_stawn_developer", false)) return false;
        return !s.optBoolean("valid", true);
    }

    static String developerName(JSONObject s) {
        JSONObject d = s == null ? null : s.optJSONObject("developer");
        String n = d == null ? "" : d.optString("name", "");
        return n.isEmpty() ? GenCentres.About.COMPANY : n;
    }

    static String usersText(JSONObject s) {
        String used = s.isNull("used_users") ? "-" : s.optString("used_users", "-");
        String max = s.isNull("max_users") ? "unlimited" : s.optString("max_users", "unlimited");
        return used + " of " + max;
    }

    static String text(JSONObject s, String key) {
        if (s == null || s.isNull(key)) return "-";
        String v = s.optString(key, "");
        return v.isEmpty() ? "-" : v;
    }

    static String statusTone(String st) {
        switch (st == null ? "" : st.toUpperCase(Locale.ROOT)) {
            case "ACTIVE": return "green";
            case "GRACE": return "amber";
            default: return "red";
        }
    }

    /** Licence details card for the About screen. */
    static View detailsCard(MainActivity a, JSONObject s) {
        LinearLayout card = Ui.card(a);
        if (s == null || s.length() == 0) {
            card.addView(Ui.text(a, "Licence details are not available right now (offline or older QCMS database).", 12, Ui.MUTED, false));
            card.addView(Ui.pair(a, "Developer", GenCentres.About.COMPANY));
            return card;
        }
        LinearLayout head = Ui.hbox(a);
        head.setGravity(Gravity.CENTER_VERTICAL);
        head.addView(Ui.text(a, text(s, "product").equals("-") ? GenCentres.About.PRODUCT : text(s, "product"), 14, Ui.TEXT, true), Ui.weight(1));
        String st = text(s, "status");
        head.addView(Ui.chip(a, st, statusTone(st)));
        card.addView(head);
        card.addView(Ui.pair(a, "Licensed company", companyName(s).isEmpty() ? "-" : companyName(s)));
        if (!s.isNull("company_legal_name") && !s.optString("company_legal_name").equals(companyName(s))) card.addView(Ui.pair(a, "Legal name", s.optString("company_legal_name")));
        card.addView(Ui.pair(a, "Plan", text(s, "plan")));
        card.addView(Ui.pair(a, "Status", st + (s.optBoolean("valid", false) ? " · valid" : " · not valid")));
        card.addView(Ui.pair(a, "Users", usersText(s)));
        card.addView(Ui.pair(a, "Valid until", text(s, "expires_on").equals("-") ? "-" : Ui.date(s.optString("expires_on"))));
        card.addView(Ui.pair(a, "Licence key", text(s, "licence_key_masked")));
        card.addView(Ui.pair(a, "Developer", developerName(s)));
        String reason = s.isNull("reason") ? "" : s.optString("reason", "");
        if (!reason.isEmpty()) card.addView(Ui.text(a, reason, 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 6));
        if (s.optBoolean("is_company_admin", false) || s.optBoolean("is_stawn_developer", false)) {
            Button web = Ui.outline(a, "Licence & Company", Ui.TEAL);
            web.setOnClickListener(v -> a.push(new LicCompanyScreen(a)));
            card.addView(web, Ui.matchWrap(a, 10));
        }
        if (s.optBoolean("is_stawn_developer", false)) {
            Button dev = Ui.outline(a, "STAWN Developer Console", Ui.TEAL_DARK);
            dev.setOnClickListener(v -> a.push(new DevConsoleScreen(a)));
            card.addView(dev, Ui.matchWrap(a, 8));
        }
        return card;
    }

    // ------------------------------------------------------------------ blocking screen
    /** Full-screen STAWN-branded licence screen (no navigation to the modules). */
    static View blockingView(MainActivity a, JSONObject s) {
        Api api = Api.get(a);
        ScrollView scroll = new ScrollView(a);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.WHITE);
        LinearLayout root = Ui.vbox(a);
        int p = Ui.dp(a, 24);
        root.setPadding(p, Ui.dp(a, 44), p, p);
        scroll.addView(root);

        android.widget.ImageView logo = new android.widget.ImageView(a);
        logo.setImageResource(R.drawable.stawn_qcms_logo);
        logo.setBackground(Ui.round(Color.parseColor("#165D91"), 0, 0, 20, a));
        logo.setClipToOutline(true);
        LinearLayout.LayoutParams llp = new LinearLayout.LayoutParams(Ui.dp(a, 72), Ui.dp(a, 72));
        llp.gravity = Gravity.CENTER_HORIZONTAL;
        root.addView(logo, llp);
        TextView name = Ui.text(a, GenCentres.About.PRODUCT, 22, Ui.TEAL_DARK, true);
        name.setGravity(Gravity.CENTER);
        name.setPadding(0, Ui.dp(a, 10), 0, 0);
        root.addView(name);
        String company = companyName(s);
        TextView comp = Ui.text(a, company.isEmpty() ? GenCentres.About.TAGLINE : company, 13, Ui.MUTED, false);
        comp.setGravity(Gravity.CENTER);
        root.addView(comp);

        LinearLayout card = Ui.card(a);
        String st = text(s, "status");
        LinearLayout head = Ui.hbox(a);
        head.setGravity(Gravity.CENTER_VERTICAL);
        head.addView(Ui.text(a, "Licence not valid", 17, Ui.RED_FG, true), Ui.weight(1));
        head.addView(Ui.chip(a, st, "red"));
        card.addView(head);
        String reason = s.isNull("reason") ? "" : s.optString("reason", "");
        card.addView(Ui.text(a, reason.isEmpty() ? "The STAWN QCMS licence of your company is not active. Please contact STAWN PRECISION to renew or activate it." : reason, 13, Ui.TEXT, false), Ui.matchWrap(a, 8));
        if (!text(s, "expires_on").equals("-")) card.addView(Ui.pair(a, "Valid until", Ui.date(s.optString("expires_on"))));
        if (!text(s, "licence_key_masked").equals("-")) card.addView(Ui.pair(a, "Licence key", s.optString("licence_key_masked")));
        if (!text(s, "plan").equals("-")) card.addView(Ui.pair(a, "Plan", s.optString("plan")));
        card.addView(Ui.pair(a, "Contact", GenCentres.About.EMAIL));
        root.addView(card, Ui.matchWrap(a, 22));

        if (s.optBoolean("is_company_admin", false)) {
            LinearLayout admin = Ui.card(a);
            admin.addView(Ui.text(a, "Activate a licence key (company administrator)", 14, Ui.TEXT, true));
            EditText key = Ui.input(a, "STAWN licence key", false);
            key.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS);
            admin.addView(key, Ui.matchWrap(a, 8));
            Button activate = Ui.primary(a, "Activate licence");
            admin.addView(activate, Ui.matchWrap(a, 10));
            activate.setOnClickListener(v -> {
                String k = key.getText().toString().trim();
                if (k.length() < 6) { key.setError("Enter the licence key from STAWN"); return; }
                activate.setEnabled(false);
                activate.setText("Activating…");
                Api.async(() -> { JSONObject res = activate(api, k); load(api); return res; }, (res, err) -> {
                    activate.setEnabled(true);
                    activate.setText("Activate licence");
                    if (err != null) { a.toast(Api.message(err)); return; }
                    if (res != null && res.has("ok") && !res.optBoolean("ok", true)) {
                        a.toast(res.optString("message", res.optString("error", "The licence key was not accepted.")));
                        return;
                    }
                    if (blocks(status)) {
                        a.toast(res != null && !res.optString("message", "").isEmpty() ? res.optString("message") : "The licence is still not valid.");
                        a.showLicenceBlocked(status);
                    } else {
                        a.toast("Licence activated. Welcome to STAWN QCMS.");
                        a.showShell(0);
                    }
                });
            });
            root.addView(admin, Ui.matchWrap(a, 12));
        }

        Button mail = Ui.outline(a, "✉ Contact " + GenCentres.About.EMAIL, Ui.TEAL_DARK);
        mail.setOnClickListener(v -> {
            try {
                Intent i = new Intent(Intent.ACTION_SENDTO, Uri.parse("mailto:" + GenCentres.About.EMAIL));
                i.putExtra(Intent.EXTRA_SUBJECT, "STAWN QCMS licence · " + (company.isEmpty() ? api.email : company));
                a.startActivity(i);
            } catch (Exception e) {
                a.toast("No e-mail app found. Write to " + GenCentres.About.EMAIL);
            }
        });
        root.addView(mail, Ui.matchWrap(a, 14));
        Button again = Ui.outline(a, "↻ Check again", Ui.TEAL);
        again.setOnClickListener(v -> a.checkLicence(true));
        root.addView(again, Ui.matchWrap(a, 8));
        Button about = Ui.outline(a, "About STAWN QCMS", Ui.TEAL);
        about.setOnClickListener(v -> aboutDialog(a, s));
        root.addView(about, Ui.matchWrap(a, 8));
        Button out = Ui.outline(a, "Sign out", Ui.RED_FG);
        out.setOnClickListener(v -> a.signOut());
        root.addView(out, Ui.matchWrap(a, 8));

        TextView foot = Ui.text(a, GenCentres.About.COPYRIGHT + "\nSigned in as " + api.email, 11, Ui.MUTED, false);
        foot.setGravity(Gravity.CENTER);
        foot.setPadding(0, Ui.dp(a, 24), 0, 0);
        root.addView(foot);
        return scroll;
    }

    private static void aboutDialog(MainActivity a, JSONObject s) {
        StringBuilder b = new StringBuilder();
        b.append(GenCentres.About.PRODUCT).append(" – ").append(GenCentres.About.TAGLINE).append("\nAndroid app v").append(BuildConfig.VERSION_NAME).append("\n\n");
        for (String[] p : GenCentres.About.DEVELOPER) b.append(p[0]).append(": ").append(p[1]).append('\n');
        b.append("\nLicence: ").append(text(s, "status")).append(" · ").append(text(s, "plan"))
            .append("\nCompany: ").append(companyName(s).isEmpty() ? "-" : companyName(s))
            .append("\nValid until: ").append(text(s, "expires_on"))
            .append("\nKey: ").append(text(s, "licence_key_masked"))
            .append("\n\n").append(GenCentres.About.COPYRIGHT);
        new AlertDialog.Builder(a).setTitle("About STAWN QCMS").setMessage(b.toString()).setPositiveButton("OK", null).show();
    }
}
