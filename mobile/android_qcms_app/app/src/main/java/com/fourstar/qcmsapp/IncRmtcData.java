package com.fourstar.qcmsapp;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Read side of core/rmtc_service.py (RMTCService) used by the native RMTC screens. Background thread only. */
final class IncRmtcData {
    private IncRmtcData() { }

    static JSONArray sourceDetails(Api api, String partId) throws Exception {
        if (partId == null || partId.trim().isEmpty()) return new JSONArray();
        return api.rows("part_raw_material_details?select=*&part_id=eq." + Api.enc(partId) + "&status=eq.ACTIVE&order=sequence_no.asc&limit=200");
    }

    private static JSONObject copy(JSONObject o) throws Exception { return new JSONObject(o == null ? "{}" : o.toString()); }

    private static int cmp(String a, String b) { return a.compareTo(b); }

    /** RMTCService.approved_source_options: one option per approved Supplier with its raw material details. */
    static List<JSONObject> approvedSourceOptions(Api api, String partId) throws Exception {
        List<JSONObject> options = new ArrayList<>();
        if (partId == null || partId.trim().isEmpty()) return options;
        List<JSONObject> raw = IncCalc.list(sourceDetails(api, partId));
        List<JSONObject> links = IncCalc.list(api.rows("part_supplier_links?select=*&part_id=eq." + Api.enc(partId) + "&approved=eq.true&order=valid_from.asc&limit=500"));
        Map<String, List<JSONObject>> rawBySupplier = new LinkedHashMap<>();
        for (JSONObject r : raw) {
            String s = Lookups.j(r, "supplier_id");
            if (s.isEmpty()) continue;
            List<JSONObject> l = rawBySupplier.get(s);
            if (l == null) { l = new ArrayList<>(); rawBySupplier.put(s, l); }
            l.add(r);
        }
        if (links.isEmpty()) {
            for (Map.Entry<String, List<JSONObject>> e : rawBySupplier.entrySet()) {
                List<JSONObject> details = e.getValue();
                JSONObject o = copy(details.get(0));
                o.put("option_key", "SUPPLIER:" + e.getKey());
                o.put("supplier_id", e.getKey());
                o.put("raw_material_detail_id", details.size() == 1 ? details.get(0).opt("id") : JSONObject.NULL);
                o.put("raw_material_details", new JSONArray(details));
                o.put("approved_source_link_id", JSONObject.NULL);
                o.put("steel_mill_id", JSONObject.NULL);
                o.put("approval_reference", JSONObject.NULL);
                o.put("source_ready", !details.isEmpty());
                o.put("approval_mode", "LEGACY_RAW_DETAIL");
                options.add(o);
            }
            return options;
        }
        String today = LocalDate.now().toString();
        Map<String, List<JSONObject>> linksBySupplier = new LinkedHashMap<>();
        for (JSONObject l : links) {
            String s = Lookups.j(l, "supplier_id");
            if (s.isEmpty()) continue;
            List<JSONObject> x = linksBySupplier.get(s);
            if (x == null) { x = new ArrayList<>(); linksBySupplier.put(s, x); }
            x.add(l);
        }
        for (Map.Entry<String, List<JSONObject>> e : linksBySupplier.entrySet()) {
            List<JSONObject> sorted = new ArrayList<>(e.getValue());
            // sorted(key=link_score, reverse=True) - stable
            sorted.sort((x, y) -> {
                String vfx = Lookups.j(x, "valid_from"), vtx = Lookups.j(x, "valid_to");
                String vfy = Lookups.j(y, "valid_from"), vty = Lookups.j(y, "valid_to");
                int ex = ((vfx.isEmpty() || vfx.compareTo(today) <= 0) && (vtx.isEmpty() || vtx.compareTo(today) >= 0)) ? 1 : 0;
                int ey = ((vfy.isEmpty() || vfy.compareTo(today) <= 0) && (vty.isEmpty() || vty.compareTo(today) >= 0)) ? 1 : 0;
                if (ex != ey) return ey - ex;
                int c = cmp(vfy, vfx);
                if (c != 0) return c;
                int rx = Lookups.j(x, "approval_reference").isEmpty() ? 0 : 1, ry = Lookups.j(y, "approval_reference").isEmpty() ? 0 : 1;
                if (rx != ry) return ry - rx;
                String ux = IncCalc.firstText(Lookups.j(x, "updated_at"), Lookups.j(x, "created_at"));
                String uy = IncCalc.firstText(Lookups.j(y, "updated_at"), Lookups.j(y, "created_at"));
                return cmp(uy, ux);
            });
            JSONObject link = sorted.get(0);
            List<JSONObject> details = rawBySupplier.containsKey(e.getKey()) ? rawBySupplier.get(e.getKey()) : new ArrayList<>();
            JSONObject o = copy(details.isEmpty() ? null : details.get(0));
            o.put("option_key", "SUPPLIER:" + e.getKey());
            o.put("supplier_id", e.getKey());
            o.put("raw_material_detail_id", details.size() == 1 ? details.get(0).opt("id") : JSONObject.NULL);
            o.put("raw_material_details", new JSONArray(details));
            o.put("approved_source_link_id", IncCalc.jo(link, "id"));
            o.put("steel_mill_id", IncCalc.jo(link, "steel_mill_id"));
            o.put("approval_reference", IncCalc.jo(link, "approval_reference"));
            o.put("supplier_part_number", IncCalc.jo(link, "supplier_part_number"));
            o.put("valid_from", IncCalc.jo(link, "valid_from"));
            o.put("valid_to", IncCalc.jo(link, "valid_to"));
            o.put("source_ready", !details.isEmpty());
            o.put("approval_mode", details.isEmpty() ? "APPROVED_SOURCE_SETUP_REQUIRED" : "APPROVED_SOURCE");
            options.add(o);
        }
        return options;
    }

