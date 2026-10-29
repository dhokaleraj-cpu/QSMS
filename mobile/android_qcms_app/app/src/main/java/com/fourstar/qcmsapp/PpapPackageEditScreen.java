package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * R39 · PPAP package header (website ppap-package section A): create from the PPAP template (customer template when it
 * exists, else the default 32-element master) linked to an APQP project / Part / Customer, submission level, PSW status,
 * customer / interim / full submit dates, owner, contact e-mail, status. Right after a new package is saved the
 * assignment e-mail goes to the responsible employees (rpc qcms_ppap_assignment_mail + qcms-send-email); a mail
 * failure never blocks the save.
 */
public final class PpapPackageEditScreen extends Screen {
    static final Field.Lookup PROJECTS = new Field.Lookup("ppap_projects",
        "id,project_code,part_id,customer_id,submission_level,target_submission_date,coordinator_employee_id,status", "", "project_code.asc",
        r -> Lookups.join(Lookups.j(r, "project_code"), Ui.pretty(Lookups.j(r, "status"))));

    private final String id;
    private final String apqpId;
    private JSONObject existing;
    private FormView form;
    private TextView problem;
    private Button save;
    private List<String> taken = new ArrayList<>();

    /** id = package to edit (null = new); apqpProjectId = prefill a new package from that APQP project. */
    public PpapPackageEditScreen(MainActivity a, String id, String apqpProjectId) { super(a); this.id = id; this.apqpId = apqpProjectId; }

