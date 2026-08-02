-- QSMS focused release 4.3.0
-- Learned master values, module-level user permissions, generated employee/heat codes,
-- material grade number and RMTC calculated Jominy/DI snapshots.

begin;

alter table public.material_grades
  add column if not exists material_number text;

create table if not exists public.master_value_catalog (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  field_key text not null,
  value_text text not null,
  normalized_value text generated always as (lower(btrim(value_text))) stored,
  usage_count bigint not null default 1,
  last_used_at timestamptz not null default now(),
  status text not null default 'ACTIVE' check (status in ('ACTIVE','INACTIVE')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, field_key, normalized_value)
);

create index if not exists idx_master_value_catalog_lookup
  on public.master_value_catalog(tenant_id, field_key, status, usage_count desc, value_text);

create table if not exists public.user_module_permissions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  module_key text not null,
  can_view boolean not null default true,
  can_create boolean not null default false,
  can_edit boolean not null default false,
  can_archive boolean not null default false,
  can_approve boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, profile_id, module_key)
);

create index if not exists idx_user_module_permissions_profile
  on public.user_module_permissions(profile_id, module_key);

create table if not exists public.heat_code_sequences (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  prefix_letter text not null check (prefix_letter ~ '^[A-Z]$'),
  current_value bigint not null default 0,
  updated_at timestamptz not null default now(),
  unique (tenant_id, prefix_letter)
);

alter table public.rmtc_approvals
  add column if not exists grain_size integer,
  add column if not exists actual_di numeric,
  add column if not exists calculated_di numeric,
  add column if not exists actual_di_status text default 'NOT_EVALUATED',
  add column if not exists calculated_di_status text default 'NOT_EVALUATED',
  add column if not exists rmtc_copy_path text;

alter table public.rmtc_jominy_results
  add column if not exists calculated_hrc numeric,
  add column if not exists calculated_result text default 'NOT_EVALUATED',
  add column if not exists applicability text default 'APPLICABLE';

alter table public.rmtc_jominy_results drop constraint if exists rmtc_jominy_results_calculated_result_check;
alter table public.rmtc_jominy_results add constraint rmtc_jominy_results_calculated_result_check
  check (calculated_result in ('PASS','FAIL','NOT_EVALUATED','NOT_APPLICABLE'));
alter table public.rmtc_jominy_results drop constraint if exists rmtc_jominy_results_applicability_check;
alter table public.rmtc_jominy_results add constraint rmtc_jominy_results_applicability_check
  check (applicability in ('APPLICABLE','NOT_APPLICABLE'));

alter table public.rmtc_approvals drop constraint if exists rmtc_approvals_actual_di_status_check;
alter table public.rmtc_approvals add constraint rmtc_approvals_actual_di_status_check
  check (actual_di_status in ('PASS','FAIL','NOT_EVALUATED','NOT_APPLICABLE'));
alter table public.rmtc_approvals drop constraint if exists rmtc_approvals_calculated_di_status_check;
alter table public.rmtc_approvals add constraint rmtc_approvals_calculated_di_status_check
  check (calculated_di_status in ('PASS','FAIL','NOT_EVALUATED','NOT_APPLICABLE'));
alter table public.rmtc_approvals drop constraint if exists rmtc_approvals_grain_size_check;
alter table public.rmtc_approvals add constraint rmtc_approvals_grain_size_check
  check (grain_size is null or grain_size between 4 and 8);

create or replace function public.qsms_remember_master_value(p_field_key text, p_value_text text)
returns text
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  tid uuid := public.current_tenant_id();
  cleaned text := btrim(coalesce(p_value_text,''));
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  if tid is null then raise exception 'Active QSMS tenant is required'; end if;
  if btrim(coalesce(p_field_key,'')) = '' or cleaned = '' then return cleaned; end if;
  insert into public.master_value_catalog(tenant_id, field_key, value_text)
  values(tid, btrim(p_field_key), cleaned)
  on conflict (tenant_id, field_key, normalized_value)
  do update set usage_count = public.master_value_catalog.usage_count + 1,
                value_text = excluded.value_text,
                status = 'ACTIVE',
                last_used_at = now(),
                updated_at = now(),
                updated_by = auth.uid();
  return cleaned;
end;
$$;

create or replace function public.qsms_next_employee_code()
returns text
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  tid uuid := public.current_tenant_id();
  next_value bigint;
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  insert into public.number_sequences(tenant_id, sequence_code, prefix, year_format, current_value, padding, reset_frequency)
  values(tid,'EMPLOYEE','EMP','',0,4,'NEVER')
  on conflict (tenant_id,sequence_code) do nothing;
  update public.number_sequences
     set current_value=current_value+1,updated_at=now(),updated_by=auth.uid()
   where tenant_id=tid and sequence_code='EMPLOYEE'
   returning current_value into next_value;
  return 'EMP-' || lpad(next_value::text,4,'0');
end;
$$;

create or replace function public.qsms_next_heat_code(p_steel_mill_id uuid)
returns text
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  tid uuid := public.current_tenant_id();
  mill_name text;
  prefix text;
  next_value bigint;
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  select party_name into mill_name
    from public.parties
   where id=p_steel_mill_id and tenant_id=tid and status='ACTIVE'
     and 'STEEL_MILL'=any(party_types);
  if mill_name is null then raise exception 'Select an active Steel Mill'; end if;
  prefix := upper(substring(regexp_replace(mill_name,'[^A-Za-z]','','g') from 1 for 1));
  if prefix is null or prefix='' then raise exception 'Steel Mill name must contain an alphabetic character'; end if;
  insert into public.heat_code_sequences(tenant_id,prefix_letter,current_value)
  values(tid,prefix,0)
  on conflict (tenant_id,prefix_letter) do nothing;
  update public.heat_code_sequences
     set current_value=current_value+1,updated_at=now()
   where tenant_id=tid and prefix_letter=prefix
   returning current_value into next_value;
  return prefix || '-' || lpad(next_value::text,4,'0');
