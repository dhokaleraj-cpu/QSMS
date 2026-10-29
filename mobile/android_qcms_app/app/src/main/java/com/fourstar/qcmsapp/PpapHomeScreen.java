package com.fourstar.qcmsapp;

import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * R39 · PPAP Document Manager home (website route ppap-home): portfolio KPIs (completed %, overdue, due this week,
 * pending), package register with search / status filter, "New PPAP package" (from template, linked to an APQP
 * project / part / customer) and a link to the same page on the website.
 */
public final class PpapHomeScreen extends Screen {
    private List<JSONObject> packages = new ArrayList<>();
    private final Map<String, List<JSONObject>> byPackage = new HashMap<>();
    private Map<String, String> customers = new HashMap<>();
    private boolean[] perms = {true, false, false, false};
    private LinearLayout listBox;
    private String term = "", status = "ALL";

    public PpapHomeScreen(MainActivity a) { super(a); }

    @Override public String title() { return "PPAP Document Manager"; }
    @Override public String subtitle() { return "NPD / APQP · PPAP packages, elements & documents"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            boolean[] p = PpapData.permissions(api);
            List<JSONObject> pk = PpapData.packages(api);
            List<JSONObject> el = pk.isEmpty() ? new ArrayList<>() : PpapData.allElements(api);
            Map<String, String> cust = new HashMap<>();
            for (JSONObject c : PpapData.list(Lookups.rows(api, Lookups.customers()))) cust.put(PpapData.s(c, "id"), Lookups.PARTY.of(c));
            return new Object[]{p, pk, el, cust};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            perms = (boolean[]) res[0];
            @SuppressWarnings("unchecked") List<JSONObject> pk = (List<JSONObject>) res[1];
            @SuppressWarnings("unchecked") List<JSONObject> el = (List<JSONObject>) res[2];
            @SuppressWarnings("unchecked") Map<String, String> cust = (Map<String, String>) res[3];
            packages = pk;
            customers = cust;
            byPackage.clear();
            for (JSONObject e : el) {
                List<JSONObject> l = byPackage.get(PpapData.s(e, "package_id"));
                if (l == null) { l = new ArrayList<>(); byPackage.put(PpapData.s(e, "package_id"), l); }
                l.add(e);
            }
            render(el);
        });
        return scroll;
    }

    static LinearLayout tile(MainActivity a, String label, String value, String foot, int fg, int bg) {
        LinearLayout t = Ui.vbox(a);
        t.setBackground(Ui.round(bg, Ui.LINE, 1, 12, a));
        int p = Ui.dp(a, 10);
        t.setPadding(p, p, p, p);
        t.addView(Ui.text(a, label.toUpperCase(Locale.ROOT), 10, Ui.MUTED, true));
        t.addView(Ui.text(a, value, 20, fg, true));
        if (foot != null && !foot.isEmpty()) t.addView(Ui.text(a, foot, 10.5f, Ui.MUTED, false));
        return t;
    }

    static void tiles(MainActivity a, LinearLayout parent, List<? extends View> tiles) {
        LinearLayout row = null;
        for (int i = 0; i < tiles.size(); i++) {
            if (i % 2 == 0) {
                row = Ui.hbox(a);
                row.setGravity(Gravity.TOP);
                parent.addView(row, Ui.matchWrap(a, i == 0 ? 0 : 8));
            }
            LinearLayout.LayoutParams lp = Ui.weight(1);
            if (i % 2 == 1) lp.leftMargin = Ui.dp(a, 8);
            row.addView(tiles.get(i), lp);
        }
        if (tiles.size() % 2 == 1 && row != null) row.addView(new View(a), Ui.weight(1));
    }

    private void render(List<JSONObject> elements) {
        offlineNote();
        if (!perms[0]) {
            add(Ui.empty(a, "You do not have PPAP (or NPD & APQP) view permission. Ask the Admin for module PPAP rights."), 4);
            return;
        }
        Map<String, Double> k = PpapData.kpis(packages, elements, LocalDate.now());
        LinearLayout box = Ui.vbox(a);
        List<LinearLayout> t = new ArrayList<>();
        t.add(tile(a, "Completed", Ui.num(k.get("percent"), 1) + "%", "Applicable elements, all packages", 0xFF15803D, 0xFFF0FDF4));
        t.add(tile(a, "Overdue", Ui.num(k.get("overdue"), 0), "Elements past due (active packages)", 0xFFB91C1C, 0xFFFEF2F2));
        t.add(tile(a, "Due this week", Ui.num(k.get("due_week"), 0), "Open elements due ≤ 7 days", 0xFFD97706, 0xFFFFF7ED));
        t.add(tile(a, "Packages", Ui.num(k.get("packages"), 0), Ui.num(k.get("active"), 0) + " active · " + Ui.num(k.get("pending"), 0) + " open elements", 0xFF1469A8, 0xFFEFF6FF));
        tiles(a, box, t);
        add(box, 2);

        LinearLayout actions = Ui.vbox(a);
        if (perms[1]) {
            Button create = Ui.primary(a, "+ New PPAP package");
            create.setOnClickListener(v -> a.push(new PpapPackageEditScreen(a, null, null)));
            actions.addView(create, Ui.matchWrap(a, 0));
        }
        actions.addView(Ui.text(a, "Tracker matrix, element templates and tracker import are on the website (PPAP → Home).", 11, Ui.MUTED, false), Ui.matchWrap(a, 8));
        add(actions, 10);

        EditText search = Ui.input(a, "Search package, PPAP no., part, customer…", false);
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
            @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
            @Override public void afterTextChanged(Editable e) { term = e.toString(); fill(); }
        });
        add(search, 12);
        HorizontalScrollView hs = new HorizontalScrollView(a);
        hs.setHorizontalScrollBarEnabled(false);
        LinearLayout chips = Ui.hbox(a);
        List<String> filters = new ArrayList<>();
        filters.add("ALL");
        filters.add("OVERDUE");
        for (String s : PpapData.PACKAGE_STATUSES) filters.add(s);
        List<TextView> views = new ArrayList<>();
        for (String f : filters) {
            TextView c = Ui.chip(a, f.equals("ALL") ? "All" : f.equals("OVERDUE") ? "With overdue" : Ui.pretty(f), f.equals(status) ? "teal" : "grey");
            c.setPadding(dp(12), dp(7), dp(12), dp(7));
            c.setOnClickListener(v -> {
                status = f;
                for (int i = 0; i < views.size(); i++) {
                    TextView x = views.get(i);
                    boolean on = filters.get(i).equals(status);
                    x.setBackground(Ui.round(on ? Ui.TEAL_SOFT : Ui.GREY_BG, 0, 0, 12, a));
                    x.setTextColor(on ? Ui.TEAL_DARK : Ui.GREY_FG);
                }
                fill();
            });
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
            lp.rightMargin = dp(6);
            chips.addView(c, lp);
            views.add(c);
        }
        hs.addView(chips);
        add(hs, 8);
        listBox = Ui.vbox(a);
        add(listBox, 6);
        fill();
    }

    private void fill() {
        if (listBox == null) return;
        listBox.removeAllViews();
        LocalDate today = LocalDate.now();
        String needle = term.trim().toLowerCase(Locale.ROOT);
        int shown = 0;
        for (JSONObject p : packages) {
            String id = PpapData.s(p, "id");
            List<JSONObject> els = byPackage.containsKey(id) ? byPackage.get(id) : new ArrayList<>();
            int overdue = 0;
            for (JSONObject e : els) if ("overdue".equals(PpapData.state(e, today))) overdue++;
            String st = PpapData.s(p, "status");
            if (status.equals("OVERDUE") && overdue == 0) continue;
            if (!status.equals("ALL") && !status.equals("OVERDUE") && !status.equalsIgnoreCase(st)) continue;
            String customer = customers.containsKey(PpapData.s(p, "customer_id")) ? customers.get(PpapData.s(p, "customer_id")) : "";
            String hay = (PpapData.s(p, "package_no") + " " + PpapData.s(p, "customer_ppap_no") + " " + PpapData.s(p, "customer_part_no") + " "
                + PpapData.s(p, "remarks") + " " + st + " " + customer).toLowerCase(Locale.ROOT);
            if (!needle.isEmpty() && !hay.contains(needle)) continue;
            shown++;
            double[] pr = PpapData.progress(els);
            LinearLayout card = Ui.card(a);
            Ui.clickable(card, Ui.PANEL, Ui.LINE, 14);
            card.setPadding(dp(12), dp(10), dp(12), dp(10));
            LinearLayout top = Ui.hbox(a);
            top.addView(Ui.text(a, PpapData.s(p, "package_no"), 14.5f, Ui.TEXT, true), Ui.weight(1));
            top.addView(Ui.chip(a, Ui.pretty(st.isEmpty() ? "IN_PROGRESS" : st), Ui.tone(st)));
            card.addView(top);
            card.addView(Ui.text(a, Lookups.join("PPAP " + (PpapData.s(p, "customer_ppap_no").isEmpty() ? "-" : PpapData.s(p, "customer_ppap_no")),
                "Part " + (PpapData.s(p, "customer_part_no").isEmpty() ? "-" : PpapData.s(p, "customer_part_no")), customer), 12, Ui.MUTED, false));
            LinearLayout foot = Ui.hbox(a);
            foot.setPadding(0, dp(6), 0, 0);
            foot.addView(Ui.chip(a, Ui.num(pr[4], 0) + "% · " + (int) pr[3] + "/" + (int) pr[2] + " done", pr[4] >= 100 ? "green" : "teal"));
            if (overdue > 0) { TextView o = Ui.chip(a, overdue + " overdue", "red"); foot.addView(o, gap()); }
            String due = PpapData.s(p, "customer_due_date");
            if (!due.isEmpty()) { TextView d = Ui.chip(a, "Customer due " + Ui.date(due), "grey"); foot.addView(d, gap()); }
            card.addView(foot);
            card.setOnClickListener(v -> a.push(new PpapPackageScreen(a, id)));
            listBox.addView(card, Ui.matchWrap(a, 8));
        }
        if (shown == 0) listBox.addView(Ui.empty(a, packages.isEmpty() ? "No PPAP packages yet." : "No package matches the filter."));
    }

    private LinearLayout.LayoutParams gap() {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.leftMargin = dp(6);
        return lp;
    }

    /** R39 · APQP project -> its PPAP packages (website npd_apqp "PPAP packages" section): open one or create a new package
     *  from the project (part, customer, level, target date, coordinator prefilled; template elements; assignment e-mail). */
    static void fromApqp(MainActivity a, JSONObject project) {
        String projectId = PpapData.s(project, "id");
        if (projectId.isEmpty()) return;
        Api.async(() -> PpapData.packagesForApqp(Api.get(a), projectId), (rows, err) -> {
            if (err != null) { a.toast(Api.message(err)); return; }
            String[] labels = new String[rows.size() + 1];
            for (int i = 0; i < rows.size(); i++) {
                JSONObject p = rows.get(i);
                labels[i] = PpapData.s(p, "package_no") + " · PPAP " + (PpapData.s(p, "customer_ppap_no").isEmpty() ? "-" : PpapData.s(p, "customer_ppap_no"))
                    + " · " + Ui.pretty(PpapData.s(p, "status")) + " · " + Math.round(p.optDouble("completion_percent", 0)) + "%";
            }
            labels[rows.size()] = "+ Create PPAP package from this APQP project";
            new android.app.AlertDialog.Builder(a).setTitle("PPAP packages · " + PpapData.s(project, "project_code"))
                .setItems(labels, (d, w) -> {
                    if (w < rows.size()) a.push(new PpapPackageScreen(a, PpapData.s(rows.get(w), "id")));
                    else a.push(new PpapPackageEditScreen(a, null, projectId));
                }).setNegativeButton("Close", null).show();
        });
    }
}
