-- QCMS 4.9.9 — universal controlled delete coverage, Material Grade numbering and RMTC/Jominy reliability.
begin;

-- Material Grade records now use the same controlled automatic serial pattern as other masters.
insert into public.number_sequences(tenant_id,sequence_code,prefix,year_format,current_value,padding,reset_frequency,last_reset_year)
select t.id,'MASTER_MATERIAL_GRADE','MAT','NONE',
       coalesce((select max(substring(m.material_number from '([0-9]+)$')::bigint)
                 from public.material_grades m
                 where m.tenant_id=t.id and m.material_number~'^MAT-[0-9]+$'),0),
       4,'NEVER',null
from public.tenants t
on conflict (tenant_id,sequence_code) do update
set prefix='MAT',year_format='NONE',padding=4,reset_frequency='NEVER',
    current_value=greatest(public.number_sequences.current_value,excluded.current_value),updated_at=now();

-- Preserve valid referenced grades that pre-date automatic numbering by assigning a serial instead of deleting them.
with ranked as (
  select m.id,m.tenant_id,
         row_number() over(partition by m.tenant_id order by m.created_at,m.id) as rn
  from public.material_grades m
  where nullif(btrim(coalesce(m.material_number,'')),'') is null
), base as (
  select tenant_id,current_value from public.number_sequences where sequence_code='MASTER_MATERIAL_GRADE'
)
update public.material_grades m
set material_number='MAT-'||lpad((b.current_value+r.rn)::text,4,'0'),updated_at=now()
from ranked r join base b on b.tenant_id=r.tenant_id
where m.id=r.id;

update public.number_sequences s
set current_value=greatest(s.current_value,coalesce(x.max_no,0)),updated_at=now()
from (
  select tenant_id,max(substring(material_number from '([0-9]+)$')::bigint) max_no
  from public.material_grades
  where material_number~'^MAT-[0-9]+$'
  group by tenant_id
) x
where s.tenant_id=x.tenant_id and s.sequence_code='MASTER_MATERIAL_GRADE';

create unique index if not exists uq_material_grades_material_number_ci
  on public.material_grades(tenant_id,lower(btrim(material_number)))
  where nullif(btrim(coalesce(material_number,'')),'') is not null;

create or replace function public.qcms_next_material_number()
returns text
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  tid uuid:=public.current_tenant_id();
  next_value bigint;
begin
  if auth.uid() is null or tid is null then raise exception 'An authenticated QCMS session is required'; end if;
  if not public.can_write_table('material_grades') then raise exception 'Create permission is required for Material Grade Master'; end if;
  insert into public.number_sequences(tenant_id,sequence_code,prefix,year_format,current_value,padding,reset_frequency,last_reset_year)
  values(tid,'MASTER_MATERIAL_GRADE','MAT','NONE',0,4,'NEVER',null)
  on conflict (tenant_id,sequence_code) do nothing;
  update public.number_sequences
  set current_value=current_value+1,updated_at=now(),updated_by=auth.uid()
  where tenant_id=tid and sequence_code='MASTER_MATERIAL_GRADE'
  returning current_value into next_value;
  return 'MAT-'||lpad(next_value::text,4,'0');
end;
$$;
revoke all on function public.qcms_next_material_number() from public,anon;
grant execute on function public.qcms_next_material_number() to authenticated;

-- Extend the existing password-protected deletion RPC to every user-facing controlled root record.
create or replace function public.qsms_delete_master_row(p_table_name text,p_record_id uuid)
returns jsonb language plpgsql security definer set search_path=public,auth as $$
declare
 tid uuid:=public.current_tenant_id();
 role_name text:=coalesce(public.current_app_role(),'VIEWER');
 module_name text:=public.qsms_module_for_table(p_table_name);
 allowed boolean:=false;
 deleted_count integer:=0;
 allowed_tables constant text[]:=array[
  'parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details',
  'part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements',
  'material_grades','material_grade_elements','parties','part_supplier_links','processes','inspection_stages',
  'quality_assets','inspection_plans','inspection_plan_characteristics','test_plans','employees','document_attachments',
  'rmtc_approvals','inward_lots','inspection_reports','inspection_results','lab_tests','osp_jobs',
  'npd_process_flows','npd_process_flow_steps','npd_process_flow_points',
  'npd_orders','npd_order_steps','npd_order_step_points',
  'ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items',
  'control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings',
  'msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics',
  'qc_calculation_records'
 ];
begin
 if auth.uid() is null then raise exception 'Authentication required';end if;
 if p_table_name is null or not(p_table_name=any(allowed_tables)) then raise exception 'Deletion is not allowed for this table';end if;
 allowed:=role_name='ADMIN' or exists(
   select 1 from public.user_module_permissions p
   where p.tenant_id=tid and p.profile_id=auth.uid() and p.module_key=module_name and p.can_view and p.can_archive
 );
 if not allowed then raise exception 'Delete permission is not assigned for this module';end if;
 execute format('delete from public.%I where id=$1 and tenant_id=$2',p_table_name) using p_record_id,tid;
 get diagnostics deleted_count=row_count;
 if deleted_count=0 then raise exception 'The selected row was not found or is outside your company tenant';end if;
 return jsonb_build_object('deleted',true,'table',p_table_name,'id',p_record_id);
exception when foreign_key_violation then
 raise exception 'This record is linked to another master or transaction. Delete the linked child record first, or deactivate the master instead.';
end;
$$;
revoke all on function public.qsms_delete_master_row(text,uuid) from public,anon;
grant execute on function public.qsms_delete_master_row(text,uuid) to authenticated;

commit;
