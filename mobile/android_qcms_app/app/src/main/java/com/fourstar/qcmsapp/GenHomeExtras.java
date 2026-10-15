package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/**
 * Home add-on: the website's "KPI OVERVIEW" (first tile of every KPI dashboard the user may view,
 * default period Last 90 days). Tap a tile to open that dashboard. Uses the 5-minute KPI cache.
 */
final class GenHomeExtras {
    private GenHomeExtras() { }

    static void addKpis(MainActivity a, LinearLayout page) {
        Api api = Api.get(a);
        LinearLayout box = Ui.vbox(a);
        LinearLayout head = Ui.hbox(a);
        head.addView(Ui.label(a, "KPI overview · " + GenKpi.PERIODS[GenKpi.DEFAULT_PERIOD]), Ui.weight(1));
        TextView all = Ui.text(a, "All dashboards ›", 12.5f, Ui.TEAL_DARK, true);
        all.setPadding(Ui.dp(a, 8), Ui.dp(a, 8), 0, Ui.dp(a, 4));
        all.setOnClickListener(v -> a.push(new GenKpiScreen(a)));
        head.addView(all);
        box.addView(head);
        LinearLayout tiles = Ui.vbox(a);
        box.addView(tiles);
        page.addView(box, Ui.matchWrap(a, 12));

        List<GenKpi.Board> hit = GenKpiScreen.cached(api, GenKpi.DEFAULT_PERIOD);
        if (hit != null) { fill(a, box, tiles, hit); return; }
        TextView wait = Ui.text(a, "Calculating KPIs…", 12, Ui.MUTED, false);
        tiles.addView(wait);
        Api.async(() -> GenKpiScreen.boards(api, GenKpi.DEFAULT_PERIOD, false), (boards, err) -> {
            tiles.removeAllViews();
            if (err != null) {
                TextView t = Ui.text(a, "KPIs not available: " + Api.message(err), 12, Ui.MUTED, false);
                t.setOnClickListener(v -> a.push(new GenKpiScreen(a)));
                tiles.addView(t);
                return;
            }
            fill(a, box, tiles, boards);
        });
    }

    private static void fill(MainActivity a, LinearLayout box, LinearLayout tiles, List<GenKpi.Board> boards) {
        tiles.removeAllViews();
        List<View> views = new ArrayList<>();
        for (GenKpi.Board b : boards) {
            if (b.tiles.isEmpty()) continue;
            GenKpi.Tile t = b.tiles.get(0);
            View tile = GenUtil.tile(a, b.title, t.label, t.value, t.foot, t.status);
            tile.setOnClickListener(v -> a.push(new GenKpiScreen(a, b.key)));
            views.add(tile);
        }
        if (views.isEmpty()) { box.setVisibility(View.GONE); return; }   // no KPI module permission: show nothing
        GenUtil.grid2(a, tiles, views, 2);
    }
}
