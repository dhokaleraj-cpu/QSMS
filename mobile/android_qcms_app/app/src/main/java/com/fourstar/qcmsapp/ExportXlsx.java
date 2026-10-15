package com.fourstar.qcmsapp;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/**
 * Real Excel workbook (.xlsx, Office Open XML) written with java.util.zip - no library needed.
 * One "Details" sheet for the key-value sections, one sheet per table: title rows, bold teal header,
 * frozen header row, auto filter, column widths, numbers stored as numbers.
 */
final class ExportXlsx {
    private ExportXlsx() { }

    private static final class Sheet {
        final String name;
        final List<List<String>> rows = new ArrayList<>();
        final List<Integer> styles = new ArrayList<>();   // style per row: 0 normal, 1 header, 3 title, 4 label row
        int headerRow = -1;
        int columns = 1;
        Sheet(String name) { this.name = name; }
        void add(List<String> row, int style) { rows.add(row); styles.add(style); columns = Math.max(columns, row.size()); }
    }

    static byte[] build(ExportDoc doc, String printedBy) throws Exception {
        List<Sheet> sheets = new ArrayList<>();
        Set<String> used = new HashSet<>();
        String printed = "Printed " + new SimpleDateFormat("dd-MM-yyyy HH:mm", Locale.ENGLISH).format(new Date())
            + (printedBy == null || printedBy.isEmpty() ? "" : " by " + printedBy);

        boolean hasPairs = false;
        for (ExportDoc.Section s : doc.sections) if (!s.pairs.isEmpty()) hasPairs = true;
        if (hasPairs || doc.tables.isEmpty()) {
            Sheet d = new Sheet(sheetName("Details", used));
            d.add(list(doc.title), 3);
            d.add(list(ExportPdf.COMPANY + (doc.subtitle.isEmpty() ? "" : " · " + doc.subtitle) + " · " + printed), 0);
            d.add(list(""), 0);
            for (ExportDoc.Section s : doc.sections) {
                if (s.pairs.isEmpty()) continue;
                d.add(list(s.title.isEmpty() ? "Details" : s.title), 1);
                for (String[] p : s.pairs) d.add(list(p[0], p[1]), 0);
                d.add(list(""), 0);
            }
            sheets.add(d);
        }
        for (ExportDoc.Table t : doc.tables) {
            Sheet s = new Sheet(sheetName(t.title.isEmpty() ? doc.title : t.title, used));
            s.add(list(t.title.isEmpty() ? doc.title : t.title), 3);
            s.add(list(doc.title + " · " + printed), 0);
            s.headerRow = s.rows.size();
            s.add(new ArrayList<>(t.columns), 1);
            for (List<String> r : t.rows) s.add(new ArrayList<>(r), 0);
            sheets.add(s);
        }

        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(bytes)) {
            StringBuilder types = new StringBuilder("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                + "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
                + "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
                + "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
                + "<Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/>"
                + "<Override PartName=\"/xl/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml\"/>");
            for (int i = 1; i <= sheets.size(); i++)
                types.append("<Override PartName=\"/xl/worksheets/sheet").append(i).append(".xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>");
            types.append("</Types>");
            put(zip, "[Content_Types].xml", types.toString());
            put(zip, "_rels/.rels", "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                + "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
                + "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/>"
                + "</Relationships>");
            StringBuilder wb = new StringBuilder("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                + "<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"><sheets>");
            StringBuilder rels = new StringBuilder("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
                + "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">");
            for (int i = 1; i <= sheets.size(); i++) {
                wb.append("<sheet name=\"").append(xml(sheets.get(i - 1).name)).append("\" sheetId=\"").append(i).append("\" r:id=\"rId").append(i).append("\"/>");
                rels.append("<Relationship Id=\"rId").append(i).append("\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet").append(i).append(".xml\"/>");
            }
            wb.append("</sheets></workbook>");
            rels.append("<Relationship Id=\"rId").append(sheets.size() + 1).append("\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/></Relationships>");
            put(zip, "xl/workbook.xml", wb.toString());
            put(zip, "xl/_rels/workbook.xml.rels", rels.toString());
            put(zip, "xl/styles.xml", STYLES);
            for (int i = 0; i < sheets.size(); i++) put(zip, "xl/worksheets/sheet" + (i + 1) + ".xml", sheetXml(sheets.get(i)));
        }
        return bytes.toByteArray();
    }

