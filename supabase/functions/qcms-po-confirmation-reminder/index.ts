import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import nodemailer from "npm:nodemailer@6.9.16";

const jsonHeaders = { "Content-Type": "application/json" };
type Row = Record<string, any>;

function hex(bytes: ArrayBuffer): string {
  return Array.from(new Uint8Array(bytes)).map((b) => b.toString(16).padStart(2, "0")).join("");
}
async function sha256(value: string): Promise<string> {
  return hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)));
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
function indiaDate(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}
function cleanError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== "POST") return new Response(JSON.stringify({ error: "POST required" }), { status: 405, headers: jsonHeaders });
    const schedulerToken = req.headers.get("X-QCMS-Scheduler") || "";
    if (!schedulerToken) return new Response(JSON.stringify({ error: "Scheduler token required" }), { status: 401, headers: jsonHeaders });

    const url = Deno.env.get("SUPABASE_URL") || "";
    const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
    if (!url || !serviceKey) throw new Error("Supabase function secrets are unavailable");
    const admin = createClient(url, serviceKey, { auth: { autoRefreshToken: false, persistSession: false } });
    const tokenHash = await sha256(schedulerToken);
    const { data: configs = [], error: configError } = await admin.from("qcms_notification_scheduler_config").select("tenant_id,scheduler_token_hash");
    if (configError) throw configError;
    const tenantIds = configs.filter((r: Row) => String(r.scheduler_token_hash) === tokenHash).map((r: Row) => String(r.tenant_id));
    if (!tenantIds.length) return new Response(JSON.stringify({ error: "Invalid scheduler token" }), { status: 401, headers: jsonHeaders });

    const reportDate = indiaDate();
    let sent = 0, failed = 0, pending = 0;
    for (const tenantId of tenantIds) {
      const { data: schedule } = await admin.from("qcms_notification_schedules").select("*").eq("tenant_id", tenantId).eq("schedule_key", "PO_CONFIRMATION_DAILY").eq("enabled", true).maybeSingle();
      if (!schedule) continue;
      if (String(schedule.last_run_local_date || "") === reportDate) continue;

      const { data: settings } = await admin.from("qcms_email_settings").select("*").eq("tenant_id", tenantId).maybeSingle();
      if (!settings?.enabled || !settings?.smtp_host || !settings?.sender_email) continue;
      const transporter = nodemailer.createTransport({
        host: settings.smtp_host,
        port: Number(settings.smtp_port || 587),
        secure: Boolean(settings.use_ssl),
        requireTLS: Boolean(settings.use_tls) && !Boolean(settings.use_ssl),
        auth: settings.smtp_username ? { user: settings.smtp_username, pass: settings.smtp_password || "" } : undefined,
        connectionTimeout: Number(settings.timeout_seconds || 20) * 1000,
        greetingTimeout: Number(settings.timeout_seconds || 20) * 1000,
        socketTimeout: Number(settings.timeout_seconds || 20) * 1000,
      });

      const { data: confirmations = [] } = await admin.from("supply_po_confirmations").select("*").eq("tenant_id", tenantId).in("confirmation_status", ["PENDING", "REVISION_REQUESTED"]).limit(5000);
      const poIds = confirmations.map((r: Row) => String(r.purchase_order_id || "")).filter(Boolean);
      const supplierIds = confirmations.map((r: Row) => String(r.supplier_id || "")).filter(Boolean);
      const { data: pos = [] } = poIds.length ? await admin.from("supply_purchase_orders").select("id,po_number,po_type,supplier_id,delivery_date,status,approval_status").eq("tenant_id", tenantId).in("id", poIds) : { data: [] } as any;
      const { data: parties = [] } = supplierIds.length ? await admin.from("parties").select("id,party_name,party_code,email,notification_emails").eq("tenant_id", tenantId).in("id", supplierIds) : { data: [] } as any;
      const poMap = new Map<string, Row>(pos.map((r: Row) => [String(r.id), r]));
      const partyMap = new Map<string, Row>(parties.map((r: Row) => [String(r.id), r]));

      for (const conf of confirmations) {
        const po = poMap.get(String(conf.purchase_order_id)) || {};
        if (!po.id || String(po.approval_status || "").toUpperCase() !== "APPROVED" || ["CANCELLED", "CLOSED"].includes(String(po.status || "").toUpperCase())) continue;
        const supplier = partyMap.get(String(conf.supplier_id)) || {};
        const emails = emailList(supplier);
        if (!emails.length) continue;
        pending += 1;
        let confirmationSent = false;
        for (const email of emails) {
          const dedupeKey = `PO_CONFIRMATION_DAILY:${reportDate}:${conf.id}:${email.toLowerCase()}`;
          const { data: existing } = await admin.from("qcms_notification_outbox").select("id,status").eq("tenant_id", tenantId).eq("dedupe_key", dedupeKey).maybeSingle();
          if (existing?.id) continue;
          const subject = `PRIORITY · Purchase Order confirmation pending · ${po.po_number || "QCMS PO"}`;
          const bodyText = [
            `Dear ${supplier.party_name || "Supplier"},`, "",
            `This is a priority daily reminder to confirm Purchase Order ${po.po_number || "-"}.`,
            `PO Type: ${String(po.po_type || "PURCHASE ORDER").replaceAll("_", " ")}`,
            `Requested confirmation date: ${String(conf.requested_at || "").slice(0, 10) || "-"}`,
            `Expected delivery date: ${po.delivery_date || "-"}`,
            `Previous automated reminders: ${Number(conf.reminder_count || 0)}`,
            "", "Please send your Purchase Order acknowledgement / confirmation on priority. Daily reminders will stop automatically once the confirmation is recorded in QCMS.",
            "", "Regards,", "Four Star Industries Pvt. Ltd. · QCMS",
          ].join("\n");
          const { data: outbox, error: insertError } = await admin.from("qcms_notification_outbox").insert({
            tenant_id: tenantId, event_key: "PO_CONFIRMATION_REQUIRED", recipient_email: email, recipient_name: supplier.party_name || null,
            subject, body_text: bodyText, body_html: bodyText.split("\n").join("<br>"),
            context: { purchase_order_id: po.id, confirmation_id: conf.id, po_number: po.po_number, report_date: reportDate, priority: "HIGH" },
            template_key: "PO_CONFIRMATION_DAILY_DIGEST", attachment_manifest: [], dedupe_key: dedupeKey,
            is_automatic: true, scheduled_for: new Date().toISOString(), status: "PENDING",
          }).select("id").single();
          if (insertError) throw insertError;
          try {
            await admin.from("qcms_notification_outbox").update({ status: "SENDING", attempts: 1, updated_at: new Date().toISOString() }).eq("id", outbox.id);
            await transporter.sendMail({
              from: settings.sender_name ? `"${String(settings.sender_name).replaceAll('"', '')}" <${settings.sender_email}>` : settings.sender_email,
              to: supplier.party_name ? `"${String(supplier.party_name).replaceAll('"', '')}" <${email}>` : email,
              replyTo: settings.reply_to || undefined, subject, text: bodyText, html: bodyText.split("\n").join("<br>"),
            });
            await admin.from("qcms_notification_outbox").update({ status: "SENT", sent_at: new Date().toISOString(), last_error: null, updated_at: new Date().toISOString() }).eq("id", outbox.id);
            sent += 1; confirmationSent = true;
          } catch (error) {
            const message = cleanError(error);
            await admin.from("qcms_notification_outbox").update({ status: "FAILED", last_error: message.slice(0, 2000), updated_at: new Date().toISOString() }).eq("id", outbox.id);
            failed += 1;
          }
        }
        if (confirmationSent) await admin.from("supply_po_confirmations").update({ last_reminder_at: new Date().toISOString(), reminder_count: Number(conf.reminder_count || 0) + 1, updated_at: new Date().toISOString() }).eq("id", conf.id).eq("tenant_id", tenantId);
      }
      await admin.from("qcms_notification_schedules").update({ last_run_local_date: reportDate, last_run_at: new Date().toISOString(), updated_at: new Date().toISOString() }).eq("id", schedule.id).eq("tenant_id", tenantId);
    }
    return new Response(JSON.stringify({ report_date: reportDate, pending_confirmations: pending, sent, failed }), { headers: jsonHeaders });
  } catch (error) {
    return new Response(JSON.stringify({ error: cleanError(error) }), { status: 500, headers: jsonHeaders });
  }
});
