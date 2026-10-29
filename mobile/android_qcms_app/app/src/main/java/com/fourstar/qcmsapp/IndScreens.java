package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * R39 · Indirect Purchase screens (web app_pages/indirect_purchase.py, module key INDIRECT_PURCHASE) over IndSvc / IndPdf:
 * PO register + record (print PDF, e-mail to supplier, submit, approval, cancel, approval history), PO entry / revision
 * (also from an approved requisition), PO approval worklist (approve / reject), requisitions (new, approve / reject,
 * convert to PO). Indirect POs carry no customer data. All rights through qcms_indirect_purchase_can (same as RLS).
 */
final class IndScreens {
    private IndScreens() { }

    static String money(double v, String currency) { return (currency == null || currency.isEmpty() ? "INR" : currency) + " " + String.format(Locale.US, "%,.2f", v); }

    // ================================================================== shared actions
    /** PDF (controlled print with the current approval watermark): View · Download · Print · Share. */
    static void pdf(MainActivity a, String poId) {
        Api api = Api.get(a);
        a.toast("Preparing the Indirect PO PDF…");
        Api.async(() -> {
            IndSvc svc = new IndSvc(api);
            JSONObject h = svc.purchaseOrder(poId);
            return new Object[]{h, IndPdf.poById(api, svc, poId, true)};
        }, (r, err) -> {
            if (err != null || r == null) { a.toast("Indirect PO PDF could not be generated: " + Api.message(err)); return; }
            JSONObject h = (JSONObject) r[0];
            ExportKit.layoutActions(a, IndPdf.TITLE + " " + IndSvc.c(h, "po_number"), IndPdf.fileName(h).replace(".pdf", ""), (byte[]) r[1]);
        });
    }

    /** _email_panel: editable To / CC / Subject / Body; the controlled PDF is attached through the QCMS outbox (purpose SUPPLIER / APPROVAL). */
    static void email(MainActivity a, String poId, String purpose, Runnable done) {
        Api api = Api.get(a);
        Api.async(() -> {
            IndSvc svc = new IndSvc(api);
            JSONObject h = svc.purchaseOrder(poId);
            String to;
            if ("APPROVAL".equals(purpose)) to = IndSvc.c(svc.approvalTarget(poId), "email");
            else {
                JSONObject v = h.optJSONObject("vendor_snapshot");
                to = SupSvc.first(IndSvc.c(v, "email"), IndSvc.c(svc.party(IndSvc.c(h, "supplier_id")), "email"));
            }
            return new Object[]{h, to.split("[,;\\s]+")[0], IndPdf.poById(api, svc, poId, true)};
        }, (r, err) -> {
            if (err != null || r == null) { a.toast(Api.message(err)); return; }
            JSONObject h = (JSONObject) r[0];
            byte[] pdf = (byte[]) r[2];
            String[] text = IndSvc.poEmailText(h, purpose);
            List<Field> f = new ArrayList<>();
            f.add(Field.text("to", "To").req());
            f.add(Field.text("cc", "CC (comma separated)"));
            f.add(Field.text("subject", "Subject").req());
            f.add(Field.area("body", "Message"));
            JSONObject v = new JSONObject();
            try { v.put("to", r[1]); v.put("subject", text[0]); v.put("body", text[1]); } catch (Exception ignored) { }
            InspUtil.formDialog(a, "APPROVAL".equals(purpose) ? "E-mail draft PO to the approver" : "E-mail approved PO to supplier", f, v, "Send e-mail", (form, values) -> {
                String to = form.str("to").trim();
                if (!to.contains("@")) throw new Api.ApiException(422, "Enter a valid To address (the supplier e-mail comes from Party Master).");
                List<String> cc = new ArrayList<>();
                for (String x : form.str("cc").replace(";", ",").split(",")) if (x.contains("@")) cc.add(x.trim());
                String event = "APPROVAL".equals(purpose) ? "INDIRECT_PO_APPROVAL_PENDING" : "INDIRECT_PO_RELEASED";
                Api.async(() -> queueMail(api, event, "indirect_purchase_orders", poId, to, cc, form.str("subject"), form.str("body"), IndPdf.fileName(h), pdf,
                    "APPROVAL".equals(purpose) ? "" : IndSvc.supplierName(h)), (res, e2) -> {
                    if (e2 != null) { a.toast("The e-mail could not be queued: " + Api.message(e2)); return; }
                    a.toast(res);
                    if (done != null) done.run();
                });
            });
        });
    }

    /** NotificationService.enqueue + dispatch (include_generated_pdf=True, include_supplier=False). */
    static String queueMail(Api api, String event, String table, String id, String to, List<String> cc, String subject, String body, String fileName, byte[] pdf, String recipientName) throws Exception {
        JSONObject manifest = SndMail.uploadExport(api, SndMail.exportFolder(api), SndFiles.safeName(fileName), pdf, "application/pdf", true);
        JSONArray ccArr = new JSONArray();
        for (String c : cc) if (c.contains("@") && !c.equalsIgnoreCase(to)) ccArr.put(c);
        JSONObject row = new JSONObject().put("event_key", event).put("recipient_email", to).put("recipient_name", recipientName == null || recipientName.isEmpty() ? JSONObject.NULL : recipientName)
            .put("cc_emails", ccArr).put("subject", subject).put("body_text", body == null ? "" : body).put("body_html", SndMail.notificationHtml(body == null ? "" : body))
            .put("related_table", table).put("related_id", id).put("context", new JSONObject().put("event_key", event).put("document_type", "Indirect Purchase"))
            .put("template_key", event).put("attachment_manifest", new JSONArray().put(manifest)).put("is_automatic", false).put("status", "PENDING");
        JSONObject saved = api.insert("qcms_notification_outbox", row);
        List<String> ids = new ArrayList<>();
        if (!IndSvc.c(saved, "id").isEmpty()) ids.add(IndSvc.c(saved, "id"));
        JSONObject res = SndMail.dispatch(api, ids);
        return res.has("error") ? "E-mail queued; delivery returned: " + res.optString("error") + ". It is retried from the outbox." : "E-mail sent to " + to + " with the controlled PDF.";
    }

