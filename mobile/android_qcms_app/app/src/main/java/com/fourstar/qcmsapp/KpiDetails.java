package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.graphics.Color;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;

/**
 * R37 (app v3.5.0): KPI drill-down and quick actions.
 * - KPI card / module infographic card -> list of the records behind the number (RPC qcms_kpi_records);
 *   a row opens the record natively (Notif.open: record screen, else module, else website page).
 * - Module infographic cards strip per department (RPC qcms_module_cards).
 * - Top-bar "+" quick actions: New transaction, New e-mail, New query / AI.
 * - Print PDF of any record (dedicated print layout, Universal Record PDF fallback): Preview / Save / Share.
 * Every RPC is optional: when it is missing or fails the app falls back to opening the module.
 */
final class KpiDetails {
    private KpiDetails() { }

    static String s(JSONObject o, String k) { return o == null || o.isNull(k) ? "" : o.optString(k, ""); }

    // ================================================================== open a card
    /** Opens the records list behind a KPI card; without a key the card's module / website route opens. */
    static void openCard(MainActivity a, String key, String department, String label, String route) {
        if (key == null || key.trim().isEmpty()) {
            if (route != null && !route.trim().isEmpty()) Notif.open(a, "", "", route, label);
            else a.toast("No details for this card.");
            return;
        }
        a.push(new KpiRecordsScreen(a, key.trim(), department, label, route));
    }

    /**
     * Opens a server KPI card: a "drill" object ({"table", "filter", "title"}) wins, then the card key
     * (qcms_kpi_records), then a key derived from the label (older databases), then the route.
     */
    static void openCard(MainActivity a, JSONObject card, String department) {
        String label = s(card, "label");
        if (label.isEmpty()) label = s(card, "title");
        String route = s(card, "route");
        JSONObject drill = card == null ? null : card.optJSONObject("drill");
        if (drill != null && !s(drill, "table").isEmpty()) { openDrill(a, drill, label, route); return; }
        if (drill != null && (!s(drill, "key").isEmpty() || !s(drill, "rpc").isEmpty())) {
            // R39: R37 drill contract (mobile/KPI_DRILL_CONTRACT.md): qcms_kpi_drilldown(p_card_key) + open_route
            JSONObject args = drill.optJSONObject("args");
            String dk = s(drill, "key").isEmpty() && args != null ? s(args, "p_card_key") : s(drill, "key");
            String open = s(drill, "open_route").isEmpty() ? route : s(drill, "open_route");
            String title = s(drill, "title").isEmpty() ? label : s(drill, "title");
            openCard(a, dk.isEmpty() ? s(card, "key") : dk, department, title, open);
            return;
        }
        String key = s(card, "key");
        if (key.isEmpty()) key = keyForLabel(label);
        openCard(a, key, department, label, route);
    }

    /** Generic drill: PostgREST rows of drill.table filtered by drill.filter; a row opens the record. */
    static void openDrill(MainActivity a, JSONObject drill, String label, String route) {
        String title = s(drill, "title");
        KpiRecordsScreen s = new KpiRecordsScreen(a, "", "", title.isEmpty() ? label : title, route);
        s.drillTable = s(drill, "table");
        s.drillFilter = drill.optJSONObject("filter");
        a.push(s);
    }

    /** Card key of a KPI label (same list as the R37 migration) - for dashboards returned without keys. */
    static String keyForLabel(String label) {
        String l = label == null ? "" : label.trim().toLowerCase(Locale.ROOT);
        if (l.isEmpty()) return "";
        String[][] map = {
            {"inward on quality hold", "inward_hold"}, {"metlab pending", "metlab_pending"}, {"bend test pending", "bend_pending"},
            {"dimensional pending", "dimensional_pending"}, {"reports finalized this month", "reports_final_month"},
            {"rejection (180 days)", "rejection_180d"}, {"rmtc pending", "rmtc_pending"}, {"complaints open", "complaints_open"},
            {"calibration overdue", "calibration_overdue"}, {"calibration due ≤ 30 days", "calibration_due_30"},
            {"open customer orders", "customer_orders_open"}, {"open order quantity", "customer_order_qty_open"},
            {"po pending approval", "po_pending_approval"}, {"open purchase orders", "po_open"}, {"rm on order", "rm_on_order"},
            {"rm received this month", "rm_received_month"}, {"forging orders open", "forging_orders_open"},
            {"dispatched this month", "dispatched_month"}, {"pieces available in batches", "batch_pcs_available"},
            {"active production batches", "batches_active"}, {"osp at vendor", "osp_at_vendor"}, {"osp sample pending", "osp_sample_pending"},
            {"osp receipt quality pending", "osp_receipt_pending"}, {"machined this month", "machined_month"},
            {"finished goods this month", "fg_month"}, {"npd open", "npd_open"}, {"npd in progress", "npd_in_progress"}, {"npd late", "npd_late"},
            {"apqp / ppap active", "apqp_active"}, {"apqp average completion", "apqp_completion"}, {"npd steps open", "npd_steps_open"},
            {"npd steps overdue", "npd_steps_overdue"}, {"first-pass yield (final reports)", "fpy_final_reports"},
            {"open po value", "po_open_value"}, {"heats released this month", "heats_released_month"}};
        for (String[] m : map) if (m[0].equals(l)) return m[1];
        return "";
    }

