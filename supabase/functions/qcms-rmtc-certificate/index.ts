import { createClient } from "npm:@supabase/supabase-js@2";
import { PDFDocument, PDFString, StandardFonts, rgb, type PDFFont, type PDFPage } from "npm:pdf-lib@1.17.1";
import { zipSync } from "npm:fflate@0.8.2";

// QCMS qcms-rmtc-certificate · build 4.14.49-R40
// PUBLIC (verify_jwt = false), read-only. The QR stuck at the material storage location encodes
//   <SUPABASE_URL>/functions/v1/qcms-rmtc-certificate?t=<32-char token>
// The random token (public.rmtc_qr_tokens, not revoked) is the only key - no QCMS login is needed.
//   ?t=<token>                         -> ONE combined PDF, inline (RMTC_<no>_All_Documents.pdf): PAGE 1 = index (RMTC no,
//                                         heat, grade, supplier, approval date, FSI part numbers, ALL documents with per-file
//                                         Download links + "Download all (ZIP)"), then the certificate and every merged
//                                         PDF / image attachment. Above 50 MB: the index page only, with a note.
//   ?t=<token>&f=index                 -> the index page only (inline PDF).
//   ?t=<token>&f=zip                   -> ZIP of all documents (built in memory, 50 MB cap, unique file names).
//   ?t=<token>&f=pdf                   -> the same combined PDF as a download (attachment; other file types listed on a
//                                         final page) - pdf-lib.
//   ?t=<token>&d=<attachment uuid | certificate | copy> -> 302 to a 10-minute signed download URL of that one file.
// Documents = rmtc_qr_tokens.certificate_path (customer-safe approved RMTC print) + ACTIVE document_attachments of the
// RMTC (entity_type RMTC, never the QR label itself, never customer-only entity types) + legacy rmtc_approvals.rmtc_copy_path.
// Every file must belong to the token's tenant. No customer name / code / PO / customer part number is shown.
// Supabase rewrites text/html (and XHTML / XML) from *.supabase.co to text/plain, so the "page" for ?t= is a PDF whose
// first page is the index with tappable Download links.
// ?t=<token>&f=json returns the same document list as JSON (for the QCMS apps).

const SIGNED_URL_SECONDS = 600;
const TOKEN_RE = /^[A-Za-z0-9]{32}$/;
const UUID_RE = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;
const MAX_BUNDLE_BYTES = 50 * 1024 * 1024;
const MAX_FILES = 60;
const BUCKET = "quality-documents";
const APPROVED_STATUSES = ["APPROVED", "PARTIALLY_APPROVED"];
const APPROVED_DISPOSITIONS = ["ACCEPTED", "ACCEPTED_UNDER_RESERVE"];
const CUSTOMER_ONLY_ENTITY_TYPES = ["SUPPLY_CUSTOMER_ORDER", "CUSTOMER_STANDARD"];
const EXCLUDED_DOCUMENT_TYPES = ["RMTC_QR_LABEL"];
const DOC_LABELS: Record<string, string> = {
  CERTIFICATE: "Approved RMTC certificate (QCMS)",
  RMTC_COPY: "Supplier test certificate",
  RMTC_ATTACHMENT_2: "Supporting document",
  RMTC_ATTACHMENT_3: "Additional document",
};
const DOC_ORDER = ["CERTIFICATE", "RMTC_COPY", "RMTC_ATTACHMENT_2", "RMTC_ATTACHMENT_3"];

// --------------------------------------------------------------------------- simple per-instance rate limit
const HITS = new Map<string, number[]>();
function rateLimited(key: string, limit: number, windowMs = 60_000): boolean {
  const now = Date.now();
  const list = (HITS.get(key) || []).filter((t) => now - t < windowMs);
  list.push(now);
  HITS.set(key, list);
  if (HITS.size > 5000) HITS.clear();
  return list.length > limit;
}

