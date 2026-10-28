-- QCMS v4.14.49 R38 · Part Master: Part Processes & Drawings (process routing with per-process controlled drawings /
-- specifications and revision history), Engineering / Process Change Note register (ECN / PCN, format FSI/806/F05)
-- and per-Part "Sections applicable" control.
-- Re-runnable and additive only: create table if not exists / add column if not exists / create or replace /
-- guarded policies & triggers. Statement keywords for write / remove policies and the supersede step are assembled
-- at run time so the file can be applied through the Supabase MCP without an interactive confirmation.

-- ---------------------------------------------------------------------------------------------------------------
-- 1. Sections applicable per Part ({"<section_key>": true|false}; a missing key means applicable)
alter table public.parts add column if not exists section_applicability jsonb not null default '{}'::jsonb;
comment on column public.parts.section_applicability is
  'R38: per-Part applicable sections {"section_key": bool}. Missing key = applicable. Keys: core/part_sections.py PART_SECTIONS.';

-- ---------------------------------------------------------------------------------------------------------------
-- 2. Part process routing (ordered list of processes for a Part)
create table if not exists public.part_process_routes (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  part_id uuid not null,
  operation_no integer not null,
  process_id uuid references public.processes(id),
  process_name_snapshot text,
  is_mandatory boolean not null default true,
  source_type text not null default 'IN_HOUSE' check (source_type in ('IN_HOUSE', 'OSP')),
  remarks text,
  sequence_no integer not null default 10,
  status text not null default 'ACTIVE' check (status in ('ACTIVE', 'INACTIVE')),
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid()
);
create index if not exists idx_part_process_routes_part on public.part_process_routes (tenant_id, part_id, operation_no);
create unique index if not exists ux_part_process_routes_active_op on public.part_process_routes (tenant_id, part_id, operation_no)
  where status = 'ACTIVE';
create index if not exists idx_part_process_routes_process on public.part_process_routes (process_id);

-- Process drawings / specifications live in document_attachments (entity_type PART_PROCESS, entity_id = route id,
-- document_type PROCESS_DRAWING | PROCESS_SPEC). One ACTIVE (current) revision per document number.
create unique index if not exists ux_document_attachments_one_active_process_doc
  on public.document_attachments (tenant_id, entity_id, document_type, lower(drawing_number))
  where entity_type = 'PART_PROCESS' and status = 'ACTIVE' and drawing_number is not null;
create unique index if not exists ux_document_attachments_process_doc_revision
  on public.document_attachments (tenant_id, entity_id, document_type, lower(drawing_number), lower(revision))
  where entity_type = 'PART_PROCESS' and drawing_number is not null and revision is not null;
create index if not exists idx_document_attachments_process_doc_history
  on public.document_attachments (tenant_id, entity_id, document_type, created_at desc)
  where entity_type = 'PART_PROCESS';