    /**
     * Client-side drill when the qcms_kpi_records RPC is missing / failing: {table, PostgREST filter}.
     * Mirrors the R37 migration for the Quality cards (status filters of the module registers).
     */
    static String[] fallbackDrill(String key) {
        String today = java.time.LocalDate.now().toString();
        String in30 = java.time.LocalDate.now().plusDays(30).toString();
        switch (key == null ? "" : key) {
            case "inward_hold": case "mod_inward": return new String[]{"inward_lots", "status=eq.HOLD_PENDING_INSPECTION"};
            case "metlab_pending": case "mod_metlab": return new String[]{"lab_tests", "status=neq.FINAL&or=(results->>inspection_method.is.null,results->>inspection_method.neq.BEND_TEST)"};
            case "bend_pending": case "mod_bend": return new String[]{"lab_tests", "status=neq.FINAL&results->>inspection_method=eq.BEND_TEST"};
            case "dimensional_pending": case "mod_dimensional": return new String[]{"inspection_reports", "status=neq.FINAL"};
            case "rmtc_pending": case "mod_rmtc": return new String[]{"rmtc_approvals", "status=not.in.(APPROVED,REJECTED,CANCELLED)"};
            case "complaints_open": return new String[]{"quality_complaints", "status=not.in.(CLOSED,CANCELLED)"};
            case "mod_customer_complaints": return new String[]{"quality_complaints", "status=not.in.(CLOSED,CANCELLED)&complaint_type=eq.CUSTOMER"};
            case "mod_supplier_complaints": return new String[]{"quality_complaints", "status=not.in.(CLOSED,CANCELLED)&complaint_type=eq.SUPPLIER"};
            case "calibration_overdue": return new String[]{"quality_assets", "or=(next_due_date.lt." + today + ",next_validation_due_date.lt." + today + ")"};
            case "calibration_due_30": case "mod_calibration": return new String[]{"quality_assets", "or=(and(next_due_date.gte." + today + ",next_due_date.lte." + in30 + "),and(next_validation_due_date.gte." + today + ",next_validation_due_date.lte." + in30 + "))"};
            case "npd_open": return new String[]{"npd_orders", "status=eq.OPEN"};
            case "npd_in_progress": return new String[]{"npd_orders", "status=eq.IN_PROGRESS"};
            default: return null;
        }
    }

    /** drill.filter {"col": "eq.X" | "X" | ["A","B"], "or": "(...)"} -> PostgREST query string. */
    static String filterQuery(JSONObject filter) {
        StringBuilder q = new StringBuilder();
        if (filter == null) return "";
        for (Iterator<String> it = filter.keys(); it.hasNext(); ) {
            String col = it.next();
            Object v = filter.opt(col);
            String expr;
            if (v instanceof JSONArray) {
                JSONArray arr = (JSONArray) v;
                StringBuilder b = new StringBuilder();
                for (int i = 0; i < arr.length(); i++) { if (i > 0) b.append(','); b.append(arr.optString(i, "")); }
                expr = "in.(" + b + ")";
            } else if (v == null || v == JSONObject.NULL) {
                expr = "is.null";
            } else {
                String sv = String.valueOf(v);
                boolean raw = col.equals("or") || col.equals("and")
                    || sv.matches("^(not\\.)?(eq|neq|lt|lte|gt|gte|like|ilike|is|in|cs|cd|fts|plfts|phfts|wfts)\\..*");
                expr = raw ? sv : "eq." + sv;
            }
            q.append('&').append(Api.enc(col)).append('=').append(Api.enc(expr));
        }
        return q.toString();
    }

