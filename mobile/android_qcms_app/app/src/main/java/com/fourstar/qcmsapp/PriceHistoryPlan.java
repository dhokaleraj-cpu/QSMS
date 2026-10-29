package com.fourstar.qcmsapp;

import org.json.JSONObject;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

/**
 * R39 · port of core/price_history_service.py (web R37b): controlled save of the Part Master Supplier / FSI Part
 * price-history grid BY ROW ID. Every grid row carries its database id, the whole edited set is validated before the
 * first write (one clear message, no partial save), the previous open period is closed automatically like the database
 * trigger, and writes are ordered (shrinking rows first, then other changes by start date, then new rows) so every
 * intermediate state passes the non-overlap guard. Fixes "Price period … overlaps the existing period …" when a row's
 * Start Date / UOM was edited (it was matched by natural key and inserted as a new period).
 */
final class PriceHistoryPlan {
    static final String TABLE = "part_supplier_price_history";
    static final String[] EDITABLE = {"start_date", "end_date", "price", "freight", "tool_cost", "packing_forwarding", "profit", "icc_rejection", "currency", "uom", "remarks", "status"};
    private static final Set<String> MONEY = new HashSet<>(java.util.Arrays.asList("price", "freight", "tool_cost", "packing_forwarding", "profit", "icc_rejection"));

    final List<Object[]> updates = new ArrayList<>();   // {id, changes}
    final List<JSONObject> inserts = new ArrayList<>();
    final List<String> autoClosed = new ArrayList<>();

    int changed() { return updates.size() + inserts.size(); }

    static final class Rule extends Exception { Rule(String m) { super(m); } }

    private static final class Row {
        String id; JSONObject data; JSONObject original; boolean userEditedEnd; String label;
        LocalDate start() { return day(data.opt("start_date")); }
        LocalDate end() { return day(data.opt("end_date")); }
        String uom() { String u = s(data.opt("uom")).toUpperCase(Locale.ROOT); return u.isEmpty() ? "KGS" : u; }
        boolean active() { String st = s(data.opt("status")).toUpperCase(Locale.ROOT); return st.isEmpty() || "ACTIVE".equals(st); }
    }

    static String s(Object v) { return v == null || v == JSONObject.NULL ? "" : String.valueOf(v).trim(); }

    static LocalDate day(Object v) {
        String t = s(v);
        if (t.length() >= 10) t = t.substring(0, 10);
        if (t.isEmpty() || "nat".equalsIgnoreCase(t) || "nan".equalsIgnoreCase(t) || "none".equalsIgnoreCase(t) || "null".equalsIgnoreCase(t)) return null;
        return LocalDate.parse(t);
    }

    static String fmt(LocalDate d) { return d == null ? "open" : String.format(Locale.US, "%02d-%02d-%04d", d.getDayOfMonth(), d.getMonthValue(), d.getYear()); }

    static Double num(Object v) {
        String t = s(v);
        if (t.isEmpty()) return null;
        try { double d = Double.parseDouble(t.replace(",", "")); return Double.isNaN(d) ? null : d; } catch (Exception e) { return null; }
    }

    /** _clean_payload. */
    static JSONObject clean(JSONObject row) throws Exception {
        JSONObject out = new JSONObject();
        for (String k : EDITABLE) {
            if (!row.has(k)) continue;
            Object v = row.opt(k);
            if (k.equals("start_date") || k.equals("end_date")) { LocalDate d = day(v); out.put(k, d == null ? JSONObject.NULL : d.toString()); }
            else if (MONEY.contains(k)) { Double d = num(v); out.put(k, d == null ? JSONObject.NULL : d); }
            else if (k.equals("currency") || k.equals("uom") || k.equals("status")) {
                String t = s(v);
                out.put(k, (t.isEmpty() ? (k.equals("currency") ? "INR" : k.equals("uom") ? "KGS" : "ACTIVE") : t).toUpperCase(Locale.ROOT));
            } else { String t = s(v); out.put(k, t.isEmpty() ? JSONObject.NULL : t); }
        }
        return out;
    }

    static boolean same(String k, Object a, Object b) {
        if (k.equals("start_date") || k.equals("end_date")) { LocalDate x = day(a), y = day(b); return x == null ? y == null : x.equals(y); }
        if (MONEY.contains(k)) { Double x = num(a), y = num(b); return (x == null && y == null) || (x != null && y != null && Math.abs(x - y) < 1e-9); }
        if (k.equals("currency") || k.equals("uom") || k.equals("status")) return s(a).toUpperCase(Locale.ROOT).equals(s(b).toUpperCase(Locale.ROOT));
        return s(a).equals(s(b));
    }

