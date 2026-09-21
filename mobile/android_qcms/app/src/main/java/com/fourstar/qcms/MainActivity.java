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

public class MainActivity extends Activity {
    private static final int FILE_CHOOSER_REQUEST = 701;
    private static final String PREFS = "qcms_mobile";
    private static final String PREF_URL = "qcms_url";
    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private SharedPreferences prefs;
    private FrameLayout drawerLayer;
    private LinearLayout drawerPanel;
    private View drawerScrim;
    private String baseUrl = "";

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

    private void showBrowser(String url) {
        baseUrl = normalizeUrl(url);
        if (baseUrl == null) { prefs.edit().remove(PREF_URL).apply(); showSetupScreen(); return; }

        FrameLayout root = new FrameLayout(this); root.setBackgroundColor(Color.WHITE); applySafeInsets(root);
        LinearLayout main = new LinearLayout(this); main.setOrientation(LinearLayout.VERTICAL); main.setBackgroundColor(Color.rgb(248,248,248));
        root.addView(main, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        LinearLayout top = new LinearLayout(this); top.setOrientation(LinearLayout.HORIZONTAL); top.setGravity(Gravity.CENTER_VERTICAL); top.setPadding(dp(4),0,dp(4),0); top.setBackgroundColor(Color.rgb(28,28,28));
        Button hamburger = iconButton("☰",22); top.addView(hamburger,new LinearLayout.LayoutParams(dp(50),dp(54)));
        ImageView logo = new ImageView(this); logo.setImageResource(R.drawable.stawn_icon); logo.setScaleType(ImageView.ScaleType.CENTER_CROP); LinearLayout.LayoutParams lpLogo=new LinearLayout.LayoutParams(dp(34),dp(34)); lpLogo.setMargins(0,0,dp(8),0); top.addView(logo,lpLogo);
        TextView title = new TextView(this); title.setText("QCMS"); title.setTextColor(Color.WHITE); title.setTextSize(18); title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD); top.addView(title,new LinearLayout.LayoutParams(0,dp(54),1));
        Button refresh=iconButton("↻",19); top.addView(refresh,new LinearLayout.LayoutParams(dp(48),dp(54)));
        Button more=iconButton("⋮",22); top.addView(more,new LinearLayout.LayoutParams(dp(48),dp(54)));
        main.addView(top,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(54)));

