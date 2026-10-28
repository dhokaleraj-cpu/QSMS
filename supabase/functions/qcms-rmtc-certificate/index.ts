import { createClient } from "npm:@supabase/supabase-js@2";

// QCMS qcms-rmtc-certificate · build 4.14.49-R38
// PUBLIC (verify_jwt = false). The QR stuck at the material storage location encodes
//   <SUPABASE_URL>/functions/v1/qcms-rmtc-certificate?t=<32-char token>
// The token is looked up with the service role in public.rmtc_qr_tokens (not revoked) and the request is
// redirected (302) to a fresh 10-minute signed URL of the stored approved-RMTC certificate PDF.
// Nothing else is exposed: no listing, no record data, only the one certificate the token was issued for.
const SIGNED_URL_SECONDS = 600;
const TOKEN_RE = /^[A-Za-z0-9]{32}$/;

function page(status: number, title: string, message: string): Response {
  const safe = (v: string) => v.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c] as string));
  const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">` +
    `<title>${safe(title)}</title><style>body{font-family:-apple-system,Segoe UI,Arial,sans-serif;background:#f8fafc;color:#0f172a;margin:0;padding:32px 16px}` +
    `main{max-width:520px;margin:auto;background:#fff;border:1px solid #cbd5e1;border-radius:10px;padding:22px}h1{font-size:18px;color:#0b6e70;margin:0 0 10px}</style></head>` +
    `<body><main><h1>${safe(title)}</h1><p>${safe(message)}</p><p style="color:#64748b;font-size:12px">STAWN QCMS · RMTC certificate QR</p></main></body></html>`;
  return new Response(html, { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
}

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== "GET" && req.method !== "HEAD") return page(405, "Method not allowed", "Open this link from the QR code.");
    const url = new URL(req.url);
    const token = (url.searchParams.get("t") || "").trim();
    if (!TOKEN_RE.test(token)) return page(400, "Invalid QR code", "This QR code is not a valid QCMS RMTC certificate code.");
    const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
    const { data: row, error } = await admin.from("rmtc_qr_tokens")
      .select("id, tenant_id, rmtc_approval_id, rmtc_number, certificate_bucket, certificate_path, revoked")
      .eq("token", token).maybeSingle();
    if (error) throw error;
    if (!row || row.revoked) return page(404, "Certificate not available", "This QR code is not active. Ask the Quality department for the current RMTC label.");
    let path = String(row.certificate_path || "").trim();
    const bucket = String(row.certificate_bucket || "quality-documents");
    if (!path) {
      // Fallback: newest PDF in the certificate folder of this RMTC.
      const folder = `${row.tenant_id}/rmtc_certificates/${row.rmtc_approval_id}`;
      const { data: files } = await admin.storage.from(bucket).list(folder, { limit: 50, sortBy: { column: "updated_at", order: "desc" } });
      const pdf = (files || []).find((f: { name: string }) => f.name.toLowerCase().endsWith(".pdf"));
      if (pdf) path = `${folder}/${pdf.name}`;
    }
    if (!path || !path.startsWith(`${row.tenant_id}/`)) return page(404, "Certificate not generated yet", `The certificate PDF for RMTC ${row.rmtc_number || ""} has not been stored yet. Open the RMTC in QCMS and press "Refresh certificate".`);
    const fileName = path.split("/").pop() || "RMTC_Certificate.pdf";
    const { data: signed, error: signError } = await admin.storage.from(bucket).createSignedUrl(path, SIGNED_URL_SECONDS, { download: fileName });
    if (signError || !signed?.signedUrl) return page(404, "Certificate not available", "The certificate file could not be found. Ask the Quality department to refresh the RMTC certificate.");
    return new Response(null, { status: 302, headers: { Location: signed.signedUrl, "Cache-Control": "no-store" } });
  } catch (err) {
    console.error("qcms-rmtc-certificate", err instanceof Error ? err.message : String(err));
    return page(500, "Temporarily unavailable", "The certificate could not be opened. Please try again in a minute.");
  }
});
