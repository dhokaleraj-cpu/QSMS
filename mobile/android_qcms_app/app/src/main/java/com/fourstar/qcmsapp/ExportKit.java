package com.fourstar.qcmsapp;

import android.app.AlertDialog;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.os.ParcelFileDescriptor;
import android.print.PageRange;
import android.print.PrintAttributes;
import android.print.PrintDocumentAdapter;
import android.print.PrintDocumentInfo;
import android.print.PrintManager;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.CompoundButton;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.io.FileOutputStream;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/**
 * Download PDF / Download Excel / Print / Email / Share for EVERY screen of the app (records, registers,
 * reports and entries). A screen can describe its content (ExportDoc.Source); otherwise the content is read
 * from what is on the screen: detail rows, form fields, section headings and every spreadsheet grid.
 */
final class ExportKit {
    static final String PDF = "application/pdf";
    static final String XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

    private ExportKit() { }

    // ------------------------------------------------------------------ entry point (top-bar ⇩ button)
    static void show(MainActivity a, Screen screen, View content) {
        if (screen == null) return;
        if (screen instanceof RecordScreen && ((RecordScreen) screen).layoutReady()) {
            RecordScreen rs = (RecordScreen) screen;
            new AlertDialog.Builder(a).setTitle(screen.title())
                .setItems(new String[]{"Print layout PDF (same as website)", "Data export: PDF / Excel / Print / Email"}, (d, w) -> {
                    if (w == 0) rs.printLayout(); else showData(a, screen, content);
                }).setNegativeButton("Close", null).show();
            return;
        }
        showData(a, screen, content);
    }

    static void showData(MainActivity a, Screen screen, View content) {
        ExportDoc captured = null;
        if (!(screen instanceof ExportDoc.Source)) {
            captured = capture(screen.title(), screen.subtitle(), content);
            if (captured.isEmpty()) {
                a.toast("Nothing to print on this screen yet - open a record, register or report first.");
                return;
            }
        }
        final ExportDoc fromScreen = captured;
        a.toast("Preparing…");
        Api.async(() -> fromScreen != null ? fromScreen : ((ExportDoc.Source) screen).export(), (doc, err) -> {
            if (err != null || doc == null) { a.toast("Could not prepare the document: " + Api.message(err)); return; }
            menu(a, doc);
        });
    }

    static void menu(MainActivity a, ExportDoc doc) {
        String info = doc.tables.isEmpty() ? "" : " · " + doc.rowCount() + " row(s)";
        String[] items = {
            "Download PDF", "Download Excel (.xlsx)", "View PDF", "Print", "Email from QCMS (PDF + Excel attached)",
            "Share PDF (WhatsApp, Gmail…)", "Share Excel"};
        new AlertDialog.Builder(a)
            .setTitle(doc.title + info)
            .setItems(items, (d, which) -> {
                switch (which) {
                    case 0: download(a, doc, false); break;
                    case 1: download(a, doc, true); break;
                    case 2: view(a, doc); break;
                    case 3: print(a, doc); break;
                    case 4: email(a, doc); break;
                    case 5: share(a, doc, false); break;
                    default: share(a, doc, true); break;
                }
            })
            .setNegativeButton("Close", null)
            .show();
    }

    // ------------------------------------------------------------------ R33: website print layout
    /** Report in the website's controlled print layout: view, download, print, email, share. */
    static void layoutMenu(MainActivity a, Api.Task<RptDoc> builder) {
        a.toast("Preparing the print layout PDF…");
        Api.async(() -> {
            RptDoc doc = builder.run();
            return new Object[]{doc, RptPdf.render(doc)};
        }, (res, err) -> {
            if (err != null || res == null) { a.toast("Could not create the PDF: " + Api.message(err)); return; }
            RptDoc doc = (RptDoc) res[0];
            byte[] pdf = (byte[]) res[1];
            layoutActions(a, doc.title, doc.fileBase, pdf);
        });
    }

