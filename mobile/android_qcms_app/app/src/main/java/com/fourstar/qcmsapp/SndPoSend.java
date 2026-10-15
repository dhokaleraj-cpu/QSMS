package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Send an approved Purchase Order to the supplier - fully native (replaces the website's
 * "supply-po-approval" email panel): print-section ticks, email preview with editable To / CC / Subject /
 * Message from the same notification route + template, generated PO PDF (+ PO documents) as attachments,
 * qcms_notification_outbox row exactly like NotificationService.enqueue, then the qcms-send-email function.
 */
public final class SndPoSend extends Screen {
    private final String poId;

    // loaded state
    private SndData.Po po;
    private List<JSONObject> employees = new ArrayList<>();
    private JSONObject route, template, context;
    private String event = "", supplierName = "";
    private List<String> supplierEmails = new ArrayList<>();
    private Exception loadError;

    // editable state (kept across rebuilds)
    private JSONObject options;
    private String to = "", cc = "", subject = "", body = "";
    private boolean includePdf = true, includeDocs = true;
    private String resultStatus, resultMessage;
    private boolean sending;

    // views
    private final Map<String, CheckBox> sectionBoxes = new LinkedHashMap<>();
    private EditText toIn, ccIn, subjectIn, bodyIn;
    private CheckBox pdfBox, docsBox;
    private TextView hiddenNote;

    private SndPoSend(MainActivity a, String poId) { super(a); this.poId = poId; }

    /** Entry point used by PoDetailScreen / SndPdfView. */
    public static void open(MainActivity a, String poId) {
        if (poId == null || poId.isEmpty()) { a.toast("Purchase Order not found."); return; }
        a.push(new SndPoSend(a, poId));
    }

    @Override public String title() { return po == null ? "Send PO to supplier" : "Send " + po.number(); }
    @Override public String subtitle() { return "PDF + email to supplier · native"; }
    @Override public int tab() { return 1; }

    @Override
    public View build() {
        newPage();
        if (po != null) { render(); return scroll; }
        if (loadError != null) { page.addView(error(loadError, () -> { loadError = null; a.rebuild(); })); return scroll; }
        page.addView(loading());
        Api.async(this::load, (ok, err) -> {
            if (err != null) loadError = err;
            a.rebuild();
        });
        return scroll;
    }

    @Override public void reload() { sync(); po = null; loadError = null; a.rebuild(); }

    // ================================================================== load + preview (NotificationService.preview / enqueue)
    private Boolean load() throws Exception {
        SndData.Po p = SndData.load(api, poId);
        employees = SndMail.employees(api);
        event = p.releaseEvent();
        route = SndMail.route(api, event);
        template = SndMail.template(api, route == null ? "" : SndData.s(route, "template_key"), event);
        supplierName = SndData.s(p.supplier, "party_name");
        supplierEmails = SndMail.partyEmails(p.supplier);
        context = enrichedContext(p);

        // To = supplier, CC = route owner / department / other supplier contacts (preview + supplier_first)
        String email = "", name = "";
        if (route != null) { String[] r = SndMail.recipientForRoute(employees, route); email = r[0]; name = r[1]; }
        List<String> ccList = new ArrayList<>();
        if (route != null && SndData.truthy(route.opt("department_cc"))) {
            List<String> ex = new ArrayList<>(); ex.add(email);
            ccList.addAll(SndMail.departmentEmails(employees, SndData.s(route, "department"), ex));
        }
        String toEmail = email;
        if (!supplierEmails.isEmpty()) {
            toEmail = supplierEmails.get(0);
            List<String> next = new ArrayList<>();
            if (!email.isEmpty()) next.add(email);
            next.addAll(ccList);
            next.addAll(supplierEmails.subList(1, supplierEmails.size()));
            ccList = next;
        }
        if (toEmail.isEmpty()) toEmail = SndData.s(p.supplier, "email");
        List<String> finalCc = new ArrayList<>();
        for (String v : ccList) {
            String t = v == null ? "" : v.trim();
            if (!t.isEmpty() && !t.equalsIgnoreCase(toEmail) && !SndMail.containsIgnoreCase(finalCc, t)) finalCc.add(t);
        }
        String subjectTemplate = template != null && !SndData.s(template, "subject_template").isEmpty() ? Lookups.j(template, "subject_template")
            : route != null && !SndData.s(route, "subject_template").isEmpty() ? Lookups.j(route, "subject_template") : "";
        String bodyTemplate = template != null ? Lookups.j(template, "body_template") : "";
        to = toEmail;
        cc = String.join("; ", finalCc);
        subject = subjectTemplate.isEmpty() ? "QCMS · " + titleCase(event.replace('_', ' ')) : SndMail.fill(subjectTemplate, context);
        body = bodyTemplate.isEmpty()
            ? "QCMS workflow notification\nDocument: " + orDash(SndData.s(context, "document_no")) + "\nNext stage: " + orDash(SndData.s(context, "next_stage"))
            : SndMail.fill(bodyTemplate, context);
        includePdf = template == null || !template.has("include_generated_pdf") || template.isNull("include_generated_pdf") || SndData.truthy(template.opt("include_generated_pdf"));
        includeDocs = template == null || !template.has("include_record_attachments") || template.isNull("include_record_attachments") || SndData.truthy(template.opt("include_record_attachments"));
        options = SndData.effectiveOptions(p.layout, p.header);
        po = p;
        return true;
    }

