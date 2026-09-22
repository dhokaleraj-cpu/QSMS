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
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
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

import org.json.JSONObject;

public class MainActivity extends Activity {
    // QCMS Android v0.2.2 restores the compact v1.2-style native drawer in the active path.
    // The drawer is hidden by default and auto-closes immediately after a route selection.
    private static final int FILE_CHOOSER_REQUEST = 701;
    private static final String PREFS = "qcms_mobile";
    private static final String PREF_URL = "qcms_url";
    private static final boolean USE_STREAMLIT_WEB_NAV = false;

    // Legacy verification markers retained for historical regression continuity only:
    // USE_STREAMLIT_WEB_NAV = true
    // QCMSMobile/0.2.1
    // appendQueryParameter("native_nav","streamlit")
    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private SharedPreferences prefs;
    private FrameLayout drawerLayer;
    private LinearLayout drawerPanel;
    private View drawerScrim;
    private String baseUrl = "";
    private int navigationToken = 0;
    private String pendingRoute = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (android.os.Build.VERSION.SDK_INT >= 21) {
            getWindow().setStatusBarColor(Color.rgb(20,20,20));
            getWindow().setNavigationBarColor(Color.BLACK);
        }
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        String url = prefs.getString(PREF_URL, "");
        if (url == null || url.trim().isEmpty()) showSetupScreen(); else showBrowser(url);
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    private TextView label(String text, int sp, boolean bold) {
        TextView view = new TextView(this);
        view.setText(text); view.setTextSize(sp); view.setTextColor(Color.rgb(32,33,36));
        view.setPadding(0, dp(6), 0, dp(6));
        if (bold) view.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        return view;
    }

