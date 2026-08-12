-- QCMS 4.10.1 — Customer Standards & Specification Bank, part-standard linkage,
-- rich selection support and controlled attachment permissions.
begin;

create table if not exists public.customer_standards (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  standard_code text not null,
  standard_name text not null,
  customer_id uuid references public.parties(id) on delete restrict,
  process_id uuid not null references public.processes(id) on delete restrict,
  author_name text,
  revision_number text not null default '00',
  revision_date date,
  status text not null default 'ACTIVE' check (status in ('ACTIVE','INACTIVE','SUPERSEDED')),
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid()
);

create table if not exists public.part_standard_links (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  part_id uuid not null references public.parts(id) on delete cascade,
  standard_id uuid not null references public.customer_standards(id) on delete restrict,
  sequence_no integer not null default 10,
  status text not null default 'ACTIVE' check (status in ('ACTIVE','INACTIVE')),
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique(part_id, standard_id)
);

create unique index if not exists uq_customer_standard_controlled_key
  on public.customer_standards(
    tenant_id,
    coalesce(customer_id,'00000000-0000-0000-0000-000000000000'::uuid),
    process_id,
    lower(btrim(standard_code)),
    lower(btrim(revision_number))
  );
create index if not exists idx_customer_standards_customer_process
  on public.customer_standards(tenant_id,customer_id,process_id,status,standard_name);
create index if not exists idx_part_standard_links_part
  on public.part_standard_links(tenant_id,part_id,sequence_no,status);

-- Automatic STD-0001 style controlled code.
create or replace function public.qsms_next_master_code(p_master_key text)
returns text
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  tid uuid:=public.current_tenant_id();
  master_key text:=lower(btrim(coalesce(p_master_key,'')));
  sequence_name text;
  code_prefix text;
  target_table text;
  next_value bigint;
begin
  if auth.uid() is null or tid is null then raise exception 'An authenticated QCMS session is required'; end if;
  case master_key
    when 'customers' then sequence_name:='MASTER_CUSTOMER';code_prefix:='CUST';target_table:='parties';
    when 'suppliers' then sequence_name:='MASTER_SUPPLIER';code_prefix:='SUP';target_table:='parties';
    when 'steel_mills' then sequence_name:='MASTER_STEEL_MILL';code_prefix:='MILL';target_table:='parties';
    when 'osp_vendors' then sequence_name:='MASTER_OSP_VENDOR';code_prefix:='OSPV';target_table:='parties';
    when 'approved_sources' then sequence_name:='MASTER_APPROVED_SOURCE';code_prefix:='SRC';target_table:='part_supplier_links';
    when 'processes' then sequence_name:='MASTER_PROCESS';code_prefix:='PROC';target_table:='processes';
    when 'inspection_stages' then sequence_name:='MASTER_INSPECTION_STAGE';code_prefix:='STG';target_table:='inspection_stages';
    when 'quality_assets' then sequence_name:='MASTER_QUALITY_ASSET';code_prefix:='AST';target_table:='quality_assets';
    when 'customer_standards' then sequence_name:='MASTER_CUSTOMER_STANDARD';code_prefix:='STD';target_table:='customer_standards';
    else raise exception 'Automatic code generation is not configured for master %',p_master_key;
  end case;
  if not public.can_write_table(target_table) then raise exception 'Create permission is required for this controlled master'; end if;
  insert into public.number_sequences(tenant_id,sequence_code,prefix,year_format,current_value,padding,reset_frequency,last_reset_year)
  values(tid,sequence_name,code_prefix,'NONE',0,4,'NEVER',null)
  on conflict (tenant_id,sequence_code) do nothing;
  update public.number_sequences
  set current_value=current_value+1,updated_at=now(),updated_by=auth.uid()
  where tenant_id=tid and sequence_code=sequence_name
  returning current_value into next_value;
  return code_prefix||'-'||lpad(next_value::text,4,'0');
end;
$$;
revoke all on function public.qsms_next_master_code(text) from public,anon;
grant execute on function public.qsms_next_master_code(text) to authenticated;