    private static String normLabel(String value) {
        String text = (value == null ? "" : value).trim().toUpperCase(Locale.ROOT).replace("INCH", "").replace("IN.", "").replace("IN", "").replace("″", "\"");
        if (text.startsWith("J")) text = text.replace(" ", "").replaceFirst("J", "");
        else text = text.replace(" ", "");
        while (text.endsWith("\"")) text = text.substring(0, text.length() - 1);
        return text;
    }

    /** RMTCService.jominy_template: part Jominy requirements with distance_16th and distance_mm. */
    static List<JSONObject> jominyTemplate(Api api, String partId) throws Exception {
        List<JSONObject> reqs = IncCalc.list(api.rows("part_jominy_requirements?select=*&part_id=eq." + Api.enc(partId) + "&status=eq.ACTIVE&order=sequence_no.asc&limit=100"));
        List<JSONObject> distances = IncCalc.list(api.rows("jominy_distances?select=*&status=eq.ACTIVE&order=distance_16th.asc&limit=100"));
        Map<String, JSONObject> byId = new LinkedHashMap<>();
        Map<String, JSONObject> byLabel = new LinkedHashMap<>();
        for (JSONObject d : distances) {
            if (!Lookups.j(d, "id").isEmpty()) byId.put(Lookups.j(d, "id"), d);
            byLabel.put(normLabel(Lookups.j(d, "distance_label")), d);
        }
        List<JSONObject> out = new ArrayList<>();
        Pattern p = Pattern.compile("(\\d+)\\s*/\\s*16", Pattern.CASE_INSENSITIVE);
        for (JSONObject req : reqs) {
            JSONObject distance = byId.get(Lookups.j(req, "jominy_distance_id"));
            if (distance == null) distance = byLabel.get(normLabel(Lookups.j(req, "distance_label")));
            int sixteenth = distance == null ? 0 : (int) IncCalc.f(distance.opt("distance_16th"));
            if (sixteenth == 0) {
                Matcher m = p.matcher(Lookups.j(req, "distance_label"));
                sixteenth = m.find() ? Integer.parseInt(m.group(1)) : 0;
                for (JSONObject d : distances) if ((int) IncCalc.f(d.opt("distance_16th")) == sixteenth) { distance = d; break; }
            }
            JSONObject o = copy(req);
            String did = distance != null && !Lookups.j(distance, "id").isEmpty() ? Lookups.j(distance, "id") : Lookups.j(req, "jominy_distance_id");
            o.put("jominy_distance_id", did.isEmpty() ? JSONObject.NULL : did);
            o.put("distance_16th", sixteenth);
            o.put("distance_mm", sixteenth != 0 ? (Object) IncCalc.round(sixteenth * 25.4 / 16, 2) : JSONObject.NULL);
            out.add(o);
        }
        return out;
    }

