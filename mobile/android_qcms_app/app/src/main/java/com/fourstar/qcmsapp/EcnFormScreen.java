package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

/**
 * R39 · ECN / PCN form in the FSI/806/F05 field order (app_pages/ecn.py ecn_form): new note (DRAFT / Submit), edit
 * (after submission only the FSI-use / approval / completion block and comments), and the MANDATORY ECN of a drawing /
 * process document replacement: the new revision is released together with its ECN (release_with_ecn - create the
 * ECN, release, link the released revision; the ECN is CANCELLED when the release fails).
 */
public final class EcnFormScreen extends Screen {
    /** Releases the pending revision; returns the activate RPC row (id, superseded_id). */
    public interface Release { JSONObject run() throws Exception; }

    private final JSONObject defaults;
    private final JSONObject existing;
    private final Release release;
    private final String releaseText;
    private FormView form;
    private TextView problem;
    private final List<Button> buttons = new ArrayList<>();
    private Map<String, String> employees;

    /** existing = saved ECN to edit (null = new); release = pending drawing replacement (null = plain ECN / PCN). */
    public EcnFormScreen(MainActivity a, JSONObject defaults, JSONObject existing, Release release, String releaseText) {
        super(a);
        this.defaults = defaults == null ? new JSONObject() : defaults;
        this.existing = existing;
        this.release = release;
        this.releaseText = releaseText;
    }

