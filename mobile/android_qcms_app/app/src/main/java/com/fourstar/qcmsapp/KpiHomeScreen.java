package com.fourstar.qcmsapp;

import android.animation.ObjectAnimator;
import android.graphics.Color;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.animation.DecelerateInterpolator;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * R35 KPI start dashboard - the first screen after login (website KPI start page, RPC qcms_kpi_dashboard).
 * Pending tasks first, then number cards and charts (GenChart) per department. Departments switch by
 * themselves every 20 s with a slide + fade animation; tapping a tab pauses that until 60 s without a tap.
 * The previous Home overview stays one tap away ("Home" button / More tab).
 */
final class KpiHomeScreen extends Screen {
    static final String[] DEPARTMENTS = {"QUALITY", "SUPPLY_CHAIN", "PRODUCTION", "NPD", "MANAGEMENT"};
    static final String[] DEPARTMENT_NAMES = {"Quality", "Supply Chain", "Production", "NPD", "Management"};
    static final long AUTO_MS = 20_000L;
    static final long IDLE_MS = 60_000L;
    private static final long FRESH_MS = 2 * 60_000L;
    private static final long ANIM_MS = 450L;

    // per-department cache (shared between rebuilds)
    private static final Map<String, JSONObject> CACHE = new HashMap<>();
    private static final Map<String, Long> CACHED_AT = new HashMap<>();
    private static String cacheUser = "";
    private static int current = 0;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private int generation = 0;
    private long pausedUntil = 0L;
    private FrameLayout stage;
    private View shown;
    private LinearLayout tabsRow;
    private HorizontalScrollView tabsScroll;
    private TextView autoNote;

    KpiHomeScreen(MainActivity a) { super(a); }

    @Override public String title() { return a.greeting(); }
    @Override public String subtitle() {
        String company = Licence.company(api);
        return LocalDate.now().format(DateTimeFormatter.ofPattern("EEE dd MMM yyyy", Locale.ENGLISH)) + (company.isEmpty() ? "" : " · " + company);
    }
    @Override public int tab() { return Catalog.HOME; }

