-- QCMS v4.14.16 - effective user/department permissions, section security, PO approval/cancel-reissue

alter table public.user_module_permissions
  add column if not exists can_validate boolean not null default false;

create table if not exists public.department_module_defaults (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  department text not null,
  module_key text not null,
  can_view boolean not null default true,
  can_create boolean not null default false,
  can_edit boolean not null default false,
  can_validate boolean not null default false,
  can_approve boolean not null default false,
  status text not null default 'ACTIVE',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, department, module_key)
);

create table if not exists public.user_section_permissions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  profile_id uuid not null references public.profiles(id) on delete cascade,
  module_key text not null,
  section_key text not null,
  can_view boolean not null default true,
  can_edit boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique (tenant_id, profile_id, module_key, section_key)
);

create table if not exists public.qcms_module_approval_routes (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  module_key text not null,
  department text,
  level_no integer not null check(level_no between 1 and 3),
  level_name text not null,
  employee_id uuid references public.employees(id),
  required boolean not null default true,
  status text not null default 'ACTIVE',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, module_key, department, level_no)
);

create table if not exists public.supply_stage_responsibilities (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  stage_key text not null,
  stage_label text not null,
  department text,
  employee_id uuid references public.employees(id),
  notify_supplier boolean not null default false,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, stage_key)
);

alter table public.supply_purchase_orders
  add column if not exists approval_status text not null default 'APPROVED',
  add column if not exists submitted_by_employee_id uuid references public.employees(id),
  add column if not exists submitted_at timestamptz,
  add column if not exists approver_employee_id uuid references public.employees(id),
  add column if not exists approved_at timestamptz,
  add column if not exists approval_remarks text,
  add column if not exists cancelled_by_employee_id uuid references public.employees(id),
  add column if not exists cancelled_at timestamptz,
  add column if not exists cancellation_reason text,
  add column if not exists replaces_purchase_order_id uuid references public.supply_purchase_orders(id),
  add column if not exists replacement_purchase_order_id uuid references public.supply_purchase_orders(id);

-- Existing POs remain effective. New POs are set PENDING_APPROVAL by application.
-- v4.14.16: controlled PO approval introduces PENDING_APPROVAL as a valid transient status.
alter table public.supply_purchase_orders drop constraint if exists supply_purchase_orders_status_check;
alter table public.supply_purchase_orders add constraint supply_purchase_orders_status_check
  check (status in ('DRAFT','PENDING_APPROVAL','OPEN','PARTIAL','CLOSED','CANCELLED'));
alter table public.supply_rm_purchase_orders drop constraint if exists supply_rm_purchase_orders_status_check;
alter table public.supply_rm_purchase_orders add constraint supply_rm_purchase_orders_status_check
  check (status in ('PENDING_APPROVAL','OPEN','PART_RECEIVED','CLOSED','CANCELLED'));
alter table public.supply_forging_orders drop constraint if exists supply_forging_orders_status_check;
alter table public.supply_forging_orders add constraint supply_forging_orders_status_check
  check (status in ('PENDING_APPROVAL','OPEN','PART_RECEIVED','CLOSED','CANCELLED'));

update public.supply_purchase_orders
set approval_status='APPROVED', approved_at=coalesce(approved_at,created_at)
where approval_status is null or approval_status='';

-- RLS / visibility tables
alter table public.department_module_defaults enable row level security;
alter table public.user_section_permissions enable row level security;
alter table public.qcms_module_approval_routes enable row level security;
alter table public.supply_stage_responsibilities enable row level security;

