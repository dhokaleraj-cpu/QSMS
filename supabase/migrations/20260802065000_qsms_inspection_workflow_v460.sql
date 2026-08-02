-- QSMS 4.6.0 inspection layout master and post-inward validation workflow.
begin;

alter table public.inspection_plans
  add column if not exists layout_type text not null default 'DIMENSIONAL',
  add column if not exists layout_name text,
  add column if not exists report_title text,
  add column if not exists format_number text,
  add column if not exists format_revision text,
  add column if not exists revision_date date,
  add column if not exists default_sample_size integer not null default 1,
  add column if not exists source_template_name text,
  add column if not exists source_template_path text,
  add column if not exists remarks text;
alter table public.inspection_plans drop constraint if exists inspection_plans_layout_type_check;
alter table public.inspection_plans add constraint inspection_plans_layout_type_check check(layout_type in ('DIMENSIONAL','METLAB'));
alter table public.inspection_plans drop constraint if exists inspection_plans_default_sample_size_check;
alter table public.inspection_plans add constraint inspection_plans_default_sample_size_check check(default_sample_size between 1 and 20);

alter table public.inspection_plan_characteristics
  add column if not exists checking_aid_text text,
  add column if not exists report_section text,
  add column if not exists is_mandatory boolean not null default true,
  add column if not exists allow_na boolean not null default false,
  add column if not exists decimal_places integer not null default 3,
  add column if not exists source_row integer,
  add column if not exists layout_metadata jsonb not null default '{}'::jsonb,
  add column if not exists status text not null default 'ACTIVE';
alter table public.inspection_plan_characteristics drop constraint if exists inspection_plan_characteristics_status_check;
alter table public.inspection_plan_characteristics add constraint inspection_plan_characteristics_status_check check(status in ('ACTIVE','INACTIVE'));

alter table public.inspection_reports
  add column if not exists process_id uuid references public.processes(id),
  add column if not exists heat_number text,
  add column if not exists heat_code text,
  add column if not exists lot_quantity numeric,
  add column if not exists supplier_id uuid references public.parties(id),
  add column if not exists drawing_number text,
  add column if not exists drawing_revision text,
  add column if not exists prepared_by_employee_id uuid references public.employees(id),
  add column if not exists validated_by_employee_id uuid references public.employees(id),
  add column if not exists approved_by_employee_id uuid references public.employees(id),
  add column if not exists attachment_path text,
  add column if not exists source_layout_revision text,
  add column if not exists validated_at timestamptz,
  add column if not exists decision_at timestamptz;

alter table public.inspection_results
  add column if not exists sequence_no integer,
  add column if not exists unit text,
  add column if not exists applicability text not null default 'APPLICABLE',
  add column if not exists report_section text,
  add column if not exists observation_count integer not null default 1;
alter table public.inspection_results drop constraint if exists inspection_results_applicability_check;
alter table public.inspection_results add constraint inspection_results_applicability_check check(applicability in ('APPLICABLE','NOT_APPLICABLE'));
alter table public.inspection_results drop constraint if exists inspection_results_result_check;
alter table public.inspection_results add constraint inspection_results_result_check check(result in ('PASS','FAIL','NOT_EVALUATED','NOT_APPLICABLE'));

alter table public.lab_tests
  add column if not exists layout_plan_id uuid references public.inspection_plans(id),
  add column if not exists process_id uuid references public.processes(id),
  add column if not exists inspection_stage_id uuid references public.inspection_stages(id),
  add column if not exists heat_number text,
  add column if not exists heat_code text,
  add column if not exists prepared_by_employee_id uuid references public.employees(id),
  add column if not exists validated_by_employee_id uuid references public.employees(id),
  add column if not exists approved_by_employee_id uuid references public.employees(id),
  add column if not exists attachment_path text,
  add column if not exists validated_at timestamptz,
  add column if not exists decision_at timestamptz;

alter table public.inward_lots
  add column if not exists quality_disposition text not null default 'PENDING',
  add column if not exists quality_reason text,
  add column if not exists released_at timestamptz;
alter table public.inward_lots drop constraint if exists inward_lots_quality_disposition_check;
alter table public.inward_lots add constraint inward_lots_quality_disposition_check check(quality_disposition in ('PENDING','ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED'));
alter table public.inward_lots drop constraint if exists inward_lots_check1;
alter table public.inward_lots drop constraint if exists inward_lots_quality_release_check;
alter table public.inward_lots add constraint inward_lots_quality_release_check check(
  status <> 'RELEASED' or (
    quality_disposition in ('ACCEPTED','ACCEPTED_UNDER_RESERVE')
    and metallurgical_status in ('PASS','HOLD','NOT_REQUIRED')
    and dimensional_status in ('PASS','HOLD','NOT_REQUIRED')
  )
);

