package com.fourstar.qcmsapp;

import android.graphics.Color;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;

/** Settings block shown at the end of the More tab (security, website, sign out, about). */
public final class MoreScreen {
    private MoreScreen() { }

    static void addSettings(MainActivity a, Screen screen, LinearLayout page) {
        Api api = Api.get(a);
        page.addView(Ui.label(a, "Security"), Ui.matchWrap(a, 16));
        LinearLayout box = Ui.card(a);
        Switch bio = new Switch(a);
        bio.setText("Fingerprint / face unlock");
        bio.setTextColor(Ui.TEXT);
        bio.setChecked(a.biometricEnabled());
        bio.setEnabled(a.biometricAvailable());
        bio.setOnCheckedChangeListener((b, on) -> a.setBiometric(on));
        box.addView(bio);
        Switch keep = new Switch(a);
        keep.setText("Keep me signed in on this phone");
        keep.setTextColor(Ui.TEXT);
        keep.setChecked(api.prefs().getBoolean("keep_signed_in", true));
        keep.setOnCheckedChangeListener((b, on) -> api.prefs().edit().putBoolean("keep_signed_in", on).apply());
        box.addView(keep, Ui.matchWrap(a, 8));
        TextView note = Ui.text(a, "The app locks after 15 minutes in the background. Your password is never stored on the phone; the session key is kept in the Android Keystore.", 11.5f, Ui.MUTED, false);
        box.addView(note, Ui.matchWrap(a, 8));
        page.addView(box, Ui.matchWrap(a, 4));

        page.addView(link(a, "Notifications", "Approvals, tasks and updates · WhatsApp alerts", v -> a.push(new NotifScreen(a))), Ui.matchWrap(a, 16));
        page.addView(link(a, "Home overview", "POs awaiting approval, calibrations due, deletion requests", v -> a.push(new HomeScreen(a))), Ui.matchWrap(a, 6));
        page.addView(link(a, "KPI start dashboard", "Quality · Supply Chain · Production · NPD · Management", v -> a.openTab(Catalog.HOME)), Ui.matchWrap(a, 6));
        AdmSettings.addAdminLinks(a, page);
        page.addView(link(a, "About STAWN QCMS", "Version, developer, copyright and licence", v -> a.push(new GenCentres.AboutScreen(a))), Ui.matchWrap(a, 6));
        page.addView(link(a, "Open full QCMS website", "Everything as on the computer", v -> a.openWeb("QCMS", "")), Ui.matchWrap(a, 6));
        page.addView(link(a, "Sign out", "Remove the saved session from this phone",
            v -> a.confirm("Sign out?", "You will need your password to sign in again.", "Sign out", a::signOut)), Ui.matchWrap(a, 14));
        String company = Licence.company(api);
        TextView about = Ui.text(a, "STAWN QCMS app v" + BuildConfig.VERSION_NAME + " · " + (company.isEmpty() ? "Four Star Industries" : company) + "\n" + GenCentres.About.COPYRIGHT + "\nSigned in as " + api.email
            + (api.employeeLabel.isEmpty() ? "" : "\nEmployee " + api.employeeLabel) + (api.role.isEmpty() ? "" : " · " + Ui.pretty(api.role)), 11.5f, Ui.MUTED, false);
        about.setPadding(Ui.dp(a, 4), Ui.dp(a, 18), Ui.dp(a, 4), 0);
        page.addView(about);
    }

    private static View link(MainActivity a, String title, String detail, View.OnClickListener click) {
        LinearLayout card = Ui.card(a);
        LinearLayout row = Ui.hbox(a);
        LinearLayout text = Ui.vbox(a);
        text.addView(Ui.text(a, title, 14, Ui.TEXT, true));
        text.addView(Ui.text(a, detail, 11.5f, Ui.MUTED, false));
        row.addView(text, Ui.weight(1));
        row.addView(Ui.text(a, "›", 24, Ui.TEAL, true));
        card.addView(row);
        Ui.clickable(card, Color.WHITE, Ui.LINE, 14);
        card.setOnClickListener(click);
        return card;
    }
}