    @Override public String title() { return id == null ? "New PPAP package" : "Edit PPAP package"; }
    @Override public String subtitle() { return "PPAP · package header"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONObject row = id == null ? null : PpapData.pkg(api, id);
            Lookups.rows(api, PROJECTS);
            Lookups.rows(api, Lookups.parts());
            Lookups.rows(api, Lookups.customers());
            Lookups.rows(api, Lookups.employees());
            List<String> numbers = new ArrayList<>();
            for (JSONObject p : PpapData.list(api.rows("ppap_packages?select=id,package_no&limit=5000")))
                if (row == null || !PpapData.s(p, "id").equals(PpapData.s(row, "id"))) numbers.add(PpapData.s(p, "package_no"));
            JSONObject prefill = null;
            if (row == null && apqpId != null && !apqpId.isEmpty()) {
                JSONObject project = Lookups.rowOf(PROJECTS, apqpId);
                if (project == null) {
                    JSONArray r = api.rows("ppap_projects?select=*&id=eq." + Api.enc(apqpId) + "&limit=1");
                    project = r.length() > 0 ? r.getJSONObject(0) : null;
                }
                if (project != null) prefill = PpapData.headerFromApqp(project, Lookups.rowOf(Lookups.parts(), PpapData.s(project, "part_id")));
            }
            return new Object[]{row, numbers, prefill};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            existing = (JSONObject) res[0];
            @SuppressWarnings("unchecked") List<String> numbers = (List<String>) res[1];
            taken = numbers;
            render((JSONObject) res[2]);
        });
        return scroll;
    }

    private void render(JSONObject prefill) {
        List<Field> f = new ArrayList<>();
        f.add(Field.text("package_no", "PPAP Package No.").hint("Blank = automatic (PPAP-<PPAP no>-<part>)"));
        f.add(Field.lookup("apqp_project_id", "APQP Project (link)", PROJECTS));
        f.add(Field.lookup("part_id", "Part (Part Master)", Lookups.parts()));
        f.add(Field.lookup("customer_id", "Customer", Lookups.customers()).req());
        f.add(Field.text("customer_part_no", "Customer Part No.").hint("Blank = Part Master part number"));
        f.add(Field.text("customer_ppap_no", "Customer PPAP No."));
        f.add(Field.select("submission_level", "Submission Level", PpapData.LEVELS).labels("Level 1", "Level 2", "Level 3", "Level 4", "Level 5").req().def("3"));
        f.add(Field.select("psw_status", "PSW Status", PpapData.PSW_STATUSES).labels(prettyAll(PpapData.PSW_STATUSES)).req().def("NOT_SUBMITTED"));
        f.add(Field.date("customer_due_date", "Customer Due Date"));
        f.add(Field.date("interim_submit_date", "Interim Submit"));
        f.add(Field.date("interim_approved_date", "Interim Approved"));
        f.add(Field.date("full_submit_date", "Full Submit"));
        f.add(Field.date("approval_date", "Approval"));
        f.add(Field.lookup("owner_employee_id", "PPAP Owner", Lookups.employees()));
        f.add(Field.text("customer_contact_email", "Customer PPAP Contact E-mail").hint("Blank = customer master e-mail; several separated by ;"));
        f.add(Field.select("status", "Package Status", PpapData.PACKAGE_STATUSES).labels(prettyAll(PpapData.PACKAGE_STATUSES)).req().def("IN_PROGRESS"));
        f.add(Field.area("remarks", "Remarks"));
        if (existing == null) {
            f.add(Field.date("default_due", "Default element due date (new package)"));
            f.add(Field.lookup("default_responsible", "Default responsible employee (new package)", Lookups.employees())
                .hint("Gets the assignment e-mail with the part details, drawings and specifications."));
        }
        form = new FormView(a, f);
        add(form, 0);
        if (existing != null) {
            form.setAll(existing);
            form.set("submission_level", PpapData.s(existing, "submission_level"));
        } else if (prefill != null) {
            form.setAll(prefill);
            form.set("default_due", PpapData.s(prefill, "customer_due_date"));
            add(MstForm.noteCard(a, "New PPAP package from the APQP project - check the header and Save."), 8);
        }
        form.onChange((k, v) -> {
            if ("part_id".equals(k) && form.str("customer_id").isEmpty()) {
                JSONObject part = Lookups.rowOf(Lookups.parts(), form.str("part_id"));
                if (part != null && !Lookups.j(part, "customer_id").isEmpty()) form.set("customer_id", Lookups.j(part, "customer_id"));
            }
            if ("apqp_project_id".equals(k) && existing == null) {
                JSONObject project = Lookups.rowOf(PROJECTS, form.str("apqp_project_id"));
                if (project != null) {
                    try {
                        JSONObject h = PpapData.headerFromApqp(project, Lookups.rowOf(Lookups.parts(), Lookups.j(project, "part_id")));
                        for (String key : new String[]{"part_id", "customer_id", "customer_part_no", "submission_level", "customer_due_date", "owner_employee_id"})
                            if (form.str(key).isEmpty() && !PpapData.s(h, key).isEmpty()) form.set(key, PpapData.s(h, key));
                    } catch (Exception ignored) { }
                }
            }
        });
        add(MstForm.noteCard(a, existing == null
            ? "The element list comes from the customer's own PPAP template when it exists, otherwise from the default template (PPAP → Element Templates on the website)."
            : "Elements, documents and the customer submission are on the package screen."), 10);
        problem = Ui.text(a, "", 13, Ui.RED_FG, false);
        problem.setVisibility(View.GONE);
        add(problem, 8);
        save = Ui.primary(a, existing == null ? "Save PPAP Package" : "Update PPAP Package");
        save.setOnClickListener(v -> save());
        add(save, 10);
    }

    static String[] prettyAll(String[] codes) {
        String[] out = new String[codes.length];
        for (int i = 0; i < codes.length; i++) out[i] = Ui.pretty(codes[i]);
        return out;
    }

    private void showProblem(String t) {
        problem.setText(t == null ? "" : t);
        problem.setVisibility(t == null || t.isEmpty() ? View.GONE : View.VISIBLE);
    }

    private void save() {
        String p = form.validate();
        List<String> errors = new ArrayList<>();
        if (p != null) errors.add(p);
        String partNo = form.str("customer_part_no");
        if (partNo.isEmpty()) {
            JSONObject part = Lookups.rowOf(Lookups.parts(), form.str("part_id"));
            if (part != null) partNo = Lookups.j(part, "part_number");
        }
        if (partNo.isEmpty()) errors.add("Customer Part No. - required (select a Part or type the customer part number).");
        String code = form.str("package_no");
        for (String t : taken) if (!code.isEmpty() && t.equalsIgnoreCase(code)) errors.add("PPAP Package No. - '" + code + "' already exists. Open it from the register instead.");
        String contact = form.str("customer_contact_email");
        List<String> emails = SndMail.splitEmails(contact);
        if (!contact.isEmpty() && emails.isEmpty()) errors.add("Customer PPAP Contact E-mail - enter a valid e-mail address.");
        if (!errors.isEmpty()) { showProblem(String.join("\n", errors)); a.toast(errors.get(0)); return; }
        showProblem("");
        final String partNumber = partNo;
        save.setEnabled(false);
        save.setText("Saving…");
        Api.async(() -> {
            JSONObject payload = new JSONObject();
            payload.put("apqp_project_id", PpapData.nz(form.str("apqp_project_id")));
            payload.put("part_id", PpapData.nz(form.str("part_id")));
            payload.put("customer_id", PpapData.nz(form.str("customer_id")));
            payload.put("customer_part_no", partNumber);
            payload.put("customer_ppap_no", PpapData.nz(form.str("customer_ppap_no")));
            payload.put("submission_level", Integer.parseInt(form.str("submission_level").isEmpty() ? "3" : form.str("submission_level")));
            payload.put("psw_status", form.str("psw_status"));
            for (String k : new String[]{"customer_due_date", "interim_submit_date", "interim_approved_date", "full_submit_date", "approval_date"})
                payload.put(k, PpapData.nz(iso(form.str(k))));
            payload.put("owner_employee_id", PpapData.nz(form.str("owner_employee_id")));
            List<String> valid = new ArrayList<>();
            for (String e : SndMail.splitEmails(form.str("customer_contact_email"))) if (!SndMail.valid(e).isEmpty()) valid.add(e);
            payload.put("customer_contact_email", PpapData.nz(String.join("; ", valid)));
            payload.put("status", form.str("status"));
            payload.put("remarks", PpapData.nz(form.str("remarks")));
            if (existing != null) {
                if (!form.str("package_no").isEmpty()) payload.put("package_no", form.str("package_no"));
                JSONObject saved = api.update("ppap_packages", PpapData.s(existing, "id"), payload);
                return new Object[]{saved, "PPAP package " + PpapData.s(saved, "package_no") + " updated."};
            }
            payload.put("package_no", form.str("package_no"));
            JSONObject saved = PpapData.createPackage(api, payload, iso(form.str("default_due")), form.str("default_responsible"));
            String mail = PpapData.assignmentMail(api, PpapData.s(saved, "id"), null, false);
            return new Object[]{saved, "PPAP package " + PpapData.s(saved, "package_no") + " created with the element list from the PPAP template. " + mail};
        }, (res, err) -> {
            save.setEnabled(true);
            save.setText(existing == null ? "Save PPAP Package" : "Update PPAP Package");
            if (err != null) { showProblem(Api.message(err)); a.toast(Api.message(err)); return; }
            JSONObject saved = (JSONObject) res[0];
            a.toast((String) res[1]);
            if (existing == null) a.replaceTop(new PpapPackageScreen(a, PpapData.s(saved, "id")));
            else a.back();
        });
    }

    static String iso(String v) { return v == null || v.length() < 10 ? (v == null ? "" : v) : v.substring(0, 10); }

    @Override public boolean onBack() {
        a.confirm("Leave without saving?", "Changes on this form are not saved.", "Leave", () -> a.back());
        return true;
    }
}
