-- QCMS v4.14.18 / 3 of 3 — comprehensive audit/activity, MetLAB/Dimensional RLS, release marker.
-- Additive/backward-compatible. No transactional/business rows are reset.

begin;

-- -----------------------------------------------------------------------------
-- 8) Comprehensive audit: record CREATE/UPDATE/DELETE with actor fallback to
--    created_by/updated_by when server-side service operations are used.
-- -----------------------------------------------------------------------------
create or replace function public.log_row_change()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  payload jsonb;
  prior jsonb;
  tid uuid;
  rid uuid;
  actor uuid;
begin
  if tg_op='DELETE' then payload:=to_jsonb(old); prior:=to_jsonb(old);
  elsif tg_op='INSERT' then payload:=to_jsonb(new); prior:=null;
  else payload:=to_jsonb(new); prior:=to_jsonb(old); end if;

  begin tid:=nullif(payload->>'tenant_id','')::uuid; exception when others then tid:=public.current_tenant_id(); end;
  begin rid:=nullif(payload->>'id','')::uuid; exception when others then rid:=null; end;
  actor:=auth.uid();
  if actor is null then
    begin actor:=nullif(payload->>'updated_by','')::uuid; exception when others then actor:=null; end;
  end if;
  if actor is null then
    begin actor:=nullif(payload->>'created_by','')::uuid; exception when others then actor:=null; end;
  end if;
  if actor is null and prior is not null then
    begin actor:=nullif(prior->>'updated_by','')::uuid; exception when others then actor:=null; end;
  end if;

  insert into public.audit_log(tenant_id,table_name,row_id,operation,old_data,new_data,changed_by)
  values(tid,tg_table_name,rid,tg_op,prior,case when tg_op='DELETE' then null else payload end,actor);
  if tg_op='DELETE' then return old; else return new; end if;
end $$;

-- Normalize all historical audit trigger names first so each table produces exactly
-- one audit row per mutation, then add the canonical trigger to every tenant-scoped
-- base table with a UUID id.
do $$
declare t record;
begin
  for t in
    select n.nspname as schema_name,c.relname as table_name,tr.tgname as trigger_name
    from pg_trigger tr
    join pg_class c on c.oid=tr.tgrelid
    join pg_namespace n on n.oid=c.relnamespace
    join pg_proc p on p.oid=tr.tgfoid
    where not tr.tgisinternal and n.nspname='public' and p.proname='log_row_change'
  loop
    execute format('drop trigger if exists %I on %I.%I',t.trigger_name,t.schema_name,t.table_name);
  end loop;

  for t in
    select c.table_name
    from information_schema.columns c
    join information_schema.columns i
      on i.table_schema=c.table_schema and i.table_name=c.table_name and i.column_name='id' and i.data_type='uuid'
    join information_schema.tables tb
      on tb.table_schema=c.table_schema and tb.table_name=c.table_name and tb.table_type='BASE TABLE'
    where c.table_schema='public' and c.column_name='tenant_id'
      and c.table_name not in ('audit_log','qcms_user_activity_log')
    group by c.table_name
  loop
    execute format('create trigger trg_audit_row_change after insert or update or delete on public.%I for each row execute function public.log_row_change()',t.table_name);
  end loop;
end $$;

-- -----------------------------------------------------------------------------
-- 9) User activity log: page/section navigation and application actions.
-- -----------------------------------------------------------------------------
create table if not exists public.qcms_user_activity_log (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  profile_id uuid references public.profiles(id) on delete set null,
  employee_id uuid references public.employees(id) on delete set null,
  user_email_snapshot text,
  role_snapshot text,
  department_snapshot text,
  module_key text,
  section_key text,
  action text not null,
  table_name text,
  row_id text,
  details jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now()
);
create index if not exists idx_qcms_activity_tenant_time on public.qcms_user_activity_log(tenant_id,occurred_at desc);
create index if not exists idx_qcms_activity_profile_time on public.qcms_user_activity_log(profile_id,occurred_at desc);
create index if not exists idx_qcms_activity_record on public.qcms_user_activity_log(tenant_id,table_name,row_id,occurred_at desc);
alter table public.qcms_user_activity_log enable row level security;
drop policy if exists qcms_activity_admin_select on public.qcms_user_activity_log;
create policy qcms_activity_admin_select on public.qcms_user_activity_log
for select to authenticated
using (tenant_id=public.current_tenant_id() and public.current_app_role() in ('ADMIN','MANAGEMENT','QUALITY_MANAGER'));

create or replace function public.qcms_log_user_activity(
  p_action text,
  p_module_key text default null,
  p_section_key text default null,
  p_table_name text default null,
  p_row_id text default null,
  p_details jsonb default '{}'::jsonb
)
returns uuid
language plpgsql security definer set search_path='public','auth' as $$
declare
  tid uuid:=public.current_tenant_id();
  pid uuid:=auth.uid();
  emp public.employees%rowtype;
  prof public.profiles%rowtype;
  activity_id uuid;
begin
  if pid is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if nullif(btrim(coalesce(p_action,'')),'') is null then raise exception 'Activity action is required'; end if;
  select * into prof from public.profiles where id=pid and tenant_id=tid;
  select * into emp from public.employees where tenant_id=tid and profile_id=pid order by updated_at desc limit 1;
  insert into public.qcms_user_activity_log(
    tenant_id,profile_id,employee_id,user_email_snapshot,role_snapshot,department_snapshot,
    module_key,section_key,action,table_name,row_id,details
  ) values (
    tid,pid,emp.id,prof.email,prof.role,emp.department,
    nullif(upper(btrim(coalesce(p_module_key,''))),''),nullif(upper(btrim(coalesce(p_section_key,''))),''),
    upper(btrim(p_action)),nullif(btrim(coalesce(p_table_name,'')),''),nullif(btrim(coalesce(p_row_id,'')),''),coalesce(p_details,'{}'::jsonb)
  ) returning id into activity_id;
  return activity_id;