    static void layoutActions(MainActivity a, String title, String fileBase, byte[] pdf) {
        String stamp = new SimpleDateFormat("yyyyMMdd_HHmm", Locale.ENGLISH).format(new Date());
        String name = SndFiles.safeName(fileBase + "_" + stamp + ".pdf");
        String[] items = {"View PDF", "Download PDF", "Print", "Email from QCMS (PDF attached)", "Share PDF (WhatsApp, Gmail…)"};
        new AlertDialog.Builder(a)
            .setTitle(title)
            .setItems(items, (d, which) -> {
                switch (which) {
                    case 0: SndPdfView.show(a, title, name, pdf); break;
                    case 1:
                        Api.async(() -> SndFiles.saveToDownloads(a, name, pdf, PDF), (saved, err) -> {
                            if (err != null || saved == null) { a.toast("Could not save: " + Api.message(err)); return; }
                            if (saved.uri == null) { a.toast("Saved: " + saved.where); return; }
                            new AlertDialog.Builder(a).setTitle("Saved").setMessage(saved.where)
                                .setPositiveButton("Open", (x, y) -> SndFiles.open(a, saved.uri, PDF))
                                .setNeutralButton("Share", (x, y) -> SndFiles.share(a, saved.uri, PDF, name))
                                .setNegativeButton("Done", null).show();
                        });
                        break;
                    case 2: printPdf(a, title, pdf); break;
                    case 3: {
                        List<Attachments.FileData> files = new ArrayList<>();
                        files.add(new Attachments.FileData(pdf, name, PDF));
                        SndEmailSend.openWith(a, "QCMS · " + title, "Dear Sir / Madam,\n\nPlease find attached " + title + " from QCMS.\n\nRegards,\n" + printedBy(a), files);
                        break;
                    }
                    default:
                        Api.async(() -> SndFiles.saveToDownloads(a, name, pdf, PDF), (saved, err) -> {
                            if (err != null || saved == null || saved.uri == null) { a.toast("Sharing needs Android 10 or newer - use Email from QCMS instead."); return; }
                            SndFiles.share(a, saved.uri, PDF, title);
                        });
                }
            })
            .setNegativeButton("Close", null)
            .show();
    }

    // ------------------------------------------------------------------ files
    static String printedBy(MainActivity a) {
        Api api = Api.get(a);
        return api.fullName != null && !api.fullName.isEmpty() ? api.fullName : api.email;
    }

    static String fileName(ExportDoc doc, String ext) {
        String stamp = new SimpleDateFormat("yyyyMMdd_HHmm", Locale.ENGLISH).format(new Date());
        return SndFiles.safeName(doc.fileBase + "_" + stamp + ext);
    }

    static byte[] pdf(MainActivity a, ExportDoc doc) throws Exception { return ExportPdf.render(doc, printedBy(a)); }

    static byte[] xlsx(MainActivity a, ExportDoc doc) throws Exception { return ExportXlsx.build(doc, printedBy(a)); }

    private static void download(MainActivity a, ExportDoc doc, boolean excel) {
        String name = fileName(doc, excel ? ".xlsx" : ".pdf");
        Api.async(() -> SndFiles.saveToDownloads(a, name, excel ? xlsx(a, doc) : pdf(a, doc), excel ? XLSX : PDF), (saved, err) -> {
            if (err != null || saved == null) { a.toast("Could not save: " + Api.message(err)); return; }
            if (saved.uri == null) { a.toast("Saved: " + saved.where); return; }
            new AlertDialog.Builder(a)
                .setTitle("Saved")
                .setMessage(saved.where)
                .setPositiveButton("Open", (d, w) -> SndFiles.open(a, saved.uri, excel ? XLSX : PDF))
                .setNeutralButton("Share", (d, w) -> SndFiles.share(a, saved.uri, excel ? XLSX : PDF, name))
                .setNegativeButton("Done", null)
                .show();
        });
    }

