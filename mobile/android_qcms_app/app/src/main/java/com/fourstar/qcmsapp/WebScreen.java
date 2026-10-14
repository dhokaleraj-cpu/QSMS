package com.fourstar.qcmsapp;

import android.app.Activity;
import android.app.DownloadManager;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Environment;
import android.provider.MediaStore;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.ProgressBar;

import java.util.Locale;

/**
 * A QCMS website page inside the app (for entry forms whose rules live in QCMS).
 * Supports camera / gallery photo upload and file downloads.
 */
public final class WebScreen extends Screen {
    static final int FILE_CHOOSER = 701;
    private final String title;
    private final String path;
    private WebView web;
    private ValueCallback<Uri[]> fileCallback;
    private Uri cameraUri;

    public WebScreen(MainActivity a, String title, String path) {
        super(a);
        this.title = title;
        this.path = path == null ? "" : path;
    }

    @Override public String title() { return title; }
    @Override public String subtitle() { return "QCMS website · sign in once if asked"; }
    @Override public int tab() {
        String p = path.toLowerCase(Locale.ROOT);
        if (p.startsWith("supply")) return 1;
        if (p.startsWith("calibration") || p.startsWith("reference")) return 3;
        if (p.isEmpty() || p.startsWith("global") || p.startsWith("kpi") || p.startsWith("records") || p.startsWith("reports") || p.startsWith("part")) return 4;
        return 2;
    }

    String url() {
        String base = BuildConfig.QCMS_WEB_URL;
        return path.isEmpty() ? base : base + "/" + path;
    }

    @Override
    public void reload() {
        if (web != null) web.reload();
    }

    @Override
    public boolean onBack() {
        if (web != null && web.canGoBack()) {
            web.goBack();
            return true;
        }
        return false;
    }

    @Override
    public View build() {
        LinearLayout box = Ui.vbox(a);
        ProgressBar progress = new ProgressBar(a, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        box.addView(progress, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(4)));
        web = new WebView(a);
        WebSettings ws = web.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setLoadWithOverviewMode(true);
        ws.setUseWideViewPort(true);
        ws.setAllowFileAccess(false);
        ws.setAllowContentAccess(true);
        ws.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        ws.setUserAgentString(ws.getUserAgentString() + " QCMSNativeApp/" + BuildConfig.VERSION_NAME);
        CookieManager cm = CookieManager.getInstance();
        cm.setAcceptCookie(true);
        cm.setAcceptThirdPartyCookies(web, true);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri target = request.getUrl();
                String scheme = target == null ? "" : String.valueOf(target.getScheme());
                if ("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme)) return false;
                try { a.startActivity(new Intent(Intent.ACTION_VIEW, target)); } catch (Exception ignored) { }
                return true;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                CookieManager.getInstance().flush();
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request != null && request.isForMainFrame()) {
                    String html = "<html><body style='font-family:sans-serif;padding:24px;color:#173233'>"
                        + "<h3 style='color:#0B6E70'>QCMS website is not reachable</h3>"
                        + "<p>No internet, or the QCMS server is waking up (up to a minute after it was idle).</p>"
                        + "<p><a href='" + url() + "' style='display:inline-block;background:#0F8B8D;color:#fff;padding:12px 18px;border-radius:10px;text-decoration:none'>Try again</a></p></body></html>";
                    view.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null);
                }
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int value) {
                progress.setProgress(value);
                progress.setVisibility(value >= 100 ? View.INVISIBLE : View.VISIBLE);
            }

            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                Intent pick = params.createIntent();
                pick.addCategory(Intent.CATEGORY_OPENABLE);
                Intent chooser = Intent.createChooser(pick, "Take photo or choose file");
                cameraUri = null;
                try {
                    ContentValues values = new ContentValues();
                    values.put(MediaStore.Images.Media.DISPLAY_NAME, "QCMS_" + System.currentTimeMillis() + ".jpg");
                    values.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
                    cameraUri = a.getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
                    if (cameraUri != null) {
                        Intent camera = new Intent(MediaStore.ACTION_IMAGE_CAPTURE);
                        camera.putExtra(MediaStore.EXTRA_OUTPUT, cameraUri);
                        camera.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
                        chooser.putExtra(Intent.EXTRA_INITIAL_INTENTS, new Intent[]{camera});
                    }
                } catch (Exception ignored) {
                    cameraUri = null;
                }
                try {
                    a.startActivityForResult(chooser, FILE_CHOOSER);
                    return true;
                } catch (Exception e) {
                    fileCallback = null;
                    a.toast("No camera / file picker available.");
                    return false;
                }
            }
        });

        web.setDownloadListener((url, userAgent, disposition, mime, length) -> {
            try {
                DownloadManager.Request req = new DownloadManager.Request(Uri.parse(url));
                req.setMimeType(mime);
                req.addRequestHeader("User-Agent", userAgent);
                String cookies = CookieManager.getInstance().getCookie(url);
                if (cookies != null) req.addRequestHeader("Cookie", cookies);
                String name = URLUtil.guessFileName(url, disposition, mime);
                req.setTitle(name);
                req.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                req.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name);
                DownloadManager dm = (DownloadManager) a.getSystemService(Context.DOWNLOAD_SERVICE);
                if (dm != null) dm.enqueue(req);
                a.toast("Downloading " + name);
            } catch (Exception e) {
                a.openInBrowser(url);
            }
        });

        box.addView(web, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        web.loadUrl(url());
        return box;
    }

    void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode != FILE_CHOOSER || fileCallback == null) return;
        Uri[] results = null;
        boolean picked = data != null && (data.getData() != null || data.getClipData() != null);
        if (resultCode == Activity.RESULT_OK && !picked && cameraUri != null) {
            results = new Uri[]{cameraUri};
        } else if (cameraUri != null) {
            try { a.getContentResolver().delete(cameraUri, null, null); } catch (Exception ignored) { }
        }
        if (resultCode == Activity.RESULT_OK && picked) {
            if (data.getClipData() != null) {
                int n = data.getClipData().getItemCount();
                results = new Uri[n];
                for (int i = 0; i < n; i++) results[i] = data.getClipData().getItemAt(i).getUri();
            } else {
                results = new Uri[]{data.getData()};
            }
        }
        cameraUri = null;
        fileCallback.onReceiveValue(results);
        fileCallback = null;
    }
}
