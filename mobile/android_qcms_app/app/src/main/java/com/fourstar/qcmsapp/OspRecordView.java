package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * R39 · the ONE Material Out / Returnable Delivery Challan record (osp_transactions.render_material_out_record):
 * tabs Details · Print · Vendor returns. Used by the OSP Material Out record (RecordScreen) and, for any OSP heat line /
 * legacy single job, by OspRecordScreen from the OSP Register (= web OSP Records section B).
 * Print = vendor-safe challan PDF (DRAFT for an older Material Out without saved challan), internal Material Out PDF,
 * challan e-mail to the OSP vendor. Customer details never print on the vendor challan.
 */
final class OspRecordView {
    private OspRecordView() { }

    static final String MODULE = "OSP_TRANSACTIONS";

    /** One Material Out document (OSPService.material_out_documents) with its challan, returns and permissions. */
    static final class Doc {
        String moId = "", jobId = "", number = "";
        JSONObject first = new JSONObject();
        List<JSONObject> lines = new ArrayList<>();
        JSONObject challan;
        List<JSONObject> challanLines = new ArrayList<>(), receipts = new ArrayList<>(), entries = new ArrayList<>(), returns = new ArrayList<>();
        JSONObject summary = new JSONObject();
        double dispatched, received;
        boolean canCreate, canEdit, canArchive;

        boolean group() { return !moId.isEmpty(); }
        String key() { return group() ? moId : jobId; }
        List<String> jobIds() { List<String> l = new ArrayList<>(); for (JSONObject r : lines) l.add(OspChallan.s(r, "id")); return l; }
        String status() {
            Set<String> s = new HashSet<>();
            for (JSONObject r : lines) s.add(OspChallan.s(r, "status"));
            return s.size() == 1 ? s.iterator().next() : "PARTIAL / MIXED";
        }
        String challanNumber() { return SupPdfKit.first(OspChallan.s(challan, "challan_number"), OspChallan.s(first, "dispatch_challan"), "-"); }
    }

    // ================================================================== data
    /** Heat lines of one Material Out (osp_jobs + v_qsms_osp_register + FSI part number + RMTC numbers). */
    static List<JSONObject> lines(Api api, String moId, String jobId) throws Exception {
        String jobFilter = moId != null && !moId.isEmpty() ? "material_out_id=eq." + Api.enc(moId) : "id=eq." + Api.enc(jobId);
        List<JSONObject> raw = InspUtil.list(api.rows("osp_jobs?select=id,material_out_id,material_out_line_no,dispatch_remarks,expected_return_date,dispatch_date,dispatch_challan,vendor_id,part_id,process_id&"
            + jobFilter + "&order=material_out_line_no.asc&limit=200"));
        Map<String, JSONObject> rawById = new HashMap<>();
        List<String> ids = new ArrayList<>();
        for (JSONObject r : raw) { rawById.put(OspChallan.s(r, "id"), r); ids.add(OspChallan.s(r, "id")); }
        List<JSONObject> out = new ArrayList<>();
        for (int i = 0; i < ids.size(); i += 80) {
            out.addAll(InspUtil.list(api.rows("v_qsms_osp_register?select=*&id=in.(" + String.join(",", ids.subList(i, Math.min(ids.size(), i + 80))) + ")")));
        }
        Set<String> partIds = new HashSet<>(), inwardIds = new HashSet<>();
        for (JSONObject r : out) {
            JSONObject j = rawById.get(OspChallan.s(r, "id"));
            for (String k : new String[]{"material_out_id", "material_out_line_no", "dispatch_remarks", "expected_return_date"}) if (j != null && !j.isNull(k)) r.put(k, j.opt(k));
            partIds.add(OspChallan.s(r, "part_id"));
            if (!OspChallan.s(r, "source_inward_lot_id").isEmpty()) inwardIds.add(OspChallan.s(r, "source_inward_lot_id"));
        }
        Map<String, JSONObject> parts = InspUtil.byId(api, "parts", "id,fsi_part_number,hsn_sac_code", partIds);
        Map<String, JSONObject> inwards = inwardIds.isEmpty() ? new HashMap<>() : InspUtil.byId(api, "inward_lots", "id,rmtc_approval_id", inwardIds);
        Set<String> certIds = new HashSet<>();
        for (JSONObject i : inwards.values()) if (!OspChallan.s(i, "rmtc_approval_id").isEmpty()) certIds.add(OspChallan.s(i, "rmtc_approval_id"));
        Map<String, JSONObject> certs = certIds.isEmpty() ? new HashMap<>() : InspUtil.byId(api, "rmtc_approvals", "id,rmtc_number,certificate_reference", certIds);
        for (JSONObject r : out) {
            r.put("fsi_part_number", OspChallan.s(parts.get(OspChallan.s(r, "part_id")), "fsi_part_number"));
            JSONObject in = inwards.get(OspChallan.s(r, "source_inward_lot_id"));
            JSONObject c = in == null ? null : certs.get(OspChallan.s(in, "rmtc_approval_id"));
            r.put("rmtc_number", OspChallan.s(c, "rmtc_number"));
            r.put("supplier_rmtc_number", OspChallan.s(c, "certificate_reference"));
        }
        out.sort((x, y) -> {
            int c = Integer.compare((int) OspChallan.f(x, "material_out_line_no"), (int) OspChallan.f(y, "material_out_line_no"));
            return c != 0 ? c : OspChallan.s(x, "id").compareTo(OspChallan.s(y, "id"));
        });
        return out;
    }

