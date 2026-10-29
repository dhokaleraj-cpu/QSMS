package com.fourstar.qcmsapp;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * R39 (website R37 core/module_kpis.py): module infographic KPI groups - RPC qcms_module_kpis(p_department, p_modules)
 * returns groups[] {key, title, icon, route, entry_route, module_key, spark[6], cards[]}; every card opens the records
 * behind its number (KpiDetails.openCard -> qcms_kpi_drilldown, contract mobile/KPI_DRILL_CONTRACT.md).
 * Groups the user cannot view (module_key + core.access can_view, GenUtil.canView) are hidden like on the website.
 * Used on the section tabs (Supply / Quality / Masters / More), the KPI start page and the "Modules" view of KPI Dashboards.
 */
final class KpiModules {
    private KpiModules() { }

    static final String RPC = "qcms_module_kpis";
    static final String[] DEPARTMENTS = {"QUALITY", "SUPPLY_CHAIN", "PRODUCTION", "NPD", "MASTERS"};
    static final String[] DEPARTMENT_NAMES = {"Quality", "Supply Chain", "Production", "NPD / APQP", "Masters"};
    private static final long FRESH_MS = 120_000L;

    private static final Map<String, JSONArray> CACHE = new HashMap<>();
    private static final Map<String, Long> CACHED_AT = new HashMap<>();
    private static final Map<String, Integer> SELECTED = new HashMap<>();
    private static String cacheUser = "";

    static String s(JSONObject o, String k) { return o == null || o.isNull(k) ? "" : o.optString(k, ""); }

    /** Departments of qcms_module_kpis shown on a bottom-navigation tab. */
    static String[] departmentsOfTab(int tab) {
        switch (tab) {
            case Catalog.SUPPLY: return new String[]{"SUPPLY_CHAIN", "PRODUCTION"};
            case Catalog.QUALITY: return new String[]{"QUALITY"};
            case Catalog.MASTERS: return new String[]{"MASTERS"};
            case Catalog.MORE: return new String[]{"NPD"};
            default: return new String[0];
        }
    }

    /** groups[] of qcms_module_kpis ({"groups": [...]}, or [{"groups": [...]}]). Background thread; throws when missing. */
    static JSONArray groupsOf(Object v) {
        if (v instanceof JSONArray) {
            JSONArray arr = (JSONArray) v;
            if (arr.length() > 0 && arr.optJSONObject(0) != null && arr.optJSONObject(0).optJSONArray("groups") != null) return arr.optJSONObject(0).optJSONArray("groups");
            return arr;
        }
        if (v instanceof JSONObject && ((JSONObject) v).optJSONArray("groups") != null) return ((JSONObject) v).optJSONArray("groups");
        return new JSONArray();
    }

    /** Permitted groups of the departments (merged, de-duplicated by key). Background thread. */
    static JSONArray load(Api api, String[] departments) throws Exception {
        JSONArray out = new JSONArray();
        java.util.Set<String> seen = new java.util.HashSet<>();
        for (String d : departments) {
            JSONArray groups = groupsOf(api.rpcValue(RPC, new JSONObject().put("p_department", d).put("p_modules", JSONObject.NULL)));
            for (int i = 0; i < groups.length(); i++) {
                JSONObject g = groups.optJSONObject(i);
                if (g == null || !seen.add(s(g, "key"))) continue;
                String moduleKey = s(g, "module_key");
                if (!moduleKey.isEmpty() && !GenUtil.canView(api, moduleKey)) continue;   // core.access can_view
                if (!g.has("department")) g.put("department", d);
                out.put(g);
            }
        }
        return out;
    }

    /** Cached load (2 min, per user) -> UI callback with the groups; fallback runs when the RPC is missing / empty. */
    static void loadCached(MainActivity a, String cacheKey, String[] departments, java.util.function.Consumer<JSONArray> done, Runnable fallback) {
        Api api = Api.get(a);
        synchronized (CACHE) {
            if (!api.userId.equals(cacheUser)) { CACHE.clear(); CACHED_AT.clear(); cacheUser = api.userId; }
        }
        JSONArray cached = CACHE.get(cacheKey);
        Long at = CACHED_AT.get(cacheKey);
        if (cached != null) done.accept(cached);
        if (cached != null && at != null && System.currentTimeMillis() - at < FRESH_MS) return;
        Api.async(() -> load(api, departments), (groups, err) -> {
            if (err != null || groups == null || groups.length() == 0) {
                if (cached == null && fallback != null) fallback.run();
                return;
            }
            CACHE.put(cacheKey, groups);
            CACHED_AT.put(cacheKey, System.currentTimeMillis());
            done.accept(groups);
        });
    }