    private static String orDash(String v) { return v == null || v.isEmpty() ? "-" : v; }

    /** Python str.title(). */
    static String titleCase(String s) {
        StringBuilder b = new StringBuilder();
        boolean up = true;
        for (char c : s.toCharArray()) {
            b.append(up ? Character.toUpperCase(c) : Character.toLowerCase(c));
            up = !Character.isLetter(c);
        }
        return b.toString();
    }

    /** NotificationService._record_context("supply_purchase_orders") + the release panel context. */
    private JSONObject enrichedContext(SndData.Po p) throws Exception {
        JSONObject h = p.header;
        JSONObject ctx = new JSONObject();
        ctx.put("record_id", p.id());
        ctx.put("related_table", "supply_purchase_orders");
        Set<String> enrichedKeys = new HashSet<>(java.util.Arrays.asList("approver_employee_name", "approver_employee_code", "approver_department", "approver_designation"));
        for (String k : SndMail.keys(h)) {
            Object v = h.opt(k);
            if (enrichedKeys.contains(k) || v instanceof JSONObject || v instanceof JSONArray) continue;
            ctx.put(k, v == null ? JSONObject.NULL : v);
        }
        String supplierId = SndData.s(h, "supplier_id");
        if (!supplierId.isEmpty()) {
            ctx.put("supplier_id", supplierId);
            ctx.put("supplier_name", nul(p.supplier, "party_name"));
            ctx.put("supplier_code", nul(p.supplier, "party_code"));
            ctx.put("supplier_email", nul(p.supplier, "email"));
        }
        ctx.put("document_no", nul(h, "po_number"));
        ctx.put("document_type", "Purchase Order");
        ctx.put("po_number", nul(h, "po_number"));
        ctx.put("order_date", nul(h, "order_date"));
        ctx.put("delivery_date", nul(h, "delivery_date"));
        ctx.put("due_date", nul(h, "delivery_date"));
        ctx.put("requisitioner", nul(h, "requisitioner"));
        ctx.put("payment_term", nul(h, "payment_term"));
        ctx.put("incoterm", nul(h, "incoterm"));
        ctx.put("quotation_reference", nul(h, "quotation_reference"));
        if (!p.items.isEmpty()) {
            List<String> supplierParts = new ArrayList<>(), originalParts = new ArrayList<>(), descriptions = new ArrayList<>(), uoms = new ArrayList<>();
            double total = 0;
            for (JSONObject it : p.items) {
                String sp = SndData.s(it, "fsi_part_number_snapshot").isEmpty() ? SndData.s(it, "item_no") : SndData.s(it, "fsi_part_number_snapshot");
                String op = SndData.s(it, "original_part_number_snapshot");
                String d = Lookups.j(it, "item_description").trim();
                String u = SndData.s(it, "uom").toUpperCase(Locale.ROOT);
                if (!sp.isEmpty() && !SndMail.containsIgnoreCase(supplierParts, sp)) supplierParts.add(sp);
                if (!op.isEmpty() && !SndMail.containsIgnoreCase(originalParts, op)) originalParts.add(op);
                if (!d.isEmpty() && !SndMail.containsIgnoreCase(descriptions, d)) descriptions.add(d);
                if (!u.isEmpty() && !SndMail.containsIgnoreCase(uoms, u)) uoms.add(u);
                total += SndData.n(it, "quantity");
            }
            String uomText = String.join(", ", uoms);
            String qty = Math.abs(total - Math.rint(total)) < 1e-9 ? String.format(Locale.US, "%,.0f", total) : SndPoPdf.qty3(total);
            String sp = String.join(", ", supplierParts), op = String.join(", ", originalParts), ds = String.join("; ", descriptions);
            ctx.put("part_number", !sp.isEmpty() ? sp : !op.isEmpty() ? op : "-");
            ctx.put("fsi_part_number", sp.isEmpty() ? "-" : sp);
            ctx.put("original_part_number", op.isEmpty() ? "-" : op);
            ctx.put("part_description", ds.isEmpty() ? "-" : ds);
            ctx.put("item_description", ds.isEmpty() ? "-" : ds);
            ctx.put("quantity_value", qty);
            ctx.put("uom", uomText.isEmpty() ? "-" : uomText);
            ctx.put("quantity", (qty + " " + uomText).trim());
            ctx.put("line_count", p.items.size());
        }
        // _po_approval_release_panel context (context overrides the record context)
        ctx.put("po_number", nul(h, "po_number"));
        ctx.put("supplier_id", supplierId);
        ctx.put("supplier_name", nul(p.supplier, "party_name"));
        ctx.put("delivery_date", nul(h, "delivery_date"));
        ctx.put("next_stage", p.releaseNextStage());
        if (!ctx.has("event_key")) ctx.put("event_key", p.releaseEvent());
        if (!ctx.has("department")) ctx.put("department", route == null ? "" : SndData.s(route, "department"));
        return ctx;
    }

