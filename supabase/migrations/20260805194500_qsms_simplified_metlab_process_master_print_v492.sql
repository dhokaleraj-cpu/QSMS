-- QSMS 4.9.2 — simplified Part Master MetLAB requirements, Process Master and report print system.
begin;

-- -----------------------------------------------------------------------------
-- Final drawing metallurgical requirements (Part-level; no process selection)
-- -----------------------------------------------------------------------------
create table if not exists public.part_metallurgical_requirements (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  part_id uuid not null references public.parts(id) on delete cascade,
  parameter_name text not null,
  minimum_spec numeric,
  maximum_spec numeric,
  sequence_no integer not null default 10,
  status text not null default 'ACTIVE',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  constraint part_metallurgical_status_check check (status in ('ACTIVE','INACTIVE')),
  constraint part_metallurgical_limits_check check (
    minimum_spec is not null or maximum_spec is not null
  ),
  constraint part_metallurgical_min_max_check check (
    minimum_spec is null or maximum_spec is null or minimum_spec <= maximum_spec
  )
);

create unique index if not exists uq_part_metallurgical_requirement
  on public.part_metallurgical_requirements(tenant_id,part_id,lower(btrim(parameter_name)));
create index if not exists idx_part_metallurgical_requirement_part
  on public.part_metallurgical_requirements(part_id,status,sequence_no);

alter table public.part_metallurgical_requirements enable row level security;
drop policy if exists tenant_select on public.part_metallurgical_requirements;
drop policy if exists tenant_insert on public.part_metallurgical_requirements;
drop policy if exists tenant_update on public.part_metallurgical_requirements;
drop policy if exists tenant_delete on public.part_metallurgical_requirements;
create policy tenant_select on public.part_metallurgical_requirements
  for select to authenticated using (tenant_id=public.current_tenant_id());
create policy tenant_insert on public.part_metallurgical_requirements
  for insert to authenticated with check (
    tenant_id=public.current_tenant_id() and public.can_write_table('parts')
  );
create policy tenant_update on public.part_metallurgical_requirements
  for update to authenticated using (
    tenant_id=public.current_tenant_id() and public.can_write_table('parts')
  ) with check (
    tenant_id=public.current_tenant_id() and public.can_write_table('parts')
  );
create policy tenant_delete on public.part_metallurgical_requirements
  for delete to authenticated using (
    tenant_id=public.current_tenant_id() and (
      public.current_app_role()='ADMIN' or exists(
        select 1 from public.user_module_permissions p
        where p.tenant_id=public.current_tenant_id()
          and p.profile_id=auth.uid() and p.module_key='PART_MASTER'
          and p.can_view and p.can_archive
      )
    )
  );
grant select,insert,update,delete on public.part_metallurgical_requirements to authenticated;

create or replace function public.enforce_part_metallurgical_requirement()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare v_part public.parts%rowtype;
begin
  select * into v_part from public.parts where id=new.part_id;
  if v_part.id is null then raise exception 'Select a valid Part Number'; end if;
  new.tenant_id:=v_part.tenant_id;
  new.parameter_name:=btrim(coalesce(new.parameter_name,''));
  if new.parameter_name='' then raise exception 'Metallurgical Parameter is required'; end if;
  if new.minimum_spec is null and new.maximum_spec is null then
    raise exception 'Enter Minimum or Maximum Specification for %',new.parameter_name;
  end if;
  if new.minimum_spec is not null and new.maximum_spec is not null
     and new.minimum_spec>new.maximum_spec then
    raise exception 'Minimum Specification cannot exceed Maximum Specification for %',new.parameter_name;
  end if;
  new.updated_at:=now();
  new.updated_by:=auth.uid();
  return new;
end;
$$;
drop trigger if exists trg_part_metallurgical_requirement on public.part_metallurgical_requirements;
create trigger trg_part_metallurgical_requirement
before insert or update on public.part_metallurgical_requirements
for each row execute function public.enforce_part_metallurgical_requirement();

-- -----------------------------------------------------------------------------
-- Identify automatically generated layouts by requirement scope.
-- -----------------------------------------------------------------------------
alter table public.inspection_plans
  add column if not exists requirement_scope text not null default 'GENERAL';