    /** Generic table row -> the drill-down row shape of qcms_kpi_records. */
    static JSONObject drillRow(String table, JSONObject r) throws Exception {
        JSONObject o = new JSONObject();
        o.put("source_table", table);
        o.put("record_id", s(r, "id"));
        o.put("reference", first(r, "report_number", "report_no", "rmtc_number", "certificate_reference", "inward_number", "grn_number",
            "complaint_number", "po_number", "order_number", "order_no", "asset_code", "asset_number", "plan_number", "reference", "code", "name", "title"));
        o.put("part", first(r, "part_number", "part_no", "fsi_part_number"));
        o.put("party", first(r, "supplier_name", "customer_name", "party_name", "vendor_name"));
        o.put("status", first(r, "status", "inspection_status"));
        o.put("record_date", first(r, "test_date", "inspection_date", "inward_date", "complaint_date", "certificate_date", "next_due_date", "order_date", "created_at"));
        String heat = s(r, "heat_number");
        o.put("detail", first(r, "subject", "asset_name", "layout_name", "description") + (heat.isEmpty() ? "" : " · Heat " + heat));
        return o;
    }

    private static String first(JSONObject r, String... keys) {
        for (String k : keys) { String v = s(r, k); if (!v.isEmpty()) return v.length() > 10 && v.matches("^\\d{4}-\\d{2}-\\d{2}T.*") ? v.substring(0, 10) : v; }
        return "";
    }

    /** "a=eq.X&or=(..)" -> "&a=eq.X&or=%28..%29" (each name / value URL-encoded). */
    static String encodeQuery(String raw) {
        StringBuilder q = new StringBuilder();
        if (raw == null || raw.isEmpty()) return "";
        for (String part : raw.split("&")) {
            int eq = part.indexOf('=');
            if (eq <= 0) continue;
            q.append('&').append(Api.enc(part.substring(0, eq))).append('=').append(Api.enc(part.substring(eq + 1)));
        }
        return q.toString();
    }

    /** Loads drill rows (runs on a background thread); query is already encoded ("&col=op.value…"). */
    static JSONArray loadDrill(Api api, String table, String query) throws Exception {
        JSONArray raw = api.rows(table + "?select=*" + query + "&limit=500");
        JSONArray out = new JSONArray();
        for (int i = 0; i < raw.length(); i++) {
            JSONObject r = raw.optJSONObject(i);
            if (r != null) out.put(drillRow(table, r));
        }
        return out;
    }

    /** Table of an app module key (pending tasks carry module_key + related_id). */
    static String tableForModuleKey(String moduleKey) {
        if (moduleKey == null || moduleKey.isEmpty()) return "";
        Module m = Catalog.get(moduleKey);
        if (m == null || m.table.isEmpty() || !"id".equals(m.idField) || m.custom != null) return "";
        return m.table;
    }

    // ================================================================== print PDF of any record
    /** Print-layout PDF of one record (View / Download / Print / Email / Share). */
    static void printRecord(MainActivity a, String table, String id, String route) {
        if (table == null || table.isEmpty() || id == null || id.isEmpty() || "null".equals(id)) {
            a.toast("This row has no record to print.");
            return;
        }
        if ("supply_purchase_orders".equals(table)) { SndPdfView.forPo(a, id); return; }
        final Api api = Api.get(a);
        // R39: a detail row prints its parent record (web global search: _resolve_target + record print panel)
        ExportKit.layoutMenu(a, () -> {
            String[] t = GenTarget.resolve(api, table, id);
            return RptReports.forRecord(api, printModule(t[0], t[0].equals(table) ? route : ""), t[1]);
        });
    }

    static Module printModule(String table, String route) {
        Module m = Notif.moduleForTable(table, route);
        if (m == null || !"id".equals(m.idField)) {
            Module byTable = Catalog.forTable(table);
            m = byTable != null && "id".equals(byTable.idField) ? byTable : Catalog.adhoc(table);
        }
        return m;
    }

    /** Long-press menu of a list row: open or print. */
    static void rowMenu(MainActivity a, String title, String table, String id, String route) {
        new AlertDialog.Builder(a).setTitle(title == null || title.isEmpty() ? "Record" : title)
            .setItems(new String[]{"Open record", "Print PDF · Preview / Save / Share"}, (d, w) -> {
                if (w == 0) GenTarget.open(a, table, id, route, title);
                else printRecord(a, table, id, route);
            })
            .setNegativeButton("Close", null).show();
    }