    private static Object nul(JSONObject o, String key) {
        if (o == null || !o.has(key) || o.isNull(key)) return JSONObject.NULL;
        return o.opt(key);
    }

    // ================================================================== UI
    private void render() {
        a.rebuildTitle(this);
        offlineNote();
        JSONObject h = po.header;
        LinearLayout head = Ui.card(a);
        LinearLayout top = Ui.hbox(a);
        top.addView(Ui.text(a, "PURCHASE ORDER", 12, Ui.TEAL_DARK, true), Ui.weight(1));
        String chip = po.cancelled() ? "Cancelled" : Ui.pretty(SndData.s(h, "approval_status"));
        top.addView(Ui.chip(a, chip, Ui.tone(chip)));
        head.addView(top);
        head.addView(Ui.text(a, po.number(), 20, Ui.TEXT, true));
        head.addView(Ui.pair(a, "Supplier", supplierName.isEmpty() ? "-" : supplierName));
        head.addView(Ui.pair(a, "Supplier email", supplierEmails.isEmpty() ? "NOT CONFIGURED in Party Master" : String.join(", ", supplierEmails)));
        head.addView(Ui.pair(a, "Type · lines", Ui.pretty(SndData.s(h, "po_type")) + " · " + po.items.size()));
        head.addView(Ui.pair(a, "Grand total", Ui.money(SndData.n(h, "grand_total"), SndData.s(h, "currency"))));
        add(head, 2);

        if (resultStatus != null) add(SndUi.resultCard(a, resultStatus, resultMessage), 10);

        String blocker = blocker();
        if (blocker != null) {
            TextView b = Ui.text(a, blocker, 12.5f, Ui.RED_FG, true);
            b.setBackground(Ui.round(Ui.RED_BG, 0, 0, 10, a));
            b.setPadding(dp(10), dp(8), dp(10), dp(8));
            add(b, 10);
        }

        // ---- print sections
        add(Ui.label(a, "PO PDF attachment · sections shown on print"), 10);
        LinearLayout box = Ui.card(a);
        sectionBoxes.clear();
        LinearLayout row = null;
        for (int i = 0; i < SndData.SECTIONS.length; i++) {
            if (i % 2 == 0) { row = Ui.hbox(a); box.addView(row); }
            String flag = SndData.SECTIONS[i][0];
            CheckBox cb = SndUi.check(a, SndData.SECTIONS[i][1], options.optBoolean(flag, true));
            cb.setTextSize(12);
            cb.setOnCheckedChangeListener((v, on) -> { try { options.put(flag, on); } catch (Exception ignored) { } updateHidden(); });
            sectionBoxes.put(flag, cb);
            row.addView(cb, Ui.weight(1));
        }
        hiddenNote = Ui.text(a, "", 11.5f, Ui.MUTED, false);
        hiddenNote.setPadding(0, dp(6), 0, 0);
        box.addView(hiddenNote);
        updateHidden();
        add(box, 2);
        LinearLayout pr = Ui.hbox(a);
        Button preview = Ui.outline(a, "Preview PDF", Ui.TEAL);
        Button saveOpts = Ui.outline(a, "Save for this PO", Ui.TEAL_DARK);
        LinearLayout.LayoutParams l = Ui.weight(1); l.rightMargin = dp(8);
        pr.addView(preview, l);
        pr.addView(saveOpts, Ui.weight(1));
        add(pr, 8);
        preview.setOnClickListener(v -> { sync(); SndPdfView.preview(a, poId, copy(options)); });
        saveOpts.setOnClickListener(v -> saveOptions());

        // ---- email
        add(Ui.label(a, "Email preview · " + event), 12);
        LinearLayout mail = Ui.card(a);
        mail.addView(Ui.text(a, "To (supplier first)", 11.5f, Ui.MUTED, true));
        toIn = SndUi.emails(a, "supplier@company.com");
        toIn.setText(to);
        mail.addView(toIn, Ui.matchWrap(a, 4));
        mail.addView(Ui.text(a, "CC (route owner / department / other supplier contacts) · separate with ;", 11.5f, Ui.MUTED, true), Ui.matchWrap(a, 10));
        ccIn = SndUi.emails(a, "name@fourstarindustries.com; …");
        ccIn.setText(cc);
        mail.addView(ccIn, Ui.matchWrap(a, 4));
        mail.addView(Ui.text(a, "Subject", 11.5f, Ui.MUTED, true), Ui.matchWrap(a, 10));
        subjectIn = Ui.input(a, "Subject", false);
        subjectIn.setText(subject);
        mail.addView(subjectIn, Ui.matchWrap(a, 4));
        mail.addView(Ui.text(a, "Message", 11.5f, Ui.MUTED, true), Ui.matchWrap(a, 10));
        bodyIn = SndUi.area(a, "Message", 6);
        bodyIn.setText(body);
        mail.addView(bodyIn, Ui.matchWrap(a, 4));
        String tkey = template != null ? SndData.s(template, "template_key") : route != null ? SndData.s(route, "template_key") : "";
        mail.addView(Ui.pair(a, "Template", tkey.isEmpty() ? event : tkey.toUpperCase(Locale.ROOT)));
        mail.addView(Ui.pair(a, "Next stage", SndData.s(context, "next_stage")));
        if (route == null) {
            TextView warn = Ui.text(a, "No enabled notification route for " + event + " - the email is sent to the To / CC above.", 11.5f, Ui.AMBER_FG, false);
            mail.addView(warn, Ui.matchWrap(a, 4));
        }
        add(mail, 2);

        // ---- attachments
        add(Ui.label(a, "Attachments"), 12);
        LinearLayout att = Ui.card(a);
        pdfBox = SndUi.check(a, po.fileName() + " (generated, sections as ticked)", includePdf);
        att.addView(pdfBox);
        int docs = po.attachments.length();
        docsBox = SndUi.check(a, "PO documents on this record (" + docs + ")", includeDocs && docs > 0);
        docsBox.setEnabled(docs > 0);
        att.addView(docsBox);
        for (int i = 0; i < docs && i < 25; i++) {
            JSONObject d = po.attachments.optJSONObject(i);
            if (d == null) continue;
            String n = SndData.s(d, "file_name").isEmpty() ? SndData.s(d, "document_title") : SndData.s(d, "file_name");
            TextView t = Ui.text(a, "• " + n + "  (" + Ui.pretty(SndData.s(d, "document_type")) + ")", 11.5f, Ui.MUTED, false);
            t.setPadding(dp(32), 0, 0, dp(2));
            att.addView(t);
        }
        add(att, 2);

        Button send = Ui.primary(a, sending ? "Sending…" : "Review & send to supplier");
        send.setEnabled(!sending && blocker == null);
        send.setOnClickListener(v -> confirmSend());
        add(send, 14);
        TextView note = Ui.text(a, "QCMS saves the email in the outbox and sends it through the company email server. "
            + "The generated PDF is removed from storage after it is sent.", 11, Ui.MUTED, false);
        add(note, 6);
    }