    static Doc load(Api api, String moId, String jobId) throws Exception {
        Doc d = new Doc();
        d.moId = moId == null ? "" : moId;
        d.jobId = jobId == null ? "" : jobId;
        if (d.moId.isEmpty() && !d.jobId.isEmpty()) {   // a heat line of a multi-heat document opens the whole document
            JSONObject j = InspUtil.get(api, "osp_jobs", d.jobId);
            if (j != null && !OspChallan.s(j, "material_out_id").isEmpty()) d.moId = OspChallan.s(j, "material_out_id");
        }
        d.lines = lines(api, d.moId, d.jobId);
        if (d.lines.isEmpty()) throw new Api.ApiException(404, "Material Out not found or not visible for your role.");
        d.first = d.lines.get(0);
        JSONObject header = d.group() ? OspChallan.one(api, "osp_material_outs", d.moId) : null;
        d.number = SupPdfKit.first(OspChallan.s(header, "material_out_number"), OspChallan.s(d.first, "osp_job_number"));
        for (JSONObject r : d.lines) { d.dispatched += OspChallan.f(r, "quantity_dispatched"); d.received += OspChallan.f(r, "quantity_received"); }
        d.challan = OspChallan.challanFor(api, d.moId, d.group() ? null : d.jobId);
        if (d.challan != null) {
            d.challanLines = OspChallan.lines(api, OspChallan.s(d.challan, "id"));
            d.entries = OspChallan.returnEntries(api, OspChallan.s(d.challan, "id"));
        }
        d.receipts = OspChallan.receipts(api, d.jobIds());
        d.returns = OspChallan.mergeReturns(d.receipts, d.entries);
        d.summary = OspChallan.balanceSummary(d.dispatched, d.returns);
        d.canCreate = AdmPerm.current(api, MODULE, "can_create");
        d.canEdit = AdmPerm.current(api, MODULE, "can_edit");
        d.canArchive = AdmPerm.current(api, MODULE, "can_archive");
        return d;
    }

    // ================================================================== view
    /** Panel with the three tabs; loads by itself. allowDelete=false from the OSP Register (as web OSP Records). */
    static View build(MainActivity a, String moId, String jobId, boolean allowDelete, Runnable reload) {
        Api api = Api.get(a);
        LinearLayout box = Ui.vbox(a);
        box.addView(Ui.label(a, "MATERIAL OUT · RETURNABLE DELIVERY CHALLAN"));
        TextView loading = Ui.text(a, "Loading Material Out / challan…", 12, Ui.MUTED, false);
        box.addView(loading);
        Api.async(() -> load(api, moId, jobId), (d, err) -> {
            box.removeView(loading);
            if (err != null || d == null) { box.addView(Ui.text(a, "Challan could not be loaded: " + Api.message(err), 12, Ui.RED_FG, false)); return; }
            render(a, api, box, d, allowDelete, reload);
        });
        return box;
    }

