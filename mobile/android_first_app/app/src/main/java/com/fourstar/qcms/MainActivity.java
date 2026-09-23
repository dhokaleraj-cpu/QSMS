package com.fourstar.qcms;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.provider.Settings;
import android.view.Gravity;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

/**
 * QCMS Mobile 1.0.2 — First-App Architecture Recovery.
 *
 * This intentionally restores the original v0.1.0 design: one hardened WebView,
 * one WebView only; QCMS itself owns all page navigation.
 * QCMS itself owns all menus and page navigation, exactly as it does in a normal
 * browser. That removes the later route translation bug where every native menu
 * selection could fall back to Dashboard/Home.
 */
public class MainActivity extends Activity {
    private static final int FILE_CHOOSER_REQUEST = 701;
    private static final String PREFS = "qcms_mobile";
    private static final String PREF_URL = "qcms_url";
    private static final String CLASSIC_UA = "QCMSClassicShell/1.0.2";

    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        String url = sanitizeQcmsUrl(prefs.getString(PREF_URL, ""));
        if (url == null || url.trim().isEmpty()) {
            showSetupScreen();
        } else {
            // Replace any old stored native-mobile URL with a clean classic URL.
            prefs.edit().putString(PREF_URL, url).apply();
            showBrowser(url);
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private TextView label(String text, int sp, boolean bold) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(sp);
        view.setTextColor(Color.rgb(32, 33, 36));
        view.setPadding(0, dp(6), 0, dp(6));
        if (bold) view.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        return view;
    }