create or replace function public.qsms_module_for_table(target_table text) returns text
language sql immutable set search_path=public as $$
select case
 when target_table in ('parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_rmtc_requirements','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','part_standard_links','document_attachments') then 'PART_MASTER'
 when target_table in ('material_grades','material_grade_elements') then 'MATERIAL_GRADE'
 when target_table in ('parties','part_supplier_links','processes','inspection_stages','quality_assets','jominy_distances','master_value_catalog','standards_register','calculation_rules','customer_standards') then 'REFERENCE_MASTERS'
 when target_table='employees' then 'EMPLOYEE_MASTER'
 when target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results','rmtc_decision_revisions') then 'RMTC_ENTRY'
 when target_table='inward_lots' then 'MATERIAL_INWARD'
 when target_table in ('production_batches','batch_movements','osp_jobs') then 'OSP_TRANSACTIONS'
 when target_table in ('inspection_plans','inspection_plan_characteristics','test_plans') then 'INSPECTION_LAYOUTS'
 when target_table in ('inspection_reports','inspection_results') then 'DIMENSIONAL_REPORT'
 when target_table='lab_tests' then 'METLAB_REPORT'
 when target_table in ('npd_process_flows','npd_process_flow_steps','npd_process_flow_points','npd_orders','npd_order_steps','npd_order_step_points','ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items','control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings','msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics') then 'NPD_APQP'
 when target_table='qc_calculation_records' then 'QC_CALCULATION_TOOLS'
 when target_table='user_module_permissions' then 'USER_ACCESS'
 else upper(target_table) end;
$$;

create or replace function public.can_write_table(target_table text) returns boolean
language plpgsql stable security definer set search_path=public,auth as $$
declare role_name text:=coalesce(public.current_app_role(),'VIEWER');
begin
 if role_name='ADMIN' then return true; end if;
 if public.qsms_has_module_write(target_table) then return true; end if;
 if target_table in ('parties','material_grades','material_grade_elements','parts','part_supplier_links','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_rmtc_requirements','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','part_standard_links','processes','inspection_stages','master_value_catalog','customer_standards') then return role_name in ('QUALITY_MANAGER','MASTER_DATA');
 elsif target_table in ('employees','quality_assets') then return role_name in ('QUALITY_MANAGER','MASTER_DATA','QUALITY_ENGINEER');
 elsif target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results','rmtc_decision_revisions') then return role_name in ('QUALITY_MANAGER','METLAB_APPROVER','SQA');
 elsif target_table='inward_lots' then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION');
 elsif target_table in ('production_batches','batch_movements','osp_jobs') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION');
 elsif target_table in ('inspection_plans','inspection_plan_characteristics','test_plans') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA');
 elsif target_table in ('inspection_reports','inspection_results') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA');
 elsif target_table='lab_tests' then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER');
 elsif target_table in ('npd_process_flows','npd_process_flow_steps','npd_process_flow_points','npd_orders','npd_order_steps','npd_order_step_points','ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items','control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings','msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA','SQA','PRODUCTION');
 elsif target_table='qc_calculation_records' then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER','SQA');
 end if;
 return false;
end;
$$;

-- Tenant isolation and audit controls for new tables.
do $$
declare table_name text;
begin
 foreach table_name in array array['customer_standards','part_standard_links'] loop
  execute format('drop trigger if exists trg_touch_updated_at on public.%I', table_name);
  execute format('create trigger trg_touch_updated_at before update on public.%I for each row execute function public.touch_updated_at()', table_name);
  execute format('drop trigger if exists trg_audit_row_change on public.%I', table_name);
  execute format('create trigger trg_audit_row_change after insert or update or delete on public.%I for each row execute function public.log_row_change()', table_name);
  execute format('alter table public.%I enable row level security', table_name);
  execute format('drop policy if exists tenant_select on public.%I', table_name);
  execute format('drop policy if exists tenant_insert on public.%I', table_name);
  execute format('drop policy if exists tenant_update on public.%I', table_name);
  execute format('drop policy if exists tenant_delete on public.%I', table_name);
  execute format('create policy tenant_select on public.%I for select to authenticated using (tenant_id=public.current_tenant_id())', table_name);
  execute format('create policy tenant_insert on public.%I for insert to authenticated with check (tenant_id=public.current_tenant_id() and public.can_write_table(%L))', table_name, table_name);
  execute format('create policy tenant_update on public.%I for update to authenticated using (tenant_id=public.current_tenant_id() and public.can_write_table(%L)) with check (tenant_id=public.current_tenant_id() and public.can_write_table(%L))', table_name, table_name, table_name);
  execute format('create policy tenant_delete on public.%I for delete to authenticated using (tenant_id=public.current_tenant_id() and public.can_write_table(%L))', table_name, table_name);
 end loop;
