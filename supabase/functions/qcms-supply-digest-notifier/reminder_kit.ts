// STAWN QCMS · R36 reminder kit (shared by the scheduled reminder edge functions).
// IDENTICAL copy in: qcms-po-confirmation-reminder, qcms-po-approval-overdue,
// qcms-overdue-notifier, qcms-supply-digest-notifier. Edit all four together
// (tests/test_r36_reminder_emails.py checks that they are identical).
//
// - HTML / plain-text tables for reminder e-mail bodies (STAWN teal header, zebra rows)
// - branded e-mail shell
// - Excel attachment of the same rows (npm:xlsx)
// - print-layout PDF snapshots (public.qcms_document_snapshots, rendered by the website)
// - Purchase Order line details (PO + items + supplier + parts + customer orders)
import * as XLSX from "npm:xlsx@0.18.5";
import { Buffer } from "node:buffer";

export type Row = Record<string, any>;
export type ColKind = "text" | "number" | "money" | "date";
export type Col = string | { label: string; kind?: ColKind };
export type Cell = string | number | null | undefined;
export type MailAttachment = { filename: string; content: Buffer; contentType: string };
export type ManifestEntry = { bucket: string; object_path: string; file_name: string; mime_type: string; generated: boolean; source_table?: string; record_id?: string };
export type SnapshotRef = { source_table: string; record_id: string; updated_at?: string | null };

export const KIT_VERSION = "R36";
export const BRAND_TEAL = "#0F6E6E";
export const DOC_BUCKET = "quality-documents";
export const MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024;
export const XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

// ------------------------------------------------------------------ formatting
export function esc(value: any): string {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}
/** Clean DB text: null / "None" / "null" / "nan" become "". */
export function clean(value: any): string {
  const text = String(value ?? "").trim();
  return ["none", "null", "nan", "undefined"].includes(text.toLowerCase()) ? "" : text;
}
export function toNumber(value: any): number | null {
  if (value === null || value === undefined || value === "") return null;
  const x = Number(value);
  return Number.isFinite(x) ? x : null;
}
export function num(value: any, digits = 3): string {
  const x = toNumber(value);
  return x === null ? "" : x.toLocaleString("en-IN", { maximumFractionDigits: digits });
}
export function money(value: any, currency?: string): string {
  const x = toNumber(value);
  if (x === null) return "";
  const text = x.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return currency ? `${clean(currency)} ${text}`.trim() : text;
}
export function day(value: any): string {
  const text = clean(value);
  return /^\d{4}-\d{2}-\d{2}/.test(text) ? text.slice(0, 10) : text;
}
function colOf(col: Col): { label: string; kind: ColKind } {
  return typeof col === "string" ? { label: col, kind: "text" } : { label: col.label, kind: col.kind || "text" };
}
function fmtCell(value: Cell, kind: ColKind): string {
  if (value === null || value === undefined || value === "") return "";
  if (kind === "number") return typeof value === "number" ? num(value) : String(value);
  if (kind === "money") return typeof value === "number" ? money(value) : String(value);
  if (kind === "date") return day(value);
  return String(value);
}

// ------------------------------------------------------------------ tables
/** Bordered HTML table: teal header, zebra rows, right-aligned numbers. Empty cells show "-". */
export function htmlTable(headers: Col[], rows: Cell[][], opts: { totals?: Cell[]; caption?: string; dropEmpty?: boolean; keep?: string[] } = {}): string {
  let cols = headers.map(colOf).map((c, i) => ({ ...c, i }));
  if (opts.dropEmpty) {
    const keep = new Set((opts.keep || []).map((x) => x.toLowerCase()));
    cols = cols.filter((c) => keep.has(c.label.toLowerCase()) || rows.some((r) => fmtCell(r[c.i], c.kind) !== "") || (opts.totals && fmtCell(opts.totals[c.i], c.kind) !== ""));
  }
  const th = `padding:7px 8px;border:1px solid #0B5858;background:${BRAND_TEAL};color:#FFFFFF;font-size:12px;font-weight:700;text-align:left;white-space:nowrap`;
  const td = "padding:6px 8px;border:1px solid #D3DCE1;font-size:12px;color:#1F2A33;vertical-align:top";
  const align = (kind: ColKind) => (kind === "number" || kind === "money" ? "text-align:right;white-space:nowrap" : kind === "date" ? "white-space:nowrap" : "");
  let html = '<div style="margin:12px 0 16px 0;overflow-x:auto">';
  if (opts.caption) html += `<div style="font-size:14px;font-weight:700;color:${BRAND_TEAL};margin:0 0 6px 0">${esc(opts.caption)}</div>`;
  html += '<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;width:100%;font-family:Arial,Helvetica,sans-serif">';
  html += "<thead><tr>" + cols.map((c) => `<th style="${th};${c.kind === "number" || c.kind === "money" ? "text-align:right" : ""}">${esc(c.label)}</th>`).join("") + "</tr></thead><tbody>";
  if (!rows.length) html += `<tr><td colspan="${cols.length}" style="${td};text-align:center;color:#64748B">No records</td></tr>`;
  rows.forEach((row, idx) => {
    const bg = idx % 2 === 0 ? "#FFFFFF" : "#F1F7F7";
    html += "<tr>" + cols.map((c) => `<td style="${td};background:${bg};${align(c.kind)}">${esc(fmtCell(row[c.i], c.kind) || "-")}</td>`).join("") + "</tr>";
  });
  if (opts.totals) {
    html += "<tr>" + cols.map((c) => `<td style="${td};background:#E2EFEF;font-weight:700;${align(c.kind)}">${esc(fmtCell(opts.totals![c.i], c.kind))}</td>`).join("") + "</tr>";
  }
  return html + "</tbody></table></div>";
}