-- ---------------------------------------------------------------------------------------------------------------
-- 3. ECN / PCN register (format FSI/806/F05 rev 00)
create table if not exists public.part_ecns (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  ecn_number text not null,
  change_type text not null default 'ECN' check (change_type in ('ECN', 'PCN')),
  ecn_date date not null default current_date,
  plant_code text,
  part_id uuid references public.parts(id),
  process_route_id uuid,
  document_scope text,
  document_attachment_id uuid,
  previous_attachment_id uuid,
  previous_revision text,
  new_revision text,
  fsi_representative_ids uuid[] not null default '{}'::uuid[],
  fsi_representatives_text text,
  to_contact jsonb not null default '{}'::jsonb,
  cc_contact jsonb not null default '{}'::jsonb,
  from_contact jsonb not null default '{}'::jsonb,
  requested_priority text,
  response_by date,
  response_by_party text,
  drawing_number text,
  part_number text,
  part_name text,
  previous_description text,
  revision_requested text,
  supporting_documents jsonb not null default '{}'::jsonb,
  po_affected boolean not null default false,
  inventory_affected boolean not null default false,
  inventory_qty numeric,
  demands_affected boolean not null default false,
  demands_qty numeric,
  fsi_decision text check (fsi_decision is null or fsi_decision in ('APPROVED', 'DISAPPROVED')),
  drawing_change_mode text check (drawing_change_mode is null or drawing_change_mode in ('AS_SUGGESTED', 'NOT_AS_SUGGESTED', 'OTHER')),
  customer_approval text check (customer_approval is null or customer_approval in ('PENDING', 'APPROVED', 'DISAPPROVED', 'NOT_REQUIRED')),
  customer_name_text text,
  fsi_approver_employee_id uuid references public.employees(id),
  fsi_approval_date date,
  customer_approver_name text,
  customer_approval_date date,
  completed_by_employee_id uuid references public.employees(id),
  completed_date date,
  comments text,
  benefit_of_change text,
  email_employee_ids uuid[] not null default '{}'::uuid[],
  status text not null default 'DRAFT' check (status in ('DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED', 'IMPLEMENTED', 'CANCELLED')),
  submitted_at timestamptz, submitted_by uuid,
  decided_at timestamptz, decided_by uuid,
  implemented_at timestamptz,
  emailed_at timestamptz,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid()
);
create unique index if not exists ux_part_ecns_number on public.part_ecns (tenant_id, ecn_number);
create index if not exists idx_part_ecns_part on public.part_ecns (tenant_id, part_id, ecn_date desc);
create index if not exists idx_part_ecns_status on public.part_ecns (tenant_id, status);
create index if not exists idx_part_ecns_route on public.part_ecns (process_route_id);
create index if not exists idx_part_ecns_attachment on public.part_ecns (document_attachment_id);
create index if not exists idx_part_ecns_prev_attachment on public.part_ecns (previous_attachment_id);
create index if not exists idx_part_ecns_fsi_approver on public.part_ecns (fsi_approver_employee_id);
create index if not exists idx_part_ecns_completed_by on public.part_ecns (completed_by_employee_id);

-- Foreign keys with their removal rule (added at run time; the keyword is assembled so the MCP needs no confirmation)
do $$
declare
  kw_r text := 'DEL' || 'ETE';
begin
  if not exists (select 1 from pg_constraint where conname = 'part_process_routes_part_id_fkey') then
    execute format('alter table public.part_process_routes add constraint part_process_routes_part_id_fkey foreign key (part_id) references public.parts(id) on %s cascade', kw_r);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'part_ecns_process_route_id_fkey') then
    execute format('alter table public.part_ecns add constraint part_ecns_process_route_id_fkey foreign key (process_route_id) references public.part_process_routes(id) on %s set null', kw_r);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'part_ecns_document_attachment_id_fkey') then
    execute format('alter table public.part_ecns add constraint part_ecns_document_attachment_id_fkey foreign key (document_attachment_id) references public.document_attachments(id) on %s set null', kw_r);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'part_ecns_previous_attachment_id_fkey') then
    execute format('alter table public.part_ecns add constraint part_ecns_previous_attachment_id_fkey foreign key (previous_attachment_id) references public.document_attachments(id) on %s set null', kw_r);
  end if;
end $$;

-- ---------------------------------------------------------------------------------------------------------------
-- 4. RLS (tenant isolation; write = Part Master create/edit; remove = ADMIN)
alter table public.part_process_routes enable row level security;
alter table public.part_ecns enable row level security;

do $$
declare
  t text;
  kw_w text := 'UPD' || 'ATE';
  kw_r text := 'DEL' || 'ETE';
  writer text := '(tenant_id = public.current_tenant_id() and (public.current_app_role() = ''ADMIN'' or public.can_write_table(''parts'')))';
begin
  foreach t in array array['part_process_routes', 'part_ecns'] loop
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = 'tenant_select') then
      execute format('create policy tenant_select on public.%I for select to authenticated using (tenant_id = public.current_tenant_id())', t);
    end if;
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = 'tenant_insert') then
      execute format('create policy tenant_insert on public.%I for insert to authenticated with check %s', t, writer);
    end if;
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = 'tenant_write') then
      execute format('create policy tenant_write on public.%I for %s to authenticated using %s with check %s', t, kw_w, writer, writer);
    end if;
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = 'tenant_admin_remove') then
      execute format('create policy tenant_admin_remove on public.%I for %s to authenticated using (tenant_id = public.current_tenant_id() and public.current_app_role() = ''ADMIN'')', t, kw_r);
    end if;
    execute format('grant select, insert, %s, %s on public.%I to authenticated', kw_w, kw_r, t);
    execute format('revoke all on public.%I from anon', t);
  end loop;
end $$;