    private String blocker() {
        if (po.cancelled()) return "This Purchase Order is CANCELLED and cannot be sent to the supplier.";
        if (!po.approved()) return "This Purchase Order is not APPROVED yet. Approve it first - the supplier only receives approved POs. (Preview PDF is available.)";
        return null;
    }

    private void updateHidden() {
        if (hiddenNote == null) return;
        List<String> hidden = new ArrayList<>();
        for (String[] s : SndData.SECTIONS) if (!options.optBoolean(s[0], true)) hidden.add(s[1]);
        hiddenNote.setText("Hidden on print: " + (hidden.isEmpty() ? "nothing - all sections print" : String.join(", ", hidden)));
    }

    private static JSONObject copy(JSONObject o) {
        try { return new JSONObject(o.toString()); } catch (Exception e) { return new JSONObject(); }
    }

    /** Keep typed values when the screen is rebuilt. */
    private void sync() {
        if (toIn != null) to = SndUi.text(toIn);
        if (ccIn != null) cc = SndUi.text(ccIn);
        if (subjectIn != null) subject = SndUi.text(subjectIn);
        if (bodyIn != null) body = SndUi.text(bodyIn);
        if (pdfBox != null) includePdf = pdfBox.isChecked();
        if (docsBox != null) includeDocs = docsBox.isChecked();
    }