/** Drop columns that are empty in every row (labels in `keep` always stay). Same result feeds HTML, text and Excel. */
export function pruneColumns(headers: Col[], rows: Cell[][], keep: string[] = []): { headers: Col[]; rows: Cell[][] } {
  const keepSet = new Set(keep.map((x) => x.toLowerCase()));
  const idx = headers.map((h, i) => ({ c: colOf(h), i })).filter(({ c, i }) => keepSet.has(c.label.toLowerCase()) || rows.some((r) => fmtCell(r[i], c.kind) !== "")).map(({ i }) => i);
  return { headers: idx.map((i) => headers[i]), rows: rows.map((r) => idx.map((i) => r[i])) };
}

/** Plain-text table for the text/plain alternative of an e-mail. */
export function textTable(headers: Col[], rows: Cell[][], maxWidth = 28): string {
  const cols = headers.map(colOf);
  const cut = (s: string) => (s.length > maxWidth ? s.slice(0, maxWidth - 1) + "…" : s);
  const data = rows.map((r) => cols.map((c, i) => cut(fmtCell(r[i], c.kind) || "-")));
  const widths = cols.map((c, i) => Math.max(cut(c.label).length, ...data.map((r) => r[i].length)));
  const line = (cells: string[]) => cells.map((v, i) => (cols[i].kind === "number" || cols[i].kind === "money" ? v.padStart(widths[i]) : v.padEnd(widths[i]))).join(" | ");
  return [line(cols.map((c) => cut(c.label))), widths.map((w) => "-".repeat(w)).join("-+-"), ...data.map(line)].join("\n");
}

// ------------------------------------------------------------------ e-mail shell
export function emailShell(args: { title: string; intro?: string[]; sections?: string[]; footer?: string; company?: string }): string {
  const company = clean(args.company) || "STAWN QCMS";
  const intro = (args.intro || []).map((line) => (String(line).trim() ? `<p style="margin:0 0 6px 0">${esc(line)}</p>` : '<div style="height:6px"></div>')).join("");
  const footer = args.footer !== undefined ? args.footer : `Automatic reminder from STAWN QCMS · ${company}. Please do not reply to this automated message unless requested.`;
  return `<!doctype html><html><body style="margin:0;padding:0;background:#F3F6F8">`
    + `<div style="max-width:1180px;margin:0 auto;padding:16px;font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.5;color:#273444">`
    + `<div style="background:${BRAND_TEAL};color:#FFFFFF;padding:12px 16px;border-radius:6px 6px 0 0">`
    + `<div style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;opacity:.85">STAWN QCMS · ${esc(company)}</div>`
    + `<div style="font-size:17px;font-weight:700">${esc(args.title)}</div></div>`
    + `<div style="background:#FFFFFF;border:1px solid #D7DEE3;border-top:0;padding:16px;border-radius:0 0 6px 6px">`
    + intro + (args.sections || []).join("")
    + `<div style="margin-top:14px;padding-top:10px;border-top:1px solid #E2E8F0;font-size:11px;color:#64748B">${esc(footer)}</div>`
    + `</div></div></body></html>`;
}

