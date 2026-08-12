-- QCMS 4.10.0 — complete controlled-delete coverage and permission routing.
-- Password verification remains in the signed-in application before this RPC is called.
begin;

create or replace function public.qsms_module_for_table(target_table text) returns text
language sql immutable set search_path=public as $$
select case
 when target_table in ('parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_rmtc_requirements','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','document_attachments') then 'PART_MASTER'
 when target_table in ('material_grades','material_grade_elements') then 'MATERIAL_GRADE'
 when target_table in ('parties','part_supplier_links','processes','inspection_stages','quality_assets','jominy_distances','master_value_catalog','standards_register','calculation_rules') then 'REFERENCE_MASTERS'
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
  'part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements',
  'material_grades','material_grade_elements','parties','part_supplier_links','processes','inspection_stages',
  'quality_assets','jominy_distances','master_value_catalog','standards_register','calculation_rules',
  'inspection_plans','inspection_plan_characteristics','test_plans','employees','document_attachments',
  'rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results','rmtc_decision_revisions',
  'inward_lots','inspection_reports','inspection_results','lab_tests','production_batches','batch_movements','osp_jobs',
  'npd_process_flows','npd_process_flow_steps','npd_process_flow_points','npd_orders','npd_order_steps','npd_order_step_points',
  'ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items',
  'control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings',
  'msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics',
  'qc_calculation_records'
 ];
begin
 if auth.uid() is null then raise exception 'Authentication required'; end if;
 if p_table_name is null or not (p_table_name=any(allowed_tables)) then
   raise exception 'Deletion is not allowed for this table';
 end if;
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
 raise exception 'This record is linked to another master or transaction. Delete the linked child record first, or deactivate the master instead.';
end;
$$;
revoke all on function public.qsms_delete_master_row(text,uuid) from public,anon;
grant execute on function public.qsms_delete_master_row(text,uuid) to authenticated;

commit;
