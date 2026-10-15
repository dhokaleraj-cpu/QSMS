package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

import org.json.JSONObject;

/**
 * Native port of app_pages/system_settings.py: AI Assistant mode and the email "From" mode, both stored in
 * master_value_catalog with core/system_settings.py rules. API keys and other secrets live only in the
 * website server secrets: the app never reads or shows them.
 */
public final class AdmSystemScreen extends Screen {
    public AdmSystemScreen(MainActivity a) { super(a); }

    @Override public String title() { return "System Settings"; }
    @Override public String subtitle() { return "Administrator controls for QCMS-wide features"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        if (!api.isAdmin()) {
            add(AdmUi.adminOnly(a, "System Settings are restricted to the QCMS System Administrator."), 4);
            return scroll;
        }
        page.addView(loading());
        Api.async(() -> {
            JSONObject record = AdmDb.aiModeRecord(api);
            JSONObject server = AdmDb.first(new org.json.JSONArray(api.get(
                "qcms_email_settings?select=id,enabled,smtp_host,sender_email&limit=1", false).body));
            String from = AdmDb.emailFromMode(api);
            return new Object[]{record, server, from};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { add(error(err, this::reload)); return; }
            render((JSONObject) res[0], (JSONObject) res[1], (String) res[2]);
        });
        return scroll;
    }

    private void render(JSONObject record, JSONObject server, String fromMode) {
        String mode = record == null ? "ALL" : AdmPy.j(record, "value_text").trim().toUpperCase(java.util.Locale.ROOT);
        LinearLayout ai = AdmUi.section(a, page, "A", "AI ASSISTANT (GLOBAL SEARCH)", "Switch the AI Assistant on or off for the whole company, or keep it for administrators only.");
        String shown = "ALL".equals(mode) ? "Enabled · all users" : "ADMIN_ONLY".equals(mode) ? "Admins only" : "Disabled";
        AdmUi.metric(a, ai, "Current mode", shown + (record == null ? " (default)" : ""));
        AdmUi.metric(a, ai, "AI engine / API key", "Kept in the website server secrets (never shown in the app)");
        if (record != null) {
            String when = AdmPy.j(record, "last_used_at").isEmpty() ? AdmPy.j(record, "updated_at") : AdmPy.j(record, "last_used_at");
            ai.addView(Ui.text(a, "Last changed: " + AdmUi.ts(when) + " UTC", 11, Ui.MUTED, false), Ui.matchWrap(a, 6));
        }
        ai.addView(AdmUi.note(a, "If the website secret QCMS_AI_MODE is set, it overrides this setting (the app cannot see website secrets).", "grey"), Ui.matchWrap(a, 8));
        final String[] choice = {mode};
        AdmUi.radio(a, ai, "AI Assistant mode", AdmDb.AI_MODES, mode, true, v -> choice[0] = v);
        AdmUi.primary(a, ai, "Save AI Assistant setting", v -> {
            Button b = (Button) v;
            AdmUi.enable(b, false);
            Api.async(() -> AdmDb.setAiMode(api, choice[0]), (r, e) -> {
                AdmUi.enable(b, true);
                if (e != null) { a.toast(Api.message(e)); return; }
                a.toast("AI Assistant is now: " + AdmDb.modeLabel(AdmDb.AI_MODES, choice[0]) + ". Users see the change on their next page refresh (within about a minute).");
                a.rebuild();
            });
        });
        ai.addView(Ui.text(a, "The AI API key is set once by the administrator in the website server secrets (website-only). Free tiers (Gemini, Groq) are rate-limited and the provider may use free-tier prompts to improve its services. Only rows the user is allowed to see are sent, but for strictly confidential data use a paid key.", 11, Ui.MUTED, false), Ui.matchWrap(a, 8));

        LinearLayout em = AdmUi.section(a, page, "B", "EMAIL MODULE · DEFAULT EMAIL SERVER", "All users send email through the default email server — no Office 365 sign-in is needed.");
        AdmUi.metric(a, em, "Email server", server != null && AdmPy.truthy(server, "enabled") ? "Enabled" : "Not enabled");
        AdmUi.metric(a, em, "SMTP host", server == null ? "" : AdmPy.j(server, "smtp_host"));
        AdmUi.metric(a, em, "Company mailbox", server == null ? "" : AdmPy.j(server, "sender_email"));
        final String[] from = {fromMode};
        AdmUi.radio(a, em, "What recipients see as the sender", AdmDb.EMAIL_FROM_MODES, fromMode, true, v -> from[0] = v);
        AdmUi.primary(a, em, "Save email From setting", v -> {
            Button b = (Button) v;
            AdmUi.enable(b, false);
            Api.async(() -> AdmDb.setSystemValue(api, AdmDb.EMAIL_FROM_MODE_KEY, from[0]), (r, e) -> {
                AdmUi.enable(b, true);
                if (e != null) { a.toast(Api.message(e)); return; }
                a.toast("Email From setting saved: " + AdmDb.modeLabel(AdmDb.EMAIL_FROM_MODES, from[0]));
                a.rebuild();
            });
        });
        em.addView(Ui.text(a,
            "• Company mailbox (recommended, default): Microsoft 365 always delivers it. Recipients see \"User Name via QCMS\" and replies go to the user's own email.\n"
                + "• User's own email: only after the Microsoft 365 admin gives the company mailbox Send As permission on every user mailbox "
                + "(Exchange admin center → Recipients → Mailboxes → user → Delegation → Send as). Without it Microsoft 365 silently bounces the email (NDR 5.7.60 SendAsDenied).\n"
                + "• Each user can edit their own From name / reply-to email in Email → My Email Settings. Change the server in Admin → Email Settings.",
            11.5f, Ui.TEXT, false), Ui.matchWrap(a, 8));
        AdmUi.outline(a, em, "Open Email Settings (server)", v -> a.openModule("email_server"));

        LinearLayout info = AdmUi.section(a, page, "", "SYSTEM INFORMATION", "Read-only.");
        info.addView(Ui.text(a, "• QCMS app version " + BuildConfig.VERSION_NAME + "\n• Website version, read cache and company / plant code are server configuration (website secrets) and are shown on the website only.", 12, Ui.TEXT, false), Ui.matchWrap(a, 6));
    }
}
