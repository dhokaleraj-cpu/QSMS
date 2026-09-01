-- QCMS v4.14.17 - automatic migration guard + configurable PO approval route precedence
-- Additive/backward-compatible. No business or transactional rows are deleted/reset.

create table if not exists public.qcms_release_schema_state (
  version text primary key,
  build text not null,
  applied_at timestamptz not null default now(),
  details jsonb not null default '{}'::jsonb
);
alter table public.qcms_release_schema_state enable row level security;
revoke all on table public.qcms_release_schema_state from anon, authenticated;

create or replace function public.qcms_purchase_order_approval_target(p_purchase_order_id uuid)
returns jsonb
language plpgsql
security definer
set search_path='public','auth'
as $$
declare
  tid uuid := public.current_tenant_id();
  po public.supply_purchase_orders%rowtype;
  submitter public.employees%rowtype;
  target public.employees%rowtype;
  route_employee_id uuid;
  route_department text;
  route_level integer;
  route_level_name text;
begin
  if auth.uid() is null or tid is null then
    raise exception 'Authenticated QCMS session required';
  end if;

  select * into po
  from public.supply_purchase_orders
  where id=p_purchase_order_id and tenant_id=tid;
  if po.id is null then raise exception 'Purchase Order not found'; end if;

  if po.submitted_by_employee_id is not null then
    select * into submitter
    from public.employees
    where id=po.submitted_by_employee_id and tenant_id=tid;
  end if;

  select r.employee_id, r.department, r.level_no, r.level_name
    into route_employee_id, route_department, route_level, route_level_name
  from public.qcms_module_approval_routes r
  join public.employees e on e.id=r.employee_id and e.tenant_id=r.tenant_id and e.status='ACTIVE'
  where r.tenant_id=tid
    and upper(btrim(r.module_key))='SUPPLY_CHAIN'
    and r.status='ACTIVE'
    and r.required
    and r.employee_id is not null
    and (
      nullif(btrim(coalesce(r.department,'')),'') is null
      or lower(btrim(r.department))=lower(btrim(coalesce(submitter.department,'')))
    )
  order by
    case when nullif(btrim(coalesce(r.department,'')),'') is not null
              and lower(btrim(r.department))=lower(btrim(coalesce(submitter.department,''))) then 0 else 1 end,
    r.level_no,
    r.created_at
  limit 1;

  if route_employee_id is not null then
    select * into target from public.employees where id=route_employee_id and tenant_id=tid;
    return jsonb_build_object(
      'source','CONFIGURED_ROUTE',
      'employee_id',target.id,
      'employee_code',target.employee_code,
      'employee_name',btrim(concat_ws(' ',target.first_name,target.last_name)),
      'email',target.email,
      'department',target.department,
      'level_no',route_level,
      'level_name',coalesce(nullif(btrim(route_level_name),''),'Approval'),
      'route_department',route_department,
      'submitted_by_employee_id',po.submitted_by_employee_id
    );
  end if;

  if submitter.reports_to_employee_id is not null then
    select * into target
    from public.employees
    where id=submitter.reports_to_employee_id and tenant_id=tid and status='ACTIVE';
    if target.id is not null then
      return jsonb_build_object(
        'source','REPORTS_TO',
        'employee_id',target.id,
        'employee_code',target.employee_code,
        'employee_name',btrim(concat_ws(' ',target.first_name,target.last_name)),
        'email',target.email,
        'department',target.department,
        'level_no',1,
        'level_name','Reports-To Manager Approval',
        'route_department',submitter.department,
        'submitted_by_employee_id',po.submitted_by_employee_id
      );
    end if;
  end if;

  return jsonb_build_object(
    'source','PERMISSION_FALLBACK',
    'employee_id',null,
    'employee_code',null,
    'employee_name',null,
    'email',null,
    'department',submitter.department,
    'level_no',1,
    'level_name','Any different employee with Supply Chain Approve permission',
    'route_department',submitter.department,
    'submitted_by_employee_id',po.submitted_by_employee_id
  );
