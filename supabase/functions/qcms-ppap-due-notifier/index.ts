// STAWN QCMS · R38 + R39 · qcms-ppap-due-notifier
// Daily (pg_cron 'qcms-ppap-due-notifier-daily', scheduler token auth like the other QCMS notifiers):
//   PPAP elements that are Pending / In progress / Rejected, belong to an active package and are due within N days
//   (default 3, schedule PPAP_DOCUMENT_DUE.days_ahead) or overdue -> ONE digest e-mail per responsible employee
//   (HTML table: part, PPAP no., package, element, due date, days overdue, status), CC to the reporting manager
//   (employees.reports_to_employee_id) when at least one row is overdue. Subject starts with the employee's department,
//   e.g. "Quality · PPAP elements due · 3 item(s) · 28-10-2026". Deduplicated per employee and day through
//   qcms_notification_outbox.dedupe_key. Also raises the in-app / mobile notifications (qcms_ppap_due_notifications).
// Mirrors core/ppap_service.due_digests (tests/test_r38_ppap.py).
// R39: each digest also carries the PART DETAILS of every package in it and the current DRAWINGS & SPECIFICATIONS
//   (public.qcms_ppap_part_context: finish / forging / HT / process drawings, process specs, linked customer standards).
//   Drawings first, then specifications, are attached from the private bucket while the mail stays within
//   18 files / 10 MB; the rest (and files missing in storage) are listed by name. Dedupe unchanged (one digest per
//   employee and day, dedupe_key PPAP_ELEMENT_DUE:<date>:<employee>).
// R39 attachment rule (daily reminders must not resend the same drawings every day): a drawing / specification is
//   ATTACHED only when it was not already attached to the same person in a SENT PPAP e-mail (assignment e-mail
//   PPAP_ASSIGNMENT or an earlier reminder) within the last ATTACH_REPEAT_DAYS = 7 days. So the first reminder carries
//   the files, later daily reminders list them ("attached on DD-MM-YYYY"), they are attached again once a week, and a
//   new drawing revision (new object path) is attached at once. The part details are in every reminder.
// Body (optional, manual runs): { "days_ahead": 3, "local_date": "2026-10-28", "dry_run": true }
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import nodemailer from "npm:nodemailer@6.9.16";
import { Buffer } from "node:buffer";
import { clean, companyName, emailShell, esc, htmlTable, textTable, type Col, type Cell, type MailAttachment, type Row } from "./reminder_kit.ts";

const jsonHeaders = { "Content-Type": "application/json" };
const SCHEDULE_KEY = "PPAP_DOCUMENT_DUE";
const DUE_STATUSES = new Set(["NOT_STARTED", "IN_PROGRESS", "REJECTED"]);
const INACTIVE_PACKAGES = new Set(["APPROVED", "CANCELLED", "CLOSED"]);
const STATUS_LABEL: Record<string, string> = { NOT_STARTED: "Pending", IN_PROGRESS: "In progress", REJECTED: "Rejected" };
const DEPARTMENT_LABEL: Record<string, string> = {
  quality: "Quality", qa: "Quality", qc: "Quality", metlab: "MetLAB", lab: "MetLAB", supplychain: "Supply Chain", scm: "Supply Chain",
  purchase: "Purchase", procurement: "Purchase", stores: "Stores", store: "Stores", npd: "NPD", rd: "R & D", engineering: "Engineering",
  production: "Production", management: "Management", admin: "Admin", administration: "Admin", hr: "HR", accounts: "Accounts",
  marketing: "Marketing", businessdevelopment: "Business Development", maintenance: "Maintenance", dispatch: "Dispatch", logistics: "Logistics",
};
const MAX_MAIL_BYTES = 10 * 1024 * 1024;   // same cap as the PPAP assignment e-mail (qcms_ppap_assignment_mail)
const MAX_MAIL_FILES = 18;
export const ATTACH_REPEAT_DAYS = 7;   // re-attach the same file to the same person at most once a week
const PPAP_MAIL_EVENTS = ["PPAP_ASSIGNMENT", "PPAP_DOCUMENT_DUE_DIGEST"];
const DOC_HEADERS: Col[] = ["Package", "Document", "File", "Drawing No.", "Rev.", "E-mail"];
const HEADERS: Col[] = ["#", "Part", "PPAP No.", "Package", "Element", { label: "Due Date", kind: "date" }, { label: "Days Overdue", kind: "number" }, "Status"];

