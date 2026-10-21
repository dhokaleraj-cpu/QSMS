package com.fourstar.qcmsapp;

import android.graphics.Color;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * R33 · Reports Centre and Records Centre exactly like the website (app_pages/reports.py render_home and
 * app_pages/records_center.py): every report / register opens natively, every record prints in the website's
 * controlled layout (Universal Record PDF) and every register downloads as a full register PDF.
 */
final class GenCentres {
    private GenCentres() { }

    static View card(MainActivity a, String title, String detail, View.OnClickListener click) {
        LinearLayout card = Ui.card(a);
        LinearLayout row = Ui.hbox(a);
        LinearLayout text = Ui.vbox(a);
        text.addView(Ui.text(a, title, 14, Ui.TEXT, true));
        if (detail != null && !detail.isEmpty()) text.addView(Ui.text(a, detail, 11.5f, Ui.MUTED, false));
        row.addView(text, Ui.weight(1));
        row.addView(Ui.text(a, "›", 24, Ui.TEAL, true));
        card.addView(row);
        Ui.clickable(card, Color.WHITE, Ui.LINE, 14);
        card.setOnClickListener(click);
        return card;
    }

    // ================================================================== Reports Centre
    static final class ReportsScreen extends Screen {
        ReportsScreen(MainActivity a) { super(a); }
        @Override public String title() { return "Reports Centre"; }
        @Override public String subtitle() { return "Supply Chain, material, quality and complaint reports"; }
        @Override public int tab() { return Catalog.MORE; }

        private static final String[][] OPERATIONAL = {
            {"customer_orders", "Supply Chain Order / Dispatch MIS", "Customer, part, monthly schedule, dispatch, pending quantity"},
            {"purchase_orders", "Purchase Order Reports", "Pending POs, RM orders, supplier and part procurement"},
            {"rep_global_balance", "Heat Number Global Balance", "RMTC plan, inward, OSP movement and global steel balance"},
            {"rep_heat_transactions", "Heat Transaction Report", "Every steel / production movement per heat"},
            {"rep_osp_balance", "OSP Heat Movement", "OSP outward, inward, material at vendor, balance to send"},
            {"rmtc", "RMTC Register", "RMTC records, heat details, validation and decision history"}};
        private static final String[][] QUALITY = {
            {"inward", "Material Inward", "Material inward, supplier, heat, RMTC and quantity records"},
            {"dimensional_reports", "Dimensional Inspection", "Dimensional results, conclusion, final decision, print layout PDF"},
            {"metlab_reports", "MetLAB", "Metallurgical results, conclusion, final decision, print layout PDF"},
            {"bend_tests", "Bend Test", "Bend test register, report and print layout PDF"},
            {"customer_complaints", "Customer Complaints", "Analysis, RCA and CAPA records"},
            {"supplier_complaints", "Supplier Complaints", "Analysis, RCA and CAPA records"}};
        private static final String[][] MANAGEMENT = {
            {"traceability", "Supply Chain Traceability", "Order-to-dispatch genealogy, heat / RMTC lineage"},
            {"npd_orders", "NPD Status", "Part development status, target dates and process completion"},
            {"apqp_projects", "APQP Status", "APQP gate status, responsibility and completion"},
            {"qc_calculations", "QC Calculations", "Saved quality-tool calculations and results"},
            {"inspection_layouts", "Inspection Layouts", "Dimensional / MetLAB layout definitions and revisions"},
            {"customer_standards", "Customer Standards", "Customer standards / specifications bank"},
            {"rep_steel_ledger", "Heat Steel Ledger", "Steel balance per heat, RMTC and part"},
            {"rep_heat_production", "Heat Production Summary", "Accepted / rejected / hold pieces per heat"},
            {"rep_inward_register", "Inward Register", "Material inward with RMTC and quality status"},
            {"rep_rmtc_usage", "Heat RMTC Usage", "Planned vs inward steel per RMTC part"},
            {"kpi_dashboards", "KPI Dashboards", "Management dashboards with charts"},
            {"report_builder", "Report Builder", "Build any report with filters, totals and charts"},
            {"master_lists", "Master Lists", "Clean lists of every master"}};