    private static void view(MainActivity a, ExportDoc doc) {
        Api.async(() -> pdf(a, doc), (bytes, err) -> {
            if (err != null || bytes == null) { a.toast("Could not create the PDF: " + Api.message(err)); return; }
            SndPdfView.show(a, doc.title, fileName(doc, ".pdf"), bytes);
        });
    }

    private static void share(MainActivity a, ExportDoc doc, boolean excel) {
        String name = fileName(doc, excel ? ".xlsx" : ".pdf");
        Api.async(() -> SndFiles.saveToDownloads(a, name, excel ? xlsx(a, doc) : pdf(a, doc), excel ? XLSX : PDF), (saved, err) -> {
            if (err != null || saved == null) { a.toast("Could not prepare the file: " + Api.message(err)); return; }
            if (saved.uri == null) {
                a.toast("Saved to " + saved.where + ". Sharing needs Android 10 or newer - use \"Email from QCMS\" instead.");
                return;
            }
            SndFiles.share(a, saved.uri, excel ? XLSX : PDF, doc.title);
        });
    }

    /** QCMS Send Email (company mailbox) with the PDF and the Excel file attached. */
    static void email(MainActivity a, ExportDoc doc) {
        Api.async(() -> {
            List<Attachments.FileData> files = new ArrayList<>();
            files.add(new Attachments.FileData(pdf(a, doc), fileName(doc, ".pdf"), PDF));
            files.add(new Attachments.FileData(xlsx(a, doc), fileName(doc, ".xlsx"), XLSX));
            return files;
        }, (files, err) -> {
            if (err != null || files == null) { a.toast("Could not prepare the attachments: " + Api.message(err)); return; }
            String subject = "QCMS · " + doc.title;
            String body = "Dear Sir / Madam,\n\nPlease find attached " + doc.title
                + (doc.subtitle.isEmpty() ? "" : " (" + doc.subtitle + ")") + " from QCMS as PDF and Excel.\n\nRegards,\n" + printedBy(a);
            SndEmailSend.openWith(a, subject, body, files);
        });
    }

    // ------------------------------------------------------------------ print (Android print service)
    static void print(MainActivity a, ExportDoc doc) {
        Api.async(() -> pdf(a, doc), (bytes, err) -> {
            if (err != null || bytes == null) { a.toast("Could not create the PDF: " + Api.message(err)); return; }
            printPdf(a, doc.title, bytes);
        });
    }

    static void printPdf(MainActivity a, String jobName, byte[] pdf) {
        try {
            PrintManager pm = a.getSystemService(PrintManager.class);
            if (pm == null) { a.toast("Printing is not available on this phone."); return; }
            pm.print("QCMS " + jobName, new PrintDocumentAdapter() {
                @Override
                public void onLayout(PrintAttributes oldAttributes, PrintAttributes newAttributes, CancellationSignal cancel,
                                     LayoutResultCallback callback, Bundle extras) {
                    if (cancel != null && cancel.isCanceled()) { callback.onLayoutCancelled(); return; }
                    PrintDocumentInfo info = new PrintDocumentInfo.Builder(SndFiles.safeName("QCMS_" + jobName + ".pdf"))
                        .setContentType(PrintDocumentInfo.CONTENT_TYPE_DOCUMENT)
                        .setPageCount(PrintDocumentInfo.PAGE_COUNT_UNKNOWN)
                        .build();
                    callback.onLayoutFinished(info, true);
                }

                @Override
                public void onWrite(PageRange[] pages, ParcelFileDescriptor destination, CancellationSignal cancel, WriteResultCallback callback) {
                    try (FileOutputStream out = new FileOutputStream(destination.getFileDescriptor())) {
                        out.write(pdf);
                        callback.onWriteFinished(new PageRange[]{PageRange.ALL_PAGES});
                    } catch (Exception e) {
                        callback.onWriteFailed(e.getMessage());
                    }
                }
            }, null);
        } catch (Exception e) {
            a.toast("Printing is not available: " + Api.message(e));
        }
    }

