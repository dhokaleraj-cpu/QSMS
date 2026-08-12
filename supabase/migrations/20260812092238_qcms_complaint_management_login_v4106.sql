-- QCMS 4.10.6 — Customer/Supplier Complaint Management and controlled follow-up tracking.
begin;

create table if not exists public.quality_complaints (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  complaint_number text not null,
  complaint_type text not null check (complaint_type in ('CUSTOMER','SUPPLIER')),
  complaint_date date not null default current_date,
  party_id uuid not null references public.parties(id) on delete restrict,
  part_id uuid references public.parts(id) on delete restrict,
  external_reference text,
  subject text not null,
  description text not null,
  affected_quantity numeric not null default 0 check (affected_quantity >= 0),
  severity text not null default 'MEDIUM' check (severity in ('LOW','MEDIUM','HIGH','CRITICAL')),
  fourstar_responsible_employee_id uuid references public.employees(id) on delete restrict,
  external_responsible_name text,
  external_responsible_email text,
  external_responsible_phone text,
  target_closure_date date,
  status text not null default 'OPEN' check (status in ('OPEN','CONTAINMENT','ROOT_CAUSE','CORRECTIVE_ACTION','VERIFICATION','CLOSED','CANCELLED')),
  containment_action text,
  root_cause text,
  corrective_action text,
  verification_result text,
  closure_date date,
  closure_remarks text,
  debit_note_required boolean not null default false,
  debit_note_status text not null default 'NOT_REQUIRED' check (debit_note_status in ('NOT_REQUIRED','PENDING','RELEASED','PARTIALLY_SETTLED','SETTLED','WAIVED')),
  debit_note_number text,
  debit_note_date date,
  debit_note_amount numeric not null default 0 check (debit_note_amount >= 0),
  currency text not null default 'INR',
  debit_note_settled_amount numeric not null default 0 check (debit_note_settled_amount >= 0),
  debit_note_settled_date date,
  commercial_remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique(tenant_id, complaint_number)
);