        @Override
        public View build() {
            newPage();
            LinearLayout kpis = Ui.hbox(a);
            TextView[] values = new TextView[4];
            String[] labels = {"Heat Numbers", "Global Heat Balance kg", "OSP Out pcs", "Balance to Send OSP pcs"};
            int[] colors = {Color.parseColor("#16A34A"), Color.parseColor("#F59E0B"), Color.parseColor("#1479CC"), Color.parseColor("#DC2626")};
            LinearLayout grid = Ui.vbox(a);
            for (int r = 0; r < 2; r++) {
                LinearLayout line = Ui.hbox(a);
                for (int c = 0; c < 2; c++) {
                    int i = r * 2 + c;
                    LinearLayout k = Ui.card(a);
                    values[i] = Ui.text(a, "…", 18, colors[i], true);
                    k.addView(values[i]);
                    k.addView(Ui.text(a, labels[i], 11, Ui.MUTED, false));
                    LinearLayout.LayoutParams lp = Ui.weight(1);
                    lp.setMargins(c == 0 ? 0 : dp(4), dp(4), c == 0 ? dp(4) : 0, 0);
                    line.addView(k, lp);
                }
                grid.addView(line);
            }
            add(grid, 0);
            Api.async(() -> {
                List<JSONObject> heat = RptReports.list(api, "v_qsms_heat_global_balance_report?select=*&limit=5000");
                List<JSONObject> osp = RptReports.list(api, "v_qsms_heat_osp_balance_report?select=*&limit=5000");
                double bal = 0, out = 0, send = 0;
                for (JSONObject h : heat) { bal += h.optDouble("available_unallocated_steel_quantity_kg", 0); out += h.optDouble("osp_out_quantity_pcs", 0); }
                for (JSONObject o : osp) send += o.optDouble("balance_to_send_osp_pcs", 0);
                return new double[]{heat.size(), bal, out, send};
            }, (v, err) -> {
                if (v == null) return;
                values[0].setText(Ui.num(v[0], 0));
                values[1].setText(Ui.num(v[1], 3));
                values[2].setText(Ui.num(v[2], 0));
                values[3].setText(Ui.num(v[3], 0));
            });
            group("Operational & Supply Chain Reports", OPERATIONAL);
            group("Quality & Material Reports", QUALITY);
            group("Management, Traceability & Control Reports", MANAGEMENT);
            add(card(a, "Records Centre", "Registers, Universal record PDFs, deletion requests, deleted records, history", v -> a.push(new RecordsScreen(a))), 14);
            return scroll;
        }

        private void group(String title, String[][] items) {
            add(Ui.label(a, title), 16);
            for (String[] it : items) {
                if (Catalog.get(it[0]) == null) continue;
                add(card(a, it[1], it[2], v -> a.openModule(it[0])), 6);
            }
        }
    }

    // ================================================================== Records Centre
    static final class RecordsScreen extends Screen {
        RecordsScreen(MainActivity a) { super(a); }
        @Override public String title() { return "Records Centre"; }
        @Override public String subtitle() { return "Registers · Universal PDFs · deletion requests · record history"; }
        @Override public int tab() { return Catalog.MORE; }