type DueRow = { part: string; ppap_no: string; package_no: string; element: string; due_date: string; days_overdue: number; status: string; package_id?: string };
type PartDoc = { bucket?: string; object_path?: string; file_name?: string; mime_type?: string; size_bytes?: number; in_storage?: boolean;
  kind?: string; category?: string; revision?: string; drawing_number?: string };
type PartContext = { package?: Row; part?: Row | null; customer?: string | null; owner?: Row | null; documents?: PartDoc[] };

export function departmentLabel(value: unknown): string {
  const raw = String(value ?? "").trim().replace(/\s+/g, " ");
  const norm = raw.toLowerCase().replace(/[^a-z0-9]+/g, "");
  if (!raw || ["qcmsteam", "qcms", "all", "none"].includes(norm)) return "";
  return DEPARTMENT_LABEL[norm] || raw;
}
function hex(bytes: ArrayBuffer): string {
  return Array.from(new Uint8Array(bytes)).map((b) => b.toString(16).padStart(2, "0")).join("");
}
async function sha256(value: string): Promise<string> {
  return hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)));
}
function localDate(now: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(now);
  const get = (type: string) => parts.find((p) => p.type === type)?.value || "00";
  return `${get("year")}-${get("month")}-${get("day")}`;
}
function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`); d.setUTCDate(d.getUTCDate() + Number(days || 0)); return d.toISOString().slice(0, 10);
}
function daysBetween(fromIso: string, toIso: string): number {
  return Math.floor((Date.parse(`${toIso}T00:00:00Z`) - Date.parse(`${fromIso}T00:00:00Z`)) / 86400000);
}
function dmy(iso: string): string {
  return /^\d{4}-\d{2}-\d{2}/.test(iso) ? `${iso.slice(8, 10)}-${iso.slice(5, 7)}-${iso.slice(0, 4)}` : iso;
}
function fullName(e: Row | undefined): string {
  return `${clean(e?.first_name)} ${clean(e?.last_name)}`.trim() || clean(e?.employee_code) || clean(e?.email);
}
function quoted(name: string, email: string): string {
  return name ? `"${name.replaceAll('"', "")}" <${email}>` : email;
}
async function selectAll(admin: any, table: string, columns: string, tenantId: string, extra?: (q: any) => any): Promise<Row[]> {
  const out: Row[] = [];
  for (let from = 0; from < 100000; from += 1000) {
    let q = admin.from(table).select(columns).eq("tenant_id", tenantId).range(from, from + 999);
    if (extra) q = extra(q);
    const { data, error } = await q;
    if (error) throw error;
    out.push(...(data || []));
    if (!data || data.length < 1000) break;
  }
  return out;
}

