package com.fourstar.qcmsapp;

import java.util.ArrayList;
import java.util.List;

/**
 * Printable / downloadable content of one screen (record, register, report or entry):
 * key-value sections and tables. ExportKit turns it into PDF, Excel (.xlsx), print jobs and emails.
 */
public final class ExportDoc {
    public static final class Section {
        public final String title;
        public final List<String[]> pairs = new ArrayList<>();
        Section(String title) { this.title = title == null ? "" : title; }
        public Section pair(String label, String value) {
            pairs.add(new String[]{label == null ? "" : label, value == null ? "" : value});
            return this;
        }
    }

    public static final class Table {
        public final String title;
        public final List<String> columns;
        public final List<List<String>> rows;
        Table(String title, List<String> columns, List<List<String>> rows) {
            this.title = title == null ? "" : title;
            this.columns = columns == null ? new ArrayList<>() : columns;
            this.rows = rows == null ? new ArrayList<>() : rows;
        }
    }

    public final String title;
    public String subtitle = "";
    public String fileBase;
    /** Record kind for email subject / file names, e.g. "Purchase Order". */
    public String kind = "";
    public final List<Section> sections = new ArrayList<>();
    public final List<Table> tables = new ArrayList<>();

    public ExportDoc(String title) {
        this.title = title == null || title.trim().isEmpty() ? "QCMS Report" : title.trim();
        this.fileBase = "QCMS_" + this.title;
    }

    public ExportDoc subtitle(String s) { subtitle = s == null ? "" : s; return this; }
    public ExportDoc file(String base) { if (base != null && !base.trim().isEmpty()) fileBase = base.trim(); return this; }

    public Section section(String title) {
        Section s = new Section(title);
        sections.add(s);
        return s;
    }

    public Table table(String title, List<String> columns, List<List<String>> rows) {
        Table t = new Table(title, columns, rows);
        tables.add(t);
        return t;
    }

    public boolean isEmpty() {
        for (Section s : sections) if (!s.pairs.isEmpty()) return false;
        for (Table t : tables) if (!t.columns.isEmpty()) return false;
        return true;
    }

    public int rowCount() {
        int n = 0;
        for (Table t : tables) n += t.rows.size();
        return n;
    }

    /** A screen that can describe its own printable content (otherwise ExportKit reads the views). */
    public interface Source {
        /** Runs on a background thread (may load every row from the server). */
        ExportDoc export() throws Exception;
    }
}