    private static void render(MainActivity a, Api api, LinearLayout box, Doc d, boolean allowDelete, Runnable reload) {
        box.addView(Ui.text(a, "Material Out " + d.number + " · Challan " + d.challanNumber(), 14, Ui.TEXT, true), Ui.matchWrap(a, 4));
        box.addView(Ui.text(a, "One record: Details (correct / delete) · Print (challan PDF, e-mail) · Vendor returns. Customer details never print on the vendor challan.", 11.5f, Ui.MUTED, false));
        JSONObject[] pending = OspChallan.PENDING.get(d.key());
        if (pending != null && d.challan == null)
            box.addView(Ui.chip(a, "Material Out is saved (stock allocated) but its challan is not saved yet - do NOT create the Material Out again. Details → Complete challan details (your entries are filled in) → Save Challan.", "amber"), Ui.matchWrap(a, 6));
        LinearLayout tabs = Ui.hbox(a);
        LinearLayout content = Ui.vbox(a);
        String[] names = {"Details", "Print", "Vendor returns"};
        Button[] buttons = new Button[names.length];
        Runnable[] show = new Runnable[names.length];
        for (int i = 0; i < names.length; i++) {
            final int index = i;
            show[i] = () -> {
                content.removeAllViews();
                for (int j = 0; j < buttons.length; j++) {
                    buttons[j].setTextColor(j == index ? android.graphics.Color.WHITE : Ui.TEAL_DARK);
                    buttons[j].setBackground(Ui.round(j == index ? Ui.TEAL : android.graphics.Color.WHITE, Ui.TEAL, 1, 10, a));
                }
                if (index == 0) details(a, api, content, d, allowDelete, reload);
                else if (index == 1) print(a, api, content, d, reload);
                else returns(a, api, content, d, reload);
            };
            buttons[i] = Ui.outline(a, names[i], Ui.TEAL_DARK);
            buttons[i].setOnClickListener(v -> show[index].run());
            LinearLayout.LayoutParams lp = Ui.weight(1);
            lp.setMargins(i == 0 ? 0 : Ui.dp(a, 4), 0, 0, 0);
            tabs.addView(buttons[i], lp);
        }
        box.addView(tabs, Ui.matchWrap(a, 8));
        box.addView(content, Ui.matchWrap(a, 6));
        show[0].run();
    }

    private static String q(double v) { return Ui.num(v, 3); }

    // ------------------------------------------------------------------ Details
    private static void details(MainActivity a, Api api, LinearLayout c, Doc d, boolean allowDelete, Runnable reload) {
        LinearLayout card = Ui.card(a);
        JSONObject ch = d.challan == null ? new JSONObject() : d.challan;
        card.addView(Ui.pair(a, "Material Out", d.number));
        card.addView(Ui.pair(a, "Challan No", d.challanNumber()));
        card.addView(Ui.pair(a, "Challan Date", Ui.date(SupPdfKit.first(OspChallan.s(ch, "challan_date"), OspChallan.s(d.first, "dispatch_date")))));
        card.addView(Ui.pair(a, "OSP Vendor", OspChallan.s(d.first, "vendor_name")));
        card.addView(Ui.pair(a, "Process", OspChallan.s(d.first, "process_name")));
        card.addView(Ui.pair(a, "Part", OspChallan.s(d.first, "part_number")));
        card.addView(Ui.pair(a, "FSI Part", OspChallan.s(d.first, "fsi_part_number")));
        card.addView(Ui.pair(a, "Expected Return / Delivery", Ui.date(SupPdfKit.first(OspChallan.s(d.first, "expected_return_date"), OspChallan.s(ch, "delivery_date")))));
        card.addView(Ui.pair(a, "Out Qty pcs", q(d.dispatched)));
        card.addView(Ui.pair(a, "Received pcs", q(d.received)));
        card.addView(Ui.pair(a, "Challan", d.challan == null ? "Not created" : "Saved" + (OspChallan.s(ch, "emailed_at").isEmpty() ? "" : " · e-mailed " + Ui.date(OspChallan.s(ch, "emailed_at")))));
        card.addView(Ui.pair(a, "Status", Ui.pretty(d.status())));
        c.addView(card);
        List<String> head = Arrays.asList("Line", "RMTC", "Supplier RMTC", "Heat Number", "Source Inward", "FSI Batch", "Out Qty pcs", "Received pcs", "Balance pcs",
            "Vendor Batch", "Sample Gate", "Receipt Decision");
        List<List<String>> rows = new ArrayList<>();
        int i = 0;
        for (JSONObject r : d.lines) {
            i++;
            double out = OspChallan.f(r, "quantity_dispatched"), rec = OspChallan.f(r, "quantity_received");
            rows.add(Arrays.asList(String.valueOf((int) OspChallan.f(r, "material_out_line_no") > 0 ? (int) OspChallan.f(r, "material_out_line_no") : i),
                SupPdfKit.first(OspChallan.s(r, "rmtc_number"), "Opening / legacy"), SupPdfKit.first(OspChallan.s(r, "supplier_rmtc_number"), "-"),
                OspChallan.s(r, "heat_number"), OspChallan.s(r, "inward_number"), OspChallan.s(r, "osp_batch_code"), q(out), q(rec), q(Math.max(out - rec, 0)),
                OspChallan.s(r, "vendor_batch_number"), Ui.pretty(OspChallan.s(r, "sample_gate_status")), Ui.pretty(OspChallan.s(r, "receipt_quality_disposition"))));
        }
        c.addView(new DataGrid(a, "Heat lines", head, rows, 260, null), Ui.matchWrap(a, 8));
        if (d.challan == null)
            c.addView(Ui.text(a, "This older Material Out has no challan details yet. Complete them once below - new Material Outs save the challan automatically. It can already be printed as a DRAFT challan (Print tab).", 12, Ui.AMBER_FG, false), Ui.matchWrap(a, 8));
        boolean allowed = d.challan == null ? (d.canCreate || d.canEdit) : d.canEdit;
        Button edit = Ui.primary(a, d.challan == null ? "Complete challan details" : "Correct challan details (Material Out + challan)");
        edit.setEnabled(allowed);
        edit.setOnClickListener(v -> a.push(new OspChallanEdit(a, d.moId, d.group() ? "" : d.jobId)));
        c.addView(edit, Ui.matchWrap(a, 10));
        if (!allowed) c.addView(Ui.text(a, "Your role has no OSP Transactions " + (d.challan == null ? "Entry/Create" : "Edit") + " right.", 11.5f, Ui.MUTED, false));
        if (allowDelete) {
            Button del = Ui.outline(a, "Delete Material Out (all heat lines, restores balances)", Ui.ORANGE);
            del.setEnabled(d.canArchive);
            del.setOnClickListener(v -> {
                if (d.group()) InspOsp.deleteMaterialOut(a, new JSONObject(mapOf("id", d.moId, "material_out_number", d.number)), reload);
                else InspOsp.deleteTransaction(a, d.first, reload);
            });
            c.addView(del, Ui.matchWrap(a, 8));
        }
    }

