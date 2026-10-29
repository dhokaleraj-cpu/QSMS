package com.fourstar.qcmsapp;

import android.text.InputType;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Switch;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Licence & Company (app_pages/licence_company.py render): A licence status + key validate / activate (company admin),
 * B company profile & logo (required fields as licence_service.missing_company_fields), C developer, D WhatsApp auto messages.
 * The WhatsApp access token is a server secret (Supabase Edge Function secret) - it is never entered or shown here.
 */
final class LicCompanyScreen extends Screen {
    LicCompanyScreen(MainActivity a) { super(a); }

    @Override public String title() { return "Licence & Company"; }
    @Override public String subtitle() { return GenCentres.About.PRODUCT + " licence, company profile and logo, WhatsApp"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> Licence.load(api), (st, err) -> {
            page.removeAllViews();
            JSONObject status = st == null ? (Licence.status == null ? new JSONObject() : Licence.status) : st;
            if (err != null && Licence.status == null) add(AdmUi.note(a, "Licence check unavailable: " + Api.message(err), "amber"), 0);
            render(status);
        });
        return scroll;
    }

    private void render(JSONObject status) {
        boolean dev = status.optBoolean("is_stawn_developer", false);
        boolean admin = status.optBoolean("is_company_admin", false) || api.isAdmin();
        boolean canEdit = admin || dev;

        LinearLayout lic = AdmUi.section(a, page, "A", GenCentres.About.PRODUCT.toUpperCase(java.util.Locale.ROOT) + " LICENCE",
            "Licensed by " + GenCentres.About.COMPANY + ". The key is checked online every time the app starts.");
        String stText = Licence.text(status, "status");
        LinearLayout chips = Ui.hbox(a);
        chips.addView(Ui.chip(a, stText.equals("-") ? "UNCHECKED" : stText, Licence.statusTone(stText)));
        lic.addView(chips, Ui.matchWrap(a, 6));
        AdmUi.metric(a, lic, "Plan", Licence.text(status, "plan"));
        AdmUi.metric(a, lic, "Users", (status.isNull("used_users") ? "0" : status.optString("used_users", "0")) + " of "
            + (status.isNull("max_users") ? "-" : status.optString("max_users", "-")) + " licensed");
        AdmUi.metric(a, lic, "Valid until", Licence.text(status, "expires_on").equals("-") ? "No expiry" : Ui.date(status.optString("expires_on")));
        String reason = LicService.s(status, "reason");
        lic.addView(Ui.text(a, (reason.isEmpty() ? "" : reason + " · ") + "Key " + Licence.text(status, "licence_key_masked") + " · last online check "
            + (LicService.s(status, "last_validated_at").isEmpty() ? "now" : AdmUi.ts(status.optString("last_validated_at"))), 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 6));
        if (canEdit) {
            EditText key = AdmUi.field(a, lic, "Licence key from STAWN", "", "STAWN-QCMS-XXXXX-XXXXX-XXXXX-XXXXX");
            key.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS);
            AdmUi.outline(a, lic, "Validate online", v -> {
                String k = AdmUi.text(key).trim();
                if (k.length() < 6) { key.setError("Enter the licence key from STAWN"); return; }
                Api.async(() -> LicService.validateKey(api, k), (r, e) -> {
                    if (e != null) { a.toast(Api.message(e)); return; }
                    info(r.optBoolean("valid", false) ? "Licence key valid" : "Licence key not valid", LicService.s(r, "status") + ": " + LicService.s(r, "reason"));
                });
            });
            AdmUi.primary(a, lic, "Activate", v -> {
                String k = AdmUi.text(key).trim();
                if (k.length() < 6) { key.setError("Enter the licence key from STAWN"); return; }
                Button b = (Button) v;
                AdmUi.enable(b, false);
                Api.async(() -> LicService.activateKey(api, k), (r, e) -> {
                    AdmUi.enable(b, true);
                    if (e != null) { a.toast(Api.message(e)); return; }
                    if (r.optBoolean("valid", false)) {
                        a.toast("Licence activated: " + LicService.s(r, "plan") + " · " + LicService.s(r, "max_users") + " users.");
                        reload();
                    } else {
                        info("Licence not activated", LicService.s(r, "status") + ": " + (r.has("reason") ? LicService.s(r, "reason") : r.optString("message", "")));
                    }
                });
            });
        } else {
            lic.addView(Ui.text(a, "Only the company administrator can enter or change the licence key.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 6));
        }

        LicProfile.section(a, page, "B", api.tenantId, LicService.s(status, "company_legal_name"), canEdit);

        LinearLayout devBox = AdmUi.section(a, page, "C", "DEVELOPER", "");
        devBox.addView(Ui.text(a, GenCentres.About.COMPANY + " · Thane, Maharashtra, India · " + GenCentres.About.EMAIL + "\n" + GenCentres.About.COPYRIGHT, 12.5f, Ui.TEXT, false), Ui.matchWrap(a, 4));
        if (dev) AdmUi.primary(a, devBox, "Open STAWN Developer Console", v -> a.push(new DevConsoleScreen(a)));

        whatsapp(canEdit);
    }

    private void whatsapp(boolean canEdit) {
        LinearLayout box = AdmUi.section(a, page, "D", "WHATSAPP AUTO MESSAGES (META WHATSAPP BUSINESS CLOUD API)",
            "Approval requests and tasks are sent as WhatsApp template messages to users who opted in (My Notifications). "
                + "The access token is a server secret – it is never stored in QCMS tables or in this app.");
        LinearLayout body = Ui.vbox(a);
        body.addView(Ui.text(a, "Loading…", 12, Ui.MUTED, false));
        box.addView(body, Ui.matchWrap(a, 4));
        Api.async(() -> LicService.whatsappSettings(api), (wa, err) -> {
            body.removeAllViews();
            if (err != null) { body.addView(AdmUi.note(a, Api.message(err), "red")); return; }
            Switch on = AdmUi.toggle(a, body, "WhatsApp messages ON", wa.optBoolean("enabled", false));
            EditText phone = AdmUi.field(a, body, "Phone Number ID", LicService.s(wa, "phone_number_id"), null);
            EditText waba = AdmUi.field(a, body, "WhatsApp Business Account ID", LicService.s(wa, "business_account_id"), null);
            EditText tAppr = AdmUi.field(a, body, "Approval template", or(LicService.s(wa, "approval_template"), "qcms_approval_request"), null);
            EditText tTask = AdmUi.field(a, body, "Task template", or(LicService.s(wa, "task_template"), "qcms_task_alert"), null);
            EditText tUpd = AdmUi.field(a, body, "Update template", or(LicService.s(wa, "update_template"), "qcms_update_alert"), null);
            EditText lang = AdmUi.field(a, body, "Template language", or(LicService.s(wa, "template_language"), "en"), null);
            EditText cc = AdmUi.field(a, body, "Default country code", or(LicService.s(wa, "default_country_code"), "91"), null);
            EditText link = AdmUi.field(a, body, "App link in messages", or(LicService.s(wa, "app_link"), "https://vf6fa9hrhxquqxmfgyy4wf.streamlit.app"), null);
            List<String> cats = new ArrayList<>();
            JSONArray cur = wa.optJSONArray("send_categories");
            for (int i = 0; cur != null && i < cur.length(); i++) if (AdmUi.listOf(LicService.WHATSAPP_CATEGORIES).contains(cur.optString(i))) cats.add(cur.optString(i));
            if (cur == null) { cats.add("APPROVAL"); cats.add("TASK"); }
            View catsView = AdmUi.multi(a, body, "Send these on WhatsApp", AdmUi.listOf(LicService.WHATSAPP_CATEGORIES), cats, null);
            for (View v : new View[]{on, phone, waba, tAppr, tTask, tUpd, lang, cc, link, catsView}) AdmUi.enableView(v, canEdit);
            if (canEdit) {
                AdmUi.primary(a, body, "Save WhatsApp settings", v -> {
                    Button b = (Button) v;
                    AdmUi.enable(b, false);
                    Api.async(() -> {
                        JSONArray sc = new JSONArray();
                        for (String c : cats.isEmpty() ? AdmUi.listOf("APPROVAL", "TASK") : cats) sc.put(c);
                        JSONObject values = new JSONObject().put("enabled", on.isChecked())
                            .put("phone_number_id", nul(AdmUi.text(phone))).put("business_account_id", nul(AdmUi.text(waba)))
                            .put("approval_template", AdmUi.text(tAppr).trim()).put("task_template", AdmUi.text(tTask).trim())
                            .put("update_template", AdmUi.text(tUpd).trim()).put("template_language", or(AdmUi.text(lang).trim(), "en"))
                            .put("default_country_code", or(AdmUi.text(cc).trim(), "91")).put("app_link", nul(AdmUi.text(link)))
                            .put("send_categories", sc);
                        LicService.saveWhatsappSettings(api, values);
                        return true;
                    }, (ok, e) -> {
                        AdmUi.enable(b, true);
                        a.toast(e != null ? Api.message(e) : "WhatsApp settings saved.");
                    });
                });
            }
            EditText to = AdmUi.field(a, body, "Send a test message to", "", "9198XXXXXXXX");
            to.setInputType(InputType.TYPE_CLASS_PHONE);
            Button test = AdmUi.outline(a, body, "Send WhatsApp test", v -> {
                String n = AdmUi.text(to).trim();
                if (n.isEmpty()) { to.setError("Enter the mobile number with country code"); return; }
                Api.async(() -> LicService.whatsappTest(api, n), (r, e) -> {
                    if (e != null) { a.toast(Api.message(e)); return; }
                    info(r.optBoolean("ok", false) ? "WhatsApp test sent" : "WhatsApp test failed",
                        r.optBoolean("ok", false) ? "Test sent to " + LicService.s(r, "to") + " (message id " + LicService.s(r, "message_id") + ")." : LicService.s(r, "error"));
                });
            });
            AdmUi.enable(test, canEdit);
            body.addView(AdmUi.note(a, "How to connect WhatsApp (one time): create a Meta Business WhatsApp app, verify the company number, copy the Phone Number ID "
                + "and WhatsApp Business Account ID above, create a permanent system-user token and store it ONLY as the Supabase secret WHATSAPP_TOKEN "
                + "(never in QCMS), create the three Utility templates qcms_approval_request / qcms_task_alert / qcms_update_alert, then switch WhatsApp ON "
                + "and send a test. Users opt in on My Notifications.", "grey"), Ui.matchWrap(a, 10));
        });
    }

    private static String or(String v, String d) { return v == null || v.isEmpty() ? d : v; }
    private static Object nul(String v) { return v == null || v.trim().isEmpty() ? JSONObject.NULL : v.trim(); }

    private void info(String title, String msg) {
        new android.app.AlertDialog.Builder(a).setTitle(title).setMessage(msg).setPositiveButton("OK", null).show();
    }
}
