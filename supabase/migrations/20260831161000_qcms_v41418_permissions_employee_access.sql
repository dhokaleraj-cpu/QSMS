-- QCMS v4.14.18 / 1 of 3 — user/role/department permissions and conservative employee recovery.
-- Additive/backward-compatible. No transactional/business rows are reset.

begin;

-- QCMS v4.14.18 - user/role/department permissions, section create/view controls,
-- employee-link/email recovery, comprehensive audit, OSP controlled delete, same-Heat reuse and MetLAB RLS alignment.
-- Additive/backward-compatible. No transactional/business rows are deleted or reset.


-- -----------------------------------------------------------------------------
-- 1) Employee hierarchy: top-level authority may intentionally have no Reports-To.
-- -----------------------------------------------------------------------------
alter table public.employees
  add column if not exists is_top_level_authority boolean not null default false;

-- Preserve the known QCMS top-level administrator as intentionally unassigned to Reports-To.
update public.employees e
set is_top_level_authority=true,
    reports_to_employee_id=null,
    updated_at=now()
where e.employee_code='QSMS-ADMIN-001'
  and exists (
    select 1 from public.profiles p
    where p.id=e.profile_id and p.tenant_id=e.tenant_id and p.role='ADMIN'
  );

-- -----------------------------------------------------------------------------
-- 2) Restore employee ↔ user links ONLY where one unlinked employee has exactly
--    one active profile with the same normalized email and that profile is not
--    already linked to another employee. This is intentionally conservative.
-- -----------------------------------------------------------------------------
with candidate_pairs as (
  select
    e.id as employee_id,
    p.id as profile_id,
    count(*) over(partition by e.id) as profile_matches,
    count(*) over(partition by p.id) as employee_matches
  from public.employees e
  join public.profiles p
    on p.tenant_id=e.tenant_id
   and lower(btrim(p.email))=lower(btrim(e.email))
   and p.status='ACTIVE'
  where e.profile_id is null
    and nullif(btrim(coalesce(e.email,'')),'') is not null
    and not exists (
      select 1 from public.employees already_linked
      where already_linked.tenant_id=e.tenant_id
        and already_linked.profile_id=p.id
    )
), safe_pairs as (
  select employee_id,profile_id
  from candidate_pairs
  where profile_matches=1 and employee_matches=1
)
update public.employees e
set profile_id=s.profile_id,
    updated_at=now()
from safe_pairs s
where e.id=s.employee_id
  and e.profile_id is null;

-- Restore an Employee Master email only when the earliest audited INSERT email
-- matches the employee's currently linked profile email and the current employee
-- email differs. This repairs login-email overwrites while preserving legitimate
-- unrelated employee email addresses.
with first_employee_email as (
  select distinct on (row_id)
    row_id,
    new_data->>'email' as original_email
  from public.audit_log
  where table_name='employees'
    and operation='INSERT'
    and nullif(new_data->>'email','') is not null
  order by row_id,changed_at
), safe_email_restore as (
  select e.id,f.original_email
  from public.employees e
  join public.profiles p on p.id=e.profile_id and p.tenant_id=e.tenant_id
  join first_employee_email f on f.row_id=e.id
  where lower(btrim(coalesce(e.email,'')))<>lower(btrim(coalesce(p.email,'')))
    and lower(btrim(coalesce(f.original_email,'')))=lower(btrim(coalesce(p.email,'')))
)
update public.employees e
set email=s.original_email,
    updated_at=now()
from safe_email_restore s
where e.id=s.id;

-- -----------------------------------------------------------------------------
-- 3) Role → Module defaults and complete Department module permissions.
-- -----------------------------------------------------------------------------
create table if not exists public.role_module_defaults (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  role text not null,
  module_key text not null,
  can_view boolean not null default true,
  can_create boolean not null default false,
  can_edit boolean not null default false,
  can_validate boolean not null default false,
  can_approve boolean not null default false,
  can_archive boolean not null default false,
  status text not null default 'ACTIVE',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique(tenant_id,role,module_key)
);