    // ================================================================== PO register
    static final class PoList extends Screen {
        private List<JSONObject> rows;
        private LinearLayout list;
        private EditText search;
        private static String status = "ALL";

        PoList(MainActivity a) { super(a); }
        @Override public String title() { return "Indirect Purchase Orders"; }
        @Override public String subtitle() { return "IPO series · approval · print · e-mail"; }
        @Override public int tab() { return Catalog.SUPPLY; }
        @Override public void reload() { rows = null; a.rebuild(); }

        @Override
        public View build() {
            newPage();
            LinearLayout top = Ui.hbox(a);
            Button create = Ui.primary(a, "+ New Indirect PO");
            create.setOnClickListener(v -> a.push(new PoEdit(a, null, null)));
            top.addView(create, Ui.weight(1));
            Button appr = Ui.outline(a, "Approvals", Ui.TEAL_DARK);
            appr.setOnClickListener(v -> a.push(new Approvals(a)));
            LinearLayout.LayoutParams lp = Ui.weight(1); lp.leftMargin = dp(6);
            top.addView(appr, lp);
            add(top, 0);
            search = Ui.input(a, "Search IPO, supplier, department, item", false);
            add(search, 8);
            Button st = Ui.outline(a, "Status: " + ("ALL".equals(status) ? "All" : IndSvc.statusLabel(status)) + " (tap to change)", Ui.TEAL);
            String[] sts = {"ALL", "DRAFT", "PENDING_APPROVAL", "APPROVED", "PARTIALLY_RECEIVED", "CLOSED", "REJECTED", "CANCELLED"};
            List<String> labels = new ArrayList<>();
            for (String s : sts) labels.add("ALL".equals(s) ? "All" : IndSvc.statusLabel(s));
            st.setOnClickListener(v -> InspUtil.pick(a, "Status", Arrays.asList(sts), labels, p -> { status = p; a.rebuild(); }));
            add(st, 6);
            list = Ui.vbox(a);
            add(list, 6);
            search.addTextChangedListener(new android.text.TextWatcher() {
                @Override public void beforeTextChanged(CharSequence s, int x, int c, int y) { }
                @Override public void onTextChanged(CharSequence s, int x, int b, int c) { }
                @Override public void afterTextChanged(android.text.Editable e) { fill(); }
            });
            if (rows != null) { fill(); return scroll; }
            list.addView(loading());
            Api.async(() -> {
                IndSvc svc = new IndSvc(api);
                if (!svc.can("view")) throw new Api.ApiException(403, "Your role has no Indirect Purchase View right.");
                return svc.poRegisterRows();
            }, (r, err) -> {
                list.removeAllViews();
                if (err != null) { list.addView(error(err, this::reload)); return; }
                rows = r;
                fill();
            });
            return scroll;
        }

        private void fill() {
            if (rows == null || list == null) return;
            list.removeAllViews();
            String q = search.getText().toString().trim().toLowerCase(Locale.ROOT);
            List<JSONObject> shown = new ArrayList<>();
            for (JSONObject r : rows) {
                if (!"ALL".equals(status) && !status.equals(IndSvc.c(r, "Status"))) continue;
                String hay = (IndSvc.c(r, "IPO Number") + " " + IndSvc.c(r, "Supplier") + " " + IndSvc.c(r, "Department") + " " + IndSvc.c(r, "Items")).toLowerCase(Locale.ROOT);
                if (!q.isEmpty() && !hay.contains(q)) continue;
                shown.add(r);
            }
            if (shown.isEmpty()) { list.addView(Ui.empty(a, "No Indirect PO matches these filters.")); return; }
            List<String> head = Arrays.asList("IPO Number", "PO Date", "Branch", "Supplier", "Department", "Items", "Grand Total", "Delivery Date", "Received %", "Status", "Approval", "Delivery");
            List<List<String>> data = new ArrayList<>();
            for (JSONObject r : shown) data.add(Arrays.asList(IndSvc.c(r, "IPO Number"), Ui.date(IndSvc.c(r, "PO Date")), IndSvc.c(r, "Branch"), IndSvc.c(r, "Supplier"),
                IndSvc.c(r, "Department"), IndSvc.c(r, "Items"), money(IndSvc.num(r, "Grand Total"), IndSvc.c(r, "Currency")), Ui.date(IndSvc.c(r, "Delivery Date")),
                Ui.num(IndSvc.num(r, "Received %"), 1), IndSvc.statusLabel(IndSvc.c(r, "Status")), IndSvc.statusLabel(IndSvc.c(r, "Approval Status")), IndSvc.c(r, "Delivery")));
            list.addView(new DataGrid(a, "Indirect PO register", head, data, 460, i -> a.push(new PoView(a, IndSvc.c(shown.get(i), "_id")))));
        }
    }

    // ================================================================== PO record
    static final class PoView extends Screen {
        private final String id;
        private JSONObject po, target;
        private List<JSONObject> items, log;
        private Map<String, Boolean> perms;

        PoView(MainActivity a, String id) { super(a); this.id = id; }
        @Override public String title() { return po == null ? "Indirect PO" : IndSvc.c(po, "po_number"); }
        @Override public String subtitle() { return po == null ? "" : IndSvc.statusLabel(IndSvc.c(po, "status")) + " · " + IndSvc.supplierName(po); }
        @Override public int tab() { return Catalog.SUPPLY; }
        @Override public void reload() { po = null; a.rebuild(); }