        @Override
        public View build() {
            newPage();
            add(Ui.label(a, "Universal record PDF download"), 0);
            add(Ui.text(a, "Select any register: download the full register PDF, or tap a record for its controlled print layout PDF (view, download, print, email, share).", 12, Ui.MUTED, false), 4);
            Map<String, List<Module>> byArea = new LinkedHashMap<>();
            String[] areas = {"Supply", "Quality", "Masters", "More"};
            for (Module m : Catalog.all()) {
                if (m.table.isEmpty() || m.table.startsWith("adhoc_") || m.idField.isEmpty() || m.custom != null) continue;
                String area = m.tab >= 1 && m.tab <= 4 ? areas[m.tab - 1] : "More";
                byArea.computeIfAbsent(area + " · " + m.section, k -> new ArrayList<>()).add(m);
            }
            for (Map.Entry<String, List<Module>> e : byArea.entrySet()) {
                add(Ui.label(a, e.getKey()), 14);
                for (Module m : e.getValue()) {
                    String kind = RptReports.dedicated(m.table) ? "Website print layout report" : "Universal record PDF";
                    add(card(a, m.title, kind, v -> a.push(new UniversalScreen(a, m))), 6);
                }
            }
            add(Ui.label(a, "Control"), 16);
            for (String key : new String[]{"deletion_requests", "deleted_records", "activity_log", "email_outbox"}) {
                Module m = Catalog.get(key);
                if (m != null) add(card(a, m.title, m.description, v -> a.openModule(key)), 6);
            }
            return scroll;
        }
    }

    /** One register: search, full register PDF, tap a record for its print layout PDF. */
    static final class UniversalScreen extends Screen {
        private final Module m;
        private List<JSONObject> rows = new ArrayList<>();
        private Map<String, Map<String, String>> fk;
        private String search = "";
        private LinearLayout holder;

        UniversalScreen(MainActivity a, Module m) { super(a); this.m = m; }
        @Override public String title() { return m.title; }
        @Override public String subtitle() { return "Universal record PDF · " + (RptReports.dedicated(m.table) ? "website print layout" : "controlled record"); }
        @Override public int tab() { return m.tab; }

        @Override
        public View build() {
            newPage();
            LinearLayout bar = Ui.hbox(a);
            EditText box = Ui.input(a, "Search this register", false);
            box.setText(search);
            bar.addView(box, Ui.weight(1));
            Button go = Ui.primary(a, "Search");
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(96), dp(48));
            lp.leftMargin = dp(8);
            bar.addView(go, lp);
            go.setOnClickListener(v -> { search = box.getText().toString().trim(); show(); });
            add(bar, 0);
            Button full = Ui.outline(a, "⇩ Download Full Register PDF", Ui.TEAL_DARK);
            full.setOnClickListener(v -> registerPdf());
            add(full, 8);
            holder = Ui.vbox(a);
            add(holder, 8);
            holder.addView(loading());
            Api.async(() -> {
                String order = m.order == null || m.order.isEmpty() ? "" : "&order=" + m.order;
                JSONArray r = api.rows(m.table + "?select=*" + m.filter + order + "&limit=2000");
                List<String> cols = new ArrayList<>();
                for (String[] c : m.cols) cols.add(c[0]);
                Map<String, Map<String, String>> labels = Labels.resolve(api, m.table, r, cols);
                return new Object[]{RptReports.list(r), labels};
            }, (res, err) -> {
                if (err != null) { holder.removeAllViews(); holder.addView(error(err, this::reload)); return; }
                @SuppressWarnings("unchecked") List<JSONObject> l = (List<JSONObject>) res[0];
                @SuppressWarnings("unchecked") Map<String, Map<String, String>> f = (Map<String, Map<String, String>>) res[1];
                rows = l;
                fk = f;
                show();
            });
            return scroll;
        }

        private List<JSONObject> visible() {
            if (search.isEmpty()) return rows;
            String q = search.toLowerCase(Locale.ROOT);
            List<JSONObject> out = new ArrayList<>();
            for (JSONObject r : rows) {
                StringBuilder b = new StringBuilder(r.toString().toLowerCase(Locale.ROOT));
                for (String[] c : m.cols) b.append(' ').append(Labels.cell(c[0], r.opt(c[0]), fk == null ? null : fk.get(c[0])).toLowerCase(Locale.ROOT));
                if (b.indexOf(q) >= 0) out.add(r);
            }
            return out;
        }

        private List<String> headers() {
            List<String> h = new ArrayList<>();
            for (String[] c : m.cols) h.add(c[1]);
            return h;
        }

