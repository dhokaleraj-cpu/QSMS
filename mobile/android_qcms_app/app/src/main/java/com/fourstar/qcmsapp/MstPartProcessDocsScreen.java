package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/**
 * R39 · Process drawings & specifications of one Part process (app_pages/ecn.py render_part_processes, lower half;
 * core/part_process_service.save_process_document_revision): document_attachments entity_type PART_PROCESS,
 * entity_id = route id, document_type PROCESS_DRAWING | PROCESS_SPEC, revision no / date, CURRENT (ACTIVE) vs OBSOLETE
 * (superseded, still viewable / downloadable), linked ECN. A new revision is uploaded to quality-documents at
 * {tenant}/parts/{part}/process_documents/{route}/{type}/{number}/{rev}_{uuid10}{ext} and activated with
 * qcms_activate_part_process_document_revision. Replacing the CURRENT revision of the same number requires an ECN first
 * (EcnFormScreen release - create ECN, release, link; ECN cancelled when the release fails).
 */
public final class MstPartProcessDocsScreen extends Screen {
    static final String ENTITY = "PART_PROCESS";
    static final String[] TYPES = {"PROCESS_DRAWING", "PROCESS_SPEC"};
    static final String[] TYPE_LABELS = {"Process Drawing", "Process Specification"};

    private final JSONObject part, route;
    private final String processText;
    private List<JSONObject> docs = new ArrayList<>();
    private Map<String, String> ecnByAttachment = new HashMap<>();
    private boolean[] perms = {false, false, false};
    private FormView form;
    private Attachments.FileData file;
    private TextView fileText;
    private Button release;

    public MstPartProcessDocsScreen(MainActivity a, JSONObject part, JSONObject route, String processName) {
        super(a);
        this.part = part;
        this.route = route;
        this.processText = "Op " + MstPartProcessScreen.op(route) + " · " + processName;
    }

    @Override public String title() { return "Process drawings & specs"; }
    @Override public String subtitle() { return processText + " · " + Lookups.j(part, "part_number"); }
    @Override public int tab() { return Catalog.MASTERS; }

    static String typeLabel(String t) {
        for (int i = 0; i < TYPES.length; i++) if (TYPES[i].equals(t)) return TYPE_LABELS[i];
        return Ui.pretty(t);
    }

    /** revision_status: ACTIVE = CURRENT, anything else = OBSOLETE. */
    static String revisionStatus(JSONObject d) { return "ACTIVE".equalsIgnoreCase(Lookups.j(d, "status")) ? "CURRENT" : "OBSOLETE"; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        final String routeId = Lookups.j(route, "id");
        Api.async(() -> {
            boolean[] p = EcnData.permissions(api);
            List<JSONObject> d = new ArrayList<>();
            for (JSONObject r : EcnData.list(api.rows("document_attachments?select=*&entity_type=eq." + ENTITY + "&entity_id=eq." + Api.enc(routeId) + "&order=created_at.desc&limit=500")))
                if (Arrays.asList(TYPES).contains(Lookups.j(r, "document_type"))) d.add(r);
            Map<String, String> ecn = new HashMap<>();
            for (JSONObject e : EcnData.list(api.rows("part_ecns?select=ecn_number,document_attachment_id&part_id=eq." + Api.enc(Lookups.j(part, "id")) + "&document_attachment_id=not.is.null&limit=2000")))
                ecn.put(Lookups.j(e, "document_attachment_id"), Lookups.j(e, "ecn_number"));
            return new Object[]{p, d, ecn};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            perms = (boolean[]) res[0];
            docs = EcnData.cast(res[1]);
            @SuppressWarnings("unchecked") Map<String, String> e = (Map<String, String>) res[2];
            ecnByAttachment = e;
            render();
        });
        return scroll;
    }

    private boolean writable() { return perms[0] || perms[1]; }

    private void open(JSONObject r) {
        String path = Lookups.j(r, "object_path");
        Api.async(() -> Attachments.signedUrl(api, path), (url, e) -> { if (e != null) a.toast(Api.message(e)); else a.openInBrowser(url); });
    }

