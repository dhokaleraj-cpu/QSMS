-- QSMS 4.6.0 sequence permission and delete allow-list updates.
create or replace function public.qsms_next_document_number(p_sequence_code text) returns text language plpgsql security definer set search_path=public,auth as $$
declare v_tenant uuid:=public.current_tenant_id();v_row public.number_sequences%rowtype;v_year integer:=extract(year from current_date)::integer;v_year_text text;v_next bigint;v_target_table text;
begin
 if auth.uid() is null or v_tenant is null then raise exception 'An authenticated QSMS session is required';end if;
 v_target_table:=case upper(p_sequence_code) when 'INWARD' then 'inward_lots' when 'DIMENSIONAL_REPORT' then 'inspection_reports' when 'METLAB_REPORT' then 'lab_tests' else 'rmtc_approvals' end;
 if not public.can_write_table(v_target_table) then raise exception 'Your QSMS role cannot create this controlled document number';end if;
 select * into v_row from public.number_sequences where tenant_id=v_tenant and upper(sequence_code)=upper(p_sequence_code) for update;
 if v_row.id is null then raise exception 'Document number sequence % is not configured',p_sequence_code;end if;
 if coalesce(v_row.reset_frequency,'YEARLY')='YEARLY' and coalesce(v_row.last_reset_year,0)<>v_year then v_row.current_value:=0;v_row.last_reset_year:=v_year;end if;
 v_next:=v_row.current_value+1;update public.number_sequences set current_value=v_next,last_reset_year=v_row.last_reset_year,updated_at=now(),updated_by=auth.uid() where id=v_row.id;
 v_year_text:=case upper(coalesce(v_row.year_format,'YYYY')) when 'YY' then right(v_year::text,2) when 'NONE' then null else v_year::text end;
 return concat_ws('-',v_row.prefix,v_year_text,lpad(v_next::text,v_row.padding,'0'));
end;$$;

create or replace function public.qsms_delete_master_row(p_table_name text,p_record_id uuid) returns jsonb language plpgsql security definer set search_path=public,auth as $$
declare tid uuid:=public.current_tenant_id();role_name text:=coalesce(public.current_app_role(),'VIEWER');module_name text:=public.qsms_module_for_table(p_table_name);allowed boolean:=false;deleted_count integer:=0;allowed_tables constant text[]:=array['parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','material_grades','material_grade_elements','parties','part_supplier_links','processes','inspection_stages','quality_assets','inspection_plans','inspection_plan_characteristics','test_plans','employees','document_attachments','rmtc_approvals','inward_lots','inspection_reports','inspection_results','lab_tests'];
begin
 if auth.uid() is null then raise exception 'Authentication required';end if;
 if p_table_name is null or not(p_table_name=any(allowed_tables)) then raise exception 'Deletion is not allowed for this table';end if;
 allowed:=role_name='ADMIN' or exists(select 1 from public.user_module_permissions p where p.tenant_id=tid and p.profile_id=auth.uid() and p.module_key=module_name and p.can_view and p.can_archive);
 if not allowed then raise exception 'Delete permission is not assigned for this module';end if;
 execute format('delete from public.%I where id=$1 and tenant_id=$2',p_table_name) using p_record_id,tid;get diagnostics deleted_count=row_count;
 if deleted_count=0 then raise exception 'The selected row was not found or is outside your company tenant';end if;
 return jsonb_build_object('deleted',true,'table',p_table_name,'id',p_record_id);
exception when foreign_key_violation then raise exception 'This record is linked to another master or transaction. Deactivate it instead of deleting it.';
end;$$;
revoke all on function public.qsms_next_document_number(text) from public,anon;
revoke all on function public.qsms_delete_master_row(text,uuid) from public,anon;
grant execute on function public.qsms_next_document_number(text) to authenticated;
grant execute on function public.qsms_delete_master_row(text,uuid) to authenticated;