    /** SupplyChainService.set_purchase_order_print_options. */
    private void saveOptions() {
        sync();
        JSONObject clean = SndData.cleanOptions(options);
        Api.async(() -> api.update("supply_purchase_orders", poId, new JSONObject().put("print_options", clean)), (row, err) -> {
            if (err != null) {
                String m = Api.message(err);
                a.toast(m.contains("print_options") ? "Per-PO print options need the R23 database step (QCMS_R23_RUN_IN_SUPABASE.sql)." : m);
                return;
            }
            try { po.header.put("print_options", clean); } catch (Exception ignored) { }
            a.toast("Saved. Downloads, batch prints and emailed PDFs of this PO use these sections.");
        });
    }

    private void confirmSend() {
        sync();
        List<String> toList = SndMail.splitEmails(to);
        List<String> ccList = SndMail.splitEmails(cc);
        String problem = null;
        if (toList.isEmpty()) problem = "Enter the supplier email in To.";
        else for (String e : toList) if (SndMail.valid(e).isEmpty()) { problem = "Not a valid email address in To: " + e; break; }
        if (problem == null) for (String e : ccList) if (SndMail.valid(e).isEmpty()) { problem = "Not a valid email address in CC: " + e; break; }
        if (problem == null && subject.trim().isEmpty()) problem = "Enter a subject.";
        if (problem == null && body.trim().isEmpty()) problem = "Enter the message.";
        if (problem != null) { a.toast(problem); return; }
        List<String> files = new ArrayList<>();
        if (includePdf) files.add(po.fileName());
        if (includeDocs && po.attachments.length() > 0) files.add(po.attachments.length() + " PO document(s)");
        String msg = "To: " + String.join(", ", toList)
            + "\nCC: " + (ccList.isEmpty() ? "—" : String.join(", ", ccList))
            + "\nSubject: " + subject.trim()
            + "\nAttachments: " + (files.isEmpty() ? "None" : String.join(" + ", files))
            + "\n\nConfirm the recipients before QCMS releases this email.";
        a.confirm("Send " + po.number() + " to the supplier?", msg, "Send email", () -> send(toList, ccList));
    }