create index if not exists idx_inspection_plans_part_layout on public.inspection_plans(part_id,layout_type,process_id,inspection_stage_id,status);
create index if not exists idx_inspection_plan_characteristics_plan on public.inspection_plan_characteristics(inspection_plan_id,status,sequence_no);
create index if not exists idx_inspection_reports_inward_type on public.inspection_reports(inward_lot_id,report_type,status,decision_at desc);
create index if not exists idx_lab_tests_inward_type on public.lab_tests(inward_lot_id,test_type,status,decision_at desc);
create index if not exists idx_inward_lots_quality_gate on public.inward_lots(status,quality_disposition,heat_number,part_id);

insert into public.number_sequences(tenant_id,sequence_code,prefix,year_format,current_value,padding,reset_frequency)
select id,'DIMENSIONAL_REPORT',coalesce(nullif(plant_code,''),'D9')||'-DIR','YYYY',0,5,'YEARLY' from public.tenants
on conflict(tenant_id,sequence_code) do nothing;
insert into public.number_sequences(tenant_id,sequence_code,prefix,year_format,current_value,padding,reset_frequency)
select id,'METLAB_REPORT','MLAB-'||coalesce(nullif(plant_code,''),'D9'),'YYYY',0,5,'YEARLY' from public.tenants
on conflict(tenant_id,sequence_code) do nothing;

create or replace function public.qsms_module_for_table(target_table text) returns text language sql immutable as $$
select case
 when target_table in ('parts','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','document_attachments') then 'PART_MASTER'
 when target_table in ('material_grades','material_grade_elements') then 'MATERIAL_GRADE'
 when target_table in ('parties','part_supplier_links','processes','inspection_stages','quality_assets','jominy_distances','master_value_catalog') then 'REFERENCE_MASTERS'
 when target_table='employees' then 'EMPLOYEE_MASTER'
 when target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results') then 'RMTC_ENTRY'
 when target_table='inward_lots' then 'MATERIAL_INWARD'
 when target_table in ('inspection_plans','inspection_plan_characteristics') then 'INSPECTION_LAYOUTS'
 when target_table in ('inspection_reports','inspection_results') then 'DIMENSIONAL_REPORT'
 when target_table='lab_tests' then 'METLAB_REPORT'
 when target_table='user_module_permissions' then 'USER_ACCESS'
 else upper(target_table) end;
$$;

create or replace function public.can_write_table(target_table text) returns boolean language plpgsql stable security definer set search_path=public,auth as $$
declare role_name text:=coalesce(public.current_app_role(),'VIEWER');
begin
 if role_name='ADMIN' then return true; end if;
 if public.qsms_has_module_write(target_table) then return true; end if;
 if target_table in ('parties','material_grades','material_grade_elements','parts','part_supplier_links','part_raw_material_details','part_jominy_requirements','part_heat_treatment_details','processes','inspection_stages','master_value_catalog') then return role_name in ('QUALITY_MANAGER','MASTER_DATA');
 elsif target_table in ('employees','quality_assets') then return role_name in ('QUALITY_MANAGER','MASTER_DATA','QUALITY_ENGINEER');
 elsif target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results') then return role_name in ('QUALITY_MANAGER','METLAB_APPROVER','SQA');
 elsif target_table='inward_lots' then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA','PRODUCTION');
 elsif target_table in ('inspection_plans','inspection_plan_characteristics') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','MASTER_DATA');
 elsif target_table in ('inspection_reports','inspection_results') then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA');
 elsif target_table='lab_tests' then return role_name in ('QUALITY_MANAGER','QUALITY_ENGINEER','METLAB_APPROVER');
 end if; return false;
end;$$;

create or replace function public.qsms_has_module_approve(p_module_key text) returns boolean language sql stable security definer set search_path=public,auth as $$
select public.current_app_role()='ADMIN'
 or exists(select 1 from public.user_module_permissions p where p.profile_id=auth.uid() and p.tenant_id=public.current_tenant_id() and p.module_key=p_module_key and p.can_view and p.can_approve)
 or (p_module_key='DIMENSIONAL_REPORT' and public.current_app_role() in ('QUALITY_MANAGER','QUALITY_ENGINEER','SQA'))
 or (p_module_key='METLAB_REPORT' and public.current_app_role() in ('QUALITY_MANAGER','METLAB_APPROVER'));