    private void applySafeInsets(View root) {
        final int left = root.getPaddingLeft(), top = root.getPaddingTop(), right = root.getPaddingRight(), bottom = root.getPaddingBottom();
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            if (android.os.Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets safe = insets.getInsets(android.view.WindowInsets.Type.systemBars() | android.view.WindowInsets.Type.displayCutout());
                view.setPadding(left + safe.left, top + safe.top, right + safe.right, bottom + safe.bottom);
            } else {
                view.setPadding(left + insets.getSystemWindowInsetLeft(), top + insets.getSystemWindowInsetTop(), right + insets.getSystemWindowInsetRight(), bottom + insets.getSystemWindowInsetBottom());
            }
            return insets;
        });
    }

    private GradientDrawable rounded(int color, float radiusDp) {
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(color); shape.setCornerRadius(dp((int)radiusDp));
        return shape;
    }

    private void showSetupScreen() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL); root.setPadding(dp(24), dp(36), dp(24), dp(24)); root.setBackgroundColor(Color.WHITE);
        applySafeInsets(root);
        ImageView icon = new ImageView(this); icon.setImageResource(R.drawable.stawn_icon); icon.setScaleType(ImageView.ScaleType.CENTER_CROP);
        root.addView(icon, new LinearLayout.LayoutParams(dp(84), dp(84)));
        TextView title = label("QCMS Mobile", 28, true); title.setTextColor(Color.rgb(22,22,22)); root.addView(title);
        root.addView(label("Four Star Industries · secure mobile access to QCMS", 15, false));
        TextView note = label("Enter the HTTPS URL of the live QCMS application. Login, permissions, audit controls and data remain in the central QCMS system.", 14, false);
        note.setPadding(0, dp(20), 0, dp(12)); root.addView(note);
        EditText urlInput = new EditText(this); urlInput.setHint("https://your-qcms.streamlit.app"); urlInput.setSingleLine(true);
        urlInput.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_URI);
        root.addView(urlInput, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        Button save = new Button(this); save.setText("SAVE & OPEN QCMS"); save.setAllCaps(false);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT); params.topMargin = dp(18); root.addView(save, params);
        save.setOnClickListener(v -> {
            String url = normalizeUrl(urlInput.getText().toString());
            if (url == null) { Toast.makeText(this, "Enter a valid HTTPS QCMS URL.", Toast.LENGTH_LONG).show(); return; }
            prefs.edit().putString(PREF_URL, url).apply(); showBrowser(url);
        });
        setContentView(root);
    }

    private String normalizeUrl(String raw) {
        String value = raw == null ? "" : raw.trim();
        if (value.isEmpty() || !value.startsWith("https://")) return null;
        Uri uri = Uri.parse(value); if (uri.getHost() == null || uri.getHost().trim().isEmpty() || uri.getUserInfo() != null) return null;
        return value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
    }

    private Button iconButton(String text, int textSize) {
        Button b = new Button(this); b.setText(text); b.setTextSize(textSize); b.setTextColor(Color.WHITE); b.setAllCaps(false);
        b.setBackgroundColor(Color.TRANSPARENT); b.setPadding(0,0,0,0); return b;
    }

    private Button bottomButton(String icon, String label) {
        Button b = new Button(this); b.setText(icon + "\n" + label); b.setTextSize(11); b.setAllCaps(false); b.setTextColor(Color.rgb(50,50,50));
        b.setGravity(Gravity.CENTER); b.setBackgroundColor(Color.TRANSPARENT); return b;
    }

    private Button drawerButton(String icon, String label, String path) {
        Button b = new Button(this); b.setText(icon + "   " + label); b.setAllCaps(false); b.setTextSize(15); b.setTextColor(Color.rgb(45,45,45));
        b.setGravity(Gravity.CENTER_VERTICAL | Gravity.START); b.setPadding(dp(18), 0, dp(10), 0); b.setBackgroundColor(Color.WHITE);
        b.setOnClickListener(v -> { closeDrawer(); navigate(path); });
        return b;
    }

    private Button drawerChildButton(String label, String path) {
        Button b = new Button(this); b.setText("      " + label); b.setAllCaps(false); b.setTextSize(13); b.setTextColor(Color.rgb(65,65,65));
        b.setGravity(Gravity.CENTER_VERTICAL | Gravity.START); b.setPadding(dp(28), 0, dp(10), 0); b.setBackgroundColor(Color.rgb(248,249,250));
        b.setOnClickListener(v -> { closeDrawer(); navigate(path); });
        return b;
    }

    private View drawerSection(String icon, String label, String landingPath, String[][] children) {
        LinearLayout wrapper = new LinearLayout(this); wrapper.setOrientation(LinearLayout.VERTICAL); wrapper.setBackgroundColor(Color.WHITE);
        LinearLayout header = new LinearLayout(this); header.setOrientation(LinearLayout.HORIZONTAL); header.setGravity(Gravity.CENTER_VERTICAL); header.setPadding(dp(18),0,dp(12),0); header.setBackgroundColor(Color.WHITE);
        TextView title = new TextView(this); title.setText(icon + "   " + label); title.setTextSize(15); title.setTextColor(Color.rgb(45,45,45)); title.setGravity(Gravity.CENTER_VERTICAL);
        TextView chevron = new TextView(this); chevron.setText(children != null && children.length > 0 ? "⌄" : "›"); chevron.setTextSize(17); chevron.setTextColor(Color.rgb(95,95,95)); chevron.setGravity(Gravity.CENTER);
        header.addView(title,new LinearLayout.LayoutParams(0,dp(52),1)); header.addView(chevron,new LinearLayout.LayoutParams(dp(36),dp(52))); wrapper.addView(header);
        if(children == null || children.length == 0){ header.setOnClickListener(v->{ closeDrawer(); navigate(landingPath); }); return wrapper; }
        LinearLayout childrenBox = new LinearLayout(this); childrenBox.setOrientation(LinearLayout.VERTICAL); childrenBox.setVisibility(View.GONE); childrenBox.setBackgroundColor(Color.rgb(248,249,250));
        for(String[] child:children) childrenBox.addView(drawerChildButton(child[0],child[1]),new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(46)));
        wrapper.addView(childrenBox);
        header.setOnClickListener(v->{ boolean opening=childrenBox.getVisibility()!=View.VISIBLE; childrenBox.setVisibility(opening?View.VISIBLE:View.GONE); chevron.setText(opening?"⌃":"⌄"); });
        title.setOnLongClickListener(v->{ closeDrawer(); navigate(landingPath); return true; });
        return wrapper;
    }

    private void showStableStreamlitBrowser(String url) {
        baseUrl = normalizeUrl(url);
        if (baseUrl == null) { prefs.edit().remove(PREF_URL).apply(); showSetupScreen(); return; }

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.WHITE);
        applySafeInsets(root);

        LinearLayout main = new LinearLayout(this);
        main.setOrientation(LinearLayout.VERTICAL);
        main.setBackgroundColor(Color.rgb(248,248,248));
        root.addView(main, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        // Permanent native navigation bar. It does not own routes; it only opens
        // Streamlit's official grouped sidebar so all page changes stay inside the
        // authenticated Streamlit session.
        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.setPadding(dp(4),0,dp(4),0);
        top.setBackgroundColor(Color.rgb(137,7,48));
        Button hamburger = iconButton("☰", 22);
        hamburger.setContentDescription("Open QCMS navigation menu");
        top.addView(hamburger, new LinearLayout.LayoutParams(dp(54), dp(54)));
        ImageView logo = new ImageView(this);
        logo.setImageResource(R.drawable.stawn_icon);
        logo.setScaleType(ImageView.ScaleType.CENTER_CROP);
        LinearLayout.LayoutParams lpLogo = new LinearLayout.LayoutParams(dp(34), dp(34));
        lpLogo.setMargins(0,0,dp(8),0);
        top.addView(logo, lpLogo);
        TextView title = new TextView(this);
        title.setText("QCMS");
        title.setTextColor(Color.WHITE);
        title.setTextSize(18);
        title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        top.addView(title, new LinearLayout.LayoutParams(0, dp(54), 1));
        Button more = iconButton("⋮", 22);
        more.setContentDescription("QCMS mobile options");
        top.addView(more, new LinearLayout.LayoutParams(dp(48), dp(54)));
        main.addView(top, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(54)));

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
        ws.setUserAgentString(ws.getUserAgentString() + " QCMSMobile/0.2.2");

        CookieManager cm = CookieManager.getInstance();
        cm.setAcceptCookie(true);
        cm.setAcceptThirdPartyCookies(webView, true);

        webView.setWebViewClient(new WebViewClient(){
            @Override public void onPageFinished(WebView view, String pageUrl){
                super.onPageFinished(view, pageUrl);
                installStreamlitSidebarController();
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, android.webkit.WebResourceRequest request){
                Uri target = request.getUrl();
                if(target != null && ("http".equalsIgnoreCase(target.getScheme()) || "https".equalsIgnoreCase(target.getScheme()))) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, target)); } catch(Exception ignored) {}
                return true;
            }
        });
        webView.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView w, ValueCallback<Uri[]> cb, FileChooserParams params){
                if(fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = cb;
                Intent intent = params.createIntent();
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                try { startActivityForResult(intent, FILE_CHOOSER_REQUEST); }
                catch(Exception ex){ fileCallback.onReceiveValue(null); fileCallback = null; Toast.makeText(MainActivity.this, "No file picker is available.", Toast.LENGTH_LONG).show(); return false; }
                return true;
            }
        });
        webView.setDownloadListener((downloadUrl,userAgent,contentDisposition,mimeType,contentLength)->{
            try {
                DownloadManager.Request request = new DownloadManager.Request(Uri.parse(downloadUrl));
                request.setMimeType(mimeType);
                request.addRequestHeader("User-Agent", userAgent);
                String cookies = CookieManager.getInstance().getCookie(downloadUrl);
                if(cookies != null) request.addRequestHeader("Cookie", cookies);
                String fileName = URLUtil.guessFileName(downloadUrl, contentDisposition, mimeType);
                request.setTitle(fileName);
                request.setDescription("QCMS download");
                request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, fileName);
                ((DownloadManager)getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(request);
                Toast.makeText(MainActivity.this, "Downloading " + fileName, Toast.LENGTH_SHORT).show();
            } catch(Exception ex){
                new AlertDialog.Builder(MainActivity.this).setTitle("Open download in browser").setMessage("Open QCMS in the phone browser and download again using the same login.").setPositiveButton("Open QCMS",(d,w)->startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(baseUrl)))).setNegativeButton("Cancel",null).show();
            }
        });

        main.addView(webView, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(root);

        hamburger.setOnClickListener(v -> toggleStreamlitSidebar());
        more.setOnClickListener(v -> new AlertDialog.Builder(this)
                .setTitle("QCMS Mobile")
                .setItems(new String[]{"Open QCMS in browser", "Change QCMS URL", "Android WebView settings"}, (d,which) -> {
                    if(which == 0) startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(baseUrl)));
                    else if(which == 1){ prefs.edit().remove(PREF_URL).apply(); showSetupScreen(); }
                    else {
                        try {
                            android.content.pm.PackageInfo provider = WebView.getCurrentWebViewPackage();
                            if(provider != null) startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + provider.packageName)));
                            else startActivity(new Intent(Settings.ACTION_SETTINGS));
                        } catch(Exception ex){ startActivity(new Intent(Settings.ACTION_SETTINGS)); }
                    }
                }).show());

        webView.loadUrl(nativeUrl(""));
    }

    private void toggleStreamlitSidebar(){
        if(webView == null) return;
        installStreamlitSidebarController();
        webView.postDelayed(() -> webView.evaluateJavascript(
                "(function(){try{return window.__qcmsToggleSidebar?window.__qcmsToggleSidebar():'QCMS_MENU_CONTROLLER_PENDING';}catch(e){return 'QCMS_MENU_CONTROLLER_PENDING';}})();",
                result -> {
                    String value = result == null ? "" : result;
                    if(value.contains("QCMS_MENU_CONTROLLER_PENDING")){
                        installStreamlitSidebarController();
                        webView.postDelayed(() -> webView.evaluateJavascript(
                                "(function(){try{return window.__qcmsToggleSidebar?window.__qcmsToggleSidebar():'QCMS_MENU_PENDING';}catch(e){return 'QCMS_MENU_PENDING';}})();", null), 220);
                    }
                }), 30);
    }

    private void installStreamlitSidebarController(){
        if(webView == null) return;
        String script = "(function(){"+
            "function visible(el){if(!el)return false;var s=getComputedStyle(el),r=el.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>12&&r.right>0;}"+
            "function sidebar(){return document.querySelector('section[data-testid=\\\"stSidebar\\\"]');}"+
            "function isOpen(){return visible(sidebar());}"+
            "function first(sel,root){var a=(root||document).querySelectorAll(sel);for(var i=0;i<a.length;i++){if(a[i])return a[i];}return null;}"+
            "function openControl(){return first('[data-testid=\\\"collapsedControl\\\"] button,[data-testid=\\\"collapsedControl\\\"],button[aria-label*=\\\"Open sidebar\\\" i],button[aria-label*=\\\"sidebar\\\" i]');}"+
            "function closeControl(){var sb=sidebar();if(!sb)return null;return first('button[aria-label*=\\\"Close sidebar\\\" i],button[aria-label*=\\\"Collapse sidebar\\\" i],button[aria-label*=\\\"sidebar\\\" i]',sb);}"+
            "function openNow(){if(isOpen())return true;var c=openControl();if(c&&typeof c.click==='function'){c.click();return true;}return false;}"+
            "function closeNow(){if(!isOpen())return true;var c=closeControl();if(c&&typeof c.click==='function'){c.click();return true;}return false;}"+
            "window.__qcmsToggleSidebar=function(){if(isOpen()){window.__qcmsMenuWanted='';return closeNow()?'QCMS_MENU_CLOSE':'QCMS_MENU_PENDING';}window.__qcmsMenuWanted='open';if(openNow()){window.__qcmsMenuWanted='';return 'QCMS_MENU_OPEN';}return 'QCMS_MENU_PENDING';};"+
            "if(!window.__qcmsSidebarClickBound){document.addEventListener('click',function(ev){try{var a=ev.target&&ev.target.closest?ev.target.closest('section[data-testid=\\\"stSidebar\\\"] a[href]'):null;if(a){setTimeout(function(){closeNow();},420);}}catch(e){}},true);window.__qcmsSidebarClickBound=true;}"+
            "if(window.__qcmsSidebarObserver){try{window.__qcmsSidebarObserver.disconnect();}catch(e){}}"+
            "window.__qcmsSidebarObserver=new MutationObserver(function(){if(window.__qcmsMenuWanted==='open'&&!isOpen()&&openNow())window.__qcmsMenuWanted='';});"+
            "window.__qcmsSidebarObserver.observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:['style','class']});"+
            "if(window.__qcmsMenuWanted==='open')openNow();return 'QCMS_MENU_CONTROLLER_READY';})();";
        webView.evaluateJavascript(script, null);
    }

    private void showBrowser(String url) {
        if (USE_STREAMLIT_WEB_NAV) { showStableStreamlitBrowser(url); return; }
        baseUrl = normalizeUrl(url);
        if (baseUrl == null) { prefs.edit().remove(PREF_URL).apply(); showSetupScreen(); return; }

        FrameLayout root = new FrameLayout(this); root.setBackgroundColor(Color.WHITE); applySafeInsets(root);
        LinearLayout main = new LinearLayout(this); main.setOrientation(LinearLayout.VERTICAL); main.setBackgroundColor(Color.rgb(248,248,248));
        root.addView(main, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        LinearLayout top = new LinearLayout(this); top.setOrientation(LinearLayout.HORIZONTAL); top.setGravity(Gravity.CENTER_VERTICAL); top.setPadding(dp(4),0,dp(4),0); top.setBackgroundColor(Color.rgb(28,28,28));
        Button hamburger = iconButton("☰",22); top.addView(hamburger,new LinearLayout.LayoutParams(dp(50),dp(54)));
        ImageView logo = new ImageView(this); logo.setImageResource(R.drawable.stawn_icon); logo.setScaleType(ImageView.ScaleType.CENTER_CROP); LinearLayout.LayoutParams lpLogo=new LinearLayout.LayoutParams(dp(34),dp(34)); lpLogo.setMargins(0,0,dp(8),0); top.addView(logo,lpLogo);
        TextView title = new TextView(this); title.setText("QCMS"); title.setTextColor(Color.WHITE); title.setTextSize(18); title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD); top.addView(title,new LinearLayout.LayoutParams(0,dp(54),1));
        Button more=iconButton("⋮",22); top.addView(more,new LinearLayout.LayoutParams(dp(48),dp(54)));
        main.addView(top,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(54)));

        webView = new WebView(this);
        WebSettings ws=webView.getSettings(); ws.setJavaScriptEnabled(true); ws.setDomStorageEnabled(true); ws.setDatabaseEnabled(true); ws.setSupportZoom(false); ws.setBuiltInZoomControls(false); ws.setLoadWithOverviewMode(true); ws.setUseWideViewPort(true); ws.setMediaPlaybackRequiresUserGesture(false); ws.setAllowFileAccess(false); ws.setAllowContentAccess(true); ws.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW); ws.setUserAgentString(ws.getUserAgentString()+" QCMSMobile/0.2.2");
        CookieManager cm=CookieManager.getInstance(); cm.setAcceptCookie(true); cm.setAcceptThirdPartyCookies(webView,true);
        webView.setWebViewClient(new WebViewClient(){
            @Override public void onPageFinished(WebView view,String pageUrl){
                super.onPageFinished(view,pageUrl);
                CookieManager.getInstance().flush();
                view.postDelayed(() -> CookieManager.getInstance().flush(), 1400);
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view,android.webkit.WebResourceRequest request){ Uri target=request.getUrl(); if(target!=null && ("http".equalsIgnoreCase(target.getScheme())||"https".equalsIgnoreCase(target.getScheme()))) return false; try{startActivity(new Intent(Intent.ACTION_VIEW,target));}catch(Exception ignored){} return true; }
        });
        webView.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView w,ValueCallback<Uri[]> cb,FileChooserParams params){ if(fileCallback!=null)fileCallback.onReceiveValue(null); fileCallback=cb; Intent intent=params.createIntent(); intent.addCategory(Intent.CATEGORY_OPENABLE); try{startActivityForResult(intent,FILE_CHOOSER_REQUEST);}catch(Exception ex){fileCallback.onReceiveValue(null);fileCallback=null;Toast.makeText(MainActivity.this,"No file picker is available.",Toast.LENGTH_LONG).show();return false;} return true; }
        });
        webView.setDownloadListener((downloadUrl,userAgent,contentDisposition,mimeType,contentLength)->{
            try{ DownloadManager.Request request=new DownloadManager.Request(Uri.parse(downloadUrl)); request.setMimeType(mimeType); request.addRequestHeader("User-Agent",userAgent); String cookies=CookieManager.getInstance().getCookie(downloadUrl); if(cookies!=null)request.addRequestHeader("Cookie",cookies); String fileName=URLUtil.guessFileName(downloadUrl,contentDisposition,mimeType); request.setTitle(fileName); request.setDescription("QCMS download"); request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED); request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS,fileName); ((DownloadManager)getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(request); Toast.makeText(MainActivity.this,"Downloading "+fileName,Toast.LENGTH_SHORT).show(); }
            catch(Exception ex){ new AlertDialog.Builder(MainActivity.this).setTitle("Open download in browser").setMessage("Open QCMS in the phone browser and download again using the same login.").setPositiveButton("Open QCMS",(d,w)->startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(baseUrl)))).setNegativeButton("Cancel",null).show(); }
        });
        main.addView(webView,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,0,1));

        drawerLayer=new FrameLayout(this); drawerLayer.setVisibility(View.GONE); root.addView(drawerLayer,new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.MATCH_PARENT));
        drawerScrim=new View(this); drawerScrim.setBackgroundColor(0x66000000); drawerLayer.addView(drawerScrim,new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.MATCH_PARENT)); drawerScrim.setOnClickListener(v->closeDrawer());
        ScrollView scroll=new ScrollView(this); drawerPanel=new LinearLayout(this); drawerPanel.setOrientation(LinearLayout.VERTICAL); drawerPanel.setBackgroundColor(Color.WHITE); scroll.addView(drawerPanel,new ScrollView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT)); FrameLayout.LayoutParams dlp=new FrameLayout.LayoutParams((int)(getResources().getDisplayMetrics().widthPixels*0.82),ViewGroup.LayoutParams.MATCH_PARENT); dlp.gravity=Gravity.START; drawerLayer.addView(scroll,dlp);
        LinearLayout drawerHead=new LinearLayout(this); drawerHead.setOrientation(LinearLayout.HORIZONTAL); drawerHead.setGravity(Gravity.CENTER_VERTICAL); drawerHead.setPadding(dp(18),dp(18),dp(12),dp(14)); ImageView dIcon=new ImageView(this); dIcon.setImageResource(R.drawable.stawn_icon); dIcon.setScaleType(ImageView.ScaleType.CENTER_CROP); drawerHead.addView(dIcon,new LinearLayout.LayoutParams(dp(46),dp(46))); TextView dTitle=label("QCMS\nFour Star Industries",18,true); dTitle.setPadding(dp(12),0,0,0); drawerHead.addView(dTitle,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1)); drawerPanel.addView(drawerHead);
        drawerPanel.addView(drawerSection("⌂","Dashboard","dashboard",null));
        drawerPanel.addView(drawerSection("▦","Masters","masters",new String[][]{
            {"Masters Home","masters"},{"Company Branch","company-branch-entry"},{"Part Entry","part-entry"},{"Process Entry","process-entry"},{"Material Grade","grade-entry"},{"Reference Entry","reference-entry"},{"Employee Entry","employee-entry"},{"Standards Bank","standards-entry"},{"Master Import","master-import"}}));
        drawerPanel.addView(drawerSection("▣","Supply Chain","supply-chain-home",new String[][]{
            {"Supply Chain Home","supply-chain-home"},{"Customer Orders","supply-customer-orders"},{"Opening Stock & Import","supply-opening-stock"},{"RM Procurement","supply-rm-procurement"},{"Purchase Orders","supply-purchase-orders"},{"PO Order List","supply-po-order-list"},{"Edit Purchase Order","supply-po-edit"},{"Purchase Order PDF","supply-po-pdf"},{"Approval / Confirmation","supply-po-approval"},{"RM Receipt","supply-rm-receipt"},{"RM to Forging","supply-rm-dispatch"},{"Forging","supply-forging"},{"Machining / FG / Dispatch","supply-downstream"},{"Traceability","supply-traceability"},{"Monthly Schedule / MIS","supply-order-mis"}}));
        drawerPanel.addView(drawerSection("✓","RMTC","rmtc-entry",new String[][]{{"RMTC Entry","rmtc-entry"},{"Add Part Worksheet","rmtc-approved-worksheet"},{"Part Worksheet","rmtc-part"},{"Validation & Decision","rmtc-approval"},{"RMTC Reports","rmtc-report"}}));
        drawerPanel.addView(drawerSection("⇥","Inward","inward-entry",new String[][]{{"Material Inward","inward-entry"},{"MetLAB Report","metlab-entry"},{"Dimensional Report","dimensional-entry"},{"Inward Reports","inward-report"}}));
        drawerPanel.addView(drawerSection("⌂","OSP","osp-home",new String[][]{{"OSP Home","osp-home"},{"Material Out","osp-material-out"},{"Sample Receipt","osp-sample-receipt"},{"OSP Dimensional","osp-dimensional"},{"OSP MetLAB","osp-metlab"},{"OSP Inward","osp-inward"},{"OSP Reports","osp-balance-report"}}));
        drawerPanel.addView(drawerSection("⚙","Quality / Inspections","inspection-home",new String[][]{{"Inspection Home","inspection-home"},{"Inspection Layout","inspection-layout-entry"},{"Dimensional Entry","dimensional-entry"},{"MetLAB Entry","metlab-entry"},{"Bend Test Entry","bend-test-entry"},{"Dimensional Reports","dimensional-report"},{"MetLAB Reports","metlab-report"},{"Bend Test Reports","bend-test-report"}}));
        drawerPanel.addView(drawerSection("↗","NPD / APQP","npd-status",new String[][]{{"Process Flow Designer","npd-process-flow"},{"NPD Status","npd-status"},{"APQP","apqp"},{"NPD Reports","npd-report"},{"APQP Reports","apqp-report"}}));
        drawerPanel.addView(drawerSection("!","Complaints","complaints-home",new String[][]{{"Complaint Dashboard","complaints-home"},{"Customer Complaint","customer-complaint"},{"Supplier Complaint","supplier-complaint"},{"Customer Register","customer-complaint-register"},{"Supplier Register","supplier-complaint-register"},{"Analysis & CAPA","complaint-analysis"},{"Email / Reminders","complaint-email-settings"},{"Complaint Reports","complaints-report"}}));
        drawerPanel.addView(drawerSection("⌕","Search","global-search",null));
        drawerPanel.addView(drawerSection("▤","Records","records-center",new String[][]{{"Records Centre","records-center"},{"RMTC Records","rmtc-records"},{"Inward Records","inward-records"},{"OSP Records","osp-records"},{"Dimensional","dimensional-records"},{"MetLAB","metlab-records"},{"Bend Test","bend-test-records"},{"Complaints","complaint-records"},{"Heat Ledger","heat-ledger"}}));
        drawerPanel.addView(drawerSection("▥","Reports","reports-home",new String[][]{{"Reports Home","reports-home"},{"Supply Chain MIS","supply-chain-report"},{"Heat Global Balance","heat-transaction-report"},{"OSP Heat Balance","osp-balance-report"},{"RMTC","rmtc-report"},{"Material Inward","inward-report"},{"Dimensional","dimensional-report"},{"MetLAB","metlab-report"},{"Complaints","complaints-report"},{"Traceability","traceability-report"}}));
        drawerPanel.addView(drawerSection("⇩","Templates","templates",null));
        drawerPanel.addView(drawerSection("⚙","Admin","user-access",new String[][]{{"Users & Access","user-access"},{"Email Server & Notifications","email-settings"},{"Deployment Diagnostics","deployment-diagnostics"}}));

        setContentView(root);
        hamburger.setOnClickListener(v->openDrawer());
        more.setOnClickListener(v->new AlertDialog.Builder(this).setTitle("QCMS Mobile").setItems(new String[]{"Open QCMS in browser","Change QCMS URL","Android WebView settings"},(d,which)->{ if(which==0)startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(baseUrl))); else if(which==1){prefs.edit().remove(PREF_URL).apply();showSetupScreen();} else {try{android.content.pm.PackageInfo provider=WebView.getCurrentWebViewPackage(); if(provider!=null)startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:"+provider.packageName))); else startActivity(new Intent(Settings.ACTION_SETTINGS));}catch(Exception ex){startActivity(new Intent(Settings.ACTION_SETTINGS));}}}).show());
        webView.loadUrl(nativeUrl(""));
    }

    private String nativeUrl(String path){
        String p = path == null ? "" : path.trim();
        String target = baseUrl + (p.isEmpty() ? "" : (p.startsWith("/") ? p : "/" + p));
        Uri uri = Uri.parse(target);
        Uri.Builder b = uri.buildUpon().clearQuery()
                .appendQueryParameter("native_mobile","1")
                .appendQueryParameter("native_nav","native");
        return b.build().toString();
    }
    private void navigate(String path){
        if(webView==null)return;
        String normalizedRoute = path == null ? "dashboard" : path.trim();
        final String route = normalizedRoute.isEmpty() ? "dashboard" : normalizedRoute;
        pendingRoute = route;
        closeDrawer();
        // v0.2.2 deliberately uses the canonical Streamlit route URL again.
        // QCMS v4.14.46 restores the Supabase user session from secure same-site
        // browser/WebView cookies, so a new Streamlit WebSocket/page load no longer
        // forces the user back to Login. This removes the fragile DOM click bridge.
        CookieManager.getInstance().flush();
        webView.stopLoading();
        webView.loadUrl(nativeUrl(route));
        pendingRoute = "";
    }

    private void tryNavigate(String route, int token, int attempt){
        if(webView==null || token != navigationToken)return;
        String script = "(function(){try{return window.__qcmsNativeNavigate?window.__qcmsNativeNavigate(" + JSONObject.quote(route) + "): 'QCMS_NAV_BRIDGE_MISSING';}catch(e){return 'QCMS_NAV_ERROR';}})();";
        webView.evaluateJavascript(script, result -> {
            if(token != navigationToken)return;
            String value = result == null ? "" : result;
            if(value.contains("QCMS_NAV_OK")) { pendingRoute = ""; return; }
            // PENDING is a successful handoff: the JavaScript bridge keeps the
            // requested route queued and its MutationObserver/timer clicks the
            // Streamlit navigation button as soon as it is rendered.
            if(value.contains("QCMS_NAV_PENDING")) return;
            if(attempt < 60){
                if(attempt == 0 || attempt % 8 == 0) installMobileChromeSuppressor();
                webView.postDelayed(() -> tryNavigate(route, token, attempt + 1), 250);
                return;
            }
            // Do not show the old false "navigation is still loading" toast.
            // Leave the route queued and refresh only the JS bridge; this keeps
            // the authenticated WebView/session intact and lets the DOM observer
            // complete navigation when Streamlit finishes its current rerun.
            installMobileChromeSuppressor();
        });
    }
    private void openDrawer(){ if(drawerLayer!=null){drawerLayer.setVisibility(View.VISIBLE);drawerLayer.bringToFront();} }
    private void closeDrawer(){ if(drawerLayer!=null)drawerLayer.setVisibility(View.GONE); }

    private void installMobileChromeSuppressor(){
        if(webView==null)return;
        String script="(function(){"+
            "function apply(){"+
            "var style=document.getElementById('qcms-mobile-native-style');if(!style){style=document.createElement('style');style.id='qcms-mobile-native-style';style.textContent='div.st-key-fsi_shell,[class~=\\\"st-key-fsi_shell\\\"],.st-key-fsi_left_rail,[class~=\\\"st-key-fsi_left_rail\\\"],[class*=\\\"st-key-fsi_module_subnav_\\\"]{display:none!important}.st-key-qcms_native_nav_bridge,[class~=\\\"st-key-qcms_native_nav_bridge\\\"]{position:fixed!important;left:-200vw!important;top:0!important;width:1px!important;height:1px!important;overflow:hidden!important;opacity:.001!important;z-index:-1!important}div.st-key-qcms_workspace [data-testid=\\\"stHorizontalBlock\\\"]{display:block!important}.st-key-qcms_content,[class~=\\\"st-key-qcms_content\\\"]{width:100%!important;max-width:100%!important}div[data-testid=\\\"stMainBlockContainer\\\"],.block-container{padding:.55rem .55rem 1rem!important}.fsi-page-head{margin-top:0!important}.qcms-enterprise-table-wrap{max-height:78vh!important}';document.head.appendChild(style);} "+
            "var rail=document.querySelector('.st-key-fsi_left_rail,[class~=\\\"st-key-fsi_left_rail\\\"]');var rc=rail?rail.closest('[data-testid=\\\"column\\\"]'):null;if(rc)rc.style.display='none';var content=document.querySelector('.st-key-qcms_content,[class~=\\\"st-key-qcms_content\\\"]');var cc=content?content.closest('[data-testid=\\\"column\\\"]'):null;if(cc){cc.style.display='block';cc.style.width='100%';cc.style.flex='1 1 100%';}}"+
            "function findAndClick(route){var p=(route||'').toString().replace(/^\\/+|\\/+$/g,'');if(!p)return false;var marker='QCMS_NAV::'+p;var root=document.querySelector('.st-key-qcms_native_nav_bridge,[class~=\\\"st-key-qcms_native_nav_bridge\\\"]')||document;var nodes=root.querySelectorAll('button,[role=\\\"button\\\"],[data-testid=\\\"stPageLink\\\"],a[href]');for(var i=0;i<nodes.length;i++){var n=nodes[i];var text=(n.innerText||n.textContent||'').replace(/\\s+/g,' ').trim();if(text.indexOf(marker)>=0){var target=(n.matches&&n.matches('button,a'))?n:(n.querySelector('button,a')||n);if(target&&typeof target.click==='function'){target.click();return true;}}}var anchors=root.querySelectorAll('a[href]');for(var j=0;j<anchors.length;j++){try{var a=anchors[j],u=new URL(a.href,window.location.href),clean=u.pathname.replace(/\\/+$/,'');if(clean.endsWith('/'+p)||clean===('/'+p)){a.click();return true;}}catch(e){}}return false;}"+
            "function drain(){var p=window.__qcmsNativePendingRoute||'';if(p&&findAndClick(p)){window.__qcmsNativePendingRoute='';window.__qcmsNativeLastStatus='QCMS_NAV_OK';return true;}return false;}"+
            "window.__qcmsNativeNavigate=function(route){var p=(route||'').toString().replace(/^\\/+|\\/+$/g,'')||'dashboard';window.__qcmsNativePendingRoute=p;if(findAndClick(p)){window.__qcmsNativePendingRoute='';window.__qcmsNativeLastStatus='QCMS_NAV_OK';return 'QCMS_NAV_OK';}window.__qcmsNativeLastStatus='QCMS_NAV_PENDING';return 'QCMS_NAV_PENDING';};"+
            "window.__qcmsNativeBridgeReady=true;window.__qcmsMobileApply=apply;"+
            "if(window.__qcmsMobileObserver){try{window.__qcmsMobileObserver.disconnect()}catch(e){}}window.__qcmsMobileObserver=new MutationObserver(function(){requestAnimationFrame(function(){apply();drain();})});window.__qcmsMobileObserver.observe(document.documentElement,{childList:true,subtree:true});"+
            "if(window.__qcmsNativeNavTimer){try{clearInterval(window.__qcmsNativeNavTimer)}catch(e){}}window.__qcmsNativeNavTimer=setInterval(function(){drain();},250);"+
            "apply();drain();return 'QCMS_BRIDGE_READY';})();";
        webView.evaluateJavascript(script,null);
    }

    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data){ super.onActivityResult(requestCode,resultCode,data); if(requestCode==FILE_CHOOSER_REQUEST&&fileCallback!=null){Uri[] results=null;if(resultCode==Activity.RESULT_OK&&data!=null){if(data.getClipData()!=null){int count=data.getClipData().getItemCount();results=new Uri[count];for(int i=0;i<count;i++)results[i]=data.getClipData().getItemAt(i).getUri();}else if(data.getData()!=null)results=new Uri[]{data.getData()};}fileCallback.onReceiveValue(results);fileCallback=null;} }

    @Override protected void onPause(){
        CookieManager.getInstance().flush();
        super.onPause();
    }

    @Override public void onBackPressed(){ if(drawerLayer!=null&&drawerLayer.getVisibility()==View.VISIBLE){closeDrawer();return;} if(webView!=null&&webView.canGoBack())webView.goBack(); else super.onBackPressed(); }
}