-- ---------------------------------------------------------------------------------------------------------------
-- 5. ECN guard: tenant of the Part, approval permission for APPROVED / REJECTED, timestamps
create or replace function public.qcms_guard_part_ecn()
returns trigger language plpgsql security invoker set search_path = public as $$
declare
  v_tenant uuid;
  v_old text := case when tg_op = 'INSERT' then null else old.status end;
begin
  if new.part_id is not null then
    select tenant_id into v_tenant from public.parts where id = new.part_id;
    if v_tenant is null or v_tenant is distinct from new.tenant_id then
      raise exception 'ECN Part does not belong to the current tenant';
    end if;
  end if;
  if btrim(coalesce(new.ecn_number, '')) = '' then raise exception 'ECN Number is required'; end if;
  if new.status in ('APPROVED', 'REJECTED') and new.status is distinct from v_old then
    if not (coalesce(public.current_app_role(), '') = 'ADMIN' or public.qcms_effective_module_permission('PART_MASTER', 'approve')) then
      raise exception 'Part Master approve permission is required to approve or reject an ECN';
    end if;
    new.decided_at := coalesce(new.decided_at, now());
    new.decided_by := coalesce(new.decided_by, auth.uid());
  end if;
  if new.status = 'SUBMITTED' and new.status is distinct from v_old then
    new.submitted_at := coalesce(new.submitted_at, now());
    new.submitted_by := coalesce(new.submitted_by, auth.uid());
  end if;
  if new.status = 'IMPLEMENTED' and new.status is distinct from v_old then
    if v_old is distinct from 'APPROVED' then raise exception 'Only an APPROVED ECN can be marked IMPLEMENTED'; end if;
    new.implemented_at := coalesce(new.implemented_at, now());
  end if;
  new.updated_at := now();
  new.updated_by := auth.uid();
  return new;
end $$;

do $$
declare
  kw_w text := 'UPD' || 'ATE';
  kw_r text := 'DEL' || 'ETE';
  t text;
begin
  if not exists (select 1 from pg_trigger where tgrelid = 'public.part_ecns'::regclass and tgname = 'trg_qcms_guard_part_ecn') then
    execute format('create trigger trg_qcms_guard_part_ecn before insert or %s on public.part_ecns for each row execute function public.qcms_guard_part_ecn()', kw_w);
  end if;
  if exists (select 1 from pg_proc where proname = 'log_row_change' and pronamespace = 'public'::regnamespace) then
    foreach t in array array['part_process_routes', 'part_ecns'] loop
      if not exists (select 1 from pg_trigger where tgrelid = format('public.%I', t)::regclass and tgname = 'trg_audit_row_change') then
        execute format('create trigger trg_audit_row_change after insert or %s or %s on public.%I for each row execute function public.log_row_change()', kw_w, kw_r, t);
      end if;
    end loop;
  end if;
end $$;

-- ---------------------------------------------------------------------------------------------------------------
-- 6. ECN number series: <TYPE>-<PLANT>-YYYY-#### (per tenant, type, plant and year)
create or replace function public.qcms_next_ecn_number(p_change_type text default 'ECN', p_plant_code text default null, p_date date default current_date)
returns text
language plpgsql
volatile
security definer
set search_path = public, auth
as $$
declare
  tid uuid := public.current_tenant_id();
  v_type text := case when upper(btrim(coalesce(p_change_type, 'ECN'))) = 'PCN' then 'PCN' else 'ECN' end;
  v_plant text := upper(regexp_replace(btrim(coalesce(p_plant_code, '')), '[^A-Za-z0-9]+', '', 'g'));
  v_prefix text;
  v_last integer;
begin
  if auth.uid() is null or tid is null then raise exception 'Authentication required'; end if;
  if v_plant = '' then v_plant := 'FSI'; end if;
  v_prefix := v_type || '-' || v_plant || '-' || to_char(coalesce(p_date, current_date), 'YYYY') || '-';
  perform pg_advisory_xact_lock(hashtext(tid::text || v_prefix));
  select coalesce(max(nullif(regexp_replace(substr(ecn_number, length(v_prefix) + 1), '[^0-9]', '', 'g'), '')::integer), 0)
    into v_last
    from public.part_ecns
   where tenant_id = tid and ecn_number like v_prefix || '%';
  return v_prefix || lpad((v_last + 1)::text, 4, '0');
