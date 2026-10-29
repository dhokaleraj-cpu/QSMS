-- QCMS v4.14.49 R40 (agent W) · public RMTC QR (no login) - all RMTC documents via the Edge Function qcms-rmtc-certificate.
-- Additive and idempotent: one partial index + table comment. No business data is changed, no policy is widened.
--
-- The QR now encodes https://<project>.supabase.co/functions/v1/qcms-rmtc-certificate?t=<32-char random token>
-- (core/rmtc_qr.QR_CONTENT = "TOKEN"). The Edge Function (verify_jwt = false, service role inside, read-only) resolves
-- the token in public.rmtc_qr_tokens (not revoked) and lists / zips / merges the customer-safe certificate
-- (rmtc_qr_tokens.certificate_path) and every ACTIVE RMTC attachment of the same tenant. Clients create tokens with the
-- existing authenticated insert policy; "Revoke QR (new code)" marks the token revoked and inserts a new one.

-- Fast lookup of the ACTIVE attachments of one RMTC (public page / ZIP / combined PDF).
create index if not exists idx_document_attachments_rmtc_active
  on public.document_attachments (tenant_id, entity_id, created_at)
  where entity_type = 'RMTC' and status = 'ACTIVE';

comment on table public.rmtc_qr_tokens is
  'R38/R40: public QR tokens for approved RMTCs (material-location QR, no login). One active (not revoked) token per RMTC; '
  'resolved by the public Edge Function qcms-rmtc-certificate (document index, f=zip, f=pdf, d=<id>). '
  'certificate_path = customer-safe RMTC print PDF in quality-documents/<tenant>/rmtc_certificates/<rmtc_id>/.';
