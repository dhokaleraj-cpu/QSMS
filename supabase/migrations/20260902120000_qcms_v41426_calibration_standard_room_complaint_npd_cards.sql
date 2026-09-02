-- QCMS v4.14.26 — Calibration & Validation, Standard Room inspection, complaint media/export and NPD card notifications.
-- Additive only. Existing production/master/quality/RMTC/OSP/Supply Chain data is preserved.
begin;

alter table public.quality_assets add column if not exists service_type text not null default 'CALIBRATION';
alter table public.quality_assets add column if not exists validation_frequency_days integer;
alter table public.quality_assets add column if not exists last_validation_date date;
alter table public.quality_assets add column if not exists next_validation_due_date date;

create table if not exists public.quality_asset_part_process_links (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  asset_id uuid not null references public.quality_assets(id) on delete restrict,
  part_id uuid not null references public.parts(id) on delete restrict,
  process_id uuid references public.processes(id) on delete restrict,
  service_type text not null default 'CALIBRATION' check (service_type in ('CALIBRATION','VALIDATION','BOTH')),
  frequency_days integer not null default 365 check (frequency_days > 0),
  characteristic_use text,
  last_service_date date,
  next_due_date date,
  responsible_employee_id uuid references public.employees(id) on delete set null,
  status text not null default 'ACTIVE' check (status in ('ACTIVE','INACTIVE')),
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid() references auth.users(id),
  updated_by uuid default auth.uid() references auth.users(id)
);
create index if not exists idx_qcms_asset_part_process_due on public.quality_asset_part_process_links(tenant_id,status,next_due_date);
create index if not exists idx_qcms_asset_part_process_asset on public.quality_asset_part_process_links(tenant_id,asset_id,part_id,process_id);

create table if not exists public.quality_asset_calibration_records (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  link_id uuid references public.quality_asset_part_process_links(id) on delete set null,
  asset_id uuid not null references public.quality_assets(id) on delete restrict,
  record_type text not null check (record_type in ('CALIBRATION','VALIDATION')),
  service_date date not null,
  result text not null default 'ACCEPTED' check (result in ('ACCEPTED','REJECTED','LIMITED_USE','PENDING')),
  report_number text,
  certificate_number text,
  calibration_agency text,
  performed_by_employee_id uuid references public.employees(id) on delete set null,
  next_due_date date,
  status text not null default 'VALID' check (status in ('VALID','REJECTED','PENDING','SUPERSEDED')),
  remarks text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid() references auth.users(id),
  updated_by uuid default auth.uid() references auth.users(id)
);
create index if not exists idx_qcms_asset_calibration_due on public.quality_asset_calibration_records(tenant_id,asset_id,next_due_date);

