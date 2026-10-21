import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

// QCMS qcms-whatsapp-dispatch · build 4.14.49-R35
// Sends WhatsApp template messages (Meta WhatsApp Business Cloud API) for in-app notifications
// whose whatsapp_status = 'PENDING' (APPROVAL / TASK by default, see public.qcms_whatsapp_settings).
// Recipient = the employee's mobile_number, only when employees.whatsapp_opt_in = true.
// Secret: WHATSAPP_TOKEN (permanent System User access token). Never stored in any table.
// Modes:
//   * scheduler  - header X-QCMS-Scheduler (pg_cron every 2 minutes)
//   * test       - Authorization: Bearer <user JWT>, body {"action":"test","to":"9198…","template":"hello_world"}
//                  allowed for company Admin / STAWN developer only.
// Template variables (body): {{1}} recipient name, {{2}} title, {{3}} details. Button-less templates.

type Row = Record<string, any>;
const cors = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS" };
const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { ...cors, "Content-Type": "application/json" } });

async function sha256(v: string) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(v));
  return Array.from(new Uint8Array(b)).map((x) => x.toString(16).padStart(2, "0")).join("");
}
// WhatsApp template parameters may not contain new lines, tabs or more than 4 consecutive spaces.
const param = (v: unknown, max = 900) => String(v ?? "-").replace(/[\r\n\t]+/g, " ").replace(/ {2,}/g, " ").trim().slice(0, max) || "-";
function phone(raw: unknown, cc: string) {
  let d = String(raw ?? "").replace(/[^0-9+]/g, "");
  if (d.startsWith("+")) return d.slice(1);
  d = d.replace(/^0+/, "");
  if (d.length === 10) return `${cc}${d}`;
  return d.length >= 11 ? d : "";
}