/** Company name for e-mails: settings.sender_name, else tenants.tenant_name. Never throws. */
export async function companyName(admin: any, tenantId: string, settings: Row | null | undefined): Promise<string> {
  const sender = clean(settings?.sender_name);
  if (sender) return sender;
  try {
    const { data } = await admin.from("tenants").select("tenant_name").eq("id", tenantId).maybeSingle();
    return clean(data?.tenant_name) || "STAWN QCMS";
  } catch (_e) {
    return "STAWN QCMS";
  }
}

// ------------------------------------------------------------------ Excel
/** Excel workbook of the same rows. Numbers stay numeric; title rows on top; column widths; auto-filter.
 *  (Bold header is requested via cell styles; the community xlsx build may ignore styles.) */
export function xlsxAttachment(sheetName: string, headers: Col[], rows: Cell[][], fileName: string, opts: { title?: string; subtitle?: string } = {}): MailAttachment & { bytes: Uint8Array } {
  const cols = headers.map(colOf);
  const top: Cell[][] = [];
  if (opts.title) top.push([opts.title]);
  if (opts.subtitle) top.push([opts.subtitle]);
  if (top.length) top.push([]);
  const body = rows.map((r) => cols.map((c, i) => {
    const v = r[i];
    if (v === null || v === undefined) return "";
    if ((c.kind === "number" || c.kind === "money") && typeof v === "number") return v;
    return c.kind === "date" ? day(v) : String(v);
  }));
  const ws = XLSX.utils.aoa_to_sheet([...top, cols.map((c) => c.label), ...body]);
  const headerRow = top.length;
  cols.forEach((c, i) => {
    const ref = XLSX.utils.encode_cell({ r: headerRow, c: i });
    if (ws[ref]) (ws[ref] as any).s = { font: { bold: true, color: { rgb: "FFFFFF" } }, fill: { fgColor: { rgb: BRAND_TEAL.slice(1) } } };
    for (let r = 0; r < body.length; r++) {
      const cell = ws[XLSX.utils.encode_cell({ r: headerRow + 1 + r, c: i })] as any;
      if (cell && typeof cell.v === "number") cell.z = c.kind === "money" ? "#,##0.00" : "#,##0.###";
    }
  });
  if (opts.title && ws["A1"]) (ws["A1"] as any).s = { font: { bold: true, sz: 13 } };
  ws["!cols"] = cols.map((c, i) => ({ wch: Math.min(48, Math.max(8, c.label.length + 2, ...body.map((r) => String(r[i] ?? "").length + 2))) }));
  if (body.length) ws["!autofilter"] = { ref: XLSX.utils.encode_range({ s: { r: headerRow, c: 0 }, e: { r: headerRow + body.length, c: cols.length - 1 } }) };
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, (clean(sheetName) || "QCMS").replace(/[\\/?*\[\]:]/g, " ").slice(0, 31));
  const bytes = new Uint8Array(XLSX.write(wb, { bookType: "xlsx", type: "array" }) as ArrayBuffer);
  return { filename: safeFileName(fileName, "QCMS_Reminder.xlsx"), content: Buffer.from(bytes), contentType: XLSX_MIME, bytes };
}

export function safeFileName(name: string, fallback = "QCMS_Document"): string {
  return String(name || "").replace(/[^A-Za-z0-9_.-]+/g, "_").replace(/^_+|_+$/g, "") || fallback;
}

// ------------------------------------------------------------------ storage helpers
/** Upload a generated attachment so the outbox manifest can be re-sent by qcms-send-email (generated:true, removed after send).
 *  Returns null on failure; never throws. */
export async function storeGenerated(admin: any, tenantId: string, folder: string, att: { filename: string; contentType: string; bytes: Uint8Array }): Promise<ManifestEntry | null> {
  try {
    const path = `${tenantId}/notification_exports/automatic/${safeFileName(folder, "reminder")}/${crypto.randomUUID()}_${att.filename}`;
    const { error } = await admin.storage.from(DOC_BUCKET).upload(path, att.bytes, { contentType: att.contentType, upsert: false });
    if (error) return null;
    return { bucket: DOC_BUCKET, object_path: path, file_name: att.filename, mime_type: att.contentType, generated: true };
  } catch (_e) {
    return null;
  }
}
/** Remove generated (generated:true) manifest files after a successful send. Snapshots are never removed. */
export async function removeGenerated(admin: any, manifest: ManifestEntry[]): Promise<void> {
  for (const item of manifest) {
    if (!item?.generated || !item.object_path) continue;
    try { await admin.storage.from(item.bucket || DOC_BUCKET).remove([item.object_path]); } catch (_e) { /* ignore */ }
  }
}

