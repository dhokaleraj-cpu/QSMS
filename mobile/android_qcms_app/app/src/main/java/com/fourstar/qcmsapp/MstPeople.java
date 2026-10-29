package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;

/**
 * Employee Master (core/employee_service.py + app_pages/employee_master.py) and Company Branch
 * (app_pages/company_branch.py) save paths, which do not go through MasterService on the website.
 */
public final class MstPeople {
    private MstPeople() { }

    static final String[] AUTHORITIES = {"RMTC_PREPARE", "RMTC_VALIDATE", "RMTC_APPROVE", "MATERIAL_INWARD_PREPARE", "RAW_MATERIAL_INSPECTION", "SETUP_APPROVAL",
        "STAGE_INSPECTION", "OSP_QUALITY_RELEASE", "LAB_VALIDATION", "FINAL_QUALITY_RELEASE", "PPAP_APPROVAL", "CALIBRATION_APPROVAL", "AUDIT_APPROVAL"};
    static final String DEPARTMENTS = "Quality, Production, Stores, MetLAB, Engineering, Supply Chain, Management, Business Development, Procurement, HR, Accounts";

    private static String collapse(Object v) { return String.join(" ", MstSave.s(v).trim().split("\\s+")).toLowerCase(Locale.ROOT); }

    // ------------------------------------------------------------------ employees
    static List<Field> employeeFields(JSONObject existing) {
        LinkedHashSet<String> auth = new LinkedHashSet<>();
        for (String s : AUTHORITIES) auth.add(s);
        JSONArray cur = existing == null ? null : existing.optJSONArray("approval_authorities");
        for (int i = 0; cur != null && i < cur.length(); i++) if (!cur.optString(i).trim().isEmpty()) auth.add(cur.optString(i));
        String self = existing == null ? "" : Lookups.j(existing, "id");
        Field.Lookup managers = new Field.Lookup("employees", "id,employee_code,first_name,last_name,designation,department", self.isEmpty() ? "" : "&id=neq." + self,
            "first_name.asc", Lookups.EMPLOYEE);
        List<Field> f = new ArrayList<>();
        f.add(Field.text("employee_code", "Employee Code").hint("Auto on save (EMP-0001) when blank; editable."));
        f.add(Field.text("first_name", "First Name").req());
        f.add(Field.text("last_name", "Last Name").req());
        f.add(Field.text("email", "Email").req());
        f.add(Field.text("department", "Department").req().hint("e.g. " + DEPARTMENTS));
        f.add(Field.text("designation", "Designation").req());
        f.add(Field.text("plant", "Plant").req().def("D9"));
        f.add(Field.text("mobile_number", "Mobile Number"));
        f.add(Field.lookup("reports_to_employee_id", "Reports To", managers));
        f.add(Field.date("experience_start_date", "Experience Start Date").def(Ui.today()));
        f.add(Field.select("status", "Status", "ACTIVE", "INACTIVE", "LEFT").req().def("ACTIVE"));
        f.add(Field.multi("approval_authorities", "Authority for Approval", auth.toArray(new String[0])));
        f.add(Field.bool("is_top_level_authority", "Top-level authority").hint("Top-level authority / No Reports-To required"));
        f.add(Field.area("remarks", "Remarks"));
        return f;
    }

