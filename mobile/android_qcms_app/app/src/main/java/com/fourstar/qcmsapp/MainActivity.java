package com.fourstar.qcmsapp;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.hardware.biometrics.BiometricManager;
import android.hardware.biometrics.BiometricPrompt;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.view.ViewGroup;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.time.LocalTime;
import java.util.ArrayDeque;
import java.util.Deque;

/**
 * QCMS native Android app (v2.0.0, QCMS R29; v3.4.0 R35: KPI start dashboard, notifications, licence).
 * Single activity: Login / biometric unlock, then Home · Orders · Inspect · Assets · More.
 */
public class MainActivity extends Activity {
    private static final long LOCK_AFTER_MS = 15L * 60L * 1000L;
    private static final String[] TABS = Catalog.TAB_NAMES;
    private static final String[] TAB_ICONS = {"⌂", "⇄", "✓", "▤", "⋯"};

    private Api api;
    private final Deque<Screen> stack = new ArrayDeque<>();
    private FrameLayout content;
    private TextView titleView;
    private TextView subtitleView;
    private LinearLayout navBar;
    private boolean shellVisible = false;
    private boolean locked = false;
    private long stoppedAt = 0L;
    private WebScreen activeWeb;
    private TextView brandView;
    private TextView bellBadge;
    private boolean foreground = false;
    /** R35: screen to open once the shell is shown (e.g. "notifications" from a system notification). */
    private String pendingOpen;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        api = Api.get(this);
        takeOpenRequest(getIntent());
        start();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        takeOpenRequest(intent);
        if (shellVisible && !locked) openPending();
    }

    private void takeOpenRequest(Intent intent) {
        String open = intent == null ? null : intent.getStringExtra(Notif.EXTRA_OPEN);
        if (open != null && !open.isEmpty()) pendingOpen = open;
    }

    private void openPending() {
        String open = pendingOpen;
        pendingOpen = null;
        if (Notif.OPEN_NOTIFICATIONS.equals(open) && !(stack.peek() instanceof NotifScreen)) push(new NotifScreen(this));
    }

    @Override
    protected void onResume() {
        super.onResume();
        foreground = true;
        if (shellVisible) {
            Notif.schedule(this);
            Notif.checkSoon(this);
            refreshBell();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        foreground = false;
    }

    boolean isForeground() { return foreground; }

    /** True while this screen is the one on display. */
    boolean isTop(Screen s) { return shellVisible && stack.peek() == s; }

    private void start() {
        if (!api.hasSavedSession()) {
            showLogin(null);
            return;
        }
        if (biometricEnabled()) {
            showLogin(null);
            unlockWithBiometric();
        } else {
            splash();
            restore();
        }
    }

    private void splash() {
        shellVisible = false;
        LinearLayout box = Ui.vbox(this);
        box.setGravity(Gravity.CENTER);
        box.setBackgroundColor(Color.WHITE);
        box.addView(logo(), new LinearLayout.LayoutParams(Ui.dp(this, 72), Ui.dp(this, 72)));
        TextView t = Ui.text(this, "Opening STAWN QCMS…", 14, Ui.MUTED, false);
        t.setPadding(0, Ui.dp(this, 14), 0, 0);
        box.addView(t);
        setContentView(box);
    }

    private void restore() {
        Api.async(() -> api.restoreSession(), (ok, err) -> {
            if (Boolean.TRUE.equals(ok)) {
                locked = false;
                showShell(0);
            } else {
                showLogin(api.online() ? "Please sign in again." : "No internet connection. Connect and sign in.");
            }
        });
    }

    // ------------------------------------------------------------------ login
    /** STAWN QCMS logo (same art as the launcher icon), rounded like the icon. */
    private View logo() {
        android.widget.ImageView logo = new android.widget.ImageView(this);
        logo.setImageResource(R.drawable.stawn_qcms_logo);
        logo.setScaleType(android.widget.ImageView.ScaleType.FIT_CENTER);
        logo.setBackground(Ui.round(Color.parseColor("#165D91"), 0, 0, 20, this));
        logo.setClipToOutline(true);
        return logo;
    }

    void showLogin(String message) {
        shellVisible = false;
        stack.clear();
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.WHITE);
        LinearLayout root = Ui.vbox(this);
        int p = Ui.dp(this, 26);
        root.setPadding(p, Ui.dp(this, 48), p, p);
        scroll.addView(root);

        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(Ui.dp(this, 72), Ui.dp(this, 72));
        lp.gravity = Gravity.CENTER_HORIZONTAL;
        root.addView(logo(), lp);
        TextView name = Ui.text(this, "STAWN QCMS", 22, Ui.TEAL_DARK, true);
        name.setGravity(Gravity.CENTER);
        name.setPadding(0, Ui.dp(this, 12), 0, 0);
        root.addView(name);
        String company = Licence.company(api);
        TextView sub = Ui.text(this, "Quality Control Monitoring System\n" + (company.isEmpty() ? "Four Star Industries" : company), 12.5f, Ui.MUTED, false);
        sub.setGravity(Gravity.CENTER);
        sub.setPadding(0, Ui.dp(this, 4), 0, Ui.dp(this, 22));
        root.addView(sub);

        if (message != null) {
            TextView m = Ui.text(this, message, 13, Ui.RED_FG, false);
            m.setBackground(Ui.round(Ui.RED_BG, 0, 0, 10, this));
            m.setPadding(Ui.dp(this, 12), Ui.dp(this, 10), Ui.dp(this, 12), Ui.dp(this, 10));
            root.addView(m, Ui.matchWrap(this, 0));
        }

        root.addView(Ui.label(this, "Email"));
        EditText email = Ui.input(this, "name@fourstarindustries.com", false);
        email.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        email.setText(api.email);
        root.addView(email, Ui.matchWrap(this, 0));
        root.addView(Ui.label(this, "Password"));
        LinearLayout pwRow = Ui.hbox(this);
        EditText password = Ui.input(this, "Password", true);
        pwRow.addView(password, Ui.weight(1));
        Button eye = Ui.outline(this, "Show", Ui.TEAL);
        eye.setTextSize(12);
        LinearLayout.LayoutParams eyeLp = new LinearLayout.LayoutParams(Ui.dp(this, 72), Ui.dp(this, 48));
        eyeLp.leftMargin = Ui.dp(this, 8);
        pwRow.addView(eye, eyeLp);
        eye.setOnClickListener(v -> {
            boolean hidden = (password.getInputType() & InputType.TYPE_TEXT_VARIATION_PASSWORD) == InputType.TYPE_TEXT_VARIATION_PASSWORD;
            password.setInputType(hidden ? (InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD) : (InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD));
            password.setSelection(password.getText().length());
            eye.setText(hidden ? "Hide" : "Show");
        });
        root.addView(pwRow, Ui.matchWrap(this, 0));

        CheckBox keep = new CheckBox(this);
        keep.setText("Keep me signed in on this phone");
        keep.setTextColor(Ui.TEXT);
        keep.setChecked(api.prefs().getBoolean("keep_signed_in", true));
        root.addView(keep, Ui.matchWrap(this, 8));

        Button signIn = Ui.primary(this, "Sign in");
        root.addView(signIn, Ui.matchWrap(this, 14));
        signIn.setOnClickListener(v -> {
            String mail = email.getText().toString().trim();
            String pw = password.getText().toString();
            if (mail.isEmpty() || pw.isEmpty()) {
                toast("Enter email and password.");
                return;
            }
            hideKeyboard(password);
            signIn.setEnabled(false);
            signIn.setText("Signing in…");
            api.prefs().edit().putBoolean("keep_signed_in", keep.isChecked()).apply();
            Api.async(() -> { api.signIn(mail, pw); return true; }, (ok, err) -> {
                if (err != null) {
                    signIn.setEnabled(true);
                    signIn.setText("Sign in");
                    toast(Api.message(err));
                    return;
                }
                locked = false;
                if (keep.isChecked() && biometricAvailable() && !api.prefs().contains("biometric")) offerBiometric();
                showShell(0);
            });
        });

        if (api.hasSavedSession() && biometricEnabled()) {
            Button bio = Ui.outline(this, "Unlock with fingerprint / face", Ui.TEAL);
            root.addView(bio, Ui.matchWrap(this, 10));
            bio.setOnClickListener(v -> unlockWithBiometric());
        }

        TextView foot = Ui.text(this, "v" + BuildConfig.VERSION_NAME + " · Secure Supabase login · locks after 15 min in background", 11, Ui.MUTED, false);
        foot.setGravity(Gravity.CENTER);
        foot.setPadding(0, Ui.dp(this, 28), 0, 0);
        root.addView(foot);
        setContentView(scroll);
    }

    private void hideKeyboard(View v) {
        InputMethodManager imm = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
        if (imm != null) imm.hideSoftInputFromWindow(v.getWindowToken(), 0);
    }

    // ------------------------------------------------------------------ biometric
    boolean biometricAvailable() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return Build.VERSION.SDK_INT >= Build.VERSION_CODES.P;
        BiometricManager bm = getSystemService(BiometricManager.class);
        return bm != null && bm.canAuthenticate() == BiometricManager.BIOMETRIC_SUCCESS;
    }

    boolean biometricEnabled() {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.P && api.prefs().getBoolean("biometric", false);
    }

    void setBiometric(boolean on) {
        api.prefs().edit().putBoolean("biometric", on).apply();
    }

    private void offerBiometric() {
        new AlertDialog.Builder(this)
            .setTitle("Use fingerprint / face unlock?")
            .setMessage("Next time open QCMS with your fingerprint or face instead of the password.")
            .setPositiveButton("Yes", (d, w) -> setBiometric(true))
            .setNegativeButton("Not now", (d, w) -> setBiometric(false))
            .show();
    }

    void unlockWithBiometric() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.P) {
            showLogin(null);
            return;
        }
        try {
            BiometricPrompt prompt = new BiometricPrompt.Builder(this)
                .setTitle("Unlock QCMS")
                .setSubtitle(api.email)
                .setNegativeButton("Use password", getMainExecutor(), (d, w) -> showLogin(null))
                .build();
            prompt.authenticate(new CancellationSignal(), getMainExecutor(), new BiometricPrompt.AuthenticationCallback() {
                @Override
                public void onAuthenticationSucceeded(BiometricPrompt.AuthenticationResult result) {
                    splash();
                    restore();
                }

                @Override
                public void onAuthenticationError(int errorCode, CharSequence errString) {
                    if (errorCode != BiometricPrompt.BIOMETRIC_ERROR_USER_CANCELED && errorCode != BiometricPrompt.BIOMETRIC_ERROR_CANCELED) {
                        toast(String.valueOf(errString));
                    }
                }
            });
        } catch (Exception e) {
            showLogin(null);
        }
    }

    @Override
    protected void onStop() {
        super.onStop();
        stoppedAt = System.currentTimeMillis();
    }

    @Override
    protected void onRestart() {
        super.onRestart();
        if (shellVisible && stoppedAt > 0 && System.currentTimeMillis() - stoppedAt > LOCK_AFTER_MS) {
            locked = true;
            showLogin("Locked after 15 minutes in the background.");
            if (biometricEnabled()) unlockWithBiometric();
        }
    }

    void sessionExpired() {
        if (shellVisible) {
            shellVisible = false;
            Api.main(() -> showLogin("Your session expired. Please sign in again."));
        }
    }

    void signOut() {
        Notif.cancelAll(this);
        Licence.status = null;
        api.signOut();
        showLogin(null);
    }

    // ------------------------------------------------------------------ R35 licence
    /** qcms_licence_status after login. Blocks only on a clear "not valid" answer; never when the RPC fails. */
    void checkLicence(boolean fromBlockScreen) {
        Api.async(() -> Licence.load(api), (st, err) -> {
            if (err != null) {
                if (fromBlockScreen) { toast("Could not check the licence: " + Api.message(err)); showShell(0); }
                return;
            }
            if (Licence.blocks(st)) { showLicenceBlocked(st); return; }
            if (fromBlockScreen) { showShell(0); return; }
            if (brandView != null) brandView.setText(brandText());
            Screen s = stack.peek();
            if (s instanceof KpiHomeScreen) setSubtitle(s.subtitle());
        });
    }

    /** STAWN-branded blocking licence screen (reason, contact, About, Sign out; admin key activation). */
    void showLicenceBlocked(org.json.JSONObject st) {
        shellVisible = false;
        stack.clear();
        setContentView(Licence.blockingView(this, st));
    }

    private String brandText() {
        String company = Licence.company(api);
        return "STAWN QCMS" + (company.isEmpty() ? "" : "  ·  " + company);
    }

    // ------------------------------------------------------------------ R35 notifications
    private static final int REQ_NOTIF = 804;

    /** Unread count on the top-bar bell (qcms_unread_notification_count). */
    void refreshBell() {
        if (bellBadge == null) return;
        Api.async(() -> Notif.unreadCount(api), (n, err) -> {
            if (err != null || n == null || bellBadge == null) return;
            bellBadge.setText(n > 99 ? "99+" : String.valueOf(n));
            bellBadge.setVisibility(n > 0 ? View.VISIBLE : View.GONE);
        });
    }

    private void askNotificationPermission() {
        if (Build.VERSION.SDK_INT < 33) return;
        if (checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) == android.content.pm.PackageManager.PERMISSION_GRANTED) return;
        if (api.prefs().getBoolean("notif_permission_asked", false)) return;
        api.prefs().edit().putBoolean("notif_permission_asked", true).apply();
        requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIF);
    }

    private View bell() {
        FrameLayout box = new FrameLayout(this);
        Button b = barButton("🔔");
        b.setTextSize(19);
        b.setOnClickListener(v -> { if (!(stack.peek() instanceof NotifScreen)) push(new NotifScreen(this)); });
        box.addView(b, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        bellBadge = Ui.text(this, "", 9.5f, Color.WHITE, true);
        bellBadge.setGravity(Gravity.CENTER);
        bellBadge.setPadding(Ui.dp(this, 4), 0, Ui.dp(this, 4), 0);
        bellBadge.setBackground(Ui.round(Color.parseColor("#DC2626"), Color.WHITE, 1, 9, this));
        bellBadge.setMinWidth(Ui.dp(this, 18));
        bellBadge.setVisibility(View.GONE);
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 18), Gravity.TOP | Gravity.END);
        lp.topMargin = Ui.dp(this, 4);
        lp.rightMargin = Ui.dp(this, 2);
        box.addView(bellBadge, lp);
        return box;
    }

    // ------------------------------------------------------------------ shell
    void showShell(int tab) {
        shellVisible = true;
        LinearLayout root = Ui.vbox(this);
        root.setBackgroundColor(Ui.BG);

        LinearLayout top = Ui.hbox(this);
        top.setBackgroundColor(Ui.TEAL);
        top.setPadding(Ui.dp(this, 6), Ui.dp(this, 6), Ui.dp(this, 6), Ui.dp(this, 8));
        Button back = barButton("‹");
        back.setTextSize(28);
        back.setOnClickListener(v -> onBackPressed());
        top.addView(back, new LinearLayout.LayoutParams(Ui.dp(this, 44), Ui.dp(this, 48)));
        LinearLayout titles = Ui.vbox(this);
        brandView = Ui.text(this, brandText(), 10, Color.parseColor("#BFE6E6"), true);
        brandView.setSingleLine(true);
        brandView.setEllipsize(android.text.TextUtils.TruncateAt.END);
        titles.addView(brandView);
        titleView = Ui.text(this, "", 17, Color.WHITE, true);
        titleView.setSingleLine(true);
        subtitleView = Ui.text(this, "", 11.5f, Color.parseColor("#D9F0F0"), false);
        subtitleView.setSingleLine(true);
        titles.addView(titleView);
        titles.addView(subtitleView);
        top.addView(titles, Ui.weight(1));
        top.addView(bell(), new LinearLayout.LayoutParams(Ui.dp(this, 46), Ui.dp(this, 48)));
        Button export = barButton("⇩");
        export.setOnClickListener(v -> exportCurrent());
        top.addView(export, new LinearLayout.LayoutParams(Ui.dp(this, 46), Ui.dp(this, 48)));
        Button refresh = barButton("↻");
        refresh.setOnClickListener(v -> { Screen s = stack.peek(); if (s != null) s.reload(); });
        top.addView(refresh, new LinearLayout.LayoutParams(Ui.dp(this, 48), Ui.dp(this, 48)));
        root.addView(top, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        // R33: global search at the top of every screen
        searchRow = Ui.hbox(this);
        searchRow.setBackgroundColor(Ui.TEAL);
        searchRow.setPadding(Ui.dp(this, 10), 0, Ui.dp(this, 10), Ui.dp(this, 8));
        searchRow.setGravity(Gravity.CENTER_VERTICAL);
        EditText searchBox = new EditText(this);
        searchBox.setHint("🔍  Search Part, Heat, RMTC, Batch, PO, Report…");
        searchBox.setHintTextColor(Ui.MUTED);
        searchBox.setTextColor(Ui.TEXT);
        searchBox.setTextSize(14);
        searchBox.setSingleLine(true);
        searchBox.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        searchBox.setPadding(Ui.dp(this, 14), Ui.dp(this, 8), Ui.dp(this, 14), Ui.dp(this, 8));
        searchBox.setBackground(Ui.round(Color.WHITE, 0, 0, 22, this));
        Runnable runSearch = () -> {
            String q = searchBox.getText().toString().trim();
            if (q.isEmpty()) { push(new GenSearchScreen(this)); return; }
            searchBox.setText("");
            searchBox.clearFocus();
            hideKeyboard(searchBox);
            push(new GenSearchScreen(this, q));
        };
        searchBox.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEARCH || actionId == EditorInfo.IME_ACTION_DONE) { runSearch.run(); return true; }
            return false;
        });
        searchRow.addView(searchBox, new LinearLayout.LayoutParams(0, Ui.dp(this, 42), 1));
        Button go = barButton("🔍");
        go.setTextSize(18);
        go.setOnClickListener(v -> runSearch.run());
        LinearLayout.LayoutParams glp = new LinearLayout.LayoutParams(Ui.dp(this, 46), Ui.dp(this, 42));
        glp.leftMargin = Ui.dp(this, 6);
        searchRow.addView(go, glp);
        root.addView(searchRow, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        content = new FrameLayout(this);
        root.addView(content, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));

        navBar = Ui.hbox(this);
        navBar.setBackgroundColor(Color.WHITE);
        navBar.setElevation(Ui.dp(this, 8));
        for (int i = 0; i < TABS.length; i++) {
            final int index = i;
            LinearLayout item = Ui.vbox(this);
            item.setGravity(Gravity.CENTER);
            item.setPadding(0, Ui.dp(this, 6), 0, Ui.dp(this, 6));
            TextView icon = Ui.text(this, TAB_ICONS[i], 18, Ui.MUTED, true);
            icon.setGravity(Gravity.CENTER);
            TextView label = Ui.text(this, TABS[i], 10.5f, Ui.MUTED, false);
            label.setGravity(Gravity.CENTER);
            item.addView(icon, new LinearLayout.LayoutParams(Ui.dp(this, 52), Ui.dp(this, 28)));
            item.addView(label);
            item.setOnClickListener(v -> openTab(index));
            Ui.clickable(item, Color.WHITE, 0, 0);
            navBar.addView(item, new LinearLayout.LayoutParams(0, Ui.dp(this, 60), 1));
        }
        root.addView(navBar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 60)));
        setContentView(root);
        backButton = back;
        openTab(tab);
        // R35: notifications (JobScheduler every 15 min + now), bell, permission, licence check
        Notif.schedule(this);
        Notif.checkSoon(this);
        refreshBell();
        askNotificationPermission();
        checkLicence(false);
        if (pendingOpen != null) openPending();
    }

    private Button backButton;
    private LinearLayout searchRow;


    private Button barButton(String text) {
        Button b = new Button(this);
        b.setText(text);
        b.setTextColor(Color.WHITE);
        b.setTextSize(22);
        b.setAllCaps(false);
        b.setStateListAnimator(null);
        b.setPadding(0, 0, 0, 0);
        Ui.clickable(b, Ui.TEAL, 0, 24);
        return b;
    }

    void openTab(int tab) {
        stack.clear();
        Screen s;
        // R35: the first screen is the KPI start dashboard; the Home overview is one tap away from it
        s = tab <= 0 || tab >= TABS.length ? new KpiHomeScreen(this) : new SectionScreen(this, tab);
        stack.push(s);
        render();
    }

    /** Top-bar ⇩: Download PDF / Excel, Print, Email or Share whatever is on screen. */
    void exportCurrent() {
        Screen s = stack.peek();
        View shown = content == null || content.getChildCount() == 0 ? null : content.getChildAt(0);
        ExportKit.show(this, s, shown);
    }

    /** Replace the current screen (e.g. New form -> the saved record). */
    void replaceTop(Screen s) {
        if (!stack.isEmpty()) stack.pop();
        stack.push(s);
        render();
    }

    /** Open a catalogue module register by key (used by Home shortcuts). */
    void openModule(String key) {
        Module m = Catalog.get(key);
        if (m == null) { toast("Module not available."); return; }
        push(m.custom != null ? m.custom.open(this) : new RegisterScreen(this, m));
    }

    /** Open a catalogue module straight on its New form. */
    void newRecord(String key) {
        Module m = Catalog.get(key);
        if (m == null || !m.canCreate()) { openModule(key); return; }
        push(EditScreen.open(this, m, null, null));
    }

    void push(Screen s) {
        stack.push(s);
        render();
    }

    void openWeb(String title, String path) {
        push(new WebScreen(this, title, path));
    }

    void rebuild() { render(); }

    /** Pop back to the previous screen and rebuild it (fresh data). */
    void back() {
        if (stack.size() > 1) {
            stack.pop();
            render();
        }
    }

    private void render() {
        if (!shellVisible || content == null) return;
        Screen s = stack.peek();
        if (s == null) return;
        activeWeb = s instanceof WebScreen ? (WebScreen) s : null;
        titleView.setText(s.title());
        String sub = s.subtitle();
        subtitleView.setText(sub);
        subtitleView.setVisibility(sub == null || sub.isEmpty() ? View.GONE : View.VISIBLE);
        backButton.setVisibility(stack.size() > 1 ? View.VISIBLE : View.GONE);
        if (searchRow != null) searchRow.setVisibility(s instanceof GenSearchScreen || s instanceof WebScreen ? View.GONE : View.VISIBLE);
        content.removeAllViews();
        content.addView(s.build(), new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        int tab = s.tab();
        for (int i = 0; i < navBar.getChildCount(); i++) {
            LinearLayout item = (LinearLayout) navBar.getChildAt(i);
            boolean on = i == tab;
            ((TextView) item.getChildAt(0)).setTextColor(on ? Color.WHITE : Ui.MUTED);
            item.getChildAt(0).setBackground(on ? Ui.round(Ui.TEAL, 0, 0, 14, this) : null);
            TextView label = (TextView) item.getChildAt(1);
            label.setTextColor(on ? Ui.TEAL_DARK : Ui.MUTED);
            label.setTypeface(on ? Typeface.DEFAULT_BOLD : Typeface.DEFAULT);
        }
    }

    /** Refresh the top-bar title after a screen learned its record number. */
    void rebuildTitle(Screen s) {
        if (s == stack.peek() && titleView != null) titleView.setText(s.title());
    }

    void setSubtitle(String text) {
        if (subtitleView != null) {
            subtitleView.setText(text);
            subtitleView.setVisibility(text == null || text.isEmpty() ? View.GONE : View.VISIBLE);
        }
    }

    @Override
    public void onBackPressed() {
        Screen s = stack.peek();
        if (s != null && s.onBack()) return;
        if (stack.size() > 1) {
            back();
        } else if (shellVisible && s != null && s.tab() != 0) {
            openTab(0);
        } else {
            super.onBackPressed();
        }
    }

    // ------------------------------------------------------------------ photos & files
    interface FileResult { void picked(Attachments.FileData file); }
    private static final int REQ_CAMERA = 801, REQ_PICK = 802, REQ_PERM = 803;
    private FileResult pendingFile;
    private Uri pendingCameraUri;
    private boolean pendingImagesOnly;

    /** Camera / gallery / file chooser. Photos are rotated upright and compressed (max 2000 px, JPEG 85). */
    void pickFile(String title, boolean imagesOnly, FileResult result) {
        pendingFile = result;
        pendingImagesOnly = imagesOnly;
        String[] items = imagesOnly ? new String[]{"Take photo", "Choose from gallery"} : new String[]{"Take photo", "Choose from gallery", "Choose file (PDF, Excel, …)"};
        new AlertDialog.Builder(this).setTitle(title).setItems(items, (d, which) -> {
            if (which == 0) startCamera();
            else {
                Intent pick = new Intent(Intent.ACTION_GET_CONTENT);
                pick.addCategory(Intent.CATEGORY_OPENABLE);
                pick.setType(which == 1 ? "image/*" : "*/*");
                try { startActivityForResult(Intent.createChooser(pick, title), REQ_PICK); } catch (Exception e) { toast("No file picker available."); }
            }
        }).setNegativeButton("Back", null).show();
    }

    private void startCamera() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q
            && checkSelfPermission(android.Manifest.permission.WRITE_EXTERNAL_STORAGE) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{android.Manifest.permission.WRITE_EXTERNAL_STORAGE}, REQ_PERM);
            return;
        }
        try {
            android.content.ContentValues values = new android.content.ContentValues();
            values.put(android.provider.MediaStore.Images.Media.DISPLAY_NAME, "QCMS_" + System.currentTimeMillis() + ".jpg");
            values.put(android.provider.MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
            pendingCameraUri = getContentResolver().insert(android.provider.MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
            Intent camera = new Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE);
            camera.putExtra(android.provider.MediaStore.EXTRA_OUTPUT, pendingCameraUri);
            camera.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            startActivityForResult(camera, REQ_CAMERA);
        } catch (Exception e) {
            toast("Camera not available: " + e.getMessage());
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        if (requestCode == REQ_NOTIF) {
            if (results.length > 0 && results[0] == android.content.pm.PackageManager.PERMISSION_GRANTED) Notif.checkSoon(this);
            return;
        }
        if (requestCode == REQ_PERM) {
            if (results.length > 0 && results[0] == android.content.pm.PackageManager.PERMISSION_GRANTED) startCamera();
            else toast("Storage permission is needed to save the camera photo (Android 9 and older).");
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (activeWeb != null && requestCode == WebScreen.FILE_CHOOSER) {
            activeWeb.onActivityResult(requestCode, resultCode, data);
            return;
        }
        if (pendingFile == null) return;
        final FileResult callback = pendingFile;
        Uri uri = null;
        if (requestCode == REQ_CAMERA && resultCode == RESULT_OK) uri = pendingCameraUri;
        else if (requestCode == REQ_PICK && resultCode == RESULT_OK && data != null) uri = data.getData();
        if (uri == null) {
            if (requestCode == REQ_CAMERA && pendingCameraUri != null) {
                try { getContentResolver().delete(pendingCameraUri, null, null); } catch (Exception ignored) { }
            }
            return;
        }
        final Uri source = uri;
        toast("Preparing file…");
        Api.async(() -> Photos.read(this, source), (file, err) -> {
            if (err != null) { toast("Could not read the file: " + Api.message(err)); return; }
            callback.picked(file);
        });
    }

    // ------------------------------------------------------------------ helpers
    void toast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show();
    }

    String greeting() {
        int h = LocalTime.now().getHour();
        String part = h < 12 ? "Good morning" : (h < 17 ? "Good afternoon" : "Good evening");
        String first = api.fullName == null ? "" : api.fullName.trim();
        if (first.contains(" ")) first = first.substring(0, first.indexOf(' '));
        return first.isEmpty() ? part : part + ", " + first;
    }

    interface TextResult { void ok(String text); }

    /** Dialog asking for a mandatory text (reason / remarks). */
    void askText(String title, String hint, String okLabel, boolean required, TextResult result) {
        EditText input = Ui.input(this, hint, false);
        input.setSingleLine(false);
        input.setMinLines(2);
        FrameLayout wrap = new FrameLayout(this);
        int p = Ui.dp(this, 20);
        wrap.setPadding(p, Ui.dp(this, 8), p, 0);
        wrap.addView(input);
        AlertDialog dialog = new AlertDialog.Builder(this)
            .setTitle(title)
            .setView(wrap)
            .setPositiveButton(okLabel, null)
            .setNegativeButton("Back", null)
            .create();
        dialog.setOnShowListener(d -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            String text = input.getText().toString().trim();
            if (required && text.isEmpty()) {
                input.setError("Required");
                return;
            }
            dialog.dismiss();
            result.ok(text);
        }));
        dialog.show();
    }

    /** Re-enter password before a sensitive action (Admin approvals of deletions). */
    void confirmPassword(String title, Runnable onOk) {
        EditText input = Ui.input(this, "Your QCMS password", true);
        FrameLayout wrap = new FrameLayout(this);
        int p = Ui.dp(this, 20);
        wrap.setPadding(p, Ui.dp(this, 8), p, 0);
        wrap.addView(input);
        new AlertDialog.Builder(this)
            .setTitle(title)
            .setView(wrap)
            .setPositiveButton("Confirm", (d, w) -> {
                String pw = input.getText().toString();
                Api.async(() -> { api.verifyPassword(pw); return true; }, (ok, err) -> {
                    if (err != null) toast(Api.message(err));
                    else onOk.run();
                });
            })
            .setNegativeButton("Back", null)
            .show();
    }

    void confirm(String title, String message, String okLabel, Runnable onOk) {
        new AlertDialog.Builder(this)
            .setTitle(title)
            .setMessage(message)
            .setPositiveButton(okLabel, (d, w) -> onOk.run())
            .setNegativeButton("Back", null)
            .show();
    }

    void openInBrowser(String url) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception e) {
            toast("No browser available.");
        }
    }
}
