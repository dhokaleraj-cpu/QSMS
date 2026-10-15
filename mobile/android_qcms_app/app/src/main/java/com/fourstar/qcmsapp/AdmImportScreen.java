package com.fourstar.qcmsapp;

import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Native port of app_pages/master_import.py for CSV files. Excel (.xlsx / .xls) cannot be read on the phone
 * (no spreadsheet library in the app): save the template's import sheet as CSV, or import Excel on the website.
 */
public final class AdmImportScreen extends Screen {
    private static String selectedKey = AdmImport.IMPORTABLE[0][0];

    private boolean allowed;
    private AdmImport.Frame frame;
    private String fileName = "";
    private LinearLayout fileBox, resultBox;

    public AdmImportScreen(MainActivity a) { super(a); }

    @Override public String title() { return "Master Import"; }
    @Override public String subtitle() { return "Upload a completed template as CSV · existing duplicate keys are skipped"; }
    @Override public int tab() { return Catalog.MORE; }

    @Override
    public View build() {
        newPage();
        page.addView(loading());
        String[] imp = AdmImport.importable(selectedKey);
        Api.async(() -> AdmPerm.current(api, imp[2], "can_create") || AdmPerm.current(api, imp[2], "can_edit"), (ok, err) -> {
            page.removeAllViews();
            allowed = err == null && ok != null && ok;
            render();
        });
        return scroll;
    }

    private void render() {
        String[] imp = AdmImport.importable(selectedKey);
        List<String> keys = new ArrayList<>(), labels = new ArrayList<>();
        for (String[] i : AdmImport.IMPORTABLE) { keys.add(i[0]); labels.add(i[1]); }
        AdmUi.choice(a, page, "Master to Import", keys, labels, selectedKey, v -> { selectedKey = v; frame = null; a.rebuild(); });
        if (!allowed) add(AdmUi.note(a, "Create or Edit permission is required for this master import.", "amber"), 8);

        LinearLayout t = AdmUi.section(a, page, "", "TEMPLATE & UPLOAD", "");
        t.addView(AdmUi.note(a, "The app imports CSV files only. Excel templates (.xlsx) with the live master-data sheets are downloaded and imported on the QCMS website. "
            + "To import from the phone, save the template's import sheet as \"CSV UTF-8\" (first row = column headings) and choose that file here.", "grey"), Ui.matchWrap(a, 6));
        List<String> cols = AdmImport.expectedColumns(selectedKey);
        t.addView(Ui.text(a, "Recognised column headings for " + imp[1] + ":\n" + String.join(" · ", cols)
            + (AdmImport.DEFS.containsKey(selectedKey) && !AdmImport.DEFS.get(selectedKey).auto.isEmpty() ? "\nLeave the master code blank or write AUTO to let QCMS generate it." : "")
            + (selectedKey.equals("employees") ? "\nLeave Employee Code blank or write AUTO to let QCMS generate it." : ""), 11.5f, Ui.TEXT, false), Ui.matchWrap(a, 8));
        AdmUi.outline(a, t, "Share CSV heading row (template)", v -> AdmUi.share(a, imp[1] + " import template.csv", AdmUi.csv(cols, new ArrayList<>())));
        Button choose = AdmUi.primary(a, t, frame == null ? "Choose completed CSV file" : "Choose another CSV file", v -> a.pickFile("Upload completed master file (CSV)", false, file -> {
            String name = file.name == null ? "" : file.name;
            String low = name.toLowerCase(Locale.ROOT);
            if (low.endsWith(".xlsx") || low.endsWith(".xls")) {
                a.toast("Excel files cannot be read in the app. Save the import sheet as CSV (UTF-8) or import on the website.");
                return;
            }
            if ((file.mime != null && file.mime.startsWith("image/")) || low.endsWith(".pdf")) {
                a.toast("Choose the completed CSV file (not a photo or PDF).");
                return;
            }
            Api.async(() -> {
                AdmImport.Frame f = AdmImport.readCsv(file.data);
                AdmImport.filterParty(f, selectedKey);
                return f;
            }, (f, err) -> {
                if (err != null) { a.toast("Could not read the uploaded master file: " + Api.message(err)); return; }
                frame = f;
                fileName = name;
                showFile();
            });
        }));
        AdmUi.enable(choose, allowed);
        fileBox = Ui.vbox(a);
        add(fileBox, 4);
        resultBox = Ui.vbox(a);
        add(resultBox, 4);
        if (frame == null) fileBox.addView(Ui.text(a, "Complete the template and upload it here. Existing matching database records are skipped; only new natural keys are imported.", 11.5f, Ui.MUTED, false));
        else showFile();
    }

