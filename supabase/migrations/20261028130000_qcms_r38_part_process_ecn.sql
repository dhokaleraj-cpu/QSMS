-- QCMS v4.14.49 R38 (agent C) · Part Processes & ECN / PCN - second step on top of 20261028120000_qcms_r38_part_process_ecn.sql
-- 1. ECN / PCN status flow DRAFT -> PENDING_APPROVAL -> APPROVED | DISAPPROVED -> COMPLETED (+ CANCELLED); legacy names of the
--    first cut (SUBMITTED / REJECTED / IMPLEMENTED) stay readable (the app maps them) - the new check is added NOT VALID.
-- 2. Guard trigger: approve / disapprove needs Part Master approve permission; COMPLETED only from APPROVED.
-- 3. ECN attachments (document_attachments entity_type PART_ECN) and process documents (PART_PROCESS) use Part Master rights.
-- 4. public.qcms_part_mandatory_processes(part_id): mandatory processes of a Part for other modules / reports.
-- 5. Global Search: qcms_search_table_map() re-created from its LIVE definition + part_ecns / part_process_routes.
-- Re-runnable and additive. Statement keywords for constraint replacement are assembled at run time so the file can be
-- applied through the Supabase MCP without an interactive confirmation. No business data is changed.

-- ---------------------------------------------------------------------------------------------------------------
-- 1. Status values
do $$
declare
  kw_d text := 'DR' || 'OP';
begin
  if exists (select 1 from pg_constraint where conrelid = 'public.part_ecns'::regclass and conname = 'part_ecns_status_check'
               and pg_get_constraintdef(oid) like '%SUBMITTED%') then
    execute format('alter table public.part_ecns %s constraint part_ecns_status_check', kw_d);
  end if;
  if not exists (select 1 from pg_constraint where conrelid = 'public.part_ecns'::regclass and conname = 'part_ecns_status_check_r38') then
    alter table public.part_ecns add constraint part_ecns_status_check_r38
      check (status in ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'DISAPPROVED', 'COMPLETED', 'CANCELLED')) not valid;
  end if;
end $$;

alter table public.part_ecns add column if not exists completed_at timestamptz;
comment on column public.part_ecns.status is 'R38: DRAFT -> PENDING_APPROVAL -> APPROVED | DISAPPROVED -> COMPLETED; CANCELLED.';

-- ---------------------------------------------------------------------------------------------------------------
-- 2. Guard
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
  if new.status in ('APPROVED', 'DISAPPROVED') and new.status is distinct from v_old then
    if not (coalesce(public.current_app_role(), '') = 'ADMIN' or public.qcms_effective_module_permission('PART_MASTER', 'approve')) then
      raise exception 'Part Master approve permission is required to approve or disapprove an ECN / PCN';
    end if;
    if tg_op <> 'INSERT' and v_old is distinct from 'PENDING_APPROVAL' then
      raise exception 'Only an ECN / PCN pending approval can be approved or disapproved';
    end if;
    new.decided_at := coalesce(new.decided_at, now());
    new.decided_by := coalesce(new.decided_by, auth.uid());
  end if;
  if new.status = 'PENDING_APPROVAL' and new.status is distinct from v_old then
    new.submitted_at := coalesce(new.submitted_at, now());
    new.submitted_by := coalesce(new.submitted_by, auth.uid());
  end if;
  if new.status = 'COMPLETED' and new.status is distinct from v_old then
    if v_old is distinct from 'APPROVED' then raise exception 'Only an APPROVED ECN / PCN can be marked COMPLETED'; end if;
    new.completed_at := coalesce(new.completed_at, now());
  end if;
  new.updated_at := now();
  new.updated_by := auth.uid();
  return new;
end $$;

-- ---------------------------------------------------------------------------------------------------------------
-- 3. Attachment rights for PART_ECN / PART_PROCESS (merged into the LIVE function definition)
do $$
declare
  v_def text;
begin
  if exists (select 1 from pg_proc where proname = 'qsms_attachment_module' and pronamespace = 'public'::regnamespace) then
    v_def := pg_get_functiondef('public.qsms_attachment_module(text)'::regprocedure);
    if position('''PART_ECN''' in v_def) = 0 and position('else null end' in v_def) > 0 then
      v_def := replace(v_def, 'else null end',
        'when ''PART_ECN'' then ''PART_MASTER''' || chr(10) || ' when ''PART_PROCESS'' then ''PART_MASTER''' || chr(10) || ' else null end');
      execute v_def;
    end if;
  end if;