    static JSONObject heatSummary(Api api, String heat) throws Exception {
        String n = IncCalc.normalize(heat);
        if (n.isEmpty()) return new JSONObject();
        JSONObject r = IncCalc.one(api, "v_qsms_heat_summary?select=*&normalized_heat_number=eq." + Api.enc(n) + "&limit=1");
        return r == null ? new JSONObject() : r;
    }

    static List<JSONObject> heatUsage(Api api, String heat) throws Exception {
        String n = IncCalc.normalize(heat);
        if (n.isEmpty()) return new ArrayList<>();
        return IncCalc.list(api.rows("v_qsms_heat_steel_ledger?select=*&normalized_heat_number=eq." + Api.enc(n) + "&order=created_at.desc&limit=500"));
    }

    /** RMTCService.canonical_heat_code: first non-empty heat_code of the heat (oldest first). */
    static String canonicalHeatCode(Api api, String heat) throws Exception {
        String n = IncCalc.normalize(heat);
        if (n.isEmpty()) return "";
        for (JSONObject r : IncCalc.list(api.rows("rmtc_approvals?select=id,heat_code,created_at&normalized_heat_number=eq." + Api.enc(n) + "&order=created_at.asc&limit=100"))) {
            String v = Lookups.j(r, "heat_code").trim();
            if (!v.isEmpty()) return v;
        }
        return "";
    }

    /** RMTCService.supplier_rmtc_duplicate. */
    static JSONObject duplicate(Api api, String heat, String supplierRmtc, String excludeId) throws Exception {
        String hk = IncCalc.normalize(heat), rk = IncCalc.normalize(supplierRmtc);
        if (hk.isEmpty() || rk.isEmpty()) return null;
        for (JSONObject r : IncCalc.list(api.rows("rmtc_approvals?select=id,rmtc_number,created_at&normalized_heat_number=eq." + Api.enc(hk)
            + "&normalized_supplier_rmtc_number=eq." + Api.enc(rk) + "&order=created_at.desc&limit=20"))) {
            if (!Lookups.j(r, "id").equals(excludeId == null ? "" : excludeId)) return r;
        }
        return null;
    }

    static List<JSONObject> coveredParts(Api api, String rmtcId) throws Exception {
        return IncCalc.list(api.rows("rmtc_part_approvals?select=*&rmtc_approval_id=eq." + Api.enc(rmtcId) + "&order=created_at.asc&limit=100"));
    }

    static JSONObject rmtc(Api api, String rmtcId) throws Exception {
        JSONObject r = IncCalc.one(api, "rmtc_approvals?select=*&id=eq." + Api.enc(rmtcId));
        if (r == null) throw new Api.ApiException(404, "RMTC record not found.");
        return r;
    }

    /** Part rows by id (active parts + any covered part ids). */
    static Map<String, JSONObject> parts(Api api) throws Exception {
        Map<String, JSONObject> out = new LinkedHashMap<>();
        for (JSONObject p : IncCalc.list(Lookups.rows(api, Lookups.parts()))) out.put(Lookups.j(p, "id"), p);
        return out;
    }

    static String partLabel(Map<String, JSONObject> parts, String id) {
        JSONObject p = parts.get(id);
        return p == null ? id : Lookups.PART.of(p);
    }

    /** Fill part labels for ids that are not in the active list (inactive parts). */
    static void addMissingParts(Api api, Map<String, JSONObject> parts, List<String> ids) throws Exception {
        List<String> missing = new ArrayList<>();
        for (String id : ids) if (!id.isEmpty() && !parts.containsKey(id)) missing.add(id);
        if (missing.isEmpty()) return;
        for (JSONObject p : IncCalc.list(api.rows("parts?select=id,part_number,fsi_part_number,part_name,material_grade_id&id=in.(" + String.join(",", missing) + ")"))) parts.put(Lookups.j(p, "id"), p);
    }

    static String keys(JSONObject o) {
        StringBuilder b = new StringBuilder();
        Iterator<String> it = o.keys();
        while (it.hasNext()) b.append(it.next()).append(' ');
        return b.toString();
    }
}
