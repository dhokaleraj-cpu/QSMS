-- QSMS 4.9.1 — OSP parameter groups, process drawings, generated layouts and reports.
begin;

-- -----------------------------------------------------------------------------
-- OSP process group header extensions
-- -----------------------------------------------------------------------------
alter table public.part_process_specifications
  add column if not exists specification_reference text,
  add column if not exists drawing_number text,
  add column if not exists drawing_revision text,
  add column if not exists layout_generated_at timestamptz;

-- -----------------------------------------------------------------------------
-- Parameter specifications grouped below one Part + OSP Process header
-- -----------------------------------------------------------------------------
create table if not exists public.part_process_parameter_specifications (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  process_specification_id uuid not null references public.part_process_specifications(id) on delete cascade,
  part_id uuid not null references public.parts(id) on delete cascade,
  process_id uuid not null references public.processes(id),
  inward_type text not null default 'OSP_PROCESS',
  inspection_type text not null,
  parameter_name text not null,
  specification_text text,
  minimum_spec numeric,
  maximum_spec numeric,
  unit text,
  characteristic_type text not null default 'VARIABLE',
  checking_method text,
  sample_size integer not null default 1,
  is_mandatory boolean not null default true,
  allow_na boolean not null default false,
  sequence_no integer not null default 10,
  status text not null default 'ACTIVE',
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  constraint part_process_parameter_inward_type_check check (inward_type='OSP_PROCESS'),
  constraint part_process_parameter_inspection_type_check check (inspection_type in ('DIMENSIONAL','METLAB')),
  constraint part_process_parameter_characteristic_type_check check (characteristic_type in ('VARIABLE','ATTRIBUTE')),
  constraint part_process_parameter_sample_size_check check (sample_size between 1 and 20),
  constraint part_process_parameter_status_check check (status in ('ACTIVE','INACTIVE')),
  constraint part_process_parameter_limits_check check (minimum_spec is null or maximum_spec is null or minimum_spec<=maximum_spec)
);

create unique index if not exists uq_part_process_parameter_name
  on public.part_process_parameter_specifications(
    tenant_id,process_specification_id,inspection_type,lower(btrim(parameter_name))
  );
create index if not exists idx_part_process_parameter_group
  on public.part_process_parameter_specifications(process_specification_id,inspection_type,status,sequence_no);
create index if not exists idx_part_process_parameter_options
  on public.part_process_parameter_specifications(process_id,inspection_type,status,parameter_name);

alter table public.part_process_parameter_specifications enable row level security;
drop policy if exists tenant_select on public.part_process_parameter_specifications;
drop policy if exists tenant_insert on public.part_process_parameter_specifications;
drop policy if exists tenant_update on public.part_process_parameter_specifications;
drop policy if exists tenant_delete on public.part_process_parameter_specifications;
create policy tenant_select on public.part_process_parameter_specifications
  for select to authenticated using (tenant_id=public.current_tenant_id());
create policy tenant_insert on public.part_process_parameter_specifications
  for insert to authenticated with check (
    tenant_id=public.current_tenant_id() and public.can_write_table('parts')
  );
create policy tenant_update on public.part_process_parameter_specifications
  for update to authenticated using (
    tenant_id=public.current_tenant_id() and public.can_write_table('parts')
  ) with check (
    tenant_id=public.current_tenant_id() and public.can_write_table('parts')
  );
create policy tenant_delete on public.part_process_parameter_specifications
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

grant select,insert,update,delete on public.part_process_parameter_specifications to authenticated;

create or replace function public.enforce_part_process_parameter_genealogy()
returns trigger
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_group public.part_process_specifications%rowtype;
begin
  select * into v_group
  from public.part_process_specifications
  where id=new.process_specification_id;
  if v_group.id is null then
    raise exception 'Select a valid Part OSP Process specification group';
  end if;
  if v_group.inward_type<>'OSP_PROCESS' then
    raise exception 'OSP parameters can be linked only to an OSP Process specification group';
  end if;
  new.tenant_id:=v_group.tenant_id;
  new.part_id:=v_group.part_id;
  new.process_id:=v_group.process_id;
  new.inward_type:='OSP_PROCESS';
  new.parameter_name:=btrim(coalesce(new.parameter_name,''));
  if new.parameter_name='' then raise exception 'OSP inspection Parameter is required'; end if;
  if new.characteristic_type='VARIABLE'
     and new.minimum_spec is null and new.maximum_spec is null
     and btrim(coalesce(new.specification_text,''))='' then
    raise exception 'Enter Minimum, Maximum or Specification for Parameter %',new.parameter_name;
  end if;
  if new.minimum_spec is not null and new.maximum_spec is not null and new.minimum_spec>new.maximum_spec then
    raise exception 'Minimum specification cannot exceed Maximum specification for Parameter %',new.parameter_name;
  end if;
  new.updated_at:=now();
  new.updated_by:=auth.uid();
  return new;
