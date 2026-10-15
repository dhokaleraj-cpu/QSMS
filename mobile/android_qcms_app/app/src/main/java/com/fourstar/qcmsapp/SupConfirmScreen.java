package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Supplier PO Confirmation (_render_supplier_confirmation_stage): attachment SUPPLIER_PO_CONFIRMATION
 * (entity PO_CONFIRMATION, folder supply-po-confirmation) then rpc qcms_confirm_purchase_order.
 */
final class SupConfirmScreen extends SupBase {
    private final String poId;
    private JSONObject header, confirmation;
    private Attachments.FileData file;

    SupConfirmScreen(MainActivity a, String poId) { super(a); this.poId = poId; }

    @Override public String title() { return "Supplier PO Confirmation"; }
    @Override public String subtitle() { return header == null ? "" : SupSvc.s(header, "po_number"); }

    /** Action helpers used by the catalogue. */
    static void reminder(MainActivity a, JSONObject conf, Runnable refresh) {
        a.confirm("Reminder sent to supplier?", "Records the reminder on this confirmation (count +1). E-mail reminders are sent from the QCMS website.", "Record reminder", () -> {
            Api api = Api.get(a);
            Api.async(() -> {
                JSONObject fresh = new SupSvc(api).get("supply_po_confirmations", SupSvc.s(conf, "id"));
                return api.update("supply_po_confirmations", SupSvc.s(conf, "id"), new JSONObject().put("last_reminder_at", SupSvc.nowUtc())
                    .put("reminder_count", (int) SupSvc.num(fresh, "reminder_count") + 1));
            }, (r, err) -> { a.toast(err != null ? Api.message(err) : "Supplier Confirmation reminder recorded."); if (err == null) refresh.run(); });
        });
    }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            JSONObject h = svc.get("supply_purchase_orders", poId);
            if (SupSvc.empty(h)) throw new Api.ApiException(404, "Purchase Order not found.");
            if (!"APPROVED".equalsIgnoreCase(SupSvc.s(h, "approval_status")))
                throw new SupSvc.Rule("Supplier Confirmation is waiting for Purchase Order approval.");
            if ("CANCELLED".equalsIgnoreCase(SupSvc.s(h, "status"))) throw new SupSvc.Rule("Cancelled Purchase Orders do not require Supplier Confirmation.");
            List<JSONObject> rows = svc.live("supply_po_confirmations?select=*&purchase_order_id=eq." + poId + "&order=created_at.desc&limit=1");
            if (rows.isEmpty()) {
                api.rpc("qcms_ensure_po_confirmation", new JSONObject().put("p_purchase_order_id", poId));
                rows = svc.live("supply_po_confirmations?select=*&purchase_order_id=eq." + poId + "&order=created_at.desc&limit=1");
            }
            if (rows.isEmpty()) throw new SupSvc.Rule("Supplier Confirmation record could not be initialized.");
            return new JSONObject[]{h, rows.get(0)};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            header = res[0]; confirmation = res[1];
            a.rebuildTitle(this);
            render();
        });
        return scroll;
    }

    private void render() {
        String status = SupSvc.first(SupSvc.up(confirmation, "confirmation_status"), "PENDING");
        add(infoCard(SupSvc.s(header, "po_number") + " · " + Ui.pretty(status), "Priority: HIGH · Reminder Count: " + (int) SupSvc.num(confirmation, "reminder_count"),
            "Requested: " + Ui.date(SupSvc.s(confirmation, "requested_at"))), 0);
        if ("CONFIRMED".equals(status)) {
            add(note("Supplier confirmed this PO · Reference: " + SupSvc.first(SupSvc.s(confirmation, "confirmation_reference"), "-") + " · Confirmed delivery: "
                + Ui.date(SupSvc.s(confirmation, "confirmed_delivery_date")), "green"), 8);
            return;
        }
        List<Field> f = new ArrayList<>();
        f.add(Field.text("confirmation_reference", "Supplier Confirmation Reference").req().def(SupSvc.s(confirmation, "confirmation_reference")));
        f.add(Field.date("confirmation_date", "Supplier Confirmation Date").req().def(Ui.today()));
        f.add(Field.date("confirmed_delivery_date", "Supplier Confirmed Delivery Date").def(SupSvc.first(SupSvc.d10(SupSvc.s(header, "delivery_date")), Ui.today())));
        f.add(Field.area("remarks", "Supplier Confirmation Remarks").def(SupSvc.s(confirmation, "remarks")));
        FormView form = new FormView(a, f);
        add(form, 8);
        TextView fileBox = pickBox("Attach Supplier PO Confirmation (photo / PDF) *");
        fileBox.setOnClickListener(v -> a.pickFile("Supplier PO Confirmation", false, fd -> { file = fd; fileBox.setText(fd.name + " · " + (fd.data.length / 1024) + " KB"); }));
        add(fileBox, 10);
        Button save = Ui.primary(a, "Save Supplier Confirmation");
        add(save, 16);
        Button remind = Ui.outline(a, "Reminder sent", Ui.TEAL);
        add(remind, 8);
        remind.setOnClickListener(v -> reminder(a, confirmation, a::rebuild));
        save.setOnClickListener(v -> {
            String problem = form.validate();
            if (problem == null && file == null) problem = "Attach the supplier PO confirmation first.";
            if (problem != null) { a.toast(problem); return; }
            busy(save, "Saving…", () -> {
                Attachments.uploadSlot(api, "PO_CONFIRMATION", SupSvc.s(confirmation, "id"), "supply-po-confirmation", "SUPPLIER_PO_CONFIRMATION", file, null, null);
                return api.rpc("qcms_confirm_purchase_order", new JSONObject().put("p_purchase_order_id", poId)
                    .put("p_confirmation_reference", form.str("confirmation_reference")).put("p_confirmation_date", SupSvc.n(form.str("confirmation_date")))
                    .put("p_confirmed_delivery_date", SupSvc.n(form.str("confirmed_delivery_date"))).put("p_remarks", SupSvc.n(form.str("remarks"))));
            }, (ok, err) -> { a.toast("Supplier PO Confirmation saved."); a.back(); });
        });
    }

    @Override public boolean onBack() { return false; }
}
