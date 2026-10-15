package com.fourstar.qcmsapp;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;

/**
 * Local files for generated PDFs: app cache (for the native viewer), Downloads (MediaStore on Android 10+,
 * app-specific Downloads folder on Android 8 / 9) and Share / Open with a content:// Uri from MediaStore.
 * APIs missing from the compile stubs are called by reflection (they exist on the device).
 */
final class SndFiles {
    private SndFiles() { }

    static String safeName(String name) {
        String s = (name == null ? "" : name).replaceAll("[^A-Za-z0-9_.-]+", "_").replaceAll("^_+|_+$", "");
        return s.isEmpty() ? "QCMS_Report.pdf" : s;
    }

    /** {app cache}/qcms_pdf/{name} - used by PdfRenderer (needs a seekable file). */
    static File writeCache(MainActivity a, String name, byte[] data) throws Exception {
        File base = (File) a.getClass().getMethod("getCacheDir").invoke(a);
        File dir = new File(base, "qcms_pdf");
        if (!dir.exists() && !dir.mkdirs()) throw new IllegalStateException("The phone storage is not available.");
        File f = new File(dir, safeName(name));
        try (FileOutputStream out = new FileOutputStream(f)) { out.write(data); }
        return f;
    }

    /** Result of a save: the MediaStore Uri (Android 10+) or the file (older phones). */
    static final class Saved {
        final Uri uri; final File file; final String where;
        Saved(Uri uri, File file, String where) { this.uri = uri; this.file = file; this.where = where; }
    }

    /** Save to Downloads/QCMS (Android 10+), else the app's own Downloads folder. */
    static Saved saveToDownloads(MainActivity a, String name, byte[] data, String mime) throws Exception {
        String file = safeName(name);
        if (Build.VERSION.SDK_INT >= 29) {
            Class<?> downloads = Class.forName("android.provider.MediaStore$Downloads");
            Uri collection = (Uri) downloads.getField("EXTERNAL_CONTENT_URI").get(null);
            ContentValues values = new ContentValues();
            values.put("_display_name", file);
            values.put("mime_type", mime);
            values.put("relative_path", Environment.DIRECTORY_DOWNLOADS + "/QCMS");
            ContentResolver resolver = a.getContentResolver();
            Uri uri = resolver.insert(collection, values);
            if (uri == null) throw new IllegalStateException("Downloads folder is not available.");
            OutputStream out = (OutputStream) ContentResolver.class.getMethod("openOutputStream", Uri.class).invoke(resolver, uri);
            if (out == null) throw new IllegalStateException("Could not write to Downloads.");
            try (OutputStream o = out) { o.write(data); }
            return new Saved(uri, null, "Downloads/QCMS/" + file);
        }
        File dir = (File) a.getClass().getMethod("getExternalFilesDir", String.class).invoke(a, Environment.DIRECTORY_DOWNLOADS);
        if (dir == null) throw new IllegalStateException("Phone storage is not available.");
        if (!dir.exists() && !dir.mkdirs()) throw new IllegalStateException("Phone storage is not available.");
        File f = new File(dir, file);
        try (FileOutputStream out = new FileOutputStream(f)) { out.write(data); }
        return new Saved(null, f, f.getAbsolutePath());
    }

    static void share(MainActivity a, Uri uri, String mime, String subject) {
        try {
            Intent send = new Intent(Intent.ACTION_SEND);
            send.setType(mime);
            send.putExtra(Intent.EXTRA_SUBJECT, subject);
            send.putExtra(Intent.EXTRA_STREAM, uri);
            send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            a.startActivity(Intent.createChooser(send, "Share " + subject));
        } catch (Exception e) {
            a.toast("No app to share with.");
        }
    }

    static void open(MainActivity a, Uri uri, String mime) {
        try {
            Intent view = new Intent(Intent.ACTION_VIEW);
            view.setDataAndType(uri, mime);
            view.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            a.startActivity(view);
        } catch (Exception e) {
            a.toast("No PDF viewer app is installed.");
        }
    }
}