alter table public.inspection_plans drop constraint if exists inspection_plans_requirement_scope_check;
alter table public.inspection_plans add constraint inspection_plans_requirement_scope_check
  check (requirement_scope in ('GENERAL','OSP_METLAB','FINAL_METALLURGICAL'));
create index if not exists idx_inspection_plans_requirement_scope
  on public.inspection_plans(part_id,process_id,requirement_scope,layout_type,status,effective_date desc);

-- Existing generated OSP MetLAB layouts are classified without modifying results.
update public.inspection_plans
set requirement_scope='OSP_METLAB'
where source_process_specification_id is not null
  and layout_type='METLAB'
  and requirement_scope='GENERAL';

-- -----------------------------------------------------------------------------
-- Generate the final Part Metallurgical Requirements layout.
-- -----------------------------------------------------------------------------
create or replace function public.qsms_generate_final_metallurgical_layout(p_part_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_tenant uuid:=public.current_tenant_id();
  v_part public.parts%rowtype;
  v_plan public.inspection_plans%rowtype;
  v_plan_number text;
  v_revision text;
  v_used boolean:=false;
  v_count integer:=0;
begin
  if auth.uid() is null or v_tenant is null then
    raise exception 'An authenticated QSMS session is required';
  end if;
  if not public.can_write_table('inspection_plans') or not public.can_write_table('parts') then
    raise exception 'Part Master and Inspection Layout edit permissions are required';
  end if;
  select * into v_part from public.parts where id=p_part_id and tenant_id=v_tenant;
  if v_part.id is null then raise exception 'Select a valid Part Number'; end if;
  select count(*) into v_count
  from public.part_metallurgical_requirements
  where part_id=v_part.id and status='ACTIVE';
  if v_count=0 then raise exception 'Add at least one active Metallurgical Requirement'; end if;

  select * into v_plan
  from public.inspection_plans
  where tenant_id=v_tenant and part_id=v_part.id
    and requirement_scope='FINAL_METALLURGICAL' and layout_type='METLAB'
  order by effective_date desc nulls last,revision desc
  limit 1;

  if v_plan.id is not null then
    select exists(select 1 from public.lab_tests where layout_plan_id=v_plan.id) into v_used;
  end if;
  v_plan_number:=left('FINAL-'||regexp_replace(v_part.part_number,'[^A-Za-z0-9]+','-','g')||'-MET',100);

  if v_plan.id is null or v_used then
    if v_plan.id is not null then
      update public.inspection_plans
      set status='SUPERSEDED',updated_at=now(),updated_by=auth.uid()
      where id=v_plan.id;
      begin
        v_revision:=lpad((coalesce(nullif(regexp_replace(v_plan.revision,'[^0-9]','','g'),''),'0')::integer+1)::text,2,'0');
      exception when others then v_revision:='01'; end;
    else
      v_revision:='00';
    end if;
    insert into public.inspection_plans(
      tenant_id,part_id,process_id,inspection_stage_id,plan_number,revision,effective_date,
      sample_plan,status,layout_type,layout_name,report_title,format_number,format_revision,
      default_sample_size,source_template_name,remarks,inward_type,requirement_scope
    ) values(
      v_tenant,v_part.id,null,null,v_plan_number,v_revision,current_date,
      '1 sample','APPROVED','METLAB',
      v_part.part_number||' · Final Metallurgical Requirements',
      'FINAL PART METALLURGICAL INSPECTION REPORT',v_plan_number,'00',1,
      'PART_MASTER_METALLURGICAL_REQUIREMENTS',
      coalesce(v_part.drawing_number,'Final drawing requirements'),
      'MATERIAL_INWARD','FINAL_METALLURGICAL'
    ) returning * into v_plan;
  else
    update public.inspection_plans set
      effective_date=current_date,status='APPROVED',
      layout_name=v_part.part_number||' · Final Metallurgical Requirements',
      report_title='FINAL PART METALLURGICAL INSPECTION REPORT',
      source_template_name='PART_MASTER_METALLURGICAL_REQUIREMENTS',
      remarks=coalesce(v_part.drawing_number,'Final drawing requirements'),
      inward_type='MATERIAL_INWARD',requirement_scope='FINAL_METALLURGICAL',
      updated_at=now(),updated_by=auth.uid()
    where id=v_plan.id returning * into v_plan;
    delete from public.inspection_plan_characteristics where inspection_plan_id=v_plan.id;
  end if;

  insert into public.inspection_plan_characteristics(
    tenant_id,inspection_plan_id,sequence_no,characteristic_no,characteristic,specification,
    lower_spec,upper_spec,unit,characteristic_type,checking_method,checking_aid_text,
    sample_size,report_section,is_mandatory,allow_na,decimal_places,layout_metadata,status
  )
  select
    v_tenant,v_plan.id,r.sequence_no,row_number() over(order by r.sequence_no,r.parameter_name)::text,
    r.parameter_name,
    concat_ws(' ',case when r.minimum_spec is not null then 'Min '||r.minimum_spec end,
                  case when r.maximum_spec is not null then 'Max '||r.maximum_spec end),
    r.minimum_spec,r.maximum_spec,null,'VARIABLE',null,null,1,'METLAB',true,false,3,
    jsonb_build_object('source','PART_MASTER_METALLURGICAL_REQUIREMENTS',
      'metallurgical_requirement_id',r.id,'part_id',v_part.id,
      'drawing_number',v_part.drawing_number,'drawing_revision',v_part.drawing_revision),
    r.status
  from public.part_metallurgical_requirements r
  where r.part_id=v_part.id and r.status='ACTIVE'
  order by r.sequence_no,r.parameter_name;
  get diagnostics v_count=row_count;

  return jsonb_build_object('generated',true,'layout_id',v_plan.id,
    'plan_number',v_plan.plan_number,'revision',v_plan.revision,'characteristics',v_count);
end;
$$;
revoke all on function public.qsms_generate_final_metallurgical_layout(uuid) from public,anon;
grant execute on function public.qsms_generate_final_metallurgical_layout(uuid) to authenticated;

-- Classify layouts generated by the existing OSP process RPC as OSP MetLAB.
create or replace function public.qsms_mark_osp_metlab_layout_scope()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
begin
  if new.source_process_specification_id is not null and new.layout_type='METLAB' then
    new.requirement_scope:='OSP_METLAB';
  end if;
  return new;
end;
$$;
drop trigger if exists trg_mark_osp_metlab_layout_scope on public.inspection_plans;
create trigger trg_mark_osp_metlab_layout_scope
before insert or update on public.inspection_plans
for each row execute function public.qsms_mark_osp_metlab_layout_scope();

-- -----------------------------------------------------------------------------
-- Simplified views used by the three-column Part Master grids.
-- -----------------------------------------------------------------------------
create or replace view public.v_qsms_osp_metlab_requirements
with (security_invoker=true)
as
select
  p.tenant_id,p.id,p.process_specification_id,p.part_id,part.part_number,part.part_name,
  p.process_id,process.process_code,process.process_name,
  p.parameter_name,p.minimum_spec,p.maximum_spec,p.sequence_no,p.status,
  g.layout_generated_at
from public.part_process_parameter_specifications p
join public.parts part on part.id=p.part_id
join public.processes process on process.id=p.process_id
join public.part_process_specifications g on g.id=p.process_specification_id
where p.inspection_type='METLAB' and p.inward_type='OSP_PROCESS';

grant select on public.v_qsms_osp_metlab_requirements to authenticated;

create or replace view public.v_qsms_part_metallurgical_requirements
with (security_invoker=true)
as
select r.tenant_id,r.id,r.part_id,p.part_number,p.part_name,
  r.parameter_name,r.minimum_spec,r.maximum_spec,r.sequence_no,r.status,
  r.created_at,r.updated_at
from public.part_metallurgical_requirements r
join public.parts p on p.id=r.part_id;
grant select on public.v_qsms_part_metallurgical_requirements to authenticated;

-- -----------------------------------------------------------------------------
-- Module permissions and password-protected deletion.
-- -----------------------------------------------------------------------------
create or replace function public.qsms_module_for_table(target_table text) returns text language sql immutable as $$
select case
 when target_table in ('parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','document_attachments') then 'PART_MASTER'
 when target_table in ('material_grades','material_grade_elements') then 'MATERIAL_GRADE'
 when target_table in ('parties','part_supplier_links','processes','inspection_stages','quality_assets','jominy_distances','master_value_catalog') then 'REFERENCE_MASTERS'
 when target_table='employees' then 'EMPLOYEE_MASTER'
 when target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results') then 'RMTC_ENTRY'
 when target_table='inward_lots' then 'MATERIAL_INWARD'
 when target_table in ('production_batches','batch_movements','osp_jobs') then 'OSP_TRANSACTIONS'
 when target_table in ('inspection_plans','inspection_plan_characteristics') then 'INSPECTION_LAYOUTS'
 when target_table in ('inspection_reports','inspection_results') then 'DIMENSIONAL_REPORT'
 when target_table='lab_tests' then 'METLAB_REPORT'
 when target_table='user_module_permissions' then 'USER_ACCESS'
 else upper(target_table) end;
$$;

create or replace function public.can_write_table(target_table text) returns boolean
language plpgsql stable security definer set search_path=public,auth as $$
declare role_name text:=coalesce(public.current_app_role(),'VIEWER');
begin
 if role_name='ADMIN' then return true; end if;
 if public.qsms_has_module_write(target_table) then return true; end if;
 if target_table in ('parties','material_grades','material_grade_elements','parts','part_supplier_links','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','processes','inspection_stages','master_value_catalog') then return role_name in ('QUALITY_MANAGER','MASTER_DATA');
 elsif target_table in ('employees','quality_assets') then return role_name in ('QUALITY_MANAGER','MASTER_DATA','QUALITY_ENGINEER');
 elsif target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results') then return role_name in ('QUALITY_MANAGER','METLAB_APPROVER','SQA');
 elsif target_table='inward_lots' then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION');
 elsif target_table in ('production_batches','batch_movements','osp_jobs') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION');
 elsif target_table in ('inspection_plans','inspection_plan_characteristics') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA');
 elsif target_table in ('inspection_reports','inspection_results') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA');
 elsif target_table='lab_tests' then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER');
 end if;
 return false;
end;
$$;

create or replace function public.qsms_delete_master_row(p_table_name text,p_record_id uuid)
returns jsonb language plpgsql security definer set search_path=public,auth as $$
declare tid uuid:=public.current_tenant_id();role_name text:=coalesce(public.current_app_role(),'VIEWER');module_name text:=public.qsms_module_for_table(p_table_name);allowed boolean:=false;deleted_count integer:=0;
allowed_tables constant text[]:=array['parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','material_grades','material_grade_elements','parties','part_supplier_links','processes','inspection_stages','quality_assets','inspection_plans','inspection_plan_characteristics','test_plans','employees','document_attachments','rmtc_approvals','inward_lots','inspection_reports','inspection_results','lab_tests'];
begin
 if auth.uid() is null then raise exception 'Authentication required';end if;
 if p_table_name is null or not(p_table_name=any(allowed_tables)) then raise exception 'Deletion is not allowed for this table';end if;
 allowed:=role_name='ADMIN' or exists(select 1 from public.user_module_permissions p where p.tenant_id=tid and p.profile_id=auth.uid() and p.module_key=module_name and p.can_view and p.can_archive);
 if not allowed then raise exception 'Delete permission is not assigned for this module';end if;
 execute format('delete from public.%I where id=$1 and tenant_id=$2',p_table_name) using p_record_id,tid;get diagnostics deleted_count=row_count;
 if deleted_count=0 then raise exception 'The selected row was not found or is outside your company tenant';end if;
 return jsonb_build_object('deleted',true,'table',p_table_name,'id',p_record_id);
exception when foreign_key_violation then raise exception 'This record is linked to another master or transaction. Deactivate it instead of deleting it.';
end;
$$;

commit;
