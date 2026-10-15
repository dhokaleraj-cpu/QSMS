package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Part Master section D · Customer standards & specifications (part_standard_links, add-only): choices are
 * ACTIVE customer_standards that are general or of the part's customer and not linked yet; each new link gets
 * sequence_no = max + 10. Unlinking stays an Administrator password delete (website).
 */
public final class MstPartStandardsScreen extends Screen {
    private final JSONObject part;
    private final String partId;

    public MstPartStandardsScreen(MainActivity a, JSONObject part) { super(a); this.part = part; this.partId = Lookups.j(part, "id"); }

    @Override public String title() { return "Standards"; }
    @Override public String subtitle() { return MstPartGrid.partLabel(part); }
    @Override public int tab() { return Catalog.MASTERS; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONArray standards = api.rows("customer_standards?select=id,standard_code,standard_name,customer_id,process_id,author_name,revision_number,revision_date,status&status=eq.ACTIVE&order=standard_code.asc&limit=3000");
            JSONArray processes = api.rows("processes?select=id,process_code,process_name,process_type&limit=3000");
            JSONArray parties = api.rows("parties?select=id,party_code,party_name,city&limit=3000");
            JSONArray links = api.rows("part_standard_links?select=*&part_id=eq." + Api.enc(partId) + "&order=sequence_no.asc&limit=1000");
            JSONArray att = api.rows("document_attachments?select=entity_id,document_type,file_name,object_path&entity_type=eq.CUSTOMER_STANDARD&document_type=eq.STANDARD_DOCUMENT&status=eq.ACTIVE&limit=5000");
            return new JSONArray[]{standards, processes, parties, links, att};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            render(res[0], res[1], res[2], res[3], res[4]);
        });
        return scroll;
    }

    private static Map<String, JSONObject> byId(JSONArray rows) {
        Map<String, JSONObject> m = new HashMap<>();
        for (int i = 0; i < rows.length(); i++) m.put(Lookups.j(rows.optJSONObject(i), "id"), rows.optJSONObject(i));
        return m;
    }

    private void render(JSONArray standards, JSONArray processes, JSONArray parties, JSONArray links, JSONArray att) {
        offlineNote();
        Map<String, JSONObject> proc = byId(processes), party = byId(parties);
        Map<String, JSONObject> attByStd = new HashMap<>();
        for (int i = 0; i < att.length(); i++) attByStd.put(Lookups.j(att.optJSONObject(i), "entity_id"), att.optJSONObject(i));
        String customer = Lookups.j(part, "customer_id");
        Set<String> linked = new HashSet<>();
        int maxSeq = 0;
        for (int i = 0; i < links.length(); i++) {
            JSONObject l = links.optJSONObject(i);
            linked.add(Lookups.j(l, "standard_id"));
            maxSeq = Math.max(maxSeq, l.optInt("sequence_no", 0));
        }
        List<String> ids = new ArrayList<>(), names = new ArrayList<>();
        Map<String, JSONObject> std = new HashMap<>();
        for (int i = 0; i < standards.length(); i++) {
            JSONObject s = standards.optJSONObject(i);
            std.put(Lookups.j(s, "id"), s);
            String c = Lookups.j(s, "customer_id");
            if (!c.isEmpty() && !c.equals(customer)) continue;
            if (linked.contains(Lookups.j(s, "id"))) continue;
            ids.add(Lookups.j(s, "id"));
            names.add(label(s, proc, party));
        }
        if (ids.isEmpty()) {
            add(MstForm.noteCard(a, "No further active Customer Standards / Specifications are available for this Part's customer. Create them in Masters → Customer standards."), 0);
        } else {
            Field f = Field.multi("standards", "Add Customer Standards / Specifications", ids.toArray(new String[0])).labels(names.toArray(new String[0]));
            f.hint = "Existing links remain protected. Unlinking a Standard requires the QCMS Administrator (password delete).";
            FormView form = new FormView(a, Arrays.asList(f));
            add(form, 0);
            Button addBtn = Ui.primary(a, "Add Selected Standards");
            add(addBtn, 10);
            final int start = maxSeq;
            addBtn.setOnClickListener(v -> {
                final JSONArray chosen;
                try { chosen = form.json().optJSONArray("standards"); } catch (Exception e) { a.toast(Api.message(e)); return; }
                if (chosen == null || chosen.length() == 0) { a.toast("Select one or more standards first."); return; }
                addBtn.setEnabled(false);
                Api.async(() -> {
                    JSONArray current = new JSONArray(api.get("part_standard_links?select=standard_id,sequence_no&part_id=eq." + Api.enc(partId) + "&limit=1000", false).body);
                    Set<String> have = new HashSet<>();
                    int next = start;
                    for (int i = 0; i < current.length(); i++) { have.add(Lookups.j(current.getJSONObject(i), "standard_id")); next = Math.max(next, current.getJSONObject(i).optInt("sequence_no", 0)); }
                    next += 10;
                    int n = 0;
                    for (int i = 0; i < chosen.length(); i++) {
                        String sid = chosen.optString(i);
                        if (have.contains(sid)) continue;
                        api.insert("part_standard_links", new JSONObject().put("part_id", partId).put("standard_id", sid).put("sequence_no", next).put("status", "ACTIVE"));
                        next += 10;
                        n++;
                    }
                    return n;
                }, (n, err) -> {
                    addBtn.setEnabled(true);
                    if (err != null) { a.toast(Api.message(err)); return; }
                    a.toast("Selected Customer Standards / Specifications linked successfully (" + n + ").");
                    a.rebuild();
                });
            });
        }
        add(Ui.label(a, "Linked standards"), 14);
        List<List<String>> data = new ArrayList<>();
        List<String> paths = new ArrayList<>();
        for (int i = 0; i < links.length(); i++) {
            JSONObject l = links.optJSONObject(i);
            if (!"ACTIVE".equals(Lookups.j(l, "status"))) continue;
            JSONObject s = std.get(Lookups.j(l, "standard_id"));
            if (s == null) continue;
            JSONObject at = attByStd.get(Lookups.j(s, "id"));
            JSONObject cust = party.get(Lookups.j(s, "customer_id"));
            data.add(Arrays.asList(Lookups.j(s, "standard_code"), Lookups.j(s, "standard_name"), Lookups.j(s, "revision_number"), Ui.date(Lookups.j(s, "revision_date")),
                proc.containsKey(Lookups.j(s, "process_id")) ? Lookups.PROCESS.of(proc.get(Lookups.j(s, "process_id"))) : "-",
                cust == null ? "General" : Lookups.PARTY.of(cust), Lookups.j(s, "author_name"), at == null ? "Not attached" : Lookups.j(at, "file_name") + " (tap to open)"));
            paths.add(at == null ? "" : Lookups.j(at, "object_path"));
        }
        if (data.isEmpty()) { add(Ui.empty(a, "No standards linked to this Part yet."), 2); return; }
        add(new DataGrid(a, "Linked standards", Arrays.asList("Code", "Standard / Specification", "Revision", "Revision Date", "Related Process", "Customer", "Author", "Attachment"),
            data, 320, index -> {
                String path = paths.get(index);
                if (path.isEmpty()) { a.toast("No attachment for this standard."); return; }
                Api.async(() -> Attachments.signedUrl(api, path), (url, e) -> { if (e != null) a.toast(Api.message(e)); else a.openInBrowser(url); });
            }), 2);
    }

    private static String label(JSONObject s, Map<String, JSONObject> proc, Map<String, JSONObject> party) {
        JSONObject c = party.get(Lookups.j(s, "customer_id"));
        JSONObject p = proc.get(Lookups.j(s, "process_id"));
        return Lookups.join(Lookups.j(s, "standard_code"), Lookups.j(s, "standard_name"), "Rev " + Lookups.j(s, "revision_number"),
            p == null ? "" : Lookups.j(p, "process_name"), c == null ? "General" : Lookups.j(c, "party_name"));
    }
}