    private void showSetupScreen() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(24), dp(32), dp(24), dp(24));
        root.setBackgroundColor(Color.WHITE);

        ImageView icon = new ImageView(this);
        icon.setImageResource(R.drawable.stawn_icon);
        icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        LinearLayout.LayoutParams iconParams = new LinearLayout.LayoutParams(dp(72), dp(72));
        iconParams.gravity = Gravity.CENTER_HORIZONTAL;
        root.addView(icon, iconParams);

        TextView title = label("QCMS Mobile", 28, true);
        title.setTextColor(Color.rgb(122, 23, 52));
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(title);

        TextView sub = label("Four Star Industries • Classic stable app", 14, true);
        sub.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(sub);

        TextView note = label("This recovery build uses the original QCMS Android architecture. The website itself owns the navigation menu and submenus, so menu clicks are not translated by Android and cannot be redirected to Home by a native route map.", 14, false);
        note.setPadding(0, dp(18), 0, dp(12));
        root.addView(note);

        EditText urlInput = new EditText(this);
        urlInput.setHint("https://your-qcms.streamlit.app");
        urlInput.setSingleLine(true);
        urlInput.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_URI);
        root.addView(urlInput, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        Button save = new Button(this);
        save.setText("SAVE & OPEN QCMS");
        save.setAllCaps(false);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.topMargin = dp(18);
        root.addView(save, params);
        save.setOnClickListener(v -> {
            String url = sanitizeQcmsUrl(urlInput.getText().toString());
            if (url == null) {
                Toast.makeText(this, "Enter a valid HTTPS QCMS URL.", Toast.LENGTH_LONG).show();
                return;
            }
            prefs.edit().putString(PREF_URL, url).apply();
            showBrowser(url);
        });

        setContentView(root);
    }

    /**
     * Keep the first-app architecture clean even if a later native build stored
     * route-control query flags left by later wrappers in SharedPreferences.
     */
    private String sanitizeQcmsUrl(String raw) {
        String value = raw == null ? "" : raw.trim();
        if (value.isEmpty() || !value.startsWith("https://")) return null;
        Uri source = Uri.parse(value);
        if (source.getHost() == null || source.getHost().trim().isEmpty()) return null;

        Uri.Builder builder = new Uri.Builder()
            .scheme("https")
            .encodedAuthority(source.getEncodedAuthority())
            .encodedPath(source.getEncodedPath());

        for (String name : source.getQueryParameterNames()) {
            String lower = name == null ? "" : name.toLowerCase(java.util.Locale.ROOT);
            if (lower.equals("native_mobile") || lower.equals("native_nav") || lower.equals("page") ||
                lower.equals("route") || lower.equals("qcms_route") || lower.equals("qcms_native_route")) {
                continue;
            }
            for (String v : source.getQueryParameters(name)) builder.appendQueryParameter(name, v);
        }
        if (source.getFragment() != null) builder.fragment(source.getFragment());
        String clean = builder.build().toString();
        while (clean.endsWith("/") && clean.length() > "https://x".length()) clean = clean.substring(0, clean.length() - 1);
        return clean;
    }

    private void showBrowser(String url) {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.WHITE);

        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(10), dp(4), dp(6), dp(4));
        bar.setBackgroundColor(Color.rgb(122, 23, 52));

        ImageView icon = new ImageView(this);
        icon.setImageResource(R.drawable.stawn_icon);
        icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        LinearLayout.LayoutParams iconParams = new LinearLayout.LayoutParams(dp(40), dp(40));
        iconParams.rightMargin = dp(8);
        bar.addView(icon, iconParams);

        LinearLayout titleWrap = new LinearLayout(this);
        titleWrap.setOrientation(LinearLayout.VERTICAL);
        titleWrap.setGravity(Gravity.CENTER_VERTICAL);
        TextView title = new TextView(this);
        title.setText("QCMS");
        title.setTextColor(Color.WHITE);
        title.setTextSize(18);
        title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        TextView company = new TextView(this);
        company.setText("Four Star Industries");
        company.setTextColor(Color.rgb(238, 238, 238));
        company.setTextSize(11);
        titleWrap.addView(title);
        titleWrap.addView(company);
        bar.addView(titleWrap, new LinearLayout.LayoutParams(0, dp(48), 1));

        Button refresh = new Button(this);
        refresh.setText("↻");
        refresh.setTextSize(18);
        refresh.setTextColor(Color.WHITE);
        refresh.setBackgroundColor(Color.TRANSPARENT);
        bar.addView(refresh, new LinearLayout.LayoutParams(dp(48), dp(48)));

        Button settings = new Button(this);
        settings.setText("⋮");
        settings.setTextSize(22);
        settings.setTextColor(Color.WHITE);
        settings.setBackgroundColor(Color.TRANSPARENT);
        bar.addView(settings, new LinearLayout.LayoutParams(dp(48), dp(48)));

        root.addView(bar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(56)));

        webView = new WebView(this);
        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setDatabaseEnabled(true);
        ws.setSupportZoom(false);
        ws.setBuiltInZoomControls(false);
        ws.setLoadWithOverviewMode(true);
        ws.setUseWideViewPort(true);
        ws.setMediaPlaybackRequiresUserGesture(false);
        ws.setAllowFileAccess(false);
        ws.setAllowContentAccess(true);
        ws.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        // Keep the original browser-owned navigation model. The classic shell uses
        // an ordinary Android WebView user agent plus a non-native diagnostic token.
        ws.setUserAgentString(ws.getUserAgentString() + " " + CLASSIC_UA);

        CookieManager cm = CookieManager.getInstance();
        cm.setAcceptCookie(true);
        cm.setAcceptThirdPartyCookies(webView, true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri target = request.getUrl();
                if (target != null && ("http".equalsIgnoreCase(target.getScheme()) || "https".equalsIgnoreCase(target.getScheme()))) {
                    // Let the WebView/Streamlit router handle the real link. Never
                    // translate menu routes into a native "page" parameter.
                    return false;
                }
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, target));
                    return true;
                } catch (Exception ignored) {
                    return true;
                }
            }

            @Override
            public void onPageFinished(WebView view, String loadedUrl) {
                super.onPageFinished(view, loadedUrl);
                CookieManager.getInstance().flush();
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> filePathCallback, FileChooserParams fileChooserParams) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = filePathCallback;
                Intent intent = fileChooserParams.createIntent();
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                try {
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                } catch (Exception ex) {
                    fileCallback = null;
                    Toast.makeText(MainActivity.this, "No file picker is available.", Toast.LENGTH_LONG).show();
                    return false;
                }
                return true;
            }
        });

        webView.setDownloadListener((downloadUrl, userAgent, contentDisposition, mimeType, contentLength) -> {
            try {
                DownloadManager.Request request = new DownloadManager.Request(Uri.parse(downloadUrl));
                request.setMimeType(mimeType);
                request.addRequestHeader("User-Agent", userAgent);
                String cookies = CookieManager.getInstance().getCookie(downloadUrl);
                if (cookies != null) request.addRequestHeader("Cookie", cookies);
                String fileName = URLUtil.guessFileName(downloadUrl, contentDisposition, mimeType);
                request.setTitle(fileName);
                request.setDescription("QCMS download");
                request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, fileName);
                DownloadManager manager = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
                manager.enqueue(request);
                Toast.makeText(MainActivity.this, "Downloading " + fileName, Toast.LENGTH_SHORT).show();
            } catch (Exception ex) {
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(downloadUrl)));
            }
        });

        root.addView(webView, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(root);

        refresh.setOnClickListener(v -> {
            CookieManager.getInstance().flush();
            webView.reload();
        });
        settings.setOnClickListener(v -> new AlertDialog.Builder(this)
            .setTitle("QCMS Mobile")
            .setItems(new String[]{"Change QCMS URL", "Open current URL in Chrome", "Android WebView settings"}, (dialog, which) -> {
                if (which == 0) {
                    prefs.edit().remove(PREF_URL).apply();
                    showSetupScreen();
                } else if (which == 1) {
                    startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(prefs.getString(PREF_URL, url))));
                } else {
                    startActivity(new Intent(Settings.ACTION_WEBVIEW_SETTINGS));
                }
            }).show());

        webView.loadUrl(url);
    }

    @Override
    protected void onPause() {
        CookieManager.getInstance().flush();
        super.onPause();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_CHOOSER_REQUEST && fileCallback != null) {
            Uri[] results = null;
            if (resultCode == Activity.RESULT_OK && data != null) {
                if (data.getClipData() != null) {
                    int count = data.getClipData().getItemCount();
                    results = new Uri[count];
                    for (int i = 0; i < count; i++) results[i] = data.getClipData().getItemAt(i).getUri();
                } else if (data.getData() != null) {
                    results = new Uri[]{data.getData()};
                }
            }
            fileCallback.onReceiveValue(results);
            fileCallback = null;
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
