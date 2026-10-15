package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/**
 * KPI Dashboards (website app_pages/kpi_dashboards.py): period filter, KPI overview, dashboard
 * picker, number tiles, native charts with their data, tables and CSV export. Calculations are the
 * exact port in GenKpi.
 */
final class GenKpiScreen extends Screen {
    // ------------------------------------------------------------------ shared cache (also used by Home)
    private static final long FRESH_MS = 5 * 60_000L;
    private static List<GenKpi.Board> cachedBoards;
    private static int cachedPeriod = -1;
    private static long cachedAt = 0;
    private static String cachedUser = "";

    static synchronized List<GenKpi.Board> cached(Api api, int period) {
        if (cachedBoards != null && cachedPeriod == period && api.userId.equals(cachedUser) && System.currentTimeMillis() - cachedAt < FRESH_MS) return cachedBoards;
        return null;
    }

    /** Boards for a period, from the 5-minute cache when fresh. Background thread. */
    private static final Object LOCK = new Object();

    static List<GenKpi.Board> boards(Api api, int period, boolean force) throws Exception {
        synchronized (LOCK) {   // one calculation at a time; a second caller then gets the fresh cache
            if (!force) { List<GenKpi.Board> hit = cached(api, period); if (hit != null) return hit; }
            List<GenKpi.Board> b = GenKpi.compute(api, period);
            synchronized (GenKpiScreen.class) {
                cachedBoards = b; cachedPeriod = period; cachedAt = System.currentTimeMillis(); cachedUser = api.userId;
            }
            return b;
        }
    }

    // ------------------------------------------------------------------ screen
    private static int period = GenKpi.DEFAULT_PERIOD;
    private String chosen;
    private List<GenKpi.Board> boards;
    private boolean force = false;

    GenKpiScreen(MainActivity a) { super(a); }

    /** Opens the KPI page with one dashboard selected (key like "po-pipeline"). */
    GenKpiScreen(MainActivity a, String boardKey) { super(a); this.chosen = boardKey; }

    @Override public String title() { return "KPI Dashboards"; }
    @Override public String subtitle() { return "Live numbers · " + GenKpi.PERIODS[period]; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        TextView wait = Ui.text(a, "Calculating KPIs…", 12, Ui.MUTED, false);
        wait.setGravity(android.view.Gravity.CENTER);
        page.addView(wait);
        final int p = period;
        final boolean f = force;
        force = false;
        Api.async(() -> boards(api, p, f), (res, err) -> {
            page.removeAllViews();
            if (err != null) { page.addView(error(err, () -> { force = true; a.rebuild(); })); return; }
            boards = res;
            render();
        });
        return scroll;
    }

    private void render() {
        page.removeAllViews();
        if (boards.isEmpty()) {
            add(Ui.empty(a, "You do not have View permission for any module used by the KPI dashboards."), 0);
            return;
        }
        // ---- period
        add(Ui.label(a, "Period"), 0);
        add(GenUtil.chips(a, Arrays.asList(GenKpi.PERIODS), period, i -> { period = i; a.rebuild(); }), 0);
        add(Ui.text(a, GenKpi.periodCaption(period, LocalDate.now()), 12, Ui.MUTED, false), 4);

        // ---- overview: first tile of every dashboard
        add(Ui.label(a, "KPI overview"), 10);
        List<View> over = new ArrayList<>();
        for (GenKpi.Board b : boards) {
            if (b.tiles.isEmpty()) continue;
            GenKpi.Tile t = b.tiles.get(0);
            View tile = GenUtil.tile(a, b.title, t.label, t.value, t.foot, t.status);
            tile.setOnClickListener(v -> select(b.key, true));
            over.add(tile);
        }
        GenUtil.grid2(a, page, over, 2);

        // ---- dashboard picker + selected dashboard
        add(Ui.label(a, "Dashboard"), 14);
        picker = Ui.vbox(a);
        add(picker, 0);
        section = Ui.vbox(a);
        section.setTag("board");
        add(section, 10);
        select(chosen, false);
    }

    private LinearLayout picker, section;

