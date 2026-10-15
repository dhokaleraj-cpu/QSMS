package com.fourstar.qcmsapp;

import org.json.JSONObject;

/** One form field (same field kinds as the QCMS website forms). */
public final class Field {
    public static final String TEXT = "text", AREA = "area", INT = "int", NUM = "num", DATE = "date", BOOL = "bool",
        SELECT = "select", LOOKUP = "lookup", MULTI = "multi", INFO = "info";

    public interface Label { String of(JSONObject row); }

    /** Dropdown filled from a table (value = id). */
    public static final class Lookup {
        public final String table, select, filter, order;
        public final Label label;
        public Lookup(String table, String select, String filter, String order, Label label) {
            this.table = table; this.select = select; this.filter = filter == null ? "" : filter; this.order = order; this.label = label;
        }
        public String key() { return table + "?" + select + "&" + filter + "&" + order; }
        public Lookup where(String extraFilter) { return new Lookup(table, select, filter + extraFilter, order, label); }
    }

    public final String key;
    public final String label;
    public final String type;
    public boolean required;
    public boolean readOnly;
    public String hint = "";
    public String[] options = new String[0];
    public String[] optionLabels;
    public Lookup lookup;
    public Object def;
    public double min = Double.NaN, max = Double.NaN;

    public Field(String key, String label, String type) {
        this.key = key; this.label = label; this.type = type;
    }

    public static Field text(String key, String label) { return new Field(key, label, TEXT); }
    public static Field area(String key, String label) { return new Field(key, label, AREA); }
    public static Field integer(String key, String label) { return new Field(key, label, INT); }
    public static Field number(String key, String label) { return new Field(key, label, NUM); }
    public static Field date(String key, String label) { return new Field(key, label, DATE); }
    public static Field bool(String key, String label) { return new Field(key, label, BOOL); }
    public static Field info(String key, String label) { Field f = new Field(key, label, INFO); f.readOnly = true; return f; }
    public static Field select(String key, String label, String... options) { Field f = new Field(key, label, SELECT); f.options = options; return f; }
    public static Field multi(String key, String label, String... options) { Field f = new Field(key, label, MULTI); f.options = options; return f; }
    public static Field lookup(String key, String label, Lookup lookup) { Field f = new Field(key, label, LOOKUP); f.lookup = lookup; return f; }

    public Field req() { required = true; return this; }
    public Field ro() { readOnly = true; return this; }
    public Field hint(String h) { hint = h; return this; }
    public Field def(Object v) { def = v; return this; }
    public Field range(double lo, double hi) { min = lo; max = hi; return this; }
    public Field labels(String... l) { optionLabels = l; return this; }

    public String optionLabel(String value) {
        if (optionLabels != null) for (int i = 0; i < options.length && i < optionLabels.length; i++) if (options[i].equals(value)) return optionLabels[i];
        return Ui.pretty(value);
    }
}