end $$;

revoke all on function public.qcms_purchase_order_approval_target(uuid) from public, anon;
grant execute on function public.qcms_purchase_order_approval_target(uuid) to authenticated;

create or replace function public.qcms_approve_purchase_order(p_purchase_order_id uuid,p_remarks text default null)
returns jsonb
language plpgsql
security definer
set search_path='public','auth'
as $$
declare
  tid uuid:=public.current_tenant_id();
  po public.supply_purchase_orders%rowtype;
  emp uuid;
  target jsonb;
  required_approver uuid;
begin
  if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
  if not (public.current_app_role()='ADMIN' or public.qsms_has_module_approve('SUPPLY_CHAIN')) then
    raise exception 'Supply Chain approval permission is required';
  end if;
  select public.qcms_current_login_employee_id() into emp;
  if emp is null then raise exception 'Login is not linked to Employee Master'; end if;

  select * into po from public.supply_purchase_orders where id=p_purchase_order_id and tenant_id=tid for update;
  if po.id is null then raise exception 'Purchase Order not found'; end if;
  if po.approval_status<>'PENDING_APPROVAL' then raise exception 'Only a pending Purchase Order can be approved'; end if;

  target := public.qcms_purchase_order_approval_target(po.id);
  required_approver := nullif(target->>'employee_id','')::uuid;

  if public.current_app_role()<>'ADMIN' then
    if required_approver is not null and emp<>required_approver then
      if coalesce(target->>'source','')='CONFIGURED_ROUTE' then
        raise exception 'This PO must be approved by the configured QCMS approval-route employee';
      else
        raise exception 'This PO must be approved by the submitting employee''s Reports-To manager';
      end if;
    end if;
    if required_approver is null and emp=po.submitted_by_employee_id then
      raise exception 'Self-approval is not permitted. Another employee with Supply Chain Approve permission must approve this PO';
    end if;
  end if;

  update public.supply_purchase_orders
  set approval_status='APPROVED',status='OPEN',approver_employee_id=emp,approved_at=now(),
      approval_remarks=nullif(btrim(coalesce(p_remarks,'')),''),updated_at=now(),updated_by=auth.uid()
  where id=po.id returning * into po;
  update public.supply_rm_purchase_orders set status='OPEN',updated_at=now(),updated_by=auth.uid()
    where purchase_order_id=po.id and status='PENDING_APPROVAL';
  update public.supply_forging_orders set status='OPEN',updated_at=now(),updated_by=auth.uid()
    where purchase_order_id=po.id and status='PENDING_APPROVAL';
  return to_jsonb(po);
end $$;

revoke all on function public.qcms_approve_purchase_order(uuid,text) from public, anon;
grant execute on function public.qcms_approve_purchase_order(uuid,text) to authenticated;
-- v4.14.16 cancellation already checks auth/tenant/write rights internally; remove the anonymous API surface as defense in depth.
revoke all on function public.qcms_cancel_purchase_order(uuid,text) from public, anon;
grant execute on function public.qcms_cancel_purchase_order(uuid,text) to authenticated;

-- Harmless Data API marker used by the one-file updater to verify the exact release
-- without needing database-admin credentials after this migration is already live.
create or replace function public.qcms_release_schema_version()
returns text
language sql
immutable
security invoker
set search_path='pg_catalog'
as $$ select '4.14.17'::text $$;
revoke all on function public.qcms_release_schema_version() from public;
grant execute on function public.qcms_release_schema_version() to anon, authenticated;

insert into public.qcms_release_schema_state(version,build,applied_at,details)
values ('4.14.17','41417-AUTO-MIGRATION-APPROVAL-ROUTES-MANIFEST-SYNC',now(),
        jsonb_build_object('approval_route_precedence','CONFIGURED_ROUTE -> REPORTS_TO -> PERMISSION_FALLBACK',
                           'automatic_migration_guard',true,
                           'data_reset',false))
on conflict(version) do update set build=excluded.build,applied_at=excluded.applied_at,details=excluded.details;