        webView = new WebView(this);
        WebSettings ws=webView.getSettings(); ws.setJavaScriptEnabled(true); ws.setDomStorageEnabled(true); ws.setDatabaseEnabled(true); ws.setSupportZoom(false); ws.setBuiltInZoomControls(false); ws.setLoadWithOverviewMode(true); ws.setUseWideViewPort(true); ws.setMediaPlaybackRequiresUserGesture(false); ws.setAllowFileAccess(false); ws.setAllowContentAccess(true); ws.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW); ws.setUserAgentString(ws.getUserAgentString()+" QCMSMobile/0.1.4");
        CookieManager cm=CookieManager.getInstance(); cm.setAcceptCookie(true); cm.setAcceptThirdPartyCookies(webView,true);
        webView.setWebViewClient(new WebViewClient(){
            @Override public void onPageFinished(WebView view,String pageUrl){ super.onPageFinished(view,pageUrl); installMobileChromeSuppressor(); }
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

        LinearLayout bottom=new LinearLayout(this); bottom.setOrientation(LinearLayout.HORIZONTAL); bottom.setGravity(Gravity.CENTER); bottom.setPadding(dp(4),0,dp(4),0); bottom.setBackgroundColor(Color.WHITE); bottom.setElevation(dp(8));
        Button home=bottomButton("⌂","Home"); bottom.addView(home,new LinearLayout.LayoutParams(0,dp(66),1));
        Button search=new Button(this); search.setText("⌕"); search.setTextSize(28); search.setTextColor(Color.WHITE); search.setBackground(rounded(Color.rgb(0,120,212),32)); LinearLayout.LayoutParams sp=new LinearLayout.LayoutParams(dp(58),dp(58)); sp.setMargins(dp(12),0,dp(12),0); bottom.addView(search,sp);
        Button complaints=bottomButton("◇","Complaints"); bottom.addView(complaints,new LinearLayout.LayoutParams(0,dp(66),1));
        main.addView(bottom,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(68)));

        drawerLayer=new FrameLayout(this); drawerLayer.setVisibility(View.GONE); root.addView(drawerLayer,new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.MATCH_PARENT));
        drawerScrim=new View(this); drawerScrim.setBackgroundColor(0x66000000); drawerLayer.addView(drawerScrim,new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.MATCH_PARENT)); drawerScrim.setOnClickListener(v->closeDrawer());
        ScrollView scroll=new ScrollView(this); drawerPanel=new LinearLayout(this); drawerPanel.setOrientation(LinearLayout.VERTICAL); drawerPanel.setBackgroundColor(Color.WHITE); scroll.addView(drawerPanel,new ScrollView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT)); FrameLayout.LayoutParams dlp=new FrameLayout.LayoutParams((int)(getResources().getDisplayMetrics().widthPixels*0.82),ViewGroup.LayoutParams.MATCH_PARENT); dlp.gravity=Gravity.START; drawerLayer.addView(scroll,dlp);
        LinearLayout drawerHead=new LinearLayout(this); drawerHead.setOrientation(LinearLayout.HORIZONTAL); drawerHead.setGravity(Gravity.CENTER_VERTICAL); drawerHead.setPadding(dp(18),dp(18),dp(12),dp(14)); ImageView dIcon=new ImageView(this); dIcon.setImageResource(R.drawable.stawn_icon); dIcon.setScaleType(ImageView.ScaleType.CENTER_CROP); drawerHead.addView(dIcon,new LinearLayout.LayoutParams(dp(46),dp(46))); TextView dTitle=label("QCMS\nFour Star Industries",18,true); dTitle.setPadding(dp(12),0,0,0); drawerHead.addView(dTitle,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1)); drawerPanel.addView(drawerHead);
        String[][] items={{"⌂","Dashboard","dashboard"},{"▦","Masters","masters"},{"▣","Supply Chain","supply-chain-home"},{"✓","RMTC","rmtc-entry"},{"⇥","Inward","inward-entry"},{"⌂","OSP","osp-home"},{"⚙","Quality / Inspections","inspection-home"},{"!","Complaints","complaints-home"},{"⌕","Search","global-search"},{"▤","Records","records-center"},{"▥","Reports","reports-home"},{"⚙","Admin","email-settings"}};
        for(String[] item:items)drawerPanel.addView(drawerButton(item[0],item[1],item[2]),new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(54)));

        setContentView(root);
        hamburger.setOnClickListener(v->openDrawer()); refresh.setOnClickListener(v->webView.reload()); home.setOnClickListener(v->navigate("dashboard")); search.setOnClickListener(v->navigate("global-search")); complaints.setOnClickListener(v->navigate("complaints-home"));
        more.setOnClickListener(v->new AlertDialog.Builder(this).setTitle("QCMS Mobile").setItems(new String[]{"Open QCMS in browser","Change QCMS URL","Android WebView settings"},(d,which)->{ if(which==0)startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(baseUrl))); else if(which==1){prefs.edit().remove(PREF_URL).apply();showSetupScreen();} else {try{android.content.pm.PackageInfo provider=WebView.getCurrentWebViewPackage(); if(provider!=null)startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:"+provider.packageName))); else startActivity(new Intent(Settings.ACTION_SETTINGS));}catch(Exception ex){startActivity(new Intent(Settings.ACTION_SETTINGS));}}}).show());
        webView.loadUrl(baseUrl);
    }

    private void navigate(String path){ if(webView==null)return; String p=path.startsWith("/")?path:"/"+path; webView.loadUrl(baseUrl+p); }
    private void openDrawer(){ if(drawerLayer!=null){drawerLayer.setVisibility(View.VISIBLE);drawerLayer.bringToFront();} }
    private void closeDrawer(){ if(drawerLayer!=null)drawerLayer.setVisibility(View.GONE); }

    private void installMobileChromeSuppressor(){
        if(webView==null)return;
        String script="(function(){function apply(){"+
            "var style=document.getElementById('qcms-mobile-native-style');if(!style){style=document.createElement('style');style.id='qcms-mobile-native-style';style.textContent='div.st-key-fsi_shell,[class~=\\\"st-key-fsi_shell\\\"],.st-key-fsi_left_rail,[class~=\\\"st-key-fsi_left_rail\\\"],[class*=\\\"st-key-fsi_module_subnav_\\\"]{display:none!important}div.st-key-qcms_workspace [data-testid=\\\"stHorizontalBlock\\\"]{display:block!important}.st-key-qcms_content,[class~=\\\"st-key-qcms_content\\\"]{width:100%!important;max-width:100%!important}div[data-testid=\\\"stMainBlockContainer\\\"],.block-container{padding:.55rem .55rem 5.2rem!important}.fsi-page-head{margin-top:0!important}.qcms-enterprise-table-wrap{max-height:72vh!important}';document.head.appendChild(style);} " +
            "var rail=document.querySelector('.st-key-fsi_left_rail,[class~=\\\"st-key-fsi_left_rail\\\"]');var rc=rail?rail.closest('[data-testid=\\\"column\\\"]'):null;if(rc)rc.style.display='none';var content=document.querySelector('.st-key-qcms_content,[class~=\\\"st-key-qcms_content\\\"]');var cc=content?content.closest('[data-testid=\\\"column\\\"]'):null;if(cc){cc.style.display='block';cc.style.width='100%';cc.style.flex='1 1 100%';}}window.__qcmsMobileApply=apply;if(window.__qcmsMobileObserver){try{window.__qcmsMobileObserver.disconnect()}catch(e){}}window.__qcmsMobileObserver=new MutationObserver(function(){requestAnimationFrame(apply)});window.__qcmsMobileObserver.observe(document.documentElement,{childList:true,subtree:true});apply();})();";
        webView.evaluateJavascript(script,null);
    }

    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data){ super.onActivityResult(requestCode,resultCode,data); if(requestCode==FILE_CHOOSER_REQUEST&&fileCallback!=null){Uri[] results=null;if(resultCode==Activity.RESULT_OK&&data!=null){if(data.getClipData()!=null){int count=data.getClipData().getItemCount();results=new Uri[count];for(int i=0;i<count;i++)results[i]=data.getClipData().getItemAt(i).getUri();}else if(data.getData()!=null)results=new Uri[]{data.getData()};}fileCallback.onReceiveValue(results);fileCallback=null;} }

    @Override public void onBackPressed(){ if(drawerLayer!=null&&drawerLayer.getVisibility()==View.VISIBLE){closeDrawer();return;} if(webView!=null&&webView.canGoBack())webView.goBack(); else super.onBackPressed(); }
}