        private List<List<String>> lines(List<JSONObject> list) {
            List<List<String>> data = new ArrayList<>();
            for (JSONObject r : list) {
                List<String> line = new ArrayList<>();
                for (String[] c : m.cols) line.add(Labels.cell(c[0], r.opt(c[0]), fk == null ? null : fk.get(c[0])));
                data.add(line);
            }
            return data;
        }

        private void show() {
            if (holder == null) return;
            holder.removeAllViews();
            List<JSONObject> list = visible();
            holder.addView(Ui.text(a, list.size() + " record(s) · tap a row for its print layout PDF", 12, Ui.MUTED, false));
            if (list.isEmpty()) { holder.addView(Ui.empty(a, "No records are available for this selection.")); return; }
            holder.addView(new DataGrid(a, m.title, headers(), lines(list), 480, index -> {
                JSONObject r = list.get(index);
                String id = Lookups.j(r, m.idField);
                new android.app.AlertDialog.Builder(a).setTitle(m.recordTitle(r))
                    .setItems(new String[]{"Print layout PDF · Download · Print · Email", "Open record"}, (d, w) -> {
                        if (w == 0) ExportKit.layoutMenu(a, () -> RptReports.forRecord(api, m, id));
                        else a.push(new RecordScreen(a, m, id));
                    }).setNegativeButton("Close", null).show();
            }), Ui.matchWrap(a, 6));
        }