    // ================================================================== section tabs / start page
    /** Section tab: chips per module + the selected module's KPI cards (website: one tab per module when > 3). */
    static void fillTab(MainActivity a, LinearLayout holder, int tab, Runnable fallback) {
        String[] depts = departmentsOfTab(tab);
        if (depts.length == 0) return;
        loadCached(a, "tab" + tab, depts, groups -> compact(a, holder, groups, "tab" + tab, null), fallback);
    }

    /** KPI start page: the department's module groups (fallback: qcms_module_cards strip). */
    static void fillDepartment(MainActivity a, LinearLayout holder, String department, Runnable onTap, Runnable fallback) {
        loadCached(a, "dept" + department, new String[]{department}, groups -> compact(a, holder, groups, "dept" + department, onTap), fallback);
    }

    /** Header + module chips + the chosen group's cards. */
    static void compact(MainActivity a, LinearLayout holder, JSONArray groups, String selKey, Runnable onTap) {
        holder.removeAllViews();
        if (groups.length() == 0) return;
        holder.addView(Ui.text(a, "Module KPIs · tap a card for its records", 12.5f, Ui.TEAL_DARK, true));
        Integer sel = SELECTED.get(selKey);
        int chosen = sel == null || sel >= groups.length() ? 0 : sel;
        if (groups.length() > 1) {
            List<String> labels = new ArrayList<>();
            for (int i = 0; i < groups.length(); i++) labels.add(chipLabel(groups.optJSONObject(i)));
            holder.addView(GenUtil.chips(a, labels, chosen, i -> {
                SELECTED.put(selKey, i);
                if (onTap != null) onTap.run();
                compact(a, holder, groups, selKey, onTap);
            }), Ui.matchWrap(a, 6));
        }
        holder.addView(groupView(a, groups.optJSONObject(chosen), onTap), Ui.matchWrap(a, 6));
    }

    static String chipLabel(JSONObject g) {
        int alerts = 0;
        JSONArray cards = g == null ? null : g.optJSONArray("cards");
        for (int i = 0; cards != null && i < cards.length(); i++) {
            JSONObject c = cards.optJSONObject(i);
            String tone = s(c, "tone");
            if (("critical".equals(tone) || "warning".equals(tone)) && c.optDouble("value", 0) > 0) alerts++;
        }
        String icon = s(g, "icon");
        return (icon.isEmpty() ? "" : icon + " ") + s(g, "title") + (alerts > 0 ? " · " + alerts + "⚠" : "");
    }

    /** One module: header (icon, title, 6-month trend), its KPI cards (tap = records), Register / New links. */
    static View groupView(MainActivity a, JSONObject g, Runnable onTap) {
        LinearLayout box = Ui.vbox(a);
        if (g == null) return box;
        LinearLayout head = Ui.hbox(a);
        head.setGravity(Gravity.CENTER_VERTICAL);
        String icon = s(g, "icon");
        head.addView(Ui.text(a, (icon.isEmpty() ? "" : icon + "  ") + s(g, "title"), 14, Ui.TEXT, true), Ui.weight(1));
        head.addView(Ui.text(a, "6-month trend ", 10.5f, Ui.MUTED, false));
        head.addView(new Spark(a, g.optJSONArray("spark")), new LinearLayout.LayoutParams(Ui.dp(a, 84), Ui.dp(a, 26)));
        box.addView(head);
        JSONArray cards = g.optJSONArray("cards");
        if (cards == null || cards.length() == 0) {
            box.addView(Ui.text(a, "No KPIs available for this module yet.", 12, Ui.MUTED, false), Ui.matchWrap(a, 4));
        } else {
            String dept = s(g, "department");
            HorizontalScrollView hs = new HorizontalScrollView(a);
            hs.setHorizontalScrollBarEnabled(false);
            LinearLayout row = Ui.hbox(a);
            row.setPadding(0, Ui.dp(a, 2), Ui.dp(a, 6), Ui.dp(a, 4));
            for (int i = 0; i < cards.length(); i++) {
                JSONObject c = cards.optJSONObject(i);
                if (c == null) continue;
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(Ui.dp(a, 168), ViewGroup.LayoutParams.WRAP_CONTENT);
                lp.rightMargin = Ui.dp(a, 8);
                row.addView(KpiDetails.moduleCard(a, c, dept, onTap), lp);
            }
            hs.addView(row);
            box.addView(hs, Ui.matchWrap(a, 6));
        }
        LinearLayout links = Ui.hbox(a);
        links.setGravity(Gravity.END);
        String route = s(g, "route"), entry = s(g, "entry_route");
        if (!entry.isEmpty()) links.addView(link(a, "＋ New", v -> newEntry(a, entry, s(g, "title"))));
        if (!route.isEmpty()) links.addView(link(a, "Register ›", v -> Notif.open(a, "", "", route, s(g, "title"))));
        box.addView(links);
        return box;
    }