alter table public.department_module_defaults
  add column if not exists can_archive boolean not null default false;

alter table public.role_module_defaults enable row level security;
drop policy if exists role_module_select on public.role_module_defaults;
create policy role_module_select on public.role_module_defaults
for select to authenticated
using (tenant_id=public.current_tenant_id());
drop policy if exists role_module_admin_write on public.role_module_defaults;
create policy role_module_admin_write on public.role_module_defaults
for all to authenticated
using (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN')
with check (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');

-- -----------------------------------------------------------------------------
-- 4) Section permission now distinguishes View/Create/Edit.
--    No section row = inherit module rights; therefore everything is visible by
--    default to a user who can view the module.
-- -----------------------------------------------------------------------------
alter table public.user_section_permissions
  add column if not exists can_create boolean;
update public.user_section_permissions
set can_create=coalesce(can_create,can_edit,false)
where can_create is null;
alter table public.user_section_permissions
  alter column can_create set default false;
alter table public.user_section_permissions
  alter column can_create set not null;

-- -----------------------------------------------------------------------------
-- 5) Complete table → module mapping. v4.14.16 did not map controlled PO header,
--    item/source and opening-stock tables, causing a valid SUPPLY_CHAIN Create
--    permission to be rejected by RLS during PO submission.
-- -----------------------------------------------------------------------------
create or replace function public.qsms_module_for_table(target_table text)
returns text language sql immutable set search_path=public as $$
select case
 when target_table in ('parts','part_material_grade_links','part_raw_material_details','part_raw_material_technical_data','part_supplier_price_history','part_jominy_requirements','part_heat_treatment_details','part_rmtc_requirements','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','document_attachments','part_standard_links') then 'PART_MASTER'
 when target_table in ('material_grades','material_grade_elements') then 'MATERIAL_GRADE'
 when target_table in ('parties','part_supplier_links','processes','inspection_stages','quality_assets','jominy_distances','master_value_catalog','standards_register','calculation_rules','customer_standards','company_branches') then 'REFERENCE_MASTERS'
 when target_table='employees' then 'EMPLOYEE_MASTER'
 when target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results','rmtc_decision_revisions') then 'RMTC_ENTRY'
 when target_table='inward_lots' then 'MATERIAL_INWARD'
 when target_table in ('production_batches','batch_movements','osp_jobs','osp_receipts') then 'OSP_TRANSACTIONS'
 when target_table in ('inspection_plans','inspection_plan_characteristics','test_plans') then 'INSPECTION_LAYOUTS'
 when target_table in ('inspection_reports','inspection_results') then 'DIMENSIONAL_REPORT'
 when target_table='lab_tests' then 'METLAB_REPORT'
 when target_table in ('npd_process_flows','npd_process_flow_steps','npd_process_flow_points','npd_orders','npd_order_steps','npd_order_step_points','ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items','control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings','msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics') then 'NPD_APQP'
 when target_table='qc_calculation_records' then 'QC_CALCULATION_TOOLS'
 when target_table in ('quality_complaints','quality_complaint_followups','quality_complaint_actions') then 'COMPLAINT_MANAGEMENT'
 when target_table in ('supply_customer_orders','supply_purchase_orders','supply_purchase_order_items','supply_purchase_order_sources','supply_opening_stock','supply_rm_purchase_orders','supply_rm_receipts','supply_forging_orders','supply_rm_dispatches','supply_forging_receipts','supply_downstream_events') then 'SUPPLY_CHAIN'
 when target_table in ('user_module_permissions','user_section_permissions','department_module_defaults','role_module_defaults','qcms_module_approval_routes','supply_stage_responsibilities','qcms_user_activity_log') then 'USER_ACCESS'
 else upper(target_table) end;
$$;

