import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import nodemailer from "npm:nodemailer@6.9.16";
import { PDFDocument, StandardFonts, rgb } from "npm:pdf-lib@1.17.1";
import { Buffer } from "node:buffer";

const jsonHeaders = { "Content-Type": "application/json" };
const BUCKET = "quality-documents";

type Row = Record<string, any>;

type DigestRow = {
  reference: string;
  part: string;
  party: string;
  due_date: string;
  status: string;
  quantity: string;
  responsible_employee_id?: string;
  supplier_id?: string;
  order_id?: string;
};

function hex(bytes: ArrayBuffer): string {
  return Array.from(new Uint8Array(bytes)).map((b) => b.toString(16).padStart(2, "0")).join("");
}
async function sha256(value: string): Promise<string> {
  return hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)));
}
function n(value: any): string {
  const x = Number(value || 0);
  return Number.isFinite(x) ? x.toLocaleString("en-IN", { maximumFractionDigits: 3 }) : "0";
}
function emailList(party: Row | undefined): string[] {
  if (!party) return [];
  const raw = [String(party.email || ""), String(party.notification_emails || "")].join(";");
  const out: string[] = [];
  for (const token of raw.split(/[;,\n]+/)) {
    const value = token.trim();
    if (value.includes("@") && !out.some((v) => v.toLowerCase() === value.toLowerCase())) out.push(value);
  }
  return out;
}
function localClock(now: Date, timeZone: string): { date: string; hour: number } {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", hourCycle: "h23",
  }).formatToParts(now);
  const get = (type: string) => parts.find((p) => p.type === type)?.value || "00";
  return { date: `${get("year")}-${get("month")}-${get("day")}`, hour: Number(get("hour")) };
}
function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`); d.setUTCDate(d.getUTCDate() + Number(days || 0)); return d.toISOString().slice(0, 10);
}
function eligibleDate(due: any, localDate: string, daysAhead: number, includeOpen: boolean, includeOverdue: boolean): { include: boolean; overdue: boolean } {
  const value = String(due || "").slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return { include: false, overdue: false };
  const overdue = value < localDate;
  if (overdue) return { include: includeOverdue, overdue: true };
  return { include: includeOpen && value <= addDays(localDate, daysAhead), overdue: false };
}
function renderTemplate(value: string, ctx: Row): string {
  return String(value || "").replace(/\{\{\s*([A-Za-z0-9_]+)\s*\}\}/g, (_m, key) => String(ctx[key] ?? "-"));
}
function esc(value: any): string {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}
function baseHtml(text: string): string {
  return `<div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#273444;line-height:1.5">${String(text || "").split("\n").map((x) => esc(x)).join("<br>")}</div>`;
}
async function npdCardsHtml(admin: any, tenantId: string, assignedRows: DigestRow[], maps: { parties: Map<string, Row>; parts: Map<string, Row>; employees: Map<string, Row> }, localDate: string): Promise<string> {
  const orderIds = Array.from(new Set(assignedRows.map((r) => String(r.order_id || "")).filter(Boolean)));
  if (!orderIds.length) return "";
  const [{ data: orders = [] }, { data: steps = [] }] = await Promise.all([
    admin.from("npd_orders").select("id,order_number,part_id,customer_id,delivery_date,status,created_by").eq("tenant_id", tenantId).in("id", orderIds).limit(500),
    admin.from("npd_order_steps").select("id,npd_order_id,operation_no,process_name,process_name_snapshot,target_date,status,completed_date,responsible_employee_id").eq("tenant_id", tenantId).in("npd_order_id", orderIds).order("operation_no").limit(5000),
  ]);
  const stepByOrder = new Map<string, Row[]>();
  for (const step of steps) stepByOrder.set(String(step.npd_order_id), [...(stepByOrder.get(String(step.npd_order_id)) || []), step]);
  let html = '<div style="font-family:Arial,Helvetica,sans-serif;margin-top:18px"><div style="font-size:15px;font-weight:700;color:#8B0015;margin-bottom:8px">NPD PROCESS STATUS · OPEN / OVERDUE</div>';
  for (const order of orders) {
    const allSteps = stepByOrder.get(String(order.id)) || []; const done = allSteps.filter((x) => String(x.status || "").toUpperCase() === "COMPLETED").length;
    const part = maps.parts.get(String(order.part_id)) || {}; const customer = maps.parties.get(String(order.customer_id)) || {};
    html += '<table cellpadding="0" cellspacing="8" border="0" style="border-collapse:separate;width:100%;margin:0 0 12px 0"><tr>';
    html += `<td valign="top" style="width:220px;border:1px solid #CBD5E1;border-left:4px solid #8B0015;padding:10px;background:#FFFFFF"><div style="font-size:15px;font-weight:800;color:#17212B">${esc(part.part_number || part.fsi_part_number || "-")}</div><div style="font-weight:700;margin:2px 0 8px">${esc(part.part_name || "")}</div><div style="font-size:11px"><b>Order:</b> ${esc(order.order_number || "-")}<br><b>Customer:</b> ${esc(customer.party_code || "")} · ${esc(customer.party_name || "-")}<br><b>Delivery:</b> ${esc(order.delivery_date || "-")}<br><b>Progress:</b> ${done}/${allSteps.length}</div></td>`;
    for (const step of allSteps) {
      const status = String(step.status || "PENDING").toUpperCase(); const target = String(step.target_date || "").slice(0,10); const overdue = status !== "COMPLETED" && Boolean(target) && target < localDate;
      let bg="#FFF7ED", border="#FDBA74", color="#9A3412", label="Pending";
      if (status === "COMPLETED") { bg="#DCFCE7"; border="#86EFAC"; color="#166534"; label="✓ Completed"; }
      else if (overdue) { bg="#FEE2E2"; border="#FCA5A5"; color="#991B1B"; label="! Overdue"; }
      else if (status === "IN_PROGRESS") { bg="#DBEAFE"; border="#93C5FD"; color="#1D4ED8"; label="● In Process"; }
      else if (status === "ON_HOLD") { bg="#F3E8FF"; border="#D8B4FE"; color="#6B21A8"; label="Ⅱ On Hold"; }
      html += `<td valign="top" style="min-width:155px;border:1px solid ${border};padding:10px;background:${bg};color:#273444"><div style="font-size:11px;font-weight:800;color:#64748B">OP ${esc(step.operation_no || "-")}</div><div style="font-size:12px;font-weight:800;margin:5px 0">${esc(step.process_name_snapshot || step.process_name || "Process")}</div><div style="display:inline-block;padding:4px 6px;border-radius:4px;background:${bg};color:${color};font-size:11px;font-weight:800">${label}</div><div style="font-size:11px;margin-top:8px">Target ${esc(target || "Not set")}</div></td>`;
    }
    html += '</tr></table>';
  }
  return html + '</div>';
}
function wrap(text: string, max = 115): string[] {
  const words = String(text || "").split(/\s+/); const lines: string[] = []; let line = "";
  for (const word of words) {
    if ((line + " " + word).trim().length > max && line) { lines.push(line); line = word; } else line = (line + " " + word).trim();
  }
  if (line) lines.push(line); return lines;
}
async function digestPdf(title: string, localDate: string, rows: DigestRow[]): Promise<Uint8Array> {
  const pdf = await PDFDocument.create(); const font = await pdf.embedFont(StandardFonts.Helvetica); const bold = await pdf.embedFont(StandardFonts.HelveticaBold);
  let page = pdf.addPage([841.89, 595.28]); let y = 560;
  const newPage = () => { page = pdf.addPage([841.89, 595.28]); y = 560; };
  const draw = (text: string, size = 8, isBold = false) => { if (y < 35) newPage(); page.drawText(text, { x: 28, y, size, font: isBold ? bold : font, color: rgb(0.08, 0.08, 0.08) }); y -= size + 4; };
  draw("FOUR STAR INDUSTRIES PVT. LTD. · QCMS", 12, true); draw(title, 14, true); draw(`Report Date: ${localDate} · Records: ${rows.length}`, 9); y -= 5;
  draw("Reference | Part | Supplier / Customer | Due Date | Status | Qty", 8, true); y -= 3;
  rows.forEach((row, idx) => {
    const line = `${idx + 1}. ${row.reference} | ${row.part || "-"} | ${row.party || "-"} | ${row.due_date || "-"} | ${row.status || "-"} | ${row.quantity || "-"}`;
    for (const piece of wrap(line)) draw(piece, 8, false);
    y -= 2;
  });
  return await pdf.save();
}