    private void showFile() {
        fileBox.removeAllViews();
        resultBox.removeAllViews();
        fileBox.addView(Ui.text(a, "File: " + fileName + "\nDetected worksheet: CSV · " + frame.rows.size() + " applicable data row(s)", 12, Ui.TEXT, true));
        List<List<String>> rows = new ArrayList<>();
        for (int i = 0; i < frame.rows.size() && i < 30; i++) {
            Map<String, String> r = frame.rows.get(i);
            List<String> line = new ArrayList<>();
            for (String c : frame.columns) line.add(r.get(c) == null ? "" : r.get(c));
            rows.add(line);
        }
        if (!frame.columns.isEmpty()) fileBox.addView(new DataGrid(a, "Import preview (first 30 rows)", frame.columns, rows, 360, null), Ui.matchWrap(a, 6));
        fileBox.addView(AdmUi.note(a, "Duplicate-safe import: existing matching master keys and duplicate rows inside the uploaded file are skipped. Only missing database records are created.", "teal"), Ui.matchWrap(a, 8));
        TextView progress = Ui.text(a, "", 12, Ui.TEAL_DARK, true);
        Button go = AdmUi.primary(a, fileBox, "Import Selected Master", v -> {
            String[] imp = AdmImport.importable(selectedKey);
            a.confirm("Import " + imp[1] + "?", frame.rows.size() + " row(s) from " + fileName + ". Existing / duplicate rows are skipped.", "Import", () -> run((Button) v, progress));
        });
        AdmUi.enable(go, allowed && !frame.rows.isEmpty());
        fileBox.addView(progress, Ui.matchWrap(a, 6));
    }

    private void run(Button b, TextView progress) {
        AdmUi.enable(b, false);
        final String key = selectedKey;
        final AdmImport.Frame f = frame;
        progress.setText("Importing…");
        Api.async(() -> AdmImport.importMaster(api, key, f, (done, total) -> Api.main(() -> progress.setText("Importing row " + (done + 1) + " of " + total + "…"))),
            (res, err) -> {
                AdmUi.enable(b, true);
                progress.setText("");
                resultBox.removeAllViews();
                if (err != null) { resultBox.addView(AdmUi.note(a, Api.message(err), "red")); return; }
                Lookups.invalidate();
                if (!res.errors.isEmpty()) {
                    StringBuilder t = new StringBuilder("Import completed with validation errors:\n\n");
                    for (int i = 0; i < res.errors.size() && i < 30; i++) t.append(res.errors.get(i)).append('\n');
                    resultBox.addView(AdmUi.note(a, t.toString().trim(), "red"), Ui.matchWrap(a, 6));
                    if (res.errors.size() > 30) resultBox.addView(Ui.text(a, (res.errors.size() - 30) + " additional row error(s) were not displayed.", 11, Ui.MUTED, false));
                }
                if (res.created > 0 || res.skipped > 0) {
                    String msg = "Master import completed: " + res.created + " created, " + res.skipped + " duplicate/existing row(s) skipped, " + res.errors.size() + " rejected.";
                    resultBox.addView(AdmUi.note(a, msg, "green"), Ui.matchWrap(a, 6));
                    a.toast(msg);
                } else if (res.errors.isEmpty()) {
                    resultBox.addView(AdmUi.note(a, "No new database-missing rows were available to import.", "teal"), Ui.matchWrap(a, 6));
                }
            });
    }
}