    private void select(String key, boolean scrollTo) {
        GenKpi.Board board = boards.get(0);
        for (GenKpi.Board b : boards) if (b.key.equals(key)) board = b;
        chosen = board.key;
        List<String> titles = new ArrayList<>();
        int sel = 0;
        for (int i = 0; i < boards.size(); i++) { titles.add(boards.get(i).title); if (boards.get(i) == board) sel = i; }
        picker.removeAllViews();
        picker.addView(GenUtil.chips(a, titles, sel, i -> select(boards.get(i).key, false)));
        section.removeAllViews();
        renderBoard(section, board);
        if (scrollTo) scrollToBoard();
    }

    private void scrollToBoard() {
        if (scroll == null) return;
        scroll.post(() -> {
            int y = dp(10);   // page top padding; children are added with ~8dp margins
            for (int i = 0; i < page.getChildCount(); i++) {
                View v = page.getChildAt(i);
                if ("board".equals(v.getTag())) { scroll.scrollTo(0, Math.max(0, y - dp(48))); return; }
                y += v.getHeight() + dp(8);
            }
        });
    }

    private void renderBoard(LinearLayout box, GenKpi.Board board) {
        TextView head = Ui.text(a, board.title.toUpperCase(Locale.ROOT), 13, Ui.TEAL_DARK, true);
        head.setLetterSpacing(0.04f);
        box.addView(head);
        if (!board.question.isEmpty()) box.addView(Ui.text(a, board.question, 12, Ui.MUTED, false), Ui.matchWrap(a, 2));
        List<View> tiles = new ArrayList<>();
        for (GenKpi.Tile t : board.tiles) tiles.add(GenUtil.tile(a, "", t.label, t.value, t.foot, t.status));
        GenUtil.grid2(a, box, tiles, 8);
        if (board.empty) {
            TextView info = Ui.text(a, "No records in this period.", 13, Ui.TEAL_DARK, false);
            info.setBackground(Ui.round(Ui.TEAL_SOFT, 0, 0, 10, a));
            info.setPadding(dp(12), dp(10), dp(12), dp(10));
            box.addView(info, Ui.matchWrap(a, 12));
            return;
        }
        for (GenKpi.Chart chart : board.charts) {
            LinearLayout card = Ui.card(a);
            card.addView(Ui.text(a, chart.title, 13.5f, Ui.TEXT, true));
            if (!chart.note.isEmpty()) card.addView(Ui.text(a, chart.note, 11, Ui.MUTED, false));
            if (chart.isEmpty()) card.addView(Ui.text(a, "No data", 12, Ui.MUTED, false), Ui.matchWrap(a, 6));
            else card.addView(new GenChart(a, chart), Ui.matchWrap(a, 8));
            List<List<String>> rows = new ArrayList<>();
            for (String[] r : chart.dataRows) rows.add(Arrays.asList(r));
            View grid = rows.isEmpty() ? Ui.text(a, "0 rows", 12, Ui.MUTED, false) : new DataGrid(a, chart.title, chart.dataHeaders, rows, 300, null);
            LinearLayout data = GenUtil.expander(a, "Data", false, grid);
            data.setBackground(null);
            data.setPadding(0, dp(6), 0, 0);
            data.setElevation(0);
            card.addView(data, Ui.matchWrap(a, 4));
            box.addView(card, Ui.matchWrap(a, 12));
        }
        for (GenKpi.Table t : board.tables) {
            View content;
            if (t.rows.isEmpty()) content = Ui.text(a, "0", 12, Ui.MUTED, false);
            else {
                List<List<String>> rows = new ArrayList<>();
                for (String[] r : t.rows) rows.add(Arrays.asList(r));
                content = new DataGrid(a, t.title, t.headers, rows, 420, null);
            }
            box.addView(GenUtil.expander(a, t.title + " · " + String.format(Locale.US, "%,d", t.rows.size()), false, content), Ui.matchWrap(a, 12));
        }
        Button csv = Ui.outline(a, "Export dashboard (CSV)", Ui.TEAL);
        csv.setOnClickListener(v -> GenUtil.exportCsv(a, board.title, "QCMS_KPI_" + board.key + "_" + LocalDate.now(),
            GenKpi.csv(board, GenKpi.PERIODS[period] + " · " + GenKpi.periodCaption(period, LocalDate.now()))));
        box.addView(csv, Ui.matchWrap(a, 14));
    }

    @Override public void reload() { force = true; a.rebuild(); }
}