async function gatherRows(admin: any, tenantId: string, schedule: Row, localDate: string, maps: { parties: Map<string, Row>; parts: Map<string, Row>; employees: Map<string, Row> }): Promise<DigestRow[]> {
  const daysAhead = Number(schedule.days_ahead || 0); const includeOpen = Boolean(schedule.include_open); const includeOverdue = Boolean(schedule.include_overdue);
  const result: DigestRow[] = [];
  const pushIf = (row: DigestRow, rawDue: any) => {
    const due = eligibleDate(rawDue, localDate, daysAhead, includeOpen, includeOverdue); if (!due.include) return;
    row.status = due.overdue ? `OVERDUE · ${row.status}` : `OPEN / DUE SOON · ${row.status}`; result.push(row);
  };

  if (schedule.schedule_key === "CUSTOMER_ORDER_OPEN_OVERDUE") {
    const { data = [] } = await admin.from("supply_customer_orders").select("*").eq("tenant_id", tenantId).limit(5000);
    for (const r of data) {
      if (["COMPLETED", "CLOSED", "CANCELLED"].includes(String(r.status || "").toUpperCase())) continue;
      const part = maps.parts.get(String(r.part_id)) || {}; const customer = maps.parties.get(String(r.customer_id)) || {};
      pushIf({ reference: String(r.master_reference_no || r.customer_order_no || "-"), part: String(part.fsi_part_number || part.part_number || "-"), party: String(customer.party_name || "-"), due_date: String(r.customer_delivery_date || "-"), status: String(r.status || "OPEN"), quantity: `${n(r.order_qty_pcs)} pcs` }, r.customer_delivery_date);
    }
  } else if (schedule.schedule_key === "PO_PENDING_APPROVAL") {
    const { data = [] } = await admin.from("supply_purchase_orders").select("*").eq("tenant_id", tenantId).eq("approval_status", "PENDING_APPROVAL").limit(5000);
    for (const r of data) {
      if (String(r.status || "").toUpperCase() === "CANCELLED") continue;
      const supplier = maps.parties.get(String(r.supplier_id)) || {}; const submitter = maps.employees.get(String(r.submitted_by_employee_id || "")) || {};
      result.push({ reference: String(r.po_number || "-"), part: String(r.po_type || "PURCHASE ORDER").replaceAll("_", " "), party: String(supplier.party_name || supplier.party_code || "-"), due_date: String(r.delivery_date || r.order_date || localDate), status: "PENDING APPROVAL", quantity: "Approval pending", supplier_id: String(r.supplier_id || ""), responsible_employee_id: String(submitter.reports_to_employee_id || "") || undefined });
    }
  } else if (schedule.schedule_key === "RM_PROCUREMENT_PENDING_DUE") {
    const { data: orders = [] } = await admin.from("supply_customer_orders").select("*").eq("tenant_id", tenantId).eq("rm_procurement_required", true).limit(5000);
    const { data: rmPos = [] } = await admin.from("supply_rm_purchase_orders").select("customer_order_id,ordered_qty_kg,status").eq("tenant_id", tenantId).limit(10000);
    const partIds = Array.from(new Set(orders.map((r: Row) => String(r.part_id || "")).filter(Boolean)));
    const { data: rawDetails = [] } = partIds.length ? await admin.from("part_raw_material_details").select("part_id,lead_time_days,status").eq("tenant_id", tenantId).eq("status", "ACTIVE").in("part_id", partIds).limit(10000) : { data: [] } as any;
    const leadByPart = new Map<string, number>();
    for (const raw of rawDetails) leadByPart.set(String(raw.part_id), Math.max(leadByPart.get(String(raw.part_id)) || 0, Number(raw.lead_time_days || 0)));
    const ordered = new Map<string, number>();
    for (const po of rmPos) if (String(po.status || "").toUpperCase() !== "CANCELLED") ordered.set(String(po.customer_order_id), (ordered.get(String(po.customer_order_id)) || 0) + Number(po.ordered_qty_kg || 0));
    for (const r of orders) {
      if (["COMPLETED","CLOSED","CANCELLED"].includes(String(r.status || "").toUpperCase())) continue;
      const pending = Math.max(Number(r.required_rm_kg || 0) - (ordered.get(String(r.id)) || 0), 0); if (pending <= 0.0001) continue;
      const part = maps.parts.get(String(r.part_id)) || {}; const customer = maps.parties.get(String(r.customer_id)) || {}; const leadDays = leadByPart.get(String(r.part_id)) || 0;
      const procurementDue = r.customer_delivery_date ? addDays(String(r.customer_delivery_date).slice(0,10), -leadDays) : r.customer_delivery_date;
      pushIf({ reference: String(r.master_reference_no || r.customer_order_no || "-"), part: String(part.fsi_part_number || part.part_number || "-"), party: String(customer.party_name || "-"), due_date: String(procurementDue || r.customer_delivery_date || "-"), status: `RM PO PENDING · lead ${leadDays}d`, quantity: `${n(pending)} kg pending` }, procurementDue || r.customer_delivery_date);
    }
  } else if (schedule.schedule_key === "RM_PO_OPEN_OVERDUE") {
    const { data = [] } = await admin.from("supply_rm_purchase_orders").select("*").eq("tenant_id", tenantId).limit(5000);
    for (const r of data) {
      if (["COMPLETED", "CLOSED", "CANCELLED"].includes(String(r.status || "").toUpperCase())) continue;
      const supplier = maps.parties.get(String(r.rm_supplier_id)) || {};
      pushIf({ reference: String(r.supplier_order_no || "-"), part: "Raw Material", party: String(supplier.party_name || supplier.party_code || "-"), due_date: String(r.expected_date || "-"), status: String(r.status || "OPEN"), quantity: `${n(r.ordered_qty_kg)} kg`, supplier_id: String(r.rm_supplier_id || "") }, r.expected_date);
    }
  } else if (schedule.schedule_key === "FORGING_ORDER_OPEN_OVERDUE") {
    const { data = [] } = await admin.from("supply_forging_orders").select("*").eq("tenant_id", tenantId).limit(5000);
    for (const r of data) {
      if (["COMPLETED", "CLOSED", "CANCELLED"].includes(String(r.status || "").toUpperCase())) continue;
      const supplier = maps.parties.get(String(r.forging_supplier_id)) || {};
      pushIf({ reference: String(r.supplier_order_no || "-"), part: "Forging", party: String(supplier.party_name || supplier.party_code || "-"), due_date: String(r.expected_date || "-"), status: String(r.status || "OPEN"), quantity: `${n(r.order_qty_pcs)} pcs`, supplier_id: String(r.forging_supplier_id || "") }, r.expected_date);
    }
  } else if (schedule.schedule_key === "OSP_RETURN_OPEN_OVERDUE") {
    const { data = [] } = await admin.from("osp_jobs").select("*").eq("tenant_id", tenantId).limit(5000);
    for (const r of data) {
      if (["COMPLETED", "REJECTED", "CANCELLED"].includes(String(r.status || "").toUpperCase())) continue;
      const vendor = maps.parties.get(String(r.vendor_id)) || {}; const part = maps.parts.get(String(r.part_id)) || {};
      pushIf({ reference: String(r.osp_job_number || "-"), part: String(part.fsi_part_number || part.part_number || "-"), party: String(vendor.party_name || vendor.party_code || "-"), due_date: String(r.expected_return_date || "-"), status: String(r.status || "AT_VENDOR"), quantity: `${n(Number(r.quantity_dispatched || 0) - Number(r.quantity_received || 0))} pcs pending`, supplier_id: String(r.vendor_id || "") }, r.expected_return_date);
    }
  } else if (schedule.schedule_key === "CALIBRATION_VALIDATION_DUE") {
    const [{ data: links = [] }, { data: assets = [] }, { data: processes = [] }] = await Promise.all([
      admin.from("quality_asset_part_process_links").select("*").eq("tenant_id", tenantId).eq("status", "ACTIVE").limit(10000),
      admin.from("quality_assets").select("id,asset_code,asset_name,asset_type,serial_number,location").eq("tenant_id", tenantId).limit(5000),
      admin.from("processes").select("id,process_code,process_name").eq("tenant_id", tenantId).limit(5000),
    ]);
    const assetMap = new Map<string, Row>(assets.map((r: Row) => [String(r.id), r])); const processMap = new Map<string, Row>(processes.map((r: Row) => [String(r.id), r]));
    for (const r of links) {
      const asset = assetMap.get(String(r.asset_id)) || {}; const part = maps.parts.get(String(r.part_id)) || {}; const process = processMap.get(String(r.process_id)) || {};
      pushIf({ reference: `${asset.asset_code || "ASSET"} · ${asset.asset_name || "Gauge / Fixture"}`, part: String(part.fsi_part_number || part.part_number || "-"), party: `${process.process_code || ""} ${process.process_name || "General"}`.trim(), due_date: String(r.next_due_date || "-"), status: String(r.service_type || "CALIBRATION"), quantity: `${r.frequency_days || 365} day frequency`, responsible_employee_id: String(r.responsible_employee_id || "") || undefined }, r.next_due_date);
    }
  } else if (schedule.schedule_key === "NPD_PROCESS_OPEN_OVERDUE") {
    const { data: steps = [] } = await admin.from("npd_order_steps").select("*").eq("tenant_id", tenantId).limit(5000);
    const { data: orders = [] } = await admin.from("npd_orders").select("id,order_number,part_id,customer_id,delivery_date").eq("tenant_id", tenantId).limit(5000);
    const orderMap = new Map<string, Row>(orders.map((r: Row) => [String(r.id), r]));
    for (const r of steps) {
      if (["COMPLETED", "APPROVED", "NOT_APPLICABLE", "CANCELLED"].includes(String(r.status || "").toUpperCase())) continue;
      const order = orderMap.get(String(r.npd_order_id)) || {}; const part = maps.parts.get(String(order.part_id)) || {}; const emp = maps.employees.get(String(r.responsible_employee_id)) || {};
      pushIf({ reference: `${order.order_number || "NPD"} · OP ${r.operation_no || "-"}`, part: String(part.fsi_part_number || part.part_number || "-"), party: `${emp.first_name || ""} ${emp.last_name || ""}`.trim() || "Unassigned", due_date: String(r.target_date || "-"), status: String(r.status || "PENDING"), quantity: String(r.process_name_snapshot || r.process_name || r.responsible || ""), responsible_employee_id: String(r.responsible_employee_id || ""), order_id: String(r.npd_order_id || "") }, r.target_date);
    }
  }
  return result;
}

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== "POST") return new Response(JSON.stringify({ error: "POST required" }), { status: 405, headers: jsonHeaders });
    const schedulerToken = req.headers.get("X-QCMS-Scheduler") || "";
    if (!schedulerToken) return new Response(JSON.stringify({ error: "Scheduler token required" }), { status: 401, headers: jsonHeaders });

    const url = Deno.env.get("SUPABASE_URL")!; const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!; const admin = createClient(url, serviceKey);
    const tokenHash = await sha256(schedulerToken);
    const { data: configs = [], error: configError } = await admin.from("qcms_notification_scheduler_config").select("tenant_id,scheduler_token_hash");
    if (configError) throw configError;
    const allowedTenants = configs.filter((r: Row) => String(r.scheduler_token_hash) === tokenHash).map((r: Row) => String(r.tenant_id));
    if (!allowedTenants.length) return new Response(JSON.stringify({ error: "Invalid scheduler token" }), { status: 401, headers: jsonHeaders });

    const now = new Date(); let processedSchedules = 0, sentMessages = 0, failedMessages = 0, generatedRows = 0;
    for (const tenantId of allowedTenants) {
      const { data: settings } = await admin.from("qcms_email_settings").select("*").eq("tenant_id", tenantId).maybeSingle();
      if (!settings?.enabled || !settings?.smtp_host || !settings?.sender_email) continue;
      const transporter = nodemailer.createTransport({
        host: settings.smtp_host, port: Number(settings.smtp_port || 587), secure: Boolean(settings.use_ssl), requireTLS: Boolean(settings.use_tls) && !Boolean(settings.use_ssl),
        auth: settings.smtp_username ? { user: settings.smtp_username, pass: settings.smtp_password || "" } : undefined,
        connectionTimeout: Number(settings.timeout_seconds || 20) * 1000, greetingTimeout: Number(settings.timeout_seconds || 20) * 1000, socketTimeout: Number(settings.timeout_seconds || 20) * 1000,
      });
      const [{ data: schedules = [] }, { data: parties = [] }, { data: parts = [] }, { data: employees = [] }, { data: templates = [] }] = await Promise.all([
        admin.from("qcms_notification_schedules").select("*").eq("tenant_id", tenantId).eq("enabled", true).limit(100),
        admin.from("parties").select("id,party_code,party_name,email,notification_emails").eq("tenant_id", tenantId).limit(5000),
        admin.from("parts").select("id,part_number,fsi_part_number,part_name").eq("tenant_id", tenantId).limit(5000),
        admin.from("employees").select("id,first_name,last_name,email,department,status,reports_to_employee_id").eq("tenant_id", tenantId).eq("status", "ACTIVE").limit(5000),
        admin.from("qcms_email_templates").select("*").eq("tenant_id", tenantId).eq("enabled", true).limit(500),
      ]);
      const maps = { parties: new Map<string, Row>(parties.map((r: Row) => [String(r.id), r])), parts: new Map<string, Row>(parts.map((r: Row) => [String(r.id), r])), employees: new Map<string, Row>(employees.map((r: Row) => [String(r.id), r])) };
      const templateMap = new Map<string, Row>(templates.map((r: Row) => [String(r.template_key), r]));

      for (const schedule of schedules) {
        const clock = localClock(now, String(schedule.timezone || "Asia/Kolkata"));
        if (clock.hour !== Number(schedule.hour_local ?? 8) || String(schedule.last_run_local_date || "") === clock.date) continue;
        processedSchedules += 1;
        const rows = await gatherRows(admin, tenantId, schedule, clock.date, maps); generatedRows += rows.length;
        const overdueCount = rows.filter((r) => r.status.startsWith("OVERDUE")).length; const openCount = rows.length - overdueCount;
        const template = templateMap.get(String(schedule.template_key || schedule.event_key)) || {};
        const baseCtx = { department: schedule.recipient_department || "QCMS Team", report_date: clock.date, open_count: openCount, overdue_count: overdueCount };
        const subject = renderTemplate(String(template.subject_template || `QCMS · ${schedule.schedule_label} · {{report_date}}`), baseCtx);
        const bodyText = renderTemplate(String(template.body_template || "Attached is the QCMS open / overdue report for {{report_date}}."), baseCtx);

        const primaryRecipients: Array<{ email: string; name: string; rows: DigestRow[] }> = [];
        if (schedule.schedule_key === "NPD_PROCESS_OPEN_OVERDUE" || schedule.schedule_key === "PO_PENDING_APPROVAL") {
          const grouped = new Map<string, DigestRow[]>();
          for (const row of rows) if (row.responsible_employee_id) grouped.set(row.responsible_employee_id, [...(grouped.get(row.responsible_employee_id) || []), row]);
          for (const [employeeId, assignedRows] of grouped) { const emp = maps.employees.get(employeeId) || {}; if (emp.email) primaryRecipients.push({ email: String(emp.email), name: `${emp.first_name || ""} ${emp.last_name || ""}`.trim(), rows: assignedRows }); }
        }
        if (!primaryRecipients.length) {
          if (schedule.employee_id) { const emp = maps.employees.get(String(schedule.employee_id)) || {}; if (emp.email) primaryRecipients.push({ email: String(emp.email), name: `${emp.first_name || ""} ${emp.last_name || ""}`.trim(), rows }); }
          else {
            const dept = String(schedule.recipient_department || "").toLowerCase().replace(/[^a-z0-9]/g, "");
            for (const emp of employees) { const eDept = String(emp.department || "").toLowerCase().replace(/[^a-z0-9]/g, ""); if (dept && eDept === dept && emp.email) primaryRecipients.push({ email: String(emp.email), name: `${emp.first_name || ""} ${emp.last_name || ""}`.trim(), rows }); }
          }
        }

        const supplierGroups = new Map<string, DigestRow[]>();
        if (schedule.include_suppliers) for (const row of rows) if (row.supplier_id) supplierGroups.set(row.supplier_id, [...(supplierGroups.get(row.supplier_id) || []), row]);
        for (const [supplierId, supplierRows] of supplierGroups) {
          const party = maps.parties.get(supplierId); for (const email of emailList(party)) primaryRecipients.push({ email, name: String(party?.party_name || "Supplier"), rows: supplierRows });
        }

        for (const recipient of primaryRecipients) {
          if (!recipient.rows.length) continue;
          const dedupeKey = `${schedule.schedule_key}:${clock.date}:${recipient.email.toLowerCase()}`;
          const { data: exists } = await admin.from("qcms_notification_outbox").select("id").eq("tenant_id", tenantId).eq("dedupe_key", dedupeKey).maybeSingle();
          if (exists?.id) continue;
          const pdfBytes = await digestPdf(String(schedule.schedule_label || "QCMS Open / Overdue Report"), clock.date, recipient.rows);
          let bodyHtml = baseHtml(bodyText);
          if (schedule.schedule_key === "NPD_PROCESS_OPEN_OVERDUE") bodyHtml += await npdCardsHtml(admin, tenantId, recipient.rows, maps, clock.date);
          const fileName = `QCMS_${String(schedule.schedule_key).replace(/[^A-Za-z0-9_-]+/g, "_")}_${clock.date}.pdf`;
          const path = `${tenantId}/notification_exports/automatic/${schedule.schedule_key}/${clock.date}/${crypto.randomUUID()}_${fileName}`;
          const upload = await admin.storage.from(BUCKET).upload(path, pdfBytes, { contentType: "application/pdf", upsert: false }); if (upload.error) throw upload.error;
          const manifest = [{ bucket: BUCKET, object_path: path, file_name: fileName, mime_type: "application/pdf", generated: true }];
          const { data: outbox, error: insertError } = await admin.from("qcms_notification_outbox").insert({ tenant_id: tenantId, event_key: schedule.event_key, recipient_email: recipient.email, recipient_name: recipient.name || null, subject, body_text: bodyText, body_html: bodyHtml, context: { ...baseCtx, schedule_key: schedule.schedule_key, record_count: recipient.rows.length }, template_key: schedule.template_key || schedule.event_key, attachment_manifest: manifest, dedupe_key: dedupeKey, is_automatic: true, scheduled_for: now.toISOString(), status: "PENDING" }).select("*").single();
          if (insertError) throw insertError;
          try {
            await admin.from("qcms_notification_outbox").update({ status: "SENDING", attempts: 1, updated_at: new Date().toISOString() }).eq("id", outbox.id);
            await transporter.sendMail({ from: settings.sender_name ? `"${String(settings.sender_name).replaceAll('"', '')}" <${settings.sender_email}>` : settings.sender_email, to: recipient.name ? `"${recipient.name.replaceAll('"', '')}" <${recipient.email}>` : recipient.email, replyTo: settings.reply_to || undefined, subject, text: bodyText, html: bodyHtml, attachments: [{ filename: fileName, content: Buffer.from(pdfBytes), contentType: "application/pdf" }] });
            await admin.from("qcms_notification_outbox").update({ status: "SENT", sent_at: new Date().toISOString(), last_error: null, updated_at: new Date().toISOString() }).eq("id", outbox.id);
            await admin.storage.from(BUCKET).remove([path]).catch(() => undefined); sentMessages += 1;
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error); await admin.from("qcms_notification_outbox").update({ status: "FAILED", last_error: message.slice(0, 2000), updated_at: new Date().toISOString() }).eq("id", outbox.id); failedMessages += 1;
          }
        }
        await admin.from("qcms_notification_schedules").update({ last_run_local_date: clock.date, last_run_at: new Date().toISOString(), updated_at: new Date().toISOString() }).eq("id", schedule.id).eq("tenant_id", tenantId);
      }
    }
    return new Response(JSON.stringify({ processed_schedules: processedSchedules, report_rows: generatedRows, sent: sentMessages, failed: failedMessages }), { headers: jsonHeaders });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error); return new Response(JSON.stringify({ error: message }), { status: 500, headers: jsonHeaders });
  }
});