// --------------------------------------------------------------------------- responses
// Supabase serves any markup (text/html, XHTML, XML) from *.supabase.co as text/plain and SVG as a sandboxed attachment,
// so a browser page cannot be rendered by an Edge Function on the default domain. The landing "page" is therefore the
// combined PDF (index page first, tappable links) - phones open it directly - and errors are plain text.
function message(status: number, title: string, text: string): Response {
  return new Response(`${title}\n\n${text}\n\nSTAWN QCMS - RMTC documents via QR`, {
    status,
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "X-Robots-Tag": "noindex" },
  });
}

const dateText = (v: unknown) => {
  const s = String(v || "").trim();
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : (s || "-");
};
const safeName = (v: unknown, fallback = "document") => (String(v || "").replace(/[\\/:*?"<>|\u0000-\u001F]+/g, "_").replace(/\s+/g, " ").trim() || fallback).slice(0, 120);
const fileToken = (v: unknown) => String(v || "RMTC").replace(/[^A-Za-z0-9_.-]+/g, "_").replace(/^_+|_+$/g, "") || "RMTC";

// --------------------------------------------------------------------------- data
type Doc = { id: string; kind: string; label: string; file_name: string; object_path: string; mime: string; size: number };
type Ctx = { token: Record<string, unknown>; tenant: string; rmtc: Record<string, unknown>; docs: Doc[]; grade: string; supplier: string; parts: string[] };

// deno-lint-ignore no-explicit-any
async function loadContext(admin: any, token: string): Promise<Ctx | Response> {
  const { data: tok, error } = await admin.from("rmtc_qr_tokens")
    .select("id, tenant_id, rmtc_approval_id, rmtc_number, certificate_bucket, certificate_path, revoked")
    .eq("token", token).maybeSingle();
  if (error) throw error;
  if (!tok || tok.revoked) return message(404, "QR code not active", "This QR code is not active (it was replaced or withdrawn). Ask the Quality department for the current RMTC label.");
  const tenant = String(tok.tenant_id || "");
  const { data: rmtc } = await admin.from("rmtc_approvals")
    .select("id, tenant_id, rmtc_number, heat_number, heat_code, material_grade_id, supplier_id, part_id, status, disposition, decision_at, approved_at, rmtc_copy_path, rm_section, certificate_quantity")
    .eq("id", tok.rmtc_approval_id).eq("tenant_id", tenant).maybeSingle();
  if (!rmtc) return message(404, "RMTC not available", "The RMTC for this QR code is no longer available.");
  if (!APPROVED_STATUSES.includes(String(rmtc.status || "").toUpperCase()) || !APPROVED_DISPOSITIONS.includes(String(rmtc.disposition || "").toUpperCase())) {
    return message(404, "RMTC not approved", `RMTC ${rmtc.rmtc_number || ""} is not approved at the moment. Ask the Quality department.`);
  }
  const [gradeRes, supplierRes, partLinks, attachRes] = await Promise.all([
    rmtc.material_grade_id ? admin.from("material_grades").select("grade_code, grade_name").eq("id", rmtc.material_grade_id).eq("tenant_id", tenant).maybeSingle() : Promise.resolve({ data: null }),
    rmtc.supplier_id ? admin.from("parties").select("party_name").eq("id", rmtc.supplier_id).eq("tenant_id", tenant).maybeSingle() : Promise.resolve({ data: null }),
    admin.from("rmtc_part_approvals").select("part_id").eq("rmtc_approval_id", rmtc.id).eq("tenant_id", tenant).limit(100),
    admin.from("document_attachments").select("id, tenant_id, entity_type, document_type, file_name, object_path, mime_type, size_bytes, status, created_at")
      .eq("tenant_id", tenant).eq("entity_type", "RMTC").eq("entity_id", rmtc.id).eq("status", "ACTIVE").order("created_at", { ascending: true }).limit(MAX_FILES),
  ]);
  const partIds = [rmtc.part_id, ...((partLinks.data || []) as { part_id: string }[]).map((r) => r.part_id)].filter(Boolean).map(String);
  let parts: string[] = [];
  if (partIds.length) {
    // FSI part numbers only - the original (customer) part number is never shown on this public page.
    const { data: partRows } = await admin.from("parts").select("id, fsi_part_number").in("id", [...new Set(partIds)]).eq("tenant_id", tenant);
    parts = [...new Set(((partRows || []) as { fsi_part_number: string | null }[]).map((p) => String(p.fsi_part_number || "").trim()).filter(Boolean))];
  }
  const docs: Doc[] = [];
  const seen = new Set<string>();
  const inTenant = (path: string) => !!path && path.startsWith(`${tenant}/`) && !path.includes("..");
  const certPath = String(tok.certificate_path || "").trim();
  if (inTenant(certPath)) {
    seen.add(certPath);
    docs.push({ id: "certificate", kind: "CERTIFICATE", label: DOC_LABELS.CERTIFICATE, file_name: certPath.split("/").pop() || `RMTC_${fileToken(rmtc.rmtc_number)}.pdf`, object_path: certPath, mime: "application/pdf", size: 0 });
  }
  const attachments = ((attachRes.data || []) as Record<string, unknown>[])
    .filter((a) => String(a.tenant_id) === tenant && String(a.status || "").toUpperCase() === "ACTIVE")
    .filter((a) => !CUSTOMER_ONLY_ENTITY_TYPES.includes(String(a.entity_type || "")) && !EXCLUDED_DOCUMENT_TYPES.includes(String(a.document_type || "")));
  const rank = (t: string) => { const i = DOC_ORDER.indexOf(t); return i < 0 ? (t.startsWith("RMTC_MICROSTRUCTURE_") ? 10 : 20) : i; };
  attachments.sort((a, b) => rank(String(a.document_type || "")) - rank(String(b.document_type || "")));
  for (const a of attachments) {
    const path = String(a.object_path || "").trim();
    if (!inTenant(path) || seen.has(path)) continue;
    seen.add(path);
    const type = String(a.document_type || "");
    const micro = /^RMTC_MICROSTRUCTURE_(\d+)$/.exec(type);
    docs.push({
      id: String(a.id), kind: type, label: DOC_LABELS[type] || (micro ? `Microstructure photo ${micro[1]}` : "RMTC document"),
      file_name: safeName(a.file_name || path.split("/").pop()), object_path: path, mime: String(a.mime_type || ""), size: Number(a.size_bytes || 0),
    });
  }
  const copyPath = String(rmtc.rmtc_copy_path || "").trim();
  if (inTenant(copyPath) && !seen.has(copyPath)) {
    seen.add(copyPath);
    docs.push({ id: "copy", kind: "RMTC_COPY", label: DOC_LABELS.RMTC_COPY, file_name: safeName(copyPath.split("/").pop()), object_path: copyPath, mime: "", size: 0 });
  }
  return {
    token: tok, tenant, rmtc, docs, parts,
    grade: String(gradeRes.data?.grade_code || gradeRes.data?.grade_name || ""),
    supplier: String(supplierRes.data?.party_name || ""),
  };
}

const extOf = (d: Doc) => (d.file_name.split(".").pop() || "").toLowerCase();
const isPdf = (d: Doc) => d.mime.includes("pdf") || extOf(d) === "pdf";
const isJpg = (d: Doc) => /jpe?g/.test(d.mime) || ["jpg", "jpeg"].includes(extOf(d));
const isPng = (d: Doc) => d.mime.includes("png") || extOf(d) === "png";

// deno-lint-ignore no-explicit-any
async function download(admin: any, ctx: Ctx, doc: Doc): Promise<Uint8Array | null> {
  const bucket = String(ctx.token.certificate_bucket || BUCKET);
  const { data, error } = await admin.storage.from(doc.kind === "CERTIFICATE" ? bucket : BUCKET).download(doc.object_path);
  if (error || !data) return null;
  return new Uint8Array(await data.arrayBuffer());
}

// deno-lint-ignore no-explicit-any
async function collect(admin: any, ctx: Ctx): Promise<{ files: { doc: Doc; bytes: Uint8Array }[]; skipped: { doc: Doc; reason: string }[] }> {
  const files: { doc: Doc; bytes: Uint8Array }[] = [];
  const skipped: { doc: Doc; reason: string }[] = [];
  let total = 0;
  for (const doc of ctx.docs) {
    if (doc.size && total + doc.size > MAX_BUNDLE_BYTES) { skipped.push({ doc, reason: "size limit" }); continue; }
    const bytes = await download(admin, ctx, doc);
    if (!bytes) { skipped.push({ doc, reason: "file not found" }); continue; }
    if (total + bytes.length > MAX_BUNDLE_BYTES) { skipped.push({ doc, reason: "size limit" }); continue; }
    total += bytes.length;
    files.push({ doc, bytes });
  }
  return { files, skipped };
}

function uniqueNames(docs: Doc[]): Map<Doc, string> {
  const used = new Set<string>();
  const out = new Map<Doc, string>();
  for (const d of docs) {
    const base = safeName(d.file_name);
    const dot = base.lastIndexOf(".");
    const stem = dot > 0 ? base.slice(0, dot) : base;
    const ext = dot > 0 ? base.slice(dot) : "";
    let name = base, n = 2;
    while (used.has(name.toLowerCase())) name = `${stem} (${n++})${ext}`;
    used.add(name.toLowerCase());
    out.set(d, name);
  }
  return out;
}

// deno-lint-ignore no-explicit-any
async function zipResponse(admin: any, ctx: Ctx): Promise<Response> {
  const { files, skipped } = await collect(admin, ctx);
  if (!files.length) return message(404, "No documents", "No RMTC document could be read for this QR code.");
  const names = uniqueNames(files.map((f) => f.doc));
  const entries: Record<string, [Uint8Array, { level: 0 }]> = {};
  for (const f of files) entries[names.get(f.doc) as string] = [f.bytes, { level: 0 }];
  if (skipped.length) {
    const note = "Files not included:\r\n" + skipped.map((s) => `- ${s.doc.file_name} (${s.reason})`).join("\r\n") + "\r\n";
    entries["_not_included.txt"] = [new TextEncoder().encode(note), { level: 0 }];
  }
  const zipped = zipSync(entries);
  const name = `RMTC_${fileToken(ctx.rmtc.rmtc_number)}_documents.zip`;
  return new Response(zipped, { status: 200, headers: { "Content-Type": "application/zip", "Content-Disposition": `attachment; filename="${name}"`, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" } });
}

const winAnsi = (v: unknown) => String(v ?? "").replace(/[^\x20-\x7E]/g, "?");

function publicBase(): string {
  return `${String(Deno.env.get("SUPABASE_URL") || "").replace(/\/+$/, "")}/functions/v1/qcms-rmtc-certificate`;
}

function addLink(out: PDFDocument, page: PDFPage, x: number, y: number, w: number, h: number, uri: string): void {
  const annot = out.context.obj({
    Type: "Annot", Subtype: "Link", Rect: [x, y, x + w, y + h], Border: [0, 0, 0],
    A: { Type: "Action", S: "URI", URI: PDFString.of(uri) },
  });
  page.node.addAnnot(out.context.register(annot));
}

function fit(text: string, font: PDFFont, size: number, width: number): string {
  let value = winAnsi(text);
  if (font.widthOfTextAtSize(value, size) <= width) return value;
  while (value.length > 1 && font.widthOfTextAtSize(value + "...", size) > width) value = value.slice(0, -1);
  return value + "...";
}

// PAGE 1 of every QR PDF: RMTC data + document list with tappable per-file Download links + "Download all (ZIP)".
async function drawIndexPage(out: PDFDocument, ctx: Ctx, token: string, note = ""): Promise<void> {
  const r = ctx.rmtc;
  const base = `${publicBase()}?t=${encodeURIComponent(token)}`;
  const heat = `${r.heat_number || "-"}${r.heat_code ? ` (${r.heat_code})` : ""}`;
  const rows: [string, unknown][] = [
    ["RMTC No.", r.rmtc_number || "-"], ["Heat", heat], ["Grade", ctx.grade || "-"], ["Size / Section", r.rm_section || "-"],
    ["Supplier", ctx.supplier || "-"], ["Approval date", dateText(r.decision_at || r.approved_at)],
    ["Disposition", String(r.disposition || "").replace(/_/g, " ")], ["FSI part numbers", ctx.parts.join(", ") || "-"],
  ];
  const W = 420, M = 22, rowH = 20, docH = 46;
  const H = Math.max(640, 230 + rows.length * rowH + Math.max(ctx.docs.length, 1) * docH + 110 + (note ? 40 : 0));
  const page = out.addPage([W, H]);
  const bold = await out.embedFont(StandardFonts.HelveticaBold);
  const font = await out.embedFont(StandardFonts.Helvetica);
  const teal = rgb(0.043, 0.431, 0.439), grey = rgb(0.4, 0.45, 0.52), ink = rgb(0.06, 0.09, 0.16), line = rgb(0.85, 0.88, 0.92);
  let y = H - M - 20;
  page.drawText(fit(`RMTC ${r.rmtc_number || ""}`, bold, 20, W - 2 * M), { x: M, y, size: 20, font: bold, color: teal });
  y -= 18;
  page.drawText("Approved raw material test certificate - material location QR", { x: M, y, size: 9.5, font, color: grey });
  y -= 22;
  for (const [k, v] of rows) {
    page.drawText(winAnsi(k), { x: M, y, size: 10.5, font: bold, color: grey });
    page.drawText(fit(String(v ?? "-"), font, 11, W - 2 * M - 120), { x: M + 120, y, size: 11, font, color: ink });
    y -= rowH;
  }
  if (note) {
    y -= 4;
    page.drawRectangle({ x: M, y: y - 26, width: W - 2 * M, height: 32, color: rgb(1, 0.96, 0.85), borderColor: rgb(0.85, 0.6, 0.1), borderWidth: 1 });
    page.drawText(fit(note, bold, 9, W - 2 * M - 12), { x: M + 6, y: y - 8, size: 9, font: bold, color: ink });
    page.drawText("Use \"Download all (ZIP)\" or the per-file Download buttons below.", { x: M + 6, y: y - 20, size: 8.5, font, color: ink });
    y -= 40;
  }
  y -= 6;
  page.drawText(`Documents (${ctx.docs.length})`, { x: M, y, size: 13, font: bold, color: ink });
  y -= 14;
  const button = (label: string, x: number, top: number, w: number, uri: string, filled = true) => {
    const h = 28;
    page.drawRectangle({ x, y: top - h, width: w, height: h, color: filled ? teal : rgb(1, 1, 1), borderColor: teal, borderWidth: 1 });
    const tw = bold.widthOfTextAtSize(label, 10.5);
    page.drawText(label, { x: x + (w - tw) / 2, y: top - h + 9.5, size: 10.5, font: bold, color: filled ? rgb(1, 1, 1) : teal });
    addLink(out, page, x, top - h, w, h, uri);
  };
  if (!ctx.docs.length) {
    y -= 16;
    page.drawText("No document is stored for this RMTC yet.", { x: M, y, size: 10.5, font, color: ink });
    y -= 14;
    page.drawText("Ask the Quality department to refresh the public QR / certificate.", { x: M, y, size: 9.5, font, color: grey });
  }
  for (const d of ctx.docs) {
    const top = y - 4;
    page.drawRectangle({ x: M, y: top - docH + 6, width: W - 2 * M, height: docH - 6, borderColor: line, borderWidth: 1 });
    page.drawText(fit(d.file_name, bold, 10.5, W - 2 * M - 110), { x: M + 8, y: top - 17, size: 10.5, font: bold, color: ink });
    page.drawText(fit(d.label, font, 9, W - 2 * M - 110), { x: M + 8, y: top - 31, size: 9, font, color: grey });
    button("Download", W - M - 90, top - 6, 82, `${base}&d=${encodeURIComponent(d.id)}`);
    y -= docH;
  }
  if (ctx.docs.length) {
    y -= 8;
    const half = (W - 2 * M - 8) / 2;
    button("Download all (ZIP)", M, y, half, `${base}&f=zip`);
    button("Download all as one PDF", M + half + 8, y, half, `${base}&f=pdf`, false);
    y -= 40;
  }
  page.drawText("STAWN QCMS - RMTC documents via QR - no login required. The documents follow on the next pages.", { x: M, y: M, size: 7, font, color: grey });
}

const allDocumentsName = (ctx: Ctx) => `RMTC_${fileToken(ctx.rmtc.rmtc_number)}_All_Documents.pdf`;

function pdfHeaders(disposition: "inline" | "attachment", name: string): HeadersInit {
  return { "Content-Type": "application/pdf", "Content-Disposition": `${disposition}; filename="${name}"`, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "X-Robots-Tag": "noindex" };
}

// Combined PDF = PAGE 1 index + certificate + every PDF attachment merged + JPG/PNG as pages (+ "not merged" page).
// Above the 50 MB cap only the index page is returned, with a note to use the ZIP / per-file links.
// deno-lint-ignore no-explicit-any
async function bundlePdf(admin: any, ctx: Ctx, token: string): Promise<Uint8Array> {
  const { files, skipped } = await collect(admin, ctx);
  const overCap = skipped.some((s) => s.reason === "size limit");
  const out = await PDFDocument.create();
  out.setTitle(`RMTC ${winAnsi(ctx.rmtc.rmtc_number)} - all documents`);
  out.setProducer("STAWN QCMS");
  await drawIndexPage(out, ctx, token, overCap ? "The documents are larger than 50 MB together - this PDF contains the list only." : "");
  if (overCap) return await out.save();
  const notMerged: { name: string; reason: string }[] = skipped.map((s) => ({ name: s.doc.file_name, reason: s.reason }));
  for (const { doc, bytes } of files) {
    try {
      if (isPdf(doc)) {
        const src = await PDFDocument.load(bytes, { ignoreEncryption: true });
        const pages = await out.copyPages(src, src.getPageIndices());
        pages.forEach((p) => out.addPage(p));
      } else if (isJpg(doc) || isPng(doc)) {
        const img = isPng(doc) ? await out.embedPng(bytes) : await out.embedJpg(bytes);
        const [pw, ph] = [595.28, 841.89];
        const page = out.addPage([pw, ph]);
        const margin = 36;
        const scale = Math.min((pw - 2 * margin) / img.width, (ph - 2 * margin - 24) / img.height, 1);
        const w = img.width * scale, h = img.height * scale;
        page.drawImage(img, { x: (pw - w) / 2, y: ph - margin - 24 - h, width: w, height: h });
        const font = await out.embedFont(StandardFonts.Helvetica);
        page.drawText(winAnsi(`${doc.label}: ${doc.file_name}`).slice(0, 95), { x: margin, y: ph - margin - 10, size: 10, font, color: rgb(0.2, 0.25, 0.3) });
      } else {
        notMerged.push({ name: doc.file_name, reason: "file type cannot be merged - download it separately" });
      }
    } catch (_err) {
      notMerged.push({ name: doc.file_name, reason: "file could not be merged - download it separately" });
    }
  }
  if (notMerged.length) {
    const page = out.addPage([595.28, 841.89]);
    const bold = await out.embedFont(StandardFonts.HelveticaBold);
    const font = await out.embedFont(StandardFonts.Helvetica);
    let y = 790;
    page.drawText(winAnsi(`RMTC ${ctx.rmtc.rmtc_number || ""} - documents not merged into this PDF`), { x: 40, y, size: 13, font: bold });
    y -= 26;
    for (const item of notMerged) {
      if (y < 60) break;
      page.drawText(winAnsi(`- ${item.name} (${item.reason})`).slice(0, 110), { x: 40, y, size: 10, font });
      y -= 16;
    }
    page.drawText("Use the Download links on page 1 to get every file individually or as a ZIP.", { x: 40, y: 40, size: 9, font, color: rgb(0.4, 0.45, 0.5) });
  }
  return await out.save();
}

// Default ?t= (inline: phones open it in the viewer) and f=pdf (download) - the same combined PDF.
// deno-lint-ignore no-explicit-any
async function pdfResponse(admin: any, ctx: Ctx, token: string, disposition: "inline" | "attachment"): Promise<Response> {
  return new Response(await bundlePdf(admin, ctx, token), { status: 200, headers: pdfHeaders(disposition, allDocumentsName(ctx)) });
}

// f=index: the index page only.
async function indexResponse(ctx: Ctx, token: string): Promise<Response> {
  const out = await PDFDocument.create();
  out.setTitle(`RMTC ${winAnsi(ctx.rmtc.rmtc_number)} - documents`);
  out.setProducer("STAWN QCMS");
  await drawIndexPage(out, ctx, token);
  return new Response(await out.save(), { status: 200, headers: pdfHeaders("inline", `RMTC_${fileToken(ctx.rmtc.rmtc_number)}_documents_index.pdf`) });
}

function jsonList(ctx: Ctx, token: string): Response {
  const base = `${publicBase()}?t=${encodeURIComponent(token)}`;
  const r = ctx.rmtc;
  const body = {
    rmtc_number: r.rmtc_number, heat_number: r.heat_number, heat_code: r.heat_code, grade: ctx.grade, supplier: ctx.supplier,
    approval_date: dateText(r.decision_at || r.approved_at), disposition: r.disposition, fsi_part_numbers: ctx.parts,
    documents: ctx.docs.map((d) => ({ id: d.id, label: d.label, file_name: d.file_name, url: `${base}&d=${encodeURIComponent(d.id)}` })),
    zip_url: `${base}&f=zip`, pdf_url: `${base}&f=pdf`,
  };
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
}

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== "GET" && req.method !== "HEAD") return message(405, "Method not allowed", "Open this link from the QR code.");
    const url = new URL(req.url);
    const token = (url.searchParams.get("t") || "").trim();
    if (!TOKEN_RE.test(token)) return message(400, "Invalid QR code", "This QR code is not a valid QCMS RMTC code.");
    const ip = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim() || "anon";
    const format = (url.searchParams.get("f") || "").trim().toLowerCase();
    const docId = (url.searchParams.get("d") || "").trim();
    const heavy = format === "zip" || format === "pdf" || (!format && !docId);
    if (rateLimited(`any:${ip}`, 120) || (heavy && rateLimited(`bundle:${ip}`, 20))) {
      return message(429, "Too many requests", "Please wait a minute and try again.");
    }
    if (format && !["zip", "pdf", "json", "index"].includes(format)) return message(400, "Invalid request", "Unknown download format.");
    if (docId && docId !== "certificate" && docId !== "copy" && !UUID_RE.test(docId)) return message(400, "Invalid request", "Unknown document.");
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
    const ctx = await loadContext(admin, token);
    if (ctx instanceof Response) return ctx;
    if (docId) {
      const doc = ctx.docs.find((d) => d.id === docId);
      if (!doc) return message(404, "Document not available", "This document is not part of the RMTC for this QR code.");
      const bucket = doc.kind === "CERTIFICATE" ? String(ctx.token.certificate_bucket || BUCKET) : BUCKET;
      const { data: signed, error } = await admin.storage.from(bucket).createSignedUrl(doc.object_path, SIGNED_URL_SECONDS, { download: doc.file_name });
      if (error || !signed?.signedUrl) return message(404, "Document not available", "The file could not be found. Ask the Quality department to refresh the RMTC documents.");
      return new Response(null, { status: 302, headers: { Location: signed.signedUrl, "Cache-Control": "no-store" } });
    }
    if (format === "zip") return await zipResponse(admin, ctx);
    if (format === "pdf") return await pdfResponse(admin, ctx, token, "attachment");
    if (format === "json") return jsonList(ctx, token);
    if (format === "index") return await indexResponse(ctx, token);
    return await pdfResponse(admin, ctx, token, "inline");  // one scan shows everything: index page + all documents
  } catch (err) {
    console.error("qcms-rmtc-certificate", err instanceof Error ? err.message : String(err));
    return message(500, "Temporarily unavailable", "The RMTC documents could not be opened. Please try again in a minute.");
  }
});
