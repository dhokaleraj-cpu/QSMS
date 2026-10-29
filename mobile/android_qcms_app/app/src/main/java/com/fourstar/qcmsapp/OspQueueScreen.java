package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * R39 · OSP inspection queues (web osp_inspections section A, R37 fixes): Sample / Receipt × Dimensional / MetLAB.
 * "Pending / New" = jobs_for_inspection (batches whose stage gate is already decided leave the list);
 * "Released without report" = gate decided but no report of the stage (e.g. a draft deleted after release) - opened
 * only to record the missing report. A row opens the OSP Dimensional / MetLAB report (InspOsp.openInspection).
 */
final class OspQueueScreen extends Screen {
    private static String scope = "OSP_SAMPLE", type = "DIMENSIONAL";
    private List<JSONObject> pending, released;

    OspQueueScreen(MainActivity a) { super(a); }

    @Override public String title() { return "OSP Inspection Queues"; }
    @Override public String subtitle() { return ("OSP_SAMPLE".equals(scope) ? "Pre-inward Sample" : "Post-receipt Full Batch") + " · " + Ui.pretty(type); }
    @Override public int tab() { return Catalog.QUALITY; }

    @Override public void reload() { pending = null; released = null; a.rebuild(); }

    @Override
    public View build() {
        newPage();
        add(toggle(new String[]{"OSP_SAMPLE", "OSP_RECEIPT"}, new String[]{"Pre-inward Sample", "Post-receipt Batch"}, scope, v -> { scope = v; reload(); }), 0);
        add(toggle(new String[]{"DIMENSIONAL", "METLAB"}, new String[]{"Dimensional", "MetLAB"}, type, v -> { type = v; reload(); }), 6);
        LinearLayout box = Ui.vbox(a);
        add(box, 8);
        if (pending != null) { render(box); return scroll; }
        box.addView(loading());
        String sc = scope, ty = type;
        Api.async(() -> {
            List<JSONObject> cands = InspOsp.inspectionCandidates(api, sc, ty);
            return new Object[]{InspOsp.jobsForInspection(cands, sc), InspOsp.releasedWithoutReport(api, cands, sc, ty)};
        }, (r, err) -> {
            box.removeAllViews();
            if (err != null) { box.addView(error(err, this::reload)); return; }
            @SuppressWarnings("unchecked") List<JSONObject> p = (List<JSONObject>) r[0];
            @SuppressWarnings("unchecked") List<JSONObject> q = (List<JSONObject>) r[1];
            pending = p; released = q;
            render(box);
        });
        return scroll;
    }

    interface Pick { void pick(String v); }

    private View toggle(String[] values, String[] labels, String current, Pick pick) {
        LinearLayout row = Ui.hbox(a);
        for (int i = 0; i < values.length; i++) {
            final String v = values[i];
            Button b = v.equals(current) ? Ui.primary(a, labels[i]) : Ui.outline(a, labels[i], Ui.TEAL_DARK);
            b.setOnClickListener(x -> pick.pick(v));
            LinearLayout.LayoutParams lp = Ui.weight(1);
            lp.rightMargin = i < values.length - 1 ? dp(6) : 0;
            row.addView(b, lp);
        }
        return row;
    }

    private void render(LinearLayout box) {
        box.addView(Ui.label(a, "PENDING / NEW · " + pending.size()));
        if (pending.isEmpty()) box.addView(Ui.empty(a, "No OSP batch is waiting for this inspection."));
        else box.addView(grid(pending), Ui.matchWrap(a, 4));
        box.addView(Ui.label(a, "RELEASED WITHOUT REPORT · " + released.size()), Ui.matchWrap(a, 14));
        box.addView(Ui.text(a, "The stage gate is already decided but no report of this stage exists (for example a draft report was deleted after release). "
            + "They are not pending; open one only to record the missing report.", 11.5f, Ui.MUTED, false));
        if (!released.isEmpty()) box.addView(grid(released), Ui.matchWrap(a, 4));
    }

    private View grid(List<JSONObject> rows) {
        List<String> head = Arrays.asList("OSP Job", "Part Number", "FSI Batch", "Heat", "Process", "OSP Vendor", "Out pcs", "Received pcs", "Sample Gate", "Receipt Decision", "Status");
        List<List<String>> data = new ArrayList<>();
        for (JSONObject r : rows) data.add(Arrays.asList(InspUtil.j(r, "osp_job_number"), InspUtil.j(r, "part_number"), InspUtil.j(r, "osp_batch_code"), InspUtil.j(r, "heat_number"),
            InspUtil.j(r, "process_name"), InspUtil.j(r, "vendor_name"), Ui.num(InspUtil.dbl(r, "quantity_dispatched"), 0), Ui.num(InspUtil.dbl(r, "quantity_received"), 0),
            Ui.pretty(InspUtil.j(r, "sample_gate_status")), Ui.pretty(InspUtil.j(r, "receipt_quality_disposition")), Ui.pretty(InspUtil.j(r, "status"))));
        return new DataGrid(a, data.size() + " batch(es)", head, data, 320, index -> InspOsp.openInspection(a, rows.get(index), type, scope));
    }
}
