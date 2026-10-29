package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

/**
 * Part Master sections B + C · Controlled drawings: a new revision is uploaded to quality-documents at
 * {tenant}/parts/{part}/controlled_drawings/{type}/{drawing}/{rev}_{uuid10}{ext} and activated with
 * qcms_activate_part_drawing_revision (previous revision becomes INACTIVE, FINISH feeds parts.drawing_*).
 * If the RPC fails the uploaded file is removed again. R39 (web R38): replacing the CURRENT revision of a drawing type opens
 * the mandatory ECN (EcnFormScreen release: create ECN, release, link; ECN cancelled when the release fails).
 */
public final class MstPartDrawingsScreen extends Screen {
    static final String[] TYPES = {"FINISH_DRAWING", "FORGING_DRAWING", "HEAT_TREATMENT_DRAWING"};
    static final String[] TYPE_LABELS = {"Finish Drawing", "Forging Drawing", "Heat Treatment Drawing"};

    private final JSONObject part;
    private final String partId;
    private JSONArray drawings = new JSONArray();
    private FormView form;
    private Attachments.FileData file;
    private TextView fileText;
    private Button release;

    public MstPartDrawingsScreen(MainActivity a, JSONObject part) { super(a); this.part = part; this.partId = Lookups.j(part, "id"); }

    @Override public String title() { return "Controlled drawings"; }
    @Override public String subtitle() { return MstPartGrid.partLabel(part); }
    @Override public int tab() { return Catalog.MASTERS; }

    static String typeLabel(String t) {
        for (int i = 0; i < TYPES.length; i++) if (TYPES[i].equals(t)) return TYPE_LABELS[i];
        return Ui.pretty(t);
    }