    @Override public String title() {
        if (existing != null) return "Edit " + EcnData.s(existing, "ecn_number");
        return release != null ? "ECN required" : "New " + ("PCN".equalsIgnoreCase(EcnData.s(defaults, "change_type")) ? "PCN" : "ECN");
    }
    @Override public String subtitle() { return "Engineering / Process Change Note · " + EcnData.FORMAT_NO + " Rev " + EcnData.FORMAT_REV_NO; }
    @Override public int tab() { return Catalog.MASTERS; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            Map<String, String> emp = EcnData.employees(api);
            JSONObject d = new JSONObject((existing != null ? existing : defaults).toString());
            if (existing == null && (d.optJSONArray("fsi_representative_ids") == null || d.optJSONArray("fsi_representative_ids").length() == 0) && !api.employeeId.isEmpty())
                d.put("fsi_representative_ids", new JSONArray().put(api.employeeId));   // default_representative = the signed-in employee
            return new Object[]{emp, d};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            @SuppressWarnings("unchecked") Map<String, String> emp = (Map<String, String>) res[0];
            employees = emp;
            render((JSONObject) res[1]);
        });
        return scroll;
    }

    private void render(JSONObject d) {
        String status = existing == null ? "DRAFT" : EcnData.status(existing);
        boolean locked = existing != null && !EcnData.EDITABLE.contains(status);
        if (release != null) add(MstForm.noteCard(a, releaseText + "\n\nComplete the Engineering Change Note: the new revision is released together with the ECN "
            + "(Save as DRAFT or Submit for approval). Nothing is saved if you go back."), 2);
        if (locked) add(MstForm.noteCard(a, "After submission only the FSI-use / approval / completion block and comments can be changed."), 2);
        String[] empIds = employees.keySet().toArray(new String[0]);
        String[] empNames = employees.values().toArray(new String[0]);
        List<Field> f = new ArrayList<>();
        f.add(hdr(Field.select("change_type", "Type", "ECN", "PCN").labels("ECN · Engineering Change Note", "PCN · Process Change Note").req().def("ECN"), locked || existing != null));
        f.add(hdr(Field.date("ecn_date", "Date").def(Ui.today()), locked));
        f.add(hdr(Field.select("requested_priority", "Requested Priority & Response", EcnData.PRIORITIES).def("Normal"), locked));
        f.add(hdr(Field.date("response_by", "Request Response By"), locked));
        f.add(hdr(Field.text("response_by_party", "Response From").def("FSI"), locked));
        f.add(hdr(Field.multi("fsi_representative_ids", "FSI Representative(s)", empIds).labels(empNames), locked));
        f.add(hdr(Field.text("fsi_representatives_text", "Other FSI Representative(s) (optional text)"), locked));
        for (String[] who : new String[][]{{"to_contact", "To"}, {"cc_contact", "CC"}, {"from_contact", "From"}})
            for (String[] c : EcnData.CONTACTS) f.add(hdr(Field.text(who[0] + "." + c[0], who[1] + " · " + c[1]), locked));
        f.add(hdr(Field.text("drawing_number", "Drawing No."), locked));
        f.add(hdr(Field.text("part_number", "Part No.").req(), locked));
        f.add(hdr(Field.text("part_name", "Part Name"), locked));
        f.add(hdr(Field.text("previous_revision", "Revision From"), locked));
        f.add(hdr(Field.text("new_revision", "Revision To"), locked));
        f.add(hdr(Field.area("previous_description", "Previous Description"), locked));
        f.add(hdr(Field.area("revision_requested", "Revision Requested (new description)").req(), locked));
        for (String[] s : EcnData.SUPPORTING) f.add(hdr(Field.bool("sup." + s[0], "Supporting document · " + s[1]), locked));
        f.add(hdr(Field.bool("po_affected", "Purchase Orders Affected"), locked));
        f.add(hdr(Field.bool("inventory_affected", "Current Inventory Affected"), locked));
        f.add(hdr(Field.number("inventory_qty", "Inventory Qty.").range(0, 1e12), locked));
        f.add(hdr(Field.bool("demands_affected", "Current Demands Affected"), locked));
        f.add(hdr(Field.number("demands_qty", "Demands Qty.").range(0, 1e12), locked));
        f.add(Field.select("drawing_change_mode", "Drawing change to occur", EcnData.MODES).labels(EcnData.MODE_LABELS).def("AS_SUGGESTED"));
        f.add(Field.text("customer_name_text", "Customer (for approval)"));
        f.add(Field.select("customer_approval", "Customer Approval", EcnData.CUSTOMER_APPROVALS).labels(EcnData.pretty(EcnData.CUSTOMER_APPROVALS)).def("PENDING"));
        f.add(Field.text("customer_approver_name", "Customer Approval Signatory"));
        f.add(Field.lookup("fsi_approver_employee_id", "FSI Approval Signatory", Lookups.employees()));
        f.add(Field.date("fsi_approval_date", "FSI Approval Date"));
        f.add(Field.date("customer_approval_date", "Customer Approval Date"));
        f.add(Field.lookup("completed_by_employee_id", "Completed By", Lookups.employees()));
        f.add(Field.date("completed_date", "Completed Date"));
        f.add(Field.area("comments", "Comments"));
        f.add(Field.area("benefit_of_change", "Benefit to this Change"));
        f.add(Field.multi("email_employee_ids", "E-mail this ECN print to (employees, optional)", empIds).labels(empNames)
            .hint("Every new ECN / PCN is also e-mailed to Quality + NPD (event ECN_CREATED)."));
        form = new FormView(a, f);
        add(form, 6);
        form.setAll(d);
        for (String who : new String[]{"to_contact", "cc_contact", "from_contact"}) {
            JSONObject c = d.optJSONObject(who);
            if (c != null) for (String[] x : EcnData.CONTACTS) form.set(who + "." + x[0], EcnData.s(c, x[0]));
        }
        JSONObject sup = d.optJSONObject("supporting_documents");
        if (sup != null) for (String[] s : EcnData.SUPPORTING) form.set("sup." + s[0], sup.optBoolean(s[0], false));
        if (EcnData.s(d, "ecn_date").isEmpty()) form.set("ecn_date", Ui.today());
        if (EcnData.s(d, "response_by_party").isEmpty()) form.set("response_by_party", "FSI");
        problem = Ui.text(a, "", 13, Ui.RED_FG, false);
        problem.setVisibility(View.GONE);
        add(problem, 8);
        LinearLayout box = Ui.vbox(a);
        if (existing != null) {
            box.addView(btn("Save ECN", true, v -> submit(null)), Ui.matchWrap(a, 0));
        } else if (release != null) {
            box.addView(btn("Save ECN as DRAFT & Release Revision", true, v -> submit("DRAFT")), Ui.matchWrap(a, 0));
            box.addView(btn("Submit ECN for Approval & Release Revision", false, v -> submit("PENDING_APPROVAL")), Ui.matchWrap(a, 8));
        } else {
            box.addView(btn("Save as DRAFT", true, v -> submit("DRAFT")), Ui.matchWrap(a, 0));
            box.addView(btn("Submit for Approval", false, v -> submit("PENDING_APPROVAL")), Ui.matchWrap(a, 8));
        }
        add(box, 10);
        add(Ui.text(a, "Print / e-mail the ECN from the ECN record (Print layout PDF → Email from QCMS).", 11.5f, Ui.MUTED, false), 6);
    }

    private static Field hdr(Field f, boolean locked) { if (locked) f.readOnly = true; return f; }

    private Button btn(String label, boolean primary, View.OnClickListener l) {
        Button b = primary ? Ui.primary(a, label) : Ui.outline(a, label, Ui.TEAL);
        b.setOnClickListener(l);
        buttons.add(b);
        return b;
    }

    /** Form -> part_ecns payload (normalize_ecn_payload). */
    private JSONObject payload() throws Exception {
        JSONObject v = form.json();
        JSONObject p = new JSONObject();
        for (String k : new String[]{"part_id", "process_route_id", "document_scope", "previous_attachment_id", "plant_code"})
            if (!EcnData.s(defaults, k).isEmpty() && existing == null) p.put(k, EcnData.s(defaults, k));
        Iterator<String> it = v.keys();
        JSONObject sup = new JSONObject();
        JSONObject[] contacts = {new JSONObject(), new JSONObject(), new JSONObject()};
        String[] who = {"to_contact", "cc_contact", "from_contact"};
        while (it.hasNext()) {
            String k = it.next();
            Object val = v.opt(k);
            if (k.startsWith("sup.")) { sup.put(k.substring(4), Boolean.TRUE.equals(val)); continue; }
            boolean done = false;
            for (int i = 0; i < 3; i++) if (k.startsWith(who[i] + ".")) { contacts[i].put(k.substring(who[i].length() + 1), val == JSONObject.NULL ? "" : String.valueOf(val)); done = true; }
            if (done) continue;
            if (k.endsWith("_date") || k.equals("response_by")) val = val == JSONObject.NULL ? val : EcnData.iso(String.valueOf(val));
            p.put(k, val);
        }
        p.put("supporting_documents", sup);
        for (int i = 0; i < 3; i++) p.put(who[i], contacts[i]);
        if (!p.optBoolean("inventory_affected", false)) p.put("inventory_qty", JSONObject.NULL);
        if (!p.optBoolean("demands_affected", false)) p.put("demands_qty", JSONObject.NULL);
        if (p.optJSONArray("fsi_representative_ids") == null) p.put("fsi_representative_ids", new JSONArray());
        if (release != null) p.put("change_type", "ECN");   // a drawing / spec replacement is an Engineering Change Note
        return p;
    }

    private void busy(boolean on) { for (Button b : buttons) b.setEnabled(!on); }

    private void submit(String status) {
        problem.setVisibility(View.GONE);
        String p0 = form.validate();
        if (p0 != null) { a.toast(p0); return; }
        final JSONObject p;
        try { p = payload(); } catch (Exception e) { a.toast(Api.message(e)); return; }
        busy(true);
        a.toast("Saving…");
        Api.async(() -> {
            if (existing != null) return new Object[]{EcnData.save(api, existing, p), ""};
            JSONObject ecn = EcnData.create(api, p, status);
            if (release == null) return new Object[]{ecn, mailAfterSave(ecn, p)};
            JSONObject released;
            try {
                released = release.run();
            } catch (Exception e) {
                EcnData.cancel(api, EcnData.s(ecn, "id"), "Revision release failed: " + Api.message(e));
                throw e;
            }
            String newId = EcnData.s(released, "id");
            String prev = EcnData.s(p, "previous_attachment_id").isEmpty() ? EcnData.s(released, "superseded_id") : EcnData.s(p, "previous_attachment_id");
            if (!newId.isEmpty()) {
                JSONObject ch = new JSONObject().put("document_attachment_id", newId);
                if (!prev.isEmpty()) ch.put("previous_attachment_id", prev);
                ecn = api.update(EcnData.TABLE, EcnData.s(ecn, "id"), ch);
            }
            return new Object[]{ecn, mailAfterSave(ecn, p)};
        }, (res, err) -> {
            busy(false);
            if (err != null) { problem.setText(Api.message(err)); problem.setVisibility(View.VISIBLE); a.toast(Api.message(err)); return; }
            JSONObject ecn = (JSONObject) res[0];
            String msg = EcnData.s(ecn, "ecn_number") + (existing != null ? " saved." : " saved as " + EcnData.statusLabel(EcnData.status(ecn)) + ".")
                + (release != null ? " New revision released; previous revision is now OBSOLETE." : "") + res[1];
            a.toast(msg.trim());
            if (existing == null) a.replaceTop(new EcnScreen(a, EcnData.s(ecn, "id")));
            else a.back();
        });
    }

    /** app_pages/ecn._mail_after_save: ECN_CREATED (Quality + NPD) + the optional e-mail to the selected employees. */
    private String mailAfterSave(JSONObject ecn, JSONObject p) {
        String note = EcnData.notifyCreated(api, ecn);
        JSONArray ids = p.optJSONArray("email_employee_ids");
        if (ids != null && ids.length() > 0) {
            List<String> chosen = new ArrayList<>();
            for (int i = 0; i < ids.length(); i++) chosen.add(ids.optString(i));
            try { note += " " + EcnData.email(api, ecn, chosen, null, null); } catch (Exception e) { note += " E-mail failed: " + Api.message(e); }
        }
        return note;
    }

    @Override public boolean onBack() {
        a.confirm("Leave without saving?", release != null ? "The new revision is NOT released without its ECN." : "Changes on this form are not saved.", "Leave", () -> a.back());
        return true;
    }
}