    static JSONObject saveEmployee(Api api, JSONObject v, JSONObject existing) throws Exception {
        String code = MstSave.s(v.opt("employee_code")).trim();
        if (code.isEmpty()) code = MstSave.codeRpc(api, "qsms_next_employee_code");
        boolean top = v.optBoolean("is_top_level_authority", false);
        JSONObject p = new JSONObject();
        p.put("employee_code", code);
        p.put("first_name", MstSave.s(v.opt("first_name")).trim());
        p.put("last_name", MstSave.s(v.opt("last_name")).trim());
        p.put("email", MstSave.s(v.opt("email")).trim().toLowerCase(Locale.ROOT));
        p.put("department", MstSave.s(v.opt("department")).trim());
        p.put("designation", MstSave.s(v.opt("designation")).trim());
        p.put("plant", MstSave.s(v.opt("plant")).trim());
        p.put("mobile_number", MstSave.orNull(MstSave.s(v.opt("mobile_number"))));
        p.put("approval_authorities", v.optJSONArray("approval_authorities") == null ? new JSONArray() : v.optJSONArray("approval_authorities"));
        p.put("is_top_level_authority", top);
        String rep = MstSave.s(v.opt("reports_to_employee_id"));
        p.put("reports_to_employee_id", top || rep.isEmpty() ? JSONObject.NULL : rep);
        String start = MstSave.s(v.opt("experience_start_date"));
        p.put("experience_start_date", start.isEmpty() ? JSONObject.NULL : start);
        p.put("status", MstSave.s(v.opt("status")).isEmpty() ? "ACTIVE" : v.opt("status"));
        p.put("remarks", MstSave.orNull(MstSave.s(v.opt("remarks"))));
        p.put("source_system", "QSMS");
        for (String k : new String[]{"first_name", "last_name", "email", "department", "designation", "plant", "employee_code"})
            if (MstSave.s(p.opt(k)).trim().isEmpty()) throw new Api.ApiException(422, Ui.pretty(k) + " is mandatory.");
        String id = existing == null ? null : Lookups.j(existing, "id");
        JSONArray rows = new JSONArray(api.get("employees?select=id,employee_code,email&limit=5000", false).body);
        for (String field : new String[]{"employee_code", "email"}) {
            String value = collapse(p.opt(field));
            if (value.isEmpty()) continue;
            for (int i = 0; i < rows.length(); i++) {
                JSONObject r = rows.getJSONObject(i);
                if (id != null && id.equals(Lookups.j(r, "id"))) continue;
                if (collapse(r.opt(field)).equals(value)) throw new Api.ApiException(409, "Duplicate " + Ui.pretty(field) + " is not allowed.");
            }
        }
        return id != null ? api.update("employees", id, p) : api.insert("employees", p);
    }

    /** employee_service.PHOTO_MAX_BYTES */
    static final int PHOTO_MAX_BYTES = 3 * 1024 * 1024;

    /** employee_service.photo_path: {tenant}/employees/{id}/photo_{id}.{jpg|png} (jpeg -> jpg; other types refused). */
    static String photoPath(String tenantId, String employeeId, String filename) throws Api.ApiException {
        String f = filename == null ? "" : filename;
        int dot = f.lastIndexOf('.');
        String ext = dot >= 0 && dot < f.length() - 1 ? f.substring(dot + 1).toLowerCase(Locale.ROOT) : "jpg";
        if ("jpeg".equals(ext)) ext = "jpg";
        if (!"jpg".equals(ext) && !"png".equals(ext)) throw new Api.ApiException(422, "Use a JPG or PNG photo.");
        return tenantId + "/employees/" + employeeId + "/photo_" + employeeId + "." + ext;
    }

    /** employee_service.upload_employee_photo: store in quality-documents (upsert) and save employees.photo_storage_path. Background thread. */
    static String storePhoto(Api api, String employeeId, Attachments.FileData f) throws Exception {
        if (f == null || f.data == null || f.data.length == 0) throw new Api.ApiException(422, "The selected photo is empty.");
        if (f.data.length > PHOTO_MAX_BYTES) throw new Api.ApiException(422, "Use a photo smaller than 3 MB.");
        String path = photoPath(api.tenantId, employeeId, f.name);
        api.upload(path, f.data, path.endsWith(".png") ? "image/png" : "image/jpeg", true);
        api.update("employees", employeeId, new JSONObject().put("photo_storage_path", path));
        LicService.clearImages();
        return path;
    }

    /** Upload / replace the employee photo (R38 Employee Master photo, also shown in the top-bar avatar). */
    static void uploadPhoto(MainActivity a, JSONObject row, Runnable refresh) {
        Api api = Api.get(a);
        String id = Lookups.j(row, "id");
        a.pickFile("Employee Photo (JPG / PNG, max 3 MB)", true, f -> {
            a.toast("Uploading photo…");
            Api.async(() -> storePhoto(api, id, f), (ok, err) -> {
                if (err != null) { a.toast("Upload failed: " + Api.message(err)); return; }
                a.toast("Employee photo uploaded successfully.");
                if (id.equals(api.employeeId)) LicBrand.refresh(a);
                refresh.run();
            });
        });
    }