end;
$$;

-- Standards use Reference Master permissions for attachment upload/replace/delete.
create or replace function public.qsms_attachment_module(p_entity_type text)
returns text language sql immutable set search_path=public as $$
select case upper(coalesce(p_entity_type, ''))
  when 'RMTC' then 'RMTC_ENTRY'
  when 'MATERIAL_INWARD' then 'MATERIAL_INWARD'
  when 'PART_MASTER' then 'PART_MASTER'
  when 'PART_PROCESS_SPEC' then 'PART_MASTER'
  when 'CUSTOMER_STANDARD' then 'REFERENCE_MASTERS'
  when 'DIMENSIONAL_REPORT' then 'DIMENSIONAL_REPORT'
  when 'METLAB_REPORT' then 'METLAB_REPORT'
  else null
end;
$$;

-- Extend permanent-delete RPC to the new standard/link records.
create or replace function public.qsms_delete_master_row(p_table_name text,p_record_id uuid)
returns jsonb language plpgsql security definer set search_path=public,auth as $$
declare
 tid uuid:=public.current_tenant_id();
 role_name text:=coalesce(public.current_app_role(),'VIEWER');
 module_name text:=public.qsms_module_for_table(p_table_name);
 allowed boolean:=false;
 deleted_count integer:=0;
 allowed_tables constant text[]:=array[
  'parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_rmtc_requirements',
  'part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','part_standard_links',
  'material_grades','material_grade_elements','parties','part_supplier_links','processes','inspection_stages',
  'quality_assets','jominy_distances','master_value_catalog','standards_register','calculation_rules','customer_standards',
  'inspection_plans','inspection_plan_characteristics','test_plans','employees','document_attachments',
  'rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results','rmtc_decision_revisions',
  'inward_lots','inspection_reports','inspection_results','lab_tests','production_batches','batch_movements','osp_jobs',
  'npd_process_flows','npd_process_flow_steps','npd_process_flow_points','npd_orders','npd_order_steps','npd_order_step_points',
  'ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items',
  'control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings',
  'msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics','qc_calculation_records'
 ];
begin
 if auth.uid() is null then raise exception 'Authentication required'; end if;
 if p_table_name is null or not (p_table_name=any(allowed_tables)) then raise exception 'Deletion is not allowed for this table'; end if;
 allowed:=role_name='ADMIN' or exists(
   select 1 from public.user_module_permissions p
   where p.tenant_id=tid and p.profile_id=auth.uid() and p.module_key=module_name
     and p.can_view and p.can_archive
 );
 if not allowed then raise exception 'Delete permission is not assigned for this module'; end if;
 execute format('delete from public.%I where id=$1 and tenant_id=$2',p_table_name) using p_record_id,tid;
 get diagnostics deleted_count=row_count;
 if deleted_count=0 then raise exception 'The selected row was not found or is outside your company tenant'; end if;
 return jsonb_build_object('deleted',true,'table',p_table_name,'id',p_record_id);
exception when foreign_key_violation then
 raise exception 'This record is linked to another master or transaction. Delete/unlink the dependent record first, or deactivate the master instead.';
end;
$$;
revoke all on function public.qsms_delete_master_row(text,uuid) from public,anon;
grant execute on function public.qsms_delete_master_row(text,uuid) to authenticated;

-- Reference-master archive permission may delete the private standards file.
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
      and exists(select 1 from public.user_module_permissions p where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid() and p.module_key='PART_MASTER' and p.can_view and p.can_archive)
    )
    or (
      (storage.foldername(name))[2]='customer_standards'
      and exists(select 1 from public.user_module_permissions p where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid() and p.module_key='REFERENCE_MASTERS' and p.can_view and p.can_archive)
    )
    or (
      (storage.foldername(name))[2]='rmtc'
      and exists(select 1 from public.user_module_permissions p where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid() and p.module_key='RMTC_ENTRY' and p.can_view and p.can_archive)
    )
    or (
      (storage.foldername(name))[2]='inward'
      and exists(select 1 from public.user_module_permissions p where p.tenant_id=public.current_tenant_id() and p.profile_id=auth.uid() and p.module_key='MATERIAL_INWARD' and p.can_view and p.can_archive)
    )
  )
);

commit;