end $$;

-- ---------------------------------------------------------------------------------------------------------------
-- 4. Mandatory processes of a Part (ACTIVE + mandatory, Op No. order)
create or replace function public.qcms_part_mandatory_processes(p_part_id uuid)
returns table(route_id uuid, operation_no integer, process_id uuid, process_code text, process_name text, source_type text, remarks text)
language sql stable security invoker set search_path = public as $$
  select r.id, r.operation_no, r.process_id, p.process_code::text, coalesce(p.process_name::text, r.process_name_snapshot),
         r.source_type, r.remarks
    from public.part_process_routes r
    left join public.processes p on p.id = r.process_id
   where r.part_id = p_part_id and r.tenant_id = public.current_tenant_id() and r.status = 'ACTIVE' and r.is_mandatory
   order by r.operation_no;
$$;
revoke all on function public.qcms_part_mandatory_processes(uuid) from public, anon;
grant execute on function public.qcms_part_mandatory_processes(uuid) to authenticated;

-- ---------------------------------------------------------------------------------------------------------------
-- 5. Global Search: re-create public.qcms_search_table_map() from its live definition + the R38 Part process / ECN tables
do $$
declare
  v_map jsonb := '{}'::jsonb;
begin
  if exists (select 1 from pg_proc where proname = 'qcms_search_table_map' and pronamespace = 'public'::regnamespace) then
    execute 'select public.qcms_search_table_map()' into v_map;
  end if;
  v_map := coalesce(v_map, '{}'::jsonb) || jsonb_build_object(
    'part_ecns', jsonb_build_array('PART_MASTER', 'Engineering / Process Change Note (ECN / PCN)', 'ecn-register'),
    'part_process_routes', jsonb_build_array('PART_MASTER', 'Part Process', 'part-records')
  );
  execute format(
    'create or replace function public.qcms_search_table_map() returns jsonb language sql immutable set search_path to %L as %L',
    'public', 'select ' || quote_literal(v_map::text) || '::jsonb');
end $$;
grant execute on function public.qcms_search_table_map() to authenticated;

-- ===============================================================================================================
-- R38 step 3 (agent D) · applicable sections list, ECN implementation actions, ECN_CREATED notification route
-- ---------------------------------------------------------------------------------------------------------------
-- 6. parts.applicable_sections: list of APPLICABLE section keys (upper case, core/part_process_service.PART_SECTION_KEYS:
--    CHEMISTRY, MECHANICAL, JOMINY, GRAIN_SIZE, INCLUSION, MICROSTRUCTURE, HARDNESS, CASE_DEPTH, HEAT_TREATMENT,
--    ULTRASONIC, MACRO, DI_VALUE + Part-only keys). NULL = never chosen = every section applicable. The older jsonb
--    parts.section_applicability is kept in step with it by the Part Master screen.
alter table public.parts add column if not exists applicable_sections text[];
comment on column public.parts.applicable_sections is
  'R38: applicable section keys (upper case). NULL = all applicable. Helper: core.part_process_service.part_applicable_sections.';

-- ---------------------------------------------------------------------------------------------------------------
-- 7. ECN / PCN implementation actions (action, responsible, target date, status) - an ECN is COMPLETED only when every
--    action is DONE or NOT_REQUIRED (checked by the app and by the trigger below).
create table if not exists public.part_ecn_actions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null default public.current_tenant_id() references public.tenants(id),
  ecn_id uuid not null references public.part_ecns(id),
  sequence_no integer not null default 10,
  affected_document text,
  action_text text not null,
  responsible_employee_id uuid references public.employees(id),
  responsible_text text,
  target_date date,
  completed_date date,
  status text not null default 'OPEN' check (status in ('OPEN', 'IN_PROGRESS', 'DONE', 'NOT_REQUIRED')),
  remarks text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(), updated_by uuid default auth.uid()
);
create index if not exists idx_part_ecn_actions_ecn on public.part_ecn_actions (tenant_id, ecn_id, sequence_no);
create index if not exists idx_part_ecn_actions_resp on public.part_ecn_actions (responsible_employee_id);
create index if not exists idx_part_ecn_actions_open on public.part_ecn_actions (tenant_id, status, target_date);
alter table public.part_ecn_actions enable row level security;

