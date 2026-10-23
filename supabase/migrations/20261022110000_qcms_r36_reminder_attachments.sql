-- QCMS v4.14.49 R36 · Reminder e-mail attachments.
-- Latest print-layout PDF per record ("document snapshot") so scheduled reminder e-mails sent by the
-- Deno edge functions can attach the same Purchase Order / MetLAB / Dimensional / RMTC / Complaint PDF
-- that the website prints (the PDFs are rendered in Python by the website and stored here).
-- Safe to re-run: create table if not exists / create index if not exists / guarded policies /
-- create or replace function. No destructive statements.

-- ---------------------------------------------------------------------------------------------
-- 1. Snapshot register (one current PDF per tenant + record + document kind)
-- ---------------------------------------------------------------------------------------------
create table if not exists public.qcms_document_snapshots (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id(),
  source_table text not null,
  record_id uuid not null,
  doc_kind text not null default 'PDF',
  bucket text not null default 'quality-documents',
  object_path text not null,
  file_name text not null,
  mime_type text not null default 'application/pdf',
  size_bytes bigint,
  record_updated_at timestamptz,
  generated_at timestamptz not null default now(),
  generated_by uuid default auth.uid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint qcms_document_snapshots_unique unique (tenant_id, source_table, record_id, doc_kind)
);
create index if not exists qcms_document_snapshots_record_idx on public.qcms_document_snapshots (tenant_id, record_id);
create index if not exists qcms_document_snapshots_generated_idx on public.qcms_document_snapshots (tenant_id, generated_at desc);
alter table public.qcms_document_snapshots enable row level security;

do $$
begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'qcms_document_snapshots' and policyname = 'qcms_document_snapshots_read') then
    create policy qcms_document_snapshots_read on public.qcms_document_snapshots for select to authenticated
      using (tenant_id = public.current_tenant_id());
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'qcms_document_snapshots' and policyname = 'qcms_document_snapshots_insert') then
    create policy qcms_document_snapshots_insert on public.qcms_document_snapshots for insert to authenticated
      with check (tenant_id = public.current_tenant_id());
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'qcms_document_snapshots' and policyname = 'qcms_document_snapshots_update') then
    create policy qcms_document_snapshots_update on public.qcms_document_snapshots for update to authenticated
      using (tenant_id = public.current_tenant_id())
      with check (tenant_id = public.current_tenant_id());
  end if;
end $$;

grant select, insert, update on public.qcms_document_snapshots to authenticated;
revoke all on public.qcms_document_snapshots from anon;

-- ---------------------------------------------------------------------------------------------
-- 2. Records referenced by currently pending reminders whose snapshot is missing or outdated.
--    security invoker: the caller's RLS decides which records are visible.
-- ---------------------------------------------------------------------------------------------
create or replace function public.qcms_reminder_snapshot_targets(p_limit integer default 20)
returns table (source_table text, record_id uuid, record_updated_at timestamptz)
language sql stable security invoker set search_path = public as $$
  with po_changed as (
    select po.id,
           greatest(po.updated_at, coalesce((select max(i.updated_at) from public.supply_purchase_order_items i where i.purchase_order_id = po.id), po.updated_at)) as changed_at
    from public.supply_purchase_orders po
    where po.tenant_id = public.current_tenant_id()
      and upper(coalesce(po.status, '')) <> 'CANCELLED'
  ),
  po_targets as (
    -- 1) POs waiting for supplier confirmation (daily supplier reminder)
    select 'supply_purchase_orders'::text as source_table, c.purchase_order_id as record_id, 1 as priority
    from public.supply_po_confirmations c
    where c.tenant_id = public.current_tenant_id()
      and upper(coalesce(c.confirmation_status, '')) in ('PENDING', 'REVISION_REQUESTED')
      and c.purchase_order_id is not null
    union
    -- 2) POs pending approval (approver overdue reminder)
    select 'supply_purchase_orders', po.id, 1
    from public.supply_purchase_orders po
    where po.tenant_id = public.current_tenant_id()
      and upper(coalesce(po.approval_status, '')) = 'PENDING_APPROVAL'
    union
    -- 3) open Raw Material POs linked to a Purchase Order
    select 'supply_purchase_orders', rm.purchase_order_id, 2
    from public.supply_rm_purchase_orders rm
    where rm.tenant_id = public.current_tenant_id()
      and rm.purchase_order_id is not null
      and upper(coalesce(rm.status, '')) not in ('COMPLETED', 'CLOSED', 'CANCELLED')
    union
    -- 4) open Forging orders linked to a Purchase Order
    select 'supply_purchase_orders', fo.purchase_order_id, 2
    from public.supply_forging_orders fo
    where fo.tenant_id = public.current_tenant_id()
      and fo.purchase_order_id is not null
      and upper(coalesce(fo.status, '')) not in ('COMPLETED', 'CLOSED', 'CANCELLED')
  ),
  po_ranked as (
    select t.source_table, t.record_id, min(t.priority) as priority, pc.changed_at
    from po_targets t join po_changed pc on pc.id = t.record_id
    group by t.source_table, t.record_id, pc.changed_at
  ),
  doc_targets as (
    select 'rmtc_approvals'::text as source_table, r.id as record_id, 3 as priority, r.updated_at as changed_at
    from public.rmtc_approvals r
    where r.tenant_id = public.current_tenant_id()
      and upper(coalesce(r.status, '')) not in ('APPROVED', 'REJECTED', 'CANCELLED')
    union all
    select 'lab_tests', l.id, 4, l.updated_at
    from public.lab_tests l
    where l.tenant_id = public.current_tenant_id()
      and upper(coalesce(l.status, '')) = 'DRAFT'
      and l.updated_at > now() - interval '90 days'
    union all
    select 'inspection_reports', ir.id, 4, ir.updated_at
    from public.inspection_reports ir
    where ir.tenant_id = public.current_tenant_id()
      and upper(coalesce(ir.status, '')) = 'DRAFT'
      and ir.updated_at > now() - interval '90 days'
    union all
    select 'quality_complaints', qc.id, 3, qc.updated_at
    from public.quality_complaints qc
    where qc.tenant_id = public.current_tenant_id()
      and upper(coalesce(qc.status, '')) not in ('CLOSED', 'CANCELLED')
  ),
  all_targets as (
    select source_table, record_id, priority, changed_at from po_ranked
    union all
    select source_table, record_id, priority, changed_at from doc_targets
  )
  select a.source_table, a.record_id, a.changed_at as record_updated_at
  from all_targets a
  left join public.qcms_document_snapshots s
    on s.tenant_id = public.current_tenant_id()
   and s.source_table = a.source_table
   and s.record_id = a.record_id
   and s.doc_kind = 'PDF_SAFE'  -- R36b: customer-free snapshots only
  where s.id is null
     or s.record_updated_at is null
     or (a.changed_at is not null and s.record_updated_at < a.changed_at)
  order by a.priority, a.changed_at desc nulls last
  limit greatest(1, least(coalesce(p_limit, 20), 200));
$$;

revoke all on function public.qcms_reminder_snapshot_targets(integer) from public, anon;
grant execute on function public.qcms_reminder_snapshot_targets(integer) to authenticated;

comment on table public.qcms_document_snapshots is 'R36: latest print-layout PDF per record, attached to scheduled reminder e-mails by the edge functions.';
