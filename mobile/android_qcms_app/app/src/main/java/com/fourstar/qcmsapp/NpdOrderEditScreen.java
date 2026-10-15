package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/**
 * NPD Order entry (npd_apqp.py render_npd_status → Order Entry). A new order copies the part's saved
 * process flow into npd_order_steps (target dates spread evenly between start and delivery) and the
 * ACTIVE flow checkpoints into npd_order_step_points.
 */
public final class NpdOrderEditScreen extends Screen {
    private final String id;
    private final JSONObject prefill;
    private JSONObject existing;
    private FormView form;
    private Button save;
    private final Field.Lookup parts = Lookups.parts();
    private final Field.Lookup customers = NpdUtil.customers();

    public NpdOrderEditScreen(MainActivity a, String id, JSONObject prefill) { super(a); this.id = id; this.prefill = prefill; }

    @Override public String title() { return (id == null ? "New · " : "Edit · ") + "NPD Order"; }
    @Override public String subtitle() { return "Fields marked * are required"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            Lookups.rows(api, parts);
            Lookups.rows(api, customers);
            if (id == null) return null;
            JSONArray r = api.rows("npd_orders?select=*&id=eq." + Api.enc(id));
            if (r.length() == 0) throw new Api.ApiException(404, "NPD Order not found.");
            return r.getJSONObject(0);
        }, (row, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            existing = row;
            render();
        });
        return scroll;
    }

    private void render() {
        offlineNote();
        Field partField = Field.lookup("part_id", "Part Number", parts).req();
        if (existing != null) partField.ro();
        List<Field> fields = new ArrayList<>(Arrays.asList(
            Field.text("order_number", "Customer / Internal Order Number").req(),
            partField,
            Field.lookup("customer_id", "Customer", customers).req(),
            Field.number("order_qty", "Order Qty (pcs)").req().range(1, 1e12).def("1"),
            Field.date("order_date", "Order Date").req().def(Ui.today()),
            Field.date("start_date", "NPD Start Date").req().def(Ui.today()),
            Field.date("delivery_date", "Customer Delivery Date").req().def(LocalDate.now().plusDays(30).toString()),
            Field.info("_status", "Order Status"),
            Field.area("remarks", "Order / Development Remarks")));
        form = new FormView(a, fields);
        LinearLayout card = Ui.card(a);
        card.addView(form);
        if (existing == null) card.addView(Ui.text(a, "Saving creates the process status cards and checkpoints from the part's saved Process Flow.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 8));
        add(card, 4);
        if (existing != null) {
            form.setAll(existing);
            form.set("_status", Ui.pretty(NpdUtil.s(existing, "status").isEmpty() ? "OPEN" : NpdUtil.s(existing, "status")));
        } else {
            form.set("_status", "Open");
            if (prefill != null) form.setAll(prefill);
            form.onChange((key, value) -> {
                if (!"part_id".equals(key) || value == null) return;
                JSONObject p = Lookups.rowOf(parts, String.valueOf(value));
                String cust = p == null ? "" : NpdUtil.s(p, "customer_id");
                if (!cust.isEmpty() && Lookups.rowOf(customers, cust) != null) form.set("customer_id", cust);
            });
        }
        save = Ui.primary(a, "Save NPD Order");
        save.setOnClickListener(v -> save());
        add(save, 14);
    }

    /** _suggested_target_dates(): start + round((i+1) × days / n); one step → the delivery date. */
    static List<LocalDate> targetDates(LocalDate start, LocalDate delivery, int count) {
        List<LocalDate> out = new ArrayList<>();
        if (count <= 0) return out;
        long total = Math.max(0, ChronoUnit.DAYS.between(start, delivery));
        if (count == 1) { out.add(delivery); return out; }
        for (int i = 0; i < count; i++) out.add(start.plusDays((long) Math.rint((i + 1) * (double) total / count)));
        return out;
    }

    private void save() {
        String problem = form.validate();
        if (problem != null) { a.toast(problem); return; }
        String number = form.str("order_number").trim();
        LocalDate start = LocalDate.parse(form.str("start_date").substring(0, 10));
        LocalDate delivery = LocalDate.parse(form.str("delivery_date").substring(0, 10));
        if (delivery.isBefore(start)) { a.toast("Customer Delivery Date cannot be before the NPD Start Date."); return; }
        save.setEnabled(false);
        save.setText("Saving…");
        Api.async(() -> {
            // case-insensitive duplicate order-number protection on create and edit
            for (JSONObject o : NpdUtil.list(api.rows("npd_orders?select=id,order_number&limit=10000"))) {
                if (existing != null && o.optString("id").equals(existing.optString("id"))) continue;
                if (NpdUtil.s(o, "order_number").trim().toLowerCase(Locale.ROOT).equals(number.toLowerCase(Locale.ROOT))) {
                    throw new Exception("Duplicate NPD Order Number is not allowed.");
                }
            }
            String partId = existing != null ? NpdUtil.s(existing, "part_id") : form.str("part_id");
            JSONArray flows = api.rows("npd_process_flows?select=id&part_id=eq." + Api.enc(partId) + "&limit=1");
            List<JSONObject> flowSteps = flows.length() == 0 ? new ArrayList<>()
                : NpdUtil.list(api.rows("npd_process_flow_steps?select=*&flow_id=eq." + flows.getJSONObject(0).optString("id") + "&order=operation_no.asc&limit=500"));
            if (flowSteps.isEmpty() && existing == null) throw new Exception("Create and save the Part Process Flow before creating this NPD Order.");
            JSONObject payload = new JSONObject();
            payload.put("order_number", number);
            payload.put("part_id", partId);
            payload.put("customer_id", form.str("customer_id"));
            payload.put("order_qty", form.num("order_qty"));
            payload.put("order_date", form.str("order_date").substring(0, 10));
            payload.put("start_date", start.toString());
            payload.put("delivery_date", delivery.toString());
            payload.put("remarks", NpdUtil.orNull(form.str("remarks")));
            if (existing != null) return api.update("npd_orders", existing.optString("id"), payload);
            payload.put("status", "OPEN");
            JSONObject saved = api.insert("npd_orders", payload);
            List<LocalDate> dates = targetDates(start, delivery, flowSteps.size());
            int done = 0;
            try {
                for (int i = 0; i < flowSteps.size(); i++) {
                    JSONObject st = flowSteps.get(i);
                    JSONObject os = new JSONObject();
                    os.put("npd_order_id", saved.optString("id"));
                    os.put("flow_step_id", st.optString("id"));
                    os.put("operation_no", NpdUtil.intOf(st.opt("operation_no"), 0));
                    os.put("process_id", st.isNull("process_id") ? JSONObject.NULL : st.opt("process_id"));
                    os.put("process_name", NpdUtil.s(st, "process_name_snapshot"));
                    os.put("target_date", dates.get(i).toString());
                    os.put("status", "PENDING");
                    os.put("completed_date", JSONObject.NULL);
                    os.put("responsible_employee_id", st.isNull("responsible_employee_id") ? JSONObject.NULL : st.opt("responsible_employee_id"));
                    os.put("responsible", st.isNull("responsible") ? JSONObject.NULL : st.opt("responsible"));
                    os.put("remarks", JSONObject.NULL);
                    JSONObject orderStep = api.insert("npd_order_steps", os);
                    JSONArray points = api.rows("npd_process_flow_points?select=*&flow_step_id=eq." + st.optString("id") + "&status=eq.ACTIVE&order=sequence_no.asc&limit=300");
                    for (JSONObject p : NpdUtil.list(points)) {
                        JSONObject op = new JSONObject();
                        op.put("npd_order_step_id", orderStep.optString("id"));
                        op.put("flow_point_id", p.optString("id"));
                        op.put("sequence_no", p.isNull("sequence_no") ? 10 : NpdUtil.intOf(p.opt("sequence_no"), 10));
                        op.put("point_text", p.isNull("point_text") ? JSONObject.NULL : p.opt("point_text"));
                        op.put("responsible_employee_id", p.isNull("responsible_employee_id") ? JSONObject.NULL : p.opt("responsible_employee_id"));
                        op.put("responsible_snapshot", p.isNull("responsible_snapshot") ? JSONObject.NULL : p.opt("responsible_snapshot"));
                        op.put("target_date", dates.get(i).toString());
                        op.put("status", "PENDING");
                        op.put("completed_date", JSONObject.NULL);
                        op.put("remarks", p.isNull("remarks") ? JSONObject.NULL : p.opt("remarks"));
                        api.insert("npd_order_step_points", op);
                    }
                    done++;
                }
            } catch (Exception e) {
                throw new Exception("NPD Order " + number + " was saved, but creating the process status cards stopped after " + done + " of "
                    + flowSteps.size() + " process(es): " + Api.message(e) + ". Delete the order and create it again, or complete it on the website.");
            }
            return saved;
        }, (saved, err) -> {
            save.setEnabled(true);
            save.setText("Save NPD Order");
            if (err != null) { a.toast(Api.message(err)); return; }
            if (existing != null) { a.toast("NPD Order saved."); a.back(); return; }
            a.toast("NPD Order saved and process/checkpoint status cards created from the Part Process Flow.");
            Module m = Catalog.get("npd_orders");
            if (m != null) a.replaceTop(new RecordScreen(a, m, saved.optString("id")));
            else a.back();
        });
    }

    @Override public boolean onBack() {
        a.confirm("Leave without saving?", "Changes on this form are not saved.", "Leave", () -> a.back());
        return true;
    }
}