    static void viewPhoto(MainActivity a, JSONObject row) {
        String path = Lookups.j(row, "photo_storage_path");
        if (path.isEmpty()) { a.toast("No photo uploaded yet."); return; }
        Api api = Api.get(a);
        Api.async(() -> Attachments.signedUrl(api, path), (url, e) -> { if (e != null) a.toast(Api.message(e)); else a.openInBrowser(url); });
    }

    // ------------------------------------------------------------------ company branches
    static List<Field> branchFields(JSONObject existing) {
        List<Field> f = new ArrayList<>();
        f.add(Field.text("branch_code", "Branch Code").req().hint("e.g. D9"));
        f.add(Field.text("plant_code", "Plant Code").hint("Defaults to the Branch Code"));
        f.add(Field.text("branch_name", "Branch Name").req().hint("e.g. Four Star Industries - D9"));
        f.add(Field.select("status", "Status", "ACTIVE", "INACTIVE").req().def("ACTIVE"));
        f.add(Field.bool("is_default", "Default Company Branch").hint("Used when the employee Plant does not map to a Branch / Plant Code"));
        f.add(Field.text("address_line1", "Address Line 1"));
        f.add(Field.text("address_line2", "Address Line 2"));
        f.add(Field.text("address_line3", "Address Line 3"));
        f.add(Field.text("city", "City"));
        f.add(Field.text("state", "State"));
        f.add(Field.text("postal_code", "Postal Code"));
        f.add(Field.text("country", "Country").def("India"));
        f.add(Field.text("gstin", "GSTIN / Tax ID"));
        f.add(Field.text("contact_person", "Contact Person"));
        f.add(Field.text("phone", "Phone"));
        f.add(Field.text("email", "Email"));
        f.add(Field.area("remarks", "Remarks"));
        return f;
    }

    static String norm(Object v) { return MstSave.words(v); }

    static JSONObject saveBranch(Api api, JSONObject v, JSONObject existing) throws Exception {
        String code = MstSave.s(v.opt("branch_code")).trim().toUpperCase(Locale.ROOT);
        String name = MstSave.s(v.opt("branch_name")).trim();
        if (code.isEmpty() || name.isEmpty()) throw new Api.ApiException(422, "Branch Code and Branch Name are required.");
        String plant = MstSave.s(v.opt("plant_code")).trim().toUpperCase(Locale.ROOT);
        boolean isDefault = v.optBoolean("is_default", false);
        JSONObject p = new JSONObject();
        p.put("branch_code", code);
        p.put("plant_code", plant.isEmpty() ? code : plant);
        p.put("branch_name", name);
        for (String k : new String[]{"address_line1", "address_line2", "address_line3", "city", "state", "postal_code", "country", "gstin", "contact_person", "phone"})
            p.put(k, MstSave.orNull(MstSave.s(v.opt(k))));
        p.put("email", MstSave.orNull(MstSave.s(v.opt("email")).trim().toLowerCase(Locale.ROOT)));
        p.put("is_default", isDefault);
        p.put("status", MstSave.s(v.opt("status")).isEmpty() ? "ACTIVE" : v.opt("status"));
        p.put("remarks", MstSave.orNull(MstSave.s(v.opt("remarks"))));
        String id = existing == null ? "" : Lookups.j(existing, "id");
        JSONArray rows = new JSONArray(api.get("company_branches?select=id,branch_code,branch_name,is_default&limit=1000", false).body);
        String nc = norm(code), nn = norm(name);
        for (int i = 0; i < rows.length(); i++) {
            JSONObject r = rows.getJSONObject(i);
            if (!id.isEmpty() && id.equals(Lookups.j(r, "id"))) continue;
            if (!nc.isEmpty() && norm(r.opt("branch_code")).equals(nc)) throw new Api.ApiException(409, "Duplicate Company Branch Code is not allowed.");
            if (!nn.isEmpty() && norm(r.opt("branch_name")).equals(nn)) throw new Api.ApiException(409, "Duplicate Company Branch Name is not allowed.");
        }
        if (isDefault) {
            for (int i = 0; i < rows.length(); i++) {
                JSONObject r = rows.getJSONObject(i);
                if (r.optBoolean("is_default", false) && !Lookups.j(r, "id").equals(id)) api.update("company_branches", Lookups.j(r, "id"), new JSONObject().put("is_default", false));
            }
        }
        return id.isEmpty() ? api.insert("company_branches", p) : api.update("company_branches", id, p);
    }
}