        private void registerPdf() {
            List<JSONObject> list = visible();
            if (list.isEmpty()) { a.toast("No records to print."); return; }
            List<String> h = headers();
            List<List<String>> data = lines(list);
            ExportKit.layoutMenu(a, () -> RptReports.register(api, m.title, h, data));
        }
    }

    // ================================================================== About
    static final class AboutScreen extends Screen {
        AboutScreen(MainActivity a) { super(a); }
        @Override public String title() { return "About STAWN QCMS"; }
        @Override public String subtitle() { return "Version, developer, copyright and licence"; }
        @Override public int tab() { return Catalog.MORE; }

        @Override
        public View build() {
            newPage();
            LinearLayout head = Ui.card(a);
            head.setGravity(android.view.Gravity.CENTER_HORIZONTAL);
            android.widget.ImageView logo = new android.widget.ImageView(a);
            logo.setImageResource(R.drawable.stawn_qcms_logo);
            head.addView(logo, new LinearLayout.LayoutParams(dp(84), dp(84)));
            TextView name = Ui.text(a, About.PRODUCT, 22, Ui.TEXT, true);
            name.setGravity(android.view.Gravity.CENTER);
            head.addView(name, Ui.matchWrap(a, 8));
            TextView tag = Ui.text(a, About.TAGLINE, 13, Ui.MUTED, false);
            tag.setGravity(android.view.Gravity.CENTER);
            head.addView(tag);
            TextView ver = Ui.text(a, "Android app v" + BuildConfig.VERSION_NAME + " · Website v" + RptPdf.WEB_VERSION, 12.5f, Ui.TEAL_DARK, true);
            ver.setGravity(android.view.Gravity.CENTER);
            head.addView(ver, Ui.matchWrap(a, 6));
            add(head, 0);

            add(Ui.label(a, "Developer"), 16);
            LinearLayout dev = Ui.card(a);
            for (String[] p : About.DEVELOPER) dev.addView(Ui.pair(a, p[0], p[1]));
            add(dev, 4);

            add(Ui.label(a, "Licensed to"), 16);
            LinearLayout lic = Ui.card(a);
            String company = Licence.company(api);
            for (String[] p : About.LICENSEE) lic.addView(Ui.pair(a, p[0], p[0].equals("Licensed user") && !company.isEmpty() ? company : p[1]));
            add(lic, 4);

            // R35: licence details from qcms_licence_status (plan, status, users, valid until, masked key, developer)
            add(Ui.label(a, "Licence"), 16);
            LinearLayout licBox = Ui.vbox(a);
            if (Licence.status != null) licBox.addView(Licence.detailsCard(a, Licence.status));
            else licBox.addView(loading());
            add(licBox, 4);
            Api.async(() -> Licence.load(api), (st, err) -> {
                licBox.removeAllViews();
                licBox.addView(Licence.detailsCard(a, err != null ? Licence.status : st));
            });

            add(Ui.label(a, "Copyright"), 16);
            LinearLayout cr = Ui.card(a);
            cr.addView(Ui.text(a, About.COPYRIGHT, 13, Ui.TEXT, true));
            for (String para : About.NOTICE) cr.addView(Ui.text(a, para, 12, Ui.MUTED, false), Ui.matchWrap(a, 8));
            add(cr, 4);

            add(Ui.label(a, "Data & security"), 16);
            LinearLayout sec = Ui.card(a);
            for (String para : About.SECURITY) sec.addView(Ui.text(a, "• " + para, 12, Ui.TEXT, false), Ui.matchWrap(a, 4));
            add(sec, 4);

            add(Ui.label(a, "Support"), 16);
            LinearLayout sup = Ui.card(a);
            sup.addView(Ui.text(a, About.SUPPORT, 12.5f, Ui.TEXT, false));
            Button mail = Ui.outline(a, "✉ Email STAWN support", Ui.TEAL_DARK);
            mail.setOnClickListener(v -> {
                try {
                    android.content.Intent i = new android.content.Intent(android.content.Intent.ACTION_SENDTO, android.net.Uri.parse("mailto:" + About.EMAIL));
                    i.putExtra(android.content.Intent.EXTRA_SUBJECT, About.PRODUCT + " support · app v" + BuildConfig.VERSION_NAME);
                    a.startActivity(i);
                } catch (Exception e) {
                    a.toast("No e-mail app found. Write to " + About.EMAIL);
                }
            });
            sup.addView(mail, Ui.matchWrap(a, 10));
            add(sup, 4);
            TextView foot = Ui.text(a, About.COPYRIGHT, 11, Ui.MUTED, false);
            foot.setGravity(android.view.Gravity.CENTER);
            add(foot, 18);
            return scroll;
        }
    }

    /** Text of the About page (same wording as the website's About page, core/about.py). */
    static final class About {
        static final String PRODUCT = "STAWN QCMS";
        static final String TAGLINE = "Quality Control Monitoring System";
        static final String COMPANY = "STAWN PRECISION PRIVATE LIMITED";
        static final String EMAIL = "business@stawnprecision.com";
        static final String COPYRIGHT = "© 2026 " + COMPANY + ". All rights reserved.";
        static final String[][] DEVELOPER = {
            {"Developed by", COMPANY}, {"Location", "Thane, Maharashtra, India"}, {"Product", PRODUCT + " – " + TAGLINE},
            {"Platforms", "Android app · Web application (desktop, tablet, phone browser)"}, {"Contact", EMAIL}};
        static final String[][] LICENSEE = {
            {"Licensed user", "Four Star Industries Pvt. Ltd."}, {"Use", "Internal quality, supply chain and traceability records"}};
        static final String[] NOTICE = {
            "STAWN QCMS, the STAWN name and logo, the software, its source code, screen designs, report and print layouts, "
                + "database design and documentation are the intellectual property of " + COMPANY + " and are protected by the "
                + "Copyright Act, 1957 (India) and international copyright laws.",
            "The software is licensed, not sold. Copying, modifying, reverse engineering, redistributing, sub-licensing or reselling "
                + "the software or any part of it without the prior written permission of " + COMPANY + " is prohibited.",
            "All business data entered in QCMS (parts, orders, inspection results, reports and documents) belongs to the licensed user.",
            "Other product and company names shown in the records belong to their respective owners."};
        static final String[] SECURITY = {
            "Data is stored in the licensed user's own Supabase database with row-level security for every company (tenant).",
            "Passwords are never stored on the phone; the session key is kept in the Android Keystore and the app locks after 15 minutes in the background.",
            "Personal e-mail credentials are visible only to their own user – not to other users or administrators.",
            "Every create, change and deletion is recorded in the record history and user activity log."};
        static final String SUPPORT = "For licences, new features, training or support contact " + COMPANY + " at " + EMAIL + ".";
    }
}