        @Override
        public View build() {
            newPage();
            if (po != null) { render(); return scroll; }
            page.addView(loading());
            Api.async(() -> {
                IndSvc svc = new IndSvc(api);
                JSONObject p = svc.purchaseOrder(id);
                if (p.length() == 0) throw new Api.ApiException(404, "Indirect PO not found or not visible for your role.");
                JSONObject t = "PENDING_APPROVAL".equals(IndSvc.up(p, "approval_status")) ? svc.approvalTarget(id) : new JSONObject();
                return new Object[]{p, svc.poItems(id), svc.approvalLog(id), svc.perms(), t};
            }, (r, err) -> {
                page.removeAllViews();
                if (err != null) { page.addView(error(err, this::reload)); return; }
                po = (JSONObject) r[0];
                @SuppressWarnings("unchecked") List<JSONObject> it = (List<JSONObject>) r[1];
                @SuppressWarnings("unchecked") List<JSONObject> lg = (List<JSONObject>) r[2];
                @SuppressWarnings("unchecked") Map<String, Boolean> pm = (Map<String, Boolean>) r[3];
                items = it; log = lg; perms = pm; target = (JSONObject) r[4];
                a.rebuildTitle(this);
                render();
            });
            return scroll;
        }

        private boolean can(String p) { return perms != null && Boolean.TRUE.equals(perms.get(p)); }

        private void render() {
            page.removeAllViews();
            String cur = SupSvc.first(IndSvc.c(po, "currency"), "INR");
            String status = IndSvc.up(po, "status");
            LinearLayout card = Ui.card(a);
            card.addView(Ui.pair(a, "IPO Number", IndSvc.c(po, "po_number") + " · Rev " + (int) IndSvc.num(po, "revision_no")));
            card.addView(Ui.pair(a, "PO Date", Ui.date(IndSvc.d10(po.opt("po_date")))));
            card.addView(Ui.pair(a, "Supplier", SupSvc.first(IndSvc.supplierName(po), "-")));
            card.addView(Ui.pair(a, "Department · Cost centre", SupSvc.first(IndSvc.c(po, "department"), "-") + " · " + SupSvc.first(IndSvc.c(po, "cost_centre"), "-")));
            card.addView(Ui.pair(a, "Requisitioner", SupSvc.first(IndSvc.c(po, "requisitioner"), "-")));
            card.addView(Ui.pair(a, "Delivery date", Ui.date(IndSvc.d10(po.opt("delivery_date")))));
            card.addView(Ui.pair(a, "Taxable", money(IndSvc.num(po, "subtotal"), cur)));
            card.addView(Ui.pair(a, "Grand Total", money(IndSvc.num(po, "grand_total"), cur)));
            card.addView(Ui.pair(a, "Status", IndSvc.statusLabel(status) + " · approval " + IndSvc.statusLabel(IndSvc.up(po, "approval_status"))));
            if (target != null && target.length() > 0) card.addView(Ui.pair(a, "Approver", SupSvc.first(IndSvc.c(target, "employee_name"), "Any approver") + " · " + IndSvc.c(target, "level_name")));
            if (!IndSvc.c(po, "approval_remarks").isEmpty()) card.addView(Ui.pair(a, "Approval remarks", IndSvc.c(po, "approval_remarks")));
            if ("CANCELLED".equals(status)) card.addView(Ui.pair(a, "Cancelled", SupSvc.first(IndSvc.c(po, "cancellation_reason"), "-")));
            add(card, 0);
            List<List<String>> data = new ArrayList<>();
            for (JSONObject l : items) data.add(Arrays.asList(String.valueOf((int) IndSvc.num(l, "line_no")), SupSvc.first(IndSvc.c(l, "item_code"), "-"), IndSvc.c(l, "item_name"),
                SupSvc.first(IndSvc.c(l, "hsn_sac"), "-"), Ui.num(IndSvc.num(l, "quantity"), 3), IndSvc.c(l, "uom"), Ui.num(IndSvc.num(l, "rate"), 2), Ui.num(IndSvc.num(l, "discount_percent"), 2),
                Ui.num(IndSvc.num(l, "taxable_amount"), 2), Ui.num(IndSvc.num(l, "gst_percent"), 2), Ui.num(IndSvc.num(l, "line_total"), 2),
                Ui.num(IndSvc.num(l, "received_qty"), 3), Ui.num(IndSvc.num(l, "accepted_qty"), 3), Ui.num(IndSvc.num(l, "rejected_qty"), 3)));
            add(new DataGrid(a, "PO lines", Arrays.asList("#", "Item Code", "Item", "HSN/SAC", "Qty", "UOM", "Rate", "Disc %", "Taxable", "GST %", "Amount", "Received", "Accepted", "Rejected"), data, 300, null), 8);
            Button print = Ui.primary(a, "Indirect PO PDF · View · Download · Print · Share");
            print.setOnClickListener(v -> pdf(a, id));
            add(print, 10);
            boolean write = can("create") || can("edit");
            if ("APPROVED".equals(IndSvc.up(po, "approval_status"))) {
                Button mail = Ui.outline(a, "E-mail approved PO to supplier (PDF attached)", Ui.TEAL);
                mail.setEnabled(write);
                mail.setOnClickListener(v -> email(a, id, "SUPPLIER", null));
                add(mail, 8);
            }
            if (IndSvc.EDITABLE_PO_STATUSES.contains(status)) {
                Button edit = Ui.outline(a, "APPROVED".equals(status) ? "Controlled revision of the approved PO" : "Edit / Revise", Ui.TEAL_DARK);
                edit.setEnabled(write);
                edit.setOnClickListener(v -> a.push(new PoEdit(a, id, null)));
                add(edit, 8);
            }
            if ("DRAFT".equals(status) || "REJECTED".equals(status)) {
                Button submit = Ui.outline(a, "Submit for Approval", Ui.TEAL_DARK);
                submit.setEnabled(write);
                submit.setOnClickListener(v -> Api.async(() -> new IndSvc(api).submitPo(id, api.employeeId), (r, err) -> {
                    if (err != null) { a.toast(Api.message(err)); return; }
                    a.toast("Indirect PO submitted for approval.");
                    reload();
                }));
                add(submit, 8);
            }
            if ("PENDING_APPROVAL".equals(IndSvc.up(po, "approval_status"))) {
                LinearLayout row = Ui.hbox(a);
                Button ok = Ui.primary(a, "Approve");
                Button no = Ui.outline(a, "Reject", Ui.ORANGE);
                ok.setEnabled(can("approve"));
                no.setEnabled(can("approve"));
                ok.setOnClickListener(v -> a.askText("Approve " + IndSvc.c(po, "po_number"), "Approval remarks (optional)", "Approve", false, rem -> decide(true, rem)));
                no.setOnClickListener(v -> a.askText("Reject " + IndSvc.c(po, "po_number"), "Rejection remarks (required)", "Reject", true, rem -> decide(false, rem)));
                row.addView(ok, Ui.weight(1));
                LinearLayout.LayoutParams lp = Ui.weight(1); lp.leftMargin = dp(6);
                row.addView(no, lp);
                add(row, 10);
                Button mail = Ui.outline(a, "E-mail draft PO to the approver", Ui.TEAL);
                mail.setEnabled(write);
                mail.setOnClickListener(v -> email(a, id, "APPROVAL", null));
                add(mail, 8);
                if (!can("approve")) add(Ui.text(a, "Approval needs the Indirect Purchase Approve right; self-approval is blocked.", 11.5f, Ui.MUTED, false), 4);
            }
            if (!"CLOSED".equals(status) && !"CANCELLED".equals(status)) {
                Button cancel = Ui.outline(a, "Cancel this PO (reason required)", Ui.ORANGE);
                cancel.setEnabled(write);
                cancel.setOnClickListener(v -> a.askText("Cancel " + IndSvc.c(po, "po_number"), "Cancellation reason", "Cancel Indirect PO", true, reason ->
                    Api.async(() -> new IndSvc(api).cancelPo(id, reason, api.employeeId), (r, err) -> {
                        if (err != null) { a.toast(Api.message(err)); return; }
                        a.toast("Indirect PO cancelled.");
                        reload();
                    })));
                add(cancel, 8);
            }
            if (!log.isEmpty()) {
                List<List<String>> lg = new ArrayList<>();
                for (JSONObject r : log) lg.add(Arrays.asList(IndSvc.c(r, "created_at").replace("T", " ").substring(0, Math.min(19, IndSvc.c(r, "created_at").length())),
                    SupSvc.first(IndSvc.c(r, "level_name"), IndSvc.c(r, "level_no")), IndSvc.c(r, "action"), IndSvc.c(r, "remarks")));
                add(new DataGrid(a, "Approval history", Arrays.asList("When", "Level", "Action", "Remarks"), lg, 220, null), 12);
            }
        }