end;
$$;

create or replace function public.qsms_module_for_table(target_table text)
returns text
language sql
immutable
as $$
  select case
    when target_table in ('parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','document_attachments') then 'PART_MASTER'
    when target_table in ('material_grades','material_grade_elements') then 'MATERIAL_GRADE'
    when target_table in ('parties','part_supplier_links','processes','inspection_stages','quality_assets','jominy_distances','master_value_catalog') then 'REFERENCE_MASTERS'
    when target_table='employees' then 'EMPLOYEE_MASTER'
    when target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results') then 'RMTC_ENTRY'
    when target_table='user_module_permissions' then 'USER_ACCESS'
    else upper(target_table)
  end;
$$;

create or replace function public.qsms_has_module_write(target_table text)
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
  select exists(
    select 1 from public.user_module_permissions p
     where p.profile_id=auth.uid()
       and p.tenant_id=public.current_tenant_id()
       and p.module_key=public.qsms_module_for_table(target_table)
       and p.can_view=true
       and (p.can_create=true or p.can_edit=true)
  );
$$;

create or replace function public.can_write_table(target_table text)
returns boolean
language plpgsql
stable
security definer
set search_path = public, auth
as $$
declare
  role_name text := coalesce(public.current_app_role(), 'VIEWER');
begin
  if role_name='ADMIN' then return true; end if;
  if public.qsms_has_module_write(target_table) then return true; end if;
  if target_table in ('parties','material_grades','material_grade_elements','parts','part_supplier_links','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','processes','inspection_stages','master_value_catalog') then
    return role_name in ('QUALITY_MANAGER','MASTER_DATA');
  elsif target_table in ('employees','quality_assets') then
    return role_name in ('QUALITY_MANAGER','MASTER_DATA','QUALITY_ENGINEER');
  elsif target_table in ('inspection_plans','inspection_plan_characteristics','test_plans') then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','METLAB_APPROVER');
  elsif target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results') then
    return role_name in ('QUALITY_MANAGER','METLAB_APPROVER','SQA');
  end if;
  return false;
end;
$$;

alter table public.master_value_catalog enable row level security;
alter table public.user_module_permissions enable row level security;
alter table public.heat_code_sequences enable row level security;

-- Controlled value catalogue policies.
drop policy if exists tenant_select on public.master_value_catalog;
create policy tenant_select on public.master_value_catalog for select to authenticated
using (tenant_id=public.current_tenant_id());
drop policy if exists tenant_insert on public.master_value_catalog;
create policy tenant_insert on public.master_value_catalog for insert to authenticated
with check (tenant_id=public.current_tenant_id() and public.can_write_table('master_value_catalog'));
drop policy if exists tenant_update on public.master_value_catalog;
create policy tenant_update on public.master_value_catalog for update to authenticated
using (tenant_id=public.current_tenant_id() and public.can_write_table('master_value_catalog'))
with check (tenant_id=public.current_tenant_id() and public.can_write_table('master_value_catalog'));

-- Permission rows are visible to the owner and administrators; only administrators change them.
drop policy if exists permission_select on public.user_module_permissions;
create policy permission_select on public.user_module_permissions for select to authenticated
using (tenant_id=public.current_tenant_id() and (profile_id=auth.uid() or public.current_app_role()='ADMIN'));
drop policy if exists permission_admin_insert on public.user_module_permissions;
create policy permission_admin_insert on public.user_module_permissions for insert to authenticated
with check (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');
drop policy if exists permission_admin_update on public.user_module_permissions;
create policy permission_admin_update on public.user_module_permissions for update to authenticated
using (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN')
with check (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');
drop policy if exists permission_admin_delete on public.user_module_permissions;
create policy permission_admin_delete on public.user_module_permissions for delete to authenticated
using (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');

-- Sequence table is not directly exposed; RPC functions operate it.
drop policy if exists sequence_admin_select on public.heat_code_sequences;
create policy sequence_admin_select on public.heat_code_sequences for select to authenticated
using (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');

revoke all on function public.qsms_next_employee_code() from public, anon;
revoke all on function public.qsms_next_heat_code(uuid) from public, anon;
revoke all on function public.qsms_remember_master_value(text,text) from public, anon;
grant execute on function public.qsms_next_employee_code() to authenticated;
grant execute on function public.qsms_next_heat_code(uuid) to authenticated;
grant execute on function public.qsms_remember_master_value(text,text) to authenticated;

-- Audit/timestamp controls for new tables.
drop trigger if exists trg_touch_updated_at on public.master_value_catalog;
create trigger trg_touch_updated_at before update on public.master_value_catalog
for each row execute function public.touch_updated_at();
drop trigger if exists trg_audit_row on public.master_value_catalog;
create trigger trg_audit_row after insert or update or delete on public.master_value_catalog
for each row execute function public.log_row_change();

drop trigger if exists trg_touch_updated_at on public.user_module_permissions;
create trigger trg_touch_updated_at before update on public.user_module_permissions
for each row execute function public.touch_updated_at();
drop trigger if exists trg_audit_row on public.user_module_permissions;
create trigger trg_audit_row after insert or update or delete on public.user_module_permissions
for each row execute function public.log_row_change();

commit;