async function sendTemplate(s: Row, token: string, to: string, template: string, lang: string, params: string[] | null) {
  const body: Row = { messaging_product: "whatsapp", to, type: "template", template: { name: template, language: { code: lang } } };
  if (params && params.length) body.template.components = [{ type: "body", parameters: params.map((t) => ({ type: "text", text: t })) }];
  const res = await fetch(`https://graph.facebook.com/${s.api_version || "v21.0"}/${s.phone_number_id}/messages`, {
    method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const out = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`WhatsApp API ${res.status}: ${JSON.stringify(out?.error || out).slice(0, 400)}`);
  return out;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    if (req.method !== "POST") return json({ error: "POST required" }, 405);
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
    const waToken = Deno.env.get("WHATSAPP_TOKEN") || "";
    const payload: Row = await req.json().catch(() => ({}));

    // ---------- test message from Admin → System Settings → WhatsApp ----------
    if (payload.action === "test") {
      const jwt = (req.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "");
      if (!jwt) return json({ error: "Sign in required" }, 401);
      const { data: u } = await admin.auth.getUser(jwt);
      if (!u?.user) return json({ error: "Session expired - sign in again" }, 401);
      const { data: prof } = await admin.from("profiles").select("id,tenant_id,role,status").eq("id", u.user.id).maybeSingle();
      const { data: dev } = await admin.from("qcms_stawn_developers").select("profile_id").eq("profile_id", u.user.id).eq("active", true).maybeSingle();
      if (!prof || prof.status !== "ACTIVE" || (prof.role !== "ADMIN" && !dev)) return json({ error: "Only the company Admin can send a WhatsApp test" }, 403);
      const { data: s } = await admin.from("qcms_whatsapp_settings").select("*").eq("tenant_id", prof.tenant_id).maybeSingle();
      if (!waToken) return json({ ok: false, configured: false, error: "Secret WHATSAPP_TOKEN is not set (supabase secrets set WHATSAPP_TOKEN=...)." });
      if (!s?.phone_number_id) return json({ ok: false, configured: false, error: "Save the WhatsApp Phone Number ID first." });
      const to = phone(payload.to, String(s.default_country_code || "91"));
      if (!to) return json({ ok: false, error: "Enter the mobile number with country code, e.g. 9198XXXXXXXX" });
      const template = String(payload.template || "hello_world");
      const params = template === "hello_world" ? null : ["QCMS user", "STAWN QCMS test message", "WhatsApp notifications are working."];
      const lang = template === "hello_world" ? "en_US" : String(s.template_language || "en");
      const out = await sendTemplate(s, waToken, to, template, lang, params);
      return json({ ok: true, to, template, message_id: out?.messages?.[0]?.id || null });
    }

    // ---------- scheduler ----------
    const token = req.headers.get("X-QCMS-Scheduler") || "";
    if (!token) return json({ error: "Scheduler token required" }, 401);
    const th = await sha256(token);
    const { data: cfg = [] } = await admin.from("qcms_notification_scheduler_config").select("tenant_id,scheduler_token_hash");
    const tenants = (cfg || []).filter((r: Row) => String(r.scheduler_token_hash) === th).map((r: Row) => String(r.tenant_id));
    if (!tenants.length) return json({ error: "Invalid scheduler token" }, 401);
    if (!waToken) return json({ configured: false, sent: 0, note: "WHATSAPP_TOKEN not set - nothing to do." });

    let sent = 0, skipped = 0, failed = 0;
    for (const tenantId of tenants) {
      const { data: s } = await admin.from("qcms_whatsapp_settings").select("*").eq("tenant_id", tenantId).maybeSingle();
      if (!s?.enabled || !s?.phone_number_id) continue;
      const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
      await admin.from("qcms_user_notifications").update({ whatsapp_status: "EXPIRED" }).eq("tenant_id", tenantId).eq("whatsapp_status", "PENDING").lt("created_at", since);
      const { data: rows = [] } = await admin.from("qcms_user_notifications")
        .select("id,recipient_employee_id,recipient_profile_id,title,body,category,web_route")
        .eq("tenant_id", tenantId).eq("whatsapp_status", "PENDING").gte("created_at", since).order("created_at").limit(100);
      for (const n of rows || []) {
        const mark = (status: string, err: string | null = null) => admin.from("qcms_user_notifications")
          .update({ whatsapp_status: status, whatsapp_error: err, ...(status === "SENT" ? { whatsapp_sent_at: new Date().toISOString() } : {}) }).eq("id", n.id);
        let emp: Row | null = null;
        if (n.recipient_employee_id) ({ data: emp } = await admin.from("employees").select("id,first_name,last_name,mobile_number,whatsapp_opt_in").eq("id", n.recipient_employee_id).maybeSingle());
        if (!emp && n.recipient_profile_id) ({ data: emp } = await admin.from("employees").select("id,first_name,last_name,mobile_number,whatsapp_opt_in").eq("profile_id", n.recipient_profile_id).maybeSingle());
        if (!emp?.whatsapp_opt_in) { await mark("SKIPPED", "Recipient has not opted in to WhatsApp"); skipped++; continue; }
        const to = phone(emp.mobile_number, String(s.default_country_code || "91"));
        if (!to) { await mark("SKIPPED", "No valid mobile number"); skipped++; continue; }
        const template = n.category === "APPROVAL" ? s.approval_template : n.category === "TASK" ? s.task_template : s.update_template;
        const name = `${emp.first_name || ""} ${emp.last_name || ""}`.trim() || "QCMS user";
        const details = param(`${n.body || ""}${s.app_link ? ` Open: ${s.app_link}/${n.web_route || ""}` : ""}`);
        try { await sendTemplate(s, waToken, to, String(template), String(s.template_language || "en"), [param(name, 60), param(n.title, 200), details]); await mark("SENT"); sent++; }
        catch (e) { await mark("FAILED", (e instanceof Error ? e.message : String(e)).slice(0, 1000)); failed++; }
      }
    }
    return json({ configured: true, sent, skipped, failed });
  } catch (e) {
    return json({ error: e instanceof Error ? e.message : String(e) }, 500);
  }
});