drop policy if exists dept_module_select on public.department_module_defaults;
create policy dept_module_select on public.department_module_defaults for select to authenticated
using (tenant_id=public.current_tenant_id());
drop policy if exists dept_module_admin_write on public.department_module_defaults;
create policy dept_module_admin_write on public.department_module_defaults for all to authenticated
using (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN')
with check (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');

drop policy if exists section_permission_select on public.user_section_permissions;
create policy section_permission_select on public.user_section_permissions for select to authenticated
using (tenant_id=public.current_tenant_id() and (profile_id=auth.uid() or public.current_app_role()='ADMIN'));
drop policy if exists section_permission_admin_write on public.user_section_permissions;
create policy section_permission_admin_write on public.user_section_permissions for all to authenticated
using (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN')
with check (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');


drop policy if exists supply_stage_resp_select on public.supply_stage_responsibilities;
create policy supply_stage_resp_select on public.supply_stage_responsibilities for select to authenticated using (tenant_id=public.current_tenant_id());
drop policy if exists supply_stage_resp_admin_write on public.supply_stage_responsibilities;
create policy supply_stage_resp_admin_write on public.supply_stage_responsibilities for all to authenticated using (tenant_id=public.current_tenant_id() and (public.current_app_role()='ADMIN' or public.qsms_has_module_approve('SUPPLY_CHAIN'))) with check (tenant_id=public.current_tenant_id() and (public.current_app_role()='ADMIN' or public.qsms_has_module_approve('SUPPLY_CHAIN')));

drop policy if exists approval_route_select on public.qcms_module_approval_routes;
create policy approval_route_select on public.qcms_module_approval_routes for select to authenticated
using (tenant_id=public.current_tenant_id());
drop policy if exists approval_route_admin_write on public.qcms_module_approval_routes;
create policy approval_route_admin_write on public.qcms_module_approval_routes for all to authenticated
using (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN')
with check (tenant_id=public.current_tenant_id() and public.current_app_role()='ADMIN');

-- Explicit module permissions must override role defaults in DB write checks.
create or replace function public.qsms_has_module_write(target_table text)
returns boolean language sql stable security definer set search_path='public','auth' as $$
  select exists(
    select 1 from public.user_module_permissions p
    where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid()
      and p.module_key=public.qsms_module_for_table(target_table)
      and p.can_view and (p.can_create or p.can_edit)
  );
$$;

create or replace function public.qsms_has_module_validate(p_module_key text)
returns boolean language sql stable security definer set search_path='public','auth' as $$
  select public.current_app_role()='ADMIN' or exists(
    select 1 from public.user_module_permissions p
    where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid()
      and p.module_key=upper(p_module_key) and p.can_view and p.can_validate
  );
$$;

-- Generic three-layer department defaults. Explicit user rows override these in app logic.
do $$
declare tid uuid; begin
  select id into tid from public.tenants order by created_at limit 1;
  if tid is null then return; end if;
  insert into public.department_module_defaults(tenant_id,department,module_key,can_view,can_create,can_edit,can_validate,can_approve)
  values
   (tid,'Supply Chain','SUPPLY_CHAIN',true,true,true,true,true),
   (tid,'Procurement','SUPPLY_CHAIN',true,true,true,true,true),
   (tid,'Production','SUPPLY_CHAIN',true,true,true,false,false),
   (tid,'Production','MATERIAL_INWARD',true,true,true,false,false),
   (tid,'Production','OSP_TRANSACTIONS',true,true,true,false,false),
   (tid,'Quality','RMTC_ENTRY',true,true,true,true,true),
   (tid,'Quality','MATERIAL_INWARD',true,true,true,true,true),
   (tid,'Quality','DIMENSIONAL_REPORT',true,true,true,true,true),
   (tid,'Quality','METLAB_REPORT',true,true,true,true,true),
   (tid,'METLAB','METLAB_REPORT',true,true,true,true,true),
   (tid,'Business Development','SUPPLY_CHAIN',true,true,true,false,false),
   (tid,'Business Development','NPD_APQP',true,true,true,false,false),
   (tid,'Management','SUPPLY_CHAIN',true,true,true,true,true),
   (tid,'Management','NPD_APQP',true,true,true,true,true),
   (tid,'Management','COMPLAINT_MANAGEMENT',true,true,true,true,true),
   (tid,'R & D','PART_MASTER',true,true,true,true,false),
   (tid,'R & D','NPD_APQP',true,true,true,true,false),
   (tid,'Viewer','PART_MASTER',true,false,false,false,false),
   (tid,'Viewer','SUPPLY_CHAIN',true,false,false,false,false)
  on conflict(tenant_id,department,module_key) do update set
    can_view=excluded.can_view,can_create=excluded.can_create,can_edit=excluded.can_edit,
    can_validate=excluded.can_validate,can_approve=excluded.can_approve,updated_at=now();
end $$;

-- PO cancellation / approval RPCs. Cancellation is blocked after receipt.
create or replace function public.qcms_cancel_purchase_order(p_purchase_order_id uuid,p_reason text)
returns jsonb language plpgsql security definer set search_path='public','auth' as $$
declare tid uuid:=public.current_tenant_id(); po public.supply_purchase_orders%rowtype; emp uuid; received numeric:=0;
begin
 if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
 if not (public.current_app_role()='ADMIN' or public.qsms_has_module_write('supply_rm_purchase_orders')) then raise exception 'Supply Chain edit permission is required'; end if;
 select * into po from public.supply_purchase_orders where id=p_purchase_order_id and tenant_id=tid for update;
 if po.id is null then raise exception 'Purchase Order not found'; end if;
 if po.status='CANCELLED' then return to_jsonb(po); end if;
 if btrim(coalesce(p_reason,''))='' then raise exception 'Cancellation reason is required'; end if;
 if po.po_type='RAW_MATERIAL' then
   select coalesce(sum(rr.received_qty_kg),0) into received from public.supply_rm_receipts rr join public.supply_rm_purchase_orders r on r.id=rr.rm_purchase_order_id where r.purchase_order_id=po.id;
 else
   select coalesce(sum(fr.received_qty_pcs),0) into received from public.supply_forging_receipts fr join public.supply_forging_orders f on f.id=fr.forging_order_id where f.purchase_order_id=po.id;
 end if;
 if received>0 then raise exception 'PO cannot be cancelled after receipt. Use controlled amendment/closure instead.'; end if;
 select public.qcms_current_login_employee_id() into emp;
 update public.supply_purchase_orders set status='CANCELLED',approval_status='CANCELLED',cancellation_reason=btrim(p_reason),cancelled_by_employee_id=emp,cancelled_at=now(),updated_at=now(),updated_by=auth.uid() where id=po.id returning * into po;
 update public.supply_rm_purchase_orders set status='CANCELLED',updated_at=now(),updated_by=auth.uid() where purchase_order_id=po.id;
 update public.supply_forging_orders set status='CANCELLED',updated_at=now(),updated_by=auth.uid() where purchase_order_id=po.id;
 return to_jsonb(po);
end $$;

create or replace function public.qcms_approve_purchase_order(p_purchase_order_id uuid,p_remarks text default null)
returns jsonb language plpgsql security definer set search_path='public','auth' as $$
declare tid uuid:=public.current_tenant_id(); po public.supply_purchase_orders%rowtype; emp uuid;
begin
 if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
 if not (public.current_app_role()='ADMIN' or public.qsms_has_module_approve('SUPPLY_CHAIN')) then raise exception 'Supply Chain approval permission is required'; end if;
 select public.qcms_current_login_employee_id() into emp;
 if emp is null then raise exception 'Login is not linked to Employee Master'; end if;
 select * into po from public.supply_purchase_orders where id=p_purchase_order_id and tenant_id=tid for update;
 if po.id is null then raise exception 'Purchase Order not found'; end if;
 if po.approval_status<>'PENDING_APPROVAL' then raise exception 'Only a pending Purchase Order can be approved'; end if;
 update public.supply_purchase_orders set approval_status='APPROVED',status='OPEN',approver_employee_id=emp,approved_at=now(),approval_remarks=nullif(btrim(coalesce(p_remarks,'')),''),updated_at=now(),updated_by=auth.uid() where id=po.id returning * into po;
 update public.supply_rm_purchase_orders set status='OPEN',updated_at=now(),updated_by=auth.uid() where purchase_order_id=po.id and status='PENDING_APPROVAL';
 update public.supply_forging_orders set status='OPEN',updated_at=now(),updated_by=auth.uid() where purchase_order_id=po.id and status='PENDING_APPROVAL';
 return to_jsonb(po);
end $$;

-- Notification templates/routes for PO approval and customer-order stage responsibility.
do $$ declare tid uuid; begin
 select id into tid from public.tenants order by created_at limit 1;
 if tid is null then return; end if;
 insert into public.qcms_email_templates(tenant_id,template_key,template_name,subject_template,body_template,enabled,include_generated_pdf,include_record_attachments)
 values
 (tid,'PO_APPROVAL_PENDING','PO Approval Pending','QCMS · PO {{ po_number }} awaiting approval','Purchase Order {{ po_number }} was prepared by {{ requisitioner }} and is awaiting manager approval.\nSupplier: {{ supplier_name }}\nNext stage: Approval.',true,true,true),
 (tid,'PO_APPROVED','PO Approved','QCMS · PO {{ po_number }} approved','Purchase Order {{ po_number }} is approved and effective.\nSupplier: {{ supplier_name }}\nNext stage: {{ next_stage }}.',true,true,true),
 (tid,'CUSTOMER_ORDER_STAGE_PENDING','Customer Order Stage Pending','QCMS · {{ customer_order }} · {{ stage }} pending','Customer Order {{ customer_order }} / {{ part_number }} is pending at {{ stage }}.\nResponsible: {{ responsible_employee }}\nDue: {{ due_date }}.',true,false,true)
 on conflict(tenant_id,template_key) do update set subject_template=excluded.subject_template,body_template=excluded.body_template,enabled=true,updated_at=now();
end $$;

alter table public.supply_customer_orders
  add column if not exists responsible_employee_id uuid references public.employees(id);

-- Ensure all enterprise functional roles used by Employee/Department access can be assigned.
alter table public.profiles drop constraint if exists profiles_role_check;
alter table public.profiles add constraint profiles_role_check check (role = any(array[
 'ADMIN','MANAGEMENT','SUPPLY_CHAIN','PROCUREMENT','BUSINESS_DEVELOPMENT','QUALITY_MANAGER','METLAB_APPROVER','QUALITY_ENGINEER','PRODUCTION','SQA','MASTER_DATA','AUDITOR','VIEWER'
]));

create or replace function public.qcms_approve_purchase_order(p_purchase_order_id uuid,p_remarks text default null)
returns jsonb language plpgsql security definer set search_path='public','auth' as $$
declare tid uuid:=public.current_tenant_id(); po public.supply_purchase_orders%rowtype; emp uuid; manager_id uuid;
begin
 if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
 if not (public.current_app_role()='ADMIN' or public.qsms_has_module_approve('SUPPLY_CHAIN')) then raise exception 'Supply Chain approval permission is required'; end if;
 select public.qcms_current_login_employee_id() into emp;
 if emp is null then raise exception 'Login is not linked to Employee Master'; end if;
 select * into po from public.supply_purchase_orders where id=p_purchase_order_id and tenant_id=tid for update;
 if po.id is null then raise exception 'Purchase Order not found'; end if;
 if po.approval_status<>'PENDING_APPROVAL' then raise exception 'Only a pending Purchase Order can be approved'; end if;
 select reports_to_employee_id into manager_id from public.employees where id=po.submitted_by_employee_id and tenant_id=tid;
 if manager_id is not null and emp<>manager_id and public.current_app_role()<>'ADMIN' then
   raise exception 'This PO must be approved by the submitting employee''s Reports To manager';
 end if;
 update public.supply_purchase_orders set approval_status='APPROVED',status='OPEN',approver_employee_id=emp,approved_at=now(),approval_remarks=nullif(btrim(coalesce(p_remarks,'')),''),updated_at=now(),updated_by=auth.uid() where id=po.id returning * into po;
 update public.supply_rm_purchase_orders set status='OPEN',updated_at=now(),updated_by=auth.uid() where purchase_order_id=po.id and status='PENDING_APPROVAL';
 update public.supply_forging_orders set status='OPEN',updated_at=now(),updated_by=auth.uid() where purchase_order_id=po.id and status='PENDING_APPROVAL';
 return to_jsonb(po);
end $$;

do $$ declare tid uuid; begin
 select id into tid from public.tenants order by created_at limit 1;
 if tid is null then return; end if;
 insert into public.qcms_notification_routes(tenant_id,event_key,route_label,department,department_cc,send_to_supplier,template_key,next_stage,enabled)
 values
  (tid,'PO_APPROVAL_PENDING','Purchase Order approval pending','Supply Chain',true,false,'PO_APPROVAL_PENDING','Manager Approval',true),
  (tid,'PO_APPROVED','Purchase Order approved','Supply Chain',true,true,'PO_APPROVED','Supplier / Next Supply Chain Stage',true),
  (tid,'CUSTOMER_ORDER_STAGE_PENDING','Customer Order stage pending','Supply Chain',false,false,'CUSTOMER_ORDER_STAGE_PENDING','Current Supply Chain Stage',true)
 on conflict(tenant_id,event_key) do update set route_label=excluded.route_label,department=excluded.department,department_cc=excluded.department_cc,send_to_supplier=excluded.send_to_supplier,template_key=excluded.template_key,next_stage=excluded.next_stage,enabled=true,updated_at=now();
end $$;

-- ---------------------------------------------------------------------------
-- v4.14.16 permission precedence hardening.
-- Explicit user permission is authoritative (including DENY), then department
-- defaults, and only then legacy role fallback. This fixes cases where a user
-- permission was saved but a broad role silently granted the action again.
-- ---------------------------------------------------------------------------
create or replace function public.qcms_current_department()
returns text language sql stable security definer set search_path='public','auth' as $$
  select coalesce((
    select nullif(btrim(e.department),'')
    from public.employees e
    left join public.profiles p on p.id=auth.uid()
    where e.tenant_id=public.current_tenant_id() and e.status='ACTIVE'
      and (e.profile_id=auth.uid() or (p.email is not null and lower(btrim(e.email))=lower(btrim(p.email))))
    order by case when e.profile_id=auth.uid() then 0 else 1 end,e.updated_at desc
    limit 1
  ),'');
$$;

create or replace function public.qsms_has_module_write(target_table text)
returns boolean language plpgsql stable security definer set search_path='public','auth' as $$
declare module_name text:=public.qsms_module_for_table(target_table); dept text:=public.qcms_current_department(); configured boolean;
begin
  if public.current_app_role()='ADMIN' then return true; end if;
  select exists(select 1 from public.user_module_permissions p where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid() and p.module_key=module_name) into configured;
  if configured then
    return exists(select 1 from public.user_module_permissions p where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid() and p.module_key=module_name and p.can_view and (p.can_create or p.can_edit));
  end if;
  if dept<>'' then
    select exists(select 1 from public.department_module_defaults d where d.tenant_id=public.current_tenant_id() and lower(btrim(d.department))=lower(btrim(dept)) and d.module_key=module_name and d.status='ACTIVE') into configured;
    if configured then
      return exists(select 1 from public.department_module_defaults d where d.tenant_id=public.current_tenant_id() and lower(btrim(d.department))=lower(btrim(dept)) and d.module_key=module_name and d.status='ACTIVE' and d.can_view and (d.can_create or d.can_edit));
    end if;
  end if;
  return false;
end $$;

create or replace function public.qsms_has_module_validate(p_module_key text)
returns boolean language plpgsql stable security definer set search_path='public','auth' as $$
declare module_name text:=upper(p_module_key); dept text:=public.qcms_current_department(); configured boolean; role_name text:=coalesce(public.current_app_role(),'VIEWER');
begin
  if role_name='ADMIN' then return true; end if;
  select exists(select 1 from public.user_module_permissions p where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid() and p.module_key=module_name) into configured;
  if configured then
    return exists(select 1 from public.user_module_permissions p where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid() and p.module_key=module_name and p.can_view and p.can_validate);
  end if;
  if dept<>'' then
    select exists(select 1 from public.department_module_defaults d where d.tenant_id=public.current_tenant_id() and lower(btrim(d.department))=lower(btrim(dept)) and d.module_key=module_name and d.status='ACTIVE') into configured;
    if configured then
      return exists(select 1 from public.department_module_defaults d where d.tenant_id=public.current_tenant_id() and lower(btrim(d.department))=lower(btrim(dept)) and d.module_key=module_name and d.status='ACTIVE' and d.can_view and d.can_validate);
    end if;
  end if;
  return role_name in ('MANAGEMENT','QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER','SQA','SUPPLY_CHAIN','PROCUREMENT');
end $$;

create or replace function public.qsms_has_module_approve(p_module_key text)
returns boolean language plpgsql stable security definer set search_path='public','auth' as $$
declare module_name text:=upper(p_module_key); dept text:=public.qcms_current_department(); configured boolean; role_name text:=coalesce(public.current_app_role(),'VIEWER');
begin
  if role_name='ADMIN' then return true; end if;
  select exists(select 1 from public.user_module_permissions p where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid() and p.module_key=module_name) into configured;
  if configured then
    return exists(select 1 from public.user_module_permissions p where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid() and p.module_key=module_name and p.can_view and p.can_approve);
  end if;
  if dept<>'' then
    select exists(select 1 from public.department_module_defaults d where d.tenant_id=public.current_tenant_id() and lower(btrim(d.department))=lower(btrim(dept)) and d.module_key=module_name and d.status='ACTIVE') into configured;
    if configured then
      return exists(select 1 from public.department_module_defaults d where d.tenant_id=public.current_tenant_id() and lower(btrim(d.department))=lower(btrim(dept)) and d.module_key=module_name and d.status='ACTIVE' and d.can_view and d.can_approve);
    end if;
  end if;
  if module_name='DIMENSIONAL_REPORT' then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','MANAGEMENT'); end if;
  if module_name='METLAB_REPORT' then return role_name in ('QUALITY_MANAGER','METLAB_APPROVER','MANAGEMENT'); end if;
  return role_name in ('MANAGEMENT');
end $$;

create or replace function public.can_write_table(target_table text)
returns boolean language plpgsql stable security definer set search_path='public','auth' as $$
declare
  role_name text:=coalesce(public.current_app_role(),'VIEWER');
  module_name text:=public.qsms_module_for_table(target_table);
  dept text:=public.qcms_current_department();
  configured boolean;
begin
  if role_name='ADMIN' then return true; end if;

  select exists(select 1 from public.user_module_permissions p where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid() and p.module_key=module_name) into configured;
  if configured then
    return exists(select 1 from public.user_module_permissions p where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid() and p.module_key=module_name and p.can_view and (p.can_create or p.can_edit));
  end if;

  if dept<>'' then
    select exists(select 1 from public.department_module_defaults d where d.tenant_id=public.current_tenant_id() and lower(btrim(d.department))=lower(btrim(dept)) and d.module_key=module_name and d.status='ACTIVE') into configured;
    if configured then
      return exists(select 1 from public.department_module_defaults d where d.tenant_id=public.current_tenant_id() and lower(btrim(d.department))=lower(btrim(dept)) and d.module_key=module_name and d.status='ACTIVE' and d.can_view and (d.can_create or d.can_edit));
    end if;
  end if;

  -- Legacy role fallback only when neither an employee override nor department
  -- matrix row exists for the module.
  if target_table in ('parties','material_grades','material_grade_elements','parts','part_material_grade_links','part_supplier_links','part_raw_material_details','part_raw_material_technical_data','part_supplier_price_history','part_jominy_requirements','part_heat_treatment_details','part_rmtc_requirements','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','part_standard_links','processes','inspection_stages','master_value_catalog','customer_standards') then
    return role_name in ('QUALITY_MANAGER','MASTER_DATA','PROCUREMENT','MANAGEMENT');
  elsif target_table in ('employees','quality_assets','company_branches') then
    return role_name in ('QUALITY_MANAGER','MASTER_DATA','QUALITY_ENGINEER','MANAGEMENT');
  elsif target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results','rmtc_decision_revisions') then
    return role_name in ('QUALITY_MANAGER','METLAB_APPROVER','SQA','MANAGEMENT');
  elsif target_table='inward_lots' then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION','SUPPLY_CHAIN','PROCUREMENT','MANAGEMENT');
  elsif target_table in ('production_batches','batch_movements','osp_jobs') then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION','SUPPLY_CHAIN','MANAGEMENT');
  elsif target_table in ('inspection_plans','inspection_plan_characteristics','test_plans') then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA','MANAGEMENT');
  elsif target_table in ('inspection_reports','inspection_results') then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','MANAGEMENT');
  elsif target_table='lab_tests' then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER','MANAGEMENT');
  elsif target_table in ('npd_process_flows','npd_process_flow_steps','npd_process_flow_points','npd_orders','npd_order_steps','npd_order_step_points','ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items','control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings','msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics') then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA','SQA','PRODUCTION','BUSINESS_DEVELOPMENT','MANAGEMENT');
  elsif target_table='qc_calculation_records' then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER','SQA','MANAGEMENT');
  elsif target_table in ('quality_complaints','quality_complaint_followups','quality_complaint_actions') then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION','BUSINESS_DEVELOPMENT','MANAGEMENT');
  elsif target_table in ('supply_customer_orders','supply_purchase_orders','supply_purchase_order_items','supply_purchase_order_sources','supply_opening_stock','supply_rm_purchase_orders','supply_rm_receipts','supply_forging_orders','supply_rm_dispatches','supply_forging_receipts','supply_downstream_events') then
    return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA','SQA','PRODUCTION','SUPPLY_CHAIN','PROCUREMENT','BUSINESS_DEVELOPMENT','MANAGEMENT');
  end if;
  return false;
end $$;

-- Seed additional existing departments into their relevant modules. All values
-- remain editable from Admin → Users & Access → Department → Module Defaults.
do $$ declare tid uuid; begin
  select id into tid from public.tenants order by created_at limit 1;
  if tid is null then return; end if;
  insert into public.department_module_defaults(tenant_id,department,module_key,can_view,can_create,can_edit,can_validate,can_approve)
  values
    (tid,'Account','SUPPLY_CHAIN',true,false,false,false,false),
    (tid,'HR','EMPLOYEE_MASTER',true,true,true,true,false),
    (tid,'Surface Treatment','OSP_TRANSACTIONS',true,true,true,false,false),
    (tid,'Surface Treatment','DIMENSIONAL_REPORT',true,true,true,false,false),
    (tid,'R&D','PART_MASTER',true,true,true,true,false),
    (tid,'R&D','NPD_APQP',true,true,true,true,false)
  on conflict(tenant_id,department,module_key) do update set
    can_view=excluded.can_view,can_create=excluded.can_create,can_edit=excluded.can_edit,
    can_validate=excluded.can_validate,can_approve=excluded.can_approve,updated_at=now();
end $$;

-- Stage-specific responsibility matrix for Supply Chain pending-action reporting.
do $$ declare tid uuid; begin
 select id into tid from public.tenants order by created_at limit 1; if tid is null then return; end if;
 insert into public.supply_stage_responsibilities(tenant_id,stage_key,stage_label,department,notify_supplier,enabled) values
  (tid,'CUSTOMER_ORDER','Customer Order / Schedule','Business Development',false,true),
  (tid,'RM_PROCUREMENT','RM Procurement / Purchase Order','Procurement',false,true),
  (tid,'RM_RECEIPT','RM Receipt / Material Inward','Supply Chain',true,true),
  (tid,'RM_TO_FORGING','RM to Forger','Supply Chain',true,true),
  (tid,'FORGING_ORDER','Forging Purchase Order','Procurement',true,true),
  (tid,'FORGING_RECEIPT','Forging Receipt','Supply Chain',true,true),
  (tid,'PART_PRODUCTION','Part Production / Machining','Production',false,true),
  (tid,'FINISHED_GOODS','Finished Goods','Production',false,true),
  (tid,'CUSTOMER_DISPATCH','Customer Dispatch','Supply Chain',false,true)
 on conflict(tenant_id,stage_key) do update set stage_label=excluded.stage_label,department=excluded.department,notify_supplier=excluded.notify_supplier,enabled=true,updated_at=now();
end $$;
