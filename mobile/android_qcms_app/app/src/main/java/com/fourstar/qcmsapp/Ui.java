package com.fourstar.qcmsapp;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.content.res.ColorStateList;
import android.text.InputType;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.text.NumberFormat;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.Locale;

/** QCMS Teal Material design system (same palette as the QCMS website). */
public final class Ui {
    public static final int TEAL = Color.parseColor("#0F8B8D");
    public static final int TEAL_DARK = Color.parseColor("#0B6E70");
    public static final int TEAL_SOFT = Color.parseColor("#E3F2F2");
    public static final int BG = Color.parseColor("#F1F6F6");
    public static final int PANEL = Color.WHITE;
    public static final int TEXT = Color.parseColor("#173233");
    public static final int MUTED = Color.parseColor("#5C7778");
    public static final int LINE = Color.parseColor("#D5E4E4");
    public static final int LINE_STRONG = Color.parseColor("#B5CFCF");
    public static final int GREEN_FG = Color.parseColor("#166534");
    public static final int GREEN_BG = Color.parseColor("#DCFCE7");
    public static final int AMBER_FG = Color.parseColor("#92400E");
    public static final int AMBER_BG = Color.parseColor("#FEF3C7");
    public static final int RED_FG = Color.parseColor("#991B1B");
    public static final int RED_BG = Color.parseColor("#FEE2E2");
    public static final int ORANGE = Color.parseColor("#C2410C");
    public static final int GREY_BG = Color.parseColor("#E2E8F0");
    public static final int GREY_FG = Color.parseColor("#334155");

    private Ui() { }

