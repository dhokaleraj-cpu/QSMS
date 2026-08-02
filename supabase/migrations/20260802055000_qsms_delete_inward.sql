-- Allow password-verified deletion of Material Inward transactions for users
-- explicitly granted Material Inward Delete permission. FK-linked production data blocks deletion.
begin;

create or replace function public.qsms_delete_master_row(p_table_name text, p_record_id uuid)
returns jsonb
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  tid uuid:=public.current_tenant_id();
  role_name text:=coalesce(public.current_app_role(),'VIEWER');
  module_name text:=public.qsms_module_for_table(p_table_name);
  allowed boolean:=false;
  deleted_count integer:=0;
  allowed_tables constant text[]:=array[
    'parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details',
    'material_grades','material_grade_elements','parties','part_supplier_links','processes',
    'inspection_stages','quality_assets','inspection_plans','inspection_plan_characteristics',
    'test_plans','employees','document_attachments','inward_lots'
  ];
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  if p_table_name is null or not (p_table_name=any(allowed_tables)) then
    raise exception 'Deletion is not allowed for this table';
  end if;
  allowed:=role_name='ADMIN' or exists(
    select 1 from public.user_module_permissions p
    where p.tenant_id=tid and p.profile_id=auth.uid()
      and p.module_key=module_name and p.can_view=true and p.can_archive=true
  );
  if not allowed then raise exception 'Delete permission is not assigned for this module'; end if;
  execute format('delete from public.%I where id=$1 and tenant_id=$2',p_table_name) using p_record_id,tid;
  get diagnostics deleted_count=row_count;
  if deleted_count=0 then raise exception 'The selected row was not found or is outside your company tenant'; end if;
  return jsonb_build_object('deleted',true,'table',p_table_name,'id',p_record_id);
exception when foreign_key_violation then
  raise exception 'This record is linked to another master or transaction. Deactivate or close it instead of deleting it.';
end;
$$;

commit;
