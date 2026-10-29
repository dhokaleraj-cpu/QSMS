package com.fourstar.qcmsapp;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

/**
 * STAWN Developer Console (app_pages/licence_company.py render_developer) - only for the STAWN developer login
 * (qcms_licence_status.is_stawn_developer; every qcms_dev_* RPC checks it again on the server):
 * A licensed companies · B issue / renew / suspend / re-activate / revoke licence keys · C new customer company ·
 * D assign company administrator · E company profile & logo of any company · F STAWN branding · H login cover photo ·
 * G all administration tools · trial / test data purge (DevPurgeScreen).
 */
final class DevConsoleScreen extends Screen {
    private JSONArray rows = new JSONArray();
    private int issueIdx = 0, assignIdx = 0, profileIdx = 0;

    DevConsoleScreen(MainActivity a) { super(a); }

    @Override public String title() { return "STAWN Developer Console"; }
    @Override public String subtitle() { return "All companies, licences and administrators · STAWN only"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONObject st = Licence.load(api);
            JSONArray list = st.optBoolean("is_stawn_developer", false) ? LicService.devOverview(api) : new JSONArray();
            return new Object[]{st, list};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { add(error(err, this::reload)); return; }
            JSONObject st = (JSONObject) res[0];
            if (!st.optBoolean("is_stawn_developer", false)) {
                add(AdmUi.adminOnly(a, "This console is only for the " + GenCentres.About.COMPANY + " developer login."), 0);
                return;
            }
            rows = (JSONArray) res[1];
            render();
        });
        return scroll;
    }

    private List<String> companyLabels() {
        List<String> out = new ArrayList<>();
        for (int i = 0; i < rows.length(); i++) {
            JSONObject r = rows.optJSONObject(i);
            out.add(LicService.s(r, "tenant_code") + " · " + LicService.s(r, "company_name"));
        }
        return out;
    }

    private List<String> indexes() {
        List<String> out = new ArrayList<>();
        for (int i = 0; i < rows.length(); i++) out.add(String.valueOf(i));
        return out;
    }

    private JSONObject company(int i) { return rows.optJSONObject(Math.max(0, Math.min(i, rows.length() - 1))); }

    private void render() {
        // ---- A licensed companies
        LinearLayout a1 = AdmUi.section(a, page, "A", "LICENSED COMPANIES", rows.length() + " compan" + (rows.length() == 1 ? "y" : "ies"));
        if (rows.length() == 0) a1.addView(AdmUi.note(a, "No companies yet.", "grey"), Ui.matchWrap(a, 4));
        else {
            List<String> cols = AdmUi.listOf("Code", "Company", "Plan", "Status", "Valid to", "Users", "Licensed users", "Setup done", "Licence key", "Last online check");
            List<List<String>> data = new ArrayList<>();
            for (int i = 0; i < rows.length(); i++) {
                JSONObject r = rows.optJSONObject(i);
                data.add(AdmUi.listOf(LicService.s(r, "tenant_code"), LicService.s(r, "company_name"), LicService.s(r, "plan"), LicService.s(r, "evaluated_status"),
                    LicService.s(r, "valid_to").isEmpty() ? "No expiry" : Ui.date(r.optString("valid_to")), LicService.s(r, "used_users"), LicService.s(r, "max_users"),
                    r.optBoolean("setup_complete", false) ? "Yes" : "No", LicService.s(r, "licence_key"), AdmUi.ts(LicService.s(r, "last_validated_at"))));
            }
            a1.addView(new DataGrid(a, "Licensed companies", cols, data, 320, index -> {
                issueIdx = index; assignIdx = index; profileIdx = index;
                a.toast("Selected " + companyLabels().get(index) + " in sections B, D and E.");
                rebuildBelow();
            }), Ui.matchWrap(a, 6));
        }
        below = Ui.vbox(a);
        page.addView(below, Ui.matchWrap(a, 0));
        rebuildBelow();
    }

    private LinearLayout below;

    private void rebuildBelow() {
        below.removeAllViews();
        LinearLayout saved = page;
        page = below;
        try {
            issue();
            newCompany();
            assign();
            if (rows.length() > 0) {
                JSONObject c = company(profileIdx);
                LinearLayout pick = AdmUi.section(a, page, "E", "COMPANY PROFILE & LOGO OF ANY COMPANY", "STAWN can complete or correct any licensed company's details.");
                AdmUi.choice(a, pick, "Company to edit", indexes(), companyLabels(), String.valueOf(profileIdx), v -> { profileIdx = Integer.parseInt(v); rebuildBelow(); });
                LicProfile.section(a, page, "E", LicService.s(c, "tenant_id"), LicService.s(c, "company_name"), true);
            }
            branding();
            loginCover();
            adminTools();
            purge();
            LinearLayout rights = AdmUi.section(a, page, "", "STAWN DEVELOPER RIGHTS", "");
            rights.addView(Ui.text(a, "The STAWN developer login keeps ADMIN rights in its home company, is never counted as a licensed user, and can "
                + "see and manage every company's licence. Company administrators only manage their own company.", 12, Ui.TEXT, false), Ui.matchWrap(a, 4));
        } finally {
            page = saved;
        }
    }

    // ---- B issue / renew licence key
    private void issue() {
        LinearLayout box = AdmUi.section(a, page, "B", "ISSUE / RENEW LICENCE KEY", "A new key replaces the company's active key (old key → SUPERSEDED).");
        if (rows.length() == 0) { box.addView(AdmUi.note(a, "Create a company first (section C).", "grey"), Ui.matchWrap(a, 4)); return; }
        AdmUi.choice(a, box, "Company", indexes(), companyLabels(), String.valueOf(issueIdx), v -> { issueIdx = Integer.parseInt(v); rebuildBelow(); });
        final String[] plan = {"STANDARD"};
        EditText users = AdmUi.number(a, box, "Licensed users", 25);
        CheckBox noExpiry = AdmUi.check(a, "No expiry", true);
        EditText validTo = AdmUi.field(a, box, "Valid until (YYYY-MM-DD)", LocalDate.now().plusDays(365).toString(), "YYYY-MM-DD");
        AdmUi.choice(a, box, "Plan", AdmUi.listOf(LicService.PLANS), plan[0], v -> {
            plan[0] = v;
            boolean trial = "TRIAL".equals(v);
            noExpiry.setChecked(!trial);
            validTo.setText(LocalDate.now().plusDays(trial ? 30 : 365).toString());
        });
        box.addView(noExpiry, Ui.matchWrap(a, 6));
        EditText notes = AdmUi.field(a, box, "Notes (order / invoice reference)", "", null);
        AdmUi.primary(a, box, "Issue licence key", v -> {
            Integer n = AdmUi.intIn(users, 1, 5000);
            if (n == null) { users.setError("1 - 5000"); return; }
            String to = noExpiry.isChecked() ? null : date(validTo);
            if (!noExpiry.isChecked() && to == null) return;
            JSONObject c = company(issueIdx);
            Button b = (Button) v;
            AdmUi.enable(b, false);
            Api.async(() -> LicService.devIssueLicence(api, LicService.s(c, "tenant_id"), plan[0], n, to, AdmUi.text(notes)), (r, e) -> {
                AdmUi.enable(b, true);
                if (e != null) { a.toast(Api.message(e)); return; }
                String key = LicService.s(r, "licence_key");
                copy(key);
                new android.app.AlertDialog.Builder(a).setTitle("Licence key issued")
                    .setMessage("Send it to the company administrator of " + LicService.s(c, "company_name") + ":\n\n" + key + "\n\n(copied to the clipboard)")
                    .setPositiveButton("OK", (d, w) -> reload()).show();
            });
        });
        JSONObject sel = company(issueIdx);
        String licenceId = LicService.s(sel, "licence_id");
        if (licenceId.isEmpty()) return;
        String currentKey = LicService.s(sel, "licence_key");
        if (!currentKey.isEmpty()) AdmUi.outline(a, box, "Copy licence key of " + LicService.s(sel, "tenant_code"), v -> {
            copy(currentKey);
            a.toast("Licence key copied: " + currentKey);
        });
        box.addView(Ui.label(a, "Change the current licence · " + LicService.s(sel, "plan") + " · " + LicService.s(sel, "status")), Ui.matchWrap(a, 10));
        EditText newUsers = AdmUi.number(a, box, "Licensed users (renewal)", sel.optInt("max_users", 25));
        EditText renewTo = AdmUi.field(a, box, "Renew valid until (YYYY-MM-DD, blank = keep)", "", "YYYY-MM-DD");
        CheckBox clear = AdmUi.check(a, "Remove the expiry date (no expiry)", false);
        box.addView(clear, Ui.matchWrap(a, 4));
        AdmUi.primary(a, box, "Renew / update this licence", v -> {
            Integer n = AdmUi.intIn(newUsers, 1, 5000);
            if (n == null) { newUsers.setError("1 - 5000"); return; }
            String to = AdmUi.text(renewTo).trim().isEmpty() ? null : date(renewTo);
            if (!AdmUi.text(renewTo).trim().isEmpty() && to == null) return;
            update(licenceId, "ACTIVE", n, to, clear.isChecked(), "Licence renewed / updated.");
        });
        AdmUi.outline(a, box, "Suspend", v -> a.confirm("Suspend licence?", "The company cannot use QCMS until the licence is re-activated.", "Suspend",
            () -> update(licenceId, "SUSPENDED", null, null, false, "Licence suspended.")));
        AdmUi.outline(a, box, "Re-activate", v -> update(licenceId, "ACTIVE", null, null, false, "Licence re-activated."));
        AdmUi.outline(a, box, "Revoke", v -> a.confirm("Revoke licence?", "The key stops working permanently. Issue a new key to restore access.", "Revoke",
            () -> update(licenceId, "REVOKED", null, null, false, "Licence revoked.")));
    }

    private void update(String licenceId, String status, Integer users, String validTo, boolean clear, String done) {
        Api.async(() -> LicService.devUpdateLicence(api, licenceId, status, users, validTo, clear, null), (r, e) -> {
            if (e != null) { a.toast(Api.message(e)); return; }
            a.toast(done + " Status: " + LicService.s(r, "status"));
            reload();
        });
    }

    private String date(EditText e) {
        String t = AdmUi.text(e).trim();
        try { return LocalDate.parse(t).toString(); } catch (Exception ex) { e.setError("Use YYYY-MM-DD"); return null; }
    }

    private void copy(String text) {
        try {
            ClipboardManager cm = (ClipboardManager) a.getSystemService(Context.CLIPBOARD_SERVICE);
            if (cm != null) cm.setPrimaryClip(ClipData.newPlainText("STAWN licence key", text));
        } catch (Exception ignored) { }
    }

    // ---- C new customer company
    private void newCompany() {
        LinearLayout box = AdmUi.section(a, page, "C", "NEW CUSTOMER COMPANY", "Creates the company (tenant). Then issue its licence key and assign its administrator.");
        EditText code = AdmUi.field(a, box, "Company code", "", "ABC");
        EditText name = AdmUi.field(a, box, "Company name", "", null);
        EditText plant = AdmUi.field(a, box, "Plant code", "", null);
        AdmUi.primary(a, box, "Create company", v -> {
            if (AdmUi.text(code).trim().isEmpty()) { code.setError("Required"); return; }
            if (AdmUi.text(name).trim().isEmpty()) { name.setError("Required"); return; }
            Api.async(() -> LicService.devCreateCompany(api, AdmUi.text(code), AdmUi.text(name), AdmUi.text(plant)), (tid, e) -> {
                if (e != null) { a.toast(Api.message(e)); return; }
                a.toast("Company created (" + tid + "). Issue its licence key next.");
                reload();
            });
        });
    }

    // ---- D assign company administrator
    private void assign() {
        LinearLayout box = AdmUi.section(a, page, "D", "ASSIGN COMPANY ADMINISTRATOR",
            "Create the person's login first (Users & Access). This moves that login into the selected company as ADMIN; the company admin then completes the company profile and logo once.");
        if (rows.length() == 0) return;
        EditText email = AdmUi.field(a, box, "Login e-mail", "", "name@company.com");
        email.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        AdmUi.choice(a, box, "Company", indexes(), companyLabels(), String.valueOf(assignIdx), v -> assignIdx = Integer.parseInt(v));
        final String[] role = {"ADMIN"};
        AdmUi.choice(a, box, "Role", AdmUi.listOf(LicService.ASSIGN_ROLES), role[0], v -> role[0] = v);
        AdmUi.primary(a, box, "Assign", v -> {
            String mail = AdmUi.text(email).trim();
            if (!mail.contains("@")) { email.setError("Enter the login e-mail"); return; }
            JSONObject c = company(assignIdx);
            a.confirm("Assign " + role[0] + "?", mail + " will be moved into " + LicService.s(c, "company_name") + " as " + role[0] + ".", "Assign", () ->
                Api.async(() -> LicService.devAssignProfile(api, mail, LicService.s(c, "tenant_id"), role[0]), (r, e) -> {
                    if (e != null) { a.toast(Api.message(e)); return; }
                    a.toast(mail + " is now " + role[0] + " of " + LicService.s(c, "tenant_code") + " · " + LicService.s(c, "company_name") + ".");
                }));
        });
    }

    // ---- F STAWN branding
    private void branding() {
        LinearLayout box = AdmUi.section(a, page, "F", "STAWN QCMS BRANDING (STAWN ONLY)",
            "The product name, icon and developer details are fixed by " + GenCentres.About.COMPANY + ". Company administrators cannot change them; "
                + "their company name and logo appear under the STAWN QCMS name.");
        LinearLayout row = Ui.hbox(a);
        ImageView icon = new ImageView(a);
        icon.setImageResource(R.drawable.stawn_qcms_logo);
        row.addView(icon, new LinearLayout.LayoutParams(dp(64), dp(64)));
        row.addView(Ui.text(a, "  App name: " + GenCentres.About.PRODUCT + " – " + GenCentres.About.TAGLINE
            + "\n  Android / iPhone / iPad: STAWN logo on the left of the top bar; company logo on the right before the user's photo"
            + "\n  App versions are shown only in User details (My Account) and on the About page."
            + "\n  Developer: " + GenCentres.About.COMPANY + " · " + GenCentres.About.EMAIL, 12, Ui.TEXT, false), Ui.weight(1));
        box.addView(row, Ui.matchWrap(a, 6));
    }

    // ---- H login page cover photo (public bucket qcms-public, developer-only write)
    private void loginCover() {
        LinearLayout box = AdmUi.section(a, page, "H", "LOGIN PAGE COVER PHOTO (STAWN ONLY)",
            "Add or replace the photo on the left of the Login page (JPG / PNG, max 5 MB, landscape ~ 1600 × 900 px). Reset to show the default factory photo again.");
        ImageView preview = new ImageView(a);
        preview.setAdjustViewBounds(true);
        preview.setScaleType(ImageView.ScaleType.FIT_CENTER);
        android.widget.TextView caption = Ui.text(a, "Loading the current cover…", 11.5f, Ui.MUTED, false);
        box.addView(preview, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(170)));
        box.addView(caption, Ui.matchWrap(a, 4));
        final boolean[] has = {false};
        Button reset = Ui.outline(a, "Reset to default photo", Ui.ORANGE);
        Runnable loadCover = () -> Api.async(LicService::loginCoverBytes, (bytes, e) -> {
            has[0] = bytes != null;
            Bitmap b = bytes == null ? null : Photos.thumbnail(bytes, 900);
            if (b != null) preview.setImageBitmap(b); else preview.setImageResource(R.drawable.stawn_qcms_logo);
            caption.setText(b != null ? "Current login cover (uploaded) - shown on the website and app Login pages"
                : "Current login cover: default factory photo (website); the app Login page shows the STAWN logo only");
            AdmUi.enable(reset, has[0]);
        });
        loadCover.run();
        AdmUi.primary(a, box, "Choose & save as login cover", v -> a.pickFile("Login cover photo", true, f -> {
            Bitmap pre = BitmapFactory.decodeByteArray(f.data, 0, f.data.length);
            if (pre != null) preview.setImageBitmap(pre);
            caption.setText("Uploading " + f.name + "…");
            Api.async(() -> LicService.uploadLoginCover(api, f), (p, e) -> {
                if (e != null) { a.toast(Api.message(e)); loadCover.run(); return; }
                a.toast("Login page cover photo updated. It shows on the Login page within a minute.");
                LicBrand.refresh(a);
                loadCover.run();
            });
        }));
        reset.setOnClickListener(v -> a.confirm("Reset login cover?", "The Login page shows the default factory photo again.", "Reset", () ->
            Api.async(() -> { LicService.resetLoginCover(api); return true; }, (ok, e) -> {
                a.toast(e != null ? Api.message(e) : "Login page cover reset to the default factory photo.");
                LicBrand.refresh(a);
                loadCover.run();
            })));
        box.addView(reset, Ui.matchWrap(a, 8));
    }

    // ---- G all administration tools
    private void adminTools() {
        LinearLayout box = AdmUi.section(a, page, "G", "ALL ADMINISTRATION TOOLS", "Every admin right in one place for the STAWN developer login.");
        String[][] tools = {
            {"user_access", "Users & Access"}, {"", "Licence, Company & WhatsApp"}, {"system_settings", "System Settings"},
            {"email_server", "Email Server & Notifications"}, {"print_designer", "Print Layout Designer"}, {"master_import", "Master Import"},
            {"employees", "Employees"}, {"records_centre", "Records Centre / Delete"}};
        for (String[] t : tools) {
            if (!t[0].isEmpty() && Catalog.get(t[0]) == null) continue;
            AdmUi.outline(a, box, t[1], v -> {
                if (t[0].isEmpty()) a.push(new LicCompanyScreen(a));
                else a.openModule(t[0]);
            });
        }
    }

    private void purge() {
        LinearLayout box = AdmUi.section(a, page, "", "TRIAL / TEST DATA PURGE",
            "Deletes the selected trial transactions together with EVERY record linked to them in this company only. Master data is never deleted. "
                + "Every row is archived before it is removed.");
        AdmUi.primary(a, box, "Open trial-data purge (STAWN developer only)", v -> a.push(new DevPurgeScreen(a)));
    }
}
