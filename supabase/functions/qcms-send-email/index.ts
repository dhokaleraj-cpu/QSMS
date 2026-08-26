import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import nodemailer from "npm:nodemailer@6.9.16";
import { Buffer } from "node:buffer";

const jsonHeaders = { "Content-Type": "application/json" };

type ManifestItem = {
  bucket?: string;
  object_path?: string;
  file_name?: string;
  mime_type?: string;
  generated?: boolean;
};

function cleanError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (message.includes("535 5.7.139") || message.toLowerCase().includes("smtpclientauthentication is disabled")) {
    return "Microsoft 365 rejected SMTP AUTH (535 5.7.139): SmtpClientAuthentication is disabled by Exchange policy. enable Authenticated SMTP for the sending mailbox/tenant or use OAuth/Modern Authentication. " + message;
  }
  return message;
}

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
    const ready = Boolean(settings?.enabled && settings?.smtp_host && settings?.smtp_port && settings?.sender_email);

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
        const attachments: Array<{ filename: string; content: Buffer; contentType?: string }> = [];
        const generatedForCleanup: Array<{ bucket: string; path: string }> = [];
        const manifest: ManifestItem[] = Array.isArray(row.attachment_manifest) ? row.attachment_manifest : [];
        for (const item of manifest.slice(0, 20)) {
          const bucket = String(item?.bucket || "quality-documents");
          const objectPath = String(item?.object_path || "").trim();
          if (!objectPath) continue;
          const { data: blob, error: downloadError } = await admin.storage.from(bucket).download(objectPath);
          if (downloadError || !blob) throw downloadError || new Error(`Attachment could not be downloaded: ${objectPath}`);
          attachments.push({
            filename: String(item?.file_name || objectPath.split("/").pop() || "attachment"),
            content: Buffer.from(await blob.arrayBuffer()),
            contentType: String(item?.mime_type || "application/octet-stream"),
          });
          if (item?.generated) generatedForCleanup.push({ bucket, path: objectPath });
        }

        await transporter.sendMail({
          from: settings.sender_name ? `"${String(settings.sender_name).replaceAll('"', '')}" <${settings.sender_email}>` : settings.sender_email,
          to: row.recipient_name ? `"${String(row.recipient_name).replaceAll('"', '')}" <${row.recipient_email}>` : row.recipient_email,
          cc: Array.isArray(row.cc_emails) && row.cc_emails.length ? row.cc_emails : undefined,
          bcc: Array.isArray(row.bcc_emails) && row.bcc_emails.length ? row.bcc_emails : undefined,
          replyTo: settings.reply_to || undefined,
          subject: row.subject,
          text: row.body_text,
          html: row.body_html || undefined,
          attachments,
        });
        await admin.from("qcms_notification_outbox").update({ status: "SENT", sent_at: new Date().toISOString(), last_error: null, updated_at: new Date().toISOString() }).eq("id", row.id);
        for (const file of generatedForCleanup) {
          await admin.storage.from(file.bucket).remove([file.path]).catch(() => undefined);
        }
        sent += 1;
      } catch (error) {
        const message = cleanError(error);
        await admin.from("qcms_notification_outbox").update({ status: "FAILED", last_error: message.slice(0, 2000), updated_at: new Date().toISOString() }).eq("id", row.id);
        failed += 1;
      }
    }
    return new Response(JSON.stringify({ processed: outbox.length, sent, failed }), { headers: jsonHeaders });
  } catch (error) {
    const message = cleanError(error);
    return new Response(JSON.stringify({ error: message }), { status: 500, headers: jsonHeaders });
  }
});
