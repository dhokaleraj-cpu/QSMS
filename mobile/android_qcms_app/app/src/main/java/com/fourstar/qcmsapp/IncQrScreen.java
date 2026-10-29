package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * R40 · "RMTC QR Codes" (web app_pages/rmtc_qr.py, route rmtc-qr; permission module RMTC_ENTRY): approved RMTC list with
 * search (RMTC no, heat, grade, supplier) and a bulk "Create public QR for approved RMTCs without one"; each row opens
 * Detail: QR image, public link (copy / share / open in the external browser - a public Edge Function page, not the QCMS
 * website), the RMTC documents (certificate + RMTC attachments) with view / download, Download all (ZIP) / as one PDF
 * (&f=zip / &f=pdf), QR PNG / JPEG / PDF, 100 x 60 mm label, Refresh certificate and Revoke QR (new code).
 * View needs RMTC_ENTRY can_view; refresh / revoke / bulk need RMTC_ENTRY can_edit or can_approve.
 */
final class IncQrScreen extends Screen {
    static final String MODULE_KEY = IncQrLabel.MODULE_KEY;  // RMTC_ENTRY
    static final String ROUTE = "rmtc-qr";
    private static String query = "";
    private List<JSONObject> rows;
    private Map<String, JSONObject> tokens;
    private Map<String, String> grades, suppliers;
    private boolean canView, manage;

    IncQrScreen(MainActivity a) { super(a); }

    @Override public String title() { return "RMTC QR Codes"; }
    @Override public String subtitle() { return "Public QR · RMTC documents download (no login)"; }
    @Override public int tab() { return Catalog.QUALITY; }
    @Override public void reload() { rows = null; a.rebuild(); }

    static boolean canManage(Api api) {
        return AdmPerm.current(api, MODULE_KEY, "can_edit") || AdmPerm.current(api, MODULE_KEY, "can_approve");
    }

    @Override
    public View build() {
        newPage();
        LinearLayout box = Ui.vbox(a);
        add(box, 0);
        if (rows != null) { render(box); return scroll; }
        box.addView(loading());
        Api.async(() -> {
            boolean view = AdmPerm.current(api, MODULE_KEY, "can_view");
            if (!view) return new Object[]{false, false, null, null, null, null};
            boolean m = canManage(api);
            JSONArray list = api.rows("rmtc_approvals?select=id,rmtc_number,certificate_reference,heat_number,heat_code,status,disposition,decision_at,approved_at,supplier_id,material_grade_id"
                + "&" + IncQrPublic.approvedFilter() + "&order=decision_at.desc.nullslast&limit=2000");
            List<JSONObject> out = new ArrayList<>();
            List<String> gIds = new ArrayList<>(), sIds = new ArrayList<>();
            for (int i = 0; i < list.length(); i++) {
                JSONObject r = list.getJSONObject(i);
                out.add(r);
                String g = Lookups.j(r, "material_grade_id"), s = Lookups.j(r, "supplier_id");
                if (!g.isEmpty() && !gIds.contains(g)) gIds.add(g);
                if (!s.isEmpty() && !sIds.contains(s)) sIds.add(s);
            }
            Map<String, String> gm = new HashMap<>(), sm = new HashMap<>();
            for (int i = 0; i < gIds.size(); i += 150) {
                JSONArray gs = api.rows("material_grades?select=id,grade_code,grade_name&id=in.(" + String.join(",", gIds.subList(i, Math.min(gIds.size(), i + 150))) + ")");
                for (int k = 0; k < gs.length(); k++) gm.put(Lookups.j(gs.optJSONObject(k), "id"), IncCalc.firstText(Lookups.j(gs.optJSONObject(k), "grade_code"), Lookups.j(gs.optJSONObject(k), "grade_name")));
            }
            for (int i = 0; i < sIds.size(); i += 150) {
                JSONArray ps = api.rows("parties?select=id,party_name&id=in.(" + String.join(",", sIds.subList(i, Math.min(sIds.size(), i + 150))) + ")");
                for (int k = 0; k < ps.length(); k++) sm.put(Lookups.j(ps.optJSONObject(k), "id"), Lookups.j(ps.optJSONObject(k), "party_name"));
            }
            Map<String, JSONObject> tk = new HashMap<>();
            try {
                JSONArray t = api.rows(IncQrPublic.TABLE + "?select=rmtc_approval_id,certificate_path,created_at&revoked=eq.false&limit=10000");
                for (int i = 0; i < t.length(); i++) tk.put(Lookups.j(t.optJSONObject(i), "rmtc_approval_id"), t.optJSONObject(i));
            } catch (Exception ignored) { }
            return new Object[]{true, m, out, tk, gm, sm};
        }, (res, err) -> {
            box.removeAllViews();
            if (err != null) { box.addView(error(err, this::reload)); return; }
            canView = (Boolean) res[0];
            manage = (Boolean) res[1];
            if (!canView) { box.addView(Ui.empty(a, "You do not have View rights for RMTC (RMTC_ENTRY). Ask your company admin.")); return; }
            @SuppressWarnings("unchecked") List<JSONObject> r = (List<JSONObject>) res[2];
            @SuppressWarnings("unchecked") Map<String, JSONObject> t = (Map<String, JSONObject>) res[3];
            @SuppressWarnings("unchecked") Map<String, String> g = (Map<String, String>) res[4];
            @SuppressWarnings("unchecked") Map<String, String> s = (Map<String, String>) res[5];
            rows = r; tokens = t; grades = g; suppliers = s;
            render(box);
        });
        return scroll;
    }