    // ------------------------------------------------------------------ read the screen
    /** Builds a document from the views on the screen: headings, label/value rows, form fields, check boxes and grids. */
    static ExportDoc capture(String title, String subtitle, View root) {
        ExportDoc doc = new ExportDoc(title).subtitle(subtitle);
        doc.file("QCMS_" + title);
        Walker w = new Walker(doc);
        if (root != null) w.walk(root);
        return doc;
    }

    private static final class Walker {
        final ExportDoc doc;
        ExportDoc.Section section;
        String heading = "";
        int grids = 0;

        Walker(ExportDoc doc) { this.doc = doc; }

        ExportDoc.Section sec() {
            if (section == null) section = doc.section(heading.isEmpty() ? "Details" : heading);
            return section;
        }

        void walk(View v) {
            if (v == null || v.getVisibility() != View.VISIBLE) return;
            if (v instanceof DataGrid) {
                DataGrid d = (DataGrid) v;
                if (!d.title().isEmpty()) heading = d.title();
                walk(d.sheet());
                return;
            }
            if (v instanceof SheetView) {
                SheetView s = (SheetView) v;
                List<List<String>> rows = new ArrayList<>();
                for (String[] r : s.rowsData()) rows.add(new ArrayList<>(Arrays.asList(r)));
                grids++;
                doc.table(heading.isEmpty() ? "Table " + grids : heading, s.columnsData(), rows);
                section = null;
                return;
            }
            if (v instanceof FormView) {
                for (String[] p : ((FormView) v).exportPairs()) if (!p[1].isEmpty()) sec().pair(p[0], p[1]);
                return;
            }
            if (v instanceof CompoundButton) {
                String t = String.valueOf(((CompoundButton) v).getText()).trim();
                if (!t.isEmpty()) sec().pair(t, ((CompoundButton) v).isChecked() ? "Yes" : "No");
                return;
            }
            if (v instanceof Button || v instanceof EditText) return;
            if (v instanceof ViewGroup) {
                ViewGroup g = (ViewGroup) v;
                if (g instanceof LinearLayout && ((LinearLayout) g).getOrientation() == LinearLayout.HORIZONTAL && g.getChildCount() == 2
                    && isPlainText(g.getChildAt(0)) && isPlainText(g.getChildAt(1))) {
                    String k = text(g.getChildAt(0)), val = text(g.getChildAt(1));
                    if (!k.isEmpty() || !val.isEmpty()) sec().pair(k, val);
                    return;
                }
                for (int i = 0; i < g.getChildCount(); i++) walk(g.getChildAt(i));
                return;
            }
            if (v instanceof TextView) {
                String t = text(v);
                if (isHeading(t)) { heading = prettyHeading(t); section = null; }
            }
        }

        static boolean isPlainText(View v) {
            return v instanceof TextView && !(v instanceof Button) && !(v instanceof EditText) && v.getVisibility() == View.VISIBLE;
        }

        static String text(View v) {
            CharSequence t = ((TextView) v).getText();
            return t == null ? "" : t.toString().trim();
        }

        /** Ui.label headings are upper case ("DETAILS", "B · RAW MATERIAL"). */
        static boolean isHeading(String t) {
            if (t.length() < 3 || t.length() > 70) return false;
            boolean letter = false;
            for (char ch : t.toCharArray()) {
                if (Character.isLowerCase(ch)) return false;
                if (Character.isLetter(ch)) letter = true;
            }
            return letter;
        }

        static String prettyHeading(String t) {
            String s = t.toLowerCase(Locale.ROOT);
            StringBuilder b = new StringBuilder();
            boolean up = true;
            for (char ch : s.toCharArray()) { b.append(up ? Character.toUpperCase(ch) : ch); up = ch == ' ' || ch == '/' || ch == '('; }
            return b.toString();
        }
    }
}