        private void decide(boolean approve, String remarks) {
            Api.async(() -> {
                IndSvc svc = new IndSvc(api);
                return approve ? svc.approvePo(id, remarks) : svc.rejectPo(id, remarks);
            }, (r, err) -> {
                if (err != null) { a.toast(Api.message(err)); return; }
                a.toast(approve ? "Indirect PO " + IndSvc.c(po, "po_number") + " " + ("APPROVED".equals(IndSvc.up(r, "approval_status")) ? "approved." : "approved at this level; next level pending.")
                    : "Indirect PO rejected.");
                reload();
            });
        }
    }

    // ================================================================== PO approval worklist
    static final class Approvals extends Screen {
        private List<JSONObject> rows;
        Approvals(MainActivity a) { super(a); }
        @Override public String title() { return "Indirect PO Approval"; }
        @Override public String subtitle() { return "Pending approval worklist · INDIRECT_PURCHASE route"; }
        @Override public int tab() { return Catalog.SUPPLY; }
        @Override public void reload() { rows = null; a.rebuild(); }

        @Override
        public View build() {
            newPage();
            LinearLayout box = Ui.vbox(a);
            add(box, 0);
            if (rows == null) {
                box.addView(loading());
                Api.async(() -> new IndSvc(api).pendingApprovalRows(), (r, err) -> {
                    box.removeAllViews();
                    if (err != null) { box.addView(error(err, this::reload)); return; }
                    rows = r;
                    fill(box);
                });
            } else fill(box);
            return scroll;
        }