    // ================================================================== module infographic cards
    /** Cards array of qcms_module_cards (plain array or {"cards": [...]}). */
    static JSONArray cardsOf(Object v) {
        if (v instanceof JSONArray) return (JSONArray) v;
        if (v instanceof JSONObject) {
            JSONObject o = (JSONObject) v;
            for (String k : new String[]{"cards", "modules", "items"}) if (o.optJSONArray(k) != null) return o.optJSONArray(k);
        }
        return new JSONArray();
    }

    /** Sub-figures of a card: [{label,value,unit}] or {"label": value}. */
    static List<String[]> subFigures(JSONObject c) {
        List<String[]> out = new ArrayList<>();
        for (String k : new String[]{"sub_figures", "subs", "sub", "figures", "subfigures", "breakdown", "details"}) {
            Object v = c.opt(k);
            if (v instanceof JSONArray) {
                JSONArray arr = (JSONArray) v;
                for (int i = 0; i < arr.length(); i++) {
                    JSONObject f = arr.optJSONObject(i);
                    if (f == null) continue;
                    String label = s(f, "label");
                    if (label.isEmpty()) label = s(f, "title");
                    if (label.isEmpty()) label = s(f, "name");
                    String unit = s(f, "unit");
                    out.add(new String[]{label, fmt(s(f, "value")) + (unit.isEmpty() ? "" : " " + unit)});
                }
                if (!out.isEmpty()) return out;
            } else if (v instanceof JSONObject) {
                JSONObject f = (JSONObject) v;
                for (Iterator<String> it = f.keys(); it.hasNext(); ) {
                    String key = it.next();
                    out.add(new String[]{Ui.pretty(key), fmt(f.optString(key, ""))});
                }
                if (!out.isEmpty()) return out;
            }
        }
        return out;
    }

    static String fmt(String value) {
        try { return GenChart.fmt(Double.parseDouble(value)); } catch (Exception e) { return value; }
    }

    /** Horizontal strip of module infographic cards; each opens the records list. */
    static View moduleStrip(MainActivity a, JSONArray cards, String department, Runnable onTap) {
        HorizontalScrollView hs = new HorizontalScrollView(a);
        hs.setHorizontalScrollBarEnabled(false);
        LinearLayout row = Ui.hbox(a);
        row.setPadding(0, Ui.dp(a, 2), Ui.dp(a, 6), Ui.dp(a, 4));
        for (int i = 0; i < cards.length(); i++) {
            JSONObject c = cards.optJSONObject(i);
            if (c == null) continue;
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(Ui.dp(a, 210), ViewGroup.LayoutParams.WRAP_CONTENT);
            lp.rightMargin = Ui.dp(a, 10);
            row.addView(moduleCard(a, c, department, onTap), lp);
        }
        hs.addView(row);
        return hs;
    }

    private static final java.util.Map<String, JSONArray> SECTION_CACHE = new java.util.HashMap<>();
    private static final java.util.Map<String, Long> SECTION_AT = new java.util.HashMap<>();
    private static String sectionUser = "";

    /** Departments of qcms_module_cards shown on a bottom-navigation tab. */
    static String[] departmentsOfTab(int tab) {
        switch (tab) {
            case Catalog.SUPPLY: return new String[]{"SUPPLY_CHAIN", "PRODUCTION"};
            case Catalog.QUALITY: return new String[]{"QUALITY"};
            case Catalog.MASTERS: return new String[]{"MANAGEMENT"};
            case Catalog.MORE: return new String[]{"NPD"};
            default: return new String[0];
        }
    }

    /**
     * R37: module infographic cards on a section tab (Supply / Quality / Masters / More), one tappable card per
     * module (RPC qcms_module_cards, cached 2 min). Hidden when the RPC is missing - the module list below keeps
     * its PostgREST record counts.
     */
    static void sectionModuleCards(MainActivity a, LinearLayout holder, int tab) {
        // R39: module infographic groups (qcms_module_kpis, R37 contract); the older one-card-per-module strip
        // (qcms_module_cards) stays as the fallback for databases without qcms_module_kpis
        KpiModules.fillTab(a, holder, tab, () -> sectionModuleCardsLegacy(a, holder, tab));
    }