    // styles: 0 normal, 1 header (bold, teal fill, border), 2 body (border), 3 title (bold 14), 4 number body (border)
    private static final String STYLES = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        + "<styleSheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">"
        + "<fonts count=\"3\"><font><sz val=\"10\"/><name val=\"Calibri\"/></font>"
        + "<font><b/><sz val=\"10\"/><color rgb=\"FF0B6E70\"/><name val=\"Calibri\"/></font>"
        + "<font><b/><sz val=\"14\"/><color rgb=\"FF173233\"/><name val=\"Calibri\"/></font></fonts>"
        + "<fills count=\"3\"><fill><patternFill patternType=\"none\"/></fill><fill><patternFill patternType=\"gray125\"/></fill>"
        + "<fill><patternFill patternType=\"solid\"><fgColor rgb=\"FFE3F2F2\"/><bgColor indexed=\"64\"/></patternFill></fill></fills>"
        + "<borders count=\"2\"><border><left/><right/><top/><bottom/><diagonal/></border>"
        + "<border><left style=\"thin\"><color rgb=\"FFB5CFCF\"/></left><right style=\"thin\"><color rgb=\"FFB5CFCF\"/></right>"
        + "<top style=\"thin\"><color rgb=\"FFB5CFCF\"/></top><bottom style=\"thin\"><color rgb=\"FFB5CFCF\"/></bottom><diagonal/></border></borders>"
        + "<cellStyleXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\"/></cellStyleXfs>"
        + "<cellXfs count=\"5\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\" xfId=\"0\"/>"
        + "<xf numFmtId=\"0\" fontId=\"1\" fillId=\"2\" borderId=\"1\" xfId=\"0\" applyFont=\"1\" applyFill=\"1\" applyBorder=\"1\"><alignment vertical=\"center\" wrapText=\"1\"/></xf>"
        + "<xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"1\" xfId=\"0\" applyBorder=\"1\"><alignment vertical=\"top\"/></xf>"
        + "<xf numFmtId=\"0\" fontId=\"2\" fillId=\"0\" borderId=\"0\" xfId=\"0\" applyFont=\"1\"/>"
        + "<xf numFmtId=\"4\" fontId=\"0\" fillId=\"0\" borderId=\"1\" xfId=\"0\" applyNumberFormat=\"1\" applyBorder=\"1\"/></cellXfs>"
        + "<cellStyles count=\"1\"><cellStyle name=\"Normal\" xfId=\"0\" builtinId=\"0\"/></cellStyles></styleSheet>";