    /** plan_price_history_save: validate the complete edited grid and return ordered writes (nothing written here). */
    static PriceHistoryPlan plan(List<JSONObject> existing, List<JSONObject> edited, JSONObject base) throws Exception {
        Map<String, JSONObject> byId = new HashMap<>();
        for (JSONObject r : existing) if (!s(r.opt("id")).isEmpty()) byId.put(s(r.opt("id")), r);
        List<Row> rows = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        int index = 0;
        for (JSONObject raw : edited) {
            index++;
            String rid = s(raw.opt("id"));
            JSONObject payload = clean(raw);
            String label = "Price row " + index;
            if (payload.isNull("start_date") && payload.isNull("price")) continue;   // blank grid row
            if (payload.isNull("start_date") || !payload.has("start_date")) throw new Rule(label + ": Start Date is required.");
            if (payload.isNull("price") || !payload.has("price")) throw new Rule(label + " (" + fmt(day(payload.opt("start_date"))) + "): Basic Rate is required.");
            if (payload.getDouble("price") < 0) throw new Rule(label + ": Basic Rate cannot be negative.");
            for (String k : new String[]{"freight", "tool_cost", "packing_forwarding", "profit", "icc_rejection"}) {
                Double d = num(payload.opt(k));
                if (d != null && d < 0) throw new Rule(label + ": " + Ui.pretty(k.toUpperCase(Locale.ROOT)) + " cannot be negative.");
            }
            String st = s(payload.opt("status"));
            if (!st.isEmpty() && !"ACTIVE".equals(st) && !"INACTIVE".equals(st)) throw new Rule(label + ": Status must be ACTIVE or INACTIVE.");
            LocalDate start = day(payload.opt("start_date")), end = day(payload.opt("end_date"));
            if (end != null && start != null && end.isBefore(start)) throw new Rule(label + ": End Date " + fmt(end) + " is before Start Date " + fmt(start) + ".");
            if (!rid.isEmpty() && !byId.containsKey(rid))
                throw new Rule(label + ": this price row no longer exists for the selected Part / Supplier / Raw Material. Refresh the page and save again.");
            if (!rid.isEmpty() && seen.contains(rid)) continue;
            if (rid.isEmpty()) {   // backward compatible natural-key match (row without id)
                String wantUom = s(payload.opt("uom")).isEmpty() ? "KGS" : s(payload.opt("uom")).toUpperCase(Locale.ROOT);
                for (JSONObject r : existing) {
                    String eu = s(r.opt("uom")).isEmpty() ? "KGS" : s(r.opt("uom")).toUpperCase(Locale.ROOT);
                    if (!seen.contains(s(r.opt("id"))) && start != null && start.equals(day(r.opt("start_date"))) && eu.equals(wantUom)) { rid = s(r.opt("id")); break; }
                }
            }
            Row row = new Row();
            row.id = rid.isEmpty() ? null : rid;
            row.data = payload;
            row.original = row.id == null ? null : byId.get(row.id);
            if (row.id != null) seen.add(row.id);
            row.userEditedEnd = row.original == null || !same("end_date", row.original.opt("end_date"), payload.opt("end_date"));
            row.label = label;
            rows.add(row);
        }
        for (Map.Entry<String, JSONObject> e : byId.entrySet()) {   // saved rows not in the grid stay (deletion is password-controlled)
            if (seen.contains(e.getKey())) continue;
            Row row = new Row();
            row.id = e.getKey(); row.data = clean(e.getValue()); row.original = e.getValue(); row.userEditedEnd = false;
            row.label = "Saved row " + fmt(day(e.getValue().opt("start_date")));
            rows.add(row);
        }
        Map<String, Row> starts = new HashMap<>();
        for (Row r : rows) {
            String key = r.uom() + "|" + r.start();
            if (starts.containsKey(key)) throw new Rule("Two price rows start on " + fmt(r.start()) + " (" + r.uom() + "). Each price revision needs its own Start Date.");
            starts.put(key, r);
        }
        PriceHistoryPlan plan = new PriceHistoryPlan();
        TreeSet<String> uoms = new TreeSet<>();
        for (Row r : rows) uoms.add(r.uom());
        for (String uom : uoms) {
            List<Row> active = new ArrayList<>();
            for (Row r : rows) if (r.uom().equals(uom) && r.active()) active.add(r);
            active.sort((x, y) -> x.start().compareTo(y.start()));
            for (int i = 0; i + 1 < active.size(); i++) {
                Row prev = active.get(i), nxt = active.get(i + 1);
                if (prev.end() == null || !prev.end().isBefore(nxt.start())) {
                    if (prev.end() == null || !prev.userEditedEnd) {
                        LocalDate newEnd = nxt.start().minusDays(1);
                        prev.data.put("end_date", newEnd.toString());
                        plan.autoClosed.add(fmt(prev.start()) + " closed on " + fmt(newEnd));
                    } else {
                        throw new Rule("Price period " + fmt(nxt.start()) + " to " + fmt(nxt.end()) + " overlaps " + fmt(prev.start()) + " to " + fmt(prev.end())
                            + ". Set the End Date of the " + fmt(prev.start()) + " row to " + fmt(nxt.start().minusDays(1)) + " or earlier, or change the Start Date.");
                    }
                }
            }
            for (int i = 0; i < active.size(); i++) for (int j = i + 1; j < active.size(); j++) {
                Row x = active.get(i), y = active.get(j);
                LocalDate xe = x.end() == null ? LocalDate.MAX : x.end(), ye = y.end() == null ? LocalDate.MAX : y.end();
                if (!x.start().isAfter(ye) && !y.start().isAfter(xe))
                    throw new Rule("Price period " + fmt(y.start()) + " to " + fmt(y.end()) + " overlaps " + fmt(x.start()) + " to " + fmt(x.end()) + ". Correct the dates and save again.");
            }
        }
        List<Object[]> shrinking = new ArrayList<>(), growing = new ArrayList<>();
        for (Row r : rows) {
            if (r.id == null) continue;
            JSONObject original = r.original == null ? new JSONObject() : r.original;
            JSONObject changes = new JSONObject();
            Iterator<String> it = r.data.keys();
            while (it.hasNext()) { String k = it.next(); if (!same(k, original.opt(k), r.data.opt(k))) changes.put(k, r.data.opt(k)); }
            if (changes.length() == 0) continue;
            LocalDate os = day(original.opt("start_date")), oe = day(original.opt("end_date"));
            String ost = s(original.opt("status")).toUpperCase(Locale.ROOT);
            boolean wasActive = ost.isEmpty() || "ACTIVE".equals(ost);
            boolean inside = os != null && !r.start().isBefore(os) && (oe == null || (r.end() != null && !r.end().isAfter(oe)));
            (!r.active() || (wasActive && inside) ? shrinking : growing).add(new Object[]{r.start(), r.id, changes});
        }
        shrinking.sort((x, y) -> ((LocalDate) x[0]).compareTo((LocalDate) y[0]));
        growing.sort((x, y) -> ((LocalDate) x[0]).compareTo((LocalDate) y[0]));
        for (Object[] o : shrinking) plan.updates.add(new Object[]{o[1], o[2]});
        for (Object[] o : growing) plan.updates.add(new Object[]{o[1], o[2]});
        List<Row> fresh = new ArrayList<>();
        for (Row r : rows) if (r.id == null) fresh.add(r);
        fresh.sort((x, y) -> x.start().compareTo(y.start()));
        for (Row r : fresh) {
            JSONObject ins = new JSONObject(base.toString());
            Iterator<String> it = r.data.keys();
            while (it.hasNext()) { String k = it.next(); ins.put(k, r.data.opt(k)); }
            plan.inserts.add(ins);
        }
        return plan;
    }

    /** save_price_history_grid: validate, plan and write (updates in order, then inserts). */
    static PriceHistoryPlan save(Api api, String partId, String supplierId, String rawId, List<JSONObject> edited) throws Exception {
        if (partId == null || partId.isEmpty() || supplierId == null || supplierId.isEmpty())
            throw new Rule("Select the Part and Supplier Raw Material record before saving price history.");
        String path = TABLE + "?select=*&part_id=eq." + Api.enc(partId) + "&supplier_id=eq." + Api.enc(supplierId)
            + (rawId == null || rawId.isEmpty() ? "" : "&raw_material_detail_id=eq." + Api.enc(rawId)) + "&order=start_date.asc&limit=5000";
        List<JSONObject> existing = SupSvc.list(api.rows(path));
        JSONObject base = new JSONObject().put("part_id", partId).put("supplier_id", supplierId).put("raw_material_detail_id", rawId == null || rawId.isEmpty() ? JSONObject.NULL : rawId);
        PriceHistoryPlan plan = plan(existing, edited, base);
        for (Object[] u : plan.updates) api.update(TABLE, (String) u[0], (JSONObject) u[1]);
        for (JSONObject ins : plan.inserts) api.insert(TABLE, ins);
        return plan;
    }
}
