package com.fourstar.qcmsapp;

import android.content.Context;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Matrix;
import android.media.ExifInterface;
import android.net.Uri;
import android.provider.OpenableColumns;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.Locale;

/** Reads a picked / captured file; photos are turned upright and compressed for upload. */
public final class Photos {
    private Photos() { }
    static final int MAX_SIDE = 2000;
    static final int MAX_FILE_BYTES = 25 * 1024 * 1024;

    public static Attachments.FileData read(Context c, Uri uri) throws Exception {
        String name = displayName(c, uri);
        String mime = c.getContentResolver().getType(uri);
        byte[] raw;
        try (InputStream in = c.getContentResolver().openInputStream(uri); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            if (in == null) throw new IllegalStateException("File is empty");
            byte[] buf = new byte[16384]; int n;
            while ((n = in.read(buf)) > 0) {
                out.write(buf, 0, n);
                if (out.size() > MAX_FILE_BYTES * 2) throw new IllegalStateException("File is larger than 25 MB.");
            }
            raw = out.toByteArray();
        }
        boolean image = (mime != null && mime.startsWith("image/")) || name.toLowerCase(Locale.ROOT).matches(".*\\.(jpg|jpeg|png|webp|heic|bmp)$");
        if (!image) {
            if (raw.length > MAX_FILE_BYTES) throw new IllegalStateException("File is larger than 25 MB.");
            return new Attachments.FileData(raw, name, mime == null ? "application/octet-stream" : mime);
        }
        byte[] jpeg = compress(raw);
        String base = name.contains(".") ? name.substring(0, name.lastIndexOf('.')) : name;
        return new Attachments.FileData(jpeg, base + ".jpg", "image/jpeg");
    }

    static String displayName(Context c, Uri uri) {
        String name = null;
        try (Cursor cur = c.getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (cur != null && cur.moveToFirst()) name = cur.getString(0);
        } catch (Exception ignored) { }
        if (name == null || name.trim().isEmpty()) name = "QCMS_" + System.currentTimeMillis() + ".jpg";
        return name;
    }

    static byte[] compress(byte[] raw) throws Exception {
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeByteArray(raw, 0, raw.length, bounds);
        int sample = 1;
        while (Math.max(bounds.outWidth, bounds.outHeight) / sample > MAX_SIDE * 2) sample *= 2;
        BitmapFactory.Options opts = new BitmapFactory.Options();
        opts.inSampleSize = sample;
        Bitmap bmp = BitmapFactory.decodeByteArray(raw, 0, raw.length, opts);
        if (bmp == null) throw new IllegalStateException("Photo could not be read.");
        float scale = Math.min(1f, MAX_SIDE / (float) Math.max(bmp.getWidth(), bmp.getHeight()));
        int rotation = 0;
        try {
            ExifInterface exif = new ExifInterface(new ByteArrayInputStream(raw));
            int o = exif.getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL);
            rotation = o == ExifInterface.ORIENTATION_ROTATE_90 ? 90 : o == ExifInterface.ORIENTATION_ROTATE_180 ? 180 : o == ExifInterface.ORIENTATION_ROTATE_270 ? 270 : 0;
        } catch (Exception ignored) { }
        if (scale < 1f || rotation != 0) {
            Matrix m = new Matrix();
            m.postScale(scale, scale);
            m.postRotate(rotation);
            Bitmap turned = Bitmap.createBitmap(bmp, 0, 0, bmp.getWidth(), bmp.getHeight(), m, true);
            if (turned != bmp) bmp.recycle();
            bmp = turned;
        }
        try (ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            bmp.compress(Bitmap.CompressFormat.JPEG, 85, out);
            bmp.recycle();
            return out.toByteArray();
        }
    }

    public static Bitmap thumbnail(byte[] data, int maxSide) {
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeByteArray(data, 0, data.length, bounds);
        int sample = 1;
        while (Math.max(bounds.outWidth, bounds.outHeight) / sample > maxSide * 2) sample *= 2;
        BitmapFactory.Options opts = new BitmapFactory.Options();
        opts.inSampleSize = sample;
        return BitmapFactory.decodeByteArray(data, 0, data.length, opts);
    }
}