create table if not exists public.quality_complaint_followups (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  complaint_id uuid not null references public.quality_complaints(id) on delete cascade,
  followup_date date not null default current_date,
  followup_type text not null default 'FOLLOW_UP' check (followup_type in ('FOLLOW_UP','CUSTOMER_UPDATE','SUPPLIER_UPDATE','INTERNAL_REVIEW','COMMERCIAL','CLOSURE_REVIEW')),
  remarks text not null,
  next_followup_date date,
  responsible_employee_id uuid references public.employees(id) on delete restrict,
  status_after_followup text check (status_after_followup is null or status_after_followup in ('OPEN','CONTAINMENT','ROOT_CAUSE','CORRECTIVE_ACTION','VERIFICATION','CLOSED','CANCELLED')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid()
);

create index if not exists idx_quality_complaints_type_status on public.quality_complaints(tenant_id, complaint_type, status, target_closure_date);
create index if not exists idx_quality_complaints_party on public.quality_complaints(tenant_id, party_id, complaint_date desc);
create index if not exists idx_quality_complaint_followups on public.quality_complaint_followups(tenant_id, complaint_id, followup_date desc);

-- Complaint numbering: CC-YYYY-00001 / SC-YYYY-00001.
create or replace function public.qcms_next_complaint_number(p_complaint_type text)
returns text
language plpgsql
security definer
set search_path=public,auth
as $$
declare
  tid uuid:=public.current_tenant_id();
  ctype text:=upper(btrim(coalesce(p_complaint_type,'')));
  seq_code text;
  prefix_text text;
  v_year integer:=extract(year from current_date)::integer;
  v_next bigint;
begin
  if auth.uid() is null or tid is null then raise exception 'An authenticated QCMS session is required'; end if;
  if ctype='CUSTOMER' then seq_code:='CUSTOMER_COMPLAINT'; prefix_text:='CC';
  elsif ctype='SUPPLIER' then seq_code:='SUPPLIER_COMPLAINT'; prefix_text:='SC';
  else raise exception 'Complaint type must be CUSTOMER or SUPPLIER'; end if;
  if not public.can_write_table('quality_complaints') then raise exception 'Create permission is required for Complaint Management'; end if;
  insert into public.number_sequences(tenant_id,sequence_code,prefix,year_format,current_value,padding,reset_frequency,last_reset_year)
  values(tid,seq_code,prefix_text,'YYYY',0,5,'YEARLY',v_year)
  on conflict (tenant_id,sequence_code) do nothing;
  update public.number_sequences
     set current_value=case when coalesce(last_reset_year,0)<>v_year then 1 else current_value+1 end,
         last_reset_year=v_year, updated_at=now(), updated_by=auth.uid()
   where tenant_id=tid and sequence_code=seq_code
   returning current_value into v_next;
  return prefix_text||'-'||v_year::text||'-'||lpad(v_next::text,5,'0');
end;
$$;
revoke all on function public.qcms_next_complaint_number(text) from public,anon;
grant execute on function public.qcms_next_complaint_number(text) to authenticated;

create or replace function public.qsms_module_for_table(target_table text) returns text
language sql immutable set search_path=public as $$
select case
 when target_table in ('parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_rmtc_requirements','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','document_attachments','part_standard_links') then 'PART_MASTER'
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
 when target_table in ('quality_complaints','quality_complaint_followups') then 'COMPLAINT_MANAGEMENT'
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
 elsif target_table in ('quality_complaints','quality_complaint_followups') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION');
 end if;
 return false;
end;
$$;

-- Tenant isolation, audit and update timestamps.
do $$
declare table_name text;
begin
 foreach table_name in array array['quality_complaints','quality_complaint_followups'] loop
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

create or replace function public.qsms_delete_master_row(p_table_name text,p_record_id uuid)
returns jsonb language plpgsql security definer set search_path=public,auth as $$
declare
 tid uuid:=public.current_tenant_id(); role_name text:=coalesce(public.current_app_role(),'VIEWER');
 module_name text:=public.qsms_module_for_table(p_table_name); allowed boolean:=false; deleted_count integer:=0;
 allowed_tables constant text[]:=array[
  'parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','part_rmtc_requirements','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','part_standard_links',
  'material_grades','material_grade_elements','parties','part_supplier_links','processes','inspection_stages','quality_assets','jominy_distances','master_value_catalog','standards_register','calculation_rules','customer_standards',
  'inspection_plans','inspection_plan_characteristics','test_plans','employees','document_attachments','rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results','rmtc_decision_revisions',
  'inward_lots','inspection_reports','inspection_results','lab_tests','production_batches','batch_movements','osp_jobs',
  'npd_process_flows','npd_process_flow_steps','npd_process_flow_points','npd_orders','npd_order_steps','npd_order_step_points','ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items','control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings','msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics',
  'qc_calculation_records','quality_complaints','quality_complaint_followups'
 ];
begin
 if auth.uid() is null then raise exception 'Authentication required'; end if;
 if p_table_name is null or not (p_table_name=any(allowed_tables)) then raise exception 'Deletion is not allowed for this table'; end if;
 allowed:=role_name='ADMIN' or exists(select 1 from public.user_module_permissions p where p.tenant_id=tid and p.profile_id=auth.uid() and p.module_key=module_name and p.can_view and p.can_archive);
 if not allowed then raise exception 'Delete permission is not assigned for this module'; end if;
 execute format('delete from public.%I where id=$1 and tenant_id=$2',p_table_name) using p_record_id,tid;
 get diagnostics deleted_count=row_count;
 if deleted_count=0 then raise exception 'The selected row was not found or is outside your company tenant'; end if;
 return jsonb_build_object('deleted',true,'table',p_table_name,'id',p_record_id);
exception when foreign_key_violation then
 raise exception 'This record is linked to another master or transaction. Delete the linked child record first, or deactivate the record instead.';
end;
$$;
revoke all on function public.qsms_delete_master_row(text,uuid) from public,anon;
grant execute on function public.qsms_delete_master_row(text,uuid) to authenticated;

commit;