create table if not exists public.standard_room_inspection_records (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  inspection_date date not null default current_date,
  instrument_asset_id uuid references public.quality_assets(id) on delete set null,
  instrument_type text not null,
  part_id uuid not null references public.parts(id) on delete restrict,
  process_id uuid references public.processes(id) on delete set null,
  heat_number text,
  batch_code text,
  report_number text,
  quantity_inspected numeric not null default 1 check (quantity_inspected >= 0),
  inspection_status text not null default 'PENDING' check (inspection_status in ('PASS','FAIL','HOLD','PENDING')),
  program_reference text,
  operator_employee_id uuid references public.employees(id) on delete set null,
  remarks text,
  status text not null default 'ACTIVE' check (status in ('ACTIVE','VOID')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid default auth.uid() references auth.users(id),
  updated_by uuid default auth.uid() references auth.users(id)
);
create index if not exists idx_qcms_standard_room_part_date on public.standard_room_inspection_records(tenant_id,part_id,inspection_date desc);
create index if not exists idx_qcms_standard_room_instrument on public.standard_room_inspection_records(tenant_id,instrument_asset_id,inspection_date desc);

-- Shared module routing for the new transaction tables.
create or replace function public.qsms_module_for_table(target_table text)
returns text language sql immutable set search_path=public as $$
select case
 when target_table in ('parts','part_material_grade_links','part_raw_material_details','part_raw_material_technical_data','part_supplier_price_history','part_jominy_requirements','part_heat_treatment_details','part_rmtc_requirements','part_process_specifications','part_process_parameter_specifications','part_metallurgical_requirements','document_attachments','part_standard_links') then 'PART_MASTER'
 when target_table in ('material_grades','material_grade_elements') then 'MATERIAL_GRADE'
 when target_table in ('parties','part_supplier_links','processes','inspection_stages','quality_assets','jominy_distances','master_value_catalog','standards_register','calculation_rules','customer_standards','company_branches') then 'REFERENCE_MASTERS'
 when target_table='employees' then 'EMPLOYEE_MASTER'
 when target_table in ('rmtc_approvals','rmtc_part_approvals','rmtc_chemistry_results','rmtc_jominy_results','rmtc_requirement_results','rmtc_decision_revisions') then 'RMTC_ENTRY'
 when target_table='inward_lots' then 'MATERIAL_INWARD'
 when target_table in ('production_batches','batch_movements','osp_jobs','osp_receipts') then 'OSP_TRANSACTIONS'
 when target_table in ('inspection_plans','inspection_plan_characteristics','test_plans') then 'INSPECTION_LAYOUTS'
 when target_table in ('inspection_reports','inspection_results') then 'DIMENSIONAL_REPORT'
 when target_table='lab_tests' then 'METLAB_REPORT'
 when target_table in ('npd_process_flows','npd_process_flow_steps','npd_process_flow_points','npd_orders','npd_order_steps','npd_order_step_points','ppap_projects','ppap_documents','pfd_headers','pfd_steps','pfmea_headers','pfmea_items','control_plan_headers','control_plan_items','spc_plans','spc_studies','spc_readings','msa_plans','msa_studies','msa_readings','capacity_studies','balloon_characteristics') then 'NPD_APQP'
 when target_table='qc_calculation_records' then 'QC_CALCULATION_TOOLS'
 when target_table in ('quality_complaints','quality_complaint_followups','quality_complaint_actions') then 'COMPLAINT_MANAGEMENT'
 when target_table in ('quality_asset_part_process_links','quality_asset_calibration_records','standard_room_inspection_records') then 'CALIBRATION_VALIDATION'
 when target_table in ('supply_customer_orders','supply_purchase_orders','supply_purchase_order_items','supply_purchase_order_sources','supply_opening_stock','supply_rm_purchase_orders','supply_rm_receipts','supply_forging_orders','supply_rm_dispatches','supply_forging_receipts','supply_downstream_events','supply_po_confirmations') then 'SUPPLY_CHAIN'
 when target_table in ('user_module_permissions','user_section_permissions','department_module_defaults','role_module_defaults','qcms_module_approval_routes','supply_stage_responsibilities','qcms_user_activity_log') then 'USER_ACCESS'
 else upper(target_table) end;
$$;

create or replace function public.qsms_attachment_module(p_entity_type text) returns text
language sql immutable set search_path=public as $$
select case upper(coalesce(p_entity_type,''))
 when 'RMTC' then 'RMTC_ENTRY'
 when 'MATERIAL_INWARD' then 'MATERIAL_INWARD'
 when 'PART_MASTER' then 'PART_MASTER'
 when 'PART_PROCESS_SPEC' then 'PART_MASTER'
 when 'CUSTOMER_STANDARD' then 'REFERENCE_MASTERS'
 when 'QUALITY_COMPLAINT' then 'COMPLAINT_MANAGEMENT'
 when 'DIMENSIONAL_REPORT' then 'DIMENSIONAL_REPORT'
 when 'METLAB_REPORT' then 'METLAB_REPORT'
 when 'SUPPLY_CUSTOMER_ORDER' then 'SUPPLY_CHAIN'
 when 'SUPPLY_PURCHASE_ORDER' then 'SUPPLY_CHAIN'
 when 'PO_CONFIRMATION' then 'SUPPLY_CHAIN'
 when 'OSP_JOB' then 'OSP_TRANSACTIONS'
 when 'QUALITY_ASSET' then 'CALIBRATION_VALIDATION'
 when 'CALIBRATION_RECORD' then 'CALIBRATION_VALIDATION'
 when 'STANDARD_ROOM_INSPECTION' then 'CALIBRATION_VALIDATION'
 else null end;
$$;

-- Tenant + module permission RLS.
alter table public.quality_asset_part_process_links enable row level security;
alter table public.quality_asset_calibration_records enable row level security;
alter table public.standard_room_inspection_records enable row level security;

do $$ declare t text; begin
  foreach t in array array['quality_asset_part_process_links','quality_asset_calibration_records','standard_room_inspection_records'] loop
    execute format('drop policy if exists tenant_select on public.%I',t);
    execute format('create policy tenant_select on public.%I for select to authenticated using (tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission(''CALIBRATION_VALIDATION'',''view''))',t);
    execute format('drop policy if exists tenant_insert on public.%I',t);
    execute format('create policy tenant_insert on public.%I for insert to authenticated with check (tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission(''CALIBRATION_VALIDATION'',''create''))',t);
    execute format('drop policy if exists tenant_update on public.%I',t);
    execute format('create policy tenant_update on public.%I for update to authenticated using (tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission(''CALIBRATION_VALIDATION'',''edit'')) with check (tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission(''CALIBRATION_VALIDATION'',''edit''))',t);
    execute format('drop policy if exists tenant_delete on public.%I',t);
    execute format('create policy tenant_delete on public.%I for delete to authenticated using (tenant_id=public.current_tenant_id() and public.qcms_effective_module_permission(''CALIBRATION_VALIDATION'',''archive''))',t);
    execute format('grant select,insert,update,delete on public.%I to authenticated',t);
  end loop;
end $$;

-- Update timestamps and full audit trail.
drop trigger if exists trg_touch_updated_at on public.quality_asset_part_process_links;
create trigger trg_touch_updated_at before update on public.quality_asset_part_process_links for each row execute function public.touch_updated_at();
drop trigger if exists trg_touch_updated_at on public.quality_asset_calibration_records;
create trigger trg_touch_updated_at before update on public.quality_asset_calibration_records for each row execute function public.touch_updated_at();
drop trigger if exists trg_touch_updated_at on public.standard_room_inspection_records;
create trigger trg_touch_updated_at before update on public.standard_room_inspection_records for each row execute function public.touch_updated_at();

drop trigger if exists trg_audit_row_change on public.quality_asset_part_process_links;
create trigger trg_audit_row_change after insert or update or delete on public.quality_asset_part_process_links for each row execute function public.log_row_change();
drop trigger if exists trg_audit_row_change on public.quality_asset_calibration_records;
create trigger trg_audit_row_change after insert or update or delete on public.quality_asset_calibration_records for each row execute function public.log_row_change();
drop trigger if exists trg_audit_row_change on public.standard_room_inspection_records;
create trigger trg_audit_row_change after insert or update or delete on public.standard_room_inspection_records for each row execute function public.log_row_change();

-- Default permission profiles. Explicit user permissions remain authoritative.
insert into public.role_module_defaults(tenant_id,role,module_key,can_view,can_create,can_edit,can_validate,can_approve,can_archive,status)
select t.id,v.role,'CALIBRATION_VALIDATION',true,v.write,v.write,v.validate,v.approve,v.archive,'ACTIVE'
from public.tenants t cross join (values
 ('QUALITY_MANAGER',true,true,true,true),
 ('QUALITY_ENGINEER',true,true,false,false),
 ('METLAB_APPROVER',true,true,false,false),
 ('MASTER_DATA',true,false,false,false),
 ('MANAGEMENT',true,true,true,true),
 ('VIEWER',false,false,false,false),
 ('AUDITOR',false,false,false,false)
) v(role,write,validate,approve,archive)
on conflict(tenant_id,role,module_key) do update set
 can_view=excluded.can_view,can_create=excluded.can_create,can_edit=excluded.can_edit,
 can_validate=excluded.can_validate,can_approve=excluded.can_approve,can_archive=excluded.can_archive,status='ACTIVE',updated_at=now();

insert into public.department_module_defaults(tenant_id,department,module_key,can_view,can_create,can_edit,can_validate,can_approve,can_archive,status)
select t.id,v.department,'CALIBRATION_VALIDATION',true,v.write,v.write,v.validate,v.approve,v.archive,'ACTIVE'
from public.tenants t cross join (values
 ('Quality',true,true,true,true),
 ('METLAB',true,true,false,false),
 ('Management',true,true,true,true)
) v(department,write,validate,approve,archive)
on conflict(tenant_id,department,module_key) do update set
 can_view=excluded.can_view,can_create=excluded.can_create,can_edit=excluded.can_edit,
 can_validate=excluded.can_validate,can_approve=excluded.can_approve,can_archive=excluded.can_archive,status='ACTIVE',updated_at=now();

-- Daily one-month-ahead calibration / validation reminders to Quality until service is completed.
insert into public.qcms_email_templates
(tenant_id,template_key,module_key,template_name,subject_template,body_template,include_generated_pdf,include_record_attachments,include_supplier,enabled)
select t.id,'CALIBRATION_VALIDATION_DUE_DIGEST','CALIBRATION_VALIDATION','Calibration / Validation Due Digest',
 'QCMS · Gauge / Fixture Calibration & Validation Due · {{report_date}}',
 'Dear Quality Team,\n\nAttached is the current QCMS Gauge / Fixture Calibration & Validation due report.\nDue within 30 days: {{open_count}}\nOverdue: {{overdue_count}}\nReport Date: {{report_date}}\n\nQCMS will repeat this reminder daily until the applicable Calibration / Validation record is completed.\n\nRegards,\nQCMS',
 true,false,false,true
from public.tenants t
on conflict(tenant_id,template_key) do update set module_key=excluded.module_key,template_name=excluded.template_name,subject_template=excluded.subject_template,body_template=excluded.body_template,enabled=true,updated_at=now();

insert into public.qcms_notification_schedules
(tenant_id,schedule_key,module_key,event_key,schedule_label,enabled,hour_local,timezone,days_ahead,include_overdue,include_open,recipient_department,include_suppliers,template_key)
select t.id,'CALIBRATION_VALIDATION_DUE','CALIBRATION_VALIDATION','CALIBRATION_VALIDATION_DUE_DIGEST','Calibration / Validation · Due within 30 days',true,8,'Asia/Kolkata',30,true,true,'Quality',false,'CALIBRATION_VALIDATION_DUE_DIGEST'
from public.tenants t
on conflict(tenant_id,schedule_key) do update set module_key=excluded.module_key,event_key=excluded.event_key,schedule_label=excluded.schedule_label,enabled=true,hour_local=8,timezone='Asia/Kolkata',days_ahead=30,include_overdue=true,include_open=true,recipient_department='Quality',include_suppliers=false,template_key=excluded.template_key,updated_at=now();

-- Controlled delete routing for calibration and Standard Room transactions.
create or replace function public.qcms_delete_transaction_row(p_table_name text,p_record_id uuid)
returns jsonb language plpgsql security definer set search_path='public','auth' as $$
declare tid uuid:=public.current_tenant_id(); module_name text:=public.qsms_module_for_table(p_table_name); deleted_count integer:=0;
allowed_tables constant text[]:=array['supply_customer_orders','supply_purchase_orders','supply_po_confirmations','supply_rm_purchase_orders','supply_rm_receipts','supply_rm_dispatches','supply_forging_orders','supply_forging_receipts','supply_downstream_events','supply_opening_stock','osp_jobs','osp_receipts','rmtc_approvals','inward_lots','inspection_reports','lab_tests','npd_orders','npd_process_flows','ppap_projects','pfd_headers','pfmea_headers','control_plan_headers','spc_studies','msa_studies','capacity_studies','qc_calculation_records','quality_complaints','quality_asset_part_process_links','quality_asset_calibration_records','standard_room_inspection_records'];
begin
 if auth.uid() is null or tid is null then raise exception 'Authenticated QCMS session required'; end if;
 if p_table_name is null or not(p_table_name=any(allowed_tables)) then raise exception 'Controlled transaction deletion is not enabled for this record type'; end if;
 if not public.qcms_effective_module_permission(module_name,'archive') then raise exception 'Delete/Archive permission is not assigned for %',module_name; end if;
 if p_table_name='osp_jobs' then return public.qcms_delete_osp_transaction(p_record_id); end if;
 if p_table_name='osp_receipts' then return public.qcms_delete_osp_receipt(p_record_id); end if;
 execute format('delete from public.%I where id=$1 and tenant_id=$2',p_table_name) using p_record_id,tid; get diagnostics deleted_count=row_count;
 if deleted_count=0 then raise exception 'Selected transaction was not found or is outside your company tenant'; end if;
 return jsonb_build_object('deleted',true,'table',p_table_name,'id',p_record_id,'module',module_name,'deleted_by',auth.uid());
exception when foreign_key_violation then raise exception 'This transaction has downstream linked records. Delete or reverse the dependent stage first; QCMS will not break genealogy.';
end $$;
revoke all on function public.qcms_delete_transaction_row(text,uuid) from public,anon;
grant execute on function public.qcms_delete_transaction_row(text,uuid) to authenticated;

create or replace function public.qcms_release_schema_version() returns text
language sql immutable set search_path='pg_catalog' as $$ select '4.14.26'::text $$;
revoke all on function public.qcms_release_schema_version() from public;
grant execute on function public.qcms_release_schema_version() to authenticated,service_role;

insert into public.qcms_release_schema_state(version,build,applied_at,details)
values('4.14.26','41426-COMPLAINT-MEDIA-CALIBRATION-STANDARD-ROOM-NPD-CARDS',now(),jsonb_build_object('calibration_validation',true,'standard_room',true,'complaint_media',true,'npd_cards',true))
on conflict(version) do update set build=excluded.build,applied_at=excluded.applied_at,details=excluded.details;

commit;