    private void render(LinearLayout box) {
        box.addView(Ui.text(a, "Each approved RMTC gets a public QR link (random code, no login). Anyone scanning it can view and download the "
            + "approved RMTC certificate and every RMTC document, or all of them as one ZIP / one PDF. Customer details are never shown.", 11.5f, Ui.MUTED, false));
        int without = 0;
        for (JSONObject r : rows) if (!tokens.containsKey(Lookups.j(r, "id"))) without++;
        if (manage) {
            Button bulk = Ui.primary(a, "Create public QR for approved RMTCs without one (" + without + ")");
            box.addView(bulk, Ui.matchWrap(a, 8));
            bulk.setEnabled(without > 0);
            int n = without;
            bulk.setOnClickListener(v -> a.confirm("Create public QR codes", "Create a public QR code and the RMTC certificate PDF for " + n
                + " approved RMTC(s) without one? This can take a while.", "Create", () -> {
                bulk.setEnabled(false);
                a.toast("Creating public QR codes…");
                Api.async(() -> IncQrPublic.bulkCreate(api), (r, err) -> {
                    bulk.setEnabled(true);
                    if (err != null) { a.toast(Api.message(err)); return; }
                    a.toast("Public QR created for " + r[0] + " RMTC(s)" + (r[1] > 0 ? "; " + r[1] + " with a warning / not created." : "."));
                    reload();
                });
            }));
        }
        EditText search = Ui.input(a, "Search RMTC no, heat, grade, supplier", false);
        search.setText(query);
        box.addView(search, Ui.matchWrap(a, 8));
        LinearLayout gridBox = Ui.vbox(a);
        box.addView(gridBox, Ui.matchWrap(a, 6));
        renderGrid(gridBox);
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
            @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
            @Override public void afterTextChanged(Editable e) { query = e == null ? "" : e.toString(); renderGrid(gridBox); }
        });
    }

    private void renderGrid(LinearLayout gridBox) {
        gridBox.removeAllViews();
        String q = query.trim().toLowerCase(Locale.ROOT);
        List<JSONObject> shown = new ArrayList<>();
        List<List<String>> data = new ArrayList<>();
        for (JSONObject r : rows) {
            String grade = grades.getOrDefault(Lookups.j(r, "material_grade_id"), ""), sup = suppliers.getOrDefault(Lookups.j(r, "supplier_id"), "");
            String hay = (Lookups.j(r, "rmtc_number") + " " + Lookups.j(r, "certificate_reference") + " " + Lookups.j(r, "heat_number") + " "
                + Lookups.j(r, "heat_code") + " " + grade + " " + sup).toLowerCase(Locale.ROOT);
            if (!q.isEmpty() && !hay.contains(q)) continue;
            JSONObject t = tokens.get(Lookups.j(r, "id"));
            shown.add(r);
            data.add(Arrays.asList(Lookups.j(r, "rmtc_number"), Lookups.j(r, "heat_number"), grade, sup,
                Ui.date(IncCalc.firstText(Lookups.j(r, "decision_at"), Lookups.j(r, "approved_at"))), Ui.pretty(Lookups.j(r, "disposition")),
                t == null ? "No" : "Yes", t == null || Lookups.j(t, "certificate_path").isEmpty() ? "-" : "Stored"));
        }
        if (shown.isEmpty()) { gridBox.addView(Ui.empty(a, rows.isEmpty() ? "No approved RMTC yet." : "No approved RMTC matches the search.")); return; }
        List<String> head = Arrays.asList("RMTC", "Heat", "Grade", "Supplier", "Approved", "Decision", "Public QR", "Certificate");
        gridBox.addView(new DataGrid(a, shown.size() + " approved RMTC(s)", head, data, 420,
            index -> a.push(new Detail(a, Lookups.j(shown.get(index), "id")))));
    }

    // ================================================================== public download helper
    /** GET a public Edge Function link (no auth header - it is a public page) into memory, capped at 60 MB. */
    static byte[] fetchPublic(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(20000);
        c.setReadTimeout(120000);
        c.setInstanceFollowRedirects(true);
        try {
            int code = c.getResponseCode();
            if (code >= 400) throw new Api.ApiException(code, "The public RMTC page returned " + code + ".");
            try (InputStream in = c.getInputStream()) {
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                byte[] buf = new byte[16384];
                int n;
                long total = 0;
                while ((n = in.read(buf)) > 0) {
                    total += n;
                    if (total > 60L * 1024 * 1024) throw new Api.ApiException(413, "The download is larger than 60 MB - open it in the browser instead.");
                    out.write(buf, 0, n);
                }
                return out.toByteArray();
            }
        } finally {
            c.disconnect();
        }
    }

    static void copy(MainActivity a, String text) {
        try {
            ClipboardManager cm = (ClipboardManager) a.getSystemService(Context.CLIPBOARD_SERVICE);
            cm.setPrimaryClip(ClipData.newPlainText("RMTC public link", text));
            a.toast("Link copied.");
        } catch (Exception e) {
            a.toast("Could not copy: " + Api.message(e));
        }
    }

    static void shareText(MainActivity a, String subject, String text) {
        try {
            Intent i = new Intent(Intent.ACTION_SEND);
            i.setType("text/plain");
            i.putExtra(Intent.EXTRA_SUBJECT, subject);
            i.putExtra(Intent.EXTRA_TEXT, text);
            a.startActivity(Intent.createChooser(i, "Share RMTC link"));
        } catch (Exception e) {
            a.toast("Could not share: " + Api.message(e));
        }
    }

    /** "Download all" choice: open the public link (&f=zip / &f=pdf) in the external browser, or download in the app. */
    static void downloadAll(MainActivity a, String url, String name, String mime) {
        new AlertDialog.Builder(a).setTitle(name)
            .setItems(new String[]{"Open in browser (download)", "Download in app (save / share)"}, (d, which) -> {
                if (which == 0) { a.openInBrowser(url); return; }
                a.toast("Downloading " + name + "…");
                Api.async(() -> fetchPublic(url), (bytes, err) -> {
                    if (err != null || bytes == null || bytes.length == 0) { a.toast("Could not download: " + Api.message(err)); return; }
                    IncQrLabel.fileActions(a, name, mime, bytes);
                });
            }).setNegativeButton("Close", null).show();
    }

    // ================================================================== detail
    static final class Detail extends Screen {
        private final String rid;
        private JSONObject rec;
        private IncQrLabel.Assets assets;
        private Bitmap bmp;
        private List<IncQrPublic.Doc> docs;
        private boolean canView, manage;

        Detail(MainActivity a, String rid) { super(a); this.rid = rid; }

        @Override public String title() { return "RMTC QR · " + (rec == null ? "" : Lookups.j(rec, "rmtc_number")); }
        @Override public String subtitle() { return "Public link · documents · downloads"; }
        @Override public int tab() { return Catalog.QUALITY; }
        @Override public void reload() { rec = null; a.rebuild(); }

        @Override
        public View build() {
            newPage();
            LinearLayout box = Ui.vbox(a);
            add(box, 0);
            if (rec != null) { render(box); return scroll; }
            box.addView(loading());
            Api.async(() -> {
                boolean view = AdmPerm.current(api, MODULE_KEY, "can_view");
                if (!view) return new Object[]{false};
                JSONObject r = IncRmtcData.rmtc(api, rid);
                if (!IncQrLabel.approved(r)) return new Object[]{true, canManage(api), r, null, null, null};
                IncQrLabel.Assets s = IncQrLabel.assets(api, r);
                Bitmap b = IncQrLabel.labelBitmap(s);
                JSONObject tokenRow = s.tokenRow != null ? s.tokenRow : IncQrPublic.activeToken(api, rid);
                return new Object[]{true, canManage(api), r, s, b, IncQrPublic.documents(api, rid, tokenRow, r)};
            }, (res, err) -> {
                box.removeAllViews();
                if (err != null) { box.addView(error(err, this::reload)); return; }
                canView = (Boolean) res[0];
                if (!canView) { box.addView(Ui.empty(a, "You do not have View rights for RMTC (RMTC_ENTRY).")); return; }
                manage = (Boolean) res[1];
                rec = (JSONObject) res[2];
                assets = (IncQrLabel.Assets) res[3];
                bmp = (Bitmap) res[4];
                @SuppressWarnings("unchecked") List<IncQrPublic.Doc> d = (List<IncQrPublic.Doc>) res[5];
                docs = d == null ? new ArrayList<>() : d;
                render(box);
            });
            return scroll;
        }

        private void render(LinearLayout box) {
            if (assets == null) { box.addView(Ui.empty(a, "This RMTC is not approved - a QR code is created only for approved RMTCs.")); return; }
            IncQrLabel.Assets s = assets;
            LinearLayout card = Ui.card(a);
            card.addView(Ui.text(a, "RMTC " + s.number, 15, Ui.TEXT, true));
            for (int i = 1; i < s.lines.size(); i++) card.addView(Ui.text(a, s.lines.get(i), 12, Ui.MUTED, false));
            ImageView img = new ImageView(a);
            img.setAdjustViewBounds(true);
            img.setScaleType(ImageView.ScaleType.FIT_CENTER);
            if (bmp != null) img.setImageBitmap(bmp);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(Ui.dp(a, 260), LinearLayout.LayoutParams.WRAP_CONTENT);
            lp.topMargin = Ui.dp(a, 8);
            card.addView(img, lp);
            card.addView(Ui.label(a, s.isPublic ? "PUBLIC LINK (NO LOGIN)" : "WEBSITE LINK (LOGIN REQUIRED - FALLBACK)"), Ui.matchWrap(a, 8));
            card.addView(Ui.text(a, s.url, 11.5f, Ui.TEAL_DARK, false));
            if (!s.note.isEmpty()) card.addView(Ui.text(a, s.note, 11.5f, Ui.AMBER_FG, false), Ui.matchWrap(a, 4));
            LinearLayout links = Ui.hbox(a);
            Button copy = Ui.outline(a, "Copy", Ui.TEAL), share = Ui.outline(a, "Share", Ui.TEAL), open = Ui.outline(a, "Open", Ui.TEAL);
            links.addView(copy, Ui.weight(1));
            links.addView(share, Ui.weight(1));
            links.addView(open, Ui.weight(1));
            card.addView(links, Ui.matchWrap(a, 6));
            copy.setOnClickListener(v -> copy(a, s.url));
            share.setOnClickListener(v -> shareText(a, "RMTC " + s.number + " · documents", "RMTC " + s.number + " · open / download all RMTC documents: " + s.url));
            open.setOnClickListener(v -> a.openInBrowser(s.url));  // public Edge Function page (external browser)
            box.addView(card, Ui.matchWrap(a, 4));

            // ---- documents
            LinearLayout dc = Ui.card(a);
            dc.addView(Ui.text(a, "RMTC DOCUMENTS · " + docs.size(), 13, Ui.TEXT, true));
            dc.addView(Ui.text(a, "Certificate first, then every RMTC attachment - the same list the public page shows.", 11, Ui.MUTED, false));
            if (docs.isEmpty()) dc.addView(Ui.empty(a, "No RMTC document stored yet." + (manage ? " Use Refresh certificate." : "")));
            for (IncQrPublic.Doc d : docs) {
                LinearLayout row = Ui.vbox(a);
                row.addView(Ui.text(a, d.title, 12.5f, Ui.TEXT, true), Ui.matchWrap(a, 8));
                row.addView(Ui.text(a, d.name + (d.size > 0 ? " · " + Ui.num(d.size / 1024.0, 0) + " KB" : ""), 11, Ui.MUTED, false));
                LinearLayout acts = Ui.hbox(a);
                Button view = Ui.outline(a, "View / Download", Ui.TEAL);
                acts.addView(view, Ui.weight(1));
                view.setOnClickListener(v -> Api.async(() -> api.download(d.path), (bytes, err) -> {
                    if (err != null || bytes == null) { a.toast("Could not download " + d.name + ": " + Api.message(err)); return; }
                    IncQrLabel.fileActions(a, d.name, d.mime, bytes);
                }));
                if (s.isPublic) {
                    Button pub = Ui.outline(a, "Public link", Ui.TEAL_DARK);
                    acts.addView(pub, Ui.weight(1));
                    pub.setOnClickListener(v -> a.openInBrowser(IncQrPublic.docUrl(s.token, d.id)));
                }
                row.addView(acts, Ui.matchWrap(a, 4));
                dc.addView(row);
            }
            if (s.isPublic) {
                Button zip = Ui.primary(a, "⇩ Download all (ZIP)");
                dc.addView(zip, Ui.matchWrap(a, 10));
                zip.setOnClickListener(v -> downloadAll(a, IncQrPublic.zipUrl(s.token), s.stem + "_documents.zip", "application/zip"));
                Button pdf = Ui.outline(a, "⇩ Download all as one PDF", Ui.TEAL);
                dc.addView(pdf, Ui.matchWrap(a, 6));
                pdf.setOnClickListener(v -> downloadAll(a, IncQrPublic.pdfUrl(s.token), s.stem + "_documents.pdf", IncQrLabel.PDF));
            }
            box.addView(dc, Ui.matchWrap(a, 10));

            // ---- QR files
            LinearLayout fc = Ui.card(a);
            fc.addView(Ui.text(a, "QR FILES", 13, Ui.TEXT, true));
            IncQrLabel.addFileButton(a, fc, "⇩ QR PNG · Save / Share", s.stem + "_QR.png", IncQrLabel.PNG, () -> IncQrLabel.png(s));
            IncQrLabel.addFileButton(a, fc, "⇩ QR JPEG · Save / Share", s.stem + "_QR.jpg", IncQrLabel.JPEG, () -> IncQrLabel.jpeg(s));
            IncQrLabel.addFileButton(a, fc, "⇩ QR PDF (A6) · View / Save / Share / Print", s.stem + "_QR.pdf", IncQrLabel.PDF, () -> IncQrLabel.pdf(s));
            IncQrLabel.addFileButton(a, fc, "🖨 Print Label PDF (100 x 60 mm)", s.stem + "_QR_Label.pdf", IncQrLabel.PDF, () -> IncQrLabel.labelPdf(s));
            box.addView(fc, Ui.matchWrap(a, 10));

            // ---- manage (RMTC edit / approve rights)
            if (!manage) return;
            LinearLayout mc = Ui.card(a);
            mc.addView(Ui.text(a, "MANAGE PUBLIC QR", 13, Ui.TEXT, true));
            Button refresh = Ui.outline(a, "Refresh certificate", Ui.TEAL);
            mc.addView(refresh, Ui.matchWrap(a, 6));
            refresh.setOnClickListener(v -> {
                refresh.setEnabled(false);
                a.toast("Regenerating the RMTC certificate PDF…");
                Api.async(() -> IncQrPublic.refreshCertificate(api, rec), (l, err) -> {
                    refresh.setEnabled(true);
                    a.toast(err != null ? "Certificate not refreshed: " + Api.message(err) : "Certificate refreshed for the public QR.");
                    reload();
                });
            });
            Button revoke = Ui.outline(a, "Revoke QR (new code)", Ui.RED_FG);
            mc.addView(revoke, Ui.matchWrap(a, 6));
            revoke.setOnClickListener(v -> a.confirm("Revoke QR", "The current QR / link stops working immediately and a NEW code is created. "
                + "Printed labels with the old QR must be replaced. Continue?", "Revoke", () -> {
                revoke.setEnabled(false);
                Api.async(() -> IncQrPublic.revoke(api, rec), (l, err) -> {
                    revoke.setEnabled(true);
                    a.toast(err != null ? "Not revoked: " + Api.message(err) : "Old QR revoked; new public QR created. Print the new label.");
                    reload();
                });
            }));
            box.addView(mc, Ui.matchWrap(a, 10));
        }
    }
}
