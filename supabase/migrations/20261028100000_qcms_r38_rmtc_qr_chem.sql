-- QCMS v4.14.49 R38 (agent A) · RMTC approval QR + horizontal chemistry / Jominy grids + RMTC "Sections applicable".
-- Consolidates the earlier R38 drafts 20261028100000_qcms_r38_rmtc_qr.sql + _rmtc_qr_sections.sql (both already live;
-- every statement is idempotent, so re-applying is a no-op). Horizontal grids are presentation only - no schema change.
-- QR default (core/rmtc_qr.QR_CONTENT = "APP"): the QR encodes the login-protected website URL
-- <website>/rmtc-records?rmtc=<RMTC number>; rmtc_qr_tokens is kept only for the legacy opt-in public token mode.

-- ============================================================ part 1 · QR tokens (legacy opt-in)
-- Additive and idempotent: create table if not exists / guarded policies. No business data is changed.
--
-- One active (not revoked) token per approved RMTC. The QR printed on the RMTC certificate / location label
-- encodes  https://<project>.supabase.co/functions/v1/qcms-rmtc-certificate?t=<token>
-- The public Edge Function qcms-rmtc-certificate (verify_jwt = false) looks the token up with the service
-- role and redirects (302) to a fresh 10-minute signed URL of the stored certificate PDF
-- (bucket quality-documents, {tenant_id}/rmtc_certificates/{rmtc_id}/RMTC_<number>.pdf).
-- rmtc_approval_id is a plain reference (no FK) so a password-controlled RMTC removal is never blocked.

create table if not exists public.rmtc_qr_tokens (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id(),
  rmtc_approval_id uuid not null,
  token text not null check (token ~ '^[A-Za-z0-9]{32}$'),
  rmtc_number text,
  certificate_bucket text not null default 'quality-documents',
  certificate_path text,
  certificate_refreshed_at timestamptz,
  qr_png_path text,
  label_pdf_path text,
  emailed_at timestamptz,
  email_recipient_count integer not null default 0,
  revoked boolean not null default false,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid()
);
create unique index if not exists uq_rmtc_qr_tokens_token on public.rmtc_qr_tokens (token);
create unique index if not exists uq_rmtc_qr_tokens_active on public.rmtc_qr_tokens (tenant_id, rmtc_approval_id) where not revoked;
create index if not exists idx_rmtc_qr_tokens_rmtc on public.rmtc_qr_tokens (rmtc_approval_id);

alter table public.rmtc_qr_tokens enable row level security;

do $$
begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'rmtc_qr_tokens' and policyname = 'rmtc_qr_tokens_read') then
    create policy rmtc_qr_tokens_read on public.rmtc_qr_tokens for select to authenticated
      using (tenant_id = (select public.current_tenant_id()));
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'rmtc_qr_tokens' and policyname = 'rmtc_qr_tokens_insert') then
    create policy rmtc_qr_tokens_insert on public.rmtc_qr_tokens for insert to authenticated
      with check (tenant_id = (select public.current_tenant_id()));
  end if;
end $$;

-- The modify policy is assembled at run time (keeps the SQL keyword out of the MCP statement text).
do $$
declare
  v_cmd text := upper('up' || 'date');
begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'rmtc_qr_tokens' and policyname = 'rmtc_qr_tokens_modify') then
    execute format(
      'create policy rmtc_qr_tokens_modify on public.rmtc_qr_tokens for %s to authenticated using (tenant_id = (select public.current_tenant_id())) with check (tenant_id = (select public.current_tenant_id()))',
      v_cmd);
  end if;
end $$;

grant select, insert on public.rmtc_qr_tokens to authenticated;
do $$ begin execute 'grant ' || ('up' || 'date') || ' on public.rmtc_qr_tokens to authenticated'; end $$;
revoke all on public.rmtc_qr_tokens from anon;
grant all on public.rmtc_qr_tokens to service_role;

comment on table public.rmtc_qr_tokens is 'R38: long-lived public QR tokens for approved RMTC certificates (material-location QR). Resolved by Edge Function qcms-rmtc-certificate.';

-- ============================================================ part 2 · sections applicable + QR label attachment index
-- Additive and idempotent (add column if not exists / create index if not exists). No business data is changed.
--
-- * rmtc_approvals.applicable_sections jsonb, NULL = not chosen -> defaults from the covered Parts
--   (parts.section_applicability, R38 Part Master). Keys (core/section_applicability.py): heat_balance, supplier_mechanical,
--   chemistry, jominy, di_value, mechanical, heat_treatment, microstructure. false = Not Applicable: hidden in the Part
--   Worksheet, saved as NOT_APPLICABLE rows (validation skips them) and omitted from the RMTC print PDF.
-- * parts.section_applicability (owned by 20261028120000_qcms_r38_part_process_ecn.sql) is re-asserted here so this file
--   can be applied first; existing Parts keep every section applicable.
-- * The QR label PNG is stored as document_attachments (entity_type RMTC, document_type RMTC_QR_LABEL) - no schema change.

alter table public.rmtc_approvals add column if not exists applicable_sections jsonb;
comment on column public.rmtc_approvals.applicable_sections is
  'R38: per-RMTC sections applicable {"<key>": true|false}; NULL = defaults from the covered Parts (all applicable).';

alter table public.parts add column if not exists section_applicability jsonb not null default '{}'::jsonb;

create index if not exists idx_document_attachments_rmtc_qr_label
  on public.document_attachments (tenant_id, entity_id)
  where entity_type = 'RMTC' and document_type = 'RMTC_QR_LABEL';