-- -----------------------------------------------------------------------------
-- 6) One authoritative effective permission function used by database workflow
--    controls. Precedence: ADMIN → explicit user → role default → department
--    default → conservative legacy role fallback.
-- -----------------------------------------------------------------------------
create or replace function public.qcms_effective_module_permission(p_module_key text,p_permission text)
returns boolean
language plpgsql stable security definer set search_path='public','auth' as $$
declare
  module_name text:=upper(btrim(coalesce(p_module_key,'')));
  permission_name text:=lower(btrim(coalesce(p_permission,'')));
  role_name text:=coalesce(public.current_app_role(),'VIEWER');
  dept text:=public.qcms_current_department();
  configured boolean:=false;
  result boolean:=false;
begin
  if auth.uid() is null or public.current_tenant_id() is null then return false; end if;
  if role_name='ADMIN' then return true; end if;
  if permission_name not in ('view','create','edit','validate','approve','archive') then return false; end if;

  select exists(
    select 1 from public.user_module_permissions p
    where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid() and upper(p.module_key)=module_name
  ) into configured;
  if configured then
    select case permission_name
      when 'view' then p.can_view
      when 'create' then p.can_create
      when 'edit' then p.can_edit
      when 'validate' then p.can_validate
      when 'approve' then p.can_approve
      when 'archive' then p.can_archive
      else false end
    into result
    from public.user_module_permissions p
    where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid() and upper(p.module_key)=module_name
    limit 1;
    return coalesce(result,false);
  end if;

  select exists(
    select 1 from public.role_module_defaults r
    where r.tenant_id=public.current_tenant_id() and upper(btrim(r.role))=upper(btrim(role_name))
      and upper(r.module_key)=module_name and r.status='ACTIVE'
  ) into configured;
  if configured then
    select case permission_name
      when 'view' then r.can_view
      when 'create' then r.can_create
      when 'edit' then r.can_edit
      when 'validate' then r.can_validate
      when 'approve' then r.can_approve
      when 'archive' then r.can_archive
      else false end
    into result
    from public.role_module_defaults r
    where r.tenant_id=public.current_tenant_id() and upper(btrim(r.role))=upper(btrim(role_name))
      and upper(r.module_key)=module_name and r.status='ACTIVE'
    limit 1;
    return coalesce(result,false);
  end if;

  if dept<>'' then
    select exists(
      select 1 from public.department_module_defaults d
      where d.tenant_id=public.current_tenant_id()
        and lower(btrim(d.department))=lower(btrim(dept))
        and upper(d.module_key)=module_name and d.status='ACTIVE'
    ) into configured;
    if configured then
      select case permission_name
        when 'view' then d.can_view
        when 'create' then d.can_create
        when 'edit' then d.can_edit
        when 'validate' then d.can_validate
        when 'approve' then d.can_approve
        when 'archive' then d.can_archive
        else false end
      into result
      from public.department_module_defaults d
      where d.tenant_id=public.current_tenant_id()
        and lower(btrim(d.department))=lower(btrim(dept))
        and upper(d.module_key)=module_name and d.status='ACTIVE'
      limit 1;
      return coalesce(result,false);
    end if;
  end if;

  -- Legacy fallback only when no user/role/department row is configured.
  if permission_name='view' then return true; end if;
  if permission_name='archive' then return false; end if;
  if permission_name='validate' then
    return role_name in ('MANAGEMENT','QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER','SQA','SUPPLY_CHAIN','PROCUREMENT');
  end if;
  if permission_name='approve' then
    if module_name='DIMENSIONAL_REPORT' then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','MANAGEMENT'); end if;
    if module_name='METLAB_REPORT' then return role_name in ('QUALITY_MANAGER','METLAB_APPROVER','MANAGEMENT'); end if;
    return role_name in ('MANAGEMENT');
  end if;
  if permission_name in ('create','edit') then
    if role_name in ('VIEWER','AUDITOR') then return false; end if;
    if module_name='SUPPLY_CHAIN' then
      return role_name in ('SUPPLY_CHAIN','PROCUREMENT','PRODUCTION','MANAGEMENT','QUALITY_MANAGER','MASTER_DATA');
    elsif module_name in ('RMTC_ENTRY','MATERIAL_INWARD','DIMENSIONAL_REPORT','METLAB_REPORT','OSP_TRANSACTIONS') then
      return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER','SQA','PRODUCTION','MANAGEMENT');
    elsif module_name='NPD_APQP' then
      return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER','SQA','PRODUCTION','BUSINESS_DEVELOPMENT','MANAGEMENT','MASTER_DATA');
    else
      return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER','SQA','MASTER_DATA','MANAGEMENT');
    end if;
  end if;
  return false;
