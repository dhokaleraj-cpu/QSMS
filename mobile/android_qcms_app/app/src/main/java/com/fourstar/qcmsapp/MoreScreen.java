package com.fourstar.qcmsapp;

import android.graphics.Color;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;

/** More: Part Master viewer, other QCMS modules, settings and sign out. */
public final class MoreScreen extends Screen {
    public MoreScreen(MainActivity a) { super(a); }

    @Override public String title() { return "More"; }
    @Override public String subtitle() { return api.fullName.isEmpty() ? api.email : api.fullName + " · " + Ui.pretty(api.role); }
    @Override public int tab() { return 4; }

    @Override
    public View build() {
        newPage();
        add(Ui.label(a, "Masters & reports"), 0);
        add(link("Part Master · Raw Material details", "Search a Part and see its RM rows in a scrollable grid", v -> a.push(new PartRmScreen(a))), 4);
        add(link("Global search", "Search every QCMS record", v -> a.openWeb("Global search", "global-search")));
        add(link("KPI dashboards", "All QCMS KPIs", v -> a.openWeb("KPI dashboards", "kpi-dashboards")));
        add(link("Records centre", "Record history, deleted records, deletion requests", v -> a.openWeb("Records", "records-center")));
        add(link("Reports", "PDF / Excel reports", v -> a.openWeb("Reports", "reports-home")));
        add(link("Open full QCMS website", "Every module, inside the app", v -> a.openWeb("QCMS", "")));

        add(Ui.label(a, "Security"), 14);
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
        add(box, 4);

        add(link("Sign out", "Remove the saved session from this phone", v -> a.confirm("Sign out?", "You will need your password to sign in again.", "Sign out", a::signOut)), 14);
        TextView about = Ui.text(a, "QCMS app v" + BuildConfig.VERSION_NAME + " · Four Star Industries\nSigned in as " + api.email, 11.5f, Ui.MUTED, false);
        about.setPadding(dp(4), dp(18), dp(4), 0);
        add(about);
        return scroll;
    }

    private View link(String title, String detail, View.OnClickListener click) {
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
