-- QCMS 4.10.7 — Detailed Customer/Supplier Complaint Analysis, Action Ownership and effectiveness closure.
begin;

alter table public.quality_complaints add column if not exists process_id uuid references public.processes(id) on delete restrict;
alter table public.quality_complaints add column if not exists defect_mode text;
alter table public.quality_complaints add column if not exists lot_batch_number text;
alter table public.quality_complaints add column if not exists heat_number text;
alter table public.quality_complaints add column if not exists problem_what text;
alter table public.quality_complaints add column if not exists problem_where text;
alter table public.quality_complaints add column if not exists problem_when text;
alter table public.quality_complaints add column if not exists detection_point text;
alter table public.quality_complaints add column if not exists occurrence_pattern text;
alter table public.quality_complaints add column if not exists impact_summary text;
alter table public.quality_complaints add column if not exists immediate_correction text;
alter table public.quality_complaints add column if not exists containment_responsible_employee_id uuid references public.employees(id) on delete restrict;
alter table public.quality_complaints add column if not exists containment_due_date date;
alter table public.quality_complaints add column if not exists containment_completed_date date;
alter table public.quality_complaints add column if not exists containment_effectiveness text;
alter table public.quality_complaints add column if not exists analysis_method text;
alter table public.quality_complaints add column if not exists why_1 text;
alter table public.quality_complaints add column if not exists why_2 text;
alter table public.quality_complaints add column if not exists why_3 text;
alter table public.quality_complaints add column if not exists why_4 text;
alter table public.quality_complaints add column if not exists why_5 text;
alter table public.quality_complaints add column if not exists occurrence_root_cause text;
alter table public.quality_complaints add column if not exists escape_root_cause text;
alter table public.quality_complaints add column if not exists systemic_root_cause text;
alter table public.quality_complaints add column if not exists root_cause_evidence text;
alter table public.quality_complaints add column if not exists root_cause_confirmed boolean not null default false;
alter table public.quality_complaints add column if not exists root_cause_confirmed_date date;
alter table public.quality_complaints add column if not exists root_cause_responsible_employee_id uuid references public.employees(id) on delete restrict;
alter table public.quality_complaints add column if not exists verification_plan text;
alter table public.quality_complaints add column if not exists effectiveness_criteria text;
alter table public.quality_complaints add column if not exists effectiveness_verified boolean not null default false;
alter table public.quality_complaints add column if not exists effectiveness_verified_date date;
alter table public.quality_complaints add column if not exists effectiveness_verified_by_employee_id uuid references public.employees(id) on delete restrict;
alter table public.quality_complaints add column if not exists recurrence_check_result text;
alter table public.quality_complaints add column if not exists closure_approved_by_employee_id uuid references public.employees(id) on delete restrict;
alter table public.quality_complaints add column if not exists closure_approved_date date;

create table if not exists public.quality_complaint_actions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id),
  complaint_id uuid not null references public.quality_complaints(id) on delete cascade,
  action_no integer not null,
  action_type text not null check (action_type in ('CORRECTION','CONTAINMENT','OCCURRENCE_CORRECTIVE','ESCAPE_CORRECTIVE','SYSTEMIC_PREVENTIVE','VERIFICATION')),
  action_description text not null,
  owner_employee_id uuid references public.employees(id) on delete restrict,
  external_owner_name text,
  target_date date,
  completion_date date,
  status text not null default 'OPEN' check (status in ('OPEN','IN_PROGRESS','COMPLETED','CANCELLED')),
  evidence text,
  effectiveness_result text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  updated_by uuid default auth.uid(),
  unique(tenant_id, complaint_id, action_no)
);

create index if not exists idx_quality_complaint_actions_status on public.quality_complaint_actions(tenant_id, complaint_id, status, target_date);