// ------------------------------------------------------------------ document snapshots
export type SnapshotCache = Map<string, { snap: Row; bytes: Uint8Array } | null>;

/** Latest print-layout PDFs (website snapshots) for the referenced records, as nodemailer attachments + manifest entries.
 *  Skips missing / outdated snapshots (snapshot older than ref.updated_at), at most `limit` files and `maxBytes` total.
 *  Never throws. */
export async function snapshotAttachments(admin: any, tenantId: string, refs: SnapshotRef[], limit = 10, maxBytes = MAX_ATTACHMENT_BYTES, cache?: SnapshotCache): Promise<{ attachments: MailAttachment[]; manifest: ManifestEntry[]; bytes: number; skipped: number }> {
  const out = { attachments: [] as MailAttachment[], manifest: [] as ManifestEntry[], bytes: 0, skipped: 0 };
  try {
    const seen = new Set<string>(); const unique: SnapshotRef[] = [];
    for (const ref of refs || []) {
      const key = `${ref?.source_table}:${ref?.record_id}`;
      if (!ref?.source_table || !ref?.record_id || seen.has(key)) continue;
      seen.add(key); unique.push(ref);
    }
    if (!unique.length || limit <= 0) return out;
    const missing = unique.filter((r) => !cache?.has(`${r.source_table}:${r.record_id}`)).map((r) => r.record_id);
    const found = new Map<string, Row>();
    for (let i = 0; i < missing.length; i += 150) {
      const { data, error } = await admin.from("qcms_document_snapshots").select("*").eq("tenant_id", tenantId).eq("doc_kind", "PDF_SAFE").in("record_id", missing.slice(i, i + 150));
      if (error) break;
      for (const row of data || []) found.set(`${row.source_table}:${row.record_id}`, row);
    }
    const names = new Set<string>();
    for (const ref of unique) {
      if (out.attachments.length >= limit) break;
      const key = `${ref.source_table}:${ref.record_id}`;
      let entry = cache?.get(key);
      if (entry === undefined) {
        const snap = found.get(key);
        entry = null;
        if (snap?.object_path) {
          try {
            const { data: blob, error } = await admin.storage.from(snap.bucket || DOC_BUCKET).download(snap.object_path);
            if (!error && blob) entry = { snap, bytes: new Uint8Array(await blob.arrayBuffer()) };
          } catch (_e) { entry = null; }
        }
        cache?.set(key, entry);
      }
      if (!entry) { out.skipped++; continue; }
      const snapAt = Date.parse(String(entry.snap.record_updated_at || ""));
      const recAt = Date.parse(String(ref.updated_at || ""));
      if (Number.isFinite(recAt) && (!Number.isFinite(snapAt) || snapAt + 1000 < recAt)) { out.skipped++; continue; } // outdated PDF: never send it
      if (out.bytes + entry.bytes.byteLength > maxBytes) { out.skipped++; continue; }
      let name = safeFileName(entry.snap.file_name || `${ref.source_table}.pdf`, "QCMS_Document.pdf");
      if (names.has(name.toLowerCase())) name = `${String(ref.record_id).slice(0, 8)}_${name}`;
      names.add(name.toLowerCase());
      const mime = clean(entry.snap.mime_type) || "application/pdf";
      out.attachments.push({ filename: name, content: Buffer.from(entry.bytes), contentType: mime });
      out.manifest.push({ bucket: entry.snap.bucket || DOC_BUCKET, object_path: entry.snap.object_path, file_name: name, mime_type: mime, generated: false, source_table: ref.source_table, record_id: ref.record_id });
      out.bytes += entry.bytes.byteLength;
    }
  } catch (_e) { /* attachments are best-effort; the reminder is still sent */ }
  return out;
}

// ------------------------------------------------------------------ Purchase Order lines
export type PoLine = {
  po_id: string; po_number: string; po_type: string; po_date: string; po_status: string; approval_status: string;
  supplier_id: string; supplier: string; item_id: string; item_no: string; part_number: string; fsi_part_number: string;
  description: string; material: string; qty: number | null; uom: string; unit_price: number | null; currency: string;
  line_value: number | null; delivery_date: string; po_delivery_date?: string; customer: string; customer_order_no: string; updated_at: string;
};