    private static TextView link(MainActivity a, String label, View.OnClickListener click) {
        TextView t = Ui.text(a, label, 12.5f, Ui.TEAL_DARK, true);
        t.setPadding(Ui.dp(a, 10), Ui.dp(a, 6), Ui.dp(a, 4), Ui.dp(a, 2));
        t.setOnClickListener(click);
        return t;
    }

    /** "New" of a module: the native entry screen when the app has one, else the website entry page. */
    static void newEntry(MainActivity a, String entryRoute, String title) {
        String key = Notif.ROUTE_MODULES.get(Notif.cleanRoute(entryRoute));
        Module m = key == null ? null : Catalog.get(key);
        if (m != null && m.canCreate()) a.newRecord(m.key);
        else Notif.open(a, "", "", entryRoute, title);
    }

    // ================================================================== KPI Dashboards · Modules view
    static final class ModulesScreen extends Screen {
        private static int dept = 0;
        private LinearLayout body;

        ModulesScreen(MainActivity a) { super(a); }

        @Override public String title() { return "Module KPIs"; }
        @Override public String subtitle() { return "Every module's KPI cards · tap a card for its records"; }
        @Override public int tab() { return Catalog.MORE; }

        @Override
        public View build() {
            newPage();
            List<String> names = new ArrayList<>();
            for (String n : DEPARTMENT_NAMES) names.add(n);
            add(GenUtil.chips(a, names, dept, i -> { dept = i; a.rebuild(); }), 0);
            body = Ui.vbox(a);
            add(body, 8);
            body.addView(loading());
            String d = DEPARTMENTS[dept];
            loadCached(a, "dept" + d, new String[]{d}, groups -> render(groups), () -> {
                body.removeAllViews();
                body.addView(Ui.empty(a, "Module KPIs need the R37 database update (qcms_module_kpis), or none of these modules is open for your access."));
            });
            return scroll;
        }

        private void render(JSONArray groups) {
            body.removeAllViews();
            if (groups.length() == 0) { body.addView(Ui.empty(a, "No " + DEPARTMENT_NAMES[dept] + " modules available for your access.")); return; }
            for (int i = 0; i < groups.length(); i++) {
                LinearLayout card = Ui.card(a);
                card.addView(groupView(a, groups.optJSONObject(i), null));
                body.addView(card, Ui.matchWrap(a, i == 0 ? 0 : 10));
            }
        }

        @Override public void reload() { CACHE.remove("dept" + DEPARTMENTS[dept]); a.rebuild(); }
    }

    // ================================================================== 6-month sparkline
    static final class Spark extends View {
        private final double[] values;
        private final Paint line = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint dot = new Paint(Paint.ANTI_ALIAS_FLAG);

        Spark(Context c, JSONArray spark) {
            super(c);
            int n = spark == null ? 0 : spark.length();
            values = new double[n];
            for (int i = 0; i < n; i++) values[i] = spark.optDouble(i, 0);
            float d = c.getResources().getDisplayMetrics().density;
            line.setColor(Ui.TEAL);
            line.setStrokeWidth(2 * d);
            dot.setColor(Ui.TEAL_DARK);
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            if (values.length < 2) return;
            float w = getWidth(), h = getHeight(), pad = h * 0.15f;
            double max = 0, min = Double.MAX_VALUE;
            for (double v : values) { max = Math.max(max, v); min = Math.min(min, v); }
            double span = max - min == 0 ? 1 : max - min;
            float px = 0, py = 0;
            for (int i = 0; i < values.length; i++) {
                float x = pad + (w - 2 * pad) * i / (values.length - 1);
                float y = (float) (h - pad - (h - 2 * pad) * (values[i] - min) / span);
                if (i > 0) canvas.drawLine(px, py, x, y, line);
                px = x; py = y;
            }
            canvas.drawCircle(px, py, h * 0.09f, dot);
        }
    }
}