    private static String sheetXml(Sheet s) {
        StringBuilder x = new StringBuilder("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            + "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">");
        if (s.headerRow >= 0) {
            int top = s.headerRow + 2;
            x.append("<sheetViews><sheetView workbookViewId=\"0\"><pane xSplit=\"1\" ySplit=\"").append(s.headerRow + 1)
             .append("\" topLeftCell=\"B").append(top).append("\" activePane=\"bottomRight\" state=\"frozen\"/></sheetView></sheetViews>");
        }
        // column widths from content (characters)
        int[] width = new int[s.columns];
        for (int ri = Math.max(0, s.headerRow); ri < s.rows.size(); ri++) {
            List<String> row = s.rows.get(ri);
            for (int c = 0; c < row.size() && c < width.length; c++) {
                String v = row.get(c) == null ? "" : row.get(c);
                width[c] = Math.max(width[c], Math.min(60, v.length() + 2));
            }
        }
        x.append("<cols>");
        for (int c = 0; c < width.length; c++) {
            int w = Math.max(10, width[c]);
            x.append("<col min=\"").append(c + 1).append("\" max=\"").append(c + 1).append("\" width=\"").append(w).append("\" customWidth=\"1\"/>");
        }
        x.append("</cols><sheetData>");
        // identifier columns (HSN, codes, numbers, positions, phone) stay text even when they look numeric
        boolean[] textColumn = new boolean[s.columns];
        if (s.headerRow >= 0) {
            List<String> head = s.rows.get(s.headerRow);
            for (int c = 0; c < head.size() && c < textColumn.length; c++) {
                String h = " " + (head.get(c) == null ? "" : head.get(c)).toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]+", " ") + " ";
                textColumn[c] = h.matches(".*( hsn| sac| code| no| number| num| pos| posnr| position| phone| mobile| pin| gstin| heat| lot| batch| serial| id| ref| reference| order| invoice| challan| asn| tc| rmtc| item| part| drawing| rev| revision| year).*");
            }
        }
        for (int r = 0; r < s.rows.size(); r++) {
            List<String> row = s.rows.get(r);
            int style = s.styles.get(r);
            boolean body = s.headerRow >= 0 && r > s.headerRow;
            x.append("<row r=\"").append(r + 1).append("\">");
            for (int c = 0; c < row.size(); c++) {
                String v = row.get(c) == null ? "" : row.get(c);
                String ref = col(c) + (r + 1);
                String num = number(v);
                if (body && num != null && !(c < textColumn.length && textColumn[c])) {
                    x.append("<c r=\"").append(ref).append("\" s=\"").append(v.contains(".") ? 4 : 2).append("\"><v>").append(num).append("</v></c>");
                } else {
                    int st = body ? 2 : style;
                    if (v.isEmpty() && st == 0) continue;
                    x.append("<c r=\"").append(ref).append("\" t=\"inlineStr\" s=\"").append(st).append("\"><is><t xml:space=\"preserve\">").append(xml(v)).append("</t></is></c>");
                }
            }
            x.append("</row>");
        }
        x.append("</sheetData>");
        if (s.headerRow >= 0 && s.columns > 0) {
            x.append("<autoFilter ref=\"A").append(s.headerRow + 1).append(":").append(col(s.columns - 1)).append(Math.max(s.rows.size(), s.headerRow + 1)).append("\"/>");
        }
        x.append("</worksheet>");
        return x.toString();
    }

    /** Numeric text (Indian / western grouping allowed) as a plain number; codes with leading zeros stay text. */
    static String number(String v) {
        String s = v == null ? "" : v.trim();
        if (s.isEmpty() || s.length() > 15) return null;
        if (!s.matches("-?[0-9][0-9,]*(\\.[0-9]+)?")) return null;
        String plain = s.replace(",", "");
        String digits = plain.startsWith("-") ? plain.substring(1) : plain;
        if (digits.length() > 1 && digits.startsWith("0") && !digits.startsWith("0.")) return null;
        if (s.contains(",") && !s.matches("-?[0-9]{1,3}(,[0-9]{2,3})*(\\.[0-9]+)?")) return null;
        return plain;
    }

    static String col(int index) {
        StringBuilder b = new StringBuilder();
        int n = index + 1;
        while (n > 0) { int m = (n - 1) % 26; b.insert(0, (char) ('A' + m)); n = (n - 1) / 26; }
        return b.toString();
    }

    static String sheetName(String raw, Set<String> used) {
        String base = (raw == null ? "" : raw).replaceAll("[\\[\\]:*?/\\\\']", " ").trim();
        if (base.isEmpty()) base = "Sheet";
        if (base.length() > 28) base = base.substring(0, 28).trim();
        String name = base;
        int i = 2;
        while (used.contains(name.toLowerCase(Locale.ROOT))) name = base + " " + (i++);
        used.add(name.toLowerCase(Locale.ROOT));
        return name;
    }

    static String xml(String s) {
        StringBuilder b = new StringBuilder();
        for (char ch : (s == null ? "" : s).toCharArray()) {
            switch (ch) {
                case '&': b.append("&amp;"); break;
                case '<': b.append("&lt;"); break;
                case '>': b.append("&gt;"); break;
                case '"': b.append("&quot;"); break;
                default:
                    if (ch < 0x20 && ch != '\n' && ch != '\t' && ch != '\r') continue;   // not allowed in XML
                    b.append(ch);
            }
        }
        return b.toString();
    }

    private static List<String> list(String... values) {
        List<String> l = new ArrayList<>();
        for (String v : values) l.add(v);
        return l;
    }

    private static void put(ZipOutputStream zip, String name, String content) throws Exception {
        zip.putNextEntry(new ZipEntry(name));
        zip.write(content.getBytes(StandardCharsets.UTF_8));
        zip.closeEntry();
    }
}
