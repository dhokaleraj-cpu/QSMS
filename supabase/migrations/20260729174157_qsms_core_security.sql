-- Quality Control Monitoring System (QSMS)
-- Initial Supabase / PostgreSQL schema
-- Apply in a new Supabase project using the SQL Editor or Supabase CLI.
-- Review all roles, policies, retention rules and calculation methods before production release.

begin;

create extension if not exists pgcrypto;

-- -----------------------------------------------------------------------------
-- Common functions
-- -----------------------------------------------------------------------------
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  new.updated_by := auth.uid();
  return new;
end;
$$;

-- -----------------------------------------------------------------------------
-- Tenant and user profiles
-- -----------------------------------------------------------------------------
create table if not exists public.tenants (
  id uuid primary key default gen_random_uuid(),
  tenant_code text not null unique,
  tenant_name text not null,
  plant_code text,
  status text not null default 'ACTIVE' check (status in ('ACTIVE','INACTIVE')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid()
);

insert into public.tenants (id, tenant_code, tenant_name, plant_code)
values ('00000000-0000-0000-0000-000000000001', 'FSI', 'Four Star Industries Pvt. Ltd.', 'D9')
on conflict (id) do nothing;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  tenant_id uuid not null references public.tenants(id),
  full_name text,
  email text,
  role text not null default 'VIEWER' check (role in (
    'ADMIN','QUALITY_MANAGER','METLAB_APPROVER','QUALITY_ENGINEER','PRODUCTION',
    'SQA','MASTER_DATA','AUDITOR','VIEWER'
  )),
  status text not null default 'ACTIVE' check (status in ('ACTIVE','INACTIVE','LOCKED')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid()
);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  -- New identities always enter the default tenant as VIEWER. Tenant and role
  -- are assigned only through the controlled administration process; user
  -- metadata is never trusted for authorization.
  resolved_tenant uuid := '00000000-0000-0000-0000-000000000001'::uuid;
begin
  insert into public.profiles (id, tenant_id, full_name, email, role, status)
  values (
    new.id,
    resolved_tenant,
    coalesce(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1)),
    new.email,
    'VIEWER',
    'ACTIVE'
  )
  on conflict (id) do update
    set email = excluded.email,
        full_name = coalesce(public.profiles.full_name, excluded.full_name),
        updated_at = now();
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert or update of email on auth.users
for each row execute function public.handle_new_user();

create or replace function public.current_tenant_id()
returns uuid
language sql
stable
security definer
set search_path = public, auth
as $$
  select tenant_id from public.profiles where id = auth.uid() and status = 'ACTIVE';
$$;

create or replace function public.current_app_role()
returns text
language sql
stable
security definer
set search_path = public, auth
as $$
  select role from public.profiles where id = auth.uid() and status = 'ACTIVE';
$$;

revoke all on function public.current_tenant_id() from public, anon;
revoke all on function public.current_app_role() from public, anon;
grant execute on function public.current_tenant_id() to authenticated;
grant execute on function public.current_app_role() to authenticated;

-- Prevent application users from escalating their own tenant, role or status.
-- SQL Editor / migration execution has auth.uid() = null and remains available
-- for controlled administration and initial setup.
create or replace function public.protect_profile_privileges()
returns trigger
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  actor_id uuid := auth.uid();
  actor_role text;
begin
  if actor_id is null then
    return new;
  end if;
  actor_role := public.current_app_role();
  if actor_role = 'ADMIN' then
    -- Tenant transfer is not supported by the application. It must be handled
    -- through a reviewed database migration if ever required.
    new.tenant_id := old.tenant_id;
    return new;
  end if;
  if actor_id <> old.id then
    raise exception 'Only an administrator can update another user profile';
  end if;
  new.tenant_id := old.tenant_id;
  new.role := old.role;
  new.status := old.status;
  return new;
end;
$$;

revoke all on function public.protect_profile_privileges() from public, anon, authenticated;

drop trigger if exists trg_protect_profile_privileges on public.profiles;
create trigger trg_protect_profile_privileges
before update on public.profiles
for each row execute function public.protect_profile_privileges();

-- Central role matrix used by tenant-table RLS policies. UI permissions improve
-- usability; this function is the database authorization boundary.
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
  if role_name = 'ADMIN' then
    return true;
  end if;
  if target_table in ('parties','material_grades','material_grade_elements','parts','part_supplier_links','processes','inspection_stages') then
    return role_name in ('QUALITY_MANAGER','MASTER_DATA');
  elsif target_table in ('quality_assets') then
    return role_name in ('QUALITY_MANAGER','MASTER_DATA','QUALITY_ENGINEER');
  elsif target_table in ('inspection_plans','inspection_plan_characteristics','test_plans') then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','METLAB_APPROVER');
  elsif target_table in ('rmtc_approvals') then
    return role_name in ('QUALITY_MANAGER','METLAB_APPROVER','SQA');
  elsif target_table in ('inward_lots') then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA');
  elsif target_table in ('production_batches','batch_movements') then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','PRODUCTION');
  elsif target_table in ('osp_jobs') then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','PRODUCTION','SQA');
  elsif target_table in ('inspection_reports','inspection_results') then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','PRODUCTION','SQA');
  elsif target_table in ('lab_tests') then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER');
  elsif target_table in ('calculation_rules') then
    return role_name in ('QUALITY_MANAGER','METLAB_APPROVER');
  elsif target_table in ('ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items','control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings','msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics') then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER');
  elsif target_table in ('calibration_events') then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER');
  elsif target_table in ('audit_plans','audit_findings') then
    return role_name in ('QUALITY_MANAGER','SQA','AUDITOR');
  elsif target_table in ('dispatches','dispatch_batches','customer_report_packages','customer_report_package_items') then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','PRODUCTION');
  elsif target_table in ('standards_register') then
    return role_name in ('QUALITY_MANAGER');
  elsif target_table in ('document_attachments') then
    return role_name <> 'VIEWER';
  elsif target_table in ('document_approvals') then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER','SQA','AUDITOR');
  elsif target_table in ('number_sequences') then
    return role_name in ('MASTER_DATA');
  end if;
  return false;
end;
$$;

revoke all on function public.can_write_table(text) from public, anon;
grant execute on function public.can_write_table(text) to authenticated;

commit;