end $$;

create or replace function public.qsms_has_module_write(target_table text)
returns boolean language sql stable security definer set search_path='public','auth' as $$
  select public.qcms_effective_module_permission(public.qsms_module_for_table(target_table),'create')
      or public.qcms_effective_module_permission(public.qsms_module_for_table(target_table),'edit');
$$;

create or replace function public.can_write_table(target_table text)
returns boolean language sql stable security definer set search_path='public','auth' as $$
  select public.qsms_has_module_write(target_table);
$$;

create or replace function public.qsms_has_module_validate(p_module_key text)
returns boolean language sql stable security definer set search_path='public','auth' as $$
  select public.qcms_effective_module_permission(p_module_key,'validate');
$$;

create or replace function public.qsms_has_module_approve(p_module_key text)
returns boolean language sql stable security definer set search_path='public','auth' as $$
  select public.qcms_effective_module_permission(p_module_key,'approve');
$$;

revoke all on function public.qcms_effective_module_permission(text,text) from public,anon;
grant execute on function public.qcms_effective_module_permission(text,text) to authenticated;
revoke all on function public.qsms_has_module_write(text) from public,anon;
grant execute on function public.qsms_has_module_write(text) to authenticated;
revoke all on function public.can_write_table(text) from public,anon;
grant execute on function public.can_write_table(text) to authenticated;
revoke all on function public.qsms_has_module_validate(text) from public,anon;
grant execute on function public.qsms_has_module_validate(text) to authenticated;
revoke all on function public.qsms_has_module_approve(text) from public,anon;
grant execute on function public.qsms_has_module_approve(text) to authenticated;

create or replace function public.qcms_effective_section_permission(p_module_key text,p_section_key text,p_permission text)
returns boolean
language plpgsql stable security definer set search_path='public','auth' as $$
declare
  permission_name text:=lower(btrim(coalesce(p_permission,'')));
  row_permission public.user_section_permissions%rowtype;
begin
  if public.current_app_role()='ADMIN' then return true; end if;
  if permission_name not in ('view','create','edit') then return false; end if;
  select * into row_permission
  from public.user_section_permissions s
  where s.tenant_id=public.current_tenant_id() and s.profile_id=auth.uid()
    and upper(s.module_key)=upper(btrim(p_module_key)) and upper(s.section_key)=upper(btrim(p_section_key))
  limit 1;
  if row_permission.id is not null then
    if permission_name='view' then return row_permission.can_view; end if;
    if permission_name='create' then return row_permission.can_view and row_permission.can_create and public.qcms_effective_module_permission(p_module_key,'create'); end if;
    return row_permission.can_view and row_permission.can_edit and public.qcms_effective_module_permission(p_module_key,'edit');
  end if;
  return public.qcms_effective_module_permission(p_module_key,permission_name);
end $$;

revoke all on function public.qcms_effective_section_permission(text,text,text) from public,anon;
grant execute on function public.qcms_effective_section_permission(text,text,text) to authenticated;

-- Secure sensitive Part Master sections at the Data API layer as well as the UI.
alter table public.part_supplier_price_history enable row level security;
drop policy if exists tenant_select on public.part_supplier_price_history;
create policy tenant_select on public.part_supplier_price_history
for select to authenticated
using (tenant_id=public.current_tenant_id() and public.qcms_effective_section_permission('PART_MASTER','PRICE_HISTORY','view'));

alter table public.part_raw_material_technical_data enable row level security;
drop policy if exists tenant_select on public.part_raw_material_technical_data;
create policy tenant_select on public.part_raw_material_technical_data
for select to authenticated
using (tenant_id=public.current_tenant_id() and public.qcms_effective_section_permission('PART_MASTER','SUPPLIER_TECHNICAL','view'));

commit;
