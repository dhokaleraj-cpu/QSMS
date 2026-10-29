package com.fourstar.qcmsapp;

import android.graphics.Bitmap;
import android.view.Gravity;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Company profile & logo section (licence_company._company_setup): the company administrator's one-time setup of the
 * own company, and the STAWN developer's editor for any licensed company. Required fields = licence_service.REQUIRED_COMPANY_FIELDS.
 */
final class LicProfile {
    private LicProfile() { }

    static void section(MainActivity a, LinearLayout page, String letter, String tenantId, String legalDefault, boolean canEdit) {
        Api api = Api.get(a);
        LinearLayout box = AdmUi.section(a, page, letter, "COMPANY PROFILE & LOGO", "Loading the company profile…");
        LinearLayout body = Ui.vbox(a);
        box.addView(body, Ui.matchWrap(a, 4));
        load(a, api, box, body, tenantId, legalDefault, canEdit);
    }

    private static void load(MainActivity a, Api api, LinearLayout box, LinearLayout body, String tenantId, String legalDefault, boolean canEdit) {
        body.removeAllViews();
        body.addView(Ui.text(a, "Loading…", 12, Ui.MUTED, false));
        Api.async(() -> {
            JSONObject company = LicService.companyProfile(api, tenantId);
            Bitmap logo = LicService.image(api, LicService.s(company, "logo_path"), 320);
            return new Object[]{company, logo};
        }, (res, err) -> {
            body.removeAllViews();
            if (err != null) { body.addView(AdmUi.note(a, Api.message(err), "red")); return; }
            render(a, api, box, body, (JSONObject) res[0], (Bitmap) res[1], tenantId, legalDefault, canEdit);
        });
    }

    private static void render(MainActivity a, Api api, LinearLayout box, LinearLayout body, JSONObject company, Bitmap logo,
                               String tenantId, String legalDefault, boolean canEdit) {
        boolean done = company.optBoolean("setup_complete", false);
        if (box.getChildCount() > 1 && box.getChildAt(1) instanceof TextView && box.getChildAt(1) != body) {
            ((TextView) box.getChildAt(1)).setText(done ? "Completed. The company administrator can still correct the details."
                : "One-time setup: fill the company details and upload the logo. They are printed on reports and shown in the app.");
        }
        LinearLayout logoRow = Ui.hbox(a);
        logoRow.setGravity(Gravity.CENTER_VERTICAL);
        if (logo != null) {
            ImageView iv = new ImageView(a);
            iv.setImageBitmap(logo);
            iv.setAdjustViewBounds(true);
            iv.setScaleType(ImageView.ScaleType.FIT_CENTER);
            logoRow.addView(iv, new LinearLayout.LayoutParams(Ui.dp(a, 120), Ui.dp(a, 72)));
        } else {
            logoRow.addView(AdmUi.note(a, "No logo yet", "grey"));
        }
        TextView logoNote = Ui.text(a, "  Company logo (PNG / JPG, max 2 MB)", 11.5f, Ui.MUTED, false);
        logoRow.addView(logoNote, Ui.weight(1));
        body.addView(logoRow, Ui.matchWrap(a, 4));
        final Attachments.FileData[] picked = {null};
        if (canEdit) {
            Button choose = Ui.outline(a, "Choose new company logo", Ui.TEAL);
            choose.setOnClickListener(v -> a.pickFile("Company logo", true, f -> {
                picked[0] = f;
                logoNote.setText("  New logo selected: " + f.name + " (" + (f.data.length / 1024) + " KB) - saved with the profile");
            }));
            body.addView(choose, Ui.matchWrap(a, 6));
        }

        Map<String, EditText> inputs = new LinkedHashMap<>();
        for (String[] f : LicService.COMPANY_FIELDS) {
            String value = LicService.s(company, f[0]);
            if (value.isEmpty() && "legal_name".equals(f[0]) && legalDefault != null) value = legalDefault;
            if (value.isEmpty() && "country".equals(f[0])) value = "India";
            EditText e = AdmUi.field(a, body, f[1], value, f[1].replace(" *", ""));
            AdmUi.enableView(e, canEdit);
            inputs.put(f[0], e);
        }
        if (!canEdit) {
            body.addView(Ui.text(a, "Only the company administrator (or STAWN) can change the company profile.", 11.5f, Ui.MUTED, false), Ui.matchWrap(a, 6));
            return;
        }
        Button draft = AdmUi.outline(a, body, "Save draft", null);
        Button finish = AdmUi.primary(a, body, done ? "Save company details" : "Save & complete company setup", null);
        android.view.View.OnClickListener save = v -> {
            boolean complete = v == finish;
            Map<String, String> values = new LinkedHashMap<>();
            for (Map.Entry<String, EditText> e : inputs.entrySet()) values.put(e.getKey(), AdmUi.text(e.getValue()));
            if (complete) {
                JSONObject check = new JSONObject();
                try { for (Map.Entry<String, String> e : values.entrySet()) check.put(e.getKey(), e.getValue()); } catch (Exception ignored) { }
                java.util.List<String> missing = LicService.missingCompanyFields(check);
                if (!missing.isEmpty()) { a.toast("Fill these company details before finishing the setup: " + String.join(", ", missing)); return; }
            }
            AdmUi.enable(draft, false);
            AdmUi.enable(finish, false);
            String tid = LicService.s(company, "tenant_id").isEmpty() ? tenantId : LicService.s(company, "tenant_id");
            Api.async(() -> {
                String logoPath = picked[0] == null ? null : LicService.uploadCompanyLogo(api, tid, picked[0]);
                LicService.saveCompanyProfile(api, tid, values, logoPath, complete);
                try { Licence.load(api); } catch (Exception ignored) { }
                return true;
            }, (ok, err) -> {
                AdmUi.enable(draft, true);
                AdmUi.enable(finish, true);
                if (err != null) { a.toast(Api.message(err)); return; }
                a.toast("Company profile saved." + (complete ? " Setup complete." : ""));
                LicBrand.refresh(a);
                load(a, api, box, body, tenantId, legalDefault, true);
            });
        };
        draft.setOnClickListener(save);
        finish.setOnClickListener(save);
    }
}
