import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import nodemailer from "npm:nodemailer@6.9.16";

const jsonHeaders = { "Content-Type": "application/json" };

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== "POST") return new Response(JSON.stringify({ error: "POST required" }), { status: 405, headers: jsonHeaders });
    const authHeader = req.headers.get("Authorization") || "";
    if (!authHeader.startsWith("Bearer ")) return new Response(JSON.stringify({ error: "Authentication required" }), { status: 401, headers: jsonHeaders });
    const token = authHeader.slice(7);
    const url = Deno.env.get("SUPABASE_URL")!;
    const anon = Deno.env.get("SUPABASE_ANON_KEY") || Deno.env.get("SUPABASE_PUBLISHABLE_KEY")!;
    const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const userClient = createClient(url, anon, { global: { headers: { Authorization: `Bearer ${token}` } } });
    const { data: userData, error: userError } = await userClient.auth.getUser(token);
    if (userError || !userData.user) return new Response(JSON.stringify({ error: "Invalid session" }), { status: 401, headers: jsonHeaders });

    const admin = createClient(url, serviceKey);
    const { data: profile, error: profileError } = await admin.from("profiles").select("tenant_id").eq("id", userData.user.id).single();
    if (profileError || !profile?.tenant_id) return new Response(JSON.stringify({ error: "QCMS profile not found" }), { status: 403, headers: jsonHeaders });
    const tenantId = profile.tenant_id;
    const body = await req.json().catch(() => ({}));
    const outboxIds = Array.isArray(body?.outbox_ids) ? body.outbox_ids.filter((v: unknown) => typeof v === "string") : [];
    if (!outboxIds.length) return new Response(JSON.stringify({ processed: 0, sent: 0, failed: 0 }), { headers: jsonHeaders });

    const { data: settings, error: settingsError } = await admin.from("qcms_email_settings").select("*").eq("tenant_id", tenantId).maybeSingle();
    if (settingsError) throw settingsError;
    const enabled = Boolean(settings?.enabled);
    const ready = enabled && settings?.smtp_host && settings?.smtp_port && settings?.sender_email;

    const { data: outbox, error: outboxError } = await admin.from("qcms_notification_outbox")
      .select("*").eq("tenant_id", tenantId).in("id", outboxIds).in("status", ["PENDING", "FAILED"]);
    if (outboxError) throw outboxError;
    if (!outbox?.length) return new Response(JSON.stringify({ processed: 0, sent: 0, failed: 0 }), { headers: jsonHeaders });

    if (!ready) {
      for (const row of outbox) {
        await admin.from("qcms_notification_outbox").update({ status: "FAILED", attempts: Number(row.attempts || 0) + 1, last_error: "Email server is disabled or incomplete.", updated_at: new Date().toISOString() }).eq("id", row.id);
      }
      return new Response(JSON.stringify({ processed: outbox.length, sent: 0, failed: outbox.length, error: "Email server is disabled or incomplete." }), { headers: jsonHeaders });
    }

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
    let sent = 0, failed = 0;
    for (const row of outbox) {
      const attempts = Number(row.attempts || 0) + 1;
      await admin.from("qcms_notification_outbox").update({ status: "SENDING", attempts, last_error: null, updated_at: new Date().toISOString() }).eq("id", row.id);
      try {
        await transporter.sendMail({
          from: settings.sender_name ? `"${String(settings.sender_name).replaceAll('"', '')}" <${settings.sender_email}>` : settings.sender_email,
          to: row.recipient_name ? `"${String(row.recipient_name).replaceAll('"', '')}" <${row.recipient_email}>` : row.recipient_email,
          replyTo: settings.reply_to || undefined,
          subject: row.subject,
          text: row.body_text,
        });
        await admin.from("qcms_notification_outbox").update({ status: "SENT", sent_at: new Date().toISOString(), last_error: null, updated_at: new Date().toISOString() }).eq("id", row.id);
        sent += 1;
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        await admin.from("qcms_notification_outbox").update({ status: "FAILED", last_error: message.slice(0, 2000), updated_at: new Date().toISOString() }).eq("id", row.id);
        failed += 1;
      }
    }
    return new Response(JSON.stringify({ processed: outbox.length, sent, failed }), { headers: jsonHeaders });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return new Response(JSON.stringify({ error: message }), { status: 500, headers: jsonHeaders });
  }
});
