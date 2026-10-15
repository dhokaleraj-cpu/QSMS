package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.graphics.Color;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * NPD Order Status (npd_apqp.py render_npd_status → Order Status): KPIs, colour-coded process cards with the
 * date-driven state, tap a process to update target / status / completed date / responsible / remarks, and the
 * checkpoints of every process. Step updates roll the order status up exactly like _sync_order_overall_status.
 */
public final class NpdOrderProgressScreen extends Screen {
    static final String[] STEP_STATUSES = {"PENDING", "IN_PROGRESS", "ON_HOLD", "COMPLETED"};
    static final String[] POINT_STATUSES = {"PENDING", "IN_PROGRESS", "ON_HOLD", "COMPLETED", "NOT_APPLICABLE"};

    private final String orderId;
    private final Field.Lookup employees = NpdUtil.employees();
    private JSONObject order;

    public NpdOrderProgressScreen(MainActivity a, String orderId) { super(a); this.orderId = orderId; }

    @Override public String title() { return order == null ? "NPD Order Status" : "Status · " + NpdUtil.s(order, "order_number"); }
    @Override public String subtitle() { return "Tap a process or checkpoint to update it"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        Api.async(() -> {
            Lookups.rows(api, employees);
            JSONArray o = api.rows("npd_orders?select=*&id=eq." + Api.enc(orderId));
            if (o.length() == 0) throw new Api.ApiException(404, "NPD Order not found.");
            JSONObject ord = o.getJSONObject(0);
            JSONArray steps = api.rows("npd_order_steps?select=*&npd_order_id=eq." + Api.enc(orderId) + "&order=operation_no.asc&limit=500");
            List<String> ids = new ArrayList<>();
            for (JSONObject s : NpdUtil.list(steps)) ids.add(s.optString("id"));
            JSONArray points = ids.isEmpty() ? new JSONArray()
                : api.rows("npd_order_step_points?select=*&npd_order_step_id=in.(" + String.join(",", ids) + ")&order=sequence_no.asc&limit=5000");
            JSONArray part = api.rows("parts?select=id,part_number,fsi_part_number,part_name&id=eq." + NpdUtil.s(ord, "part_id"));
            JSONArray cust = api.rows("parties?select=id,party_code,party_name&id=eq." + NpdUtil.s(ord, "customer_id"));
            return new Object[]{ord, steps, points, part.length() > 0 ? part.getJSONObject(0) : new JSONObject(), cust.length() > 0 ? cust.getJSONObject(0) : new JSONObject()};
        }, (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, this::reload)); return; }
            order = (JSONObject) res[0];
            a.rebuildTitle(this);
            render(NpdUtil.list((JSONArray) res[1]), NpdUtil.list((JSONArray) res[2]), (JSONObject) res[3], (JSONObject) res[4]);
        });
        return scroll;
    }

    /** _step_realtime_state(): state key + detail text. */
    static String[] state(JSONObject step, LocalDate today) {
        String status = NpdUtil.s(step, "status").isEmpty() ? "PENDING" : NpdUtil.s(step, "status").toUpperCase();
        LocalDate target = NpdUtil.date(step.opt("target_date"));
        LocalDate completed = NpdUtil.date(step.opt("completed_date"));
        if ("COMPLETED".equals(status)) {
            if (target != null && completed != null && completed.isAfter(target)) {
                return new String[]{"completed_late", "Completed " + Ui.date(completed.toString()) + " · " + ChronoUnit.DAYS.between(target, completed) + " day(s) late"};
            }
            return new String[]{"completed", ("Completed " + (completed != null ? Ui.date(completed.toString()) : "")).trim()};
        }
        if ("ON_HOLD".equals(status)) return new String[]{"hold", "Target " + (target != null ? Ui.date(target.toString()) : "not set")};
        if (target != null && target.isBefore(today)) {
            return new String[]{"overdue", "Target " + Ui.date(target.toString()) + " · " + ChronoUnit.DAYS.between(target, today) + " day(s) overdue"};
        }
        if ("IN_PROGRESS".equals(status)) {
            if (target != null) return new String[]{"in_progress", "Target " + Ui.date(target.toString()) + " · " + ChronoUnit.DAYS.between(today, target) + " day(s) remaining"};
            return new String[]{"in_progress", "Target date not set"};
        }
        if (target != null) return new String[]{"pending", "Target " + Ui.date(target.toString()) + " · " + ChronoUnit.DAYS.between(today, target) + " day(s) remaining"};
        return new String[]{"not_planned", "Target date not set"};
    }

    private static String[] legend(String state) {
        switch (state) {
            case "completed": return new String[]{"Completed", "✓", "green"};
            case "completed_late": return new String[]{"Completed Late", "✓", "amber"};
            case "in_progress": return new String[]{"In Process", "●", "teal"};
            case "overdue": return new String[]{"Overdue", "!", "red"};
            case "hold": return new String[]{"On Hold", "Ⅱ", "amber"};
            case "not_planned": return new String[]{"Not Planned", "○", "grey"};
            default: return new String[]{"Pending", "○", "grey"};
        }
    }

    private static boolean closed(JSONObject p) {
        String s = NpdUtil.s(p, "status");
        return "COMPLETED".equals(s) || "NOT_APPLICABLE".equals(s);
    }

    private void render(List<JSONObject> steps, List<JSONObject> points, JSONObject part, JSONObject customer) {
        offlineNote();
        LocalDate today = LocalDate.now();
        Map<String, List<JSONObject>> byStep = new HashMap<>();
        for (JSONObject p : points) {
            String k = NpdUtil.s(p, "npd_order_step_id");
            if (!byStep.containsKey(k)) byStep.put(k, new ArrayList<>());
            byStep.get(k).add(p);
        }
        int overdue = 0, completed = 0, closedPoints = 0;
        for (JSONObject s : steps) {
            if ("overdue".equals(state(s, today)[0])) overdue++;
            if ("COMPLETED".equals(NpdUtil.s(s, "status"))) completed++;
        }
        for (JSONObject p : points) if (closed(p)) closedPoints++;
        LocalDate due = NpdUtil.date(order.opt("delivery_date"));
        if (due == null) due = today;
        long days = ChronoUnit.DAYS.between(today, due);
        String overall = !steps.isEmpty() && completed == steps.size() ? "COMPLETED" : (overdue > 0 ? "DELAYED" : "ON TRACK");

        LinearLayout head = Ui.card(a);
        LinearLayout top = Ui.hbox(a);
        top.addView(Ui.text(a, NpdUtil.s(order, "order_number"), 17, Ui.TEXT, true), Ui.weight(1));
        String st = NpdUtil.s(order, "status").isEmpty() ? "OPEN" : NpdUtil.s(order, "status");
        top.addView(Ui.chip(a, Ui.pretty(st), Ui.tone(st)));
        head.addView(top);
        head.addView(Ui.text(a, NpdUtil.join(NpdUtil.s(part, "part_number"), NpdUtil.s(part, "part_name")) + "\n"
            + NpdUtil.join(NpdUtil.s(customer, "party_code"), NpdUtil.s(customer, "party_name")), 12, Ui.MUTED, false));
        head.addView(Ui.pair(a, "Order Qty", Ui.num(order.optDouble("order_qty", 0), 0) + " pcs"));
        head.addView(Ui.pair(a, "Processes Complete", completed + "/" + steps.size()));
        head.addView(Ui.pair(a, "Checkpoints Complete", closedPoints + "/" + points.size()));
        head.addView(Ui.pair(a, "Overdue Processes", String.valueOf(overdue)));
        head.addView(Ui.pair(a, "Days to Delivery", days + " (" + Ui.date(due.toString()) + ")"));
        LinearLayout rt = Ui.hbox(a);
        rt.addView(Ui.text(a, "Real-time Status", 12, Ui.MUTED, false), Ui.weight(1));
        rt.addView(Ui.chip(a, overall, "DELAYED".equals(overall) ? "red" : "green"));
        head.addView(rt, Ui.matchWrap(a, 4));
        add(head, 2);

        add(Ui.label(a, "Order process status"), 12);
        if (steps.isEmpty()) { add(Ui.empty(a, "No process sequence is available for this order."), 2); return; }
        for (JSONObject s : steps) {
            String[] stt = state(s, today);
            String[] lg = legend(stt[0]);
            List<JSONObject> pts = byStep.containsKey(s.optString("id")) ? byStep.get(s.optString("id")) : new ArrayList<>();
            int done = 0;
            for (JSONObject p : pts) if (closed(p)) done++;
            LinearLayout card = Ui.card(a);
            int stripe = "red".equals(lg[2]) ? Ui.RED_FG : "green".equals(lg[2]) ? Ui.GREEN_FG : "amber".equals(lg[2]) ? Ui.AMBER_FG : "teal".equals(lg[2]) ? Ui.TEAL : Ui.LINE_STRONG;
            card.setBackground(Ui.round(Color.WHITE, stripe, 2, 14, a));
            LinearLayout line = Ui.hbox(a);
            line.addView(Ui.text(a, "OP " + NpdUtil.s(s, "operation_no") + " · " + (NpdUtil.s(s, "process_name").isEmpty() ? "Process" : NpdUtil.s(s, "process_name")), 14.5f, Ui.TEXT, true), Ui.weight(1));
            line.addView(Ui.chip(a, lg[1] + " " + lg[0], lg[2]));
            card.addView(line);
            card.addView(Ui.text(a, Ui.pretty(NpdUtil.s(s, "status").isEmpty() ? "PENDING" : NpdUtil.s(s, "status")) + " · " + stt[1]
                + (pts.isEmpty() ? "" : " · Points " + done + "/" + pts.size()), 12, Ui.MUTED, false));
            String resp = NpdUtil.s(s, "responsible");
            if (!resp.isEmpty()) card.addView(Ui.text(a, "Responsible: " + resp, 11.5f, Ui.MUTED, false));
            if (!NpdUtil.s(s, "remarks").isEmpty()) card.addView(Ui.text(a, "Remarks: " + NpdUtil.s(s, "remarks"), 11.5f, Ui.TEXT, false));
            TextView upd = Ui.text(a, "Update process ›", 13, Ui.TEAL_DARK, true);
            upd.setPadding(0, dp(8), 0, dp(4));
            upd.setOnClickListener(v -> editStep(s));
            card.addView(upd);
            if (!pts.isEmpty()) {
                card.addView(Ui.divider(a), Ui.matchWrap(a, 4));
                card.addView(Ui.text(a, "Checkpoints " + done + "/" + pts.size(), 11, Ui.MUTED, true), Ui.matchWrap(a, 4));
                for (JSONObject p : pts) {
                    LinearLayout pl = Ui.hbox(a);
                    pl.setPadding(0, dp(6), 0, dp(6));
                    LinearLayout pt = Ui.vbox(a);
                    pt.addView(Ui.text(a, NpdUtil.s(p, "sequence_no") + ". " + NpdUtil.s(p, "point_text"), 12.5f, Ui.TEXT, false));
                    String sub = NpdUtil.join(NpdUtil.s(p, "target_date").isEmpty() ? "" : "Target " + Ui.date(NpdUtil.s(p, "target_date")),
                        NpdUtil.s(p, "completed_date").isEmpty() ? "" : "Done " + Ui.date(NpdUtil.s(p, "completed_date")), NpdUtil.s(p, "responsible_snapshot"), NpdUtil.s(p, "remarks"));
                    if (!sub.isEmpty()) pt.addView(Ui.text(a, sub, 11, Ui.MUTED, false));
                    pl.addView(pt, Ui.weight(1));
                    String ps = NpdUtil.s(p, "status").isEmpty() ? "PENDING" : NpdUtil.s(p, "status");
                    pl.addView(Ui.chip(a, Ui.pretty(ps), "NOT_APPLICABLE".equals(ps) ? "grey" : Ui.tone(ps)));
                    Ui.clickable(pl, Color.WHITE, 0, 8);
                    pl.setOnClickListener(v -> editPoint(p, s));
                    card.addView(pl);
                }
            }
            add(card, 8);
        }
    }

    // ------------------------------------------------------------------ dialogs
    interface Saver { void save(JSONObject values, AlertDialog dialog) throws Exception; }

    private void dialog(String title, List<Field> fields, JSONObject row, Saver saver) {
        FormView form = new FormView(a, fields);
        form.setAll(row);
        ScrollView sv = new ScrollView(a);
        LinearLayout pad = Ui.vbox(a);
        pad.setPadding(dp(18), dp(4), dp(18), dp(8));
        pad.addView(form);
        sv.addView(pad);
        AlertDialog d = new AlertDialog.Builder(a).setTitle(title).setView(sv).setPositiveButton("Save", null).setNegativeButton("Back", null).create();
        d.setOnShowListener(x -> d.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            String problem = form.validate();
            if (problem != null) { a.toast(problem); return; }
            try { saver.save(form.json(), d); } catch (Exception e) { a.toast(Api.message(e)); }
        }));
        d.show();
    }

    /** Website rule: COMPLETED without a date = today; any other status clears the completed date. */
    private static Object completedDate(String status, Object entered) {
        if (!"COMPLETED".equals(status)) return JSONObject.NULL;
        String s = NpdUtil.clean(entered);
        return s.isEmpty() ? LocalDate.now().toString() : s.substring(0, 10);
    }

    private Object legacy(JSONObject row, String snapshotKey) {
        return NpdUtil.s(row, "responsible_employee_id").isEmpty() ? row.opt(snapshotKey) : null;
    }

    private void editStep(JSONObject step) {
        List<Field> fields = Arrays.asList(
            Field.date("target_date", "Target Date").req(),
            Field.select("status", "Status", STEP_STATUSES).req(),
            Field.date("completed_date", "Completed Date").hint("Filled with today when Completed is saved without a date"),
            Field.lookup("responsible_employee_id", "Responsible Employee", employees),
            Field.area("remarks", "Remarks shown on the card"));
        JSONObject row = NpdUtil.copy(step);
        try { if (NpdUtil.s(row, "status").isEmpty()) row.put("status", "PENDING"); } catch (Exception ignored) { }
        final Object legacyText = legacy(step, "responsible");
        dialog("Update OP " + NpdUtil.s(step, "operation_no") + " · " + NpdUtil.s(step, "process_name"), fields, row, (v, d) -> {
            String status = v.optString("status", "PENDING");
            String emp = NpdUtil.clean(v.opt("responsible_employee_id"));
            JSONObject payload = new JSONObject();
            payload.put("target_date", NpdUtil.clean(v.opt("target_date")).substring(0, 10));
            payload.put("status", status);
            payload.put("completed_date", completedDate(status, v.opt("completed_date")));
            payload.put("responsible_employee_id", emp.isEmpty() ? JSONObject.NULL : emp);
            payload.put("responsible", NpdUtil.snapshot(employees, emp, legacyText));
            payload.put("remarks", NpdUtil.orNull(NpdUtil.clean(v.opt("remarks"))));
            Api.async(() -> {
                api.update("npd_order_steps", step.optString("id"), payload);
                syncOrderStatus();
                return true;
            }, (ok, err) -> {
                if (err != null) { a.toast(Api.message(err)); return; }
                d.dismiss();
                a.toast("NPD process card updated.");
                a.rebuild();
            });
        });
    }

    /** _sync_order_overall_status(). */
    private void syncOrderStatus() throws Exception {
        List<JSONObject> refreshed = NpdUtil.list(api.rows("npd_order_steps?select=id,status&npd_order_id=eq." + Api.enc(orderId) + "&order=operation_no.asc&limit=500"));
        boolean all = !refreshed.isEmpty(), hold = false, progress = false;
        for (JSONObject s : refreshed) {
            String v = NpdUtil.s(s, "status").isEmpty() ? "PENDING" : NpdUtil.s(s, "status").toUpperCase();
            if (!"COMPLETED".equals(v)) all = false;
            if ("ON_HOLD".equals(v)) hold = true;
            if ("IN_PROGRESS".equals(v) || "COMPLETED".equals(v)) progress = true;
        }
        String status = all ? "COMPLETED" : hold ? "ON_HOLD" : progress ? "IN_PROGRESS" : "OPEN";
        if (!status.equals(NpdUtil.s(order, "status"))) api.update("npd_orders", orderId, new JSONObject().put("status", status));
    }

    private void editPoint(JSONObject point, JSONObject step) {
        List<Field> fields = Arrays.asList(
            Field.info("point_text", "Checkpoint / Bullet Point"),
            Field.date("target_date", "Target Date"),
            Field.select("status", "Status", POINT_STATUSES).req(),
            Field.date("completed_date", "Completed Date").hint("Filled with today when Completed is saved without a date"),
            Field.lookup("responsible_employee_id", "Responsible Employee", employees),
            Field.area("remarks", "Remarks"));
        JSONObject row = NpdUtil.copy(point);
        try { if (NpdUtil.s(row, "status").isEmpty()) row.put("status", "PENDING"); } catch (Exception ignored) { }
        final Object legacyText = legacy(point, "responsible_snapshot");
        dialog("OP " + NpdUtil.s(step, "operation_no") + " · checkpoint " + NpdUtil.s(point, "sequence_no"), fields, row, (v, d) -> {
            String status = v.optString("status", "PENDING");
            String emp = NpdUtil.clean(v.opt("responsible_employee_id"));
            String target = NpdUtil.clean(v.opt("target_date"));
            JSONObject payload = new JSONObject();
            payload.put("target_date", target.isEmpty() ? JSONObject.NULL : target.substring(0, 10));
            payload.put("status", status);
            payload.put("completed_date", completedDate(status, v.opt("completed_date")));
            payload.put("responsible_employee_id", emp.isEmpty() ? JSONObject.NULL : emp);
            payload.put("responsible_snapshot", NpdUtil.snapshot(employees, emp, legacyText));
            payload.put("remarks", NpdUtil.orNull(NpdUtil.clean(v.opt("remarks"))));
            Api.async(() -> api.update("npd_order_step_points", point.optString("id"), payload), (ok, err) -> {
                if (err != null) { a.toast(Api.message(err)); return; }
                d.dismiss();
                a.toast("Checkpoint status updated for OP " + NpdUtil.s(step, "operation_no") + ".");
                a.rebuild();
            });
        });
    }
}