    private void send(List<String> toList, List<String> ccList) {
        sending = true;
        resultStatus = null;
        a.rebuild();
        JSONObject sendOptions = copy(options);
        boolean withPdf = includePdf, withDocs = includeDocs;
        String subj = subject.trim(), text = body;
        Api.async(() -> {
            // 1. sections chosen here are saved on the PO (approval / release panel behaviour; non-blocking)
            try { api.update("supply_purchase_orders", poId, new JSONObject().put("print_options", SndData.cleanOptions(sendOptions))); } catch (Exception ignored) { }
            // 2. attachment manifest: generated PDF (stored under notification_exports, generated=true) + PO documents
            JSONArray manifest = new JSONArray();
            String uploaded = null;
            if (withPdf) {
                byte[] pdf = SndPoPdf.build(po, sendOptions);
                JSONObject m = SndMail.uploadExport(api, SndMail.exportFolder(api), po.fileName(), pdf, "application/pdf", true);
                uploaded = m.optString("object_path");
                manifest.put(m);
            }
            if (withDocs) {
                Set<String> seen = new HashSet<>();
                for (int i = 0; i < po.attachments.length() && i < 25; i++) {
                    JSONObject d = po.attachments.optJSONObject(i);
                    String path = d == null ? "" : SndData.s(d, "object_path");
                    if (path.isEmpty() || !seen.add(path)) continue;
                    JSONObject m = new JSONObject();
                    m.put("bucket", SndMail.BUCKET);
                    m.put("object_path", path);
                    String fn = SndData.s(d, "file_name").isEmpty() ? SndData.s(d, "document_title") : SndData.s(d, "file_name");
                    m.put("file_name", fn.isEmpty() ? "attachment" : fn);
                    m.put("mime_type", SndData.s(d, "mime_type").isEmpty() ? "application/octet-stream" : SndData.s(d, "mime_type"));
                    m.put("generated", false);
                    manifest.put(m);
                }
            }
            // 3. outbox row (NotificationService.enqueue payload)
            String primary = toList.get(0);
            JSONObject ctx = copy(context);
            if (toList.size() > 1) ctx.put("to_emails", SndMail.toArray(toList));
            List<String> finalCc = new ArrayList<>();
            for (String v : ccList) if (!v.equalsIgnoreCase(primary) && !SndMail.containsIgnoreCase(finalCc, v) && !SndMail.containsIgnoreCase(toList, v)) finalCc.add(v);
            String tkey = template != null && !SndData.s(template, "template_key").isEmpty() ? SndData.s(template, "template_key")
                : route != null && !SndData.s(route, "template_key").isEmpty() ? SndData.s(route, "template_key") : event;
            JSONObject payload = new JSONObject();
            payload.put("event_key", event);
            payload.put("recipient_email", primary);
            payload.put("recipient_name", SndMail.containsIgnoreCase(supplierEmails, primary) && !supplierName.isEmpty() ? supplierName : JSONObject.NULL);
            payload.put("cc_emails", SndMail.toArray(finalCc));
            payload.put("subject", subj);
            payload.put("body_text", text);
            payload.put("body_html", SndMail.notificationHtml(text));
            payload.put("related_table", "supply_purchase_orders");
            payload.put("related_id", poId);
            payload.put("context", ctx);
            payload.put("template_key", tkey.toUpperCase(Locale.ROOT));
            payload.put("attachment_manifest", manifest);
            payload.put("dedupe_key", JSONObject.NULL);
            payload.put("is_automatic", false);
            payload.put("status", "PENDING");
            JSONObject row;
            try {
                row = api.insert("qcms_notification_outbox", payload);
            } catch (Exception e) {
                if (uploaded != null) api.removeObject(uploaded);
                throw e;
            }
            // 4. dispatch + wait for the delivery result
            List<String> ids = new ArrayList<>();
            ids.add(SndData.s(row, "id"));
            JSONObject result = SndMail.dispatch(api, ids);
            List<JSONObject> rows = SndMail.waitForOutbox(api, ids, 20000);
            String[] out = SndMail.outcome(rows, result);
            return out;
        }, (out, err) -> {
            sending = false;
            if (err != null) {
                resultStatus = "FAILED";
                resultMessage = "Nothing was sent: " + Api.message(err);
            } else {
                resultStatus = out[0];
                resultMessage = "SENT".equals(out[0]) ? "The controlled PO PDF was emailed to " + toList.get(0) + "." : out[1];
                a.toast("SENT".equals(out[0]) ? "PO emailed to the supplier." : "QUEUED".equals(out[0]) ? "Email queued." : "Email not sent - see the message.");
            }
            a.rebuild();
            if (scroll != null) scroll.post(() -> scroll.scrollTo(0, 0));
        });
    }
}
