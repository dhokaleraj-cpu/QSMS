package com.fourstar.qcms;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.provider.Settings;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

/**
 * QCMS Mobile 0.2.4
 *
 * Single, native navigation architecture based on the proven early QCMS mobile drawer.
 * The menu button + drawer live outside the WebView, therefore Streamlit CSS/DOM changes
 * can never hide or disable Android navigation. Streamlit renders content only.
 */
public class MainActivity extends Activity {
    private static final int FILE_CHOOSER_REQUEST = 701;
    private static final String PREFS = "qcms_mobile";
    private static final String PREF_URL = "qcms_url";
    private static final String MOBILE_USER_AGENT = "QCMSMobile/0.2.4";
    private static final String DEBUG_PACKAGE = "com.fourstar.qcms.test";

    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private SharedPreferences prefs;
    private FrameLayout drawerLayer;
    private String baseUrl = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (android.os.Build.VERSION.SDK_INT >= 21) {
            getWindow().setStatusBarColor(Color.rgb(20, 20, 20));
            getWindow().setNavigationBarColor(Color.BLACK);
        }
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        String url = prefs.getString(PREF_URL, "");
        if (url == null || url.trim().isEmpty()) showSetupScreen(); else showBrowser(url);
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

    private void applySafeInsets(View root) {
        root.setFitsSystemWindows(true);
        final int left = root.getPaddingLeft();
        final int top = root.getPaddingTop();
        final int right = root.getPaddingRight();
        final int bottom = root.getPaddingBottom();
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            if (android.os.Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets safe = insets.getInsets(
                        android.view.WindowInsets.Type.systemBars() | android.view.WindowInsets.Type.displayCutout());
                view.setPadding(left + safe.left, top + safe.top, right + safe.right, bottom + safe.bottom);
            } else {
                view.setPadding(
                        left + insets.getSystemWindowInsetLeft(),
                        top + insets.getSystemWindowInsetTop(),
                        right + insets.getSystemWindowInsetRight(),
                        bottom + insets.getSystemWindowInsetBottom());
            }
            return insets;
        });
    }

    private GradientDrawable rounded(int color, int radiusDp) {
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(color);
        shape.setCornerRadius(dp(radiusDp));
        return shape;
    }

    private void showSetupScreen() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(24), dp(36), dp(24), dp(24));
        root.setBackgroundColor(Color.WHITE);
        applySafeInsets(root);

        ImageView icon = new ImageView(this);
        icon.setImageResource(R.drawable.stawn_icon);
        icon.setScaleType(ImageView.ScaleType.CENTER_CROP);
        root.addView(icon, new LinearLayout.LayoutParams(dp(84), dp(84)));

        TextView title = label("QCMS Mobile", 28, true);
        title.setTextColor(Color.rgb(22, 22, 22));
        root.addView(title);
        root.addView(label("Four Star Industries · Android 0.2.4", 15, false));

        TextView note = label(
                "Enter the HTTPS URL of the live QCMS application. The Android MENU is native and remains available independently of the web page.",
                14, false);
        note.setPadding(0, dp(20), 0, dp(12));
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
            String url = normalizeUrl(urlInput.getText().toString());
            if (url == null) {
                Toast.makeText(this, "Enter a valid HTTPS QCMS URL.", Toast.LENGTH_LONG).show();
                return;
            }
            prefs.edit().putString(PREF_URL, url).apply();
            showBrowser(url);
        });
        setContentView(root);
    }

    private String normalizeUrl(String raw) {
        String value = raw == null ? "" : raw.trim();
        if (value.isEmpty() || !value.startsWith("https://")) return null;
        Uri uri = Uri.parse(value);
        if (uri.getHost() == null || uri.getHost().trim().isEmpty() || uri.getUserInfo() != null) return null;
        return value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
    }

    private Button menuButton() {
        Button b = new Button(this);
        b.setText("MENU");
        b.setTextSize(13);
        b.setTextColor(Color.WHITE);
        b.setAllCaps(false);
        b.setGravity(Gravity.CENTER);
        b.setPadding(dp(8), 0, dp(8), 0);
        b.setBackgroundColor(Color.TRANSPARENT);
        b.setCompoundDrawablesWithIntrinsicBounds(R.drawable.ic_qcms_menu, 0, 0, 0);
        b.setCompoundDrawablePadding(dp(6));
        b.setContentDescription("Open QCMS navigation menu");
        return b;
    }

    private Button iconButton(String text, int textSize) {
        Button b = new Button(this);
        b.setText(text);
        b.setTextSize(textSize);
        b.setTextColor(Color.WHITE);
        b.setAllCaps(false);
        b.setBackgroundColor(Color.TRANSPARENT);
        b.setPadding(0, 0, 0, 0);
        return b;
    }

    private Button drawerChildButton(String label, String path) {
        Button b = new Button(this);
        b.setText("      " + label);
        b.setAllCaps(false);
        b.setTextSize(13);
        b.setTextColor(Color.rgb(55, 55, 55));
        b.setGravity(Gravity.CENTER_VERTICAL | Gravity.START);
        b.setPadding(dp(28), 0, dp(10), 0);
        b.setBackgroundColor(Color.rgb(248, 249, 250));
        b.setOnClickListener(v -> {
            closeDrawer();
            navigate(path);
        });
        return b;
    }

    private View drawerSection(String icon, String label, String landingPath, String[][] children) {
        LinearLayout wrapper = new LinearLayout(this);
        wrapper.setOrientation(LinearLayout.VERTICAL);
        wrapper.setBackgroundColor(Color.WHITE);

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(18), 0, dp(12), 0);
        header.setBackgroundColor(Color.WHITE);

        TextView title = new TextView(this);
        title.setText(icon + "   " + label);
        title.setTextSize(15);
        title.setTextColor(Color.rgb(45, 45, 45));
        title.setGravity(Gravity.CENTER_VERTICAL);

        TextView chevron = new TextView(this);
        chevron.setText(children != null && children.length > 0 ? "⌄" : "›");
        chevron.setTextSize(17);
        chevron.setTextColor(Color.rgb(95, 95, 95));
        chevron.setGravity(Gravity.CENTER);

        header.addView(title, new LinearLayout.LayoutParams(0, dp(52), 1));
        header.addView(chevron, new LinearLayout.LayoutParams(dp(36), dp(52)));
        wrapper.addView(header);

        if (children == null || children.length == 0) {
            header.setOnClickListener(v -> {
                closeDrawer();
                navigate(landingPath);
            });
            return wrapper;
        }

        LinearLayout childrenBox = new LinearLayout(this);
        childrenBox.setOrientation(LinearLayout.VERTICAL);
        childrenBox.setVisibility(View.GONE);
        childrenBox.setBackgroundColor(Color.rgb(248, 249, 250));
        for (String[] child : children) {
            childrenBox.addView(drawerChildButton(child[0], child[1]),
                    new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(46)));
        }
        wrapper.addView(childrenBox);

        header.setOnClickListener(v -> {
            boolean opening = childrenBox.getVisibility() != View.VISIBLE;
            childrenBox.setVisibility(opening ? View.VISIBLE : View.GONE);
            chevron.setText(opening ? "⌃" : "⌄");
        });
        title.setOnLongClickListener(v -> {
            closeDrawer();
            navigate(landingPath);
            return true;
        });
        return wrapper;
    }

    private void showBrowser(String url) {
        baseUrl = normalizeUrl(url);
        if (baseUrl == null) {
            prefs.edit().remove(PREF_URL).apply();
            showSetupScreen();
            return;
        }

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.WHITE);
        applySafeInsets(root);

        LinearLayout main = new LinearLayout(this);
        main.setOrientation(LinearLayout.VERTICAL);
        main.setBackgroundColor(Color.rgb(248, 248, 248));
        root.addView(main, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        // Native top bar: outside WebView, not affected by any CSS, Streamlit rerun or DOM mutation.
        LinearLayout top = new LinearLayout(this);
        top.setId(View.generateViewId());
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.setPadding(dp(2), 0, dp(4), 0);
        top.setBackgroundColor(Color.rgb(122, 23, 52));
        top.setMinimumHeight(dp(52));
        top.setElevation(dp(10));
        top.setVisibility(View.VISIBLE);

        Button hamburger = menuButton();
        top.addView(hamburger, new LinearLayout.LayoutParams(dp(92), dp(52)));

        ImageView logo = new ImageView(this);
        logo.setImageResource(R.drawable.stawn_icon);
        logo.setScaleType(ImageView.ScaleType.CENTER_CROP);
        LinearLayout.LayoutParams lpLogo = new LinearLayout.LayoutParams(dp(32), dp(32));
        lpLogo.setMargins(0, 0, dp(8), 0);
        top.addView(logo, lpLogo);

        TextView title = new TextView(this);
        title.setText("QCMS");
        title.setTextColor(Color.WHITE);
        title.setTextSize(18);
        title.setGravity(Gravity.CENTER_VERTICAL);
        title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        top.addView(title, new LinearLayout.LayoutParams(0, dp(52), 1));

        TextView version = new TextView(this);
        version.setText("0.2.4");
        version.setTextColor(0xFFD8D8D8);
        version.setTextSize(10);
        version.setGravity(Gravity.CENTER);
        top.addView(version, new LinearLayout.LayoutParams(dp(42), dp(52)));

        Button more = iconButton("⋮", 22);
        more.setContentDescription("QCMS mobile options");
        top.addView(more, new LinearLayout.LayoutParams(dp(42), dp(52)));
        main.addView(top, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(52)));

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
        ws.setUserAgentString(ws.getUserAgentString() + " " + MOBILE_USER_AGENT);

        CookieManager cm = CookieManager.getInstance();
        cm.setAcceptCookie(true);
        cm.setAcceptThirdPartyCookies(webView, true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String pageUrl) {
                super.onPageFinished(view, pageUrl);
                CookieManager.getInstance().flush();
                // Native bar stays above the WebView after every load/rerun.
                top.setVisibility(View.VISIBLE);
                top.bringToFront();
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, android.webkit.WebResourceRequest request) {
                Uri target = request.getUrl();
                if (target != null && ("http".equalsIgnoreCase(target.getScheme()) || "https".equalsIgnoreCase(target.getScheme()))) {
                    return false;
                }
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, target));
                } catch (Exception ignored) { }
                return true;
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView w, ValueCallback<Uri[]> cb, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = cb;
                Intent intent = params.createIntent();
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                try {
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                } catch (Exception ex) {
                    fileCallback.onReceiveValue(null);
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
                ((DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(request);
                Toast.makeText(MainActivity.this, "Downloading " + fileName, Toast.LENGTH_SHORT).show();
            } catch (Exception ex) {
                new AlertDialog.Builder(MainActivity.this)
                        .setTitle("Open download in browser")
                        .setMessage("Open QCMS in the phone browser and download again using the same login.")
                        .setPositiveButton("Open QCMS", (d, w) -> startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(baseUrl))))
                        .setNegativeButton("Cancel", null)
                        .show();
            }
        });
        main.addView(webView, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));

        // Native drawer overlay. This is a sibling of the WebView rather than HTML inside it.
        drawerLayer = new FrameLayout(this);
        drawerLayer.setVisibility(View.GONE);
        drawerLayer.setElevation(dp(20));
        root.addView(drawerLayer, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        View drawerScrim = new View(this);
        drawerScrim.setBackgroundColor(0x66000000);
        drawerLayer.addView(drawerScrim, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        drawerScrim.setOnClickListener(v -> closeDrawer());

        ScrollView scroll = new ScrollView(this);
        LinearLayout drawerPanel = new LinearLayout(this);
        drawerPanel.setOrientation(LinearLayout.VERTICAL);
        drawerPanel.setBackgroundColor(Color.WHITE);
        scroll.addView(drawerPanel, new ScrollView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        FrameLayout.LayoutParams dlp = new FrameLayout.LayoutParams(
                (int) (getResources().getDisplayMetrics().widthPixels * 0.86),
                ViewGroup.LayoutParams.MATCH_PARENT);
        dlp.gravity = Gravity.START;
        drawerLayer.addView(scroll, dlp);

        LinearLayout drawerHead = new LinearLayout(this);
        drawerHead.setOrientation(LinearLayout.HORIZONTAL);
        drawerHead.setGravity(Gravity.CENTER_VERTICAL);
        drawerHead.setPadding(dp(18), dp(18), dp(8), dp(14));
        ImageView dIcon = new ImageView(this);
        dIcon.setImageResource(R.drawable.stawn_icon);
        dIcon.setScaleType(ImageView.ScaleType.CENTER_CROP);
        drawerHead.addView(dIcon, new LinearLayout.LayoutParams(dp(46), dp(46)));
        TextView dTitle = label("QCMS\nFour Star Industries", 18, true);
        dTitle.setPadding(dp(12), 0, 0, 0);
        drawerHead.addView(dTitle, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        Button close = new Button(this);
        close.setText("×");
        close.setTextSize(24);
        close.setAllCaps(false);
        close.setBackgroundColor(Color.TRANSPARENT);
        close.setContentDescription("Close QCMS navigation menu");
        close.setOnClickListener(v -> closeDrawer());
        drawerHead.addView(close, new LinearLayout.LayoutParams(dp(44), dp(44)));
        drawerPanel.addView(drawerHead);

        drawerPanel.addView(drawerSection("⌂", "Dashboard", "dashboard", null));
        drawerPanel.addView(drawerSection("▦", "Masters", "masters", new String[][]{
                {"Masters Home", "masters"}, {"Company Branch", "company-branch-entry"}, {"Part Entry", "part-entry"},
                {"Part Records", "part-records"}, {"Process Entry", "process-entry"}, {"Material Grade", "grade-entry"},
                {"Reference Entry", "reference-entry"}, {"Employee Entry", "employee-entry"}, {"Standards Bank", "standards-entry"},
                {"Master Import", "master-import"}}));
        drawerPanel.addView(drawerSection("▣", "Supply Chain", "supply-chain-home", new String[][]{
                {"Supply Chain Home", "supply-chain-home"}, {"Customer Orders", "supply-customer-orders"},
                {"Opening Stock & Import", "supply-opening-stock"}, {"RM Procurement", "supply-rm-procurement"},
                {"Purchase Orders", "supply-purchase-orders"}, {"PO Order List", "supply-po-order-list"},
                {"Edit Purchase Order", "supply-po-edit"}, {"Purchase Order PDF", "supply-po-pdf"},
                {"Approval / Confirmation", "supply-po-approval"}, {"RM Receipt", "supply-rm-receipt"},
                {"RM to Forging", "supply-rm-dispatch"}, {"Forging", "supply-forging"},
                {"Machining / FG / Dispatch", "supply-downstream"}, {"Traceability", "supply-traceability"},
                {"Monthly Schedule / MIS", "supply-order-mis"}}));
        drawerPanel.addView(drawerSection("✓", "RMTC", "rmtc-entry", new String[][]{
                {"RMTC Entry", "rmtc-entry"}, {"Add Part Worksheet", "rmtc-approved-worksheet"},
                {"Part Worksheet", "rmtc-part"}, {"Validation & Decision", "rmtc-approval"}, {"RMTC Reports", "rmtc-report"}}));
        drawerPanel.addView(drawerSection("⇥", "Inward", "inward-entry", new String[][]{
                {"Material Inward", "inward-entry"}, {"MetLAB Report", "metlab-entry"},
                {"Dimensional Report", "dimensional-entry"}, {"Inward Reports", "inward-report"}}));
        drawerPanel.addView(drawerSection("◇", "OSP", "osp-home", new String[][]{
                {"OSP Home", "osp-home"}, {"Material Out", "osp-material-out"}, {"Sample Receipt", "osp-sample-receipt"},
                {"OSP Dimensional", "osp-dimensional"}, {"OSP MetLAB", "osp-metlab"}, {"OSP Inward", "osp-inward"},
                {"OSP Reports", "osp-balance-report"}}));
        drawerPanel.addView(drawerSection("⚙", "Quality / Inspections", "inspection-home", new String[][]{
                {"Inspection Home", "inspection-home"}, {"Inspection Layout", "inspection-layout-entry"},
                {"Layout Records", "inspection-layout-records"}, {"Dimensional Entry", "dimensional-entry"},
                {"MetLAB Entry", "metlab-entry"}, {"Bend Test Entry", "bend-test-entry"},
                {"Dimensional Reports", "dimensional-report"}, {"MetLAB Reports", "metlab-report"}, {"Bend Test Reports", "bend-test-report"}}));
        drawerPanel.addView(drawerSection("↗", "NPD / APQP", "npd-status", new String[][]{
                {"Process Flow Designer", "npd-process-flow"}, {"NPD Status", "npd-status"}, {"APQP", "apqp"},
                {"NPD Reports", "npd-report"}, {"APQP Reports", "apqp-report"}}));
        drawerPanel.addView(drawerSection("!", "Complaints", "complaints-home", new String[][]{
                {"Complaint Dashboard", "complaints-home"}, {"Customer Complaint", "customer-complaint"},
                {"Supplier Complaint", "supplier-complaint"}, {"Customer Register", "customer-complaint-register"},
                {"Supplier Register", "supplier-complaint-register"}, {"Analysis & CAPA", "complaint-analysis"},
                {"Email / Reminders", "complaint-email-settings"}, {"Complaint Reports", "complaints-report"}}));
        drawerPanel.addView(drawerSection("⌕", "Search", "global-search", null));
        drawerPanel.addView(drawerSection("▤", "Records", "records-center", new String[][]{
                {"Records Centre", "records-center"}, {"RMTC Records", "rmtc-records"}, {"Inward Records", "inward-records"},
                {"OSP Records", "osp-records"}, {"Dimensional", "dimensional-records"}, {"MetLAB", "metlab-records"},
                {"Bend Test", "bend-test-records"}, {"Complaints", "complaint-records"}, {"Heat Ledger", "heat-ledger"}}));
        drawerPanel.addView(drawerSection("▥", "Reports", "reports-home", new String[][]{
                {"Reports Home", "reports-home"}, {"Supply Chain MIS", "supply-chain-report"},
                {"Heat Global Balance", "heat-transaction-report"}, {"OSP Heat Balance", "osp-balance-report"},
                {"RMTC", "rmtc-report"}, {"Material Inward", "inward-report"}, {"Dimensional", "dimensional-report"},
                {"MetLAB", "metlab-report"}, {"Complaints", "complaints-report"}, {"Traceability", "traceability-report"}}));
        drawerPanel.addView(drawerSection("⇩", "Templates", "templates", null));
        drawerPanel.addView(drawerSection("⚙", "Admin", "user-access", new String[][]{
                {"Users & Access", "user-access"}, {"Email Server & Notifications", "email-settings"},
                {"Deployment Diagnostics", "deployment-diagnostics"}}));

        setContentView(root);
        top.bringToFront();
        hamburger.setOnClickListener(v -> openDrawer());
        more.setOnClickListener(v -> new AlertDialog.Builder(this)
                .setTitle("QCMS Mobile 0.2.4")
                .setMessage("Package: " + getPackageName() + "\nNavigation: Native V1.2-style drawer")
                .setPositiveButton("Open QCMS in browser", (d, which) -> startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(baseUrl))))
                .setNeutralButton("Change URL", (d, which) -> {
                    prefs.edit().remove(PREF_URL).apply();
                    showSetupScreen();
                })
                .setNegativeButton("Close", null)
                .show());

        webView.loadUrl(nativeUrl(""));
    }

    private String nativeUrl(String path) {
        String p = path == null ? "" : path.trim();
        String target = baseUrl + (p.isEmpty() ? "" : (p.startsWith("/") ? p : "/" + p));
        Uri uri = Uri.parse(target);
        return uri.buildUpon()
                .clearQuery()
                .appendQueryParameter("native_mobile", "1")
                .appendQueryParameter("native_nav", "native")
                .appendQueryParameter("android_build", "0.2.4")
                .build()
                .toString();
    }

    private void navigate(String path) {
        if (webView == null) return;
        String normalizedRoute = path == null ? "dashboard" : path.trim();
        final String route = normalizedRoute.isEmpty() ? "dashboard" : normalizedRoute;
        closeDrawer();
        CookieManager.getInstance().flush();
        webView.loadUrl(nativeUrl(route));
    }

    private void openDrawer() {
        if (drawerLayer != null) {
            drawerLayer.setVisibility(View.VISIBLE);
            drawerLayer.bringToFront();
            drawerLayer.setElevation(dp(20));
        }
    }

    private void closeDrawer() {
        if (drawerLayer != null) drawerLayer.setVisibility(View.GONE);
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
        if (drawerLayer != null && drawerLayer.getVisibility() == View.VISIBLE) {
            closeDrawer();
            return;
        }
        if (webView != null && webView.canGoBack()) webView.goBack(); else super.onBackPressed();
    }
}