    private void render() {
        offlineNote();
        add(Ui.label(a, "Revision history (tap a row to view / download)"), 0);
        if (docs.isEmpty()) add(Ui.empty(a, "No process drawings / specifications released for this process yet (optional)."), 2);
        else {
            List<List<String>> data = new ArrayList<>();
            for (JSONObject d : docs) {
                data.add(Arrays.asList(typeLabel(Lookups.j(d, "document_type")), Lookups.j(d, "drawing_number"), Lookups.j(d, "document_title"), Lookups.j(d, "revision"),
                    Ui.date(Lookups.j(d, "revision_date")), revisionStatus(d), Lookups.j(d, "file_name"), Ui.date(Lookups.j(d, "created_at")),
                    ecnByAttachment.containsKey(Lookups.j(d, "id")) ? ecnByAttachment.get(Lookups.j(d, "id")) : ""));
            }
            add(new DataGrid(a, "Process drawings / specifications", Arrays.asList("Type", "Drawing / Spec No.", "Title / Description", "Rev No.", "Rev Date",
                "Status", "File", "Uploaded At", "ECN"), data, 320, index -> open(docs.get(index))), 2);
        }
        if (!writable()) { add(Ui.text(a, "Part Master create / edit permission is required to release a revision.", 12, Ui.MUTED, false), 10); return; }

        add(Ui.label(a, "Release a process drawing / specification revision"), 14);
        List<Field> f = new ArrayList<>();
        f.add(Field.select("document_type", "Document Type", TYPES).labels(TYPE_LABELS).req().def("PROCESS_DRAWING"));
        f.add(Field.text("document_number", "Drawing / Spec No.").req().hint("An existing number releases its next revision (ECN required); a new number starts a new document."));
        f.add(Field.text("document_title", "Title / Description"));
        f.add(Field.text("revision", "Revision Number").req());
        f.add(Field.date("revision_date", "Revision Date").req().def(Ui.today()));
        form = new FormView(a, f);
        form.onChange((k, v) -> { if ("document_type".equals(k)) defaultNumber(); });
        add(form, 0);
        form.set("revision_date", Ui.today());
        defaultNumber();
        fileText = Ui.text(a, "No file selected (PDF, PNG, JPG, DWG, DXF, XLSX, DOCX)", 12, Ui.MUTED, false);
        add(fileText, 8);
        Button pick = Ui.outline(a, "Choose file (camera or file)", Ui.TEAL);
        pick.setOnClickListener(v -> a.pickFile("Process drawing / specification", false, fd -> {
            file = fd;
            fileText.setText(fd.name + " · " + (fd.data.length / 1024) + " KB");
            fileText.setTextColor(Ui.TEXT);
        }));
        add(pick, 6);
        release = Ui.primary(a, "Release Process Document Revision");
        release.setOnClickListener(v -> release());
        add(release, 10);
        add(Ui.text(a, "Releasing a new revision of an existing number makes the previous revision OBSOLETE (still downloadable) and needs an ECN.", 11.5f, Ui.MUTED, false), 6);
    }

    private JSONObject current(String type, String number) {
        for (JSONObject d : docs)
            if (type.equals(Lookups.j(d, "document_type")) && "ACTIVE".equalsIgnoreCase(Lookups.j(d, "status")) && Lookups.j(d, "drawing_number").equalsIgnoreCase(number)) return d;
        return null;
    }

    private void defaultNumber() {
        if (form == null) return;
        String type = form.str("document_type").isEmpty() ? "PROCESS_DRAWING" : form.str("document_type");
        for (JSONObject d : docs)
            if (type.equals(Lookups.j(d, "document_type")) && "ACTIVE".equalsIgnoreCase(Lookups.j(d, "status"))) { form.set("document_number", Lookups.j(d, "drawing_number")); return; }
        form.set("document_number", "");
    }