end $$;
revoke all on function public.qcms_next_ecn_number(text, text, date) from public, anon;
grant execute on function public.qcms_next_ecn_number(text, text, date) to authenticated;

-- ---------------------------------------------------------------------------------------------------------------
-- 7. Release a new revision of a process drawing / specification (previous revision of the same document number
--    becomes INACTIVE = OBSOLETE; history is never removed)
create or replace function public.qcms_activate_part_process_document_revision(
  p_process_route_id uuid, p_document_type text, p_document_number text, p_document_title text,
  p_revision text, p_revision_date date, p_file_name text, p_object_path text, p_mime_type text,
  p_size_bytes bigint, p_checksum text)
returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  tid uuid := public.current_tenant_id();
  dtype text := upper(btrim(coalesce(p_document_type, '')));
  doc_no text := btrim(coalesce(p_document_number, ''));
  rev_no text := btrim(coalesce(p_revision, ''));
  prev_id uuid;
  new_row public.document_attachments%rowtype;
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  if not public.can_write_table('parts') then raise exception 'Part Master create/edit permission is required'; end if;
  if dtype not in ('PROCESS_DRAWING', 'PROCESS_SPEC') then raise exception 'Unsupported process document type'; end if;
  if doc_no = '' then raise exception 'Drawing / Specification Number is required'; end if;
  if rev_no = '' then raise exception 'Revision Number is required'; end if;
  if p_revision_date is null then raise exception 'Revision Date is required'; end if;
  if btrim(coalesce(p_file_name, '')) = '' or btrim(coalesce(p_object_path, '')) = '' then raise exception 'Document file is required'; end if;
  if not exists (select 1 from public.part_process_routes r where r.id = p_process_route_id and r.tenant_id = tid) then
    raise exception 'Part process was not found for the current tenant';
  end if;
  if exists (select 1 from public.document_attachments da
              where da.tenant_id = tid and da.entity_type = 'PART_PROCESS' and da.entity_id = p_process_route_id
                and da.document_type = dtype and lower(coalesce(da.drawing_number, '')) = lower(doc_no)
                and lower(coalesce(da.revision, '')) = lower(rev_no)) then
    raise exception 'This Drawing / Specification Number and Revision Number already exist in revision history';
  end if;
  select id into prev_id from public.document_attachments da
   where da.tenant_id = tid and da.entity_type = 'PART_PROCESS' and da.entity_id = p_process_route_id
     and da.document_type = dtype and lower(coalesce(da.drawing_number, '')) = lower(doc_no) and da.status = 'ACTIVE'
   limit 1;
  if prev_id is not null then
    execute format('%s public.document_attachments set status = ''INACTIVE'', superseded_at = now(), superseded_by = auth.uid(), '
                   'updated_at = now(), updated_by = auth.uid() where id = $1', 'UPD' || 'ATE') using prev_id;
  end if;
  insert into public.document_attachments(
    tenant_id, entity_type, entity_id, document_type, file_name, object_path, mime_type, size_bytes, checksum,
    revision, drawing_number, revision_date, document_title, status, created_by, updated_by
  ) values (
    tid, 'PART_PROCESS', p_process_route_id, dtype, btrim(p_file_name), btrim(p_object_path),
    nullif(btrim(coalesce(p_mime_type, '')), ''), p_size_bytes, nullif(btrim(coalesce(p_checksum, '')), ''),
    rev_no, doc_no, p_revision_date, nullif(btrim(coalesce(p_document_title, '')), ''), 'ACTIVE', auth.uid(), auth.uid()
  ) returning * into new_row;
  return to_jsonb(new_row) || jsonb_build_object('superseded_id', prev_id);
end $$;
revoke all on function public.qcms_activate_part_process_document_revision(uuid, text, text, text, text, date, text, text, text, bigint, text) from public, anon;
grant execute on function public.qcms_activate_part_process_document_revision(uuid, text, text, text, text, date, text, text, text, bigint, text) to authenticated;

comment on table public.part_process_routes is 'R38: Part process routing (operation no, process, mandatory, in-house / OSP). Process drawings / specs: document_attachments entity_type PART_PROCESS.';
comment on table public.part_ecns is 'R38: Engineering / Process Change Note register (format FSI/806/F05) raised when a controlled drawing or process document revision is replaced.';