export const PO_LINE_HEADERS: Col[] = [
  "PO No", { label: "PO Date", kind: "date" }, "Supplier", "Item No", "Part Number", "FSI Part No", "Description",
  "Material / RM Section", { label: "Qty", kind: "number" }, "UOM", { label: "Unit Price", kind: "money" }, "Currency",
  { label: "Line Value", kind: "money" }, { label: "Delivery Date", kind: "date" }, "Customer", "Customer Order No",
];
/** R36b: customer details are internal. Anything that can reach a supplier / vendor uses this: no customer, no
 *  customer order no, no customer part number, no customer delivery date (PO delivery date only). */
export const SUPPLIER_SAFE_HIDDEN = new Set(["Customer", "Customer Order No", "Part Number"]);
export function supplierSafeLine(line: PoLine): PoLine {
  return { ...line, part_number: "", customer: "", customer_order_no: "", delivery_date: line.po_delivery_date || "" };
}
export function poLineCells(line: PoLine): Cell[] {
  return [line.po_number, line.po_date, line.supplier, line.item_no, line.part_number, line.fsi_part_number, line.description,
    line.material, line.qty, line.uom, line.unit_price, line.currency, line.line_value, line.delivery_date, line.customer, line.customer_order_no];
}
/** Totals row for PO_LINE_HEADERS (qty per UOM when single UOM, value per currency). */
export function poLineTotals(lines: PoLine[]): Cell[] {
  const uoms = Array.from(new Set(lines.map((l) => l.uom).filter(Boolean)));
  const currencies = Array.from(new Set(lines.map((l) => l.currency).filter(Boolean)));
  const qty = uoms.length <= 1 ? lines.reduce((s, l) => s + (l.qty || 0), 0) : null;
  const value = currencies.length <= 1 ? lines.reduce((s, l) => s + (l.line_value || 0), 0) : null;
  const valueText = currencies.length > 1 ? currencies.map((c) => money(lines.filter((l) => l.currency === c).reduce((s, l) => s + (l.line_value || 0), 0), c)).join(" · ") : value;
  return ["Total", "", "", "", "", "", `${lines.length} line(s)`, "", qty, uoms.length === 1 ? uoms[0] : "", "", currencies.length === 1 ? currencies[0] : "", valueText, "", "", ""];
}
export function poTotalsText(lines: PoLine[]): string {
  const byCurrency = new Map<string, number>();
  for (const l of lines) byCurrency.set(l.currency || "", (byCurrency.get(l.currency || "") || 0) + (l.line_value || 0));
  const value = Array.from(byCurrency.entries()).map(([c, v]) => money(v, c)).join(" · ") || "-";
  const byUom = new Map<string, number>();
  for (const l of lines) byUom.set(l.uom || "", (byUom.get(l.uom || "") || 0) + (l.qty || 0));
  const qty = Array.from(byUom.entries()).map(([u, q]) => `${num(q)} ${u}`.trim()).join(" · ") || "-";
  return `${lines.length} line(s) · total quantity ${qty} · total value (excl. tax) ${value}`;
}
/** Latest change of a PO (header or any line) for snapshot freshness checks. */
export function poUpdatedAt(lines: PoLine[], poId: string, fallback?: string): string {
  let best = Date.parse(String(fallback || "")); let text = String(fallback || "");
  for (const l of lines) {
    if (l.po_id !== poId) continue;
    const t = Date.parse(l.updated_at);
    if (Number.isFinite(t) && (!Number.isFinite(best) || t > best)) { best = t; text = l.updated_at; }
  }
  return text;
}

/** Tenant-scoped `.in()` select in chunks of 150 ids. Throws on error (callers catch). */
export async function selectIn(admin: any, table: string, columns: string, tenantId: string, column: string, ids: string[], extra?: (q: any) => any): Promise<Row[]> {
  const out: Row[] = []; const unique = Array.from(new Set(ids.filter(Boolean)));
  for (let i = 0; i < unique.length; i += 150) {
    let q = admin.from(table).select(columns).eq("tenant_id", tenantId).in(column, unique.slice(i, i + 150));
    if (extra) q = extra(q);
    const { data, error } = await q.limit(5000);
    if (error) throw error;
    out.push(...(data || []));
  }
  return out;
}