    /** save_process_document_revision: storage upload + qcms_activate_part_process_document_revision (file removed again on failure). */
    static JSONObject releaseRevision(Api api, JSONObject route, String type, String number, String title, String rev, String date, Attachments.FileData f) throws Exception {
        if (f == null) throw new Api.ApiException(422, "Select the controlled file.");
        if (f.data == null || f.data.length == 0) throw new Api.ApiException(422, "The selected file is empty.");
        int dot = f.name.lastIndexOf('.');
        String ext = dot >= 0 && dot < f.name.length() - 1 ? f.name.substring(dot).toLowerCase(Locale.ROOT) : ".bin";
        String mime = f.mime == null || f.mime.isEmpty() ? "application/octet-stream" : f.mime;
        String path = api.tenantId + "/parts/" + Lookups.j(route, "part_id") + "/process_documents/" + Lookups.j(route, "id") + "/" + type.toLowerCase(Locale.ROOT) + "/"
            + MstPartDrawingsScreen.token(number) + "/" + MstPartDrawingsScreen.token(rev) + "_" + UUID.randomUUID().toString().replace("-", "").substring(0, 10) + ext;
        api.upload(path, f.data, mime, false);
        try {
            JSONObject args = new JSONObject();
            args.put("p_process_route_id", Lookups.j(route, "id"));
            args.put("p_document_type", type);
            args.put("p_document_number", number);
            args.put("p_document_title", title == null || title.trim().isEmpty() ? JSONObject.NULL : title.trim());
            args.put("p_revision", rev);
            args.put("p_revision_date", date.length() >= 10 ? date.substring(0, 10) : date);
            args.put("p_file_name", f.name);
            args.put("p_object_path", path);
            args.put("p_mime_type", mime);
            args.put("p_size_bytes", (long) f.data.length);
            args.put("p_checksum", MstSave.sha256(f.data));
            return MstPartDrawingsScreen.rpcRow(api.rpc("qcms_activate_part_process_document_revision", args));
        } catch (Exception e) {
            try { api.removeObject(path); } catch (Exception ignored) { }
            throw e;
        }
    }

    private void release() {
        String p = form.validate();
        if (p != null) { a.toast(p); return; }
        if (file == null) { a.toast("Select the controlled file."); return; }
        if (file.data == null || file.data.length == 0) { a.toast("The selected file is empty."); return; }
        final String type = form.str("document_type"), number = form.str("document_number").trim(), title = form.str("document_title").trim(),
            rev = form.str("revision").trim(), date = form.str("revision_date");
        for (JSONObject d : docs)
            if (type.equals(Lookups.j(d, "document_type")) && Lookups.j(d, "drawing_number").equalsIgnoreCase(number) && Lookups.j(d, "revision").equalsIgnoreCase(rev)) {
                a.toast("This Drawing / Specification Number and Revision Number already exist in revision history.");
                return;
            }
        final Attachments.FileData f = file;
        JSONObject cur = current(type, number);
        if (cur != null) {
            // Replacing the CURRENT revision needs an ECN - nothing is released before the ECN is saved.
            try {
                JSONObject d = EcnData.revisionDefaults(part, type, number, cur, rev, date, processText, title);
                d.put("process_route_id", Lookups.j(route, "id"));
                String text = "You are replacing " + typeLabel(type) + " " + number + " Rev " + (Lookups.j(cur, "revision").isEmpty() ? "-" : Lookups.j(cur, "revision"))
                    + " (" + processText + ") with Rev " + rev + " (" + f.name + ").";
                a.push(new EcnFormScreen(a, d, null, () -> releaseRevision(api, route, type, number, title, rev, date, f), text));
            } catch (Exception e) { a.toast(Api.message(e)); }
            return;
        }
        release.setEnabled(false);
        release.setText("Uploading…");
        Api.async(() -> releaseRevision(api, route, type, number, title, rev, date, f), (ok, err) -> {
            release.setEnabled(true);
            release.setText("Release Process Document Revision");
            if (err != null) { a.toast(Api.message(err)); return; }
            a.toast(typeLabel(type) + " " + number + " Rev " + rev + " released.");
            a.rebuild();
        });
    }
}