/** One digest per responsible employee (same rules as core/ppap_service.due_digests). */
export function buildDigests(packages: Row[], elements: Row[], employees: Row[], today: string, daysAhead: number) {
  const active = new Map<string, Row>(packages.filter((p) => !INACTIVE_PACKAGES.has(String(p.status || "IN_PROGRESS").toUpperCase())).map((p) => [String(p.id), p]));
  const emp = new Map<string, Row>(employees.map((e) => [String(e.id), e]));
  const limit = addDays(today, daysAhead);
  const grouped = new Map<string, DueRow[]>();
  for (const e of elements) {
    const pkg = active.get(String(e.package_id));
    const owner = String(e.responsible_employee_id || "");
    const status = String(e.status || "NOT_STARTED").toUpperCase();
    const due = String(e.due_date || "").slice(0, 10);
    if (!pkg || !owner || !DUE_STATUSES.has(status) || !/^\d{4}-\d{2}-\d{2}$/.test(due) || due > limit) continue;
    const row: DueRow = {
      part: clean(pkg.customer_part_no) || "-", ppap_no: clean(pkg.customer_ppap_no) || "-", package_no: clean(pkg.package_no),
      element: `${String(Number(e.element_no || 0)).padStart(2, "0")} ${clean(e.element_name)}`.trim(),
      due_date: due, days_overdue: Math.max(0, daysBetween(due, today)), status: STATUS_LABEL[status] || status,
      package_id: String(pkg.id),
    };
    grouped.set(owner, [...(grouped.get(owner) || []), row]);
  }
  const digests: Array<{ employee_id: string; email: string; name: string; department: string; cc: string[]; rows: DueRow[]; overdue: number; subject: string; dedupe_key: string }> = [];
  for (const [employeeId, rows] of grouped) {
    const e = emp.get(employeeId) || {};
    const email = clean(e.email);
    if (!email.includes("@")) continue;
    rows.sort((a, b) => b.days_overdue - a.days_overdue || a.due_date.localeCompare(b.due_date) || a.part.localeCompare(b.part) || a.element.localeCompare(b.element));
    const overdue = rows.filter((r) => r.days_overdue > 0).length;
    const cc: string[] = [];
    if (overdue) {
      const manager = emp.get(String(e.reports_to_employee_id || "")) || {};
      const managerEmail = clean(manager.email);
      if (managerEmail.includes("@") && managerEmail.toLowerCase() !== email.toLowerCase()) cc.push(managerEmail);
    }
    const department = clean(e.department);
    const label = departmentLabel(department) || "Quality";
    digests.push({ employee_id: employeeId, email, name: fullName(e), department, cc, rows, overdue,
      subject: `${label} · PPAP elements due · ${rows.length} item(s) · ${dmy(today)}`, dedupe_key: `PPAP_ELEMENT_DUE:${today}:${employeeId}` });
  }
  digests.sort((a, b) => a.email.toLowerCase().localeCompare(b.email.toLowerCase()));
  return digests;
}

function partLabel(ctx: PartContext | null | undefined, fallback: string): string {
  const part = ctx?.part || {};
  const label = [clean(part.part_number), clean(part.part_name) ? `(${clean(part.part_name)})` : ""].filter(Boolean).join(" ");
  return label || clean(ctx?.package?.customer_part_no) || fallback || "-";
}

/** PART DETAILS block of one package (internal e-mail: the customer name is allowed). */
export function partDetailsHtml(packageNo: string, ctx: PartContext | null | undefined): string {
  const part = ctx?.part || {}, pkg = ctx?.package || {};
  const grade = clean(part.material_grade);
  const pairs: Array<[string, string]> = [
    ["PPAP Package No.", clean(pkg.package_no) || packageNo], ["Customer PPAP No.", clean(pkg.customer_ppap_no)],
    ["Part Number", clean(part.part_number)], ["FSI Part Number", clean(part.fsi_part_number)], ["Part Name", clean(part.part_name)],
    ["Customer", clean(ctx?.customer)], ["Customer Part No.", clean(pkg.customer_part_no)], ["Material Grade", grade],
    ["Drawing No. / Rev.", [clean(part.drawing_number), clean(part.drawing_revision)].filter(Boolean).join(" / Rev. ")],
    ["Customer Due Date", dmy(clean(pkg.customer_due_date))], ["Submission Level", pkg.submission_level ? `Level ${pkg.submission_level}` : ""],
  ].filter(([, v]) => clean(v)) as Array<[string, string]>;
  const td = "padding:5px 8px;border:1px solid #D3DCE1;font-size:12px;vertical-align:top";
  return `<div style="font-size:14px;font-weight:700;color:#0F6E6E;margin:12px 0 6px 0">Part details · ${esc(clean(pkg.package_no) || packageNo)}</div>`
    + `<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;width:100%;font-family:Arial,Helvetica,sans-serif">`
    + pairs.map(([k, v]) => `<tr><td style="${td};background:#F3F7F7;font-weight:700;width:30%">${esc(k)}</td><td style="${td}">${esc(v)}</td></tr>`).join("")
    + `</table>`;
}
export function partDetailsText(packageNo: string, ctx: PartContext | null | undefined): string {
  const part = ctx?.part || {}, pkg = ctx?.package || {};
  const lines = [`Part details · ${clean(pkg.package_no) || packageNo}`,
    `  Part: ${partLabel(ctx, "-")}`, clean(part.fsi_part_number) ? `  FSI Part Number: ${clean(part.fsi_part_number)}` : "",
    clean(ctx?.customer) ? `  Customer: ${clean(ctx?.customer)}` : "", clean(part.material_grade) ? `  Material Grade: ${clean(part.material_grade)}` : "",
    clean(part.drawing_number) ? `  Drawing No. / Rev.: ${clean(part.drawing_number)}${clean(part.drawing_revision) ? " / Rev. " + clean(part.drawing_revision) : ""}` : "",
    clean(pkg.customer_due_date) ? `  Customer Due Date: ${dmy(clean(pkg.customer_due_date))}` : ""];
  return lines.filter(Boolean).join("\n");
}

