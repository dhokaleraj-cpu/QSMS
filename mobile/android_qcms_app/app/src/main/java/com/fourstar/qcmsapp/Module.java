package com.fourstar.qcmsapp;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** One QCMS module as shown in the app: register (grid), record view, native entry and actions. */
public final class Module {
    public interface Editor { Screen open(MainActivity a, String id, JSONObject prefill); }
    public interface Action { void run(MainActivity a, JSONObject row, Runnable refresh); }
    public interface Opener { Screen open(MainActivity a); }

    /** Child table shown on the record (e.g. inspection results of a report). */
    public static final class Child {
        public final String title, table, fk, order;
        public final String[][] cols;
        public Child(String title, String table, String fk, String order, String[][] cols) {
            this.title = title; this.table = table; this.fk = fk; this.order = order; this.cols = cols;
        }
    }

    public static final class Act {
        public final String label; public final Action action; public final String when;
        Act(String label, String when, Action action) { this.label = label; this.when = when; this.action = action; }
    }

    public final String key;
    public final String title;
    public final int tab;
    public final String section;
    public final String table;
    public String filter = "";
    public String order = "created_at.desc";
    public String description = "";
    public String titleField = "";
    public String statusField = "status";
    public final List<String[]> cols = new ArrayList<>();
    public String[] search = new String[0];
    public final List<Child> children = new ArrayList<>();
    public final List<Act> actions = new ArrayList<>();
    public String attachEntity;
    public String attachFolder;
    public Editor editor;
    public Opener custom;
    public boolean deletable = true;
    public String[] statusFilters = new String[0];

    /** Generic form (EditScreen) when no custom editor is set. */
    public final List<Field> form = new ArrayList<>();
    /** Document number generated on first save: field + RPC + JSON args (e.g. qsms_next_document_number). */
    public String numberField, numberRpc, numberArgs;
    /** Values always written on insert (e.g. party_types, status). */
    public JSONObject fixed;
    /** Validation / calculation before the generic save; throw an Exception with a clear message to stop. */
    public interface Hook { void apply(MainActivity a, Api api, JSONObject values, JSONObject existing) throws Exception; }
    public Hook beforeSave;
    /** Called after a successful generic save (follow-up writes). */
    public Hook afterSave;
    /** Attachment slots (document types) offered on the record; multi = titled photos (complaints style). */
    public String[] attachSlots = new String[0];
    public boolean attachMulti = false;
    /** Fields whose change is not allowed after the record leaves DRAFT (e.g. report links). */
    public boolean editable = true;

    public Module form(Field... fields) { for (Field f : fields) form.add(f); return this; }
    public Module numbered(String field, String rpc, String argsJson) { numberField = field; numberRpc = rpc; numberArgs = argsJson; return this; }
    public Module fixed(JSONObject values) { fixed = values; return this; }
    public Module before(Hook h) { beforeSave = h; return this; }
    public Module after(Hook h) { afterSave = h; return this; }
    public Module slots(String... types) { attachSlots = types; return this; }
    public Module multiAttach() { attachMulti = true; return this; }
    public Module noEdit() { editable = false; return this; }
    public boolean canCreate() { return editor != null || !form.isEmpty(); }

    public Module(String key, String title, int tab, String section, String table) {
        this.key = key; this.title = title; this.tab = tab; this.section = section; this.table = table;
    }

    public Module desc(String d) { description = d; return this; }
    public Module filter(String f) { filter = f; return this; }
    public Module order(String o) { order = o; return this; }
    public Module titleField(String f) { titleField = f; return this; }
    public Module status(String f) { statusField = f; return this; }
    /** Register column: field (or field.label path for FK), label, kind (text/date/num/status/fk). */
    public Module col(String field, String label) { cols.add(new String[]{field, label, ""}); return this; }
    public Module col(String field, String label, String kind) { cols.add(new String[]{field, label, kind}); return this; }
    public Module search(String... fields) { search = fields; return this; }
    public Module child(String title, String table, String fk, String order, String[][] cols) { children.add(new Child(title, table, fk, order, cols)); return this; }
    public Module action(String label, String when, Action a) { actions.add(new Act(label, when, a)); return this; }
    public Module attach(String entity, String folder) { attachEntity = entity; attachFolder = folder; return this; }
    public Module editor(Editor e) { editor = e; return this; }
    public Module custom(Opener o) { custom = o; return this; }
    public Module readOnly() { deletable = false; return this; }
    public Module statuses(String... s) { statusFilters = s; return this; }

    /** Primary key column ("" = rows cannot be opened, e.g. summary views). */
    public String idField = "id";
    public Module id(String field) { idField = field == null ? "" : field; return this; }

    public String selectList() {
        StringBuilder b = new StringBuilder(idField.isEmpty() ? (cols.isEmpty() ? "*" : cols.get(0)[0]) : idField);
        if (!titleField.isEmpty()) b.append(',').append(titleField);
        for (String[] c : cols) {
            String f = c[0];
            if (b.indexOf("," + f + ",") < 0 && !("," + b + ",").contains("," + f + ",")) b.append(',').append(f);
        }
        if (!statusField.isEmpty() && !("," + b + ",").contains("," + statusField + ",")) b.append(',').append(statusField);
        return b.toString();
    }

    public String recordTitle(JSONObject row) {
        String t = titleField.isEmpty() ? "" : Lookups.j(row, titleField);
        if (t.isEmpty() && !cols.isEmpty()) t = Lookups.j(row, cols.get(0)[0]);
        return t.isEmpty() ? title : t;
    }
}
