package com.fourstar.qcmsapp;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.pdf.PdfRenderer;
import android.os.Build;
import android.os.ParcelFileDescriptor;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

/**
 * Native PDF viewer: pages rendered with PdfRenderer, Save to Downloads, Share and Open with.
 * forPo() generates the controlled Purchase Order PDF on the phone (no website).
 */
public final class SndPdfView extends Screen {
    private static final String MIME = "application/pdf";
    private static final int RENDER_WIDTH_PX = 900;

    private final String poId;
    private final JSONObject options;
    private String title;
    private String fileName;
    private byte[] pdf;
    private List<Bitmap> pages;
    private SndData.Po po;
    private SndFiles.Saved saved;
    private Exception failure;

    private SndPdfView(MainActivity a, String poId, JSONObject options, String title, String fileName, byte[] pdf) {
        super(a);
        this.poId = poId;
        this.options = options;
        this.title = title;
        this.fileName = fileName;
        this.pdf = pdf;
    }

    /** Purchase Order PDF with the PO's saved print sections. */
    public static void forPo(MainActivity a, String poId) {
        a.push(new SndPdfView(a, poId, null, "Purchase Order PDF", "Purchase_Order.pdf", null));
    }

    /** Purchase Order PDF preview with the ticked sections (not saved on the PO). */
    static void preview(MainActivity a, String poId, JSONObject options) {
        a.push(new SndPdfView(a, poId, options, "PO PDF preview", "Purchase_Order_PREVIEW.pdf", null));
    }

    /** Any generated PDF. */
    static void show(MainActivity a, String title, String fileName, byte[] pdf) {
        a.push(new SndPdfView(a, null, null, title, fileName, pdf));
    }

    @Override public String title() { return title; }
    @Override public String subtitle() { return pages == null ? "Generating…" : pages.size() + " page(s) · " + fileName; }
    @Override public int tab() { return 1; }

    @Override
    public View build() {
        newPage();
        if (pages != null) { render(); return scroll; }
        if (failure != null) { page.addView(error(failure, this::retry)); return scroll; }
        page.addView(loading());
        Api.async(() -> {
            if (pdf == null) {
                po = SndData.load(api, poId);
                pdf = SndPoPdf.build(po, options);
                fileName = options == null ? po.fileName() : po.fileName().replace(".pdf", "_PREVIEW.pdf");
                title = po.number().isEmpty() ? title : (options == null ? "PO " : "Preview ") + po.number();
            }
            File f = SndFiles.writeCache(a, fileName, pdf);
            return renderPages(f);
        }, (list, err) -> {
            if (err != null || list == null) {
                failure = err != null ? err : new IllegalStateException("The PDF could not be shown.");
                a.rebuild();
                return;
            }
            pages = list;
            a.rebuild();
        });
        return scroll;
    }

    private void retry() { failure = null; a.rebuild(); }

    private static List<Bitmap> renderPages(File f) throws Exception {
        List<Bitmap> out = new ArrayList<>();
        ParcelFileDescriptor fd = ParcelFileDescriptor.open(f, ParcelFileDescriptor.MODE_READ_ONLY);
        PdfRenderer renderer = new PdfRenderer(fd);
        try {
            for (int i = 0; i < renderer.getPageCount(); i++) {
                PdfRenderer.Page p = renderer.openPage(i);
                try {
                    int w = RENDER_WIDTH_PX;
                    int h = Math.max(1, Math.round(w * (p.getHeight() / (float) Math.max(1, p.getWidth()))));
                    Bitmap b = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
                    p.render(b, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);
                    out.add(b);
                } finally {
                    p.close();
                }
            }
        } finally {
            renderer.close();
            try { fd.close(); } catch (Exception ignored) { }
        }
        return out;
    }