end;
$$;

drop trigger if exists trg_part_process_parameter_genealogy on public.part_process_parameter_specifications;
create trigger trg_part_process_parameter_genealogy
before insert or update on public.part_process_parameter_specifications
for each row execute function public.enforce_part_process_parameter_genealogy();

-- Generated layouts retain the source OSP process group.
alter table public.inspection_plans
  add column if not exists source_process_specification_id uuid references public.part_process_specifications(id);
create index if not exists idx_inspection_plan_process_group
  on public.inspection_plans(source_process_specification_id,layout_type,status,effective_date desc);

-- -----------------------------------------------------------------------------
-- Attachment permissions for OSP process drawings
-- -----------------------------------------------------------------------------
create or replace function public.qsms_attachment_module(p_entity_type text)
returns text
language sql
immutable
as $$
select case upper(coalesce(p_entity_type, ''))
  when 'RMTC' then 'RMTC_ENTRY'
  when 'MATERIAL_INWARD' then 'MATERIAL_INWARD'
  when 'PART_MASTER' then 'PART_MASTER'
  when 'PART_PROCESS_SPEC' then 'PART_MASTER'
  when 'DIMENSIONAL_REPORT' then 'DIMENSIONAL_REPORT'
  when 'METLAB_REPORT' then 'METLAB_REPORT'
  else null
end;
$$;