    @Override
    public View build() {
        generation++;
        if (!api.userId.equals(cacheUser)) { CACHE.clear(); CACHED_AT.clear(); cacheUser = api.userId; }
        LinearLayout root = Ui.vbox(a);
        root.setBackgroundColor(Ui.BG);

        // ---- brand header: STAWN QCMS + licensed company, Home overview and refresh
        LinearLayout head = Ui.hbox(a);
        head.setGravity(Gravity.CENTER_VERTICAL);
        head.setPadding(dp(12), dp(10), dp(12), dp(4));
        LinearLayout brand = Ui.vbox(a);
        brand.addView(Ui.text(a, "STAWN QCMS · KPI dashboard", 15, Ui.TEAL_DARK, true));
        String company = Licence.company(api);
        if (!company.isEmpty()) brand.addView(Ui.text(a, company, 11.5f, Ui.MUTED, false));
        head.addView(brand, Ui.weight(1));
        Button home = Ui.outline(a, "⌂ Home", Ui.TEAL);
        home.setTextSize(12);
        home.setOnClickListener(v -> a.push(new HomeScreen(a)));
        head.addView(home, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(40)));
        Button refresh = Ui.outline(a, "↻", Ui.TEAL);
        refresh.setOnClickListener(v -> refresh());
        LinearLayout.LayoutParams rlp = new LinearLayout.LayoutParams(dp(48), dp(40));
        rlp.leftMargin = dp(6);
        head.addView(refresh, rlp);
        root.addView(head, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        // ---- department tabs
        tabsScroll = new HorizontalScrollView(a);
        tabsScroll.setHorizontalScrollBarEnabled(false);
        tabsRow = Ui.hbox(a);
        tabsRow.setPadding(dp(12), dp(6), dp(12), dp(2));
        for (int i = 0; i < DEPARTMENTS.length; i++) {
            final int index = i;
            TextView chip = Ui.text(a, DEPARTMENT_NAMES[i], 12.5f, Ui.TEXT, false);
            chip.setPadding(dp(14), dp(8), dp(14), dp(8));
            chip.setOnClickListener(v -> { pauseAuto(); show(index, index > current); });
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            lp.rightMargin = dp(6);
            tabsRow.addView(chip, lp);
        }
        tabsScroll.addView(tabsRow);
        root.addView(tabsScroll, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        autoNote = Ui.text(a, "", 10.5f, Ui.MUTED, false);
        autoNote.setPadding(dp(14), dp(2), dp(14), dp(2));
        root.addView(autoNote);

        // ---- animated stage
        stage = new FrameLayout(a);
        stage.setClipChildren(true);
        root.addView(stage, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        shown = null;
        show(current, true);
        scheduleAuto();
        return root;
    }

    // ------------------------------------------------------------------ auto advance
    private boolean alive(int gen) { return gen == generation && a.isTop(this) && a.isForeground(); }

    private void scheduleAuto() {
        final int gen = generation;
        handler.postDelayed(new Runnable() {
            @Override public void run() {
                if (gen != generation || !a.isTop(KpiHomeScreen.this)) return;    // screen left or rebuilt: stop
                if (a.isForeground() && System.currentTimeMillis() >= pausedUntil) show((current + 1) % DEPARTMENTS.length, true);
                updateAutoNote();
                handler.postDelayed(this, AUTO_MS);
            }
        }, AUTO_MS);
        updateAutoNote();
    }

    private void pauseAuto() {
        pausedUntil = System.currentTimeMillis() + IDLE_MS;
        updateAutoNote();
        final int gen = generation;
        handler.postDelayed(() -> { if (alive(gen)) updateAutoNote(); }, IDLE_MS + 200);
    }

    private void updateAutoNote() {
        if (autoNote == null) return;
        boolean paused = System.currentTimeMillis() < pausedUntil;
        autoNote.setText(paused ? "Auto-switch paused · resumes after 60 s without a tap" : "Departments switch every 20 s · tap a tab to stay");
    }

    // ------------------------------------------------------------------ department pages
    private void markTabs() {
        for (int i = 0; i < tabsRow.getChildCount(); i++) {
            TextView chip = (TextView) tabsRow.getChildAt(i);
            boolean on = i == current;
            chip.setTextColor(on ? Color.WHITE : Ui.TEXT);
            chip.setTypeface(on ? android.graphics.Typeface.DEFAULT_BOLD : android.graphics.Typeface.DEFAULT);
            chip.setBackground(on ? Ui.round(Ui.TEAL, 0, 0, 16, a) : Ui.round(Color.WHITE, Ui.LINE_STRONG, 1, 16, a));
        }
        final View sel = tabsRow.getChildAt(current);
        if (sel != null) tabsScroll.post(() -> tabsScroll.smoothScrollTo(Math.max(0, sel.getLeft() - dp(12)), 0));
    }

    /** Builds the page of one department and slides / fades it in. */
    private void show(int index, boolean forward) {
        current = index;
        markTabs();
        ScrollView sv = new ScrollView(a);
        sv.setFillViewport(true);
        LinearLayout body = Ui.vbox(a);
        body.setPadding(dp(12), dp(6), dp(12), dp(96));
        sv.addView(body);
        sv.setOnTouchListener((v, e) -> { if (e.getAction() == android.view.MotionEvent.ACTION_DOWN && System.currentTimeMillis() < pausedUntil) pauseAuto(); return false; });

        String dept = DEPARTMENTS[index];
        JSONObject cached = CACHE.get(dept);
        Long at = CACHED_AT.get(dept);
        if (cached != null) render(body, cached);
        else body.addView(loading());
        if (cached == null || at == null || System.currentTimeMillis() - at > FRESH_MS) load(dept, body, cached == null);

        View old = shown;
        shown = sv;
        stage.addView(sv, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        if (old == null) return;
        float w = stage.getWidth() > 0 ? stage.getWidth() : a.getResources().getDisplayMetrics().widthPixels;
        float dir = forward ? 1f : -1f;
        sv.setTranslationX(dir * w * 0.35f);
        sv.setAlpha(0f);
        ObjectAnimator inX = ObjectAnimator.ofFloat(sv, "translationX", dir * w * 0.35f, 0f);
        ObjectAnimator inA = ObjectAnimator.ofFloat(sv, "alpha", 0f, 1f);
        ObjectAnimator outX = ObjectAnimator.ofFloat(old, "translationX", 0f, -dir * w * 0.35f);
        ObjectAnimator outA = ObjectAnimator.ofFloat(old, "alpha", 1f, 0f);
        for (ObjectAnimator an : new ObjectAnimator[]{inX, inA, outX, outA}) {
            an.setDuration(ANIM_MS);
            an.setInterpolator(new DecelerateInterpolator());
            an.start();
        }
        handler.postDelayed(() -> stage.removeView(old), ANIM_MS + 50);
    }

    private void load(String dept, LinearLayout body, boolean showError) {
        Api.async(() -> api.rpcObject("qcms_kpi_dashboard", new JSONObject().put("p_department", dept)), (res, err) -> {
            if (err != null) {
                if (showError) { body.removeAllViews(); body.addView(error(err, this::refresh)); }
                return;
            }
            CACHE.put(dept, res);
            CACHED_AT.put(dept, System.currentTimeMillis());
            if (DEPARTMENTS[current].equals(dept) && body.isAttachedToWindow()) { body.removeAllViews(); render(body, res); }
        });
    }

    private void refresh() {
        CACHE.clear();
        CACHED_AT.clear();
        pauseAuto();
        if (stage != null) { stage.removeAllViews(); shown = null; show(current, true); }
        a.refreshBell();
    }

    @Override public void reload() { refresh(); }

    private static String s(JSONObject o, String k) { return o == null || o.isNull(k) ? "" : o.optString(k, ""); }

    private void render(LinearLayout body, JSONObject d) {
        String dept = s(d, "department");
        TextView title = Ui.text(a, (dept.isEmpty() ? DEPARTMENT_NAMES[current] : GenUtil.title(dept.replace('_', ' ').toLowerCase(Locale.ROOT))).toUpperCase(Locale.ROOT), 13, Ui.TEAL_DARK, true);
        title.setLetterSpacing(0.04f);
        body.addView(title, Ui.matchWrap(a, 4));

        // ---- pending tasks first
        JSONArray tasks = d.optJSONArray("pending_tasks");
        LinearLayout taskCard = Ui.card(a);
        int n = tasks == null ? 0 : tasks.length();
        LinearLayout th = Ui.hbox(a);
        th.setGravity(Gravity.CENTER_VERTICAL);
        th.addView(Ui.text(a, "Pending tasks", 14, Ui.TEXT, true), Ui.weight(1));
        th.addView(Ui.chip(a, String.valueOf(n), n > 0 ? "amber" : "green"));
        taskCard.addView(th);
        if (n == 0) {
            TextView ok = Ui.text(a, "Nothing is waiting for you. ✓", 13, Ui.GREEN_FG, false);
            ok.setPadding(0, dp(8), 0, dp(2));
            taskCard.addView(ok);
        }
        for (int i = 0; i < Math.min(n, 12); i++) {
            JSONObject t = tasks.optJSONObject(i);
            if (t == null) continue;
            LinearLayout row = Ui.hbox(a);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(0, dp(9), 0, dp(9));
            LinearLayout text = Ui.vbox(a);
            text.addView(Ui.text(a, s(t, "title"), 13, Ui.TEXT, true));
            String due = s(t, "due");
            String mod = s(t, "module_key");
            String detail = (mod.isEmpty() ? "" : Ui.pretty(mod)) + (due.isEmpty() ? "" : (mod.isEmpty() ? "" : " · ") + "Due " + Ui.date(due));
            if (!detail.isEmpty()) text.addView(Ui.text(a, detail, 11.5f, Ui.MUTED, false));
            row.addView(text, Ui.weight(1));
            row.addView(Ui.text(a, "›", 22, Ui.TEAL, true));
            row.setOnClickListener(v -> { pauseAuto(); Notif.open(a, "", s(t, "related_id"), s(t, "web_route"), s(t, "title")); });
            taskCard.addView(Ui.divider(a));
            taskCard.addView(row);
        }
        if (n > 12) taskCard.addView(Ui.text(a, "+ " + (n - 12) + " more", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 4));
        body.addView(taskCard, Ui.matchWrap(a, 8));

        // ---- number cards
        JSONArray cards = d.optJSONArray("cards");
        List<View> tiles = new ArrayList<>();
        for (int i = 0; cards != null && i < cards.length(); i++) {
            JSONObject c = cards.optJSONObject(i);
            if (c == null) continue;
            String unit = s(c, "unit");
            String value = s(c, "value");
            try { value = GenChart.fmt(Double.parseDouble(value)); } catch (Exception ignored) { }
            View tile = GenUtil.tile(a, "", s(c, "label"), value + (unit.isEmpty() ? "" : " " + unit), "", status(s(c, "tone")));
            String route = s(c, "route");
            if (!route.isEmpty()) tile.setOnClickListener(v -> { pauseAuto(); Notif.open(a, "", "", route, s(c, "label")); });
            tiles.add(tile);
        }
        if (!tiles.isEmpty()) GenUtil.grid2(a, body, tiles, 12);

        // ---- charts
        JSONArray charts = d.optJSONArray("charts");
        for (int i = 0; charts != null && i < charts.length(); i++) {
            JSONObject c = charts.optJSONObject(i);
            if (c == null) continue;
            GenKpi.Chart chart = chart(c);
            LinearLayout card = Ui.card(a);
            card.addView(Ui.text(a, chart.title, 13.5f, Ui.TEXT, true));
            if (chart.isEmpty()) card.addView(Ui.text(a, "No data", 12, Ui.MUTED, false), Ui.matchWrap(a, 6));
            else card.addView(new GenChart(a, chart), Ui.matchWrap(a, 8));
            body.addView(card, Ui.matchWrap(a, 12));
        }
        if (tiles.isEmpty() && (charts == null || charts.length() == 0)) {
            body.addView(Ui.empty(a, "No KPI numbers for this department yet."), Ui.matchWrap(a, 12));
        }
        Button all = Ui.outline(a, "All KPI dashboards", Ui.TEAL);
        all.setOnClickListener(v -> a.push(new GenKpiScreen(a)));
        body.addView(all, Ui.matchWrap(a, 14));
    }

    /** Server chart JSON -> GenKpi.Chart (donut is drawn as GenChart's share view). */
    static GenKpi.Chart chart(JSONObject c) {
        String type = s(c, "type").toLowerCase(Locale.ROOT);
        String kind = type.equals("line") ? "line" : (type.equals("donut") || type.equals("pie")) ? "pie" : "bar";
        GenKpi.Chart chart = new GenKpi.Chart(s(c, "title"), kind, "");
        JSONArray labels = c.optJSONArray("labels");
        for (int i = 0; labels != null && i < labels.length(); i++) chart.cats.add(labels.isNull(i) ? "" : labels.optString(i, ""));
        JSONArray series = c.optJSONArray("series");
        chart.dataHeaders.add("Label");
        for (int k = 0; series != null && k < series.length(); k++) {
            JSONObject sr = series.optJSONObject(k);
            if (sr == null) continue;
            JSONArray vals = sr.optJSONArray("values");
            double[] v = new double[chart.cats.size()];
            for (int i = 0; i < v.length; i++) v[i] = vals == null || i >= vals.length() || vals.isNull(i) ? 0 : vals.optDouble(i, 0);
            String name = s(sr, "name");
            if (series.length() == 1 && kind.equals("pie")) name = "";
            chart.series.put(name, v);
            chart.dataHeaders.add(name.isEmpty() ? "Value" : name);
        }
        for (int i = 0; i < chart.cats.size(); i++) {
            String[] row = new String[chart.series.size() + 1];
            row[0] = chart.cats.get(i);
            int col = 1;
            for (double[] v : chart.series.values()) row[col++] = GenChart.fmt(v[i]);
            chart.dataRows.add(row);
        }
        return chart;
    }

    static String status(String tone) {
        switch (tone == null ? "" : tone.toLowerCase(Locale.ROOT)) {
            case "good": case "green": case "ok": case "success": return "good";
            case "warning": case "amber": case "warn": case "yellow": return "warning";
            case "serious": case "orange": return "serious";
            case "critical": case "red": case "bad": case "danger": return "critical";
            default: return "neutral";
        }
    }
}