        private void fill(LinearLayout box) {
            if (rows.isEmpty()) { box.addView(Ui.empty(a, "No Indirect PO is waiting for approval.")); return; }
            List<List<String>> data = new ArrayList<>();
            for (JSONObject r : rows) data.add(Arrays.asList(IndSvc.c(r, "IPO Number"), Ui.date(IndSvc.c(r, "PO Date")), IndSvc.c(r, "Supplier"), IndSvc.c(r, "Department"),
                money(IndSvc.num(r, "Grand Total"), "INR"), IndSvc.c(r, "Requisitioner"), IndSvc.c(r, "Approver"), IndSvc.c(r, "Approval Level"), String.valueOf((long) IndSvc.num(r, "Pending Days"))));
            box.addView(new DataGrid(a, "Pending approval", Arrays.asList("IPO Number", "PO Date", "Supplier", "Department", "Grand Total", "Requisitioner", "Approver", "Level", "Pending Days"),
                data, 420, i -> a.push(new PoView(a, IndSvc.c(rows.get(i), "_id")))));
            box.addView(Ui.text(a, "Open a PO to check it as the supplier will receive it, then approve or reject with remarks.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 4));
        }
    }

    // ================================================================== PO entry / revision
    static final class PoEdit extends Screen {
        private final String id;
        private final String requisitionId;
        private IndSvc svc;
        private List<JSONObject> suppliers, branches, items;
        private JSONObject existing, prefill;
        private List<JSONObject> existingLines;
        private FormView form;
        private RowsEditor grid;
        private boolean loaded, saving;

        PoEdit(MainActivity a, String id, String requisitionId) { super(a); this.id = id; this.requisitionId = requisitionId; }
        @Override public String title() { return id == null ? "New Indirect PO" : "Revise " + IndSvc.c(existing, "po_number"); }
        @Override public String subtitle() { return "Supplier · plant · lines · terms"; }
        @Override public int tab() { return Catalog.SUPPLY; }

        @Override
        public View build() {
            newPage();
            if (loaded) { render(); return scroll; }
            page.addView(loading());
            Api.async(() -> {
                svc = new IndSvc(api);
                if (!(svc.can("create") || svc.can("edit"))) throw new Api.ApiException(403, "Your role has no Indirect Purchase Entry/Create or Edit right.");
                suppliers = svc.suppliers();
                branches = svc.branches();
                items = svc.items(true);
                if (id != null) { existing = svc.purchaseOrder(id); existingLines = svc.poItems(id); }
                if (requisitionId != null) prefill = svc.requisitionPrefill(requisitionId);
                return true;
            }, (ok, err) -> {
                if (err != null) { page.removeAllViews(); page.addView(error(err, () -> { loaded = false; a.rebuild(); })); return; }
                loaded = true;
                a.rebuildTitle(this);
                render();
            });
            return scroll;
        }

        private static void detach(View v) { if (v != null && v.getParent() != null) ((android.view.ViewGroup) v.getParent()).removeView(v); }

        private void render() {
            page.removeAllViews();
            if (form == null) build0(); else { detach(form); detach(grid); }
            LinearLayout card = Ui.card(a);
            card.addView(form);
            add(card, 0);
            add(Ui.label(a, "PO lines · + to add · tap a line to edit (master item fills UOM / GST / HSN / last price when blank)"), 12);
            add(grid, 4);
            add(Ui.text(a, "GST is CGST + SGST when the supplier is in the plant state, else IGST. Indirect POs carry no customer data.", 11.5f, Ui.MUTED, false), 4);
            Button preview = Ui.outline(a, "Preview PDF (not saved)", Ui.TEAL);
            preview.setOnClickListener(v -> preview());
            add(preview, 12);
            Button draft = Ui.outline(a, "Save as Draft", Ui.TEAL_DARK);
            draft.setOnClickListener(v -> save(false, draft));
            add(draft, 8);
            Button submit = Ui.primary(a, "Save & Submit for Approval");
            submit.setOnClickListener(v -> save(true, submit));
            add(submit, 8);
            if ("APPROVED".equals(IndSvc.up(existing, "status")))
                add(Ui.text(a, "Controlled revision: the approved PO returns to approval with revision number + 1. POs with receipts cannot be revised.", 11.5f, Ui.AMBER_FG, false), 6);
        }

        private void build0() {
            List<String> sIds = new ArrayList<>(), sNames = new ArrayList<>();
            for (JSONObject p : suppliers) { sIds.add(IndSvc.c(p, "id")); sNames.add(Lookups.join(IndSvc.c(p, "party_code"), IndSvc.c(p, "party_name"), IndSvc.c(p, "city"))); }
            List<String> bIds = new ArrayList<>(), bNames = new ArrayList<>();
            String defBranch = "";
            for (JSONObject b : branches) {
                bIds.add(IndSvc.c(b, "id"));
                bNames.add(IndSvc.c(b, "branch_name") + " · " + SupSvc.first(IndSvc.c(b, "plant_code"), IndSvc.c(b, "branch_code")));
                if (b.optBoolean("is_default", false) || defBranch.isEmpty()) defBranch = IndSvc.c(b, "id");
            }
            List<Field> f = new ArrayList<>();
            f.add(Field.select("supplier_id", "Supplier (Party Master)", sIds.toArray(new String[0])).labels(sNames.toArray(new String[0])).req());
            if (!bIds.isEmpty()) f.add(Field.select("company_branch_id", "Company Branch / Plant (ship-to = plant)", bIds.toArray(new String[0])).labels(bNames.toArray(new String[0])).req());
            f.add(Field.date("po_date", "PO Date").req());
            f.add(Field.date("delivery_date", "Delivery Date"));
            f.add(Field.text("department", "Department").req());
            f.add(Field.text("cost_centre", "Cost Centre"));
            f.add(Field.text("requisitioner", "Requisitioner"));
            f.add(Field.text("payment_term", "Payment Term"));
            f.add(Field.text("incoterm", "Incoterm"));
            f.add(Field.text("ship_via", "Ship Via"));
            f.add(Field.text("quotation_reference", "Quotation Reference"));
            f.add(Field.date("quotation_date", "Quotation Date"));
            f.add(Field.select("currency", "Currency", "INR", "USD", "EUR", "GBP").req());
            f.add(Field.number("freight_amount", "Freight").range(0, Double.MAX_VALUE));
            f.add(Field.number("other_amount", "Other Charges").range(0, Double.MAX_VALUE));
            f.add(Field.number("over_receipt_tolerance_percent", "Over-receipt tolerance %").range(0, 50));
            f.add(Field.area("terms", "Terms"));
            f.add(Field.area("special_instructions", "Special Instructions"));
            f.add(Field.area("remarks", "Remarks"));
            form = new FormView(a, f);
            JSONObject src = existing != null ? existing : prefill != null ? prefill : new JSONObject();
            form.set("supplier_id", IndSvc.c(src, "supplier_id"));
            form.set("company_branch_id", SupSvc.first(IndSvc.c(src, "company_branch_id"), defBranch));
            form.set("po_date", existing != null ? IndSvc.d10(existing.opt("po_date")) : Ui.today());
            for (String k : new String[]{"department", "cost_centre", "requisitioner", "payment_term", "incoterm", "ship_via", "quotation_reference", "remarks"}) form.set(k, IndSvc.c(src, k));
            for (String k : new String[]{"delivery_date", "quotation_date"}) if (!IndSvc.d10(src.opt(k)).isEmpty()) form.set(k, IndSvc.d10(src.opt(k)));
            form.set("currency", SupSvc.first(IndSvc.c(src, "currency"), "INR"));
            for (String k : new String[]{"freight_amount", "other_amount", "over_receipt_tolerance_percent"}) form.set(k, Ui.num(IndSvc.num(src, k), 2).replace(",", ""));
            form.set("terms", existing != null ? IndSvc.c(existing, "terms") : IndSvc.DEFAULT_TERMS);
            form.set("special_instructions", existing != null ? IndSvc.c(existing, "special_instructions") : IndSvc.DEFAULT_INSTRUCTIONS);
            List<String> iIds = new ArrayList<>(), iNames = new ArrayList<>();
            iIds.add(""); iNames.add("Free description (one-off purchase)");
            for (JSONObject it : items) { iIds.add(IndSvc.c(it, "id")); iNames.add(Lookups.join(IndSvc.c(it, "item_code"), IndSvc.c(it, "item_name"), IndSvc.c(it, "uom"))); }
            grid = new RowsEditor(a, "PO lines", Arrays.asList(
                Field.select("item_id", "Master item", iIds.toArray(new String[0])).labels(iNames.toArray(new String[0])),
                Field.text("item_name", "Item / description (free text when no master item)"), Field.text("description", "Specification / description"),
                Field.select("uom", "UOM", IndSvc.UOMS), Field.number("quantity", "Quantity").range(0, Double.MAX_VALUE).req(), Field.number("rate", "Rate").range(0, Double.MAX_VALUE),
                Field.number("discount_percent", "Discount %").range(0, 100), Field.select("gst_percent", "GST %", IndSvc.GST_RATES), Field.text("hsn_sac", "HSN / SAC"),
                Field.date("required_date", "Required Date"), Field.text("remarks", "Line remarks")),
                Arrays.asList(new String[]{"item_name", "Item"}, new String[]{"uom", "UOM"}, new String[]{"quantity", "Qty"}, new String[]{"rate", "Rate"},
                    new String[]{"discount_percent", "Disc %"}, new String[]{"gst_percent", "GST %"}, new String[]{"hsn_sac", "HSN/SAC"}, new String[]{"required_date", "Required"}));
            try { grid.template(new JSONObject().put("uom", "NOS").put("gst_percent", "18").put("quantity", "1")); } catch (Exception ignored) { }
            List<JSONObject> rows = new ArrayList<>();
            if (existingLines != null) for (JSONObject l : existingLines) rows.add(lineRow(l, "rate"));
            else if (prefill != null) { JSONArray pl = prefill.optJSONArray("lines"); for (int i = 0; pl != null && i < pl.length(); i++) rows.add(lineRow(pl.optJSONObject(i), "rate")); }
            grid.setRows(rows);
            grid.onChanged(this::fillFromMaster);
        }

        private JSONObject lineRow(JSONObject l, String rateKey) {
            JSONObject r = new JSONObject();
            try {
                for (String k : new String[]{"item_id", "item_name", "description", "uom", "hsn_sac", "remarks", "requisition_item_id"}) r.put(k, IndSvc.c(l, k));
                r.put("quantity", IndSvc.num(l, "quantity"));
                r.put("rate", IndSvc.num(l, rateKey));
                r.put("discount_percent", IndSvc.num(l, "discount_percent"));
                r.put("gst_percent", l.has("gst_percent") ? Ui.num(IndSvc.num(l, "gst_percent"), 2).replace(",", "") : "18");
                r.put("required_date", IndSvc.d10(l.opt("required_date")));
            } catch (Exception ignored) { }
            return r;
        }

        /** A picked master item fills UOM / GST % / HSN / last price / name when left blank or zero. */
        private void fillFromMaster() {
            boolean changed = false;
            for (JSONObject r : grid.rows()) {
                JSONObject it = null;
                for (JSONObject x : items) if (IndSvc.c(x, "id").equals(IndSvc.c(r, "item_id")) && !IndSvc.c(r, "item_id").isEmpty()) it = x;
                if (it == null) continue;
                try {
                    if (IndSvc.c(r, "item_name").isEmpty()) { r.put("item_name", IndSvc.c(it, "item_name")); changed = true; }
                    if (IndSvc.c(r, "hsn_sac").isEmpty() && !IndSvc.c(it, "hsn_sac").isEmpty()) { r.put("hsn_sac", IndSvc.c(it, "hsn_sac")); changed = true; }
                    if (IndSvc.num(r, "rate") == 0 && IndSvc.num(it, "last_price") > 0) { r.put("rate", IndSvc.num(it, "last_price")); changed = true; }
                    if (!IndSvc.c(it, "uom").isEmpty() && (IndSvc.c(r, "uom").isEmpty())) { r.put("uom", IndSvc.c(it, "uom")); changed = true; }
                } catch (Exception ignored) { }
            }
            if (changed) grid.refresh();
        }

        private JSONObject header() throws Exception {
            JSONObject p = new JSONObject();
            for (String k : new String[]{"supplier_id", "company_branch_id", "po_date", "delivery_date", "department", "cost_centre", "requisitioner", "payment_term", "incoterm",
                "ship_via", "quotation_reference", "quotation_date", "currency", "terms", "special_instructions", "remarks"}) p.put(k, form.str(k));
            for (String k : new String[]{"freight_amount", "other_amount", "over_receipt_tolerance_percent"}) p.put(k, IndSvc.num(form.str(k)));
            p.put("ship_to_source_type", "BRANCH");
            p.put("ship_to_branch_id", form.str("company_branch_id"));
            if (existing != null && existing.optJSONObject("print_options") != null) p.put("print_options", existing.optJSONObject("print_options"));
            if (prefill != null) { p.put("requisition_id", IndSvc.c(prefill, "requisition_id")); p.put("requisitioner_employee_id", IndSvc.c(prefill, "requisitioner_employee_id")); }
            return p;
        }

        private void preview() {
            String problem = form.validate();
            if (problem != null) { a.toast(problem); return; }
            Api.async(() -> {
                JSONObject built = svc.previewPo(header(), grid.rows());
                return IndPdf.build(api, built.getJSONObject("header"), SupSvc.list(built.getJSONArray("items")), true);
            }, (pdf, err) -> {
                if (err != null) { a.toast(Api.message(err)); return; }
                SndPdfView.show(a, "Indirect PO preview · not saved", "Indirect_PO_PREVIEW.pdf", pdf);
            });
        }

        private void save(boolean submit, Button button) {
            if (saving) return;
            String problem = form.validate();
            if (problem != null) { a.toast(problem); return; }
            saving = true;
            button.setEnabled(false);
            Api.async(() -> {
                JSONObject p = header();
                return id == null ? svc.createPo(p, grid.rows(), submit, api.employeeId) : svc.updatePo(id, p, grid.rows(), submit, api.employeeId);
            }, (row, err) -> {
                saving = false;
                button.setEnabled(true);
                if (err != null) { a.toast(Api.message(err)); return; }
                a.toast("Indirect PO " + IndSvc.c(row, "po_number") + (submit ? " saved and submitted for approval." : " saved as Draft."));
                String rid = SupSvc.first(IndSvc.c(row, "id"), id == null ? "" : id);
                a.replaceTop(new PoView(a, rid));
            });
        }
    }

    // ================================================================== requisitions
    static final class Requisitions extends Screen {
        private List<JSONObject> rows;
        private Map<String, Boolean> perms;
        Requisitions(MainActivity a) { super(a); }
        @Override public String title() { return "Purchase Requisitions"; }
        @Override public String subtitle() { return "Indirect Purchase · approve / reject · convert to PO"; }
        @Override public int tab() { return Catalog.SUPPLY; }
        @Override public void reload() { rows = null; a.rebuild(); }

        @Override
        public View build() {
            newPage();
            Button create = Ui.primary(a, "+ New Requisition");
            create.setOnClickListener(v -> a.push(new PrEdit(a)));
            add(create, 0);
            LinearLayout box = Ui.vbox(a);
            add(box, 8);
            if (rows == null) {
                box.addView(loading());
                Api.async(() -> { IndSvc svc = new IndSvc(api); return new Object[]{svc.requisitions(), svc.perms()}; }, (r, err) -> {
                    box.removeAllViews();
                    if (err != null) { box.addView(error(err, this::reload)); return; }
                    @SuppressWarnings("unchecked") List<JSONObject> rs = (List<JSONObject>) r[0];
                    @SuppressWarnings("unchecked") Map<String, Boolean> pm = (Map<String, Boolean>) r[1];
                    rows = rs; perms = pm;
                    fill(box);
                });
            } else fill(box);
            return scroll;
        }

        private void fill(LinearLayout box) {
            if (rows.isEmpty()) { box.addView(Ui.empty(a, "No purchase requisition yet.")); return; }
            List<List<String>> data = new ArrayList<>();
            for (JSONObject r : rows) data.add(Arrays.asList(IndSvc.c(r, "pr_number"), Ui.date(IndSvc.d10(r.opt("pr_date"))), IndSvc.c(r, "department"), IndSvc.c(r, "requested_by_name"),
                Ui.date(IndSvc.d10(r.opt("required_date"))), IndSvc.c(r, "priority"), IndSvc.c(r, "purpose"), Ui.pretty(IndSvc.c(r, "status"))));
            box.addView(new DataGrid(a, "Requisition register", Arrays.asList("PR Number", "PR Date", "Department", "Requested By", "Required", "Priority", "Purpose", "Status"),
                data, 460, i -> actions(rows.get(i))));
            box.addView(Ui.text(a, "Tap a requisition to see its lines, approve / reject a submitted one or convert an approved one into an Indirect PO.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 4));
        }

        private void actions(JSONObject pr) {
            String status = IndSvc.up(pr, "status");
            List<String> items = new ArrayList<>();
            items.add("View lines");
            if ("SUBMITTED".equals(status)) { items.add("Approve requisition"); items.add("Reject requisition"); }
            if ("APPROVED".equals(status) || "PARTIALLY_ORDERED".equals(status)) items.add("Convert to Indirect PO");
            new android.app.AlertDialog.Builder(a).setTitle(IndSvc.c(pr, "pr_number")).setItems(items.toArray(new String[0]), (d, w) -> {
                String pick = items.get(w);
                String id = IndSvc.c(pr, "id");
                if (pick.startsWith("View")) {
                    Api.async(() -> new IndSvc(api).requisitionItems(id), (ls, err) -> {
                        if (err != null) { a.toast(Api.message(err)); return; }
                        StringBuilder b = new StringBuilder();
                        for (JSONObject l : ls) b.append((int) IndSvc.num(l, "line_no")).append(". ").append(IndSvc.c(l, "item_name")).append(" · ").append(Ui.num(IndSvc.num(l, "quantity"), 3))
                            .append(' ').append(IndSvc.c(l, "uom")).append(" · ordered ").append(Ui.num(IndSvc.num(l, "ordered_qty"), 3)).append('\n');
                        a.confirm(IndSvc.c(pr, "pr_number"), b.length() == 0 ? "No lines." : b.toString(), "OK", () -> { });
                    });
                } else if (pick.startsWith("Approve")) {
                    if (perms == null || !Boolean.TRUE.equals(perms.get("approve"))) { a.toast("Approval needs the Indirect Purchase Approve right."); return; }
                    a.askText("Approve " + IndSvc.c(pr, "pr_number"), "Remarks (optional)", "Approve", false, rem -> decide(id, true, rem));
                } else if (pick.startsWith("Reject")) {
                    if (perms == null || !Boolean.TRUE.equals(perms.get("approve"))) { a.toast("Rejection needs the Indirect Purchase Approve right."); return; }
                    a.askText("Reject " + IndSvc.c(pr, "pr_number"), "Rejection remarks", "Reject", true, rem -> decide(id, false, rem));
                } else a.push(new PoEdit(a, null, id));
            }).setNegativeButton("Back", null).show();
        }

        private void decide(String id, boolean approve, String remarks) {
            Api.async(() -> new IndSvc(api).decideRequisition(id, approve, remarks, api.employeeId), (r, err) -> {
                if (err != null) { a.toast(Api.message(err)); return; }
                a.toast(approve ? "Requisition approved." : "Requisition rejected.");
                reload();
            });
        }
    }

    static final class PrEdit extends Screen {
        private FormView form;
        private RowsEditor grid;
        private List<JSONObject> items;
        private boolean saving;
        PrEdit(MainActivity a) { super(a); }
        @Override public String title() { return "New Requisition"; }
        @Override public String subtitle() { return "Items from the master or free description"; }
        @Override public int tab() { return Catalog.SUPPLY; }

        @Override
        public View build() {
            newPage();
            if (items == null) {
                page.addView(loading());
                Api.async(() -> new IndSvc(api).items(true), (r, err) -> {
                    if (err != null) { page.removeAllViews(); page.addView(error(err, this::reload)); return; }
                    items = r;
                    render();
                });
                return scroll;
            }
            render();
            return scroll;
        }

        private void render() {
            page.removeAllViews();
            if (form == null) {
                List<Field> f = new ArrayList<>();
                f.add(Field.lookup("company_branch_id", "Company Branch / Plant", Lookups.branches()));
                f.add(Field.date("pr_date", "PR Date").req());
                f.add(Field.text("department", "Department").req());
                f.add(Field.text("cost_centre", "Cost Centre"));
                f.add(Field.date("required_date", "Required Date").req());
                f.add(Field.select("priority", "Priority", "NORMAL", "URGENT", "LOW").req());
                f.add(Field.text("purpose", "Purpose"));
                f.add(Field.area("remarks", "Remarks"));
                form = new FormView(a, f);
                form.set("pr_date", Ui.today());
                form.set("priority", "NORMAL");
                List<String> iIds = new ArrayList<>(), iNames = new ArrayList<>();
                iIds.add(""); iNames.add("Free description");
                for (JSONObject it : items) { iIds.add(IndSvc.c(it, "id")); iNames.add(Lookups.join(IndSvc.c(it, "item_code"), IndSvc.c(it, "item_name"), IndSvc.c(it, "uom"))); }
                grid = new RowsEditor(a, "Requisition lines", Arrays.asList(
                    Field.select("item_id", "Master item", iIds.toArray(new String[0])).labels(iNames.toArray(new String[0])), Field.text("item_name", "Item / description"),
                    Field.select("uom", "UOM", IndSvc.UOMS), Field.number("quantity", "Quantity").range(0, Double.MAX_VALUE).req(),
                    Field.number("estimated_rate", "Estimated Rate").range(0, Double.MAX_VALUE), Field.date("required_date", "Required Date"), Field.text("remarks", "Remarks")),
                    Arrays.asList(new String[]{"item_name", "Item"}, new String[]{"uom", "UOM"}, new String[]{"quantity", "Qty"}, new String[]{"estimated_rate", "Est. Rate"}, new String[]{"required_date", "Required"}));
                try { grid.template(new JSONObject().put("uom", "NOS").put("quantity", "1")); } catch (Exception ignored) { }
                grid.setRows(new ArrayList<>());
            } else { PoEdit.detach(form); PoEdit.detach(grid); }
            LinearLayout card = Ui.card(a);
            card.addView(form);
            add(card, 0);
            add(Ui.label(a, "Lines · + to add"), 12);
            add(grid, 4);
            Button save = Ui.primary(a, "Submit Requisition");
            save.setOnClickListener(v -> {
                if (saving) return;
                String problem = form.validate();
                if (problem != null) { a.toast(problem); return; }
                saving = true;
                save.setEnabled(false);
                Api.async(() -> {
                    JSONObject h = new JSONObject();
                    for (String k : new String[]{"company_branch_id", "pr_date", "department", "cost_centre", "required_date", "priority", "purpose", "remarks"}) h.put(k, form.str(k));
                    h.put("requested_by_employee_id", api.employeeId == null ? "" : api.employeeId);
                    h.put("requested_by_name", api.fullName == null ? "" : api.fullName);
                    return new IndSvc(api).createRequisition(h, grid.rows());
                }, (r, err) -> {
                    saving = false;
                    save.setEnabled(true);
                    if (err != null) { a.toast(Api.message(err)); return; }
                    a.toast("Requisition " + IndSvc.c(r, "pr_number") + " submitted.");
                    a.back();
                });
            });
            add(save, 14);
        }
    }

    /** Indirect GRN register action: controlled GRN print. */
    static void grnPdf(MainActivity a, JSONObject row, Runnable refresh) {
        Api api = Api.get(a);
        String id = IndSvc.c(row, "id");
        Api.async(() -> { IndSvc svc = new IndSvc(api); return new Object[]{svc.grn(id), IndPdf.grnById(api, svc, id)}; }, (r, err) -> {
            if (err != null || r == null) { a.toast("Indirect GRN PDF could not be generated: " + Api.message(err)); return; }
            ExportKit.layoutActions(a, IndPdf.GRN_TITLE + " " + IndSvc.c((JSONObject) r[0], "grn_number"), IndPdf.grnFileName((JSONObject) r[0]).replace(".pdf", ""), (byte[]) r[1]);
        });
    }

    /** GRN without PO approval (self-approval blocked by qcms_decide_indirect_grn). */
    static void grnDecide(MainActivity a, JSONObject row, Runnable refresh, boolean approve) {
        Api api = Api.get(a);
        a.askText((approve ? "Approve " : "Reject ") + IndSvc.c(row, "grn_number"), approve ? "Remarks (optional)" : "Rejection remarks", approve ? "Approve" : "Reject", !approve, rem ->
            Api.async(() -> new IndSvc(api).decideGrn(IndSvc.c(row, "id"), approve, rem), (r, err) -> {
                if (err != null) { a.toast(Api.message(err)); return; }
                a.toast(approve ? "GRN approved and stock posted." : "GRN rejected.");
                refresh.run();
            }));
    }
}
