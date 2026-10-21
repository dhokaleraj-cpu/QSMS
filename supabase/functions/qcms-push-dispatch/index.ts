import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

// QCMS qcms-push-dispatch · build 4.14.49-R35
// Sends PENDING in-app notifications (public.qcms_user_notifications) to the user's registered
// iPhone / iPad (APNs, token-based .p8 key) and Android (FCM HTTP v1) devices.
// Secrets (Supabase → Edge Functions → Secrets). Nothing configured = clean no-op.
//   APNS_KEY_P8      contents of the AuthKey_XXXXXXXXXX.p8 file (PEM text)
//   APNS_KEY_ID      10-character key id
//   APNS_TEAM_ID     10-character Apple Team ID
//   APNS_BUNDLE_ID   optional, default com.stawnprecision.qcms
//   FCM_SERVICE_ACCOUNT_JSON  optional, Firebase service-account JSON (Android)
// Called every 2 minutes by pg_cron with the X-QCMS-Scheduler token (same as the other QCMS notifiers).

type Row = Record<string, any>;
const headers = { "Content-Type": "application/json" };
const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers });

async function sha256(v: string) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(v));
  return Array.from(new Uint8Array(b)).map((x) => x.toString(16).padStart(2, "0")).join("");
}
function b64url(data: ArrayBuffer | Uint8Array | string) {
  const bytes = typeof data === "string" ? new TextEncoder().encode(data) : new Uint8Array(data as ArrayBuffer);
  let s = ""; for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function pemBody(pem: string) {
  const clean = pem.replace(/-----[^-]+-----/g, "").replace(/\s+/g, "");
  const raw = atob(clean); const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out.buffer;
}

let apnsJwt: { token: string; at: number } | null = null;
async function apnsToken(keyP8: string, keyId: string, teamId: string) {
  const now = Math.floor(Date.now() / 1000);
  if (apnsJwt && now - apnsJwt.at < 1800) return apnsJwt.token;
  const key = await crypto.subtle.importKey("pkcs8", pemBody(keyP8), { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const head = b64url(JSON.stringify({ alg: "ES256", kid: keyId }));
  const claims = b64url(JSON.stringify({ iss: teamId, iat: now }));
  const sig = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, new TextEncoder().encode(`${head}.${claims}`));
  apnsJwt = { token: `${head}.${claims}.${b64url(sig)}`, at: now };
  return apnsJwt.token;
}

let fcmAccess: { token: string; exp: number; project: string } | null = null;
async function fcmToken(saJson: string) {
  const now = Math.floor(Date.now() / 1000);
  if (fcmAccess && fcmAccess.exp - 60 > now) return fcmAccess;
  const sa = JSON.parse(saJson);
  const key = await crypto.subtle.importKey("pkcs8", pemBody(sa.private_key), { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["sign"]);
  const head = b64url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const claims = b64url(JSON.stringify({ iss: sa.client_email, scope: "https://www.googleapis.com/auth/firebase.messaging",
    aud: "https://oauth2.googleapis.com/token", iat: now, exp: now + 3600 }));
  const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, new TextEncoder().encode(`${head}.${claims}`));
  const res = await fetch("https://oauth2.googleapis.com/token", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer", assertion: `${head}.${claims}.${b64url(sig)}` }) });
  const body = await res.json();
  if (!res.ok) throw new Error(`FCM OAuth failed: ${JSON.stringify(body).slice(0, 300)}`);
  fcmAccess = { token: body.access_token, exp: now + Number(body.expires_in || 3600), project: sa.project_id };
  return fcmAccess;
}

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== "POST") return json({ error: "POST required" }, 405);
    const token = req.headers.get("X-QCMS-Scheduler") || "";
    if (!token) return json({ error: "Scheduler token required" }, 401);
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    const th = await sha256(token);
    const { data: cfg = [] } = await admin.from("qcms_notification_scheduler_config").select("tenant_id,scheduler_token_hash");
    const tenants = (cfg || []).filter((r: Row) => String(r.scheduler_token_hash) === th).map((r: Row) => String(r.tenant_id));
    if (!tenants.length) return json({ error: "Invalid scheduler token" }, 401);

    const keyP8 = Deno.env.get("APNS_KEY_P8") || "", keyId = Deno.env.get("APNS_KEY_ID") || "", teamId = Deno.env.get("APNS_TEAM_ID") || "";
    const bundle = Deno.env.get("APNS_BUNDLE_ID") || "com.stawnprecision.qcms";
    const fcmSa = Deno.env.get("FCM_SERVICE_ACCOUNT_JSON") || "";
    const apnsReady = Boolean(keyP8 && keyId && teamId);
    const fcmReady = Boolean(fcmSa);
    if (!apnsReady && !fcmReady) return json({ configured: false, sent: 0, note: "No APNs / FCM secrets set - nothing to do." });

    const since = new Date(Date.now() - 30 * 60 * 1000).toISOString();
    // stale PENDING rows (older than 30 min) are not pushed any more - the user sees them in the app
    await admin.from("qcms_user_notifications").update({ push_status: "EXPIRED" }).in("tenant_id", tenants).eq("push_status", "PENDING").lt("created_at", since);
    const { data: rows = [] } = await admin.from("qcms_user_notifications")
      .select("id,tenant_id,recipient_profile_id,title,body,category,web_route,related_id,module_key,push_attempts")
      .in("tenant_id", tenants).eq("push_status", "PENDING").gte("created_at", since).order("created_at").limit(200);
    let sent = 0, skipped = 0, failed = 0;
    for (const n of rows || []) {
      if (!n.recipient_profile_id) { await admin.from("qcms_user_notifications").update({ push_status: "NO_DEVICE" }).eq("id", n.id); skipped++; continue; }
      const { data: devices = [] } = await admin.from("qcms_push_devices").select("id,platform,token").eq("profile_id", n.recipient_profile_id).eq("enabled", true);
      if (!devices?.length) { await admin.from("qcms_user_notifications").update({ push_status: "NO_DEVICE" }).eq("id", n.id); skipped++; continue; }
      const { count: unread } = await admin.from("qcms_user_notifications").select("id", { count: "exact", head: true })
        .eq("recipient_profile_id", n.recipient_profile_id).eq("is_read", false);
      let ok = 0; const errors: string[] = [];
      for (const d of devices) {
        try {
          const platform = String(d.platform || "").toUpperCase();
          if (platform.startsWith("IOS") && apnsReady) {
            const host = platform === "IOS_SANDBOX" ? "https://api.sandbox.push.apple.com" : "https://api.push.apple.com";
            const res = await fetch(`${host}/3/device/${d.token}`, {
              method: "POST",
              headers: { authorization: `bearer ${await apnsToken(keyP8, keyId, teamId)}`, "apns-topic": bundle, "apns-push-type": "alert",
                "apns-priority": n.category === "APPROVAL" ? "10" : "5", "content-type": "application/json" },
              body: JSON.stringify({ aps: { alert: { title: n.title, body: String(n.body || "").slice(0, 900) }, sound: "default", badge: Number(unread || 0),
                "thread-id": n.module_key || "qcms" }, notification_id: n.id, web_route: n.web_route, related_id: n.related_id, category: n.category }),
            });
            if (res.ok) ok++;
            else {
              const t = await res.text(); errors.push(`APNs ${res.status} ${t.slice(0, 160)}`);
              if (res.status === 410 || /BadDeviceToken|Unregistered/.test(t)) await admin.from("qcms_push_devices").update({ enabled: false, last_error: t.slice(0, 300) }).eq("id", d.id);
            }
          } else if (platform === "ANDROID" && fcmReady) {
            const f = await fcmToken(fcmSa);
            const res = await fetch(`https://fcm.googleapis.com/v1/projects/${f.project}/messages:send`, {
              method: "POST", headers: { authorization: `Bearer ${f.token}`, "content-type": "application/json" },
              body: JSON.stringify({ message: { token: d.token, notification: { title: n.title, body: String(n.body || "").slice(0, 900) },
                data: { notification_id: String(n.id), web_route: String(n.web_route || ""), category: String(n.category || "") },
                android: { priority: n.category === "APPROVAL" ? "HIGH" : "NORMAL", notification: { channel_id: "qcms_alerts" } } } }),
            });
            if (res.ok) ok++;
            else {
              const t = await res.text(); errors.push(`FCM ${res.status} ${t.slice(0, 160)}`);
              if (res.status === 404 || /UNREGISTERED/.test(t)) await admin.from("qcms_push_devices").update({ enabled: false, last_error: t.slice(0, 300) }).eq("id", d.id);
            }
          }
        } catch (e) { errors.push(e instanceof Error ? e.message : String(e)); }
      }
      const attempts = Number(n.push_attempts || 0) + 1;
      if (ok > 0) { await admin.from("qcms_user_notifications").update({ push_status: "SENT", pushed_at: new Date().toISOString(), push_attempts: attempts, push_error: null }).eq("id", n.id); sent++; }
      else if (!errors.length) { await admin.from("qcms_user_notifications").update({ push_status: "NO_PROVIDER", push_attempts: attempts }).eq("id", n.id); skipped++; }
      else { await admin.from("qcms_user_notifications").update({ push_status: attempts >= 3 ? "FAILED" : "PENDING", push_attempts: attempts, push_error: errors.join(" | ").slice(0, 1000) }).eq("id", n.id); failed++; }
    }
    return json({ configured: true, apns: apnsReady, fcm: fcmReady, sent, skipped, failed });
  } catch (e) {
    return json({ error: e instanceof Error ? e.message : String(e) }, 500);
  }
});