    /** part_master._storage_token. */
    static String token(String v) {
        String s = (v == null ? "" : v.trim()).replaceAll("[^a-zA-Z0-9._-]+", "_");
        s = s.replaceAll("^[._-]+|[._-]+$", "");
        return s.isEmpty() ? "drawing" : s;
    }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> api.rows("document_attachments?select=*&entity_type=eq.PART_MASTER&entity_id=eq." + Api.enc(partId) + "&order=created_at.desc&limit=500"),
            (rows, err) -> {
                page.removeAllViews();
                if (err != null) { page.addView(error(err, this::reload)); return; }
                drawings = new JSONArray();
                for (int i = 0; i < rows.length(); i++) if (Arrays.asList(TYPES).contains(Lookups.j(rows.optJSONObject(i), "document_type"))) drawings.put(rows.optJSONObject(i));
                render();
            });
        return scroll;
    }

    private JSONObject active(String type) {
        for (int i = 0; i < drawings.length(); i++) {
            JSONObject r = drawings.optJSONObject(i);
            if (type.equals(Lookups.j(r, "document_type")) && "ACTIVE".equalsIgnoreCase(Lookups.j(r, "status"))) return r;
        }
        return null;
    }

    private void open(JSONObject r) {
        String path = Lookups.j(r, "object_path");
        Api.async(() -> Attachments.signedUrl(api, path), (url, e) -> { if (e != null) a.toast(Api.message(e)); else a.openInBrowser(url); });
    }

    private void render() {
        offlineNote();
        if (!MstPartSections.isApplicable(part, "DRAWINGS"))
            add(MstForm.noteCard(a, "Controlled Drawings is marked NOT APPLICABLE for this Part (Sections applicable)."), 0);
        add(Ui.label(a, "Current ACTIVE drawings"), 0);
        for (int i = 0; i < TYPES.length; i++) {
            JSONObject cur = active(TYPES[i]);
            LinearLayout card = Ui.card(a);
            card.addView(Ui.text(a, TYPE_LABELS[i], 14, Ui.TEXT, true));
            card.addView(Ui.text(a, cur == null ? "No ACTIVE controlled drawing" : "ACTIVE · Drawing " + nz(Lookups.j(cur, "drawing_number")) + " · Rev "
                + nz(Lookups.j(cur, "revision")) + " · " + Ui.date(Lookups.j(cur, "revision_date")), 12, Ui.MUTED, false));
            if (cur != null) {
                TextView o = Ui.text(a, "Open current file", 13, Ui.TEAL_DARK, true);
                o.setPadding(0, dp(6), 0, 0);
                o.setOnClickListener(v -> open(cur));
                card.addView(o);
            }
            add(card, 6);
        }

        add(Ui.label(a, "Release new revision"), 14);
        List<Field> fields = new ArrayList<>();
        fields.add(Field.select("document_type", "Drawing Type", TYPES).labels(TYPE_LABELS).req().def("FINISH_DRAWING"));
        fields.add(Field.text("drawing_number", "Drawing Number").req());
        fields.add(Field.text("revision", "Revision Number").req());
        fields.add(Field.date("revision_date", "Revision Date").req().def(Ui.today()));
        form = new FormView(a, fields);
        form.onChange((k, v) -> { if ("document_type".equals(k)) defaultNumber(); });
        add(form, 0);
        defaultNumber();
        fileText = Ui.text(a, "No file selected (PDF, PNG, JPG, DWG, DXF)", 12, Ui.MUTED, false);
        add(fileText, 8);
        Button pick = Ui.outline(a, "Choose drawing file (camera or file)", Ui.TEAL);
        add(pick, 6);
        pick.setOnClickListener(v -> a.pickFile("Controlled Drawing File", false, f -> {
            file = f;
            fileText.setText(f.name + " · " + (f.data.length / 1024) + " KB");
            fileText.setTextColor(Ui.TEXT);
        }));
        release = Ui.primary(a, "Release New Revision");
        add(release, 10);
        release.setOnClickListener(v -> release());
        add(Ui.text(a, "Uploading a new revision automatically makes the previous revision of that type INACTIVE; old drawings stay downloadable below. "
            + "Replacing a current revision requires an Engineering Change Note (ECN) first - the ECN form opens and the revision is released with it.", 11.5f, Ui.MUTED, false), 6);

        add(Ui.label(a, "Drawing revision history"), 14);
        if (drawings.length() == 0) { add(Ui.empty(a, "No controlled drawing revisions have been released for this Part yet."), 2); return; }
        List<List<String>> data = new ArrayList<>();
        for (int i = 0; i < drawings.length(); i++) {
            JSONObject r = drawings.optJSONObject(i);
            data.add(Arrays.asList(typeLabel(Lookups.j(r, "document_type")), Lookups.j(r, "drawing_number"), Lookups.j(r, "revision"), Ui.date(Lookups.j(r, "revision_date")),
                Lookups.j(r, "status").toUpperCase(Locale.ROOT), Lookups.j(r, "file_name"), Ui.date(Lookups.j(r, "created_at")), Ui.date(Lookups.j(r, "superseded_at"))));
        }
        add(new DataGrid(a, "Drawing revisions", Arrays.asList("Drawing Type", "Drawing Number", "Revision Number", "Revision Date", "Status", "File (tap to open)", "Released At", "Superseded At"),
            data, 320, index -> open(drawings.optJSONObject(index))), 2);
    }

    private static String nz(String s) { return s.isEmpty() ? "-" : s; }

    private void defaultNumber() {
        String type = form.str("document_type");
        JSONObject cur = active(type.isEmpty() ? "FINISH_DRAWING" : type);
        String n = cur != null ? Lookups.j(cur, "drawing_number") : ("FINISH_DRAWING".equals(type) ? Lookups.j(part, "drawing_number") : "");
        form.set("drawing_number", n);
    }

    /** Activate-RPC result (object or one-row array) -> row with id / superseded_id. */
    static JSONObject rpcRow(String body) {
        String b = body == null ? "" : body.trim();
        try {
            if (b.startsWith("[")) { JSONArray arr = new JSONArray(b); return arr.length() > 0 && arr.optJSONObject(0) != null ? arr.getJSONObject(0) : new JSONObject(); }
            if (b.startsWith("{")) return new JSONObject(b);
        } catch (Exception ignored) { }
        return new JSONObject();
    }

    /** save_part_drawing_revision: storage upload + qcms_activate_part_drawing_revision (file removed again on failure). */
    static JSONObject releaseDrawing(Api api, String partId, String type, String number, String rev, String date, Attachments.FileData f) throws Exception {
        int dot = f.name.lastIndexOf('.');
        String ext = dot >= 0 && dot < f.name.length() - 1 ? f.name.substring(dot).toLowerCase(Locale.ROOT) : ".bin";
        String mime = f.mime == null || f.mime.isEmpty() ? "application/octet-stream" : f.mime;
        String path = api.tenantId + "/parts/" + partId + "/controlled_drawings/" + type.toLowerCase(Locale.ROOT) + "/" + token(number) + "/" + token(rev) + "_"
            + UUID.randomUUID().toString().replace("-", "").substring(0, 10) + ext;
        api.upload(path, f.data, mime, false);
        try {
            JSONObject args = new JSONObject();
            args.put("p_part_id", partId);
            args.put("p_document_type", type);
            args.put("p_drawing_number", number);
            args.put("p_revision", rev);
            args.put("p_revision_date", date.length() >= 10 ? date.substring(0, 10) : date);
            args.put("p_file_name", f.name);
            args.put("p_object_path", path);
            args.put("p_mime_type", mime);
            args.put("p_size_bytes", (long) f.data.length);
            args.put("p_checksum", MstSave.sha256(f.data));
            JSONObject row = rpcRow(api.rpc("qcms_activate_part_drawing_revision", args));
            if (Lookups.j(row, "id").isEmpty()) {
                // older RPC result without the row: find the released revision by its object path
                JSONArray r = api.rows("document_attachments?select=id&object_path=eq." + Api.enc(path) + "&limit=1");
                if (r.length() > 0) row.put("id", Lookups.j(r.getJSONObject(0), "id"));
            }
            return row;
        } catch (Exception e) {
            try { api.removeObject(path); } catch (Exception ignored) { }
            throw e;
        }
    }

    private void release() {
        String p = form.validate();
        if (p != null) { a.toast(p); return; }
        if (file == null) { a.toast("Select the controlled drawing file."); return; }
        if (file.data == null || file.data.length == 0) { a.toast("The selected drawing file is empty."); return; }
        final String type = form.str("document_type"), number = form.str("drawing_number").trim(), rev = form.str("revision").trim(), date = form.str("revision_date");
        final Attachments.FileData f = file;
        JSONObject cur = active(type);
        if (cur != null) {
            // R38 rule: replacing the CURRENT revision requires an ECN first (the form opens; nothing is released before it is saved).
            for (int i = 0; i < drawings.length(); i++) {
                JSONObject r = drawings.optJSONObject(i);
                if (type.equals(Lookups.j(r, "document_type")) && Lookups.j(r, "drawing_number").equalsIgnoreCase(number) && Lookups.j(r, "revision").equalsIgnoreCase(rev)) {
                    a.toast("This Drawing Number and Revision Number already exist in revision history.");
                    return;
                }
            }
            try {
                JSONObject d = EcnData.revisionDefaults(part, type, number, cur, rev, date, "", "");
                String text = "You are replacing " + typeLabel(type) + " " + number + " Rev " + nz(Lookups.j(cur, "revision")) + " with Rev " + rev + " (" + f.name + ").";
                a.push(new EcnFormScreen(a, d, null, () -> releaseDrawing(api, partId, type, number, rev, date, f), text));
            } catch (Exception e) { a.toast(Api.message(e)); }
            return;
        }
        release.setEnabled(false);
        release.setText("Uploading…");
        Api.async(() -> releaseDrawing(api, partId, type, number, rev, date, f), (ok, err) -> {
            release.setEnabled(true);
            release.setText("Release New Revision");
            if (err != null) { a.toast(Api.message(err)); return; }
            a.toast(typeLabel(type) + " " + number + " Rev " + rev + " released. Previous revision is now INACTIVE.");
            Lookups.invalidate();
            a.rebuild();
        });
    }
}