$$;

create or replace function public.qsms_refresh_inward_quality_gate(p_inward_id uuid) returns jsonb language plpgsql security definer set search_path=public,auth as $$
declare v_inward public.inward_lots%rowtype;v_dim text:='PENDING';v_dim_reason text;v_met text:='PENDING';v_met_reason text;v_quality text:='PENDING';v_status text:='HOLD_PENDING_INSPECTION';v_met_status text:='PENDING';v_dim_status text:='PENDING';v_reason text;
begin
 select * into v_inward from public.inward_lots where id=p_inward_id for update;
 if v_inward.id is null then raise exception 'Material Inward record was not found'; end if;
 select disposition,disposition_reason into v_dim,v_dim_reason from public.inspection_reports where inward_lot_id=p_inward_id and report_type='DIMENSIONAL' and status='FINAL' order by decision_at desc nulls last,updated_at desc limit 1;
 select disposition,disposition_reason into v_met,v_met_reason from public.lab_tests where inward_lot_id=p_inward_id and test_type='METLAB' and status='FINAL' order by decision_at desc nulls last,updated_at desc limit 1;
 v_dim:=coalesce(v_dim,'PENDING');v_met:=coalesce(v_met,'PENDING');
 v_dim_status:=case v_dim when 'ACCEPTED' then 'PASS' when 'ACCEPTED_UNDER_RESERVE' then 'HOLD' when 'REJECTED' then 'FAIL' else 'PENDING' end;
 v_met_status:=case v_met when 'ACCEPTED' then 'PASS' when 'ACCEPTED_UNDER_RESERVE' then 'HOLD' when 'REJECTED' then 'FAIL' else 'PENDING' end;
 if v_dim='REJECTED' or v_met='REJECTED' then v_quality:='REJECTED';v_status:='REJECTED';
 elsif v_dim in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') and v_met in ('ACCEPTED','ACCEPTED_UNDER_RESERVE') then
   v_quality:=case when v_dim='ACCEPTED_UNDER_RESERVE' or v_met='ACCEPTED_UNDER_RESERVE' then 'ACCEPTED_UNDER_RESERVE' else 'ACCEPTED' end;v_status:='RELEASED';
 end if;
 v_reason:=nullif(concat_ws(' | ',case when v_met in ('ACCEPTED_UNDER_RESERVE','REJECTED') then 'MetLAB: '||coalesce(v_met_reason,'') end,case when v_dim in ('ACCEPTED_UNDER_RESERVE','REJECTED') then 'Dimensional: '||coalesce(v_dim_reason,'') end),'');
 update public.inward_lots set metallurgical_status=v_met_status,dimensional_status=v_dim_status,quality_disposition=v_quality,quality_reason=v_reason,status=v_status,released_at=case when v_status='RELEASED' then coalesce(released_at,now()) else null end,updated_at=now(),updated_by=auth.uid() where id=p_inward_id;
 return jsonb_build_object('inward_id',p_inward_id,'metlab_disposition',v_met,'dimensional_disposition',v_dim,'quality_disposition',v_quality,'status',v_status);
end;$$;

create or replace function public.qsms_sync_inward_quality_gate() returns trigger language plpgsql security definer set search_path=public,auth as $$begin if new.inward_lot_id is not null then perform public.qsms_refresh_inward_quality_gate(new.inward_lot_id);end if;return new;end;$$;