    private void render() {
        a.rebuildTitle(this);
        LinearLayout actions = Ui.hbox(a);
        Button save = Ui.primary(a, "Save to Downloads");
        Button share = Ui.outline(a, "Share", Ui.TEAL);
        LinearLayout.LayoutParams l = Ui.weight(1);
        l.rightMargin = dp(8);
        actions.addView(save, l);
        actions.addView(share, Ui.weight(1));
        add(actions, 2);
        save.setOnClickListener(v -> save(false, false));
        share.setOnClickListener(v -> save(true, false));
        Button open = Ui.outline(a, "Open in PDF app (zoom / print)", Ui.TEAL);
        open.setOnClickListener(v -> save(false, true));
        add(open, 8);
        if (poId != null && options == null && po != null && !po.cancelled()) {
            Button email = Ui.outline(a, "Email this PO to the supplier", Ui.TEAL_DARK);
            email.setOnClickListener(v -> SndPoSend.open(a, poId));
            add(email, 8);
        }
        if (po != null && !po.approved()) {
            add(Ui.chip(a, "Not approved yet · PDF carries the PENDING APPROVAL watermark", "amber"), 8);
        }
        TextView hint = Ui.text(a, pages.size() + " page(s) · scroll to read. Use \"Open in PDF app\" to zoom or print.", 11.5f, Ui.MUTED, false);
        add(hint, 8);
        for (int i = 0; i < pages.size(); i++) {
            PageView pv = new PageView(a, pages.get(i));
            pv.setBackgroundColor(Color.WHITE);
            pv.setElevation(dp(2));
            add(pv, 10);
            TextView n = Ui.text(a, "Page " + (i + 1) + " of " + pages.size(), 10.5f, Ui.MUTED, false);
            n.setGravity(android.view.Gravity.CENTER);
            add(n, 2);
        }
    }

    /** Save once (MediaStore), then share / open the same Uri. */
    private void save(boolean thenShare, boolean thenOpen) {
        if (pdf == null) return;
        if (saved != null) { after(thenShare, thenOpen); return; }
        Api.async(() -> SndFiles.saveToDownloads(a, fileName, pdf, MIME), (s, err) -> {
            if (err != null || s == null) { a.toast("Could not save the PDF: " + Api.message(err)); return; }
            saved = s;
            a.toast("Saved: " + s.where);
            after(thenShare, thenOpen);
        });
    }

    private void after(boolean thenShare, boolean thenOpen) {
        if (!thenShare && !thenOpen) {
            if (saved != null) a.toast("Already saved: " + saved.where);
            return;
        }
        if (saved.uri == null) {
            // Android 8 / 9: no MediaStore Downloads collection and no FileProvider in this app.
            a.toast("Saved to " + saved.where + ". Sharing / opening needs Android 10 or newer - send the PO by email from QCMS instead.");
            return;
        }
        if (thenShare) SndFiles.share(a, saved.uri, MIME, fileName);
        else SndFiles.open(a, saved.uri, MIME);
    }

    /** One PDF page scaled to the screen width. */
    static final class PageView extends View {
        private final Bitmap bitmap;
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | 2 /* FILTER_BITMAP_FLAG */);

        PageView(Context c, Bitmap b) { super(c); bitmap = b; }

        @Override
        protected void onMeasure(int widthSpec, int heightSpec) {
            int w = View.MeasureSpec.getSize(widthSpec);
            int h = bitmap == null || bitmap.getWidth() == 0 ? w : Math.round(w * (bitmap.getHeight() / (float) bitmap.getWidth()));
            setMeasuredDimension(w, h);
        }

        @Override
        protected void onDraw(Canvas c) {
            c.drawColor(Color.WHITE);
            if (bitmap == null || bitmap.getWidth() == 0) return;
            float s = getWidth() / (float) bitmap.getWidth();
            c.save();
            c.scale(s, s);
            c.drawBitmap(bitmap, 0f, 0f, paint);
            c.restore();
        }
    }

    static boolean canShare() { return Build.VERSION.SDK_INT >= 29; }
}
