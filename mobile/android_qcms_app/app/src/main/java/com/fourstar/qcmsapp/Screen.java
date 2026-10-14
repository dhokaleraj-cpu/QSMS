package com.fourstar.qcmsapp;

import android.content.Context;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;

/** One app screen. Screens build plain framework views; MainActivity owns navigation. */
public abstract class Screen {
    protected final MainActivity a;
    protected final Api api;
    protected ScrollView scroll;
    protected LinearLayout page;

    protected Screen(MainActivity activity) {
        this.a = activity;
        this.api = Api.get(activity);
    }

    public abstract String title();
    public String subtitle() { return ""; }
    /** Bottom-navigation tab this screen belongs to (0 Home, 1 Orders, 2 Inspect, 3 Assets, 4 More). */
    public abstract int tab();
    public abstract View build();
    /** Called by the refresh button. */
    public void reload() { a.rebuild(); }
    public boolean onBack() { return false; }

    protected Context c() { return a; }
    protected int dp(float v) { return Ui.dp(a, v); }

    /** Standard scrolling page with 12dp gutters. */
    protected ScrollView newPage() {
        scroll = new ScrollView(a);
        scroll.setFillViewport(true);
        page = Ui.vbox(a);
        page.setPadding(dp(12), dp(10), dp(12), dp(96));
        scroll.addView(page);
        return scroll;
    }

    protected void add(View v) { page.addView(v, Ui.matchWrap(a, 8)); }
    protected void add(View v, int topDp) { page.addView(v, Ui.matchWrap(a, topDp)); }

    protected View loading() {
        LinearLayout box = Ui.vbox(a);
        box.setGravity(Gravity.CENTER);
        box.setPadding(0, dp(40), 0, dp(40));
        ProgressBar bar = new ProgressBar(a);
        box.addView(bar);
        TextView t = Ui.text(a, "Loading…", 12, Ui.MUTED, false);
        t.setGravity(Gravity.CENTER);
        box.addView(t);
        return box;
    }

    protected View error(Exception e, Runnable retry) {
        if (e instanceof Api.ApiException && ((Api.ApiException) e).status == 401) {
            a.sessionExpired();
        }
        LinearLayout card = Ui.card(a);
        TextView title = Ui.text(a, "Could not load", 15, Ui.RED_FG, true);
        card.addView(title);
        TextView msg = Ui.text(a, Api.message(e), 13, Ui.TEXT, false);
        msg.setPadding(0, dp(6), 0, dp(10));
        card.addView(msg);
        if (retry != null) {
            Button b = Ui.outline(a, "Try again", Ui.TEAL);
            b.setOnClickListener(v -> retry.run());
            card.addView(b, Ui.matchWrap(a, 0));
        }
        return card;
    }

    /** Small banner when the data shown came from the offline copy. */
    protected void offlineNote() {
        if (api.lastCallOffline) {
            TextView t = Ui.chip(a, "Offline · showing the last saved data", "amber");
            add(t, 4);
        }
    }
}