    static void sectionModuleCardsLegacy(MainActivity a, LinearLayout holder, int tab) {
        String[] depts = departmentsOfTab(tab);
        if (depts.length == 0) return;
        Api api = Api.get(a);
        if (!api.userId.equals(sectionUser)) { SECTION_CACHE.clear(); SECTION_AT.clear(); sectionUser = api.userId; }
        String cacheKey = String.valueOf(tab);
        JSONArray cached = SECTION_CACHE.get(cacheKey);
        Long at = SECTION_AT.get(cacheKey);
        if (cached != null) fillSection(a, holder, cached, depts[0]);
        if (cached != null && at != null && System.currentTimeMillis() - at < 120_000L) return;
        Api.async(() -> {
            JSONArray merged = new JSONArray();
            java.util.Set<String> seen = new java.util.HashSet<>();
            for (String d : depts) {
                JSONArray cards = cardsOf(api.rpcValue("qcms_module_cards", new JSONObject().put("p_department", d)));
                for (int i = 0; i < cards.length(); i++) {
                    JSONObject c = cards.optJSONObject(i);
                    if (c == null) continue;
                    String k = s(c, "key").isEmpty() ? s(c, "title") : s(c, "key");
                    if (seen.add(k)) merged.put(c);
                }
            }
            return merged;
        }, (cards, err) -> {
            if (err != null || cards == null) return;
            SECTION_CACHE.put(cacheKey, cards);
            SECTION_AT.put(cacheKey, System.currentTimeMillis());
            fillSection(a, holder, cards, depts[0]);   // harmless when the tab was left meanwhile
        });
    }

    private static void fillSection(MainActivity a, LinearLayout holder, JSONArray cards, String department) {
        holder.removeAllViews();
        if (cards.length() == 0) return;
        holder.addView(Ui.text(a, "Module highlights · tap a card for its records", 12.5f, Ui.TEAL_DARK, true));
        holder.addView(moduleStrip(a, cards, department, null), Ui.matchWrap(a, 6));
    }