/** object_path -> date (YYYY-MM-DD) of the files already attached to this person in a SENT PPAP e-mail since ``sinceIso``. */
export async function recentAttachmentPaths(admin: any, tenantId: string, email: string, sinceIso: string): Promise<Map<string, string>> {
  const out = new Map<string, string>();
  try {
    const { data } = await admin.from("qcms_notification_outbox").select("recipient_email,attachment_manifest,sent_at,created_at")
      .eq("tenant_id", tenantId).in("event_key", PPAP_MAIL_EVENTS).eq("status", "SENT").gte("created_at", `${sinceIso}T00:00:00Z`)
      .order("created_at", { ascending: false }).limit(500);
    for (const r of (data || []) as Row[]) {
      if (clean(r.recipient_email).toLowerCase() !== email.toLowerCase()) continue;
      const when = clean(r.sent_at || r.created_at).slice(0, 10);
      for (const m of (Array.isArray(r.attachment_manifest) ? r.attachment_manifest : []) as Row[]) {
        const path = clean(m?.object_path);
        if (path && !m?.generated && !out.has(path)) out.set(path, when);
      }
    }
  } catch (_e) { /* no history: attach as usual */ }
  return out;
}

/** Pick attachments: drawings first, then specifications (context order), within 18 files / 10 MB; the rest are listed. */
export function planAttachments(docs: Array<PartDoc & { package_no: string }>, maxFiles = MAX_MAIL_FILES, maxBytes = MAX_MAIL_BYTES,
                                recentlySent: Map<string, string> = new Map()) {
  const seen = new Set<string>();
  const ordered = [...docs.filter((d) => d.kind === "drawing"), ...docs.filter((d) => d.kind !== "drawing")];
  const attach: Array<PartDoc & { package_no: string }> = [], listed: Array<PartDoc & { package_no: string; reason: string }> = [];
  let bytes = 0;
  for (const d of ordered) {
    const path = clean(d.object_path);
    if (!path || seen.has(path)) continue;
    seen.add(path);
    const size = Number(d.size_bytes || 0) > 0 ? Number(d.size_bytes) : 2 * 1024 * 1024;
    if (d.in_storage === false) { listed.push({ ...d, reason: "File not found in storage - open it in QCMS" }); continue; }
    if (recentlySent.has(path)) { listed.push({ ...d, reason: `Attached on ${dmy(recentlySent.get(path) || "")} - open it in QCMS` }); continue; }
    if (attach.length < maxFiles && bytes + size <= maxBytes) { attach.push(d); bytes += size; }
    else listed.push({ ...d, reason: "Not attached (e-mail size) - open it in QCMS" });
  }
  return { attach, listed, bytes };
}

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== "POST") return new Response(JSON.stringify({ error: "POST required" }), { status: 405, headers: jsonHeaders });
    const schedulerToken = req.headers.get("X-QCMS-Scheduler") || "";
    if (!schedulerToken) return new Response(JSON.stringify({ error: "Scheduler token required" }), { status: 401, headers: jsonHeaders });
    const body = await req.json().catch(() => ({})) as Row;

    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    const tokenHash = await sha256(schedulerToken);
    const { data: configs = [], error: configError } = await admin.from("qcms_notification_scheduler_config").select("tenant_id,scheduler_token_hash");
    if (configError) throw configError;
    const tenants = (configs || []).filter((r: Row) => String(r.scheduler_token_hash) === tokenHash).map((r: Row) => String(r.tenant_id));
    if (!tenants.length) return new Response(JSON.stringify({ error: "Invalid scheduler token" }), { status: 401, headers: jsonHeaders });

    const now = new Date();
    const result = { tenants: 0, digests: 0, sent: 0, failed: 0, skipped_duplicates: 0, in_app: 0, dry_run: Boolean(body.dry_run) };
    for (const tenantId of tenants) {
      const { data: schedule } = await admin.from("qcms_notification_schedules").select("*").eq("tenant_id", tenantId).eq("schedule_key", SCHEDULE_KEY).maybeSingle();
      if (schedule && schedule.enabled === false && !body.force) continue;
      const timezone = String(schedule?.timezone || "Asia/Kolkata");
      const today = /^\d{4}-\d{2}-\d{2}$/.test(String(body.local_date || "")) ? String(body.local_date) : localDate(now, timezone);
      const daysAhead = Math.max(0, Number(body.days_ahead ?? schedule?.days_ahead ?? 3));
      result.tenants += 1;

      const [packages, elements, employees] = await Promise.all([
        selectAll(admin, "ppap_packages", "id,package_no,customer_part_no,customer_ppap_no,status", tenantId),
        selectAll(admin, "ppap_package_elements", "id,package_id,element_no,element_name,status,due_date,responsible_employee_id", tenantId,
          (q: any) => q.in("status", Array.from(DUE_STATUSES)).not("due_date", "is", null).lte("due_date", addDays(today, daysAhead))),
        selectAll(admin, "employees", "id,first_name,last_name,employee_code,email,department,status,reports_to_employee_id", tenantId),
      ]);
      const digests = buildDigests(packages, elements, employees, today, daysAhead);
      result.digests += digests.length;
      if (body.dry_run) continue;

      try {
        const { data: count } = await admin.rpc("qcms_ppap_due_notifications", { p_tenant_id: tenantId, p_local_date: today, p_days_ahead: daysAhead });
        result.in_app += Number(count || 0);
      } catch (_e) { /* in-app notification is optional */ }
      if (!digests.length) continue;

      const { data: settings } = await admin.from("qcms_email_settings").select("*").eq("tenant_id", tenantId).maybeSingle();
      if (!settings?.enabled || !settings?.smtp_host || !settings?.sender_email) continue;
      const transporter = nodemailer.createTransport({
        host: settings.smtp_host, port: Number(settings.smtp_port || 587), secure: Boolean(settings.use_ssl), requireTLS: Boolean(settings.use_tls) && !Boolean(settings.use_ssl),
        auth: settings.smtp_username ? { user: settings.smtp_username, pass: settings.smtp_password || "" } : undefined,
        connectionTimeout: Number(settings.timeout_seconds || 20) * 1000, greetingTimeout: Number(settings.timeout_seconds || 20) * 1000, socketTimeout: Number(settings.timeout_seconds || 20) * 1000,
      });
      const company = await companyName(admin, tenantId, settings);
      const contexts = new Map<string, PartContext | null>();
      const fileCache = new Map<string, Buffer | null>();
      const contextOf = async (packageId: string): Promise<PartContext | null> => {
        if (!packageId) return null;
        if (!contexts.has(packageId)) {
          try {
            const { data } = await admin.rpc("qcms_ppap_part_context", { p_package_id: packageId });
            contexts.set(packageId, (data || null) as PartContext | null);
          } catch (_e) { contexts.set(packageId, null); }
        }
        return contexts.get(packageId) || null;
      };
      const download = async (bucket: string, path: string): Promise<Buffer | null> => {
        const key = `${bucket}/${path}`;
        if (!fileCache.has(key)) {
          try {
            const { data: blob, error } = await admin.storage.from(bucket).download(path);
            fileCache.set(key, error || !blob ? null : Buffer.from(await blob.arrayBuffer()));
          } catch (_e) { fileCache.set(key, null); }
        }
        return fileCache.get(key) || null;
      };

      for (const digest of digests) {
        const { data: exists } = await admin.from("qcms_notification_outbox").select("id").eq("tenant_id", tenantId).eq("dedupe_key", digest.dedupe_key).maybeSingle();
        if (exists?.id) { result.skipped_duplicates += 1; continue; }
        // R39: part details + current drawings / specifications of every package in this digest
        const packageIds = Array.from(new Set(digest.rows.map((r) => String(r.package_id || "")).filter(Boolean)));
        const partSections: string[] = [], partTexts: string[] = [];
        const allDocs: Array<PartDoc & { package_no: string }> = [];
        const labelByPackage = new Map<string, string>();
        for (const packageId of packageIds) {
          const ctx = await contextOf(packageId);
          const packageNo = digest.rows.find((r) => r.package_id === packageId)?.package_no || "";
          labelByPackage.set(packageId, partLabel(ctx, digest.rows.find((r) => r.package_id === packageId)?.part || ""));
          if (!ctx) continue;
          partSections.push(partDetailsHtml(packageNo, ctx));
          partTexts.push(partDetailsText(packageNo, ctx));
          for (const d of (Array.isArray(ctx.documents) ? ctx.documents : [])) allDocs.push({ ...d, package_no: clean(ctx.package?.package_no) || packageNo });
        }
        const recent = await recentAttachmentPaths(admin, tenantId, digest.email, addDays(today, -(ATTACH_REPEAT_DAYS - 1)));
        const plan = planAttachments(allDocs, MAX_MAIL_FILES, MAX_MAIL_BYTES, recent);
        const attachments: MailAttachment[] = [];
        const manifest: Row[] = [];
        const status = new Map<string, string>();
        for (const d of plan.attach) {
          const bucket = clean(d.bucket) || "quality-documents", path = clean(d.object_path);
          const content = await download(bucket, path);
          if (!content) { status.set(path, "Could not be downloaded - open it in QCMS"); continue; }
          attachments.push({ filename: clean(d.file_name) || path.split("/").pop() || "document", content, contentType: clean(d.mime_type) || "application/octet-stream" });
          manifest.push({ bucket, object_path: path, file_name: clean(d.file_name), mime_type: clean(d.mime_type) || "application/octet-stream", generated: false });
          status.set(path, "Attached");
        }
        for (const d of plan.listed) status.set(clean(d.object_path), d.reason);
        const docCells: Cell[][] = [...plan.attach, ...plan.listed].map((d) => [d.package_no, clean(d.category), clean(d.file_name), clean(d.drawing_number), clean(d.revision), status.get(clean(d.object_path)) || "-"]);
        const cells: Cell[][] = digest.rows.map((r, i) => [i + 1, labelByPackage.get(String(r.package_id || "")) || r.part, r.ppap_no, r.package_no, r.element, r.due_date, r.days_overdue || null, r.days_overdue ? `Overdue · ${r.status}` : r.status]);
        const open = digest.rows.length - digest.overdue;
        const intro = [`Dear ${digest.name || "Colleague"},`, "",
          `The PPAP elements below are assigned to you and are due within ${daysAhead} day(s) or overdue.`,
          `Overdue: ${digest.overdue} · due soon: ${open} · report date ${dmy(today)}.`,
          digest.cc.length ? "Your reporting manager is copied because at least one element is overdue." : "",
          "Please upload the documents and set the element status in QCMS → PPAP → Package.",
          plan.attach.length + plan.listed.length ? `The part details and the current drawings / specifications are below; they are attached while the e-mail size allows (files already sent to you in the last ${ATTACH_REPEAT_DAYS} days are listed only).` : ""];
        const sections = [htmlTable(HEADERS, cells, { caption: `PPAP elements · ${digest.rows.length} item(s)` }), ...partSections,
          htmlTable(DOC_HEADERS, docCells, { caption: `Current drawings & specifications · ${attachments.length} attached` })];
        const html = emailShell({ title: "PPAP elements due / overdue", company, intro, sections });
        const text = `${intro.join("\n")}\n\n${textTable(HEADERS, cells)}\n\n${partTexts.join("\n\n")}\n\nCURRENT DRAWINGS & SPECIFICATIONS\n`
          + (docCells.length ? textTable(DOC_HEADERS, docCells) : "No controlled drawing or specification is stored for these parts yet.");
        const { data: outbox, error: insertError } = await admin.from("qcms_notification_outbox").insert({
          tenant_id: tenantId, event_key: "PPAP_DOCUMENT_DUE_DIGEST", recipient_email: digest.email, recipient_name: digest.name || null,
          cc_emails: digest.cc, subject: digest.subject, body_text: text, body_html: html, template_key: "PPAP_DOCUMENT_DUE_DIGEST",
          context: { schedule_key: SCHEDULE_KEY, report_date: today, days_ahead: daysAhead, record_count: digest.rows.length, overdue_count: digest.overdue, department: departmentLabel(digest.department) || "Quality", module_key: "PPAP",
            package_ids: packageIds, attached_count: attachments.length, listed_files: plan.listed.map((d) => clean(d.file_name)) },
          attachment_manifest: manifest, dedupe_key: digest.dedupe_key, is_automatic: true, scheduled_for: now.toISOString(), status: "PENDING",
        }).select("id").single();
        if (insertError) {
          if (String(insertError.message || "").toLowerCase().includes("duplicate")) { result.skipped_duplicates += 1; continue; }
          throw insertError;
        }
        try {
          await admin.from("qcms_notification_outbox").update({ status: "SENDING", attempts: 1, updated_at: new Date().toISOString() }).eq("id", outbox.id);
          await transporter.sendMail({
            from: quoted(clean(settings.sender_name), settings.sender_email), to: quoted(digest.name, digest.email),
            cc: digest.cc.length ? digest.cc : undefined, replyTo: settings.reply_to || undefined, subject: digest.subject, text, html,
            attachments: attachments.length ? attachments : undefined,
          });
          await admin.from("qcms_notification_outbox").update({ status: "SENT", sent_at: new Date().toISOString(), last_error: null, updated_at: new Date().toISOString() }).eq("id", outbox.id);
          result.sent += 1;
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          await admin.from("qcms_notification_outbox").update({ status: "FAILED", last_error: message.slice(0, 2000), updated_at: new Date().toISOString() }).eq("id", outbox.id);
          result.failed += 1;
        }
      }
      // last_run_local_date = today also tells qcms-overdue-notifier (hour_local 8, runs after this 07:50 IST job) that the
      // PPAP_DOCUMENT_DUE schedule already ran today, so no second PPAP e-mail is produced there.
      if (schedule?.id) {
        await admin.from("qcms_notification_schedules").update({ last_run_local_date: today, last_run_at: new Date().toISOString(), updated_at: new Date().toISOString() }).eq("id", schedule.id).eq("tenant_id", tenantId);
      }
    }
    return new Response(JSON.stringify(result), { headers: jsonHeaders });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return new Response(JSON.stringify({ error: message }), { status: 500, headers: jsonHeaders });
  }
});