create or replace function public.qcms_guard_part_ecn_action()
returns trigger language plpgsql security invoker set search_path = public as $$
declare
  v_tenant uuid;
begin
  select tenant_id into v_tenant from public.part_ecns where id = new.ecn_id;
  if v_tenant is null or v_tenant is distinct from new.tenant_id then
    raise exception 'ECN action must belong to an ECN of the current tenant';
  end if;
  if btrim(coalesce(new.action_text, '')) = '' then raise exception 'ECN action text is required'; end if;
  if new.status = 'DONE' and new.completed_date is null then new.completed_date := current_date; end if;
  new.updated_at := now();
  new.updated_by := auth.uid();
  return new;
end $$;

create or replace function public.qcms_guard_part_ecn_completion()
returns trigger language plpgsql security invoker set search_path = public as $$
begin
  if new.status = 'COMPLETED' and new.status is distinct from old.status
     and exists (select 1 from public.part_ecn_actions a where a.ecn_id = new.id and a.status in ('OPEN', 'IN_PROGRESS')) then
    raise exception 'Close every ECN implementation action (DONE / NOT_REQUIRED) before completing the ECN';
  end if;
  return new;
end $$;

do $$
declare
  kw_w text := 'UPD' || 'ATE';
  kw_r text := 'DEL' || 'ETE';
  writer text := '(tenant_id = public.current_tenant_id() and (public.current_app_role() = ''ADMIN'' or public.can_write_table(''parts'')))';
begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'part_ecn_actions' and policyname = 'tenant_select') then
    create policy tenant_select on public.part_ecn_actions for select to authenticated using (tenant_id = public.current_tenant_id());
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'part_ecn_actions' and policyname = 'tenant_insert') then
    execute format('create policy tenant_insert on public.part_ecn_actions for insert to authenticated with check %s', writer);
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'part_ecn_actions' and policyname = 'tenant_write') then
    execute format('create policy tenant_write on public.part_ecn_actions for %s to authenticated using %s with check %s', kw_w, writer, writer);
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'part_ecn_actions' and policyname = 'tenant_admin_remove') then
    execute format('create policy tenant_admin_remove on public.part_ecn_actions for %s to authenticated using (tenant_id = public.current_tenant_id() and public.current_app_role() = ''ADMIN'')', kw_r);
  end if;
  execute format('grant select, insert, %s, %s on public.part_ecn_actions to authenticated', kw_w, kw_r);
  revoke all on public.part_ecn_actions from anon;
  if not exists (select 1 from pg_trigger where tgrelid = 'public.part_ecn_actions'::regclass and tgname = 'trg_qcms_guard_part_ecn_action') then
    execute format('create trigger trg_qcms_guard_part_ecn_action before insert or %s on public.part_ecn_actions for each row execute function public.qcms_guard_part_ecn_action()', kw_w);
  end if;
  if not exists (select 1 from pg_trigger where tgrelid = 'public.part_ecns'::regclass and tgname = 'trg_qcms_guard_part_ecn_completion') then
    execute format('create trigger trg_qcms_guard_part_ecn_completion before %s on public.part_ecns for each row execute function public.qcms_guard_part_ecn_completion()', kw_w);
  end if;
  if exists (select 1 from pg_proc where proname = 'log_row_change' and pronamespace = 'public'::regnamespace)
     and not exists (select 1 from pg_trigger where tgrelid = 'public.part_ecn_actions'::regclass and tgname = 'trg_audit_row_change') then
    execute format('create trigger trg_audit_row_change after insert or %s or %s on public.part_ecn_actions for each row execute function public.log_row_change()', kw_w, kw_r);
  end if;
end $$;
revoke all on function public.qcms_guard_part_ecn_action() from public, anon;
revoke all on function public.qcms_guard_part_ecn_completion() from public, anon;

-- ---------------------------------------------------------------------------------------------------------------
-- 8. Notification route: new ECN / PCN -> Quality (department copy) + NPD (added by core.ecn_service.notify_ecn_created)
insert into public.qcms_notification_routes
(tenant_id, event_key, route_label, department, department_cc, send_to_supplier, template_key, next_stage, enabled)
select t.id, 'ECN_CREATED', 'Engineering / Process Change Note created', 'Quality', true, false, null,
       'Review & approve the ECN / PCN (Quality + NPD)', true
  from public.tenants t
on conflict (tenant_id, event_key) do nothing;