    private static Map<String, Object> mapOf(String k1, Object v1, String k2, Object v2) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put(k1, v1);
        m.put(k2, v2);
        return m;
    }

    // ------------------------------------------------------------------ Print
    private static void print(MainActivity a, Api api, LinearLayout c, Doc d, Runnable reload) {
        boolean saved = d.challan != null;
        if (saved) {
            LinearLayout card = Ui.card(a);
            card.addView(Ui.text(a, "Calculating totals…", 12, Ui.MUTED, false));
            c.addView(card);
            Api.async(() -> OspChallan.payloadForChallan(api, d.challan), (p, err) -> {
                card.removeAllViews();
                if (err != null || p == null) { card.addView(Ui.text(a, "Challan PDF could not be generated: " + Api.message(err), 12, Ui.RED_FG, false)); return; }
                JSONObject t = p.optJSONObject("totals");
                card.addView(Ui.pair(a, "Taxable (INR)", Ui.num(OspChallan.f(t, "subtotal"), 2)));
                card.addView(Ui.pair(a, "GST (INR)", Ui.num(OspChallan.f(t, "tax"), 2)));
                card.addView(Ui.pair(a, "Total (INR)", Ui.num(OspChallan.f(t, "total"), 2)));
                card.addView(Ui.pair(a, "Balance at vendor (pcs)", Ui.num(OspChallan.f(p.optJSONObject("summary"), "balance"), 3)));
                card.addView(Ui.pair(a, "Print status", OspChallan.statusLabel(p)));
            });
        } else {
            c.addView(Ui.text(a, "No challan details are saved yet: the challan prints as a DRAFT (watermarked) from the Material Out itself.", 12, Ui.AMBER_FG, false));
        }
        Button pdf = Ui.primary(a, saved ? "Challan PDF · View · Download · Print · Share" : "DRAFT Challan PDF · View · Download · Share");
        pdf.setOnClickListener(v -> challanPdf(a, api, d, (payload, bytes) ->
            ExportKit.layoutActions(a, OspChallan.CHALLAN_TITLE + " " + OspChallan.s(payload, "challan_number"), OspChallanPdf.fileBase(payload), bytes)));
        c.addView(pdf, Ui.matchWrap(a, 10));
        if (saved) {
            Button mail = Ui.outline(a, "E-mail challan to OSP Vendor (PDF attached)", Ui.TEAL);
            mail.setEnabled(d.canEdit || d.canCreate);
            mail.setOnClickListener(v -> emailDialog(a, api, d, reload));
            c.addView(mail, Ui.matchWrap(a, 8));
            if (!OspChallan.s(d.challan, "emailed_at").isEmpty())
                c.addView(Ui.text(a, "Last e-mailed " + OspChallan.s(d.challan, "emailed_at").replace("T", " ").substring(0, Math.min(16, OspChallan.s(d.challan, "emailed_at").length()))
                    + " to " + OspChallan.s(d.challan, "emailed_to"), 11.5f, Ui.MUTED, false));
        }
        Button internal = Ui.outline(a, "Internal Material Out record PDF · all heat lines", Ui.TEAL_DARK);
        internal.setOnClickListener(v -> ExportKit.layoutMenu(a, () -> internalRecord(d)));
        c.addView(internal, Ui.matchWrap(a, 8));
        c.addView(Ui.text(a, "The challan and its e-mail are vendor-safe: FSI part number only - no customer name, code, PO or customer part number. The internal record is for QCMS (heat / RMTC genealogy).", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 6));
    }

    interface PdfReady { void ready(JSONObject payload, byte[] pdf); }

    static void challanPdf(MainActivity a, Api api, Doc d, PdfReady ready) {
        a.toast("Preparing the Returnable Delivery Challan…");
        Api.async(() -> {
            JSONObject payload = d.challan != null ? OspChallan.payloadForChallan(api, d.challan) : OspChallan.payloadForDocument(api, d.moId, d.group() ? null : d.jobId);
            return new Object[]{payload, OspChallanPdf.render(SupPdfKit.layout(api), payload)};
        }, (r, err) -> {
            if (err != null || r == null) { a.toast("Challan PDF could not be generated: " + Api.message(err)); return; }
            ready.ready((JSONObject) r[0], (byte[]) r[1]);
        });
    }

    /** _render_material_out_internal_pdf: controlled record with every RMTC / heat dispatch line (not for the vendor). */
    static RptDoc internalRecord(Doc d) {
        LinkedHashMap<String, Object> header = new LinkedHashMap<>();
        header.put("Part", OspChallan.s(d.first, "part_number"));
        header.put("Vendor", OspChallan.s(d.first, "vendor_name"));
        header.put("Process", OspChallan.s(d.first, "process_name"));
        header.put("Challan", OspChallan.s(d.first, "dispatch_challan"));
        header.put("Date", OspChallan.s(d.first, "dispatch_date"));
        header.put("Expected Return", OspChallan.s(d.first, "expected_return_date"));
        header.put("Total Qty pcs", q(d.dispatched));
        header.put("Remarks", OspChallan.s(d.first, "dispatch_remarks"));
        List<Map<String, Object>> rows = new ArrayList<>();
        int i = 0;
        for (JSONObject r : d.lines) {
            i++;
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("Line", (int) OspChallan.f(r, "material_out_line_no") > 0 ? (int) OspChallan.f(r, "material_out_line_no") : i);
            m.put("RMTC", SupPdfKit.first(OspChallan.s(r, "rmtc_number"), "Opening / legacy"));
            m.put("Heat", OspChallan.s(r, "heat_number"));
            m.put("Inward", OspChallan.s(r, "inward_number"));
            m.put("FSI Batch", OspChallan.s(r, "osp_batch_code"));
            m.put("Qty pcs", q(OspChallan.f(r, "quantity_dispatched")));
            rows.add(m);
        }
        LinkedHashMap<String, Object> sections = new LinkedHashMap<>();
        sections.put("RMTC / HEAT DISPATCH LINES", rows);
        RptDoc doc = RptReports.controlled("OSP MATERIAL OUT", header, sections, d.number, "", null, null);
        doc.file("QCMS_" + d.number + "_Material_Out");
        return doc;
    }

    private static void emailDialog(MainActivity a, Api api, Doc d, Runnable reload) {
        challanPdf(a, api, d, (payload, pdf) -> Api.async(() -> OspChallan.one(api, "parties", OspChallan.s(d.first, "vendor_id")), (vendor, err) -> {
            List<String> emails = OspChallan.vendorEmails(vendor == null ? new JSONObject() : vendor);
            String[] sb = OspChallan.emailBody(payload);
            JSONObject v = new JSONObject();
            try {
                v.put("to", emails.isEmpty() ? "" : emails.get(0));
                v.put("cc", emails.size() > 1 ? String.join(", ", emails.subList(1, emails.size())) : "");
                v.put("subject", sb[0]);
                v.put("body", sb[1]);
            } catch (Exception ignored) { }
            List<Field> f = new ArrayList<>();
            f.add(Field.text("to", "To").req());
            f.add(Field.text("cc", "CC (comma separated)"));
            f.add(Field.text("subject", "Subject").req());
            f.add(Field.area("body", "Message"));
            String vendorName = OspChallan.s(vendor, "party_name");
            InspUtil.formDialog(a, "E-mail challan to OSP Vendor", f, v, "Send Challan E-mail", (form, values) -> {
                String to = form.str("to");
                if (!to.contains("@")) throw new Api.ApiException(422, "Enter the vendor e-mail address.");
                List<String> cc = new ArrayList<>();
                for (String x : form.str("cc").replace(";", ",").split(",")) if (x.contains("@")) cc.add(x.trim());
                Api.async(() -> OspChallan.emailVendor(api, d.challan, d.first, pdf, to, cc, form.str("subject"), form.str("body"), vendorName), (res, e2) -> {
                    if (e2 != null) { a.toast("The e-mail could not be queued: " + Api.message(e2)); return; }
                    a.toast("Challan " + OspChallan.s(d.challan, "challan_number") + " " + res + " to " + to + " with the PDF attached.");
                    reload.run();
                });
            });
        }));
    }

    // ------------------------------------------------------------------ Vendor returns
    private static void returns(MainActivity a, Api api, LinearLayout c, Doc d, Runnable reload) {
        c.addView(Ui.text(a, "Every OSP Inward receipt is a vendor return automatically (same quantity, never counted twice). Add the vendor challan / invoice / vehicle / rejected quantity here, or record a return without OSP Inward.", 11.5f, Ui.MUTED, false));
        if (d.challan == null) {
            c.addView(Ui.text(a, "Complete the challan details first (Details → Complete challan details). OSP Inward receipts already recorded will then appear here automatically.", 12, Ui.AMBER_FG, false), Ui.matchWrap(a, 8));
            return;
        }
        LinearLayout k = Ui.card(a);
        k.addView(Ui.pair(a, "Dispatched pcs", q(OspChallan.f(d.summary, "dispatched"))));
        k.addView(Ui.pair(a, "Returned pcs", q(OspChallan.f(d.summary, "returned"))));
        k.addView(Ui.pair(a, "Rejected pcs", q(OspChallan.f(d.summary, "rejected"))));
        k.addView(Ui.pair(a, "Balance pcs at vendor", q(OspChallan.f(d.summary, "balance"))));
        c.addView(k, Ui.matchWrap(a, 6));
        Map<String, String> heat = heatLabels(d);
        if (d.returns.isEmpty()) c.addView(Ui.text(a, "No vendor return yet. Returns recorded in OSP Inward appear here automatically.", 12, Ui.MUTED, false), Ui.matchWrap(a, 6));
        else {
            List<List<String>> rows = new ArrayList<>();
            for (JSONObject r : d.returns) rows.add(Arrays.asList(OspChallan.s(r, "source"), SupPdfKit.first(OspChallan.s(r, "receipt_number"), "-"),
                heat.getOrDefault(OspChallan.s(r, "osp_job_id"), "-"), SupPdfKit.first(OspChallan.s(r, "challan_no"), "-"), Ui.date(OspChallan.s(r, "challan_date")),
                SupPdfKit.first(OspChallan.s(r, "invoice_no"), "-"), Ui.date(OspChallan.s(r, "invoice_date")), q(OspChallan.f(r, "qty_returned")), q(OspChallan.f(r, "qty_rejected")),
                SupPdfKit.first(OspChallan.s(r, "vehicle_no"), "-"), SupPdfKit.first(OspChallan.s(r, "remarks"), "-")));
            c.addView(new DataGrid(a, "Vendor returns", Arrays.asList("Source", "OSP Inward", "Heat Line", "Vendor Challan", "Challan Date", "Vendor Invoice", "Invoice Date",
                "Returned pcs", "Rejected pcs", "Vehicle No", "Remarks"), rows, 300, index -> {
                JSONObject r = d.returns.get(index);
                String entryId = OspChallan.s(r, "entry_id");
                JSONObject entry = null;
                for (JSONObject e : d.entries) if (OspChallan.s(e, "id").equals(entryId)) entry = e;
                JSONObject receipt = null;
                for (JSONObject rc : d.receipts) if (OspChallan.s(rc, "id").equals(OspChallan.s(r, "receipt_id"))) receipt = rc;
                returnAction(a, api, d, entry, receipt, reload);
            }), Ui.matchWrap(a, 6));
            c.addView(Ui.text(a, "Tap a return to update its details" + (d.canArchive ? " or delete the return entry." : "."), 11.5f, Ui.MUTED, false));
        }
        Button add = Ui.primary(a, "Add / update vendor return");
        add.setEnabled(d.canEdit || d.canCreate);
        add.setOnClickListener(v -> {
            List<String> ids = new ArrayList<>(), names = new ArrayList<>();
            ids.add("");
            names.add("No OSP Inward · return recorded on the challan only (e.g. unprocessed / rejected material)");
            Set<String> linked = new HashSet<>();
            for (JSONObject e : d.entries) if (!OspChallan.s(e, "osp_receipt_id").isEmpty()) linked.add(OspChallan.s(e, "osp_receipt_id"));
            for (JSONObject r : d.receipts) {
                ids.add(OspChallan.s(r, "id"));
                names.add("OSP Inward " + OspChallan.s(r, "receipt_number") + " · " + Ui.date(OspChallan.s(r, "receipt_date")) + " · " + q(OspChallan.f(r, "quantity_received")) + " pcs"
                    + (linked.contains(OspChallan.s(r, "id")) ? " · details saved" : ""));
            }
            InspUtil.pick(a, "Linked OSP Inward receipt", ids, names, picked -> {
                JSONObject receipt = null, entry = null;
                for (JSONObject r : d.receipts) if (OspChallan.s(r, "id").equals(picked)) receipt = r;
                if (receipt != null) for (JSONObject e : d.entries) if (OspChallan.s(e, "osp_receipt_id").equals(picked)) entry = e;
                returnForm(a, api, d, entry, receipt, reload);
            });
        });
        c.addView(add, Ui.matchWrap(a, 10));
    }

    private static Map<String, String> heatLabels(Doc d) {
        Map<String, String> m = new LinkedHashMap<>();
        for (JSONObject r : d.lines) m.put(OspChallan.s(r, "id"), "Line " + Math.max(1, (int) OspChallan.f(r, "material_out_line_no")) + " · Heat " + OspChallan.s(r, "heat_number")
            + " · FSI Batch " + SupPdfKit.first(OspChallan.s(r, "osp_batch_code"), "-"));
        return m;
    }

    private static void returnAction(MainActivity a, Api api, Doc d, JSONObject entry, JSONObject receipt, Runnable reload) {
        List<String> items = new ArrayList<>(Arrays.asList("Update return details"));
        if (entry != null && d.canArchive) items.add("Delete this return entry (password)");
        new android.app.AlertDialog.Builder(a).setTitle("Vendor return").setItems(items.toArray(new String[0]), (dlg, which) -> {
            if (which == 0) { returnForm(a, api, d, entry, receipt, reload); return; }
            a.confirm("Delete return entry?", "OSP Inward receipts are not affected. You will be asked for your password.", "Continue", () ->
                a.confirmPassword("Confirm delete with your password", () -> Api.async(() -> { OspChallan.deleteReturn(api, OspChallan.s(entry, "id")); return true; }, (ok, err) -> {
                    if (err != null) { a.toast(Api.message(err)); return; }
                    a.toast("Return entry deleted. OSP Inward receipts are not affected.");
                    reload.run();
                })));
        }).setNegativeButton("Back", null).show();
    }

    /** Add / update one vendor return (OSPChallanService.save_return; receipt quantity stays the OSP Inward quantity). */
    private static void returnForm(MainActivity a, Api api, Doc d, JSONObject entry, JSONObject receipt, Runnable reload) {
        if (!(d.canEdit || d.canCreate)) { a.toast("Your role has no OSP Transactions Edit right."); return; }
        JSONObject e = entry == null ? new JSONObject() : entry, r = receipt == null ? new JSONObject() : receipt;
        Map<String, String> heat = heatLabels(d);
        List<Field> f = new ArrayList<>();
        Field line = Field.select("osp_job_id", "Heat line", heat.keySet().toArray(new String[0])).labels(heat.values().toArray(new String[0])).req();
        if (receipt != null) line.ro();
        f.add(line);
        f.add(Field.text("vendor_challan_number", "Vendor Challan No"));
        f.add(Field.date("vendor_challan_date", "Vendor Challan Date"));
        f.add(Field.text("vehicle_number", "Vehicle No"));
        f.add(Field.text("vendor_invoice_number", "Vendor Invoice No"));
        f.add(Field.date("vendor_invoice_date", "Vendor Invoice Date"));
        if (receipt != null) f.add(Field.info("quantity_returned", "Quantity returned (pcs) · OSP Inward quantity (edit it in OSP Inward)"));
        else f.add(Field.number("quantity_returned", "Quantity returned (pcs)").range(0, Double.MAX_VALUE));
        f.add(Field.number("quantity_rejected", "Quantity rejected / not returned (pcs)").range(0, Double.MAX_VALUE));
        f.add(Field.text("remarks", "Return Remarks"));
        JSONObject v = new JSONObject();
        try {
            String job = SupPdfKit.first(OspChallan.s(e, "osp_job_id"), OspChallan.s(r, "osp_job_id"), heat.isEmpty() ? "" : heat.keySet().iterator().next());
            v.put("osp_job_id", job);
            v.put("vendor_challan_number", SupPdfKit.first(OspChallan.s(e, "vendor_challan_number"), OspChallan.s(r, "receipt_challan")));
            v.put("vendor_challan_date", day(SupPdfKit.first(OspChallan.s(e, "vendor_challan_date"), OspChallan.s(r, "receipt_date"))));
            v.put("vehicle_number", OspChallan.s(e, "vehicle_number"));
            v.put("vendor_invoice_number", SupPdfKit.first(OspChallan.s(e, "vendor_invoice_number"), OspChallan.s(r, "vendor_invoice_number")));
            v.put("vendor_invoice_date", day(SupPdfKit.first(OspChallan.s(e, "vendor_invoice_date"), OspChallan.s(r, "vendor_invoice_date"))));
            v.put("quantity_returned", Ui.num(receipt != null ? OspChallan.f(r, "quantity_received") : OspChallan.f(e, "quantity_returned"), 3).replace(",", ""));
            v.put("quantity_rejected", Ui.num(OspChallan.f(e, "quantity_rejected"), 3).replace(",", ""));
            v.put("remarks", OspChallan.s(e, "remarks"));
        } catch (Exception ignored) { }
        InspUtil.formDialog(a, entry == null ? "Save vendor return" : "Update vendor return", f, v, entry == null ? "Save Return" : "Update Return", (form, values) -> {
            JSONObject p = new JSONObject();
            p.put("osp_job_id", receipt != null ? OspChallan.s(r, "osp_job_id") : form.str("osp_job_id"));
            p.put("osp_receipt_id", receipt != null ? OspChallan.s(r, "id") : OspChallan.s(e, "osp_receipt_id"));
            for (String key : new String[]{"vendor_challan_number", "vendor_challan_date", "vendor_invoice_number", "vendor_invoice_date", "vehicle_number", "remarks"}) p.put(key, form.str(key));
            p.put("quantity_returned", receipt != null ? 0 : OspChallan.f(form.str("quantity_returned")));
            p.put("quantity_rejected", OspChallan.f(form.str("quantity_rejected")));
            OspChallan.cleanReturn(p);   // validation message before the dialog closes
            String target = entry == null ? null : OspChallan.s(entry, "id");
            Api.async(() -> OspChallan.saveReturn(api, OspChallan.s(d.challan, "id"), p, target), (ok, err) -> {
                if (err != null) { a.toast(Api.message(err)); return; }
                a.toast("Vendor return saved. The challan's Supplier Details section is updated.");
                reload.run();
            });
        });
    }

    private static String day(String v) { return v == null || v.length() < 10 ? Ui.today() : v.substring(0, 10); }

    /** Lower-case status helper for tests / labels. */
    static String norm(String v) { return v == null ? "" : v.trim().toUpperCase(Locale.ROOT); }

    static JSONArray toArray(List<JSONObject> l) { JSONArray a = new JSONArray(); for (JSONObject o : l) a.put(o); return a; }
}