/** All lines of the given Purchase Orders with supplier, part and customer-order details. Never throws (returns [] on error). */
export async function poLineRows(admin: any, tenantId: string, poIds: string[]): Promise<PoLine[]> {
  try {
    const ids = Array.from(new Set((poIds || []).map(String).filter(Boolean)));
    if (!ids.length) return [];
    const pos = await selectIn(admin, "supply_purchase_orders", "id,po_number,po_type,order_date,delivery_date,supplier_id,currency,status,approval_status,updated_at", tenantId, "id", ids);
    const items = await selectIn(admin, "supply_purchase_order_items", "*", tenantId, "purchase_order_id", ids, (q) => q.order("created_at"));
    const sources = await selectIn(admin, "supply_purchase_order_sources", "purchase_order_id,purchase_order_item_id,customer_order_id", tenantId, "purchase_order_id", ids);
    const orderIds = [...items.map((i) => String(i.customer_order_id || "")), ...sources.map((s) => String(s.customer_order_id || ""))];
    const orders = await selectIn(admin, "supply_customer_orders", "id,customer_order_no,master_reference_no,customer_id,part_id,customer_delivery_date", tenantId, "id", orderIds);
    const orderMap = new Map<string, Row>(orders.map((o) => [String(o.id), o]));
    const partyIds = [...pos.map((p) => String(p.supplier_id || "")), ...orders.map((o) => String(o.customer_id || ""))];
    const parties = await selectIn(admin, "parties", "id,party_code,party_name", tenantId, "id", partyIds);
    const partyMap = new Map<string, Row>(parties.map((p) => [String(p.id), p]));
    const parts = await selectIn(admin, "parts", "id,part_number,fsi_part_number,part_name", tenantId, "id", [...items.map((i) => String(i.part_id || "")), ...orders.map((o) => String(o.part_id || ""))]);
    const partMap = new Map<string, Row>(parts.map((p) => [String(p.id), p]));
    const poMap = new Map<string, Row>(pos.map((p) => [String(p.id), p]));
    const sourcesByItem = new Map<string, Row[]>();
    for (const s of sources) sourcesByItem.set(String(s.purchase_order_item_id || ""), [...(sourcesByItem.get(String(s.purchase_order_item_id || "")) || []), s]);
    const lines: PoLine[] = [];
    for (const poId of ids) {
      const po = poMap.get(poId); if (!po) continue;
      const supplier = partyMap.get(String(po.supplier_id || "")) || {};
      for (const item of items.filter((i) => String(i.purchase_order_id) === poId)) {
        const linked = [String(item.customer_order_id || ""), ...(sourcesByItem.get(String(item.id)) || []).map((s) => String(s.customer_order_id || ""))].filter(Boolean);
        const linkedOrders = Array.from(new Set(linked)).map((id) => orderMap.get(id)).filter(Boolean) as Row[];
        const part = partMap.get(String(item.part_id || "")) || partMap.get(String(linkedOrders[0]?.part_id || "")) || {};
        const customers = Array.from(new Set(linkedOrders.map((o) => clean(partyMap.get(String(o.customer_id || ""))?.party_name)).filter(Boolean)));
        const orderNos = Array.from(new Set(linkedOrders.map((o) => clean(o.customer_order_no) || clean(o.master_reference_no)).filter(Boolean)));
        const qty = toNumber(item.quantity); const price = toNumber(item.unit_price);
        const lineValue = qty !== null && price !== null ? Math.round(qty * price * 100) / 100 : toNumber(item.line_total);
        const itemUpdated = Date.parse(String(item.updated_at || "")), poUpdated = Date.parse(String(po.updated_at || ""));
        lines.push({
          po_id: poId, po_number: clean(po.po_number), po_type: clean(po.po_type).replaceAll("_", " "), po_date: day(po.order_date),
          po_status: clean(po.status), approval_status: clean(po.approval_status), supplier_id: clean(po.supplier_id),
          supplier: clean(supplier.party_name) || clean(supplier.party_code), item_id: String(item.id), item_no: clean(item.item_no),
          part_number: clean(item.original_part_number_snapshot) || clean(part.part_number),
          fsi_part_number: clean(item.fsi_part_number_snapshot) || clean(part.fsi_part_number),
          description: clean(item.item_description) || clean(part.part_name), material: clean(item.rm_section),
          qty, uom: clean(item.uom).toUpperCase(), unit_price: price, currency: clean(po.currency) || "INR", line_value: lineValue,
          delivery_date: day(po.delivery_date) || day(linkedOrders[0]?.customer_delivery_date),
          po_delivery_date: day(po.delivery_date),
          customer: customers.join(", "), customer_order_no: orderNos.join(", "),
          updated_at: (Number.isFinite(itemUpdated) && (!Number.isFinite(poUpdated) || itemUpdated > poUpdated)) ? String(item.updated_at) : String(po.updated_at || ""),
        });
      }
    }
    return lines;
  } catch (_e) {
    return [];
  }
}