    static View moduleCard(MainActivity a, JSONObject c, String department, Runnable onTap) {
        int color = GenUtil.statusColor(KpiHomeScreen.status(s(c, "tone")));
        LinearLayout card = Ui.vbox(a);
        card.setBackground(Ui.round(Color.WHITE, Ui.LINE, 1, 14, a));
        View bar = new View(a);
        bar.setBackground(Ui.round(color, 0, 0, 3, a));
        card.addView(bar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(a, 5)));
        LinearLayout box = Ui.vbox(a);
        box.setPadding(Ui.dp(a, 12), Ui.dp(a, 8), Ui.dp(a, 12), Ui.dp(a, 10));
        String title = s(c, "title");
        if (title.isEmpty()) title = s(c, "label");
        TextView t = Ui.text(a, title.toUpperCase(Locale.ROOT), 10.5f, Ui.MUTED, true);
        t.setSingleLine(true);
        t.setEllipsize(android.text.TextUtils.TruncateAt.END);
        box.addView(t);
        String unit = s(c, "unit");
        LinearLayout val = Ui.hbox(a);
        val.setGravity(Gravity.BOTTOM);
        val.addView(Ui.text(a, fmt(s(c, "value")), 26, Ui.TEXT, true));
        if (!unit.isEmpty()) {
            TextView u = Ui.text(a, " " + unit, 12, Ui.MUTED, false);
            u.setPadding(0, 0, 0, Ui.dp(a, 4));
            val.addView(u);
        }
        box.addView(val);
        List<String[]> subs = subFigures(c);
        for (int i = 0; i < Math.min(subs.size(), 4); i++) {
            LinearLayout line = Ui.hbox(a);
            TextView l = Ui.text(a, subs.get(i)[0], 11.5f, Ui.MUTED, false);
            l.setSingleLine(true);
            l.setEllipsize(android.text.TextUtils.TruncateAt.END);
            line.addView(l, Ui.weight(1));
            line.addView(Ui.text(a, subs.get(i)[1], 11.5f, Ui.TEXT, true));
            box.addView(line);
        }
        TextView more = Ui.text(a, "View records ›", 11.5f, Ui.TEAL_DARK, true);
        more.setPadding(0, Ui.dp(a, 6), 0, 0);
        box.addView(more);
        card.addView(box);
        card.setOnClickListener(v -> {
            if (onTap != null) onTap.run();
            openCard(a, c, department);   // drill object, card key, label key or the module route
        });
        return card;
    }

    // ================================================================== "+" quick actions
    /** label, app module key, website route (used when the module is not in the app), permission module key. */
    static final String[][] TRANSACTIONS = {
        {"RMTC entry", "rmtc", "rmtc-entry", "RMTC_ENTRY"},
        {"Material inward", "inward", "inward-entry", "MATERIAL_INWARD"},
        {"Dimensional report", "dimensional_reports", "dimensional-entry", "DIMENSIONAL_REPORT"},
        {"MetLAB report", "metlab_reports", "metlab-entry", "METLAB_REPORT"},
        {"Bend test report", "bend_tests", "bend-test-entry", "METLAB_REPORT"},
        {"Inspection layout", "inspection_layouts", "inspection-layout-entry", "INSPECTION_LAYOUTS"},
        {"OSP material out", "osp_material_out", "osp-material-out", "OSP_TRANSACTIONS"},
        {"OSP material inward", "osp_receipts", "osp-inward", "OSP_TRANSACTIONS"},
        {"OSP sample receipt", "", "osp-sample-receipt", "OSP_TRANSACTIONS"},
        {"Customer complaint", "customer_complaints", "customer-complaint", "COMPLAINT_MANAGEMENT"},
        {"Supplier complaint", "supplier_complaints", "supplier-complaint", "COMPLAINT_MANAGEMENT"},
        {"Calibration / validation", "calibration_records", "calibration-validation", "CALIBRATION_VALIDATION"},
        {"Standard room inspection", "standard_room", "standard-room-inspection", "CALIBRATION_VALIDATION"},
        {"Purchase order", "purchase_orders", "supply-purchase-orders", "SUPPLY_CHAIN"},
        // R39 (core/quick_add.py): indirect purchase + RM procurement (app module found by route when present)
        {"Indirect PO", "", "indirect-po", "SUPPLY_CHAIN"},
        {"Indirect requisition", "", "indirect-requisition", "SUPPLY_CHAIN"},
        {"RM procurement", "rm_po_stages", "supply-rm-procurement", "SUPPLY_CHAIN"},
        {"Customer order", "customer_orders", "supply-customer-orders", "SUPPLY_CHAIN"},
        {"RM receipt", "rm_receipts", "supply-rm-receipt", "SUPPLY_CHAIN"},
        {"RM dispatch", "rm_dispatches", "supply-rm-dispatch", "SUPPLY_CHAIN"},
        {"Forging order", "forging_orders", "supply-forging", "SUPPLY_CHAIN"},
        {"Downstream event", "downstream_events", "supply-downstream", "SUPPLY_CHAIN"},
        {"NPD order", "npd_orders", "npd-status", "NPD_APQP"},
        {"APQP project", "apqp_projects", "apqp", "NPD_APQP"},
        {"QC calculation", "qc_calculations", "qc-tools", "QC_CALCULATION_TOOLS"},
    };

    static void quickActions(MainActivity a) {
        String[] items = {"＋ New transaction", "✉ New e-mail", "🔍 New query (global search)", "✦ Ask QCMS AI (Search & AI)", "▦ New dashboard (My Dashboards)"};
        new AlertDialog.Builder(a).setTitle("Quick actions")
            .setItems(items, (d, w) -> {
                switch (w) {
                    case 0: newTransaction(a); break;
                    case 1: newEmail(a); break;
                    case 2: a.push(GenSearchScreen.newQuery(a)); break;   // empty query, keyboard up
                    case 4: a.push(new GenDashScreen(a)); break;            // R39: web "+" → New dashboard
                    default: a.openSearchAi();
                }
            })
            .setNegativeButton("Close", null).show();
    }

    /** Create screens the user may use: module Create permission (core.access.module_permissions) is checked first. */
    static void newTransaction(MainActivity a) {
        Api api = Api.get(a);
        a.toast("Checking your permissions…");
        Api.async(() -> {
            java.util.Map<String, Boolean> cache = new java.util.HashMap<>();
            List<String[]> allowed = new ArrayList<>();
            for (String[] t : TRANSACTIONS) {
                String perm = t[3];
                if (!perm.isEmpty()) {
                    Boolean ok = cache.get(perm);
                    if (ok == null) { ok = GenUtil.permissions(api, perm).optBoolean("can_create", false); cache.put(perm, ok); }
                    if (!ok) continue;
                }
                allowed.add(t);
            }
            return allowed;
        }, (list, err) -> {
            if (err != null || list == null) { a.toast("Could not read your permissions: " + Api.message(err)); return; }
            if (list.isEmpty()) {
                new AlertDialog.Builder(a).setTitle("New transaction")
                    .setMessage("You do not have Create permission on any QCMS transaction. Ask the QCMS Administrator for access.")
                    .setPositiveButton("OK", null).show();
                return;
            }
            List<String> labels = new ArrayList<>();
            for (String[] t : list) {
                Module m = moduleOf(t);
                labels.add(t[0] + (m == null || !m.canCreate() ? "  (website form)" : ""));
            }
            new AlertDialog.Builder(a).setTitle("New transaction")
                .setItems(labels.toArray(new String[0]), (d, w) -> {
                    String[] t = list.get(w);
                    Module m = moduleOf(t);
                    if (m != null) a.newRecord(m.key);
                    else Notif.open(a, "", "", t[2], t[0]);   // website entry page (no native module)
                })
                .setNegativeButton("Back", null).show();
        });
    }

    /** App module of a quick action: its key, else the module registered for its website route. */
    static Module moduleOf(String[] t) {
        String key = t[1].isEmpty() ? Notif.ROUTE_MODULES.get(t[2]) : t[1];
        return key == null ? null : Catalog.get(key);
    }

    static void newEmail(MainActivity a) {
        if (Catalog.get("email_send") != null) a.openModule("email_send");
        else Notif.open(a, "", "", "email-send", "Send Email");
    }

    // ================================================================== records behind a KPI number
    static final class KpiRecordsScreen extends Screen {
        private final String key, department, label, route;
        /** Generic drill (card "drill" object): PostgREST table + filter instead of qcms_kpi_records. */
        String drillTable = "";
        JSONObject drillFilter;
        /** R39: rows already computed on the phone (custom dashboard widgets) - shown as they are. */
        JSONArray preset;
        private JSONArray rows;
        private String filter = "";
        private LinearLayout list;

        KpiRecordsScreen(MainActivity a, String key, String department, String label, String route) {
            super(a);
            this.key = key;
            this.department = department == null ? "" : department;
            this.label = label == null || label.isEmpty() ? Ui.pretty(key) : label;
            this.route = route == null ? "" : route;
        }

        @Override public String title() { return label; }
        @Override public String subtitle() {
            return (rows == null ? "Records behind this number" : rows.length() + " record(s)") + " · tap to open · hold to print";
        }
        @Override public int tab() { return Catalog.HOME; }

        @Override
        public View build() {
            newPage();
            if (rows != null) { render(); return scroll; }
            page.addView(loading());
            Api.async(() -> {
                if (drillTable != null && !drillTable.isEmpty()) return loadDrill(api, drillTable, filterQuery(drillFilter));
                if (preset != null) return preset;
                // R39: R37 contract - qcms_kpi_drilldown(p_card_key, p_limit) works for every key (module metric
                // keys mk_* and start-dashboard keys); qcms_kpi_records on older databases; then the client drill
                try {
                    return api.rpcRows("qcms_kpi_drilldown", new JSONObject().put("p_card_key", key).put("p_limit", 500));
                } catch (Exception drillErr) {
                    if (drillErr instanceof Api.ApiException && ((Api.ApiException) drillErr).status == 401) throw drillErr;
                }
                JSONObject args = new JSONObject().put("p_card_key", key).put("p_limit", 500);
                args.put("p_department", department.isEmpty() ? JSONObject.NULL : department);
                try {
                    return api.rpcRows("qcms_kpi_records", args);
                } catch (Exception rpcErr) {
                    if (rpcErr instanceof Api.ApiException && ((Api.ApiException) rpcErr).status == 401) throw rpcErr;
                    // older database: the same records straight from the module table (status filter)
                    String[] fb = fallbackDrill(key);
                    if (fb == null) throw rpcErr;
                    return loadDrill(api, fb[0], encodeQuery(fb[1]));
                }
            }, (res, err) -> {
                if (err != null || res == null) {
                    if (err instanceof Api.ApiException && ((Api.ApiException) err).status == 401) { page.removeAllViews(); page.addView(error(err, null)); return; }
                    if (!route.isEmpty() && a.isTop(this)) {
                        // older database / RPC failed: open the module like before
                        a.toast("Details list not available - opening the module.");
                        a.back();
                        Notif.open(a, "", "", route, label);
                        return;
                    }
                    page.removeAllViews();
                    page.addView(error(err == null ? new Exception("No data") : err, this::reload));
                    return;
                }
                rows = res;
                a.setSubtitle(subtitle());
                render();
            });
            return scroll;
        }

        private void render() {
            page.removeAllViews();
            LinearLayout head = Ui.card(a);
            LinearLayout top = Ui.hbox(a);
            top.setGravity(Gravity.CENTER_VERTICAL);
            top.addView(Ui.text(a, label, 15, Ui.TEXT, true), Ui.weight(1));
            top.addView(Ui.chip(a, String.valueOf(rows.length()), rows.length() > 0 ? "amber" : "green"));
            head.addView(top);
            head.addView(Ui.text(a, "Tap a record to open it · hold a record for Print PDF (Preview / Save / Share)", 11.5f, Ui.MUTED, false));
            add(head, 0);
            if (rows.length() > 8) {
                EditText search = Ui.input(a, "Filter: reference, part, party, status…", false);
                search.setText(filter);
                search.addTextChangedListener(new android.text.TextWatcher() {
                    @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
                    @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
                    @Override public void afterTextChanged(android.text.Editable e) { filter = e.toString(); fill(); }
                });
                add(search, 8);
            }
            list = Ui.vbox(a);
            add(list, 8);
            fill();
            if (!route.isEmpty() && preset == null) {
                android.widget.Button mod = Ui.outline(a, "Open the module", Ui.TEAL);
                mod.setOnClickListener(v -> Notif.open(a, "", "", route, label));
                add(mod, 12);
            }
            android.widget.Button csv = Ui.outline(a, "Export list (CSV)", Ui.TEAL_DARK);
            csv.setOnClickListener(v -> {
                List<String[]> out = new ArrayList<>();
                for (int i = 0; i < rows.length(); i++) {
                    JSONObject r = rows.optJSONObject(i);
                    if (r != null) out.add(new String[]{s(r, "reference"), s(r, "part"), s(r, "party"), s(r, "status"), s(r, "record_date"), s(r, "detail")});
                }
                GenUtil.exportCsv(a, label, "QCMS_KPI_" + GenUtil.safeName(label),
                    GenUtil.csv(GenUtil.listOf("Reference", "Part", "Party", "Status", "Date", "Detail"), out));
            });
            add(csv, 8);
        }

        private void fill() {
            if (list == null) return;
            list.removeAllViews();
            String f = filter.trim().toLowerCase(Locale.ROOT);
            int shown = 0;
            for (int i = 0; i < rows.length(); i++) {
                JSONObject r = rows.optJSONObject(i);
                if (r == null) continue;
                String hay = (s(r, "reference") + " " + s(r, "part") + " " + s(r, "party") + " " + s(r, "status") + " " + s(r, "detail")).toLowerCase(Locale.ROOT);
                if (!f.isEmpty() && !hay.contains(f)) continue;
                list.addView(row(r), Ui.matchWrap(a, shown == 0 ? 0 : 8));
                shown++;
            }
            if (shown == 0) list.addView(Ui.empty(a, rows.length() == 0 ? "No records behind this number right now. ✓" : "No record matches the filter."));
        }

        private View row(JSONObject r) {
            String table = s(r, "source_table");
            String id = s(r, "record_id");
            String ref = s(r, "reference");
            LinearLayout card = Ui.card(a);
            LinearLayout top = Ui.hbox(a);
            top.setGravity(Gravity.CENTER_VERTICAL);
            top.addView(Ui.text(a, ref.isEmpty() ? Ui.pretty(table) : ref, 14, Ui.TEXT, true), Ui.weight(1));
            String st = s(r, "status");
            if (!st.isEmpty()) top.addView(Ui.chip(a, Ui.pretty(st), Ui.tone(st)));
            card.addView(top);
            String part = s(r, "part"), party = s(r, "party"), date = s(r, "record_date");
            StringBuilder line = new StringBuilder();
            if (!part.isEmpty()) line.append(part);
            if (!party.isEmpty()) line.append(line.length() > 0 ? " · " : "").append(party);
            if (!date.isEmpty()) line.append(line.length() > 0 ? " · " : "").append(Ui.date(date));
            if (line.length() > 0) card.addView(Ui.text(a, line.toString(), 12, Ui.MUTED, false));
            String detail = s(r, "detail");
            if (!detail.isEmpty()) card.addView(Ui.text(a, detail, 12, Ui.TEXT, false));
            LinearLayout actions = Ui.hbox(a);
            actions.setGravity(Gravity.END);
            TextView print = Ui.text(a, "🖨 Print PDF", 12, Ui.TEAL_DARK, true);
            print.setPadding(dp(8), dp(6), dp(8), dp(2));
            print.setOnClickListener(v -> printRecord(a, table, id, route));
            actions.addView(print);
            TextView open = Ui.text(a, "Open ›", 12, Ui.TEAL_DARK, true);
            open.setPadding(dp(8), dp(6), dp(2), dp(2));
            actions.addView(open);
            card.addView(actions);
            final String title = ref.isEmpty() ? label : ref;
            card.setOnClickListener(v -> GenTarget.open(a, table, id, route, title));
            card.setOnLongClickListener(v -> { rowMenu(a, title, table, id, route); return true; });
            return card;
        }

        @Override public void reload() { rows = null; a.rebuild(); }
    }
}