drop trigger if exists trg_touch_updated_at on public.quality_complaint_actions;
create trigger trg_touch_updated_at before update on public.quality_complaint_actions for each row execute function public.touch_updated_at();
drop trigger if exists trg_audit_row_change on public.quality_complaint_actions;
create trigger trg_audit_row_change after insert or update or delete on public.quality_complaint_actions for each row execute function public.log_row_change();

alter table public.quality_complaint_actions enable row level security;
drop policy if exists tenant_select on public.quality_complaint_actions;
drop policy if exists tenant_insert on public.quality_complaint_actions;
drop policy if exists tenant_update on public.quality_complaint_actions;
drop policy if exists tenant_delete on public.quality_complaint_actions;
create policy tenant_select on public.quality_complaint_actions for select to authenticated using (tenant_id=public.current_tenant_id());
create policy tenant_insert on public.quality_complaint_actions for insert to authenticated with check (tenant_id=public.current_tenant_id() and public.can_write_table('quality_complaints'));
create policy tenant_update on public.quality_complaint_actions for update to authenticated using (tenant_id=public.current_tenant_id() and public.can_write_table('quality_complaints')) with check (tenant_id=public.current_tenant_id() and public.can_write_table('quality_complaints'));
create policy tenant_delete on public.quality_complaint_actions for delete to authenticated using (tenant_id=public.current_tenant_id() and public.can_write_table('quality_complaints'));

-- Complaint documents use Complaint Management permissions.
create or replace function public.qsms_attachment_module(p_entity_type text)
returns text language sql immutable set search_path=public as $$
select case upper(coalesce(p_entity_type, ''))
  when 'RMTC' then 'RMTC_ENTRY'
  when 'MATERIAL_INWARD' then 'MATERIAL_INWARD'
  when 'PART_MASTER' then 'PART_MASTER'
  when 'PART_PROCESS_SPEC' then 'PART_MASTER'
  when 'CUSTOMER_STANDARD' then 'REFERENCE_MASTERS'
  when 'QUALITY_COMPLAINT' then 'COMPLAINT_MANAGEMENT'
  when 'DIMENSIONAL_REPORT' then 'DIMENSIONAL_REPORT'
  when 'METLAB_REPORT' then 'METLAB_REPORT'
  else null
end;
$$;

-- Add detailed action records to the controlled delete service.
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
  'qc_calculation_records','quality_complaints','quality_complaint_followups','quality_complaint_actions'
 ];
begin
 if auth.uid() is null then raise exception 'Authentication required'; end if;
 if p_table_name is null or not (p_table_name=any(allowed_tables)) then raise exception 'Deletion is not allowed for this table'; end if;
 if p_table_name='quality_complaint_actions' then module_name:='COMPLAINT_MANAGEMENT'; end if;
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

-- Database-level closure guard: quality closure needs confirmed RCA and verified effectiveness.
create or replace function public.qcms_guard_complaint_closure()
returns trigger language plpgsql set search_path=public as $$
begin
  if new.status='CLOSED' then
    if not coalesce(new.root_cause_confirmed,false) then
      raise exception 'Root cause must be confirmed before Complaint closure';
    end if;
    if not coalesce(new.effectiveness_verified,false) then
      raise exception 'Corrective action effectiveness must be verified before Complaint closure';
    end if;
    if new.closure_date is null then
      raise exception 'Actual Closure Date is required before Complaint closure';
    end if;
    if exists(select 1 from public.quality_complaint_actions a where a.tenant_id=new.tenant_id and a.complaint_id=new.id and a.status not in ('COMPLETED','CANCELLED')) then
      raise exception 'All Complaint action-plan items must be completed or cancelled before closure';
    end if;
  end if;
  return new;
end;
$$;
drop trigger if exists trg_qcms_guard_complaint_closure on public.quality_complaints;
create trigger trg_qcms_guard_complaint_closure before insert or update of status,root_cause_confirmed,effectiveness_verified,closure_date on public.quality_complaints for each row execute function public.qcms_guard_complaint_closure();

commit;