create or replace function public.qsms_delete_document_attachment(p_attachment_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_tenant uuid:=public.current_tenant_id();
  v_attachment public.document_attachments%rowtype;
  v_module text;
  v_allowed boolean:=false;
begin
  if auth.uid() is null or v_tenant is null then raise exception 'An authenticated QSMS session is required'; end if;
  select * into v_attachment from public.document_attachments
  where id=p_attachment_id and tenant_id=v_tenant for update;
  if v_attachment.id is null then raise exception 'The selected attachment was not found'; end if;
  v_module:=public.qsms_attachment_module(v_attachment.entity_type);
  v_allowed:=public.current_app_role()='ADMIN' or (
    v_module is not null and exists(
      select 1 from public.user_module_permissions p
      where p.tenant_id=v_tenant and p.profile_id=auth.uid()
        and p.module_key=v_module and p.can_view and p.can_archive
    )
  );
  if not v_allowed then raise exception 'Attachment delete permission is not assigned for this module'; end if;
  delete from public.document_attachments where id=p_attachment_id and tenant_id=v_tenant;
  return jsonb_build_object('deleted',true,'id',p_attachment_id,'entity_type',v_attachment.entity_type,
    'entity_id',v_attachment.entity_id,'object_path',v_attachment.object_path);
end;
$$;

-- Extend controlled storage deletion to Part/OSP drawing folders.
drop policy if exists qsms_storage_delete on storage.objects;
create policy qsms_storage_delete on storage.objects
for delete to authenticated
using (
  bucket_id='quality-documents'
  and (storage.foldername(name))[1]=public.current_tenant_id()::text
  and (
    public.current_app_role()='ADMIN'
    or (
      (storage.foldername(name))[2] in ('parts','osp_process_drawings')
      and exists(
        select 1 from public.user_module_permissions p
        where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid()
          and p.module_key='PART_MASTER' and p.can_view and p.can_archive
      )
    )
    or (
      (storage.foldername(name))[2]='rmtc'
      and exists(select 1 from public.user_module_permissions p
        where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid()
          and p.module_key='RMTC_ENTRY' and p.can_view and p.can_archive)
    )
    or (
      (storage.foldername(name))[2]='inward'
      and exists(select 1 from public.user_module_permissions p
        where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid()
          and p.module_key='MATERIAL_INWARD' and p.can_view and p.can_archive)
    )
  )
);

-- -----------------------------------------------------------------------------
-- Module mapping and controlled deletion support
-- -----------------------------------------------------------------------------
create or replace function public.qsms_module_for_table(target_table text) returns text language sql immutable as $$
select case
 when target_table in ('parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_process_specifications','part_process_parameter_specifications','document_attachments') then 'PART_MASTER'
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
 if target_table in ('parties','material_grades','material_grade_elements','parts','part_supplier_links','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_process_specifications','part_process_parameter_specifications','processes','inspection_stages','master_value_catalog') then return role_name in ('QUALITY_MANAGER','MASTER_DATA');
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
allowed_tables constant text[]:=array['parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_process_specifications','part_process_parameter_specifications','material_grades','material_grade_elements','parties','part_supplier_links','processes','inspection_stages','quality_assets','inspection_plans','inspection_plan_characteristics','test_plans','employees','document_attachments','rmtc_approvals','inward_lots','inspection_reports','inspection_results','lab_tests'];
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

-- -----------------------------------------------------------------------------
-- Generate approved OSP inspection layouts directly from grouped parameters.
-- Used layouts are versioned; unused generated layouts are refreshed in place.
-- -----------------------------------------------------------------------------
create or replace function public.qsms_generate_osp_inspection_layouts(p_process_specification_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  v_tenant uuid:=public.current_tenant_id();
  v_group public.part_process_specifications%rowtype;
  v_part public.parts%rowtype;
  v_process public.processes%rowtype;
  v_type text;
  v_required boolean;
  v_parameter_count integer;
  v_plan public.inspection_plans%rowtype;
  v_plan_id uuid;
  v_revision text;
  v_used boolean;
  v_plan_number text;
  v_layout_count integer:=0;
  v_characteristic_count integer:=0;
begin
  if auth.uid() is null or v_tenant is null then raise exception 'An authenticated QSMS session is required'; end if;
  if not public.can_write_table('inspection_plans') or not public.can_write_table('parts') then
    raise exception 'Part Master and Inspection Layout edit permissions are required';
  end if;
  select * into v_group from public.part_process_specifications
  where id=p_process_specification_id and tenant_id=v_tenant and inward_type='OSP_PROCESS' and status='ACTIVE';
  if v_group.id is null then raise exception 'Select an active Part OSP Process specification group'; end if;
  select * into v_part from public.parts where id=v_group.part_id;
  select * into v_process from public.processes where id=v_group.process_id;
  if v_part.id is null or v_process.id is null then raise exception 'Part or OSP Process Master is missing'; end if;

  foreach v_type in array array['DIMENSIONAL','METLAB'] loop
    v_required:=case when v_type='DIMENSIONAL' then v_group.dimensional_required else v_group.metlab_required end;
    select count(*) into v_parameter_count from public.part_process_parameter_specifications
      where process_specification_id=v_group.id and inspection_type=v_type and status='ACTIVE';
    if not v_required and v_parameter_count=0 then continue; end if;
    if v_required and v_parameter_count=0 then
      raise exception '% parameters are required before generating the % OSP layout',v_type,v_type;
    end if;

    select * into v_plan from public.inspection_plans
      where tenant_id=v_tenant and source_process_specification_id=v_group.id and layout_type=v_type
      order by effective_date desc nulls last,revision desc limit 1;
    v_used:=false;
    if v_plan.id is not null then
      if v_type='DIMENSIONAL' then
        select exists(select 1 from public.inspection_reports where inspection_plan_id=v_plan.id) into v_used;
      else
        select exists(select 1 from public.lab_tests where layout_plan_id=v_plan.id) into v_used;
      end if;
    end if;

    if v_plan.id is null or v_used then
      if v_plan.id is not null then
        update public.inspection_plans set status='SUPERSEDED',updated_at=now(),updated_by=auth.uid() where id=v_plan.id;
        begin
          v_revision:=lpad((coalesce(nullif(regexp_replace(v_plan.revision,'[^0-9]','','g'),''),'0')::integer+1)::text,2,'0');
        exception when others then v_revision:='01'; end;
      else
        v_revision:='00';
      end if;
      v_plan_number:=left('OSP-'||regexp_replace(v_part.part_number,'[^A-Za-z0-9]+','-','g')||'-'||regexp_replace(v_process.process_code,'[^A-Za-z0-9]+','-','g')||'-'||case when v_type='DIMENSIONAL' then 'DIM' else 'MET' end,100);
      insert into public.inspection_plans(
        tenant_id,part_id,process_id,inspection_stage_id,plan_number,revision,effective_date,
        sample_plan,status,layout_type,layout_name,report_title,format_number,format_revision,
        default_sample_size,source_template_name,remarks,inward_type,source_process_specification_id
      ) values(
        v_tenant,v_group.part_id,v_group.process_id,null,v_plan_number,v_revision,current_date,
        coalesce(v_group.sample_quantity,1)||' sample(s)','APPROVED',v_type,
        v_part.part_number||' · '||v_process.process_name||' · OSP '||initcap(lower(v_type)),
        'OSP '||v_process.process_name||' '||v_type||' INSPECTION REPORT',
        v_plan_number,'00',coalesce(v_group.sample_quantity,1),'PART_MASTER_OSP_PROCESS_GROUP',
        coalesce(v_group.specification_reference,v_group.process_specification),
        'OSP_PROCESS',v_group.id
      ) returning * into v_plan;
    else
      update public.inspection_plans set
        part_id=v_group.part_id,process_id=v_group.process_id,effective_date=current_date,
        sample_plan=coalesce(v_group.sample_quantity,1)||' sample(s)',status='APPROVED',
        layout_name=v_part.part_number||' · '||v_process.process_name||' · OSP '||initcap(lower(v_type)),
        report_title='OSP '||v_process.process_name||' '||v_type||' INSPECTION REPORT',
        default_sample_size=coalesce(v_group.sample_quantity,1),source_template_name='PART_MASTER_OSP_PROCESS_GROUP',
        remarks=coalesce(v_group.specification_reference,v_group.process_specification),
        inward_type='OSP_PROCESS',source_process_specification_id=v_group.id,
        updated_at=now(),updated_by=auth.uid()
      where id=v_plan.id returning * into v_plan;
      delete from public.inspection_plan_characteristics where inspection_plan_id=v_plan.id;
    end if;
    v_plan_id:=v_plan.id;

    insert into public.inspection_plan_characteristics(
      tenant_id,inspection_plan_id,sequence_no,characteristic_no,characteristic,specification,
      lower_spec,upper_spec,unit,characteristic_type,checking_method,checking_aid_text,
      sample_size,report_section,is_mandatory,allow_na,decimal_places,layout_metadata,status
    )
    select
      v_tenant,v_plan_id,p.sequence_no,row_number() over(order by p.sequence_no,p.parameter_name)::text,
      p.parameter_name,
      coalesce(nullif(btrim(p.specification_text),''),
        concat_ws(' ',case when p.minimum_spec is not null then 'Min '||p.minimum_spec end,
                      case when p.maximum_spec is not null then 'Max '||p.maximum_spec end,
                      p.unit)),
      p.minimum_spec,p.maximum_spec,p.unit,p.characteristic_type,p.checking_method,p.checking_method,
      p.sample_size,v_type,p.is_mandatory,p.allow_na,3,
      jsonb_build_object('source','PART_MASTER_OSP_PROCESS_GROUP','process_specification_id',v_group.id,
        'parameter_specification_id',p.id,'drawing_number',v_group.drawing_number,'drawing_revision',v_group.drawing_revision),
      p.status
    from public.part_process_parameter_specifications p
    where p.process_specification_id=v_group.id and p.inspection_type=v_type and p.status='ACTIVE'
    order by p.sequence_no,p.parameter_name;

    get diagnostics v_parameter_count=row_count;
    v_characteristic_count:=v_characteristic_count+v_parameter_count;
    v_layout_count:=v_layout_count+1;
  end loop;

  update public.part_process_specifications set layout_generated_at=now(),updated_at=now(),updated_by=auth.uid()
  where id=v_group.id;
  return jsonb_build_object('generated',true,'process_specification_id',v_group.id,
    'layouts',v_layout_count,'characteristics',v_characteristic_count);
end;
$$;

revoke all on function public.qsms_generate_osp_inspection_layouts(uuid) from public,anon;
grant execute on function public.qsms_generate_osp_inspection_layouts(uuid) to authenticated;

-- -----------------------------------------------------------------------------
-- Process parameter and report views
-- -----------------------------------------------------------------------------
create or replace view public.v_qsms_part_process_parameter_specs
with (security_invoker=true)
as
select
  p.tenant_id,p.id,p.process_specification_id,p.part_id,part.part_number,part.part_name,
  p.process_id,process.process_code,process.process_name,process.process_type,
  p.inward_type,p.inspection_type,p.parameter_name,p.specification_text,p.minimum_spec,p.maximum_spec,
  p.unit,p.characteristic_type,p.checking_method,p.sample_size,p.is_mandatory,p.allow_na,
  p.sequence_no,p.status,p.remarks,p.created_at,p.updated_at,
  group_header.process_specification,group_header.specification_reference,
  group_header.drawing_number,group_header.drawing_revision,group_header.layout_generated_at
from public.part_process_parameter_specifications p
join public.part_process_specifications group_header on group_header.id=p.process_specification_id
join public.parts part on part.id=p.part_id
join public.processes process on process.id=p.process_id;

create or replace view public.v_qsms_osp_parameter_options
with (security_invoker=true)
as
select distinct on (p.tenant_id,p.process_id,p.inspection_type,lower(p.parameter_name))
  p.tenant_id,p.process_id,process.process_code,process.process_name,
  p.inspection_type,p.parameter_name,p.unit,p.characteristic_type,p.checking_method
from public.part_process_parameter_specifications p
join public.processes process on process.id=p.process_id
where p.status='ACTIVE'
order by p.tenant_id,p.process_id,p.inspection_type,lower(p.parameter_name),p.updated_at desc;

create or replace view public.v_qsms_heat_transaction_report
with (security_invoker=true)
as
select
  r.tenant_id,r.normalized_heat_number,r.heat_number,
  pa.part_id,part.part_number,part.part_name,
  pa.updated_at as transaction_at,'RMTC_PLAN'::text as transaction_type,
  r.rmtc_number as transaction_number,r.certificate_reference as reference_number,
  supplier.party_name as party_name,null::text as process_name,
  coalesce(pa.planned_steel_quantity_kg,0) as steel_quantity_kg,
  coalesce(pa.planned_production_quantity_pcs,0) as production_quantity_pcs,
  'PLAN'::text as movement_direction,pa.disposition as transaction_status
from public.rmtc_approvals r
join public.rmtc_part_approvals pa on pa.rmtc_approval_id=r.id
join public.parts part on part.id=pa.part_id
left join public.parties supplier on supplier.id=r.supplier_id
where r.status not in ('REJECTED','SUPERSEDED') and coalesce(r.disposition,'PENDING')<>'REJECTED'
union all
select
  i.tenant_id,upper(regexp_replace(btrim(i.heat_number),'[^A-Za-z0-9]','','g')),i.heat_number,
  i.part_id,part.part_number,part.part_name,
  i.created_at,'MATERIAL_INWARD',i.inward_number,coalesce(i.invoice_number,i.grn_number),
  supplier.party_name,null,
  coalesce(i.steel_quantity_kg,i.required_steel_quantity_kg,i.quantity_received,0),
  coalesce(i.production_quantity_pcs,i.accepted_production_quantity_pcs,0),
  'IN',i.status
from public.inward_lots i
join public.parts part on part.id=i.part_id
left join public.parties supplier on supplier.id=i.supplier_id
union all
select
  o.tenant_id,upper(regexp_replace(btrim(source_batch.heat_number),'[^A-Za-z0-9]','','g')),source_batch.heat_number,
  o.part_id,part.part_number,part.part_name,
  o.created_at,'OSP_OUT',o.osp_job_number,o.dispatch_challan,vendor.party_name,process.process_name,
  coalesce(o.quantity_dispatched,0)*coalesce(nullif(i.input_weight_kg,0),0),
  coalesce(o.quantity_dispatched,0),'OUT',o.status
from public.osp_jobs o
join public.production_batches source_batch on source_batch.id=o.source_batch_id
join public.inward_lots i on i.id=o.source_inward_lot_id
join public.parts part on part.id=o.part_id
join public.parties vendor on vendor.id=o.vendor_id
join public.processes process on process.id=o.process_id
where o.status<>'CANCELLED'
union all
select
  o.tenant_id,upper(regexp_replace(btrim(source_batch.heat_number),'[^A-Za-z0-9]','','g')),source_batch.heat_number,
  o.part_id,part.part_number,part.part_name,
  coalesce(o.receipt_date,o.updated_at),'OSP_INWARD',coalesce(o.receipt_number,o.osp_job_number),
  coalesce(o.vendor_invoice_number,o.tc_number),vendor.party_name,process.process_name,
  coalesce(o.quantity_received,0)*coalesce(nullif(i.input_weight_kg,0),0),
  coalesce(o.quantity_received,0),'IN',o.receipt_quality_disposition
from public.osp_jobs o
join public.production_batches source_batch on source_batch.id=o.source_batch_id
join public.inward_lots i on i.id=o.source_inward_lot_id
join public.parts part on part.id=o.part_id
join public.parties vendor on vendor.id=o.vendor_id
join public.processes process on process.id=o.process_id
where o.status<>'CANCELLED' and coalesce(o.quantity_received,0)>0;

create or replace view public.v_qsms_heat_global_balance_report
with (security_invoker=true)
as
select
  h.*,
  coalesce(osp.osp_out_quantity_pcs,0) as osp_out_quantity_pcs,
  coalesce(osp.osp_inward_quantity_pcs,0) as osp_inward_quantity_pcs,
  greatest(coalesce(osp.osp_out_quantity_pcs,0)-coalesce(osp.osp_inward_quantity_pcs,0),0) as osp_quantity_at_vendor_pcs,
  coalesce(osp.osp_job_count,0) as osp_job_count
from public.v_qsms_heat_summary h
left join (
  select upper(regexp_replace(btrim(source_batch.heat_number),'[^A-Za-z0-9]','','g')) as normalized_heat_number,
    sum(case when o.status<>'CANCELLED' then o.quantity_dispatched else 0 end) as osp_out_quantity_pcs,
    sum(case when o.status<>'CANCELLED' then o.quantity_received else 0 end) as osp_inward_quantity_pcs,
    count(*) filter(where o.status<>'CANCELLED') as osp_job_count
  from public.osp_jobs o join public.production_batches source_batch on source_batch.id=o.source_batch_id
  group by upper(regexp_replace(btrim(source_batch.heat_number),'[^A-Za-z0-9]','','g'))
) osp on osp.normalized_heat_number=h.normalized_heat_number;

create or replace view public.v_qsms_heat_osp_balance_report
with (security_invoker=true)
as
select
  i.tenant_id,i.id as inward_lot_id,i.inward_number,i.inward_date,
  upper(regexp_replace(btrim(i.heat_number),'[^A-Za-z0-9]','','g')) as normalized_heat_number,
  i.heat_number,i.part_id,part.part_number,part.part_name,
  coalesce(nullif(i.accepted_production_quantity_pcs,0),nullif(i.production_quantity_pcs,0),0) as released_quantity_pcs,
  coalesce(sum(o.quantity_dispatched) filter(where o.status<>'CANCELLED'),0) as osp_out_quantity_pcs,
  coalesce(sum(o.quantity_received) filter(where o.status<>'CANCELLED'),0) as osp_inward_quantity_pcs,
  greatest(coalesce(nullif(i.accepted_production_quantity_pcs,0),nullif(i.production_quantity_pcs,0),0)-
    coalesce(sum(o.quantity_dispatched) filter(where o.status<>'CANCELLED'),0),0) as balance_to_send_osp_pcs,
  greatest(coalesce(sum(o.quantity_dispatched) filter(where o.status<>'CANCELLED'),0)-
    coalesce(sum(o.quantity_received) filter(where o.status<>'CANCELLED'),0),0) as quantity_at_osp_vendor_pcs,
  count(o.id) filter(where o.status<>'CANCELLED') as osp_job_count,
  string_agg(distinct process.process_name,', ' order by process.process_name) filter(where o.status<>'CANCELLED') as osp_processes,
  string_agg(distinct vendor.party_name,', ' order by vendor.party_name) filter(where o.status<>'CANCELLED') as osp_vendors,
  max(o.updated_at) as last_osp_activity_at
from public.inward_lots i
join public.parts part on part.id=i.part_id
left join public.osp_jobs o on o.source_inward_lot_id=i.id
left join public.processes process on process.id=o.process_id
left join public.parties vendor on vendor.id=o.vendor_id
where i.status='RELEASED' and i.quality_disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE')
group by i.tenant_id,i.id,i.inward_number,i.inward_date,i.heat_number,i.part_id,part.part_number,part.part_name,
  i.accepted_production_quantity_pcs,i.production_quantity_pcs;

grant select on public.v_qsms_part_process_parameter_specs,public.v_qsms_osp_parameter_options,
  public.v_qsms_heat_transaction_report,public.v_qsms_heat_global_balance_report,
  public.v_qsms_heat_osp_balance_report to authenticated;

grant execute on function public.qsms_delete_document_attachment(uuid) to authenticated;
grant execute on function public.qsms_delete_master_row(text,uuid) to authenticated;

commit;