create or replace function public.qsms_finalize_dimensional_report(p_report_id uuid,p_disposition text,p_reason text,p_validated_by_employee_id uuid,p_approved_by_employee_id uuid) returns jsonb language plpgsql security definer set search_path=public,auth as $$
declare v_report public.inspection_reports%rowtype;v_bad integer;v_disposition text:=upper(btrim(coalesce(p_disposition,'')));
begin
 if not public.qsms_has_module_approve('DIMENSIONAL_REPORT') then raise exception 'Dimensional Report approval permission is required';end if;
 if v_disposition not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED') then raise exception 'Select Accepted, Accepted Under Reserve or Rejected';end if;
 if v_disposition in ('ACCEPTED_UNDER_RESERVE','REJECTED') and btrim(coalesce(p_reason,''))='' then raise exception 'A reserve or rejection reason is mandatory';end if;
 select * into v_report from public.inspection_reports where id=p_report_id and tenant_id=public.current_tenant_id() for update;if v_report.id is null then raise exception 'Dimensional report was not found';end if;
 select count(*) into v_bad from public.inspection_results where inspection_report_id=p_report_id and result not in ('PASS','NOT_APPLICABLE');
 if v_disposition='ACCEPTED' and v_bad>0 then raise exception 'Accepted is allowed only when every applicable characteristic passes';end if;
 update public.inspection_reports set disposition=v_disposition,disposition_reason=nullif(btrim(coalesce(p_reason,'')),''),validated_by_employee_id=p_validated_by_employee_id,approved_by_employee_id=p_approved_by_employee_id,validated_at=now(),decision_at=now(),status='FINAL',overall_result=case when v_disposition='REJECTED' then 'FAIL' when v_disposition='ACCEPTED_UNDER_RESERVE' then 'HOLD' else 'PASS' end,updated_at=now(),updated_by=auth.uid() where id=p_report_id;
 return public.qsms_refresh_inward_quality_gate(v_report.inward_lot_id);
end;$$;

create or replace function public.qsms_finalize_metlab_report(p_report_id uuid,p_disposition text,p_reason text,p_validated_by_employee_id uuid,p_approved_by_employee_id uuid) returns jsonb language plpgsql security definer set search_path=public,auth as $$
declare v_report public.lab_tests%rowtype;v_disposition text:=upper(btrim(coalesce(p_disposition,'')));v_bad integer:=0;
begin
 if not public.qsms_has_module_approve('METLAB_REPORT') then raise exception 'MetLAB Report approval permission is required';end if;
 if v_disposition not in ('ACCEPTED','ACCEPTED_UNDER_RESERVE','REJECTED') then raise exception 'Select Accepted, Accepted Under Reserve or Rejected';end if;
 if v_disposition in ('ACCEPTED_UNDER_RESERVE','REJECTED') and btrim(coalesce(p_reason,''))='' then raise exception 'A reserve or rejection reason is mandatory';end if;
 select * into v_report from public.lab_tests where id=p_report_id and tenant_id=public.current_tenant_id() for update;if v_report.id is null then raise exception 'MetLAB report was not found';end if;
 select count(*) into v_bad from jsonb_array_elements(coalesce(v_report.results->'rows','[]'::jsonb)) item where coalesce(item->>'result','NOT_EVALUATED') not in ('PASS','NOT_APPLICABLE');
 if v_disposition='ACCEPTED' and v_bad>0 then raise exception 'Accepted is allowed only when every applicable test result passes';end if;
 update public.lab_tests set disposition=v_disposition,disposition_reason=nullif(btrim(coalesce(p_reason,'')),''),validated_by_employee_id=p_validated_by_employee_id,approved_by_employee_id=p_approved_by_employee_id,validated_at=now(),decision_at=now(),status='FINAL',overall_result=case when v_disposition='REJECTED' then 'FAIL' when v_disposition='ACCEPTED_UNDER_RESERVE' then 'HOLD' else 'PASS' end,updated_at=now(),updated_by=auth.uid() where id=p_report_id;
 return public.qsms_refresh_inward_quality_gate(v_report.inward_lot_id);
end;$$;

drop trigger if exists trg_sync_inward_from_dimensional on public.inspection_reports;
create trigger trg_sync_inward_from_dimensional after insert or update of disposition,status,inward_lot_id on public.inspection_reports for each row execute function public.qsms_sync_inward_quality_gate();
drop trigger if exists trg_sync_inward_from_metlab on public.lab_tests;
create trigger trg_sync_inward_from_metlab after insert or update of disposition,status,inward_lot_id on public.lab_tests for each row execute function public.qsms_sync_inward_quality_gate();

revoke all on function public.qsms_refresh_inward_quality_gate(uuid) from public,anon;
revoke all on function public.qsms_finalize_dimensional_report(uuid,text,text,uuid,uuid) from public,anon;
revoke all on function public.qsms_finalize_metlab_report(uuid,text,text,uuid,uuid) from public,anon;
grant execute on function public.qsms_refresh_inward_quality_gate(uuid) to authenticated;
grant execute on function public.qsms_finalize_dimensional_report(uuid,text,text,uuid,uuid) to authenticated;
grant execute on function public.qsms_finalize_metlab_report(uuid,text,text,uuid,uuid) to authenticated;
commit;