    public static int dp(Context c, float value) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value, c.getResources().getDisplayMetrics()));
    }

    public static GradientDrawable round(int fill, int strokeColor, int strokeDp, float radiusDp, Context c) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(fill);
        d.setCornerRadius(dp(c, radiusDp));
        if (strokeDp > 0) d.setStroke(dp(c, strokeDp), strokeColor);
        return d;
    }

    /** Ripple feedback on any tappable surface. */
    public static void clickable(View v, int fill, int stroke, float radiusDp) {
        Context c = v.getContext();
        GradientDrawable content = round(fill, stroke, stroke == 0 ? 0 : 1, radiusDp, c);
        GradientDrawable mask = round(Color.WHITE, 0, 0, radiusDp, c);
        v.setBackground(new RippleDrawable(ColorStateList.valueOf(Color.parseColor("#330F8B8D")), content, mask));
        v.setClickable(true);
        v.setFocusable(true);
    }

    /** JSON nulls arrive as the word "null" from org.json; never show that to the user. */
    public static CharSequence clean(CharSequence value) {
        if (value == null) return "";
        String s = value.toString();
        if (!s.contains("null")) return value;
        if (s.trim().equals("null")) return "";
        return s.replaceAll("\\bnull\\b", "-");
    }

    public static TextView text(Context c, CharSequence value, float sp, int color, boolean bold) {
        TextView t = new TextView(c);
        t.setText(clean(value));
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(color);
        if (bold) t.setTypeface(Typeface.create("sans-serif-medium", Typeface.BOLD));
        return t;
    }

    public static TextView label(Context c, String value) {
        TextView t = text(c, value.toUpperCase(Locale.ROOT), 10.5f, MUTED, true);
        t.setLetterSpacing(0.04f);
        t.setPadding(0, dp(c, 10), 0, dp(c, 4));
        return t;
    }

    public static LinearLayout vbox(Context c) {
        LinearLayout l = new LinearLayout(c);
        l.setOrientation(LinearLayout.VERTICAL);
        return l;
    }

    public static LinearLayout hbox(Context c) {
        LinearLayout l = new LinearLayout(c);
        l.setOrientation(LinearLayout.HORIZONTAL);
        l.setGravity(Gravity.CENTER_VERTICAL);
        return l;
    }

    public static LinearLayout card(Context c) {
        LinearLayout l = vbox(c);
        l.setBackground(round(PANEL, LINE, 1, 14, c));
        int p = dp(c, 12);
        l.setPadding(p, p, p, p);
        l.setElevation(dp(c, 1));
        return l;
    }

    public static LinearLayout.LayoutParams matchWrap(Context c, int topMarginDp) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(c, topMarginDp);
        return lp;
    }

    public static LinearLayout.LayoutParams weight(float w) {
        return new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, w);
    }

    public static TextView chip(Context c, String value, String tone) {
        int fg = GREY_FG, bg = GREY_BG;
        String t = tone == null ? "" : tone;
        switch (t) {
            case "green": fg = GREEN_FG; bg = GREEN_BG; break;
            case "amber": fg = AMBER_FG; bg = AMBER_BG; break;
            case "red": fg = RED_FG; bg = RED_BG; break;
            case "teal": fg = TEAL_DARK; bg = TEAL_SOFT; break;
            default: break;
        }
        TextView chip = text(c, value, 10.5f, fg, true);
        chip.setBackground(round(bg, 0, 0, 12, c));
        chip.setPadding(dp(c, 8), dp(c, 3), dp(c, 8), dp(c, 3));
        chip.setSingleLine(true);
        return chip;
    }

    /** Tone for any QCMS status word. */
    public static String tone(String status) {
        String s = status == null ? "" : status.toUpperCase(Locale.ROOT);
        if (s.contains("CANCEL") || s.contains("REJECT") || s.contains("OVERDUE") || s.contains("FAIL") || s.equals("NG")) return "red";
        if (s.contains("PENDING") || s.contains("DUE") || s.contains("PROGRESS") || s.contains("DRAFT") || s.contains("REVISED")) return "amber";
        if (s.contains("APPROV") || s.contains("COMPLETE") || s.contains("CONFIRM") || s.contains("VALID") || s.equals("OK") || s.contains("ACTIVE") || s.contains("CLOSED") || s.contains("RELEASED")) return "green";
        if (s.contains("OPEN")) return "teal";
        return "grey";
    }

    public static String pretty(String status) {
        if (status == null || status.isEmpty() || "null".equals(status)) return "-";
        String s = status.replace('_', ' ').toLowerCase(Locale.ROOT);
        StringBuilder out = new StringBuilder();
        boolean up = true;
        for (char ch : s.toCharArray()) {
            out.append(up ? Character.toUpperCase(ch) : ch);
            up = ch == ' ';
        }
        return out.toString();
    }

    public static Button primary(Context c, String value) {
        Button b = new Button(c);
        b.setText(value);
        b.setAllCaps(false);
        b.setTextColor(Color.WHITE);
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        b.setTypeface(Typeface.DEFAULT_BOLD);
        b.setMinHeight(dp(c, 48));
        b.setStateListAnimator(null);
        clickable(b, TEAL, 0, 12);
        return b;
    }

    public static Button outline(Context c, String value, int color) {
        Button b = new Button(c);
        b.setText(value);
        b.setAllCaps(false);
        b.setTextColor(color);
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        b.setTypeface(Typeface.DEFAULT_BOLD);
        b.setMinHeight(dp(c, 48));
        b.setStateListAnimator(null);
        GradientDrawable content = round(Color.WHITE, color, 2, 12, c);
        GradientDrawable mask = round(Color.WHITE, 0, 0, 12, c);
        b.setBackground(new RippleDrawable(ColorStateList.valueOf(Color.parseColor("#220F8B8D")), content, mask));
        return b;
    }

    public static EditText input(Context c, String hint, boolean password) {
        EditText e = new EditText(c);
        e.setHint(hint);
        e.setSingleLine(true);
        e.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        e.setTextColor(TEXT);
        e.setHintTextColor(Color.parseColor("#8FA5A6"));
        e.setBackground(round(Color.WHITE, LINE_STRONG, 1, 10, c));
        e.setPadding(dp(c, 12), dp(c, 11), dp(c, 12), dp(c, 11));
        e.setInputType(password ? (InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD) : InputType.TYPE_CLASS_TEXT);
        return e;
    }

    /** Row "label ........ value" used on detail cards. */
    public static LinearLayout pair(Context c, String key, CharSequence value) {
        LinearLayout row = hbox(c);
        row.setPadding(0, dp(c, 4), 0, dp(c, 4));
        TextView k = text(c, key, 12, MUTED, false);
        CharSequence shown = clean(value);
        TextView v = text(c, shown.length() == 0 ? "-" : shown, 12.5f, TEXT, true);
        v.setGravity(Gravity.END);
        row.addView(k, weight(0.42f));
        row.addView(v, weight(0.58f));
        return row;
    }

    public static View divider(Context c) {
        View v = new View(c);
        v.setBackgroundColor(Color.parseColor("#EEF3F3"));
        v.setLayoutParams(new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, Math.max(1, dp(c, 1))));
        return v;
    }

    public static TextView empty(Context c, String message) {
        TextView t = text(c, message, 13, MUTED, false);
        t.setGravity(Gravity.CENTER);
        t.setPadding(dp(c, 16), dp(c, 32), dp(c, 16), dp(c, 32));
        return t;
    }

    // ------------------------------------------------------------- formatting
    private static final Locale INDIA = new Locale("en", "IN");

    public static String num(double value, int maxDecimals) {
        NumberFormat f = NumberFormat.getNumberInstance(INDIA);
        f.setMaximumFractionDigits(maxDecimals);
        f.setMinimumFractionDigits(0);
        return f.format(value);
    }

    public static String money(double value, String currency) {
        String cur = currency == null || currency.isEmpty() || currency.equalsIgnoreCase("INR") ? "₹ " : currency.toUpperCase(Locale.ROOT) + " ";
        NumberFormat f = NumberFormat.getNumberInstance(INDIA);
        f.setMaximumFractionDigits(2);
        f.setMinimumFractionDigits(0);
        return cur + f.format(value);
    }

    /** ISO yyyy-MM-dd (or timestamp) to dd-MM-yyyy as used on QCMS prints. */
    public static String date(String iso) {
        if (TextUtils.isEmpty(iso) || "null".equals(iso)) return "-";
        try {
            LocalDate d = LocalDate.parse(iso.length() >= 10 ? iso.substring(0, 10) : iso);
            return d.format(DateTimeFormatter.ofPattern("dd-MM-yyyy", Locale.ROOT));
        } catch (Exception e) {
            return iso;
        }
    }

    public static String today() {
        return LocalDate.now().toString();
    }
}