end $$;
revoke all on function public.qcms_log_user_activity(text,text,text,text,text,jsonb) from public,anon;
grant execute on function public.qcms_log_user_activity(text,text,text,text,text,jsonb) to authenticated;

-- -----------------------------------------------------------------------------
-- 10) MetLAB / Dimensional RLS permission synchronization and attachment rights.
--     Fixes the reported 403 "new row violates row-level security policy" when
--     a user has Create/Edit permission in Users & Access.
-- -----------------------------------------------------------------------------
create or replace function public.qsms_can_manage_attachment(p_entity_type text,p_action text default 'EDIT')
returns boolean
language plpgsql stable security definer set search_path='public','auth' as $$
declare
  module_name text:=public.qsms_attachment_module(p_entity_type);
  action_name text:=lower(btrim(coalesce(p_action,'edit')));
begin
  if auth.uid() is null or public.current_tenant_id() is null or module_name is null then return false; end if;
  if action_name='archive' then return public.qcms_effective_module_permission(module_name,'archive'); end if;
  if action_name='create' then return public.qcms_effective_module_permission(module_name,'create'); end if;
  return public.qcms_effective_module_permission(module_name,'edit');
end $$;
revoke all on function public.qsms_can_manage_attachment(text,text) from public,anon;
grant execute on function public.qsms_can_manage_attachment(text,text) to authenticated;

alter table public.lab_tests enable row level security;
drop policy if exists tenant_insert on public.lab_tests;
create policy tenant_insert on public.lab_tests
for insert to authenticated
with check (tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('METLAB_REPORT','create'));
drop policy if exists tenant_update on public.lab_tests;
create policy tenant_update on public.lab_tests
for update to authenticated
using (tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('METLAB_REPORT','edit'))
with check (tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('METLAB_REPORT','edit'));

alter table public.inspection_reports enable row level security;
drop policy if exists tenant_insert on public.inspection_reports;
create policy tenant_insert on public.inspection_reports
for insert to authenticated
with check (tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('DIMENSIONAL_REPORT','create'));
drop policy if exists tenant_update on public.inspection_reports;
create policy tenant_update on public.inspection_reports
for update to authenticated
using (tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('DIMENSIONAL_REPORT','edit'))
with check (tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission('DIMENSIONAL_REPORT','edit'));

-- Re-assert attachment policies so uploaded MetLAB / Dimensional evidence uses
-- the permission of the owning module, not unrelated Part Master rights.
drop policy if exists tenant_insert on public.document_attachments;
create policy tenant_insert on public.document_attachments
for insert to authenticated
with check (tenant_id=public.current_tenant_id() and public.qsms_can_manage_attachment(entity_type,'CREATE'));
drop policy if exists tenant_update on public.document_attachments;
create policy tenant_update on public.document_attachments
for update to authenticated
using (tenant_id=public.current_tenant_id() and public.qsms_can_manage_attachment(entity_type,'EDIT'))
with check (tenant_id=public.current_tenant_id() and public.qsms_can_manage_attachment(entity_type,'EDIT'));

-- -----------------------------------------------------------------------------
-- 12) OSP transaction delete permission remains explicit and password-protected
--     in the application. The server-side delete RPC recognizes OSP as its own
--     module and therefore honors the user's Delete/Archive permission.
-- -----------------------------------------------------------------------------
-- Mapping is already defined above; keep this assertion inside the migration so
-- deployment verification can prove the requested OSP delete contract.
do $$
begin
  if public.qsms_module_for_table('osp_jobs')<>'OSP_TRANSACTIONS' then
    raise exception 'OSP delete permission mapping is not active';
  end if;
  if public.qsms_module_for_table('lab_tests')<>'METLAB_REPORT' then
    raise exception 'MetLAB RLS permission mapping is not active';
  end if;
end $$;

-- -----------------------------------------------------------------------------
-- 13) Release marker for one-file automatic migration verification.
-- -----------------------------------------------------------------------------
create or replace function public.qcms_release_schema_version()
returns text language sql immutable security invoker set search_path='pg_catalog'
as $$ select '4.14.18'::text $$;
revoke all on function public.qcms_release_schema_version() from public;
grant execute on function public.qcms_release_schema_version() to anon,authenticated;

insert into public.qcms_release_schema_state(version,build,applied_at,details)
values ('4.14.18','41418-PERMISSIONS-AUDIT-EMPLOYEE-OSP-RMTC-METLAB-RLS-PDF',now(),
        jsonb_build_object(
          'permission_precedence','ADMIN -> USER -> ROLE -> DEPARTMENT -> LEGACY',
          'po_supply_mapping_fixed',true,
          'section_create_view_edit',true,
          'employee_link_recovery','unique exact email only',
          'employee_email_recovery','earliest audited email must match linked profile',
          'comprehensive_record_audit',true,
          'user_activity_log',true,
          'data_reset',false
        ))
on conflict(version) do update set build=excluded.build,applied_at=excluded.applied_at,details=excluded.details;

commit;
